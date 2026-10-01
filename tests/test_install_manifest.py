import json
import sys
from pathlib import Path
from datetime import datetime
import pytest

from synlynk.install_manifest import (
    get_install_manifest,
    write_install_manifest,
    record_install,
    update_ecosystem_status,
    DEFAULT_MANIFEST_PATH
)

def test_get_install_manifest_none(tmp_path):
    manifest_path = tmp_path / "install.json"
    assert get_install_manifest(path=manifest_path) is None

def test_record_install(tmp_path):
    manifest_path = tmp_path / "install.json"
    
    result = record_install(
        method="script",
        version="0.23.0",
        python_exe="/usr/bin/python3",
        env_path="/opt/synlynk/.venv",
        binary_path="/usr/local/bin/synlynk",
        install_spec={"source": "github"},
        rollback_target="0.22.0",
        path=manifest_path
    )
    
    assert manifest_path.exists()
    
    with open(manifest_path, "r") as f:
        data = json.load(f)
        
    assert data["method"] == "script"
    assert data["version"] == "0.23.0"
    assert data["python_executable"] == "/usr/bin/python3"
    assert "python_version" in data
    assert data["environment_path"] == "/opt/synlynk/.venv"
    assert data["binary_path"] == "/usr/local/bin/synlynk"
    assert data["install_spec"] == {"source": "github"}
    assert "installed_at" in data
    assert data["rollback_target"] == "0.22.0"
    assert data["ecosystem_tools"] == {}
    
    # Check return value matches
    assert result == data

def test_get_install_manifest(tmp_path):
    manifest_path = tmp_path / "install.json"
    data = {
        "method": "pipx",
        "version": "0.23.0",
        "python_executable": "/usr/bin/python3",
        "python_version": "3.10.0",
        "environment_path": "/opt/synlynk/.venv",
        "binary_path": "/usr/local/bin/synlynk",
        "install_spec": {},
        "installed_at": "2026-10-01T12:00:00Z",
        "rollback_target": None,
        "ecosystem_tools": {}
    }
    with open(manifest_path, "w") as f:
        json.dump(data, f)
        
    loaded = get_install_manifest(path=manifest_path)
    assert loaded == data

def test_update_ecosystem_status(tmp_path):
    manifest_path = tmp_path / "install.json"
    record_install(
        method="script",
        version="0.23.0",
        python_exe="/usr/bin/python3",
        env_path="/opt/synlynk/.venv",
        binary_path="/usr/local/bin/synlynk",
        install_spec={"source": "github"},
        path=manifest_path
    )
    
    update_ecosystem_status(
        tool_name="gh",
        installed=True,
        metadata={"version": "2.0.0"},
        path=manifest_path
    )
    
    data = get_install_manifest(path=manifest_path)
    assert "gh" in data["ecosystem_tools"]
    assert data["ecosystem_tools"]["gh"] == {
        "installed": True,
        "metadata": {"version": "2.0.0"}
    }
    
    # Update another tool without overwriting
    update_ecosystem_status(
        tool_name="pytest",
        installed=False,
        metadata={},
        path=manifest_path
    )
    
    data2 = get_install_manifest(path=manifest_path)
    assert "gh" in data2["ecosystem_tools"]
    assert "pytest" in data2["ecosystem_tools"]
    assert data2["ecosystem_tools"]["pytest"] == {
        "installed": False,
        "metadata": {}
    }
