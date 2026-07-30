# Worktree Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific adaptation (locked CLAUDE.md role split):** this repo's PM/implementer split means Claude never implements code end-to-end. The "implementer" role for every task below is a `synlynk dispatch codex --task "..." --force-agent --context-mode task` job (Python/CLI/tests are Codex's column), not a native Claude Agent-tool subagent. Claude performs both review stages (spec compliance, then code quality) itself by reading the diff. If review finds issues, dispatch a follow-up Codex job with specific fix instructions.

**Goal:** Ship `synlynk worktree audit` and `synlynk worktree clean` — a CLI command group that automates the safe/needs-review/unsafe classification of stale git worktrees (ancestor check, PR state via `gh`, dirty/nesting handling) and an optional dry-run-by-default cleanup action, plus a lightweight `WORKTREES` staleness hint in `synlynk status`.

**Architecture:** New self-contained module `synlynk/worktree.py` (dataclasses + pure classification functions + subprocess-orchestrating `cmd_worktree_audit`/`cmd_worktree_clean`/`_worktree_status_hint`), wired into `synlynk/cli.py`'s subparser dispatch and imported by `synlynk/status.py` for the new `WORKTREES` line. Classification logic (`_classify_worktree`, `_apply_nesting_floor`) is pure — it takes pre-computed signals as arguments — so almost all test coverage exercises it directly with hand-built inputs; only the orchestration layer needs real git fixtures.

**Tech Stack:** Python 3.9+ stdlib only (`subprocess`, `dataclasses`, `json`, `os`, `re`) — matches the rest of `synlynk/`. Tests use `pytest` with `tmp_path`/`monkeypatch`, following `tests/test_probe.py`'s conventions (stub executable scripts on `PATH` for `gh`; real git repos in `tmp_path` for git-level fixtures since git-only operations are cheap and deterministic, unlike `gh` which needs network/auth).

---

## File Structure

- Create: `synlynk/worktree.py` — all new logic (dataclasses, pure classifiers, subprocess wrappers, `cmd_worktree_audit`, `cmd_worktree_clean`, `_worktree_status_hint`).
- Modify: `synlynk/cli.py` — add `worktree audit`/`worktree clean` subparsers (near the existing `doctor`/`probe` parsers, ~line 316-322) and their dispatch branch (near the existing `doctor`/`probe` dispatch, ~line 1098-1101).
- Modify: `synlynk/status.py` — add a `WORKTREES` line to `_format_status_terminal()` and a `"worktrees"` field to its JSON payload; `cmd_status()` calls the new `_worktree_status_hint()`.
- Test: `tests/test_worktree.py` — new file, all 14 spec-required cases plus parser/entry-builder coverage.

---

### Task 1: Dataclasses + pure porcelain parser

**Files:**
- Create: `synlynk/worktree.py`
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worktree.py
from synlynk.worktree import WorktreeEntry, WorktreeVerdict, _parse_worktree_porcelain


def test_parse_worktree_porcelain_basic():
    text = (
        "worktree /repo/main\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.worktrees/chore+foo\n"
        "HEAD def456\n"
        "branch refs/heads/chore/foo\n"
        "\n"
        "worktree /repo/.worktrees/detached-one\n"
        "HEAD ghi789\n"
        "detached\n"
    )
    parsed = _parse_worktree_porcelain(text)
    assert parsed == [
        {"path": "/repo/main", "branch": "main", "bare": False},
        {"path": "/repo/.worktrees/chore+foo", "branch": "chore/foo", "bare": False},
        {"path": "/repo/.worktrees/detached-one", "branch": None, "bare": False},
    ]


def test_worktree_entry_and_verdict_are_dataclasses_with_defaults():
    entry = WorktreeEntry(path="/x", branch="feat/y")
    assert entry.nested_under is None
    verdict = WorktreeVerdict(path="/x", branch="feat/y", verdict="safe", reason="merged")
    assert verdict.nested_under is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worktree.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.worktree'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/worktree.py
