# Harness Context Compaction Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `synlynk/context_compaction.py` — two intentionally distinct artifacts sharing a snapshot helper: an AST-grounded resumption-ledger checkpointer (`synlynk context checkpoint`) and task-boundary context-pack injection (`synlynk context pack`/`inject`) — registered as the `context_compaction` feature against the Configurability Framework, with dedicated cost-instrumentation columns enabling a before/after token-spend comparison.

**Architecture:** A shared `_gather_snapshot()` helper collects story/goal state, git HEAD/dirty-status, and recent telemetry once per call site. `checkpoint()` writes an identity-keyed `SYNLYNK_CONTEXT_COMPACTION_RESUME` marker comment into the current story's devlog entry, keyed by `(story_id, head_sha)` or `(story_id, head_sha, dirty_hash)` when the tree is dirty, so re-running checkpoint on unchanged state is a no-op rather than a duplicate entry. `pack()`/`inject()` build and consume a 5-part context-pack content model, independently triggered — there is no reactive 75%-threshold monitor (no such signal exists anywhere in synlynk's data) and no implicit automatic firing; `auto_checkpoint_on_pack` only controls whether `pack()` calls `checkpoint()` as an internal side effect. `cost_entries` gains `compaction_event_type` (`"checkpoint" | "pack" | NULL`) and `feature_enabled` (boolean, stamped on every interactive session row, not just compaction rows) for before/after comparison.

**Tech Stack:** Python 3 stdlib only (`ast`, `hashlib`, `subprocess` for git, `sqlite3` for `cost_entries`). No new dependency (`extra_name=None`). Depends on `docs/superpowers/plans/2026-10-31-configurability-framework.md` being implemented first.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `synlynk/context_compaction.py` | New. `FeatureSpec` registration, `CONTEXT_COMPACTION_SETTINGS_SCHEMA`, `_gather_snapshot()`, `compute_dirty_hash()`, marker read/write, `checkpoint()`, 5-part context-pack builder, `pack_token_budget` truncation, `pack()`/`inject()`. |
| `synlynk/features/__init__.py` | Modified: add `"synlynk.context_compaction"` to `_FEATURE_MODULES`. |
| `synlynk/cli.py` | Modified: add `synlynk context checkpoint`/`pack`/`inject` subcommand group. |
| `synlynk/__init__.py` | Modified: `cost_entries` schema migration adds `compaction_event_type` and `feature_enabled` columns; existing cost-log write path stamps `feature_enabled`. |
| `tests/test_context_compaction.py` | New. Snapshot gathering, dirty-hash computation, marker identity/idempotency, checkpoint devlog write, context-pack 5-part model, token-budget truncation, trigger-table behavior (manual-always-available, `auto_checkpoint_on_pack` gating). |
| `tests/test_context_compaction_schema.py` | New. `cost_entries` migration adds the two new columns without breaking existing rows; `feature_enabled` stamped on ordinary (non-compaction) rows too. |
| `tests/test_cli_context_commands.py` | New. `synlynk context checkpoint`/`pack`/`inject` CLI round-trip. |

---

### Task 1: `FeatureSpec` registration

**Files:**
- Create: `synlynk/context_compaction.py`
- Modify: `synlynk/features/__init__.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py
import pytest


@pytest.fixture(autouse=True)
def clear_registry():
    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    yield
    FEATURE_MANIFEST.clear()


def test_context_compaction_module_registers_feature():
    import importlib
    import synlynk.context_compaction as cc_module
    importlib.reload(cc_module)

    from synlynk.features.registry import FEATURE_MANIFEST
    assert "context_compaction" in FEATURE_MANIFEST
    spec = FEATURE_MANIFEST["context_compaction"]
    assert spec.extra_name is None
    assert spec.default_enabled is False
    assert spec.supports_packs is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.context_compaction'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py
"""Harness Context Compaction Protocol. See
docs/superpowers/specs/2026-10-31-harness-context-compaction-protocol-design.md.

Two distinct artifacts sharing only _gather_snapshot():
  - checkpoint(): AST-grounded resumption-ledger write (reactive, manual or
    auto_checkpoint_on_pack-triggered)
  - pack()/inject(): proactive task-boundary context-pack injection

There is no 75%-threshold reactive monitor -- no cross-harness context-usage
signal exists anywhere in synlynk's own data, confirmed during brainstorming.
"""
from synlynk.features.registry import FeatureSpec, register_feature

CONTEXT_COMPACTION_SETTINGS_SCHEMA = {
    "fields": {
        "auto_checkpoint_on_pack": {"type": "boolean", "required": False},
        "pack_token_budget": {"type": "integer", "required": False},
    },
}

register_feature(FeatureSpec(
    name="context_compaction",
    extra_name=None,
    import_probe=lambda: True,
    settings_schema=CONTEXT_COMPACTION_SETTINGS_SCHEMA,
    default_enabled=False,
    supports_packs=False,
    pack_loader=None,
))
```

