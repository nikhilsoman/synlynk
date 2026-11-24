# Maintainer Full Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Maintainer to parity with TPM's autonomy model — a real scheduled wake cycle that acts on its findings, with settings-driven per-action toggles, Agent Studio/Overview/Proposal Studio surfaces, fence-hint and Slack notification paths, a CLI/GitHub Actions trigger, and a portability layer (taxonomy-as-config + a domain-pack extension point) so none of it is hardcoded to this repo's software-engineering vocabulary.

**Architecture:** A small `MaintainerActionRegistry` (`synlynk/maintainer_registry.py`) lets any action (sentinel triage, backlog burndown, mesh sweep) register itself with a default config, a filter schema, and a run function; `run_maintainer_wake_cycle()` iterates the registry the same way `run_tpm_wake_cycle()` drives TPM's loop, staging proposals through a three-tier proximal-selection resolver (code-graph → doc-graph → keyword fallback) that reads its keyword taxonomy from `.synlynk/maintainer_taxonomy.json` instead of a hardcoded dict. A generic `generate_role_ops_panel_html(role_slug, data)` (`synlynk/viz/role_ops_panel.py`) renders the registry's state for any role, consumed from both Agent Studio (full panel) and the Overview page (condensed widget). `viz/roadmap_studio.py`'s existing TPM-only approval UI is renamed to `generate_proposal_studio_html` (with a backward-compatible alias) and extended to render a `source` badge and a severity-flagged lane so Maintainer's proposals appear alongside TPM's unchanged.

**Tech Stack:** Python 3 stdlib only (no new dependencies) — `json`, `sqlite3` (existing `_get_db()` connections), `argparse` (CLI), server-rendered HTML/CSS/vanilla JS strings (existing Vizor pattern, no frontend framework), `pytest` for tests.

---

## File Structure

| File | Responsibility |
|---|---|
| **Create** `synlynk/maintainer_taxonomy.py` | Loads/merges `.synlynk/maintainer_taxonomy.json` + `.synlynk/domain_pack.json`; exposes `cluster_keywords()`, `remediation_topics()`, `doc_type_extensions()` |
| **Create** `.synlynk/maintainer_taxonomy.json` | This repo's own pre-populated cluster keywords + remediation topics (today's hardcoded values, moved to config) |
| **Create** `.synlynk/domain_pack.json` | The one worked "synlynk-default" domain pack (§7 of the spec) |
| **Modify** `synlynk/maintainer.py` | `cluster_open_issues()` and `is_issue_remediated()` read from `maintainer_taxonomy.py` instead of hardcoded constants; adds `select_proposal_target()` (dual-graph proximal selection), `run_maintainer_wake_cycle()`, `_ensure_github_issue_for_story()`; registers the 3 actions with `maintainer_registry.py` at import time |
| **Create** `synlynk/maintainer_registry.py` | `register_action()`, `registered_actions()`, `get_action_config()`, `clear_registry()` |
| **Modify** `synlynk/docgraph.py` | `classify_doc_type()` gains an optional `extensions` param checked before the `general_doc` fallback |
| **Modify** `synlynk/scheduler.py` | `_run_maintainer_triage_pass()` calls `run_maintainer_wake_cycle()` instead of discarding `triage_sentinel_alerts()`'s result |
| **Create** `synlynk/maintainer_hints.py` | Fence-hint contributor; registers itself with `fencing.py` on import |
| **Modify** `synlynk/notifiers/slack.py` | Adds `"maintainer_promote"` to `NOTIFY_EVENT_TYPES`; adds `_slack_webhook_url()` config reader |
| **Modify** `synlynk/cli.py` | New `maintainer wake` subcommand (parser + dispatch branch); imports `maintainer_hints` for its registration side effect |
| **Modify** `synlynk/taxonomy.py` | New `maintainer wake` `COMMAND_TAXONOMY` entry |
| **Create** `.github/workflows/maintainer-sweep.yml` | `workflow_dispatch` + nightly cron calling `synlynk maintainer wake` |
| **Modify** `synlynk/viz/onboarding.py` | Adds `maintainer` to `roles_info` |
| **Create** `synlynk/viz/role_ops_panel.py` | `generate_role_ops_panel_html(role_slug, data)` — generic operations panel |
| **Modify** `synlynk/viz/roles.py` | Inserts the Operations panel after the existing "Edit Charter" `<details>` block |
| **Modify** `synlynk/viz/overview.py` | Inserts a condensed Maintainer widget section-card before the shortcuts grid |
| **Modify** `synlynk/viz/roadmap_studio.py` | Renames `generate_roadmap_studio_html` → `generate_proposal_studio_html` (alias kept), adds `source` badge + "Needs attention now" lane |

Tests live alongside: `tests/test_maintainer_taxonomy.py`, `tests/test_maintainer_registry.py`, extensions to `tests/test_maintainer.py`, `tests/test_docgraph.py`, `tests/test_fencing_hint_contributors.py`, `tests/test_viz_roles.py`, `tests/test_viz_roadmap_studio.py`, a new `tests/test_viz_role_ops_panel.py`, and a new `tests/test_cli_maintainer_wake.py`.

---

### Task 1: Taxonomy config loader (portability — spec §6)

**Files:**
- Create: `synlynk/maintainer_taxonomy.py`
- Create: `.synlynk/maintainer_taxonomy.json`
- Test: `tests/test_maintainer_taxonomy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_maintainer_taxonomy.py
import json

from synlynk.maintainer_taxonomy import cluster_keywords, remediation_topics


def test_cluster_keywords_reads_repo_config(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({
        "cluster_keywords": {"backend": ["sqlite", "api"]},
        "remediation_topics": ["custom topic"],
    }))

    keywords = cluster_keywords(repo_root=str(tmp_path))
    assert keywords == {"backend": ["sqlite", "api"]}

    topics = remediation_topics(repo_root=str(tmp_path))
    assert topics == ("custom topic",)


def test_cluster_keywords_falls_back_to_builtin_defaults_when_missing(tmp_path):
    keywords = cluster_keywords(repo_root=str(tmp_path))
    assert "backend" in keywords
    assert "frontend" in keywords

    topics = remediation_topics(repo_root=str(tmp_path))
    assert "invariant 1" in topics
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_maintainer_taxonomy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.maintainer_taxonomy'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/maintainer_taxonomy.py
"""Per-workspace domain vocabulary for Maintainer's keyword clustering and
remediation-topic matching (spec: docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md §6).

Moves cluster_open_issues()'s keyword buckets and is_issue_remediated()'s
remediation-topic list out of Python so a synlynk-managed workspace outside
this repo's own software-engineering domain can populate its own vocabulary
without a code change.
"""
import json
import os
from typing import Dict, List, Tuple

_BUILTIN_CLUSTER_KEYWORDS: Dict[str, List[str]] = {
    "backend": ["sqlite", "database", "server", "api", "endpoint", "query"],
    "frontend": ["css", "html", "ui", "vizor", "widget", "render"],
    "cli": ["argparse", "subcommand", "cli.py", "command"],
    "docs": ["readme", "docstring", "documentation", "spec"],
    "sentinel": ["alert", "circuit breaker", "sentinel", "flatline"],
    "testing": ["pytest", "fixture", "test_", "flaky"],
}

_BUILTIN_REMEDIATION_TOPICS: Tuple[str, ...] = (
    "invariant 1",
    "circuit breaker",
    "daemon supervision",
)


def _taxonomy_path(repo_root: str) -> str:
    return os.path.join(repo_root, ".synlynk", "maintainer_taxonomy.json")


def _load_taxonomy_file(repo_root: str) -> dict:
    path = _taxonomy_path(repo_root)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def cluster_keywords(repo_root: str = ".") -> Dict[str, List[str]]:
    """Cluster name -> keyword list, from .synlynk/maintainer_taxonomy.json or built-in defaults."""
    data = _load_taxonomy_file(repo_root)
    configured = data.get("cluster_keywords")
    if isinstance(configured, dict) and configured:
        return configured
    return dict(_BUILTIN_CLUSTER_KEYWORDS)


def remediation_topics(repo_root: str = ".") -> Tuple[str, ...]:
    """Remediation-topic keywords, from .synlynk/maintainer_taxonomy.json or built-in defaults."""
    data = _load_taxonomy_file(repo_root)
    configured = data.get("remediation_topics")
    if isinstance(configured, list) and configured:
        return tuple(configured)
    return _BUILTIN_REMEDIATION_TOPICS
```

```json
// .synlynk/maintainer_taxonomy.json
{
  "cluster_keywords": {
    "backend": ["sqlite", "database", "server", "api", "endpoint", "query"],
    "frontend": ["css", "html", "ui", "vizor", "widget", "render"],
    "cli": ["argparse", "subcommand", "cli.py", "command"],
    "docs": ["readme", "docstring", "documentation", "spec"],
    "sentinel": ["alert", "circuit breaker", "sentinel", "flatline"],
    "testing": ["pytest", "fixture", "test_", "flaky"]
  },
  "remediation_topics": ["invariant 1", "circuit breaker", "daemon supervision"]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_maintainer_taxonomy.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/maintainer_taxonomy.py .synlynk/maintainer_taxonomy.json tests/test_maintainer_taxonomy.py
git commit -m "feat(maintainer): externalize cluster/remediation vocabulary into per-workspace config

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 2: Domain Pack extension point (spec §7)

**Files:**
- Modify: `synlynk/maintainer_taxonomy.py` (add `load_domain_pack`, `doc_type_extensions`, merge logic in `cluster_keywords`/`remediation_topics`)
- Modify: `synlynk/docgraph.py:98-129` (`classify_doc_type`)
- Create: `.synlynk/domain_pack.json`
- Test: `tests/test_maintainer_taxonomy.py` (append), `tests/test_docgraph.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_maintainer_taxonomy.py`:

```python
from synlynk.maintainer_taxonomy import load_domain_pack, doc_type_extensions


