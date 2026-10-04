# Grok Fail-Closed Permission Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Grok's `--always-approve --permission-mode bypassPermissions` dispatch bypass structurally opt-in and gated behind `skip_permissions`, with a real fail-closed path when it's declined, instead of today's unconditional, implicit injection — while auto-opting-in internally so no existing caller breaks.

**Architecture:** Mirror the `local` adapter's `PermissionEnforcementError` pattern, but gated: `_grok_permission_flags()` raises when permissions are requested and `skip_permissions=False`, returns the bypass flags unchanged when `skip_permissions=True`. `dispatch_agent()` auto-sets `skip_permissions=True` for Grok before any flag logic runs, since Grok's CLI has no working non-bypass headless mode (LIVE-13). The `GrokAdapter` (not yet live in the dispatch pipeline) and `LegacyAdapter` get the same gate so they don't silently reintroduce the bug later.

**Tech Stack:** Python 3 stdlib, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-04-grok-failclosed-permission-enforcement-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `synlynk/_constants.py` | Harness capability baselines | Remove Grok's unconditional `required_flags: ["--always-approve"]` |
| `synlynk/dispatch.py` | Legacy dispatch flag/permission logic | Gate `_grok_permission_flags` behind `skip_permissions`; thread it through `_permissions_to_flags`; add `"grok"` to `_dispatch_flags_for_agent`'s skip-gated set; auto-opt-in inside `dispatch_agent()` |
| `synlynk/harness_adapters/base.py` | Shared adapter types | Add `PermissionEnforcementError` (moved here from `local.py`); add `skip_permissions` to the `HarnessAdapter` Protocol |
| `synlynk/harness_adapters/local.py` | Local adapter | Import `PermissionEnforcementError` from `base.py` instead of defining its own |
| `synlynk/harness_adapters/grok.py` | Grok adapter | Gate `translate_permissions` the same way as the legacy function; thread `skip_permissions` through `build_cmd` |
| `synlynk/harness_adapters/legacy.py` | Fallback adapter for unported harnesses | Thread `skip_permissions` through to `_permissions_to_flags` |
| `synlynk/harness_adapters/request.py` | `DispatchRequest` dataclass | Add `skip_permissions: bool = False` field |
| `tests/test_dispatch.py` | Legacy dispatch tests | Update 1 existing test, add 2 new |
| `tests/test_synlynk.py` | Baseline tests | Update 2 existing tests |
| `tests/test_agent_quota_tracking.py` | Permission-resolution tests | Update 2 existing tests |
| `tests/test_grok_adapter.py` | GrokAdapter tests | Update 1 existing test, add 2 new |
| `tests/test_legacy_adapter.py` | LegacyAdapter tests | Update 1 existing test |
| `tests/test_local_adapter.py` | LocalAdapter tests | No code change, just verify still green |
| New: `tests/test_harness_adapter_permission_error_identity.py` | Cross-adapter consolidation check | Add 1 new test |

No new files are created for implementation code — every adapter/dispatch file already exists from gh:#1924's port. Only one new, small test file is added (component 3's consolidation check doesn't fit naturally into any single existing per-adapter test file).

---

## Task 1: Remove Grok's unconditional `--always-approve` from the baseline

**Files:**
- Modify: `synlynk/_constants.py:209`
- Modify: `tests/test_synlynk.py` (two existing tests, both inside the file)

- [ ] **Step 1: Update the two existing tests first (they currently assert the old behavior)**

In `tests/test_synlynk.py`, find `test_agent_capability_baselines_includes_grok` (around line 7827) and change this line:

```python
    assert grok["dispatch_flags"]["required_flags"] == ["--always-approve"]
```

to:

```python
    # --always-approve is no longer an unconditional baseline requirement —
    # it's added explicitly via _dispatch_flags_for_agent(skip_permissions=True)
    # and dispatch_agent()'s Grok auto-opt-in instead (gh:#1925 part 1).
    assert grok["dispatch_flags"]["required_flags"] == []
```

Then find `test_grok_baseline_requires_always_approve` (around line 7843) and replace the whole function body:

```python
def test_grok_baseline_requires_always_approve():
    # Headless Grok requires --always-approve so compound shell is not auto-cancelled (#1277).
    from synlynk import HARNESS_CAPABILITY_BASELINES
    grok = HARNESS_CAPABILITY_BASELINES.get("grok", {})
    flags = grok.get("dispatch_flags", {})
    assert "--always-approve" in flags.get("valid_flags", []), \
        "--always-approve must be valid for Grok (--yes was dropped)"
    assert "--permission-mode" in flags.get("valid_flags", []), \
        "--permission-mode must remain valid for bypassPermissions fallback"
    assert flags.get("required_flags", []) == ["--always-approve"], \
        "Grok must require --always-approve for headless dispatch"
    assert "--yes" in flags.get("invalid_flags", []), \
        "--yes must be invalid for Grok (it was dropped by Grok CLI)"
```

