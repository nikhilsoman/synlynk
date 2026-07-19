# Story-ID Auto-Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every `dispatch_agent()` call gets a resolved `story_id` — auto-detected from a GitHub issue reference or generated ad-hoc — so `capability_ratings` rows are written for every dispatch instead of silently dropped, and existing jobs missing a `story_id` can be backfilled after the fact.

**Architecture:** A new `synlynk/story_provisioning.py` module owns issue detection (`--issue` flag → `#(\d+)` regex on task text → ad-hoc timestamp fallback), a pluggable classifier (`heuristic` implemented now; `llm`/`pm_manual` raise `NotImplementedError` stubs gated by a new `story_classification.method` config key), and `resolve_or_create_story_id()`, which is idempotent (looks up `stories` before creating). `dispatch_agent()` calls it whenever no explicit `story_id` was passed. `cmd_story_create()` gains an optional `story_id` override so the resolver can insert a caller-chosen deterministic ID instead of the function's own md5-derived one. A new `synlynk backfill-capability-ratings` CLI command walks `jobs.json` for jobs with `story_id == ""`, resolves/creates a story for each from its stored task text and log, and re-invokes `_write_capability_rating()`.

**Tech Stack:** Python 3 stdlib only (`re`, `time`, `subprocess`, `hashlib`, `json`), sqlite3 via the existing `_get_db()`/`_migrate_db()` machinery, `gh issue view` CLI for label/title lookups, pytest + `project_dir`/`isolated_db` fixtures from `tests/conftest.py`.

