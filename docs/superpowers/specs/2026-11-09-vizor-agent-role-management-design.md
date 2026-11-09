# Vizor Agent Role Management — Design

**Date:** 2026-11-09
**Status:** Brainstormed, approved by Nikhil, pending plan + build
**Motivating incident:** gh:#5178-#5181 (X6M-Work governance gap — PRs #5172-#5174 merged on a fabricated non-author review, with no role charged to catch it)

## 1. Problem

synlynk's workspace agents are a core piece of its autonomy story, but agent role management today is split across four layers that don't talk to each other:

- **Registry** (`agent list`/`agent init`): 8 roles (`dev, qa, pm, architect, tpm, designer, marketing, synlynk-bot`), all bulk-provisioned at the same instant (2026-10-02T07:31:17Z) — convenient at bootstrap, never revisited.
- **Charter** (`.synlynk/charters/<role>.json`): mandate, `autonomous_authorities`, `escalation_triggers`, `behavioral_weights`, optional `wake_cycle_sop`/`harness_bindings`.
- **GitHub App identity**: per-role credentials for dispatched GH writes.
- **CLI command surface**: e.g. `synlynk maintainer triage/probe/sweep`, wired to a scheduler hook.

`maintainer` is the clearest symptom: it has a full charter (`autonomous_authorities: [worktree_cleanup, policy_sync, sentinel_triage, release_cut]`, `escalation_triggers` including `invariant_violation_detected`) and a scheduled deterministic automation (`_run_maintainer_triage_pass` → `triage_sentinel_alerts`, run every `autonomy_pass_interval_seconds`), but it is **absent from the agent registry and has no GitHub App identity** — so it cannot be `synlynk dispatch`-ed, and its judgment-requiring authorities (`worktree_cleanup`, `release_cut`, and the newly-identified need for external-contribution triage) were never built. Nothing in the charter maps to a code hook that would have caught a fabricated review.

Vizor's existing "Workspace Agent Roles & Onboarding Studio" (`synlynk/viz/roles.py`) already renders charter cards with an "Edit Charter" button — but it's a no-op, and the canvas's own drawer says "Role provisioning stays on the CLI (`synlynk identity`)." There is no UI path today to add, edit, or retire a role's charter, let alone see what a charter edit actually changes about synlynk's behavior.

## 2. Target role taxonomy

Grounded in standard engineering-org functional conventions (not synlynk-invented categories), per the decision to prioritize common practice over bespoke patterns at this stage:

| Role | Function family | Mandate | Key authorities | Escalation triggers | Change vs. today |
|---|---|---|---|---|---|
| pm | Delivery | Backlog intake, priority, GOVERNS linkage | — | — | unchanged |
| architect | Delivery | Spec/design gate | — | spec/GOVERNS gaps | unchanged |
| tpm | Delivery | Cross-role scheduling, release *coordination* | unblock dependencies, release scheduling | cross-team conflict | expanded scope (was near-idle) |
| dev | Delivery | Implementation | implement, open PR | — | unchanged |
| qa | Quality & Trust | Review, merge gate | approve/block merge, **review-provenance verification** | review-provenance mismatch | new explicit authority — closes the X6M-Work gap directly |
| secops | Quality & Trust (NEW) | Security posture: secrets, credentials, access, vulnerable deps | `secret_scan`, `credential_audit`, `dependency_vuln_triage`, `access_review`; owns its own policy/tooling; can veto any lane regardless of other approvals | `credential_leak_detected`, `critical_vulnerability_found`, `unauthorized_gh_write_detected` (always terminal — never auto-remediated) | new role |
| maintainer | Platform | Repo/workspace hygiene, release process, invariant enforcement | `worktree_cleanup`, `policy_sync`, `sentinel_triage`, `release_cut`, **+ `external_contribution_triage`** (new) | `invariant_violation_detected`, `budget_exceeded`, `irreversible_action_required`, `database_corruption_detected` | **promoted**: register as a real dispatchable agent with a GitHub App identity |
| infra/devops | Platform (NEW) | CI pipeline health, daemon/scheduler runtime health, deploy execution | `ci_pipeline_health`, `daemon_ops`, `deploy_execution`, `environment_provisioning` | `pipeline_down`, `daemon_crashloop`, `deploy_failure` | new role |
| designer | Experience | UI/content design | — | — | unchanged (flagged for idle-status re-check under the Empirical Capability Assessment Policy, not redefined) |
| marketing | Experience | External comms, release notes | — | — | unchanged |
| synlynk-bot | — | CI/system identity | — | — | **reclassified**: documented explicitly as a non-agentic identity, not a charter-bearing role |

Boundary notes:
- **maintainer** owns release *process* (versioning, changelog, GitHub Release) and hygiene/invariant enforcement.
- **infra/devops** owns runtime/pipeline health and deploy *execution*.
- **secops** has cross-cutting veto authority with its own dedicated policy and tooling, not merely a review step riding on others' tools.

Escalation flow: `qa`/`infra-devops`/`dev`/`tpm` escalate to `maintainer` on their respective triggers; `maintainer` and `secops` are the two roles whose unresolved escalations terminate at a human/pm, never auto-remediated.

## 3. Charter field model: prompts with enforcement tagging

Each charter field (mandate, `autonomous_authorities`, `escalation_triggers`) is authored as free text in a prompt-style input, pre-filled with a recommended default pulled from the role's template — not a fixed checklist pulled rigidly from an enum. This resolves the tension between "charters should drive platform behavior" (so synlynk's code needs to interpret the field) and "don't force users into a closed vocabulary" (so typing a novel idea must never fail):

