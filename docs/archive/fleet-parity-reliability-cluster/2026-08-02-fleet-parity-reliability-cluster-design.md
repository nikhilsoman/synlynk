# Fleet-Parity Reliability Cluster — Design

**Status:** Draft, pending review
**Issues:** #340 (Codex sandbox blocks network for package installs), #342 (Grok has no CWD auto-relocation defense), #347 (no preflight verification that a dispatched agent loaded its instruction file)
**Precedes:** none — this is the reliability half of the fleet-parity audit; the security half (#348, #338) shipped as PR #641.

## Background

The fleet-parity audit (issues #332/#338/#340/#342/#347/#348/#419/#461) split into two severity clusters: security (an agent does more than it was granted — #348, #338, already shipped) and reliability (a job fails or drifts *without* exceeding its granted scope — #340, #342, #347, this spec). All three reliability issues are real gaps confirmed against the current codebase (post-#641-merge, `main@a16653d`).

1. **#340 — Codex's `workspace-write` sandbox blocks outbound network by default**, so any dispatched task that needs `pip install` / `.venv` setup / similar silently fails inside the sandbox. Confirmed live this session against the actually-installed `codex-cli 0.144.1`: `curl` to `https://pypi.org` fails with `curl: (6) Could not resolve host: pypi.org` under default `-s workspace-write`; adding `-c 'sandbox_workspace_write.network_access=true'` produces a `(network access enabled)` sandbox banner and a successful HTTP 200. This confirms the exact config key, which the original issue only speculated needed confirming.
2. **#342 — Grok has neither the `--cwd` flag passed on dispatch nor a prompt-level working-directory reminder**, the same class of risk that caused the Agy CWD fix in `8c1e124`. Confirmed via code read: `_format_prompt_for_agent()` (`synlynk/dispatch.py:772`) has dedicated branches for `codex` and `agy` but Grok falls into the generic fallback with no CWD reminder; no `--cwd`/`-C` flag is passed for Grok or Codex anywhere in `dispatch.py`.
3. **#347 — no preflight or postflight check confirms a dispatched agent actually loaded its injected instruction file** (CLAUDE.md / GEMINI.md / etc., marked with `<!-- synlynk:start version="X" tool="Y" -->` in `synlynk/instructions.py:158`). A dispatched job can silently operate against stale or absent instructions with no signal anywhere in `synlynk status`/`jobs`.

## Decisions Locked In (from brainstorming)

- **One bundled spec** covering all three issues, decomposed into independently-dispatchable tasks — matches the security cluster's precedent rather than three separate specs.
- **#340 gets the full fix, permission-gated** — not detection-only. A new permission (`run:install`) must be explicitly granted before Codex's sandbox network restriction is loosened; nothing changes for existing dispatches.
- **Reliability-severity issues are advisory, not fail-closed.** Unlike the security cluster's #348/#338 (which now refuse to dispatch when a restriction can't be enforced), #340/#342/#347 concern jobs that fail or drift *without exceeding granted scope* — the correct response is detect-and-surface (a `WARNING` sentinel, same tier as the existing `HARNESS_VERSION_DRIFT`), not blocking dispatch, except where noted below (#340's preflight probe, which is a real capability check, not a scope-enforcement gate).
- **#347 gets the cheapest implementation depth** (prompt-echo-and-grep, advisory-only) rather than a doctor-level smoke check or telemetry-only logging — those are explicit follow-ups, same treatment the security cluster gave aider `--read` and Agy `--sandbox`.
- **Baseline correction, not a fresh problem:** codex's `AGENT_CAPABILITY_BASELINES` entry already has a `network_deps` key (added by the security cluster's `env_passthrough` work) — contrary to #340's original claim that it's absent. That field feeds `_preflight_dispatch()`'s **host**-reachability check (a raw socket connect from the dispatcher machine, `dispatch.py:1482-1498`), which is a different and insufficient check for "can the *sandboxed subprocess* reach network" — it does not solve #340 on its own, so this spec does not populate it.

## Architecture

### 1. #340 — `run:install` permission + sandbox network override + preflight probe

