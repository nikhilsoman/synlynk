from synlynk.viz import VizorHandler, generate_roles_html


def _roles_data():
    return {
        "workspace": {"name": "demo"},
        "goals": [{"outcome": "Ship a governed workspace"}],
        "workspace_agents": [{
            "agent_id": "pm-primary",
            "role": "pm",
            "durability": "durable",
            "target_harnesses": ["claude"],
            "charter_excerpt": "Owns roadmap decisions and workspace coordination.",
        }],
    }


def test_generate_roles_html_renders_active_agents():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert "<!DOCTYPE html>" in rendered
    assert "Workspace Agent Roles" in rendered
    assert "Living Charters" in rendered
    assert "@pm" in rendered


def test_generate_roles_html_renders_working_charter_editor():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert 'data-agent-id="pm-primary"' in rendered
    assert "/roles/charter/update" in rendered
    assert "<textarea" in rendered


def test_handler_handle_role_create(monkeypatch):
    from synlynk import agent_store

    calls = {}
    monkeypatch.setattr(agent_store, "list_agents", lambda: [])
    monkeypatch.setattr(agent_store, "register_agent", lambda agent_id, aliases: calls.update(agent_id=agent_id, aliases=aliases))
    monkeypatch.setattr(agent_store, "propose_charter_revision", lambda *args, **kwargs: calls.update(charter=args[1]))
    result = VizorHandler.__new__(VizorHandler)._handle_role_create({"role": "security-auditor", "durability": "durable"})
    assert result["ok"] is True
    assert "agent_id" in result
    assert calls["aliases"] == [{"kind": "role_slug", "value": "security-auditor"}]


def test_handle_role_create_stamps_human_actor_type(monkeypatch):
    from synlynk import agent_store

    calls = {}
    monkeypatch.setattr(agent_store, "list_agents", lambda: [])
    monkeypatch.setattr(agent_store, "register_agent", lambda agent_id, aliases: None)
    monkeypatch.setattr(
        agent_store, "propose_charter_revision",
        lambda *args, **kwargs: calls.update(kwargs) or 1,
    )
    VizorHandler.__new__(VizorHandler)._handle_role_create({"role": "security-auditor", "durability": "durable"})
    assert calls.get("actor_type") == "human"


def test_handle_charter_update_writes_new_revision(monkeypatch):
    from synlynk import agent_store

    calls = {}
    monkeypatch.setattr(agent_store, "read_charter", lambda agent_id: (
        "---\nschema_version: 1\nrole: secops\ndescription: \"x\"\n"
        "durability: durable\ntools: []\ncredentials: []\n---\n\n"
        "## Instructions\n\nOld mandate.\n\n## Authority & Escalation\n\nOld.\n\n"
        "## Workflow Ownership\n\nOld.\n",
        1,
    ))
    monkeypatch.setattr(
        agent_store, "propose_charter_revision",
        lambda *args, **kwargs: calls.update(kwargs) or 2,
    )
    result = VizorHandler.__new__(VizorHandler)._handle_charter_update({
        "agent_id": "secops", "parent_revision": 1,
        "mandate": "New mandate text.",
    })
    assert result["ok"] is True
    assert result["revision"] == 2
    assert calls.get("actor_type") == "human"


def test_handle_charter_update_conflict_on_stale_revision(monkeypatch):
    from synlynk import agent_store

    monkeypatch.setattr(agent_store, "read_charter", lambda agent_id: ("---\nrole: secops\n---\n\n## Instructions\n\nx\n", 3))

    def _raise(*args, **kwargs):
        raise agent_store.RevisionConflictError("stale")
    monkeypatch.setattr(agent_store, "propose_charter_revision", _raise)

    result = VizorHandler.__new__(VizorHandler)._handle_charter_update({
        "agent_id": "secops", "parent_revision": 1, "mandate": "New mandate.",
    })
    assert result["ok"] is False
    assert "conflict" in result["error"].lower()


def test_generate_roles_html_no_longer_claims_cli_only_provisioning():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert "stays on the CLI" not in rendered


def test_generate_roles_html_tags_enforced_authority():
    data = _roles_data()
    data["workspace_agents"][0]["autonomous_authorities"] = [
        {"name": "worktree_cleanup", "enforced": True},
        {"name": "author_blog", "enforced": False},
    ]
    rendered = generate_roles_html(data, 8721)
    assert "Enforced" in rendered
    assert "Guidance" in rendered


def test_generate_roles_html_renders_ftue_wizard_steps():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert 'data-step="1"' in rendered
    assert 'data-step="4"' in rendered
    assert "synlynk identity init --role" in rendered


def test_generate_roles_html_lists_attachable_capabilities():
    data = _roles_data()
    data["capability_registry"] = [
        {"capability_id": "worktree-cleanup", "name": "worktree_cleanup", "source": "native"},
    ]
    rendered = generate_roles_html(data, 8721)
    assert "worktree-cleanup" in rendered
    assert "Attach" in rendered