**Correction vs. the approved spec (`docs/superpowers/specs/2026-07-19-story-id-auto-provisioning-design.md`):** two implementation details in the spec don't match the real codebase and are corrected here:
1. The spec assumed `cmd_story_create(story_id="story-issue-395", ...)` already accepts a caller-supplied ID. It doesn't — `synlynk/db.py:1461-1503` always generates its own via `hashlib.md5(f"{title}{time.time()}"...)`. Task 1 below adds the missing optional parameter.
2. The spec's stated classifier fallback (`engg_domain="unknown"`, `stage="build"`) uses values that are not in the real enums. `_DISCIPLINES`, `_ORG_DOMAINS`, `_ROLES`, `_STAGES` (`synlynk/db.py:13-38`) have no `"unknown"` slot, and `_validate_enum_value()` (`synlynk/db.py:45-50`) raises `ValueError` rather than coercing. `_STAGES` also doesn't contain `"build"` (that's a separate `phase` field, whose own default in `cmd_story_create` genuinely is `"build"` — the spec conflated the two fields). The classifier below passes `None` for unmatched fields instead, so `_normalize_capability_tags()`'s real defaulting (`backend`/`platform`/`dev`/`open`) applies — this reproduces the spec's intent ("don't block on unmatched fields") using values that actually validate.

---

### Task 1: Add optional `story_id` override to `cmd_story_create()`

**Files:**
- Modify: `synlynk/db.py:1461-1503`
- Test: `tests/test_capability_scoring.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_capability_scoring.py`:

```python
def test_cmd_story_create_accepts_story_id_override(project_dir, monkeypatch):
    import synlynk as sl

    returned_id = sl.cmd_story_create("Fix flaky worktree test", story_id="story-issue-395")

    assert returned_id == "story-issue-395"
    conn = sl._get_db()
    row = conn.execute(
        "SELECT story_id, title FROM stories WHERE story_id=?", ("story-issue-395",)
    ).fetchone()
    conn.close()
    assert row == ("story-issue-395", "Fix flaky worktree test")


def test_cmd_story_create_still_generates_id_when_not_given(project_dir, monkeypatch):
    import synlynk as sl

    generated_id = sl.cmd_story_create("Some other story")

    assert generated_id.startswith("story-")
    assert generated_id != "story-issue-395"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_scoring.py::test_cmd_story_create_accepts_story_id_override -v`
Expected: FAIL with `TypeError: cmd_story_create() got an unexpected keyword argument 'story_id'`

- [ ] **Step 3: Implement the override**

In `synlynk/db.py`, change the signature and body of `cmd_story_create` (lines 1461-1475):

```python
def cmd_story_create(title: str, engg_domain: str = None,
                     org_domain: str = None, phase: str = "build",
                     org_domain_tags: list = None,
                     estimated_tokens: int = None,
                     stack_tags: list = None,
                     discipline: str = None,
                     role: str = None,
                     stage: str = None,
                     story_id: str = None) -> str:
    """Creates a story record in state.db. Returns the generated or supplied story_id."""
    from synlynk import _GREEN, _RESET, _generate_todo_md, _get_db, load_config
    import hashlib as _hashlib
    import json as _json
    if story_id is None:
        story_id = "story-" + _hashlib.md5(
            f"{title}{time.time()}".encode()
        ).hexdigest()[:8]
```

Leave the rest of the function body (lines 1476-1503) unchanged — it already just uses the `story_id` local variable for the INSERT and the return value.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_scoring.py::test_cmd_story_create_accepts_story_id_override tests/test_capability_scoring.py::test_cmd_story_create_still_generates_id_when_not_given -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_capability_scoring.py
git commit -m "feat(db): allow cmd_story_create to accept a caller-supplied story_id"
```

---

### Task 2: Add `story_classification` key to config defaults

**Files:**
- Modify: `synlynk/__init__.py:1366-1394` (`load_config()`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_load_config_defaults_story_classification_method(project_dir):
    import synlynk as sl

    config = sl.load_config()

    assert config["story_classification"] == {"method": "heuristic"}


def test_load_config_preserves_explicit_story_classification_method(project_dir):
    import json
    import synlynk as sl

    config_path = ".synlynk/config.json"
    with open(config_path) as f:
        existing = json.load(f)
    existing["story_classification"] = {"method": "pm_manual"}
    with open(config_path, "w") as f:
        json.dump(existing, f)

    config = sl.load_config()

    assert config["story_classification"] == {"method": "pm_manual"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_load_config_defaults_story_classification_method -v`
Expected: FAIL with `KeyError: 'story_classification'`

- [ ] **Step 3: Add the default**

In `synlynk/__init__.py`, inside the `defaults` dict in `load_config()` (around line 1387, right after `"roles": _default_roles_map(),`):

```python
        "roles": _default_roles_map(),
        "story_classification": {"method": "heuristic"},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_load_config_defaults_story_classification_method tests/test_config.py::test_load_config_preserves_explicit_story_classification_method -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_config.py
git commit -m "feat(config): add story_classification.method schema key"
```

---

### Task 3: Create `synlynk/story_provisioning.py` — issue detection + heuristic classifier

**Files:**
- Create: `synlynk/story_provisioning.py`
- Test: `tests/test_story_provisioning.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_story_provisioning.py`:

```python
import subprocess
import pytest


def test_detect_issue_number_prefers_explicit_issue_arg():
    from synlynk.story_provisioning import _detect_issue_number

    assert _detect_issue_number("fix something #999", issue=395) == 395


def test_detect_issue_number_falls_back_to_regex_on_task_text():
    from synlynk.story_provisioning import _detect_issue_number

    assert _detect_issue_number("rebind DB_PATH per #395", issue=None) == 395


def test_detect_issue_number_returns_none_when_no_match():
    from synlynk.story_provisioning import _detect_issue_number

    assert _detect_issue_number("free text task with no issue ref", issue=None) is None


def test_classify_heuristic_matches_docs_keyword_when_gh_unavailable(monkeypatch):
    from synlynk import story_provisioning as sp

    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )
    result = sp._classify_heuristic(issue_number=None, task_text="Update the README docs")

    assert result["discipline"] == "docs"
    assert result["title"] == "Update the README docs"


def test_classify_heuristic_uses_gh_issue_labels_when_available(monkeypatch):
    from synlynk import story_provisioning as sp
    import json

    class FakeResult:
        returncode = 0
        stdout = json.dumps({
            "title": "Rebind DB_PATH in selftest",
            "body": "The live selftest writes to the wrong DB",
            "labels": [{"name": "bug"}],
        })
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())
    result = sp._classify_heuristic(issue_number=395, task_text="rebind DB_PATH #395")

    assert result["title"] == "Rebind DB_PATH in selftest"
    assert result["discipline"] == "backend"


def test_classify_heuristic_falls_back_to_none_fields_when_nothing_matches(monkeypatch):
    from synlynk import story_provisioning as sp

    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )
    result = sp._classify_heuristic(issue_number=None, task_text="do the thing")

    assert result["discipline"] is None
    assert result["org_domain"] is None
    assert result["role"] is None
    assert result["stage"] is None


def test_classify_story_raises_not_implemented_for_llm_method(monkeypatch):
    from synlynk import story_provisioning as sp

    with pytest.raises(NotImplementedError):
        sp.classify_story(issue_number=None, task_text="anything", method="llm")


def test_classify_story_raises_not_implemented_for_pm_manual_method(monkeypatch):
    from synlynk import story_provisioning as sp

    with pytest.raises(NotImplementedError):
        sp.classify_story(issue_number=None, task_text="anything", method="pm_manual")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_story_provisioning.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.story_provisioning'`

- [ ] **Step 3: Implement the module**

Create `synlynk/story_provisioning.py`:

```python
"""synlynk story provisioning: issue detection, heuristic classification,
and deterministic story_id resolution for dispatches missing a story_id."""

import json
import re
import subprocess
import sys
import time

_ISSUE_NUMBER_RE = re.compile(r"#(\d+)")


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _detect_issue_number(task_text: str, issue=None):
    """Resolves an issue number: explicit --issue flag > #(\\d+) in task text > None."""
    if issue is not None:
        return int(issue)
    match = _ISSUE_NUMBER_RE.search(task_text or "")
    if match:
        return int(match.group(1))
    return None


_DISCIPLINE_KEYWORDS = {
    "frontend": ("frontend", "css", "html", "ui ", "react"),
    "backend": ("backend", "api", "server", "database", "db_path", "sqlite"),
    "data": ("data pipeline", "etl", "dataset"),
    "ml": ("model training", "ml ", "machine learning"),
    "testing": ("test", "pytest", "selftest", "flaky"),
    "security": ("security", "auth", "vulnerability", "cve"),
    "devops": ("ci ", "deploy", "pipeline", "docker", "infra"),
    "docs": ("docs", "documentation", "readme", "blog post"),
    "architecture": ("architecture", "redesign", "refactor"),
}

_ORG_DOMAIN_LABEL_MAP = {
    "documentation": "content",
}


def _classify_heuristic(issue_number, task_text: str) -> dict:
    """Classifies a story from GitHub issue labels/title (if available) or task text keywords.

    Returns a dict with discipline/org_domain/role/stage/title. Unmatched fields
    are None so _normalize_capability_tags()'s real defaults apply downstream —
    the enums have no "unknown" value to fall back to.
    """
    title = None
    haystack = (task_text or "").lower()
    labels: list = []

    if issue_number is not None:
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_number),
                 "--json", "title,body,labels"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                issue_data = json.loads(result.stdout)
                title = issue_data.get("title")
                labels = [lbl.get("name", "").lower() for lbl in issue_data.get("labels", [])]
                haystack = f"{title or ''} {issue_data.get('body') or ''} {task_text or ''}".lower()
        except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

    if title is None:
        title = (task_text or "").strip()[:200] or f"Ad-hoc dispatch {int(time.time())}"

    discipline = None
    for candidate, keywords in _DISCIPLINE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords) or candidate in labels:
            discipline = candidate
            break

    org_domain = None
    for label in labels:
        if label in _ORG_DOMAIN_LABEL_MAP:
            org_domain = _ORG_DOMAIN_LABEL_MAP[label]
            break

    return {
        "title": title,
        "discipline": discipline,
        "org_domain": org_domain,
        "role": None,
        "stage": None,
    }


def classify_story(issue_number, task_text: str, method: str = "heuristic") -> dict:
    """Dispatches to the configured classification method."""
    if method == "heuristic":
        return _classify_heuristic(issue_number, task_text)
    if method == "llm":
        raise NotImplementedError("story classification method 'llm' is not yet implemented")
    if method == "pm_manual":
        raise NotImplementedError("story classification method 'pm_manual' is not yet implemented")
    raise ValueError(f"Unknown story_classification.method: {method!r}")


def resolve_or_create_story_id(task_text: str, issue=None) -> str:
    """Returns an existing or newly-created story_id for a dispatch with no story_id.

    Deterministic: story-issue-<N> when an issue is detected (reused across repeat
    dispatches for the same issue), else story-adhoc-<timestamp>.
    """
    issue_number = _detect_issue_number(task_text, issue=issue)
    if issue_number is not None:
        story_id = f"story-issue-{issue_number}"
    else:
        story_id = f"story-adhoc-{int(time.time())}"

    get_db = _pkg("_get_db")
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone()
    conn.close()
    if exists:
        return story_id

    load_config = _pkg("load_config")
    config = load_config() if load_config else {}
    method = (config.get("story_classification") or {}).get("method", "heuristic")
    classification = classify_story(issue_number, task_text, method=method)

    cmd_story_create = _pkg("cmd_story_create")
    cmd_story_create(
        classification["title"],
        discipline=classification["discipline"],
        org_domain=classification["org_domain"],
        role=classification["role"],
        stage=classification["stage"],
        story_id=story_id,
    )
    return story_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_story_provisioning.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/story_provisioning.py tests/test_story_provisioning.py
git commit -m "feat(story): add issue detection, heuristic classifier, resolve_or_create_story_id"
```

---

### Task 4: Wire `story_provisioning` into `synlynk/__init__.py`

**Files:**
- Modify: `synlynk/__init__.py`
- Test: `tests/test_story_provisioning.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_story_provisioning.py`:

```python
def test_resolve_or_create_story_id_reachable_from_top_level_package():
    import synlynk as sl

    assert callable(sl.resolve_or_create_story_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_story_provisioning.py::test_resolve_or_create_story_id_reachable_from_top_level_package -v`
Expected: FAIL with `AttributeError: module 'synlynk' has no attribute 'resolve_or_create_story_id'`

- [ ] **Step 3: Add the import**

In `synlynk/__init__.py`, add a new import block right after the existing `from synlynk.jobs import (...)` block (after line 175, which currently ends with `cmd_jobs_handoff,\n)`):

```python
from synlynk.story_provisioning import (
    _classify_heuristic,
    _detect_issue_number,
    classify_story,
    resolve_or_create_story_id,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_story_provisioning.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_story_provisioning.py
git commit -m "feat(story): expose story_provisioning functions on the synlynk package"
```

---

### Task 5: Wire `resolve_or_create_story_id()` into `dispatch_agent()`

**Files:**
- Modify: `synlynk/dispatch.py:808-825`
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatch.py`:

```python
def test_dispatch_agent_auto_provisions_story_id_when_not_given(project_dir, monkeypatch):
    import synlynk as sl

    class FakeProc:
        pid = 1

    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)

    job = sl.dispatch_agent("claude", "rebind DB_PATH per #395", context_mode="none")

    assert job["story_id"] == "story-issue-395"
    conn = sl._get_db()
    row = conn.execute("SELECT story_id FROM stories WHERE story_id=?", ("story-issue-395",)).fetchone()
    conn.close()
    assert row is not None


