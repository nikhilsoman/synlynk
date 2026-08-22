# qa Merge-Restricted-Classes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `synlynk pr check` merge a PR itself, without waiting on architect, when the PR is docs-only (per the file-pattern definition in the design spec) and the existing block-only qa gate (`qa_gate_verdict()`) is green — controlled by a new `qa_gate_mode: "merge-restricted-classes"` config value.

**Architecture:** A pure, shared file-pattern matcher (`is_docs_only_change`) decides PR class; it's called from `cmd_pr_check()` in `synlynk/db.py` (the human/CI-facing entry point that already computes the block-only gate verdict at line 3035). When `qa_gate_mode` is `"merge-restricted-classes"`, the gate is green, and the changed-files list is docs-only, `cmd_pr_check()` calls `gh pr merge --squash` directly instead of leaving the PR for architect. The `qa-gate` CI job (`.github/workflows/test.yml`) is unaffected — it only computes the required-check verdict and never merges, so this design touches no CI YAML.

**Tech Stack:** Python 3 stdlib (`fnmatch`, `subprocess`, `json`), `gh` CLI (`gh pr diff --name-only`, `gh pr merge`), existing `synlynk/qa_gate.py` (`qa_gate_verdict`), existing `synlynk/db.py` (`cmd_pr_check`), existing `.synlynk/config.json`.

---

## Task 1: Docs-only file-pattern matcher

**Files:**
- Create: `synlynk/merge_class.py`
- Test: `tests/test_merge_class.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_merge_class.py
from synlynk.merge_class import is_docs_only_change


def test_is_docs_only_change_true_for_docs_dir_files():
    assert is_docs_only_change(["docs/superpowers/specs/2026-08-22-example.md", "docs/blog/01-post.md"]) is True


def test_is_docs_only_change_true_for_root_markdown():
    assert is_docs_only_change(["README.md", "CLAUDE.md", "CHANGELOG.md"]) is True


def test_is_docs_only_change_true_for_project_docs():
    assert is_docs_only_change(["project-docs/roadmap.md", "project-docs/todo.md"]) is True


def test_is_docs_only_change_false_for_project_docs_config():
    assert is_docs_only_change(["project-docs/.synlynk_config.json"]) is False


def test_is_docs_only_change_false_when_any_code_file_present():
    assert is_docs_only_change(["docs/blog/01-post.md", "synlynk/db.py"]) is False


def test_is_docs_only_change_false_for_ci_config():
    assert is_docs_only_change([".github/workflows/test.yml"]) is False


def test_is_docs_only_change_false_for_synlynk_config():
    assert is_docs_only_change([".synlynk/config.json"]) is False


def test_is_docs_only_change_false_for_empty_change_list():
    assert is_docs_only_change([]) is False


def test_is_docs_only_change_true_for_nested_markdown_outside_docs_dir():
    assert is_docs_only_change(["tests/README.md"]) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_merge_class.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.merge_class'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/merge_class.py
"""File-pattern classification of PR changesets for qa_gate_mode
"merge-restricted-classes". See
docs/superpowers/specs/2026-08-22-qa-merge-restricted-classes-design.md §3.
"""

import fnmatch


_DOCS_ONLY_EXCLUDE = ("project-docs/.synlynk_config.json",)


def is_docs_only_change(changed_files: list) -> bool:
    """True only if every changed file is a docs file and the list is non-empty.

    A docs file matches docs/**, *.md at any path, or project-docs/** --
    except project-docs/.synlynk_config.json, which is config, not prose.
    One non-doc file anywhere disqualifies the whole PR (no partial credit,
    per the design's §3). An empty changed_files list is not docs-only --
    there's nothing to have verified as docs, so it fails closed to False.
    """
    if not changed_files:
        return False
    for path in changed_files:
        if path in _DOCS_ONLY_EXCLUDE:
            return False
        if fnmatch.fnmatch(path, "docs/*") or fnmatch.fnmatch(path, "docs/**/*"):
            continue
        if fnmatch.fnmatch(path, "*.md") or fnmatch.fnmatch(path, "**/*.md"):
            continue
        if fnmatch.fnmatch(path, "project-docs/*") or fnmatch.fnmatch(path, "project-docs/**/*"):
            continue
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_merge_class.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/merge_class.py tests/test_merge_class.py
git commit -m "feat: add docs-only file-pattern matcher for merge-restricted-classes"
```

