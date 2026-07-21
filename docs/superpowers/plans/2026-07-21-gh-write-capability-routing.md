# GitHub-Write Capability Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `synlynk dispatch` automatically route GitHub-write tasks (`gh pr review`/`gh pr merge`) away from agents that structurally can't complete them headless (Agy, Codex, local), instead of relying on dispatch-time convention.

**Architecture:** Add a `can_gh_write` boolean to each agent's entry in `AGENT_CAPABILITY_BASELINES`. Add a `--requires-gh-write` CLI flag on `synlynk dispatch`, threaded through to a new `requires_gh_write` parameter on `dispatch_agent()`. Inside `dispatch_agent()`, after the existing story-based agent resolution, check the resolved agent's `can_gh_write` baseline and reroute or warn as needed.

**Tech Stack:** Python 3, argparse, pytest.

---

### Task 1: Add `can_gh_write` to `AGENT_CAPABILITY_BASELINES`

**Files:**
- Modify: `synlynk/_constants.py:44-118`

- [ ] **Step 1: Add `can_gh_write` to each agent baseline**

Open `synlynk/_constants.py`. The `AGENT_CAPABILITY_BASELINES` dict currently looks like this (line 44 onward):

```python
AGENT_CAPABILITY_BASELINES = {
    "claude": {
        "cli": "claude",
        "non_interactive_flags": ["--print"],
        "dispatch_flags": ["--dangerously-skip-permissions"],
        "roles": ["architect", "builder"],
        "strengths": ["long context", "reasoning", "code review", "planning"],
    },
    "codex": {
        "cli": "codex",
        # 'exec' subcommand + '-' reads prompt from stdin without requiring a TTY.
        # 'codex exec' sets approval:never by default — no bypass flag needed.
        # '-s workspace-write' confines writes to workdir + /tmp while allowing
        # model-generated file edits. Do NOT add --dangerously-bypass-approvals-and-sandbox:
        # it silently overrides -s and runs at danger-full-access (full host access).
        "non_interactive_flags": [
            "exec", "-",
            "-s", "workspace-write",
        ],
        "roles": ["builder"],
        "strengths": ["code completion", "inline edits", "fast iteration"],
    },
    "agy": {
        "cli": "agy",
        "non_interactive_flags": [],
        "prompt_flag": "-p",     # placed last: agy -p "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--print", "--model", "--add-dir", "--sandbox"],
            "invalid_flags": ["--always-approve", "--non-interactive"],
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "unbuffered",
            "env_vars_required": ["PYTHONUNBUFFERED=1"],
            "non_interactive_flag": "-p",
        },
        "network_deps": {
            "required_endpoints": ["generativelanguage.googleapis.com:443", "oauth2.googleapis.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
    "grok": {
        "cli": "grok",
        "non_interactive_flags": [],
        "prompt_flag": "--single",  # placed last: grok --always-approve --single "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--always-approve", "--output-format", "--model", "--single"],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            "required_flags": ["--always-approve"],
        },
        "network_deps": {
            "required_endpoints": ["cli-chat-proxy.grok.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "architect"],
        "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
    },
    "local": {
        "cli": "aider",
        "non_interactive_flags": [],
        "dispatch_flags": ["--no-auto-commits", "--yes-always"],
        "prompt_file_flag": "--message-file",
        "network_deps": {
            "required_endpoints": ["127.0.0.1:8080"],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
    },
}
```

Add a `"can_gh_write": <bool>` key to each of the five agent dicts, per the evidence in issue #426. Result (only the added lines are new — every other line stays exactly as-is):