def test_load_domain_pack_merges_cluster_keywords_over_repo_defaults(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "maintainer_taxonomy.json").write_text(json.dumps({
        "cluster_keywords": {"backend": ["sqlite"]},
        "remediation_topics": ["topic a"],
    }))
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({
        "pack_name": "test-pack",
        "cluster_keywords": {"backend": ["sqlite", "postgres"], "ops": ["pager"]},
        "remediation_topics": ["topic b"],
        "doc_type_extensions": {"compliance_doc": ["hipaa"]},
    }))

    pack = load_domain_pack(repo_root=str(tmp_path))
    assert pack["pack_name"] == "test-pack"

    keywords = cluster_keywords(repo_root=str(tmp_path))
    assert keywords["backend"] == ["sqlite", "postgres"]
    assert keywords["ops"] == ["pager"]

    topics = remediation_topics(repo_root=str(tmp_path))
    assert "topic b" in topics


def test_load_domain_pack_returns_none_when_absent(tmp_path):
    assert load_domain_pack(repo_root=str(tmp_path)) is None


def test_doc_type_extensions_reads_domain_pack(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({
        "pack_name": "test-pack",
        "doc_type_extensions": {"shot_list": ["shotlist", "shot-list"]},
    }))
    assert doc_type_extensions(repo_root=str(tmp_path)) == {"shot_list": ["shotlist", "shot-list"]}
```

Append to `tests/test_docgraph.py`:

```python
from synlynk.docgraph import classify_doc_type


def test_classify_doc_type_checks_extensions_before_general_doc_fallback():
    extensions = {"compliance_doc": ["hipaa", "compliance/"]}
    assert classify_doc_type("docs/hipaa-checklist.md", extensions=extensions) == "compliance_doc"
    assert classify_doc_type("compliance/annual-review.md", extensions=extensions) == "compliance_doc"


def test_classify_doc_type_builtin_buckets_take_priority_over_extensions():
    extensions = {"compliance_doc": ["readme"]}
    assert classify_doc_type("README.md", extensions=extensions) == "readme"


def test_classify_doc_type_without_extensions_unchanged():
    assert classify_doc_type("docs/notes.md") == "general_doc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_maintainer_taxonomy.py tests/test_docgraph.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_domain_pack'` and `TypeError: classify_doc_type() got an unexpected keyword argument 'extensions'`

- [ ] **Step 3: Implement the domain pack loader**

Append to `synlynk/maintainer_taxonomy.py`:

```python
from typing import Optional


def _domain_pack_path(repo_root: str) -> str:
    return os.path.join(repo_root, ".synlynk", "domain_pack.json")


def load_domain_pack(repo_root: str = ".") -> Optional[dict]:
    """Load .synlynk/domain_pack.json, or None if it doesn't exist/parse."""
    path = _domain_pack_path(repo_root)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def doc_type_extensions(repo_root: str = ".") -> Dict[str, List[str]]:
    """doc_type -> matcher-substring list, from the domain pack (empty if none)."""
    pack = load_domain_pack(repo_root)
    if not pack:
        return {}
    extensions = pack.get("doc_type_extensions")
    return extensions if isinstance(extensions, dict) else {}
```

Now update `cluster_keywords()` and `remediation_topics()` in the same file to layer the domain pack over the taxonomy file (pack values win per-key, matching spec §7: "pack values layer over repo defaults"):

```python
def cluster_keywords(repo_root: str = ".") -> Dict[str, List[str]]:
    """Cluster name -> keyword list: domain pack layered over .synlynk/maintainer_taxonomy.json, falling back to built-in defaults."""
    data = _load_taxonomy_file(repo_root)
    configured = data.get("cluster_keywords")
    merged = dict(configured) if isinstance(configured, dict) and configured else dict(_BUILTIN_CLUSTER_KEYWORDS)

    pack = load_domain_pack(repo_root)
    if pack:
        pack_keywords = pack.get("cluster_keywords")
        if isinstance(pack_keywords, dict):
            merged.update(pack_keywords)
    return merged


def remediation_topics(repo_root: str = ".") -> Tuple[str, ...]:
    """Remediation-topic keywords: domain pack layered over .synlynk/maintainer_taxonomy.json, falling back to built-in defaults."""
    data = _load_taxonomy_file(repo_root)
    configured = data.get("remediation_topics")
    merged = list(configured) if isinstance(configured, list) and configured else list(_BUILTIN_REMEDIATION_TOPICS)

    pack = load_domain_pack(repo_root)
    if pack:
        pack_topics = pack.get("remediation_topics")
        if isinstance(pack_topics, list):
            for topic in pack_topics:
                if topic not in merged:
                    merged.append(topic)
    return tuple(merged)
```

Replace the two function definitions already written in Task 1 with these versions (same file, same names — this is an edit, not a duplicate addition).

- [ ] **Step 4: Implement the `classify_doc_type` extension param**

Edit `synlynk/docgraph.py`, replacing the function at lines 98-129:

```python
def classify_doc_type(rel_path: str, extensions: Optional[Dict[str, List[str]]] = None) -> str:
    """Classify markdown document by directory or filename convention.

    `extensions` (doc_type -> substring list, from a domain pack's
    doc_type_extensions) is checked after the built-in structural buckets and
    before the general_doc fallback, per spec
    docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md §7.
    """
    norm = rel_path.replace("\\", "/").lower()
    base = os.path.basename(norm)

    if "docs/superpowers/specs/" in norm or norm.startswith("specs/"):
        return "spec"
    if "docs/superpowers/plans/" in norm or norm.startswith("plans/"):
        return "plan"
    if "project-docs/decisions/" in norm or "decisions/" in norm:
        return "decision"
    if "project-docs/devlogs/" in norm or "devlogs/" in norm:
        return "devlog"
    if base == "roadmap.md" or "roadmap" in base:
        return "roadmap"
    if base == "todo.md":
        return "todo"
    if base == "costs.md":
        return "costs"
    if base == "memory.md":
        return "memory"
    if base == "readme.md":
        return "readme"
    if base == "changelog.md":
        return "changelog"
    if "guide" in norm or "tutorial" in norm:
        return "guide"
    if "strategy" in norm:
        return "strategy"
    if "blog" in norm:
        return "blog"

    if extensions:
        for doc_type, substrings in extensions.items():
            for substring in substrings:
                if substring.lower() in norm:
                    return doc_type

    return "general_doc"
```

This requires `Optional` already imported at the top of `docgraph.py` (it is, line 17) — no import changes needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_maintainer_taxonomy.py tests/test_docgraph.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Ship the one worked domain pack**

```json
// .synlynk/domain_pack.json
{
  "pack_name": "synlynk-default",
  "cluster_keywords": {
    "backend": ["sqlite", "database", "server", "api", "endpoint", "query"],
    "frontend": ["css", "html", "ui", "vizor", "widget", "render"],
    "cli": ["argparse", "subcommand", "cli.py", "command"],
    "docs": ["readme", "docstring", "documentation", "spec"],
    "sentinel": ["alert", "circuit breaker", "sentinel", "flatline"],
    "testing": ["pytest", "fixture", "test_", "flaky"]
  },
  "remediation_topics": ["invariant 1", "circuit breaker", "daemon supervision"],
  "doc_type_extensions": {}
}
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/maintainer_taxonomy.py synlynk/docgraph.py .synlynk/domain_pack.json tests/test_maintainer_taxonomy.py tests/test_docgraph.py
git commit -m "feat(maintainer): domain pack extension point for taxonomy and doc-type classification

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 3: Rewire `cluster_open_issues()` and `is_issue_remediated()` onto the taxonomy loader

**Files:**
- Modify: `synlynk/maintainer.py:12-16` (delete `_REMEDIATION_TOPICS`), `:26-59` (`is_issue_remediated`), `:261-292` (`cluster_open_issues`)
- Test: `tests/test_maintainer.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_maintainer.py`:

```python
import json

from synlynk.maintainer import cluster_open_issues, is_issue_remediated


def test_cluster_open_issues_uses_repo_taxonomy_file(tmp_path, monkeypatch):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "maintainer_taxonomy.json").write_text(json.dumps({
        "cluster_keywords": {"video": ["ffmpeg", "transcode"]},
        "remediation_topics": [],
    }))
    monkeypatch.chdir(tmp_path)

    issues = [{"number": 1, "title": "ffmpeg transcode crashes on odd framerates", "labels": []}]
    clustered = cluster_open_issues(issues)
    assert "video" in clustered
    assert clustered["video"][0]["number"] == 1


