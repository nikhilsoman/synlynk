import json
import os
import time

from synlynk.doctor import cleanup_selftest_workspaces
from synlynk.selftest import ScenarioContext, _workspace_dir


def test_workspace_dir_records_process_owner(monkeypatch, tmp_path):
    scratch_workspace = tmp_path / "synlynk-selftest-owned"

    def fake_mkdtemp(prefix):
        scratch_workspace.mkdir()
        return str(scratch_workspace)

    monkeypatch.setattr(
        "synlynk.selftest.tempfile.mkdtemp",
        fake_mkdtemp,
    )

    workspace = _workspace_dir(ScenarioContext(repo_path="", live=True))

    owner = json.loads((workspace / ".owner.json").read_text())
    assert owner["pid"] == os.getpid()
    assert isinstance(owner["created_at"], float)


def test_cleanup_preserves_active_process_workspace(tmp_path):
    active_dir = tmp_path / "synlynk-selftest-active"
    active_dir.mkdir()
    (active_dir / ".owner.json").write_text(
        json.dumps({"pid": os.getpid(), "created_at": 1_000_000.0})
    )

    removed = cleanup_selftest_workspaces(temp_root=str(tmp_path))

    assert removed == 0
    assert active_dir.exists()


def test_cleanup_removes_dead_process_workspace(tmp_path):
    dead_dir = tmp_path / "synlynk-selftest-dead"
    dead_dir.mkdir()
    (dead_dir / ".owner.json").write_text(
        json.dumps({"pid": 99_999_999, "created_at": time.time()})
    )

    removed = cleanup_selftest_workspaces(temp_root=str(tmp_path))

    assert removed == 1
    assert not dead_dir.exists()


def test_cleanup_preserves_fresh_workspace_without_owner(tmp_path):
    fresh_dir = tmp_path / "synlynk-selftest-fresh"
    fresh_dir.mkdir()

    removed = cleanup_selftest_workspaces(temp_root=str(tmp_path))

    assert removed == 0
    assert fresh_dir.exists()


def test_cleanup_removes_stale_workspace_without_owner(tmp_path):
    stale_dir = tmp_path / "synlynk-selftest-stale"
    stale_dir.mkdir()
    stale_mtime = time.time() - 3_601
    os.utime(stale_dir, (stale_mtime, stale_mtime))

    removed = cleanup_selftest_workspaces(temp_root=str(tmp_path))

    assert removed == 1
    assert not stale_dir.exists()


def test_cleanup_treats_nonpositive_owner_pid_as_invalid(tmp_path):
    stale_dir = tmp_path / "synlynk-selftest-invalid-owner"
    stale_dir.mkdir()
    (stale_dir / ".owner.json").write_text(
        json.dumps({"pid": 0, "created_at": time.time() - 3_601})
    )
    stale_mtime = time.time() - 3_601
    os.utime(stale_dir, (stale_mtime, stale_mtime))

    removed = cleanup_selftest_workspaces(temp_root=str(tmp_path))

    assert removed == 1
    assert not stale_dir.exists()
