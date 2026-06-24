# Health Pulse — Silent Auto-Upgrade & Onboarding Auditor

**Date:** 2026-06-24  
**Status:** Approved for implementation  
**Target version:** v0.9.5  

---

## Goal

Run a silent health audit on every synlynk command. After the command completes, show at most one nudge line (the highest-priority pending check), with a separator above and below. If more nudges are pending, append a `+N more: synlynk doctor` count. Never interrupt the command itself; never pollute piped output.

---

## Architecture

### `HealthCheck` dataclass

```python
@dataclasses.dataclass
class HealthCheck:
    id: str            # "VERSION", "ONBOARDING", "AGENT_PROFILES", "IDENTITY", "TEAM_PULSE"
    priority: int      # 1=CRITICAL  2=HIGH  3=MEDIUM  4=LOW
    rearm_type: str    # "time" | "condition"
    interval_hours: int  # only used when rearm_type == "time"; ignored otherwise
    run: object        # callable → (nudge_msg, action_hint, rearm_key) | None
```

### Registry

A module-level `HEALTH_CHECKS: list[HealthCheck]` ordered by priority. Adding a new check = appending one entry. The runner (`health_pulse`) never changes when checks are added.

### State file

`.synlynk/health_state.json` — created on first run, updated after every shown nudge:

```json
{
  "VERSION":        { "last_run_ts": 0, "last_nudge_ts": 0, "rearm_key": "" },
  "ONBOARDING":     { "last_run_ts": 0, "last_nudge_ts": 0, "rearm_key": "" },
  "AGENT_PROFILES": { "last_run_ts": 0, "last_nudge_ts": 0, "rearm_key": "" },
  "IDENTITY":       { "last_run_ts": 0, "last_nudge_ts": 0, "rearm_key": "" },
  "TEAM_PULSE":     { "last_run_ts": 0, "last_nudge_ts": 0, "rearm_key": "" }
}
```

- `last_run_ts` — Unix timestamp of the last time the check's `run()` was called. Used to throttle expensive checks (network, git) so they don't execute on every invocation.
- `last_nudge_ts` — Unix timestamp of the last time this check's nudge was shown to the user.
- `rearm_key` — the last condition value that triggered a nudge. For condition-gated checks: if current key == stored key, nudge is suppressed. For time-gated checks: unused for suppression (time gate handles it).

### `health_pulse(command)` — runner

Called at the end of every command dispatch in `main()`. Execution flow:

1. Skip entirely if `command` is in the skip set: `{"upgrade", "init", "join", "doctor", "identity", None}`
2. Load `.synlynk/health_state.json` (create with defaults if missing)
3. For each `HealthCheck` in `HEALTH_CHECKS` (already priority-sorted):
   a. Apply run throttle: for time-gated checks (`rearm_type == "time"`), skip `run()` if `time.time() - last_run_ts < interval_hours * 3600` — use the stored `rearm_key` as the cached result. For condition-gated checks (`rearm_type == "condition"`), always call `run()` — they are filesystem-only and complete in <1ms.
   b. Call `check.run()` — returns `(nudge_msg, action_hint, rearm_key)` or `None`
   c. Update `last_run_ts` in state
   d. If `run()` returned `None` → no nudge pending for this check, continue
   e. Apply nudge gate:
      - time-gated: suppress if `time.time() - last_nudge_ts < interval_hours * 3600`
      - condition-gated: suppress if `rearm_key == state[id].rearm_key` and `last_nudge_ts > 0`
   f. If not suppressed → append `(priority, nudge_msg, action_hint, rearm_key, check.id)` to `pending`
4. If `pending` is empty → return silently
5. Sort `pending` by priority, take index 0 as `top`
6. Print nudge to `stderr`:
   ```
     ─────────────────────────────────────────
     ⚑  <nudge_msg>  →  <action_hint>[ · +N more: synlynk doctor]
     ─────────────────────────────────────────
   ```
7. Update state: set `last_nudge_ts = now` and `rearm_key = top.rearm_key` for `top.id`
8. Write updated state back to `.synlynk/health_state.json`

Network calls (version check) only happen when `last_run_ts` is stale. All other checks are filesystem-only and complete in <5ms.

### Call sites in `main()`

- `exec` branch: call `health_pulse(args.command)` after `exec_command()` returns, before `sys.exit(result)`
- All other branches: single `health_pulse(getattr(args, "command", None))` call at the end of `main()`, after all `elif` branches

---

## The 5 Checks

### 1. `ONBOARDING` — CRITICAL, condition-gated

**What it checks:**
- `.synlynk/config.json` exists
- `project-docs/` directory exists (or configured `_docs_dir()`)
- At least one AI instruction file exists: `CLAUDE.md`, `GEMINI.md`, or `AGENTS.md`

**`run()` logic:**
- If all three present → return `None`
- Otherwise → return `("project not fully initialized", "synlynk init", "present")` if any missing; rearm_key `"missing"` if all absent, `"partial"` if some missing

**Rearm key:** `"present"` (all good) | `"partial"` (some missing) | `"missing"` (nothing there). Re-arms the moment the key changes — e.g. if a user deletes `CLAUDE.md`, the key flips from `"present"` to `"partial"` and the nudge fires again.

---

### 2. `VERSION` — HIGH, time-gated (24h)

**What it checks:**
- Fetches latest release tag from `https://api.github.com/repos/nikhilsoman/synlynk/releases/latest` via `urllib.request` (same logic as existing `upgrade()`)
- Compares to `VERSION` constant

**`run()` logic:**
- On network failure → return `None` silently (never block on connectivity)
- If `latest == VERSION` → return `None`
- Otherwise → return `(f"v{VERSION} installed — v{latest} available", "synlynk upgrade", latest)`

