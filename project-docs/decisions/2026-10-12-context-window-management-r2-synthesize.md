<!-- generated - source of truth is state.db -->
---
decision_id: dec-5cc6c82e
topic: "Context-window management R2: synthesize R1's findings (project-docs/decisions/2026-10-12-context-window-management-r1-audit-your.md) into one cohesive modification to synlynk's instruction-writer for each harness (the CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md templates init() generates), plus a shared task-boundary compaction-trigger and context-pack design. R1 confirmed: budget signals belong in the dispatch-wrapper layer not model-side; Agy resends its full instruction file every turn (confirmed, highest-ROI restructuring target); Claude is per-session (confirmed, lower urgency); Codex's per-turn behavior and Grok's entire native-environment audit are OPEN GAPS, not confirmed either way -- do not assume a mechanism for either; instead specify what empirical probe would close each gap, and design the instruction-writer modification to degrade safely (e.g. default to the Agy-style worst-case treatment) for any harness whose reload behavior is unconfirmed. Full spec at docs/superpowers/specs/2026-10-12-context-window-optimization-design.md (GOVERNS story-c04f64b1 / goal-e79062e8)."
date: 2026-10-12
panel: [claude, agy, codex]
status: approved
---

## Topic
Context-window management R2: synthesize R1's findings (project-docs/decisions/2026-10-12-context-window-management-r1-audit-your.md) into one cohesive modification to synlynk's instruction-writer for each harness (the CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md templates init() generates), plus a shared task-boundary compaction-trigger and context-pack design. R1 confirmed: budget signals belong in the dispatch-wrapper layer not model-side; Agy resends its full instruction file every turn (confirmed, highest-ROI restructuring target); Claude is per-session (confirmed, lower urgency); Codex's per-turn behavior and Grok's entire native-environment audit are OPEN GAPS, not confirmed either way -- do not assume a mechanism for either; instead specify what empirical probe would close each gap, and design the instruction-writer modification to degrade safely (e.g. default to the Agy-style worst-case treatment) for any harness whose reload behavior is unconfirmed. Full spec at docs/superpowers/specs/2026-10-12-context-window-optimization-design.md (GOVERNS story-c04f64b1 / goal-e79062e8).

## Panel Inputs

### claude
[model=default; version=2.1.292 (Claude Code)]

Position: ship a single degrade-safe instruction-writer change now; don't wait on Codex/Grok probes.

**Instruction-writer modification:** Add one shared "context discipline" block emitted into every generated file (CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md), parameterized by a per-harness `reload_confidence` enum: `confirmed_per_turn` (Agy), `confirmed_per_session` (Claude), `unconfirmed` (Codex, Grok — default). The block tells the harness to keep its own instruction file terse and push detail into a referenced context-pack rather than inline prose, since any harness that *might* resend the full file per turn pays the same tax Agy does. Unconfirmed defaults to the Agy treatment — worst case, not average case — until a probe confirms otherwise. This is the one place R1's finding (budget signals live in the dispatch wrapper, not the model) and the per-harness reload uncertainty actually intersect: the generator can't special-case Codex/Grok without evidence, so it has to treat "unknown" as "expensive" by construction.

**Context-pack design:** A generated `.synlynk/context-pack/<task-id>.md`, assembled by the dispatch wrapper at task-boundary time, not by the harness. Contains only: GOVERNS linkage, current story/goal, last devlog entry, and the diff-relevant file list — not the full roadmap/memory/todo concatenation `generate_context()` currently produces. The instruction file points to it by path instead of inlining project-docs content, so a harness that reloads its instruction file every turn reloads a pointer, not the payload.

**Compaction trigger:** Fire at task boundaries (dispatch job start/end, PR open/merge), not on a token-percentage heuristic — consistent with R1's wrapper-layer finding. Concretely: `exec_command()` regenerates the context-pack and truncates/archives the previous one at each boundary, so staleness cost is bounded by task granularity rather than turn count.