def test_dispatch_agent_reuses_existing_story_id_for_repeat_issue_dispatch(project_dir, monkeypatch):
    import synlynk as sl

    class FakeProc:
        pid = 1

    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)

    job1 = sl.dispatch_agent("claude", "first pass on #395", context_mode="none")
    job2 = sl.dispatch_agent("codex", "follow-up fix on #395", context_mode="none")

    assert job1["story_id"] == job2["story_id"] == "story-issue-395"


def test_dispatch_agent_explicit_story_id_bypasses_auto_provisioning(project_dir, monkeypatch):
    import synlynk as sl

    class FakeProc:
        pid = 1

    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)

    job = sl.dispatch_agent("claude", "task text with #999", story_id="story-manual-1", context_mode="none")

    assert job["story_id"] == "story-manual-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_auto_provisions_story_id_when_not_given -v`
Expected: FAIL — `job["story_id"]` is `None`/empty instead of `"story-issue-395"`

- [ ] **Step 3: Wire in the resolver**

In `synlynk/dispatch.py`, change `dispatch_agent()`'s signature and the block right after agent validation (lines 808-825):

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
    if story_id and not force_agent:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                agent = best

    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")

    if not story_id:
        resolve_or_create_story_id = _pkg("resolve_or_create_story_id")
        if resolve_or_create_story_id:
            story_id = resolve_or_create_story_id(task, issue=issue)