"""synlynk worktree: audit and clean up stale git worktrees/branches."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorktreeEntry:
    path: str
    branch: str
    nested_under: Optional[str] = None


@dataclass
class WorktreeVerdict:
    path: str
    branch: str
    verdict: str  # "safe" | "needs-review" | "unsafe"
    reason: str
    nested_under: Optional[str] = None


def _parse_worktree_porcelain(text: str) -> list:
    """Parses `git worktree list --porcelain` output into raw dicts."""
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                entries.append(current)
            current = {"path": line[len("worktree "):].strip(), "branch": None, "bare": False}
        elif current is None:
            continue
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            current["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line.startswith("bare"):
            current["bare"] = True
    if current is not None:
        entries.append(current)
    return entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worktree.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/worktree.py tests/test_worktree.py
git commit -m "feat(worktree): add dataclasses and porcelain parser"
```

---

### Task 2: Entry builder — exclusion + nesting

**Files:**
- Modify: `synlynk/worktree.py`
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worktree.py (append)
from synlynk.worktree import _build_worktree_entries


def test_build_worktree_entries_excludes_main_and_cwd():
    raw = [
        {"path": "/repo", "branch": "main", "bare": False},
        {"path": "/repo/.worktrees/a", "branch": "chore/a", "bare": False},
        {"path": "/repo/.worktrees/b", "branch": "chore/b", "bare": False},
    ]
    entries = _build_worktree_entries(raw, main_repo_path="/repo", cwd_worktree_path="/repo/.worktrees/b")
    assert [e.path for e in entries] == ["/repo/.worktrees/a"]
    assert entries[0].branch == "chore/a"


def test_build_worktree_entries_computes_nesting():
    raw = [
        {"path": "/repo", "branch": "main", "bare": False},
        {"path": "/repo/.worktrees/parent", "branch": "chore/parent", "bare": False},
        {"path": "/repo/.worktrees/parent/worktrees/job-1", "branch": "dispatch/codex/job-1", "bare": False},
    ]
    entries = _build_worktree_entries(raw, main_repo_path="/repo", cwd_worktree_path="/nowhere")
    by_path = {e.path: e for e in entries}
    assert by_path["/repo/.worktrees/parent"].nested_under is None
    assert by_path["/repo/.worktrees/parent/worktrees/job-1"].nested_under == "/repo/.worktrees/parent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worktree.py -v -k build_worktree_entries`
Expected: FAIL with `ImportError: cannot import name '_build_worktree_entries'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/worktree.py (append)
def _is_subpath(child: str, parent: str) -> bool:
    child_r = os.path.realpath(child)
    parent_r = os.path.realpath(parent)
    return child_r != parent_r and child_r.startswith(parent_r + os.sep)


def _build_worktree_entries(raw_entries: list, main_repo_path: str, cwd_worktree_path: str) -> list:
    """Excludes the main repo checkout and cwd's own worktree, then computes nesting."""
    filtered = []
    for raw in raw_entries:
        path = raw.get("path")
        if not path or raw.get("bare"):
            continue
        if os.path.realpath(path) == os.path.realpath(main_repo_path):
            continue
        if os.path.realpath(path) == os.path.realpath(cwd_worktree_path):
            continue
        filtered.append(WorktreeEntry(path=path, branch=raw.get("branch") or ""))

    for entry in filtered:
        candidates = [other for other in filtered if _is_subpath(entry.path, other.path)]
        if candidates:
            parent = max(candidates, key=lambda o: len(o.path))
            entry.nested_under = parent.path

    return filtered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worktree.py -v -k build_worktree_entries`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/worktree.py tests/test_worktree.py
git commit -m "feat(worktree): build worktree entries with exclusion and nesting"
```

---

### Task 3: `_classify_worktree` — the classification algorithm

This is the pure function implementing the spec's ordered rules 1-3 (dirty override → ancestor check → PR state). Rule 4 (nesting floor) is a separate second pass — Task 4. It also covers the spec's "missing worktree directory" error-handling case, which is folded into the same function via a `worktree_missing` flag so the whole primary ordering lives in one place.

**Files:**
- Modify: `synlynk/worktree.py`
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_worktree.py (append)
from synlynk.worktree import _classify_worktree


def _entry(path="/repo/.worktrees/x", branch="chore/x"):
    return WorktreeEntry(path=path, branch=branch)


def test_classify_ancestor_true_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=True, gh_available=True, pr_info=None, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "safe"
    assert v.reason == "merged, direct ancestor"


def test_classify_pr_merged_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 552, "state": "MERGED"}, net_diff_lines=None, commits_ahead=3,
    )
    assert v.verdict == "safe"
    assert v.reason == "PR #552 merged"


def test_classify_pr_closed_net_zero_or_negative_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 516, "state": "CLOSED"}, net_diff_lines=-4, commits_ahead=2,
    )
    assert v.verdict == "safe"
    assert "no unique content" in v.reason


def test_classify_pr_closed_net_positive_is_needs_review():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 517, "state": "CLOSED"}, net_diff_lines=42, commits_ahead=2,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "PR #517 closed, 42 net lines of unmerged content"


def test_classify_pr_open_is_unsafe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 566, "state": "OPEN"}, net_diff_lines=None, commits_ahead=1,
    )
    assert v.verdict == "unsafe"
    assert v.reason == "PR #566 open — active work"


def test_classify_no_pr_found_is_needs_review():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info=None, net_diff_lines=None, commits_ahead=1,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "no PR found, 1 commits ahead of main"


def test_classify_dirty_overrides_everything():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=True, dirty_summary="M GEMINI.md",
        is_ancestor=True, gh_available=True,
        pr_info={"number": 1, "state": "MERGED"}, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "dirty: M GEMINI.md"


def test_classify_gh_unavailable_falls_back_to_needs_review():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=False,
        pr_info=None, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "could not verify PR state — gh unavailable"


