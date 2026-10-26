"""Resolve and render the charter for the current human authority role."""


class CharterInjectionError(Exception):
    """Raised when the authority role has no usable registered charter."""


SKILL_CONTRACT_PROMPTS = {
    "test-driven-development": (
        "[MANDATORY SKILL CONTRACT: test-driven-development]\n"
        "You MUST implement changes following strict TDD:\n"
        "1. Author a reproduction/verification test first.\n"
        "2. Verify test failure on baseline.\n"
        "3. Implement the minimal fix.\n"
        "4. Verify test success and lack of regressions.\n"
        "Commits that add code without accompanying tests violate this contract."
    ),
    "systematic-debugging": (
        "[MANDATORY SKILL CONTRACT: systematic-debugging]\n"
        "When diagnosing any unexpected behavior or test failure:\n"
        "1. Formulate testable root-cause hypotheses before editing code.\n"
        "2. Verify symptoms with evidence before proposing fixes.\n"
        "3. No speculative edits or premature completions without verification."
    ),
    "brainstorming": (
        "[MANDATORY SKILL CONTRACT: brainstorming]\n"
        "Before writing implementation code:\n"
        "1. Verify user intent and requirements.\n"
        "2. Explore alternative architectural approaches.\n"
        "3. Commit spec to docs/superpowers/specs/ before implementation."
    ),
}


def _find_agent_for_role(role: str, entries):
    for entry in entries:
        role_slug = next(
            (alias["value"] for alias in entry["aliases"] if alias["kind"] == "role_slug"),
            None,
        )
        if role_slug == role and not entry.get("disabled"):
            return entry
    return None


def resolve_role_charter(role: str = None, repo_path: str = None):
    """Resolve and return (role, agent_id, revision, content)."""
    from synlynk import agent_store
    from synlynk.policy import get_human_authority_role

    if role is None:
        role = get_human_authority_role(repo_path=repo_path)
    entries = agent_store.list_agents()
    if not entries:
        return role, "", 0, ""

    entry = _find_agent_for_role(role, entries)
    if entry is None:
        raise CharterInjectionError(
            f"Role {role!r} requested for charter injection, but no registered agent has "
            f"role_slug {role!r} (see agent_store.list_agents())"
        )

    content, revision = agent_store.read_charter(entry["agent_id"])
    if not content.strip():
        raise CharterInjectionError(
            f"role {role!r} (agent_id {entry['agent_id']!r}) has no charter content "
            f"(revision {revision})"
        )
    return role, entry["agent_id"], revision, content.strip()


def render_charter_section(repo_path: str = None, role: str = None) -> str:
    """Return the resolved authority role's charter as a Markdown section."""
    resolved_role, _agent_id, revision, content = resolve_role_charter(role=role, repo_path=repo_path)
    if not content:
        return ""

    from synlynk import charter_schema

    frontmatter_text, _body = charter_schema.split_frontmatter(content)
    bound_skills = []
    if frontmatter_text is not None:
        parsed = charter_schema.parse_frontmatter(frontmatter_text)
        skills = parsed.get("skills")
        if isinstance(skills, list):
            bound_skills = [skill for skill in skills if skill]

    bound_skills_section = ""
    if bound_skills:
        skill_contracts = []
        for skill in bound_skills:
            if skill in SKILL_CONTRACT_PROMPTS:
                skill_contracts.append(SKILL_CONTRACT_PROMPTS[skill])

        contracts_text = ""
        if skill_contracts:
            contracts_text = "\n\n" + "\n\n".join(skill_contracts)

        bound_skills_section = (
            "\n\n## Bound Skills (required)\n\n"
            "This role's charter binds the following skills for this dispatch. "
            "If your harness supports an\n"
            "equivalent skill/tool-loading mechanism, invoke it before proceeding "
            "— these are required, not optional,\n"
            "for tasks they apply to:\n"
            + "".join(f"- {skill}\n" for skill in bound_skills).rstrip("\n")
            + contracts_text
        )

    return (
        f"## Role Charter ({resolved_role}, revision {revision})\n\n"
        f"{content}{bound_skills_section}\n\n---\n\n"
    )
