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


def test_explicit_harness_is_binding_before_capability_probe(monkeypatch):
    import synlynk as sl
    import synlynk.capability_probe as probe_mod
    from synlynk.dispatch import resolve_dispatch_harness

    monkeypatch.setattr(sl, "_best_agent_for_story", lambda *_args, **_kwargs: "agy")
    probed = []

    def capture_probe(**kwargs):
        probed.append(kwargs["candidate_harness"])
        return kwargs["candidate_harness"]

    monkeypatch.setattr(probe_mod, "resolve_capable_dispatch_harness", capture_probe)

    resolved = resolve_dispatch_harness(
        "codex", story_id="story-learned-agy", task="implement the requested fix"
    )

    assert resolved == "codex"
    assert probed == ["codex"]


def test_explicit_harness_is_binding_through_real_capability_probe(monkeypatch):
    from synlynk.capability_probe import IncompatibleHarnessCapabilityError
    from synlynk.capability_probe import CapabilityEvaluationResult
    from synlynk.dispatch import resolve_dispatch_harness

    monkeypatch.setattr(
        "synlynk.capability_probe.evaluate_harness_capabilities",
        lambda harness, _required, **_kwargs: CapabilityEvaluationResult(
            allowed=harness == "agy",
            missing_capabilities=[] if harness == "agy" else ["browser"],
        ),
    )

    with __import__("pytest").raises(IncompatibleHarnessCapabilityError):
        resolve_dispatch_harness("codex", task="browser automation", requires=["browser"])


def test_auto_harness_uses_learned_route_before_capability_probe(monkeypatch):
    import synlynk as sl
    import synlynk.capability_probe as probe_mod
    from synlynk.dispatch import resolve_dispatch_harness

    monkeypatch.setattr(sl, "_best_agent_for_story", lambda *_args, **_kwargs: "agy")
    probed = []

    def capture_probe(**kwargs):
        probed.append(kwargs["candidate_harness"])
        return kwargs["candidate_harness"]

    monkeypatch.setattr(probe_mod, "resolve_capable_dispatch_harness", capture_probe)

    resolved = resolve_dispatch_harness(
        "auto", story_id="story-learned-agy", task="implement the requested fix"
    )

    assert resolved == "agy"
    assert probed == ["agy"]


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

    result = resolve_dispatch_harness("auto", agent_id="dev-agent-1")
    assert result == "codex"


def test_role_only_dispatch_cold_start_falls_back_to_static_baseline(tmp_path, monkeypatch):
    os.makedirs("synlynk/state", exist_ok=True)
    from synlynk.dispatch import resolve_dispatch_harness

    _register_agent(tmp_path, monkeypatch, "dev-agent-2", "architect")

    result = resolve_dispatch_harness("auto", agent_id="dev-agent-2")
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
        "auto", agent_id="dev-agent-3", static_baseline=True
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
        "auto", agent_id="dev-agent-4", story_id="story-real-1", static_baseline=True
    )
    assert result == "claude"


def test_review_dispatch_excludes_branch_daemon_implementer(tmp_path, monkeypatch):
    import json
    import pytest
    from synlynk import _get_db
    import synlynk.db as db_mod
    from synlynk.capability_probe import IncompatibleHarnessCapabilityError
    from synlynk.dispatch import resolve_dispatch_harness

    monkeypatch.chdir(tmp_path)
    os.makedirs("synlynk/state", exist_ok=True)
    monkeypatch.setattr(db_mod, "_pr_head_branch", lambda pr_num: "dispatch/codex/job-63a4b857" if pr_num == 2272 else None)

    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, harness, agent, task, purpose, status, priority, depends_on, enqueued_at, handoff_count, requires_gh_write, gh_write_verification_attempts, terminal_evidence_strength) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("job-63a4b857", "codex", "codex", "impl task", "implementation", "completed", 1, "[]", "2026-10-14T00:00:00", 0, 0, 0, "strong"),
    )
    conn.commit()
    conn.close()

    # 1. Review task names PR #2272, head branch dispatch/codex/job-63a4b857, daemon job harness codex, purpose implementation, no cost row.
    # An explicit excluded harness fails closed instead of silently becoming Agy.
    with pytest.raises(IncompatibleHarnessCapabilityError):
        resolve_dispatch_harness("codex", task="review PR #2272", task_type="review", requires_gh_write=True)

    # 2. Same rows, requested harness agy, returns agy.
    res2 = resolve_dispatch_harness("agy", task="review PR #2272", task_type="review", requires_gh_write=True)
    assert res2 == "agy"

    # 3. force_agent=True with requested harness codex raises IncompatibleHarnessCapabilityError.
    with pytest.raises(IncompatibleHarnessCapabilityError):
        resolve_dispatch_harness("codex", task="review PR #2272", task_type="review", requires_gh_write=True, force_agent=True)

    # 4. Head branch missing, or daemon row absent: no exclusion, requested codex stays codex.
    monkeypatch.setattr(db_mod, "_pr_head_branch", lambda pr_num: None)
    res4a = resolve_dispatch_harness("codex", task="review PR #2272", task_type="review", requires_gh_write=True)
    assert res4a == "codex"

    monkeypatch.setattr(db_mod, "_pr_head_branch", lambda pr_num: "dispatch/codex/job-missing-daemon" if pr_num == 2272 else None)
    res4b = resolve_dispatch_harness("codex", task="review PR #2272", task_type="review", requires_gh_write=True)
    assert res4b == "codex"

    # Reset monkeypatch for test 5
    monkeypatch.setattr(db_mod, "_pr_head_branch", lambda pr_num: "dispatch/codex/job-63a4b857" if pr_num == 2272 else None)

    # 5. A cost_entries row for that PR whose harness is agy does not override the daemon/branch harness codex. The review still must not run on codex.
    conn = _get_db()
    conn.execute(
        "INSERT INTO cost_entries (job_id, pr_number, harness, agent, session_date, cost_source) VALUES (?, ?, ?, ?, ?, ?)",
        ("job-other", 2272, "agy", "agy", "2026-10-14", "native"),
    )
    conn.commit()
    conn.close()

    with pytest.raises(IncompatibleHarnessCapabilityError):
        resolve_dispatch_harness("codex", task="review PR #2272", task_type="review", requires_gh_write=True)

    # 6. .synlynk/policy.json in the repo still has cross_harness_review_required_mode == observe after your change. Assert that. Do not edit the file.
    repo_policy_path = os.path.join(os.path.dirname(__file__), "..", ".synlynk", "policy.json")
    with open(repo_policy_path, "r", encoding="utf-8") as f:
        policy_data = json.load(f)
    assert policy_data["overrides"]["merge_authority"]["cross_harness_review_required_mode"] == "observe"