```

Everything from `if agent == "local":` onward (previously line 827) is unchanged — this insert lands between the existing agent-validation `raise ValueError` and the local-agent concurrency check, so it runs after best-agent routing (which only applies when a `story_id` was already supplied) and before every downstream use of `story_id` (job dict, context scope, etc.).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_auto_provisions_story_id_when_not_given tests/test_dispatch.py::test_dispatch_agent_reuses_existing_story_id_for_repeat_issue_dispatch tests/test_dispatch.py::test_dispatch_agent_explicit_story_id_bypasses_auto_provisioning -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat(dispatch): auto-provision story_id when none is supplied"
```

---

### Task 6: Add `--issue` CLI flag and thread it through

**Files:**
- Modify: `synlynk/cli.py:424-451` (dispatch subparser), `synlynk/cli.py:825-833` (call site)
- Test: `tests/test_cli_parser.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_parser.py`:

```python
def test_dispatch_parser_accepts_issue_flag():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["dispatch", "claude", "--task", "fix it", "--issue", "395"])

    assert args.issue == 395


def test_dispatch_parser_issue_defaults_to_none():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["dispatch", "claude", "--task", "fix it"])

    assert args.issue is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_parser.py::test_dispatch_parser_accepts_issue_flag -v`
Expected: FAIL with `AttributeError: 'Namespace' object has no attribute 'issue'`