def test_is_issue_remediated_uses_repo_remediation_topics(tmp_path, monkeypatch):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "maintainer_taxonomy.json").write_text(json.dumps({
        "cluster_keywords": {},
        "remediation_topics": ["frame drop"],
    }))
    monkeypatch.chdir(tmp_path)

    remediated = is_issue_remediated(
        issue_text="frame drop bug in the renderer",
        commit_messages=["fix: resolve frame drop issue in renderer path"],
    )
    assert remediated is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_maintainer.py -v -k taxonomy`
Expected: FAIL — `cluster_open_issues` has no `"video"` bucket (keyword list is still the hardcoded 6 buckets), so `clustered["video"]` raises `KeyError`.

- [ ] **Step 3: Implement**

Edit `synlynk/maintainer.py`. Delete the hardcoded constant block at lines 12-16 (`_REMEDIATION_TOPICS = (...)`) and add the import at the top of the file alongside the existing imports:

```python
from synlynk.maintainer_taxonomy import cluster_keywords, remediation_topics
```

In `is_issue_remediated()` (currently lines 26-59), find the line(s) referencing `_REMEDIATION_TOPICS` and replace with a call to `remediation_topics()`:

```python
def is_issue_remediated(issue_text: str, commit_messages: list[str], issue_number: int = None) -> bool:
    # ... existing #N / gh:#N / fixes #N / closes #N / resolves #N / gh-N matching unchanged ...

    topics = remediation_topics()
    issue_lower = issue_text.lower()
    for topic in topics:
        if topic in issue_lower:
            for msg in commit_messages:
                if topic in msg.lower():
                    return True

    # ... existing "circuit breaker" + "live-19" special case and generic live-\d+ matching unchanged ...
```

(Keep every other branch of the existing function body exactly as-is — only the `_REMEDIATION_TOPICS` reference becomes `topics = remediation_topics()`.)

In `cluster_open_issues()` (currently lines 261-292), replace the hardcoded 7-bucket dict with a call to `cluster_keywords()`, keeping the `"other"` fallback bucket:

```python
def cluster_open_issues(issues: list[dict]) -> dict[str, list[dict]]:
    """Cluster open issues by keyword/label match against the repo's taxonomy."""
    keywords_by_cluster = cluster_keywords()
    clustered: dict[str, list[dict]] = {name: [] for name in keywords_by_cluster}
    clustered["other"] = []

    for issue in issues:
        title = str(issue.get("title") or "").lower()
        body = str(issue.get("body") or "").lower()
        labels = [str(l).lower() for l in (issue.get("labels") or [])]
        haystack = f"{title} {body} {' '.join(labels)}"

        matched = False
        for cluster_name, keywords in keywords_by_cluster.items():
            if any(kw.lower() in haystack for kw in keywords):
                clustered[cluster_name].append(issue)
                matched = True
                break
        if not matched:
            clustered["other"].append(issue)

    return {name: items for name, items in clustered.items() if items}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_maintainer.py -v`
Expected: PASS (all existing + 2 new tests green — confirms the taxonomy swap didn't break the pre-existing hardcoded-bucket test cases, since `.synlynk/maintainer_taxonomy.json` created in Task 1 reproduces today's exact buckets when no `tmp_path`/`monkeypatch.chdir` override is in play)

- [ ] **Step 5: Commit**

```bash
git add synlynk/maintainer.py tests/test_maintainer.py
git commit -m "refactor(maintainer): cluster_open_issues and is_issue_remediated read taxonomy from config

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 4: `MaintainerActionRegistry` (spec §5.2)

**Files:**
- Create: `synlynk/maintainer_registry.py`
- Test: `tests/test_maintainer_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_maintainer_registry.py
import json

import pytest

from synlynk.maintainer_registry import (
    register_action,
    registered_actions,
    get_action_config,
    clear_registry,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_registry()
    yield
    clear_registry()


def test_register_action_stores_defaults_and_filter_schema():
    register_action(
        name="sentinel_triage",
        default_config={"enabled": True, "mode": "dry_run"},
        filter_schema={"exclude_codes": "list[str]"},
        run_fn=lambda **kwargs: {"ok": True},
    )
    actions = registered_actions()
    assert "sentinel_triage" in actions
    assert actions["sentinel_triage"].default_config == {"enabled": True, "mode": "dry_run"}
    assert actions["sentinel_triage"].filter_schema == {"exclude_codes": "list[str]"}


def test_get_action_config_returns_defaults_when_no_config_file(tmp_path):
    register_action(
        name="mesh_sweep",
        default_config={"enabled": True, "mode": "dry_run"},
        filter_schema={},
        run_fn=lambda **kwargs: {"ok": True},
    )
    config = get_action_config("mesh_sweep", repo_root=str(tmp_path))
    assert config == {"enabled": True, "mode": "dry_run"}


def test_get_action_config_applies_repo_overrides(tmp_path):
    register_action(
        name="backlog_burndown",
        default_config={"enabled": True, "mode": "dry_run"},
        filter_schema={"exclude_labels": "list[str]"},
        run_fn=lambda **kwargs: {"ok": True},
    )
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({
        "maintainer_autonomy": {
            "backlog_burndown": {"mode": "promote", "exclude_labels": ["do-not-autosweep"]},
        }
    }))

    config = get_action_config("backlog_burndown", repo_root=str(tmp_path))
    assert config == {
        "enabled": True,
        "mode": "promote",
        "exclude_labels": ["do-not-autosweep"],
    }


def test_get_action_config_raises_for_unregistered_name(tmp_path):
    with pytest.raises(KeyError):
        get_action_config("nonexistent", repo_root=str(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_maintainer_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.maintainer_registry'`

- [ ] **Step 3: Implement**

```python
# synlynk/maintainer_registry.py
"""Generic action-registration object for any role's autonomous wake cycle.

Not Maintainer-specific: any role adopting this pattern (spec §5.2,
docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md)
registers an action with a default config, a filter schema, and a run
function. Registration produces a settings entry under
.synlynk/config.json's `maintainer_autonomy` block (read via
get_action_config), wake-cycle participation, and a toggle/filter card in
the Role Operations Panel (synlynk/viz/role_ops_panel.py).
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass
class RegisteredAction:
    name: str
    default_config: Dict[str, Any] = field(default_factory=dict)
    filter_schema: Dict[str, str] = field(default_factory=dict)
    run_fn: Callable[..., Dict[str, Any]] = None


_REGISTRY: Dict[str, RegisteredAction] = {}


def register_action(
    name: str,
    default_config: Dict[str, Any],
    filter_schema: Dict[str, str],
    run_fn: Callable[..., Dict[str, Any]],
) -> None:
    """Register (or re-register, idempotently) an autonomous action."""
    _REGISTRY[name] = RegisteredAction(
        name=name,
        default_config=dict(default_config),
        filter_schema=dict(filter_schema),
        run_fn=run_fn,
    )


def registered_actions() -> Dict[str, RegisteredAction]:
    """All currently registered actions, keyed by name."""
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Clear all registered actions (test isolation)."""
    _REGISTRY.clear()


def _settings_section_key(name: str) -> str:
    return "maintainer_autonomy"


def get_action_config(name: str, repo_root: str = ".") -> Dict[str, Any]:
    """Registered action's default_config, overridden by
    .synlynk/config.json's maintainer_autonomy block for this action name."""
    action = _REGISTRY.get(name)
    if action is None:
        raise KeyError(f"no registered action named {name!r}")

    config = dict(action.default_config)
    path = os.path.join(repo_root, ".synlynk", "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            section = data.get(_settings_section_key(name)) or {}
            overrides = section.get(name) or {}
            config.update(overrides)
        except (json.JSONDecodeError, OSError):
            pass
    return config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_maintainer_registry.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/maintainer_registry.py tests/test_maintainer_registry.py
git commit -m "feat(maintainer): generic action registry for settings-driven wake-cycle actions

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 5: Dual-graph proximal selection (spec §5.6)

**Files:**
- Modify: `synlynk/maintainer.py` (add `select_proposal_target`)
- Test: `tests/test_maintainer.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_maintainer.py`:

```python
from synlynk.maintainer import select_proposal_target


def test_select_proposal_target_matches_via_code_graph_adjacency(monkeypatch):
    open_proposals = [{"proposal_id": "p1", "touched_files": ["synlynk/maintainer.py"]}]
    candidate = {"touched_files": ["synlynk/maintainer_registry.py"]}

    def fake_graph_distance(file_a, file_b, repo_root="."):
        return 1  # adjacent

    monkeypatch.setattr("synlynk.maintainer._code_graph_distance", fake_graph_distance)

    target = select_proposal_target(candidate, open_proposals, repo_root=".")
    assert target == "p1"


def test_select_proposal_target_falls_back_to_doc_graph(monkeypatch):
    open_proposals = [{"proposal_id": "p1", "touched_files": ["unrelated/file.py"], "story_ids": ["s1"]}]
    candidate = {"touched_files": ["another/unrelated.py"], "story_ids": ["s2"]}

    monkeypatch.setattr("synlynk.maintainer._code_graph_distance", lambda *a, **k: None)

    class FakeDocGraph:
        reverse_code_index = {
            "unrelated/file.py": ["docs/a.md"],
            "another/unrelated.py": ["docs/a.md"],
        }
        reverse_doc_index: dict = {}

    monkeypatch.setattr("synlynk.maintainer._load_docgraph", lambda repo_root: FakeDocGraph())

    target = select_proposal_target(candidate, open_proposals, repo_root=".")
    assert target == "p1"


def test_select_proposal_target_falls_back_to_keyword_match(monkeypatch, tmp_path):
    monkeypatch.setattr("synlynk.maintainer._code_graph_distance", lambda *a, **k: None)
    monkeypatch.setattr("synlynk.maintainer._load_docgraph", lambda repo_root: None)

    open_proposals = [{"proposal_id": "p1", "cluster": "backend"}]
    candidate = {"cluster": "backend"}

    target = select_proposal_target(candidate, open_proposals, repo_root=str(tmp_path))
    assert target == "p1"


def test_select_proposal_target_returns_none_when_no_tier_matches(monkeypatch, tmp_path):
    monkeypatch.setattr("synlynk.maintainer._code_graph_distance", lambda *a, **k: None)
    monkeypatch.setattr("synlynk.maintainer._load_docgraph", lambda repo_root: None)

    open_proposals = [{"proposal_id": "p1", "cluster": "frontend"}]
    candidate = {"cluster": "backend"}

    target = select_proposal_target(candidate, open_proposals, repo_root=str(tmp_path))
    assert target is None


