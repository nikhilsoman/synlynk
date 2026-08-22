from unittest.mock import patch, MagicMock
import json


def test_cmd_pr_check_merges_docs_only_pr_when_mode_is_merge_restricted_classes(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "merge-restricted-classes"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=501), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "green", "reason": "CI green, no unresolved sentinel alert"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md"]), \
         patch("subprocess.run") as mock_run, \
         patch("synlynk.db._detect_hand_edit", None), \
         patch("synlynk.db.cmd_audit_docs", return_value=[]):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cmd_pr_check()

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert len(merge_calls) == 1
    assert merge_calls[0].args[0] == ["gh", "pr", "merge", "501", "--squash"]


def test_cmd_pr_check_does_not_merge_when_mode_is_block_only(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "block-only"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=502), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "green", "reason": "ok"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md"]), \
         patch("subprocess.run") as mock_run, \
         patch("synlynk.db._detect_hand_edit", None), \
         patch("synlynk.db.cmd_audit_docs", return_value=[]):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cmd_pr_check()

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert merge_calls == []


def test_cmd_pr_check_does_not_merge_non_docs_only_pr_in_merge_restricted_mode(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "merge-restricted-classes"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=503), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "green", "reason": "ok"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md", "synlynk/db.py"]), \
         patch("subprocess.run") as mock_run, \
         patch("synlynk.db._detect_hand_edit", None), \
         patch("synlynk.db.cmd_audit_docs", return_value=[]):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cmd_pr_check()

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert merge_calls == []


def test_cmd_pr_check_does_not_merge_when_gate_is_red(project_dir, tmp_path, monkeypatch):
    from synlynk.db import cmd_pr_check

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"qa_gate_mode": "merge-restricted-classes"}))

    with patch("synlynk.db._is_github_remote", return_value=True), \
         patch("synlynk.db._current_pr_number", return_value=504), \
         patch("synlynk.db._extract_pr_review_cycles", return_value=0), \
         patch("synlynk.db._apply_review_cycle_multiplier"), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value={"verdict": "red", "reason": "CI matrix is red"}), \
         patch("synlynk.db._gh_pr_changed_files", return_value=["docs/blog/01-post.md"]), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        try:
            cmd_pr_check()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1

    merge_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["gh", "pr"] and "merge" in c.args[0]]
    assert merge_calls == []
