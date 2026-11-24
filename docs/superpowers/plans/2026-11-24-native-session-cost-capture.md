# Native-Session Cost Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. In this repo the implementer stage is routed through `synlynk dispatch` (Codex/Grok/Agy), never Claude. Steps use checkbox (`- [ ]`) syntax for tracking.

**Governing Goal(s):** goal-62f693b8

**Goal:** Capture native Claude Code session usage from transcripts into `cost_entries` automatically, de-duplicated and idempotent, with a hook dispatcher, a derived session-to-PR view, and a backfill that replaces `estimated_manual` guesses.

**Architecture:** `synlynk/native_capture.py` is the single reader/writer (CLI, hook and backfill all call it). `synlynk/session_hooks.py` is a thin dispatcher. A new migration adds a cursor table, a session-to-PR link table, a unique partial index and the `cost_entries_effective` view; every reader moves to the view. Spec: `docs/superpowers/specs/2026-11-24-native-session-cost-capture-design.md` (DECIDE record `dec-11a45658`).

**Tech Stack:** Python 3 stdlib only, SQLite (numbered migrations in `synlynk/migrations/`, latest is `m0040`), pytest. Tests use the autouse `isolated_db` fixture in `tests/conftest.py`.

**Order (spec section 12):** view and guard test, then capture, then backfill, then anything that sums native cost. Do not reorder Tasks 1-2 after later tasks.

