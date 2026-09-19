"""Living charter drift detection and reviewable proposal generation."""

from __future__ import annotations

import json
from pathlib import Path

from synlynk.capability import capability_score


def _static_capabilities(path: str = ".synlynk/capability-roles.json") -> dict:
    """Load optional static charter probabilities, preserving old role maps."""
    try:
        with open(path) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    values = payload.get("static_capabilities", payload.get("capabilities", {}))
    return values if isinstance(values, dict) else {}


def detect_charter_divergence(conn=None, *, threshold: float = 0.25,
                              static_capabilities: dict | None = None) -> list[dict]:
    """Return empirical rows whose rate differs from the charter by > threshold."""
    from synlynk import _get_db
    db = conn or _get_db()
    owned = conn is None
    try:
        rows = db.execute("SELECT * FROM capability_ledger ORDER BY harness, task_domain, model_id").fetchall()
        names = [d[0] for d in db.execute("SELECT * FROM capability_ledger LIMIT 0").description]
        static = static_capabilities or _static_capabilities()
        findings = []
        for row in rows:
            item = dict(zip(names, row))
            empirical = item["alpha"] / (item["alpha"] + item["beta"])
            configured = static.get(item["harness"], {}).get(item["task_domain"], static.get(item["task_domain"], 0.5))
            if isinstance(configured, dict):
                configured = configured.get("success_rate", configured.get("probability", 0.5))
            configured = float(configured)
            divergence = empirical - configured
            if abs(divergence) > threshold:
                findings.append({**item, "empirical_success_rate": empirical,
                                 "static_success_rate": configured,
                                 "divergence": divergence})
        return findings
    finally:
        if owned:
            db.close()


def _proposal_text(finding: dict, roles_path: str, corpus_path: str) -> str:
    direction = "increase" if finding["divergence"] > 0 else "decrease"
    return f"""# Living charter proposal: {finding['harness']} / {finding['task_domain']}

This proposal is intentionally reviewable and does not modify a charter automatically.

- Model: `{finding['model_id']}`
- Harness: `{finding['harness']}`
- Domain: `{finding['task_domain']}`
- Empirical success rate: {finding['empirical_success_rate']:.1%}
- Static charter rate: {finding['static_success_rate']:.1%}
- Divergence: {finding['divergence']:+.1%}
- Observations: {finding['observations']}

Recommendation: **{direction}** the role's stated capability for this domain after
human review. Update `{roles_path}` and record the evidence in `{corpus_path}`.
"""


