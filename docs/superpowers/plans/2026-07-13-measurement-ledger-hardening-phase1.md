# Measurement Ledger Hardening — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every `cost_entries` row an explicit, enforced provenance tag (`actual` / `estimated_token_rate` / `estimated_tshirt` / `estimated_manual` / `legacy_unknown`), close every known write-coverage gap (zero-token skip, `jobs.py` reconcile paths, `synlynk launch`, `support_engineer.py`), and route all writes through one chokepoint function so the invariant can never be silently bypassed.

**Architecture:** A single new function, `_insert_cost_row()` in `synlynk/db.py`, becomes the only code path allowed to `INSERT`/`UPDATE` `cost_entries`. `cost_source` gets `NOT NULL` with no default (enforced at the DB layer via a full table rebuild migration, since SQLite can't add a bare `NOT NULL` column to a non-empty table). `synlynk/costs.py` gains tier-resolution logic (`_resolve_cost_tier`) and a t-shirt fallback chain (`_estimate_tshirt_tokens`) that every caller — `update_costs()`, `dispatch.py`, `jobs.py`'s two reconcile paths, `cmd_launch`, `support_engineer.py`, and the new `synlynk cost log` command — funnels through instead of writing SQL directly.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest (existing `tests/conftest.py` fixtures: `isolated_db`, `project_dir`).

**Scope note:** This plan covers **Phase 1 only** (schema, chokepoint, fallback chain, coverage-gap fixes, `synlynk cost log`, rate-file/billing-mode, reporting/parser updates) per the design spec's own Phase 1/Phase 2 split (`docs/superpowers/specs/2026-07-13-measurement-ledger-hardening-design.md` §4, §12). Phase 2 (per-agent structured-output extraction adapters) is independently shippable and gets its own follow-up plan once Phase 1 lands — all three external reviewers (Agy, Codex, Grok) confirmed no structural dependency runs the other direction.

---

## File Structure

| File | Responsibility in this plan |
|---|---|
| `synlynk/db.py` | Schema rebuild migration for `cost_entries` (new columns + `NOT NULL` `cost_source`); `_insert_cost_row()` chokepoint; new `cmd_cost_log()`; `_parse_costs_md()` prefix-tolerant parsing |
| `synlynk/costs.py` | `_TokenCounts.basis` attribute + `extract_tokens()` population; `_resolve_billing_mode()`; `_load_model_rates()` (replaces hardcoded `_MODEL_RATE_TABLE`, validates `unit` key); `_resolve_cost_tier()`; `_estimate_tshirt_tokens()` fallback chain; `update_costs()` refactored to call the chokepoint; `parse_costs_md()` prefix-tolerant parsing |
| `synlynk/dispatch.py` | Remove the `if in_tokens > 0` write gate (~line 1013); always resolve a tier and write exactly one row per terminal job state |
| `synlynk/jobs.py` | Wire `_reconcile_jobs()` (line 851) and `_reconcile_daemon_jobs()` (line 1213) to the chokepoint via `job_id`, closing the reconcile-path gap |
| `synlynk/__init__.py` | Fix `cmd_launch()` (line 2057) to route through the fallback chain instead of writing bare `0`/`0` |
| `synlynk/support_engineer.py` | Wire `_run_investigation()` (after the `subprocess.run` at line 413) to write one cost row per investigation |
| `synlynk/cli.py` | New `synlynk cost log` subcommand parser |
| `.synlynk/model_rates.json` | New file, created by `synlynk init` (not this plan's `synlynk/__init__.py` init path — see Task 11) with `unit`, `billing_mode`, `models`, `default` keys |
| `/Users/nikhilsoman/dev/synlynk/CLAUDE.md` | New "Cost Capture Protocol" section (§9 of the spec) |
| `tests/test_cost_ledger.py` | New test file — all Phase 1 tests live here rather than scattered, since they share fixtures and test one cohesive subsystem |

No files are deleted. `synlynk/team.py` is **not modified** — `_actual_tokens_for_story()` stays as-is (display-only, telemetry-sourced); the historical-average fallback tier reads `cost_entries` directly instead, per spec §5.1.

---

## Task 1: Schema migration — rebuild `cost_entries` with provenance columns

**Files:**
- Modify: `synlynk/db.py:409-460` (the `executescript` block inside `_migrate_db` that creates `cost_entries`)
- Test: `tests/test_cost_ledger.py` (new file)

SQLite cannot add a `NOT NULL` column with no default to a non-empty table via `ALTER TABLE ADD COLUMN` — it raises `OperationalError: Cannot add a NOT NULL column with default value NULL`. Since `cost_source` must be `NOT NULL` with no default (the primary enforcement mechanism per spec §3.1), existing databases need a table rebuild, not an `ALTER TABLE`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py
import os
import sqlite3
import pytest


def test_cost_entries_has_provenance_columns(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    conn.close()
    assert "cost_source" in cols
    assert "estimate_basis" in cols
    assert "job_id" in cols


def test_cost_source_not_null_no_default(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens) "
            "VALUES ('2026-07-13', 'claude', 'claude-sonnet-4-6', 100, 50)"
        )
    conn.close()


def test_migration_backfills_existing_rows_as_legacy_unknown(project_dir, monkeypatch):
    """A DB created before this migration (no provenance columns, has rows) must
    backfill cost_source='legacy_unknown' on rebuild, never 'actual'."""
    import synlynk
    db_path = os.path.join(project_dir, "state.db")
    monkeypatch.setattr(synlynk, "DB_PATH", db_path)

    # Simulate a pre-migration DB: old-shape cost_entries with one row, no provenance cols.
    pre_conn = sqlite3.connect(db_path)
    pre_conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            story_id TEXT,
            epic_id INTEGER,
            phase_id INTEGER,
            total_cost_usd REAL,
            notes TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    pre_conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, total_cost_usd) "
        "VALUES ('2026-01-01', 'claude', 'claude-sonnet-4-6', 1000, 500, 0.01)"
    )
    pre_conn.commit()
    pre_conn.close()

    conn = synlynk._get_db()  # triggers _migrate_db -> rebuild
    row = conn.execute("SELECT cost_source, estimate_basis FROM cost_entries WHERE session_date='2026-01-01'").fetchone()
    conn.close()
    assert row == ("legacy_unknown", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -v`
Expected: FAIL — `cost_source` column does not exist / no `IntegrityError` raised.

- [ ] **Step 3: Implement the rebuild migration**

In `synlynk/db.py`, replace the `cost_entries` block inside the `executescript("""..."""` at line 409-460 so the table is created fresh with the new columns (this is the CREATE-only path for brand-new databases):

```python
        CREATE TABLE IF NOT EXISTS cost_entries (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date      TEXT NOT NULL,
            agent             TEXT,
            model             TEXT,
            input_tokens      INTEGER,
            output_tokens     INTEGER,
            cache_read_tokens INTEGER,
            story_id          TEXT REFERENCES stories(story_id),
            epic_id           INTEGER REFERENCES roadmap_arcs(id),
            phase_id          INTEGER REFERENCES roadmap_phases(id),
            total_cost_usd    REAL,
            notes             TEXT,
            cost_source       TEXT NOT NULL,
            estimate_basis    TEXT,
            job_id            TEXT,
            recorded_at       TEXT DEFAULT (datetime('now'))
        );
```

Immediately after the existing `cost_cols` block at line 479-489 (which adds `story_id`/`epic_id`/`phase_id` for pre-existing tables), add the rebuild path for tables that predate the provenance columns:

```python
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    for col, typedef in [
        ("story_id", "TEXT REFERENCES stories(story_id)"),
        ("epic_id", "INTEGER REFERENCES roadmap_arcs(id)"),
        ("phase_id", "INTEGER REFERENCES roadmap_phases(id)"),
    ]:
        if col not in cost_cols:
            try:
                conn.execute(f"ALTER TABLE cost_entries ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

    if "cost_source" not in cost_cols:
        # cost_source is NOT NULL with no default (spec §3.1) — SQLite can't ALTER
        # a non-empty table to add that directly, so rebuild the table.
        conn.execute("ALTER TABLE cost_entries RENAME TO cost_entries_pre_provenance")
        conn.execute("""
            CREATE TABLE cost_entries (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date      TEXT NOT NULL,
                agent             TEXT,
                model             TEXT,
                input_tokens      INTEGER,
                output_tokens     INTEGER,
                cache_read_tokens INTEGER,
                story_id          TEXT REFERENCES stories(story_id),
                epic_id           INTEGER REFERENCES roadmap_arcs(id),
                phase_id          INTEGER REFERENCES roadmap_phases(id),
                total_cost_usd    REAL,
                notes             TEXT,
                cost_source       TEXT NOT NULL,
                estimate_basis    TEXT,
                job_id            TEXT,
                recorded_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        old_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries_pre_provenance)")}
        select_cols = ", ".join(
            c if c in old_cols else "NULL"
            for c in ("session_date", "agent", "model", "input_tokens", "output_tokens",
                       "cache_read_tokens", "story_id", "epic_id", "phase_id",
                       "total_cost_usd", "notes", "recorded_at")
        )
        conn.execute(f"""
            INSERT INTO cost_entries
                (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                 story_id, epic_id, phase_id, total_cost_usd, notes, cost_source, estimate_basis, recorded_at)
            SELECT {select_cols}, 'legacy_unknown', NULL, recorded_at
            FROM cost_entries_pre_provenance
        """)
        conn.execute("DROP TABLE cost_entries_pre_provenance")
        cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}

    if "job_id" not in cost_cols:
        try:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN job_id TEXT")
        except sqlite3.OperationalError:
            pass
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cost_entries_job_id "
        "ON cost_entries(job_id) WHERE job_id IS NOT NULL"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_cost_ledger.py
git commit -m "feat(costs): rebuild cost_entries with cost_source/estimate_basis/job_id"
```

---

## Task 2: `_insert_cost_row()` chokepoint

**Files:**
- Modify: `synlynk/db.py` (add function near `_migrate_db`, after Task 1's block)
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_ledger.py (append)

def test_insert_cost_row_rejects_invalid_cost_source(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    with pytest.raises(ValueError):
        _insert_cost_row(
            session_date="2026-07-13", agent="claude", model="claude-sonnet-4-6",
            input_tokens=100, output_tokens=50, cache_read_tokens=0,
            cost_source="made_up_tier", total_cost_usd=0.01,
        )


def test_insert_cost_row_writes_a_row(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _insert_cost_row(
        session_date="2026-07-13", agent="claude", model="claude-sonnet-4-6",
        input_tokens=100, output_tokens=50, cache_read_tokens=0,
        cost_source="actual", total_cost_usd=0.01,
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT agent, cost_source FROM cost_entries").fetchone()
    conn.close()
    assert row == ("claude", "actual")


def test_insert_cost_row_idempotent_on_job_id(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _insert_cost_row(
        session_date="2026-07-13", agent="claude", model="claude-sonnet-4-6",
        input_tokens=100, output_tokens=50, cache_read_tokens=0,
        cost_source="estimated_tshirt", total_cost_usd=0.01, job_id="job-abc123",
    )
    _insert_cost_row(
        session_date="2026-07-13", agent="claude", model="claude-sonnet-4-6",
        input_tokens=200, output_tokens=80, cache_read_tokens=0,
        cost_source="actual", total_cost_usd=0.02, job_id="job-abc123",
    )
    conn = synlynk._get_db()
    rows = conn.execute("SELECT input_tokens, cost_source FROM cost_entries WHERE job_id='job-abc123'").fetchall()
    conn.close()
    assert rows == [(200, "actual")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k insert_cost_row -v`
Expected: FAIL — `ImportError: cannot import name '_insert_cost_row'`

- [ ] **Step 3: Implement `_insert_cost_row()`**

Add to `synlynk/db.py`, directly after `_migrate_db` (which ends around line 621):

```python
_VALID_COST_SOURCES = {
    "actual", "estimated_token_rate", "estimated_tshirt", "estimated_manual", "legacy_unknown",
}


def _insert_cost_row(session_date: str, agent: str, model: str, input_tokens: int,
                      output_tokens: int, cache_read_tokens: int, cost_source: str,
                      total_cost_usd: float, notes: str = None, story_id: str = None,
                      epic_id: int = None, phase_id: int = None, estimate_basis: str = None,
                      job_id: str = None) -> None:
    """The only code path allowed to write to cost_entries (spec §3.1).

    Idempotent on job_id: a second write for the same job_id updates the
    existing row instead of inserting a duplicate (prevents double-counting
    when both a foreground dispatch path and a reconcile path observe the
    same job).
    """
    from synlynk import _get_db
    if cost_source not in _VALID_COST_SOURCES:
        raise ValueError(f"Invalid cost_source: {cost_source!r}, must be one of {_VALID_COST_SOURCES}")
    conn = _get_db()
    try:
        if job_id:
            existing = conn.execute(
                "SELECT id FROM cost_entries WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE cost_entries SET
                         session_date=?, agent=?, model=?, input_tokens=?, output_tokens=?,
                         cache_read_tokens=?, cost_source=?, estimate_basis=?, total_cost_usd=?,
                         notes=?, story_id=?, epic_id=?, phase_id=?
                       WHERE job_id=?""",
                    (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                     cost_source, estimate_basis, total_cost_usd, notes, story_id, epic_id,
                     phase_id, job_id),
                )
                conn.commit()
                return
        conn.execute(
            """INSERT INTO cost_entries
               (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                cost_source, estimate_basis, total_cost_usd, notes, story_id, epic_id, phase_id, job_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
             cost_source, estimate_basis, total_cost_usd, notes, story_id, epic_id, phase_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k insert_cost_row -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_cost_ledger.py
git commit -m "feat(costs): add _insert_cost_row chokepoint with job_id idempotency"
```

---

## Task 3: Extraction-confidence signal on `extract_tokens()`

**Files:**
- Modify: `synlynk/costs.py:19-77` (`_TokenCounts`, `extract_tokens`)
- Test: `tests/test_cost_ledger.py`

Per spec §4.1, this is required in Phase 1 so tier resolution can distinguish a real regex match from a guessed 80/20 split. To avoid breaking the 5 existing 2-value-unpack call sites (`dispatch.py:1009`, `jobs.py:851,939,1069,1213`), `basis` is added as an **attribute** on `_TokenCounts` (same pattern already used for `cache_read_tokens`), not a third tuple value — `__iter__`/`__len__` stay at 2 items.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
from synlynk.costs import extract_tokens


def test_extract_tokens_basis_regex_pair():
    result = extract_tokens("Input tokens: 1,200. Output tokens: 340.")
    assert (result.input_tokens, result.output_tokens) == (1200, 340)
    assert result.basis == "regex_pair"


def test_extract_tokens_basis_total_split():
    result = extract_tokens("Total tokens: 1000")
    assert result.basis == "total_split"


def test_extract_tokens_basis_none():
    result = extract_tokens("no token info in this output at all")
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.basis == "none"


def test_extract_tokens_still_unpacks_as_pair():
    in_tokens, out_tokens = extract_tokens("Input tokens: 10. Output tokens: 5.")
    assert (in_tokens, out_tokens) == (10, 5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k extract_tokens_basis -v`
Expected: FAIL — `AttributeError: '_TokenCounts' object has no attribute 'basis'`

- [ ] **Step 3: Implement**

In `synlynk/costs.py`, update `_TokenCounts`:

```python
class _TokenCounts(object):
    __slots__ = ("input_tokens", "output_tokens", "cache_read_tokens", "basis")

    def __init__(self, input_tokens, output_tokens, cache_read_tokens, basis="none"):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_tokens = cache_read_tokens
        self.basis = basis

    def __iter__(self):
        yield self.input_tokens
        yield self.output_tokens

    def __len__(self):
        return 2
```

Update `extract_tokens()` to set `basis` — replace the body from `in_tokens = 0` through the `cache_read_tokens` block with:

```python
    in_tokens = 0
    out_tokens = 0
    basis = "none"
    for pat, flags in patterns:
        m = re.search(pat, output_text, flags)
        if m:
            in_tokens = _parse_count(m.group(1))
            out_tokens = _parse_count(m.group(2))
            basis = "regex_pair"
            break
    if not in_tokens and not out_tokens:
        m = re.search(r'(?:Tokens used|Total tokens)\s*[:\n]\s*([\d,]+)', output_text, re.IGNORECASE)
        if m:
            total = _parse_count(m.group(1))
            in_tokens = int(total * 0.8)
            out_tokens = total - in_tokens
            basis = "total_split"

    cache_read_tokens = 0
    cache_patterns = [
        r'"(?:cached_tokens|cache_read_tokens)"\s*:\s*([\d,]+)',
        r'Cache read tokens:\s*([\d,]+)',
        r'Cached tokens:\s*([\d,]+)',
    ]
    for pat in cache_patterns:
        m = re.search(pat, output_text, re.IGNORECASE)
        if m:
            cache_read_tokens = _parse_count(m.group(1))
            break

    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, basis)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k extract_tokens -v`
Expected: PASS (4 new tests, plus any pre-existing `extract_tokens` tests still pass)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): extract_tokens reports extraction basis (regex_pair/total_split/none)"
```

---

## Task 4: Rate file with `billing_mode` and `unit` validation

**Files:**
- Create: `.synlynk/model_rates.json` (written by `synlynk init` — see Task 11 for the init-time write; this task adds the *loader*)
- Modify: `synlynk/costs.py` (replace `_MODEL_RATE_TABLE` usage with a loader)
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_ledger.py (append)
import json
from synlynk.costs import _load_model_rates, _resolve_billing_mode


def test_load_model_rates_valid_file(project_dir):
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump({
            "rates_updated_at": "2026-07-13",
            "unit": "usd_per_1k_tokens",
            "models": {"claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}},
            "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
            "billing_mode": {"default": "subscription", "local": "actual"},
        }, f)
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["models"]["claude-sonnet-4-6"]["input"] == 0.003
    assert rates["billing_mode"]["default"] == "subscription"


def test_load_model_rates_missing_unit_falls_back(project_dir, capsys):
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump({"models": {}, "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}}, f)
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"] == {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
    captured = capsys.readouterr()
    assert "unit" in captured.out.lower() or "unit" in captured.err.lower()


def test_load_model_rates_missing_file_uses_hardcoded_default(project_dir):
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"]["input"] == 0.003


def test_resolve_billing_mode_local_hardcoded_actual(project_dir):
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump({
            "unit": "usd_per_1k_tokens", "models": {},
            "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0},
            "billing_mode": {"default": "subscription", "local": "subscription"},
        }, f)
    os.chdir(project_dir)
    assert _resolve_billing_mode("local") == "actual"


def test_resolve_billing_mode_falls_back_to_default(project_dir):
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump({
            "unit": "usd_per_1k_tokens", "models": {},
            "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0},
            "billing_mode": {"default": "subscription"},
        }, f)
    os.chdir(project_dir)
    assert _resolve_billing_mode("codex") == "subscription"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "load_model_rates or resolve_billing_mode" -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement**

In `synlynk/costs.py`, replace the `_DEFAULT_MODEL_RATE` / `_MODEL_RATE_TABLE` / `_model_rate_for_version` block (lines 139-155) with:

```python
_DEFAULT_MODEL_RATE = {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
_EXPECTED_RATE_UNIT = "usd_per_1k_tokens"
_HARDCODED_FALLBACK_RATES = {
    "rates_updated_at": None,
    "unit": _EXPECTED_RATE_UNIT,
    "models": {
        "claude-opus-4-8": {"input": 0.015, "output": 0.075, "cache_read": 0.0000015},
        "claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "gpt-5-codex": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "gpt-5.4-mini": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.01, "cache_read": 0.000125},
        "grok-build": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "grok-composer-2.5-fast": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    },
    "default": _DEFAULT_MODEL_RATE,
    "billing_mode": {"default": "subscription", "local": "actual"},
}
_RATES_PATH = ".synlynk/model_rates.json"


def _load_model_rates() -> dict:
    """Loads .synlynk/model_rates.json. Falls back to hardcoded rates (with a
    warning) if the file is missing, malformed, or has a wrong/missing 'unit'."""
    if not os.path.exists(_RATES_PATH):
        return _HARDCODED_FALLBACK_RATES
    try:
        with open(_RATES_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        print(f"  ⚠ {_RATES_PATH} is unreadable — falling back to hardcoded default rates.")
        return _HARDCODED_FALLBACK_RATES
    if data.get("unit") != _EXPECTED_RATE_UNIT:
        print(
            f"  ⚠ {_RATES_PATH} has missing or unexpected 'unit' "
            f"(expected {_EXPECTED_RATE_UNIT!r}, got {data.get('unit')!r}) — "
            "falling back to hardcoded default rates to avoid a pricing unit mismatch."
        )
        return _HARDCODED_FALLBACK_RATES
    data.setdefault("default", _DEFAULT_MODEL_RATE)
    data.setdefault("models", {})
    data.setdefault("billing_mode", {"default": "subscription", "local": "actual"})
    return data


def _resolve_billing_mode(agent: str) -> str:
    """Resolves 'actual' vs 'subscription' for an agent. 'local' is always
    'actual' regardless of config (spec §3.2), matching its existing $0 rate override."""
    normalized_agent = os.path.basename(agent or "")
    if normalized_agent == "local":
        return "actual"
    rates = _load_model_rates()
    billing_mode = rates.get("billing_mode", {})
    return billing_mode.get(normalized_agent, billing_mode.get("default", "subscription"))


def _model_rate_for_version(model_version, agent=None):
    normalized_agent = os.path.basename(agent or "")
    if normalized_agent == "local":
        return {"input": 0.0, "output": 0.0, "cache_read": 0.0}
    rates = _load_model_rates()
    return rates["models"].get(model_version, rates["default"])
```

Add `import json` is already present at the top of `costs.py` (line 3) — no new import needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "load_model_rates or resolve_billing_mode" -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): load rates from .synlynk/model_rates.json with unit validation and billing_mode"
```

---

## Task 5: T-shirt fallback chain (`_estimate_tshirt_tokens`)

**Files:**
- Modify: `synlynk/costs.py` (new function)
- Test: `tests/test_cost_ledger.py`

Per spec §5.1, sourced from `cost_entries` (`actual`/`estimated_token_rate` rows only), not `stories.actual_tokens` (confirmed dead — see `team.py:337`, computed dynamically from telemetry, never stored).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_ledger.py (append)
from synlynk.costs import _estimate_tshirt_tokens


def test_estimate_tshirt_tier1_story_estimate(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, phase, estimated_tokens) "
        "VALUES ('story-1', 'Test', 'backend', 'build', 4000)"
    )
    conn.commit()
    conn.close()
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id="story-1", discipline="backend", phase="build")
    assert basis == "story_estimate"
    assert in_t + out_t == 4000


def test_estimate_tshirt_tier2_historical_avg(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'backend', 'build')",
            (f"story-hist-{i}",)
        )
    conn.commit()
    conn.close()
    for i in range(3):
        _insert_cost_row(
            session_date="2026-07-01", agent="claude", model="claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500, cache_read_tokens=0,
            cost_source="actual", total_cost_usd=0.01, story_id=f"story-hist-{i}",
        )
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="backend", phase="build")
    assert basis == "historical_avg"
    assert (in_t, out_t) == (1000, 500)


def test_estimate_tshirt_tier3_fixed_default(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="backend", phase="build")
    assert basis == "fixed_default"
    assert in_t > 0 and out_t > 0


def test_estimate_tshirt_ignores_estimated_tshirt_rows_in_history(project_dir, monkeypatch):
    """Historical averaging must not recycle guessed rows into future guesses (Grok's finding)."""
    import synlynk
    from synlynk.db import _insert_cost_row
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'frontend', 'build')",
            (f"story-guess-{i}",)
        )
    conn.commit()
    conn.close()
    for i in range(3):
        _insert_cost_row(
            session_date="2026-07-01", agent="claude", model="claude-sonnet-4-6",
            input_tokens=9999, output_tokens=9999, cache_read_tokens=0,
            cost_source="estimated_tshirt", estimate_basis="fixed_default",
            total_cost_usd=0.01, story_id=f"story-guess-{i}",
        )
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="frontend", phase="build")
    assert basis == "fixed_default"
    assert in_t != 9999
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k estimate_tshirt -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement**

Add to `synlynk/costs.py`:

```python
_FIXED_DEFAULT_TOKENS_IN = 5000
_FIXED_DEFAULT_TOKENS_OUT = 2000
_HISTORICAL_AVG_MIN_SAMPLES = 3
_HISTORICAL_AVG_LOOKBACK = 20


def _estimate_tshirt_tokens(story_id: str = None, discipline: str = None, phase: str = None) -> tuple:
    """Fallback chain for estimated_tshirt tier (spec §5.1). Returns (in_tokens, out_tokens, estimate_basis).
    Tier 1: story's estimated_tokens (split evenly in/out).
    Tier 2: historical average from cost_entries actual/estimated_token_rate rows,
            same discipline+phase, >=3 samples.
    Tier 3: fixed conservative default.
    """
    conn = _pkg("_get_db")()
    try:
        if story_id:
            row = conn.execute(
                "SELECT estimated_tokens FROM stories WHERE story_id=?", (story_id,)
            ).fetchone()
            if row and row[0]:
                half = row[0] // 2
                return half, row[0] - half, "story_estimate"
        if discipline and phase:
            rows = conn.execute(
                """SELECT cost_entries.input_tokens, cost_entries.output_tokens
                   FROM cost_entries
                   JOIN stories ON cost_entries.story_id = stories.story_id
                   WHERE stories.discipline = ? AND stories.phase = ?
                     AND cost_entries.cost_source IN ('actual', 'estimated_token_rate')
                   ORDER BY cost_entries.id DESC LIMIT ?""",
                (discipline, phase, _HISTORICAL_AVG_LOOKBACK),
            ).fetchall()
            if len(rows) >= _HISTORICAL_AVG_MIN_SAMPLES:
                avg_in = sum(r[0] or 0 for r in rows) // len(rows)
                avg_out = sum(r[1] or 0 for r in rows) // len(rows)
                return avg_in, avg_out, "historical_avg"
        return _FIXED_DEFAULT_TOKENS_IN, _FIXED_DEFAULT_TOKENS_OUT, "fixed_default"
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k estimate_tshirt -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): estimated_tshirt fallback chain sourced from cost_entries, not stories.actual_tokens"
```

---

## Task 6: `_resolve_cost_tier()` and `update_costs()` refactor

**Files:**
- Modify: `synlynk/costs.py:158-205` (`update_costs`)
- Test: `tests/test_cost_ledger.py`

This is the task that fixes the `cost_entries.agent`-stores-username bug (Grok's finding) and makes `update_costs()` the always-write, tier-aware orchestrator that every caller in Tasks 7-10 uses.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_ledger.py (append)
from synlynk.costs import _resolve_cost_tier, update_costs


def test_resolve_cost_tier_regex_pair_subscription():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="regex_pair")
    assert (cost_source, basis) == ("estimated_token_rate", "regex_pair")


def test_resolve_cost_tier_regex_pair_local_is_actual():
    cost_source, basis = _resolve_cost_tier(agent="local", basis="regex_pair")
    assert cost_source == "actual"
    assert basis is None


def test_resolve_cost_tier_total_split_always_tshirt():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="total_split")
    assert (cost_source, basis) == ("estimated_tshirt", "total_split")


def test_resolve_cost_tier_none_returns_none():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="none")
    assert cost_source is None


