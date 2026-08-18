from synlynk._constants import HARNESS_CAPABILITY_BASELINES


def test_every_agent_baseline_declares_env_passthrough():
    for agent, baseline in HARNESS_CAPABILITY_BASELINES.items():
        assert "env_passthrough" in baseline, f"{agent} baseline missing env_passthrough"
        assert isinstance(baseline["env_passthrough"], list), f"{agent} env_passthrough must be a list"
