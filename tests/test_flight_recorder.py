import json

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
