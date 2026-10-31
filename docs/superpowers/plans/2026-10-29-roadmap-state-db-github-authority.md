# Roadmap/Cost/Decision Authority: state.db + GitHub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `state.db` the sole authority for roadmap/cost/decision data, sync it to GitHub Milestones/Issues via API only (no Projects v2 custom fields), fix the dead `cost_entries.epic_id`/`phase_id` write path, fully backfill history, and drop `roadmap.md`/`todo.md`/`costs.md` from git tracking.

**Architecture:** Four sequential phases, each its own PR except Phase 3 (an operator-triggered run of code merged in Phase 2). Phase 1 is a pure schema+write-path fix with no GitHub dependency. Phase 2 adds a new `synlynk/gh_sync.py` module that renders already-authoritative `state.db` rows onto GitHub Milestones/Issues, keyed by a new `github_sync_map` cache table, and wires it into existing mutation points (`cmd_roadmap_add`, `cmd_roadmap_update`, `cmd_story_done`, `cmd_release`). Phase 3 runs the one-time backfill using Phase 2's code. Phase 4 removes the markdown mirrors from git only after Phase 3's verification gate passes.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `hashlib`, `json`), the project's versioned migration framework (`synlynk/migrations/`), `pytest`, and the existing `synlynk.gh_shim.run_gh()` helper for role-scoped `gh` CLI calls (no new HTTP client).

**Epic:** gh:#2653 · **Release target:** unscheduled (gh:#2653 has no milestone set)

**Spec:** `docs/superpowers/specs/2026-10-29-roadmap-state-db-github-authority-design.md`

---

## Phase 1: Schema Migration + `cost_entries.epic_id` Write-Path Fix

### Task 1: Migration `m0029` — `roadmap_arcs.is_milestone_eligible` + normalization

**Files:**
- Create: `synlynk/migrations/m0029_roadmap_arcs_milestone_eligibility.py`
- Modify: `synlynk/migrations/runner.py`
- Test: `tests/test_migrations_framework.py`

**Context:** `roadmap_arcs` (schema at `synlynk/db.py:1834-1841`: `id, version UNIQUE, title, status, target_date, notes`) has 66 rows today including non-version identifiers (`"Future Expansions"`, `"epic-job-truth-2026-08"`), a range string (`"v0.1–v0.3.0"`), and a likely-duplicate (`"1.0.0"` vs `"v1.0.0"`). Per spec §3.2, add `is_milestone_eligible` (default `true`), flag the three known-bad rows `false`, and collapse the `"1.0.0"` duplicate into `"v1.0.0"` by repointing FK references (`roadmap_phases.arc_version`, `cost_entries.epic_id`) rather than deleting the losing row.

- [ ] **Step 1: Write the failing test**

```python
def test_m0029_adds_is_milestone_eligible_and_normalizes_known_rows(tmp_path):
    import sqlite3
    from synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            title TEXT, status TEXT DEFAULT 'planned',
            target_date TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
            phase_title TEXT NOT NULL, status TEXT DEFAULT 'planned',
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_id INTEGER REFERENCES roadmap_arcs(id)
        )"""
    )
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v1.0.0', 'First release')")
    v1_id = conn.execute("SELECT id FROM roadmap_arcs WHERE version='v1.0.0'").fetchone()[0]
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('1.0.0', 'First release dupe')")
    dupe_id = conn.execute("SELECT id FROM roadmap_arcs WHERE version='1.0.0'").fetchone()[0]
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('Future Expansions', 'placeholder')")
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v0.1–v0.3.0', 'early range')")
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title) VALUES ('1.0.0', 'phase on dupe')"
    )
    conn.execute(
        "INSERT INTO cost_entries (epic_id) VALUES (?)", (dupe_id,)
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    assert "is_milestone_eligible" in cols

    rows = {
        r[0]: r[1]
        for r in conn.execute("SELECT version, is_milestone_eligible FROM roadmap_arcs")
    }
    assert rows["v1.0.0"] == 1
    assert rows["Future Expansions"] == 0
    assert rows["v0.1–v0.3.0"] == 0
    assert "1.0.0" not in rows  # dupe row removed after repointing

    # FK references repointed to the surviving v1.0.0 row.
    assert conn.execute(
        "SELECT arc_version FROM roadmap_phases WHERE phase_title='phase on dupe'"
    ).fetchone()[0] == "v1.0.0"
    assert conn.execute(
        "SELECT epic_id FROM cost_entries"
    ).fetchone()[0] == v1_id

    conn.close()


def test_m0029_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            title TEXT, status TEXT DEFAULT 'planned',
            target_date TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
            phase_title TEXT NOT NULL, status TEXT DEFAULT 'planned',
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_id INTEGER REFERENCES roadmap_arcs(id)
        )"""
    )
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v1.0.0', 'First release')")
    conn.commit()

    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()

    assert conn.execute(
        "SELECT COUNT(*) FROM roadmap_arcs WHERE version='v1.0.0'"
    ).fetchone()[0] == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_framework.py -k m0029 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility'`

- [ ] **Step 3: Write the migration**

```python
"""Migration 29: roadmap_arcs.is_milestone_eligible + known-row normalization.

Flags non-version identifiers and pre-granularity range strings so the
GitHub Milestone sync (gh:#2653 design) never tries to create a Milestone
for them, and collapses the "1.0.0" / "v1.0.0" duplicate by repointing
FK references rather than deleting the losing row's history.
"""
import sqlite3

from synlynk.migrations import Migration

# Known-bad roadmap_arcs.version values that are not real release
# identifiers, flagged non-eligible rather than deleted (editorial calls
# made in the 2026-10-29 design spec, §3.2).
_NOT_MILESTONE_ELIGIBLE = {"Future Expansions", "epic-job-truth-2026-08", "v0.1–v0.3.0"}

# Known duplicate: "1.0.0" predates the "vX.Y.Z" convention and refers to
# the same release as "v1.0.0".
_DUPLICATE_VERSION = "1.0.0"
_CANONICAL_VERSION = "v1.0.0"


def _up(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    if "is_milestone_eligible" not in cols:
        conn.execute(
            "ALTER TABLE roadmap_arcs ADD COLUMN is_milestone_eligible "
            "BOOLEAN NOT NULL DEFAULT 1"
        )

    if _NOT_MILESTONE_ELIGIBLE:
        placeholders = ",".join("?" for _ in _NOT_MILESTONE_ELIGIBLE)
        conn.execute(
            f"UPDATE roadmap_arcs SET is_milestone_eligible = 0 "
            f"WHERE version IN ({placeholders})",
            tuple(_NOT_MILESTONE_ELIGIBLE),
        )

    dupe = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version = ?", (_DUPLICATE_VERSION,)
    ).fetchone()
    canonical = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version = ?", (_CANONICAL_VERSION,)
    ).fetchone()
    if dupe and canonical:
        dupe_id = dupe[0]
        conn.execute(
            "UPDATE roadmap_phases SET arc_version = ? WHERE arc_version = ?",
            (_CANONICAL_VERSION, _DUPLICATE_VERSION),
        )
        conn.execute(
            "UPDATE cost_entries SET epic_id = ? WHERE epic_id = ?",
            (canonical[0], dupe_id),
        )
        conn.execute("DELETE FROM roadmap_arcs WHERE id = ?", (dupe_id,))


MIGRATION = Migration(
    version=29,
    name="roadmap_arcs_milestone_eligibility",
    up=_up,
)
```