def test_update_costs_writes_agent_name_not_username(project_dir, monkeypatch):
    """Regression test for the cost_entries.agent-stores-username bug (Grok's review)."""
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    update_costs(
        "claude -p 'do the thing'", 1000, 500, 12.3,
        model_version="claude-sonnet-4-6", agent="claude",
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT agent FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "claude"


def test_update_costs_zero_tokens_still_writes_tshirt_row(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    update_costs("claude -p 'x'", 0, 0, 5.0, model_version="claude-sonnet-4-6", agent="claude")
    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "resolve_cost_tier or update_costs" -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Add `_resolve_cost_tier` to `synlynk/costs.py`, above `update_costs`:

```python
def _resolve_cost_tier(agent: str, basis: str) -> tuple:
    """Maps an extraction basis + billing mode to (cost_source, estimate_basis).
    Returns (None, None) for basis == 'none' — caller must run the t-shirt
    fallback chain (_estimate_tshirt_tokens) instead."""
    if basis in ("regex_pair", "structured_output"):
        billing_mode = _resolve_billing_mode(agent)
        if billing_mode == "actual":
            return "actual", None
        return "estimated_token_rate", basis
    if basis == "total_split":
        return "estimated_tshirt", "total_split"
    return None, None
```

Replace `update_costs()` (lines 158-205) entirely:

```python
def update_costs(command: str, in_tokens: int, out_tokens: int, duration: float,
                 cache_read_tokens=None, model_version=None, story_id=None,
                 epic_id=None, phase_id=None, agent=None, basis="none",
                 job_id=None, discipline=None, phase=None) -> None:
    """Resolves a provenance tier and writes exactly one cost_entries row via
    the _insert_cost_row chokepoint. Never skips a write — a zero-token or
    unextractable result falls through to the estimated_tshirt chain."""
    agent_name = agent or (command.split()[0] if command else "")
    if not model_version:
        model_version = extract_model_version("", agent=agent_name) if agent_name else "unknown"

    cost_source, estimate_basis = _resolve_cost_tier(agent_name, basis)
    if cost_source is None:
        in_tokens, out_tokens, estimate_basis = _estimate_tshirt_tokens(
            story_id=story_id, discipline=discipline, phase=phase
        )
        cost_source = "estimated_tshirt"

    rates = _model_rate_for_version(model_version, agent=agent_name)
    cache_read_tokens = 0 if cache_read_tokens is None else cache_read_tokens
    est_cost = (
        (in_tokens / 1000 * rates["input"]) +
        (out_tokens / 1000 * rates["output"]) +
        (cache_read_tokens / 1000 * rates["cache_read"])
    )
    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    flag = "" if cost_source == "actual" else ("[legacy] " if cost_source == "legacy_unknown" else "[est] ")
    entry = (f"| {ts} | {agent_name} | 1 | {in_tokens}/{out_tokens} "
             f"| {flag}${est_cost:.4f} | exec: {short_cmd} |\n")

    _pkg("_insert_cost_row")(
        session_date=ts, agent=agent_name, model=model_version,
        input_tokens=in_tokens, output_tokens=out_tokens, cache_read_tokens=cache_read_tokens,
        cost_source=cost_source, estimate_basis=estimate_basis, total_cost_usd=est_cost,
        notes=f"exec: {short_cmd}", story_id=story_id, epic_id=epic_id, phase_id=phase_id,
        job_id=job_id,
    )

    if _pkg("_is_migrated")():
        costs_file = os.path.join(_pkg("_synlynk_project_docs_dir")(), "costs.md")
        os.makedirs(os.path.dirname(costs_file), exist_ok=True)
        with open(costs_file, "a") as f:
            f.write(entry)
        _pkg("_dr_sync")("costs.md")
    else:
        _pkg("_check_upstream_divergence")()
        costs_file = os.path.join(_pkg("_docs_dir")(), "costs.md")
        if os.path.exists(costs_file):
            with open(costs_file, "a") as f:
                f.write(entry)
```

Note: `_insert_cost_row` needs to be importable via `_pkg()` — it lives in `db.py`, and `db.py` functions are re-exported from `synlynk/__init__.py` (same pattern as `_get_db`, already used elsewhere in `costs.py`). Task 7 confirms `_insert_cost_row` is added to `__init__.py`'s import list from `db.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "resolve_cost_tier or update_costs" -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): update_costs always writes via tier resolution, fixes agent-stores-username bug"
```

---

## Task 7: Export `_insert_cost_row` from `synlynk/__init__.py`

**Files:**
- Modify: `synlynk/__init__.py` (import list, two locations: line ~94 area and line ~3392 area, matching the existing dual-import pattern for `parse_costs_md` / `_parse_costs_md`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
def test_insert_cost_row_reachable_via_pkg_lookup():
    import synlynk
    assert hasattr(synlynk, "_insert_cost_row")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k reachable_via_pkg -v`
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Implement**

In `synlynk/__init__.py`, find the import block containing `parse_costs_md,` (around line 94) — it imports from `synlynk.costs`. Find the import block containing `_parse_costs_md,` (around line 3392) — it imports from `synlynk.db`. Add `_insert_cost_row,` alphabetically into the same `from synlynk.db import (...)` block that already has `_parse_costs_md,`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k reachable_via_pkg -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "chore(costs): export _insert_cost_row from synlynk package namespace"
```

---

## Task 8: `dispatch.py` — remove the zero-token write gate

**Files:**
- Modify: `synlynk/dispatch.py:1007-1039`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
def test_dispatch_writes_cost_row_even_on_zero_token_extraction(project_dir, monkeypatch, git_worktree_repo):
    import synlynk
    import synlynk.dispatch as dispatch_mod
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(dispatch_mod, "extract_tokens", lambda text: synlynk.costs._TokenCounts(0, 0, 0, "none"))
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **k: _FakeProcess())
    # Full dispatch_agent() invocation is covered by existing dispatch tests (test_dispatch_cycle.py);
    # this test targets exec_command's write-gate directly via a minimal fake process.
    class _FakeProcess:
        returncode = 0
        stdout = None
        def wait(self): return 0
        def poll(self): return 0
    dispatch_mod.exec_command(["claude", "-p", "hi"], generate_context=lambda: None,
                               check_budgets=lambda: None, set_state=lambda s: None,
                               extract_tokens=lambda t: synlynk.costs._TokenCounts(0, 0, 0, "none"),
                               extract_model_version=lambda t, agent=None: "claude-sonnet-4-6",
                               model_rate_for_version=None, update_costs=synlynk.costs.update_costs,
                               check_costs=lambda: None, log_telemetry=lambda e: None,
                               get_username=lambda: "nikhil")
    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source FROM cost_entries").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "estimated_tshirt"
```

**Note:** if `exec_command`'s actual signature differs from the keyword-argument shape assumed above (it takes an internal dependency-injection pattern per the code read in Task context — `generate_context`, `check_budgets`, `extract_tokens`, `update_costs` etc. are all passed as parameters, confirmed at `dispatch.py:960-1043`), adjust the call to match the real parameter list found by running `python3 -c "import synlynk.dispatch as d, inspect; print(inspect.signature(d.exec_command))"` before writing the test body — the goal (assert a row exists with `cost_source='estimated_tshirt'` after a zero-token run) is what matters, not the exact fake-process scaffolding.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k dispatch_writes_cost_row_even_on_zero -v`
Expected: FAIL — no row written (current gate skips the write).

- [ ] **Step 3: Implement**

In `synlynk/dispatch.py`, replace lines 1007-1039 (the `if extract_tokens:` block through the `else: print("Token count unavailable...")`) with:

```python
        if extract_tokens:
            token_counts = extract_tokens(output_text)
            in_tokens, out_tokens = token_counts
            cache_read_tokens = getattr(token_counts, "cache_read_tokens", 0)
            basis = getattr(token_counts, "basis", "none")
        else:
            in_tokens, out_tokens, cache_read_tokens, basis = 0, 0, 0, "none"

        if not _is_interactive(cmd_args):
            model_version = extract_model_version(output_text, agent=cmd_args[0]) if extract_model_version else "unknown"
            if update_costs:
                update_costs(
                    " ".join(cmd_args),
                    in_tokens,
                    out_tokens,
                    duration,
                    cache_read_tokens=cache_read_tokens,
                    model_version=model_version,
                    agent=cmd_args[0],
                    basis=basis,
                )
            if in_tokens > 0 or out_tokens > 0:
                print(f"  ⚡ Tokens: {in_tokens:,} in / {out_tokens:,} out")
            else:
                print(f"  ⚡ Token count unavailable — logged as estimated_tshirt fallback")
        else:
            print("  ⚡ Token count unavailable (interactive mode)")
```

This removes the `if in_tokens > 0:` gate entirely — `update_costs()` is now called unconditionally for every non-interactive run, and `update_costs()` itself (Task 6) handles the zero-token fallback internally.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k dispatch_writes_cost_row_even_on_zero -v`
Expected: PASS

- [ ] **Step 5: Run the full existing dispatch test suite to check for regressions**

Run: `pytest tests/test_dispatch_cycle.py tests/test_agy_dispatch_fix.py -v`
Expected: PASS — no regressions from removing the gate.

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_cost_ledger.py
git commit -m "fix(dispatch): remove zero-token write gate, always write a cost row"
```

---

## Task 9: Wire `jobs.py` reconcile paths to the chokepoint

**Files:**
- Modify: `synlynk/jobs.py` (`_reconcile_jobs` at line 851, `_reconcile_daemon_jobs` at line 1213)
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
def test_reconcile_daemon_jobs_writes_cost_row(project_dir, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, pid, status, started_at, log_path) "
        "VALUES ('job-recon-1', 'claude', NULL, 999999, 'running', '2026-07-13T00:00:00', ?)",
        (os.path.join(project_dir, "job-recon-1.log"),)
    )
    conn.commit()
    conn.close()
    with open(os.path.join(project_dir, "job-recon-1.log"), "w") as f:
        f.write("Input tokens: 500. Output tokens: 200.")

    monkeypatch.setattr(jobs_mod.os, "waitpid", lambda pid, opts: (pid, 0))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda pid, sig: None)

    jobs_mod._reconcile_daemon_jobs()

    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries WHERE job_id='job-recon-1'").fetchone()
    conn.close()
    assert row is not None
    assert row[1] == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k reconcile_daemon_jobs_writes -v`
Expected: FAIL — no row (reconcile path currently only writes `daemon_jobs` status, never `cost_entries`).

- [ ] **Step 3: Implement**

In `synlynk/jobs.py`, in `_reconcile_daemon_jobs()`, immediately after the `in_tokens, out_tokens = _pkg("extract_tokens")(log_text)` line at 1213 and before the `cost_usd = _job_cost_usd(...)` line, insert:

```python
                token_counts = _pkg("extract_tokens")(log_text)
                in_tokens, out_tokens = token_counts
                basis = getattr(token_counts, "basis", "none")
                model_version = _pkg("extract_model_version")(log_text, agent=agent)
                _pkg("update_costs")(
                    f"{agent} job {job_id}", in_tokens, out_tokens, duration_s or 0.0,
                    model_version=model_version, story_id=story_id, agent=agent,
                    basis=basis, job_id=job_id,
                )
                cost_usd = _job_cost_usd(agent, in_tokens, out_tokens, model_version)