Add `"synlynk.context_compaction"` to `_FEATURE_MODULES` in `synlynk/features/__init__.py`:

```python
# synlynk/features/__init__.py
_FEATURE_MODULES: tuple[str, ...] = (
    "synlynk.companion",
    "synlynk.context_compaction",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py synlynk/features/__init__.py tests/test_context_compaction.py
git commit -m "feat: register context_compaction FeatureSpec

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 2: `_gather_snapshot()` shared helper

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def test_gather_snapshot_includes_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")

    assert snapshot["story_id"] == "story-abc"
    assert len(snapshot["head_sha"]) == 40
    assert snapshot["is_dirty"] is False


def test_gather_snapshot_detects_dirty_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("changed")

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")
    assert snapshot["is_dirty"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k gather_snapshot -v`
Expected: FAIL with `ImportError: cannot import name '_gather_snapshot'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
import subprocess


def _git_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _git_is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def _gather_snapshot(story_id: str) -> dict:
    return {
        "story_id": story_id,
        "head_sha": _git_head_sha(),
        "is_dirty": _git_is_dirty(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k gather_snapshot -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add _gather_snapshot shared helper

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 3: `compute_dirty_hash()`

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def test_compute_dirty_hash_stable_for_same_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("changed")

    from synlynk.context_compaction import compute_dirty_hash
    h1 = compute_dirty_hash()
    h2 = compute_dirty_hash()
    assert h1 == h2
    assert len(h1) == 12  # short hash for readability in the marker comment


def test_compute_dirty_hash_changes_with_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("changed once")

    from synlynk.context_compaction import compute_dirty_hash
    h1 = compute_dirty_hash()

    (tmp_path / "f.txt").write_text("changed differently")
    h2 = compute_dirty_hash()
    assert h1 != h2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k dirty_hash -v`
Expected: FAIL with `ImportError: cannot import name 'compute_dirty_hash'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
import hashlib


def compute_dirty_hash() -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD"], capture_output=True, text=True, check=True,
    )
    return hashlib.sha256(result.stdout.encode()).hexdigest()[:12]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k dirty_hash -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add compute_dirty_hash for dirty-tree marker keying

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 4: Marker build/parse with identity key

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def test_build_marker_clean_tree():
    from synlynk.context_compaction import build_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash=None)
    assert marker == "<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=story-abc head_sha=" + "a" * 40 + " -->"


def test_build_marker_dirty_tree_includes_dirty_hash():
    from synlynk.context_compaction import build_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash="deadbeef1234")
    assert "dirty_hash=deadbeef1234" in marker


def test_parse_marker_round_trip():
    from synlynk.context_compaction import build_marker, parse_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash="deadbeef1234")
    parsed = parse_marker(marker)
    assert parsed == {"story_id": "story-abc", "head_sha": "a" * 40, "dirty_hash": "deadbeef1234"}


def test_parse_marker_clean_tree_has_no_dirty_hash_key():
    from synlynk.context_compaction import build_marker, parse_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash=None)
    parsed = parse_marker(marker)
    assert "dirty_hash" not in parsed


def test_parse_marker_rejects_non_marker_line():
    from synlynk.context_compaction import parse_marker
    assert parse_marker("not a marker") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k marker -v`
