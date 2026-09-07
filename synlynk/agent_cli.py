"""CLI handlers for `synlynk agent init/list/show/edit/disable`.

Onboarding surface layered on top of synlynk/agent_store.py's storage
functions (PR #988). See docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md.
"""
import sys
import uuid

from synlynk import agent_store
from synlynk import charter_schema


def _build_seed_charter(
    role: str,
    description: str,
    durability: str,
    instructions: str,
    authority: str,
    workflow: str,
) -> str:
    """Assemble a seed charter, sharing the YAML/section envelope across roles."""
    return (
        "---\n"
        "schema_version: 1\n"
        f"role: {role}\n"
        f'description: "{description}"\n'
        f"durability: {durability}\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\n"
        f"{instructions}\n\n"
        "## Authority & Escalation\n\n"
        f"{authority}\n\n"
        "## Workflow Ownership\n\n"
        f"{workflow}\n"
    )


SEED_CHARTERS = {
    'dev': _build_seed_charter(
        'dev',
        'Implementation — writes the code.',
        'dispatch-only',
        "Implementation work: turn an approved plan or ticket into working, tested\ncode. Dispatch-triggered only — no autonomous loop. Follow the plan's task\nbreakdown; do not redesign architecture mid-implementation.",
        "Decides implementation details (naming, file layout, test structure) within\nan approved plan unilaterally. Escalates to whoever holds\n`human_authority_role` before deviating from the plan's architecture or\nscope.",
        'Owns the Implement stage of the end-to-end workflow.',
    ),
    'qa': _build_seed_charter(
        'qa',
        'Quality assurance — tests and verifies work.',
        'durable',
        'Quality assurance: writes and runs tests, verifies implementation work\nagainst its plan/spec before merge, and evaluates merge readiness. Its\nmerge authority is limited by `.synlynk/policy.json` and is currently\ndemonstrated for the merge-restricted docs-only class.',
        'Decides pass/fail on verification unilaterally, including blocking a\nmerge on missing test coverage. May merge only classes allowed by the\npolicy gate; harder PR classes remain subject to the assigned reviewer\nand human authority. Escalates when a fix requires descoping or\nrenegotiating the original plan.',
        'Owns implementation verification, the CI/CD gate, and the\npolicy-defined merge gate of the end-to-end workflow.',
    ),
    'pm': _build_seed_charter(
        'pm',
        'Program management — roadmap, brainstorming, issue triage.',
        'durable',
        "Represents the human user in everything built: brainstorming, issuing\nwork, major decisions based on other roles' reports, keeping course.\nRuns a continuous triage loop — responds to inbound signals/reports,\nre-prioritizes the backlog, dispatches tpm on already-approved work —\nto prevent workspace dormancy when unattended.\n\nRuns a weekly competitive-intelligence sweep: tracks products serving\nsynlynk's user segments, maintains a living capability/marketing-gap comparison doc,\nopens research tickets for candidate features, convenes\nharness-maintainer decide rounds, and escalates strong-fit candidates\nto the user as feature proposals.",
        "Durable, narrowly scoped. Anything matching a major decision (spec\napproval, budget/release sign-off, charter changes) queues and blocks\nfor whoever holds `human_authority_role` — pm never commits the human\nto something they haven't seen.",
        'Owns Named Releases (final sign-off + narrative).',
    ),
    'architect': _build_seed_charter(
        'architect',
        'System design — architecture and technical direction.',
        'session-only',
        "System design: is provisioned to write and approve the Spec and Plan for\nnon-trivial work and to review technical changes. The project corpus so\nfar records those activities under Claude's pm/reviewer role rather than\na separately exercised architect identity.",
        'Session-only, human-in-the-loop by design. It does not claim independent\nmerge authority on the current corpus; review and merge authority follow\nthe explicit policy and assigned non-authoring reviewer. Architect never\nreviews its own dispatch. Escalates architectural tradeoffs with\ncost/scope implications to whoever holds `human_authority_role`.',
        'Is available for the Spec, Plan, and Review stages of the end-to-end\nworkflow; the current corpus does not show a separately exercised\narchitect identity owning those stages.',
    ),
    'tpm': _build_seed_charter(
        'tpm',
        'Technical program management — cross-cutting coordination, GOVERNS integration.',
        'durable',
        'Operations: scans ready stories without an active or completed job,\nchecks policy authority, files or maintains approval tickets for blocked\ndispatches, and dispatches work once authority is available. Reports\nstatus back to pm and does not decide technical approach.',
        "Decides ticket sequencing and dispatch scheduling within the ready-story\nsweep. Does not bypass policy or approval requirements. Escalates to\nwhoever holds `human_authority_role` when tracked work reveals a scope or\narchitecture gap the plan didn't anticipate.",
        'Runs the tasking/tracking/reporting loop through `tpm sweep`, using story\nand daemon-job state plus the approval-ticket resolution state written by\nthe lifecycle event scanner as its data source.',
    ),
    'designer': _build_seed_charter(
        'designer',
        'Design — visual and interaction design.',
        'dispatch-only',
        'UI/UX: maintains end-user-facing interfaces, journeys, and look & feel.\nDispatch-triggered only, routed to Agy (CSS/templates/content/subpages).',
        'Decides visual/interaction details within an approved design direction\nunilaterally. Escalates to whoever holds `human_authority_role` before a\nchange that alters user-facing information architecture.',
        'Owns the design pass within the Implement stage for user-facing surfaces.',
    ),
    'marketing': _build_seed_charter(
        'marketing',
        'Marketing — external communication and positioning.',
        'dispatch-only',
        "All end-user-facing comms: docs, blogs, website, plus outbound digital\nmarketing. For an explicitly dispatched comms task, turns an approved\ntechnical summary into the actual post or other content, following\n`docs/blog/README.md`'s series template and Named Release content rules.\nDispatch-triggered only, routed to Agy (docs/templates/content).",
        'Decides post structure, tone, and framing unilaterally within the series\ntemplate. Escalates to whoever holds `human_authority_role` before\npublishing anything that commits to a roadmap claim not yet approved.',
        "Owns the Blog/Comms pass of the Named Release stage. Also owns the\nstanding readership-growth outcome tracked as goal-0c4e96ff (book\nmanuscript + blog series), fed by stories the PM links to that goal —\ndispatched automatically per the TPM sweep's role-based routing (see\nsynlynk/tpm_sweep.py), not on every PR.",
    ),
    'synlynk-bot': _build_seed_charter(
        'synlynk-bot',
        'Catch-all workspace automation identity.',
        'durable',
        'Infra automation identity for workspace-level jobs with no natural owner\namong the seven org-chart roles (e.g. scheduled housekeeping, projection\nregeneration). Not a decision-making role.',
        'Holds no unilateral decision authority. Any action beyond routine\nhousekeeping escalates to whoever holds `human_authority_role`.',
        "Owns no workflow stage; supports other roles' stages as infrastructure.",
    ),
}
ROLES = list(charter_schema.KNOWN_ROLES)



