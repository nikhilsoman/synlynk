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


def test_generate_roles_html_has_synlynk_identity_note_without_create_form():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert "synlynk identity" in rendered.lower()
    assert "<form" not in rendered
    assert "/roles/create" not in rendered


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


