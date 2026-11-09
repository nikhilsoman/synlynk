# Vizor Agent Role Management — Design

**Date:** 2026-11-09
**Status:** Brainstormed, approved by Nikhil, decide-panel-gated, pending plan + build
**Motivating incident:** gh:#5178-#5181 (X6M-Work governance gap — PRs #5172-#5174 merged on a fabricated non-author review, with no role charged to catch it)
**Decide panel:** `project-docs/decisions/2026-11-09-decide-panel-agent-role-management-agent...` (claude/agy/codex/grok) — approved Agent Studio as foundational, gated on §3a's four conditions, rejected tool-named roles (§4a)

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

### 3a. Governance gates (from the 2026-11-09 decide panel)

The panel (claude/agy/codex/grok) approved Agent Studio as foundational but made these four conditions a precondition of Phase 1, not a later hardening pass — reasoning that an unaudited free-text charter editor reproduces the same failure shape as the motivating incident (an unattributed, unverified change to who's trusted to do what):

1. **Audited charter writes.** Every charter edit (mandate/authorities/triggers, Enforced or Guidance) is a versioned write with a diff and an attributable actor — no silent overwrite of `.synlynk/charters/<role>.json`. This is the direct governance analogue of the review-provenance gap the X6M incident exposed, applied to charter edits themselves.
2. **`capability_ratings` wiring from day one.** Every role activated through the FTUE wizard or promoted via Phase 1 (`maintainer`, `secops`, `infra/devops`) gets a `capability_ratings` task-type bucket immediately, not a hand-authored assignment added later. Agent Studio must not recreate the kind of unmeasured routing lock the 2026-10-04 Empirical Capability Assessment Policy is actively reassessing.
3. **Role lifecycle includes deprecation/merge, not just creation.** The FTUE wizard (§5) and registry need a symmetric "retire or merge this role" path — including GitHub App identity revocation — so the taxonomy can be pruned as usage data lands, not just grown.
4. **Trust/dedup review gates remote and upstream flows.** The upstream GitHub feature-request flow (§4) and the Capability Registry's remote-connector ingestion (§4, Zapier MCP/Composio/Smithery) do not ship until a dedup-against-open-issues check and a third-party trust/egress review exist. The panel cited gh:#2139's stale-closure lesson as the precedent for why "file it and assume it's handled" isn't sufficient, and remote manifests are the registry's largest untrusted-input surface.

These gates are reflected in the phase sequencing in §6.

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

When no existing capability (native, local, or remote) covers a "Guidance only" authority, the editor offers **"File feature request on github.com/nikhilsoman/synlynk →"**: pre-filled issue titled `[Charter Intent] <authority> for <role>`, labeled `feature-proposal` + `pm-intake`, body auto-populated with role/mandate context and workspace id, filed against synlynk core (not the user's fork) so PM can triage and dedupe (existing `duplicate` label) across every workspace's requests. synlynk is Apache-2.0 — forking and extending locally is already fully permitted and requires no license accommodation; "contributing back" is a process convention, not a license obligation, so a local fork that builds a new native hook uses the same flow as a pull request instead of an issue. **Gated per §3a.4** — this flow does not ship until the dedup/trust-review gate exists.

### 4a. Tool/driver-specific roles — rejected

The decide panel explicitly rejected naming agent roles after specific tools (e.g. a "Google Stitch UI/UX driver agent" as its own role). Reasoning: a role is an *accountability* boundary (who may merge, veto, escalate) and a tool binding is an *execution* detail (how the work gets done) — collapsing them into one vendor-named primitive re-introduces the same per-harness/per-tool hard-coding the 2026-10-04 Empirical Capability Assessment Policy just suspended for harness routing.

Tool/driver integrations like Stitch are modeled as `harness_bindings` + Capability Registry entries attached to the existing stable functional roles (`designer`, `dev`) — not as new role primitives. Tool binding itself is delegated to the harness and MCP discovery mechanics (a tool's own manifest/documentation), not hard-coded per-vendor inside synlynk. synlynk's layer stops at the generic function-scoped roles plus the governance hooks harnesses don't reliably self-enforce (review provenance, secret scanning, worktree cleanup, release cuts, identity) — it does not grow a hand-maintained per-vendor agent catalog.

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

Re-sequenced per the decide panel: §3a's governance gates move into the earliest phases they bear on, rather than trailing as hardening work; the two phases with the largest untrusted-input/trust-review surface (remote registry ingest, upstream issue-filing) are explicitly held until their gate lands. Each phase is independently shippable; #1-#2 alone resolves the motivating incident.

1. **Taxonomy activation + audit log + capability_ratings wiring** — register `maintainer`, `secops`, `infra/devops` as real dispatchable agents with GitHub App identities; wire `external_contribution_triage` into maintainer's charter; every charter write (this phase's and all later ones) goes through a versioned, attributable diff log (§3a.1); every activated role gets a `capability_ratings` task-type bucket at activation, not after the fact (§3a.2).
2. **BAU charter editor** — prompt-box fields with Enforced/Guidance tagging, replacing the dead button in `roles.py`; writes go through Phase 1's audit log.
3. **Role lifecycle: deprecation/merge** — symmetric "retire or merge this role" path (§3a.3), including GitHub App identity revocation; ships alongside the editor since both operate on the same charter-write path.
4. **FTUE wizard** — 5-step new-role provisioning, built on #2/#3's field and lifecycle components.
5. **Native hook catalog** — browsable, `description`/`purpose`/`scope` required per entry; wires into #2's "Attach existing hook" action.
6. **Capability Registry, local source** — installed-MCP/Skill picker scoped per `harness_bindings`. No external trust surface (harness-local), so not gated.
7. **HELD until the §3a.4 trust/dedup gate exists:** upstream feature-request flow ("File on github.com/nikhilsoman/synlynk") and Capability Registry remote-source ingestion (Zapier MCP/Composio/Smithery-compatible manifests). The dedup-against-open-issues check and third-party trust/egress review are a prerequisite design-and-build item in their own right, not a checkbox inside this phase.

## 7. Explicitly out of scope (filed as follow-ons, not folded in)

Per the decide panel, two adjacent questions it raised are follow-on stories under BS-15/gh:#2126, not scope creep into this spec:

- **Publishing a synlynk MCP server** (dispatch, pr check, GOVERNS, cost, charter read) into harness/plugin marketplaces as a second distribution surface alongside `install.sh`/pipx. The panel's view: this weakens (doesn't eliminate) the "home harness essential" premise in gh:#2126, since synlynk's control plane becomes callable from any MCP-capable client — but the host-local daemon/worktrees/`state.db` still need somewhere to run. Worth its own design pass against gh:#2126's five open questions.
- **The tool-binding-vs-role boundary** (§4a) generalized beyond this spec's taxonomy — i.e., a reusable principle for any future "should X be a role or a capability" question, not just Stitch.

## 8. Open items for the implementation plan

- Exact `charter_schema.py` changes needed to support free-text authorities/triggers with an Enforced/Guidance classification (currently a closed enum).
- Where the Capability Registry's manifest store lives (new `state.db` table vs. a `.synlynk/capabilities/` file tree) — follows the same durability pattern as charters.
- Whether `designer`/`tpm`'s idle-activity status gets addressed in this work or deferred to the next Empirical Capability Assessment Policy review cycle (recommend: defer — it's a capability-measurement question, not a role-management-tooling gap).
- `synlynk pr check`'s new secops-gate condition (which PR shapes trigger it) needs its own small design pass during planning, not fully specified here.
- Concrete design for the charter audit log (§3a.1): storage (state.db table vs. append-only file), what counts as "attributable actor" for a Vizor-UI-initiated edit (session identity vs. GitHub login), and retention.
- Concrete design for the §3a.4 trust/dedup gate itself (dedup matching strategy against open issues; what "third-party trust review" checks for a remote connector manifest before it's ingestable) — needed before Phase 7 can start.