**Rearm key:** the latest version string (e.g. `"0.9.5"`). Re-arms when a newer release appears, even if nudge was already shown for a previous version.

**Run throttle:** `interval_hours=24` — `run()` is only called (network hit) once per 24h. Between calls, the `rearm_key` stored in `health_state.json` from the last successful run is used to decide if a nudge is still pending. This means the version nudge persists across invocations (until dismissed by upgrading) without hitting the network each time.

---

### 3. `AGENT_PROFILES` — MEDIUM, condition-gated

**What it checks:**
- `.agents/` directory exists and contains at least one `.json` file

**`run()` logic:**
- If `.agents/` missing or empty → return `("no agent profiles configured", "synlynk agent configure claude", "empty")`
- Otherwise → return `None`

**Rearm key:** `"|".join(sorted(filenames))` — re-arms if profiles are deleted, so the nudge fires again for any new user who hasn't configured profiles.

---

### 4. `IDENTITY` — LOW, condition-gated

**What it checks:**
- `~/.synlynk/identity.key` exists

**`run()` logic:**
- If missing → return `("no identity key — capability ratings unsigned", "synlynk identity init", "missing")`
- Otherwise → return `None`

**Rearm key:** `"present"` | `"missing"`. One-time nudge; re-arms only if key is deleted.

---

### 5. `TEAM_PULSE` — LOW, time-gated (24h)

**What it checks:**
- Only runs when `project-docs/.synlynk_config.json` has `mode == "team"`
- Reads git contributors from last 30 days: `git log --format="%ae" --since="30 days ago"`
- Reads devlog filenames in `project-docs/devlogs/`
- Cross-references: contributors with no matching devlog file are "unlogged"

**`run()` logic:**
- If solo mode or git unavailable → return `None`
- If no unlogged contributors → return `None`
- Otherwise → return `(f"{n} contributor(s) have no synlynk devlog", "synlynk team status", ",".join(sorted(unlogged_emails)))`

**Rearm key:** sorted comma-joined list of unlogged contributor emails. Re-arms when a new contributor appears without a devlog.

---

## Output Format

Printed to `stderr`. Fixed separator width: 45 dashes. Uses existing colour constants.

**Single nudge:**
```
  ─────────────────────────────────────────
  ⚑  v0.9.3 installed — v0.9.4 available  →  synlynk upgrade
  ─────────────────────────────────────────
```

**With overflow:**
```
  ─────────────────────────────────────────
  ⚑  project not fully initialized  →  synlynk init  · +2 more: synlynk doctor
  ─────────────────────────────────────────
```

Colours: `_DIM` separators · `_YELLOW` for `⚑` · plain for nudge message · `_CYAN` for action hint · `_DIM` for `· +N more` suffix.

---

## `synlynk doctor` command

New command that runs all checks unconditionally (ignoring time gates and condition suppression) and prints every pending nudge with full detail:

```
  synlynk doctor

  ✓  onboarding       project fully initialized
  ✦  version          v0.9.3 installed — v0.9.4 available  →  synlynk upgrade
  ✦  agent profiles   no profiles in .agents/  →  synlynk agent configure claude
  ✓  identity         key present at ~/.synlynk/identity.key
  ✓  team pulse       all contributors have devlogs  (solo mode)
```

Exit code 0 if all checks pass, 1 if any check returns a nudge.

---

## Testing

Each `_check_*` function is tested independently via monkeypatch — no network, no filesystem side effects beyond a `tmp_path` fixture.

Key test cases:
- `test_health_pulse_skips_excluded_commands` — pulse returns immediately for `init`, `upgrade`, `doctor`, `join`, `identity`
- `test_health_pulse_no_output_when_no_nudges` — stderr empty when all checks pass
- `test_health_pulse_shows_highest_priority` — CRITICAL shown over HIGH when both pending
- `test_health_pulse_overflow_count` — `+N more` count correct
- `test_health_pulse_time_gate_suppresses` — nudge not shown if shown within 24h
- `test_health_pulse_condition_gate_suppresses` — nudge not shown if rearm_key unchanged
- `test_health_pulse_condition_gate_rearms` — nudge shown when rearm_key changes
- `test_check_onboarding_all_present` — returns None
- `test_check_onboarding_missing_config` — returns CRITICAL nudge
- `test_check_version_up_to_date` — returns None
- `test_check_version_stale` — returns HIGH nudge with correct version strings
- `test_check_version_network_failure` — returns None silently
- `test_check_agent_profiles_empty` — returns MEDIUM nudge
- `test_check_agent_profiles_populated` — returns None
- `test_check_identity_missing` — returns LOW nudge
- `test_check_identity_present` — returns None
- `test_check_team_pulse_solo_mode` — returns None
- `test_check_team_pulse_unlogged_contributor` — returns LOW nudge
- `test_doctor_command_all_pass` — exit 0, all ✓
- `test_doctor_command_with_failures` — exit 1, shows ✦ lines

---

## Files Changed

| File | Change |
|---|---|
| `synlynk/__init__.py` | Add `HealthCheck` dataclass, `HEALTH_CHECKS` registry, `_check_version()`, `_check_onboarding()`, `_check_agent_profiles()`, `_check_identity()`, `_check_team_pulse()`, `_load_health_state()`, `_save_health_state()`, `_should_run_check()`, `_should_show_nudge()`, `health_pulse()`, `cmd_doctor()`. Wire `health_pulse()` into `main()`. Add `doctor` subparser. |
| `tests/test_synlynk.py` | 20 new tests covering all check functions, runner logic, gates, and doctor command |
