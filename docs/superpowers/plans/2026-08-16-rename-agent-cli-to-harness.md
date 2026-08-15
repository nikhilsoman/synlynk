# Rename synlynk agent CLI to harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `synlynk agent add/configure/run/list` CLI verb group to `synlynk harness add/configure/run/list`, freeing the `agent` top-level verb for Task #97's new role-identity commands.

**Architecture:** Single-file argparse change in `synlynk/cli.py` (subparser group + dispatch block), no changes to the underlying `cmd_agent_*` Python functions. One existing CLI-route test updates its `sys.argv` fixture to match.

**Tech Stack:** Python 3 stdlib (`argparse`), `pytest`.

---

### Task 1: Update the CLI-route test to the new `harness` verb

**Files:**
- Modify: `tests/test_roles.py:229-241`

- [ ] **Step 1: Update the failing-first test**

Replace the existing `test_agent_add_cli_route` test (lines 229-241) with:

```python
def test_agent_add_cli_route(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(synlynk, "cmd_agent_add", lambda name: calls.append(name))

    old_argv = sys.argv
    sys.argv = ["synlynk", "harness", "add", "codex"]
    try:
        synlynk.main()
    finally:
        sys.argv = old_argv

    assert calls == ["codex"]


def test_agent_run_cli_route_parses_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        synlynk, "cmd_agent_run",
        lambda name, dry_run=False, install_cron=False: calls.append((name, dry_run, install_cron)),
    )

    old_argv = sys.argv
    sys.argv = ["synlynk", "harness", "run", "claude", "--dry-run"]
    try:
        synlynk.main()
    finally:
        sys.argv = old_argv

    assert calls == [("claude", True, False)]


def test_agent_verb_no_longer_recognized(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    old_argv = sys.argv
    sys.argv = ["synlynk", "agent", "add", "codex"]
    try:
        with pytest.raises(SystemExit):
            synlynk.main()
    finally:
        sys.argv = old_argv
```

This test file already imports `sys` and `synlynk` (used by the existing test at line 237). Check whether `pytest` is already imported at the top of `tests/test_roles.py`:

```bash
grep -n "^import pytest" tests/test_roles.py
```

If that grep produces no output, add `import pytest` to the top of `tests/test_roles.py` alongside the existing imports.

- [ ] **Step 2: Run the new/updated tests to verify they fail**

Run: `python3 -m pytest tests/test_roles.py -k "agent_add_cli_route or agent_run_cli_route_parses_dry_run or agent_verb_no_longer_recognized" -v`

