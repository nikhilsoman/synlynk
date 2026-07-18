import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))


def test_estimate_sweep_cost_multiplies_agents_models_skills(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from synlynk.capability_sweep import _estimate_sweep_cost

    discovered = {
        "codex": ["gpt-5-codex"],
        "agy": ["gemini-2.5-pro"],
    }
    skills = ["PROG", "TEST"]

    cost = _estimate_sweep_cost(discovered, skills)

    assert cost > 0
    assert isinstance(cost, float)


def test_estimate_sweep_cost_scales_with_more_models():
    from synlynk.capability_sweep import _estimate_sweep_cost

    small = _estimate_sweep_cost({"codex": ["gpt-5-codex"]}, ["PROG"])
    large = _estimate_sweep_cost({"codex": ["gpt-5-codex", "gpt-5.4-mini"]}, ["PROG"])

    assert large > small


def test_sweep_aborts_when_estimate_exceeds_cap(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.capability_sweep import cmd_capability_sweep
    import pytest

    monkeypatch.setattr(
        "synlynk.capability_sweep._discover_models",
        lambda: {"codex": [f"model-{i}" for i in range(50)]},
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_capability_sweep(cost_cap_override=0.01)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "exceeds cap" in captured.out.lower() or "exceeds cap" in captured.err.lower()