def test_classify_missing_worktree_directory_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=True, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True, pr_info=None, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "safe"
    assert v.reason == "worktree directory missing — stale registration"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worktree.py -v -k classify`
Expected: FAIL with `ImportError: cannot import name '_classify_worktree'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/worktree.py (append)
def _classify_worktree(
    entry: WorktreeEntry,
    worktree_missing: bool,
    is_dirty: bool,
    dirty_summary: str,
    is_ancestor: bool,
    gh_available: bool,
    pr_info,
    net_diff_lines,
    commits_ahead: int,
) -> WorktreeVerdict:
    """Pure classifier — rules 1-3 of the spec's ordered algorithm. Takes
    pre-fetched git/gh signals as arguments; does not shell out itself."""
    if worktree_missing:
        return WorktreeVerdict(
            entry.path, entry.branch, "safe",
            "worktree directory missing — stale registration", entry.nested_under,
        )
    if is_dirty:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"dirty: {dirty_summary}", entry.nested_under,
        )
    if is_ancestor:
        return WorktreeVerdict(
            entry.path, entry.branch, "safe",
            "merged, direct ancestor", entry.nested_under,
        )
    if not gh_available:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            "could not verify PR state — gh unavailable", entry.nested_under,
        )
    if pr_info is None:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"no PR found, {commits_ahead} commits ahead of main", entry.nested_under,
        )

    state = pr_info.get("state")
    number = pr_info.get("number")
    if state == "MERGED":
        return WorktreeVerdict(
            entry.path, entry.branch, "safe", f"PR #{number} merged", entry.nested_under,
        )
    if state == "CLOSED":
        net = net_diff_lines if net_diff_lines is not None else 0
        if net <= 0:
            return WorktreeVerdict(
                entry.path, entry.branch, "safe",
                f"PR #{number} closed, stale — no unique content vs main", entry.nested_under,
            )
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"PR #{number} closed, {net} net lines of unmerged content", entry.nested_under,
        )
    if state == "OPEN":
        return WorktreeVerdict(
            entry.path, entry.branch, "unsafe", f"PR #{number} open — active work", entry.nested_under,
        )
    return WorktreeVerdict(
        entry.path, entry.branch, "needs-review",
        f"no PR found, {commits_ahead} commits ahead of main", entry.nested_under,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worktree.py -v -k classify`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/worktree.py tests/test_worktree.py
git commit -m "feat(worktree): implement classification algorithm"
```

---

### Task 4: `_apply_nesting_floor` — the second pass

**Files:**
- Modify: `synlynk/worktree.py`
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_worktree.py (append)
from synlynk.worktree import _apply_nesting_floor


def test_nesting_floor_nested_under_safe_parent_stays_safe():
    parent = WorktreeVerdict(path="/p", branch="chore/parent", verdict="safe", reason="merged, direct ancestor")
    child = WorktreeVerdict(
        path="/p/worktrees/job-1", branch="dispatch/codex/job-1", verdict="safe",
        reason="merged, direct ancestor", nested_under="/p",
    )
    result = _apply_nesting_floor([parent, child])
    by_path = {v.path: v for v in result}
    assert by_path["/p/worktrees/job-1"].verdict == "safe"


def test_nesting_floor_raises_child_to_parent_verdict():
    parent_needs_review = WorktreeVerdict(path="/p", branch="chore/parent", verdict="needs-review", reason="no PR found, 1 commits ahead of main")
    child_safe = WorktreeVerdict(
        path="/p/worktrees/job-1", branch="dispatch/codex/job-1", verdict="safe",
        reason="merged, direct ancestor", nested_under="/p",
    )
    result = _apply_nesting_floor([parent_needs_review, child_safe])
    by_path = {v.path: v for v in result}
    assert by_path["/p/worktrees/job-1"].verdict == "needs-review"
    assert "parent worktree not yet safe" in by_path["/p/worktrees/job-1"].reason

    parent_unsafe = WorktreeVerdict(path="/q", branch="chore/parent2", verdict="unsafe", reason="PR #1 open — active work")
    child_needs_review = WorktreeVerdict(
        path="/q/worktrees/job-2", branch="dispatch/codex/job-2", verdict="needs-review",
        reason="no PR found, 1 commits ahead of main", nested_under="/q",
    )
    result2 = _apply_nesting_floor([parent_unsafe, child_needs_review])
    by_path2 = {v.path: v for v in result2}
    assert by_path2["/q/worktrees/job-2"].verdict == "unsafe"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worktree.py -v -k nesting_floor`
Expected: FAIL with `ImportError: cannot import name '_apply_nesting_floor'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/worktree.py (append)
_VERDICT_RANK = {"safe": 0, "needs-review": 1, "unsafe": 2}


def _apply_nesting_floor(verdicts: list) -> list:
    """Second pass: a nested worktree's verdict can never be better than its
    parent's. `needs-review` is the floor unless the parent is `unsafe`."""
    by_path = {v.path: v for v in verdicts}
    result = []
    for v in verdicts:
        parent = by_path.get(v.nested_under) if v.nested_under else None
        if parent is None or parent.verdict == "safe":
            result.append(v)
            continue
        floor_verdict = "unsafe" if parent.verdict == "unsafe" else "needs-review"
        if _VERDICT_RANK[floor_verdict] > _VERDICT_RANK[v.verdict]:
            result.append(WorktreeVerdict(
                v.path, v.branch, floor_verdict,
                f"{v.reason}; parent worktree not yet safe", v.nested_under,
            ))
        else:
            result.append(v)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worktree.py -v -k nesting_floor`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/worktree.py tests/test_worktree.py
git commit -m "feat(worktree): implement nesting-floor second pass"
```

---

### Task 5: Signal gathering + `cmd_worktree_audit` orchestration

This wires the pure functions from Tasks 1-4 to real subprocess calls, and formats the report. Tests use a real git repo fixture in `tmp_path` (worktrees are cheap/deterministic with plain git) plus a stub `gh` script on `PATH`, mirroring `tests/test_probe.py`'s convention for the one subprocess dependency (`gh`) that needs network/auth stubbing.

**Files:**
- Modify: `synlynk/worktree.py`
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_worktree.py (append)
import subprocess as _subprocess


def _run(cmd, cwd):
    result = _subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, f"{cmd} failed: {result.stderr}"
    return result


def _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False):
    """Real git repo fixture: main repo with one linked worktree on a
    feature branch. If branch_ahead_of_main, the feature branch gets an
    extra commit main doesn't have (so merge-base --is-ancestor is false)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    _run(["git", "remote", "add", "origin", str(repo)], cwd=repo)
    _run(["git", "branch", "origin/main"], cwd=repo)

    wt_dir = tmp_path / "wt-feature"
    _run(["git", "worktree", "add", str(wt_dir), "-b", "chore/feature"], cwd=repo)
    if branch_ahead_of_main:
        (wt_dir / "extra.txt").write_text("new stuff\n")
        _run(["git", "add", "."], cwd=wt_dir)
        _run(["git", "commit", "-m", "extra work"], cwd=wt_dir)
    return repo, wt_dir


def _make_stub_gh(tmp_path, monkeypatch, auth_ok=True, pr_json="[]"):
    script = tmp_path / "gh"
    script.write_text(
        f"""#!/bin/sh
if [ "$1" = "auth" ]; then
  {"exit 0" if auth_ok else "exit 1"}
fi
if [ "$1" = "pr" ]; then
  echo '{pr_json}'
  exit 0
