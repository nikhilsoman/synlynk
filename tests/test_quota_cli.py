"""Integration tests for synlynk quota CLI commands (MC-5)."""

import json
import pytest
from synlynk.cli import build_parser, main


def test_quota_advisory_cli(capsys):
    parser = build_parser()
    args = parser.parse_args(["quota", "advisory"])
    assert args.command == "quota"
    assert args.quota_action == "advisory"


def test_quota_advisory_cli_json(capsys):
    parser = build_parser()
    args = parser.parse_args(["quota", "advisory", "--json"])
    assert args.json_output is True


def test_quota_calibrate_cli_parsing():
    parser = build_parser()
    args = parser.parse_args([
        "quota", "calibrate",
        "--harness", "claude",
        "--window", "5h",
        "--p1", "10.0",
        "--p2", "30.0",
        "--tokens", "40000",
        "--track", "default",
    ])
    assert args.command == "quota"
    assert args.quota_action == "calibrate"
    assert args.harness == "claude"
    assert args.p1 == 10.0
    assert args.p2 == 30.0
    assert args.tokens == 40000


def test_quota_calibrate_execution(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"schema_version": 1}))

    # Run quota calibrate command
    try:
        main([
            "quota", "calibrate",
            "--harness", "codex",
            "--window", "5h",
            "--p1", "15.0",
            "--p2", "35.0",
            "--tokens", "50000",
            "--json",
        ])
    except SystemExit as e:
        assert e.code in (0, None)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["valid"] is True
    assert data["calculated_ceiling"] == 250000


def test_quota_advisory_execution(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"schema_version": 1}))

    try:
        main(["quota", "advisory"])
    except SystemExit as e:
        assert e.code in (0, None)
    out = capsys.readouterr().out
    assert "SYNLYNK FLEET UTILIZATION ADVISORY" in out
    for line in out.splitlines():
        assert len(line) <= 56