---

## Task 2: `qa_gate_mode` config plumbing + changed-files helper

**Base branch:** this task's branch is based on Task 1's branch (stacked).

**Files:**
- Modify: `synlynk/qa_gate.py`
- Test: `tests/test_qa_gate.py` (create if it doesn't already exist — check with `ls tests/test_qa_gate.py` first; if it exists, append to it instead of overwriting)

**Context:** `.synlynk/config.json` currently has no `qa_gate_mode` key at all (confirmed by reading the live config file in this repo) — `synlynk/viz.py:199-204`'s `_load_config()` pattern (`open(".synlynk/config.json")`, catch-all `except Exception: return {}`) is the established way to read it defensively. This task adds a `_qa_gate_mode()` reader using that same defensive pattern, defaulting to `"block-only"` when the key is absent — matching the design spec's own framing of `"block-only"` as the default. It also adds `_gh_pr_changed_files(pr_number)`, a thin wrapper around `gh pr diff --name-only`, since Task 1's `is_docs_only_change` needs a `changed_files: list` and nothing in the codebase currently exposes that for an arbitrary already-open PR (the existing `changed_files` builders in `synlynk/jobs.py:738-765` operate on a local worktree's `git diff`, not `gh pr diff` against a PR number — the wrong tool here since `cmd_pr_check` may run in CI where the only local checkout is the PR branch itself, and using `gh pr diff` keeps this consistent with how `qa_gate.py` already talks to GitHub via `gh`).

- [ ] **Step 1: Write the failing tests**

Create (or append to) `tests/test_qa_gate.py`:

```python
from unittest.mock import patch, MagicMock
from synlynk.qa_gate import _qa_gate_mode, _gh_pr_changed_files


def test_qa_gate_mode_defaults_to_block_only_when_key_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text("{}")
    assert _qa_gate_mode() == "block-only"


def test_qa_gate_mode_reads_configured_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"qa_gate_mode": "merge-restricted-classes"}')
    assert _qa_gate_mode() == "merge-restricted-classes"


def test_qa_gate_mode_defaults_to_block_only_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _qa_gate_mode() == "block-only"


def test_gh_pr_changed_files_parses_gh_output():
    result = MagicMock(returncode=0, stdout="docs/a.md\ndocs/b.md\n")
    with patch("subprocess.run", return_value=result) as mock_run:
        files = _gh_pr_changed_files(1234)
    assert files == ["docs/a.md", "docs/b.md"]
    assert mock_run.call_args.args[0] == ["gh", "pr", "diff", "1234", "--name-only"]


def test_gh_pr_changed_files_returns_empty_list_on_gh_failure():
    result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=result):
        assert _gh_pr_changed_files(1234) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -v`
Expected: FAIL with `ImportError: cannot import name '_qa_gate_mode'`

- [ ] **Step 3: Write the implementation**

In `synlynk/qa_gate.py`, add after the module docstring imports (after line 14):

```python
def _qa_gate_mode() -> str:
    """Reads qa_gate_mode from .synlynk/config.json, defaulting to "block-only".

    Mirrors the defensive read pattern in synlynk/viz.py's _load_config():
    any read/parse failure (missing file, malformed JSON) falls back to the
    default rather than raising, since a config problem here must fail
    closed to the safest mode, not crash the gate.
    """
    try:
        with open(".synlynk/config.json") as f:
            config = json.load(f)
    except Exception:
        return "block-only"
    return config.get("qa_gate_mode") or "block-only"


def _gh_pr_changed_files(pr_number) -> list:
    """Returns the list of file paths changed in pr_number, or [] on any gh failure."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number), "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    return [p for p in (result.stdout or "").splitlines() if p]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -v`
