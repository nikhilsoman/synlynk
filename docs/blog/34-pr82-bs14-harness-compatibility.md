---
post: 34
pr: "#82"
merged: 2026-07-01
---

# PR #82 — BS-14 Harness Compatibility System

## The Broader Goal at the End of the Previous PR

At the close of the BS-5 website sprint (PRs #78–#81), synlynk had a working four-agent dispatch loop — Claude, Agy, Grok, Codex — with sentinel observability and a growing test suite. The stated goal was a **Developer Preview (v0.10.0)**: pipx packaging, README, and `synlynk viz`. LIVE-1 changed the priority order.

## Strategic Shifts in This PR

LIVE-1 (#81) exposed a class of failure that made the Developer Preview untenable: Agy jobs were silently hanging for 6+ hours with zero output, and Grok was receiving `--always-approve` — a flag its CLI actively rejects — on every dispatch. Both failures were invisible to the sentinel system. No alert, no kill, no retry. The user discovered them manually.

The insight: synlynk worked well when Claude was the harness. In every other harness it was brittle in different ways. That's the opposite of a composable dispatch layer.

BS-14 was pulled forward from its pre-GA slot to become the immediate priority: build the infrastructure that makes synlynk behaviour consistent regardless of which agent CLI is running. Not polishing the wrapper — hardening the contract between synlynk and each harness.

## What This PR Shipped

### Phase 1 — v0.10.1: LIVE-1 Fixes

**Agy baseline correction.** The root cause of the 6h hang: `AGENT_CAPABILITY_BASELINES["agy"]` had `required_flags: ["--non-interactive"]` — a flag that doesn't exist in the Agy CLI. Every Agy job launched and crashed silently before producing any output. Fixed by removing `--non-interactive` from `required_flags`, adding it to `invalid_flags`, and documenting that Agy's non-interactive mode is `-p`/`--print` (already handled via the existing `prompt_via_arg: True` + `prompt_flag: "-p"` path). `headless_contract` updated with `requires_pty: False`, `stdout_flush_method: unbuffered`, `env_vars_required: ["PYTHONUNBUFFERED=1"]`.

**Grok baseline correction.** `--always-approve` moved from the dispatch path to `invalid_flags`. `network_deps` added with `required_endpoints: ["cli-chat-proxy.grok.com:443"]` — Grok's CLI proxy endpoint that every dispatch depends on.

**`_check_job_stall()` — STALL_NO_OUTPUT sentinel.** Replaces the old global `check_stall()` (job-global, state-file-based) with a per-job log-byte check inside `_reconcile_jobs()`. If a running job's log file is still 0 bytes after a configurable timeout (`stall_timeout_minutes`, global default 30, per-agent override in `.synlynk/config.json`), the job process receives SIGKILL and the `STALL_NO_OUTPUT` sentinel fires. The 6h Agy hang would have been caught at 30 minutes.

**`_preflight_dispatch()` — HARNESS_PREFLIGHT_FAIL sentinel.** Called at the top of every `dispatch_agent()` invocation, before any subprocess is spawned. Two checks: (1) flag validation — any flag in the agent's `invalid_flags` set blocks dispatch immediately; (2) network reachability — TCP connect (2s timeout) to every `required_endpoint`. Returns `{"passed": bool, "sentinel": str, "reason": str}`. If not passed: writes sentinel, raises `RuntimeError` — no subprocess spawned. Adds ~2s worst case when a network endpoint is unreachable; fast-path exits in <1ms on flag failures.

### Phase 2 — v0.11.0: Full Harness Compatibility System

**Five new `state.db` tables via `_migrate_db()`.** All idempotent (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`):

- `harness_baselines` — curated capability snapshots keyed by `(harness_name, cli_version)`
- `harness_records` — live per-agent state: `installed_version`, `compliance_status`, `active_contract`, `capability_hash`, `last_probe_at`
- `harness_verb_map` — cross-harness interoperability matrix (see below)
- `harness_command_palette` — full `--help` tree per harness, with `first_seen_version` / `last_seen_version` for removal detection
- `harness_version_history` — append-only log of `version_change`, `drift_detected`, `doctor_run` events

**`harness` + `model` fields in `.agents/<agent>.json`.** `_load_agent_profile()` updated to `setdefault("harness", agent_name)` and `setdefault("model", "unknown")`. `.agents/claude.json`, `.agents/codex.json` created. `.agents/agy.json` and `.agents/grok.json` already existed from Phase 1.

**`_probe_agent()` + `synlynk probe`.** The probe trigger chain:
1. Run `agent --version` (5s timeout) to fingerprint installed CLI
2. Fast-path: if `harness_records` shows matching version + capability hash → `{"skipped": True}` (no further work)
3. Full probe: compute `_compute_capability_hash()` (SHA256[:16] of `headless_contract` + `dispatch_flags`), run network preflight, upsert `harness_records`, append `harness_version_history` on `version_change` or `drift_detected`, scan command palette, write instruction fence
4. `synlynk probe [--agent NAME]` CLI subcommand

**`_compute_capability_hash()`.** 16-char SHA256 of `{"contract": headless_contract, "flags": dispatch_flags}` JSON (keys sorted). Stable fingerprint for fast-path skip and drift detection.

**`synlynk doctor` TC-1–TC-4 compliance suite.** Four checks per agent:
- TC-1 (`_run_tc1`): Spawn agent with non-interactive flag in pipe mode; if `communicate()` times out → `requires_pty: True`, `passed: False`
- TC-2 (`_run_tc2`): Check `invalid_flags` list + grep `--help` output for `valid_flags` presence; failed flags returned
- TC-3 (`_run_tc3`): TCP connect to each `required_endpoint`; unreachable list returned
- TC-4 (`_run_tc4`): For each active verb in `harness_verb_map`, verify the mapped command exists (`--help` reachable); failed verbs returned

Results update `harness_records.compliance_status` and append a `doctor_run` history row.

**`_VERB_MAP_SEED` — 64-row Command Interoperability Matrix.** Full synlynk verb surface mapped across all four agents across five categories:

| Category | Verbs |
|---|---|
| dispatch | `dispatch.task`, `dispatch.headless`, `dispatch.resume`, `dispatch.approve`, `dispatch.model`, `dispatch.tools`, `dispatch.context` |
| observability | `jobs`, `status`, `telemetry`, `costs` |
| harness | `probe`, `doctor` |
| pm | `story`, `epic`, `decide` |
| workspace | `workspace`, `upgrade` |

Each cell is `full` / `partial` (with notes) / `none`. `none` blocks; `partial` warns. `_check_verb_support(verb, agent_name, db)` returns the lookup result. Extension opportunities — verbs where a harness has a native command but synlynk has no mapping — surface as `synlynk_verb IS NULL` rows from palette scan.

**`_scan_command_palette()`.** Parses `agent --help` stdout+stderr with two regex patterns: flags (`--flag  description`) and subcommands (`word word  description`). Inserts new commands with `first_seen_version`; marks removed commands (previously active, now absent) with `last_seen_version = current_version`. Called from `_probe_agent()` after `harness_records` upsert.

**Instruction fence — `_upsert_harness_fence()`.** Idempotent managed section in agent instruction files (CLAUDE.md, GEMINI.md, AGENTS.md, GROK.md). Format:

```
<!-- synlynk:harness v{version} verified:{ts} -->
# Harness Instructions (synlynk-managed — do not edit)

## Headless Execution Contract
...
<!-- /synlynk:harness -->
```

Regex-replaces the existing fence block if present; appends if absent. Byte-preserves all content outside the fence. Human-authored content above and below is never touched. `_build_fence_body_from_record()` populates the block from `harness_records` (falls back to `AGENT_CAPABILITY_BASELINES` if no DB record yet). Called from `_probe_agent()`.

**`HARNESS_VERSION_DRIFT` sentinel.** Wired into `_preflight_dispatch()`. On every dispatch, if `harness_records.last_probe_at` is >1hr stale: spawn `agent --version` (3s timeout), compare to recorded version. If different: fire `WARNING HARNESS_VERSION_DRIFT` (non-blocking — dispatch continues). Instructs the user to run `synlynk probe`.

### Code review findings (fixed in same PR)

One post-implementation review finding: `dispatch_agent()` had a `try/except TypeError` fallback to a single-arg `_preflight_dispatch(agent)` call — a migration artifact from an earlier partial implementation. Removed. All 29 test monkeypatches updated from `lambda agent: None` to `lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, ...}`.

### Test surface

- `tests/test_harness_compatibility.py` — new file, 13 tests covering: probe fast-path, harness_records upsert, version_change history, TC-1–TC-3, palette scan + removal, fence upsert (replace / append / skip missing / byte-preservation), drift sentinel
- `tests/test_synlynk.py` — 18 new tests for grok/agy baselines, stall detection, preflight flag + network blocking, agent-json roundtrip
- **503 tests passing** total

## Brainstorm Visuals Used

Full visual brainstorm companion run at session start (2026-06-30). HTML files local-only (`.superpowers/brainstorm/` is gitignored). Key decisions informed by the visual session: hybrid approach (curated baselines + dynamic discovery), agent-vs-harness naming separation, managed fence ownership model, full verb surface scope for the interop matrix.

## What This Achieved on the Path to Autonomy

Before this PR, any autonomous dispatch to Agy would silently hang for hours. Any dispatch to Grok would fail at CLI startup. The system appeared to work because Claude-as-harness masked the incompatibilities.

BS-14 establishes the **contract layer** between synlynk and each agent harness: explicit headless execution contracts, validated flag maps, live network preflight, and a compliance test suite that runs on every probe. The instruction fence means agents now receive harness-specific execution guidance that synlynk manages automatically — it updates when the harness changes, not when a human remembers to update it.

The verb interoperability matrix is the first step toward capability-aware routing: knowing which verbs work on which harness at what fidelity is the prerequisite for synlynk deciding "this task should go to Codex, not Agy, because Agy has no `dispatch.resume` support."

## Strategic Note: The Goal at the End of This PR

The harness contract layer is in place. The next work items are:
- **v0.10.0 Developer Preview**: pipx packaging, pyproject.toml, README, `synlynk viz` (BS-6) — the launch milestone
- **BS-13 Live Job Observatory**: real-time SSE job streaming dashboard
- **BS-15 Native Harness**: synlynk as its own dispatch harness (no dependency on Claude CLI in the loop)

The four-agent fleet now dispatches correctly from any harness. Autonomous operation — where synlynk itself decides routing, monitors compliance, and repairs drift without human intervention — is structurally closer than it was yesterday.
