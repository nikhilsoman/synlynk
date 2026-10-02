import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

def generate_executive_brief(repo_path: str, goals: List[dict], evidence: dict, mode: str = "Brownfield") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Executive Project Brief: {Path(repo_path).name or 'Root Workspace'}",
        f"**Mode:** {mode} | **Generated:** {now}",
        "",
        "## 1. Discovered Signals & Architecture",
        f"- **Root Path:** `{repo_path}`",
        f"- **Source Files Detected:** {evidence.get('code_files', 0)}",
        f"- **Package Manifests:** {', '.join(evidence.get('manifests', [])) or 'None'}",
        f"- **Test Surface:** {evidence.get('test_files', 0)} test files",
        "",
        "## 2. Synthesized Strategic Goals",
    ]

    for idx, g in enumerate(goals, 1):
        lines.extend([
            f"### Goal {idx} [{g.get('priority', 'P1')}]: {g.get('title', 'Goal')}",
            f"- **Category:** `{g.get('category', 'general')}`",
            f"- **Rationale:** {g.get('rationale', '')}",
            "- **Acceptance Criteria:**",
        ])
        for ac in g.get("acceptance_criteria", []):
            lines.append(f"  - [ ] {ac}")
        lines.append("")

    lines.extend([
        "## 3. Recommended First-Session Execution Step",
        f"Launch the P0 milestone delivery: execute `{goals[0].get('id', 'goal-1') if goals else 'goal-1'}` in an isolated worktree.",
        ""
    ])
    return "\n".join(lines)

def save_executive_brief(repo_path: str, content: str) -> Path:
    docs_dir = Path(repo_path) / "project-docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    brief_path = docs_dir / "brief.md"
    brief_path.write_text(content, encoding="utf-8")
    return brief_path

def review_and_approve_goals_tui(goals: List[dict], interactive: bool = True) -> List[dict]:
    if not interactive:
        return goals

    print("\n════════════════════════════════════════════════════════════════════")
    print(" 🎯 Review & Approve Synthesized Goals")
    print("════════════════════════════════════════════════════════════════════")
    for idx, g in enumerate(goals, 1):
        print(f" [{idx}] [{g.get('priority')}] {g.get('title')}")
        print(f"     → {g.get('rationale')}")

    print("\n Press [Enter] to approve all goals, or type comma-separated numbers to select.")
    try:
        val = input(" Choice (default: all): ").strip()
        if val:
            indices = [int(x.strip()) - 1 for x in val.split(",") if x.strip().isdigit()]
            selected = [goals[i] for i in indices if 0 <= i < len(goals)]
            if selected:
                return selected
    except (EOFError, KeyboardInterrupt):
        pass
    return goals