- [ ] **Step 3: Add the flag and thread it through**

In `synlynk/cli.py`, add a new `add_argument` call right after the existing `--story` registration (after line 433, `help="Story/task ID for context labelling")`):

```python
    dispatch_parser.add_argument("--issue", type=int, default=None,
        help="GitHub issue number to associate this dispatch with (auto-detected from #N in --task if omitted)")
```

Then update the call site (lines 827-832) to pass it through:

```python
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_parser.py::test_dispatch_parser_accepts_issue_flag tests/test_cli_parser.py::test_dispatch_parser_issue_defaults_to_none -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_cli_parser.py
git commit -m "feat(cli): add --issue flag to synlynk dispatch"
```

---

### Task 7: `synlynk backfill-capability-ratings` command

**Files:**
- Modify: `synlynk/story_provisioning.py` (add `cmd_backfill_capability_ratings`)
- Modify: `synlynk/__init__.py` (export it)
- Modify: `synlynk/cli.py` (new subparser + dispatch branch, both `from synlynk import (...)` blocks)
- Test: `tests/test_story_provisioning.py`, `tests/test_cli_parser.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_story_provisioning.py`:

```python
def test_backfill_capability_ratings_skips_jobs_with_existing_story_id(project_dir, monkeypatch):
    from synlynk import story_provisioning as sp
    import synlynk as sl

    sl._save_jobs([{"id": "job-1", "agent": "claude", "story_id": "story-existing",
                    "task": "already has a story", "log_file": None}])

    backfilled, skipped = sp.cmd_backfill_capability_ratings()

    assert backfilled == 0
    assert skipped == 0


def test_backfill_capability_ratings_skips_jobs_with_missing_log_file(project_dir, monkeypatch, tmp_path):
    from synlynk import story_provisioning as sp
    import synlynk as sl

    missing_log = str(tmp_path / "does-not-exist.log")
    sl._save_jobs([{"id": "job-2", "agent": "claude", "story_id": "",
                    "task": "no log on disk", "log_file": missing_log}])

    backfilled, skipped = sp.cmd_backfill_capability_ratings()

    assert backfilled == 0
    assert skipped == 1


def test_backfill_capability_ratings_resolves_story_and_writes_rating(project_dir, monkeypatch, tmp_path):
    from synlynk import story_provisioning as sp
    import synlynk as sl
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )

    log_file = tmp_path / "job-3.log"
    log_file.write_text("47 passed in 3.2s\n")
    sl._save_jobs([{"id": "job-3", "agent": "claude", "story_id": "",
                    "task": "fix the thing #501", "log_file": str(log_file),
                    "model_at_dispatch": "claude-sonnet-5"}])

    backfilled, skipped = sp.cmd_backfill_capability_ratings()

    assert backfilled == 1
    assert skipped == 0
    jobs = sl._load_jobs()
    assert jobs[0]["story_id"] == "story-issue-501"
    conn = sl._get_db()
    rating = conn.execute(
        "SELECT story_id FROM capability_ratings WHERE story_id=?", ("story-issue-501",)
    ).fetchone()
    conn.close()
    assert rating is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_story_provisioning.py -k backfill -v`
