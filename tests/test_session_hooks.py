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
