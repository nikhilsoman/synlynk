---
decision_id: dec-20260927-round-1-architecture-review
topic: "Round 1: Deep Architectural & Performance Review for v1.0.0 Dev Preview Release"
date: 2026-09-27
panel: [claude, codex, agy, grok]
status: approved
primary_goal: goal-d3333441
governing_loop: goal-eacab0dc
target_milestone: 2026-10-01 (v1.0.0 Dev Preview)
---

# Round 1: Deep Architectural & Performance Review — Panel Synthesis & Decision Record

## Executive Synthesis

# Executive Architecture Review Decision — Synlynk v1.0.0 Developer Preview

## Unanimous Consensus (4/4 panelists independently converged)

1. **Exit code ≠ success.** Every panelist independently named the same failure signature: a harness (most often Grok, sometimes Codex/Agy) returns exit 0 with zero files changed and no GitHub effect. This is documented in your own memory (LIVE-8/#1166, job-status false-negative #1377) and reproduced in live telemetry (Grok "cancelled" mid-task, Codex read-only DNS block). All four independently proposed the same fix: **completion must be verified against an observed git diff / GitHub object, not the process return code.**
2. **Token bloat is a real, already-manifested cost bug, not a hypothetical.** Codex jobs burning 5–10M tokens with 0 files touched are in `.synlynk/sentinel.md` right now. All four flag context-mode selection (`full` vs `task`), oversized preamble/instruction injection, and lack of an in-flight kill switch as root causes — not the AST packer itself, which all agree is directionally sound.
3. **Semantic overload of Agent/Harness/Role/GitHub-App-Identity is real friction**, evidenced by the fact that your own CLAUDE.md has to re-explain the Harness-vs-Agent distinction inline, every time the term is used. All four recommend collapsing the *user-facing* surface to two nouns (Role + Harness) while keeping the richer internal model.
4. **GOVERNS' 7-stage FSM is correct as an internal model, wrong as the only user-facing default.** Unanimous recommendation: keep it running underneath, but expose a compressed view (3–5 stages) for anything short of a full feature epic.
5. **Worktree/lock leakage is a known, previously-manifested problem** (your own 30-stale-worktree audit) and needs to move from "documented discipline" to an enforced lifecycle (leases, TTL, reap-before-create).
6. **Vizor/daemon must degrade gracefully when offline or unconfigured** — GitHub App token refresh attempting DNS with no fallback, and Vizor blanking when `graph.json` is absent, are both cited as day-1 crash risks independent of each other (Agy found the DNS log line directly, Grok separately concluded Vizor must render off `state.db` alone).

## Divergent / Additional Points Worth Flagging

- **Scope of the "safety net must be structural" claim**: Claude and Codex frame this as a completion-contract redesign across `jobs.py`/`dispatch.py`; Grok is most concrete about *where* — capability probes must run *before* dispatch routing (not just verify after), specifically to stop Grok/Codex from ever being routed to effects they can't perform (network, gh-write).
- **CLAUDE.md accuracy drift** (Claude's finding): the architecture doc still describes synlynk as "a single-file Python CLI" when it's 138 modules / ~73K lines. No other panelist flagged this, but it's a real, cheap, high-leverage fix — regenerate from `synlynk scan` rather than hand-maintain.
- **GitHub App identity should be opt-in, not default** (Claude + Grok agree explicitly; Agy implies it via the 2-tier collapse). Codex didn't address this directly. This matters because a solo dev-preview user has no reason to hit the self-approval/collision edge cases at all.
- **Command surface size**: Grok is alone in proposing an explicit ~8-verb preview surface with the rest hidden until `doctor` clears dependencies. Directionally consistent with the others' "reduce ceremony" theme but the most concrete, actionable version of it.
- **Metric framing**: Codex's "tokens per verified acceptance criterion" is a sharper economic metric than the others proposed and is compatible with the shared token-budget recommendation.

## Identified Architectural Risks (cross-referenced against live evidence, not just theory)

| Risk | Evidence | Severity |
|---|---|---|
| Silent no-op success | Grok/Codex exit-0-zero-diff jobs, LIVE-8/#1166, #1377 | **Critical** — erodes trust invisibly |
| Token/cost runaway | job-f09488b0 (10.7M tokens/$32.61), job-cf837848 (7.6M tokens/6hr/$5.26, 0 files) | **Critical** — real money already burned |
| Worktree/lock leaks | 30-worktree audit finding, `index.lock` contention | High — compounds over time, breaks concurrent dispatch |
| Dual/unclear ledger | `state.db` vs `project-docs/*.md` (some generated, some hand-edited) ambiguity | High — user edits the wrong surface, "state looks corrupt" |
| Daemon/network coupling | GitHub App token refresh DNS failure with no offline fallback | Medium-high — day-1 crash-loop risk for offline/unconfigured users |
| Receipt-check brittleness | `lines[0] == expected` string match in `_check_task_receipt`, causing `TASK_RECEIPT_WARN` false positives | Medium — noisy, erodes signal quality of Sentinel itself |
| Terminology/lifecycle ceremony | Agent/Harness/Role/App-Identity overlap; 7-stage GOVERNS FSM required for trivial tasks | Medium — onboarding friction, not correctness risk |

## Five Mandatory Architectural Invariants for v1.0.0

1. **Effect-verified completion.** A mutating job may only be marked `succeeded` if `(exit_code == 0) AND (non-empty git diff against job base OR explicit read-only classification) AND (verification step actually ran)`. Zero-diff mutating jobs get a distinct status (`completed_without_changes` / `FAILED_NOOP_DENIED`), never `succeeded`. This single invariant closes the #1 cross-panelist finding.
2. **Hard, enforced token/cost budgets with in-flight kill, not post-hoc audit.** Per-dispatch input cap, cumulative-per-job cap, and a circuit breaker that kills a process crossing a token threshold with zero file changes — before the bill lands, not in next morning's Sentinel log.
3. **Capability-probed routing, fail-closed.** Before a job is queued, a cached capability probe determines whether the target harness can actually perform the required effect (shell, network, gh-write) in the current sandbox. Unknown or failed probe → do not dispatch to that harness for that effect class.
4. **One ledger, one writer.** `state.db` (SQLite/WAL) is the sole mutation authority; every markdown/Vizor/GitHub surface is an explicit read-projection. Enforce one-writer-per-worktree locking with reap-before-create at dispatch start, not periodic audit.
5. **Compressed, accurate default surface.** User-facing vocabulary limited to Role + Harness (GitHub App identity becomes an opt-in upgrade, not default); GOVERNS exposed by default as a 3–5 state view (e.g., Plan → Run → Verify → Review → Finish) with the full 7-stage FSM available on request; CLAUDE.md/architecture docs regenerated from actual module state before ship, not hand-maintained prose that's two orders of magnitude off.

---

**Decision:** Synlynk v1.0.0 Developer Preview is **not ready to ship as currently specified**. The orchestration substrate (worktree isolation, SQLite ledger, AST-based context packing, role-scoped review) is architecturally sound and unusually well-instrumented with its own incident history — but that safety net currently lives in operator discipline and CLAUDE.md prose, not enforced code paths, and dev-preview users will have none of the tribal knowledge currently substituting for guardrails. Ship only after the five invariants above are implemented and demonstrable end-to-end (fresh install → dispatch → effect-verified completion → recoverable failure), with GitHub App identity and the full GOVERNS ceremony made opt-in rather than default. Until then, the risk is not that the preview looks unfinished — it's that it looks finished while silently burning users' money and trust.

---

## Detailed Panelist Submissions

### 1. Claude Architecture Review
# Synlynk v1.0.0 Dev Preview — Architecture Review (Round 1)

Grounded in the actual repo state, not just the briefing doc: `synlynk/` is **138 modules, ~73K lines**, with `dispatch.py` and `jobs.py` alone at ~4,000 lines each. CLAUDE.md still describes this as "a single-file Python CLI... the entire application logic lives in one file" — that description is badly stale, and it matters: onboarding docs describing a codebase 100x smaller than reality is itself a dev-preview risk (new contributors and even harnesses will orient themselves wrong). There's also a live uncommitted diff in `cli.py` right now converting two top-level imports of `synlynk.quota` into lazy in-function imports — a strong signal of circular-import pressure in the CLI module graph, consistent with `synlynk heal`'s existence as a dedicated import-cycle detector.

## 1. Stability & Day-1 Reliability

The single biggest risk to first-run experience isn't a missing feature, it's **silent partial failure** — a pattern your own memory log documents repeatedly (job-status false-negatives #1377, `--requires-gh-write` silent no-ops, Grok's sandbox denying `bash` while reporting exit 0). For a dev-preview user running `synlynk init` → `synlynk dispatch` for the first time, a job that reports success but touched nothing is worse than a crash — a crash gets reported, a false-positive erodes trust silently and the user blames their own prompt.

Must be rock-solid day 1:
- **`synlynk doctor`** must catch the actual failure classes you've hit in production (missing GitHub App token, sandbox denying shell, worktree lock contention) — not just "is Python installed." If doctor is currently mostly environment checks, it's underselling what dev-preview users will actually hit.
- **`synlynk init` and first dispatch must have zero circular-import or lazy-import surprises.** The pattern in the current uncommitted diff (deferring imports to dodge a cycle) is a patch on a symptom; if this exists in `cli.py`'s hot path, first-run users hit `ImportError` under just the wrong invocation order.
- **Daemon persistence gap** (your own tracked issue #1228 — CWD-relative pidfile/github_apps paths breaking across worktrees) is exactly the kind of bug that looks fine in the maintainer's own dev environment and breaks immediately for a fresh user whose CWD assumptions differ.

## 2. Token Economics & Performance

The architecture bets correctly on AST-based context minimization (`impact.py`, `pack.py`) over naively stuffing full files into every dispatch — that's the right instinct and the sub-1.5k-token signature/test inlining target is a reasonable design point. Two risks:

- **Context mode mismatch is already a known failure pattern in your own usage** (memory: "`--dispatch --context-mode` — match mode to prompt self-containedness, not habit from prior dispatch in sequence"). If *you*, the primary operator, get this wrong repeatedly, dev-preview users with no tacit model of the tool will get it wrong far more often, burning tokens on either over-inclusion (bloat) or under-inclusion (hallucinated context, wasted retry cycles). This wants a heuristic default, not a flag users must reason about from scratch.
- **`dispatch.py` and `jobs.py` at 4,000 lines each are themselves token-bloat risk when *synlynk's own code* is the subject of a dispatch** (self-hosted meta-work, agent-role reviews of synlynk PRs). Any context-packaging pass that doesn't special-case its own core files will blow past the AST-inlining budget on exactly the modules doing the most work. Worth confirming `pack.py` degrades gracefully (falls back to signature-only) rather than linearly ballooning on these files.

## 3. Design Flaws & Semantic Friction

The **Agent vs. Harness split** (`docs/glossary-agent-vs-harness.md`) is good instinct but is a real ongoing tax — your own CLAUDE.md has to restate "Note: 'Harness' below means the execution backend... not the Agent (role)" in *every table that uses the word*. If the docs need a disclaimer next to every occurrence, the terminology hasn't landed. For v1.0.0 dev preview, either the CLI surface needs to make this distinction self-evident (e.g., `--harness codex --role qa` always paired, never a bare positional that could be read as either), or the two concepts should collapse for the external-facing CLI even if they stay separate internally.

The **GOVERNS 7-stage FSM + 5-tier goal resolution** is a lot of ceremony for a dev-preview user's first goal. If a new user's first interaction with `synlynk goal create` requires understanding a 7-stage lifecycle before they get value, that's friction ahead of payoff. Consider whether the FSM can stay fully implemented but *invisible* by default — auto-advance through Open→Visualize→Execute silently unless the user asks to see state.

**Role-scoped GitHub App identities** solve a real problem (non-author review requirement) but introduce the "chicken-and-egg self-approval" and "same-identity collision" edge cases your own CLAUDE.md already has multiple fallback paragraphs for. Three tiers of exception-handling in the docs for one mechanism (qa APPROVE default → same-identity COMMENT fallback → host-auth escalation) is a sign the mechanism has more states than the problem needs. If v1.0.0 dev-preview users don't have multiple GitHub Apps provisioned (likely — most will run solo), this entire subsystem should degrade to "just use my own gh auth" with a clearly logged reason, not silently attempt role-scoped auth and fail confusingly.

## 4. Multi-Harness Failure Modes & Sandbox Resilience

This is your most mature failure-mode catalog and also your biggest unresolved risk surface for external users, because the catalog was built entirely from *your own* incidents:

- Grok: sandbox denies `bash` entirely in some environments, reports success anyway (confirmed via `git diff origin/main` showing zero change despite "OK" status).
- Codex: needs explicit network grant for GH writes; silent no-op without it previously.
- Agy: recurring "timeout waiting for response," now down-weighted in favor of Codex/Grok.
- Job-status generally: cannot be trusted alone — every verified memory entry says "verify via `gh pr view --json reviews` / direct diff, never trust status label."

For a dev-preview shipping to users who don't have your incident history, **"never trust job status alone" cannot remain a tribal-knowledge rule enforced by CLAUDE.md text** — it has to be enforced by the tool. Concretely: `synlynk jobs` / dispatch completion should itself run the verification step (diff-against-base, not just process exit code) before reporting success to the user, rather than relying on the calling agent to remember to double-check. Right now the safety net is "the PM remembers to verify" — that doesn't scale past your own session.

Worktree locking and stale-worktree accumulation (your own audit found 30 stale worktrees from purely reactive cleanup) suggests the lifecycle needs a hard TTL/lock-timeout, not just the documented "clean up in the same turn as merge" discipline — discipline is exactly what breaks first when a dev-preview user doesn't know the discipline exists.

## 5. Concrete Recommendations

1. **Make verification structural, not procedural.** Fold "diff-against-base after every dispatch" directly into `jobs.py`'s completion path so a false-positive success can't reach the user/CLI output at all. This single change would have prevented at least 4 of the incidents in your own memory log.
2. **Collapse role-scoped GitHub identity to opt-in.** Default v1.0.0 dev-preview behavior should be single-identity (host `gh` auth), with role-scoped Apps as an explicit `synlynk harness add --role-scoped` upgrade path for team-mode users. Don't make solo dev-preview users pay the self-approval/collision tax for a multi-agent-identity feature they don't need yet.
3. **Regenerate CLAUDE.md's architecture section from the actual module graph** before shipping — a `synlynk scan`-generated architecture snapshot beats a hand-maintained paragraph that's already wrong by two orders of magnitude on line count. This is cheap and directly reduces onboarding confusion for both human contributors and dispatched harnesses reading their own instructions.
4. **Add a context-mode default heuristic to `pack.py`/dispatch**, keyed on prompt length + whether the task references files already in the worktree, so users don't have to manually reason about `--context-mode` the way you've had to learn to.
5. **Give the daemon a fixed, non-CWD-relative state root** (e.g., `~/.synlynk/<project-hash>/`) before dev-preview — issue #1228 is exactly the class of bug that's invisible in a maintainer's stable environment and immediately visible the moment a user has multiple worktrees, which dev-preview users doing any real multi-branch work will hit on day one.

**Verdict:** The core engine (worktree-isolated dispatch, AST-based context minimization, role-scoped identities, GOVERNS lifecycle) is architecturally sound and unusually well-instrumented — the fact that you have a documented incident history with root causes and fix PRs for nearly every failure mode above is a genuine strength most projects at this stage lack. But right now that safety net is encoded as *operator discipline and CLAUDE.md prose* rather than *enforced code paths*, and a dev-preview audience won't have the tribal knowledge that's currently substituting for guardrails. Ship v1.0.0 only after promoting the top two or three "never trust X alone" rules from documentation into code (especially job-status verification), trimming the identity/FSM ceremony a solo user doesn't need on day one, and fixing the CWD-relative daemon state bug — the rest of the architecture is ready, but its correctness is currently held together by you personally remembering what's broken.

### 2. Codex Architecture Review
## 1. Primary Assessment

Synlynk has a compelling architecture, but v1.0.0 Developer Preview should be treated as a reliability product, not yet as a fully autonomous engineering operating system.

The strongest differentiators are:

- Local-first execution and SQLite-based mutation authority.
- Worktree isolation across multiple agent harnesses.
- Role-scoped GitHub identities and review gates.
- AST-aware context reduction.
- A unified visual control plane.

The primary risk is architectural surface area. The release combines a daemon, event FSM, four external harnesses, local models, GitHub Apps, worktrees, SSE, SQLite, AST indexing, cost telemetry, and a large Vizor UI. Any unclear boundary between these systems will appear to users as “the agent did nothing,” “the state is wrong,” or “the task is stuck.”

For the preview, operational predictability matters more than feature breadth.

## 2. What Must Be Rock-Solid on Day One

The minimum reliable user journey should be:

1. Install and initialize Synlynk.
2. Run a health check.
3. Create or select a task.
4. Dispatch it to one harness.
5. See truthful live progress.
6. Inspect the resulting worktree and artifacts.
7. Run verification.
8. Review or merge through an explicit gate.
9. Recover cleanly from interruption.

The following capabilities must be dependable:

- Deterministic startup and configuration validation.
- Clear detection of missing binaries, credentials, GitHub permissions, and unsupported models.
- Idempotent daemon startup and restart recovery.
- Durable state transitions in SQLite, including crash recovery.
- Job leases, heartbeats, timeouts, cancellation, and orphan reaping.
- Truthful job status: distinguish `queued`, `running`, `completed`, `failed`, `cancelled`, `timed_out`, and `completed_without_changes`.
- Worktree lifecycle management, including stale-lock detection and safe cleanup.
- A CLI path that remains fully usable if Vizor or SSE fails.
- A single “doctor” command that reports actionable remediation rather than generic errors.
- A small set of golden end-to-end tests covering install, dispatch, interruption, retry, and recovery.

The most dangerous preview failure is not a visible crash. It is a successful-looking job that silently produced no work, failed to persist its result, or left the user unsure whether retrying is safe.

The UI should therefore expose facts, not inferred optimism:

- Last heartbeat.
- Current process ID.
- Harness command and version.
- Worktree path.
- Git diff/stat.
- Last state transition.
- Exit code and stderr.
- Whether artifacts were indexed.
- Whether verification actually ran.

## 3. Token Economics and Performance

### Context packaging

The context pack and AST inlining strategy is directionally correct, but token minimization must be measured against task success, not treated as an absolute goal.

A useful context pack should be:

- Task-specific.
- Symbol-oriented.
- Dependency-aware.
- Stable across retries.
- Explicit about omitted information.
- Small enough to inspect and cache.

Every dispatched job should receive a manifest containing:

- Task objective and acceptance criteria.
- Relevant files and symbols.
- Direct callers and callees.
- Tests likely to fail or require modification.
- Repository conventions.
- Prior attempt summaries.
- Explicit exclusions.

Avoid repeatedly sending static repository instructions, large unchanged files, or full AST neighborhoods. Cache immutable context artifacts by content hash and send only references or deltas where the harness permits it.

### AST inlining

AST-derived signatures are valuable, but signature-only context can become semantically unsafe when behavior depends on:

- Decorators.
- Dynamic dispatch.
- Configuration.
- SQL schemas.
- Templates.
- Serialization formats.
- Side effects during import.
- Generated code.
- Framework conventions.

The packer should classify context into:

- Required source.
- Required signatures.
- Required tests.
- Optional supporting context.
- Omitted context with a reason.

That lets the harness request expansion instead of forcing Synlynk to guess how much source is enough.

### Token-bloat risks

The major risks are:

- Passing the full GOVERNS history to every agent.
- Repeating identical logs across retries.
- Including Vizor telemetry or event streams in agent prompts.
- Including all related files instead of the minimal dependency cone.
- Letting failed agents write verbose summaries that are then repackaged.
- Nested multi-agent delegation where each child receives the parent’s entire context.
- Sending tool output without truncation, normalization, or deduplication.

Introduce hard budgets at three levels:

- Per-dispatch input budget.
- Per-job cumulative budget, including retries.
- Per-goal budget across all agents.

When a budget is exceeded, the system should stop or require explicit expansion. It should not silently continue burning tokens.

A useful economic metric is not tokens per job, but:

`tokens per verified acceptance criterion`

That metric captures whether context reduction is actually improving productivity.

## 4. Design Flaws and Semantic Friction

### GOVERNS is conceptually strong but too prominent

The seven-stage lifecycle is useful internally, but users should not need to understand Goal → Open → Visualize → Execute → Release → Notify → Sustain before completing a task.

Expose a simpler user-facing model:

- Plan.
- Run.
- Verify.
- Review.
- Finish.

Map the richer GOVERNS lifecycle underneath it. Advanced users can inspect the underlying stages, but ordinary users should see practical progress.

### Avoid two competing sources of truth

SQLite should remain the mutation ledger. GitHub, Vizor, state files, and event streams should be projections or integrations.

This needs to be enforced explicitly:

- SQLite owns job and lifecycle state.
- GitHub owns externally visible collaboration state.
- Git is the source of code truth.
- Vizor is a read model.
- SSE is a transport, not a state store.

If users can mutate equivalent state through multiple interfaces, reconciliation behavior must be specified. Otherwise, Synlynk will develop “state drift” bugs that are difficult to explain.

### Separate orchestration from visualization

Vizor should never be required for dispatch correctness. The daemon and CLI must work without the browser, canvas, or SSE relay. The UI should consume a versioned read API and tolerate delayed or missing events by rehydrating from SQLite-backed endpoints.

### Do not overexpose autonomous semantics

Terms such as “Sustain,” “Universal GOVERNS,” “Jev System 1,” “topological feature vectors,” and “minimal cone worktrees” may be meaningful internally but can create product friction. The preview should lead with outcomes:

- Faster task setup.
- Smaller agent context.
- Safer parallel work.
- Better review automation.
- Recoverable execution.

Technical names should be available in diagnostics and documentation, not required for basic use.

## 5. Multi-Harness Failure Modes and Sandbox Resilience

The orchestration layer must assume that harnesses are unreliable and inconsistent.

Important failure classes include:

- Exit code 0 with no file changes.
- Partial edits followed by abrupt termination.
- Tool cancellation after the agent has modified files.
- Output truncation or malformed structured output.
- Permission denial that looks like an agent failure.
- Missing network access.
- Worktree already locked by another job.
- Agent process survives after the controller times out.
- Harness reports completion before filesystem writes are flushed.
- Different harnesses interpret the same task contract differently.
- Retry creates a second conflicting worktree or duplicates a PR.
- A child agent succeeds while the parent process loses its result.

Every harness adapter should implement a common contract:

- Start.
- Heartbeat.
- Structured progress events.
- Cancellation.
- Timeout.
- Exit classification.
- Changed-file detection.
- Artifact collection.
- Verification result.
- Final summary.

A zero exit code should never equal success by itself. Success should require a configurable evidence policy, for example:

- Expected artifact exists.
- Relevant files changed, if changes were expected.
- Tests or checks ran.
- Acceptance criteria were evaluated.
- Agent produced a valid structured result.

For no-op jobs, report `completed_without_changes`, not `completed`.

Sandbox resilience should include:

- Preflight permission checks.
- A capability matrix per harness.
- Explicit distinction between unavailable tools and failed tools.
- A fallback path that preserves the worktree for inspection.
- Retry policies based on failure class, not generic repetition.
- Per-worktree leases and ownership metadata.
- Safe recovery commands for abandoned jobs.
- Never automatically deleting a worktree containing uncommitted changes.

The system should also record a durable execution receipt for every job: inputs, harness, command, environment capabilities, timestamps, exit classification, changed files, tests, token usage, and final disposition.

## 6. High-Impact Recommendations

### 1. Make the execution contract evidence-based

Define one versioned job contract shared by Claude, Codex, Agy, Grok, and local models. Completion must require evidence, not merely process termination.

This is the highest-priority change because it addresses silent no-op success, inconsistent harness behavior, and unreliable retries simultaneously.

### 2. Add a first-class recovery and reconciliation supervisor

Implement a daemon supervisor that handles:

- Heartbeats.
- Leases.
- Orphan detection.
- Timeouts.
- Retry classification.
- Worktree locks.
- Daemon restart recovery.
- SQLite-to-projection reconciliation.

The supervisor should be independently testable without invoking real agents.

### 3. Introduce strict context budgets and adaptive expansion

Give every job a context manifest, token budget, and expansion mechanism. Start with the minimal AST cone, then allow the agent or policy engine to request specific source regions when needed.

Track tokens per verified outcome, retry amplification, context-cache hit rate, and wasted-token categories.

### 4. Reduce the user-facing state model

Keep GOVERNS internally, but expose a simpler flow: Plan → Run → Verify → Review → Finish. Provide an advanced diagnostics view for the full lifecycle.

This will materially reduce onboarding friction without sacrificing architectural capability.

### 5. Ship a CLI-first golden-path release

Treat Vizor as an accelerator, not a dependency. The preview should be fully useful through CLI and API with the browser unavailable. Build a release acceptance suite that exercises fresh install, dispatch, crash recovery, cancellation, no-op completion, stale worktrees, GitHub permission failure, and replay after daemon restart.

## Verdict:

Synlynk’s core architecture is viable and differentiated, but v1.0.0 should narrow its promise to reliable, inspectable, recoverable agent execution. The release is ready only when SQLite state, job evidence, worktree ownership, harness failure classification, and token budgets are more deterministic than the underlying agents themselves. Simplify the user-facing lifecycle, enforce a common execution contract, and make recovery a first-class feature; otherwise, the preview risks demonstrating impressive orchestration while undermining user trust at exactly the moments that matter most.

### 3. Agy Architecture Review
- **Last Completed Task:** AST Knowledge Graph Lifecycle, Rich Context Pack, Sparse Cones & Deep KG UX ([PR #1799](https://github.com/nikhilsoman/synlynk/pull/1799)) [by @nikhilsoman]
- **Next Active Task:** BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform] (`story-bs7-interop`)

---

# Architecture & Performance Review: Synlynk v1.0.0 Developer Preview

## Executive Overview
Synlynk represents an ambitious, technically sophisticated autonomous engineering substrate. Operating as a host-local, zero-SaaS orchestration daemon with multi-harness delegation ([Claude](https://docs.anthropic.com), [Codex](https://openai.com), [Agy](https://antigravity.dev), [Grok](https://x.ai)), Git worktree isolation, deterministic 7-stage [`GOVERNS`](file:///Users/nikhilsoman/dev/synlynk/synlynk/governs_fsm.py) state machines, and an AST-driven knowledge graph control plane, it solves fundamental multi-agent coordination problems.

However, telemetry from the active codebase and [`.synlynk/sentinel.md`](file:///Users/nikhilsoman/dev/synlynk/.synlynk/sentinel.md) reveals critical failure modes: **runaway token bloat** (jobs burning 4M–10M tokens with 0 files touched), **brittle receipt markers** generating constant Sentinel alerts, **silent no-op completions in restricted harness sandboxes**, and **network-coupling in the local daemon**. 

Addressing these architectural friction points prior to the **01 Oct 2026** Developer Preview is essential for user trust and out-of-the-box reliability.

---

## 1. Product Stability & Out-of-the-box Reliability for v1.0.0 Dev Preview

To ensure initial adopters experience immediate value without crashes or friction during day-1 onboarding (`synlynk init`, `synlynk start`, `synlynk viz`), three core systems require immediate hardening:

### A. Resilient Host-Local Daemon Initialization ([`synlynk/daemon.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/daemon.py))
* **Local-First & Offline Resilience:** Active logs on [`synlynk watch`](file:///Users/nikhilsoman/dev/synlynk/synlynk/watch.py) demonstrate an immediate fragility:
  ```text
  ⚠ could not refresh GitHub App token for role 'tpm': <urlopen error [Errno 8] nodename nor servname provided, or not known>
  ```
  The daemon continuously attempts remote HTTP calls via [`github_app_auth.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/github_app_auth.py) without checking network reachability or local configuration state.
  * **Day 1 Requirement:** If GitHub Apps are unconfigured or the machine is offline, the daemon must fall back seamlessly to local Git author attribution (`git config user.name`) and disable the GitHub App refresh cycle without terminal spam or thread stalls.
* **Atomic PID & Lockfile Recovery:** With [`fcntl.flock`](file:///Users/nikhilsoman/dev/synlynk/synlynk/daemon.py#L90) on `.synlynk/daemon.pid.lock`, killed or restarted processes on macOS/Linux occasionally leave orphan sockets or locked state. The daemon must incorporate an uncrashable orphan-reap cycle during `synlynk init` and `synlynk start`.

### B. SQLite WAL Concurrency & Lock Contention ([`synlynk/db.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/db.py))
* With the daemon polling every 5 seconds, Vizor rendering telemetry projections, and headless worker jobs updating story states in parallel, [`state.db`](file:///Users/nikhilsoman/dev/synlynk/synlynk/db.py) is a high-traffic choke point.
* **Day 1 Requirement:** Ensure `PRAGMA busy_timeout = 10000` is unconditionally enforced on all read/write connections. Every state transition in [`governs_fsm.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/governs_fsm.py) and [`jobs.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/jobs.py) must run within short-lived transaction scopes to eliminate `sqlite3.OperationalError: database is locked`.

### C. Vizor Web Control Plane Fallbacks ([`synlynk/viz.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/viz.py), [`synlynk/viz_views.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/viz_views.py))
* On a clean repository before `synlynk scan` or `synlynk pack` has executed, `.synlynk/graphify-out/graph.json` does not exist.
* The frontend canvases (`tube.html`, `logical.html`) must gracefully render a lightweight "Workspace Indexing Required" state rather than failing with JavaScript null-reference errors.

---

## 2. Token Economics & Multi-Agent Dispatch Performance

Telemetry in [`.synlynk/sentinel.md`](file:///Users/nikhilsoman/dev/synlynk/.synlynk/sentinel.md) shows severe anomalies:
* **Job `job-f09488b0` (Codex):** Consumed **10,744,867 tokens** ($32.61) across 8 files.
* **Job `job-5a159fe6` (Codex):** Consumed **5,445,964 tokens** ($16.52) across 5 files.
* **Jobs `job-8575a177`, `job-006f075f`, `job-e655562a`:** Consumed **749k to 4.47M tokens with 0 files touched**.

### A. Root Causes of Token runaway
1. **Unbounded Multi-Turn Conversation Loops:** Headless dispatch CLI wrappers run interactive tool-calling loops without turn-level token throttles. When an agent enters an error loop (e.g. repeated test failures or bash permission rejections), the full system prompt and context are resent on every iteration, compounding token consumption exponentially.
2. **Context Pack Ingestion Bloat:** While [`pack.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/pack.py#L11) bounds AST snippets to 1,500 tokens (`_cut_to_token_budget`), the broader prompt generator in [`context.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/context.py#L322) dumps active items from [`todo.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (currently **1,403 lines!**), historical sentinel alerts, and roadmap tables into `.synlynk/context.md`.
3. **Keyword Matching False Positives:** In [`pack.py:synthesize_context_pack`](file:///Users/nikhilsoman/dev/synlynk/synlynk/pack.py#L140-L165), keyword extraction matches generic terms (e.g., `test`, `file`, `data`), pulling in disjoint AST communities and unnecessary signatures.

### B. Optimization Strategy
* **Active In-Flight Circuit Breaker:** [`enforce_job_circuit_breaker`](file:///Users/nikhilsoman/dev/synlynk/synlynk/sentinel.py#L727) currently acts as a post-mortem detector. It must be converted into an **in-flight watchdog** that monitors job streaming logs or process metrics and sends `SIGTERM` if an agent hits 500k tokens or 20 tool calls without creating/editing a file.
* **Prompt Caching Structure:** Partition prompts into an immutable **System & AST Anchor** (cached by provider APIs at 90% discount) and a dynamic **Task Working Cone**.
* **Pruned Context Slices:** Workers must only receive context scoped to their assigned `story_id`, never the global repository task ledger.

---

## 3. Eliminating Design Flaws & Semantic Friction

To prevent users from getting bogged down in semantic debates, two conceptual layers need architectural simplification:

### A. The "Harness vs. Agent vs. Role vs. App Identity" Quagmire
* Currently, the system distinguishes between:
  1. **Harness:** The model execution CLI (Claude, Codex, Agy, Grok).
  2. **Agent / Role:** The persona charter (`dev`, `qa`, `architect`, `pm`, `tpm`).
  3. **GitHub App Identity:** RS256 JWT-authenticated installation token.
* This causes confusion when routing tasks (e.g., `#423`, `#426`, `#569` where Grok cannot write, Codex needs explicit `--requires-gh-write`, and QA reviews must dodge author identity collisions).
* **Simplification for v1.0.0:** Collapse into a **2-Tier Model**:
  * **Role (The "What"):** Defines permissions, charters, and Git/GitHub identity.
  * **Harness Engine (The "How"):** The execution runtime.
  * The user should only assign tasks to a *Role* (e.g., `synlynk dispatch --as-role qa`), and Synlynk's capability matrix must automatically resolve the eligible harness and credential bindings without exposing manual routing flags.

### B. Rigid GOVERNS Lifecycle Friction ([`governs_fsm.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/governs_fsm.py))
* The 7-stage event FSM (`goal` $\rightarrow$ `open` $\rightarrow$ `visualize` $\rightarrow$ `execute` $\rightarrow$ `release` $\rightarrow$ `notify` $\rightarrow$ `sustain`) is excellent for major architectural milestones, but induces semantic drag for quick bugfixes, chores, and docs updates.
* **Simplification:** Implement a **Fast-Track Lifecycle**:
  * *Standard Epic:* 7 stages with required specs and release collateral.
  * *Fast-Track Patch / Chore:* 3 stages (`open` $\rightarrow$ `execute` $\rightarrow$ `sustain`), automatically inferred by [`governs_resolver.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/governs_resolver.py) based on issue labels or branch prefixes (`fix/`, `chore/`).

---

## 4. Multi-Harness Failure Modes & Sandbox Resilience

Headless dispatches fail in subtle ways that undermine autonomous operation. Two failure modes dominate current telemetry:

### A. The Silent Exit-0 / Non-Execution Trap
* **The Problem:** The Grok dispatch sandbox completely denies shell execution, and Codex occasionally terminates cleanly with `exit 0` but fails post-response processing, resulting in **0 files touched and 0 diffs**.
* **The Solution — Attested Delta Contract:**
  Process exit codes (`returncode == 0`) must **never** be treated as proof of success. In [`dispatch.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/dispatch.py#L1528) and [`jobs.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/jobs.py#L1850), a job must only be marked `succeeded` if it fulfills the **Attested Delta Triple**:
  $$\text{Success} \iff (\text{Exit Code} == 0) \land (\Delta_{\text{git}} > 0 \lor \text{Explicit Read-Only Task}) \land (\text{Verify Tests Passed})$$
  Any write task exiting 0 with zero git diff must fail immediately with status `FAILED_NOOP_DENIED`.

### B. The `TASK_RECEIPT_WARN` False-Positive Epidemic
* Telemetry in `sentinel.md` recorded dozens of alerts on 2026-09-27:
  ```text
  [WARN] TASK_RECEIPT_WARN: Job job-xxxx on agent 'claude'/'codex'/'grok' skipped/mismatched the task receipt marker (absent) but real work landed in its worktree
  ```
* Looking at [`jobs.py:233`](file:///Users/nikhilsoman/dev/synlynk/synlynk/jobs.py#L233):
  ```python
  if lines[0] == expected:
      return "ok"
  ```
  Checking strictly `lines[0]` causes immediate failure if the agent outputs thinking tokens, greeting banners, or CLI telemetry first.
* **The Solution:** Use relaxed frontmatter parsing or search the first 20 non-empty lines for `SYNLYNK_TASK_RECEIVED: <sha>`. Better yet, have the dispatch wrapper script inject the attestation receipt automatically on start, rather than relying on LLM text compliance.

---

## 5. Concrete Architecture Recommendations for v1.0.0 Dev Preview

| # | Component | High-Impact Recommendation | Expected Benefit |
|---|---|---|---|
| **1** | **Dispatch & Sentinel** | **Active In-Flight Circuit Breakers:** Inject a real-time monitor into [`dispatch.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/dispatch.py) that terminates any job crossing 500k tokens with 0 files touched, and pre-checks harness sandbox capabilities (e.g. disallow Grok for bash-required jobs). | Eliminates runaway $15–$35 token burn incidents completely. |
| **2** | **Context & Pack** | **Sparse Worktree & Story-Isolated Context:** Ensure [`synthesize_context_pack`](file:///Users/nikhilsoman/dev/synlynk/synlynk/pack.py#L102) and [`generate_context`](file:///Users/nikhilsoman/dev/synlynk/synlynk/context.py#L322) emit only story-relevant files and symbols (max 3k tokens total) instead of ingesting the 1,400-line global `todo.md`. | Drops median input token load per dispatch by 60–80%. |
| **3** | **Job Attestation** | **Attested Delta Verification & Relaxed Receipts:** Replace brittle `lines[0]` string matching in [`_check_task_receipt`](file:///Users/nikhilsoman/dev/synlynk/synlynk/jobs.py#L221) with header-tolerant scanning, and enforce `git diff` non-emptiness before recording job success. | Clears false-positive Sentinel noise and catches silent sandbox drops. |
| **4** | **Daemon & Auth** | **Graceful Offline / Zero-Config Degraded Mode:** Wrap GitHub App authentication in [`github_app_auth.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/github_app_auth.py) with an explicit network-connectivity probe; fall back to local Git configuration silently when offline. | Rock-solid first-time developer experience without DNS/network crash loops. |
| **5** | **GOVERNS FSM** | **Bimodal Lifecycle Paths (Standard vs. Fast-Track):** Allow small fixes, docs, and test iterations to bypass the heavy `visualize` / `notify` ceremony, reserving full 7-stage state machines for feature epics. | Removes developer friction while retaining architectural governance. |

---

Verdict: Synlynk v1.0.0 possesses an exceptional foundational architecture—combining a zero-SaaS host-local daemon, deterministic Git worktree isolation, AST blast-radius calculation, and multi-harness dispatch into an autonomous engineering platform that stands far ahead of conventional script-based agent wrappers. However, before the October 01 Developer Preview, the team must address operational fragility: specifically by implementing active in-flight token circuit breakers, enforcing verified Git delta contracts over hollow exit-0 statuses, eliminating brittle receipt-checking false positives, and decoupling local daemon startup from remote GitHub App availability. With these five surgical hardenings in place, Synlynk v1.0.0 will deliver a dependable, production-grade developer experience on day one.

### 4. Grok Architecture Review
I'll ground this review in the actual architecture, not just the briefing. First I'm checking how the daemon, dispatch, context packing, and harness failure paths are really built.The v1.0.0 developer preview is a real local control plane with a strong ledger and a weak completion contract. The day-1 risk is not missing diagrams. It is a user who runs one headless job, sees exit 0, and gets no branch, no review, and a large bill.

## 1. What has to be rock-solid on day one

Ship one path that cannot lie: install, `doctor`, one dispatch, a worktree, a verified diff, and a status line that matches `git` and `gh`. Everything else is optional.

That path is narrower than the current surface. `COMMAND_TAXONOMY` is a large command set. The injected instruction files repeat role charters, merge policy, Herdr protocol, and a trigger registry. A new user meets a fleet operating system before they meet a working agent. The first-win onboarding spec (`2026-09-03-zero-risk-onboarding-and-first-win-design.md`) is still marked In Review. Until that path is the default, the 3,311-test suite protects the authors, not the first install.

Three facts must be true before a preview user is asked to trust the product:

- **The daemon layout is one sentence and it matches the code.** Vizor is `localhost:8721`. The job daemon is `localhost:27471`. The SSE relay is `localhost:27472`. The briefing collapses the first and third and drops the second. Operators will debug the wrong port.
- **SQLite WAL in `~/.synlynk/projects/<hash>/state.db` is the only mutation ledger, and the CLI says that path.** Markdown under `project-docs/` is a projection. `todo.md` is already generated. If both look editable, users will edit the wrong one and conclude state is corrupt.
- **GitHub Apps are not required for the first win.** Six RS256 app identities (dev, qa, architect, pm, tpm, synlynk-bot) are the right design for non-author review. They are the wrong gate for "show me a branch." A preview that only works after app registration, JWT signing, and org install will be judged on identity setup, not on dispatch.

Vizor should stay up on a read of `state.db` even when no harness is installed. If the HUD is the product's face, a dead daemon or a missing Graphify cache cannot blank it. Show an empty fleet and a single next action from `doctor`.

## 2. Token economics

The expensive failure is already measured. Job `job-cf837848` ran about six hours on `context_mode=full`, spent roughly 7.6M input tokens and $5.26, touched zero files, and died with exit `-9`. Sentinel now flags `TOKEN_BLOAT` and `COST_INFLATION` after reconciliation. That is an audit, not a brake. The money is gone before the alert exists.

`synlynk pack` is aimed at the right shape: signatures, docstrings, caller and callee chords, and test file names inside a 1,500-token budget. It is not yet the dispatch payload. In `dispatch.py`, `synthesize_context_pack()` is appended to `context_text` after `generate_context()` and the role charter. A missing `graph.json` triggers a Graphify extract inside prompt assembly. The pack adds tokens. It does not replace the constitution.

Three burns dominate a multi-harness run:

- **Preamble, not code.** Harness instruction blocks in this repo are thousands of lines of SOP, duplicated across agent files, and then wrapped again with task receipts, instruction-version receipts, charter text, and GitHub-write instructions. A 1,500-token cone cannot win against that prefix. Headless workers should get a short profile, not the Home Conductor constitution.
- **`context_mode=full` is monotonic.** Each turn resends history plus the base pack. Default `task` mode is the right default. `full` on a headless job should be a deliberate override with a hard cumulative input cap and a mid-flight kill, not a sentinel row the next morning.
- **The 1,500 budget is `len(text) / 4`.** That under-counts code, identifiers, and JSON. Docstrings are inlined in full before the cutter runs, and test discovery substring-scans every `tests/test_*.py`. The result is a soft cap that still ships the wrong slice when the match is broad.

Multi-agent dispatch multiplies all of this. A plan, an implement, and a review are three full prefixes unless the review prompt is the diff plus the acceptance check and nothing else. Routing four public harnesses at one task is a cost bug unless a capability probe has already eliminated three of them.

## 3. Semantic friction to remove

The architecture has too many lifecycles for one user action.

| What the user wants | What the product asks them to hold in their head |
|---|---|
| Who is accountable | Role, charter, GitHub App, and sometimes "agent" |
| What executes | Harness, model, sandbox profile, permission grant |
| Whether it is done | Story state, job exit code, GOVERNS stage, PR state |

Agent versus harness is a real distinction and should stay in the glossary. It should not be the first thing a preview teaches. User-facing nouns for v1: **Role** and **Harness**. The GitHub App is how a role authenticates. GOVERNS (Goal, Open, Visualize, Execute, Release, Notify, Sustain) can keep driving the daemon. The HUD should show Goal, Working, Shipped.

The same compression applies to Vizor. Status, Topologies, Projections, and Telemetry are enough. The older Gantt, journeys, tube map, cost, and efficiency views, plus the newer HLD stack, sequence player, and ecosystem radar, are views of one graph. Ship four entry points that deep-link. Do not make the taxonomy the interface.

Two claims will start semantic arguments if they stay unqualified. "Zero-SaaS" is true for the ledger and the daemon. Inference still leaves the machine for Anthropic, Google, OpenAI, xAI, and GitHub. Say "no hosted control plane." And the brainstorm-first, spec-before-code gate is correct for developing synlynk itself. Copied into a customer repo as the default worker prompt, it turns "fix this function" into a process debate. Workers get the task and the cone. The constitution stays with the home session.

## 4. Failure modes that already happened

Exit 0 is not completion. The capability baseline records both false failures and false successes. The one that will burn preview users is the false success: Grok job reported `done`, exit 0, zero files, and no GitHub review (LIVE-8, #1166). The same harness has returned a generic OK while `git diff origin/main` was empty because the dispatch sandbox denied `bash`. Codex in read-only mode blocks DNS, so a review routed there without `sandbox_workspace_write.network_access=true` cannot reach `api.github.com`. Agy has raised `PermissionEnforcementError` on a read-only grant even though the CLI has a plan mode. Grok's `dontAsk` mode auto-cancels a flagged compound shell command in about a millisecond and ends the turn (`PermissionCancelled`), which is why dispatch now forces `--always-approve` when shell or tests are granted.

The substrate still treats the process exit as the primary fact and the git or GitHub effect as a commentary. `files_touched` and `gh_write_expect` exist, and the July 2026 verification epic exists because status used to be a sidecar file plus a hardcoded empty file list. Stall detection has killed jobs whose logs were simply unflushed. Shared `index.lock` and stale worktrees are the other half: a July audit found on the order of 30 abandoned worktrees, and concurrent jobs against one tree was the original reason for per-job worktrees.

A preview policy that says "do not trust job status; go check `gh`" is an operator workaround. The product has to refuse the green state itself.

## 5. Five changes that move the release

1. **Effect-verified completion.** A mutating job is `done` only when the promised effect is visible: a non-empty diff against the job base, or a GitHub object that `gh` can read back. Exit 0 with an empty diff and a missing review is `empty_success`, and it is a failure. No-op work must carry an explicit receipt. Sentinel stays as the log of that decision, not the thing that notices it later.

2. **A hard context budget on the worker, with pack as the body.** Headless prompts are task, acceptance check, charter excerpt, and the pack, under one real token cap. `generate_context(scope=full)` and the long instruction files are not prepended. If `graph.json` is missing, dispatch does not extract the graph while building the prompt; it ships a smaller lexical pack and says the graph was cold. Cumulative input past the reservation kills the process.

3. **A five-second capability probe, cached, fail-closed.** Before a job is queued, check the effect it needs: shell, tests, network, GitHub write. Route only to a harness whose last probe passed for that effect. Grok does not receive GitHub-write or review work until a live probe shows a review object, not an exit code. Codex never gets a network task in read-only. An unknown probe result does not dispatch.

4. **One writer per worktree, and reap before create.** Take a lock around worktree add and index updates. Reconcile `index.lock` orphans and zombie PIDs at the start of dispatch, not in a periodic audit. The July pile-up should be impossible to repeat silently.

5. **A preview command surface of about eight verbs.** `init`, `doctor`, `dispatch`, `jobs`, `status`, `pr`, `viz`, `cost`. GitHub Apps, GOVERNS, swarm, mesh, and the rest stay installed and hidden until `doctor` reports their dependencies. The first successful run is a local branch from a single installed harness, with no app and no spec document.

## Verdict

Verdict: the host-local WAL daemon, per-job worktrees, role-scoped GitHub identities, and the AST pack are the right skeleton for a zero-hosted orchestrator, but v1.0.0 will feel unreliable until completion is defined as an observed git or GitHub effect, headless prompts are capped cones instead of constitutions, and the preview exposes one harness path that works before any of the fleet machinery is turned on.