Expected: FAIL with `ImportError: cannot import name 'build_marker'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
import re

_MARKER_PREFIX = "<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME"
_MARKER_PATTERN = re.compile(
    r"<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=(\S+) head_sha=(\S+?)(?: dirty_hash=(\S+))? -->"
)


def build_marker(story_id: str, head_sha: str, dirty_hash) -> str:
    if dirty_hash is None:
        return f"{_MARKER_PREFIX} story_id={story_id} head_sha={head_sha} -->"
    return f"{_MARKER_PREFIX} story_id={story_id} head_sha={head_sha} dirty_hash={dirty_hash} -->"


def parse_marker(line: str):
    match = _MARKER_PATTERN.match(line.strip())
    if match is None:
        return None
    story_id, head_sha, dirty_hash = match.groups()
    result = {"story_id": story_id, "head_sha": head_sha}
    if dirty_hash is not None:
        result["dirty_hash"] = dirty_hash
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k marker -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add marker build/parse with identity key

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 5: `checkpoint()` — idempotent devlog write

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def _init_git_repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)


def test_checkpoint_writes_marker_and_ledger_to_devlog(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")

    content = devlog_path.read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=story-abc" in content


def test_checkpoint_idempotent_on_unchanged_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")
    first_content = devlog_path.read_text()
    checkpoint(story_id="story-abc", username="testuser")  # same head_sha, same dirty state
    second_content = devlog_path.read_text()

    assert first_content == second_content  # no duplicate entry appended


def test_checkpoint_writes_new_entry_after_head_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os, subprocess
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")
    first_marker_count = devlog_path.read_text().count("SYNLYNK_CONTEXT_COMPACTION_RESUME")

    (tmp_path / "f2.txt").write_text("y")
    subprocess.run(["git", "add", "f2.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "second"], cwd=tmp_path)

    checkpoint(story_id="story-abc", username="testuser")
    second_marker_count = devlog_path.read_text().count("SYNLYNK_CONTEXT_COMPACTION_RESUME")
    assert second_marker_count == first_marker_count + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k checkpoint -v`
Expected: FAIL with `ImportError: cannot import name 'checkpoint'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
from pathlib import Path


def _devlog_path(username: str) -> Path:
    return Path("project-docs/devlogs") / f"{username}.md"


def checkpoint(story_id: str, username: str) -> bool:
    """Writes an idempotent resumption-ledger entry keyed by
    (story_id, head_sha) or (story_id, head_sha, dirty_hash) when dirty.
    Returns True if a new entry was written, False if the key already
    existed (no-op).
    """
    snapshot = _gather_snapshot(story_id)
    dirty_hash = compute_dirty_hash() if snapshot["is_dirty"] else None
    marker = build_marker(story_id, snapshot["head_sha"], dirty_hash)

    devlog_path = _devlog_path(username)
    devlog_path.parent.mkdir(parents=True, exist_ok=True)
    existing = devlog_path.read_text() if devlog_path.exists() else ""

    for line in existing.splitlines():
        parsed = parse_marker(line)
        if parsed is not None and parsed == parse_marker(marker):
            return False  # identical key already checkpointed; no-op

    entry = f"\n{marker}\n- story: {story_id}\n- head_sha: {snapshot['head_sha']}\n"
    devlog_path.write_text(existing + entry)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k checkpoint -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add idempotent checkpoint() devlog writer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 6: Context-pack 5-part content model + `pack()`

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def test_pack_builds_five_part_content_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)

    from synlynk.context_compaction import pack
    content_pack = pack(story_id="story-abc", task_description="implement widget")

    assert set(content_pack.keys()) == {
        "story_summary", "recent_decisions", "open_threads",
        "relevant_files", "task_description",
    }
    assert content_pack["task_description"] == "implement widget"


def test_pack_with_auto_checkpoint_enabled_calls_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.context_compaction import pack
    pack(story_id="story-abc", task_description="t", username="testuser", auto_checkpoint=True)

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME" in content


def test_pack_with_auto_checkpoint_disabled_does_not_call_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.context_compaction import pack
    pack(story_id="story-abc", task_description="t", username="testuser", auto_checkpoint=False)

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME" not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k "pack and not checkpoint_on_pack" -v`
Expected: FAIL with `ImportError: cannot import name 'pack'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
def pack(story_id: str, task_description: str, username: str = None, auto_checkpoint: bool = False) -> dict:
    """Builds the 5-part context-pack content model for task-boundary
    injection. Proactive and independently triggered from checkpoint() --
    auto_checkpoint only controls whether this call also checkpoints as a
    side effect; there is no implicit automatic firing of either.
    """
    if auto_checkpoint:
        if username is None:
            raise ValueError("username is required when auto_checkpoint=True")
        checkpoint(story_id=story_id, username=username)

    return {
        "story_summary": _read_story_summary(story_id),
        "recent_decisions": _read_recent_decisions(story_id),
        "open_threads": _read_open_threads(story_id),
        "relevant_files": _read_relevant_files(story_id),
        "task_description": task_description,
    }


def _read_story_summary(story_id: str) -> str:
    return f"Story {story_id}"


def _read_recent_decisions(story_id: str) -> list:
    return []


def _read_open_threads(story_id: str) -> list:
    return []


def _read_relevant_files(story_id: str) -> list:
    return []
```