```

(this replaces the existing bare `in_tokens, out_tokens = _pkg("extract_tokens")(log_text)` line — the two-value unpack still works unchanged since `_TokenCounts.__iter__` still yields 2 items per Task 3.)

Apply the same pattern in `_reconcile_jobs()` at line 851 — replace:

```python
            in_tokens, out_tokens = _pkg("extract_tokens")(log_text)
            cost_usd = _job_cost_usd(
                job.get("agent", ""),
                in_tokens,
                out_tokens,
                job.get("model_version") or job.get("model_at_dispatch"),
            )
```

with:

```python
            token_counts = _pkg("extract_tokens")(log_text)
            in_tokens, out_tokens = token_counts
            basis = getattr(token_counts, "basis", "none")
            model_version = job.get("model_version") or job.get("model_at_dispatch")
            _pkg("update_costs")(
                f"{job.get('agent', '')} job {job.get('id', '')}", in_tokens, out_tokens,
                duration_s or 0.0, model_version=model_version, story_id=job.get("story_id"),
                agent=job.get("agent", ""), basis=basis, job_id=job.get("id"),
            )
            cost_usd = _job_cost_usd(
                job.get("agent", ""),
                in_tokens,
                out_tokens,
                model_version,
            )
```

Both `update_costs` and `extract_model_version` must be reachable via `_pkg()` in `jobs.py` — check the top of `jobs.py` for an existing `_pkg` helper (same pattern as `costs.py`'s); if `update_costs`/`extract_model_version` aren't already in `synlynk/__init__.py`'s namespace reachable by `_pkg`, they already are (confirmed: `dispatch.py` calls them the same way, and both files rely on the same `_pkg()`-via-`sys.modules["synlynk"]` lookup pattern, so no new export is needed — `update_costs` and `extract_model_version` are already imported into `synlynk/__init__.py` per the `costs.py` grep in this plan's research).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k reconcile_daemon_jobs_writes -v`
Expected: PASS

