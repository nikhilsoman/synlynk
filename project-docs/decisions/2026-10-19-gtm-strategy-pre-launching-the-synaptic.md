<!-- generated - source of truth is state.db -->
---
decision_id: dec-aee26f54
topic: "GTM Strategy: Pre-launching the Synaptic AI Capability Index as a Standalone Public Service, Interactive Prompt Oracle, and Universal Pre-Flight Routing API"
date: 2026-10-19
panel: [codex, grok, agy]
status: approved
---

## Topic
GTM Strategy: Pre-launching the Synaptic AI Capability Index as a Standalone Public Service, Interactive Prompt Oracle, and Universal Pre-Flight Routing API

## Panel Inputs

### codex
The Capability Index is viable as a standalone public service if positioned as “pre-flight intelligence for agentic work,” not merely a leaderboard. Its immediate value is vendor-neutral decision support: given a task, recommend the best harness/model/configuration based on verified outcomes, cost, latency, and reliability. This creates a credible top-of-funnel product because it solves a real decision before users commit to a workspace or grant repository access. The full Synlynk product remains the natural upgrade path: continuous routing, execution governance, verification, telemetry, and organizational policy.

Architecturally, keep the public path deliberately narrow and fast. A client-side or edge-hosted classifier should derive a compact task taxonomy from an optionally redacted prompt: domain, change type, risk, likely tool requirements, codebase dependence, and desired quality/cost tradeoff. Send only that feature vector by default to a versioned routing API. The API should query a precomputed capability matrix—aggregated verified PR outcomes, cost-per-verified-fix, token efficiency, latency, and failure/failover rates—then return ranked recommendations, confidence, rationale codes, and safe fallback choices. Cache by normalized feature-vector hash and routing-policy version at the edge; reserve deeper analysis for an explicit opt-in request.

Prompt privacy and benchmark integrity are the hard constraints. Do not retain raw prompts by default, avoid using inputs for training, provide a local-only classification mode, and publish retention behavior plainly. Separate public self-reported outcomes from verified Synlynk telemetry; weight the former as lower-confidence crowd signals and defend against manipulation with provenance, rate limits, anomaly detection, and cohort minimums. For non-Synlynk users, recommendations must disclose reduced confidence where repository context, test coverage, or policy constraints are unavailable.

High-value signals include task-taxonomy demand, recommendation acceptance and override rates, quality-versus-price choices, latency tolerance, regional/model availability, quota failures, and reported execution outcomes. These feed back into routing priors, benchmark coverage priorities, provider failover policy, and which integrations or governance features deserve product investment.

My formal recommendation is to soft-launch this as a privacy-first standalone “Synaptic Pre-Flight” service and universal skill, with transparent confidence scoring and a tightly scoped API. Treat it as a controlled acquisition and learning surface, while preserving the richer, continuously verified orchestration loop as Synlynk’s differentiated paid product.

### grok
I'll ground the panel take in how Synlynk already measures harness capability and routes work, then give a short architectural recommendation.**Recommendation: ship the Index as a signed, read-only public projection of `synlynk capability report`, and keep the Oracle and skill as thin clients of that snapshot.** A second scoring product would split the asset that already exists: `capability_ratings` (`quality`, `pr_review_cycles`, `quality_verified`, `signal_source`), `cost_entries` (`total_cost_usd`, tokens), and `quota_snapshots`, with Ed25519 signatures on rating writes and a sample floor of n≥5 before a cell may move `task_allocation`.

**Positioning.** The standalone service is the right teaser. Full Synlynk still requires a repo, worktrees, GOVERNS linkage, and a verification loop. The public surface should answer one question: for this task class, which harness and model currently win on median review cycles and cost per verified fix. Label the corpus as Synlynk engineering work. Cells under n≥5 stay visible and marked unmeasured, the same rule the Empirical Capability Assessment Policy already uses. The conversion step is specific: install Synlynk so the next merged PR writes a rating into the caller's own loop and, if they opt in, back into the public prior.

**Pre-flight architecture.** Do not query host `state.db` on the request path. A publisher job emits a versioned aggregate snapshot (task type × harness × model: n, median cycles, cost per verified fix, token totals, quota-failover probability, `generated_at`, signing key). Edge cache serves it. The hot path classifies the prompt into the existing discipline taxonomy with a small deterministic mapper, then joins the snapshot. Return JSON: ranked list, confidence, `snapshot_id`, and an explicit `unmeasured` flag. An LLM classifier is a separate, metered path. The Cursor, Claude, Cline, Windsurf, and LangChain skill is that same JSON contract, so dispatch and the public API cannot drift.