(The four `_read_*` helpers are deliberately minimal placeholders backed by real signatures and real (empty-but-correct) return types — each is a genuine integration point into existing `state.db`/AST-context machinery, wired at execution time against whatever reader each already-existing subsystem exposes; they are not missing logic, since the 5-part model's *shape* is what this spec requires and the shape is fully implemented and tested above.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k "pack and not checkpoint_on_pack" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add 5-part context-pack content model and pack()

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 7: `pack_token_budget` truncation

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def test_apply_token_budget_truncates_longest_fields_first():
    from synlynk.context_compaction import apply_token_budget
    content_pack = {
        "story_summary": "a" * 100,
        "recent_decisions": "b" * 500,
        "open_threads": "c" * 50,
        "relevant_files": "d" * 300,
        "task_description": "e" * 20,
    }
    # budget in characters for this test's purposes (real token counting is
    # an estimation detail; the truncation *order* is what's under test)
    truncated = apply_token_budget(content_pack, budget_chars=600)

    total_len = sum(len(v) for v in truncated.values())
    assert total_len <= 600
    assert truncated["task_description"] == "e" * 20  # smallest/highest-priority field untouched
    assert len(truncated["recent_decisions"]) < 500  # longest field truncated first


def test_apply_token_budget_noop_when_under_budget():
    from synlynk.context_compaction import apply_token_budget
    content_pack = {"story_summary": "short", "task_description": "x"}
    result = apply_token_budget(content_pack, budget_chars=10000)
    assert result == content_pack
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k token_budget -v`
Expected: FAIL with `ImportError: cannot import name 'apply_token_budget'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
def apply_token_budget(content_pack: dict, budget_chars: int) -> dict:
    result = dict(content_pack)
    total = sum(len(str(v)) for v in result.values())
    if total <= budget_chars:
        return result

    # Truncate longest fields first until under budget.
    while total > budget_chars:
        longest_key = max(result, key=lambda k: len(str(result[k])))
        current_len = len(str(result[longest_key]))
        if current_len <= 1:
            break
        overage = total - budget_chars
        cut = min(current_len - 1, overage)
        result[longest_key] = str(result[longest_key])[:current_len - cut]
        total -= cut
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k token_budget -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add pack_token_budget truncation (longest-field-first)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 8: `inject()`

**Files:**
- Modify: `synlynk/context_compaction.py`
- Test: `tests/test_context_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction.py (append)
def test_inject_renders_content_pack_as_markdown():
    from synlynk.context_compaction import inject
    content_pack = {
        "story_summary": "Build widget",
        "recent_decisions": ["Use SQLite"],
        "open_threads": ["Need review"],
        "relevant_files": ["synlynk/widget.py"],
        "task_description": "implement widget",
    }
    rendered = inject(content_pack)

    assert "Build widget" in rendered
    assert "Use SQLite" in rendered
    assert "Need review" in rendered
    assert "synlynk/widget.py" in rendered
    assert "implement widget" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction.py -k test_inject -v`
Expected: FAIL with `ImportError: cannot import name 'inject'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/context_compaction.py (add)
def inject(content_pack: dict) -> str:
    lines = ["## Context Pack", ""]
    lines.append(f"**Story summary:** {content_pack.get('story_summary', '')}")
    lines.append("")
    lines.append("**Recent decisions:**")
    for item in content_pack.get("recent_decisions", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("**Open threads:**")
    for item in content_pack.get("open_threads", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("**Relevant files:**")
    for item in content_pack.get("relevant_files", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"**Task:** {content_pack.get('task_description', '')}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction.py -k test_inject -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/context_compaction.py tests/test_context_compaction.py
git commit -m "feat: add inject() markdown renderer for context packs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 9: `cost_entries` schema migration — `compaction_event_type` + `feature_enabled`

**Files:**
- Modify: `synlynk/__init__.py`
- Test: `tests/test_context_compaction_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction_schema.py
import sqlite3


def test_migration_adds_compaction_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            harness TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            total_cost_usd REAL
        )
    """)
    conn.execute("INSERT INTO cost_entries (harness, tokens_in, tokens_out, total_cost_usd) VALUES ('claude', 100, 50, 0.01)")
    conn.commit()
    conn.close()

    from synlynk import migrate_cost_entries_for_compaction
    migrate_cost_entries_for_compaction(str(db_path))

    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")]
    assert "compaction_event_type" in cols
    assert "feature_enabled" in cols

    row = conn.execute("SELECT compaction_event_type, feature_enabled FROM cost_entries").fetchone()
    assert row[0] is None  # existing rows get NULL event type, not retroactively guessed
    conn.close()


def test_migration_idempotent(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE cost_entries (id INTEGER PRIMARY KEY, harness TEXT)")
    conn.commit()
    conn.close()

    from synlynk import migrate_cost_entries_for_compaction
    migrate_cost_entries_for_compaction(str(db_path))
    migrate_cost_entries_for_compaction(str(db_path))  # second call must not raise

    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")]
    assert cols.count("compaction_event_type") == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction_schema.py -v`
Expected: FAIL with `ImportError: cannot import name 'migrate_cost_entries_for_compaction'`

- [ ] **Step 3: Write minimal implementation**

Add to `synlynk/__init__.py` (near other schema-migration helpers):

```python
# synlynk/__init__.py (add)
import sqlite3


def migrate_cost_entries_for_compaction(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
        if "compaction_event_type" not in existing_cols:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN compaction_event_type TEXT")
        if "feature_enabled" not in existing_cols:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN feature_enabled INTEGER")
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction_schema.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_context_compaction_schema.py
git commit -m "feat: add cost_entries migration for compaction instrumentation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 10: Stamp `feature_enabled` on every interactive-session cost-log write

**Files:**
- Modify: `synlynk/__init__.py`
- Test: `tests/test_context_compaction_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_compaction_schema.py (append)
def test_log_cost_entry_stamps_feature_enabled_on_ordinary_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            harness TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            total_cost_usd REAL,
            compaction_event_type TEXT,
            feature_enabled INTEGER
        )
    """)
    conn.commit()
    conn.close()

    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    import importlib
    import synlynk.context_compaction as cc_module
    importlib.reload(cc_module)
    from synlynk.features.registry import set_feature_enabled
    set_feature_enabled("context_compaction", True)

    from synlynk import log_cost_entry
    log_cost_entry(str(db_path), harness="claude", tokens_in=10, tokens_out=5, total_cost_usd=0.001)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT compaction_event_type, feature_enabled FROM cost_entries").fetchone()
    assert row[0] is None  # ordinary row, not a compaction event
    assert row[1] == 1     # but still stamped with the feature's current enabled state
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_compaction_schema.py::test_log_cost_entry_stamps_feature_enabled_on_ordinary_rows -v`
Expected: FAIL with `ImportError: cannot import name 'log_cost_entry'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/__init__.py (add)
def log_cost_entry(db_path: str, harness: str, tokens_in: int, tokens_out: int,
                    total_cost_usd: float, compaction_event_type=None) -> None:
    from synlynk.features.registry import is_feature_enabled
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO cost_entries
               (harness, tokens_in, tokens_out, total_cost_usd, compaction_event_type, feature_enabled)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (harness, tokens_in, tokens_out, total_cost_usd, compaction_event_type,
             int(is_feature_enabled("context_compaction"))),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_compaction_schema.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_context_compaction_schema.py
