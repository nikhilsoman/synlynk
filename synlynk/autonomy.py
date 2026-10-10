import json
import os
from enum import Enum


class AutonomyMode(str, Enum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


def _get_config_path() -> str:
    return os.path.join(os.getcwd(), ".synlynk", "config.json")


def get_autonomy_mode() -> AutonomyMode:
    path = _get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            mode_val = data.get("autonomy_mode", "supervised").lower()
            return AutonomyMode(mode_val)
        except (json.JSONDecodeError, ValueError, OSError):
            return AutonomyMode.SUPERVISED
    return AutonomyMode.SUPERVISED


def set_autonomy_mode(mode) -> AutonomyMode:
    if isinstance(mode, AutonomyMode):
        target = mode
    else:
        try:
            target = AutonomyMode(str(mode).lower())
        except ValueError:
            raise ValueError(
                f"Invalid autonomy mode '{mode}'. Choose from: manual, supervised, autonomous"
            )

    path = _get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

    data["autonomy_mode"] = target.value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return target


def can_auto_advance(stage: str, mode: AutonomyMode) -> bool:
    stage_normalized = stage.lower().strip()
    if mode == AutonomyMode.MANUAL:
        return False
    if mode == AutonomyMode.SUPERVISED:
        # Pauses before execution and public release
        if stage_normalized in ("execute", "release"):
            return False
        return True
    if mode == AutonomyMode.AUTONOMOUS:
        return True
    return False
