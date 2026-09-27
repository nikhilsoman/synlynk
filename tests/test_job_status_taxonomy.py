"""Tests for Job Status Taxonomy and Invariant 1 Status Constants."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_job_status_constants_exist_and_distinct():
    import synlynk.jobs as jobs_mod

    # Mandatory Invariant 1 constants
    assert hasattr(jobs_mod, "STATUS_COMPLETED_WITHOUT_CHANGES")
    assert jobs_mod.STATUS_COMPLETED_WITHOUT_CHANGES == "completed_without_changes"

    assert hasattr(jobs_mod, "STATUS_FAILED_NOOP_DENIED")
    assert jobs_mod.STATUS_FAILED_NOOP_DENIED == "failed_noop_denied"

    assert hasattr(jobs_mod, "STATUS_FAILED_VERIFICATION")
    assert jobs_mod.STATUS_FAILED_VERIFICATION == "failed_verification"

    # Core status constants
    assert hasattr(jobs_mod, "STATUS_COMPLETED")
    assert jobs_mod.STATUS_COMPLETED == "completed"

    assert hasattr(jobs_mod, "STATUS_FAILED")
    assert jobs_mod.STATUS_FAILED == "failed"

    assert hasattr(jobs_mod, "STATUS_RUNNING")
    assert jobs_mod.STATUS_RUNNING == "running"


def test_job_status_collections_and_membership():
    import synlynk.jobs as jobs_mod

    assert hasattr(jobs_mod, "ALL_JOB_STATUSES")
    assert isinstance(jobs_mod.ALL_JOB_STATUSES, (set, frozenset, tuple, list))

    all_statuses = set(jobs_mod.ALL_JOB_STATUSES)
    assert jobs_mod.STATUS_COMPLETED_WITHOUT_CHANGES in all_statuses
    assert jobs_mod.STATUS_FAILED_NOOP_DENIED in all_statuses
    assert jobs_mod.STATUS_FAILED_VERIFICATION in all_statuses
    assert jobs_mod.STATUS_COMPLETED in all_statuses
    assert jobs_mod.STATUS_FAILED in all_statuses
    assert jobs_mod.STATUS_RUNNING in all_statuses


def test_job_status_classification_helpers():
    import synlynk.jobs as jobs_mod

    # Success predicate: only true success (completed) is considered successful
    assert jobs_mod.is_successful_status("completed") is True
    assert jobs_mod.is_successful_status("completed_without_changes") is False
    assert jobs_mod.is_successful_status("failed_noop_denied") is False
    assert jobs_mod.is_successful_status("failed_verification") is False
    assert jobs_mod.is_successful_status("failed") is False
    assert jobs_mod.is_successful_status("running") is False

    # Terminal predicate: running is not terminal, completed / failed / noops are terminal
    assert jobs_mod.is_terminal_status("completed") is True
    assert jobs_mod.is_terminal_status("completed_without_changes") is True
    assert jobs_mod.is_terminal_status("failed_noop_denied") is True
    assert jobs_mod.is_terminal_status("failed_verification") is True
    assert jobs_mod.is_terminal_status("failed") is True
    assert jobs_mod.is_terminal_status("running") is False
    assert jobs_mod.is_terminal_status("queued") is False

    # Noop predicate
    assert jobs_mod.is_noop_status("completed_without_changes") is True
    assert jobs_mod.is_noop_status("failed_noop_denied") is True
    assert jobs_mod.is_noop_status("completed") is False
    assert jobs_mod.is_noop_status("failed") is False