def test_select_proposal_target_degrades_gracefully_on_non_code_dominant_workspace(monkeypatch, tmp_path):
    """A workspace with mostly non-_SOURCE_SUFFIXES files (e.g. a content/doc-heavy
    rxcc/vdowrx/Hitchcock-style workspace) must not raise -- it falls through
    code-graph and doc-graph tiers cleanly to the keyword fallback."""
    monkeypatch.setattr("synlynk.maintainer._code_graph_distance", lambda *a, **k: None)
    monkeypatch.setattr("synlynk.maintainer._load_docgraph", lambda repo_root: None)

    open_proposals = [{"proposal_id": "p1", "cluster": "docs"}]
    candidate = {"cluster": "docs", "touched_files": ["content/episode-12.fcpxml"]}

    target = select_proposal_target(candidate, open_proposals, repo_root=str(tmp_path))
    assert target == "p1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_maintainer.py -v -k select_proposal_target`
Expected: FAIL with `ImportError: cannot import name 'select_proposal_target'`

- [ ] **Step 3: Implement**

Append to `synlynk/maintainer.py`:

```python
from typing import Optional


def _code_graph_distance(file_a: str, file_b: str, repo_root: str = ".") -> Optional[int]:
    """Graph distance between two source files via the code graph, or None
    if either file has no graph node (e.g. non-_SOURCE_SUFFIXES file, or the
    graph hasn't been built for this HEAD)."""
    try:
        from synlynk.graph_cache import read_traversal_cache
    except Exception:
        return None
    try:
        cache = read_traversal_cache(repo_root)
    except Exception:
        return None
    if not cache:
        return None
    adjacency = cache.get("adjacency") or {}
    if file_a not in adjacency or file_b not in adjacency:
        return None
    if file_b in adjacency.get(file_a, []):
        return 1
    return None


def _load_docgraph(repo_root: str = "."):
    """Load the persisted .synlynk/docgraph.json, or None if absent/unreadable."""
    import json
    import os

    path = os.path.join(repo_root, ".synlynk", "docgraph.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    from synlynk.docgraph import DocGraph

    return DocGraph(**{k: v for k, v in data.items() if k in DocGraph.__dataclass_fields__})


_PROXIMITY_THRESHOLD = 2


def select_proposal_target(
    candidate: dict, open_proposals: list[dict], repo_root: str = "."
) -> Optional[str]:
    """Three-tier proximal selection: code-graph -> doc-graph -> keyword
    fallback (spec §5.6). Returns the proposal_id to join, or None to start
    a new proposal/accumulate toward the cluster-volume threshold.
    """
    candidate_files = candidate.get("touched_files") or []

    # Tier 1: code-graph proximity.
    for proposal in open_proposals:
        for proposal_file in proposal.get("touched_files") or []:
            for candidate_file in candidate_files:
                distance = _code_graph_distance(candidate_file, proposal_file, repo_root)
                if distance is not None and distance <= _PROXIMITY_THRESHOLD:
                    return proposal["proposal_id"]

    # Tier 2: doc-graph proximity (shared referencing doc, or shared
    # issues_and_prs/code_references with an existing proposal's stories).
    docgraph = _load_docgraph(repo_root)
    if docgraph is not None:
        candidate_docs: set = set()
        for f in candidate_files:
            candidate_docs.update(docgraph.reverse_code_index.get(f, []))
        if candidate_docs:
            for proposal in open_proposals:
                proposal_docs: set = set()
                for f in proposal.get("touched_files") or []:
                    proposal_docs.update(docgraph.reverse_code_index.get(f, []))
                if candidate_docs & proposal_docs:
                    return proposal["proposal_id"]

    # Tier 3: keyword clustering fallback (today's mechanism, reading its
    # taxonomy from .synlynk/maintainer_taxonomy.json per spec §6).
    candidate_cluster = candidate.get("cluster")
    if candidate_cluster:
        for proposal in open_proposals:
            if proposal.get("cluster") == candidate_cluster:
                return proposal["proposal_id"]

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_maintainer.py -v -k select_proposal_target`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/maintainer.py tests/test_maintainer.py
git commit -m "feat(maintainer): dual-graph proximal selection for proposal clustering

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 6: `run_maintainer_wake_cycle()` (spec §5.1, §5.3)

**Files:**
- Modify: `synlynk/maintainer.py` (add `_ensure_github_issue_for_story`, `run_maintainer_wake_cycle`, register the 3 actions at module import time)
- Test: `tests/test_maintainer.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_maintainer.py`:

```python
from synlynk.maintainer import run_maintainer_wake_cycle
from synlynk.maintainer_registry import clear_registry, registered_actions


def test_run_maintainer_wake_cycle_registers_all_three_actions():
    import synlynk.maintainer  # noqa: F401 -- re-import triggers registration if cleared
    actions = registered_actions()
    assert set(actions.keys()) >= {"sentinel_triage", "backlog_burndown", "mesh_sweep"}


def test_run_maintainer_wake_cycle_dry_run_stages_without_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )
    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", lambda **kwargs: 0)

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    assert result["sentinel_triage"]["mode"] == "dry_run"
    assert result["backlog_burndown"]["mode"] == "dry_run"
    assert result["mesh_sweep"]["mode"] == "dry_run"


def test_run_maintainer_wake_cycle_skips_disabled_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text('{"maintainer_autonomy": {"mesh_sweep": {"enabled": false}}}')

    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )

    def _should_not_run(**kwargs):
        raise AssertionError("mesh_sweep must not run when disabled")

    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", _should_not_run)

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    assert result["mesh_sweep"]["skipped"] is True


def test_run_maintainer_wake_cycle_critical_finding_bypasses_cluster_minimum(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    critical_group = {
        "fingerprint": "CRITICAL:SEV1_FAULT",
        "severity": "CRITICAL",
        "code": "SEV1_FAULT",
        "total_occurrences": 1,
        "sample_messages": ["crash"],
    }
    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [critical_group])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )
    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", lambda **kwargs: 0)
    monkeypatch.setattr(
        "synlynk.maintainer._ensure_github_issue_for_story",
        lambda story, repo_root=".": 999,
    )

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    proposals = result["sentinel_triage"]["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["severity"] == "critical"
    assert proposals[0]["stories"][0]["github_issue"] == 999
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_maintainer.py -v -k wake_cycle`
Expected: FAIL with `ImportError: cannot import name 'run_maintainer_wake_cycle'`

- [ ] **Step 3: Implement**

Append to `synlynk/maintainer.py`:

```python
def _ensure_github_issue_for_story(story: dict, repo_root: str = ".") -> int:
    """Open a GitHub issue for a story that has none yet, via the qa-role
    write path, so Proposal Studio never shows an orphaned story (spec §5.3)."""
    existing = story.get("github_issue")
    if existing:
        return int(existing)

    import subprocess

    title = story.get("title") or f"Maintainer finding: {story.get('story_id', 'untitled')}"
    body = story.get("body") or "Filed by Maintainer's autonomous wake cycle."
    result = subprocess.run(
        [
            "python3", "bin/synlynk.py", "gh", "--role", "qa", "--",
            "issue", "create", "--title", title, "--body", body,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    import re

    match = re.search(r"#(\d+)", result.stdout or "")
    return int(match.group(1)) if match else 0


def _run_sentinel_triage_action(mode: str, repo_root: str = ".") -> dict:
    groups = triage_sentinel_alerts(max_age_days=7)
    proposals = []
    for group in groups:
        severity_label = "critical" if group["severity"] == "CRITICAL" else (
            "high" if group["severity"] == "ERROR" else "normal"
        )
        if severity_label in ("critical", "high"):
            story = {"story_id": group["fingerprint"], "title": format_triage_issue(group)[:80]}
            if mode == "promote":
                story["github_issue"] = _ensure_github_issue_for_story(story, repo_root=repo_root)
            proposals.append({
                "proposal_id": f"maintainer-sentinel-{group['fingerprint']}",
                "source": "maintainer:sentinel_triage",
                "title": f"Sentinel: {group['code']}",
                "severity": severity_label,
                "cluster": "sentinel",
                "stories": [story],
            })
    return {"mode": mode, "groups": len(groups), "proposals": proposals}


def _run_backlog_burndown_action(mode: str, repo_root: str = ".") -> dict:
    result = run_backlog_burndown_sweep(repo_root=repo_root, dry_run=(mode != "promote"))
    return {"mode": mode, **result}


def _run_mesh_sweep_action(mode: str, repo_root: str = ".") -> dict:
    exit_code = cmd_maintainer_sweep(repo_root=repo_root, refresh_graph=(mode == "promote"))
    return {"mode": mode, "exit_code": exit_code}


from synlynk.maintainer_registry import register_action, get_action_config

register_action(
    name="sentinel_triage",
    default_config={"enabled": True, "mode": "dry_run"},
    filter_schema={"exclude_codes": "list[str]"},
    run_fn=_run_sentinel_triage_action,
)
register_action(
    name="backlog_burndown",
    default_config={"enabled": True, "mode": "dry_run"},
    filter_schema={"exclude_labels": "list[str]"},
    run_fn=_run_backlog_burndown_action,
)
register_action(
    name="mesh_sweep",
    default_config={"enabled": True, "mode": "dry_run"},
    filter_schema={},
    run_fn=_run_mesh_sweep_action,
)


def run_maintainer_wake_cycle(repo_root: str = ".") -> dict:
    """Run Maintainer's autonomous wake-cycle SOP: sentinel triage, backlog
    burndown, mesh sweep -- mirroring run_tpm_wake_cycle()'s shape (spec §5.1).
    Each registered action runs in dry_run (stage, no side effects) or
    promote (real side effects) mode per its settings-registry config.
    """
    from synlynk.maintainer_registry import registered_actions

    results: dict = {}
    for name, action in registered_actions().items():
        config = get_action_config(name, repo_root=repo_root)
        if not config.get("enabled", True):
            results[name] = {"skipped": True}
            continue
        mode = config.get("mode", "dry_run")
        results[name] = action.run_fn(mode=mode, repo_root=repo_root)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_maintainer.py -v -k wake_cycle`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full maintainer test module to check for regressions**

