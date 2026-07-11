# Codex Worktree git-ref Write Blocking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Codex dispatch jobs from failing to create new git branches/refs inside their isolated worktree, by widening Codex's sandboxed writable roots to include the main repo's shared git ref store.

**Architecture:** `dispatch_agent()` in `synlynk/dispatch.py` already mutates the `flags` list per-agent (see the existing `if agent == "grok":` blocks). This plan adds one more such block for `agent == "codex"` that resolves the main repo's git-common-dir via `git rev-parse --path-format=absolute --git-common-dir` and appends `--add-dir <that-path>` to `flags`, so the `codex exec -s workspace-write` process it later runs (via `subprocess.Popen(["sh", "-c", shell_cmd], ...)`, `dispatch.py:806-812`) is explicitly granted write access to the shared ref store, not just its own worktree.

**Tech Stack:** Python 3, stdlib `subprocess`, pytest (existing `tests/test_agy_dispatch_fix.py` conventions — `monkeypatch.setattr(sl.subprocess, "run"/"Popen", ...)`).

**Tracks:** [#161](https://github.com/nikhilsoman/synlynk/issues/161). Full root-cause writeup and validated reproduction: `docs/superpowers/specs/2026-07-11-codex-worktree-git-refs-design.md`.

---

### Task 1: Add `--add-dir <git-common-dir>` to Codex dispatch flags

**Files:**
- Modify: `synlynk/dispatch.py:704-709` (inside `dispatch_agent()`, immediately after the existing `if agent == "grok":` blocks, before the `probe_model = _pkg(...)` line at `:711`)
- Test: `tests/test_agy_dispatch_fix.py`

Current code at `synlynk/dispatch.py:704-710` (for orientation — do not change these lines, insert after them):

```python
    load_profile = _pkg("_load_agent_profile")
    profile = load_profile(agent) if load_profile else {}
    dispatch_mode = (cfg or {}).get("dispatch_mode", "daily-grind") if load_config else "daily-grind"
    if agent == "grok" and profile.get("always_approve_unsupported"):
        flags = [flag for flag in flags if flag != "--always-approve"]
        flags = flags + ["--permission-mode", "bypassPermissions"]
    if agent == "grok":
        flags = flags + ["--output-format", "json"]

    probe_model = _pkg("_probe_model_version")
```

- [ ] **Step 1: Write the failing test — success case**

Add to `tests/test_agy_dispatch_fix.py` (append at end of file; the file already has `import hashlib`, `import os`, `import subprocess`, `import pytest` at the top — no new imports needed):

```python
def test_dispatch_codex_adds_git_common_dir_as_writable(git_worktree_repo, monkeypatch):
    import synlynk as sl

    calls = []

    class FakeProc:
        pid = 4242

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if cmd[:2] == ["git", "worktree"]:
            class WorktreeResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return WorktreeResult()
        if cmd[:2] == ["git", "rev-parse"]:
            class RevParseResult:
                returncode = 0
                stdout = "/fake/repo/.git\n"
                stderr = ""
            return RevParseResult()
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    captured_popen = {}

    def fake_popen(cmd, **kwargs):
        captured_popen["cmd"] = cmd
        captured_popen["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)

    sl.dispatch_agent("codex", "fix bug", skip_preflight=True)

    rev_parse_calls = [c for c in calls if c[0][:2] == ["git", "rev-parse"]]
    assert len(rev_parse_calls) == 1
    assert rev_parse_calls[0][0] == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
    assert rev_parse_calls[0][1]["cwd"] == os.getcwd()

    shell_cmd = captured_popen["cmd"][2]
    assert "--add-dir /fake/repo/.git" in shell_cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_codex_adds_git_common_dir_as_writable -v`

Expected: FAIL — either an `AssertionError: unexpected subprocess.run call: ['git', 'rev-parse', ...]` (if the fake_run raises on an unexpected call because the real code never makes it) or, more likely, `assert len(rev_parse_calls) == 1` fails with `0 == 1` because `dispatch_agent()` never calls `git rev-parse` yet.

- [ ] **Step 3: Implement the fix**

Edit `synlynk/dispatch.py`. Insert this block immediately after the existing `if agent == "grok": flags = flags + ["--output-format", "json"]` line and before `probe_model = _pkg("_probe_model_version")`:

```python
    if agent == "codex":
        try:
            git_common_dir_result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True, text=True, cwd=os.getcwd(), timeout=5,
            )
            if git_common_dir_result.returncode == 0:
                git_common_dir = git_common_dir_result.stdout.strip()
                flags = flags + ["--add-dir", git_common_dir]
        except Exception:
            pass
```

The full surrounding region should read:

```python
    load_profile = _pkg("_load_agent_profile")
    profile = load_profile(agent) if load_profile else {}
    dispatch_mode = (cfg or {}).get("dispatch_mode", "daily-grind") if load_config else "daily-grind"
    if agent == "grok" and profile.get("always_approve_unsupported"):
        flags = [flag for flag in flags if flag != "--always-approve"]
        flags = flags + ["--permission-mode", "bypassPermissions"]
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    if agent == "codex":
        try:
            git_common_dir_result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True, text=True, cwd=os.getcwd(), timeout=5,
            )
            if git_common_dir_result.returncode == 0:
                git_common_dir = git_common_dir_result.stdout.strip()
                flags = flags + ["--add-dir", git_common_dir]
        except Exception:
            pass

    probe_model = _pkg("_probe_model_version")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_codex_adds_git_common_dir_as_writable -v`

Expected: PASS

- [ ] **Step 5: Write the failing test — failure/defense-in-depth case**

Add to `tests/test_agy_dispatch_fix.py`:

```python
def test_dispatch_codex_skips_add_dir_when_git_rev_parse_fails(git_worktree_repo, monkeypatch):
    import synlynk as sl

    class FakeProc:
        pid = 4242

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "worktree"]:
            class WorktreeResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return WorktreeResult()
        if cmd[:2] == ["git", "rev-parse"]:
            class RevParseResult:
                returncode = 128
                stdout = ""
                stderr = "fatal: not a git repository\n"
            return RevParseResult()
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    captured_popen = {}

    def fake_popen(cmd, **kwargs):
        captured_popen["cmd"] = cmd
        captured_popen["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)

    job = sl.dispatch_agent("codex", "fix bug", skip_preflight=True)

    assert job["id"]
    shell_cmd = captured_popen["cmd"][2]
    assert "--add-dir" not in shell_cmd
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_codex_skips_add_dir_when_git_rev_parse_fails -v`

Expected: This test should actually **PASS immediately** given the Step 3 implementation (the `if git_common_dir_result.returncode == 0:` guard already skips appending on non-zero return code) — there is no separate implementation step needed. Run it to confirm this rather than expecting a failure. If it fails, the `returncode == 0` guard in Step 3 was not applied correctly — re-check the edit.

- [ ] **Step 7: Run the full test file to confirm no regressions**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py -v`

Expected: All tests PASS, including the two new ones and the pre-existing `test_dispatch_perjob_git_worktree_isolation_*` tests (which dispatch `agent="codex"` too — confirm they still pass since they use `fake_run` functions that return a single Result object for every call, which the codex `--add-dir` block's `git rev-parse` call will also receive; check their `Result.returncode` defaults to `0` and `stdout` defaults to `""` — `git_common_dir_result.stdout.strip()` on an empty string yields `""`, so `flags = flags + ["--add-dir", ""]` will be appended in those tests too. This is harmless for those tests since they don't assert on `--add-dir` absence, but confirm no assertion in those tests breaks on the extra flag being present.)

- [ ] **Step 8: Run the full project test suite**

Run: `python3 -m pytest tests/ -q`

Expected: All tests pass except the known pre-existing baseline failures (unrelated to this change): `test_packaging.py::test_detect_install_type_pip`, `test_detect_install_type_script`, `test_detect_install_type_unknown`, `test_synlynk.py::test_run_tc4_skips_flag_only_command_templates`, `test_upgrade_auto_installs_new_version`.

- [ ] **Step 9: Commit**

```bash
git add synlynk/dispatch.py tests/test_agy_dispatch_fix.py
git commit -m "fix(dispatch): add --add-dir <git-common-dir> to codex sandbox flags

Codex's -s workspace-write sandbox blocks creating new refs in the
main repo's shared .git/refs/heads/ (git worktrees don't have their
own ref store), which silently broke any git checkout -b / commit
that needed a new ref from inside a dispatched Codex job. Widening
the sandbox's writable roots to include the git-common-dir (resolved
via git rev-parse, not hardcoded to <cwd>/.git so it still works from
nested worktrees) fixes it without loosening the sandbox mode itself.

Closes #161"
```

---

## Notes for the implementing agent

- Do not add a corresponding block for any other agent (`claude`, `agy`, `grok`) — none of them run under a directory-scoped OS sandbox the way Codex's `-s workspace-write` does, so this fix is intentionally Codex-only. See the design doc's "Why Codex-only, inline" section if asked to generalize this.
- Do not change Codex's sandbox mode (`-s workspace-write` stays as-is) and do not add `--dangerously-bypass-approvals-and-sandbox` anywhere — that flag silently grants full host access and is explicitly called out as unsafe in the existing comment at `synlynk/_constants.py:53-56`.
- The `timeout=5` on the `git rev-parse` subprocess call matches the existing `timeout=3` pattern used for `[agent_name, "--version"]` probes elsewhere in `dispatch.py:527` — kept slightly higher here since `rev-parse` can be marginally slower on large repos, but there's no hard requirement backing the exact number; 5s is a reasonable ceiling that will never realistically be hit for a local `git rev-parse`.
