<!-- generated - source of truth is state.db -->
---
decision_id: dec-00b401f2
topic: "Unified Onboarding Journeys & Self-Updating Lifecycle Architecture: Dual-Surface CLI/TUI and Vizor, Topology Discovery (Greenfield vs Multi-Repo), 1-Click Dependency & Harness Binding, GOVERNS/Dispatch/Decide Orientation, Fleet Templates, First-Win Build Loop, and Cross-Workspace Auto-Upgrade for Dev Preview"
date: 2026-10-01
panel: [claude, codex, agy]
status: approved
---

## Topic
Unified Onboarding Journeys & Self-Updating Lifecycle Architecture: Dual-Surface CLI/TUI and Vizor, Topology Discovery (Greenfield vs Multi-Repo), 1-Click Dependency & Harness Binding, GOVERNS/Dispatch/Decide Orientation, Fleet Templates, First-Win Build Loop, and Cross-Workspace Auto-Upgrade for Dev Preview

## Panel Inputs

### claude
[model=sonnet; version=2.1.284 (Claude Code)]

**Analysis**

The topic bundles seven concerns, but they collapse into one question: what is the single source of truth for onboarding state, and which surface owns it? If CLI/TUI and Vizor each carry their own onboarding logic, they will drift. Synlynk's own record already shows this failure mode, with worktree-relative paths (#1228), stale-revert bugs (#884/#899) and shard sprawl (#1831).

**Recommendation: one engine, two skins.**

1. **Engine in the CLI, Vizor as a renderer.** Onboarding is a resumable state machine persisted in `state.db`. Steps are topology discovery, dependency and harness binding, GOVERNS/dispatch/decide orientation, fleet template, and first-win. Each step is idempotent and emits JSON, consistent with `synlynk status --json` already being Vizor's data contract. Vizor shows progress and triggers steps, and it never owns logic.

2. **Topology discovery is read-only first.** Detect greenfield, single repo or multi-repo by scanning, then propose a workspace map. This reuses `.synlynk/vizor-workspace-map.json`. Mutate only after confirmation.

3. **"1-click" binding means a probe, then a plan, then a confirm.** It does not mean silent install. Harness auth is flaky: Grok has session-expiry and 402 failures, and Agy times out. Onboarding must verify each binding with a real round-trip dispatch and show per-harness health. A green status label alone is not evidence, per #202.

4. **First-win loop comes before the explanation.** Orient the user on GOVERNS, dispatch and decide through one real, tiny, template-seeded story that is dispatched, reviewed and merged. That earns the vocabulary instead of lecturing on it. Keep it opt-in and degrade gracefully with zero agents, per the agent design principles.