- [ ] **Step 5: Run the full existing jobs test suite to check for regressions**

Run: `pytest tests/test_jobs.py tests/test_fleet_scheduler.py -v`
Expected: PASS — no regressions.

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_cost_ledger.py
git commit -m "fix(jobs): wire reconcile paths to cost ledger, closing the never-writes gap"
```

---

## Task 10: `cmd_launch()` — route through fallback chain instead of bare 0/0

**Files:**
- Modify: `synlynk/__init__.py:2049-2067`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
def test_cmd_launch_writes_estimated_tshirt_not_bare_zero(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "generate_context", lambda scope=None: None)
    monkeypatch.setattr(synlynk.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda e: None)
    synlynk.cmd_launch("claude", story_id=None)
    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k cmd_launch_writes_estimated_tshirt -v`
Expected: FAIL — current code writes `input_tokens=0` untagged.

- [ ] **Step 3: Implement**

In `synlynk/__init__.py`, replace lines 2056-2066:

```python
    model_version = extract_model_version("", agent=agent)
    update_costs(
        cli,
        0,
        0,
        duration,
        cache_read_tokens=0,
        model_version=model_version,
        story_id=story_id,
        agent=agent,
    )
```

with:

```python
    model_version = extract_model_version("", agent=agent)
    update_costs(
        cli,
        0,
        0,
        duration,
        cache_read_tokens=0,
        model_version=model_version,
        story_id=story_id,
        agent=agent,
        basis="none",
    )
```

