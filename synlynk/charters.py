"""Living charter drift detection and reviewable proposal generation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from synlynk.capability import capability_score


@dataclass
class AgentCharter:
    role: str
    harness_bindings: List[str]
    mandate: str
    autonomous_authorities: List[str]
    escalation_triggers: List[str]
    behavioral_weights: Dict[str, str]
    durability: Optional[str] = None
    wake_cycle_sop: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    sops: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    credentials: List[str] = field(default_factory=list)
    verification_contracts: List[str] = field(default_factory=list)
    description: Optional[str] = None


DEFAULT_ROLE_CHARTERS: Dict[str, dict] = {
    "architect": {
        "role": "architect",
        "harness_bindings": ["claude", "codex"],
        "mandate": "Own system design, specifications, and architectural invariants across all domains. Author rigorous specs and implementation plans triggered by approved brainstorming agendas, and submit specs for human approval.",
        "autonomous_authorities": ["draft_spec", "draft_plan", "review_architecture", "file_spec_review_issue"],
        "escalation_triggers": ["invariant_violation_detected", "budget_exceeded", "cross_repo_breaking_change", "unresolved_design_ambiguity"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "conservative"},
        "durability": "durable",
        "wake_cycle_sop": [
            "1. Agenda Intake: On trigger from a closed brainstorm agenda issue, ingest the agenda doc and all human comments/directives.",
            "2. Spec Authoring: Author the formal design specification in docs/superpowers/specs/ following the Brainstorm-First policy, including Architecture, Invariants, and Verification Contracts.",
            "3. Spec Review Filing: Commit the spec to a feature branch and file a GitHub review issue via gh issue create assigned to nikhilsoman with label spec-approval-pending, linking the spec diff.",
            "4. Plan Authoring: Monitor open spec review issues. When closed by the operator, ingest feedback and author the implementation plan in docs/superpowers/plans/.",
            "5. Plan Handoff: Commit the implementation plan and notify TPM to begin task decomposition."
        ],
    },
    "dev": {
        "role": "dev",
        "harness_bindings": ["codex", "agy", "grok"],
        "mandate": "Implement and verify approved tasks and fixes. Execute TDD in isolated leased worktrees, verify effect contracts, and submit PRs for non-author review.",
        "autonomous_authorities": ["claim_story", "implement", "test", "refactor", "create_pr"],
        "escalation_triggers": ["invariant_violation_detected", "budget_exceeded", "spec_ambiguous", "test_failure_unresolved"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "moderate"},
        "wake_cycle_sop": [
            "1. Claim Story: Claim next undispatched story from state.db where role='dev' and readiness='ready'.",
            "2. Worktree Isolation: Spawn an isolated leased worktree on a feature branch (feat/dev/<story-id>).",
            "3. TDD Build: Author failing verification test first, implement code changes, run full unit test suite.",
            "4. Effect Verification: Confirm verified effects and clean git diff.",
            "5. Pull Request: Push branch to origin and call gh pr create with test receipts, tagging QA role for review.",
            "6. Story Handoff: Update story in state.db to stage='execute' and await QA merge."
        ],
    },
    "designer": {
        "role": "designer",
        "harness_bindings": ["agy", "grok"],
        "mandate": "Design and implement UI layouts, CSS architecture, visual components, HTML templates, and asset specifications in a domain-agnostic manner.",
        "autonomous_authorities": ["claim_story", "design_tokens", "implement_styles", "review_visuals", "create_pr"],
        "escalation_triggers": ["invariant_violation_detected", "design_system_conflict", "budget_exceeded"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "moderate"},
        "wake_cycle_sop": [
            "1. Claim Story: Claim next undispatched story from state.db where role='designer' and readiness='ready'.",
            "2. Worktree Isolation: Spawn an isolated leased worktree on a feature branch (feat/designer/<story-id>).",
            "3. Style & Layout: Implement CSS/templates following modern web standards, semantic HTML, and accessibility guidelines.",
            "4. Visual Verification: Verify layout rendering, responsive breakpoints, and component tests.",
            "5. Pull Request: Push branch to origin and call gh pr create with visual receipts, tagging QA role for review."
        ],
    },
    "maintainer": {
        "role": "maintainer",
        "harness_bindings": ["claude"],
        "mandate": "Maintain repository and workspace substrate hygiene: prune merged worktrees, reconcile policy drift, triage sentinel alerts, and monitor database integrity.",
        "autonomous_authorities": ["worktree_cleanup", "policy_sync", "sentinel_triage", "release_cut"],
        "escalation_triggers": ["invariant_violation_detected", "budget_exceeded", "irreversible_action_required", "database_corruption_detected"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "conservative"},
        "durability": "durable",
        "wake_cycle_sop": [
            "1. Worktree Cleanup: Execute synlynk worktree clean --apply to remove merged/stale worktrees and prune stale tracking branches.",
            "2. Sentinel Triage: Parse .synlynk/sentinel.md via synlynk maintainer triage, archive stale alerts (>7d) to .synlynk/archive/, and clear resolved faults.",
            "3. State Integrity: Verify canonical state.db WAL checkpointing, foreign key integrity, and connection health.",
            "4. Policy Sync: Check .synlynk/policy.json and agent role charters for schema drift and notify PM if discrepancies exist."
        ],
    },
    "marketing": {
        "role": "marketing",
        "harness_bindings": ["agy", "claude"],
        "mandate": "Own release communications, milestone retrospectives, documentation narratives, and outward-facing announcements.",
        "autonomous_authorities": ["author_blog", "draft_announcement", "sync_docs"],
        "escalation_triggers": ["unverified_claims", "release_date_unaligned", "budget_exceeded"],
        "behavioral_weights": {"verbosity": "expressive", "risk_tolerance": "conservative"},
        "wake_cycle_sop": [
            "1. Release Monitoring: Track completed milestone epics and closed release PRs.",
            "2. Retrospective Drafting: Author retrospective blogs in docs/blog/ focusing on intent, technical pathways, and verified outcomes.",
            "3. Docs Synchronization: Sync documentation narratives and changelog entries with shipped capabilities."
        ],
    },
    "pm": {
        "role": "pm",
        "harness_bindings": [],
        "mandate": "Own portfolio goal alignment, ideation intake, and human governance gates. Sweep active goals, author structured brainstorming agendas, file GitHub review issues, and manage human sign-offs before implementation starts.",
        "autonomous_authorities": ["sweep_goals", "draft_brainstorm_agenda", "file_github_issue", "approve_priority", "author_story", "approve_spec"],
        "escalation_triggers": ["budget_exceeded", "cross_story_conflict", "charter_change_requested", "human_rejection_received"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "conservative"},
        "durability": "durable",
        "wake_cycle_sop": [
            "1. Goal Sweep: Run synlynk goal list to inspect all active goals in state.db.",
            "2. Spec/Plan Audit: For each active goal, verify whether an approved design spec exists in docs/superpowers/specs/ and a committed plan exists in docs/superpowers/plans/.",
            "3. Brainstorm Intake: For any active goal lacking a design spec, conduct background context research and draft a domain-agnostic brainstorming agenda in docs/brainstorm/ detailing Intent, Context, Trade-offs, and Key Decisions.",
            "4. GitHub Assignment: Call gh issue create to file an agenda issue assigned to nikhilsoman with labels brainstorm-agenda,pm-intake, linking the agenda doc and instructing operator to close issue to approve.",
            "5. Dual Surfacing: Emit a task boundary fence notice to terminal stdout and append an alert entry to .synlynk/viz-inbox.json.",
            "6. Approval Polling: Check open brainstorm agenda issues via gh issue view. When closed by operator, extract comments and trigger Architect spec authoring.",
            "7. TPM Proposal Triage: Review TPM's pending proposals and plans; approve, reprioritize, or request rework.",
            "8. Idle-Avoidance: If no pending approval or goal sweep work exists, reconcile open stories and roadmap phases against state.db before exiting."
        ],
    },
    "qa": {
        "role": "qa",
        "harness_bindings": ["codex", "agy"],
        "mandate": "Independent non-author verification and merge oracle for all repository changes. Verify correctness, enforce CI gates, conduct cross-harness PR reviews, and execute merges under sole merge authority.",
        "autonomous_authorities": ["review_pr", "verify_effects", "approve_pr", "merge_pr"],
        "escalation_triggers": ["invariant_violation_detected", "self_approval_conflict", "budget_exceeded", "ci_failure"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "conservative"},
        "durability": "durable",
        "wake_cycle_sop": [
            "1. PR Detection: Poll open PRs awaiting review in the repository.",
            "2. Non-Author Check: Confirm reviewer identity differs from PR author (and harness differs per cross_harness_review_required).",
            "3. Verification Gate: Check out PR into a dedicated review worktree and execute synlynk pr check.",
            "4. Test Execution: Run automated test suite and effect verification contracts.",
            "5. Formal Review: If green, submit formal approval via gh pr review --approve.",
            "6. Merge Execution: Under merge_authority.can_merge: ['qa'], execute gh pr merge --squash --delete-branch.",
            "7. Post-Merge Update: Mark story done in state.db and trigger maintainer sweep."
        ],
    },
    "tpm": {
        "role": "tpm",
        "harness_bindings": [],
        "mandate": "Own task decomposition, work-graph sequencing, and story dispatch tracking. Decompose approved implementation plans into atomic ready stories, assign domain-agnostic roles, and advance execution through the autonomous sweep.",
        "autonomous_authorities": ["decompose_plan", "create_story", "triage_issue", "dispatch_track"],
        "escalation_triggers": ["technical_ambiguity", "priority_ambiguity", "dispatch_blocked_twice", "plan_unapproved"],
        "behavioral_weights": {"verbosity": "concise", "risk_tolerance": "moderate"},
        "durability": "durable",
        "wake_cycle_sop": [
            "1. Plan Intake: Ingest newly committed plans in docs/superpowers/plans/ that lack tracked stories in state.db.",
            "2. Task Decomposition: Decompose markdown task checkboxes (- [ ] Task N: ...) into atomic stories in state.db via synlynk story create.",
            "3. Role Tagging: Assign role tags (dev for logic/backend/plumbing, designer for CSS/templates/components, qa for verification contracts) and mark readiness='ready'.",
            "4. Story-Goal Linkage: Link each generated story to its parent goal via synlynk goal link.",
            "5. Sweep Execution: Run synlynk tpm sweep to dispatch ready stories to designated worker harnesses without waiting for interactive input.",
            "6. Execution Tracking: Poll in-flight dispatched jobs; route blocked dependencies and escalate persistent blockers to PM."
        ],
    },
}


def _charters_dir() -> str:
    cwd = os.getcwd()
    candidate = os.path.join(cwd, ".synlynk", "charters")
    if os.path.exists(candidate):
        return candidate
    try:
        from synlynk.scan import _find_repo_root
        root = _find_repo_root(cwd)
        if root:
            root_candidate = os.path.join(root, ".synlynk", "charters")
            if os.path.exists(root_candidate):
                return root_candidate
    except Exception:
        pass
    return candidate


def validate_charter(charter: AgentCharter) -> bool:
    if not charter.role or not charter.mandate:
        return False
    if not isinstance(charter.harness_bindings, list):
        return False
    return True


def load_charter(role: str) -> AgentCharter:
    # 1. Load legacy JSON data or canonical built-in data if present as baseline fallback
    path = os.path.join(_charters_dir(), f"{role}.json")
    json_data: dict = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception:
            pass
    if not json_data and role in DEFAULT_ROLE_CHARTERS:
        json_data = dict(DEFAULT_ROLE_CHARTERS[role])

    if json_data:
        default_bindings = json_data.get("harness_bindings", [])
        default_mandate = json_data.get("mandate", f"Default operating charter for role {role}")
        default_authorities = json_data.get("autonomous_authorities", [])
        default_escalation = json_data.get("escalation_triggers", [])
        default_weights = json_data.get("behavioral_weights", {})
    else:
        default_bindings = ["claude", "codex"] if role in ("architect", "tpm") else ["codex", "agy", "grok"]
        default_mandate = f"Default operating charter for role {role}"
        default_authorities = ["draft_spec", "implement", "test"] if role != "qa" else ["review", "verify"]
        default_escalation = ["invariant_violation_detected", "budget_exceeded"]
        default_weights = {"verbosity": "concise", "risk_tolerance": "conservative"}
    default_durability = json_data.get("durability")
    default_wake_cycle = json_data.get("wake_cycle_sop", [])
    default_skills = json_data.get("skills", [])
    default_sops = json_data.get("sops", [])
    default_tools = json_data.get("tools", [])
    default_credentials = json_data.get("credentials", [])
    default_contracts = json_data.get("verification_contracts", [])
    default_description = json_data.get("description")

    # 2. Try reading from registered agent store Markdown charter
    try:
        from synlynk import agent_store, charter_schema
        entries = agent_store.list_agents()
        for entry in entries:
            role_slug = next(
                (alias["value"] for alias in entry.get("aliases", []) if alias.get("kind") == "role_slug"),
                None,
            )
            if role_slug == role and not entry.get("disabled"):
                content, _rev = agent_store.read_charter(entry["agent_id"])
                if content and content.strip():
                    frontmatter_text, _body = charter_schema.split_frontmatter(content)
                    if frontmatter_text:
                        parsed = charter_schema.parse_frontmatter(frontmatter_text)
                        mandate = parsed.get("mandate") or parsed.get("description") or default_mandate
                        wake_cycle_sop = parsed.get("wake_cycle_sop") or parsed.get("sops") or default_wake_cycle
                        autonomous_authorities = (
                            parsed["autonomous_authorities"]
                            if parsed.get("autonomous_authorities") is not None and len(parsed["autonomous_authorities"]) > 0
                            else default_authorities
                        )
                        escalation_triggers = (
                            parsed["escalation_triggers"]
                            if parsed.get("escalation_triggers") is not None and len(parsed["escalation_triggers"]) > 0
                            else default_escalation
                        )
                        behavioral_weights = (
                            parsed["behavioral_weights"]
                            if parsed.get("behavioral_weights") and isinstance(parsed.get("behavioral_weights"), dict)
                            else default_weights
                        )
                        harness_bindings = (
                            parsed["harness_bindings"]
                            if parsed.get("harness_bindings") is not None
                            else default_bindings
                        )
                        return AgentCharter(
                            role=parsed.get("role", role),
                            harness_bindings=harness_bindings,
                            mandate=mandate,
                            autonomous_authorities=autonomous_authorities,
                            escalation_triggers=escalation_triggers,
                            behavioral_weights=behavioral_weights,
                            durability=parsed.get("durability") or default_durability,
                            wake_cycle_sop=wake_cycle_sop,
                            skills=parsed.get("skills") or default_skills,
                            sops=parsed.get("sops") or default_sops,
                            tools=parsed.get("tools") or default_tools,
                            credentials=parsed.get("credentials") or default_credentials,
                            verification_contracts=parsed.get("verification_contracts") or default_contracts,
                            description=parsed.get("description") or default_description,
                        )
    except Exception:
        pass

    return AgentCharter(
        role=role,
        harness_bindings=default_bindings,
        mandate=default_mandate,
        autonomous_authorities=default_authorities,
        escalation_triggers=default_escalation,
        behavioral_weights=default_weights,
        durability=default_durability,
        wake_cycle_sop=default_wake_cycle,
        skills=default_skills,
        sops=default_sops,
        tools=default_tools,
        credentials=default_credentials,
        verification_contracts=default_contracts,
        description=default_description,
    )


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
        "maintainer": "graphify-maintainer-sweep",
    },
    "testbed": {
        "qa": "testbed-acceptance-runner",
        "verifier": "testbed-acceptance-runner",
        "architect": "testbed-topology-audit",
    },
}

ROLE_SUPERPOWERS_SKILLS: dict[str, list[str]] = {
    "dev": ["test-driven-development", "systematic-debugging"],
    "builder": ["test-driven-development", "systematic-debugging"],
    "qa": ["systematic-debugging"],
    "verifier": ["systematic-debugging"],
    "architect": ["brainstorming"],
    "pm": ["brainstorming"],
    "tpm": ["brainstorming"],
    "maintainer": ["systematic-debugging"],
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
    "maintainer",
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
                for s in ROLE_SUPERPOWERS_SKILLS.get(role, []):
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
        for s in ROLE_SUPERPOWERS_SKILLS.get(role, []):
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
