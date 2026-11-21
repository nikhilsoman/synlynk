import json
import io

import pytest

from synlynk import flight_recorder as fr


def test_no_synlynk_dir_created_in_uninitialized_dir(tmp_path):
    fr.record(
        tmp_path,
        command="init",
        flags=["--force"],
        exit_code=1,
        duration=0.1,
        error="x",
    )

    assert not (tmp_path / ".synlynk").exists()


def test_caps_at_50_records(tmp_path):
    (tmp_path / ".synlynk").mkdir()

    for _ in range(60):
        fr.record(tmp_path, "c", [], 0, 0.0, "")

    lines = (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()
    assert len(lines) == 50


def test_error_line_is_redacted_at_write_time(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    secret = "ghp_" + "a" * 36

    fr.record(tmp_path, "c", [], 1, 0.0, f"boom {secret}\nignored")

    rec = json.loads(
        (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1]
    )
    assert secret not in rec["error"]
    assert rec["error"] == "boom [REDACTED]"
    assert rec["failed"] is True


def test_secret_scanner_replaces_entire_error_line(tmp_path):
    (tmp_path / ".synlynk").mkdir()

    fr.record(tmp_path, "c", [], 1, 0.0, "password=hunter2hunter2")

    rec = json.loads(
        (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1]
    )
    assert rec["error"] == "[redacted]"


def test_only_flag_names_are_stored(tmp_path):
    (tmp_path / ".synlynk").mkdir()

    fr.record(
        tmp_path,
        "dispatch",
        ["--task", "private task text", "--model=gpt-secret", "positional"],
        0,
        0.0,
        "",
    )

    rec = json.loads(
        (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1]
    )
    assert rec["flags"] == ["--task", "--model"]


def test_write_failure_never_raises(tmp_path, monkeypatch):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(
        fr,
        "_append",
        lambda *args: (_ for _ in ()).throw(OSError("disk")),
    )

    fr.record(tmp_path, "c", [], 0, 0.0, "")


def test_off_switch_and_clear(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text('{"flight_recorder": false}')

    fr.record(tmp_path, "c", [], 0, 0.0, "")
    assert not (synlynk_dir / "flight.jsonl").exists()

    (synlynk_dir / "config.json").write_text("{}")
    fr.record(tmp_path, "c", [], 0, 0.0, "")
    fr.clear(tmp_path)
    assert not (synlynk_dir / "flight.jsonl").exists()


def test_cli_failure_records_and_prints_footer(tmp_path, monkeypatch, capsys):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    import synlynk.cli as cli

    monkeypatch.setattr(cli, "_dispatch_command", lambda args: 1)

    rc = cli.run_with_recorder(["doctor"])

    assert rc == 1
    assert "synlynk report --last" in capsys.readouterr().err
    record = json.loads(
        (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1]
    )
    assert record["command"] == "doctor"
    assert record["exit_code"] == 1


def test_cli_system_exit_is_recorded_and_reraised(tmp_path, monkeypatch):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    import synlynk.cli as cli

    def fail(_args):
        print("specific failure", file=cli.sys.stderr)
        raise SystemExit(7)

    monkeypatch.setattr(cli, "_dispatch_command", fail)

    with pytest.raises(SystemExit) as raised:
        cli.run_with_recorder(["doctor"])

    assert raised.value.code == 7
    record = json.loads(
        (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1]
    )
    assert record["exit_code"] == 7
    assert record["error"] == "specific failure"


def test_cli_stderr_wrapper_preserves_target_stream_capabilities(monkeypatch):
    import synlynk.cli as cli

    class Target:
        encoding = "utf-8"
        errors = "surrogateescape"
        buffer = io.BytesIO()

        def write(self, text):
            return len(text)

        def flush(self):
            pass

        def isatty(self):
            return True

        def fileno(self):
            return 42

        def writable(self):
            return True

    target = Target()
    monkeypatch.setattr(cli.sys, "stderr", target)
    observed = {}

    def inspect_stderr(_args):
        observed["isatty"] = cli.sys.stderr.isatty()
        observed["fileno"] = cli.sys.stderr.fileno()
        observed["encoding"] = cli.sys.stderr.encoding
        observed["errors"] = cli.sys.stderr.errors
        observed["writable"] = cli.sys.stderr.writable()
        observed["buffer"] = cli.sys.stderr.buffer
        return 0

    monkeypatch.setattr(cli, "_dispatch_command", inspect_stderr)

    assert cli.run_with_recorder(["doctor"]) == 0
    assert observed == {
        "isatty": True,
        "fileno": 42,
        "encoding": "utf-8",
        "errors": "surrogateescape",
        "writable": True,
        "buffer": target.buffer,
    }


def test_stderr_tee_retains_only_bounded_first_nonempty_line():
    import synlynk.cli as cli

    class Target:
        written = 0

        def write(self, text):
            self.written += len(text)
            return len(text)

        def flush(self):
            pass

    target = Target()
    tee = cli._StderrTee(target)
    tee.write("\nfirst failure\n")
    tee.write("x" * (1024 * 1024))

    assert tee.first_line == "first failure"
    assert len(tee.first_line) <= 2048
    assert target.written == len("\nfirst failure\n") + 1024 * 1024


def test_cli_records_first_stderr_line_from_bounded_capture(tmp_path, monkeypatch):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    import synlynk.cli as cli

    def fail(_args):
        print("first failure", file=cli.sys.stderr)
        print("later detail", file=cli.sys.stderr)
        return 1

    monkeypatch.setattr(cli, "_dispatch_command", fail)

    assert cli.run_with_recorder(["doctor"]) == 1
    record = json.loads(
        (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1]
    )
    assert record["error"] == "first failure"


def test_report_command_is_not_recorded_or_given_footer(tmp_path, monkeypatch, capsys):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    import synlynk.cli as cli

    monkeypatch.setattr(cli, "_dispatch_command", lambda args: 1)

    assert cli.run_with_recorder(["report", "--last"]) == 1
    assert not (tmp_path / ".synlynk" / "flight.jsonl").exists()
    assert "synlynk report --last" not in capsys.readouterr().err