`update_costs()` (Task 6) already resolves `basis="none"` through the t-shirt fallback chain internally — the only change needed at this call site is passing `basis="none"` explicitly instead of relying on the old default of no tier info at all.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k cmd_launch_writes_estimated_tshirt -v`
Expected: PASS

- [ ] **Step 5: Run existing launch tests to check for regressions**

Run: `pytest tests/test_launch.py tests/test_launch_templates.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "fix(launch): route synlynk launch cost rows through the tshirt fallback chain"
```

---

## Task 11: Wire `support_engineer.py`'s investigation call site

**Files:**
- Modify: `synlynk/support_engineer.py:412-432` (`_run_investigation`)
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
def test_run_investigation_writes_one_cost_row(project_dir, monkeypatch):
    import synlynk
    import synlynk.support_engineer as se_mod
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(se_mod, "generate_context", lambda scope=None: None)
    monkeypatch.setattr(se_mod.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(se_mod, "LOGS_DIR", str(project_dir))
    monkeypatch.setattr(se_mod, "PROMPTS_DIR", str(project_dir))

    finding = {"signal_hash": "abc123", "type": "flatline", "severity": "high",
               "detail": "3 consecutive failures", "summary": "flatline detected"}
    agent_cfg = {"investigator": "claude"}

    investigation = se_mod._run_investigation(finding, agent_cfg)

    conn = synlynk._get_db()
    rows = conn.execute("SELECT cost_source FROM cost_entries").fetchall()
    conn.close()
    assert len(rows) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k run_investigation_writes_one_cost_row -v`