- [ ] **Step 4: Register in the runner**

Edit `synlynk/migrations/runner.py`:

```python
from synlynk.migrations.m0028_deprecate_execution_log_models import MIGRATION as M0028
from synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility import MIGRATION as M0029
```

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029,
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_migrations_framework.py -k m0029 -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0029_roadmap_arcs_milestone_eligibility.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat: add roadmap_arcs.is_milestone_eligible + normalize known-bad rows (m0029)"
```

### Task 2: Migration `m0030` — `github_sync_map` table

**Files:**
- Create: `synlynk/migrations/m0030_github_sync_map.py`
- Modify: `synlynk/migrations/runner.py`
- Test: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing test**

```python
def test_m0030_creates_github_sync_map_table(tmp_path):
    import sqlite3
    from synlynk.migrations.m0030_github_sync_map import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(github_sync_map)")}
    assert cols == {
        "entity_type", "entity_id", "github_number", "github_node_id",
        "content_hash", "last_synced_at",
    }

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, content_hash) "
        "VALUES ('roadmap_arc', '7', 42, 'abc123')"
    )
    conn.commit()
    row = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id='7'"
    ).fetchone()
    assert row == (42, "abc123")
    conn.close()


def test_m0030_entity_type_and_id_are_primary_key(tmp_path):
    import sqlite3
    from synlynk.migrations.m0030_github_sync_map import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    MIGRATION.up(conn)
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('story', 'story-abc', 10)"
    )
    conn.commit()
    with __import__("pytest").raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
            "VALUES ('story', 'story-abc', 99)"
        )
    conn.close()


def test_m0030_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0030_github_sync_map import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='github_sync_map'"
    ).fetchone()
    assert row is not None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_framework.py -k m0030 -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the migration**

```python
"""Migration 30: github_sync_map — cache of local-row <-> GitHub-number pairs.

This is a cache of a GitHub-side fact, not a second source of truth for
roadmap/cost data (gh:#2653 design, §3.4): it exists purely so sync runs
don't re-derive GitHub issue/milestone numbers by API search every time.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS github_sync_map (
            entity_type    TEXT NOT NULL,
            entity_id      TEXT NOT NULL,
            github_number  INTEGER NOT NULL,
            github_node_id TEXT,
            content_hash   TEXT,
            last_synced_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (entity_type, entity_id)
        )"""
    )


MIGRATION = Migration(
    version=30,
    name="github_sync_map",
    up=_up,
)
```

- [ ] **Step 4: Register in the runner**

Edit `synlynk/migrations/runner.py`:

```python
from synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility import MIGRATION as M0029
from synlynk.migrations.m0030_github_sync_map import MIGRATION as M0030
```

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029, M0030,
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_migrations_framework.py -k m0030 -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0030_github_sync_map.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat: add github_sync_map cache table (m0030)"
```

### Task 3: `cost_entries.epic_id`/`phase_id` resolution in `_insert_cost_row`

**Files:**
- Modify: `synlynk/db.py:2403` (`_insert_cost_row`)
- Test: `tests/test_cost_entries.py` (create if it doesn't already exist — check first with `ls tests/test_cost_entries.py`)

**Context:** `_insert_cost_row` (`synlynk/db.py:2403-2403+`) already accepts `epic_id`/`phase_id` parameters that every caller passes as `None`. Per spec §3.1, resolve them from `story_id` via `roadmap_phases.story_id → arc_version → roadmap_arcs.id`, following the exact try/except pattern already used two lines above for `role_val` resolution (`synlynk/db.py`, the `role_val is None and story_id` block). When unresolvable, leave `epic_id` NULL and set `estimate_basis = "epic_unresolved"` so unresolved rows are queryable rather than silently absent from rollups.

- [ ] **Step 1: Write the failing test**

```python
def test_insert_cost_row_resolves_epic_id_from_story_phase(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import db

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT UNIQUE)"
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT, phase_title TEXT, status TEXT,
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT,
            harness TEXT, agent_role TEXT, model TEXT, input_tokens INTEGER,
            output_tokens INTEGER, cache_read_tokens INTEGER, story_id TEXT,
            type_id TEXT, epic_id INTEGER, phase_id INTEGER, total_cost_usd REAL,
            api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT, notes TEXT,
            cost_source TEXT, estimate_basis TEXT, job_id TEXT,
            decision_revision INTEGER, recorded_at TEXT, dispatch_context TEXT,
            context_mode TEXT, turn_usage_json TEXT, session_id TEXT, pr_number INTEGER
        )"""
    )
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, role TEXT)"
    )
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, role TEXT, context_mode TEXT, session_id TEXT)")
    conn.execute("CREATE TABLE job_terminal_decision (job_id TEXT, revision INTEGER)")
    conn.execute("INSERT INTO roadmap_arcs (version) VALUES ('v1.0.0')")
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title, story_id) "
        "VALUES ('v1.0.0', 'Core cluster', 'story-abc')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    db._insert_cost_row(
        session_date="2026-10-29",
        agent="claude",
        story_id="story-abc",
        total_cost_usd=1.23,
        cost_source="actual",
    )

    conn = sqlite3.connect(tmp_path / "state.db")
    row = conn.execute(
        "SELECT epic_id, phase_id, estimate_basis FROM cost_entries WHERE story_id='story-abc'"
    ).fetchone()
    arc_id = conn.execute("SELECT id FROM roadmap_arcs WHERE version='v1.0.0'").fetchone()[0]
    phase_id = conn.execute("SELECT id FROM roadmap_phases WHERE story_id='story-abc'").fetchone()[0]
    conn.close()
    assert row == (arc_id, phase_id, None)


def test_insert_cost_row_marks_unresolved_when_no_phase_match(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import db

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT UNIQUE)"
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT, phase_title TEXT, status TEXT,
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT,
            harness TEXT, agent_role TEXT, model TEXT, input_tokens INTEGER,
            output_tokens INTEGER, cache_read_tokens INTEGER, story_id TEXT,
            type_id TEXT, epic_id INTEGER, phase_id INTEGER, total_cost_usd REAL,
            api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT, notes TEXT,
            cost_source TEXT, estimate_basis TEXT, job_id TEXT,
            decision_revision INTEGER, recorded_at TEXT, dispatch_context TEXT,
            context_mode TEXT, turn_usage_json TEXT, session_id TEXT, pr_number INTEGER
        )"""
    )
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, role TEXT)")
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, role TEXT, context_mode TEXT, session_id TEXT)")
    conn.execute("CREATE TABLE job_terminal_decision (job_id TEXT, revision INTEGER)")
    conn.execute("INSERT INTO stories (story_id) VALUES ('story-orphan')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    db._insert_cost_row(
        session_date="2026-10-29",
        agent="claude",
        story_id="story-orphan",
        total_cost_usd=1.0,
        cost_source="actual",
    )

    conn = sqlite3.connect(tmp_path / "state.db")
    row = conn.execute(
        "SELECT epic_id, phase_id, estimate_basis FROM cost_entries WHERE story_id='story-orphan'"
    ).fetchone()
    conn.close()
    assert row == (None, None, "epic_unresolved")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_entries.py -k epic_id -v`
Expected: FAIL — second test's `estimate_basis` assertion fails (currently stays `None`, not `"epic_unresolved"`), since resolution does not exist yet.

- [ ] **Step 3: Implement the resolution chain**

In `synlynk/db.py`, inside `_insert_cost_row`, immediately after the existing `role_val` resolution block (the one reading `"SELECT role FROM stories WHERE story_id=?"`) and before the `context_mode` inheritance block, insert:

```python
        if epic_id is None and phase_id is None and story_id:
            try:
                p_row = conn.execute(
                    "SELECT id, arc_version FROM roadmap_phases WHERE story_id=?",
                    (story_id,),
                ).fetchone()
                if p_row:
                    phase_id = p_row[0]
                    arc_row = conn.execute(
                        "SELECT id FROM roadmap_arcs WHERE version=?",
                        (p_row[1],),
                    ).fetchone()
                    if arc_row:
                        epic_id = arc_row[0]
                elif estimate_basis is None:
                    estimate_basis = "epic_unresolved"
            except sqlite3.Error:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_entries.py -k epic_id -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full cost-entries + migrations suite to check for regressions**