```python
AGENT_CAPABILITY_BASELINES = {
    "claude": {
        "cli": "claude",
        "non_interactive_flags": ["--print"],
        "dispatch_flags": ["--dangerously-skip-permissions"],
        "roles": ["architect", "builder"],
        "strengths": ["long context", "reasoning", "code review", "planning"],
        "can_gh_write": True,
    },
    "codex": {
        "cli": "codex",
        # 'exec' subcommand + '-' reads prompt from stdin without requiring a TTY.
        # 'codex exec' sets approval:never by default — no bypass flag needed.
        # '-s workspace-write' confines writes to workdir + /tmp while allowing
        # model-generated file edits. Do NOT add --dangerously-bypass-approvals-and-sandbox:
        # it silently overrides -s and runs at danger-full-access (full host access).
        "non_interactive_flags": [
            "exec", "-",
            "-s", "workspace-write",
        ],
        "roles": ["builder"],
        "strengths": ["code completion", "inline edits", "fast iteration"],
        "can_gh_write": False,
    },
    "agy": {
        "cli": "agy",
        "non_interactive_flags": [],
        "prompt_flag": "-p",     # placed last: agy -p "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--print", "--model", "--add-dir", "--sandbox"],
            "invalid_flags": ["--always-approve", "--non-interactive"],
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "unbuffered",
            "env_vars_required": ["PYTHONUNBUFFERED=1"],
            "non_interactive_flag": "-p",
        },
        "network_deps": {
            "required_endpoints": ["generativelanguage.googleapis.com:443", "oauth2.googleapis.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented"],
        "can_gh_write": False,
    },
    "grok": {
        "cli": "grok",
        "non_interactive_flags": [],
        "prompt_flag": "--single",  # placed last: grok --always-approve --single "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--always-approve", "--output-format", "--model", "--single"],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            "required_flags": ["--always-approve"],
        },
        "network_deps": {
            "required_endpoints": ["cli-chat-proxy.grok.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "architect"],
        "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
        "can_gh_write": True,
    },
    "local": {
        "cli": "aider",
        "non_interactive_flags": [],
        "dispatch_flags": ["--no-auto-commits", "--yes-always"],
        "prompt_file_flag": "--message-file",
        "network_deps": {
            "required_endpoints": ["127.0.0.1:8080"],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
        "can_gh_write": False,
    },
}
```

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `python3 -c "from synlynk._constants import AGENT_CAPABILITY_BASELINES; print(AGENT_CAPABILITY_BASELINES['grok']['can_gh_write'], AGENT_CAPABILITY_BASELINES['codex']['can_gh_write'])"`
Expected: `True False`

- [ ] **Step 3: Commit**

```bash
git add synlynk/_constants.py
git commit -m "feat: add can_gh_write capability flag to AGENT_CAPABILITY_BASELINES"
```

---

### Task 2: Add `requires_gh_write` enforcement to `dispatch_agent()`

**Files:**
- Modify: `synlynk/dispatch.py:810-830`
- Test: `tests/test_dispatch.py`

This task is TDD: write the failing tests first, then implement.

- [ ] **Step 1: Write the failing tests**

Open `tests/test_dispatch.py`. Add these five tests at the end of the file (the file already imports `from synlynk.dispatch import _format_job_summary` at the top — add the additional imports shown inside each test, matching the existing style in this file):

```python
def test_dispatch_agent_requires_gh_write_false_is_noop(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent("agy", "write docs", story_id="story-manual-1", context_mode="none")

    assert job["agent"] == "agy"


def test_dispatch_agent_requires_gh_write_true_capable_agent_unchanged(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent(
        "grok", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, force_agent=True,
    )

    assert job["agent"] == "grok"


def test_dispatch_agent_requires_gh_write_reroutes_incapable_agent(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent(
        "agy", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True,
    )

    assert job["agent"] != "agy"
    assert sl.AGENT_CAPABILITY_BASELINES[job["agent"]]["can_gh_write"] is True
    captured = capsys.readouterr()
    assert "rerouted" in captured.out
    assert "#426" in captured.out


def test_dispatch_agent_requires_gh_write_force_agent_warns_and_proceeds(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent(
        "codex", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, force_agent=True,
    )

    assert job["agent"] == "codex"
    captured = capsys.readouterr()
    assert "codex" in captured.err
    assert "#426" in captured.err


def test_dispatch_agent_requires_gh_write_raises_when_no_capable_agent(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    no_capable = {
        name: {**baseline, "can_gh_write": False}
        for name, baseline in sl.AGENT_CAPABILITY_BASELINES.items()
    }
    monkeypatch.setattr(dispatch_mod, "AGENT_CAPABILITY_BASELINES", no_capable)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    with pytest.raises(ValueError, match="can_gh_write"):
        sl.dispatch_agent(
            "agy", "review and merge PR #500", story_id="story-manual-1",
            context_mode="none", requires_gh_write=True,
        )
```

