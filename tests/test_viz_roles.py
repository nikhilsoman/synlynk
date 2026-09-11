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


def test_generate_roles_html_has_provision_drawer():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert "Onboard Workspace Role" in rendered
    assert "archetype" in rendered.lower()
    assert "/roles/create" in rendered
    assert "Fullstack Builder" in rendered


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