fi
exit 0
"""
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")


def test_cmd_worktree_audit_reports_safe_ancestor(tmp_path, monkeypatch, capsys):
    from synlynk.worktree import cmd_worktree_audit

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_audit(json_output=False)
    assert "SAFE (1)" in output
    assert "chore/feature" in output
    assert "merged, direct ancestor" in output


def test_cmd_worktree_audit_json_output_shape(tmp_path, monkeypatch):
    from synlynk.worktree import cmd_worktree_audit

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_audit(json_output=True)
    payload = json.loads(output)
    assert payload == [
        {
            "path": str(wt_dir),
            "branch": "chore/feature",
            "verdict": "safe",
            "reason": "merged, direct ancestor",
            "nested_under": None,
        }
    ]


def test_cmd_worktree_audit_no_worktrees_prints_one_liner(tmp_path, monkeypatch):
    from synlynk.worktree import cmd_worktree_audit

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_audit(json_output=False)
    assert output == "No stale worktrees — nothing to audit."
```

Add `import os` and `import json` at the top of `tests/test_worktree.py` if not already present (Task 1's stub used `os` implicitly via the porcelain text only — add both explicitly now).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worktree.py -v -k cmd_worktree_audit`
Expected: FAIL with `ImportError: cannot import name 'cmd_worktree_audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/worktree.py (append)
def _gh_auth_available() -> bool:
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _git_status_dirty(path: str):
    result = subprocess.run(["git", "status", "--short"], cwd=path, capture_output=True, text=True, timeout=10)
    output = result.stdout.strip()
    if not output:
        return False, ""
    return True, output.splitlines()[0]


def _git_is_ancestor(branch: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "origin/main"],
        cwd=path, capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _git_commits_ahead(branch: str, path: str) -> int:
    result = subprocess.run(
        ["git", "log", f"origin/main..{branch}", "--oneline"],
        cwd=path, capture_output=True, text=True, timeout=10,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def _git_net_diff_lines(branch: str, path: str) -> int:
    result = subprocess.run(
        ["git", "diff", f"origin/main..{branch}", "--shortstat"],
        cwd=path, capture_output=True, text=True, timeout=10,
    )
    text = result.stdout.strip()
    ins_match = re.search(r"(\d+) insertion", text)
    del_match = re.search(r"(\d+) deletion", text)
    insertions = int(ins_match.group(1)) if ins_match else 0
    deletions = int(del_match.group(1)) if del_match else 0
    return insertions - deletions


def _gh_pr_for_branch(branch: str):
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "all", "--search", f"head:{branch}",
         "--json", "number,state,mergedAt"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except (ValueError, json.JSONDecodeError):
        return None
    return data[0] if data else None


def _gather_worktree_signals(entry: WorktreeEntry, gh_available: bool) -> dict:
    if not os.path.isdir(entry.path):
        return {"worktree_missing": True}
    try:
        is_dirty, dirty_summary = _git_status_dirty(entry.path)
        if is_dirty:
            return {"worktree_missing": False, "is_dirty": True, "dirty_summary": dirty_summary}

        is_ancestor = _git_is_ancestor(entry.branch, entry.path)
        if is_ancestor:
            return {"worktree_missing": False, "is_dirty": False, "is_ancestor": True}

        pr_info = None
        net_diff_lines = None
        if gh_available:
            pr_info = _gh_pr_for_branch(entry.branch)
            if pr_info and pr_info.get("state") == "CLOSED":
                net_diff_lines = _git_net_diff_lines(entry.branch, entry.path)
        commits_ahead = _git_commits_ahead(entry.branch, entry.path)
        return {
            "worktree_missing": False,
            "is_dirty": False,
            "is_ancestor": False,
            "gh_available": gh_available,
            "pr_info": pr_info,
            "net_diff_lines": net_diff_lines,
            "commits_ahead": commits_ahead,
        }
    except (subprocess.SubprocessError, OSError) as exc:
        return {"error": str(exc)}


def _verdict_from_signals(entry: WorktreeEntry, signals: dict, gh_available: bool) -> WorktreeVerdict:
    if signals.get("error"):
        return WorktreeVerdict(entry.path, entry.branch, "needs-review", signals["error"], entry.nested_under)
    return _classify_worktree(
        entry,
        worktree_missing=signals.get("worktree_missing", False),
        is_dirty=signals.get("is_dirty", False),
        dirty_summary=signals.get("dirty_summary", ""),
        is_ancestor=signals.get("is_ancestor", False),
        gh_available=signals.get("gh_available", gh_available),
        pr_info=signals.get("pr_info"),
        net_diff_lines=signals.get("net_diff_lines"),
        commits_ahead=signals.get("commits_ahead", 0),
    )


def _get_repo_root() -> str:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def _list_worktrees(main_repo_path: str, cwd_worktree_path: str) -> list:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=main_repo_path, capture_output=True, text=True, timeout=10,
    )
    raw = _parse_worktree_porcelain(result.stdout)
    return _build_worktree_entries(raw, main_repo_path, cwd_worktree_path)


def _collect_verdicts(main_repo_path: str, cwd_worktree_path: str) -> list:
    entries = _list_worktrees(main_repo_path, cwd_worktree_path)
    gh_available = _gh_auth_available()
    verdicts = []
    for entry in entries:
        signals = _gather_worktree_signals(entry, gh_available)
        verdicts.append(_verdict_from_signals(entry, signals, gh_available))
    return _apply_nesting_floor(verdicts)


def _format_audit_report(verdicts: list, json_output: bool = False) -> str:
    if json_output:
        payload = [
            {"path": v.path, "branch": v.branch, "verdict": v.verdict,
             "reason": v.reason, "nested_under": v.nested_under}
            for v in verdicts
        ]
        return json.dumps(payload, indent=2)

    if not verdicts:
        return "No stale worktrees — nothing to audit."

    safe = [v for v in verdicts if v.verdict == "safe"]
    needs_review = [v for v in verdicts if v.verdict == "needs-review"]
    unsafe = [v for v in verdicts if v.verdict == "unsafe"]

    lines = [
        f"SYNLYNK WORKTREE AUDIT   {len(verdicts)} worktrees checked (excluding main + current session)",
        "",
    ]
    if safe:
        lines.append(f"SAFE ({len(safe)}) — merged/stale, no action needed but removable")
        for v in safe:
            lines.append(f"  {v.branch:<30}  {v.reason}")
        lines.append("")
    if needs_review:
        lines.append(f"NEEDS-REVIEW ({len(needs_review)}) — a human should look")
        for v in needs_review:
            lines.append(f"  {v.branch:<30}  {v.reason}")
        lines.append("")
    if unsafe:
        lines.append(f"UNSAFE ({len(unsafe)}) — active, do not touch")
        for v in unsafe:
            lines.append(f"  {v.branch:<30}  {v.reason}")
        lines.append("")
    if safe:
        lines.append(f"Run `synlynk worktree clean --apply` to remove the {len(safe)} SAFE items.")

    return "\n".join(lines).rstrip()


def cmd_worktree_audit(json_output: bool = False) -> str:
    main_repo_path = _get_repo_root()
    cwd_worktree_path = os.getcwd()
    verdicts = _collect_verdicts(main_repo_path, cwd_worktree_path)
    output = _format_audit_report(verdicts, json_output)
    print(output)
    return output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worktree.py -v -k cmd_worktree_audit`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/worktree.py tests/test_worktree.py
git commit -m "feat(worktree): implement cmd_worktree_audit orchestration and report format"
```

---

### Task 6: `cmd_worktree_clean` — dry-run and `--apply`

**Files:**
- Modify: `synlynk/worktree.py`
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_worktree.py (append)
def test_cmd_worktree_clean_dry_run_does_not_mutate(tmp_path, monkeypatch):
    from synlynk.worktree import cmd_worktree_clean

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_clean(apply=False, json_output=False)
    assert "[dry-run] would remove 1 worktrees + branches (use --apply)" in output
    assert wt_dir.exists()
    branches = _run(["git", "branch", "--list", "chore/feature"], cwd=repo).stdout
    assert "chore/feature" in branches


def test_cmd_worktree_clean_apply_removes_safe_items(tmp_path, monkeypatch):
    from synlynk.worktree import cmd_worktree_clean

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_clean(apply=True, json_output=False)
    assert "wt=removed" in output
    assert "branch=deleted" in output
    assert not wt_dir.exists()
    branches = _run(["git", "branch", "--list", "chore/feature"], cwd=repo).stdout
    assert "chore/feature" not in branches


def test_cmd_worktree_clean_apply_partial_failure_continues_batch(tmp_path, monkeypatch):
    from synlynk import worktree as worktree_mod

    repo, wt_dir_a = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    wt_dir_b = tmp_path / "wt-feature-b"
    _run(["git", "worktree", "add", str(wt_dir_b), "-b", "chore/feature-b"], cwd=repo)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    real_run = worktree_mod.subprocess.run

    def _flaky_run(cmd, *args, **kwargs):
        if cmd[:3] == ["git", "branch", "-D"] and cmd[3] == "chore/feature":
            class _Result:
                returncode = 1
                stderr = "branch is checked out elsewhere"
                stdout = ""
            return _Result()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(worktree_mod.subprocess, "run", _flaky_run)

    output = worktree_mod.cmd_worktree_clean(apply=True, json_output=False)
    assert "chore/feature   wt=removed   branch=FAILED" in output
    assert "chore/feature-b   wt=removed   branch=deleted" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worktree.py -v -k cmd_worktree_clean`
Expected: FAIL with `ImportError: cannot import name 'cmd_worktree_clean'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/worktree.py (append)
def _nesting_depth(verdict: WorktreeVerdict, by_path: dict) -> int:
    depth = 0
    cur = verdict
    seen = set()
    while cur.nested_under and cur.nested_under in by_path and cur.path not in seen:
        seen.add(cur.path)
        depth += 1
        cur = by_path[cur.nested_under]
    return depth


def cmd_worktree_clean(apply: bool = False, json_output: bool = False) -> str:
    main_repo_path = _get_repo_root()
    cwd_worktree_path = os.getcwd()
    verdicts = _collect_verdicts(main_repo_path, cwd_worktree_path)

    if not apply:
        safe_count = sum(1 for v in verdicts if v.verdict == "safe")
        if json_output:
            payload = {
                "dry_run": True,
                "would_remove": safe_count,
                "items": [
                    {"path": v.path, "branch": v.branch, "verdict": v.verdict,
                     "reason": v.reason, "nested_under": v.nested_under}
                    for v in verdicts
                ],
            }
            output = json.dumps(payload, indent=2)
        else:
            report = _format_audit_report(verdicts, json_output=False)
            summary = f"[dry-run] would remove {safe_count} worktrees + branches (use --apply)"
            output = f"{report}\n\n{summary}" if report != "No stale worktrees — nothing to audit." else report
        print(output)
        return output

    by_path = {v.path: v for v in verdicts}
    safe_verdicts = [v for v in verdicts if v.verdict == "safe"]
    safe_verdicts.sort(key=lambda v: _nesting_depth(v, by_path), reverse=True)

    result_lines = []
    for v in safe_verdicts:
        wt_status = "removed"
        try:
            r = subprocess.run(
                ["git", "worktree", "remove", "--force", v.path],
                cwd=main_repo_path, capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                wt_status = f"FAILED({r.stderr.strip()[:80]})"
        except (subprocess.SubprocessError, OSError) as exc:
            wt_status = f"FAILED({exc})"

        branch_status = "deleted"
        try:
            r = subprocess.run(
                ["git", "branch", "-D", v.branch],
                cwd=main_repo_path, capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                branch_status = f"FAILED({r.stderr.strip()[:80]})"
        except (subprocess.SubprocessError, OSError) as exc:
            branch_status = f"FAILED({exc})"

        remote_status = "remote-none/skip"
        try:
            r = subprocess.run(
                ["git", "push", "origin", "--delete", v.branch],
                cwd=main_repo_path, capture_output=True, text=True, timeout=15,
            )
            remote_status = "remote-deleted" if r.returncode == 0 else "remote-none/skip"
        except (subprocess.SubprocessError, OSError):
            remote_status = "remote-none/skip"

        result_lines.append(f"{v.branch}   wt={wt_status}   branch={branch_status}   {remote_status}")

    subprocess.run(["git", "worktree", "prune"], cwd=main_repo_path, capture_output=True, text=True, timeout=15)

    if json_output:
        output = json.dumps({"applied": True, "results": result_lines}, indent=2)
    else:
        output = "\n".join(result_lines) if result_lines else "No SAFE items to remove."
    print(output)
    return output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worktree.py -v -k cmd_worktree_clean`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/worktree.py tests/test_worktree.py
git commit -m "feat(worktree): implement cmd_worktree_clean dry-run and --apply"
```

---

### Task 7: Wire `worktree audit`/`worktree clean` into `synlynk/cli.py`

**Files:**
- Modify: `synlynk/cli.py:322` (subparser registration, right after the existing `doctor` parser)
- Modify: `synlynk/cli.py:1100-1101` (dispatch branch, right after the existing `doctor` dispatch)
- Test: `tests/test_worktree.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worktree.py (append)
def test_cli_registers_worktree_audit_and_clean_subcommands():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["worktree", "audit", "--json"])
    assert args.command == "worktree"
    assert args.worktree_action == "audit"
    assert args.json_output is True

    args2 = parser.parse_args(["worktree", "clean", "--apply"])
    assert args2.command == "worktree"
    assert args2.worktree_action == "clean"
    assert args2.apply is True
    assert args2.json_output is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worktree.py -v -k cli_registers_worktree`
Expected: FAIL with `SystemExit` (argparse rejects unrecognized `worktree` command) or `AttributeError`

- [ ] **Step 3: Write minimal implementation**

In `synlynk/cli.py`, immediately after this existing line (~322):

```python
    subparsers.add_parser("doctor", help="Run health checks on your synlynk installation")
```

add:

```python
    worktree_parser = subparsers.add_parser(
        "worktree", help="Audit and clean up stale git worktrees/branches"
    )
    worktree_sub = worktree_parser.add_subparsers(dest="worktree_action")
    worktree_audit_parser = worktree_sub.add_parser(
        "audit", help="Report worktree safety classification (read-only)"
    )
    worktree_audit_parser.add_argument("--json", action="store_true", dest="json_output",
                                       help="Output machine-readable JSON")
    worktree_clean_parser = worktree_sub.add_parser(
        "clean", help="Remove SAFE worktrees/branches (dry-run unless --apply)"
    )
    worktree_clean_parser.add_argument("--apply", action="store_true",
                                       help="Actually remove SAFE items (default is dry-run)")
    worktree_clean_parser.add_argument("--json", action="store_true", dest="json_output",
                                       help="Output machine-readable JSON")
```

In `synlynk/cli.py`, immediately after this existing block (~1098-1101):

```python
    elif args.command == "probe":
        cmd_probe(agent=getattr(args, "agent", None))
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
```

add:

```python
    elif args.command == "worktree":
        from synlynk.worktree import cmd_worktree_audit, cmd_worktree_clean
        action = getattr(args, "worktree_action", None)
        if action == "audit":
            cmd_worktree_audit(json_output=args.json_output)
        elif action == "clean":
            cmd_worktree_clean(apply=args.apply, json_output=args.json_output)
        else:
            worktree_parser.print_help()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worktree.py -v -k cli_registers_worktree`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: PASS, no failures introduced in other CLI-parsing tests

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_worktree.py
git commit -m "feat(cli): wire worktree audit/clean subcommands"
```

---

### Task 8: `_worktree_status_hint` + `synlynk status` integration

**Files:**
- Modify: `synlynk/worktree.py`
- Modify: `synlynk/status.py:300-397` (`_format_status_terminal` and `cmd_status`)
- Test: `tests/test_worktree.py`
- Test: `tests/test_status.py` if it exists (check with `ls tests/test_status.py`); otherwise the new assertions live in `tests/test_worktree.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_worktree.py (append)
def test_worktree_status_hint_counts_non_dirty_worktrees(tmp_path, monkeypatch):
    from synlynk.worktree import _worktree_status_hint

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=True)
    monkeypatch.chdir(repo)

    hint = _worktree_status_hint()
    assert hint == {"local": 1, "stale_hint": 1}


def test_worktree_status_hint_returns_none_when_no_worktrees(tmp_path, monkeypatch):
    from synlynk.worktree import _worktree_status_hint

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    monkeypatch.chdir(repo)

    assert _worktree_status_hint() is None


def test_worktree_status_hint_never_invokes_gh(tmp_path, monkeypatch):
    from synlynk import worktree as worktree_mod

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    monkeypatch.chdir(repo)

    real_run = worktree_mod.subprocess.run

    def _guarded_run(cmd, *args, **kwargs):
        assert cmd[0] != "gh", "‌_worktree_status_hint must never call gh"
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(worktree_mod.subprocess, "run", _guarded_run)
    hint = worktree_mod._worktree_status_hint()
    assert hint == {"local": 1, "stale_hint": 1}


def test_status_terminal_includes_worktrees_line_when_stale_present():
    from synlynk.status import _format_status_terminal

    output = _format_status_terminal(
        harness_rows=[], cycle_map={}, efficiency_ratio=1.0, dispatch_mode="daily-grind",
        sentinels_active=0, json_output=False, rates_updated_at="2026-07-29",
        worktree_hint={"local": 6, "stale_hint": 2},
    )
    assert "WORKTREES  6 local, 2 look stale — run `synlynk worktree audit`" in output


def test_status_terminal_omits_worktrees_line_when_no_stale():
    from synlynk.status import _format_status_terminal

    output = _format_status_terminal(
        harness_rows=[], cycle_map={}, efficiency_ratio=1.0, dispatch_mode="daily-grind",
        sentinels_active=0, json_output=False, rates_updated_at="2026-07-29",
        worktree_hint=None,
    )
    assert "WORKTREES" not in output


def test_status_json_includes_worktrees_field():
    import json as _json
    from synlynk.status import _format_status_terminal

    output = _format_status_terminal(
        harness_rows=[], cycle_map={}, efficiency_ratio=1.0, dispatch_mode="daily-grind",
        sentinels_active=0, json_output=True, rates_updated_at="2026-07-29",
        worktree_hint={"local": 6, "stale_hint": 2},
    )
    payload = _json.loads(output)
    assert payload["worktrees"] == {"local": 6, "stale_hint": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worktree.py -v -k "status_hint or status_terminal or status_json"`
Expected: FAIL — `_worktree_status_hint` doesn't exist yet, and `_format_status_terminal` doesn't accept `worktree_hint`

- [ ] **Step 3: Write minimal implementation**

In `synlynk/worktree.py`, append:

```python
def _worktree_status_hint():
    """Cheap local-only pre-pass for `synlynk status` — dirty + ancestor
    checks only, no `gh` calls. Returns None when there's nothing to report."""
    try:
        main_repo_path = _get_repo_root()
        entries = _list_worktrees(main_repo_path, os.getcwd())
    except (subprocess.SubprocessError, OSError):
        return None
    if not entries:
        return None

    stale = 0
    for entry in entries:
        if not os.path.isdir(entry.path):
            stale += 1
            continue
        try:
            is_dirty, _ = _git_status_dirty(entry.path)
        except (subprocess.SubprocessError, OSError):
            continue
        if not is_dirty:
            stale += 1

    return {"local": len(entries), "stale_hint": stale}