Expected: FAIL — zero rows (confirmed zero `update_costs()` calls in `support_engineer.py` today).

- [ ] **Step 3: Implement**

In `synlynk/support_engineer.py`, in `_run_investigation()`, immediately after the `log_text` read block (after line 419, `log_text = open(log_file).read()`) and before the `import re as _re` line, insert:

```python
    duration_s = time.time() - _investigation_start
    token_counts = _pkg("extract_tokens")(log_text)
    in_tokens, out_tokens = token_counts
    basis = getattr(token_counts, "basis", "none")
    model_version = _pkg("extract_model_version")(log_text, agent=agent)
    _pkg("update_costs")(
        f"{agent} investigate {job_id}", in_tokens, out_tokens, duration_s,
        model_version=model_version, story_id=story_id, agent=agent, basis=basis,
    )
```

This requires a start-time marker. Add `_investigation_start = time.time()` immediately before the `try:` block that wraps `subprocess.run(["sh", "-c", shell_cmd], timeout=300)` (line 412).

The fixer path (`_apply_fix`, which reuses `investigation["log_text"]` rather than making its own model call) is intentionally **not** wired here — per spec §7, it "does not get a second cost row unless it makes its own separate model call," and the current fixer implementation applies a diff via `git apply` with no separate CLI invocation, so no cost row is warranted there.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k run_investigation_writes_one_cost_row -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/support_engineer.py tests/test_cost_ledger.py
git commit -m "feat(support-engineer): write one cost row per investigation, closing the zero-calls gap"
```

---

## Task 12: `synlynk cost log` command

**Files:**
- Modify: `synlynk/cli.py` (new parser)
- Modify: `synlynk/db.py` (new `cmd_cost_log`)
- Modify: `synlynk/__init__.py` (import + dispatch wiring)
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_ledger.py (append)
from synlynk.db import cmd_cost_log


def test_cmd_cost_log_writes_estimated_manual_row(project_dir, monkeypatch, capsys):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    cmd_cost_log(agent="claude", tokens_in=2000, tokens_out=800, story_id=None, note="brainstorm session")
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, estimate_basis, input_tokens, output_tokens, phase_id, notes FROM cost_entries"
    ).fetchone()
    conn.close()
    assert row[0] == "estimated_manual"
    assert row[1] == "cli_manual_entry"
    assert (row[2], row[3]) == (2000, 800)
    assert row[5] == "brainstorm session"


def test_cmd_cost_log_with_story_id(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute("INSERT INTO stories (story_id, title, discipline, phase) VALUES ('story-9', 'T', 'backend', 'build')")
    conn.commit()
    conn.close()
    cmd_cost_log(agent="claude", tokens_in=500, tokens_out=200, story_id="story-9", note=None)
    conn = synlynk._get_db()
    row = conn.execute("SELECT story_id FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "story-9"


def test_cmd_cost_log_rejects_negative_tokens(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    with pytest.raises(ValueError):
        cmd_cost_log(agent="claude", tokens_in=-1, tokens_out=200, story_id=None, note=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k cmd_cost_log -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `cmd_cost_log` in `synlynk/db.py`**

Add after `cmd_score_list` (or any convenient point after the existing `cmd_score_*` functions):

```python
def cmd_cost_log(agent: str, tokens_in: int, tokens_out: int, story_id: str = None,
                 note: str = None) -> None:
    """Logs a manually-reported cost row for native/unwrapped sessions (spec §5.2).
    Tagged estimated_manual, estimate_basis='cli_manual_entry'. Replaces the
    parallel <project>_costs.md file for this class of work."""
    from synlynk import (
        _GREEN, _RESET, _get_db, _insert_cost_row, extract_model_version, get_username,
    )
    if tokens_in < 0 or tokens_out < 0:
        raise ValueError("tokens-in and tokens-out must be non-negative")

    conn = _get_db()
    discipline = phase = None
    if story_id:
        row = conn.execute(
            "SELECT discipline, phase FROM stories WHERE story_id=?", (story_id,)
        ).fetchone()
        if row:
            discipline, phase = row
    conn.close()

    model_version = extract_model_version("", agent=agent)
    from synlynk.costs import _model_rate_for_version
    rates = _model_rate_for_version(model_version, agent=agent)
    est_cost = (tokens_in / 1000 * rates["input"]) + (tokens_out / 1000 * rates["output"])
    ts = time.strftime('%Y-%m-%d %H:%M')

    _insert_cost_row(
        session_date=ts, agent=agent, model=model_version,
        input_tokens=tokens_in, output_tokens=tokens_out, cache_read_tokens=0,
        cost_source="estimated_manual", estimate_basis="cli_manual_entry",
        total_cost_usd=est_cost, notes=note, story_id=story_id,
    )
    label = f"story {story_id}" if story_id else f"phase={phase or 'dream/plan'} (no story)"
    print(f"  {_GREEN}✓{_RESET} Manual cost entry logged for {agent} — {label}: "
          f"{tokens_in:,} in / {tokens_out:,} out, est. ${est_cost:.4f}")
```

`time` is already imported at the top of `db.py` (used elsewhere for `datetime('now')` defaults and other `cmd_*` functions) — verify with `grep -n "^import time" synlynk/db.py`; if absent, add `import time` to the top-of-file imports.

Add the CLI parser in `synlynk/cli.py`, immediately after the `score_parser` block (after line ~536, before `identity_parser`):

```python
    cost_parser = subparsers.add_parser("cost", help="Manage the cost ledger")
    cost_sub = cost_parser.add_subparsers(dest="cost_action")
    cost_log_parser = cost_sub.add_parser("log", help="Log a manual cost entry for native/unwrapped sessions")
    cost_log_parser.add_argument("--agent", required=True)
    cost_log_parser.add_argument("--tokens-in", type=int, required=True, dest="tokens_in")
    cost_log_parser.add_argument("--tokens-out", type=int, required=True, dest="tokens_out")
    cost_log_parser.add_argument("--story-id", default=None, dest="story_id")
    cost_log_parser.add_argument("--note", default=None)
```

Wire dispatch in `synlynk/__init__.py`, next to the `elif args.command == "score":` block (around line 736):

```python
    elif args.command == "cost":
        if args.cost_action == "log":
            cmd_cost_log(args.agent, args.tokens_in, args.tokens_out,
                        story_id=args.story_id, note=args.note)
```

Add `cmd_cost_log,` to the `from synlynk.db import (...)` block alongside `cmd_score_add` (line ~178).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k cmd_cost_log -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Manual CLI smoke test**

Run: `cd /tmp && mkdir synlynk-smoke-test && cd synlynk-smoke-test && python3 -m synlynk init --non-interactive 2>&1 | tail -5 && python3 -m synlynk cost log --agent claude --tokens-in 3000 --tokens-out 1200 --note "brainstorm smoke test"`
Expected: prints `✓ Manual cost entry logged for claude — phase=dream/plan (no story): 3,000 in / 1,200 out, est. $0.0270`

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/cli.py synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "feat(cost): add synlynk cost log command for native/unwrapped session tracking"
```

