import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _register_agent(tmp_path, monkeypatch, agent_id, org_role):
    monkeypatch.chdir(tmp_path)
    from synlynk import agent_store

    monkeypatch.setattr(
        agent_store, "_workspace_root", lambda _workspace_id: str(tmp_path / "workspace")
    )
    agent_store.register_agent(
        agent_id, aliases=[{"kind": "role_slug", "value": org_role}]
    )
    return agent_id


def test_role_only_dispatch_uses_synthetic_story_capability_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("synlynk/state", exist_ok=True)
    from synlynk import _get_db
    from synlynk._constants import _role_dispatch_story_id
    from synlynk.dispatch import resolve_dispatch_harness

    _register_agent(tmp_path, monkeypatch, "dev-agent-1", "architect")
    story_id = _role_dispatch_story_id("architect")
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories "
        "(story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "seed", "general", "general", "general", "build", "architect"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness("claude", agent_id="dev-agent-1")
    assert result == "codex"


def test_role_only_dispatch_cold_start_falls_back_to_static_baseline(tmp_path, monkeypatch):
    os.makedirs("synlynk/state", exist_ok=True)
    from synlynk.dispatch import resolve_dispatch_harness

    _register_agent(tmp_path, monkeypatch, "dev-agent-2", "architect")

    result = resolve_dispatch_harness("codex", agent_id="dev-agent-2")
    assert result == "claude"


def test_static_baseline_forces_static_pick_over_synthetic_story_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("synlynk/state", exist_ok=True)
    from synlynk import _get_db
    from synlynk._constants import _role_dispatch_story_id
    from synlynk.dispatch import resolve_dispatch_harness

    _register_agent(tmp_path, monkeypatch, "dev-agent-3", "architect")
    story_id = _role_dispatch_story_id("architect")
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories "
        "(story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "seed", "general", "general", "general", "build", "architect"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness(
        "codex", agent_id="dev-agent-3", static_baseline=True
    )
    assert result == "claude"


def test_static_baseline_forces_static_pick_even_with_real_story_id_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("synlynk/state", exist_ok=True)
    from synlynk import _get_db
    from synlynk.dispatch import resolve_dispatch_harness

    _register_agent(tmp_path, monkeypatch, "dev-agent-4", "architect")
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories "
        "(story_id, title, discipline, org_domain, industry, phase) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("story-real-1", "Real story", "general", "general", "general", "build"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("story-real-1", "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness(
        "codex", agent_id="dev-agent-4", story_id="story-real-1", static_baseline=True
    )
    assert result == "claude"