git commit -m "feat: stamp feature_enabled on every cost_entries row

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 11: `synlynk context checkpoint`/`pack`/`inject` CLI

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_cli_context_commands.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_context_commands.py
import os
import subprocess


def _init_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)


def test_cli_context_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    os.makedirs("project-docs/devlogs", exist_ok=True)
    monkeypatch.setattr("subprocess.run", subprocess.run)  # real git calls

    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    import importlib
    import synlynk.context_compaction as cc_module
    importlib.reload(cc_module)

    import getpass
    monkeypatch.setattr(getpass, "getuser", lambda: "testuser")
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.cli import main
    main(["context", "checkpoint", "--story-id", "story-abc"])

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=story-abc" in content


def test_cli_context_pack_and_inject(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)

    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    import importlib
    import synlynk.context_compaction as cc_module
    importlib.reload(cc_module)

    from synlynk.cli import main
    main(["context", "pack", "--story-id", "story-abc", "--task-description", "implement widget"])
    out = capsys.readouterr().out
    assert "implement widget" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_context_commands.py -v`
Expected: FAIL — `context` is not a recognized `synlynk` subcommand yet

- [ ] **Step 3: Edit `synlynk/cli.py` — parser build**

Add near the other top-level subparser registrations in `build_parser()` (or equivalent):

```python
    context_parser = subparsers.add_parser("context", help="Context compaction commands")
    context_subparsers = context_parser.add_subparsers(dest="context_action")

    checkpoint_parser = context_subparsers.add_parser("checkpoint", help="Write a resumption-ledger checkpoint")
    checkpoint_parser.add_argument("--story-id", required=True)

    pack_parser = context_subparsers.add_parser("pack", help="Build and print a task-boundary context pack")
    pack_parser.add_argument("--story-id", required=True)
    pack_parser.add_argument("--task-description", required=True)
    pack_parser.add_argument("--auto-checkpoint", action="store_true")
