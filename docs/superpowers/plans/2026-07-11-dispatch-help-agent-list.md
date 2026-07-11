# dispatch --help Stale Agent List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `synlynk dispatch --help`'s agent list (help text + accepted values) derive from `AGENT_CAPABILITY_BASELINES` instead of a hand-maintained string, so it can never drift out of sync again, and reject unrecognized agent names at the CLI layer instead of falling through to `dispatch_agent()`.

**Architecture:** `main()` in `synlynk/cli.py` already imports `AGENT_CAPABILITY_BASELINES`-adjacent internals unconditionally via a single `from synlynk import (...)` block before building the argparse parser. Add `AGENT_CAPABILITY_BASELINES` to that block, then replace the `agent` positional argument's hardcoded `help=` string with one built from `sorted(AGENT_CAPABILITY_BASELINES)`, and add `choices=` using the same list.

**Tech Stack:** Python 3 stdlib `argparse`, pytest (existing `tests/test_synlynk.py` conventions — `sys.argv` + `synlynk.main()` + `capsys` + `pytest.raises(SystemExit)`, as used by `test_daemon_cli_status_not_running` and similar).

**Tracks:** [#160](https://github.com/nikhilsoman/synlynk/issues/160). Full design: `docs/superpowers/specs/2026-07-11-dispatch-help-agent-list-design.md`.

---

### Task 1: Derive `dispatch --help` agent list from `AGENT_CAPABILITY_BASELINES`

**Files:**
- Modify: `synlynk/cli.py:138` (import block), `synlynk/cli.py:407-408` (argument definition)
- Test: `tests/test_synlynk.py`

Current code at `synlynk/cli.py:138-196` (orientation only — the block is long; only line 138 itself changes, adding one import name):

```python
def main() -> None:
    from synlynk import (
        VERSION,
        SynlynkDaemon,
        SynlynkRelay,
        _CYAN,
        _GREEN,
        _RESET,
        _daemon_install_service,
        _daemon_uninstall_service,
        _reconcile_jobs,
        _update_config,
        checkpoint,
        cmd_agent_configure,
        ...
```

Current code at `synlynk/cli.py:405-408`:

```python
    dispatch_parser = subparsers.add_parser(
        "dispatch", help="Dispatch an agent to run a task in the background")
    dispatch_parser.add_argument("agent",
        help="Agent name: claude, agy, codex")
```

- [ ] **Step 1: Write the failing test — help text lists every known agent**

Add to `tests/test_synlynk.py` (the file already has `import sys`, `import pytest`, and a top-level `synlynk` import used throughout — no new imports needed):

```python
def test_dispatch_help_lists_all_known_agents(project_dir, capsys):
    old_argv = sys.argv
    sys.argv = ["synlynk", "dispatch", "--help"]
    try:
        with pytest.raises(SystemExit) as exc:
            synlynk.main()
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert exc.value.code == 0
    for agent_name in sorted(synlynk.AGENT_CAPABILITY_BASELINES):
        assert agent_name in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py::test_dispatch_help_lists_all_known_agents -v`

Expected: FAIL — `assert 'grok' in captured.out` fails, since the current hardcoded help string is `"Agent name: claude, agy, codex"` and does not contain `"grok"`.

- [ ] **Step 3: Implement the fix**

Edit `synlynk/cli.py`. In the `from synlynk import (...)` block starting at line 138, add `AGENT_CAPABILITY_BASELINES` as the first imported name (imports in this block are alphabetized after the first few uppercase constants — insert it alongside `VERSION`, `SynlynkDaemon`, `SynlynkRelay`):

```python
def main() -> None:
    from synlynk import (
        VERSION,
        AGENT_CAPABILITY_BASELINES,
        SynlynkDaemon,
        SynlynkRelay,
        _CYAN,
        _GREEN,
        _RESET,
        _daemon_install_service,
        _daemon_uninstall_service,
        _reconcile_jobs,
        _update_config,
        checkpoint,
        cmd_agent_configure,
        ...
```

(Keep every other name in that block exactly as-is — only `AGENT_CAPABILITY_BASELINES` is newly added.)

Then replace `synlynk/cli.py:405-408`:

```python
    dispatch_parser = subparsers.add_parser(
        "dispatch", help="Dispatch an agent to run a task in the background")
    dispatch_parser.add_argument("agent",
        help="Agent name: claude, agy, codex")
```

with:

```python
    dispatch_parser = subparsers.add_parser(
        "dispatch", help="Dispatch an agent to run a task in the background")
    known_agents = sorted(AGENT_CAPABILITY_BASELINES)
    dispatch_parser.add_argument("agent",
        choices=known_agents,
        help=f"Agent name: {', '.join(known_agents)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py::test_dispatch_help_lists_all_known_agents -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_synlynk.py
git commit -m "fix(cli): derive dispatch --help agent list from AGENT_CAPABILITY_BASELINES

The agent list in 'synlynk dispatch --help' was a hardcoded string
that drifted out of sync when grok was added to
AGENT_CAPABILITY_BASELINES, incorrectly implying grok wasn't a valid
dispatch target even though doctor and dispatch_agent() both already
recognized it. Deriving the help text from the same source of truth
every other agent-aware code path already uses makes this structurally
unable to drift again.

Refs #160"
```

### Task 2: Reject unrecognized agent names at the CLI layer via `choices=`

**Files:**
- Test: `tests/test_synlynk.py` (no further changes to `synlynk/cli.py` — `choices=known_agents` was already added in Task 1, Step 3)

- [ ] **Step 1: Write the failing test — invalid agent rejected before reaching `dispatch_agent()`**

Add to `tests/test_synlynk.py`:

```python
def test_dispatch_rejects_unknown_agent_before_dispatch_agent_called(project_dir, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(synlynk, "dispatch_agent", lambda *a, **kw: calls.append((a, kw)))
    old_argv = sys.argv
    sys.argv = ["synlynk", "dispatch", "nonexistent-agent", "--task", "x"]
    try:
        with pytest.raises(SystemExit) as exc:
            synlynk.main()
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert exc.value.code != 0
    assert "invalid choice" in captured.err
    assert calls == []
```

Note: this test runs *before* Task 1's fix would technically be required for `choices=` to exist — but since Task 1 already added `choices=known_agents` in its Step 3, this test is verifying that specific piece of that same change. It's written as its own task because it exercises a functionally distinct behavior (CLI-layer rejection vs. help-text content) per the design doc's two-part testing section, even though both land from the same code edit.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py::test_dispatch_rejects_unknown_agent_before_dispatch_agent_called -v`

Expected: This test should already **PASS** at this point, since Task 1 Step 3 already added `choices=known_agents` to the parser. Run it to confirm rather than expecting a failure. If it fails, re-check that Task 1's edit to `synlynk/cli.py:405-408` was applied exactly as shown (in particular, that `choices=known_agents` — not just the `help=` f-string — was included).

- [ ] **Step 3: Run the full test file to confirm no regressions**

Run: `python3 -m pytest tests/test_synlynk.py -v -k "dispatch_help_lists_all_known_agents or dispatch_rejects_unknown_agent"`

Expected: `2 passed`

- [ ] **Step 4: Run the full project test suite**

Run: `python3 -m pytest tests/ -q`

Expected: All tests pass except the known pre-existing baseline failures (unrelated to this change, confirmed present on `main` independent of any dispatch-related work): `test_packaging.py::test_detect_install_type_pip`, `test_detect_install_type_script`, `test_detect_install_type_unknown`, `test_synlynk.py::test_run_tc4_skips_flag_only_command_templates`, `test_upgrade_auto_installs_new_version`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_synlynk.py
git commit -m "test(cli): verify unknown dispatch agent rejected before dispatch_agent() runs

Refs #160"
```

---

## Notes for the implementing agent

- Both tasks touch the same two-line code change in `synlynk/cli.py` (Task 1, Step 3) — Task 2 adds no further production code, only a second test that exercises the `choices=` half of that same edit. Do not duplicate the `synlynk/cli.py` edit; it's made once, in Task 1.
- Do not change `dispatch_agent()`'s own `ValueError` check (`synlynk/dispatch.py:665-666`) — it stays as the correct guard for any caller that reaches `dispatch_agent()` directly (e.g. from tests, or other internal code), not just CLI invocations.
- Do not touch `doctor`'s agent enumeration logic — it was already correct; only the hardcoded `cli.py` help string was stale.
- `known_agents = sorted(AGENT_CAPABILITY_BASELINES)` currently evaluates to `["agy", "claude", "codex", "grok"]`. If this list changes in the future (a fifth agent added, or one removed), no code in this plan needs to change — that's the entire point of the fix.
