from pathlib import Path
from synlynk import native_capture as nc
from tests.test_native_capture_ledger import conn  # noqa: F401

FIXTURE = Path(__file__).parent / "fixtures" / "native_capture" / "session_124f8b4d_usage.jsonl"


def test_pinned_fixture_contains_no_content_or_text():
    content = FIXTURE.read_text()
    for line in content.splitlines():
        assert '"content"' not in line
        assert '"text"' not in line


def test_pinned_fixture_reproduces_rca_totals(conn, tmp_path):
    res = nc.capture(conn, "124f8b4d", FIXTURE)
    assert res["complete"] is True
    out, cr = conn.execute("SELECT SUM(output_tokens), SUM(cache_read_tokens) FROM cost_entries WHERE cost_source='transcript_derived'").fetchone()
    assert (out, cr) == (243_094, 54_415_618)