Run: `pytest tests/test_cost_entries.py tests/test_migrations_framework.py -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_cost_entries.py
git commit -m "fix: resolve cost_entries.epic_id/phase_id from story_id at write time"
```

**Phase 1 complete.** This is its own PR per spec §9 rollout order — open it now before starting Phase 2.

---

## Phase 2: Sync Mechanism

### Task 4: `synlynk/gh_sync.py` — module skeleton, content hashing, `gh api` wrapper

**Files:**
- Create: `synlynk/gh_sync.py`
- Test: `tests/test_gh_sync.py`

**Context:** Use the existing `run_gh()` helper (`synlynk/gh_shim.py:171`) for every `gh` call — it already resolves role-scoped tokens and fails closed per the Hardened PR Review Policy. No new HTTP client. Content hashing is `sha256` over the fields that determine rendered content, used to skip no-op `PATCH` calls.

- [ ] **Step 1: Write the failing test**

```python
def test_content_hash_is_stable_for_same_input():
    from synlynk.gh_sync import _content_hash

    a = _content_hash({"title": "v1.0.0", "status": "shipped", "due_on": "2026-01-01"})
    b = _content_hash({"title": "v1.0.0", "status": "shipped", "due_on": "2026-01-01"})
    assert a == b


def test_content_hash_differs_when_input_differs():
    from synlynk.gh_sync import _content_hash

    a = _content_hash({"title": "v1.0.0", "status": "shipped"})
    b = _content_hash({"title": "v1.0.0", "status": "planned"})
    assert a != b


def test_gh_api_json_parses_successful_response(monkeypatch):
    import subprocess
    from synlynk import gh_sync

    def fake_run_gh(args, **kwargs):
        assert args[0] == "api"
        return subprocess.CompletedProcess(args, 0, '[{"number": 1, "title": "v1.0.0"}]', "")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)
    result = gh_sync._gh_api_json(["repos/o/r/milestones", "--paginate"])
    assert result == [{"number": 1, "title": "v1.0.0"}]


def test_gh_api_json_raises_on_nonzero_exit(monkeypatch):
    import subprocess
    import pytest
    from synlynk import gh_sync

    def fake_run_gh(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "refused")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)
    with pytest.raises(RuntimeError, match="refused"):
        gh_sync._gh_api_json(["repos/o/r/milestones"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gh_sync.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.gh_sync'`

- [ ] **Step 3: Write the module skeleton**

```python
"""GitHub-native sync for roadmap/story/decision rows (gh:#2653 design).

Renders already-authoritative state.db rows onto GitHub Milestones/Issues
(Pattern A: core primitives only, no Projects v2 custom fields — see the
design spec's "Why Pattern A, not Pattern B" section). github_sync_map is
a cache of GitHub-side facts, never a second source of truth.
"""
import hashlib
import json
import subprocess

from synlynk.gh_shim import run_gh


def _content_hash(fields: dict) -> str:
    """Stable hash of the fields that determine a synced item's rendered content."""
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gh_api_json(args: list, role: str = "pm", **kwargs):
    """Run `gh api <args>` and parse JSON stdout. Raises RuntimeError on failure."""
    result = run_gh(["api"] + args, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"gh api {args} failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gh_sync.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync.py tests/test_gh_sync.py
git commit -m "feat: gh_sync module skeleton — content hashing + gh api wrapper"
```

### Task 5: Milestone sync for `roadmap_arcs`

**Files:**
- Modify: `synlynk/gh_sync.py`
- Test: `tests/test_gh_sync.py`

**Context:** Per spec §4: one `GET /repos/{owner}/{repo}/milestones?state=all` per sync run, build a `title → milestone` map, check-then-create/update, record in `github_sync_map`. Status mapping: `shipped`/`superseded` → closed, `planned`/`deferred` → open; `deferred`/`superseded` also get a `status:deferred`/`status:superseded` label.

- [ ] **Step 1: Write the failing test**