with:

```python
def test_grok_baseline_requires_always_approve():
    # --always-approve/--permission-mode stay valid Grok CLI flags, but are no
    # longer an unconditional baseline requirement (gh:#1925 part 1) — the
    # bypass is now added explicitly and only when skip_permissions=True
    # (dispatch_agent() auto-sets this for Grok; see
    # docs/superpowers/specs/2026-10-04-grok-failclosed-permission-enforcement-design.md).
    from synlynk import HARNESS_CAPABILITY_BASELINES
    grok = HARNESS_CAPABILITY_BASELINES.get("grok", {})
    flags = grok.get("dispatch_flags", {})
    assert "--always-approve" in flags.get("valid_flags", []), \
        "--always-approve must be valid for Grok (--yes was dropped)"
    assert "--permission-mode" in flags.get("valid_flags", []), \
        "--permission-mode must remain valid for bypassPermissions fallback"
    assert flags.get("required_flags", []) == [], \
        "Grok's baseline must not unconditionally require --always-approve"
    assert "--yes" in flags.get("invalid_flags", []), \
        "--yes must be invalid for Grok (it was dropped by Grok CLI)"
```

- [ ] **Step 2: Run the two tests to verify they fail against today's code**

Run: `pytest tests/test_synlynk.py::test_agent_capability_baselines_includes_grok tests/test_synlynk.py::test_grok_baseline_requires_always_approve -v`
Expected: both FAIL (today's baseline still has `required_flags: ["--always-approve"]`)

- [ ] **Step 3: Remove the unconditional required flag from the baseline**

In `synlynk/_constants.py`, find this block (around line 200):

```python
        "dispatch_flags": {
            "valid_flags": [
                "--always-approve",
                "--permission-mode",
                "--output-format",
                "--model",
                "--single",
            ],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            "required_flags": ["--always-approve"],
        },
```

Change the `required_flags` line to:

```python
        "dispatch_flags": {
            "valid_flags": [
                "--always-approve",
                "--permission-mode",
                "--output-format",
                "--model",
                "--single",
            ],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            # Not unconditionally required (gh:#1925 part 1) — added explicitly
            # by _dispatch_flags_for_agent(skip_permissions=True) instead, which
            # dispatch_agent() auto-sets for Grok (see LIVE-13 and
            # docs/superpowers/specs/2026-10-04-grok-failclosed-permission-enforcement-design.md).
            "required_flags": [],
        },
```

- [ ] **Step 4: Run the two tests again to verify they pass**

Run: `pytest tests/test_synlynk.py::test_agent_capability_baselines_includes_grok tests/test_synlynk.py::test_grok_baseline_requires_always_approve -v`
Expected: both PASS

- [ ] **Step 5: Run the full test_synlynk.py file to check for other regressions from this one-line change**

Run: `pytest tests/test_synlynk.py -k grok -v`
Expected: all Grok-related tests in this file PASS (no other test in this file asserts on Grok's `required_flags`)

- [ ] **Step 6: Commit**

```bash
git add synlynk/_constants.py tests/test_synlynk.py
git commit -m "fix(grok): remove unconditional --always-approve baseline requirement (gh:#1925 part 1)"
```

---

## Task 2: Gate `_grok_permission_flags` behind `skip_permissions`

**Files:**
- Modify: `synlynk/dispatch.py:700-711` (`_grok_permission_flags`)
- Modify: `synlynk/dispatch.py:740-790` (`_permissions_to_flags`, the `grok` branch around line 784-785)
- Modify: `tests/test_dispatch.py:1918-1932` (existing test)
- Modify: `tests/test_agent_quota_tracking.py` (two existing tests, around lines 1026 and 1038)

- [ ] **Step 1: Update the existing `_grok_permission_flags` test first**

In `tests/test_dispatch.py`, find `test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted` (around line 1918) and replace it:

```python
def test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted():
    from synlynk.dispatch import _grok_permission_flags

    shell_flags = _grok_permission_flags(["read:*", "run:shell"])
    test_flags = _grok_permission_flags(["read:*", "run:tests"])
    write_flags = _grok_permission_flags(["read:*", "write:src/"])

    assert shell_flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert test_flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert write_flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert "dontAsk" not in shell_flags
    assert "dontAsk" not in test_flags
    assert "dontAsk" not in write_flags
    assert _grok_permission_flags([]) == []
```

with:

```python
def test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted():
    from synlynk.dispatch import _grok_permission_flags

    shell_flags = _grok_permission_flags(["read:*", "run:shell"], skip_permissions=True)
    test_flags = _grok_permission_flags(["read:*", "run:tests"], skip_permissions=True)
    write_flags = _grok_permission_flags(["read:*", "write:src/"], skip_permissions=True)

    assert shell_flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert test_flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert write_flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert "dontAsk" not in shell_flags
    assert "dontAsk" not in test_flags
    assert "dontAsk" not in write_flags
    assert _grok_permission_flags([]) == []
    assert _grok_permission_flags([], skip_permissions=False) == []


def test_grok_permission_flags_raises_when_not_skipped():
    from synlynk.dispatch import _grok_permission_flags, PermissionEnforcementError

    with pytest.raises(PermissionEnforcementError, match="grok"):
        _grok_permission_flags(["run:shell"], skip_permissions=False)


def test_grok_permission_flags_empty_permissions_never_raises():
    from synlynk.dispatch import _grok_permission_flags

    # No permissions requested means nothing to enforce, regardless of the flag.
    assert _grok_permission_flags([], skip_permissions=False) == []
    assert _grok_permission_flags(None, skip_permissions=False) == []
```

- [ ] **Step 2: Update the two existing `_permissions_to_flags("grok", ...)` tests in `tests/test_agent_quota_tracking.py`**

Find `test_phase_2_of_docssuperpowersplans20260730h_grok_role_permission_flags` (around line 1026) and change:

```python
    permissions = _resolve_dispatch_permissions("grok", role_list=[role_name])
    flags = _permissions_to_flags("grok", permissions)

    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert "dontAsk" not in flags
```

to:

```python
    permissions = _resolve_dispatch_permissions("grok", role_list=[role_name])
    flags = _permissions_to_flags("grok", permissions, skip_permissions=True)

    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert "dontAsk" not in flags
```

Find `test_phase_2_of_docssuperpowersplans20260730h_grok_regression_no_empty_fallthrough` (around line 1038) and change:

```python
    flags = _permissions_to_flags("grok", ["read:*"])
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert "dontAsk" not in flags
```

to:

```python
    flags = _permissions_to_flags("grok", ["read:*"], skip_permissions=True)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
    assert "dontAsk" not in flags
```

- [ ] **Step 3: Run all four tests to verify they fail against today's code**

Run: `pytest tests/test_dispatch.py::test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted tests/test_dispatch.py::test_grok_permission_flags_raises_when_not_skipped tests/test_dispatch.py::test_grok_permission_flags_empty_permissions_never_raises -v`
Expected: the first FAILS with `TypeError: _grok_permission_flags() got an unexpected keyword argument 'skip_permissions'`; the second and third FAIL (function not raising, or not yet defined to accept the kwarg).

Run: `pytest tests/test_agent_quota_tracking.py -k "grok_role_permission_flags or grok_regression_no_empty_fallthrough" -v`
Expected: both FAIL with a `TypeError` for the unexpected `skip_permissions` keyword.

- [ ] **Step 4: Implement the gated `_grok_permission_flags`**

In `synlynk/dispatch.py`, find (around line 700):

```python
def _grok_permission_flags(permissions: list) -> list:
    """Translate resolved permission strings into Grok CLI permission flags.

    For headless execution (#1732, #1734), passes `--always-approve` and
    `--permission-mode bypassPermissions` to prevent tool cancellations.
    """
    permission_set = {perm for perm in (permissions or []) if perm}
    if not permission_set:
        return []

    return ["--always-approve", "--permission-mode", "bypassPermissions"]
```

Replace with:

```python
def _grok_permission_flags(permissions: list, skip_permissions: bool = False) -> list:
    """Translate resolved permission strings into Grok CLI permission flags.

    Grok's CLI has no working non-bypass headless mode (LIVE-13:
    docs/rca/2026-09-22-LIVE-13-grok-headless-dispatch-permission-bypass.md) —
    under --permission-mode dontAsk it silently cancels tool calls while
    reporting success. For headless execution (#1732, #1734), passing
    `--always-approve` and `--permission-mode bypassPermissions` avoids that.

    This is now gated behind `skip_permissions` (gh:#1925 part 1) rather than
    unconditional: when permissions are requested and the caller has not
    opted into the bypass, raise instead of silently granting it.
    dispatch_agent() auto-opts-in for Grok specifically so existing callers
    are unaffected — see
    docs/superpowers/specs/2026-10-04-grok-failclosed-permission-enforcement-design.md.
    """
    permission_set = {perm for perm in (permissions or []) if perm}
    if not permission_set:
        return []

    if not skip_permissions:
        raise PermissionEnforcementError(
            f"grok has no scoped-permission headless mode for requested permissions "
            f"{sorted(permission_set)} (LIVE-13: Grok's --permission-mode dontAsk silently "
            "cancels tool calls). Pass skip_permissions=True to proceed with "
            "--always-approve --permission-mode bypassPermissions instead."
        )

    return ["--always-approve", "--permission-mode", "bypassPermissions"]
```

Note: `PermissionEnforcementError` is defined later in the same file (around line 713, right after this function). Python resolves this at call time, not at function-definition time, so no import reordering is needed — the class exists in the module namespace by the time `_grok_permission_flags` is actually called.

- [ ] **Step 5: Thread `skip_permissions` through the `grok` branch of `_permissions_to_flags`**

In `synlynk/dispatch.py`, find (around line 784):

```python
    if agent == "grok":
        return _grok_permission_flags(permissions)
```

Replace with:

```python
    if agent == "grok":
        return _grok_permission_flags(permissions, skip_permissions=skip_permissions)
```

- [ ] **Step 6: Run the four tests again to verify they pass**

Run: `pytest tests/test_dispatch.py::test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted tests/test_dispatch.py::test_grok_permission_flags_raises_when_not_skipped tests/test_dispatch.py::test_grok_permission_flags_empty_permissions_never_raises -v`
Expected: all PASS

Run: `pytest tests/test_agent_quota_tracking.py -k "grok_role_permission_flags or grok_regression_no_empty_fallthrough" -v`
Expected: both PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py tests/test_agent_quota_tracking.py
git commit -m "fix(grok): gate _grok_permission_flags bypass behind skip_permissions (gh:#1925 part 1)"
```

---

## Task 3: Add `"grok"` to `_dispatch_flags_for_agent`'s skip-gated append set

**Files:**
- Modify: `synlynk/dispatch.py:425-445` (`_dispatch_flags_for_agent`)
- Modify: `tests/test_dispatch.py:1934-1960` (existing test's monkeypatch)

This task matters independently of Task 2 because `_dispatch_flags_for_agent` reads the
baseline directly — after Task 1 removed Grok's `required_flags` entry, nothing currently adds
`--always-approve` through this path at all unless `skip_permissions=True` is both passed in
*and* the agent is in the gated set. Today that set is `{"claude", "agy"}`.

- [ ] **Step 1: Update the existing dedup test's monkeypatch first**

In `tests/test_dispatch.py`, find `test_grok_dispatch_deduplicates_boolean_permission_and_baseline_flags`
(around line 1934) and change this line:

```python
    monkeypatch.setattr(dispatch_mod, "_dispatch_flags_for_agent", lambda agent: ["--always-approve"])
```

to:

```python
    monkeypatch.setattr(
        dispatch_mod, "_dispatch_flags_for_agent",
        lambda agent, skip_permissions=False: ["--always-approve"],
    )
```

This is necessary because Task 4 (below) makes `dispatch_agent()` call
`_dispatch_flags_for_agent(agent, skip_permissions=True)` for every Grok dispatch — a
single-argument lambda monkeypatch would raise `TypeError: <lambda>() got an unexpected
keyword argument 'skip_permissions'` once that auto-opt-in lands.

- [ ] **Step 2: Run the test to verify it currently still passes (confirms the `TypeError` only appears after Task 4, not before)**

Run: `pytest tests/test_dispatch.py::test_grok_dispatch_deduplicates_boolean_permission_and_baseline_flags -v`
Expected: PASS (this step is a sanity check — Task 4 hasn't landed yet, so the single-arg-safe
two-arg lambda works fine against today's call site too)

- [ ] **Step 3: Add `"grok"` to the gated set**

In `synlynk/dispatch.py`, find (around line 440):

```python
    if skip_permissions and agent in {"claude", "agy"}:
        flags.append("--dangerously-skip-permissions")
    return flags
```

Leave this line alone — it only adds `--dangerously-skip-permissions`, which is wrong for
Grok's CLI (that flag is in Grok's `invalid_flags`). Instead, add a separate, Grok-specific
branch right after it:

```python
    if skip_permissions and agent in {"claude", "agy"}:
        flags.append("--dangerously-skip-permissions")
    if skip_permissions and agent == "grok" and "--always-approve" not in flags:
        flags.append("--always-approve")
    return flags
```

- [ ] **Step 4: Write a new test confirming this behavior directly**

Add to `tests/test_dispatch.py` (near the other `_dispatch_flags_for_agent` tests — search the
file for `_dispatch_flags_for_agent` to find a good neighboring spot):

```python
def test_dispatch_flags_for_agent_grok_adds_always_approve_only_when_skipped():
    from synlynk.dispatch import _dispatch_flags_for_agent

    assert "--always-approve" not in _dispatch_flags_for_agent("grok")
    assert "--always-approve" not in _dispatch_flags_for_agent("grok", skip_permissions=False)
    assert "--always-approve" in _dispatch_flags_for_agent("grok", skip_permissions=True)


def test_dispatch_flags_for_agent_grok_never_adds_dangerously_skip_permissions():
    from synlynk.dispatch import _dispatch_flags_for_agent

    # --dangerously-skip-permissions is in Grok's invalid_flags; the skip gate
    # must add --always-approve for Grok, never this flag.
    flags = _dispatch_flags_for_agent("grok", skip_permissions=True)
    assert "--dangerously-skip-permissions" not in flags
```

- [ ] **Step 5: Run the new tests to verify they fail against pre-Step-3 code, then pass after Step 3**

Run: `pytest tests/test_dispatch.py::test_dispatch_flags_for_agent_grok_adds_always_approve_only_when_skipped tests/test_dispatch.py::test_dispatch_flags_for_agent_grok_never_adds_dangerously_skip_permissions -v`
Expected (before Step 3's code change): the first test FAILS (`--always-approve` missing when `skip_permissions=True`, since no code path added it yet — Grok's baseline `required_flags` is now `[]` from Task 1, and this function doesn't yet special-case Grok)
Expected (after Step 3's code change): both PASS

- [ ] **Step 6: Run the full dispatch-flags test slice to check for regressions**

Run: `pytest tests/test_dispatch.py -k "dispatch_flags_for_agent or grok" -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix(grok): add --always-approve via _dispatch_flags_for_agent only when skip_permissions=True (gh:#1925 part 1)"
```

---

## Task 4: Auto-opt-in `skip_permissions=True` for Grok inside `dispatch_agent()`

**Files:**
- Modify: `synlynk/dispatch.py:3183` (right after the final `agent` resolution check)
- Test: `tests/test_dispatch.py` (new test)

This is the piece that keeps every existing Grok dispatch caller working unchanged after
Tasks 1-3 removed the unconditional bypass.

- [ ] **Step 1: Write the new test first**

Add to `tests/test_dispatch.py` (a good neighboring spot is right after
`test_grok_dispatch_deduplicates_boolean_permission_and_baseline_flags`, since it uses the
same `fake_popen` pattern):

```python
def test_grok_dispatch_auto_skips_permissions_by_default(project_dir, monkeypatch):
    """A Grok dispatch with no explicit skip_permissions arg must still succeed
    with the bypass flags present — dispatch_agent() auto-opts-in for Grok
    (gh:#1925 part 1) since Grok's CLI has no working non-bypass headless mode."""
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_popen(command, *args, **kwargs):
        captured["command"] = command

        class FakeProc:
            pid = 12345

        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda *a, **kw: {"passed": True})

    dispatch_mod.dispatch_agent(
        agent="grok",
        task="run tests",
        grants=["run:shell"],
        force_agent=True,
        skip_preflight=True,
        context_mode="none",
        # skip_permissions deliberately omitted — must default to working behavior.
    )

    shell_cmd = captured["command"][2]
    assert "--always-approve" in shell_cmd
    assert "--permission-mode bypassPermissions" in shell_cmd
```

- [ ] **Step 2: Run the test to verify it fails against today's code**

Run: `pytest tests/test_dispatch.py::test_grok_dispatch_auto_skips_permissions_by_default -v`
Expected: FAILS — `_grok_permission_flags` (Task 2) now raises `PermissionEnforcementError`
for this dispatch, because nothing has set `skip_permissions=True` yet.

- [ ] **Step 3: Add the auto-opt-in**

In `synlynk/dispatch.py`, find the final-agent-resolution guard (around line 3183):

```python
    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")

    # A capability gate may reroute the harness (for example, Grok write
    # denial or GitHub-write routing). Re-resolve against the final harness so
    # automatic model defaults never leak across sandbox boundaries.
    model_routing = resolve_dispatch_model(
```

Insert the auto-opt-in between the `ValueError` guard and the `model_routing` call:

```python
    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")

    if agent == "grok" and not skip_permissions:
        # Grok's CLI has no working non-bypass headless mode (LIVE-13:
        # docs/rca/2026-09-22-LIVE-13-grok-headless-dispatch-permission-bypass.md).
        # Auto-opt-in here (rather than requiring every caller to pass
        # --dangerously-skip-permissions) so existing Grok dispatch workflows
        # keep working unchanged after gh:#1925 part 1 made the bypass gated
        # instead of unconditional. See
        # docs/superpowers/specs/2026-10-04-grok-failclosed-permission-enforcement-design.md.
        skip_permissions = True

    # A capability gate may reroute the harness (for example, Grok write
    # denial or GitHub-write routing). Re-resolve against the final harness so
    # automatic model defaults never leak across sandbox boundaries.
    model_routing = resolve_dispatch_model(
```

This placement is deliberately after the `agent not in baselines_map` check (so `agent` is
fully final — including any `--requires-gh-write` reroute or Grok-sandbox-write-denial
failover from earlier in the function) and before `baselines = baselines_map[agent]` /
`dispatch_flags = _dispatch_flags_for_agent(...)` (around line 3324-3328), which is the first
place `skip_permissions` actually gets read.

- [ ] **Step 4: Run the test again to verify it passes**

Run: `pytest tests/test_dispatch.py::test_grok_dispatch_auto_skips_permissions_by_default -v`
Expected: PASS

- [ ] **Step 5: Run the three pre-existing full-dispatch Grok integration tests to confirm no regression**

Run: `pytest tests/test_synlynk.py::test_grok_dispatch_uses_always_approve tests/test_synlynk.py::test_grok_fallback_permission_mode tests/test_synlynk.py::test_grok_dispatch_single_flag_placed_before_prompt -v`
Expected: all PASS (these dispatch through role-based permission grants rather than explicit
`grants=`, but the auto-opt-in applies regardless of how permissions were resolved)

- [ ] **Step 6: Run the full `tests/test_dispatch.py` and `tests/test_agent_quota_tracking.py` files**

Run: `pytest tests/test_dispatch.py tests/test_agent_quota_tracking.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix(grok): auto-opt-in skip_permissions for Grok dispatches (gh:#1925 part 1)

Grok's CLI has no working non-bypass headless mode (LIVE-13). Rather than
requiring every existing caller to pass --dangerously-skip-permissions,
dispatch_agent() now sets skip_permissions=True internally for Grok before
flag resolution runs, so the gated bypass added in the prior two commits
doesn't break any current Grok dispatch workflow."
```

---

## Task 5: Consolidate `PermissionEnforcementError` into `base.py` and gate `GrokAdapter`/`LegacyAdapter`

**Files:**
- Modify: `synlynk/harness_adapters/base.py`
- Modify: `synlynk/harness_adapters/local.py`
- Modify: `synlynk/harness_adapters/grok.py`
- Modify: `synlynk/harness_adapters/legacy.py`
- Modify: `synlynk/harness_adapters/request.py`
- Modify: `tests/test_grok_adapter.py` (1 existing test), add 2 new
- Modify: `tests/test_legacy_adapter.py` (1 existing test)
- Create: `tests/test_harness_adapter_permission_error_identity.py`

- [ ] **Step 1: Add `skip_permissions` to `DispatchRequest`**

In `synlynk/harness_adapters/request.py`, find the last field:

```python
    permissions: list = field(default_factory=list)
    read_only: bool = False
```

Add a new field after it:

```python
    permissions: list = field(default_factory=list)
    read_only: bool = False
    skip_permissions: bool = False
```

- [ ] **Step 2: Move `PermissionEnforcementError` into `base.py` and add `skip_permissions` to the Protocol**

In `synlynk/harness_adapters/base.py`, find:

```python
class FailureKind(Enum):
    AUTH_EXPIRED = "auth_expired"
    QUOTA_EXHAUSTED = "quota_exhausted"
    SANDBOX_DENIED = "sandbox_denied"
```

Add the new class right after it:

```python
class FailureKind(Enum):
    AUTH_EXPIRED = "auth_expired"
    QUOTA_EXHAUSTED = "quota_exhausted"
    SANDBOX_DENIED = "sandbox_denied"


class PermissionEnforcementError(RuntimeError):
    """Raised when a harness adapter has no mechanism to enforce requested
    permissions and the caller has not explicitly opted into a full bypass."""
```

Then find the Protocol's `translate_permissions` signature:

```python
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        ...
```

Change it to:

```python
    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        ...
```

- [ ] **Step 3: Update `local.py` to import the moved class instead of defining its own**

In `synlynk/harness_adapters/local.py`, find:

```python
"""Local (aider/oMLX) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class PermissionEnforcementError(RuntimeError):
    pass


class LocalAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
```

Replace with:

```python
"""Local (aider/oMLX) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind, PermissionEnforcementError
from synlynk.harness_adapters.request import DispatchRequest


class LocalAdapter:
    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
```

(`local` has no bypass to gate — it always raises when permissions are requested, regardless
of `skip_permissions` — so the parameter is accepted for Protocol conformance but otherwise
unused in the method body, which stays exactly as it was.)

- [ ] **Step 4: Run the existing local-adapter test suite to confirm the import-path change didn't break anything**

Run: `pytest tests/test_local_adapter.py -v`
Expected: all PASS (the test file imports `PermissionEnforcementError` from
`synlynk.harness_adapters.local`, which still re-exports it as a module attribute after the
`from ... import` in Step 3 — no test changes needed)

- [ ] **Step 5: Update the existing `GrokAdapter` test first**

In `tests/test_grok_adapter.py`, find:

```python
def test_grok_translate_permissions_nonempty_grants_always_approve():
    adapter = GrokAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
```

Replace with:

```python
def test_grok_translate_permissions_nonempty_grants_always_approve():
    adapter = GrokAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=True)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]


def test_grok_translate_permissions_raises_when_not_skipped():
    import pytest
    from synlynk.harness_adapters.base import PermissionEnforcementError

    adapter = GrokAdapter()
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=False)


def test_grok_translate_permissions_raises_by_default_when_skip_permissions_omitted():
    import pytest
    from synlynk.harness_adapters.base import PermissionEnforcementError

    adapter = GrokAdapter()
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False)
```

- [ ] **Step 6: Run the new/updated GrokAdapter tests to verify they fail against today's code**

Run: `pytest tests/test_grok_adapter.py -v`
Expected: `test_grok_translate_permissions_nonempty_grants_always_approve` FAILS with a
`TypeError` (unexpected keyword `skip_permissions`); the two new tests FAIL (also `TypeError`,
since the parameter doesn't exist yet)

- [ ] **Step 7: Implement the gate in `GrokAdapter`**

In `synlynk/harness_adapters/grok.py`, find:

```python
"""Grok HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class GrokAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        permission_set = {perm for perm in (permissions or []) if perm}
        if not permission_set:
            return []
        return ["--always-approve", "--permission-mode", "bypassPermissions"]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("grok")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags
```

Replace with:

```python
"""Grok HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind, PermissionEnforcementError
from synlynk.harness_adapters.request import DispatchRequest


class GrokAdapter:
    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        permission_set = {perm for perm in (permissions or []) if perm}
        if not permission_set:
            return []
        if not skip_permissions:
            raise PermissionEnforcementError(
                f"grok has no scoped-permission headless mode for requested permissions "
                f"{sorted(permission_set)} (LIVE-13: Grok's --permission-mode dontAsk silently "
                "cancels tool calls). Pass skip_permissions=True to proceed with "
                "--always-approve --permission-mode bypassPermissions instead."
            )
        return ["--always-approve", "--permission-mode", "bypassPermissions"]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("grok", skip_permissions=request.skip_permissions)
        flags += self.translate_permissions(
            request.permissions, request.read_only, skip_permissions=request.skip_permissions
        )
        return flags
```

- [ ] **Step 8: Run the GrokAdapter tests again to verify they pass**

Run: `pytest tests/test_grok_adapter.py -v`
Expected: all PASS

- [ ] **Step 9: Update the existing `LegacyAdapter` Grok test**

In `tests/test_legacy_adapter.py`, find:

```python
def test_legacy_adapter_translate_permissions_matches_existing_grok_logic():
    adapter = LegacyAdapter(agent="grok")
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]
```

Replace with:

```python
def test_legacy_adapter_translate_permissions_matches_existing_grok_logic():
    adapter = LegacyAdapter(agent="grok")
    flags = adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=True)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]