---

## Task 13: `synlynk release` uses the `cost log` mechanism

**Files:**
- Modify: wherever `synlynk release` is implemented (locate via `grep -n "def cmd_release" synlynk/*.py` at task start)
- Test: `tests/test_cost_ledger.py`

Per spec §7, `synlynk release` closes its coverage cell by documentation/convention, not new code — it's a native/PM-style invocation like brainstorming, so it uses `synlynk cost log` the same way a human would after a release session. This task only needs a CLAUDE.md/doc note (folded into Task 14's protocol addition) — **no code change**, since `cmd_release` doesn't itself dispatch a CLI agent that could be auto-wired.

- [ ] **Step 1: Confirm `cmd_release` has no wrapped-agent invocation to wire**

Run: `grep -n "def cmd_release" -A 20 synlynk/*.py`
Expected: confirms `cmd_release` shells out to `gh release create` / git tooling directly, with no `dispatch_agent()` or CLI-agent subprocess call — i.e., there is genuinely nothing to instrument, matching the spec's conclusion.

- [ ] **Step 2: No test needed — this is a documentation-only closure, tracked in Task 14's protocol note.**

(No commit for this task in isolation — it's folded into Task 14.)

---

## Task 14: Reporting — `[est]`/`[legacy]` flags and parser compatibility

**Files:**
- Modify: `synlynk/costs.py:271-291` (`parse_costs_md`)
- Modify: `synlynk/db.py:165-190` (`_parse_costs_md`)
- Test: `tests/test_cost_ledger.py`

Task 6 already changed the written format to prefix non-`actual` rows with `[est] ` or `[legacy] ` before the `$` (e.g. `[est] $0.0270`). Both parsers currently do `float(parts[N].lstrip("$"))` / `.replace('$', '')`, which raises or silently mis-parses on a `[est] ` / `[legacy] ` prefix that comes *before* the `$`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_ledger.py (append)
from synlynk.costs import parse_costs_md as costs_parse_costs_md
from synlynk.db import _parse_costs_md as db_parse_costs_md


def test_costs_py_parse_costs_md_handles_est_prefix(project_dir, monkeypatch):
    import synlynk
    docs_dir = os.path.join(project_dir, "project-docs")
    monkeypatch.setattr(synlynk, "_docs_dir", lambda: docs_dir)
    with open(os.path.join(docs_dir, "costs.md"), "a") as f:
        f.write("| 2026-07-13 10:00 | claude | 1 | 1000/500 | [est] $0.0270 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:05 | claude | 1 | 800/400 | [legacy] $0.0100 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:10 | claude | 1 | 200/100 | $0.0050 | exec: claude -p |\n")
    total_usd, total_requests = costs_parse_costs_md()
    assert total_requests == 3
    assert round(total_usd, 4) == round(0.0270 + 0.0100 + 0.0050, 4)


def test_db_parse_costs_md_handles_prefixed_cost_column():
    content = "| 2026-07-13 | claude | claude-sonnet-4-6 | 1000 | 500 | 0 | [est] $0.0270 | note |\n"
    rows = db_parse_costs_md(content)
    assert len(rows) == 1
    assert rows[0]["total_cost_usd"] == 0.0270
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "parse_costs_md" -v`
Expected: FAIL — `ValueError` swallowed by the existing bare `try/except: continue`/`return default`, producing wrong totals (e.g. `total_requests` undercounts).

- [ ] **Step 3: Implement**

In `synlynk/costs.py`, `parse_costs_md()`, replace:

```python
            cost_str = parts[5].lstrip("$")
            try:
                total_usd += float(cost_str)
                total_requests += 1
            except ValueError:
                continue
```

with:

```python
            cost_str = parts[5]
            for prefix in ("[est] ", "[legacy] ", "~"):
                if cost_str.startswith(prefix):
                    cost_str = cost_str[len(prefix):]
                    break
            cost_str = cost_str.lstrip("$")
            try:
                total_usd += float(cost_str)
                total_requests += 1
            except ValueError:
                continue
```

In `synlynk/db.py`, `_parse_costs_md()`, replace the `_float` helper:

```python
        def _float(v):
            try: return float(v.replace('$', '').replace(',', ''))
            except: return None
```

with:

```python
        def _float(v):
            for prefix in ("[est] ", "[legacy] "):
                if v.startswith(prefix):
                    v = v[len(prefix):]
                    break
            try: return float(v.replace('$', '').replace(',', ''))
            except: return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "parse_costs_md" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py synlynk/db.py tests/test_cost_ledger.py
git commit -m "fix(costs): parsers tolerate [est]/[legacy] prefixed cost cells"
```

---

## Task 15: `.synlynk/model_rates.json` scaffolded by `synlynk init`

**Files:**
- Modify: `synlynk/__init__.py` (`init()` function — locate the block that writes `.synlynk/config.json` and add a sibling write for `model_rates.json`)
- Test: `tests/test_init_business_goals.py` pattern reused — add to `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
def test_init_writes_model_rates_json(tmp_path, monkeypatch):
    import synlynk
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "state.db"))
    synlynk.init()
    rates_path = tmp_path / ".synlynk" / "model_rates.json"
    assert rates_path.exists()
    data = json.loads(rates_path.read_text())
    assert data["unit"] == "usd_per_1k_tokens"
    assert data["billing_mode"]["local"] == "actual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k init_writes_model_rates -v`
Expected: FAIL — file does not exist.

- [ ] **Step 3: Implement**

In `synlynk/__init__.py`, in `init()`, find the block that creates `.synlynk/config.json` (search `os.makedirs(".synlynk"` or `config.json` in `init()`). Immediately after that write, add:

```python
    rates_path = os.path.join(".synlynk", "model_rates.json")
    if not os.path.exists(rates_path):
        from synlynk.costs import _HARDCODED_FALLBACK_RATES
        rates_seed = dict(_HARDCODED_FALLBACK_RATES)
        rates_seed["rates_updated_at"] = time.strftime("%Y-%m-%d")
        with open(rates_path, "w") as f:
            json.dump(rates_seed, f, indent=2)
        print(f"  ✓ Created {rates_path}")
```

`init()` per `CLAUDE.md`'s documented behavior "Skips existing files" — the `if not os.path.exists` guard matches that convention.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k init_writes_model_rates -v`
Expected: PASS

- [ ] **Step 5: Run the full init test suite to check for regressions**

Run: `pytest tests/test_init_business_goals.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "feat(init): scaffold .synlynk/model_rates.json on synlynk init"
```

---

## Task 16: `check_budgets()` sums all tiers, separates failed-job placeholder noise

**Files:**
- Modify: `synlynk/costs.py:242-268` (`check_budgets`)
- Test: `tests/test_cost_ledger.py`

Per spec §8, all tiers (including `legacy_unknown`) count toward budget alerts — this already holds true since `parse_costs_md()` sums every row regardless of tier (Task 14 didn't change that). The new requirement is the separate failed-job placeholder sub-line.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_ledger.py (append)
from synlynk.costs import check_budgets


def test_check_budgets_reports_failed_job_placeholders_separately(project_dir, monkeypatch, capsys):
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "load_config", lambda: {
        "budget": {"limit_usd": 1000.0, "limit_requests": 1000}
    })
    monkeypatch.setattr(synlynk.costs, "parse_costs_md", lambda: (0.5, 3))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, estimate_basis, notes) VALUES "
        "('2026-07-13', 'claude', 'claude-sonnet-4-6', 5000, 2000, 0.1, 'estimated_tshirt', "
        "'fixed_default', 'exec: failed job, exit 1')"
    )
    conn.commit()
    conn.close()
    check_budgets()
    captured = capsys.readouterr()
    assert "failed-job placeholder" in captured.out.lower()
```

**Note:** this test asserts on a specific heuristic for "which rows count as failed-job placeholders" — the implementation below uses `notes LIKE '%failed%'` as the signal, since `update_costs()` (Task 6) doesn't currently thread a distinct `job_failed` boolean through to the notes field. If a cleaner signal is preferred (e.g., a dedicated `job_failed BOOLEAN` column), that's a valid alternative — pick one and keep the test's assertion aligned with whichever signal is implemented. This plan uses the notes-substring approach because it requires no additional schema column.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k failed_job_placeholders -v`
Expected: FAIL — no such sub-line printed today.