```python
def test_sync_arc_creates_milestone_when_absent(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1)"
    )
    conn.commit()

    calls = []

    def fake_gh_api_json(args, **kwargs):
        calls.append(args)
        if args[0] == "repos/o/r/milestones" and "--method" not in args:
            return []
        return {"number": 99, "node_id": "MI_abc"}

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")

    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map WHERE entity_type='roadmap_arc' AND entity_id='1'"
    ).fetchone()
    assert mapped == (99,)
    create_calls = [c for c in calls if "--method" in c and "POST" in c]
    assert len(create_calls) == 1
    conn.close()


def test_sync_arc_skips_patch_when_content_hash_unchanged(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1)"
    )
    fields = gh_sync._arc_sync_fields(conn, arc_id=1)
    existing_hash = gh_sync._content_hash(fields)
    conn.execute(
        "INSERT INTO github_sync_map VALUES ('roadmap_arc', '1', 99, 'MI_abc', ?, datetime('now'))",
        (existing_hash,),
    )
    conn.commit()

    calls = []

    def fake_gh_api_json(args, **kwargs):
        calls.append(args)
        return []

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")

    assert calls == []  # no API calls at all — nothing changed
    conn.close()


def test_sync_arc_noop_when_not_milestone_eligible(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (2, 'Future Expansions', NULL, 'planned', NULL, NULL, 0)"
    )
    conn.commit()

    calls = []
    monkeypatch.setattr(gh_sync, "_gh_api_json", lambda args, **kw: calls.append(args))

    gh_sync.sync_arc(conn, arc_id=2, owner="o", repo="r")

    assert calls == []
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gh_sync.py -k sync_arc -v`
Expected: FAIL with `AttributeError: module 'synlynk.gh_sync' has no attribute 'sync_arc'`

- [ ] **Step 3: Implement `sync_arc`**

Append to `synlynk/gh_sync.py`:

```python
_STATUS_LABELS = {"deferred": "status:deferred", "superseded": "status:superseded"}
_CLOSED_STATUSES = {"shipped", "superseded"}


def _render_arc_description(conn, arc_id: int) -> str:
    phases = conn.execute(
        "SELECT phase_title, status FROM roadmap_phases "
        "WHERE arc_version = (SELECT version FROM roadmap_arcs WHERE id=?) "
        "ORDER BY id ASC",
        (arc_id,),
    ).fetchall()
    rollup = _cost_rollup_for_arc(conn, arc_id)
    lines = [f"- [{'x' if status == 'done' else ' '}] {title}" for title, status in phases]
    lines.append("")
    lines.append(
        f"**Cost rollup:** ${rollup['actual_usd']:.2f} actual "
        f"across {rollup['entry_count']} entries "
        f"({rollup['unresolved_count']} unattributed)"
    )
    return "\n".join(lines)


def _arc_sync_fields(conn, arc_id: int) -> dict:
    row = conn.execute(
        "SELECT version, title, status, target_date FROM roadmap_arcs WHERE id=?",
        (arc_id,),
    ).fetchone()
    version, title, status, target_date = row
    return {
        "title": version,
        "state": "closed" if status in _CLOSED_STATUSES else "open",
        "due_on": target_date,
        "description": _render_arc_description(conn, arc_id),
    }


def sync_arc(conn, arc_id: int, owner: str, repo: str, role: str = "pm") -> None:
    row = conn.execute(
        "SELECT version, status, is_milestone_eligible FROM roadmap_arcs WHERE id=?",
        (arc_id,),
    ).fetchone()
    version, status, eligible = row
    if not eligible:
        return

    fields = _arc_sync_fields(conn, arc_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id=?",
        (str(arc_id),),
    ).fetchone()

    if mapped and mapped[1] == new_hash:
        return  # nothing changed since last sync

    payload = {
        "title": fields["title"],
        "state": fields["state"],
        "description": fields["description"],
    }
    if fields["due_on"]:
        payload["due_on"] = f"{fields['due_on']}T00:00:00Z"

    if mapped:
        github_number = mapped[0]
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/milestones/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/milestones", "--method", "POST"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        github_number = result["number"]
        node_id = result.get("node_id")

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('roadmap_arc', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (str(arc_id), github_number, node_id, new_hash),
    )
    conn.commit()

    label = _STATUS_LABELS.get(status)
    if label:
        try:
            _gh_api_json(
                [f"repos/{owner}/{repo}/issues/{github_number}/labels", "--method", "POST", f"-flabels[]={label}"],
                role=role,
            )
        except RuntimeError:
            pass  # Milestones don't support labels directly on all gh versions; best-effort only.


def _cost_rollup_for_arc(conn, arc_id: int) -> dict:
    row = conn.execute(
        "SELECT COALESCE(SUM(actual_usd), 0.0), COUNT(*), "
        "SUM(CASE WHEN estimate_basis='epic_unresolved' THEN 1 ELSE 0 END) "
        "FROM cost_entries WHERE epic_id=?",
        (arc_id,),
    ).fetchone()
    return {
        "actual_usd": row[0] or 0.0,
        "entry_count": row[1] or 0,
        "unresolved_count": row[2] or 0,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gh_sync.py -k sync_arc -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync.py tests/test_gh_sync.py
git commit -m "feat: sync roadmap_arcs to GitHub Milestones (idempotent)"
```

### Task 6: Issue sync for stories and decisions

**Files:**
- Modify: `synlynk/gh_sync.py`
- Test: `tests/test_gh_sync.py`

**Context:** Per spec §4: story/phase → Issue assigned to the release's Milestone, body includes `<!-- synlynk:story_id=story-xxxx -->` footer so matching doesn't depend on title stability. `decisions` row → Issue, no milestone, label `decision`, state from `decisions.status`.

- [ ] **Step 1: Write the failing test**

```python
def test_sync_story_creates_issue_with_footer(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, gh_issue TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO stories VALUES ('story-abc', 'Core cluster', 'open', NULL)"
    )
    conn.commit()

    created = {}

    def fake_gh_api_json(args, **kwargs):
        if "--method" in args and "POST" in args:
            created["args"] = args
            return {"number": 7, "node_id": "I_xyz"}
        return []

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_story(conn, story_id="story-abc", owner="o", repo="r", milestone_number=None)

    body_arg = next(a for a in created["args"] if a.startswith("-fbody="))
    assert "<!-- synlynk:story_id=story-abc -->" in body_arg
    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map WHERE entity_type='story' AND entity_id='story-abc'"
    ).fetchone()
    assert mapped == (7,)
    conn.close()


def test_sync_decision_creates_issue_with_decision_label(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, topic TEXT, status TEXT, "
        "synthesis TEXT, decision_text TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO decisions VALUES ('dec-1', 'Should we X?', 'decided', 'yes because', 'Do X')"
    )
    conn.commit()

    created = {}

    def fake_gh_api_json(args, **kwargs):
        if "--method" in args and "POST" in args:
            created["args"] = args
            return {"number": 12, "node_id": "I_dec"}
        return []

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_decision(conn, decision_id="dec-1", owner="o", repo="r")

    assert "-flabels[]=decision" in created["args"]
    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map WHERE entity_type='decision' AND entity_id='dec-1'"
    ).fetchone()
    assert mapped == (12,)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gh_sync.py -k "sync_story or sync_decision" -v`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement `sync_story` and `sync_decision`**