```

In `synlynk/status.py`, change the `_format_status_terminal` signature (currently at line 300):

```python
def _format_status_terminal(
    harness_rows: list,
    cycle_map: dict,
    efficiency_ratio: float,
    dispatch_mode: str,
    sentinels_active: int,
    json_output: bool = False,
    rates_updated_at: Optional[str] = None,
    worktree_hint: Optional[dict] = None,
) -> str:
```

In the JSON payload block (currently lines 313-327), add the `"worktrees"` field:

```python
    if json_output:
        payload = {
            "headless_efficiency": efficiency_ratio,
            "fleet": {
                "attached": attached,
                "total": len(agents),
                "dispatch_mode": dispatch_mode,
            },
            "agents": {r["agent_name"]: r for r in harness_rows},
            "cycle_capability": cycle_map,
            "capacity": TIER1_CAPACITY,
            "sentinels_active": sentinels_active,
            "rates_updated_at": rates_updated_at,
            "worktrees": worktree_hint or {"local": 0, "stale_hint": 0},
        }
        return json.dumps(payload, indent=2)
```

In the terminal lines block, change (currently lines 331-340):

```python
    lines = [
        f"SYNLYNK ECOSYSTEM STATUS  {ts}",
        "━" * 44,
        "",
        f"HEADLESS EFFICIENCY  {efficiency_ratio}×   headless dispatch baseline",
        "",
        f"FLEET   {attached}/{len(agents)} attached   mode: {dispatch_mode}",
    ]
    if worktree_hint and worktree_hint.get("stale_hint", 0) > 0:
        lines.append(
            f"WORKTREES  {worktree_hint['local']} local, {worktree_hint['stale_hint']} "
            f"look stale — run `synlynk worktree audit`"
        )
    lines += [
        "BUDGET  limit tracked via .synlynk/config.json",
        _format_rates_line(rates_updated_at),
        "",
        f"{'AGENT SCORE':<14} {'ATTACH':>8}  {'COMPLETE':>9}  {'VERSION':>10}",
    ]
