from synlynk.story_summary import derive_story_summary


def test_short_title_is_kept():
    assert derive_story_summary("fix: pr check exits when no PR exists") == (
        "fix: pr check exits when no PR exists"
    )


def test_task_prompt_becomes_a_task_name():
    title = (
        "Implement Task 8 of docs/superpowers/plans/2026-07-22-rollback-mechanism.md: "
        "add `--dry-run` to `synlynk init`"
    )
    assert derive_story_summary(title) == "Task 8: rollback mechanism"


def test_example_and_calibration_prompts_are_named():
    assert derive_story_summary(
        "Write a minimal example demonstrating Testing for a small Python function."
    ) == "Example: Testing"
    assert derive_story_summary(
        "Review this Requirements Definition and Management calibration task output"
    ).startswith("Review calibration: Requirements")


def test_emdash_title_keeps_the_name_before_the_dash():
    assert derive_story_summary(
        "BS-8: synlynk story split — observatory-driven auto-decomposition for context-window-crossing stories"
    ) == "BS-8: synlynk story split"


def test_long_prompt_stops_on_a_word():
    summary = derive_story_summary("Fix the " + "registry " * 40)
    assert not summary.endswith(" ")
    assert "registry" in summary
    assert len(summary) <= 80


def test_empty_title():
    assert derive_story_summary("") == "Untitled story"
    assert derive_story_summary("\n\n") == "Untitled story"