Append to `synlynk/gh_sync.py`:

```python
def _story_sync_fields(conn, story_id: str) -> dict:
    row = conn.execute(
        "SELECT title, status FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    title, status = row
    body = (
        f"{title or story_id}\n\n"
        f"<!-- synlynk:story_id={story_id} -->"
    )
    return {"title": title or story_id, "state": "closed" if status == "done" else "open", "body": body}


def sync_story(conn, story_id: str, owner: str, repo: str, milestone_number: int | None, role: str = "pm") -> None:
    fields = _story_sync_fields(conn, story_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='story' AND entity_id=?",
        (story_id,),
    ).fetchone()
    if mapped and mapped[1] == new_hash:
        return

    payload = {"title": fields["title"], "state": fields["state"], "body": fields["body"]}
    if milestone_number is not None:
        payload["milestone"] = milestone_number

    if mapped:
        github_number = mapped[0]
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues", "--method", "POST"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        github_number = result["number"]
        node_id = result.get("node_id")
        conn.execute(
            "UPDATE stories SET gh_issue=? WHERE story_id=?", (str(github_number), story_id)
        )

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('story', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (story_id, github_number, node_id, new_hash),
    )
    conn.commit()


def _decision_sync_fields(conn, decision_id: str) -> dict:
    row = conn.execute(
        "SELECT topic, status, synthesis, decision_text FROM decisions WHERE decision_id=?",
        (decision_id,),
    ).fetchone()
    topic, status, synthesis, decision_text = row
    body = (
        f"**Synthesis:** {synthesis}\n\n**Decision:** {decision_text}\n\n"
        f"<!-- synlynk:decision_id={decision_id} -->"
    )
    return {"title": topic, "state": "closed" if status == "decided" else "open", "body": body}


def sync_decision(conn, decision_id: str, owner: str, repo: str, role: str = "pm") -> None:
    fields = _decision_sync_fields(conn, decision_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='decision' AND entity_id=?",
        (decision_id,),
    ).fetchone()
    if mapped and mapped[1] == new_hash:
        return

    payload = {"title": fields["title"], "state": fields["state"], "body": fields["body"], "labels[]": "decision"}

    if mapped:
        github_number = mapped[0]
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues", "--method", "POST"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        github_number = result["number"]
        node_id = result.get("node_id")

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('decision', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (decision_id, github_number, node_id, new_hash),
    )
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gh_sync.py -k "sync_story or sync_decision" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync.py tests/test_gh_sync.py
git commit -m "feat: sync stories and decisions to GitHub Issues (idempotent)"
```

### Task 7: `synlynk gh sync-roadmap [--dry-run] [--backfill]` CLI command

**Files:**
- Create: `synlynk/gh_sync_cli.py`
- Modify: `synlynk/cli.py` (gh dispatch block, ~`synlynk/cli.py:2511`)
- Test: `tests/test_gh_sync_cli.py`

