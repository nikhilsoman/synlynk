"""Regression tests for synlynk module re-exports during modularisation."""


def test_constants_importable_from_package():
    from synlynk import HARNESS_CAPABILITY_BASELINES, QUOTA_PATTERNS, VERSION

    assert isinstance(VERSION, str)
    assert "claude" in HARNESS_CAPABILITY_BASELINES
    assert isinstance(QUOTA_PATTERNS, list)


def test_upgrade_symbols_importable_from_package():
    from synlynk import _detect_install_type, _get_pipx_source, _run_upgrade, _ver_tuple, _warn_stale_script_install, upgrade

    assert callable(_detect_install_type)
    assert callable(_get_pipx_source)
    assert callable(_run_upgrade)
    assert callable(_ver_tuple)
    assert callable(_warn_stale_script_install)
    assert callable(upgrade)


def test_sentinel_symbols_importable_from_package():
    from synlynk import _check_costs_freshness, _extract_auto_signals, _extract_compliance_tags, _read_sentinel_alerts, _write_sentinel_alert, check_sentinel_patterns, log_telemetry_event, sentinel_clear, sentinel_list

    assert callable(_check_costs_freshness)
    assert callable(_extract_auto_signals)
    assert callable(_extract_compliance_tags)
    assert callable(_read_sentinel_alerts)
    assert callable(_write_sentinel_alert)
    assert callable(check_sentinel_patterns)
    assert callable(log_telemetry_event)
    assert callable(sentinel_clear)
    assert callable(sentinel_list)


def test_probe_symbols_importable_from_package():
    from synlynk import _build_fence_body_from_record, _build_fence_content, _compute_capability_hash, _fence_exists, _probe_agent, _probe_model_version, _run_tc0, _run_tc1, _run_tc2, _run_tc3, _run_tc4, _scan_command_palette, _upsert_harness_fence, _write_scan_fences, cmd_probe

    assert callable(_build_fence_body_from_record)
    assert callable(_build_fence_content)
    assert callable(_compute_capability_hash)
    assert callable(_fence_exists)
    assert callable(_probe_agent)
    assert callable(_probe_model_version)
    assert callable(_run_tc0)
    assert callable(_run_tc1)
    assert callable(_run_tc2)
    assert callable(_run_tc3)
    assert callable(_run_tc4)
    assert callable(_scan_command_palette)
    assert callable(_upsert_harness_fence)
    assert callable(_write_scan_fences)
    assert callable(cmd_probe)


def test_dispatch_symbols_importable_from_package():
    from synlynk import _check_job_stall, _check_pre_exec_gate, _format_job_summary, _format_prompt_for_agent, _inject_grok_rules, _is_interactive, _job_summary_path, _preflight_dispatch, _spawn_with_pty_fallback, _tee_process, _warn_context_size, _write_job_summary, dispatch_agent, exec_command

    assert callable(_check_job_stall)
    assert callable(_check_pre_exec_gate)
    assert callable(_format_job_summary)
    assert callable(_format_prompt_for_agent)
    assert callable(_inject_grok_rules)
    assert callable(_is_interactive)
    assert callable(_job_summary_path)
    assert callable(_preflight_dispatch)
    assert callable(_spawn_with_pty_fallback)
    assert callable(_tee_process)
    assert callable(_warn_context_size)
    assert callable(_write_job_summary)
    assert callable(dispatch_agent)
    assert callable(exec_command)