def test_legacy_adapter_translate_permissions_grok_raises_when_not_skipped():
    import pytest
    from synlynk.harness_adapters.base import PermissionEnforcementError

    adapter = LegacyAdapter(agent="grok")
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=False)
```

- [ ] **Step 10: Run the LegacyAdapter tests to verify they fail against today's code**

Run: `pytest tests/test_legacy_adapter.py -v`
Expected: `test_legacy_adapter_translate_permissions_matches_existing_grok_logic` FAILS with a
`TypeError` (unexpected keyword `skip_permissions`); the new test FAILS too (same reason)

- [ ] **Step 11: Thread `skip_permissions` through `LegacyAdapter.translate_permissions`**

In `synlynk/harness_adapters/legacy.py`, find:

```python
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk.dispatch import _permissions_to_flags

        return _permissions_to_flags(self.agent, permissions, read_only=read_only)
```

Replace with:

```python
    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        from synlynk.dispatch import _permissions_to_flags

        return _permissions_to_flags(
            self.agent, permissions, read_only=read_only, skip_permissions=skip_permissions
        )
```

- [ ] **Step 12: Run the LegacyAdapter tests again, plus the codex one (regression check), to verify all pass**

Run: `pytest tests/test_legacy_adapter.py -v`
Expected: all PASS (`test_legacy_adapter_translate_permissions_matches_existing_codex_logic` is
unaffected — Codex's branch of `_permissions_to_flags` doesn't look at `skip_permissions` for
anything in its own logic, and passing the new keyword through is harmless since it's accepted
and simply ignored there)

- [ ] **Step 13: Write the cross-adapter consolidation test**

Create `tests/test_harness_adapter_permission_error_identity.py`:

```python
"""Confirms gh:#1925 part 1's consolidation: local.py and grok.py both raise
the SAME PermissionEnforcementError class (from base.py), not two separate
same-named classes."""