Expected: FAIL with `AttributeError: module 'synlynk.story_provisioning' has no attribute 'cmd_backfill_capability_ratings'`

- [ ] **Step 3: Implement the command**

Append to `synlynk/story_provisioning.py`:

```python
def cmd_backfill_capability_ratings() -> tuple:
    """Backfills capability_ratings for completed jobs missing a story_id.

    Returns (backfilled_count, skipped_count).
    """
    load_jobs = _pkg("_load_jobs")
    save_jobs = _pkg("_save_jobs")
    write_rating = _pkg("_write_capability_rating")

    jobs = load_jobs()
    backfilled = 0
    skipped = 0

    for job in jobs:
        if job.get("story_id"):
            continue

        log_file = job.get("log_file")
        if not log_file or not os.path.exists(log_file):
            print(f"  ⚠ skipping job {job.get('id', '?')}: no log file at {log_file!r}")
            skipped += 1
            continue

        try:
            with open(log_file) as f:
                log_text = f.read()
        except OSError as exc:
            print(f"  ⚠ skipping job {job.get('id', '?')}: could not read log ({exc})")
            skipped += 1
            continue

        story_id = resolve_or_create_story_id(job.get("task", ""))
        job["story_id"] = story_id
        try:
            write_rating(job, log_text)
        except ValueError as exc:
            print(f"  ⚠ capability rating skipped for job {job.get('id', '?')}: {exc}")
            skipped += 1
            continue
        backfilled += 1

    save_jobs(jobs)
    print(f"  ✓ backfilled {backfilled}, skipped {skipped}")
    return backfilled, skipped
```

Add `import os` to the top of `synlynk/story_provisioning.py` (alongside the existing `import json`, `import re`, `import subprocess`, `import sys`, `import time`).

- [ ] **Step 4: Export it from the package**

In `synlynk/__init__.py`, update the `story_provisioning` import block added in Task 4:

```python
from synlynk.story_provisioning import (
    _classify_heuristic,
    _detect_issue_number,
    classify_story,
    cmd_backfill_capability_ratings,
    resolve_or_create_story_id,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_story_provisioning.py -k backfill -v`
Expected: 3 passed

- [ ] **Step 6: Wire the CLI subcommand**

In `synlynk/cli.py`, add a new subparser after the `logs_parser` registration (after the block ending `help="Number of lines to show (default: 50)")`):