def cmd_charters_adapt(*, conn=None, threshold: float = 0.25, dry_run: bool = True,
                       proposals_dir: str = ".synlynk/charter-proposals",
                       roles_path: str = ".synlynk/roles.yaml",
                       corpus_path: str = "docs/charters/corpus-references.md") -> list[dict]:
    """Detect drift and emit one markdown proposal per divergent capability."""
    findings = detect_charter_divergence(conn, threshold=threshold)
    for finding in findings:
        finding["proposal"] = _proposal_text(finding, roles_path, corpus_path)
        if not dry_run:
            destination = Path(proposals_dir) / (
                f"{finding['harness']}-{finding['task_domain']}-{finding['model_id']}.md".replace("/", "-"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(finding["proposal"])
        print(f"{finding['harness']}/{finding['task_domain']}: "
              f"{finding['empirical_success_rate']:.1%} vs {finding['static_success_rate']:.1%} "
              f"({finding['divergence']:+.1%})")
    if not findings:
        print("No charter capability drift above the threshold.")

    adapted = adapt_charters_for_installed_tools(dry_run=dry_run)
    for role, info in adapted.items():
        if info.get("skills"):
            action_word = "Bound" if not dry_run else "Would bind"
            print(f"{action_word} skills to {role}: {', '.join(info['skills'])}")

    return findings


TOOL_ROLE_SKILLS: dict[str, dict[str, str]] = {
    "graphify": {
        "architect": "graphify-architecture-audit",
        "qa": "graphify-pr-impact",
        "verifier": "graphify-pr-impact",
        "dev": "graphify-symbol-navigator",
        "builder": "graphify-symbol-navigator",
        "pm": "graphify-domain-sweep",
    },
}

ALL_ADAPT_ROLES = (
    "architect",
    "qa",
    "verifier",
    "dev",
    "builder",
    "pm",
    "tpm",
    "designer",
    "marketing",
    "synlynk-bot",
)


def adapt_charters_for_installed_tools(*, dry_run: bool = False) -> dict[str, dict]:
    """Inspect installed ecosystem tools and attach corresponding skills to agent roles."""
    from synlynk import agent_store
    from synlynk import charter_schema
    from synlynk import tool_installer
    from synlynk.agent_cli import SEED_CHARTERS

    active_role_skills: dict[str, list[str]] = {}
    for tool_name, role_skill_map in TOOL_ROLE_SKILLS.items():
        if tool_installer.is_tool_available(tool_name):
            for role, skill in role_skill_map.items():
                active_role_skills.setdefault(role, []).append(skill)

    agents_by_role: dict[str, dict] = {}
    try:
        registered_agents = agent_store.list_agents()
        for agent in registered_agents:
            for alias in agent.get("aliases", []):
                if alias.get("kind") == "role_slug":
                    agents_by_role[alias["value"]] = agent
    except Exception:
        agents_by_role = {}

    updated: dict[str, dict] = {}
    for role in ALL_ADAPT_ROLES:
        if role in agents_by_role:
            agent = agents_by_role[role]
            agent_id = agent["agent_id"]
            content, revision = agent_store.read_charter(agent_id)
            if content:
                frontmatter_text, _ = charter_schema.split_frontmatter(content)
                parsed = charter_schema.parse_frontmatter(frontmatter_text) if frontmatter_text else {}
                existing_skills = list(parsed.get("skills", [])) if isinstance(parsed.get("skills"), list) else []

                desired_skills = list(existing_skills)
                for s in active_role_skills.get(role, []):
                    if s not in desired_skills:
                        desired_skills.append(s)

                # Remove skills for tools that are not available
                for tool_name, role_skill_map in TOOL_ROLE_SKILLS.items():
                    if not tool_installer.is_tool_available(tool_name):
                        skill_to_remove = role_skill_map.get(role)
                        if skill_to_remove and skill_to_remove in desired_skills:
                            desired_skills.remove(skill_to_remove)

                if desired_skills:
                    skills_block = "skills:\n" + "\n".join(f"  - {s}" for s in desired_skills) + "\n"
                else:
                    skills_block = "skills: []\n"

                new_content = charter_schema.set_frontmatter_block(content, "skills", skills_block)
                if not dry_run and new_content != content:
                    try:
                        agent_store.propose_charter_revision(
                            agent_id, new_content, actor="charters_adapt", parent_revision=revision
                        )
                    except Exception:
                        pass

                updated[role] = {
                    "role": role,
                    "skills": desired_skills,
                    "charter": new_content,
                    "agent_id": agent_id,
                }
                continue

        # Fallback to seed charter when no registered agent exists
        seed_role = "qa" if role == "verifier" else ("dev" if role == "builder" else role)
        seed_content = SEED_CHARTERS.get(seed_role, SEED_CHARTERS.get("dev", ""))
        frontmatter_text, _ = charter_schema.split_frontmatter(seed_content)
        parsed = charter_schema.parse_frontmatter(frontmatter_text) if frontmatter_text else {}
        existing_skills = list(parsed.get("skills", [])) if isinstance(parsed.get("skills"), list) else []

        desired_skills = list(existing_skills)
        for s in active_role_skills.get(role, []):
            if s not in desired_skills:
                desired_skills.append(s)

        for tool_name, role_skill_map in TOOL_ROLE_SKILLS.items():
            if not tool_installer.is_tool_available(tool_name):
                skill_to_remove = role_skill_map.get(role)
                if skill_to_remove and skill_to_remove in desired_skills:
                    desired_skills.remove(skill_to_remove)

        if desired_skills:
            skills_block = "skills:\n" + "\n".join(f"  - {s}" for s in desired_skills) + "\n"
        else:
            skills_block = "skills: []\n"

        new_content = charter_schema.set_frontmatter_block(seed_content, "skills", skills_block)
        updated[role] = {
            "role": role,
            "skills": desired_skills,
            "charter": new_content,
        }

    return updated


TRIGGER_REGISTRY: list[tuple[str, str | None, str]] = [
    ("fan out swarm work", "run ephemeral workers", "synlynk swarm dispatch"),
    ("show swarm runners", None, "synlynk swarm status"),
    ("tear down swarm runners", None, "synlynk swarm destroy"),
    ("generate media assets", "render svg diagrams and og cards", "synlynk media generate"),
    ("list registered models", None, "synlynk models list"),
    ("show model details", None, "synlynk models show"),
    ("discover installed models", None, "synlynk models discover"),
    ("switch home harness", "set home harness", "synlynk home"),
    ("set up synlynk here", "get started with synlynk", "synlynk init"),
    ("start a new project", "is this a new or existing project", "synlynk start"),
    ("scan this repo", "inventory this codebase", "synlynk scan"),
    ("fix repository gaps automatically", "run autonomous remediation", "synlynk heal"),
    ("run magic pr", "instant first win", "synlynk heal --magic"),
    ("add me to this project", "onboard me", "synlynk join"),
    ("migrate the old config", "upgrade project-docs layout", "synlynk migrate"),
    ("configure the codex harness", "override dispatch flags for grok", "synlynk configure agent"),
    ("add this agent binary", "retrofit an agent onto this project", "synlynk harness add"),
    ("write this agent's context profile", None, "synlynk harness configure"),
    ("what agents are configured", "list our agents", "synlynk harness list"),
    ("set this config key", None, "synlynk config set"),
    ("control workspace-agent nudges", None, "synlynk config nudges"),
    ("let's decide on X", "record this decision", "synlynk decide"),
    ("create a new goal", "start a business goal for X", "synlynk goal create"),
    ("what goals are active", "list our goals", "synlynk goal list"),
    ("open a work session", "start a work session", "synlynk session open"),
    ("what session am I in", "show the active session", "synlynk session status"),
    ("checkpoint this session", "save a session checkpoint", "synlynk session checkpoint"),
    ("close out this session", "finish this work session", "synlynk session close"),
    ("link this story to the goal", "attach this to goal X", "synlynk goal link"),
    ("how close is this goal", "goal completion rollup", "synlynk goal status"),
    ("create a story for X", "write up this piece of work", "synlynk story create"),
    ("what stories do we have", "list open stories", "synlynk story list"),
    ("mark this story ready", None, "synlynk story ready"),
    ("revert this story to draft", None, "synlynk story draft"),
    ("mark this story done", None, "synlynk story done"),
    ("capture discovered work", "stage a task into backlog", "synlynk backlog capture"),
    ("list staged backlog", "show discovered tasks", "synlynk backlog list"),
    ("sync backlog to github", "create issues for discovered tasks", "synlynk backlog sync"),
    ("ingest github issues", "fetch backlog issues", "synlynk backlog ingest"),
    ("triage open backlog", "synthesize backlog stories", "synlynk backlog triage"),
    ("auto-promote backlog items", "promote triaged stories to ready", "synlynk backlog auto-promote"),
    ("add a roadmap arc", "add a roadmap phase", "synlynk roadmap add"),
    ("open the workspace", "open this project", "synlynk open"),
    ("what should I do next", "give me a task to launch", "synlynk launch"),
    ("who has what role on this project", None, "synlynk roles"),
    ("let's build X", "can you implement...", "synlynk dispatch"),
    ("backfill capability ratings", "repair missing story ids", "synlynk backfill-capability-ratings"),
    ("adapt living charters", "detect charter drift", "synlynk charters adapt"),
    ("what's still running", "check on that job", "synlynk jobs"),
    ("hand this stalled job to another agent", None, "synlynk jobs handoff"),
    ("reap zombie jobs", "clear dead running jobs", "synlynk jobs reap"),
    ("batch these up", "run this fleet-wide", "synlynk schedule"),
    ("run the TPM sweep", "sweep ready stories", "synlynk tpm sweep"),
    ("run the competitive sweep", "check for competitor gaps", "synlynk pm sweep"),
    ("cut a release", "ship v0.x.0", "synlynk release"),
    ("is this PR's model version attested", None, "synlynk pr check"),
    ("qa merge gate status", "is the qa-gate green", "synlynk pr gate-status"),
    ("am I authorized to merge this", "check merge authority", "synlynk policy check-merge"),
    ("show current policy", "what is the current policy", "synlynk policy show"),
    ("sync branch protection", "enforce policy on github", "synlynk policy sync-branch-protection"),
    ("platform ops report", "nightly ops rollup", "synlynk ops report"),
    ("run a health check", "is synlynk set up correctly", "synlynk doctor"),
    ("probe this endpoint", None, "synlynk probe"),
    ("audit stale worktrees", "classify worktree safety", "synlynk worktree audit"),
    ("clean up stale worktrees", "remove safe worktrees", "synlynk worktree clean"),
    ("audit docs", "audit devlog identity drift", "synlynk audit-docs"),
    ("run claude directly with context", None, "synlynk exec"),
    ("launch the terminal ui", "open the curses dashboard", "synlynk tui"),
    ("tail that job's logs", None, "synlynk logs"),
    ("drop me into that job's shell", None, "synlynk shell"),
    ("what sentinel alerts are active", None, "synlynk sentinel list"),
    ("clear that sentinel alert", None, "synlynk sentinel clear"),
    ("log this manual session's cost", None, "synlynk cost log"),
    ("reconcile subscription costs", "true up monthly spend", "synlynk cost true-up"),
    ("grant a credit balance", "record a credit grant", "synlynk credit grant"),
    ("show agent quota headroom", None, "synlynk quota"),
    ("run a capability sweep", "seed capability baselines", "synlynk capability sweep"),
    ("run the trio protocol", None, "synlynk run --trio"),
    ("is the local oMLX agent reachable", None, "synlynk local doctor"),
    ("upgrade synlynk", None, "synlynk upgrade"),
    ("roll back the last change", None, "synlynk rollback"),
    ("where are we", "what's the state of things", "synlynk status"),
    ("show me the live HUD", "watch the workspace", "synlynk watch"),
    ("open the dashboard", "show me the browser view", "synlynk viz"),
    ("check relay health", None, "synlynk relay status"),
    ("message another agent", None, "synlynk relay send"),
    ("tail relay events", None, "synlynk relay tail"),
]


def render_trigger_registry_markdown() -> str:
    """Render the standard trigger registry markdown block."""
    lines = ["## Trigger registry", ""]
    for row in TRIGGER_REGISTRY:
        if row[1]:
            lines.append(f'- "{row[0]}", "{row[1]}" -> `{row[2]}`')
        else:
            lines.append(f'- "{row[0]}" -> `{row[2]}`')
    lines.append("")
    return "\n".join(lines)


def refresh_agent_instruction_triggers(repo_root: str = ".", dry_run: bool = False) -> dict[str, bool]:
    """Scan and update trigger registry across all instruction files (CLAUDE.md, GEMINI.md, AGENTS.md, GROK.md)."""
    root = Path(repo_root)
    trigger_md = render_trigger_registry_markdown().strip()
    target_files = ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md"]
    updated = {}

    for fname in target_files:
        fpath = root / fname
        if not fpath.exists():
            continue
        import re
        content = fpath.read_text(encoding="utf-8")
        if "## Trigger registry" in content:
            pattern = r"## Trigger registry[\s\S]*?(?=\n## |\n<!-- synlynk:end -->|\Z)"
            replacement = trigger_md + "\n\n"
            new_content = re.sub(pattern, replacement, content, count=1)
            if new_content != content:
                if not dry_run:
                    fpath.write_text(new_content, encoding="utf-8")
                updated[fname] = True
            else:
                updated[fname] = False
        else:
            updated[fname] = False

    return updated
