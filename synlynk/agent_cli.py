"""CLI handlers for `synlynk agent init/list/show/edit/disable`.

Onboarding surface layered on top of synlynk/agent_store.py's storage
functions (PR #988). See docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md.
"""
import sys
import uuid

from synlynk import agent_store
from synlynk import charter_schema

SEED_CHARTERS = {
    "dev": (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "Implementation — writes the code."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "Implementation work: turn an approved plan or ticket into working, tested\n"
        "code. Dispatch-triggered only — no autonomous loop. Follow the plan's task\n"
        "breakdown; do not redesign architecture mid-implementation.\n\n"
        "## Authority & Escalation\n\n"
        "Decides implementation details (naming, file layout, test structure) within\n"
        "an approved plan unilaterally. Escalates to whoever holds\n"
        "`human_authority_role` before deviating from the plan's architecture or\n"
        "scope.\n\n"
        "## Workflow Ownership\n\n"
        "Owns the Implement stage of the end-to-end workflow.\n"
    ),
    "qa": (
        "---\n"
        "schema_version: 1\n"
        "role: qa\n"
        'description: "Quality assurance — tests and verifies work."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "Quality assurance: writes and runs tests, verifies implementation work\n"
        "against its plan/spec before merge, and holds merge authority per\n"
        "`.synlynk/policy.json`'s `merge_authority`.\n\n"
        "## Authority & Escalation\n\n"
        "Decides pass/fail on a PR unilaterally, including blocking a merge on\n"
        "missing test coverage. Escalates to whoever holds `human_authority_role`\n"
        "when a fix requires descoping or renegotiating the original plan.\n\n"
        "## Workflow Ownership\n\n"
        "Owns the CI/CD gate and Deploy stage of the end-to-end workflow.\n"
    ),
    "pm": (
        "---\n"
        "schema_version: 1\n"
        "role: pm\n"
        'description: "Program management — roadmap, brainstorming, issue triage."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "Program management: owns the roadmap, runs brainstorming sessions, and\n"
        "triages incoming issues. Runs a weekly competitive-intelligence sweep:\n"
        "tracks products serving synlynk's user segments, maintains a living\n"
        "capability/marketing-gap comparison doc, opens research tickets for\n"
        "candidate features, convenes harness-maintainer decide rounds, and\n"
        "escalates strong-fit candidates to the user as feature proposals.\n\n"
        "## Authority & Escalation\n\n"
        "Decides roadmap prioritization and issue triage unilaterally. Anything\n"
        "matching a major decision (spec approval, budget/release sign-off, charter\n"
        "changes) queues and blocks for whoever holds `human_authority_role` — pm\n"
        "never commits the human to something they haven't seen.\n\n"
        "## Workflow Ownership\n\n"
        "Owns Named Releases (final sign-off + narrative).\n"
    ),
    "architect": (
        "---\n"
        "schema_version: 1\n"
        "role: architect\n"
        'description: "System design — architecture and technical direction."\n'
        "durability: session-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "System design: writes and approves both the Spec and the Plan for\n"
        "non-trivial work, and does PR code review.\n\n"
        "## Authority & Escalation\n\n"
        "Session-only, human-in-the-loop by design. Holds merge authority alongside\n"
        "qa; non-authoring-reviewer discipline applies — architect never reviews its\n"
        "own dispatch. Escalates architectural tradeoffs with cost/scope\n"
        "implications to whoever holds `human_authority_role`.\n\n"
        "## Workflow Ownership\n\n"
        "Owns the Review and Merge stages of the end-to-end workflow.\n"
    ),
    "tpm": (
        "---\n"
        "schema_version: 1\n"
        "role: tpm\n"
        'description: "Technical program management — cross-cutting coordination, GOVERNS integration."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "Operations: turns architect's finished plan into tracked, dispatched\n"
        "tickets, does actual tasking/tracking, and reports status back to pm. Does\n"
        "not decide technical approach.\n\n"
        "## Authority & Escalation\n\n"
        "Decides ticket sequencing and dispatch scheduling unilaterally. Escalates\n"
        "to whoever holds `human_authority_role` when tracked work reveals a\n"
        "scope or architecture gap the plan didn't anticipate.\n\n"
        "## Workflow Ownership\n\n"
        "Runs a continuous tasking/tracking/reporting loop, consuming GOVERNS'\n"
        "existing lifecycle-enforcement event contract as its data source.\n"
    ),
    "designer": (
        "---\n"
        "schema_version: 1\n"
        "role: designer\n"
        'description: "Design — visual and interaction design."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "UI/UX: maintains end-user-facing interfaces, journeys, and look & feel.\n"
        "Dispatch-triggered only, routed to Agy (CSS/templates/content/subpages).\n\n"
        "## Authority & Escalation\n\n"
        "Decides visual/interaction details within an approved design direction\n"
        "unilaterally. Escalates to whoever holds `human_authority_role` before a\n"
        "change that alters user-facing information architecture.\n\n"
        "## Workflow Ownership\n\n"
        "Owns the design pass within the Implement stage for user-facing surfaces.\n"
    ),
    "marketing": (
        "---\n"
        "schema_version: 1\n"
        "role: marketing\n"
        'description: "Marketing — external communication and positioning."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "All end-user-facing comms: docs, blogs, website, plus outbound digital\n"
        "marketing. Writes every PR's blog post — dev/architect hand off a short\n"
        "technical summary at merge time, marketing turns it into the actual post.\n"
        "Owns `docs/blog/README.md`'s series template and Named Release blog\n"
        "content. Dispatch-triggered only, routed to Agy (docs/templates/content).\n\n"
        "## Authority & Escalation\n\n"
        "Decides post structure, tone, and framing unilaterally within the series\n"
        "template. Escalates to whoever holds `human_authority_role` before\n"
        "publishing anything that commits to a roadmap claim not yet approved.\n\n"
        "## Workflow Ownership\n\n"
        "Owns the Blog/Comms pass of the Named Release stage.\n"
    ),
    "synlynk-bot": (
        "---\n"
        "schema_version: 1\n"
        "role: synlynk-bot\n"
        'description: "Catch-all workspace automation identity."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        "Infra automation identity for workspace-level jobs with no natural owner\n"
        "among the seven org-chart roles (e.g. scheduled housekeeping, projection\n"
        "regeneration). Not a decision-making role.\n\n"
        "## Authority & Escalation\n\n"
        "Holds no unilateral decision authority. Any action beyond routine\n"
        "housekeeping escalates to whoever holds `human_authority_role`.\n\n"
        "## Workflow Ownership\n\n"
        "Owns no workflow stage; supports other roles' stages as infrastructure.\n"
    ),
}

ROLES = list(charter_schema.KNOWN_ROLES)


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

    except charter_schema.CharterValidationError as exc:
        print("Charter failed validation:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Updated charter for {agent_id} (revision {new_revision})")


def cmd_agent_sync_routing(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    role = next(
        (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), ""
    )
    _, revision_before = agent_store.read_charter(agent_id)
    new_revision = agent_store.sync_dispatch_routing(agent_id, role, actor="cli")
    if new_revision == revision_before:
        print(f"No task_allocation entry for role '{role}' in policy.json — nothing to sync.")
    else:
        print(f"Synced dispatch_routing for {agent_id} (role: {role}, revision {new_revision})")


def cmd_agent_disable(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    if entry.get("disabled"):
        print(f"Agent {agent_id} is already disabled.")
        return
    agent_store.set_agent_disabled(agent_id, actor="cli")
    print(f"Disabled agent {agent_id}.")