```python
    backfill_parser = subparsers.add_parser(
        "backfill-capability-ratings",
        help="Resolve/create story_ids for completed jobs missing one and write their capability ratings")
```

Add `cmd_backfill_capability_ratings` to both `from synlynk import (...)` blocks in `cli.py` (the one inside `build_parser()` around line 185, alphabetically between `cmd_agent_run` and `cmd_decide`; and the one inside the command-dispatch function around line 715, same alphabetical spot).

Add the dispatch branch in the `elif args.command ==` chain, right after the existing `elif args.command == "dispatch":` block (after its `sys.exit(1)` at line ~840):

```python
    elif args.command == "backfill-capability-ratings":
        cmd_backfill_capability_ratings()
```

- [ ] **Step 7: Write the CLI-level test**

Add to `tests/test_cli_parser.py`:

```python
def test_backfill_capability_ratings_parser_registered():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["backfill-capability-ratings"])

    assert args.command == "backfill-capability-ratings"
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_cli_parser.py::test_backfill_capability_ratings_parser_registered -v`
Expected: 1 passed

- [ ] **Step 9: Commit**

```bash
git add synlynk/story_provisioning.py synlynk/__init__.py synlynk/cli.py tests/test_story_provisioning.py tests/test_cli_parser.py
git commit -m "feat(cli): add synlynk backfill-capability-ratings command"
```

---

### Task 8: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass, including the pre-existing `test_dispatch_agent_task_scope_without_story_uses_reduced_context` (in `tests/test_synlynk.py`) and `test_dispatch_agent_creates_job_entry` / `test_dispatch_agent_claude_includes_dangerously_skip_permissions` (both call `dispatch_agent` with an explicit `story_id="14"`, so Task 5's change is a no-op for them).

**Known content-shape change to watch for:** `test_dispatch_agent_task_scope_without_story_uses_reduced_context` dispatches with no `story_id`, so after Task 5 it now gets an auto-provisioned `story-adhoc-<timestamp>` instead of `None`. `_generate_task_context()` (`synlynk/context.py:75-103`) writes an extra `## Story` section when `story_id` resolves to a real row. The test's assertions (`task_size < full_size`, absence of `"Recent Devlog"` and `"Sentinel Alerts"`) still hold either way, but if this test starts failing, that's the cause — not a real regression, just fix the fixture-generated context size assumption if needed.

- [ ] **Step 2: If anything fails, fix and re-run**

Re-run just the failing test file with `-v` after each fix until `pytest tests/ -v` is fully green.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A
git commit -m "test: fix regressions surfaced by story_id auto-provisioning"
```

(Skip this step entirely if Step 1 was already green — don't create an empty commit.)

---

## Self-Review Notes

- **Spec coverage:** All three of the spec's architecture sections are covered — Task 5/6 (resolver + dispatch wiring + issue detection), Task 3 (heuristic classifier + config schema in Task 2), Task 7 (backfill command). Deterministic story-issue-`<N>` reuse across repeat dispatches is covered by Task 5's `test_dispatch_agent_reuses_existing_story_id_for_repeat_issue_dispatch`.
- **Placeholder scan:** No TBD/TODO markers; every step has complete code.
- **Type consistency:** `resolve_or_create_story_id(task_text, issue=None) -> str` signature is identical everywhere it's called (Task 5's `dispatch_agent`, Task 7's `cmd_backfill_capability_ratings`). `classify_story(issue_number, task_text, method) -> dict` and `_classify_heuristic(issue_number, task_text) -> dict` return the same four-plus-title key shape (`title`, `discipline`, `org_domain`, `role`, `stage`) used consistently in Task 3's tests and Task 5/7's callers.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-story-id-auto-provisioning.md`. This is a Python/CLI/tests-only plan — entirely Codex's role per this project's PM/implementer split (Claude does not implement).

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh Codex subagent per task via `synlynk dispatch codex`, review between tasks, fast iteration.

**2. Inline Execution** — dispatch the whole plan to Codex as one job with `--context-mode full`, batch execution with checkpoints.

Which approach?
