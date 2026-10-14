from pathlib import Path

import synlynk.cli as cli


def test_fleet_list_uses_real_cli_entry_point(capsys):
    cli.main(["fleet", "list"])

    output = capsys.readouterr().out
    assert "saas_web" in output
    assert "fintech" in output


def test_fleet_apply_dry_run_prints_roles_without_writing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    cli.main(["fleet", "apply", "saas_web", "--dry-run"])

    output = capsys.readouterr().out
    assert "Fleet template: saas_web" in output
    assert "pm" in output
    assert "claude" in output
    assert not (Path(".synlynk") / "config.json").exists()
