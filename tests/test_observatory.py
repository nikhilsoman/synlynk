import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_build_snapshot_returns_empty_on_missing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.observatory import build_job_observatory_snapshot

    snapshot = build_job_observatory_snapshot()
    assert snapshot["jobs"] == []
    assert snapshot["repos"] == []
    assert snapshot["stages"] == {}
    assert snapshot["rollups"]["total_cost"] == 0.0
    assert snapshot["rollups"]["active_count"] == 0


def test_build_snapshot_active_jobs_included(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jobs_file = tmp_path / ".synlynk" / "jobs.json"
    _write_json(
        jobs_file,
        [
            {
                "id": "job-active-1",
                "repo": "nikhilsoman/synlynk",
                "agent": "codex",
                "originating_agent": "claude",
                "status": "running",
                "started_at": "2026-07-05T09:00:00",
                "log_file": ".synlynk/logs/job-active-1.log",
                "context_file": ".synlynk/contexts/job-active-1.md",
            }
        ],
    )

    from synlynk.observatory import build_job_observatory_snapshot

    snapshot = build_job_observatory_snapshot()
    assert len(snapshot["jobs"]) == 1
    job = snapshot["jobs"][0]
    assert job["id"] == "job-active-1"
    assert job["repo"] == "nikhilsoman/synlynk"
    assert job["stage"] == "running"
    assert job["originating_agent"] == "claude"


def test_build_snapshot_rollups_sum_cost(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / ".synlynk" / "jobs.json",
        [
            {
                "id": "job-cost-1",
                "repo": "nikhilsoman/synlynk",
                "agent": "codex",
                "status": "running",
                "started_at": "2026-07-05T09:00:00",
            },
            {
                "id": "job-cost-2",
                "repo": "nikhilsoman/synlynk",
                "agent": "agy",
                "status": "done",
                "started_at": "2026-07-05T08:30:00",
            },
        ],
    )
    _write_json(
        tmp_path / ".synlynk" / "telemetry.json",
        [
            {"job_id": "job-cost-1", "cost_usd": 1.25, "input_tokens": 1000, "output_tokens": 250, "requests": 4},
            {"job_id": "job-cost-2", "cost_usd": 0.75, "input_tokens": 500, "output_tokens": 100, "requests": 2},
        ],
    )

    from synlynk.observatory import build_job_observatory_snapshot

    snapshot = build_job_observatory_snapshot()
    assert snapshot["rollups"]["total_cost"] == 2.0
    assert snapshot["rollups"]["total_requests"] == 6
    assert snapshot["rollups"]["total_tokens"] == 1850


def test_render_observatory_panel_no_crash(tmp_path):
    from synlynk.hud import FrameBuffer, render_observatory_panel

    buf = FrameBuffer(rows=12, cols=120)
    render_observatory_panel(buf, [], {"total_cost": 0.0, "active_count": 0, "total_requests": 0, "total_tokens": 0}, cols=120)
    output = buf.flush()
    assert "OBSERVATORY" in output
    assert "no live jobs" in output.lower()


def test_render_observatory_panel_shows_job_id(tmp_path):
    from synlynk.hud import FrameBuffer, render_observatory_panel

    buf = FrameBuffer(rows=12, cols=120)
    jobs = [
        {
            "id": "job1234",
            "repo": "nikhilsoman/synlynk",
            "agent": "codex",
            "stage": "running",
            "status": "running",
            "runtime_seconds": 65,
            "cost_usd": 1.23,
            "input_tokens": 100,
            "output_tokens": 20,
        }
    ]
    render_observatory_panel(buf, jobs, {"total_cost": 1.23, "active_count": 1, "total_requests": 1, "total_tokens": 120}, cols=120)
    output = buf.flush()
    assert "job1234" in output
