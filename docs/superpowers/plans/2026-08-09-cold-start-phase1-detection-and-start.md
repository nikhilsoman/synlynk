# Cold-Start Phase 1: Detection + `synlynk start` + New-Project Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Role split reminder (this repo's CLAUDE.md):** the controller coordinating this plan (Claude) does not write implementation code directly. Each task below is written so its full text can be handed to `python3 -m synlynk dispatch <agy|grok|codex> --task "..." --force-agent --context-mode full`. Reviewer/spec-compliance stages stay with Claude.

**Goal:** Add a new `synlynk start` command that silently detects whether the current directory is a brand-new or existing project (asking a single confirm only when genuinely ambiguous), runs a 4-question intent-capture flow for new projects, and runs a shallow env-probe + single-question flow for existing projects — ending every run with one concrete next action.

**Architecture:** One new focused module, `synlynk/coldstart.py`, holding detection heuristics and both cold-start flows. It reuses existing primitives rather than duplicating them: `_static_scan()` and `discover_agents()`/`run_workspace_scan()` for signals, `init()` for new-project bootstrap (config + docs + agent files), and `cmd_roadmap_add()` / `cmd_story_create()` (both in `synlynk/db.py`) for writing the captured intent into the existing roadmap/todo data model rather than hand-editing markdown. `cli.py` gets a new `start` subparser and one new `elif` branch in `main()`.

**Tech Stack:** Python 3 stdlib only (argparse, subprocess, os, json) — matches the rest of the codebase. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-09-cold-start-design.md` — this plan covers the "Detection: new vs. existing" and "New-project path" sections in full, and the *baseline* (non-canon) portion of "Existing-project path" (env-probe, shallow scan summary, one question, zero-harness banner, re-run refresh prompt). Canon file generation (`workspace-canon.md`) is explicitly out of scope for this plan — see Phase 2.

---

## File Structure

- **Create:** `synlynk/coldstart.py` — detection heuristics, ambiguous-case confirm, new-project flow, existing-project baseline flow, `cmd_start()` orchestrator.
- **Create:** `tests/test_coldstart.py` — unit + integration tests for all of the above.
- **Modify:** `synlynk/cli.py` — add `start` subparser (`build_parser()`, near the `init`/`join` parsers) and one `elif args.command == "start":` branch in `main()`.

## Task 1: Detection heuristics

**Files:**
- Create: `synlynk/coldstart.py`
- Test: `tests/test_coldstart.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_coldstart.py
import os
import subprocess

import pytest

from synlynk.coldstart import _detect_cold_start_mode


def _git_init(root, commits=0, files=None):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
    for fname, content in (files or {}).items():
        (root / fname).write_text(content)
    for i in range(commits):
        (root / f"commit_{i}.txt").write_text(str(i))
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"commit {i}"], cwd=root, capture_output=True, check=True)


def test_detect_confident_new_empty_dir(tmp_path):
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "new"


def test_detect_confident_new_git_zero_commits_no_content(tmp_path):
    _git_init(tmp_path, commits=0)
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "new"


def test_detect_ambiguous_git_zero_commits_with_readme(tmp_path):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray readme\n"})
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "ambiguous"


def test_detect_confident_existing_with_commits_and_manifest(tmp_path):
    _git_init(tmp_path, commits=3, files={"package.json": "{}"})
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "existing"
    assert result["signals"]["commit_count"] == 3


def test_detect_ambiguous_commits_but_no_recognizable_files(tmp_path):
    (tmp_path / ".git").mkdir()  # not a real repo — has_git True via os.path.isdir check
    result = _detect_cold_start_mode(str(tmp_path))
    # a .git dir with no working commits and no content is still "new" (fresh git init)
    assert result["mode"] == "new"


