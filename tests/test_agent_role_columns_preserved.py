def test_daemon_jobs_agent_id_column_unchanged():
    """Guards against #786 Plan A renaming the genuine Agent-role identifier."""
    import subprocess

    result = subprocess.run(
        ["grep", "-n", "agent_id", "synlynk/db.py", "synlynk/cli.py", "synlynk/dispatch.py"],
        capture_output=True,
        text=True,
    )
    assert "agent_id" in result.stdout


def test_stories_role_column_unchanged():
    import subprocess

    result = subprocess.run(
        ["grep", "-n", "stories.role\\|role TEXT", "synlynk/db.py"],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() != ""
