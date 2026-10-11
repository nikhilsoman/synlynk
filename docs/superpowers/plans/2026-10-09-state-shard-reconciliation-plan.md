# State Shard Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the residual `_project_root()` fallback gap that can mint stray legacy shards, and extend `synlynk state inventory` with row counts, staleness, project-fingerprint matching, and a safe dry-run-first `--reconcile` mode, so gh:#1831's orphaned-story-data (e.g. the 975-row `13267207` shard) can be recovered without bulk-deleting anything.

**Architecture:** `synlynk/__init__.py:_project_root()` gets a hardened exception path (raise unless an explicit env override is set). `synlynk/state_inventory.py` gains three new functions (`_match_project`, `_reconcile_plan`, and extensions to `inventory()`) plus CLI wiring in `synlynk/cli.py` for `--reconcile`, `--apply`, `--cutoff-days`, and `--ignore-conflicts` on the existing `state inventory` subcommand.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `argparse`, `pathlib`, `shutil`, `hashlib`) — no new dependencies, matching the rest of the `synlynk` package.

---

## Task 1: Harden `_project_root()`'s silent `getcwd()` fallback

**Files:**
- Modify: `synlynk/__init__.py:265-278`
- Test: `tests/test_project_root_hardening.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_project_root_hardening.py
import subprocess
import pytest

import synlynk


def test_project_root_raises_when_git_resolution_fails(monkeypatch):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0] if args else ["git"])

    monkeypatch.setattr(subprocess, "check_output", _raise)
    monkeypatch.delenv("SYNLYNK_ALLOW_CWD_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="git-common-dir"):
        synlynk._project_root()


def test_project_root_falls_back_to_cwd_with_explicit_override(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0] if args else ["git"])

    monkeypatch.setattr(subprocess, "check_output", _raise)
    monkeypatch.setenv("SYNLYNK_ALLOW_CWD_FALLBACK", "1")
    monkeypatch.chdir(tmp_path)

    assert synlynk._project_root() == str(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_project_root_hardening.py -v`
Expected: both tests FAIL — the first because no `RuntimeError` is raised (current code silently returns `os.getcwd()`), the second because `SYNLYNK_ALLOW_CWD_FALLBACK` isn't read at all yet.

- [ ] **Step 3: Implement the hardened fallback**

Replace `synlynk/__init__.py:265-278` with:

```python
def _project_root() -> str:
    """Return the shared repo root for the current git worktree.

    Raises RuntimeError if git-common-dir resolution fails, unless
    SYNLYNK_ALLOW_CWD_FALLBACK=1 is set (see gh:#1831 — a silent CWD
    fallback here previously minted duplicate per-directory legacy
    state.db shards for the same project).
    """
    import subprocess

    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if common:
            return os.path.abspath(os.path.join(common, ".."))
    except Exception as exc:
        if os.environ.get("SYNLYNK_ALLOW_CWD_FALLBACK") == "1":
            return os.getcwd()
        raise RuntimeError(
            "could not resolve git-common-dir; refusing to silently fall back "
            "to the current working directory (this previously minted stray "
            "per-directory state shards — see gh:#1831). Set "
            "SYNLYNK_ALLOW_CWD_FALLBACK=1 to override."
        ) from exc
    return os.getcwd()
```

Note: the `if common:` / final `return os.getcwd()` path (empty-but-successful git output, no exception) is unchanged — only the `except` branch gains the raise/override behavior.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_project_root_hardening.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the existing `_project_root` callers' tests to check for regressions**

Run: `python3 -m pytest tests/test_control_plane_daemon_health.py tests/test_generated_docs_lock.py tests/test_migrate.py -v`
Expected: PASS — these tests all mock/patch `synlynk._project_root` directly or run inside a real git checkout, so git resolution succeeds and the hardened path is never exercised by them.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_project_root_hardening.py
git commit -m "fix(state): raise instead of silently falling back to getcwd() in _project_root()

A bare except-Exception-pass previously let _project_root() silently
return os.getcwd() on any git-common-dir resolution failure, which is
the root cause gh:#1831 traces for stray per-directory legacy state
shards (13267207, d8a234b7). Now raises RuntimeError unless an
explicit SYNLYNK_ALLOW_CWD_FALLBACK=1 override is set."
```

---

## Task 2: Extend `inventory()` with row counts and staleness

**Files:**
- Modify: `synlynk/state_inventory.py:34-86`
- Test: `tests/test_state_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_state_inventory.py`:

```python
import time