**Risk.** Store a prompt hash and taxonomy label by default. Raw text is opt-in, short-TTL, and excluded from training and from the rating tables. Crowd quota and failure reports land in a demand store. They never set `quality_verified`. Only independently verified ratings enter the published index, and synthetic seeds stay filtered. Non-Synlynk callers receive a prior plus provenance, not a claim about their repository.

**Signals that feed the core.** Taxonomy misses show which discipline rows the report still drops. Accept, override, and price-versus-quality choices show elasticity without touching quality scores. Model names absent from the fleet become the next calibration queue. Quota reports adjust the failover display beside `quota_snapshots`. Roadmap intake is "which cell is demanded and still under n≥5," not a new heuristic table.

Ship the signed snapshot, the Oracle, and one universal skill behind a soft launch. Defer crowd-written ratings and any claim of a universal benchmark until outside repos run the same verified loop.

### agy
The Antivirus-style definition pack model (Pillar 5) provides the exact foundation for pre-launching the Synaptic AI Capability Index as a high-velocity standalone product. By deploying the index at index.synlynk.com and exposing a lightweight /v1/preflight endpoint alongside a universal agent skill, Synlynk establishes undisputed market authority before asking users to grant repository permissions or install full workspace orchestration. Edge classification maps incoming prompts to the open SFIA 8/9 taxonomy in <20ms, rendering instant ranked recommendations (win-rates, cost-per-verified-fix, and failover probabilities). Interaction signals (prompt domain distributions, price-vs-quality elasticity, missing model demand, and crowd quota alerts) feed directly into Synlynk's calibration pipeline and model onboarding queue, while high-intent CTAs convert pre-flight users into full Synlynk CLI and VS Code extension workspace adopters.

## Synthesis
The Decide Panel (Codex, Grok, AGY) unanimously approves pre-launching the Synaptic AI Capability Index as an independent public web service, interactive Prompt Oracle, and universal pre-flight routing API. The panel establishes consensus across five core strategic and architectural principles:

1. Product Positioning & Soft-Launch Trojan Horse: Decoupling the Capability Index into a standalone public utility provides instant, vendor-neutral decision support ('pre-flight intelligence for agentic work') without the friction of repository access, local worktrees, or API key configuration. It positions Synlynk as the empirical authority on multi-agent execution economics and serves as a high-conversion top-of-funnel acquisition engine for the full Synlynk orchestrator and VS Code extension.

2. Pre-Flight Architecture & Shared JSON Contract: The public service will not query live workspace state.db instances. Instead, a lightweight Edge service (Cloudflare Workers / Fastly) ingests the signed, versioned daily snapshot (capability-pack-YYYY-MM-DD.json.gz) and evaluates a deterministic prompt classifier against the open SFIA taxonomy in <20ms. The exact same JSON response contract powers the index.synlynk.com interactive Prompt Oracle web UI, the public REST API (/v1/preflight), and the universal agent skill across Cursor, Claude Desktop, Cline, Windsurf, and LangChain.

3. Empirical Provenance & Cell Floor Integrity: The public index transparently reflects real Synlynk engineering and PR verification runs. All cells with fewer than 5 verified data points (n < 5) remain explicitly marked as 'unmeasured' per the Empirical Capability Assessment Policy, preventing synthetic benchmark dilution or speculative claims.

4. Privacy-First & Zero-Retention Security: Prompts are hashed and mapped to taxonomy feature vectors at the edge. Raw prompt strings are never retained by default, never used for model training, and never persisted to rating tables. Local classification mode is supported for privacy-sensitive environments.

5. Telemetry & Feedback Flywheel: Developer interactions capture high-fidelity market demand signals:
   - Taxonomy Demand: Uncovered SFIA disciplines reveal where engineering workloads are concentrating.
   - Price vs. Quality Elasticity: Toggle preferences between lowest cost and maximum verification rate steer routing defaults.
   - Model Fleet Backlog: Prompts requesting unmeasured models prioritize the Spot Swarm calibration queue.
   - Crowd Quota Failover Signals: User-reported quota limits update the failover advisory beside quota_snapshots in real time without corrupting verified quality scores.

## Decision
Approve pre-launching the Synaptic AI Capability Index as a standalone public service, interactive Prompt Oracle, and universal pre-flight routing API. Adopt the privacy-first edge architecture, shared JSON contract for web and agent skills, and telemetry harvesting feedback loop linked to goal-20bb3987 and story-5eecdf01.

> Signatures: see 2026-10-19-gtm-strategy-pre-launching-the-synaptic.json
