# PR #1003 — Agent-Roles-Charters Phase 1: Giving Workspace Agents a CLI

## The Goal at the End of the Previous PR

PR #993 (`chore/rename-agent-cli-to-harness`, merged 2026-08-15) freed up the `synlynk agent` verb
group by renaming synlynk's execution-backend commands from `agent` to `harness`. That PR existed
purely to clear a naming collision — it shipped no new capability itself. Its explicit purpose was
to unblock the next piece of work: a persistent, org-chart-style **Agent** concept (dev, qa, pm,
architect, tpm, designer, marketing, synlynk-bot) that is distinct from the swappable **Harness**
(Claude, Agy, Grok, Codex) that executes a dispatched task. That distinction — Agent as *who*,
Harness as *how* — is documented in `docs/glossary-agent-vs-harness.md`, itself the product of
brainstorming that preceded #993.

The underlying storage layer for this — `synlynk/agent_store.py`, with agent registration, charter
storage with revision provenance, and per-agent config projections — had already shipped in PR #988.
What was missing was any way for a human or another agent to actually *use* it: no CLI to create an
agent, no way to dispatch work under an agent's identity, no way for `dispatch_agent()` to resolve
"the dev agent" into a concrete harness + role + GitHub identity.

## Strategic Shift in This PR

None — this PR is exactly the Phase 1 scope that #993 was clearing space for. The one refinement
made mid-execution was a **plan-design fix**, not a strategic pivot: the original implementation
plan specified a test (`test_cmd_agent_edit_stale_revision_exits_1`) asserting that `cmd_agent_edit`
detects a stale charter revision across two sequential CLI invocations. On inspection, no correct
implementation of `cmd_agent_edit` could ever fail that test — it reads `parent_revision` fresh via
`read_charter()` immediately before writing, so there's no cross-invocation window for staleness to
occur. The fix was to monkeypatch `agent_store.propose_charter_revision` to raise
`RevisionConflictError` directly, exercising the CLI's exception-handling path in isolation rather
than chasing an unachievable race condition. This is exactly the kind of gap the writing-plans
skill's self-review pass is supposed to catch, and didn't — worth remembering for future plans that
touch revision-conflict handling.

## What This PR Shipped

**CLI onboarding surface** (`synlynk/agent_cli.py`, wired into `synlynk/cli.py`):

```
synlynk agent init <role>      # one agent per org-chart role; seeds charter + capability_grants: {}
synlynk agent list              # table of all registered agents, active/disabled
synlynk agent show <id|alias>   # resolves by full id or role-slug alias
synlynk agent edit <id> <file>  # propose a charter revision; exits 1 on stale revision
synlynk agent disable <id>      # idempotent disable
```

Each `agent init` writes a registry entry (`agent_store.register_agent`) and a
`.synlynk/agents/<id>.yaml` projection carrying agent id, workspace id, role, and an
`overrides.capability_grants: {}` map — a placeholder for the capability-scoping work planned for a
later phase. The charter itself is not duplicated into this projection; it stays in the agent store's
own revision-tracked storage, read via `agent_store.read_charter()`.

**Dispatch integration** (`synlynk/dispatch.py`): `dispatch_agent()` gained an optional `agent_id`
parameter. When supplied, it resolves the agent's org-chart role (raising `ValueError` if the agent
is unregistered or disabled — a fail-closed check before any subprocess spawns), maps that role into
the existing baseline-role vocabulary via a new `_ORG_ROLE_TO_BASELINE_ROLE` table:

```python
_ORG_ROLE_TO_BASELINE_ROLE = {
    "dev": "builder", "qa": "verifier", "architect": "architect",
    "tpm": "architect", "pm": "architect", "designer": "builder",
    "marketing": "builder", "synlynk-bot": "builder",
}
```

and falls back to a new `_harness_for_org_role()` selector only when the existing `story_id`-based
`_best_agent_for_story` auto-selection doesn't produce a pick — for **harness auto-selection**,
`story_id` still wins when both are present, and `agent_id` is additive rather than a replacement
for the existing routing path. GitHub identity/token resolution is a separate lookup with the
opposite precedence: it reads `role = agent_role or _role_for_story(story_id) or "dev"`, so an
explicit `agent_id` overrides `story_id` for *which role's `gh` token gets used*, even though it
doesn't override `story_id` for *which harness gets picked*.

**CLI flag**: `synlynk dispatch --as-agent <id_or_alias>` resolves the agent at the CLI layer before
calling `dispatch_agent()`, and makes the harness positional argument optional so `--as-agent` alone
can trigger auto-selection.

**Test approach**: TDD throughout, executed via `subagent-driven-development` — each of the plan's 8
tasks was dispatched to Codex individually (`synlynk dispatch codex --task "..." --force-agent
--context-mode full`), reviewed inline against the plan and against a fresh `pytest` run before the
next task began. Final state: 109 tests across `test_agent_cli.py` + `test_dispatch.py`, full suite
at 2019 passed / 2 skipped / 0 failed.

## Brainstorm Visuals Used

None — this phase built directly on the already-approved `2026-08-09-synlynk-agent-roles-charters-design.md`
spec and its Phase 1 sub-spec (`2026-08-16-agent-roles-phase1-cli-design.md`); no new visual
brainstorming was needed for CLI plumbing work.

## What This Achieved on the Path to Autonomy

This is the first point where a *workspace agent identity* — not just a harness selection — can
drive a real dispatch. Previously, "who is doing this work" and "what tool is executing it" were the
same variable (`args.agent` meant harness). Now they're separable: `synlynk dispatch codex --as-agent
dev` says "the dev agent's work, executed by Codex" — which is the precondition for later phases
where an agent's charter, capability grants, and memory namespace actually constrain or inform what
gets dispatched on its behalf, rather than every dispatch being anonymous.

## The Goal at the End of This PR

Phase 1 (CLI onboarding + dispatch integration) is done. The `agent_id` field is resolved and used
for routing/identity but is not yet persisted on `daemon_jobs` for attribution/grouping (flagged as
a non-blocking follow-up in code review — filed as a gap, not silently dropped), and `cmd_agent_edit`
still unconditionally resets `capability_grants: {}` on every edit rather than preserving
non-empty grants — both are real footguns for the next phase, where capability grants are expected
to become load-bearing rather than a placeholder. That's the shape of Phase 2: making
`capability_grants` mean something, and making dispatched jobs traceable back to the agent identity
that requested them, not just the harness that ran them.