```

Finally, update `cmd_status` (currently lines 371-396) to compute and pass the hint:

```python
def cmd_status(db_conn=None, json_output: bool = False) -> str:
    """Print ecosystem status for the current workspace."""
    from synlynk import _get_db, _read_sentinel_alerts, load_config
    from synlynk.costs import _load_model_rates
    from synlynk.worktree import _worktree_status_hint

    if db_conn is None:
        db_conn = _get_db()

    config = load_config()
    dispatch_mode = config.get("dispatch_mode", "daily-grind")
    harness_rows = _load_harness_status_rows(db_conn)
    cycle_map = _load_cycle_capability_rows(db_conn)
    efficiency = _headless_efficiency_ratio(_load_exec_jobs_from_telemetry())
    sentinels_active = len(_read_sentinel_alerts())
    rates_updated_at = _load_model_rates().get("rates_updated_at")
    worktree_hint = _worktree_status_hint()
    output = _format_status_terminal(
        harness_rows,
        cycle_map,
        efficiency,
        dispatch_mode,
        sentinels_active,
        json_output=json_output,
        rates_updated_at=rates_updated_at,
        worktree_hint=worktree_hint,
    )
    print(output)
    return output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worktree.py -v -k "status_hint or status_terminal or status_json"`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: PASS — in particular, any existing `_format_status_terminal`/`cmd_status` callers in `tests/test_status.py` (if present) must still pass since `worktree_hint` defaults to `None`

- [ ] **Step 6: Commit**

```bash
git add synlynk/worktree.py synlynk/status.py tests/test_worktree.py
git commit -m "feat(status): add WORKTREES staleness hint line"
```

---

### Task 9: Final full-suite run and PR

**Files:** none (verification + PR only)

- [ ] **Step 1: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: PASS, 0 failures

- [ ] **Step 2: Manually exercise both commands against this repo**

Run: `python3 -m synlynk worktree audit`
Expected: prints a real classification of this repo's current worktrees (or the "no stale worktrees" line if none remain)

Run: `python3 -m synlynk worktree clean`
Expected: prints the dry-run variant of the same report, ending in `[dry-run] would remove N worktrees + branches (use --apply)`

Run: `python3 -m synlynk status`
Expected: if any worktrees are currently stale, a `WORKTREES` line appears between `FLEET` and `BUDGET`

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin chore/worktree-audit-design
gh pr create --title "feat(worktree): add synlynk worktree audit/clean command group" --body "$(cat <<'EOF'
## Summary
- Adds `synlynk worktree audit` (read-only) and `synlynk worktree clean` (dry-run by default, `--apply` to execute) per docs/superpowers/specs/2026-07-29-worktree-audit-design.md
- Classifies every worktree as SAFE/NEEDS-REVIEW/UNSAFE via dirty check → merge-base ancestor check → gh PR state → nesting floor
- Adds a lightweight WORKTREES staleness hint line to `synlynk status` (local-only, no gh calls)

## Test plan
- [ ] `pytest tests/test_worktree.py -v` — all 14 spec-required cases plus parser/CLI-wiring coverage pass
- [ ] `pytest tests/ -v` — full suite green, no regressions in `synlynk status`/`synlynk cli` tests
- [ ] Manual: `synlynk worktree audit`, `synlynk worktree clean`, `synlynk status` against this repo's real worktree state
EOF
)"
```