def test_detect_ambiguous_no_git_but_project_files_present(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "ambiguous"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coldstart.py -v`
Expected: `ModuleNotFoundError: No module named 'synlynk.coldstart'`

- [ ] **Step 3: Write the detection implementation**

```python
# synlynk/coldstart.py
"""Cold-start detection and entry flows for `synlynk start`.

Detects whether the current directory is a brand-new project, an existing
one, or genuinely ambiguous, then routes to the appropriate flow. See
docs/superpowers/specs/2026-08-09-cold-start-design.md for the full design.
"""
import os
import subprocess

_MANIFEST_FILES = (
    "package.json", "pyproject.toml", "setup.py", "requirements.txt",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Gemfile",
)
_README_FILES = ("README.md", "README.rst", "README.txt", "README")


def _commit_count(root: str) -> int:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return 0
        return int(result.stdout.strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0


def _detect_cold_start_mode(root: str = ".") -> dict:
    """Returns {"mode": "new"|"existing"|"ambiguous", "reason": str, "signals": dict}.

    Heuristics (see spec "Detection: new vs. existing"):
    - No .git, no manifest/README, no visible files -> confident new.
    - .git present, 0 commits, no manifest/README -> confident new (fresh `git init`).
    - .git present, 0 commits, manifest/README present -> ambiguous (forked/cloned
      scaffold not yet committed).
    - .git present, commits > 0, manifest/README/other files present -> confident existing.
    - .git present, commits > 0, nothing recognizable -> ambiguous.
    - No .git, but manifest/README present -> ambiguous (project files without git yet).
    """
    has_git = os.path.isdir(os.path.join(root, ".git"))
    has_manifest = any(os.path.exists(os.path.join(root, f)) for f in _MANIFEST_FILES)
    has_readme = any(os.path.exists(os.path.join(root, f)) for f in _README_FILES)
    try:
        visible_files = [f for f in os.listdir(root) if not f.startswith(".")]
    except OSError:
        visible_files = []
    commit_count = _commit_count(root) if has_git else 0

    signals = {
        "has_git": has_git,
        "has_manifest": has_manifest,
        "has_readme": has_readme,
        "commit_count": commit_count,
        "visible_file_count": len(visible_files),
    }

    if not has_git:
        if has_manifest or has_readme:
            return {"mode": "ambiguous",
                    "reason": "project files present but no git repo yet",
                    "signals": signals}
        return {"mode": "new", "reason": "empty directory, no git", "signals": signals}

    if commit_count == 0:
        if has_manifest or has_readme:
            return {"mode": "ambiguous",
                    "reason": "git initialized but 0 commits, with existing content "
                              "(fork/clone scaffold?)",
                    "signals": signals}
        return {"mode": "new",
                "reason": "git initialized, 0 commits, no content",
                "signals": signals}

    if has_manifest or has_readme or visible_files:
        return {"mode": "existing",
                "reason": f"{commit_count} commit(s), project files present",
                "signals": signals}

    return {"mode": "ambiguous",
            "reason": f"{commit_count} commit(s) but no recognizable project files",
            "signals": signals}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "feat: add cold-start mode detection heuristics"
```

## Task 2: Ambiguous-case confirm

**Files:**
- Modify: `synlynk/coldstart.py`
- Test: `tests/test_coldstart.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_coldstart.py
from synlynk.coldstart import _resolve_cold_start_mode


def test_resolve_confident_mode_does_not_prompt(tmp_path, monkeypatch):
    def _fail_input(prompt):
        raise AssertionError("should not prompt when detection is confident")
    monkeypatch.setattr("builtins.input", _fail_input)
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "new"


def test_resolve_ambiguous_mode_prompts_and_honors_existing_answer(tmp_path, monkeypatch):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray\n"})
    monkeypatch.setattr("builtins.input", lambda prompt: "existing")
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "existing"


def test_resolve_ambiguous_mode_prompts_and_honors_new_answer(tmp_path, monkeypatch):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray\n"})
    monkeypatch.setattr("builtins.input", lambda prompt: "new")
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "new"


def test_resolve_ambiguous_mode_defaults_to_existing_on_empty_answer(tmp_path, monkeypatch):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray\n"})
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "existing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coldstart.py -k resolve -v`
Expected: `ImportError: cannot import name '_resolve_cold_start_mode'`

- [ ] **Step 3: Implement the resolver**

Append to `synlynk/coldstart.py`:

```python
def _resolve_cold_start_mode(root: str = ".") -> str:
    """Runs detection; prompts a single one-line confirm only if ambiguous.

    Returns "new" or "existing" (never "ambiguous" — the prompt collapses it).
    Empty/unrecognized answers default to "existing" (the safer assumption —
    treating an existing project as new would risk overwriting content).
    """
    detected = _detect_cold_start_mode(root)
    if detected["mode"] != "ambiguous":
        return detected["mode"]

    answer = input(
        f"Looks like an existing project ({detected['reason']}) — "
        f"is that right, or are we starting fresh? [existing/new] "
    ).strip().lower()
    if answer in ("new", "n"):
        return "new"
    return "existing"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -k resolve -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "feat: add one-line confirm for ambiguous cold-start detection"
```

## Task 3: New-project flow

**Files:**
- Modify: `synlynk/coldstart.py`
- Test: `tests/test_coldstart.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_coldstart.py
from synlynk.coldstart import _prompt_new_project_questions, _run_new_project_flow


def test_prompt_new_project_questions_collects_four_answers(monkeypatch):
    answers = iter([
        "Build a recipe-sharing CLI",
        "a Python CLI package",
        "solo",
        "codex",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    result = _prompt_new_project_questions()
    assert result == {
        "goal": "Build a recipe-sharing CLI",
        "deliverable_shape": "a Python CLI package",
        "team_mode": "solo",
        "preferred_implementer": "codex",
    }


def test_prompt_new_project_questions_implementer_optional(monkeypatch):
    answers = iter(["Goal", "Shape", "team", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    result = _prompt_new_project_questions()
    assert result["preferred_implementer"] is None
    assert result["team_mode"] == "team"


def test_run_new_project_flow_writes_config_and_roadmap_row(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    answers = {
        "goal": "Build a recipe-sharing CLI",
        "deliverable_shape": "a Python CLI package",
        "team_mode": "solo",
        "preferred_implementer": None,
    }
    _run_new_project_flow(answers)

    assert os.path.exists(".synlynk/config.json")
    assert os.path.exists("project-docs/roadmap.md")
    roadmap_text = open("project-docs/roadmap.md").read()
    assert "Build a recipe-sharing CLI" in roadmap_text

    captured = capsys.readouterr()
    assert "next" in captured.out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coldstart.py -k new_project -v`
Expected: `ImportError` for both new names

- [ ] **Step 3: Implement the new-project flow**

Append to `synlynk/coldstart.py`:

```python
def _prompt_new_project_questions() -> dict:
    """Exactly 4 questions per spec: goal, deliverable shape, solo/team, implementer."""
    goal = input("In one sentence, what are you trying to build? ").strip()
    deliverable_shape = input("What shape is the deliverable (CLI, web app, library, etc.)? ").strip()
    team_mode = input("Solo or team? [solo] ").strip().lower() or "solo"
    preferred_implementer = input(
        "Preferred implementer, if you already know (claude/agy/codex/grok, or blank)? "
    ).strip().lower() or None
    return {
        "goal": goal,
        "deliverable_shape": deliverable_shape,
        "team_mode": team_mode,
        "preferred_implementer": preferred_implementer,
    }


def _run_new_project_flow(answers: dict) -> None:
    """Bootstraps a brand-new project: config + docs via init(), then seeds the
    captured intent as the first roadmap arc. No workspace-canon.md — round 1-2
    of the cold-start design explicitly excludes canon generation for new projects
    (nothing to document yet)."""
    from synlynk import init
    from synlynk.db import cmd_roadmap_add

    mode = "team" if answers["team_mode"].startswith("team") else "solo"
    init(mode=mode)

    version = "v0.1.0"
    cmd_roadmap_add(
        version=version,
        title=answers["goal"],
        status="planned",
        notes=f"Deliverable shape: {answers['deliverable_shape']}."
              + (f" Preferred implementer: {answers['preferred_implementer']}."
                 if answers["preferred_implementer"] else ""),
    )

    print(f"\nSetup complete. Next: run `synlynk dispatch {answers['preferred_implementer'] or '<agent>'} "
          f"--task \"{answers['goal']}\"` to start building against {version}.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -k new_project -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "feat: add new-project 4-question cold-start flow"
```

## Task 4: Existing-project baseline flow

**Files:**
- Modify: `synlynk/coldstart.py`
- Test: `tests/test_coldstart.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_coldstart.py
from unittest.mock import patch

from synlynk.coldstart import _run_existing_project_flow


def test_run_existing_project_flow_prints_summary_and_seeds_story(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    fake_scan = {
        "repos": [{"name": "myrepo", "path": str(tmp_path), "stack_labels": ["python"],
                    "readme_excerpt": "", "context_sections": {}}],
        "harnesses": [{"name": "claude"}],
        "agents": [{"name": "claude", "functional": True}],
        "skills": [],
        "topology": "single",
        "workspace_name": "myrepo",
        "home_harness": "claude",
        "scanned_at": "",
    }
    monkeypatch.setattr("builtins.input", lambda prompt: "fix the flaky CI job")

    with patch("synlynk.scan.run_workspace_scan", return_value=fake_scan) as mock_scan:
        _run_existing_project_flow(str(tmp_path))
        mock_scan.assert_called_once_with(roots=[str(tmp_path)], deep=False)

    captured = capsys.readouterr()
    assert "myrepo" in captured.out
    assert "python" in captured.out


def test_run_existing_project_flow_warns_on_zero_functional_harnesses(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    fake_scan = {
        "repos": [{"name": "myrepo", "path": str(tmp_path), "stack_labels": [],
                    "readme_excerpt": "", "context_sections": {}}],
        "harnesses": [],
        "agents": [{"name": "claude", "functional": False}],
        "skills": [],
        "topology": "single",
        "workspace_name": "myrepo",
        "home_harness": None,
        "scanned_at": "",
    }
    monkeypatch.setattr("builtins.input", lambda prompt: "look around")

    with patch("synlynk.scan.run_workspace_scan", return_value=fake_scan):
        _run_existing_project_flow(str(tmp_path))

    captured = capsys.readouterr()
    assert "no working harnesses" in captured.out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coldstart.py -k existing_project -v`
Expected: `ImportError: cannot import name '_run_existing_project_flow'`

- [ ] **Step 3: Implement the existing-project baseline flow**

Append to `synlynk/coldstart.py`:

```python
def _run_existing_project_flow(root: str = ".") -> None:
    """Baseline warm-start for an existing repo: env-probe + shallow scan summary
    + one question, routed into a seeded story. Does NOT generate
    workspace-canon.md — that lands in cold-start Phase 2."""
    import synlynk.scan as scan_mod
    from synlynk.db import cmd_story_create

    scan = scan_mod.run_workspace_scan(roots=[root], deep=False)

    repo = scan["repos"][0] if scan["repos"] else {"name": os.path.basename(os.path.abspath(root)),
                                                     "stack_labels": []}
    functional_agents = [a for a in scan.get("agents", []) if a.get("functional")]

    print(f"\nFound: {repo['name']}  ·  stack: {', '.join(repo['stack_labels']) or 'unknown'}  "
          f"·  topology: {scan.get('topology', 'single')}")
    if functional_agents:
        print(f"Harnesses ready: {', '.join(a['name'] for a in functional_agents)}")
    else:
        checked = ", ".join(a["name"] for a in scan.get("agents", [])) or "none found on PATH"
        print(f"No working harnesses detected (checked: {checked}). "
              "You can still browse the scan output; install/auth a harness to dispatch work.")

    intent = input("\nWhat are you trying to do right now? ").strip()
    if intent:
        story_id = cmd_story_create(title=intent)
        print(f"\nNext: run `synlynk dispatch <agent> --task \"{intent}\"` "
              f"to work on {story_id}, or `synlynk story list` to see it queued.")
    else:
        print("\nNo task captured — run `synlynk start` again anytime, "
              "or `synlynk scan --deep` for a fuller picture.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -k existing_project -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "feat: add existing-project baseline cold-start flow"
```

## Task 5: `cmd_start()` orchestrator + re-run refresh prompt

**Files:**
- Modify: `synlynk/coldstart.py`
- Test: `tests/test_coldstart.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_coldstart.py
from synlynk.coldstart import cmd_start


def test_cmd_start_runs_new_flow_for_empty_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    answers = iter(["Build a thing", "CLI", "solo", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    cmd_start()
    assert os.path.exists(".synlynk/config.json")


def test_cmd_start_runs_existing_flow_for_populated_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_init(tmp_path, commits=2, files={"README.md": "# repo\n"})
    os.makedirs(".synlynk", exist_ok=True)  # pre-existing synlynk project, skip re-run prompt path
    fake_scan = {
        "repos": [{"name": tmp_path.name, "path": str(tmp_path), "stack_labels": [],
                    "readme_excerpt": "", "context_sections": {}}],
        "harnesses": [], "agents": [], "skills": [], "topology": "single",
        "workspace_name": tmp_path.name, "home_harness": None, "scanned_at": "",
    }
    answers = iter(["y", "look around"])  # y = confirm refresh, then the intent question
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    with patch("synlynk.scan.run_workspace_scan", return_value=fake_scan):
        cmd_start()
    captured = capsys.readouterr()
    assert "found" in captured.out.lower()


def test_cmd_start_rerun_declined_leaves_project_untouched(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_init(tmp_path, commits=2, files={"README.md": "# repo\n"})
    os.makedirs(".synlynk", exist_ok=True)
    monkeypatch.setattr("builtins.input", lambda prompt: "N")
    cmd_start()
    captured = capsys.readouterr()
    assert "unchanged" in captured.out.lower() or "skipped" in captured.out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coldstart.py -k cmd_start -v`
Expected: `ImportError: cannot import name 'cmd_start'`

- [ ] **Step 3: Implement the orchestrator**

Append to `synlynk/coldstart.py`:

```python
def cmd_start() -> None:
    """Entry point for `synlynk start`. See spec's "synlynk start EXACT FLOW"."""
    already_initialized = os.path.exists(".synlynk/config.json")
    if already_initialized:
        answer = input(
            ".synlynk/config.json already exists — refresh cold-start detection "
            "and re-run the relevant flow? [y/N] "
        ).strip().lower()
        if answer != "y":
            print("Left project unchanged.")
            return

    mode = _resolve_cold_start_mode(".")
    if mode == "new":
        answers = _prompt_new_project_questions()
        _run_new_project_flow(answers)
    else:
        _run_existing_project_flow(".")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -k cmd_start -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "feat: add synlynk start orchestrator with re-run refresh prompt"
```

## Task 6: Wire `synlynk start` into the CLI

**Files:**
- Modify: `synlynk/cli.py:243` (near the `join` parser)
- Modify: `synlynk/cli.py:1262` (near the `elif args.command == "join":` branch)
- Test: `tests/test_cli_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_cli_parser.py
def test_start_command_parses(build_parser_fn):
    parser = build_parser_fn()
    args = parser.parse_args(["start"])
    assert args.command == "start"
```

Check `tests/test_cli_parser.py` for the exact fixture name used to get `build_parser()` in this file (e.g. `from synlynk.cli import build_parser` imported at module level, or a `build_parser_fn` fixture) — match whatever convention the file already uses instead of inventing a new one; adjust the test above to that convention before running.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_parser.py -k start_command -v`
Expected: FAIL — `start` not a recognized command (argparse error or `args.command` is `None`)

- [ ] **Step 3: Add the subparser**

In `synlynk/cli.py`, immediately after line 243 (`subparsers.add_parser("join", help="Onboard as a new member to an existing project")`), add:

```python
    subparsers.add_parser(
        "start", help="Cold-start entry point: detect new vs. existing project and guide setup"
    )
```

- [ ] **Step 4: Add the dispatch branch**

In `synlynk/cli.py`, find the `elif args.command == "join":` branch (around line 1262) and add a new branch immediately before it:

```python
    elif args.command == "start":
        from synlynk.coldstart import cmd_start
        cmd_start()
    elif args.command == "join":
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli_parser.py -k start_command -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_cli_parser.py
git commit -m "feat: wire synlynk start into the CLI"
```

## Task 7: Full suite + self-review pass

**Files:** none new — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass (existing suite + the new `test_coldstart.py` + updated `test_cli_parser.py`), no regressions.

- [ ] **Step 2: Manual smoke test — new-project path**

```bash
mkdir -p /tmp/coldstart-smoke-new && cd /tmp/coldstart-smoke-new
python3 -m synlynk start
# Answer the 4 prompts; confirm .synlynk/config.json and project-docs/roadmap.md
# are written and the printed next-action line references the captured goal.
```

- [ ] **Step 3: Manual smoke test — existing-project path**

```bash
cd /Users/nikhilsoman/dev/synlynk   # a real existing repo
python3 -m synlynk start
# Confirm it detects "existing" silently (no ambiguous prompt), prints the
# shallow scan summary, asks the one intent question, and seeds a story.
```

- [ ] **Step 4: Commit any fixes found during smoke testing**

If the manual smoke tests surface issues, fix them in `synlynk/coldstart.py` or `synlynk/cli.py`, re-run `pytest -q`, and commit with a message describing the fix.

---

## Self-Review Notes (completed during plan authoring)

- **Spec coverage:** "Detection: new vs. existing" → Tasks 1-2. "New-project path" → Task 3. "Existing-project path" baseline (env-probe, shallow scan, one question, zero-harness banner) → Task 4. "Re-running `start`" `[y/N]` refresh → Task 5. CLI surface → Task 6. `workspace-canon.md`, deep-scan consent gate, staleness, and everything from "Canon becomes the documentation index" onward are explicitly Phase 2+ and not covered here.
- **Placeholder scan:** no TBD/TODO markers; every step has complete, runnable code.
- **Type consistency:** `_detect_cold_start_mode` returns `{"mode", "reason", "signals"}` consistently across Tasks 1-2; `_resolve_cold_start_mode` returns a plain string (`"new"`/`"existing"`) consumed identically by `cmd_start` in Task 5; `_run_new_project_flow`/`_run_existing_project_flow` signatures match their call sites in `cmd_start`.
