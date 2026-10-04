def test_dispatch_agent_still_accepts_all_existing_kwargs(monkeypatch):
    """dispatch_agent()'s signature must not change shape for any existing caller."""
    import inspect
    from synlynk.dispatch import dispatch_agent

    sig = inspect.signature(dispatch_agent)
    existing_kwargs = {
        "agent", "task", "story_id", "agent_id", "force_agent", "context_mode",
        "cycle", "skip_preflight", "requires_gh_write", "static_baseline",
        "task_type", "requires", "grants", "revokes", "job_id", "issue", "base",
        "scope_paths", "session_id", "gh_write_target_kind", "gh_write_expect",
        "model", "effort", "model_tier", "role", "task_domain", "criticality",
        "lambda_", "db_conn", "_startup_failover", "container_image",
    }
    assert existing_kwargs.issubset(set(sig.parameters.keys()))