**Branching:** one feature branch per task group is fine, but docs go in separate PRs. Every task ends with a commit trailer `Co-Authored-By: <implementing harness trailer>`. Verification runs use `pytest -q`, never `-v` (gh:#2240).

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/migrations/m0041_native_session_capture.py` | cursor table, `session_pr_links`, unique partial index, `cost_entries_effective` view |
| `synlynk/pricing.py` | `price_usd(model, usage)`; wraps `costs._load_model_rates`; unknown model returns `None` |
| `synlynk/native_capture.py` | transcript parsing, dedup, bucketing, upsert, cursor, rescan, exclusions, reconcile, PR-link extraction |
| `synlynk/session_hooks.py` | `dispatch_event(agent, event, payload)`, handler registry, settings.json merge/removal |
| `synlynk/native_backfill.py` | `plan_backfill`, `apply_backfill` |
| `synlynk/cli.py` | `cost capture-session`, `cost link-session`, `cost backfill-native`, `hook claude <event>` |
| `synlynk/doctor.py` | `_hc_native_capture`, `--fix` hook install |
| `synlynk/db.py` | `pr check` native identity fallback via `session_pr_links` |
| `tests/native_capture_fixtures.py` | synthetic transcript builder (counts only, no message text) |
| `tests/test_*native*.py`, `tests/migrations/test_m0041_*.py` | tests per task |

Transcript record shapes used by the fixtures (counts and ids only):

```json
{"type":"assistant","timestamp":"2026-11-24T10:00:00.000Z","sessionId":"s1","message":{"id":"msg_1","model":"claude-sonnet-5-5","usage":{"input_tokens":10,"output_tokens":20,"cache_creation_input_tokens":30,"cache_read_input_tokens":40}}}
{"type":"pr-link","sessionId":"s1","prNumber":5511,"prUrl":"https://github.com/o/r/pull/5511","timestamp":"2026-11-24T10:05:00.000Z"}
```

---

### Task 1: Migration m0041 (cursor, links, unique index, effective view)

**Files:**
- Create: `synlynk/migrations/m0041_native_session_capture.py`
- Modify: `synlynk/migrations/__init__.py` or `runner.py` only if migrations are registered by hand (check how `m0040` is registered and mirror it)
- Test: `tests/migrations/test_m0041_native_session_capture.py`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3

from synlynk.migrations.m0041_native_session_capture import MIGRATION


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT NOT NULL,
            harness TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, total_cost_usd REAL, cost_source TEXT NOT NULL,
            estimate_basis TEXT, job_id TEXT, session_id TEXT, pr_number INTEGER,
            turn_usage_json TEXT, payment_mode TEXT, notes TEXT)"""
    )
    return conn


def test_creates_tables_view_and_index():
    conn = _conn()
    MIGRATION.up(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"native_capture_cursor", "session_pr_links"} <= tables
    views = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    assert "cost_entries_effective" in views


def test_unique_partial_index_blocks_duplicate_transcript_rows():
    conn = _conn()
    MIGRATION.up(conn)
    ins = ("INSERT INTO cost_entries (session_date, model, cost_source, session_id) "
           "VALUES ('2026-11-24', 'm', 'transcript_derived', 's1')")
    conn.execute(ins)
    try:
        conn.execute(ins.replace("2026-11-24", "2026-11-24T23:00:00"))
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised
    # other cost_source values are not constrained
    manual = ins.replace("transcript_derived", "estimated_manual")
    conn.execute(manual)
    conn.execute(manual)


def test_effective_view_hides_superseded_rows_only():
    conn = _conn()
    MIGRATION.up(conn)
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, estimate_basis) VALUES ('d','estimated_manual','superseded_by_transcript')")
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, estimate_basis) VALUES ('d','estimated_manual',NULL)")
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, estimate_basis) VALUES ('d','estimated_manual','unverified_estimate')")
    assert conn.execute("SELECT COUNT(*) FROM cost_entries_effective").fetchone()[0] == 2


def test_idempotent():
    conn = _conn()
    MIGRATION.up(conn)
    MIGRATION.up(conn)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest -q tests/migrations/test_m0041_native_session_capture.py`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Migration 41: native-session capture storage (LIVE-35, gh:#5457)."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS native_capture_cursor (
            session_id      TEXT PRIMARY KEY,
            transcript_path TEXT NOT NULL,
            byte_offset     INTEGER NOT NULL DEFAULT 0,
            anchor          TEXT NOT NULL DEFAULT '',
            final           INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS session_pr_links (
            session_id    TEXT NOT NULL,
            pr_number     INTEGER NOT NULL,
            role          TEXT NOT NULL DEFAULT 'implementer',
            first_seen_ts TEXT,
            source        TEXT NOT NULL,
            PRIMARY KEY (session_id, pr_number, role)
        )"""
    )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_cost_entries_transcript_bucket
           ON cost_entries (session_id, model, substr(session_date, 1, 10))
           WHERE cost_source = 'transcript_derived'"""
    )
    conn.execute("DROP VIEW IF EXISTS cost_entries_effective")
    conn.execute(
        """CREATE VIEW cost_entries_effective AS
           SELECT * FROM cost_entries
           WHERE COALESCE(estimate_basis, '') != 'superseded_by_transcript'"""
    )


MIGRATION = Migration(version=41, name="native_session_capture", up=_up)
```

Note: `SELECT *` in a view freezes columns at creation; the migration drops and recreates the view, and any later migration that adds `cost_entries` columns must recreate it too (add that sentence to the migration docstring).

- [ ] **Step 4: Register and run**

Mirror however `m0040_exploration_spend_tracking` is registered (grep for `m0040`). Run: `pytest -q tests/migrations/test_m0041_native_session_capture.py` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations tests/migrations/test_m0041_native_session_capture.py
git commit -m "feat(capture): m0041 cursor, session_pr_links, unique index, effective view"
```

---

### Task 2: Raw-read guard test and reader migration to `cost_entries_effective`

**Files:**
- Create: `tests/test_cost_entries_raw_read_guard.py`
- Modify: every reader found by the guard (initial list from `grep -rln "FROM cost_entries"`): `synlynk/platform_ops.py`, `db.py`, `governs_gate.py`, `dispatch.py`, `quota.py`, `selftest.py`, `capability_window.py`, `routing.py`, `costs.py`, `quota_capture.py`, `uxcore.py`, `gh_sync.py`, `cost_audit.py`, `jobs.py`, `greenfield/daily_sync.py`, `viz/data.py`, `bin/backfill_api_equivalent_usd.py`

- [ ] **Step 1: Write the guard test**

```python
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+cost_entries\b(?!_)", re.IGNORECASE)

# Writers, schema/migration code and the view definition may touch the raw table.
ALLOWED = {
    "synlynk/migrations",          # directory prefix
    "synlynk/db_schema.py",
    "synlynk/native_capture.py",   # upsert/rescan targets the raw table
    "synlynk/native_backfill.py",
}


def _allowed(rel: str) -> bool:
    return any(rel == a or rel.startswith(a + "/") for a in ALLOWED)


def test_no_raw_cost_entries_reads_outside_allowlist():
    offenders = []
    for path in list((ROOT / "synlynk").rglob("*.py")) + list((ROOT / "bin").glob("*.py")):
        rel = str(path.relative_to(ROOT))
        if _allowed(rel):
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if PATTERN.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "read cost_entries_effective instead:\n" + "\n".join(offenders)
```

- [ ] **Step 2: Run to see the offender list**

Run: `pytest -q tests/test_cost_entries_raw_read_guard.py`
Expected: FAIL listing ~44 lines.

- [ ] **Step 3: Convert readers**

For each listed line, change `FROM cost_entries` / `JOIN cost_entries` to `FROM cost_entries_effective` / `JOIN cost_entries_effective`. Do NOT touch `INSERT INTO`, `UPDATE`, `ALTER TABLE`, `PRAGMA table_info(cost_entries)` (the pattern only matches FROM/JOIN). If a reader runs against a database that has not been migrated to m0041 (tests that build bare schemas), the view will not exist: for those tests add the view creation to the test's schema fixture by calling `MIGRATION.up(conn)` from m0041, not by weakening the code. Where `db.py` creates `cost_entries` at line ~1877 for fresh databases, also ensure the migration runner executes m0041 on fresh databases (the runner runs all migrations; verify with a test that opens a brand-new DB and queries the view).

- [ ] **Step 4: Run guard and affected suites**

Run: `pytest -q tests/test_cost_entries_raw_read_guard.py` Expected: PASS.
Run: `pytest -q -x` Expected: PASS (fix any bare-schema fixtures per Step 3).

- [ ] **Step 5: Commit**

```bash
git add -A synlynk bin tests
git commit -m "refactor(cost): read cost_entries_effective everywhere; add raw-read guard test"
```

---

### Task 3: Pricing interface (`synlynk/pricing.py`)

Spec section 4 step 4 and gh:#5501 interface. The data table itself is #5501; this task adds the interface over the existing `costs._load_model_rates()` (unit `usd_per_1k_tokens`).

**Files:**
- Create: `synlynk/pricing.py`
- Test: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing test**

```python
from synlynk import pricing


def test_known_model_prices_all_four_token_kinds(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", lambda: {"models": {"m1": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}}})
    usd = pricing.price_usd("m1", input_tokens=1000, output_tokens=1000, cache_read_tokens=1_000_000, cache_creation_tokens=1000)
    # 1000*0.003/1000 + 1000*0.015/1000 + 1e6*0.0000003/1000 + 1000*(0.003*1.25)/1000
    assert abs(usd - (0.003 + 0.015 + 0.0003 + 0.00375)) < 1e-9


def test_explicit_cache_write_rate_wins(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", lambda: {"models": {"m1": {"input": 0.003, "output": 0.015, "cache_read": 0.0, "cache_write": 0.01}}})
    assert abs(pricing.price_usd("m1", 0, 0, 0, 1000) - 0.01) < 1e-9


def test_unknown_model_is_none_never_a_default_rate(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", lambda: {"models": {}, "default": {"input": 9, "output": 9, "cache_read": 9}})
    assert pricing.price_usd("claude-unknown", 1000, 1000, 0, 0) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest -q tests/test_pricing.py` Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
"""Per-model pricing interface. Unknown models are never priced at another model's rate."""
from typing import Optional

CACHE_WRITE_INPUT_MULTIPLIER = 1.25  # used only when a model has no explicit cache_write rate


def _rates() -> dict:
    from synlynk.costs import _load_model_rates

    return _load_model_rates()


def price_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> Optional[float]:
    rate = _rates().get("models", {}).get(model)
    if not rate:
        return None
    cache_write = rate.get("cache_write", rate["input"] * CACHE_WRITE_INPUT_MULTIPLIER)
    return (
        input_tokens * rate["input"]
        + output_tokens * rate["output"]
        + cache_read_tokens * rate.get("cache_read", 0.0)
        + cache_creation_tokens * cache_write
    ) / 1000.0
```

- [ ] **Step 4: Run** `pytest -q tests/test_pricing.py` Expected: PASS.

- [ ] **Step 5: Commit** `git commit -am "feat(pricing): price_usd interface, unknown model is unpriced"` (add new files first).

---

### Task 4: Transcript fixtures and the parser (de-dup, bucketing)

**Files:**
- Create: `tests/native_capture_fixtures.py`, `synlynk/native_capture.py` (parser part)
- Test: `tests/test_native_capture_parse.py`

- [ ] **Step 1: Write the fixture builder**

```python
# tests/native_capture_fixtures.py
import json


def assistant(msg_id, model="claude-sonnet-5-5", ts="2026-11-24T10:00:00.000Z",
              i=10, o=20, cc=30, cr=40, session="s1"):
    return json.dumps({
        "type": "assistant", "timestamp": ts, "sessionId": session,
        "message": {"id": msg_id, "model": model, "usage": {
            "input_tokens": i, "output_tokens": o,
            "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr}},
    })


def pr_link(pr, session="s1", ts="2026-11-24T10:05:00.000Z"):
    return json.dumps({"type": "pr-link", "sessionId": session, "prNumber": pr,
                       "prUrl": f"https://github.com/o/r/pull/{pr}", "timestamp": ts})


def write(path, lines):
    path.write_text("\n".join(lines) + "\n")
    return path
```

- [ ] **Step 2: Write the failing parser tests**

```python
from synlynk import native_capture as nc
from tests.native_capture_fixtures import assistant, pr_link


def test_repeated_message_id_counts_once_first_seen_wins():
    data = "\n".join([assistant("m1", o=5), assistant("m1", o=5), assistant("m2", o=7)]).encode() + b"\n"
    res = nc.parse_chunk(data, known_ids=set())
    assert [r.message_id for r in res.records] == ["m1", "m2"]
    assert res.consumed == len(data)


def test_dedup_against_ids_known_from_earlier_chunks_at_any_distance():
    known = {f"x{i}" for i in range(1000)}   # session-wide, not a sliding window
    data = (assistant("x0") + "\n" + assistant("m2") + "\n").encode()
    res = nc.parse_chunk(data, known_ids=known)
    assert [r.message_id for r in res.records] == ["m2"]
    assert known == {f"x{i}" for i in range(1000)}   # parse_chunk does not mutate its input


def test_incomplete_trailing_line_is_left_unconsumed():
    complete = (assistant("m1") + "\n").encode()
    partial = b'{"type":"assistant","message":{"id":"m2"'
    res = nc.parse_chunk(complete + partial, known_ids=set())
    assert res.consumed == len(complete)
    assert len(res.records) == 1


def test_synthetic_model_and_non_assistant_skipped():
    data = (assistant("m1", model="<synthetic>") + "\n" + pr_link(5) + "\n").encode()
    res = nc.parse_chunk(data, known_ids=set())
    assert res.records == []
    assert res.pr_links == [(5, "2026-11-24T10:05:00.000Z")]


def test_format_drift_fails_loudly():
    bad = '{"type":"assistant","timestamp":"2026-11-24T10:00:00Z","message":{"id":"m1","model":"x","usage":{"tokens":5}}}\n'
    try:
        nc.parse_chunk(bad.encode(), known_ids=set())
        raised = False
    except nc.TranscriptFormatError:
        raised = True
    assert raised


def test_buckets_split_by_model_and_utc_day():
    lines = [assistant("m1", ts="2026-11-24T23:59:00.000Z"),
             assistant("m2", ts="2026-11-25T00:01:00.000Z"),
             assistant("m3", model="claude-opus-4-8", ts="2026-11-25T00:02:00.000Z")]
    res = nc.parse_chunk(("\n".join(lines) + "\n").encode(), known_ids=set())
    b = nc.bucketize(res.records)
    assert set(b) == {("claude-sonnet-5-5", "2026-11-24"), ("claude-sonnet-5-5", "2026-11-25"), ("claude-opus-4-8", "2026-11-25")}
    assert b[("claude-sonnet-5-5", "2026-11-24")].output_tokens == 20
```

- [ ] **Step 3: Run to verify failure** — `pytest -q tests/test_native_capture_parse.py` Expected: FAIL.

- [ ] **Step 4: Implement the parser**

De-duplication is session-wide: the caller passes every message id already counted for the session (`known_ids`), so a repeat is dropped at any distance, not only within a sliding window.

```python
"""Native-session transcript capture: reader, de-dup, bucketing, ledger upsert."""
import json
from dataclasses import dataclass, field


class TranscriptFormatError(Exception):
    """The transcript's usage shape no longer matches what this reader understands."""


@dataclass
class Record:
    message_id: str
    model: str
    day: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


@dataclass
class Bucket:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    messages: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    records: list
    pr_links: list
    consumed: int


_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def parse_chunk(data: bytes, known_ids: set) -> ParseResult:
    end = data.rfind(b"\n") + 1  # only complete lines
    seen = set(known_ids)       # never mutate the caller's set
    records, pr_links = [], []
    for raw in data[:end].splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue  # a corrupt line is skipped, never counted
        kind = obj.get("type")
        if kind == "pr-link" and isinstance(obj.get("prNumber"), int):
            pr_links.append((obj["prNumber"], obj.get("timestamp")))
            continue
        if kind != "assistant":
            continue
        msg = obj.get("message") or {}
        model = msg.get("model")
        if not model or model == "<synthetic>":
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict) or not all(k in usage for k in _USAGE_KEYS):
            raise TranscriptFormatError(f"usage shape changed for message {msg.get('id')!r}")
        mid = msg.get("id")
        if not mid:
            raise TranscriptFormatError("assistant record without message.id")
        if mid in seen:
            continue
        seen.add(mid)
        ts = obj.get("timestamp") or ""
        records.append(Record(mid, model, ts[:10], usage["input_tokens"], usage["output_tokens"],
                              usage["cache_creation_input_tokens"], usage["cache_read_input_tokens"]))
    return ParseResult(records, pr_links, end)


def bucketize(records) -> dict:
    out: dict = {}
    for r in records:
        b = out.setdefault((r.model, r.day), Bucket())
        b.input_tokens += r.input_tokens
        b.output_tokens += r.output_tokens
        b.cache_creation_tokens += r.cache_creation_tokens
        b.cache_read_tokens += r.cache_read_tokens
        b.messages[r.message_id] = [r.input_tokens, r.output_tokens, r.cache_read_tokens, r.cache_creation_tokens]
    return out
```

- [ ] **Step 5: Run and commit** — `pytest -q tests/test_native_capture_parse.py` Expected: PASS. `git add synlynk/native_capture.py tests && git commit -m "feat(capture): transcript parser with first-seen dedup and bucketing"`.

---

### Task 5: Ledger upsert, cursor, rescan and bounded capture

**Files:**
- Modify: `synlynk/native_capture.py`
- Test: `tests/test_native_capture_ledger.py`

Behavior (spec 4, 4.0, 8):
- **Chunked and bounded.** `capture` reads the transcript in `CHUNK_BYTES` chunks. Each chunk is parsed, applied to the ledger and the cursor advanced in ONE transaction, so progress is persisted after every chunk. When `budget_s` is given and elapsed time exceeds it with bytes still unread, `capture` returns `complete=False` and leaves the remainder to the sweep. The Stop hook passes a small budget; the sweep and CLI pass none.
- **Session-wide de-dup.** Every counted message id is kept in the bucket row's `turn_usage_json["messages"]`; `capture` loads them once per call as `known_ids`, so a repeat is dropped at any distance, immediately.
- **Offset integrity.** The cursor stores an `anchor`: sha1 of the first 4096 bytes plus the last 4096 bytes before `byte_offset`. A mismatch means the file was rewritten (same size or larger) and triggers a rescan.
- **Rescan triggers:** no cursor but existing rows; file smaller than `byte_offset`; anchor mismatch. A rescan deletes the session's `transcript_derived` rows and cursor in one transaction, then proceeds from byte 0 through the same chunk loop.
- `final=True` (SessionEnd) only marks the cursor `final=1` when the capture completed. There is no separate verification pass, because de-dup is session-wide and exact.

- [ ] **Step 1: Write the failing tests**

```python
import json
import sqlite3

import pytest

from synlynk import native_capture as nc
from synlynk.migrations.m0041_native_session_capture import MIGRATION
from tests.native_capture_fixtures import assistant, write


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE cost_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT NOT NULL,
        agent TEXT, harness TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
        total_cost_usd REAL, cost_source TEXT NOT NULL, estimate_basis TEXT, job_id TEXT, session_id TEXT,
        pr_number INTEGER, turn_usage_json TEXT, payment_mode TEXT, notes TEXT, story_id TEXT)""")
    c.execute("CREATE TABLE sessions (session_id TEXT PRIMARY KEY, title TEXT, goal_id TEXT, status TEXT, opened_at TEXT)")
    MIGRATION.up(c)
    return c


def rows(c):
    return c.execute("SELECT model, session_date, input_tokens, output_tokens, cache_read_tokens, estimate_basis, cost_source FROM cost_entries ORDER BY model, session_date").fetchall()


def cursor(c):
    return c.execute("SELECT byte_offset, final FROM native_capture_cursor WHERE session_id='s1'").fetchone()


def test_capture_writes_one_row_per_bucket(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1"), assistant("m1"), assistant("m2")])
    assert nc.capture(conn, "s1", p)["complete"] is True
    r = rows(conn)
    assert len(r) == 1
    assert r[0][2:5] == (20, 40, 80)       # in, out, cache_read for m1+m2, de-duplicated
    assert r[0][6] == "transcript_derived"


def test_unknown_model_is_unpriced_not_zero(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1", model="claude-nonexistent")])
    nc.capture(conn, "s1", p)
    cost, basis = conn.execute("SELECT total_cost_usd, estimate_basis FROM cost_entries").fetchone()
    assert cost is None and basis == "unpriced"


def test_capture_twice_is_idempotent(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1"), assistant("m2")])
    nc.capture(conn, "s1", p)
    before = rows(conn)
    nc.capture(conn, "s1", p)
    assert rows(conn) == before


def test_incremental_append_adds_only_new_usage(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1")])
    nc.capture(conn, "s1", p)
    with open(p, "a") as f:
        f.write(assistant("m1") + "\n" + assistant("m2") + "\n")
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][2:5] == (20, 40, 80)


def test_far_apart_repeat_is_dropped_immediately_on_incremental_append(conn, tmp_path):
    ids = [f"x{i}" for i in range(40)]            # far beyond any small window
    p = write(tmp_path / "s1.jsonl", [assistant(i) for i in ids])
    nc.capture(conn, "s1", p)
    with open(p, "a") as f:
        f.write(assistant("x0") + "\n")            # repeat of a message counted 40 messages ago
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][2] == 10 * 40             # no double count, no later correction needed


def test_cursor_loss_triggers_rescan_not_double_count(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1"), assistant("m2")])
    nc.capture(conn, "s1", p)
    conn.execute("DELETE FROM native_capture_cursor")
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][2:5] == (20, 40, 80)


def test_shrunk_transcript_triggers_rescan(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1"), assistant("m2"), assistant("m3")])
    nc.capture(conn, "s1", p)
    write(p, [assistant("m1")])
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][2:5] == (10, 20, 40)


def test_same_size_rewrite_triggers_rescan(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1", o=11), assistant("m2", o=22)])
    nc.capture(conn, "s1", p)
    size = p.stat().st_size
    write(p, [assistant("n1", o=33), assistant("n2", o=44)])      # same byte length, different content
    assert p.stat().st_size == size
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][3] == 33 + 44


def test_larger_rewrite_triggers_rescan(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1", o=11)])
    nc.capture(conn, "s1", p)
    write(p, [assistant("n1", o=33), assistant("n2", o=44), assistant("n3", o=55)])
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][3] == 33 + 44 + 55


def test_budget_exhausted_saves_progress_and_defers_remainder(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(nc, "CHUNK_BYTES", 2048)                   # force many chunks
    p = write(tmp_path / "s1.jsonl", [assistant(f"m{i}") for i in range(200)])
    size = p.stat().st_size
    first = nc.capture(conn, "s1", p, budget_s=0)                  # budget already spent after the first chunk
    assert first["complete"] is False
    off, final = cursor(conn)
    assert 0 < off < size and final == 0                           # progress persisted, not marked final
    partial = rows(conn)[0][2]
    assert 0 < partial < 10 * 200
    second = nc.capture(conn, "s1", p)                             # the sweep path: no budget
    assert second["complete"] is True
    assert rows(conn)[0][2] == 10 * 200                            # exact total, nothing lost or doubled
    assert cursor(conn)[0] == size


def test_final_marks_cursor_only_when_complete(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(nc, "CHUNK_BYTES", 2048)
    p = write(tmp_path / "s1.jsonl", [assistant(f"m{i}") for i in range(200)])
    nc.capture(conn, "s1", p, final=True, budget_s=0)
    assert cursor(conn)[1] == 0
    nc.capture(conn, "s1", p, final=True)
    assert cursor(conn)[1] == 1


def test_line_longer_than_a_chunk_still_makes_progress(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(nc, "CHUNK_BYTES", 256)
    big = json.loads(assistant("m1"))
    big["padding"] = "x" * 5000                                    # one line far larger than CHUNK_BYTES
    p = tmp_path / "s1.jsonl"
    p.write_text(json.dumps(big) + "\n" + assistant("m2") + "\n")
    nc.capture(conn, "s1", p)
    assert rows(conn)[0][2] == 20


def test_missing_transcript_is_explicit_error_never_a_zero_row(conn, tmp_path):
    with pytest.raises(nc.TranscriptMissingError):
        nc.capture(conn, "s1", tmp_path / "gone.jsonl")
    assert rows(conn) == []


def test_multi_day_multi_model_rows(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1", ts="2026-11-24T23:00:00Z"),
                                      assistant("m2", ts="2026-11-25T01:00:00Z"),
                                      assistant("m3", model="claude-opus-4-8", ts="2026-11-25T01:00:00Z")])
    nc.capture(conn, "s1", p)
    assert len(rows(conn)) == 3


def test_persisted_rows_and_error_log_contain_no_message_text(conn, tmp_path):
    secret = "TOP-SECRET-PROMPT-TEXT"
    line = json.loads(assistant("m1"))
    line["message"]["content"] = [{"type": "text", "text": secret}]
    p = tmp_path / "s1.jsonl"
    p.write_text(json.dumps(line) + "\n")
    nc.capture(conn, "s1", p)
    dump = json.dumps(conn.execute("SELECT * FROM cost_entries").fetchall()) + json.dumps(conn.execute("SELECT * FROM native_capture_cursor").fetchall())
    assert secret not in dump
```

- [ ] **Step 2: Run to verify failure** — `pytest -q tests/test_native_capture_ledger.py` Expected: FAIL (`nc.capture` missing).

- [ ] **Step 3: Implement**

Append to `synlynk/native_capture.py`:

```python
import hashlib
import os
import sqlite3
import time
from pathlib import Path

from synlynk import pricing

CHUNK_BYTES = 1 << 20
ANCHOR_BYTES = 4096


class TranscriptMissingError(Exception):
    """The transcript path does not exist (rotated, deleted, or never written)."""


def _session_row(conn, session_id):
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, title, status, opened_at) VALUES (?, ?, 'native', datetime('now'))",
        (session_id, "native-capture"),
    )


def _anchor(path: Path, offset: int) -> str:
    """sha1 of the first and last ANCHOR_BYTES before `offset`; detects a rewritten transcript."""
    if offset <= 0:
        return ""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(min(ANCHOR_BYTES, offset)))
        f.seek(max(0, offset - ANCHOR_BYTES))
        h.update(f.read(min(ANCHOR_BYTES, offset)))
    return h.hexdigest()


def _known_ids(conn, session_id) -> set:
    ids: set = set()
    for (blob,) in conn.execute(
        "SELECT turn_usage_json FROM cost_entries WHERE cost_source='transcript_derived' AND session_id=?",
        (session_id,),
    ):
        ids.update(json.loads(blob or "{}").get("messages", {}))
    return ids


def _row_cost(model, inp, out, cr, cc):
    cost = pricing.price_usd(model, inp, out, cr, cc)
    return cost, ("unpriced" if cost is None else "transcript_priced")


def _apply_bucket(conn, session_id, model, day, b):
    existing = conn.execute(
        "SELECT id, input_tokens, output_tokens, cache_read_tokens, turn_usage_json FROM cost_entries "
        "WHERE cost_source='transcript_derived' AND session_id=? AND model=? AND substr(session_date,1,10)=?",
        (session_id, model, day),
    ).fetchone()
    inp, out, cr, cc = b.input_tokens, b.output_tokens, b.cache_read_tokens, b.cache_creation_tokens
    msgs = dict(b.messages)
    if existing:
        _id, e_in, e_out, e_cr, e_json = existing
        prev = json.loads(e_json or "{}")
        inp += e_in or 0
        out += e_out or 0
        cr += e_cr or 0
        cc += prev.get("cache_creation_total", 0)
        msgs = {**prev.get("messages", {}), **msgs}
    cost, basis = _row_cost(model, inp, out, cr, cc)
    blob = json.dumps({"cache_creation_total": cc, "messages": msgs, "payment_mode_provisional": True})
    if existing:
        conn.execute(
            "UPDATE cost_entries SET input_tokens=?, output_tokens=?, cache_read_tokens=?, total_cost_usd=?, "
            "estimate_basis=?, turn_usage_json=? WHERE id=?",
            (inp, out, cr, cost, basis, blob, existing[0]),
        )
    else:
        conn.execute(
            "INSERT INTO cost_entries (session_date, agent, harness, model, input_tokens, output_tokens, cache_read_tokens, "
            "total_cost_usd, cost_source, estimate_basis, session_id, turn_usage_json, payment_mode) "
            "VALUES (?, 'claude', 'claude', ?, ?, ?, ?, ?, 'transcript_derived', ?, ?, ?, 'subscription')",
            (day, model, inp, out, cr, cost, basis, session_id, blob),
        )


def _log_error(msg: str) -> None:
    path = Path(os.path.expanduser("~/.synlynk/native_capture_errors.log"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(msg.replace("\n", " ")[:500] + "\n")  # ids and counts only, never message text
    except OSError:
        pass


def capture(conn, session_id: str, transcript, *, final: bool = False, budget_s=None) -> dict:
    path = Path(transcript)
    if not path.exists():
        raise TranscriptMissingError(str(path))
    started = time.monotonic()
    size = path.stat().st_size
    cur = conn.execute(
        "SELECT byte_offset, anchor FROM native_capture_cursor WHERE session_id=?", (session_id,)
    ).fetchone()
    has_rows = conn.execute(
        "SELECT 1 FROM cost_entries WHERE cost_source='transcript_derived' AND session_id=? LIMIT 1", (session_id,)
    ).fetchone()
    rescan = (cur is None and bool(has_rows)) or (
        cur is not None and (size < cur[0] or _anchor(path, cur[0]) != cur[1])
    )
    if cur is not None and not rescan and size == cur[0]:
        if final:
            with conn:
                conn.execute("UPDATE native_capture_cursor SET final=1 WHERE session_id=?", (session_id,))
        return {"records": 0, "complete": True, "rescan": False}   # nothing new: no id load, no parse
    offset = 0 if (rescan or cur is None) else cur[0]
    with conn:
        _session_row(conn, session_id)
        if rescan:
            conn.execute("DELETE FROM cost_entries WHERE cost_source='transcript_derived' AND session_id=?", (session_id,))
            conn.execute("DELETE FROM native_capture_cursor WHERE session_id=?", (session_id,))
    known = _known_ids(conn, session_id)
    total = 0
    complete = False
    while True:
        n = CHUNK_BYTES
        while True:                               # grow the read until it holds a complete line
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read(n)
            res = parse_chunk(data, known)
            if res.consumed or len(data) < n:
                break
            n *= 2
        if not data or res.consumed == 0:
            complete = True                       # EOF, or only a partial trailing line remains
            break
        buckets = bucketize(res.records)
        new_offset = offset + res.consumed
        with conn:
            for (model, day), b in buckets.items():
                _apply_bucket(conn, session_id, model, day, b)
            for pr, ts in res.pr_links:
                conn.execute(
                    "INSERT OR IGNORE INTO session_pr_links (session_id, pr_number, role, first_seen_ts, source) "
                    "VALUES (?, ?, 'implementer', ?, 'pr-link')", (session_id, pr, ts))
            conn.execute(
                "INSERT INTO native_capture_cursor (session_id, transcript_path, byte_offset, anchor, final, updated_at) "
                "VALUES (?, ?, ?, ?, 0, datetime('now')) ON CONFLICT(session_id) DO UPDATE SET "
                "transcript_path=excluded.transcript_path, byte_offset=excluded.byte_offset, "
                "anchor=excluded.anchor, updated_at=excluded.updated_at",
                (session_id, str(path), new_offset, _anchor(path, new_offset)))
        known.update(r.message_id for r in res.records)
        total += len(res.records)
        offset = new_offset
        if budget_s is not None and time.monotonic() - started > budget_s and offset < path.stat().st_size:
            break                                 # progress is saved; the sweep finishes the rest
    if complete and final:
        with conn:
            conn.execute("UPDATE native_capture_cursor SET final=1 WHERE session_id=?", (session_id,))
    return {"records": total, "complete": complete, "rescan": rescan}
```

Notes for the implementer: every chunk commits atomically with its cursor, so an interruption at any point leaves ledger and cursor consistent and a later call resumes exactly where it stopped. A rescan re-derives `session_pr_links` through the same loop (`INSERT OR IGNORE` keeps it idempotent).

- [ ] **Step 4: Run** — `pytest -q tests/test_native_capture_ledger.py` Expected: PASS. Fix any test whose expected token tuple differs only because of fixture defaults (i=10, o=20, cr=40 per message).

- [ ] **Step 5: Commit** — `git add synlynk tests && git commit -m "feat(capture): chunked, bounded, session-wide-deduped capture with rescan recovery"`.

---

### Task 6: Exclusions, reconcile, sweep

**Files:**
- Modify: `synlynk/native_capture.py`
- Test: `tests/test_native_capture_sweep.py`

Rules (spec 4.1): skip when the transcript's project directory name contains `-worktrees-job-` or `/worktrees/job-` (Claude encodes `/` as `-`), or when the `session_id` already has a ledger row with a `job_id`. Interactive sessions in `.claude/worktrees/<name>` are captured. Re-evaluated on every sweep. Reconcile flags any session with both kinds of rows.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from synlynk import native_capture as nc
from tests.native_capture_fixtures import assistant, write
from tests.test_native_capture_ledger import conn  # noqa: F401  (reuse fixture)


def test_is_dispatch_transcript_by_slug():
    assert nc.is_dispatch_slug("-Users-n-dev-synlynk-worktrees-job-4ca44bdb")
    assert nc.is_dispatch_slug("-Users-n-dev-synlynk--worktrees-job-1")
    assert not nc.is_dispatch_slug("-Users-n-dev-synlynk")
    assert not nc.is_dispatch_slug("-Users-n-dev-synlynk--claude-worktrees-feature-x")


def test_sweep_skips_dispatch_dirs_and_job_sessions(conn, tmp_path):
    base = tmp_path / "projects"
    native = base / "-Users-n-dev-synlynk"
    job = base / "-Users-n-dev-synlynk-worktrees-job-1"
    native.mkdir(parents=True); job.mkdir(parents=True)
    write(native / "s1.jsonl", [assistant("m1")])
    write(job / "s2.jsonl", [assistant("m2")])
    write(native / "s3.jsonl", [assistant("m3")])
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, session_id, job_id) VALUES ('2026-11-24','dispatch','s3','job-9')")
    summary = nc.sweep(conn, base)
    got = {r[0] for r in conn.execute("SELECT session_id FROM cost_entries WHERE cost_source='transcript_derived'")}
    assert got == {"s1"}
    assert summary["skipped_dispatch"] == 2


def test_sweep_skips_finalized_unchanged_transcripts(conn, tmp_path):
    base = tmp_path / "projects" / "-Users-n-dev-synlynk"
    base.mkdir(parents=True)
    p = write(base / "s1.jsonl", [assistant("m1")])
    nc.capture(conn, "s1", p, final=True)
    assert nc.sweep(conn, tmp_path / "projects")["captured"] == 0


def test_reconcile_flags_sessions_with_both_row_kinds(conn):
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, session_id) VALUES ('2026-11-24','transcript_derived','sX')")
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, session_id, job_id) VALUES ('2026-11-24','dispatch','sX','job-1')")
    assert nc.reconcile(conn) == ["sX"]
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: Implement**

```python
def is_dispatch_slug(slug: str) -> bool:
    # Dispatch jobs run in <repo>/worktrees/job-<id>; Claude-managed interactive worktrees are
    # <repo>/.claude/worktrees/<name> (slug contains "claude-worktrees-") and are captured.
    return "worktrees-job-" in slug and "claude-worktrees-" not in slug


def _has_job_rows(conn, session_id) -> bool:
    return bool(conn.execute("SELECT 1 FROM cost_entries WHERE session_id=? AND job_id IS NOT NULL LIMIT 1", (session_id,)).fetchone())


def sweep(conn, projects_dir=None) -> dict:
    base = Path(projects_dir or os.path.expanduser("~/.claude/projects"))
    out = {"captured": 0, "skipped_dispatch": 0, "errors": 0}
    for proj in sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []:
        dispatch_dir = is_dispatch_slug(proj.name)
        for t in sorted(proj.glob("*.jsonl")):
            sid = t.stem
            if dispatch_dir or _has_job_rows(conn, sid):
                out["skipped_dispatch"] += 1
                continue
            cur = conn.execute("SELECT byte_offset, final FROM native_capture_cursor WHERE session_id=?", (sid,)).fetchone()
            if cur and cur[1] and t.stat().st_size == cur[0]:
                continue
            try:
                capture(conn, sid, t)
                out["captured"] += 1
            except (TranscriptFormatError, TranscriptMissingError, sqlite3.Error) as exc:
                out["errors"] += 1
                _log_error(f"sweep session={sid}: {type(exc).__name__}")
    return out


def reconcile(conn) -> list:
    return [r[0] for r in conn.execute(
        "SELECT session_id FROM cost_entries WHERE session_id IS NOT NULL "
        "GROUP BY session_id HAVING SUM(cost_source='transcript_derived')>0 AND SUM(job_id IS NOT NULL)>0 ORDER BY session_id")]
```

`sweep` must call `is_dispatch_slug(proj.name)` rather than an inline check (replace the `dispatch_dir = is_dispatch_slug(proj.name)` line).

- [ ] **Step 4: Run** — `pytest -q tests/test_native_capture_sweep.py` Expected: PASS.

- [ ] **Step 5: Real-data verification before moving on (gate for backfill).** Run a read-only check over the 106 job directories:
`python3 -c "import os;from synlynk import native_capture as n;b=os.path.expanduser('~/.claude/projects');d=[x for x in os.listdir(b) if n.is_dispatch_slug(x)];print(len(d))"` Expected: 106 (or the current count). Record the number in the PR.

- [ ] **Step 6: Commit** — `git commit -m "feat(capture): dispatch exclusion, sweep and reconcile"`.

---

### Task 7: Session-to-PR links (tool-use extraction, manual link, pr check fallback)

**Files:**
- Modify: `synlynk/native_capture.py` (tool-use extraction), `synlynk/db.py` (`_implementation_identity_from_native_cost_entry`, `_review_identity_from_native_cost_entry` fallback)
- Test: `tests/test_native_capture_links.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

from synlynk import native_capture as nc
from tests.native_capture_fixtures import assistant, write
from tests.test_native_capture_ledger import conn  # noqa: F401


def _tool_use(cmd, ts="2026-11-24T10:10:00Z"):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {"id": "t" + str(abs(hash(cmd))), "model": "claude-sonnet-5-5",
        "usage": {"input_tokens": 1, "output_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        "content": [{"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}})


def test_pr_numbers_extracted_from_gh_pr_commands_without_keeping_command_text(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [_tool_use("synlynk gh --role qa -- pr review 5511 --approve"),
                                      _tool_use("gh pr merge 5512 --squash"), _tool_use("ls -la")])
    nc.capture(conn, "s1", p)
    links = {(r[0], r[1]) for r in conn.execute("SELECT pr_number, source FROM session_pr_links")}
    assert links == {(5511, "tool-use"), (5512, "tool-use")}
    assert "squash" not in json.dumps(conn.execute("SELECT * FROM session_pr_links").fetchall())


def test_review_command_links_role_reviewer(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [_tool_use("gh pr review 5511 --approve")])
    nc.capture(conn, "s1", p)
    assert conn.execute("SELECT role FROM session_pr_links WHERE pr_number=5511").fetchone()[0] == "reviewer"


def test_manual_link_is_idempotent(conn):
    nc.link_session(conn, "s1", 5420, role="implementer")
    nc.link_session(conn, "s1", 5420, role="implementer")
    assert conn.execute("SELECT COUNT(*) FROM session_pr_links").fetchone()[0] == 1


def test_linked_session_identity_lookup(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1")])
    nc.capture(conn, "s1", p)
    nc.link_session(conn, "s1", 5420, role="implementer")
    assert nc.linked_session_identity(conn, 5420, "implementer") == ("claude", "claude-sonnet-5-5")
    assert nc.linked_session_identity(conn, 9999, "implementer") is None
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: Implement**

In `parse_chunk`, for `assistant` records also scan `msg.get("content")` items of `type == "tool_use"` with `name == "Bash"`; apply this regex to `input.command` and append `(number, ts, role)`; discard the command string immediately:

```python
import re
_GH_PR_RE = re.compile(r"\bgh\b[^|;&\n]*?\bpr\s+(review|merge|create|checks|view|comment|update-branch|diff|ready)\b[^|;&\n]*?\b(\d{2,6})\b")
# role: review/merge by a reviewer session -> 'reviewer'; create -> 'implementer'
```

Add `tool_pr_links: list = field(default_factory=list)` to `ParseResult` (a defaulted field, so Task 4's constructor calls keep working); inside `capture`'s per-chunk transaction, insert each one into `session_pr_links` with `source='tool-use'` next to the existing `pr-link` inserts. Role mapping: `review` → `reviewer`, `create` → `implementer`, everything else → `implementer` only if no reviewer link exists for that session/PR, else skip. Then:

```python
def link_session(conn, session_id, pr_number, *, role="implementer", source="manual"):
    with conn:
        conn.execute("INSERT OR IGNORE INTO session_pr_links (session_id, pr_number, role, first_seen_ts, source) "
                     "VALUES (?, ?, ?, datetime('now'), ?)", (session_id, pr_number, role, source))


def linked_session_identity(conn, pr_number, role):
    row = conn.execute(
        "SELECT ce.harness, ce.model FROM session_pr_links l JOIN cost_entries_effective ce "
        "ON ce.session_id = l.session_id AND ce.cost_source='transcript_derived' "
        "WHERE l.pr_number=? AND l.role=? ORDER BY ce.output_tokens DESC LIMIT 1", (pr_number, role)).fetchone()
    return tuple(row) if row else None
```

(`linked_session_identity` reads the view, which is allowed because the raw-read guard pattern excludes `cost_entries_effective`; the module itself is also allow-listed.) In `synlynk/db.py`, extend `_implementation_identity_from_native_cost_entry` and `_review_identity_from_native_cost_entry`: when their existing query finds nothing, return `linked_session_identity(conn, pr_number, "implementer"|"reviewer")` in the same tuple shape those functions already return (read their current return type first and adapt). A missing link keeps returning the existing "no provenance" result: absence of a link means unknown, not none.

- [ ] **Step 4: Run** — `pytest -q tests/test_native_capture_links.py tests/test_native_capture_ledger.py` plus the existing `pr check` provenance tests: `pytest -q -k "provenance"`. Expected: PASS.

- [ ] **Step 5: Invariant test (no per-PR summation).** Add to the same file:

```python
def test_session_cost_is_never_multiplied_by_linked_pr_count(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1")])
    nc.capture(conn, "s1", p)
    for pr in (1, 2, 3):
        nc.link_session(conn, "s1", pr)
    total = conn.execute("SELECT SUM(output_tokens) FROM cost_entries_effective").fetchone()[0]
    assert total == 20
```

- [ ] **Step 6: Commit** — `git commit -m "feat(capture): session-to-PR links from pr-link, tool-use and manual sources"`.

---

### Task 8: CLI (`cost capture-session`, `cost link-session`)

**Files:**
- Modify: `synlynk/cli.py` (parser near line 1815, dispatch near line 3527)
- Test: `tests/test_native_capture_cli.py`

- [ ] **Step 1: Write the failing test**

Follow how existing `cost` CLI tests invoke the CLI (grep `tests/` for `["cost", "log"` and copy the invocation style, including the DB fixture). Cases: `cost capture-session --session s1 --transcript <fixture>` writes a row; running it twice leaves the same row count; `--pending` runs the sweep against a temp projects dir passed via `--projects-dir`; `cost link-session --session s1 --pr 5420 --role implementer` inserts one `manual` link; a missing transcript exits non-zero with a message containing the path and writes no row.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

Parser (inside the `cost` subparsers):

```python
cap = cost_sub.add_parser("capture-session", help="Capture a native Claude session's usage from its transcript")
cap.add_argument("--session", dest="session_id")
cap.add_argument("--transcript")
cap.add_argument("--pending", action="store_true", help="Sweep all pending native transcripts")
cap.add_argument("--projects-dir", default=None)
cap.add_argument("--final", action="store_true")
link = cost_sub.add_parser("link-session", help="Link a captured session to a PR")
link.add_argument("--session", required=True, dest="session_id")
link.add_argument("--pr", type=int, required=True)
link.add_argument("--role", choices=["implementer", "reviewer"], default="implementer")
```

Dispatch branch calls `synlynk.native_capture` through `_get_db()`. `--pending` with `--session` is an error. A `TranscriptMissingError` prints `error: transcript not found: <path>` and exits 1. When `--session` is given without `--transcript`, resolve by globbing `~/.claude/projects/*/<session>.jsonl` and fail loudly if zero or more than one match.

- [ ] **Step 4: Run** — `pytest -q tests/test_native_capture_cli.py` Expected: PASS.

- [ ] **Step 5: Update the command taxonomy.** README's `synlynk release --check-docs` fails on unlisted shipped commands, so add `cost capture-session` and `cost link-session` wherever `COMMAND_TAXONOMY` lists `cost` subcommands (grep it) and run `pytest -q -k taxonomy`.

- [ ] **Step 6: Commit** — `git commit -m "feat(cli): cost capture-session and link-session"`.

---

### Task 9: Hook dispatcher (`synlynk hook claude <event>`)

**Files:**
- Create: `synlynk/session_hooks.py`
- Modify: `synlynk/cli.py` (`hook` command)
- Test: `tests/test_session_hooks.py`

- [ ] **Step 1: Write the failing tests**

```python
import io
import json

from synlynk import session_hooks as sh
from tests.test_native_capture_ledger import conn  # noqa: F401


def test_garbage_payload_exits_zero_and_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(sh, "ERROR_LOG", tmp_path / "err.log")
    assert sh.run("claude", "Stop", io.StringIO("not json")) == 0
    assert (tmp_path / "err.log").read_text()


def test_unknown_event_is_a_noop_exit_zero():
    assert sh.run("claude", "PreCompact", io.StringIO("{}")) == 0


def test_stop_and_session_end_call_cost_handler(monkeypatch):
    calls = []
    monkeypatch.setattr(sh, "_cost_capture", lambda payload, final: calls.append((payload["session_id"], final)))
    sh.run("claude", "Stop", io.StringIO(json.dumps({"session_id": "s1", "transcript_path": "/x"})))
    sh.run("claude", "SessionEnd", io.StringIO(json.dumps({"session_id": "s1", "transcript_path": "/x"})))
    assert calls == [("s1", False), ("s1", True)]


def test_handler_exception_never_propagates(monkeypatch, tmp_path):
    monkeypatch.setattr(sh, "ERROR_LOG", tmp_path / "err.log")
    def boom(payload, final): raise RuntimeError("x")
    monkeypatch.setattr(sh, "_cost_capture", boom)
    assert sh.run("claude", "Stop", io.StringIO(json.dumps({"session_id": "s1", "transcript_path": "/x"}))) == 0


def test_hook_passes_a_time_budget_to_capture(monkeypatch):
    seen = []
    from synlynk import native_capture as nc
    monkeypatch.setattr(sh, "_get_conn", lambda: object())
    monkeypatch.setattr(nc, "capture", lambda conn, sid, path, **kw: seen.append(kw) or {"complete": True})
    sh.run("claude", "Stop", io.StringIO(json.dumps({"session_id": "s1", "transcript_path": "/x"})))
    sh.run("claude", "SessionEnd", io.StringIO(json.dumps({"session_id": "s1", "transcript_path": "/x"})))
    assert seen[0]["budget_s"] <= 0.2 and seen[0]["final"] is False
    assert seen[1]["budget_s"] <= 8 and seen[1]["final"] is True       # below the 10 s hook timeout


def test_stop_incremental_append_is_fast_on_a_realistic_large_transcript(conn, tmp_path):
    """~50 MB transcript, ~2000 assistant messages (real sessions are mostly large tool-result lines)."""
    import json as _json
    import time
    from synlynk import native_capture as nc
    from tests.native_capture_fixtures import assistant
    pad = _json.dumps({"type": "user", "message": {"content": "p" * 100_000}})
    lines = []
    for i in range(2000):
        lines.append(assistant(f"m{i}"))
        if i % 4 == 0:
            lines.append(pad)
    p = tmp_path / "s1.jsonl"
    p.write_text("\n".join(lines) + "\n")
    assert p.stat().st_size > 45_000_000
    nc.capture(conn, "s1", p)
    with open(p, "a") as fh:
        fh.write("\n".join(assistant(f"n{i}") for i in range(10)) + "\n")
    t0 = time.perf_counter()
    nc.capture(conn, "s1", p, budget_s=0.15)
    assert time.perf_counter() - t0 < 0.2


def test_first_capture_of_a_large_pending_transcript_is_bounded_and_resumable(conn, tmp_path, monkeypatch):
    from synlynk import native_capture as nc
    from tests.native_capture_fixtures import assistant, write
    monkeypatch.setattr(nc, "CHUNK_BYTES", 4096)
    p = write(tmp_path / "s1.jsonl", [assistant(f"m{i}") for i in range(500)])
    first = nc.capture(conn, "s1", p, budget_s=0)          # Stop-hook behaviour when the budget is already spent
    assert first["complete"] is False                    # remainder deferred to the sweep
    assert conn.execute("SELECT byte_offset FROM native_capture_cursor").fetchone()[0] > 0   # progress persisted

```

The `conn` fixture is imported at the top of `tests/test_session_hooks.py` with `from tests.test_native_capture_ledger import conn  # noqa: F401`, as the other native-capture test files do. The 200 ms assertion is the spec's Stop budget; if CI machines are too slow for it, keep the assertion and lower the padding, never raise the threshold. Do not mark the test `slow` unless the repo already defines that marker.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

```python
"""Session-hook dispatcher: `synlynk hook <agent> <event>` reads the hook payload on stdin."""
import json
import os
from pathlib import Path

ERROR_LOG = Path(os.path.expanduser("~/.synlynk/native_capture_errors.log"))


def _log(msg: str) -> None:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a") as f:
            f.write(msg.replace("\n", " ")[:300] + "\n")
    except OSError:
        pass


STOP_BUDGET_S = 0.15        # Stop must stay well under the 200 ms spec budget
SESSION_END_BUDGET_S = 5.0  # below the 10 s hook timeout; leftover work is finished by the sweep


def _get_conn():
    from synlynk import _get_db

    return _get_db()


def _cost_capture(payload: dict, final: bool) -> None:
    from synlynk import native_capture as nc

    nc.capture(_get_conn(), payload["session_id"], payload["transcript_path"], final=final,
               budget_s=SESSION_END_BUDGET_S if final else STOP_BUDGET_S)


_HANDLERS = {("claude", "Stop"): [("cost_capture", False)], ("claude", "SessionEnd"): [("cost_capture", True)]}


def run(agent: str, event: str, stdin) -> int:
    try:
        payload = json.load(stdin)
    except Exception as exc:  # garbage input must never fail the session
        _log(f"hook {agent}/{event}: unreadable payload ({type(exc).__name__})")
        return 0
    for name, final in _HANDLERS.get((agent, event), []):
        try:
            if name == "cost_capture":
                _cost_capture(payload, final)
        except Exception as exc:
            _log(f"hook {agent}/{event} {name}: {type(exc).__name__}")
    return 0
```

CLI: `synlynk hook claude <Stop|SessionEnd|...>` calls `session_hooks.run(agent, event, sys.stdin)` and `sys.exit(0)` unconditionally (wrap in `try/finally`). No handler stubs for other events.

- [ ] **Step 4: Run** — `pytest -q tests/test_session_hooks.py` Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(hooks): session-hook dispatcher with cost capture handler"`.

---

### Task 10: Consent-gated hook install and `doctor` checks

**Files:**
- Modify: `synlynk/session_hooks.py` (merge/remove helpers), `synlynk/doctor.py` (`_hc_native_capture`, register after `_hc_todo_drift` in the list near line 1709, `--fix` path), `synlynk/init` flow (offer only; locate via `grep -n "def init" bin/synlynk.py synlynk/*.py`)
- Test: `tests/test_session_hooks_install.py`, `tests/test_doctor_native_capture.py`

- [ ] **Step 1: Write the failing tests**

```python
from synlynk import session_hooks as sh
from tests.test_native_capture_ledger import conn  # noqa: F401

EXISTING = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "bash /h/auto-checkpoint-docs.sh"}]}],
                      "PreCompact": [{"hooks": [{"type": "command", "command": "bash /h/x.sh"}]}]}, "theme": "dark"}


def test_merge_preserves_existing_hooks_and_other_keys():
    out = sh.merge_hooks(EXISTING)
    cmds = [h["command"] for g in out["hooks"]["Stop"] for h in g["hooks"]]
    assert "bash /h/auto-checkpoint-docs.sh" in cmds
    assert any(c.startswith("synlynk hook claude Stop") for c in cmds)
    assert any(h["command"].startswith("synlynk hook claude SessionEnd") for g in out["hooks"]["SessionEnd"] for h in g["hooks"])
    assert out["theme"] == "dark" and out["hooks"]["PreCompact"] == EXISTING["hooks"]["PreCompact"]


def test_merge_is_idempotent():
    once = sh.merge_hooks(EXISTING)
    assert sh.merge_hooks(once) == once


def test_remove_deletes_only_synlynk_entries():
    assert sh.remove_hooks(sh.merge_hooks(EXISTING)) == EXISTING


def test_inputs_are_not_mutated():
    import copy
    snap = copy.deepcopy(EXISTING)
    sh.merge_hooks(EXISTING)
    assert EXISTING == snap


def test_hook_commands_have_a_timeout():
    out = sh.merge_hooks({})
    assert all(h["timeout"] <= 10 for g in out["hooks"]["Stop"] for h in g["hooks"])
```

Doctor tests: `_hc_native_capture()` returns `fail` with a fix of `synlynk doctor --fix` when settings lack the entries; `warn` when the error log is non-empty; `fail` when native transcripts exist with no ledger rows (use a temp projects dir and `monkeypatch` the base path); `ok` otherwise. A `--fix` test asserts settings.json is written only when the user confirms (reuse the existing `--fix`/`--yes` mechanism; read how another `--fix` repair asks for consent and mirror it) and that a timestamped backup `settings.json.synlynk-bak` is written first.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

```python
TAG = "synlynk hook claude "


def _entry(event: str) -> dict:
    return {"hooks": [{"type": "command", "command": f"{TAG}{event}", "timeout": 10}]}


def merge_hooks(settings: dict) -> dict:
    import copy
    out = copy.deepcopy(settings)
    hooks = out.setdefault("hooks", {})
    for event in ("Stop", "SessionEnd"):
        groups = hooks.setdefault(event, [])
        if not any(h.get("command", "").startswith(TAG) for g in groups for h in g.get("hooks", [])):
            groups.append(_entry(event))
    return out


def remove_hooks(settings: dict) -> dict:
    import copy
    out = copy.deepcopy(settings)
    for event in list(out.get("hooks", {})):
        groups = [g for g in out["hooks"][event]
                  if not any(h.get("command", "").startswith(TAG) for h in g.get("hooks", []))]
        if groups:
            out["hooks"][event] = groups
        else:
            del out["hooks"][event]
    if not out.get("hooks"):
        out.pop("hooks", None)
    return out
```

`remove_hooks` must restore EXISTING exactly in the test: since EXISTING has `Stop` and `PreCompact`, removing leaves both; confirm `SessionEnd` disappears entirely.

`_hc_native_capture` reads `~/.claude/settings.json`, the error log, and runs a read-only comparison of `~/.claude/projects` transcripts (non-dispatch) against `cost_entries` via `native_capture.reconcile`-style query; it also reports `reconcile(conn)` findings and unpriced models. `init` only prints the offer and the exact command (`synlynk doctor --fix`); it never edits settings.json.

- [ ] **Step 4: Run** — both new test files. Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(hooks): consent-gated settings merge and doctor native-capture check"`.

---

### Task 11: Backfill (`cost backfill-native`)

**Files:**
- Create: `synlynk/native_backfill.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_native_backfill.py`

Rules (spec 9): candidates are `cost_source='estimated_manual'`, `harness='claude'`, `job_id IS NULL`. Per UTC day: if a `transcript_derived` row exists for that day, candidate rows for that day get `estimate_basis='superseded_by_transcript'` (values untouched). Candidate rows on days with no transcript get `estimate_basis='unverified_estimate'`. Dry-run is the default and prints old vs new. Applying twice is a no-op. Never delete, never alter token or cost values. The model correction is carried by the transcript rows (they record the real model); the superseded manual rows keep their original model text.

- [ ] **Step 1: Write the failing tests**

```python
from synlynk import native_backfill as nb
from tests.test_native_capture_ledger import conn  # noqa: F401


def _manual(conn, day, model="claude-sonnet-4-6", pr=None):
    conn.execute("INSERT INTO cost_entries (session_date, harness, model, input_tokens, output_tokens, total_cost_usd, cost_source, pr_number) "
                 "VALUES (?, 'claude', ?, 120000, 15000, 1.0, 'estimated_manual', ?)", (day, model, pr))


def _derived(conn, day):
    conn.execute("INSERT INTO cost_entries (session_date, harness, model, input_tokens, output_tokens, cost_source, session_id) "
                 "VALUES (?, 'claude', 'claude-sonnet-5-5', 10, 20, 'transcript_derived', 's1')", (day,))


def test_dry_run_changes_nothing_and_reports(conn):
    _manual(conn, "2026-11-24"); _derived(conn, "2026-11-24")
    plan = nb.plan_backfill(conn)
    assert [p.action for p in plan] == ["supersede"]
    assert conn.execute("SELECT estimate_basis FROM cost_entries WHERE cost_source='estimated_manual'").fetchone()[0] is None


def test_apply_supersedes_matched_and_relabels_unmatched_without_touching_values(conn):
    _manual(conn, "2026-11-24"); _manual(conn, "2026-11-20"); _derived(conn, "2026-11-24")
    nb.apply_backfill(conn)
    got = dict(conn.execute("SELECT session_date, estimate_basis FROM cost_entries WHERE cost_source='estimated_manual'").fetchall())
    assert got == {"2026-11-24": "superseded_by_transcript", "2026-11-20": "unverified_estimate"}
    assert conn.execute("SELECT SUM(input_tokens), SUM(total_cost_usd) FROM cost_entries WHERE cost_source='estimated_manual'").fetchone() == (240000, 2.0)


def test_apply_twice_is_a_noop(conn):
    _manual(conn, "2026-11-24"); _derived(conn, "2026-11-24")
    nb.apply_backfill(conn)
    assert nb.plan_backfill(conn) == []


def test_superseded_rows_vanish_from_effective_view(conn):
    _manual(conn, "2026-11-24"); _derived(conn, "2026-11-24")
    nb.apply_backfill(conn)
    assert conn.execute("SELECT COUNT(*) FROM cost_entries_effective WHERE cost_source='estimated_manual'").fetchone()[0] == 0


def test_dispatch_rows_with_job_id_are_never_candidates(conn):
    conn.execute("INSERT INTO cost_entries (session_date, harness, cost_source, job_id) VALUES ('2026-11-24','claude','estimated_manual','job-1')")
    _derived(conn, "2026-11-24")
    assert nb.plan_backfill(conn) == []
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

```python
"""Backfill: replace estimated_manual native rows with transcript-derived truth (gh:#5503)."""
from dataclasses import dataclass


@dataclass
class Change:
    row_id: int
    session_date: str
    old_basis: object
    action: str   # 'supersede' | 'relabel_unverified'


def plan_backfill(conn) -> list:
    derived_days = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(session_date,1,10) FROM cost_entries WHERE cost_source='transcript_derived'")}
    out = []
    for rid, day, basis in conn.execute(
        "SELECT id, substr(session_date,1,10), estimate_basis FROM cost_entries "
        "WHERE cost_source='estimated_manual' AND harness='claude' AND job_id IS NULL "
        "AND COALESCE(estimate_basis,'') NOT IN ('superseded_by_transcript','unverified_estimate') ORDER BY id"):
        out.append(Change(rid, day, basis, "supersede" if day in derived_days else "relabel_unverified"))
    return out


def apply_backfill(conn) -> list:
    plan = plan_backfill(conn)
    with conn:
        for c in plan:
            new = "superseded_by_transcript" if c.action == "supersede" else "unverified_estimate"
            conn.execute("UPDATE cost_entries SET estimate_basis=? WHERE id=?", (new, c.row_id))
    return plan
```

CLI: `cost backfill-native [--apply]`; dry-run prints one line per change (`id date old -> new`) and the totals; `--apply` requires the effective view and guard test to exist (assert the view is present, else exit 1 with a message pointing at Task 1/2). After `--apply`, print the reminder to run `git diff --numstat origin/main` before committing any regenerated `costs.md`.

- [ ] **Step 4: Run** — `pytest -q tests/test_native_backfill.py` Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(cost): backfill-native supersedes manual estimates from transcripts"`.

---

### Task 12: Acceptance fixture and end-to-end

**Files:**
- Create: `tests/fixtures/native_capture/session_124f8b4d_usage.jsonl` (generated, counts only), `tests/test_native_capture_acceptance.py`

- [ ] **Step 1: Generate the pinned fixture (one-off, not committed code).** Write `scratch` script that reads `~/.claude/projects/-Users-nikhilsoman-dev-synlynk/124f8b4d-1358-452a-9ecc-0a154566a363.jsonl` and, for each `assistant` and `pr-link` record, emits only `type`, `timestamp`, `sessionId`, `message.id`, `message.model`, `message.usage` (and `prNumber`, `prUrl`). Drop `content` and every other field. Truncate at the record whose timestamp is the RCA measurement time recorded in `docs/rca/2026-11-23-LIVE-35-native-session-cost-capture.md` so the totals match the RCA. Commit the output file; assert in the test that no line contains the keys `content` or `text`.
- [ ] **Step 2: Write the acceptance test.**

```python
def test_pinned_fixture_reproduces_rca_totals(conn, tmp_path):
    nc.capture(conn, "124f8b4d", FIXTURE)
    out, cr = conn.execute("SELECT SUM(output_tokens), SUM(cache_read_tokens) FROM cost_entries WHERE cost_source='transcript_derived'").fetchone()
    assert (out, cr) == (243_094, 54_415_618)
```

If the totals differ, do not edit the expected numbers: the truncation point is wrong (re-derive it from the RCA table) or the parser is wrong (fix the parser).
- [ ] **Step 3: Run the whole suite** — `pytest -q` Expected: PASS.
- [ ] **Step 4: Commit** — `git commit -m "test(capture): pinned acceptance fixture reproduces RCA totals"`.

---

### Task 13: Operational rollout (no code; each step is a verification)

- [ ] **Step 1:** `synlynk cost backfill-native` (dry-run). Review the report with Nikhil. Expect the 291 `estimated_manual` rows to split into superseded and unverified.
- [ ] **Step 2:** `synlynk cost capture-session --pending` to capture existing transcripts; run `synlynk doctor` and confirm zero reconcile findings, zero unpriced models you did not expect (Sonnet 5.5 is unpriced until gh:#5501 lands: expected), and that the 106 dispatch directories were skipped.
- [ ] **Step 3:** After approval, `synlynk cost backfill-native --apply`. Then `git diff --numstat origin/main` on any regenerated `costs.md` before committing.
- [ ] **Step 4:** For the five blocked PRs, find each implementing session and run `synlynk cost link-session --session <id> --pr <N> --role implementer` for #5420, #5425, #5433, #5447, #5453 (the reviewer session likewise with `--role reviewer`), then `synlynk pr check --pr <N>` and confirm the provenance message is gone. Record the derivation in a PR comment.
- [ ] **Step 5:** `synlynk doctor --fix` (with Nikhil's consent) installs the hooks; verify by ending a throwaway session and confirming exactly one row per (session, model, day).
- [ ] **Step 6:** Comment on gh:#5457 with results and close #5498, #5499, #5503; leave #5501 open until the price table data lands; close #5450 separately.

---

## Self-Review

**Spec coverage:** section 3 architecture → Tasks 4-6, 9; section 4 flow, 4.0 recovery, 4.1 exclusions, 4.2 links → Tasks 5, 6, 7; section 5 schema, effective view and guard → Tasks 1-2; section 6 hook install → Task 10; section 7 privacy → Task 5 test, Task 7 test, Task 12 fixture check; section 8 failure behaviour → Tasks 5, 9; section 9 backfill → Task 11; section 10 scope (price interface) → Task 3; section 11 tests → distributed, acceptance in Task 12; hook latency → Task 9; payment_mode provisional → Task 5 (`payment_mode_provisional` in `turn_usage_json`; gh:#5500 reads it).

**Spec addendum needed:** `session_pr_links` gains a `role` column (implementer/reviewer) because `pr check`'s cross-harness gate needs both identities; the spec lists four columns. Record this in the PR description for the plan; no separate spec PR is required unless the reviewer asks.

**Known risks the implementer must check, not assume:** (1) the exact JSON field names `timestamp`, `message.id`, `message.usage` and `tool_use` content shape were verified on one session only; Task 4's drift test and Task 12's fixture are the safety net. (2) `cost_entries.session_id` has a foreign key to `sessions`; Task 5 inserts a `sessions` row first. (3) `SELECT *` views freeze columns (Task 1 note). (4) Tests that build bare `cost_entries` schemas will need the m0041 view (Task 2 Step 3). (5) `is_dispatch_slug` must be verified against real directory names (Task 6 Step 5).

**Type consistency:** `capture(conn, session_id, transcript, *, final=False, budget_s=None)` (returns `{records, complete, rescan}`) is the one entry point used by the CLI (Task 8), hook (Task 9), sweep (Task 6) and acceptance test (Task 12). `parse_chunk(data, known_ids)` returns `ParseResult(records, pr_links, consumed)`; Task 7 adds `tool_pr_links` without renaming existing fields.

**Dispatch routing (interim default, measured per the capability policy):** Tasks 1-2, 4-6 and 11 are data/plumbing (Codex); Tasks 8-10 are CLI/hook plumbing (Codex or Grok); Task 12 and 13 are PM-verified. Review is cross-harness+model on every PR; Claude is the author of this plan and must not review work it directs line by line without a non-author reviewer.
