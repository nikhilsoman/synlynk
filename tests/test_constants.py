from synlynk._constants import HARNESS_CAPABILITY_BASELINES


def test_every_agent_baseline_declares_env_passthrough():
    for agent, baseline in HARNESS_CAPABILITY_BASELINES.items():
        assert "env_passthrough" in baseline, f"{agent} baseline missing env_passthrough"
        assert isinstance(baseline["env_passthrough"], list), f"{agent} env_passthrough must be a list"


def test_agy_baseline_valid_flags_includes_print_timeout_and_mode():
    valid = HARNESS_CAPABILITY_BASELINES["agy"]["dispatch_flags"]["valid_flags"]
    assert "--print-timeout" in valid
    assert "--mode" in valid