Expected: all tests pass (5 new, plus any pre-existing tests in the file if it already existed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/qa_gate.py tests/test_qa_gate.py
git commit -m "feat: add qa_gate_mode config reader and gh PR changed-files helper"
```

---

## Task 3: Wire the docs-only fast path into `cmd_pr_check`

**Base branch:** this task's branch is based on Task 2's branch (stacked).

**Files:**
- Modify: `synlynk/db.py`
- Test: `tests/test_db_pr_check_merge_restricted.py`

**Context:** `cmd_pr_check()` (`synlynk/db.py:3006-3077`) already computes the block-only gate verdict at lines 3033-3042 (`qa_gate_verdict(owner, repo)`, printing green/red, raising `SystemExit(1)` on red) inside the `if _is_github_remote():` block that also resolves `pr_number = _current_pr_number()`. This task adds the fast-path merge immediately after that existing green-gate print (line 3042), only when `pr_number` is known, `_qa_gate_mode() == "merge-restricted-classes"`, and `is_docs_only_change(_gh_pr_changed_files(pr_number))` is True. Per the design spec §4, the block-only gate check (§3 of the block-only spec) still applies unconditionally — this task adds a merge action *after* the gate is confirmed green, it does not change how the gate itself is computed or bypass it for any file class.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db_pr_check_merge_restricted.py
from unittest.mock import patch, MagicMock
import json


def test_cmd_pr_check_merges_docs_only_pr_when_mode_is_merge_restricted_classes(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "merge-restricted-classes"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=501), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "green", "reason": "CI green, no unresolved sentinel alert"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md"]), \
         patch("subprocess.run") as mock_run, \
         patch("synlynk.db._detect_hand_edit", None), \
         patch("synlynk.db.cmd_audit_docs", return_value=[]):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cmd_pr_check()

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert len(merge_calls) == 1
    assert merge_calls[0].args[0] == ["gh", "pr", "merge", "501", "--squash"]


def test_cmd_pr_check_does_not_merge_when_mode_is_block_only(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "block-only"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=502), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "green", "reason": "ok"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md"]), \
         patch("subprocess.run") as mock_run, \
         patch("synlynk.db._detect_hand_edit", None), \
         patch("synlynk.db.cmd_audit_docs", return_value=[]):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cmd_pr_check()

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert merge_calls == []


def test_cmd_pr_check_does_not_merge_non_docs_only_pr_in_merge_restricted_mode(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "merge-restricted-classes"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=503), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "green", "reason": "ok"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md", "synlynk/db.py"]), \
         patch("subprocess.run") as mock_run, \
         patch("synlynk.db._detect_hand_edit", None), \
         patch("synlynk.db.cmd_audit_docs", return_value=[]):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cmd_pr_check()

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert merge_calls == []


def test_cmd_pr_check_does_not_merge_when_gate_is_red(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "merge-restricted-classes"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=504), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "red", "reason": "CI matrix is red"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md"]), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        try:
            cmd_pr_check()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert merge_calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db_pr_check_merge_restricted.py -v`
Expected: FAIL — no merge call happens in any scenario yet, so `test_cmd_pr_check_merges_docs_only_pr_when_mode_is_merge_restricted_classes` fails on `assert len(merge_calls) == 1` (got 0); the other three pass already since nothing merges (accidentally passing, not proof of correctness — Step 4 below re-runs the full file after the real implementation to confirm all four for the right reasons)

- [ ] **Step 3: Write the implementation**

In `synlynk/db.py`, add imports near the existing `from synlynk.sentinel import _extract_pr_review_cycles` line inside `cmd_pr_check()` (line 3017):

```python
    from synlynk.sentinel import _extract_pr_review_cycles
    from synlynk.qa_gate import _qa_gate_mode, _gh_pr_changed_files
    from synlynk.merge_class import is_docs_only_change
```

Then modify the gate block (lines 3033-3042) to add the fast-path merge after the green print:

```python
        owner, repo = detect_remote_owner_repo()
        if owner and repo:
            gate = qa_gate_verdict(owner, repo)
            if gate["verdict"] == "red":
                conn.close()
                print(f"\n  🚫 [PR CHECK BLOCKED] qa gate is red: {gate['reason']}")
                print("  This is qa's block-only merge gate (CI matrix + sentinel health)\n")
                print("  See docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md\n")
                raise SystemExit(1)
            print(f"  {_GREEN}✓{_RESET} qa gate green — {gate['reason']}")

            if pr_number is not None and _qa_gate_mode() == "merge-restricted-classes":
                changed_files = _gh_pr_changed_files(pr_number)
                if is_docs_only_change(changed_files):
                    print(f"  {_GREEN}✓{_RESET} docs-only PR, qa gate green — qa merging directly (merge-restricted-classes)")
                    subprocess.run(["gh", "pr", "merge", str(pr_number), "--squash"], check=False)
```

Note: `subprocess` is already imported at module scope in `synlynk/db.py` — check with `grep -n "^import subprocess" synlynk/db.py` before adding a duplicate import; if it's not already imported, add `import subprocess` near the top of the file alongside the other stdlib imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db_pr_check_merge_restricted.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -m 'not local_hardware' -q`
Expected: no regressions. `cmd_pr_check`'s pre-existing tests (if any exist under a different filename — check with `grep -rl "cmd_pr_check" tests/`) must still pass; since the new code only fires when `_qa_gate_mode() == "merge-restricted-classes"` and that key is absent from every existing test's config fixture (defaulting to `"block-only"`), no pre-existing test should be affected.

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_db_pr_check_merge_restricted.py
git commit -m "feat: merge docs-only PRs directly when qa_gate_mode is merge-restricted-classes"
```

---

## Task 4: Config default + docs

**Base branch:** this task's branch is based on Task 3's branch (stacked).

**Files:**
- Modify: `.synlynk/config.json`
- Modify: `docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md` (status line only)

**Context:** This task is deliberately small and docs-only itself (fitting, given the feature). It makes the new mode discoverable without changing default behavior: `.synlynk/config.json` gets an explicit `"qa_gate_mode": "block-only"` key (previously absent and defaulted implicitly — now explicit so `synlynk status`/`synlynk vizor` and anyone reading the file can see the toggle exists), and the original block-only spec gets a one-line "Applied" note pointing at this implementation, mirroring the existing "Applied: 2026-08-22 — block-only implemented" line already at the top of that file (line 6).

- [ ] **Step 1: Add the explicit default to config**

Edit `.synlynk/config.json`, adding `"qa_gate_mode": "block-only",` after the `"schema_version": 1,` line:

```json
{
  "schema_version": 1,
  "qa_gate_mode": "block-only",
  "budget": {
```

- [ ] **Step 2: Note the new mode's implementation in the original spec**

In `docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md`, append to the existing `**Applied:**` line (line 6):

```markdown
**Applied:** 2026-08-22 — `block-only` implemented (#1082, #1083, #1084, #1089) and `qa-gate` is a live required status check on `main`'s branch protection. See `docs/blog/123-pr1082-1089-qa-merge-gate-live5.md` for the implementation writeup. `merge-restricted-classes` (docs-only PRs) implemented per `docs/superpowers/specs/2026-08-22-qa-merge-restricted-classes-design.md` and `docs/superpowers/plans/2026-08-22-qa-merge-restricted-classes.md`.
```

- [ ] **Step 3: Run the full test suite to confirm the config change doesn't break anything**

Run: `pytest tests/ -m 'not local_hardware' -q`
Expected: no regressions — `.synlynk/config.json` gaining an explicit key with the same effective default value should not change any test's behavior, since `_qa_gate_mode()` already returned `"block-only"` for the absent-key case.

- [ ] **Step 4: Commit**

```bash
git add .synlynk/config.json docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md
git commit -m "docs: make qa_gate_mode default explicit, note merge-restricted-classes landed"
```

---

## Dispatch plan

Per this project's capability-based task allocation (Claude = pm/review/deploy only; implementation goes to Codex/Grok/Agy):

| Task | Harness | Why |
|---|---|---|
| 1 | Codex | Pure function, single new file, complete spec — mechanical, matches Codex's `refactor`/`cli-plumbing` lane. |
| 2 | Codex | Same file family (`qa_gate.py`), config read + gh subprocess wrapper — moderate but still mechanical. |
| 3 | Codex | Integration into an existing, well-understood function (`cmd_pr_check`) with a clear surrounding pattern to extend — no GitHub-write execution happens during the test run itself (all `subprocess.run`/`gh` calls are mocked), so this does not require the GitHub-write routing override; only the merged production code path calls a real `gh pr merge`. |
| 4 | Codex | Docs-only edits, trivially mechanical. |

Each task's branch is based on the prior task's branch (stacked), not on `main`. Claude reviews each PR (non-authoring, `synlynk pr check`, COMMENT-review-with-checklist fallback per `#423`) before the next task is dispatched. Because this feature's own production behavior is "merge a docs-only PR automatically," Claude reviewing and merging Tasks 1-4 manually (rather than relying on the feature merging its own PRs) is intentional — none of these four PRs are docs-only (they all touch `.py`/test files except Task 4), so the new fast path would not fire on them even after Task 3 lands.
