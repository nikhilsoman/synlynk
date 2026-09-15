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
