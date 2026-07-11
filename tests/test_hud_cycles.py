import json

from synlynk.hud import CYCLES, CYCLE_COLOURS, JobSnapshot


def test_cycles_is_governs_seven_stages():
    assert CYCLES == ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]


def test_cycle_colours_covers_every_cycle():
    assert set(CYCLE_COLOURS.keys()) == set(CYCLES)


def test_cycle_summary_defaults_unset_job_to_execute(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([{"status": "running", "agent": "codex", "task": "t"}]))
    summary = JobSnapshot(str(jobs_file)).cycle_summary()
    assert summary["execute"]["running"] == 1