**Context:** `gh_parser` (`synlynk/cli.py:995-1016`) captures everything after `synlynk gh` as `gh_args` via `nargs=argparse.REMAINDER` and passes it straight to `cmd_gh()`, which execs the real `gh` binary. `sync-roadmap` must be intercepted *before* that pass-through, in the `elif args.command == "gh":` dispatch block (`synlynk/cli.py:2511-2520`).

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_sync_roadmap_dry_run_does_not_write_sync_map(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync_cli, gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1)"
    )
    conn.commit()
    conn.close()

    calls = []
    monkeypatch.setattr(gh_sync, "sync_arc", lambda *a, **kw: calls.append(("sync_arc", a, kw)))
    monkeypatch.setattr(gh_sync_cli, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    gh_sync_cli.cmd_sync_roadmap(dry_run=True, backfill=False, owner="o", repo="r")

    assert calls == []  # dry-run never calls the real sync functions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gh_sync_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.gh_sync_cli'`

- [ ] **Step 3: Implement `cmd_sync_roadmap`**

```python
"""CLI entry point for `synlynk gh sync-roadmap`."""
from synlynk import _get_db


def cmd_sync_roadmap(dry_run: bool, backfill: bool, owner: str, repo: str, role: str = "pm") -> None:
    from synlynk import gh_sync

    conn = _get_db()
    try:
        eligible_ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM roadmap_arcs WHERE is_milestone_eligible = 1 ORDER BY id ASC"
            ).fetchall()
        ]
        if dry_run:
            print(f"  [dry-run] would sync {len(eligible_ids)} milestone-eligible roadmap_arcs rows")
            if backfill:
                story_count = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
                decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
                print(f"  [dry-run] would backfill {story_count} stories, {decision_count} decisions")
            return

        for arc_id in eligible_ids:
            gh_sync.sync_arc(conn, arc_id=arc_id, owner=owner, repo=repo, role=role)

        if backfill:
            from synlynk.gh_sync_backfill import run_backfill
            run_backfill(conn, owner=owner, repo=repo, role=role)
    finally:
        conn.close()
    print("  ✓ sync-roadmap complete")
```

- [ ] **Step 4: Wire the CLI dispatch**

Edit `synlynk/cli.py`, inside `elif args.command == "gh":` (~line 2511), before the existing `sys.exit(cmd_gh(...))` fallback:

```python
    elif args.command == "gh":
        from synlynk.gh_role import cmd_gh
        if getattr(args, "shim_env", False) or getattr(args, "shim_install", False):
            from synlynk import gh_shim
            if getattr(args, "shim_env", False):
                print(gh_shim.shim_env())
            else:
                print(f"Installed gh shim in {gh_shim.install_shim()}")
            sys.exit(0)
        gh_args = getattr(args, "gh_args", []) or []
        if gh_args and gh_args[0] == "sync-roadmap":
            from synlynk.gh_sync_cli import cmd_sync_roadmap
            import subprocess
            remote = subprocess.run(
                ["gh", "repo", "view", "--json", "owner,name"],
                capture_output=True, text=True,
            )
            import json as _json
            repo_info = _json.loads(remote.stdout)
            cmd_sync_roadmap(
                dry_run="--dry-run" in gh_args,
                backfill="--backfill" in gh_args,
                owner=repo_info["owner"]["login"],
                repo=repo_info["name"],
                role=args.role or "pm",
            )
            sys.exit(0)
        sys.exit(cmd_gh(args.role, gh_args))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_gh_sync_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/gh_sync_cli.py synlynk/cli.py tests/test_gh_sync_cli.py
git commit -m "feat: synlynk gh sync-roadmap [--dry-run] [--backfill] command"
```

### Task 8: Wire inline sync into `cmd_roadmap_add`, `cmd_roadmap_update`, `cmd_story_done`

**Files:**
- Modify: `synlynk/db.py:4047-4102` (`cmd_roadmap_add`), `synlynk/db.py:4104-4188` (`cmd_roadmap_update`), `synlynk/db.py:4309-4354` (`cmd_story_done`)
- Test: `tests/test_roadmap_commands.py` (create if it doesn't already exist — check first)

**Context:** Per spec §4 trigger points: sync the affected arc/story "same place `roadmap.md` regeneration happens today." Each of the three functions already calls `_generate_roadmap_md()` at a specific point — add a best-effort sync call immediately after it, wrapped so a GitHub-side failure (offline, rate-limited, no token) never blocks the local mutation that already succeeded.

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_roadmap_add_triggers_arc_sync(tmp_path, monkeypatch):
    from synlynk import db

    sync_calls = []
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: None)
    monkeypatch.setattr(db, "_try_sync_arc_by_version", lambda version: sync_calls.append(version))
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: type("A", (), {"allowed": True})())

    import sqlite3
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT)"
    )
    conn.execute("CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
                  "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    db.cmd_roadmap_add(version="v2.0.0", title="Second release")

    assert sync_calls == ["v2.0.0"]


def test_cmd_roadmap_add_does_not_raise_when_sync_fails(tmp_path, monkeypatch):
    from synlynk import db

    def failing_sync(version):
        raise RuntimeError("gh api down")

    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: None)
    monkeypatch.setattr(db, "_try_sync_arc_by_version", failing_sync)
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: type("A", (), {"allowed": True})())

    import sqlite3
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT)"
    )
    conn.execute("CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
                  "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    db.cmd_roadmap_add(version="v2.0.0", title="Second release")  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roadmap_commands.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.db' has no attribute '_try_sync_arc_by_version'`

- [ ] **Step 3: Implement `_try_sync_arc_by_version` and `_try_sync_story`, wire them in**

Add to `synlynk/db.py` near `_generate_roadmap_md` (~line 3533):

```python
def _try_sync_arc_by_version(version: str) -> None:
    """Best-effort GitHub Milestone sync. Never raises — a GitHub-side
    failure must not block the local roadmap mutation that already
    committed successfully."""
    from synlynk import _get_db
    from synlynk.gh_sync import sync_arc
    from synlynk.github_repo import resolve_owner_repo

    try:
        owner, repo = resolve_owner_repo()
    except Exception:
        return
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM roadmap_arcs WHERE version=?", (version,)).fetchone()
        if row:
            sync_arc(conn, arc_id=row[0], owner=owner, repo=repo)
    except Exception:
        pass
    finally:
        conn.close()


def _try_sync_story(story_id: str) -> None:
    """Best-effort GitHub Issue sync for a single story. Never raises."""
    from synlynk import _get_db
    from synlynk.gh_sync import sync_story
    from synlynk.github_repo import resolve_owner_repo

    try:
        owner, repo = resolve_owner_repo()
    except Exception:
        return
    conn = _get_db()
    try:
        phase = conn.execute(
            "SELECT arc_version FROM roadmap_phases WHERE story_id=?", (story_id,)
        ).fetchone()
        milestone_number = None
        if phase:
            mapped = conn.execute(
                "SELECT gm.github_number FROM github_sync_map gm "
                "JOIN roadmap_arcs ra ON ra.id = CAST(gm.entity_id AS INTEGER) "
                "WHERE gm.entity_type='roadmap_arc' AND ra.version=?",
                (phase[0],),
            ).fetchone()
            milestone_number = mapped[0] if mapped else None
        sync_story(conn, story_id=story_id, owner=owner, repo=repo, milestone_number=milestone_number)
    except Exception:
        pass
    finally:
        conn.close()
```

Create a small new module `synlynk/github_repo.py` (the owner/repo resolution is needed by both the CLI command in Task 7 and these inline hooks — factor it out instead of duplicating the `gh repo view` subprocess call):

```python
"""Resolve the current repo's owner/name for gh_sync calls."""
import json
import subprocess


def resolve_owner_repo() -> tuple[str, str]:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh repo view failed: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    return info["owner"]["login"], info["name"]
```

Simplify Task 7's CLI wiring in `synlynk/cli.py` to reuse this instead of inlining the subprocess call:

```python
        if gh_args and gh_args[0] == "sync-roadmap":
            from synlynk.gh_sync_cli import cmd_sync_roadmap
            from synlynk.github_repo import resolve_owner_repo
            owner, repo = resolve_owner_repo()
            cmd_sync_roadmap(
                dry_run="--dry-run" in gh_args,
                backfill="--backfill" in gh_args,
                owner=owner,
                repo=repo,
                role=args.role or "pm",
            )
            sys.exit(0)
```

Now wire the three call sites. In `cmd_roadmap_add` (`synlynk/db.py`, end of function):

```python
    _generate_roadmap_md()
    _try_sync_arc_by_version(version)
    label = phase_title if phase_title else (title or version)
    print(f"  {_GREEN}✓{_RESET} Roadmap updated — {version}: {label}")
```

In `cmd_roadmap_update` (end of function):

```python
    _generate_roadmap_md()
    _try_sync_arc_by_version(new_arc)
    print(f"  {_GREEN}✓{_RESET} Roadmap phase updated — ID {row[0]} ({new_arc}): {new_title}")
```

In `cmd_story_done`, right after the existing conditional `_generate_roadmap_md()` call:

```python
    if phase_result.rowcount:
        _generate_roadmap_md()
    _try_sync_story(story_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_roadmap_commands.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full roadmap/story/db test files to check for regressions**

Run: `pytest tests/test_roadmap_commands.py tests/test_gh_sync.py tests/test_cost_entries.py -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/github_repo.py synlynk/cli.py tests/test_roadmap_commands.py
git commit -m "feat: wire inline GitHub sync into roadmap add/update and story done"
```

### Task 9: Wire Milestone close into `synlynk release` checklist

**Files:**
- Modify: `synlynk/__init__.py` (`cmd_release`, ~line 2837-3148)
- Test: `tests/test_release_checklist.py` (create if it doesn't already exist — check first)

**Context:** `cmd_release`'s checklist (`synlynk/__init__.py`, tail of the function around line 3100-3148) prints `[ ] gh release create v{next_version}` and `[ ] Roadmap row marked shipped` as manual, unchecked lines. Replace the roadmap-row line with an automated call that flips the arc's `status` to `shipped` and syncs the Milestone closed — leave `gh release create` itself manual (out of scope per spec §7: "Any change to the actual release process beyond wiring Milestone create/close").

- [ ] **Step 1: Write the failing test**

First, read the exact surrounding lines to confirm the current checklist text before patching:

Run: `grep -n "Roadmap row marked shipped" synlynk/__init__.py`

```python
def test_release_checklist_marks_roadmap_arc_shipped(tmp_path, monkeypatch):
    from synlynk import __init__ as synlynk_init

    sync_calls = []
    monkeypatch.setattr(synlynk_init, "_try_sync_arc_by_version", lambda v: sync_calls.append(v))

    import sqlite3
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT)"
    )
    conn.execute("INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First', 'planned', NULL, NULL)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(synlynk_init, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    synlynk_init._mark_roadmap_arc_shipped("v1.0.0")

    conn = sqlite3.connect(tmp_path / "state.db")
    status = conn.execute("SELECT status FROM roadmap_arcs WHERE version='v1.0.0'").fetchone()[0]
    conn.close()
    assert status == "shipped"
    assert sync_calls == ["v1.0.0"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_release_checklist.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.__init__' has no attribute '_mark_roadmap_arc_shipped'`

- [ ] **Step 3: Implement `_mark_roadmap_arc_shipped` and call it from the checklist**

Add near `cmd_release` in `synlynk/__init__.py`:

```python
def _mark_roadmap_arc_shipped(version: str) -> None:
    """Flip a roadmap_arcs row to shipped and sync its Milestone closed.
    Replaces the manual '[ ] Roadmap row marked shipped' checklist step."""
    from synlynk.db import _try_sync_arc_by_version

    conn = _get_db()
    try:
        conn.execute(
            "UPDATE roadmap_arcs SET status='shipped' WHERE version=?", (version,)
        )
        conn.commit()
    finally:
        conn.close()
    _try_sync_arc_by_version(version)
```

Then, at the exact checklist line found by the grep in Step 1 (replace the `[ ] Roadmap row marked shipped` print with a call before it prints the surrounding checklist block):

```python
    _mark_roadmap_arc_shipped(next_version)
    print(f"  [x] Roadmap row marked shipped and Milestone closed — {next_version}")
```

(Leave the adjacent `[ ] gh release create v{next_version}` line untouched — that step stays manual per spec §7.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_release_checklist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_release_checklist.py
git commit -m "feat: synlynk release automatically marks roadmap arc shipped + closes Milestone"
```

**Phase 2 complete.** Open this as its own PR per spec §9.

---

## Phase 3: Backfill Run

### Task 10: `run_backfill` — full historical sync (operator-triggered, code merged now)

**Files:**
- Create: `synlynk/gh_sync_backfill.py`
- Test: `tests/test_gh_sync_backfill.py`

**Context:** Implements spec §5's five ordered steps. Per the user's explicit instruction, backfill is unconditional — every story across every arc, regardless of status, no skip rule, no volume cap. Normalization (§3.2) already ran as part of migration `m0029` (Task 1), so step 1 here is a verification check, not a re-run.

- [ ] **Step 1: Write the failing test**

```python
def test_run_backfill_syncs_every_arc_story_and_decision(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import gh_sync_backfill

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, gh_issue TEXT)")
    conn.execute("CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, topic TEXT, status TEXT, "
                  "synthesis TEXT, decision_text TEXT)")
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute("INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First', 'shipped', NULL, NULL, 1)")
    conn.execute("INSERT INTO roadmap_arcs VALUES (2, 'Future Expansions', NULL, 'planned', NULL, NULL, 0)")
    conn.execute("INSERT INTO stories VALUES ('story-a', 'A', 'done', NULL)")
    conn.execute("INSERT INTO stories VALUES ('story-b', 'B', 'open', '42')")
    conn.execute("INSERT INTO decisions VALUES ('dec-1', 'Topic', 'decided', 'syn', 'text')")
    conn.commit()

    arc_calls, story_calls, decision_calls = [], [], []
    monkeypatch.setattr(gh_sync_backfill.gh_sync, "sync_arc", lambda conn, arc_id, **kw: arc_calls.append(arc_id))
    monkeypatch.setattr(gh_sync_backfill.gh_sync, "sync_story", lambda conn, story_id, **kw: story_calls.append(story_id))
    monkeypatch.setattr(gh_sync_backfill.gh_sync, "sync_decision", lambda conn, decision_id, **kw: decision_calls.append(decision_id))

    gh_sync_backfill.run_backfill(conn, owner="o", repo="r")

    assert arc_calls == [1]  # arc 2 is not milestone-eligible, skipped
    assert sorted(story_calls) == ["story-a", "story-b"]  # every story, regardless of status/gh_issue
    assert decision_calls == ["dec-1"]
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gh_sync_backfill.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.gh_sync_backfill'`

- [ ] **Step 3: Implement `run_backfill`**

```python
"""One-time full-history backfill to GitHub (gh:#2653 design, §5).

Backfill is unconditional: every story across every arc regardless of
status, no skip rule, no volume cap — explicit user instruction overriding
an earlier draft that proposed skipping old shipped-arc stories.
"""
from synlynk import gh_sync


def run_backfill(conn, owner: str, repo: str, role: str = "pm") -> dict:
    arc_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM roadmap_arcs WHERE is_milestone_eligible = 1 ORDER BY id ASC"
        ).fetchall()
    ]
    for arc_id in arc_ids:
        gh_sync.sync_arc(conn, arc_id=arc_id, owner=owner, repo=repo, role=role)

    story_ids = [r[0] for r in conn.execute("SELECT story_id FROM stories ORDER BY story_id ASC").fetchall()]
    for story_id in story_ids:
        phase = conn.execute(
            "SELECT arc_version FROM roadmap_phases WHERE story_id=?", (story_id,)
        ).fetchone()
        milestone_number = None
        if phase:
            mapped = conn.execute(
                "SELECT gm.github_number FROM github_sync_map gm "
                "JOIN roadmap_arcs ra ON ra.id = CAST(gm.entity_id AS INTEGER) "
                "WHERE gm.entity_type='roadmap_arc' AND ra.version=?",
                (phase[0],),
            ).fetchone()
            milestone_number = mapped[0] if mapped else None
        gh_sync.sync_story(conn, story_id=story_id, owner=owner, repo=repo, milestone_number=milestone_number, role=role)

    decision_ids = [r[0] for r in conn.execute("SELECT decision_id FROM decisions ORDER BY decision_id ASC").fetchall()]
    for decision_id in decision_ids:
        gh_sync.sync_decision(conn, decision_id=decision_id, owner=owner, repo=repo, role=role)

    return {
        "arcs_synced": len(arc_ids),
        "stories_synced": len(story_ids),
        "decisions_synced": len(decision_ids),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gh_sync_backfill.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync_backfill.py tests/test_gh_sync_backfill.py
git commit -m "feat: run_backfill — full unconditional historical sync to GitHub"
```

**Phase 3 code is merged as part of Phase 2's PR work above** (it has no independent schema dependency and is fully unit-testable with mocks). Per spec §9, the *execution* of this code against the real repo happens after merge, as an operator-triggered run — not a PR by itself:

```bash
synlynk gh sync-roadmap --backfill --dry-run   # review proposed changes first
synlynk gh sync-roadmap --backfill             # then execute
```

After running, perform the spec §5 verification gate manually before proceeding to Phase 4:
- Spot-check N=5 most-recent `shipped` milestones' `closed_at` against `git log` release-commit dates.
- Confirm the Milestone-rendered cost rollup for the v0.26.x arcs matches a direct `cost_entries` query for the same `epic_id`s.

---

## Phase 4: Drop `roadmap.md`/`todo.md`/`costs.md` From Git Tracking

**Do not start this phase until the Phase 3 verification gate above has passed against the real repo.**

### Task 11: Untrack the generated markdown files

**Files:**
- Modify: `.gitignore`
- Modify: `.gitattributes`
- Modify: `CLAUDE.md` (Merge strategy note)
- Delete (from git index only, not disk): `project-docs/roadmap.md`, `project-docs/todo.md`, `project-docs/costs.md`

**Context:** `_generate_roadmap_md`, `_generate_todo_md`, `_generate_costs_md` (`synlynk/db.py:3286`, `:3533`, `:3576`) keep running on-demand — they're how `state.db` gets rendered locally or in CI. Only the committed copies go away. `.gitattributes` currently declares `merge=union` for `project-docs/todo.md` and `project-docs/costs.md` (devlogs keep their union merge — they stay git-tracked, out of scope here) — that attribute is moot once the files are untracked and should be removed to avoid a stale, misleading entry.

- [ ] **Step 1: Confirm current tracked state**

Run: `git ls-files project-docs/roadmap.md project-docs/todo.md project-docs/costs.md`
Expected: all three paths listed (confirms they are currently tracked, matching the plan's premise)

- [ ] **Step 2: Untrack the files**

```bash
git rm --cached project-docs/roadmap.md project-docs/todo.md project-docs/costs.md
```

- [ ] **Step 3: Add them to `.gitignore`**

Append to `.gitignore`:

```
# Generated from state.db — rendered on demand via `synlynk roadmap`/`synlynk cost log`
# commands or `synlynk gh sync-roadmap`. state.db is sole authority (gh:#2653).
project-docs/roadmap.md
project-docs/todo.md
project-docs/costs.md
```

- [ ] **Step 4: Remove the now-moot `.gitattributes` entries**

Edit `.gitattributes`, remove these two lines (keep the devlogs line and the comment block, since devlogs remain git-tracked):

```
project-docs/todo.md merge=union
project-docs/costs.md merge=union
```

- [ ] **Step 5: Update the CLAUDE.md note describing this behavior**

In `CLAUDE.md`, find the "Merge strategy for high-churn project-docs (issue #379)" paragraph and replace it with:

```markdown
**roadmap/todo/costs authority (gh:#2653, 2026-10-29):** `project-docs/roadmap.md`,
`todo.md`, and `costs.md` are no longer git-tracked. `state.db` is sole authority;
GitHub Milestones/Issues are the shareable projection (synced via `synlynk gh
sync-roadmap`). Render a local copy on demand with the existing `synlynk roadmap`/
`synlynk cost log` commands — do not hand-edit or commit the output.
Decisions and devlogs remain git-tracked; root `.gitattributes` keeps `merge=union`
on `project-docs/devlogs/*.md` for concurrent-append safety.
```

- [ ] **Step 6: Verify the generators still work on demand (not CI-covered, manual spot check)**

Run: `python3 bin/synlynk.py roadmap add --version v0.0.0-test --title "plan verification"`
Expected: command succeeds, prints the roadmap-updated confirmation, and `project-docs/roadmap.md` is rewritten on disk but shows as untracked/ignored in `git status` (not staged for commit)

Then clean up the test row:
Run: `sqlite3 ~/.synlynk/workspaces/<slug>/state.db "DELETE FROM roadmap_arcs WHERE version='v0.0.0-test'"` (confirm the correct workspace slug via `synlynk status` first — do not guess the path)

- [ ] **Step 7: Commit**

```bash
git add .gitignore .gitattributes CLAUDE.md
git commit -m "chore: drop roadmap.md/todo.md/costs.md from git tracking (gh:#2653)

state.db is sole authority; GitHub Milestones/Issues (synced via
synlynk gh sync-roadmap) are the shareable projection. Files remain
available as local, on-demand, generated-not-committed output."
```

**Phase 4 complete.** This is its own PR per spec §9, opened only after the Phase 3 verification gate has passed in the real repo.

---

## Self-Review Notes

- **Spec coverage:** §1 (problem) — addressed by Phase 1's premise correction already in the committed spec, no separate task needed. §2.1 (drop markdown) — Task 11. §2.2 (Milestone/Issue sync, Pattern A) — Tasks 4-6. §2.3 (`epic_id` required fix) — Task 3. §2.4 (normalize `roadmap_arcs`) — Task 1. §2.5 (devlog protocol extension) — intentionally a CLAUDE.md-only process note per spec §6 ("no new mechanism"); not a code task, folded into Task 11 Step 5's doc update scope note rather than a separate task, since the spec is explicit that no new mechanism is being built. §2.6 (decisions backfill) — Task 10. §3.4 (`github_sync_map`) — Task 2. §4 (trigger points) — Tasks 7-9. §5 (backfill order + verification gate) — Task 10 + the manual gate documented after it. §8 (testing) — every task has unit tests; the spec's "integration test against a real test-org repo" is explicitly manual/non-CI per spec §8, matching the Phase 3 operator-run framing.
- **Placeholder scan:** no TBD/TODO markers; every step has runnable code and exact commands.
- **Type consistency:** `sync_arc(conn, arc_id, owner, repo, role="pm")`, `sync_story(conn, story_id, owner, repo, milestone_number, role="pm")`, `sync_decision(conn, decision_id, owner, repo, role="pm")` signatures are introduced in Tasks 5-6 and reused identically in Tasks 8-10 — checked for drift, none found.
