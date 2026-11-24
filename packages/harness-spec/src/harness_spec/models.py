"""Data models for harness-spec."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass(frozen=True)
class SandboxProfile:
    name: str
    network_allowed: bool
    filesystem_mode: str  # "strict", "workspace_only", "full"
    flag_arguments: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class HarnessContract:
    binary_name: str
    display_name: str
    installed: bool
    version: Optional[str] = None
    headless_prompt_flag: str = "-p"  # e.g., -p vs --prompt vs stdin
    default_sandbox_flag: Optional[str] = None
    env_overrides: Dict[str, str] = field(default_factory=dict)