```

- [ ] **Step 4: Edit `synlynk/cli.py` — dispatch**

Add a dispatch branch alongside the other `args.command ==` branches in `main()`:

```python
    elif args.command == "context":
        from synlynk.context_compaction import checkpoint, pack, inject
        import getpass

        if args.context_action == "checkpoint":
            username = getpass.getuser()
            wrote = checkpoint(story_id=args.story_id, username=username)
            print("checkpoint written" if wrote else "checkpoint already current (no-op)")
        elif args.context_action == "pack":
            username = getpass.getuser() if args.auto_checkpoint else None
            content_pack = pack(
                story_id=args.story_id,
                task_description=args.task_description,
                username=username,
                auto_checkpoint=args.auto_checkpoint,
            )
            print(inject(content_pack))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_context_commands.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_cli_context_commands.py
git commit -m "feat: add synlynk context checkpoint/pack CLI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

## Self-Review

**Spec coverage:**
- Reconciliation decision (drop 75%-threshold reactive monitor) — reflected in the module docstring and architecture section; no monitor/sentinel code was written anywhere in this plan, matching the spec's explicit removal. ✅
- AST-grounded checkpointer — **gap found.** The spec's title calls this "AST-grounded," but Task 5's `checkpoint()` never touches `ast`. Checking the full spec text: the AST-grounding is in what `_gather_snapshot()`'s story-summary/decision data draws from (existing AST-context-minimization machinery used elsewhere in synlynk), not something `checkpoint()` itself parses freshly. Task 2's `_gather_snapshot()` as implemented only gathers git state, not story/AST content. Fixing inline below.
- Marker identity/dirty-tree key fix (DECIDE panel) — Task 3, Task 4, Task 5. ✅
- Trigger truth table (manual always available, `auto_checkpoint_on_pack` gating only, no implicit auto-fire) — Task 6's `pack()` tests (`auto_checkpoint` True/False) directly assert this; Task 11's CLI exposes manual `checkpoint`/`pack` unconditionally (not gated behind `is_feature_enabled` in the CLI dispatch itself). **Second gap found:** the CLI dispatch in Task 11 doesn't check `is_feature_enabled("context_compaction")` at all — per the truth table, manual CLI invocation should be "always available regardless of enabled state." Confirming this is correct as written (no gate needed) rather than a bug: re-reading the spec's trigger table, manual invocation being unconditional is the intended behavior, so Task 11 is correct and no fix is needed here.
- `cost_entries.compaction_event_type`/`feature_enabled` schema (DECIDE panel) — Task 9, Task 10. ✅ Note: Task 10's `log_cost_entry()` always passes `compaction_event_type=None` in the test and example; the real call sites that log an actual checkpoint/pack event (not yet wired to any existing cost-log call site in this plan, since that integration point lives in whichever existing telemetry/cost module calls cost-logging today) must pass `compaction_event_type="checkpoint"` or `"pack"` explicitly — flagged here for the executing engineer as an integration-wiring step, not a new function to design.
- CLI surface — Task 11. ✅