**New permission string: `run:install`.** Chosen over `network:package-registry` to stay in the existing `run:` namespace alongside `run:tests`/`run:shell` rather than introducing a new namespace for one case. Not added to any role's default permission set in `_ROLE_PERMISSION_DEFAULTS` (`synlynk/_constants.py:19-32`) — must be explicitly requested per-dispatch.

**`_permissions_to_flags()` codex branch** (`synlynk/dispatch.py:233-237`):

```python
if agent == "codex":
    has_write = any((perm or "").startswith("write:") for perm in (permissions or []))
    flags = [] if has_write else ["--ask-for-approval", "untrusted"]
    if "run:install" in (permissions or []):
        flags = flags + ["-c", "sandbox_workspace_write.network_access=true"]
    return flags
```

**`--add-dir` widening for package caches**, in the existing codex flags block (`synlynk/dispatch.py:1718-1733`, which already appends `--add-dir <git_common_dir>` unconditionally): when `run:install` is in the dispatch's permissions, also append `--add-dir <pip_cache_dir>` and `--add-dir <uv_cache_dir>` using `os.path.expanduser("~/.cache/pip")` and `os.path.expanduser("~/.cache/uv")` — the two Python package-manager cache dirs relevant to this repo (a pure-Python CLI with no npm/cargo dependency). Widening to other cache dirs (npm, cargo) is out of scope until a real task needs it.

**New preflight probe** in `_preflight_dispatch()` (`synlynk/dispatch.py:1395+`), added after the existing `network_deps.required_endpoints` host-reachability loop (`1482-1498`): when `agent_name == "codex"` and `"run:install" in (permissions or [])`, run

```python
subprocess.run(
    ["codex", "exec", "-s", "workspace-write",
     "-c", "sandbox_workspace_write.network_access=true", "-"],
    input="Run exactly this shell command: curl -sS --max-time 3 -o /dev/null -w '%{http_code}' https://pypi.org . Then stop.",
    capture_output=True, text=True, timeout=15,
)
```

and check the captured stdout for `200`. Failure returns the same `{"passed": False, "sentinel": "HARNESS_PREFLIGHT_FAIL", "reason": ...}` shape every other preflight check already uses (`1444-1448`, `1466-1470`, `1494-1498`) — this blocks the real dispatch, since a task that needs network and can't get it should fail before wasting a full dispatch cycle. This check only runs when `run:install` is actually granted, so it adds zero cost to any dispatch that doesn't request it.

### 2. #342 — Grok CWD prompt reminder + defensive flags

**`_format_prompt_for_agent()`** (`synlynk/dispatch.py:772-804`): add a `grok` branch before the generic fallback, mirroring Agy's existing pattern:

```python
if agent == "grok":
    working_dir = cwd_hint or os.getcwd()
    return (
        f"## Working Directory\n{working_dir}\n"
        f"All file edits MUST be in this directory.\n\n"
        f"Task: {task}\n"
        f"{story_ref}\n"
        f"{file_section}\n"
        f"{verify_section}\n"
        f"Context summary:\n{context_text}"
    )
```

`cwd_hint` is already threaded through the sole call site (`synlynk/dispatch.py:1809`, `cwd_hint=worktree_path`) — no new plumbing required.

**Dispatch flags**: `worktree_path` isn't computed until `synlynk/dispatch.py:1750`, after the existing per-agent flags block (`1706-1733`) where `--add-dir` is appended. A new small block goes immediately after `worktree_path = worktree_info["path"]` (line 1750):

```python
if agent == "grok":
    flags = flags + ["--cwd", worktree_path]
if agent == "codex":
    flags = flags + ["-C", worktree_path]
```

Codex's `-C` is defensive (no known incident, added because the issue's own `codex --help` check found the flag exists) — bundled into the same task as Grok's fix since both are one-line additions to the same new code block.

### 3. #347 — instruction-file fingerprint echo + advisory sentinel

**Prompt addition** in `_format_prompt_for_agent()`: every branch (codex, agy, grok, generic fallback) gets one additional line appended to its returned prompt:

```python
fingerprint_line = f"\n\nYour first output line must be exactly: SYNLYNK_FINGERPRINT: {VERSION}\n"
```

using the existing `VERSION` constant from `synlynk/_constants.py` (the same version embedded in the instruction-file marker `<!-- synlynk:start version="{VERSION}" tool="{tool}" -->` written by `synlynk/instructions.py:158`) — this ties the echoed value directly to the version actually present in that agent's instruction file at dispatch time, not a hardcoded string.