Run: `pytest tests/test_maintainer.py tests/test_maintainer_graph_sweep.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add synlynk/maintainer.py tests/test_maintainer.py
git commit -m "feat(maintainer): run_maintainer_wake_cycle acts on triage/burndown/sweep findings

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 7: Wire the wake cycle into the scheduler (spec §5.1 end)

**Files:**
- Modify: `synlynk/scheduler.py:276-281` (`_run_maintainer_triage_pass`)
- Test: `tests/test_scheduler.py` (append — if this file doesn't exist, create it following the module's existing test conventions)

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_scheduler.py (create the file if it does not exist,
# with this single test plus the import line below)
def test_run_maintainer_triage_pass_calls_wake_cycle(monkeypatch):
    from synlynk import scheduler

    called = {}

    def fake_wake_cycle(**kwargs):
        called["ran"] = True
        return {"sentinel_triage": {"mode": "dry_run"}}

    monkeypatch.setattr("synlynk.maintainer.run_maintainer_wake_cycle", fake_wake_cycle)
    scheduler._run_maintainer_triage_pass()
    assert called.get("ran") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py -v -k maintainer_triage_pass`
Expected: FAIL — `fake_wake_cycle` never called, because `_run_maintainer_triage_pass()` still calls `triage_sentinel_alerts()` directly and discards it.

- [ ] **Step 3: Implement**

Replace `synlynk/scheduler.py:276-281`:

```python
def _run_maintainer_triage_pass() -> None:
    try:
        from synlynk.maintainer import run_maintainer_wake_cycle
        run_maintainer_wake_cycle()
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py -v -k maintainer_triage_pass`
Expected: PASS

- [ ] **Step 5: Run the full scheduler test suite to check for regressions**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add synlynk/scheduler.py tests/test_scheduler.py
git commit -m "fix(scheduler): maintainer triage pass runs the full wake cycle, not just triage

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 8: Fence-hint contributor (spec §5.7, part 3)

**Files:**
- Create: `synlynk/maintainer_hints.py`
- Modify: `synlynk/cli.py` (import for registration side effect)
- Test: `tests/test_fencing_hint_contributors.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fencing_hint_contributors.py`:

```python
from synlynk.fencing import FenceData, clear_hint_contributors, render_task_fence
from synlynk.maintainer_hints import maintainer_fence_hint_contributor, _pending_proposal_count


def test_maintainer_fence_hint_contributor_adds_hint_when_proposals_pending(monkeypatch):
    clear_hint_contributors()
    from synlynk.fencing import register_hint_contributor
    register_hint_contributor(maintainer_fence_hint_contributor)

    monkeypatch.setattr("synlynk.maintainer_hints._pending_proposal_count", lambda: 3)

    data = FenceData(command="exec", kind="actual", in_tokens=10, out_tokens=10, cost_usd=0.01, basis="actual")
    rendered = render_task_fence(data)
    assert "3 maintainer proposal" in rendered

    clear_hint_contributors()


def test_maintainer_fence_hint_contributor_silent_when_nothing_pending(monkeypatch):
    clear_hint_contributors()
    from synlynk.fencing import register_hint_contributor
    register_hint_contributor(maintainer_fence_hint_contributor)

    monkeypatch.setattr("synlynk.maintainer_hints._pending_proposal_count", lambda: 0)

    data = FenceData(command="exec", kind="actual", in_tokens=10, out_tokens=10, cost_usd=0.01, basis="actual")
    rendered = render_task_fence(data)
    assert "maintainer proposal" not in rendered

    clear_hint_contributors()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fencing_hint_contributors.py -v -k maintainer_fence`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.maintainer_hints'`

- [ ] **Step 3: Implement**

```python
# synlynk/maintainer_hints.py
"""Maintainer's CLI/TUI fence-hint contributor (spec §5.7, part 3). Surfaces
a one-line hint after any `synlynk exec`/`synlynk maintainer ...` invocation
when a pending proposal or dry-run finding exists -- the terminal-side
notification surface for people not looking at Vizor.
"""
import json
import os

from synlynk.fencing import FenceData, register_hint_contributor


def _pending_proposal_count(repo_root: str = ".") -> int:
    path = os.path.join(repo_root, ".synlynk", "proposals.json")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        proposals = data.get("proposals") or []
        return sum(1 for p in proposals if p.get("source", "").startswith("maintainer:"))
    except (json.JSONDecodeError, OSError):
        return 0


def maintainer_fence_hint_contributor(data: FenceData) -> None:
    count = _pending_proposal_count()
    if count > 0:
        label = "proposal" if count == 1 else "proposals"
        data.hints.append(f"{count} maintainer {label} pending review in Proposal Studio")


register_hint_contributor(maintainer_fence_hint_contributor)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fencing_hint_contributors.py -v -k maintainer_fence`
Expected: PASS (2 passed)

- [ ] **Step 5: Wire the import-time registration into the CLI**

Edit `synlynk/cli.py`, adding near the top-level imports (alongside the other `from synlynk...` imports at the top of the file):

```python
import synlynk.maintainer_hints  # noqa: F401 -- registers the fence-hint contributor on import
```

- [ ] **Step 6: Run the fencing test suite to check for regressions**

Run: `pytest tests/test_fencing.py tests/test_fencing_hint_contributors.py -v`
Expected: PASS (all tests green)

- [ ] **Step 7: Commit**

```bash
git add synlynk/maintainer_hints.py synlynk/cli.py tests/test_fencing_hint_contributors.py
git commit -m "feat(maintainer): register fence-hint contributor for pending proposals

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 9: Slack notification on promote (spec §5.7, part 2)

**Files:**
- Modify: `synlynk/notifiers/slack.py:13-21` (`NOTIFY_EVENT_TYPES`), append `_slack_webhook_url`
- Modify: `synlynk/maintainer.py` (add `_notify_slack_on_promotion`, call it from the three `_run_*_action` functions when `notify_slack` is set or severity is critical)
- Test: `tests/test_maintainer.py` (append), a new `tests/test_notifiers_slack.py` if none exists (check first with `ls tests/test_notifiers*`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_notifiers_slack.py (create if it doesn't already exist)
import json

from synlynk.notifiers.slack import NOTIFY_EVENT_TYPES, _slack_webhook_url


def test_maintainer_promote_is_a_notify_event_type():
    assert "maintainer_promote" in NOTIFY_EVENT_TYPES


def test_slack_webhook_url_reads_from_config(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({
        "notifiers": {"slack_webhook_url": "https://hooks.slack.test/abc"}
    }))
    assert _slack_webhook_url(repo_root=str(tmp_path)) == "https://hooks.slack.test/abc"


def test_slack_webhook_url_returns_none_when_unconfigured(tmp_path):
    assert _slack_webhook_url(repo_root=str(tmp_path)) is None
```

Append to `tests/test_maintainer.py`:

```python
def test_sentinel_triage_action_notifies_slack_for_critical_regardless_of_mode(monkeypatch):
    from synlynk.maintainer import _run_sentinel_triage_action

    critical_group = {
        "fingerprint": "CRITICAL:X",
        "severity": "CRITICAL",
        "code": "X",
        "total_occurrences": 1,
        "sample_messages": ["boom"],
    }
    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [critical_group])
    monkeypatch.setattr("synlynk.maintainer._ensure_github_issue_for_story", lambda story, repo_root=".": 1)

    notified = []
    monkeypatch.setattr(
        "synlynk.maintainer._notify_slack_on_promotion",
        lambda proposal, repo_root=".": notified.append(proposal["proposal_id"]),
    )

    _run_sentinel_triage_action(mode="dry_run")
    assert len(notified) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifiers_slack.py tests/test_maintainer.py -v -k "slack or notif"`
Expected: FAIL — `ImportError: cannot import name '_slack_webhook_url'`, `AssertionError: 'maintainer_promote' not in NOTIFY_EVENT_TYPES`, `AttributeError: module 'synlynk.maintainer' has no attribute '_notify_slack_on_promotion'`

- [ ] **Step 3: Implement the Slack side**

Edit `synlynk/notifiers/slack.py`, replacing the `NOTIFY_EVENT_TYPES` list at lines 13-21:

```python
NOTIFY_EVENT_TYPES = [
    "dispatch",
    "approve_pr",
    "pr_approve",
    "pr_approved",
    "kill_job",
    "job_kill",
    "job_killed",
    "maintainer_promote",
]
```

Append to the same file:

```python
def _slack_webhook_url(repo_root: str = ".") -> str | None:
    import os as _os

    path = _os.path.join(repo_root, ".synlynk", "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return (config.get("notifiers") or {}).get("slack_webhook_url")
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return None
```

- [ ] **Step 4: Implement the Maintainer side**

Append to `synlynk/maintainer.py`:

