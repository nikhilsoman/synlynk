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


def test_session_cost_is_never_multiplied_by_linked_pr_count(conn, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1")])
    nc.capture(conn, "s1", p)
    for pr in (1, 2, 3):
        nc.link_session(conn, "s1", pr)
    total = conn.execute("SELECT SUM(output_tokens) FROM cost_entries_effective").fetchone()[0]
    assert total == 20
