import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

DEFAULT_MANIFEST_PATH = Path.home() / ".synlynk" / "install.json"

def get_install_manifest(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    manifest_path = path if path is not None else DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

def write_install_manifest(manifest_data: Dict[str, Any], path: Optional[Path] = None) -> Path:
    manifest_path = path if path is not None else DEFAULT_MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    tmp_path = manifest_path.with_suffix('.tmp')
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    
    os.replace(tmp_path, manifest_path)
    return manifest_path

def record_install(
    method: str, 
    version: str, 
    python_exe: str, 
    env_path: str, 
    binary_path: str, 
    install_spec: Dict[str, Any], 
    rollback_target: Optional[str] = None, 
    path: Optional[Path] = None
) -> Dict[str, Any]:
    
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # Simple formatting for UTC timestamp
    installed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    manifest_data = {
        "method": method,
        "version": version,
        "python_executable": python_exe,
        "python_version": python_version,
        "environment_path": env_path,
        "binary_path": binary_path,
        "install_spec": install_spec,
        "installed_at": installed_at,
        "rollback_target": rollback_target,
        "ecosystem_tools": {}
    }
    
    write_install_manifest(manifest_data, path)
    return manifest_data

def update_ecosystem_status(
    tool_name: str, 
    installed: bool, 
    metadata: Dict[str, Any], 
    path: Optional[Path] = None
) -> Dict[str, Any]:
    
    manifest_data = get_install_manifest(path)
    if manifest_data is None:
        manifest_data = {"ecosystem_tools": {}}
        
    if "ecosystem_tools" not in manifest_data:
        manifest_data["ecosystem_tools"] = {}
        
    manifest_data["ecosystem_tools"][tool_name] = {
        "installed": installed,
        "metadata": metadata
    }
    
    write_install_manifest(manifest_data, path)
    return manifest_data