- **⚡ Enforced** — the typed string matches a known identifier with a real code hook behind it (e.g. `secret_scan` → `run_secret_scanning`, `review-provenance mismatch` → a `synlynk pr check` gate). Shown with the hook it's wired to.
- **◌ Guidance only** — no code hook exists yet. Accepted immediately, surfaced to the agent as context/behavioral guidance (via its `wake_cycle_sop`/prompt assembly), and flagged as a candidate for a future code hook.

Mandate stays free text throughout — it's always guidance, shaping how the agent reasons, never a code gate.

## 4. Capability Registry (unifies code hooks, local MCPs/Skills, and third-party connectors)

A single data model with three ingestion sources, each producing the same manifest shape so the "browse and attach" UI in the charter editor works identically regardless of source:

```json
{
  "capability_id": "secret-scan-mcp-github",
  "name": "run_secret_scanning",
  "source": "native | local_harness | remote_connector",
  "description": "...",
  "purpose": "...",
  "scope": "...",
  "auth": { "type": "...", "...": "..." },
  "enforced_hook": "synlynk.cli:cmd_pr_check#secops_gate | null",
  "harness_compat": ["claude", "codex", "agy", "grok"] | "any"
}
```

- **Native** — synlynk's own code hooks: `pr_check_gate`, `dispatch_routing_rule`, `scheduler_autonomy_stage`, `sentinel_pattern_handler`, `run_secret_scanning`, etc. Each requires a canonical `description`/`purpose`/`scope` — no bare function names in the catalog.
- **Local-harness** — MCP servers and Skills already installed in whichever harness will execute the agent, scoped by `harness_bindings` (a Claude-only MCP must not appear as attachable when the role's binding is Codex-only).
- **Remote connector** — third-party-published manifests satisfying the same shape. Confirmed via research: **Zapier MCP** (~10-40k app actions depending on source) and **Composio**/**Smithery** (MCP tool registries) already exist and are directly consumable as MCP servers — synlynk does not need to build a Zapier/IFTTT equivalent, only ingest manifests from them. ([LangGraph Studio: The first agent IDE](https://blog.langchain.com/langgraph-studio-the-first-agent-ide), [CrewAI Agents concepts](https://docs.crewai.com/en/concepts/agents.md) — used as external validation, not a UI template to copy: CrewAI's free-text `role`/`goal`/`backstory` + named-`tools`-list split independently converges with the prompt-box + attach-from-registry split designed here.)

When no existing capability (native, local, or remote) covers a "Guidance only" authority, the editor offers **"File feature request on github.com/nikhilsoman/synlynk →"**: pre-filled issue titled `[Charter Intent] <authority> for <role>`, labeled `feature-proposal` + `pm-intake`, body auto-populated with role/mandate context and workspace id, filed against synlynk core (not the user's fork) so PM can triage and dedupe (existing `duplicate` label) across every workspace's requests. synlynk is Apache-2.0 — forking and extending locally is already fully permitted and requires no license accommodation; "contributing back" is a process convention, not a license obligation, so a local fork that builds a new native hook uses the same flow as a pull request instead of an issue.

## 5. Vizor UI: FTUE and BAU

**BAU — charter editor** (replaces the dead "Edit Charter" button in `synlynk/viz/roles.py`):
- Opens a drawer/panel with the prompt-box fields from §3, each showing its Enforced/Guidance tag.
- "Attach existing capability" action opens the Capability Registry browser (§4) scoped to the role's `harness_bindings`.
- A review step shows the concrete behavior change before saving (e.g., "qa gains a new `pr check` gate requiring secops sign-off when a PR touches secrets/deps").

**FTUE — new role wizard** (5 steps, replacing "stays on the CLI" for role provisioning):
1. Pick function family (Delivery / Quality & Trust / Platform / Experience) → template suggestions from §2's taxonomy, or "blank charter."
2. Customize fields (§3's prompt boxes, pre-filled from template).
3. Escalation & cross-lane veto scope.
4. Provision identity: writes `.synlynk/charters/<role>.json`, validates against `charter_schema.py`'s role enum, checks for name collisions, provisions the GitHub App identity.
5. Review & activate: explicit "what this changes in synlynk's actual behavior" summary (dispatch routing eligibility, new `pr check` gates, scheduler participation or lack thereof) before the role goes live.

## 6. Phased build plan

Each phase is independently shippable; #1-#2 alone resolves the motivating incident.

1. **Taxonomy activation** — register `maintainer`, `secops`, `infra/devops` as real dispatchable agents with GitHub App identities; wire `external_contribution_triage` into maintainer's charter.
2. **BAU charter editor** — prompt-box fields with Enforced/Guidance tagging, replacing the dead button in `roles.py`.
3. **FTUE wizard** — 5-step new-role provisioning, built on #2's field components.
4. **Native hook catalog** — browsable, `description`/`purpose`/`scope` required per entry; wires into #2's "Attach existing hook" action.
5. **Upstream feature-request flow** — "File on github.com/nikhilsoman/synlynk" action for Guidance-only items.
6. **Capability Registry, local source** — installed-MCP/Skill picker scoped per `harness_bindings`.
7. **Capability Registry, remote source** — third-party connector manifest ingestion (Zapier MCP/Composio/Smithery-compatible), same manifest shape as #6.

## 7. Open items for the implementation plan

- Exact `charter_schema.py` changes needed to support free-text authorities/triggers with an Enforced/Guidance classification (currently a closed enum).
- Where the Capability Registry's manifest store lives (new `state.db` table vs. a `.synlynk/capabilities/` file tree) — follows the same durability pattern as charters.
- Whether `designer`/`tpm`'s idle-activity status gets addressed in this work or deferred to the next Empirical Capability Assessment Policy review cycle (recommend: defer — it's a capability-measurement question, not a role-management-tooling gap).
- `synlynk pr check`'s new secops-gate condition (which PR shapes trigger it) needs its own small design pass during planning, not fully specified here.
