import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _register_agent(tmp_path, monkeypatch, agent_id, org_role):
    """Registers a workspace agent with the given org role, returning its agent_id."""
    monkeypatch.chdir(tmp_path)
    from synlynk import agent_store
    agent_store.init_agent(agent_id, role=org_role, charter="test agent")
    return agent_id


def test_role_only_dispatch_uses_synthetic_story_capability_score(tmp_path, monkeypatch):
    """A role-only dispatch (no story_id) with an existing synthetic-story rating picks the
    learned harness, not the alphabetical-first static baseline."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, agent_store
    from synlynk._constants import _role_dispatch_story_id
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-1", role="architect", charter="test")
    story_id = _role_dispatch_story_id("architect")
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "seed", "general", "general", "general", "build", "architect"),
    )
    # "codex" would never win _harness_for_org_role's static architect pick (codex isn't
    # tagged "architect" in AGENT_CAPABILITY_BASELINES) — so a codex pick here proves the
    # synthetic-story score path fired, not the static fallback.
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (story_id, "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness("claude", agent_id="dev-agent-1")
    assert result == "codex"


def test_role_only_dispatch_cold_start_falls_back_to_static_baseline(tmp_path, monkeypatch):
    """No prior synthetic-story rating for this role -> unchanged _harness_for_org_role pick."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import agent_store
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-2", role="architect", charter="test")
    result = resolve_dispatch_harness("claude", agent_id="dev-agent-2")
    # architect baseline role: "agy" sorts first alphabetically among CORE_FLEET agents
    # tagged "architect" in AGENT_CAPABILITY_BASELINES.
    assert result == "agy"


def test_static_baseline_forces_static_pick_over_synthetic_story_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, agent_store
    from synlynk._constants import _role_dispatch_story_id
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-3", role="architect", charter="test")
    story_id = _role_dispatch_story_id("architect")
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "seed", "general", "general", "general", "build", "architect"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (story_id, "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness("claude", agent_id="dev-agent-3", static_baseline=True)
    assert result == "agy"  # static baseline pick, ignoring the codex score


def test_static_baseline_forces_static_pick_even_with_real_story_id_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, agent_store
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-4", role="architect", charter="test")
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, org_domain, industry, phase) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("story-real-1", "Real story", "general", "general", "general", "build"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-real-1", "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness(
        "claude", agent_id="dev-agent-4", story_id="story-real-1", static_baseline=True
    )
    assert result == "agy"  # static baseline pick, ignoring the real story_id's codex score
