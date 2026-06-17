import os
import json
import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a per-test temp file so tests never share state.db."""
    import synlynk
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "state.db"))


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Creates a minimal synlynk project structure and chdirs into it."""
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "devlogs").mkdir()
    (tmp_path / ".synlynk").mkdir()

    (tmp_path / "project-docs" / "todo.md").write_text(
        "# Project Todo List\n## Active Tasks\n"
        "- [ ] Task one <!-- id: 1 -->\n"
        "- [ ] Task two <!-- id: 2 -->\n"
    )
    (tmp_path / "project-docs" / "memory.md").write_text("# synlynk Memory\n\n## Decisions\n- Decision A\n")
    (tmp_path / "project-docs" / "roadmap.md").write_text(
        "# synlynk Roadmap\n\n"
        "| Priority | Feature | Description | Status | Target Release | Owner |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| P0 | Feature A | Desc A | In Progress | v1.2.1 | [Unassigned] |\n"
        "| P1 | Feature B | Desc B | Planned | v1.3.0 | [Unassigned] |\n"
    )
    (tmp_path / "project-docs" / "costs.md").write_text(
        "# Project Costs Tracking\n"
        "## Session Summary\n"
        "| Date | User | Requests | Tokens (In/Out) | Estimated Cost (USD) | Summary |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| 2026-05-17 10:00 | nikhilsoman | 1 | 1000/500 | $0.50 | session 1 |\n"
        "| 2026-05-17 11:00 | nikhilsoman | 1 | 800/400 | $0.74 | session 2 |\n"
    )
    config = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "watch_interval_seconds": 30,
        "org": None, "team": None, "sync_endpoint": None,
        "exec_timeout_minutes": 30
    }
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))
    (tmp_path / "project-docs" / ".synlynk_config.json").write_text(
        json.dumps({"mode": "single", "version": "1.1.0"})
    )

    monkeypatch.chdir(tmp_path)
    return tmp_path
