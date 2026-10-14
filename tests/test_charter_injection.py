import json

import pytest

from synlynk import agent_store
from synlynk.charter_injection import CharterInjectionError, render_charter_section


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


def _charter_with_skills(role, skills):
    content = _valid_charter(role, "Bound skill test")
    return content.replace(
        "credentials: []\n",
        "credentials: []\n" + "skills:\n" + "".join(f"  - {skill}\n" for skill in skills),
    )


def _register_pm_with_charter(repo_dir, monkeypatch, content="# PM Charter\n\nDo PM things.\n"):
    monkeypatch.chdir(repo_dir)
    fake_home = repo_dir / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    agent_id = "pm-primary"
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        agent_id, _valid_charter("pm", content), actor="test", parent_revision=0
    )
    return agent_id


def test_render_charter_section_includes_resolved_role_charter(project_dir, tmp_path, monkeypatch):
    _register_pm_with_charter(project_dir, monkeypatch)
    section = render_charter_section(repo_path=str(project_dir))
    assert "## Role Charter" in section
    assert "Do PM things." in section
    assert "pm" in section


def test_render_charter_section_resolves_reassigned_role(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    agent_store.register_agent("architect-primary", [{"kind": "role_slug", "value": "architect"}])
    agent_store.propose_charter_revision(
        "architect-primary", _valid_charter("architect", "Design things."),
        actor="test", parent_revision=0,
    )
    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.write_text(json.dumps({
        "schema_version": 1,
        "repo_id": "test",
        "overrides": {
            "human_authority_role": {"role": "architect", "requires_human_approval": True},
        },
    }))
    section = render_charter_section(repo_path=str(project_dir))
    assert "Design things." in section


def test_render_charter_section_is_noop_when_workspace_has_no_agents(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    assert render_charter_section(repo_path=str(project_dir)) == ""


def test_render_charter_section_raises_when_registered_agents_lack_role(
    project_dir, tmp_path, monkeypatch
):
    monkeypatch.chdir(project_dir)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    agent_store.register_agent(
        "architect-primary", [{"kind": "role_slug", "value": "architect"}]
    )
    with pytest.raises(CharterInjectionError, match="no registered agent"):
        render_charter_section(repo_path=str(project_dir))


@pytest.mark.parametrize("skills", [["test-driven-development", "systematic-debugging"]])
def test_render_charter_section_includes_bound_skills_when_present(
    project_dir, tmp_path, monkeypatch, skills
):
    monkeypatch.chdir(project_dir)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    agent_store.register_agent("dev-primary", [{"kind": "role_slug", "value": "dev"}])
    agent_store.propose_charter_revision(
        "dev-primary", _charter_with_skills("dev", skills), actor="test", parent_revision=0
    )

    section = render_charter_section(repo_path=str(project_dir), role="dev")

    assert "## Bound Skills (required)" in section
    assert "- test-driven-development" in section
    assert "- systematic-debugging" in section


def test_render_charter_section_omits_bound_skills_when_absent(project_dir, tmp_path, monkeypatch):
    _register_pm_with_charter(project_dir, monkeypatch)

    section = render_charter_section(repo_path=str(project_dir))

    assert "## Bound Skills" not in section


def test_render_charter_section_omits_bound_skills_when_empty_list(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    agent_store.register_agent("pm-primary", [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        "pm-primary", _charter_with_skills("pm", []), actor="test", parent_revision=0
    )

    section = render_charter_section(repo_path=str(project_dir))

    assert "## Bound Skills" not in section


def test_render_charter_section_unchanged_for_pre_migration_charter(project_dir, tmp_path, monkeypatch):
    legacy = "# PM Charter\n\nDo PM things.\n"
    monkeypatch.setattr(
        "synlynk.charter_injection.resolve_role_charter",
        lambda **kwargs: ("pm", "pm-primary", 1, legacy),
    )

    section = render_charter_section(repo_path=str(project_dir))

    assert section == f"## Role Charter (pm, revision 1)\n\n{legacy}\n\n---\n\n"
