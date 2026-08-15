# Workspace Agent Artifact Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build canonical, workspace-scoped storage for durable agents' charter/memory/Statements-of-Record and a stable `agent_id` identity registry, per `docs/superpowers/specs/2026-08-15-workspace-agent-artifact-storage-design.md`.

**Architecture:** One new module, `synlynk/agent_store.py`, holding all read/write logic for the workspace-level store (`~/.synlynk/workspaces/<workspace_id>/agents/`). `workspace_id` is minted once into the existing `.synlynk/config.json`. Canonical content (charter/memory/SoR) lives entirely outside any repo, in per-artifact Markdown files paired with append-only `.revisions.jsonl` provenance logs. The repo-local `.synlynk/agents/<agent_id>.yaml` is a generated, non-canonical projection.

**Tech Stack:** Python 3 stdlib only (`json`, `hashlib`, `uuid`, `os`, `datetime`) — this repo has zero dependencies beyond stdlib (see root `CLAUDE.md`: "No dependencies beyond Python 3 stdlib"). The projection file uses a `.yaml` extension but is hand-serialized by a small flat-dict emitter in this plan — do **not** add a `PyYAML` dependency.

**Note on line numbers:** every line number cited below was accurate at plan-writing time but is not a stable identifier — locate each anchor by function/table name first (`grep -n "def load_config"`, etc.) and treat the cited line as a hint, not ground truth.

---

## Explicitly out of scope

Per the design spec §5: the `gated` mutability/approval workflow, GOVERNS-derived action-log/cost projections, Phase 1's own `agent init/list/show/edit/disable` CLI, cross-repo `workspace_id` sharing, `state.db` relocation, the `repos` table, `sync_log`, `synlynk workspace join`, and server-side storage. Those get separate follow-up plans.

---

### Task 1: `get_workspace_id()` — mint-once workspace identity

**Files:**
- Create: `synlynk/agent_store.py`
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_store.py`:

```python
import json
import os


def test_get_workspace_id_mints_and_persists(project_dir):
    from synlynk.agent_store import get_workspace_id

    workspace_id = get_workspace_id()
    assert workspace_id
    with open(".synlynk/config.json") as f:
        config = json.load(f)
    assert config["workspace_id"] == workspace_id


def test_get_workspace_id_idempotent(project_dir):
    from synlynk.agent_store import get_workspace_id

    first = get_workspace_id()
    second = get_workspace_id()
    assert first == second


def test_get_workspace_id_never_overwrites_existing_value(project_dir):
    from synlynk.agent_store import get_workspace_id

    with open(".synlynk/config.json") as f:
        config = json.load(f)
    config["workspace_id"] = "pre-existing-id"
    with open(".synlynk/config.json", "w") as f:
        json.dump(config, f)

    assert get_workspace_id() == "pre-existing-id"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.agent_store'`

- [ ] **Step 3: Write minimal implementation**

Create `synlynk/agent_store.py`:

```python
"""Workspace-level storage for durable agents' charter, memory, and
Statements of Record. See docs/superpowers/specs/2026-08-15-workspace-agent-artifact-storage-design.md.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from synlynk import _write_json_atomic

_CONFIG_PATH = os.path.join(".synlynk", "config.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_raw_config() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        return {}
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def get_workspace_id() -> str:
    """Return this repo's workspace_id, minting and persisting one on first call.

    Each repo currently gets its own workspace_id (no cross-repo sharing yet —
    see design spec Conflict B). Never overwrites an existing value.
    """
    config = _load_raw_config()
    existing = config.get("workspace_id")
    if existing:
        return existing
    workspace_id = str(uuid.uuid4())
    config["workspace_id"] = workspace_id
    _write_json_atomic(_CONFIG_PATH, config)
    return workspace_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: workspace_id mint-once helper for agent artifact storage"
```

---

### Task 2: Agent store paths + `agent_id` registry

