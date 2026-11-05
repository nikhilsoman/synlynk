import pytest

import synlynk
from synlynk.db import cmd_pr_check


def _unavailable():
    raise RuntimeError(
        "canonical state DB unavailable or unusable at /host/state.db: "
        "[Errno 1] Operation not permitted; refusing to select a "
        "non-canonical fallback."
    )


def _patch_github(monkeypatch, verdict):
    monkeypatch.setattr(synlynk, "_get_db", _unavailable)
    monkeypatch.setattr("synlynk.db._is_github_remote", lambda: True)
    monkeypatch.setattr("synlynk.db._current_pr_number", lambda pr_number=None: pr_number or 2570)
    monkeypatch.setattr("synlynk.db.detect_remote_owner_repo", lambda: ("nikhilsoman", "synlynk"))
    monkeypatch.setattr(
        "synlynk.db.qa_gate_verdict",
        lambda owner, repo, **kwargs: {"verdict": verdict, "reason": f"gate {verdict}"},
    )


def test_pr_check_degraded_passes_when_the_qa_gate_is_green(monkeypatch, capsys):
    """gh:#2573 — an unreachable canonical ledger does not block a green CI gate."""
    _patch_github(monkeypatch, "green")

    cmd_pr_check(pr_number=2570)

    output = capsys.readouterr().out
    assert "PR CHECK DEGRADED" in output
    assert "No fallback ledger was opened" in output
    assert "qa gate green" in output
    assert "Ledger gates skipped" in output


def test_pr_check_degraded_blocks_when_the_qa_gate_is_red(monkeypatch, capsys):
    _patch_github(monkeypatch, "red")

    with pytest.raises(SystemExit) as raised:
        cmd_pr_check(pr_number=2570)

    assert raised.value.code == 1
    output = capsys.readouterr().out
    assert "qa gate is red" in output
    assert "PR CHECK DEGRADED" in output


def test_pr_check_degraded_blocks_without_a_pull_request(monkeypatch, capsys):
    _patch_github(monkeypatch, "green")
    monkeypatch.setattr("synlynk.db._current_pr_number", lambda pr_number=None: None)

    with pytest.raises(SystemExit) as raised:
        cmd_pr_check()

    assert raised.value.code == 1
    assert "no PR number" in capsys.readouterr().out


def test_pr_check_does_not_degrade_on_an_unrelated_runtime_error(monkeypatch):
    def boom():
        raise RuntimeError("schema migration failed")

    monkeypatch.setattr(synlynk, "_get_db", boom)

    with pytest.raises(RuntimeError, match="schema migration failed"):
        cmd_pr_check(pr_number=2570)