def test_inventory_reports_row_count_and_staleness(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s-1', 'Example story')")
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s-2', 'Another story')")
    conn.commit()
    conn.close()

    rows = inventory(repo)

    assert len(rows) == 1
    assert rows[0]["row_count"] == 2
    assert "mtime_iso" in rows[0]
    assert rows[0]["staleness_days"] >= 0


def test_inventory_row_count_zero_when_no_stories_table(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample (value TEXT)")
    conn.commit()
    conn.close()

    rows = inventory(repo)

    assert rows[0]["row_count"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_state_inventory.py -v`
Expected: FAIL with `KeyError: 'row_count'` (field doesn't exist yet)

- [ ] **Step 3: Implement row_count/mtime_iso/staleness_days**

Modify `synlynk/state_inventory.py`. Add near the top-level imports:

```python
import datetime
```

Add a new helper after `_metadata()` (after line 57):

```python
def _row_count(path: Path) -> int | None:
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "stories" not in tables:
                return None
            return conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None
```

Modify the loop body inside `inventory()` (replace the existing `item.update(_metadata(path))` line and the lines around it):

```python
    for path in sorted(p for p in paths if p.is_file()):
        mtime = path.stat().st_mtime
        mtime_dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        staleness_days = (datetime.datetime.now(tz=datetime.timezone.utc) - mtime_dt).days
        item = {
            "path": str(path),
            "class": _classify(path, repo),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "sidecars": {suffix: Path(f"{path}{suffix}").is_file() for suffix in ("-wal", "-shm", "-journal")},
            "row_count": _row_count(path),
            "mtime_iso": mtime_dt.isoformat(),
            "staleness_days": staleness_days,
        }
        item.update(_metadata(path))
        rows.append(item)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_state_inventory.py -v`
Expected: PASS (all tests in the file, including the pre-existing `test_inventory_is_read_only_and_classifies_repo_artifact`)

- [ ] **Step 5: Commit**

```bash
git add synlynk/state_inventory.py tests/test_state_inventory.py
git commit -m "feat(state): add row_count/mtime_iso/staleness_days to state inventory

Per the 2026-10-09 state-shard-reconciliation design: lets an
operator see, for every legacy shard, how much real story data it
holds and how stale it is, without opening sqlite3 by hand."
```

---

## Task 3: Add `_match_project()` for fingerprint + heuristic project matching

**Files:**
- Modify: `synlynk/state_inventory.py`
- Test: `tests/test_state_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_state_inventory.py`:

```python
def _make_db_with_identity(path, product_id, stories=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE state_identity (
            product_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            canonical_path TEXT NOT NULL,
            lineage_generation INTEGER NOT NULL DEFAULT 1,
            source_sha256 TEXT,
            bootstrapped_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO state_identity(product_id, mode, canonical_path) VALUES (?, 'canonical', ?)",
        (product_id, str(path)),
    )
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    for story_id, title, gh_issue in stories:
        conn.execute(
            "INSERT INTO stories (story_id, title, gh_issue) VALUES (?, ?, ?)",
            (story_id, title, gh_issue),
        )
    conn.commit()
    conn.close()


def test_match_project_exact_fingerprint(tmp_path):
    from synlynk.state_inventory import _match_project

    workspaces_root = tmp_path / "workspaces"
    canonical_db = workspaces_root / "myproj" / "state.db"
    _make_db_with_identity(canonical_db, "prod-abc123")

    legacy_db = tmp_path / "legacy" / "state.db"
    _make_db_with_identity(legacy_db, "prod-abc123")

    match = _match_project(legacy_db, workspaces_root)

    assert match["slug"] == "myproj"
    assert match["method"] == "fingerprint"
    assert match["confidence"] == "exact"


def test_match_project_heuristic_fallback(tmp_path):
    from synlynk.state_inventory import _match_project

    workspaces_root = tmp_path / "workspaces"
    canonical_db = workspaces_root / "synlynk" / "state.db"
    _make_db_with_identity(
        canonical_db, "prod-xyz",
        stories=[("s-1", "feat(workspace): add product repo registration", "#2101")],
    )

    legacy_db = tmp_path / "legacy" / "state.db"
    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, gh_issue) VALUES "
        "('legacy-1', 'feat(workspace): add product repo registration', '#2101')"
    )
    conn.commit()
    conn.close()

    match = _match_project(legacy_db, workspaces_root)

    assert match["slug"] == "synlynk"
    assert match["method"] == "heuristic"
    assert match["confidence"] == "heuristic"


def test_match_project_no_match(tmp_path):
    from synlynk.state_inventory import _match_project

    workspaces_root = tmp_path / "workspaces"
    canonical_db = workspaces_root / "other" / "state.db"
    _make_db_with_identity(
        canonical_db, "prod-other",
        stories=[("s-1", "completely unrelated story about widgets", None)],
    )

    legacy_db = tmp_path / "legacy" / "state.db"
    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, gh_issue) VALUES "
        "('legacy-1', 'nothing in common with anything', NULL)"
    )
    conn.commit()
    conn.close()

    match = _match_project(legacy_db, workspaces_root)

    assert match["slug"] is None
    assert match["method"] == "none"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_state_inventory.py -k match_project -v`
Expected: FAIL with `ImportError: cannot import name '_match_project'`

- [ ] **Step 3: Implement `_match_project()`**

Add to `synlynk/state_inventory.py`, after `_row_count()`:

```python
def _identity_product_id(path: Path) -> str | None:
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "state_identity" not in tables:
                return None
            row = conn.execute("SELECT product_id FROM state_identity LIMIT 1").fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _recent_story_fingerprints(path: Path, limit: int = 20) -> set[str]:
    """Return a set of normalized (title, gh_issue) tokens for recent stories."""
    tokens: set[str] = set()
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "stories" not in tables:
                return tokens
            cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
            select_cols = ["title"]
            if "gh_issue" in cols:
                select_cols.append("gh_issue")
            order_col = "created_at" if "created_at" in cols else "id"
            query = f"SELECT {', '.join(select_cols)} FROM stories ORDER BY {order_col} DESC LIMIT ?"
            for row in conn.execute(query, (limit,)):
                for value in row:
                    if value:
                        tokens.add(str(value).strip().lower())
        finally:
            conn.close()
    except Exception:
        pass
    return tokens


