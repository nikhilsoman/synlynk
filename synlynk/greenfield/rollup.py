"""Multi-surface Genesis Rollup Card formatter (v0.28.5)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def format_rollup_card(
    workspace_dir: str,
    project_name: str,
    artifacts: List[str],
    *,
    branch: str = "main",
    github_repo: Optional[str] = None,
    decision_id: Optional[str] = None,
    vizor_port: int = 33333,
) -> str:
    """Format the integrated multi-surface summary card upon Genesis completion."""
    abs_workspace = os.path.abspath(workspace_dir)
    repo_display = github_repo or f"https://github.com/my-org/{project_name}"
    vizor_url = f"http://localhost:{vizor_port}/overview"
    dec_suffix = f"({decision_id})" if decision_id else ""

    lines = [
        "┌─────────────────────────────────────────────────────────────────────────────┐",
        "│ 🚀 PROJECT GENESIS COMPLETE                                                  │",
        "│                                                                             │",
        f"│ • Local Workspace:   {abs_workspace[:45].ljust(45)} (branch: {branch})│",
        f"│ • GitHub Repository: {repo_display[:50].ljust(54)} │",
        f"│ • Vizor HUD (Local): {vizor_url[:50].ljust(54)} │",
        "│                                                                             │",
        "│ 📁 Generated Governance Artifacts:                                          │",
    ]

    for art in artifacts:
        lines.append(f"│   ├── {art[:68].ljust(68)} │")

    lines.extend([
        "│                                                                             │",
        "│ ⚡ Next Step: Run 'synlynk dispatch' or open Vizor to start Task 2!         │",
        "└─────────────────────────────────────────────────────────────────────────────┘",
    ])
    return "\n".join(lines)