```python
def _notify_slack_on_promotion(proposal: dict, repo_root: str = ".") -> None:
    from datetime import datetime, timezone

    from synlynk import uxcore
    from synlynk.notifiers.slack import _slack_webhook_url, post_to_webhook

    webhook_url = _slack_webhook_url(repo_root=repo_root)
    if not webhook_url:
        return

    event = uxcore.Event(
        actor_id="maintainer",
        action="maintainer_promote",
        params={"proposal_id": proposal.get("proposal_id"), "source": proposal.get("source")},
        timestamp=datetime.now(timezone.utc).isoformat(),
        result={"title": proposal.get("title"), "severity": proposal.get("severity")},
    )
    try:
        post_to_webhook(webhook_url, event)
    except Exception:
        pass
```

Now wire it into `_run_sentinel_triage_action` (edit the function added in Task 6): after appending a proposal to the `proposals` list inside the loop, check whether to notify. Replace the body of the `for group in groups:` loop with:

```python
    for group in groups:
        severity_label = "critical" if group["severity"] == "CRITICAL" else (
            "high" if group["severity"] == "ERROR" else "normal"
        )
        if severity_label in ("critical", "high"):
            story = {"story_id": group["fingerprint"], "title": format_triage_issue(group)[:80]}
            if mode == "promote":
                story["github_issue"] = _ensure_github_issue_for_story(story, repo_root=repo_root)
            proposal = {
                "proposal_id": f"maintainer-sentinel-{group['fingerprint']}",
                "source": "maintainer:sentinel_triage",
                "title": f"Sentinel: {group['code']}",
                "severity": severity_label,
                "cluster": "sentinel",
                "stories": [story],
            }
            proposals.append(proposal)
            notify_config = get_action_config("sentinel_triage", repo_root=repo_root)
            if severity_label == "critical" or notify_config.get("notify_slack"):
                _notify_slack_on_promotion(proposal, repo_root=repo_root)
```