def _match_project(shard_path: Path, workspaces_root: Path) -> dict:
    """Best-effort match of a legacy shard to a known canonical workspace DB."""
    if not workspaces_root.is_dir():
        return {"slug": None, "method": "none", "confidence": None}

    candidates = sorted(workspaces_root.glob("*/state.db"))

    shard_product_id = _identity_product_id(shard_path)
    if shard_product_id is not None:
        for candidate in candidates:
            if _identity_product_id(candidate) == shard_product_id:
                return {
                    "slug": candidate.parent.name,
                    "method": "fingerprint",
                    "confidence": "exact",
                }

    shard_tokens = _recent_story_fingerprints(shard_path)
    if shard_tokens:
        best_slug = None
        best_overlap = 0
        for candidate in candidates:
            candidate_tokens = _recent_story_fingerprints(candidate)
            overlap = len(shard_tokens & candidate_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_slug = candidate.parent.name
        if best_slug is not None and best_overlap >= 1:
            return {"slug": best_slug, "method": "heuristic", "confidence": "heuristic"}

    return {"slug": None, "method": "none", "confidence": None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_state_inventory.py -k match_project -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Wire `project_match` into `inventory()` for legacy-project shards**

Modify the loop body in `inventory()` (added in Task 2) to add project matching for shards classified as `legacy-project`:

```python
    workspaces_root = home / "workspaces"
    for path in sorted(p for p in paths if p.is_file()):
        mtime = path.stat().st_mtime
        mtime_dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        staleness_days = (datetime.datetime.now(tz=datetime.timezone.utc) - mtime_dt).days
        item = {
            "path": str(path),
            "class": _classify(path, repo),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "sidecars": {suffix: Path(f"{path}{suffix}").is_file() for suffix in ("-wal", "-shm", "-journal")},
            "row_count": _row_count(path),
            "mtime_iso": mtime_dt.isoformat(),
            "staleness_days": staleness_days,
        }
        item.update(_metadata(path))
        if item["class"] == "legacy-project":
            item["project_match"] = _match_project(path, workspaces_root)
        rows.append(item)
```

(`home` is already defined earlier in `inventory()` as `Path(os.path.expanduser("~/.synlynk"))`.)

Add a test:

```python
def test_inventory_adds_project_match_for_legacy_shards(tmp_path, monkeypatch):
    home = tmp_path / "home" / ".synlynk"
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path / "home" / ".synlynk") if p == "~/.synlynk" else p)

    canonical_db = home / "workspaces" / "myproj" / "state.db"
    _make_db_with_identity(canonical_db, "prod-match-me")

    legacy_db = home / "projects" / "abc12345" / "state.db"
    _make_db_with_identity(legacy_db, "prod-match-me")

    repo = tmp_path / "repo"
    repo.mkdir()

    rows = inventory(repo, all_artifacts=True)

    legacy_rows = [r for r in rows if r["class"] == "legacy-project"]
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["project_match"]["slug"] == "myproj"
```

- [ ] **Step 6: Run full test file**

Run: `python3 -m pytest tests/test_state_inventory.py -v`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
git add synlynk/state_inventory.py tests/test_state_inventory.py
git commit -m "feat(state): match legacy shards to a canonical workspace via fingerprint/heuristic

_match_project() tries an exact state_identity.product_id match first,
then falls back to recent-story title/gh_issue token overlap for
pre-schema shards that have no state_identity table at all (the case
for both 13267207 and d8a234b7, per gh:#1831's spot-check)."
```

---

## Task 4: Add `_reconcile_plan()` for union-merge planning

**Files:**
- Modify: `synlynk/state_inventory.py`
- Test: `tests/test_state_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_state_inventory.py`:

```python
def _make_stories_db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    for story_id, title, gh_issue in rows:
        conn.execute(
            "INSERT INTO stories (story_id, title, gh_issue) VALUES (?, ?, ?)",
            (story_id, title, gh_issue),
        )
    conn.commit()
    conn.close()


def test_reconcile_plan_no_overlap_unions_everything(tmp_path):
    from synlynk.state_inventory import _reconcile_plan

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", None)])
    _make_stories_db(canonical, [("c-1", "Story B", None)])

    plan = _reconcile_plan(shard, canonical)

    assert [r["story_id"] for r in plan["to_add"]] == ["s-1"]
    assert plan["already_present"] == []
    assert plan["conflicts"] == []


def test_reconcile_plan_full_overlap_is_noop(tmp_path):
    from synlynk.state_inventory import _reconcile_plan

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", "#100")])
    _make_stories_db(canonical, [("s-1", "Story A", "#100")])

    plan = _reconcile_plan(shard, canonical)

    assert plan["to_add"] == []
    assert [r["story_id"] for r in plan["already_present"]] == ["s-1"]
    assert plan["conflicts"] == []


def test_reconcile_plan_detects_conflict(tmp_path):
    from synlynk.state_inventory import _reconcile_plan

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A, edited in shard", "#100")])
    _make_stories_db(canonical, [("s-1", "Story A, edited in canonical", "#100")])

    plan = _reconcile_plan(shard, canonical)

    assert plan["to_add"] == []
    assert plan["already_present"] == []
    assert [r["story_id"] for r in plan["conflicts"]] == ["s-1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_state_inventory.py -k reconcile_plan -v`
Expected: FAIL with `ImportError: cannot import name '_reconcile_plan'`

- [ ] **Step 3: Implement `_reconcile_plan()`**

Add to `synlynk/state_inventory.py`:

```python
def _read_stories(path: Path) -> dict[str, dict]:
    """Read all stories from a DB keyed by story_id. Returns {} if no stories table."""
    result: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "stories" not in tables:
                return result
            cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
            if "story_id" not in cols:
                return result
            select_cols = ["story_id", "title"]
            if "gh_issue" in cols:
                select_cols.append("gh_issue")
            if "created_at" in cols:
                select_cols.append("created_at")
            for row in conn.execute(f"SELECT {', '.join(select_cols)} FROM stories"):
                record = dict(zip(select_cols, row))
                result[record["story_id"]] = record
        finally:
            conn.close()
    except Exception:
        pass
    return result


def _reconcile_plan(shard_path: Path, canonical_path: Path) -> dict:
    """Compute a union-merge plan for shard_path's stories into canonical_path's."""
    shard_stories = _read_stories(shard_path)
    canonical_stories = _read_stories(canonical_path)

    to_add = []
    already_present = []
    conflicts = []

    for story_id, shard_row in shard_stories.items():
        canonical_row = canonical_stories.get(story_id)
        if canonical_row is None:
            to_add.append(shard_row)
        elif canonical_row.get("title") == shard_row.get("title"):
            already_present.append(shard_row)
        else:
            conflicts.append(shard_row)

    return {"to_add": to_add, "already_present": already_present, "conflicts": conflicts}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_state_inventory.py -k reconcile_plan -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/state_inventory.py tests/test_state_inventory.py
git commit -m "feat(state): add _reconcile_plan() for union-merge planning

Keys stories by story_id (the business key, not the raw autoincrement
id — needed because 13267207 and d8a234b7's id spaces don't
correspond to the same stories, per the design's spot-check). Any
story_id present in both DBs with a different title is flagged as a
conflict rather than silently merged either direction."
```

---

## Task 5: Add `--apply` write path with mandatory backup

**Files:**
- Modify: `synlynk/state_inventory.py`
- Test: `tests/test_state_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_state_inventory.py`:

```python
def test_apply_reconcile_backs_up_and_merges(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", None), ("s-2", "Story B", None)])
    _make_stories_db(canonical, [("c-1", "Story C", None)])

    result = apply_reconcile(shard, canonical)

    assert result["added"] == 2
    assert result["skipped_conflicts"] == 0
    backups = list(canonical.parent.glob("state.db.pre-reconcile-*.bak"))
    assert len(backups) == 1

    merged = _read_stories(canonical)
    assert set(merged.keys()) == {"c-1", "s-1", "s-2"}


def test_apply_reconcile_skips_conflicts_by_default(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A, shard version", None)])
    _make_stories_db(canonical, [("s-1", "Story A, canonical version", None)])

    result = apply_reconcile(shard, canonical)

    assert result["added"] == 0
    assert result["skipped_conflicts"] == 1
    merged = _read_stories(canonical)
    assert merged["s-1"]["title"] == "Story A, canonical version"


def test_apply_reconcile_raises_on_conflict_without_ignore_flag(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A, shard version", None)])
    _make_stories_db(canonical, [("s-1", "Story A, canonical version", None)])

    with pytest.raises(ValueError, match="conflict"):
        apply_reconcile(shard, canonical, ignore_conflicts=False)
```

Add `import pytest` to the top of `tests/test_state_inventory.py` if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_state_inventory.py -k apply_reconcile -v`
Expected: FAIL with `ImportError: cannot import name 'apply_reconcile'`

- [ ] **Step 3: Implement `apply_reconcile()`**

Add to `synlynk/state_inventory.py`. Add `import shutil` and `import time` to the top-level imports, then:

```python
def apply_reconcile(shard_path: Path, canonical_path: Path, *, ignore_conflicts: bool = True) -> dict:
    """Merge shard_path's stories into canonical_path, backing up canonical first.

    Conflicting story_ids (same id, different title) are never overwritten.
    With ignore_conflicts=True (the default for this function; the CLI
    defaults to requiring an explicit flag — see Task 6) they are counted
    and skipped. With ignore_conflicts=False, a ValueError is raised instead
    and nothing is written.
    """
    plan = _reconcile_plan(shard_path, canonical_path)
    if plan["conflicts"] and not ignore_conflicts:
        raise ValueError(
            f"{len(plan['conflicts'])} conflict(s) found; re-run with ignore_conflicts=True "
            "to skip them, or resolve manually first"
        )

    backup_path = canonical_path.parent / f"{canonical_path.name}.pre-reconcile-{int(time.time())}.bak"
    shutil.copy2(canonical_path, backup_path)

    conn = sqlite3.connect(canonical_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
        insert_cols = ["story_id", "title"]
        if "gh_issue" in cols:
            insert_cols.append("gh_issue")
        placeholders = ", ".join("?" for _ in insert_cols)
        with conn:
            for row in plan["to_add"]:
                values = [row.get(c) for c in insert_cols]
                conn.execute(
                    f"INSERT INTO stories ({', '.join(insert_cols)}) VALUES ({placeholders})",
                    values,
                )
    except Exception:
        conn.close()
        raise
    conn.close()

    return {
        "added": len(plan["to_add"]),
        "already_present": len(plan["already_present"]),
        "skipped_conflicts": len(plan["conflicts"]),
        "backup_path": str(backup_path),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_state_inventory.py -k apply_reconcile -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add a rollback-on-failure test**

```python
def test_apply_reconcile_rolls_back_on_failure(tmp_path, monkeypatch):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", None)])
    _make_stories_db(canonical, [("c-1", "Story C", None)])

    before = _read_stories(canonical)

    import sqlite3 as sqlite3_module
    real_connect = sqlite3_module.connect

    def _boom(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        original_execute = conn.execute

        def _execute(sql, *a, **k):
            if sql.strip().upper().startswith("INSERT"):
                raise sqlite3_module.OperationalError("simulated failure")
            return original_execute(sql, *a, **k)

        conn.execute = _execute
        return conn

    monkeypatch.setattr(sqlite3_module, "connect", _boom)

    with pytest.raises(sqlite3_module.OperationalError):
        apply_reconcile(shard, canonical)

    after = _read_stories(canonical)
    assert after == before
```

Run: `python3 -m pytest tests/test_state_inventory.py -k apply_reconcile -v`
Expected: PASS (4 passed) — the `with conn:` block makes the connection a context manager that rolls back automatically on an uncaught exception before commit.

- [ ] **Step 6: Commit**

```bash
git add synlynk/state_inventory.py tests/test_state_inventory.py
git commit -m "feat(state): add apply_reconcile() with mandatory backup and atomic merge

Always snapshots the canonical DB to a .pre-reconcile-<timestamp>.bak
file before writing. Conflicting story_ids are never overwritten —
skipped by default, or the whole call raises ValueError and writes
nothing if ignore_conflicts=False. A failure mid-merge leaves the
canonical DB untouched (transaction rollback via sqlite3's context
manager)."
```

---

## Task 6: Wire `--reconcile`/`--apply`/`--ignore-conflicts` into the CLI

**Files:**
- Modify: `synlynk/cli.py:996-1004` (argparse), `synlynk/cli.py:2234-2240` (dispatch)
- Modify: `synlynk/state_inventory.py` (`cmd_state_inventory`)
- Test: `tests/test_state_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_state_inventory.py`:

```python
def test_cmd_state_inventory_reconcile_dry_run_prints_plan(tmp_path, monkeypatch, capsys):
    from synlynk.state_inventory import cmd_state_inventory

    home = tmp_path / "home" / ".synlynk"
    monkeypatch.setattr(
        "os.path.expanduser",
        lambda p: str(tmp_path / "home" / ".synlynk") if p == "~/.synlynk" else p,
    )

    canonical = home / "workspaces" / "myproj" / "state.db"
    _make_stories_db(canonical, [("c-1", "Existing story", None)])
    legacy = home / "projects" / "abc12345" / "state.db"
    _make_stories_db(legacy, [("s-1", "Orphaned story", None)])

    repo = tmp_path / "repo"
    repo.mkdir()

    exit_code = cmd_state_inventory(repo_root=str(repo), reconcile_slug="myproj", apply=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "to_add" in captured.out or "Orphaned story" in captured.out
    # Dry run: canonical must be untouched
    assert _read_stories(canonical) == {"c-1": {"story_id": "c-1", "title": "Existing story"}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_state_inventory.py -k reconcile_dry_run -v`
Expected: FAIL with `TypeError: cmd_state_inventory() got an unexpected keyword argument 'reconcile_slug'`

- [ ] **Step 3: Implement the CLI-facing reconcile mode**

Modify `cmd_state_inventory()` in `synlynk/state_inventory.py`:

```python
def cmd_state_inventory(
    *,
    repo_root: str = ".",
    json_output: bool = False,
    all_artifacts: bool = False,
    reconcile_slug: str | None = None,
    apply: bool = False,
    ignore_conflicts: bool = False,
    cutoff_days: int | None = None,
) -> int:
    if reconcile_slug is not None:
        return _cmd_reconcile(
            repo_root, reconcile_slug, apply=apply,
            ignore_conflicts=ignore_conflicts, cutoff_days=cutoff_days,
        )

    rows = inventory(repo_root, all_artifacts=all_artifacts)
    if json_output:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print("PATH\tCLASS\tSIZE\tROWS\tSTALE_DAYS\tINTEGRITY")
        for row in rows:
            print(
                f"{row['path']}\t{row['class']}\t{row['size_bytes']}\t"
                f"{row.get('row_count')}\t{row.get('staleness_days')}\t"
                f"{row.get('integrity', 'unknown')}"
            )
    return 0


def _cmd_reconcile(
    repo_root: str, slug: str, *, apply: bool, ignore_conflicts: bool,
    cutoff_days: int | None = None,
) -> int:
    home = Path(os.path.expanduser("~/.synlynk"))
    canonical_path = home / "workspaces" / slug / "state.db"
    if not canonical_path.is_file():
        print(f"error: no canonical state.db found for slug {slug!r} at {canonical_path}")
        return 1

    rows = inventory(repo_root, all_artifacts=True)
    matched_shards = [
        r for r in rows
        if r["class"] == "legacy-project"
        and r.get("project_match", {}).get("slug") == slug
    ]
    if cutoff_days is not None:
        skipped = [r for r in matched_shards if r["staleness_days"] > cutoff_days]
        matched_shards = [r for r in matched_shards if r["staleness_days"] <= cutoff_days]
        for shard in skipped:
            print(
                f"skipping {shard['path']}: staleness {shard['staleness_days']}d "
                f"exceeds --cutoff-days {cutoff_days}"
            )
    if not matched_shards:
        print(f"no legacy shards matched to slug {slug!r}")
        return 0

    exit_code = 0
    for shard in matched_shards:
        shard_path = Path(shard["path"])
        plan = _reconcile_plan(shard_path, canonical_path)
        print(f"=== {shard_path} -> {canonical_path} ===")
        print(json.dumps(plan, indent=2, sort_keys=True, default=str))
        if apply:
            if plan["conflicts"] and not ignore_conflicts:
                print(
                    f"refusing to apply: {len(plan['conflicts'])} conflict(s). "
                    "Re-run with --ignore-conflicts to skip them."
                )
                exit_code = 1
                continue
            result = apply_reconcile(shard_path, canonical_path, ignore_conflicts=True)
            print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_state_inventory.py -k reconcile_dry_run -v`
Expected: PASS

- [ ] **Step 4a: Write a failing test for `--cutoff-days` filtering**

Append to `tests/test_state_inventory.py`:

```python
def test_cmd_state_inventory_reconcile_respects_cutoff_days(tmp_path, monkeypatch, capsys):
    from synlynk.state_inventory import cmd_state_inventory

    monkeypatch.setattr(
        "os.path.expanduser",
        lambda p: str(tmp_path / "home" / ".synlynk") if p == "~/.synlynk" else p,
    )
    home = tmp_path / "home" / ".synlynk"

    canonical = home / "workspaces" / "myproj" / "state.db"
    _make_stories_db(canonical, [("c-1", "Existing story", None)])
    legacy = home / "projects" / "abc12345" / "state.db"
    _make_stories_db(legacy, [("s-1", "Orphaned story", None)])

    old_time = time.time() - (100 * 86400)
    os.utime(legacy, (old_time, old_time))

    repo = tmp_path / "repo"
    repo.mkdir()

    exit_code = cmd_state_inventory(
        repo_root=str(repo), reconcile_slug="myproj", apply=False, cutoff_days=10,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipping" in captured.out
    assert "no legacy shards matched" in captured.out or "skipping" in captured.out
```

Add `import os` and `import time` to the top of `tests/test_state_inventory.py` if not already present (both are needed by this test and the earlier staleness test in Task 2).

- [ ] **Step 4b: Run test to verify it fails**

Run: `python3 -m pytest tests/test_state_inventory.py -k cutoff_days -v`
Expected: FAIL with `TypeError: cmd_state_inventory() got an unexpected keyword argument 'cutoff_days'`

- [ ] **Step 4c: Run test to verify it passes (after Step 3's `_cmd_reconcile`/`cmd_state_inventory` signatures include `cutoff_days`)**

Run: `python3 -m pytest tests/test_state_inventory.py -k cutoff_days -v`
Expected: PASS

- [ ] **Step 5: Wire CLI argparse flags**

In `synlynk/cli.py`, modify lines 997-1004 (the existing `state_inventory` parser block):

```python
    state_inventory = state_sub.add_parser(
        "inventory", help="Read-only inventory with hashes and integrity checks"
    )
    state_inventory.add_argument("--json", action="store_true", dest="json_output")
    state_inventory.add_argument(
        "--all", action="store_true", dest="all_artifacts",
        help="Include the full ~/.synlynk legacy/quarantine/backup tree",
    )
    state_inventory.add_argument(
        "--reconcile", default=None, dest="reconcile_slug", metavar="SLUG",
        help="Plan (default) or apply merging matched legacy shards into workspace SLUG's state.db",
    )
    state_inventory.add_argument(
        "--apply", action="store_true",
        help="Actually write the reconcile merge (default is dry-run plan only)",
    )
    state_inventory.add_argument(
        "--ignore-conflicts", action="store_true", dest="ignore_conflicts",
        help="Skip conflicting story rows instead of refusing to apply",
    )
    state_inventory.add_argument(
        "--cutoff-days", type=int, default=None, dest="cutoff_days", metavar="N",
        help="With --reconcile, skip matched shards whose staleness exceeds N days",
    )
```

Modify the dispatch block at `synlynk/cli.py:2234-2240`:

```python
        if args.state_action == "inventory":
            from synlynk.state_inventory import cmd_state_inventory

            sys.exit(cmd_state_inventory(
                json_output=args.json_output,
                all_artifacts=getattr(args, "all_artifacts", False),
                reconcile_slug=getattr(args, "reconcile_slug", None),
                apply=getattr(args, "apply", False),
                ignore_conflicts=getattr(args, "ignore_conflicts", False),
                cutoff_days=getattr(args, "cutoff_days", None),
            ))
```

- [ ] **Step 6: Run the full test file plus a CLI smoke test**

Run: `python3 -m pytest tests/test_state_inventory.py -v`
Expected: PASS (all tests)

Run: `python3 bin/synlynk.py state inventory --help`
Expected: help text shows `--reconcile`, `--apply`, `--ignore-conflicts`, `--cutoff-days` alongside the existing `--json`/`--all`

- [ ] **Step 7: Commit**

```bash
git add synlynk/cli.py synlynk/state_inventory.py tests/test_state_inventory.py
git commit -m "feat(state): wire --reconcile/--apply/--ignore-conflicts/--cutoff-days into state inventory CLI

synlynk state inventory --reconcile <slug> prints a dry-run merge plan
for every legacy shard matched to that workspace slug; --apply
actually performs the merge (still refusing on unflagged conflicts).
--cutoff-days N skips matched shards staler than N days, so a
reconcile run doesn't reach into truly ancient dead shards by
accident. No new subcommand — extends the existing 'state inventory'
per the design's decision to avoid a second overlapping command."
```

---

## Task 7: Run the full test suite and update the taxonomy/docs if needed

**Files:**
- Read: `synlynk/taxonomy.py:121-123`
- Verify: no doc/README changes required (confirmed in design: "state inventory" is already a taxonomy entry at maturity_tier 1; this plan only adds flags to the existing command, not a new one)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest -x -q`
Expected: all tests pass, including the pre-existing suite (no regressions from Tasks 1-6)

- [ ] **Step 2: Confirm no README/taxonomy update is required**

```bash
grep -n '"state inventory"' synlynk/taxonomy.py
```
Expected: the existing entry at `synlynk/taxonomy.py:121-123` is unchanged — this plan adds flags to an existing, already-documented command, not a new command, so no taxonomy row or README command-table update is needed. If `synlynk release --check-docs` is run later for a named release, it should pass without changes from this PR.

- [ ] **Step 3: Manually dry-run against one real matched shard (operator-run, not part of CI)**

This step is for Nikhil to run manually after the PR merges — not part of the automated task, since it touches the real `~/.synlynk` tree:

```bash
synlynk state inventory --all --json | python3 -c "import json,sys; rows=json.load(sys.stdin); print([r for r in rows if r.get('project_match',{}).get('slug')=='synlynk' and r['class']=='legacy-project'])"
synlynk state inventory --reconcile synlynk
```
Review the printed plan before ever passing `--apply`.

- [ ] **Step 4: Commit (if any fixups were needed in Step 1)**

Only commit if Step 1 required a fix; otherwise this task has no commit of its own.
