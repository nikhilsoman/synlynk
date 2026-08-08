from synlynk.fencing import (
    FenceData,
    NudgeData,
    is_fenced_command,
    render_nudge_fence,
    render_task_fence,
)


def test_render_nudge_fence_includes_message_and_id():
    data = NudgeData(
        nudge_id="goal-closed-goal-90e73dfd",
        title="Goal closed",
        message="All stories linked to goal-90e73dfd are done - ",
        follow_up="synlynk goal status",
    )
    output = render_nudge_fence(data)
    assert "Goal closed" in output
    assert "All stories linked to goal-90e73dfd are done - " in output
    assert "synlynk goal status" in output


def test_render_nudge_fence_has_bordered_box_shape():
    data = NudgeData(nudge_id="x", title="T", message="M")
    output = render_nudge_fence(data)
    lines = output.rstrip("\n").split("\n")
    assert lines[0].startswith("--")
    assert lines[-1] == "-" * 36


def test_render_task_fence_estimate():
    data = FenceData(
        command="dispatch",
        kind="estimate",
        in_tokens=28000,
        out_tokens=4000,
        cost_usd=0.42,
        basis="prompt_estimate",
    )
    out = render_task_fence(data)
    assert "-- dispatch estimate " in out
    assert "~$0.42" in out
    assert "28,000 in / 4,000 out" in out
    assert "prompt_estimate" in out
    assert "tip:" not in out


def test_render_task_fence_actual_with_hints():
    data = FenceData(
        command="jobs",
        kind="actual",
        in_tokens=3916492,
        out_tokens=33996,
        cost_usd=12.26,
        basis="structured_output",
        hints=["Run `synlynk watch` for a live overview"],
        label="job-d63c4cf4",
    )
    out = render_task_fence(data)
    assert "-- job-d63c4cf4 complete " in out
    assert "$12.26" in out
    assert "~$" not in out
    assert "3,916,492 in / 33,996 out" in out
    assert "tip:    Run `synlynk watch` for a live overview" in out


def test_render_task_fence_no_label_defaults_to_command():
    data = FenceData(
        command="exec",
        kind="actual",
        in_tokens=100,
        out_tokens=50,
        cost_usd=0.01,
        basis="regex_pair",
    )
    out = render_task_fence(data)
    assert "-- exec complete " in out


def test_is_fenced_command_allowlisted():
    config = {"fenced_commands": ["dispatch", "jobs"]}
    assert is_fenced_command("dispatch", config) is True
    assert is_fenced_command("release", config) is False


def test_is_fenced_command_missing_key_defaults_empty():
    assert is_fenced_command("dispatch", {}) is False