5. **Auto-upgrade is the risky part, so scope it down for dev preview.** Do not auto-apply across workspaces. Use notify, then `synlynk upgrade --all` with a dry-run diff, a per-workspace migration version stamp, and rollback. Never touch a dirty worktree. Past regressions (#884 stale revert, the costs.md data loss) show silent cross-workspace writes are where trust breaks.

**Sequencing:** state machine and CLI first, then Vizor rendering, then templates, then opt-in upgrade. Sequencing the upgrade last lets it ride on proven migration stamps.

**Position:** Build a CLI-owned, resumable, idempotent onboarding state machine that Vizor renders. Make topology discovery read-only, make harness binding probe-verified and user-confirmed, and make the first-win build the orientation. For dev preview, ship upgrade as explicit, dry-run-first and rollback-capable, not automatic. Per the Brainstorm-First Policy, commit a spec in `docs/superpowers/specs/` and get Nikhil's sign-off before any dispatch.

### codex
[model=default; version=codex-cli 0.155.1]

The proposal is strategically sound, but it should be treated as a dependency-ordered product architecture, not one large feature. The unifying principle should be: one onboarding workflow engine, two surfaces. The CLI/TUI should provide fast orientation, defaults, validation, and no-browser operation; Vizor should provide topology, provenance, and exploration. Neither surface should own separate business logic.

Topology discovery must distinguish greenfield repositories from multi-repo workspaces. A single repo should feel frictionless, while a workspace registry should model multiple repos as related projections of one product. Discovery must be deterministic and read-only first, with explicit “unknown” states rather than inferred certainty. The server should resolve workspace slugs to trusted repository and state paths; clients must never submit filesystem paths.

“One-click” dependency and harness binding is valuable only if it means guided, capability-checked defaults—not opaque automation. The system should inspect dependencies, available harness capabilities, permissions, cost, and network requirements, then present a recommended binding with a reversible confirmation. Fleet templates should encode repeatable role/harness/policy bundles, but remain versioned, auditable, and overridable per repository.

GOVERNS should remain the internal lifecycle substrate, while the user-facing journey compresses it into Goal → Dispatch → Decide/Verify → Release → Sustain. The First-Win loop should prove one safe, additive change through effect-verified completion; a green process exit without a diff or verifiable artifact is not success. Cross-workspace auto-upgrade for Dev Preview should use signed, versioned templates and compatibility checks, with staged rollout, rollback, and explicit separation between standards updates and repository mutations.

My position: approve the direction, but sequence it as trusted workspace identity and routing, truthful topology discovery, read-only GOVERNS and capability binding, a shared CLI/Vizor First-Win journey, then gated fleet templates and auto-upgrade. Do not ship autonomous cross-repo writes, fuzzy lifecycle transitions, or background Graphify until a second non-synlynk workspace completes the full loop reliably.

### agy
[model=default; version=1.2.14]

**Last completed task:** `docs: checkpoint Specs 1–3 completion, archive finished stories, and update cost log (#1893)`  
**Next task from `todo.md`:** `BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform]`

---

The proposed architecture establishes an essential onboarding bridge for Dev Preview adoption by eliminating initial configuration friction across both CLI/TUI and Vizor web surfaces. To preserve architectural integrity, the dual-surface experience must be driven by a unified, headless state engine (`onboarding_state.py`) exposing identical event hooks to both surfaces, preventing UI drift and split-brain configuration states. Topology discovery should rely on deterministic, read-only heuristics—distinguishing greenfield repositories from monorepos and multi-repo workspaces prior to provisioning `.synlynk/config.json`. Furthermore, 1-click dependency and harness binding must execute preflight capability probing (`synlynk probe`) to confirm auth, sandbox network bounds, and token rate gates before agents are assigned.

Anchoring orientation around the GOVERNS framework, dispatch workflows, and fleet templates provides immediate conceptual clarity. Rather than confronting users with raw policy files, fleet templates should scaffold pre-configured agent matrices (Claude PM/Architect, Agy/Codex implementation, Grok QA) aligned to repo topology. Coupling this to a scripted "First-Win Build Loop"—an isolated, zero-risk dispatch verifying branch isolation, telemetry, and effect-verified review—secures rapid developer trust and demonstrates system safety upfront.

However, cross-workspace auto-upgrade presents the highest blast-radius risk during Dev Preview. Automated, background schema mutations across heterogeneous workspaces risk SQLite WAL lock contention and instruction drift. Auto-upgrades must be decoupled from passive daemon polling, strictly requiring explicit semantic-version pinning, preflight migration dry-runs (`synlynk migrate --dry-run`), and automated rollback snapshots.

**Position & Recommendation:** I **support approval** of the Unified Onboarding and Self-Updating Lifecycle Architecture with two core stipulations: (1) enforce dual-surface parity by driving both TUI and Vizor from a single canonical headless onboarding driver, and (2) demote cross-workspace auto-upgrades from ambient daemon execution to an explicit, opt-in prompt with rollback guarantees. Prioritizing the first-win loop and harness binding first will establish immediate developer trust.

## Synthesis
## Synthesis: Unified Onboarding & Self-Updating Lifecycle

**Where all three agree**
- **One engine, two skins.** Onboarding is a headless, resumable, idempotent state machine in the CLI, persisted in `state.db` and emitting JSON. The CLI/TUI and Vizor are renderers over it, and neither owns logic. This follows from `synlynk status --json` already being Vizor's data contract. It also avoids the drift seen in #1228, #884/#899 and #1831.
- **Topology discovery is read-only first.** It detects greenfield, single-repo or multi-repo and proposes a workspace map from `.synlynk/vizor-workspace-map.json`. It reports "unknown" rather than guessing, and mutates only after confirmation. Per Codex, the server resolves workspace slugs to paths and clients never submit filesystem paths.
- **"1-click" binding means probe, plan, confirm.** Each harness is verified with a real round-trip (`synlynk probe`) covering auth, sandbox/network and cost. Per-harness health is shown, and a green job-status label is not evidence (#202). Grok session-expiry and 402 failures and Agy timeouts make this necessary.
- **The first-win loop is the orientation.** One tiny template-seeded story is dispatched, reviewed and merged. It counts as success only with a verifiable diff or artifact, so a green exit with no effect is a failure. It is opt-in and degrades gracefully with zero agents.
- **Auto-upgrade is the highest-risk piece, so it is not automatic in Dev Preview.** It uses notify, then explicit opt-in, a dry-run diff, per-workspace migration version stamps and rollback snapshots. It never touches a dirty worktree and never runs from the passive daemon (WAL contention, instruction drift).

**Differences, resolved**
- **Sequencing.** Claude puts the state machine first. Codex puts workspace identity and routing first, then truthful discovery. Agy puts the first-win loop and harness binding first. I'll take Codex's order, since identity and routing are the foundation of the state machine. Agy's priority for the first-win loop and harness binding holds within it.
- **Fleet templates.** Codex wants them versioned, signed and overridable per repo. Agy wants them to scaffold role/harness matrices by topology. Both apply. Templates go in after the first-win loop, gated.
- **GOVERNS framing.** Codex proposes a user-facing Goal → Dispatch → Decide/Verify → Release → Sustain, with GOVERNS kept as the internal substrate. I'm adopting that.
- **Codex's gate.** No autonomous cross-repo writes, fuzzy lifecycle transitions or background Graphify until a second non-synlynk workspace completes the full loop reliably. I'm adopting it as the exit criterion for the templates and upgrade phases.

**Sequence**
1. Trusted workspace identity and slug routing (builds on Spec 1).
2. Onboarding state machine plus truthful, read-only topology discovery.
3. Probe-verified, user-confirmed harness and dependency binding, plus read-only GOVERNS/dispatch/decide orientation.
4. Shared CLI/Vizor first-win loop, effect-verified.
5. Gated, versioned fleet templates.
6. Opt-in `synlynk upgrade --all` with dry-run, migration stamps and rollback.

I haven't persisted this to a spec or devlog. Per the Brainstorm-First Policy, no dispatch happens until a spec is committed under `docs/superpowers/specs/` and you've signed off. I'm on `main`, so that spec needs a worktree and branch first.

Decision: Approve the unified onboarding architecture as one CLI-owned, resumable, idempotent state machine that both the CLI/TUI and Vizor render. Topology discovery is read-only and server-resolved. Harness binding is probe-verified and user-confirmed. The first-win loop is effect-verified and doubles as the GOVERNS/dispatch/decide orientation. Build it in the order identity and routing, discovery, binding, first-win, templates, upgrade, and hold templates and upgrade until a second non-synlynk workspace completes the full loop. For Dev Preview, cross-workspace auto-upgrade is not automatic. It ships only as an explicit opt-in command with dry-run, per-workspace version stamps and rollback, never from the daemon. Next step is a committed design spec awaiting Nikhil's sign-off, with no implementation dispatched before then.

## Decision
Decision: Approve the unified onboarding architecture as one CLI-owned, resumable, idempotent state machine that both the CLI/TUI and Vizor render. Topology discovery is read-only and server-resolved. Harness binding is probe-verified and user-confirmed. The first-win loop is effect-verified and doubles as the GOVERNS/dispatch/decide orientation. Build it in the order identity and routing, discovery, binding, first-win, templates, upgrade, and hold templates and upgrade until a second non-synlynk workspace completes the full loop. For Dev Preview, cross-workspace auto-upgrade is not automatic. It ships only as an explicit opt-in command with dry-run, per-workspace version stamps and rollback, never from the daemon. Next step is a committed design spec awaiting Nikhil's sign-off, with no implementation dispatched before then.

> Signatures: see 2026-10-01-unified-onboarding-journeys-self-updatin.json