Check the top of `tests/test_dispatch.py` for a `pytest` import — if it's not already imported, add `import pytest` alongside the existing `from synlynk.dispatch import _format_job_summary` line.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k requires_gh_write -v`
Expected: FAIL — `TypeError: dispatch_agent() got an unexpected keyword argument 'requires_gh_write'` on every test.

- [ ] **Step 3: Add the `requires_gh_write` parameter and enforcement logic**

Open `synlynk/dispatch.py`. Find the `dispatch_agent` signature and story-resolution block (currently lines 810-830):

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None) -> dict:
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    dispatch_time = None
    if not story_id:
        dispatch_time = time.time()
    if story_id and not force_agent:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                agent = best

    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")
```

Replace it with (adds the `requires_gh_write` parameter and the enforcement block right after the existing story-based resolution, before the unknown-agent check):

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   requires_gh_write: bool = False) -> dict:
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    dispatch_time = None
    if not story_id:
        dispatch_time = time.time()
    if story_id and not force_agent:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                agent = best

    if requires_gh_write:
        current_baseline = baselines_map.get(agent, {})
        if not current_baseline.get("can_gh_write", False):
            capable_agents = [
                name for name, baseline in baselines_map.items()
                if baseline.get("can_gh_write", False)
            ]
            if not capable_agents:
                raise ValueError(
                    "No agent in AGENT_CAPABILITY_BASELINES has can_gh_write: True"
                )
            if force_agent:
                print(
                    f"  ⚠ '{agent}' cannot reliably complete GitHub-write actions "
                    f"headless (see #426) — proceeding because --force-agent was set",
                    file=sys.stderr,
                )
            else:
                rerouted_to = capable_agents[0]
                print(
                    f"  ↪ rerouted '{agent}' -> '{rerouted_to}' "
                    f"(--requires-gh-write; '{agent}' cannot do this headless, see #426)"
                )
                agent = rerouted_to

    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")
```

Check the top of `synlynk/dispatch.py` for `import sys` — it's needed for the `file=sys.stderr` call. If it's not already imported, add `import sys` to the module's import block.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_dispatch.py -k requires_gh_write -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Run the full dispatch test suite to check for regressions**

Run: `pytest tests/test_dispatch.py tests/test_synlynk.py tests/test_dispatch_cycle.py tests/test_agy_dispatch_fix.py tests/test_cost_ledger.py -v`
Expected: PASS — no existing test's behavior changed, since `requires_gh_write` defaults to `False` and every branch above is gated on it being `True`.

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: add requires_gh_write enforcement to dispatch_agent()"
```

---

### Task 3: Add `--requires-gh-write` CLI flag

**Files:**
- Modify: `synlynk/cli.py:423-428` (dispatch_parser arguments)
- Modify: `synlynk/cli.py:836-842` (dispatch_agent call site)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_dispatch.py`:

```python
def test_cli_dispatch_passes_requires_gh_write_flag(project_dir, monkeypatch):
    import synlynk.cli as cli_mod
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["requires_gh_write"] = kwargs.get("requires_gh_write")
        return {"id": "job-test", "pid": 1, "fence": None}

    monkeypatch.setattr(cli_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "grok", "--task", "review and merge PR #500",
         "--requires-gh-write", "--force-agent"],
    )

    cli_mod.main()

    assert captured["requires_gh_write"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_dispatch.py::test_cli_dispatch_passes_requires_gh_write_flag -v`
Expected: FAIL — `error: unrecognized arguments: --requires-gh-write` (argparse exits via `SystemExit`, so the test fails with that error surfacing, or with `captured["requires_gh_write"]` being `None`/`KeyError` if argparse silently drops it — either way, not `True`).

- [ ] **Step 3: Add the CLI flag**

Open `synlynk/cli.py`. Find this block (currently around line 423-428):

