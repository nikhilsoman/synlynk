"""Shared task-boundary cost fence helpers."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FenceData:
    command: str
    kind: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    basis: str
    hints: List[str] = field(default_factory=list)
    label: Optional[str] = None


@dataclass
class NudgeData:
    nudge_id: str
    title: str
    message: str
    follow_up: Optional[str] = None


def render_task_fence(data: FenceData) -> str:
    """Render a bordered fence block for a FenceData instance."""
    label = data.label or data.command
    suffix = "estimate" if data.kind == "estimate" else "complete"
    header = f"-- {label} {suffix} " + "-" * max(1, 32 - len(label) - len(suffix))
    prefix = "~$" if data.kind == "estimate" else "$"
    lines = [
        header,
        f"cost:   {prefix}{data.cost_usd:.2f}  ({data.in_tokens:,} in / {data.out_tokens:,} out, {data.basis})",
    ]
    for hint in data.hints:
        lines.append(f"tip:    {hint}")
    lines.append("-" * 36)
    return "\n".join(lines) + "\n"


def render_nudge_fence(data: NudgeData) -> str:
    """Render a bordered workspace-agent nudge block."""
    header = f"-- {data.title} " + "-" * max(1, 32 - len(data.title))
    lines = [header, data.message]
    if data.follow_up:
        lines.append(f"next: {data.follow_up}")
    lines.append("-" * 36)
    return "\n".join(lines) + "\n"


def is_fenced_command(command: str, config: dict) -> bool:
    """True if `command` is in config['fenced_commands']."""
    return command in (config.get("fenced_commands") or [])
