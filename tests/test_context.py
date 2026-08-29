import os

import pytest

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


def test_generate_context_raises_when_authority_role_unregistered(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(os.path, "expanduser", lambda path: path.replace("~", str(tmp_path / "fake_home")))
    with pytest.raises(Exception, match="no registered agent"):
        generate_context(scope="full", out_path=str(project_dir / ".synlynk" / "context.md"))