Expected: `test_agent_add_cli_route` FAILs (argparse still only recognizes `agent`, not `harness` — `SystemExit: 2` from unrecognized command). `test_agent_run_cli_route_parses_dry_run` FAILs the same way. `test_agent_verb_no_longer_recognized` PASSes already (it exercises today's existing behavior, `agent` currently works, so it currently does NOT raise `SystemExit`) — note this one is actually expected to FAIL right now since `agent add codex` currently succeeds. All three failing/wrong-direction results at this point confirm the tests are wired to the target (post-rename) behavior, not accidentally already passing.

- [ ] **Step 3: Commit the test change**

```bash
git add tests/test_roles.py
git commit -m "test: update agent CLI-route test to harness verb, ahead of rename"
```

---

### Task 2: Rename the `agent` subparser group and dispatch block to `harness`

**Files:**
- Modify: `synlynk/cli.py:467-481` (subparser block)
- Modify: `synlynk/cli.py` (the `help_parsers` dict literal containing `"agent": agent_parser,` — locate via grep, originally observed near line 881)
- Modify: `synlynk/cli.py:1297-1311` (dispatch block)

- [ ] **Step 1: Replace the subparser block**

Find this block in `synlynk/cli.py` (originally at lines 467-481):

```python
    agent_parser = subparsers.add_parser("agent", help="Manage and run autopilot agents")
    agent_sub = agent_parser.add_subparsers(dest="agent_action")
    agent_add_parser = agent_sub.add_parser("add", help="Retrofit an on-PATH agent into this project")
    agent_add_parser.add_argument("name", help="Agent binary name on PATH")
    agent_configure_parser = agent_sub.add_parser("configure", help="Interactively write .agents/<name>.json context profile")
    agent_configure_parser.add_argument("name", help="Agent name: claude, agy, codex, grok")
    agent_run_parser = agent_sub.add_parser("run", help="Run a named agent once")
    agent_run_parser.add_argument("name", help="Agent name (matches .agents/<name>.json)")
    agent_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="Collect signals and print findings; no dispatch/issue/PR")
    agent_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron", help="Install local crontab entry for this agent")
    agent_sub.add_parser("list", help="List .agents/ configs and last run status")
```

Replace it with:

```python
    harness_parser = subparsers.add_parser("harness", help="Manage and run autopilot harnesses")
    harness_sub = harness_parser.add_subparsers(dest="harness_action")
    harness_add_parser = harness_sub.add_parser("add", help="Retrofit an on-PATH harness into this project")
    harness_add_parser.add_argument("name", help="Harness binary name on PATH")
    harness_configure_parser = harness_sub.add_parser("configure", help="Interactively write .agents/<name>.json context profile")
    harness_configure_parser.add_argument("name", help="Harness name: claude, agy, codex, grok")
    harness_run_parser = harness_sub.add_parser("run", help="Run a named harness once")
    harness_run_parser.add_argument("name", help="Harness name (matches .agents/<name>.json)")
    harness_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="Collect signals and print findings; no dispatch/issue/PR")
    harness_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron", help="Install local crontab entry for this harness")
    harness_sub.add_parser("list", help="List .agents/ configs and last run status")
```

Preserve the exact indentation of the original block (match whatever indent level the surrounding code in `build_parser()` uses — do not reformat).

- [ ] **Step 2: Update the `help_parsers` dict registration**

Locate the dict literal assigned to `parser._synlynk_help_parsers` (or a similarly named `help_parsers` variable) inside `build_parser()`. Find the line:

```python
        "agent": agent_parser,
```

Replace it with:

```python
        "harness": harness_parser,
```

Confirm via:

```bash
grep -n '"agent": agent_parser' synlynk/cli.py
```

Expected: no output after the edit (zero matches).

- [ ] **Step 3: Replace the dispatch block**

Find this block in `synlynk/cli.py` (originally at lines 1297-1311):

```python
    elif args.command == "agent":
        action = getattr(args, "agent_action", None)
        if action == "add":
            cmd_agent_add(args.name)
        elif action == "configure":
            cmd_agent_configure(args.name)
        elif action == "run":
            cmd_agent_run(
                args.name,
                dry_run=getattr(args, "dry_run", False),
                install_cron=getattr(args, "install_cron", False),
            )
        elif action == "list":
            cmd_agent_list()
        else:
            help_parsers.get("agent", parser).print_help()
```

Replace it with:

```python
    elif args.command == "harness":
        action = getattr(args, "harness_action", None)
        if action == "add":
            cmd_agent_add(args.name)
        elif action == "configure":
            cmd_agent_configure(args.name)
        elif action == "run":
            cmd_agent_run(
                args.name,
                dry_run=getattr(args, "dry_run", False),
                install_cron=getattr(args, "install_cron", False),
            )
        elif action == "list":
            cmd_agent_list()
        else:
            help_parsers.get("harness", parser).print_help()
```

Note: `cmd_agent_add`, `cmd_agent_configure`, `cmd_agent_run`, `cmd_agent_list` — the imported function names — do **not** change. Only the `args.command` string, the `harness_action` attribute name, and the `help_parsers` lookup key change.

Do not touch any other `args.command ==` branch, and do not touch `dispatch_parser`'s `agent` positional argument (cli.py:576-579), `open_parser`'s `agent` positional (cli.py:702), `cmd_probe(agent=...)` (cli.py:1274, 1387), `cmd_quota(agent=...)`/its preview print (cli.py:1113), or the `configure agent` branch (cli.py:1421-onward) — these are explicitly out of scope per the design spec §2.

- [ ] **Step 4: Run the full test suite**

Run: `python3 -m pytest tests/ -q`

Expected: all tests pass, including the three from Task 1 (`test_agent_add_cli_route`, `test_agent_run_cli_route_parses_dry_run`, `test_agent_verb_no_longer_recognized` all PASS now).

If any other test fails referencing `"agent"` CLI routing (not caught in the pre-implementation grep), read the failure, confirm it's a stale reference to the old `agent` verb specifically (not a false positive from `--agent`/`dispatch <agent>`/`open <agent>`/`configure agent`, which are unaffected by this change), and update it to `harness` following the same pattern as Task 1.

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py
git commit -m "feat: rename synlynk agent CLI group to harness

Frees the agent verb for Task #97's new role-identity commands.
cmd_agent_add/configure/run/list function names are unchanged —
only the CLI verb, harness_action dest, and help_parsers key move.

See docs/superpowers/specs/2026-08-16-rename-agent-cli-to-harness-design.md"
```

---

### Task 3: Final full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite one more time from a clean tree**

```bash
git status --short
python3 -m pytest tests/ -q
```

Expected: `git status --short` shows no uncommitted changes (Task 2 Step 5 already committed everything). Full suite passes with 0 failures.

- [ ] **Step 2: Manually smoke-test the renamed CLI**

```bash
python3 bin/synlynk.py harness --help
python3 bin/synlynk.py harness add --help
python3 bin/synlynk.py agent --help
```

Expected: the first two print help text for the new `harness` group and its `add` subcommand. The third (`agent --help`) exits non-zero with argparse's "invalid choice" error, since no `agent` verb exists yet (Task #97 will add one later) — this confirms the old verb is genuinely gone, not just aliased.