**Postflight check**, added at the point where captured job output is already parsed for tokens/sentinels (same general area as the existing `check_sentinel_patterns` / token-extraction logic): grep the first 5 lines of captured stdout for `SYNLYNK_FINGERPRINT: `. If absent or the version doesn't match `VERSION`, call

```python
write_alert("WARNING", "INSTRUCTION_FINGERPRINT_MISMATCH",
            f"Agent '{agent}' did not echo the expected instruction-file fingerprint "
            f"(expected {VERSION}); it may be operating on stale or missing instructions.")
```

— the same `_write_sentinel_alert()` function and severity tier already used for `HARNESS_VERSION_DRIFT`, so it surfaces through `synlynk status`/`jobs` via existing machinery with no new plumbing. Never blocks dispatch or job completion — advisory only, matching this cluster's "drift, not scope violation" character.

## Data Flow / Error Handling

- #340's preflight probe only executes when `run:install` is granted, so it adds no latency or failure surface to any dispatch that doesn't request it. When it does run and fails, dispatch is blocked before any worktree/subprocess work begins — same cheap-failure shape as the security cluster's `PermissionEnforcementError`.
- #342 is a pure prompt/flag addition with no new failure modes — it can only prevent a Grok job from writing outside its worktree, never cause a previously-succeeding dispatch to fail.
- #347 is advisory-only by construction: a missing or mismatched fingerprint never blocks dispatch or fails the job, it only writes a `WARNING` sentinel alongside the job's normal completion. This is deliberate — the fingerprint can't distinguish "agent ignored the instruction" from "agent read it but chose not to echo the marker," so treating a mismatch as a hard failure would produce false positives.

## Testing

- `_permissions_to_flags()`: new test asserting codex + `run:install` in permissions adds `-c sandbox_workspace_write.network_access=true`; existing codex tests (no `run:install`) assert no config override flag appears — regression coverage for the unchanged branch.
- New preflight test for #340: monkeypatch `subprocess.run` to return a fake `200` / non-`200` result, assert the check routes to `HARNESS_PREFLIGHT_FAIL` correctly on failure and passes through cleanly on success; assert the check is skipped entirely (no subprocess call at all) when `run:install` is absent from permissions.
- `_add_dir` widening: test that codex flags include the pip/uv cache dirs only when `run:install` is granted, and that the pre-existing unconditional `git_common_dir` append is unaffected.
- `_format_prompt_for_agent()`: new `test_format_prompt_for_grok_includes_cwd_reminder`, mirroring the existing Agy test (`test_format_prompt_for_agy_is_concise` or equivalent) in structure.
- New test asserting the `--cwd`/`-C` flags appear for grok/codex dispatch after `worktree_path` is known, using the real worktree path value.
- Fingerprint check: unit tests feeding synthetic captured output with (a) a matching fingerprint line, (b) a mismatched version, (c) no fingerprint line at all — asserting `WARNING`/`INSTRUCTION_FINGERPRINT_MISMATCH` fires only for (b) and (c), and that in no case does the job get marked failed or blocked because of it.
- Full existing dispatch test suite must stay green before merge — these changes touch shared dispatch code paths (`_permissions_to_flags`, `_format_prompt_for_agent`, `_preflight_dispatch`, the flags-construction block) used by every dispatch regardless of agent.

## Out of Scope (this spec)

- Widening `--add-dir` to npm/cargo/other package-manager cache dirs beyond pip/uv — added only if a real task demonstrates the need.
- #347's doctor-level smoke check (dispatching a trivial task via `synlynk doctor` and confirming the fingerprint round-trips) and telemetry-only logging depth — both explicit follow-ups, not solved here.
- Populating `AGENT_CAPABILITY_BASELINES["codex"]["network_deps"]["required_endpoints"]` — established above as the wrong mechanism for #340's actual gap (host reachability, not sandbox reachability); left empty.
- Any change to Claude/Agy/Local's CWD handling for #342 — the issue itself found no incident or missing flag for those agents; Codex's `-C` addition is defensive-only, riding along because it's a one-line addition in the same new code block as Grok's real fix.
