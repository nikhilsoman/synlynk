import json
import os

from synlynk import load_config


def test_load_config_default_fenced_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    config = load_config()
    assert config["fenced_commands"] == ["dispatch", "jobs", "exec", "schedule"]


def test_load_config_preserves_existing_fenced_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"fenced_commands": ["dispatch"]}, f)
    config = load_config()
    assert config["fenced_commands"] == ["dispatch"]


def test_load_config_defaults_story_classification_method(project_dir):
    import synlynk as sl

    config = sl.load_config()

    assert config["story_classification"] == {"method": "heuristic"}


def test_load_config_preserves_explicit_story_classification_method(project_dir):
    import synlynk as sl

    config_path = ".synlynk/config.json"
    with open(config_path) as f:
        existing = json.load(f)
    existing["story_classification"] = {"method": "pm_manual"}
    with open(config_path, "w") as f:
        json.dump(existing, f)

    config = sl.load_config()

    assert config["story_classification"] == {"method": "pm_manual"}
