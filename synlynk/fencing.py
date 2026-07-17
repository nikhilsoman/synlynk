"""Estimate fence helpers for task dispatch output."""

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class FenceData:
    command: str
    kind: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    basis: str
    hints: Optional[Iterable[str]] = None
    label: Optional[str] = None


def render_task_fence(fence: FenceData) -> str:
    """Render a compact human-readable estimate fence."""
    title = fence.label or fence.command
    status = "estimate" if fence.kind == "estimate" else "complete"
    cost_prefix = "~" if fence.kind == "estimate" else ""
    token_text = f"{fence.in_tokens:,} in / {fence.out_tokens:,} out"
    lines = [
        f"-- {title} {status} ",
        f"cost: {cost_prefix}${fence.cost_usd:.2f}",
        token_text,
        f"basis: {fence.basis}",
    ]
    for hint in fence.hints or []:
        lines.append(f"tip:    {hint}")
    return (
        "\n".join(lines)
    )


def is_fenced_command(command: str, config: dict) -> bool:
    """Return True when command is explicitly listed for fence rendering."""
    fenced_commands = config.get("fenced_commands") or []
    return command in fenced_commands