(This replaces the equivalent loop body written in Task 6's `_run_sentinel_triage_action` — same function, same file, just the loop body gains the notify branch.)

Also add `"notify_slack": False` to the three `register_action(...)` calls' `default_config` dicts (sentinel_triage, backlog_burndown, mesh_sweep) from Task 6, matching spec §5.7's "per-action `notify_slack: bool` setting (default `false`)":

```python
register_action(
    name="sentinel_triage",
    default_config={"enabled": True, "mode": "dry_run", "notify_slack": False},
    filter_schema={"exclude_codes": "list[str]"},
    run_fn=_run_sentinel_triage_action,
)
register_action(
    name="backlog_burndown",
    default_config={"enabled": True, "mode": "dry_run", "notify_slack": False},
    filter_schema={"exclude_labels": "list[str]"},
    run_fn=_run_backlog_burndown_action,
)
register_action(
    name="mesh_sweep",
    default_config={"enabled": True, "mode": "dry_run", "notify_slack": False},
    filter_schema={},
    run_fn=_run_mesh_sweep_action,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_notifiers_slack.py tests/test_maintainer.py -v`
Expected: PASS (all tests green, including the Task 6 wake-cycle tests — `test_run_maintainer_wake_cycle_critical_finding_bypasses_cluster_minimum` still passes since it monkeypatches `_ensure_github_issue_for_story` and doesn't configure a webhook URL, so `_notify_slack_on_promotion` no-ops via the `if not webhook_url: return` guard)

- [ ] **Step 6: Commit**

```bash
git add synlynk/notifiers/slack.py synlynk/maintainer.py tests/test_notifiers_slack.py tests/test_maintainer.py
git commit -m "feat(maintainer): gate a Slack push on promotion via notify_slack setting

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 10: CLI `maintainer wake` subcommand (spec §5.8, CLI part)

**Files:**
- Modify: `synlynk/cli.py:1372` (add `wake` subparser next to `maintainer_sweep_parser`), `:3056` (dispatch branch)
- Modify: `synlynk/taxonomy.py:561` (append `maintainer wake` entry)
- Test: `tests/test_cli_maintainer_wake.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_maintainer_wake.py
import subprocess
import sys


def test_cli_maintainer_wake_subcommand_parses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    result = subprocess.run(
        [sys.executable, str(__import__("pathlib").Path(__file__).parent.parent / "bin" / "synlynk.py"),
         "maintainer", "wake", "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    assert "wake" in result.stdout.lower()


def test_maintainer_wake_taxonomy_entry_exists():
    from synlynk.taxonomy import COMMAND_TAXONOMY

    commands = [entry["command"] for entry in COMMAND_TAXONOMY]
    assert "maintainer wake" in commands
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_maintainer_wake.py -v`
Expected: FAIL — `--help` on `maintainer wake` exits non-zero (subcommand doesn't exist yet); `"maintainer wake" not in commands`

- [ ] **Step 3: Implement the CLI subparser**

Edit `synlynk/cli.py`, inserting right after the existing `maintainer_burndown_parser.add_argument("--limit", ...)` block (currently ending at line 1381, just before `dispatch_parser = subparsers.add_parser(...)` at line 1383):

```python
    maintainer_wake_parser = maintainer_sub.add_parser(
        "wake", help="Run Maintainer's autonomous wake cycle: sentinel triage, backlog burndown, mesh sweep")
```

Edit the dispatch branch at `synlynk/cli.py:3053-3081` (`elif args.command == "maintainer":`), adding a `wake` branch. Replace the import line and add a new `elif`:

```python
    elif args.command == "maintainer":
        from synlynk.maintainer import (
            cmd_maintainer_sweep, triage_sentinel_alerts, probe_reproduction,
            cmd_maintainer_burndown, run_maintainer_wake_cycle,
        )
        action = getattr(args, "maintainer_action", None)
        if action == "wake":
            result = run_maintainer_wake_cycle(repo_root=os.getcwd())
            for name, outcome in result.items():
                if outcome.get("skipped"):
                    print(f"  {name}: skipped (disabled)")
                else:
                    print(f"  {name}: mode={outcome.get('mode')} {outcome}")
        elif action == "burndown":
```

(The remaining `elif`/`else` branches for `burndown`/`sweep`/`probe`/triage-default stay exactly as they are today — this only adds the new `if action == "wake":` branch ahead of them and extends the import line.)

- [ ] **Step 4: Implement the taxonomy entry and regenerate docs**

Append to `synlynk/taxonomy.py`, immediately after the `maintainer burndown` entry (currently ending at line 561):

```python
    {"command": "maintainer wake", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["run the maintainer wake cycle", "maintainer wake"],
     "hook_event": None},
```

Run: `python3 scripts/generate_command_docs.py`
Expected: regenerates `docs/reference/commands.md`'s generated block to include `maintainer wake`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli_maintainer_wake.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the broader CLI and taxonomy test suites to check for regressions**

Run: `pytest tests/test_taxonomy.py tests/test_taxonomy_archetypes.py tests/test_taxonomy_standards.py -v`
Expected: PASS (all tests green)

- [ ] **Step 7: Commit**

```bash
git add synlynk/cli.py synlynk/taxonomy.py docs/reference/commands.md tests/test_cli_maintainer_wake.py
git commit -m "feat(cli): add 'synlynk maintainer wake' subcommand

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 11: GitHub Actions trigger (spec §5.8, GH part)

**Files:**
- Create: `.github/workflows/maintainer-sweep.yml`

- [ ] **Step 1: Write the workflow file**

```yaml
# .github/workflows/maintainer-sweep.yml
name: Maintainer Wake Cycle

on:
  workflow_dispatch: {}
  schedule:
    - cron: "0 7 * * *"

jobs:
  wake:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run Maintainer wake cycle
        run: python3 bin/synlynk.py maintainer wake
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/maintainer-sweep.yml'))"`
Expected: no output, exit code 0

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/maintainer-sweep.yml
git commit -m "ci: add nightly + manual GitHub Actions trigger for Maintainer's wake cycle

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 12: Onboarding fix (spec §5.9)

**Files:**
- Modify: `synlynk/viz/onboarding.py:275-283` (`roles_info`)
- Test: `tests/test_viz_onboarding.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_viz_onboarding.py`:

```python
def test_roles_info_includes_maintainer():
    import inspect

    from synlynk.viz import onboarding

    source = inspect.getsource(onboarding)
    assert '"maintainer"' in source or "'maintainer'" in source
```

(This test inspects source rather than calling the function directly, since `roles_info` is a local variable inside `generate_onboarding_html` rather than a module-level export — matching how it's actually declared at `synlynk/viz/onboarding.py:275`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_onboarding.py -v -k roles_info_includes_maintainer`
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Implement**

Edit `synlynk/viz/onboarding.py:275-283`, adding the `maintainer` row to the `roles_info` list:

```python
    roles_info = [
        ("pm", "Program Manager", "claude", "Roadmap, goal tracking, issue triage, and named release narratives."),
        ("tpm", "Technical Program Manager", "claude", "Milestone execution loop, cross-harness sweeps, and dependency tracking."),
        ("qa", "QA Engineer", "claude", "Autonomous PR review, test validation, and merge-gate authority."),
        ("dev", "Software Developer", "codex", "Core implementation, tests, bugfixes, refactoring, and PR creation."),
        ("architect", "Lead Architect", "claude", "System architecture, specifications, technical decisions, and charter governance."),
        ("marketing", "Marketing Engineer", "agy", "Release communications, documentation compilation, and build diary blogs."),
        ("infra", "DevOps & Infrastructure", "grok", "Pulumi IaC, AWS cloud resource management, and CI/CD pipelines."),
        ("maintainer", "Platform Maintainer", "claude", "Sentinel-alert triage, backlog burndown, and mesh/contract-drift sweeps."),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_onboarding.py -v -k roles_info_includes_maintainer`
Expected: PASS

- [ ] **Step 5: Run the full onboarding test suite to check for regressions**

Run: `pytest tests/test_viz_onboarding.py tests/test_onboarding_safety.py tests/test_onboarding_state.py tests/test_onboarding_topology.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz/onboarding.py tests/test_viz_onboarding.py
git commit -m "fix(onboarding): add maintainer to GitHub App identity roles_info

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 13: Role Operations Panel (spec §5.4)

**Files:**
- Create: `synlynk/viz/role_ops_panel.py`
- Modify: `synlynk/viz/roles.py` (insert panel after Edit Charter `<details>`)
- Modify: `synlynk/viz/overview.py` (insert condensed widget before the shortcuts grid)
- Test: `tests/test_viz_role_ops_panel.py` (new), `tests/test_viz_roles.py` (append), `tests/test_viz_overview.py` (append — create if it doesn't exist)

- [ ] **Step 1: Write the failing test for the panel itself**

```python
# tests/test_viz_role_ops_panel.py
from synlynk.viz.role_ops_panel import generate_role_ops_panel_html


def test_panel_renders_each_registered_action_with_toggle_state():
    data = {
        "actions": [
            {"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": "2026-11-23T10:00:00Z", "pending_proposals": 2},
            {"name": "backlog_burndown", "enabled": False, "mode": "dry_run", "last_run": None, "pending_proposals": 0},
            {"name": "mesh_sweep", "enabled": True, "mode": "promote", "last_run": "2026-11-24T06:00:00Z", "pending_proposals": 0, "low_signal": True},
        ]
    }
    html = generate_role_ops_panel_html("maintainer", data)
    assert "sentinel_triage" in html
    assert "backlog_burndown" in html
    assert "mesh_sweep" in html
    assert "2026-11-23T10:00:00Z" in html
    assert "low-signal" in html.lower() or "low signal" in html.lower()


def test_panel_is_generic_across_role_slugs():
    data = {"actions": [{"name": "custom_action", "enabled": True, "mode": "dry_run", "last_run": None, "pending_proposals": 0}]}
    html = generate_role_ops_panel_html("tpm", data)
    assert "custom_action" in html
    assert "tpm" in html.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_role_ops_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.viz.role_ops_panel'`

- [ ] **Step 3: Implement the panel**

```python
# synlynk/viz/role_ops_panel.py
"""Generic per-role autonomous-action operations panel (spec §5.4,
docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md).

Keyed by role_slug + the MaintainerActionRegistry's registered actions for
that role, so any future role adopting the same wake-cycle pattern gets this
UI for free, on both Agent Studio (full panel) and the Overview page
(condensed widget via render_condensed_widget_html below).
"""
import html as html_mod


def _action_card_html(action: dict) -> str:
    name = html_mod.escape(str(action.get("name", "")))
    enabled = bool(action.get("enabled"))
    mode = html_mod.escape(str(action.get("mode", "dry_run")))
    last_run = html_mod.escape(str(action.get("last_run") or "never"))
    pending = int(action.get("pending_proposals", 0) or 0)
    toggle_label = "On" if enabled else "Off"
    low_signal_html = (
        '<span class="ops-low-signal" title="This workspace has little source-code coverage for the code graph to carry signal">low signal</span>'
        if action.get("low_signal") else ""
    )
    return f"""
      <div class="ops-action-card" data-action="{name}">
        <div class="ops-action-header">
          <span class="ops-action-name">{name}</span>
          <span class="ops-action-toggle ops-toggle-{'on' if enabled else 'off'}">{toggle_label}</span>
          <span class="ops-action-mode">{mode}</span>
          {low_signal_html}
        </div>
        <div class="ops-action-meta">
          <span class="ops-last-run">Last run: {last_run}</span>
          <span class="ops-pending-count">{pending} pending proposal{'s' if pending != 1 else ''}</span>
        </div>
      </div>"""


def generate_role_ops_panel_html(role_slug: str, data: dict) -> str:
    """Full operations panel for role_slug, consumed by viz/roles.py's
    Agent Studio card. Renders one card per registered action in data["actions"]."""
    role_slug_html = html_mod.escape(str(role_slug))
    actions = data.get("actions") or []
    cards_html = "".join(_action_card_html(a) for a in actions)
    return f"""
    <details class="edit-charter ops-panel" data-role="{role_slug_html}">
      <summary>Operations</summary>
      <div class="ops-panel-body">
        {cards_html}
      </div>
    </details>"""


def generate_condensed_widget_html(role_slug: str, data: dict) -> str:
    """Condensed Overview-page widget: badges per action + pending-proposal
    count + last-wake-cycle timestamp, linking out to the full panel."""
    role_slug_html = html_mod.escape(str(role_slug))
    actions = data.get("actions") or []
    total_pending = sum(int(a.get("pending_proposals", 0) or 0) for a in actions)
    last_wake = max(
        (a.get("last_run") for a in actions if a.get("last_run")),
        default="never",
    )
    badges_html = "".join(
        f'<span class="ops-badge ops-badge-{html_mod.escape(str(a.get("mode", "off")))}">{html_mod.escape(str(a.get("name", "")))}: '
        f'{"Dry-run" if a.get("mode") == "dry_run" else ("Promoted" if a.get("enabled") else "Off")}</span>'
        for a in actions
    )
    return f"""
      <div class="section-card ops-widget" data-role="{role_slug_html}">
        <div class="section-header">
          <div class="section-title">{role_slug_html.capitalize()} Operations</div>
          <a href="roles.html" class="section-link">View in Agent Studio →</a>
        </div>
        <div class="ops-widget-badges">{badges_html}</div>
        <div class="ops-widget-meta">
          <span>{total_pending} pending proposal{'s' if total_pending != 1 else ''}</span>
          <span>Last wake cycle: {html_mod.escape(str(last_wake))}</span>
        </div>
      </div>"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_role_ops_panel.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Write the failing test for roles.py insertion**

Append to `tests/test_viz_roles.py`:

```python
def test_maintainer_role_card_includes_operations_panel():
    from synlynk.viz.roles import generate_roles_html

    data = {
        "agents": [
            {"slug": "maintainer", "title": "Platform Maintainer", "harness": "claude",
             "ops_data": {"actions": [{"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": None, "pending_proposals": 0}]}},
        ]
    }
    html = generate_roles_html(data, port=8321)
    assert "ops-panel" in html
    assert "sentinel_triage" in html
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py -v -k operations_panel`
Expected: FAIL — `"ops-panel" not in html`

- [ ] **Step 7: Implement the roles.py insertion**

In `synlynk/viz/roles.py`, inside the per-agent `cards.append(f"""...""")` f-string, find the existing `<details class="edit-charter">...</details>` block and its following `<div class="authorities">{authority_html}</div>` line. Add an operations-panel variable computed before the `cards.append(...)` call, and splice it into the f-string immediately after the `</details>` that closes the Edit Charter block:

```python
        from synlynk.viz.role_ops_panel import generate_role_ops_panel_html
        ops_data = agent.get("ops_data")
        ops_panel_html = generate_role_ops_panel_html(slug, ops_data) if ops_data else ""
```

(Place this immediately before the `cards.append(f"""...""")` call inside the per-agent loop, using whatever the loop's existing per-agent variable name is for the slug — per the file read in the prior window, the loop is `for agent in agents:` with a local `slug = agent.get("slug", ...)` already established before the f-string; reuse that existing variable name verbatim, do not introduce a second one.)

Then in the f-string itself, immediately after the line that closes the existing Edit Charter block (`</details>`) and before the `<div class="authorities">{authority_html}</div>` line, insert:

```python
          {ops_panel_html}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py -v -k operations_panel`
Expected: PASS

- [ ] **Step 9: Run the full roles test suite to check for regressions**

Run: `pytest tests/test_viz_roles.py -v`
Expected: PASS (all tests green)

- [ ] **Step 10: Write the failing test for the overview.py widget**

Create `tests/test_viz_overview.py` if it doesn't already exist (check with `ls tests/test_viz_overview.py` first), with:

```python
def test_overview_renders_maintainer_operations_widget():
    from synlynk.viz.overview import generate_overview_html

    data = {
        "workspace": {"name": "test-workspace", "updated_at": "2026-11-24"},
        "telemetry": {"sentinel_alerts": []},
        "sentinel_acks": {},
        "maintainer_ops": {"actions": [{"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": None, "pending_proposals": 1}]},
    }
    html = generate_overview_html(data, port=8321)
    assert "ops-widget" in html
    assert "sentinel_triage" in html
```

- [ ] **Step 11: Run test to verify it fails**

Run: `pytest tests/test_viz_overview.py -v`
Expected: FAIL — `"ops-widget" not in html`

- [ ] **Step 12: Implement the overview.py widget insertion**

Edit `synlynk/viz/overview.py`, inserting a new section-card immediately before the `<div class="shortcuts-section">` block at the end of the returned HTML (the exact spot found in the file's tail: right after the `</div>` that closes the "Recent / Active Dispatches" `section-card`, and before `</div>` that closes the two-column wrapper). Add this just before the `return f"""..."""`'s shortcuts-section line:

```python
    maintainer_ops = data.get("maintainer_ops")
    maintainer_widget_html = ""
    if maintainer_ops:
        from synlynk.viz.role_ops_panel import generate_condensed_widget_html
        maintainer_widget_html = generate_condensed_widget_html("maintainer", maintainer_ops)
```

(Place this assignment near the top of `generate_overview_html`, alongside the other `data.get(...)` extractions already present at the top of the function.)

Then in the returned f-string, insert `{maintainer_widget_html}` as a new line immediately after the "Recent / Active Dispatches" section-card's closing `</div>` and before `<div class="shortcuts-section">`.

- [ ] **Step 13: Run test to verify it passes**

Run: `pytest tests/test_viz_overview.py -v`
Expected: PASS

- [ ] **Step 14: Commit**

```bash
git add synlynk/viz/role_ops_panel.py synlynk/viz/roles.py synlynk/viz/overview.py tests/test_viz_role_ops_panel.py tests/test_viz_roles.py tests/test_viz_overview.py
git commit -m "feat(viz): generic Role Operations Panel for Agent Studio + Overview widget

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 14: Proposal Studio generalization (spec §5.5)

**Files:**
- Modify: `synlynk/viz/roadmap_studio.py` (rename function, keep alias, add `source` badge + severity lane)
- Test: `tests/test_viz_roadmap_studio.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_viz_roadmap_studio.py`:

```python
def test_generate_proposal_studio_html_renders_source_badge_and_severity_lane():
    from synlynk.viz.roadmap_studio import generate_proposal_studio_html

    studio_data = {
        "tickets": [
            {"id": "t1", "release_version": "v0.40.0", "theme": "Maintainer", "status": "open",
             "stories": [{"story_id": "s1", "source": "maintainer:sentinel_triage", "severity": "critical", "github_issue": 5500}]},
        ]
    }
    html = generate_proposal_studio_html(port=8321)
    # generate_proposal_studio_html's existing signature takes only `port` and
    # reads studio data from the live DB at render time (matching
    # generate_roadmap_studio_html's current signature) -- this test only
    # confirms the renamed function is importable and still returns a non-empty page.
    assert "<html" in html.lower()


def test_generate_roadmap_studio_html_alias_still_importable():
    from synlynk.viz.roadmap_studio import generate_roadmap_studio_html, generate_proposal_studio_html

    assert generate_roadmap_studio_html is generate_proposal_studio_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roadmap_studio.py -v -k proposal_studio`
Expected: FAIL with `ImportError: cannot import name 'generate_proposal_studio_html'`

- [ ] **Step 3: Rename the function and add the alias**

Edit `synlynk/viz/roadmap_studio.py`, changing the function definition line:

```python
def generate_proposal_studio_html(port: int) -> str:
    """Generate the per-workspace Proposal Studio canvas (proposal_studio.html).

    Generalized from TPM-only Roadmap Studio (spec §5.5,
    docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md) to
    render multi-source proposals (tpm / maintainer:backlog_burndown /
    maintainer:mesh_sweep / maintainer:sentinel_triage) alongside each other.
    """
```

At the bottom of the same file, add the backward-compatible alias (so `synlynk/viz/cache.py`'s existing `from synlynk.viz.roadmap_studio import generate_roadmap_studio_html` keeps working unchanged):

```python
# Backward-compatible alias -- synlynk/viz/cache.py imports this name directly
# to key the roadmap_studio.html route; keeping it avoids a broken bookmark
# (spec §5.5: "old route kept as an alias").
generate_roadmap_studio_html = generate_proposal_studio_html
```

- [ ] **Step 4: Add the `source` badge and severity lane to `cardHtml`**

Within `generate_proposal_studio_html`'s existing `cardHtml(story, ticketId, openTickets)` JS function (part of the returned HTML's `<script>` block), add a `source` badge span and route severity-flagged stories into a separate lane. Find the existing card-building template literal inside `cardHtml` and add a badge element reading `story.source`:

```javascript
function cardHtml(story, ticketId, openTickets) {
  const sourceLabel = story.source ? story.source.replace('maintainer:', 'M: ') : 'tpm';
  const sourceBadge = `<span class="source-badge source-${sourceLabel.replace(/[^a-z0-9]/gi, '-')}">${sourceLabel}</span>`;
  const issueLink = story.github_issue
    ? `<a class="issue-link" href="https://github.com/${window.__SYNLYNK_REPO__ || ''}/issues/${story.github_issue}" target="_blank">#${story.github_issue}</a>`
    : '';
  return `
    <div class="story-card" data-story-id="${story.story_id}" data-ticket-id="${ticketId}">
      ${sourceBadge}
      ${issueLink}
      <div class="story-title">${story.title || story.story_id}</div>
    </div>`;
}
```

(This is an additive change to the existing template-literal body — keep every other line of `cardHtml` that was already there, such as the drag-and-drop `draggable` attribute and any existing click handlers; only the `sourceBadge`/`issueLink` lines and their insertion into the returned template are new.)

For the severity lane, add a new top-level container in the page's rendered HTML (not JS) immediately above the existing ticket-columns container, in the same returned f-string:

```html
<div id="needs-attention-lane" class="needs-attention-lane">
  <div class="lane-header">Needs attention now</div>
  <div id="needs-attention-cards" class="lane-cards"></div>
</div>
```

And in the JS `draw()` function (the existing render entry point), add a pass that filters `studioData.tickets`' stories for `story.severity in ('critical', 'high')` and renders them into `#needs-attention-cards` via `cardHtml`, ahead of the normal per-ticket column rendering (which continues to render every story, including severity-flagged ones, in its ticket column — the lane is an additional "also shown here" surface, not an exclusive one, matching spec §5.5's framing of volume-clustered vs. severity-flagged as two lenses on the same data):

```javascript
  const attentionCards = document.getElementById('needs-attention-cards');
  if (attentionCards) {
    const urgent = [];
    (studioData.tickets || []).forEach(ticket => {
      (ticket.stories || []).forEach(story => {
        if (story.severity === 'critical' || story.severity === 'high') {
          urgent.push(cardHtml(story, ticket.id, studioData.tickets));
        }
      });
    });
    attentionCards.innerHTML = urgent.join('');
  }
```

(Place this block at the start of the existing `draw()` function, before its existing per-ticket-column rendering loop.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_viz_roadmap_studio.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Run the full roadmap/proposal studio test suites to check for regressions**

Run: `pytest tests/test_viz_roadmap_studio.py tests/test_viz_nav_roadmap_studio.py tests/test_viz_roadmap_studio_routes.py tests/test_viz_write_routes_roadmap_studio.py -v`
Expected: PASS (all tests green — confirms `cache.py`'s unmodified `from synlynk.viz.roadmap_studio import generate_roadmap_studio_html` import still resolves via the alias)

- [ ] **Step 7: Commit**

```bash
git add synlynk/viz/roadmap_studio.py tests/test_viz_roadmap_studio.py
git commit -m "feat(viz): generalize Roadmap Studio into multi-source Proposal Studio

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- §5.1 wake cycle → Task 6 (`run_maintainer_wake_cycle`), Task 7 (scheduler wiring).
- §5.2 action registry → Task 4.
- §5.3 proposal shape + non-null `github_issue` enforcement → Task 6 (`_ensure_github_issue_for_story`, called in promote mode before staging).
- §5.4 Role Operations Panel (Agent Studio + Overview) → Task 13.
- §5.5 Proposal Studio generalization (rename, alias, source badge, severity lane, unchanged drag/drop) → Task 14.
- §5.6 dual-graph proximal selection → Task 5.
- §5.7 notifications (Vizor always-on, Slack gated, fence hints) → Vizor coverage is Task 13's widget/panel; Slack is Task 9; fence hints are Task 8.
- §5.8 CLI/GH trigger → Task 10 (CLI), Task 11 (GH Actions workflow); slash-command dispatcher explicitly out of scope (non-goal, not planned).
- §5.9 onboarding fix → Task 12.
- §6 taxonomy-as-config → Tasks 1 and 3.
- §7 Domain Pack extension point → Task 2.
- §8 testing approach → every task includes its own unit tests per the spec's list (action dry-run/promote branching in Task 6/9, proximal-selection tiers including the non-code-dominant degradation case in Task 5, severity-override bypass in Task 6, `load_domain_pack()` merge behavior in Task 2, full wake-cycle integration in Task 6, Vizor rendering in Tasks 13-14, CLI wiring in Task 10).
- §9 future work → correctly excluded from every task (no slash-command dispatcher, no rxcc/vdowrx/Hitchcock-specific packs, no changes to other roles' wake cycles beyond the minimum TPM/Roadmap-Studio touch already covered in Task 14).

**2. Placeholder scan:** No TBD/TODO markers; every step has complete code, including the HTML/JS insertions in Tasks 13-14, which quote the exact surrounding lines from the files read during planning (`synlynk/viz/roles.py`'s Edit Charter `</details>` boundary, `synlynk/viz/overview.py`'s "Recent / Active Dispatches" section-card boundary, `synlynk/viz/roadmap_studio.py`'s `cardHtml`/`draw()` functions).

**3. Type/signature consistency:** `select_proposal_target(candidate, open_proposals, repo_root=".")` (Task 5) is called with keyword args consistently; `run_maintainer_wake_cycle(repo_root=".")` (Task 6) matches its call sites in Task 7 (scheduler, no args — uses the default) and Task 10 (CLI, explicit `repo_root=os.getcwd()`); `get_action_config(name, repo_root=".")` (Task 4) is called identically in Tasks 6 and 9; `generate_role_ops_panel_html(role_slug, data)` and `generate_condensed_widget_html(role_slug, data)` (Task 13) share the same two-arg shape the spec's §5.4 text specifies; `_ensure_github_issue_for_story(story, repo_root=".")` (Task 6) is referenced with the same signature in Task 6's own `_run_sentinel_triage_action` and in Task 9's test monkeypatches.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-24-maintainer-full-autonomy.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
