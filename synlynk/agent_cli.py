"""CLI handlers for `synlynk agent init/list/show/edit/disable`.

Onboarding surface layered on top of synlynk/agent_store.py's storage
functions (PR #988). See docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md.
"""
import sys
import uuid

from synlynk import agent_store

SEED_CHARTERS = {
    "dev": "Implementation — writes the code.",
    "qa": "Quality assurance — tests and verifies work.",
    "pm": (
        "Program management — roadmap, brainstorming, issue triage. "
        "Runs a weekly competitive-intelligence sweep: tracks products serving "
        "synlynk's user segments, maintains a living capability/marketing-gap "
        "comparison doc, opens research tickets for candidate features, "
        "convenes harness-maintainer decide rounds, and escalates strong-fit "
        "candidates to the user as feature proposals."
    ),
    "architect": "System design — architecture and technical direction.",
    "tpm": "Technical program management — cross-cutting coordination, GOVERNS integration.",
    "designer": "Design — visual and interaction design.",
    "marketing": "Marketing — external communication and positioning.",
    "synlynk-bot": "Catch-all workspace automation identity.",
}

ROLES = list(SEED_CHARTERS)


def _resolve_or_exit(id_or_alias: str) -> str:
    agents = agent_store.list_agents()
    for entry in agents:
        if entry["agent_id"] == id_or_alias:
            return id_or_alias
    resolved = agent_store.resolve_agent_id(id_or_alias)
    if resolved:
        return resolved
    print(f"No agent found matching '{id_or_alias}'.", file=sys.stderr)
    raise SystemExit(1)


def cmd_agent_init(role: str) -> str:
    for entry in agent_store.list_agents():
        for alias in entry["aliases"]:
            if alias["kind"] == "role_slug" and alias["value"] == role:
                print(
                    f"Role '{role}' already has an agent ({entry['agent_id']}). "
                    "Only one agent per role is supported.",
                    file=sys.stderr,
                )
                raise SystemExit(1)

    agent_id = str(uuid.uuid4())
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(
        agent_id, SEED_CHARTERS[role], actor="cli", parent_revision=0
    )
    agent_store.regenerate_agent_projection(
        agent_id, repo_overrides={"capability_grants": {}}
    )
    print(f"Created agent {agent_id} (role: {role})")
    return agent_id


def cmd_agent_list() -> None:
    agents = agent_store.list_agents()
    if not agents:
        print("No agents registered. Run `synlynk agent init <role>` to create one.")
        return
    print(f"{'AGENT_ID':<38}{'ROLE':<13}{'STATUS':<11}CREATED_AT")
    for entry in agents:
        role = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), "?"
        )
        status = "disabled" if entry.get("disabled") else "active"
        print(f"{entry['agent_id']:<38}{role:<13}{status:<11}{entry['created_at']}")


def cmd_agent_show(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    role = next(
        (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), "?"
    )
    status = "disabled" if entry.get("disabled") else "active"
    content, revision = agent_store.read_charter(agent_id)

    print(f"agent_id:   {agent_id}")
    print(f"role:       {role}")
    print(f"status:     {status}")
    print(f"created_at: {entry['created_at']}")
    print("history:")
    for event in entry["history"]:
        print(f"  {event}")
    print(f"charter (revision {revision}):")
    print(content)


def cmd_agent_edit(id_or_alias: str, charter_path: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    if charter_path == "-":
        new_content = sys.stdin.read()
    else:
        with open(charter_path) as f:
            new_content = f.read()

    _, parent_revision = agent_store.read_charter(agent_id)
    try:
        new_revision = agent_store.propose_charter_revision(
            agent_id, new_content, actor="cli", parent_revision=parent_revision
        )
    except agent_store.RevisionConflictError:
        print(
            "Charter was updated by someone else since you last viewed it. "
            f"Run `synlynk agent show {agent_id}` and retry.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    agent_store.regenerate_agent_projection(agent_id)
    print(f"Updated charter for {agent_id} (revision {new_revision})")


def cmd_agent_disable(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    if entry.get("disabled"):
        print(f"Agent {agent_id} is already disabled.")
        return
    agent_store.set_agent_disabled(agent_id, actor="cli")
    print(f"Disabled agent {agent_id}.")