- [ ] **Step 3: Implement**

First, in `synlynk/dispatch.py`'s `update_costs()` call site (Task 8's replacement block), thread the failure state into the `command` label passed to `update_costs`, so the note captures it — replace:

```python
                update_costs(
                    " ".join(cmd_args),
```

with:

```python
                cmd_label = " ".join(cmd_args) + (" [failed job]" if exit_code != 0 and (in_tokens == 0 and out_tokens == 0) else "")
                update_costs(
                    cmd_label,
```

Then in `synlynk/costs.py`, add to `check_budgets()` (after the existing `total_reqs` warning block, before the function ends):

```python
    conn = _pkg("_get_db")()
    try:
        failed_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_cost_usd), 0) FROM cost_entries "
            "WHERE cost_source = 'estimated_tshirt' AND estimate_basis = 'fixed_default' "
            "AND notes LIKE '%failed job%'"
        ).fetchone()
    finally:
        conn.close()
    failed_count, failed_usd = failed_row
    if failed_count:
        print(f"  ℹ️  {failed_count} failed-job placeholder estimates, ${failed_usd:.2f} "
              "(not blended into the spend total above)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k failed_job_placeholders -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py synlynk/dispatch.py tests/test_cost_ledger.py
git commit -m "feat(costs): check_budgets reports failed-job placeholder estimates as a separate sub-line"
```

---

## Task 17: DB-level enforcement test + call-site audit (primary safety nets)

**Files:**
- Test only: `tests/test_cost_ledger.py`

Per spec §10, the raw-INSERT `IntegrityError` test (already written in Task 1, Step 1) is the **primary** enforcement mechanism. This task adds the secondary call-site audit net.

- [ ] **Step 1: Write the call-site audit test**

```python
# tests/test_cost_ledger.py (append)
import ast


def test_only_insert_cost_row_writes_to_cost_entries():
    """Every INSERT/UPDATE against cost_entries in the source tree must go
    through _insert_cost_row — no other call site is allowed to write directly."""
    allowed_files_with_direct_sql = {
        "synlynk/db.py",  # _insert_cost_row itself + the one-time _migrate_import backfill path + migration rebuild
    }
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    violations = []
    for dirpath, _, filenames in os.walk(os.path.join(repo_root, "synlynk")):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            rel_path = os.path.relpath(os.path.join(dirpath, fname), repo_root)
            with open(os.path.join(dirpath, fname)) as f:
                content = f.read()
            if rel_path in allowed_files_with_direct_sql:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                if ("INSERT INTO cost_entries" in line or "UPDATE cost_entries" in line):
                    violations.append(f"{rel_path}:{lineno}")
    assert violations == [], f"Direct cost_entries writes outside db.py: {violations}"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k only_insert_cost_row_writes -v`
Expected: PASS — after Tasks 1-16, the only `INSERT INTO cost_entries` / `UPDATE cost_entries` strings left in the tree are inside `db.py` (`_insert_cost_row`, `_migrate_import`'s one-time backfill importer, and the Task 1 migration rebuild). If this fails, it means a call site was missed in an earlier task — go back and fix it before proceeding.

- [ ] **Step 3: Write the migration/backfill and idempotency/always-write tests referenced in spec §10 that aren't yet covered**

These are already covered by earlier tasks: migration backfill (Task 1), idempotency (Task 2), always-write on zero tokens (Task 6, Task 8). Confirm coverage:

Run: `pytest tests/test_cost_ledger.py -v --collect-only | grep -c "test_"`
Expected: 30+ collected tests spanning all of Tasks 1-16.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cost_ledger.py
git commit -m "test(costs): call-site audit confirms _insert_cost_row is the sole cost_entries writer"
```

---

## Task 18: CLAUDE.md — "Cost Capture Protocol" section

**Files:**
- Modify: `/Users/nikhilsoman/dev/synlynk/CLAUDE.md`

- [ ] **Step 1: Add the protocol section**

Open `/Users/nikhilsoman/dev/synlynk/CLAUDE.md` and add a new section, matching the existing "Blog Post Protocol" and "Workspace Map Update Protocol" sections in placement and weight (insert after "Workspace Map Update Protocol"):

```markdown
## Cost Capture Protocol

**For every PR, before merging:** confirm all dispatched/wrapped work in this PR is
auto-captured (nothing to do — it already is via `dispatch_agent()`/`synlynk exec`),
and any native/PM-session work (brainstorming, design docs, manual fixes) not tied
to a dispatched job has a corresponding `synlynk cost log` entry. If genuinely zero
cost was incurred outside dispatched work, note that explicitly in the PR rather
than skipping the check silently.

`synlynk release` sessions use `synlynk cost log` the same way — there is no
automatic capture for native CLI invocations of `gh release create` / release
tooling.

Enforced by discipline (Claude/PM checks it as part of PR housekeeping), not CI —
matches how the Blog Post Protocol already operates. Not a blocking CI gate.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Cost Capture Protocol to CLAUDE.md"
```

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-07-13-measurement-ledger-hardening-design.md`):

| Spec section | Covered by |
|---|---|
| §2 Core Invariant (no silent `actual`) | Task 1 (NOT NULL, no default), Task 2 (`_insert_cost_row` validates tier), Task 17 (call-site audit) |
| §3 Provenance taxonomy + `estimate_basis` | Task 1 (schema), Task 6 (`_resolve_cost_tier`) |
| §3.1 No silent `actual` enforcement | Task 1 Step 1 (`IntegrityError` test), Task 17 |
| §3.2 Billing mode | Task 4 |
| §3.3 Historical backfill → `legacy_unknown` | Task 1 |
| §4.1 Extraction confidence in Phase 1 | Task 3 |
| §5.1 T-shirt fallback chain, `cost_entries`-sourced (not `stories.actual_tokens`) | Task 5 |
| §5.1.1 Always write a row + `job_id` idempotency | Task 2 (idempotency), Task 6/8 (always-write), Task 9 (reconcile wiring) |
| §5.2 `synlynk cost log` | Task 12 |
| §6 Rate file, `unit` validation, `cost_entries.agent` bug fix | Task 4 (rate file), Task 6 (agent bug fix) |
| §7 Coverage closure (all 8 rows) | Task 8 (exec/dispatch), Task 9 (jobs.py reconcile), Task 10 (launch), Task 11 (support_engineer), Task 12 (dream/plan via cost log), Task 13 (release) |
| §8 Reporting (`[est]`/`[legacy]`, parser fix, budget-noise mitigation) | Task 6 (write format), Task 14 (parsers), Task 16 (budget noise) |
| §9 CLAUDE.md protocol | Task 18 |
| §10 Testing approach (16 items) | Distributed across Tasks 1-17; call-site audit explicitly in Task 17 |
| §11 Out of scope | Not built here — confirmed absent from all tasks (no autopilot fleet, no CI gate, no capability matrix, no local-agent scheduler, no IDE assistants) |

**2. Placeholder scan:** none found. Every task has real code, real assertions, real commands. Task 8's test includes an explicit note that the fake-scaffolding may need adjusting to match `exec_command`'s real signature — this is flagged as a concrete pre-check instruction (run `inspect.signature`), not a vague "handle appropriately."

**3. Type/signature consistency check:**
- `update_costs()` signature is defined once in Task 6 (`agent`, `basis`, `job_id`, `discipline`, `phase` added as new kwargs) and every caller in Tasks 8-12 uses that exact signature.
- `_insert_cost_row()` signature is defined once in Task 2 and used identically in Task 6, Task 12.
- `_estimate_tshirt_tokens()` returns `(in_tokens, out_tokens, estimate_basis)` consistently in Task 5 and Task 6.
- `_TokenCounts.basis` attribute name is consistent across Task 3, and every `getattr(token_counts, "basis", "none")` call site in Tasks 8, 9, 11.
- `_resolve_cost_tier()` returns `(cost_source, estimate_basis)` — a 2-tuple, not the 3-value shape of `_estimate_tshirt_tokens()` — consistently referenced as such in Task 6.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-13-measurement-ledger-hardening-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Per this project's locked agent-role split (CLAUDE.md), implementation is delegated to Agy/Grok/Codex regardless of which option is chosen — "Subagent-Driven" here means dispatching each task via `synlynk dispatch <agent> --task "..." --force-agent --context-mode full` rather than a Claude Code subagent, consistent with how the design review itself was dispatched.

**Which approach?**
