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
