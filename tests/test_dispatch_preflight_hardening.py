import concurrent.futures
import os
import pytest

from synlynk.session import (
    _add_active_claim,
    _remove_active_claim,
    _read_active_claim_leases,
)
from synlynk.dispatch import _infer_task_type, _task_requires_gh_write


def test_concurrent_active_claim_operations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)

    def worker(idx):
        story = f"story-{idx}"
        lease = f"lease-{idx}"
        _add_active_claim(story, lease)
        leases = _read_active_claim_leases()
        assert story in leases
        if idx % 2 == 0:
            _remove_active_claim(story)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(20)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    remaining = _read_active_claim_leases()
    # All odd stories should remain, evens should be removed
    for i in range(20):
        story = f"story-{i}"
        if i % 2 == 1:
            assert story in remaining
        else:
            assert story not in remaining


def test_task_type_governs_gh_write_inference():
    # If explicit task_type is calibration or eval, gh_write should be False
    assert _task_requires_gh_write("create pr for feature", task_type="calibration") is False
    assert _task_requires_gh_write("create pr for feature", task_type="review") is False


def test_worktree_preflight_stale_cleanup(tmp_path, monkeypatch):
    from synlynk.dispatch import _cleanup_stale_worktree_preflight

    fake_worktree = tmp_path / "worktrees" / "stale-job"
    fake_worktree.mkdir(parents=True)
    (fake_worktree / "leftover.txt").write_text("stranded")

    _cleanup_stale_worktree_preflight(str(fake_worktree))
    assert not fake_worktree.exists()
