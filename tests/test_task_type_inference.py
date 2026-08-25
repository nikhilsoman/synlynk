import pytest


@pytest.mark.parametrize(
    "task",
    [
        "Review and post a GitHub PR review for PR #1164 in nikhilsoman/synlynk",
        "Post a GitHub PR review for PR #1164",
        "Please do a code review of PR #42 and leave comments",
    ],
)
def test_infer_task_type_review(task):
    from synlynk.dispatch import _infer_task_type

    assert _infer_task_type(task) == "review"


@pytest.mark.parametrize(
    "task",
    [
        "Fix the login bug in auth.py",
        "Close issue #99 as duplicate",
        "",
        None,
    ],
)
def test_infer_task_type_does_not_guess(task):
    from synlynk.dispatch import _infer_task_type

    assert _infer_task_type(task) is None
