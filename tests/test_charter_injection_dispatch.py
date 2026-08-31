import os
import json
import pytest
import synlynk
from synlynk import agent_store
from synlynk.charter_injection import (
    CharterInjectionError,
    render_charter_section,
    resolve_role_charter,
)


def _valid_charter(role, marker):
    return (
        "---\n"
        "schema_version: 1\n"
        f"role: {role}\n"
        f"description: \"{marker}\"\n"
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        f"{marker}\n\n"
        "## Authority & Escalation\n\nEscalates per policy.\n\n"
        "## Workflow Ownership\n\nOwns this test.\n"
    )


def _init_workspace_agents(project_dir, monkeypatch):
    monkeypatch.chdir(project_dir)
    fake_home = project_dir / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    for role in ["pm", "dev", "qa", "architect"]:
        agent_id = f"agent-{role}-1"
        agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
        agent_store.propose_charter_revision(
            agent_id,
            _valid_charter(role, f"This agent owns {role} tasks and execution."),
            actor="test",
            parent_revision=0,
        )


def test_render_charter_section_empty_workspace(tmp_path, monkeypatch):
    """When no agents are registered in the workspace, charter rendering returns empty string."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    result = render_charter_section(repo_path=str(tmp_path))
    assert result == ""


def test_render_charter_section_default_pm(project_dir, monkeypatch):
    """Default charter section resolves the human_authority_role (defaulting to pm)."""
    _init_workspace_agents(project_dir, monkeypatch)

    result = render_charter_section(repo_path=str(project_dir))
    assert "## Role Charter (pm, revision 1)" in result
    assert "This agent owns pm tasks and execution." in result


def test_render_charter_section_explicit_role(project_dir, monkeypatch):
    """Explicit role passes through and renders that role charter."""
    _init_workspace_agents(project_dir, monkeypatch)

    result = render_charter_section(repo_path=str(project_dir), role="dev")
    assert "## Role Charter (dev, revision 1)" in result
    assert "This agent owns dev tasks and execution." in result

    qa_result = render_charter_section(repo_path=str(project_dir), role="qa")
    assert "## Role Charter (qa, revision 1)" in qa_result
    assert "This agent owns qa tasks and execution." in qa_result


def test_render_charter_section_missing_role_raises(project_dir, monkeypatch):
    """When workspace is adopted but requested role does not exist, raises CharterInjectionError."""
    _init_workspace_agents(project_dir, monkeypatch)

    with pytest.raises(CharterInjectionError) as exc:
        render_charter_section(repo_path=str(project_dir), role="nonexistent_role")
    assert "nonexistent_role" in str(exc.value)


def test_task_context_includes_charter(project_dir, monkeypatch, isolated_db):
    """_generate_task_context includes the charter for the story or explicit role."""
    _init_workspace_agents(project_dir, monkeypatch)

    db = synlynk._get_db()
    db.execute(
        "INSERT INTO stories (story_id, title, role, status) VALUES (?, ?, ?, ?)",
        ("story-101", "Implement feature", "dev", "open")
    )
    db.commit()

    context_str = synlynk._generate_task_context("story-101", role="dev")
    assert "## Role Charter (dev, revision 1)" in context_str
    assert "This agent owns dev tasks and execution." in context_str


def test_dispatch_agent_populates_charter_metadata_and_context(project_dir, monkeypatch, isolated_db):
    """dispatch_agent includes charter in context and populates job dict metadata."""
    _init_workspace_agents(project_dir, monkeypatch)

    class FakeProc:
        pid = 12345
        returncode = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def communicate(self, *args, **kwargs):
            return (b"", b"")

        def poll(self):
            return None

    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(synlynk, "_preflight_dispatch", lambda **kw: {"passed": True, "sentinel": None, "reason": None})

    job = synlynk.dispatch_agent("codex", "Run unit tests", role="qa", context_mode="full")
    assert job["charter_role"] == "qa"
    assert job["charter_revision"] == 1
    assert os.path.exists(job["context_file"])
    with open(job["context_file"]) as f:
        ctx_content = f.read()
    assert "## Role Charter (qa, revision 1)" in ctx_content
