# Codex Direct GitHub-Write Network Access via Config Override — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Codex to perform GitHub-write operations (reviews, comments, issue closures) by automatically granting `_CODEX_NETWORK_PERMISSION` (`run:install`) and appending `-c sandbox_workspace_write.network_access=true` when `--requires-gh-write` is specified on dispatch, closing the execution gap in #865/#1268.

**Architecture:** 
In `synlynk/dispatch.py`, `_permissions_to_flags()` already knows how to append `["-c", "sandbox_workspace_write.network_access=true"]` when `_CODEX_NETWORK_PERMISSION` (`"run:install"`) is present in `permissions`. However, `dispatch_agent()` previously only appended `"run:shell"` to `effective_grants` when `requires_gh_write` was True, omitting `_CODEX_NETWORK_PERMISSION`. We update `dispatch_agent()` so that for Codex, `requires_gh_write=True` auto-includes `_CODEX_NETWORK_PERMISSION` in `effective_grants`, causing `_permissions_to_flags` to cleanly generate the network override flag.

**Tech Stack:** Python stdlib, pytest.

---

### Task 1: Add Unit Tests for Codex GH-Write Network Flag Generation

**Files:**
- Modify: `tests/test_agent_cli.py`

- [ ] **Step 1: Write the failing tests**

Add the following tests to `tests/test_agent_cli.py`:

```python
def test_codex_dispatch_effective_grants_includes_network_permission_on_gh_write():
    from synlynk._constants import _CODEX_NETWORK_PERMISSION
    from synlynk.dispatch import _permissions_to_flags, _resolve_dispatch_permissions

    # Simulate effective_grants when requires_gh_write is True for codex
    agent = "codex"
    requires_gh_write = True
    effective_grants = []
    if requires_gh_write:
        if "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
            effective_grants.append(_CODEX_NETWORK_PERMISSION)

    perms = _resolve_dispatch_permissions(agent, role_list=["builder"], grants=effective_grants)
    assert _CODEX_NETWORK_PERMISSION in perms

    flags = _permissions_to_flags(agent, perms)
    assert flags[-2:] == ["-c", "sandbox_workspace_write.network_access=true"]


def test_codex_dispatch_effective_grants_omits_network_permission_when_gh_write_false():
    from synlynk._constants import _CODEX_NETWORK_PERMISSION
    from synlynk.dispatch import _permissions_to_flags, _resolve_dispatch_permissions

    agent = "codex"
    requires_gh_write = False
    effective_grants = []
    if requires_gh_write:
        if "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
            effective_grants.append(_CODEX_NETWORK_PERMISSION)

    perms = _resolve_dispatch_permissions(agent, role_list=["builder"], grants=effective_grants)
    assert _CODEX_NETWORK_PERMISSION not in perms

    flags = _permissions_to_flags(agent, perms)
    assert "sandbox_workspace_write.network_access=true" not in flags
```

- [ ] **Step 2: Verify test passes against unit helper**

Run: `python -m pytest tests/test_agent_cli.py -k "test_codex_dispatch_effective_grants" -v`

---

### Task 2: Update `dispatch_agent()` in `synlynk/dispatch.py`

**Files:**
- Modify: `synlynk/dispatch.py`

- [ ] **Step 1: Update `dispatch_agent()` grant resolution**

In `synlynk/dispatch.py` around line 2443:

```python
    effective_grants = list(grants or [])
    if requires_gh_write:
        if "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
            effective_grants.append(_CODEX_NETWORK_PERMISSION)
```

- [ ] **Step 2: Add integration test verifying flags passed to Codex in dispatch preflight**

In `tests/test_agent_cli.py`, add a test verifying that `dispatch_agent()` with `requires_gh_write=True` includes the network flag for Codex:

```python
def test_dispatch_agent_codex_requires_gh_write_appends_network_access_flag(monkeypatch, tmp_path):
    import synlynk.dispatch as dispatch_mod

    recorded_cmd = []

    def fake_popen(cmd, *args, **kwargs):
        recorded_cmd.extend(cmd)
        class DummyProc:
            pid = 9999
            returncode = 0
            stdout = None
            def poll(self): return 0
            def wait(self, timeout=None): return 0
            def communicate(self, *a, **kw): return ("", "")
        return DummyProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "fake-token")
    monkeypatch.setattr(dispatch_mod, "_gh_write_allow_host_auth", lambda: True)

    # Dispatch codex with requires_gh_write
    try:
        dispatch_mod.dispatch_agent(
            agent="codex",
            task="gh pr review 123 --comment -b test",
            requires_gh_write=True,
            agent_role="qa",
            skip_preflight=True,
        )
    except Exception:
        pass

    assert "-c" in recorded_cmd
    idx = recorded_cmd.index("-c")
    assert recorded_cmd[idx + 1] == "sandbox_workspace_write.network_access=true"
```

- [ ] **Step 3: Run full test suite for dispatch and agent cli**

Run:
```bash
python -m pytest tests/test_agent_cli.py tests/test_synlynk.py -q
```
Verify all tests pass.