**Empirical probes to close the open gaps (ship alongside, don't gate on):**
- Codex: dispatch a 3-turn task, diff bytes-sent-to-API (via telemetry token counts in `cost_entries`) turn-over-turn; flat vs. growing tells you per-turn resend vs. session-cached.
- Grok: same instrumentation plus an explicit check of whether its native environment exposes any persistent-context/caching primitive at all (currently unknown, not just unmeasured) — a one-line capability probe added to `capability_probe.py` alongside `CAP_GH_WRITE`.

Ship the generator change and probes together in one PR; downgrade Codex/Grok from `unconfirmed` only after ≥5 samples per the Empirical Capability Assessment Policy.

### agy
[model=default; version=1.3.3]

Last completed task: `Context-window management R1 audit (dec-96ad1a51 / goal-e79062e8)`  
Next task from [`todo.md`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+tpm-daemon-autonomy-fix-design/.claude/worktrees/docs+claude+dev-preview-roadmap-execution/worktrees/docs-context-window-optimization/project-docs/todo.md): `Context-window management R2 synthesis & instruction-writer design (story-c04f64b1 / goal-e79062e8)`

---

### Context-Window Management R2: Synthesis & Recommendation

#### 1. Instruction-Writer Restructuring (Index + Links)
To eliminate monolithic instruction overhead across `synlynk init()`, migrate all harness templates (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `AI_INSTRUCTIONS.md`) to a standardized **Index-and-Links** format (<40 resident lines each):
- **Core Stays Resident:** Harness metadata, strict repo hygiene (branching/commit trailers), and short skill/routing pointers.
- **Modular SOP Extraction:** Offload domain workflows, PR review checklists, and Herdr conventions into on-demand files under `docs/sop/` (e.g., `docs/sop/pr-review.md`).
- **Defensive Defaulting:** Because Agy incurs compounding per-turn payload re-inlining and unconfirmed harnesses risk identical churn, **every template must degrade safely by adopting this lightweight index-and-links structure by default**.

#### 2. Closing Empirical Gaps for Codex & Grok
Before tailoring harness-specific optimizations, synlynk must run empirical probe jobs:
- **Codex Reload Probe:** Dispatch a 2-turn synthetic job with a 500-token file edit, append 2,000 distinct lines to `AGENTS.md` between turns, and inspect turn-2 API input token telemetry. Identical base counts confirm per-session caching; an increase proves per-turn reloading.
- **Grok Native Environment Audit:** Run a headless dispatch probe testing basic pipe responsiveness with relaxed timeouts, verifying whether custom instructions inject per turn or per session, and checking for native context budget/compaction hooks.

#### 3. Shared Task-Boundary Compaction Trigger & Context Packs
Because no model introspects its own context window, tracking belongs entirely in the dispatch/exec wrapper layer:
- **Compaction Trigger:** The wrapper calculates cumulative context pressure from response telemetry (`promptTokenCount` for Gemini; transcript length for Claude/others). When usage exceeds a configurable threshold (e.g., 70% window capacity), the wrapper fires a `/clear` or `/compact` reset at natural boundaries: dispatch job completion, story sign-off, or PR merge.
- **Context-Pack Reload:** Following boundary compaction, the wrapper injects a targeted `.synlynk/context-packs/<job-id>.md` bundle (containing the active issue/story, affected file stubs, and recent decisions) instead of blindly concatenating monolithic roadmap, memory, and todo state.

#### Position
I strongly recommend adopting **Approach C (Hybrid)**: restructure `synlynk init()` instruction templates across all harnesses into lean index files pointing to on-demand SOPs, default unverified harnesses to Agy's lightweight pattern pending empirical telemetry probes, and implement wrapper-managed task-boundary compaction paired with minimal context-pack reloads.

### codex
[model=default; version=codex-cli 0.162.1]

**Analysis.** R1 supports a hybrid design. Context-budget signals belong in the dispatch wrapper: models should not be expected to know how much context remains. Agy’s `promptTokenCount` is available to the wrapper; Claude’s current signal is an external transcript-size proxy. Neither establishes a model-side trigger. Reload behavior also changes the payoff of trimming instructions: Agy resends its full instruction file each turn, so a slim `GEMINI.md` index with detailed guidance fetched as needed is the highest-priority restructuring. Claude loads instructions per session, so trimming still helps, but has less repeated-turn benefit.

Codex’s reload behavior remains unverified: documentation establishes instruction discovery and injection, but not whether this hosted session reloads instructions each turn. Probe it by recording controlled request or token usage across turns with a fixed transcript, then repeat after changing an instruction file mid-session and observe whether the change takes effect without restart. Grok’s audit is still open after timeouts; probe the native CLI directly for instruction loading, scoping and lazy-load behavior, budget telemetry, and available compaction controls. Until either audit produces evidence, generate a short resident index and apply Agy’s worst-case assumption that instructions may be resent each turn.

**Recommendation.** Update `init()`’s `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `AI_INSTRUCTIONS.md` templates to keep a concise, stable operating index in each file and move detailed procedures into linked topic documents, with harness-specific pointers where on-demand reading is supported. Keep the shared task-boundary rules in the resident index: at dispatch completion, story completion, or PR merge, the wrapper checks its available telemetry or estimate and compacts only at that boundary when a configured threshold is crossed. After compaction, load a task-specific context pack containing the active story or goal, relevant files, and necessary prior decisions, rather than rebuilding the full todo, memory, and roadmap stack. **I recommend adopting this hybrid as the R2 position, prioritizing Agy’s per-turn instruction cost while treating Codex and Grok reload behavior as open empirical questions, not established facts.**

## Synthesis
Decision: Adopt the hybrid synthesis — ship one degrade-safe instruction-writer change now, don't gate on Codex/Grok probes.

**Instruction-writer:** Restructure every `init()`-generated template (CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md) into an index-and-links format: a lean resident core (harness identity, repo hygiene/branching/commit trailers, routing pointers, shared task-boundary rules) under ~40 lines, with domain SOPs (PR review checklist, Herdr conventions, etc.) extracted to on-demand files under `docs/sop/`. Parameterize by a `reload_confidence` enum — `confirmed_per_turn` (Agy), `confirmed_per_session` (Claude), `unconfirmed` (Codex, Grok). `unconfirmed` defaults to the Agy worst-case treatment by construction, not by estimate, until a probe confirms otherwise. This is the one change that correctly resolves R1's wrapper-vs-model-side finding against the per-harness reload uncertainty: the generator can't special-case what it hasn't measured, so "unknown" must cost the same as "expensive."

**Context-pack:** Dispatch wrapper assembles `.synlynk/context-pack/<task-id>.md` at task-boundary time — GOVERNS linkage, current story/goal, last devlog entry, diff-relevant file list only, not the full roadmap/memory/todo concatenation `generate_context()` produces today. Instruction files reference it by path; a harness that reloads its instructions every turn now reloads a pointer, not the payload.

**Compaction trigger:** Lives in the wrapper, fires at task boundaries (dispatch job start/end, story sign-off, PR open/merge) — not on a token-percentage heuristic. `exec_command()` regenerates the pack and archives the prior one at each boundary, bounding staleness by task granularity.

**Empirical probes (ship alongside, non-blocking):**
- *Codex:* fixed-transcript multi-turn dispatch job; record/compare per-turn input-token telemetry from `cost_entries`, and separately mutate `AGENTS.md` mid-session to see if the change takes effect without restart. Flat tokens + no-effect-without-restart ⇒ per-session caching; growing tokens or live pickup ⇒ per-turn reload.
- *Grok:* same telemetry instrumentation plus a one-line capability probe in `capability_probe.py` (alongside `CAP_GH_WRITE`) checking whether its native environment exposes any persistent-context/caching/compaction primitive at all — currently unknown, not just unmeasured.

Both probes land in the same PR as the generator/wrapper change. Codex/Grok only move off `unconfirmed` once they clear ≥5 merged-job samples under the Empirical Capability Assessment Policy — no earlier.

## Decision
Decision: Adopt the hybrid synthesis — ship one degrade-safe instruction-writer change now, don't gate on Codex/Grok probes.

> Signatures: see 2026-10-12-context-window-management-r2-synthesize.json