```python
    dispatch_parser.add_argument("--force-agent", action="store_true", dest="force_agent",
        help="Bypass capability routing — dispatch to the exact agent specified")
    dispatch_parser.add_argument(
        "--context-mode", choices=["none", "task", "full"], default="task",
        dest="context_mode", help="Context injection mode"
    )
```

Replace it with:

```python
    dispatch_parser.add_argument("--force-agent", action="store_true", dest="force_agent",
        help="Bypass capability routing — dispatch to the exact agent specified")
    dispatch_parser.add_argument("--requires-gh-write", action="store_true", dest="requires_gh_write",
        help="Task needs gh pr review/merge — reroute to a capable agent unless --force-agent is set (see #426)")
    dispatch_parser.add_argument(
        "--context-mode", choices=["none", "task", "full"], default="task",
        dest="context_mode", help="Context injection mode"
    )
```

- [ ] **Step 4: Pass the flag through at the call site**

Find the `dispatch_agent` call site (currently around line 836-842):

```python
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None))
```

Replace it with:

```python
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 requires_gh_write=getattr(args, "requires_gh_write", False))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_dispatch.py::test_cli_dispatch_passes_requires_gh_write_flag -v`
Expected: PASS

- [ ] **Step 6: Run the full test suite**

Run: `pytest -q`
Expected: PASS — all tests green, no regressions anywhere in the suite.

- [ ] **Step 7: Commit**

```bash
git add synlynk/cli.py tests/test_dispatch.py
git commit -m "feat: add --requires-gh-write CLI flag to synlynk dispatch"
```

---

### Task 4: Update routing SOP doc to reference the new flag

**Files:**
- Modify: `CLAUDE.md` (or wherever the "Capability-Based Task Allocation" / routing SOP text lives — check `synlynk/probe.py`'s `_CAPABILITY_ALLOCATION_SOP` for the canonical source, same file(s) touched by the earlier docs-only #423/#426 fix)

- [ ] **Step 1: Find the canonical SOP text source**

Run: `grep -rn "_CAPABILITY_ALLOCATION_SOP\|GitHub write actions" synlynk/probe.py CLAUDE.md`

This locates the single source of truth for the routing table text (likely a Python string constant in `synlynk/probe.py` that gets written into `CLAUDE.md`/`GEMINI.md`/`GROK.md`/`AGENTS.md` by `synlynk init`, and the already-updated project-root `CLAUDE.md` from the prior docs-only PR).

- [ ] **Step 2: Add one sentence noting the flag exists**

Wherever the "GitHub write actions (pr review/merge) -> Grok only" note was added by the earlier docs-only fix, append one sentence: `Pass --requires-gh-write on synlynk dispatch to have this enforced automatically instead of relying on manual routing (see #426).` Apply the same one-line addition to every file that carries a copy of this text (mirror whatever the earlier docs-only PR touched — likely `CLAUDE.md` and the `_CAPABILITY_ALLOCATION_SOP` constant if it's the generation source).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md synlynk/probe.py
git commit -m "docs: note --requires-gh-write flag in routing SOP"
```

(If `synlynk/probe.py` wasn't touched because the SOP text isn't generated from there, adjust the `git add` to whatever files were actually edited in Step 2.)

---

## Self-Review Notes

- **Spec coverage:** Task 1 covers the spec's `can_gh_write` baseline additions. Task 2 covers all 5 testing scenarios from the spec's Testing section (no-op default, capable-agent pass-through, reroute, force-agent-warns, no-capable-agent error) plus the enforcement logic itself. Task 3 covers the `--requires-gh-write` CLI flag and its wiring through the call site. Task 4 closes the loop on the spec's implicit expectation that the SOP doc (already updated by the separate docs-only PR) references the new automated mechanism once it exists.
- **Placeholder scan:** No TBD/TODO; every step has literal code or an exact command.
- **Type consistency:** `requires_gh_write: bool = False` is used identically in the `dispatch_agent()` signature (Task 2) and the CLI call site (Task 3). `can_gh_write` key name matches between Task 1 (baseline dict) and Task 2 (enforcement logic reading `baseline.get("can_gh_write", False)`).
