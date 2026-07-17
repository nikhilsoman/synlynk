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
