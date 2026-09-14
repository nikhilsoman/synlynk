import json
import os
from pathlib import Path
from typing import List, Dict, Any


def detect_developer_surfaces(repo_root: str) -> List[str]:
    """Detect presence of AI IDEs, cloud workspaces, and developer surfaces in repo or host."""
    p = Path(repo_root)
    surfaces = []
    if (p / ".cursor").is_dir() or os.path.exists("/Applications/Cursor.app"):
        surfaces.append("cursor")
    if (p / ".windsurf").is_dir() or (p / ".windsurfrules").is_file():
        surfaces.append("windsurf")
    if (p / ".vscode").is_dir():
        surfaces.append("vscode")
    if (p / ".warp").is_dir() or (Path.home() / ".warp").is_dir() or os.environ.get("TERM_PROGRAM") == "WarpTerminal":
        surfaces.append("warp")
    if (Path.home() / ".gemini" / "antigravity-cli").is_dir() or os.environ.get("ANTIGRAVITY_ENV"):
        surfaces.append("antigravity")
    if (p / ".replit").is_file() or os.environ.get("REPL_ID") or os.environ.get("REPLIT_ENVIRONMENT"):
        surfaces.append("replit")
    if (p / ".emergent").is_dir() or os.environ.get("EMERGENT_ENV"):
        surfaces.append("emergent")
    if (Path.home() / "Library" / "Application Support" / "Claude").is_dir():
        surfaces.append("claude_desktop")
    if not surfaces:
        surfaces.append("terminal")
    return surfaces


def bind_surface_rules(repo_root: str, surfaces: List[str]) -> Dict[str, Any]:
    """Inject non-destructive rules, workflows, and MCP configs for detected surfaces."""
    p = Path(repo_root)
    results = {}

    if "cursor" in surfaces:
        rules_dir = p / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        mdc_path = rules_dir / "synlynk.mdc"
        mdc_path.write_text("""---
description: synlynk project protocol — Home Conductor, task tracking, worktree discipline
alwaysApply: true
---

# synlynk Home Conductor Protocol

## Role & Identity
You are operating inside a synlynk-managed repository. You are the Home Conductor.
- Read `.synlynk/context.md` at session start.
- Work in dedicated git worktrees (`git worktree add .worktrees/<name> feat/<name>`). Never commit directly to main.
- Do NOT hand-edit `todo.md`. Update task status via `synlynk story done <id>`.
- Record decisions in `project-docs/memory.md` with attribution.
- Provisioned Workspace Agents (`@syn-pm[bot]`, `@syn-qa[bot]`) handle review and approval gates.
""")
        results["cursor"] = str(mdc_path)

    if "warp" in surfaces:
        warp_wf_dir = p / ".warp" / "workflows"
        warp_wf_dir.mkdir(parents=True, exist_ok=True)
        wf_path = warp_wf_dir / "synlynk.yaml"
        wf_path.write_text("""name: synlynk start
description: Launch synlynk autonomous developer onboarding or workspace session
command: synlynk start
tags:
  - synlynk
  - ai-agent
---
name: synlynk dispatch
description: Dispatch an away worker harness into an isolated worktree
command: synlynk dispatch {{harness}} --task "{{task}}"
tags:
  - synlynk
  - dispatch
""")
        results["warp"] = str(wf_path)

    if "replit" in surfaces:
        replit_rules = p / ".replitrules"
        replit_rules.write_text("""<!-- synlynk:start version="0.21.0" tool="replit" -->
# synlynk Replit Agent Instructions
You are operating as a Synlynk Home Conductor inside Replit.
- Synlynk daemon is running at http://localhost:27471.
- Read `.synlynk/context.md` for workspace state.
- Always implement features in dedicated branches/worktrees before merging.
<!-- synlynk:end -->
""")
        results["replit"] = str(replit_rules)

    if "emergent" in surfaces:
        emergent_dir = p / ".emergent"
        emergent_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = emergent_dir / "synlynk.json"
        cfg_path.write_text(json.dumps({
            "mcp_gateway": "http://localhost:27471/mcp",
            "autonomous_mode": True,
            "worktree_isolation": True
        }, indent=2))
        results["emergent"] = str(cfg_path)

    if "antigravity" in surfaces:
        gemini_md = p / "GEMINI.md"
        gemini_md.write_text("""<!-- synlynk:start version="0.21.0" tool="agy" -->
# synlynk AntiGravity Instructions
You are the primary Home Harness and Project Conductor.
- Context window: 1M-2M tokens (ingest `.synlynk/context.md` in full).
- Drive Unattended Milestone Loop: Spec -> Plan -> Worktree -> TDD -> PR.
- Record decisions in `project-docs/memory.md`.
<!-- synlynk:end -->
""")
        results["antigravity"] = str(gemini_md)

    return results
