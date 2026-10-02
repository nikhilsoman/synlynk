import pytest
from synlynk.autonomy import (
    AutonomyMode,
    get_autonomy_mode,
    set_autonomy_mode,
    can_auto_advance,
)

def test_autonomy_mode_default_is_supervised(tmp_path, monkeypatch):
    config_file = tmp_path / ".synlynk" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{}")
    monkeypatch.chdir(tmp_path)

    assert get_autonomy_mode() == AutonomyMode.SUPERVISED

def test_autonomy_mode_mutation_persists(tmp_path, monkeypatch):
    config_file = tmp_path / ".synlynk" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{}")
    monkeypatch.chdir(tmp_path)

    set_autonomy_mode(AutonomyMode.AUTONOMOUS)
    assert get_autonomy_mode() == AutonomyMode.AUTONOMOUS

    set_autonomy_mode(AutonomyMode.MANUAL)
    assert get_autonomy_mode() == AutonomyMode.MANUAL

def test_autonomy_mode_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid autonomy mode"):
        set_autonomy_mode("wild_west")

def test_can_auto_advance_rules():
    # manual allows no automatic transitions
    assert not can_auto_advance("open", AutonomyMode.MANUAL)
    assert not can_auto_advance("execute", AutonomyMode.MANUAL)

    # supervised allows drafting but halts before execution & release
    assert can_auto_advance("visualize", AutonomyMode.SUPERVISED)
    assert not can_auto_advance("execute", AutonomyMode.SUPERVISED)
    assert not can_auto_advance("release", AutonomyMode.SUPERVISED)

    # autonomous allows all standard GOVERNS transitions
    assert can_auto_advance("open", AutonomyMode.AUTONOMOUS)
    assert can_auto_advance("execute", AutonomyMode.AUTONOMOUS)
    assert can_auto_advance("release", AutonomyMode.AUTONOMOUS)