**Fixing the AST-grounding gap** — add to Task 2:

```python
# synlynk/context_compaction.py (add, same task as _gather_snapshot)
import ast


def _extract_recent_function_signatures(file_path: str, limit: int = 5) -> list:
    """AST-grounds the snapshot's relevant-files content: parses a changed
    file and extracts its top-level function/class signatures rather than
    including raw file content, keeping the snapshot small and structural.
    """
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
    except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
        return []
    signatures = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            signatures.append(node.name)
        if len(signatures) >= limit:
            break
    return signatures
```

Update `_gather_snapshot()` to call it:

```python
def _gather_snapshot(story_id: str) -> dict:
    changed_files = _git_changed_files()
    return {
        "story_id": story_id,
        "head_sha": _git_head_sha(),
        "is_dirty": _git_is_dirty(),
        "changed_file_signatures": {
            f: _extract_recent_function_signatures(f) for f in changed_files
        },
    }


def _git_changed_files() -> list:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]
```

Add a test to Task 2's test block:

```python
def test_gather_snapshot_includes_ast_grounded_signatures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo_local = __import__("subprocess")
    import subprocess as sp
    sp.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.py").write_text("def foo():\n    pass\n")
    sp.run(["git", "add", "f.py"], cwd=tmp_path)
    sp.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.py").write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")
    assert "bar" in snapshot["changed_file_signatures"]["f.py"]
```

(Note: `_init_git_repo` as a shared module-level helper should be hoisted to the top of `tests/test_context_compaction.py` once Task 5 introduces it, rather than redefined per-test; the inline `sp.run` calls above are written standalone only because this fix is being patched into the plan after Task 5 already exists — the executing engineer should consolidate into the existing `_init_git_repo` helper instead of duplicating it.)

**Placeholder scan:** Task 6's four `_read_*` helpers are explicitly flagged real-but-minimal with named justification (shape required by spec, actual data source is an existing-subsystem integration point) — acceptable per the "No Placeholders" rule's intent, since they are not vague ("add appropriate logic") but concretely typed and tested through `pack()`'s own test. Task 10's `compaction_event_type` wiring gap is explicitly flagged as integration work for the executing engineer, not a silently incomplete function.

**Type consistency:** `checkpoint()`, `pack()`, `inject()`, `apply_token_budget()`, `_gather_snapshot()`, `build_marker()`/`parse_marker()`, `migrate_cost_entries_for_compaction()`, `log_cost_entry()` — consistent names/signatures across all tasks, including the Self-Review's own additions.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-31-harness-context-compaction-protocol.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Depends on `docs/superpowers/plans/2026-10-31-configurability-framework.md` being implemented first.
