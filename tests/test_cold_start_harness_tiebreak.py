"""Cold-start cost tiebreak must not select an incapable local harness (gh:#2048)."""

import os


def _seed_tied_story(conn, story_id, agents):
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, org_domain, industry, phase, estimated_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "cold", "backend", "platform", "unknown", "build", 1000),
    )
    for agent in agents:
        conn.execute(
            "INSERT INTO capability_ratings "
            "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
            " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (story_id, agent, "m", "backend", "platform", "unknown", "build", "auto", 8.0, 8.0),
        )
    conn.commit()


def test_cold_start_cost_tie_still_prefers_zero_cost_local_without_requirements(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story

    conn = _get_db()
    _seed_tied_story(conn, "story-tie", ["agy", "claude", "codex", "grok", "local"])
    conn.close()

    assert _best_agent_for_story("story-tie") == "local"


def test_cold_start_tie_excludes_local_when_github_write_is_required(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story

    conn = _get_db()
    _seed_tied_story(conn, "story-gh", ["agy", "claude", "codex", "grok", "local"])
    conn.close()

    chosen = _best_agent_for_story("story-gh", required_capabilities={"write:github", "run:shell"})
    assert chosen != "local"
    assert chosen in {"agy", "claude", "codex", "grok"}


def test_cold_start_returns_none_when_only_local_cannot_satisfy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story

    conn = _get_db()
    _seed_tied_story(conn, "story-only-local", ["local"])
    conn.close()

    assert _best_agent_for_story(
        "story-only-local", required_capabilities={"write:github"}
    ) is None


def test_reroute_message_blames_probed_harness_not_cli_argument():
    from synlynk.dispatch import _capability_reroute_message

    message = _capability_reroute_message("grok", "codex", "local")
    assert "rerouted 'grok' -> 'codex'" in message
    assert "capability-probed: 'local'" in message
    assert "capability-probed: 'grok'" not in message


def test_resolve_records_substituted_local_as_the_probed_harness(monkeypatch):
    from synlynk.dispatch import resolve_dispatch_harness, take_probed_dispatch_harness

    monkeypatch.setattr(
        "synlynk._best_agent_for_story",
        lambda story_id, **kwargs: "local",
    )
    result = resolve_dispatch_harness(
        "grok",
        story_id="story-cold",
        task="ship the infra change",
        task_type="infra",
        requires_gh_write=True,
    )
    assert result == "codex"
    assert take_probed_dispatch_harness() == "local"