def test_local_and_grok_adapters_share_permission_enforcement_error_class():
    from synlynk.harness_adapters import base, grok, local

    assert local.PermissionEnforcementError is base.PermissionEnforcementError
    assert grok.PermissionEnforcementError is base.PermissionEnforcementError


def test_local_and_grok_permission_errors_are_interchangeable_in_except_blocks():
    from synlynk.harness_adapters.grok import GrokAdapter
    from synlynk.harness_adapters.local import PermissionEnforcementError as LocalError

    adapter = GrokAdapter()
    try:
        adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=False)
        assert False, "expected PermissionEnforcementError"
    except LocalError:
        pass  # catching via the OTHER module's imported name must work — same class object
```

- [ ] **Step 14: Run the new test to verify it fails before Step 2/3's consolidation, passes after**

Run: `pytest tests/test_harness_adapter_permission_error_identity.py -v`
Expected: PASS (Steps 2-3 already landed earlier in this task, so this should pass immediately
— this step is a confirmation, not a red/green TDD cycle, since the consolidation code is
already in place by this point in the task)

- [ ] **Step 15: Run the full harness_adapters test slice**

Run: `pytest tests/test_grok_adapter.py tests/test_legacy_adapter.py tests/test_local_adapter.py tests/test_harness_adapter_registry.py tests/test_harness_adapter_permission_error_identity.py -v`
Expected: all PASS

- [ ] **Step 16: Commit**

```bash
git add synlynk/harness_adapters/base.py synlynk/harness_adapters/local.py \
        synlynk/harness_adapters/grok.py synlynk/harness_adapters/legacy.py \
        synlynk/harness_adapters/request.py \
        tests/test_grok_adapter.py tests/test_legacy_adapter.py \
        tests/test_harness_adapter_permission_error_identity.py
