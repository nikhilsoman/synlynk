import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cmd_logs_redacts_active_token_values(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    logs_dir = tmp_path / ".synlynk" / "logs"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "job-test.log"
    log_file.write_text("normal output line\nGH_TOKEN=ghs_supersecrettoken123 leaked by accident\nmore output\n")

    import synlynk as sl
    from synlynk import github_app_auth as gh_auth

    gh_auth._persist_token_for_redaction("dev", "ghs_supersecrettoken123", 9999999999)

    monkeypatch.setattr(sl, "_load_jobs", lambda: [
        {"id": "job-test", "agent": "codex", "log_file": str(log_file)}
    ])

    sl.cmd_logs("job-test", tail=50)
    out = capsys.readouterr().out
    assert "ghs_supersecrettoken123" not in out
    assert "***REDACTED***" in out
    assert "normal output line" in out  # non-secret lines still display normally
