import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_JOBS = [
    {
        "id": "job-aaa",
        "agent": "codex",
        "task": "feat/bs20-deep-scan",
        "cycle": "work",
        "status": "running",
        "started_at": "2026-07-03T10:00:00",
        "ended_at": None,
        "exit_code": None,
    },
    {
        "id": "job-bbb",
        "agent": "agy",
        "task": "docs/blog-post",
        "cycle": "work",
        "status": "running",
        "started_at": "2026-07-03T10:05:00",
        "ended_at": None,
        "exit_code": None,
    },
    {
        "id": "job-ccc",
        "agent": "claude",
        "task": "BS-13 brainstorm",
        "cycle": "dream",
        "status": "done",
        "started_at": "2026-07-03T08:00:00",
        "ended_at": "2026-07-03T09:30:00",
        "exit_code": 0,
    },
]


def make_snapshot(tmp_path, jobs=SAMPLE_JOBS):
    from synlynk.hud import JobSnapshot

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs))
    return JobSnapshot(str(jobs_file))


def test_active_jobs_returns_running(tmp_path):
    snap = make_snapshot(tmp_path)
    active = snap.active_jobs()
    assert len(active) == 2
    assert all(j["status"] == "running" for j in active)


def test_active_jobs_for_cycle(tmp_path):
    snap = make_snapshot(tmp_path)
    work_jobs = snap.active_jobs(cycle="work")
    assert len(work_jobs) == 2
    dream_jobs = snap.active_jobs(cycle="dream")
    assert dream_jobs == []


def test_recent_jobs(tmp_path):
    snap = make_snapshot(tmp_path)
    recent = snap.recent_jobs(n=5)
    assert len(recent) == 1
    assert recent[0]["id"] == "job-ccc"


def test_cycle_summary(tmp_path):
    snap = make_snapshot(tmp_path)
    summary = snap.cycle_summary()
    assert summary["work"]["running"] == 2
    assert summary["work"]["ready"] is False
    assert summary["dream"]["running"] == 0
    assert summary["dream"]["ready"] is True


def test_missing_jobs_file(tmp_path):
    from synlynk.hud import JobSnapshot

    snap = JobSnapshot(str(tmp_path / "nonexistent.json"))
    assert snap.active_jobs() == []
    assert snap.recent_jobs() == []


def test_elapsed_seconds(tmp_path):
    snap = make_snapshot(tmp_path)
    active = snap.active_jobs()
    assert all(isinstance(j.get("elapsed_s"), int) and j["elapsed_s"] >= 0 for j in active)
