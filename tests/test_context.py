import os
import sqlite3

from synlynk import agent_store
from synlynk.context import generate_context


def _valid_charter(role, marker):
    return (
        "---\n"
        "schema_version: 1\n"
        f"role: {role}\n"
        f'description: "{marker}"\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        f"{marker}\n\n"
        "## Authority & Escalation\n\nEscalates per policy.\n\n"
        "## Workflow Ownership\n\nOwns this test.\n"
    )


def _register_pm(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda path: path.replace("~", str(fake_home)))
    agent_store.register_agent("pm-primary", [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        "pm-primary", _valid_charter("pm", "Do PM things."), actor="test", parent_revision=0
    )


def test_generate_context_includes_resolved_role_charter(project_dir, tmp_path, monkeypatch):
    _register_pm(project_dir, tmp_path, monkeypatch)
    context_text = generate_context(
        scope="full", out_path=str(project_dir / ".synlynk" / "context.md")
    )
    assert "## Role Charter" in context_text
    assert "Do PM things." in context_text


def test_generate_context_is_noop_when_workspace_has_no_agents(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(os.path, "expanduser", lambda path: path.replace("~", str(tmp_path / "fake_home")))
    context_text = generate_context(
        scope="full", out_path=str(project_dir / ".synlynk" / "context.md")
    )
    assert "## Role Charter" not in context_text


def test_generate_context_stamps_dynamic_runtime_home_authority(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("ANTIGRAVITY_SESSION_ID", "test-session-123")
    context_text = generate_context(
        scope="full", out_path=str(project_dir / ".synlynk" / "context.md")
    )
    assert "## Active Session Runtime Authority" in context_text
    assert "**Active Home Harness:** agy" in context_text
    assert "Constitutional Precedence" in context_text


def test_write_context_pack_contains_required_sections(tmp_path, monkeypatch):
    from synlynk import context as context_mod

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, "
        "engg_domain TEXT, org_domain TEXT, phase TEXT, role TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO stories VALUES ('story-1', 'Add widget', 'backend', "
        "'core', 'build', 'dev', 'open')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        context_mod, "_get_db", lambda: sqlite3.connect(str(db_path)), raising=False
    )

    out_path = tmp_path / "context-packs" / "job-xyz.md"
    context_mod.write_context_pack(
        job_id="job-xyz",
        story_id="story-1",
        out_path=str(out_path),
    )

    assert out_path.exists()
    text = out_path.read_text()
    assert "## Objective" in text
    assert "## Findings" in text
    assert "## Changed Files / Verification State" in text
    assert "## Unresolved Work" in text
    assert "## Must-Survive Constraints" in text
    assert "Add widget" in text