**Files:**
- Modify: `synlynk/agent_store.py`
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_store.py`:

```python
def test_agent_store_path_under_workspace_home(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    workspace_id = agent_store.get_workspace_id()
    path = agent_store.agent_store_path("dev-primary")
    assert path == str(fake_home / ".synlynk" / "workspaces" / workspace_id / "agents" / "dev-primary")


def test_register_and_resolve_agent(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent(
        "dev-primary",
        aliases=[
            {"kind": "role_slug", "value": "dev"},
            {"kind": "github_app_slug", "value": "synlynk-dev[bot]"},
        ],
    )

    assert agent_store.resolve_agent_id("dev") == "dev-primary"
    assert agent_store.resolve_agent_id("synlynk-dev[bot]") == "dev-primary"
    assert agent_store.resolve_agent_id("unregistered-alias") is None


def test_register_agent_rejects_duplicate_agent_id(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    try:
        agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev2"}])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_register_agent_rejects_duplicate_alias_across_agents(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    try:
        agent_store.register_agent("dev-secondary", aliases=[{"kind": "role_slug", "value": "dev"}])
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.agent_store' has no attribute 'agent_store_path'`

- [ ] **Step 3: Write minimal implementation**

Append to `synlynk/agent_store.py`:

```python
def _workspace_root(workspace_id: str) -> str:
    return os.path.expanduser(os.path.join("~", ".synlynk", "workspaces", workspace_id))


def agent_store_path(agent_id: str) -> str:
    """Resolve the canonical on-disk directory for one agent's artifacts."""
    workspace_id = get_workspace_id()
    return os.path.join(_workspace_root(workspace_id), "agents", agent_id)


def _registry_path() -> str:
    workspace_id = get_workspace_id()
    return os.path.join(_workspace_root(workspace_id), "agents", "registry.json")


def _load_registry() -> dict:
    path = _registry_path()
    if not os.path.exists(path):
        return {"agents": []}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"agents": []}


def register_agent(agent_id: str, aliases: list) -> None:
    """Register a new agent_id with its aliases. Fails loudly on any collision.

    aliases: list of {"kind": str, "value": str} dicts.
    """
    registry = _load_registry()
    existing_ids = {a["agent_id"] for a in registry["agents"]}
    if agent_id in existing_ids:
        raise ValueError(f"agent_id {agent_id!r} is already registered")

    existing_values = {
        alias["value"] for agent in registry["agents"] for alias in agent["aliases"]
    }
    for alias in aliases:
        if alias["value"] in existing_values:
            raise ValueError(f"alias {alias['value']!r} is already registered to another agent")

    registry["agents"].append({
        "agent_id": agent_id,
        "created_at": _now_iso(),
        "aliases": aliases,
        "history": [{"event": "created", "at": _now_iso()}],
    })
    path = _registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _write_json_atomic(path, registry)


def resolve_agent_id(alias: str) -> str:
    """Resolve an alias to its canonical agent_id, or None if unregistered.

    Never guesses — an unregistered alias returns None, it does not fork a
    new agent record.
    """
    registry = _load_registry()
    for agent in registry["agents"]:
        for a in agent["aliases"]:
            if a["value"] == alias:
                return agent["agent_id"]
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py -v`
Expected: PASS (7 tests total)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: agent store path resolution + agent_id registry"
```

---

### Task 3: Charter revision storage

**Files:**
- Modify: `synlynk/agent_store.py`
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_store.py`:

```python
def test_read_charter_missing_returns_empty(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    content, revision = agent_store.read_charter("dev-primary")
    assert content == ""
    assert revision == 0


def test_propose_charter_revision_writes_and_reads_back(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    new_revision = agent_store.propose_charter_revision(
        "dev-primary", "# Charter v1", actor="human:nikhilsoman", parent_revision=0
    )
    assert new_revision == 1

    content, revision = agent_store.read_charter("dev-primary")
    assert content == "# Charter v1"
    assert revision == 1


def test_propose_charter_revision_stale_parent_raises_conflict(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_charter_revision(
        "dev-primary", "# Charter v1", actor="human:nikhilsoman", parent_revision=0
    )
    try:
        agent_store.propose_charter_revision(
            "dev-primary", "# Charter v2 (stale)", actor="human:nikhilsoman", parent_revision=0
        )
        assert False, "expected agent_store.RevisionConflictError"
    except agent_store.RevisionConflictError:
        pass


def test_charter_revisions_jsonl_provenance_chain(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store
    import json as _json

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_charter_revision(
        "dev-primary", "# Charter v1", actor="human:nikhilsoman", parent_revision=0
    )
    agent_store.propose_charter_revision(
        "dev-primary", "# Charter v2", actor="agent:dev-primary", parent_revision=1
    )

    revisions_path = os.path.join(
        agent_store.agent_store_path("dev-primary"), "charter.revisions.jsonl"
    )
    lines = [_json.loads(line) for line in open(revisions_path) if line.strip()]
    assert len(lines) == 2
    assert lines[0]["revision"] == 1
    assert lines[0]["parent_hash"] is None
    assert lines[1]["revision"] == 2
    assert lines[1]["parent_hash"] == lines[0]["content_hash"]
    assert lines[1]["actor"] == "agent:dev-primary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.agent_store' has no attribute 'read_charter'`

- [ ] **Step 3: Write minimal implementation**

Append to `synlynk/agent_store.py`:

```python
class RevisionConflictError(Exception):
    """Raised when a proposed revision's parent_revision doesn't match the current head."""


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_versioned_file(file_path: str, revisions_path: str):
    """Return (content, current_revision) for a single-file versioned artifact."""
    if not os.path.exists(file_path):
        return "", 0
    with open(file_path) as f:
        content = f.read()
    revision = 0
    if os.path.exists(revisions_path):
        with open(revisions_path) as f:
            revision = sum(1 for line in f if line.strip())
    return content, revision


def _write_versioned_file(file_path: str, revisions_path: str, content: str, actor: str, parent_revision: int) -> int:
    """Write a new revision of a single-file versioned artifact. Raises RevisionConflictError on stale parent_revision."""
    _, current_revision = _read_versioned_file(file_path, revisions_path)
    if parent_revision != current_revision:
        raise RevisionConflictError(
            f"parent_revision {parent_revision} does not match current head {current_revision}"
        )
    parent_hash = None
    if current_revision > 0:
        with open(file_path) as f:
            parent_hash = _content_hash(f.read())

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)

    new_revision = current_revision + 1
    entry = {
        "revision": new_revision,
        "parent_hash": parent_hash,
        "content_hash": _content_hash(content),
        "actor": actor,
        "timestamp": _now_iso(),
    }
    with open(revisions_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return new_revision


def read_charter(agent_id: str):
    """Return (content, current_revision) for an agent's charter. ("", 0) if none exists yet."""
    base = agent_store_path(agent_id)
    return _read_versioned_file(
        os.path.join(base, "charter.md"), os.path.join(base, "charter.revisions.jsonl")
    )


def propose_charter_revision(agent_id: str, content: str, actor: str, parent_revision: int) -> int:
    """Write a new charter revision if parent_revision matches the current head.

    Raises RevisionConflictError otherwise. No auto-approval logic here — the
    'gated' (agent-proposed/human-approved) mutability tier is out of scope
    for this slice (design spec section 5).
    """
    base = agent_store_path(agent_id)
    return _write_versioned_file(
        os.path.join(base, "charter.md"),
        os.path.join(base, "charter.revisions.jsonl"),
        content,
        actor,
        parent_revision,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py -v`
Expected: PASS (11 tests total)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: charter revision storage with provenance chain"
```

---

### Task 4: Memory + Statements-of-Record storage

**Files:**
- Modify: `synlynk/agent_store.py`
- Test: `tests/test_agent_store.py`

**Category layout note:** unlike charter (one file, one revisions.jsonl), `memory/` and `statements-of-record/` hold multiple named entries sharing **one** `revisions.jsonl` per category, per the design spec's file layout. Each JSONL line gains an `"entry"` field to disambiguate; revision numbers are counted per-entry within that shared file.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_store.py`:

```python
def test_read_entry_missing_returns_empty(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    content, revision = agent_store.read_entry("dev-primary", "memory", "onboarding-notes")
    assert content == ""
    assert revision == 0


def test_propose_entry_revision_writes_and_reads_back(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    new_revision = agent_store.propose_entry_revision(
        "dev-primary", "memory", "onboarding-notes", "notes v1",
        actor="agent:dev-primary", parent_revision=0,
    )
    assert new_revision == 1

    content, revision = agent_store.read_entry("dev-primary", "memory", "onboarding-notes")
    assert content == "notes v1"
    assert revision == 1


def test_entries_in_same_category_have_independent_revision_counters(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-a", "a v1", actor="agent:dev-primary", parent_revision=0
    )
    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-b", "b v1", actor="agent:dev-primary", parent_revision=0
    )
    _, rev_a = agent_store.read_entry("dev-primary", "memory", "entry-a")
    _, rev_b = agent_store.read_entry("dev-primary", "memory", "entry-b")
    assert rev_a == 1
    assert rev_b == 1


def test_memory_and_sor_categories_share_one_revisions_file_each(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store
    import json as _json

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-a", "a v1", actor="agent:dev-primary", parent_revision=0
    )
    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-b", "b v1", actor="agent:dev-primary", parent_revision=0
    )

    revisions_path = os.path.join(agent_store.agent_store_path("dev-primary"), "memory", "revisions.jsonl")
    lines = [_json.loads(line) for line in open(revisions_path) if line.strip()]
    assert {line["entry"] for line in lines} == {"entry-a", "entry-b"}


def test_statements_of_record_category(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_entry_revision(
        "dev-primary", "statements-of-record", "2026-08-15-decision", "decided X",
        actor="human:nikhilsoman", parent_revision=0,
    )
    content, revision = agent_store.read_entry("dev-primary", "statements-of-record", "2026-08-15-decision")
    assert content == "decided X"
    assert revision == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.agent_store' has no attribute 'read_entry'`

- [ ] **Step 3: Write minimal implementation**

Append to `synlynk/agent_store.py`:

```python
_ENTRY_CATEGORIES = ("memory", "statements-of-record")


def _entry_file_path(agent_id: str, category: str, entry_name: str) -> str:
    assert category in _ENTRY_CATEGORIES, f"unknown category {category!r}"
    return os.path.join(agent_store_path(agent_id), category, f"{entry_name}.md")


def _entry_revisions_path(agent_id: str, category: str) -> str:
    assert category in _ENTRY_CATEGORIES, f"unknown category {category!r}"
    return os.path.join(agent_store_path(agent_id), category, "revisions.jsonl")


def _current_entry_revision(revisions_path: str, entry_name: str) -> int:
    if not os.path.exists(revisions_path):
        return 0
    count = 0
    with open(revisions_path) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["entry"] == entry_name:
                count += 1
    return count


def _latest_entry_content_hash(revisions_path: str, entry_name: str):
    if not os.path.exists(revisions_path):
        return None
    latest = None
    with open(revisions_path) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["entry"] == entry_name:
                latest = row
    return latest["content_hash"] if latest else None


def read_entry(agent_id: str, category: str, entry_name: str):
    """Return (content, current_revision) for one named entry in memory/ or statements-of-record/."""
    file_path = _entry_file_path(agent_id, category, entry_name)
    revisions_path = _entry_revisions_path(agent_id, category)
    if not os.path.exists(file_path):
        return "", 0
    with open(file_path) as f:
        content = f.read()
    return content, _current_entry_revision(revisions_path, entry_name)


def propose_entry_revision(agent_id: str, category: str, entry_name: str, content: str, actor: str, parent_revision: int) -> int:
    """Write a new revision of one named entry. Raises RevisionConflictError on stale parent_revision.

    memory/ and statements-of-record/ share this same mechanism (design spec
    section 4: "no separate design needed per category") — reuses the
    charter revision chain's hashing approach, but revisions.jsonl is shared
    per-category (keyed by "entry") rather than per-artifact.
    """
    file_path = _entry_file_path(agent_id, category, entry_name)
    revisions_path = _entry_revisions_path(agent_id, category)

    current_revision = _current_entry_revision(revisions_path, entry_name)
    if parent_revision != current_revision:
        raise RevisionConflictError(
            f"parent_revision {parent_revision} does not match current head {current_revision} for entry {entry_name!r}"
        )
    parent_hash = _latest_entry_content_hash(revisions_path, entry_name)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)

    new_revision = current_revision + 1
    entry_row = {
        "entry": entry_name,
        "revision": new_revision,
        "parent_hash": parent_hash,
        "content_hash": _content_hash(content),
        "actor": actor,
        "timestamp": _now_iso(),
    }
    with open(revisions_path, "a") as f:
        f.write(json.dumps(entry_row) + "\n")
    return new_revision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py -v`
Expected: PASS (16 tests total)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: memory + statements-of-record entry storage"
```

---

### Task 5: `regenerate_agent_projection()` — repo-local generated projection

**Files:**
- Modify: `synlynk/agent_store.py`
- Test: `tests/test_agent_store.py`

**Note on `.gitignore`:** `.synlynk/agents/<agent_id>.yaml` is already covered by the existing root `.gitignore` rule `.synlynk/*` (line 2) — there is no explicit `!.synlynk/agents` allowlist entry, so no `.gitignore` change is needed. Verify this with `git check-ignore` in the test below rather than assuming.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_store.py`:

```python
def test_regenerate_agent_projection_writes_flat_yaml(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    agent_store.propose_charter_revision(
        "dev-primary", "# secret charter content", actor="human:nikhilsoman", parent_revision=0
    )

    agent_store.regenerate_agent_projection("dev-primary", repo_overrides={"note": "pinned"})

    projection_path = os.path.join(".synlynk", "agents", "dev-primary.yaml")
    assert os.path.exists(projection_path)
    with open(projection_path) as f:
        rendered = f.read()
    assert "agent_id: dev-primary" in rendered
    assert "note: pinned" in rendered
    assert "secret charter content" not in rendered


def test_regenerate_agent_projection_is_idempotent(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    agent_store.regenerate_agent_projection("dev-primary", repo_overrides=None)
    projection_path = os.path.join(".synlynk", "agents", "dev-primary.yaml")
    with open(projection_path) as f:
        first = f.read()
    agent_store.regenerate_agent_projection("dev-primary", repo_overrides=None)
    with open(projection_path) as f:
        second = f.read()
    assert first == second


def test_regenerate_agent_projection_path_is_gitignored(project_dir, tmp_path, monkeypatch, git_worktree_repo):
    from synlynk import agent_store
    import subprocess

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    agent_store.regenerate_agent_projection("dev-primary", repo_overrides=None)

    result = subprocess.run(
        ["git", "check-ignore", os.path.join(".synlynk", "agents", "dev-primary.yaml")],
        cwd=git_worktree_repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, "expected .synlynk/agents/dev-primary.yaml to be gitignored"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.agent_store' has no attribute 'regenerate_agent_projection'`

- [ ] **Step 3: Write minimal implementation**

Append to `synlynk/agent_store.py`:

```python
def _dump_flat_yaml(data: dict, indent: int = 0) -> str:
    """Minimal hand-rolled YAML emitter for a flat (optionally one-level-nested) dict.

    Stdlib-only — this repo has zero external dependencies (see root CLAUDE.md).
    Only handles the shapes this module actually needs: str/int/bool/None
    scalars and one level of nested dict. Not a general-purpose YAML writer.
    """
    lines = []
    pad = "  " * indent
    for key, value in data.items():
        if value is None:
            lines.append(f"{pad}{key}: null")
        elif isinstance(value, dict):
            if not value:
                lines.append(f"{pad}{key}: {{}}")
            else:
                lines.append(f"{pad}{key}:")
                lines.append(_dump_flat_yaml(value, indent + 1))
        else:
            lines.append(f"{pad}{key}: {value}")
    return "\n".join(lines)


def _agent_role(agent_id: str) -> str:
    registry = _load_registry()
    for agent in registry["agents"]:
        if agent["agent_id"] == agent_id:
            for alias in agent["aliases"]:
                if alias["kind"] == "role_slug":
                    return alias["value"]
    return ""


def regenerate_agent_projection(agent_id: str, repo_overrides: dict = None) -> None:
    """Write the repo-local generated projection for one agent.

    Contains only agent_id/role/workspace_id/overrides metadata — never
    canonical charter/memory content. Idempotent: identical inputs produce
    byte-identical output. Already covered by the existing .gitignore rule
    `.synlynk/*` — no .gitignore change needed.
    """
    workspace_id = get_workspace_id()
    payload = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "role": _agent_role(agent_id),
        "overrides": repo_overrides or {},
    }
    rendered = _dump_flat_yaml(payload) + "\n"

    projection_dir = os.path.join(".synlynk", "agents")
    os.makedirs(projection_dir, exist_ok=True)
    projection_path = os.path.join(projection_dir, f"{agent_id}.yaml")
    with open(projection_path, "w") as f:
        f.write(rendered)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py -v`
Expected: PASS (19 tests total)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: regenerate_agent_projection for repo-local generated agent metadata"
```

---

### Task 6: Integration test

**Files:**
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Write the integration test**

Append to `tests/test_agent_store.py`:

```python
def test_full_flow_canonical_content_lives_only_in_workspace_store(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    workspace_id = agent_store.get_workspace_id()
    assert workspace_id

    agent_store.register_agent(
        "dev-primary",
        aliases=[
            {"kind": "role_slug", "value": "dev"},
            {"kind": "github_app_slug", "value": "synlynk-dev[bot]"},
        ],
    )
    assert agent_store.resolve_agent_id("dev") == "dev-primary"

    rev1 = agent_store.propose_charter_revision(
        "dev-primary", "# Dev charter v1", actor="human:nikhilsoman", parent_revision=0
    )
    assert rev1 == 1
    rev2 = agent_store.propose_charter_revision(
        "dev-primary", "# Dev charter v2 — expanded scope", actor="agent:dev-primary", parent_revision=1
    )
    assert rev2 == 2

    content, revision = agent_store.read_charter("dev-primary")
    assert content == "# Dev charter v2 — expanded scope"
    assert revision == 2

    agent_store.regenerate_agent_projection("dev-primary", repo_overrides={"pinned_role": "dev"})

    projection_path = os.path.join(".synlynk", "agents", "dev-primary.yaml")
    with open(projection_path) as f:
        projection_content = f.read()
    assert "Dev charter" not in projection_content
    assert "agent_id: dev-primary" in projection_content

    canonical_charter_path = os.path.join(
        agent_store.agent_store_path("dev-primary"), "charter.md"
    )
    assert str(fake_home) in canonical_charter_path
    with open(canonical_charter_path) as f:
        assert "Dev charter v2" in f.read()
```

- [ ] **Step 2: Run the full test file**

Run: `pytest tests/test_agent_store.py -v`
Expected: PASS (20 tests total)

- [ ] **Step 3: Run the full project test suite**

Run: `pytest -q`
Expected: all tests pass, no regressions (baseline before this plan: 1966 passed, 2 skipped — this plan adds 20 new tests to that baseline, so expect 1986 passed, 2 skipped)

- [ ] **Step 4: Commit**

```bash
git add tests/test_agent_store.py
git commit -m "test: integration coverage for full agent artifact storage flow"
```
