# synlynk Agent Roles & Charters — Design

**Date:** 2026-08-09
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman

## 1. Motivation

Three previously-separate mental models of "who does work in synlynk" had drifted out of sync:

1. **5 identity-roles** (dev, qa, pm, architect, synlynk-bot) provisioned with GitHub App identities via issue #859 — named ahead of any charter definition, as infrastructure-first groundwork.
2. **4 tool-agents** (Claude, Agy, Grok, Codex) with a capability-based task allocation table in CLAUDE.md (implement/test/css/templates/content/subpages → Agy; implement/test/canvas/js/infra → Grok; implement/test/refactor/cli-plumbing → Codex; pm/review/deploy/brainstorm → Claude).
3. **1 shipped durable agent** — the Support Engineer (`synlynk/support_engineer.py`), plus GOVERNS lifecycle-enforcement primitives (PR #817).

This design reconciles all three into one coherent 8-role org chart, defines each role's charter and durability, establishes a dispatch policy (with live calibration) mapping roles to tool-agent backends, and lays out how a project's work flows end-to-end through the roles from spec to release.

## 2. The 8-Role Org Chart

| Role | Charter | Durability |
|---|---|---|
| **pm** | Represents the human user in everything built: brainstorming, issuing work, major decisions based on other roles' reports, keeping course. Owns Named Releases (final sign-off + narrative). | **Durable, narrowly scoped.** Runs a continuous triage loop — responds to inbound signals/reports, re-prioritizes the backlog, dispatches tpm on already-approved work — to prevent workspace dormancy when unattended. Anything matching a "major decision" (spec approval, budget/release sign-off, charter changes) queues and blocks for the human. pm never commits the human to something they haven't seen. |
| **architect** | Technical custodian of build quality, design, and performance — "everything technical." Owns the full technical design surface: writes/approves both the Spec and the Plan. Does PR code review and holds merge authority. | Session-only, human-in-the-loop by design. |
| **tpm** | Operations role: turns architect's finished plan into tracked, dispatched tickets; does actual tasking/tracking; reports status back to pm. Does not decide technical approach. | **Durable.** Continuous tasking/tracking/reporting loop. Consumes GOVERNS' existing lifecycle-enforcement event contract (PR #817) as its data source rather than building independent tracking — see §4. Lightweight periodic reconciliation is kept only as a correctness backstop, never the primary source of truth. |
| **dev** | Implementation — writes the code. | Dispatch-triggered only, no autonomous loop. |
| **designer** | UI/UX specialist: maintains end-user-facing interfaces, journeys, and look & feel. | Dispatch-triggered only. |
| **qa** | Test coverage, overall quality & performance, CI/CD, IaC, and deployments. | **Durable.** The shipped Support Engineer (`synlynk/support_engineer.py`) is qa's always-on presence. |
| **marketing** | All end-user-facing comms: docs, blogs, website, plus outbound digital marketing. Writes every PR's blog post — dev/architect hand off a short technical summary at merge time, marketing turns it into the actual post. Owns `docs/blog/README.md`'s series template and Named Release blog content. | Dispatch-triggered only. |
| **synlynk-bot** | *Not a role.* Shared automation identity used by durable roles' (tpm's, qa's/Support Engineer's) scheduled/cron-triggered writes and GOVERNS enforcement comments. | Infra identity, always-on but not a role. |

All 8 roles have provisioned GitHub App identities as of this session (see §6).

## 3. Role → Tool-Agent Dispatch Policy + Live Calibration

### 3.1 Base mapping

Role → tool-agent mapping is **flexible**: each role owns the *what* and accountability; tool-agents (Claude, Agy, Grok, Codex) are swappable *how*-execution backends selected per-task by capability fit. Today's capability-based routing table becomes each role's dispatch policy:

| Role | Typical dispatch targets |
|---|---|
| pm | Claude only — represents the human, not delegated out |
| architect | Claude only — technical judgment + review/merge authority, not delegated out |
| tpm | Claude (durable loop) |
| dev | Codex (refactor/CLI-plumbing), Grok (canvas/JS/infra/data-structures), Agy (general implementation) |
| designer | Agy (CSS/templates/content/subpages) |
| qa | Codex (test/refactor), Grok (infra/CI-CD), Support Engineer (durable) |
| marketing | Agy (docs/templates/content) |

### 3.2 GitHub-write routing (supersedes #426)

Issue #426's "route all GitHub-write tasks to Grok by default" policy is **retired**, effective this design. #426 bundled two separate constraints:

- **Execution capability**: Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design — Codex structurally cannot perform `gh` writes. This constraint is unchanged and still applies.
- **Identity correctness**: before issue #859, no harness had a role-scoped token, so any harness's GitHub write could silently fall through to the shared personal `nikhilsoman` keyring identity (documented as issue #569's failure mode). Routing everything through Grok was a stopgap to make that failure predictable, not because Grok was uniquely suited to GitHub writes.

Issue #859 closed the identity gap structurally: writes now attribute to the role's own GitHub App bot (verified live — a smoke-test dispatch's comment was authored by `synlynk-synlynk-pm[bot]`) regardless of which harness executes the call. With identity bound to the role's token rather than the executing harness, forcing all GitHub-write tasks through Grok no longer serves a purpose.

**New policy**: GitHub-write tasks route by the same per-role capability-fit policy as any other task (§3.1), with **Codex excluded only on execution-capability grounds**. A one-time spot-check (via `synlynk pr check`) should confirm App-bot attribution on the first GitHub write from each newly-eligible role/harness pairing under real dispatch load.

Whether Codex's sandbox constraint itself is fixable (a narrow, auditable egress exception) is tracked separately as issue **#865** — not a blocking dependency of this policy change.

Decision confirmed via `synlynk decide` panel (claude, agy, codex — unanimous), recorded at `project-docs/decisions/2026-08-09-should-synlynk-retire-its-standing-githu.md`.

### 3.3 Live calibration (holdback)

The base mapping in §3.1 is a default, not a permanent hard-wire. A stratified holdback layer continuously tests whether it's still correct, so synlynk can detect harness/model degradation or improvement over time rather than routing to yesterday's best-fit agent forever:

- **Sampling rates** per `(role, task-type)` cell: 2% for expensive/high-risk/`--requires-gh-write` tasks, 5% default, 10% for cheap/reversible work — occasionally routing to a normally-non-preferred agent or a different model/effort-level within the same harness.
- **Confidence-adaptive**: a cell starts at the *upper* end of its sampling band until it has ≥10 observations in a rolling 30-day window, then decays toward the lower end once it accumulates 50+ consistent observations.
- **Shared capability ledger**: both `capability_sweep.py`'s existing periodic synthetic sweeps and live holdback traffic write into one ledger keyed by `(role, task-type, SFIA skill)`. Sweep (synthetic, reproducible, SFIA-tagged) and holdback (real task distribution, real cost/rate-limit conditions) are complementary, not competing — sweep is not retired.
- **Feedback loop**: re-ranking proposals require ≥5–10 same-direction observations and ship as a versioned, canaried policy overlay with a rollback threshold and audit trail, surfaced to Claude/pm for approval — never silently auto-applied. Exception: fail-closed safety demotion on repeated near-zero challenger scores applies immediately and automatically (mirrors the `--requires-gh-write` fail-closed precedent from #569).
- **Staying current**: tpm's durable loop drives three triggers — volume-based reconciliation every ~100–200 completed dispatches, sweep's existing independent cadence, event-triggered re-sweep on a human-flagged new model/harness version release, plus a daily staleness check that force-sweeps any ledger cell untouched for 30+ days.

Decision confirmed via `synlynk decide` panel (claude, agy, codex — unanimous), recorded at `project-docs/decisions/2026-08-09-synlynk-s-role-to-tool-agent-dispatch-po.md`.

## 4. GOVERNS ↔ tpm Integration

tpm's durable tasking/tracking/reporting loop consumes GOVERNS' existing lifecycle-enforcement event contract (PR #817) as its data source, rather than building a second, independent tracking mechanism. This matches synlynk's own established single-writer/multi-reader state pattern (e.g. `telemetry.json` feeding `costs.md`, sentinel checks, and `synlynk status --json`) and avoids the drift failure mode already documented in repo memory #202 ("never trust `synlynk jobs` status alone").

GOVERNS remains the sole enforcement authority over lifecycle validity; tpm builds a derived read model on top for scheduling, assignment, and reporting. Before tpm depends on it in production, the GOVERNS event contract should be verified sufficiently expressive: typed payloads, task/story/goal linkage, and completion/failure/quarantine states. tpm keeps lightweight periodic reconciliation strictly as a correctness backstop, never as its primary source of truth.

Decision confirmed via `synlynk decide` panel (claude, agy, codex — unanimous), recorded at `project-docs/decisions/2026-08-09-should-tpm-s-durable-tasking-tracking-re.md`.

## 5. End-to-End Project Workflow

| Stage | Owner | Detail |
|---|---|---|
| Brainstorm / Spec | pm (kicks off) + architect (writes/approves) | Brainstorm-First Policy unchanged — spec must be committed to `docs/superpowers/specs/` and signed off before any plan work starts |
| Plan | architect | Spec and Plan are both design-time technical artifacts; architect owns the full technical design surface |
| Task breakdown / tracking | tpm | Turns architect's finished plan into tracked, dispatched tickets; does not decide technical approach (§4) |
| Build | dev / designer, dispatch-triggered | Routed via §3's dispatch policy + live holdback calibration. GitHub-write tasks route per §3.2 (capability-fit, Codex excluded) |
| Review | architect | PR code review for build quality/correctness against the plan; non-authoring-reviewer discipline still applies — architect never reviews its own dispatch |
| Merge | architect | Merge authority sits with architect following successful review |
| CI/CD gate + Deploy | qa | Owns pipeline health and deploy mechanics per qa's explicit charter |
| Named Release cut | pm | pm's durable triage loop queues release sign-off as a "major decision" — blocks for human even though pm is durable (§2's narrow-scope rule) |
| Blog post / docs | marketing | dev/architect leave a technical summary in the PR description at merge time; marketing turns it into `docs/blog/NN-prN-*.md` and owns the series template |
| Ongoing tasking/tracking/reporting | tpm (durable) → pm (durable, narrow) | Continuous loop even when the human is away — routine work keeps moving, major decisions still wait for the human |

## 6. Identity Provisioning Status

All 8 roles have provisioned GitHub App identities as of 2026-08-09, verified via `synlynk identity list` and `synlynk doctor` (`identity_roles` and `identity_file_perms` both green):

| Role | app_slug |
|---|---|
| dev | synlynk-synlynk-dev |
| qa | synlynk-synlynk-qa |
| pm | synlynk-synlynk-pm |
| architect | synlynk-synlynk-architect |
| synlynk-bot | synlynk-synlynk-synlynk-bot |
| tpm | synlynk-synlynk-tpm |
| designer | synlynk-synlynk-designer |
| marketing | synlynk-synlynk-marketing |

dev/qa/pm/architect/synlynk-bot were provisioned under issue #859 (closed). tpm/designer/marketing were provisioned in this session, in scope for this design per explicit decision to provision "while the manual flow is warm."

## 7. SFIA Capability Taxonomy — Scope

The SFIA-based capability taxonomy (`synlynk/taxonomy_standards.py` `SFIA_CODES`, `synlynk/capability_sweep.py`) is incorporated **narrowly**, per unanimous `synlynk decide` panel recommendation:

- **In scope now**: SFIA as role-charter vocabulary (grounds §2's charter prose in a standard vocabulary — cheap, already exists in-repo, immediately auditable) and as an annotation dimension for `capability_sweep.py`'s existing empirical calibration (§3.3's shared capability ledger is keyed in part by SFIA skill — this normalizes calibration's reporting scale, it does not replace calibration's own logic).
- **Explicitly deferred** (see §8): SFIA-driven workspace role scoping, SFIA-driven tool/service inference, and SFIA-driven cross-workspace/Tokq portability. SFIA is tool-agnostic and non-generative — none of these need synlynk-authored mapping/overlay logic that doesn't exist yet.

Decision recorded at `project-docs/decisions/2026-08-09-should-the-sfia-based-capability-taxonom.md`.

## 8. Deferred / Out-of-Scope Items

Every item raised during this design that isn't resolved above is tracked here, not silently dropped:

| Item | Status | Why deferred |
|---|---|---|
| SFIA-driven workspace role scoping | Deferred, future enhancement | Needs a synlynk-authored mapping layer that doesn't exist yet (§7) |
| SFIA-driven tool/service inference | Deferred, future enhancement | Same gap — SFIA doesn't define tooling conventions (§7) |
| SFIA-driven cross-workspace/Tokq portability | Deferred, future enhancement | Speculative scope — revisit once Tokq's cross-repo work actually exists to be portable *to* (§7) |
| `agent_slots` missing `grok` in `.synlynk/config.json` | Filed as **#863** | Pre-existing config bug, orthogonal to this redesign |
| Manifest callback 404 (`synlynk.com/github-apps/<project>/<role>/webhook`) | Filed as **#864** | Pre-existing GitHub App provisioning-flow UX gap, not introduced by this design |
| Codex sandbox `api.github.com` egress block | Filed as **#865** | Distinct security boundary from identity attribution; needs its own security/runtime design review, not a blocking dependency of §3.2 |

## 9. Out of Scope for This Spec

- Implementing the dispatch-policy code changes (§3), the GOVERNS↔tpm consumer (§4), or the holdback calibration mechanism (§3.3) — this document defines the design; implementation is a separate plan per the Design → Plan → Build sequence.
- Updating CLAUDE.md's Capability-Based Task Allocation table to reflect §3's corrected policy — a follow-up docs task once this spec is approved.
- Fixing any of the three deferred issues in §8.