def _role_slug(entry: dict, default: str = "?") -> str:
    return next(
        (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"),
        default,
    )


def _status_label(entry: dict) -> str:
    return "disabled" if entry.get("disabled") else "active"


def _agent_entry(agent_id: str) -> dict:
    return next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)



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
        if _role_slug(entry, default="") == role:
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
        role = _role_slug(entry)
        status = _status_label(entry)
        print(f"{entry['agent_id']:<38}{role:<13}{status:<11}{entry['created_at']}")


def cmd_agent_show(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = _agent_entry(agent_id)
    role = _role_slug(entry)
    status = _status_label(entry)
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
    entry = _agent_entry(agent_id)
    role = _role_slug(entry, default="")
    _, revision_before = agent_store.read_charter(agent_id)
    new_revision = agent_store.sync_dispatch_routing(agent_id, role, actor="cli")
    if new_revision == revision_before:
        print(f"No task_allocation entry for role '{role}' in policy.json — nothing to sync.")
    else:
        print(f"Synced dispatch_routing for {agent_id} (role: {role}, revision {new_revision})")


def cmd_agent_disable(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = _agent_entry(agent_id)
    if entry.get("disabled"):
        print(f"Agent {agent_id} is already disabled.")
        return
    agent_store.set_agent_disabled(agent_id, actor="cli")
    print(f"Disabled agent {agent_id}.")