Co-Authored-By trailer per this repo's Repo Hygiene SOP: `Co-Authored-By: Codex <noreply@openai.com>` (implementer) — Claude adds its own trailer only if it makes further commits during review-driven fixes.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- Command shape (`audit [--json]`, `clean [--apply] [--json]`) → Task 7.
- Data source (porcelain parsing, dirty/ancestor/gh/diff-stat signals) → Tasks 1, 2, 5.
- Classification algorithm (all 4 ordered rules) → Tasks 3 (rules 1-3) and 4 (rule 4).
- Report format (SAFE/NEEDS-REVIEW/UNSAFE sections, zero-worktree one-liner, `--json` shape) → Task 5.
- `clean` behavior (dry-run default, `--apply` sequence, nested-before-parent ordering, per-item result lines, partial-failure-continues, final prune) → Task 6.
- Error handling (gh-unavailable fallback, missing-worktree-directory, per-worktree subprocess-failure isolation) → Tasks 3 (missing dir, gh-unavailable) and 5 (`_gather_worktree_signals`'s try/except → `error` reason).
- `synlynk status` integration (local-only hint, omit-when-zero, `--json` field) → Task 8.
- Module & code structure (every named function/dataclass) → present across Tasks 1-8; `WorktreeEntry`/`WorktreeVerdict` (Task 1), `_parse_worktree_list`'s spec-name is realized as `_parse_worktree_porcelain` + `_build_worktree_entries` (Task 1/2 — split for testability, functionally equivalent), `_classify_worktree` (Task 3), `_apply_nesting_floor` (Task 4), `cmd_worktree_audit` (Task 5), `cmd_worktree_clean` (Task 6), `_worktree_status_hint` (Task 8).
- Testing — all 14 enumerated cases are present verbatim across Tasks 3, 4, 6, 8.

**2. Placeholder scan** — no TBD/TODO/"add error handling"-style steps; every step has complete, runnable code.

**3. Type consistency** — `WorktreeEntry(path, branch, nested_under)` and `WorktreeVerdict(path, branch, verdict, reason, nested_under)` are defined once in Task 1 and used with identical field names/order in every later task. `_classify_worktree`'s parameter names (`worktree_missing`, `is_dirty`, `dirty_summary`, `is_ancestor`, `gh_available`, `pr_info`, `net_diff_lines`, `commits_ahead`) are used identically by its Task 3 tests and by `_verdict_from_signals` in Task 5. `cmd_worktree_audit`/`cmd_worktree_clean` signatures (`json_output: bool = False`, `apply: bool = False`) match the CLI wiring in Task 7 and the spec's command shape.

**Noted implementation deviations from the spec's literal wording (both intentional, both behavior-preserving):**
- Spec names one function `_parse_worktree_list`; this plan splits it into a pure `_parse_worktree_porcelain` (text → raw dicts) and `_build_worktree_entries` (exclusion + nesting) so the porcelain-parsing logic is unit-testable without a real git repo. Combined, they do exactly what the spec's single function describes.
- Spec's diff-stat signal uses `git diff --stat`; this plan uses `git diff --shortstat`, which reports the same insertions/deletions totals in a single easily-regexable line instead of a per-file table — net-line-count output is identical.
- `_worktree_status_hint`'s spec return type is written as `Optional[str]`; this plan returns `Optional[dict]` (`{"local": N, "stale_hint": M}`) instead, since `synlynk status`'s JSON payload needs those two numbers directly (the spec's own `--json` section requires the same `{"local": N, "stale_hint": M}` shape). `_format_status_terminal` builds the terminal string from the dict — behavior matches the spec's example output exactly.