git commit -m "fix(harness-adapters): gate GrokAdapter/LegacyAdapter bypass behind skip_permissions (gh:#1925 part 1)

Consolidates PermissionEnforcementError into harness_adapters/base.py (was
duplicated between dispatch.py and harness_adapters/local.py) so grok.py
can raise/catch the same class as local.py. GrokAdapter isn't live in the
dispatch pipeline yet (command-building still runs through the legacy
dispatch.py functions), but leaving it unfixed would silently reintroduce
this bug once a future pipeline cutover starts using it."
```

---

## Task 6: Full regression pass

**Files:** None (verification only)

- [ ] **Step 1: Run every test file touched by this plan together**

Run:
```bash
pytest tests/test_dispatch.py tests/test_synlynk.py tests/test_agent_quota_tracking.py \
       tests/test_agent_cli.py tests/test_grok_adapter.py tests/test_legacy_adapter.py \
       tests/test_local_adapter.py tests/test_harness_adapter_registry.py \
       tests/test_harness_adapter_permission_error_identity.py -v
```
Expected: all PASS, 0 failures

- [ ] **Step 2: Run the full test suite to catch anything outside the touched files**

Run: `pytest -q`
Expected: all PASS, 0 failures (if any unrelated pre-existing failures are present on `main`,
confirm via `git stash` + rerun that they predate this branch before treating them as
regressions introduced here)

- [ ] **Step 3: Grep-sanity-check no stray unconditional bypass remains**

Run: `grep -n 'required_flags.*always-approve' synlynk/_constants.py`
Expected: no output (the only prior occurrence was Grok's, removed in Task 1)

- [ ] **Step 4: No commit needed for this task** — it's verification-only. If Step 2 surfaces a
failure traceable to this plan's changes, fix it in the task where the bug was introduced and
re-run Tasks 1-6's verification steps for that task, rather than papering over it here.
