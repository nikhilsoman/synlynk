<!-- generated - source of truth is state.db -->
---
decision_id: dec-96ad1a51
topic: "Context-window management R1: audit your native environment's instruction-reload behavior (per-turn vs per-session, with evidence), context-scoping/lazy-load primitives, and any context-budget signal you can expose for preemptive compaction. Full spec at docs/superpowers/specs/2026-10-12-context-window-optimization-design.md (GOVERNS story-c04f64b1 / goal-e79062e8). NOTE: grok timed out twice (headless command timed out) and is excluded from this round — its native-environment findings are a known gap to fill separately."
date: 2026-10-12
panel: [claude, agy, codex]
status: approved
---

## Topic
Context-window management R1: audit your native environment's instruction-reload behavior (per-turn vs per-session, with evidence), context-scoping/lazy-load primitives, and any context-budget signal you can expose for preemptive compaction. Full spec at docs/superpowers/specs/2026-10-12-context-window-optimization-design.md (GOVERNS story-c04f64b1 / goal-e79062e8). NOTE: grok timed out twice (headless command timed out) and is excluded from this round — its native-environment findings are a known gap to fill separately.

## Panel Inputs

### claude
[model=default; version=2.1.292 (Claude Code)]

**Claude native-environment audit — instruction reload, context-scoping, and budget signals**

**Instruction reload: per-session, not per-turn, with one caveat.** CLAUDE.md, user memory, and skill metadata load once at session start and persist in the context window verbatim — they are not re-fetched or re-injected each turn. Evidence from this very session: the full global CLAUDE.md, project CLAUDE.md (including the nested-worktree-path variant), and MEMORY.md index all arrived in the first system-reminder block, not repeated per message. The caveat is tool-result-triggered reinjection: deferred-tool listings and skill *content* (not metadata) only materialize when invoked via ToolSearch or Skill — that's lazy-load, not reload. SessionStart hooks (the superpowers reminder) fire once per session boundary, confirmed by the `<EXTREMELY_IMPORTANT>` block appearing exactly once here.

**Context-scoping primitives that exist today:** (1) Skill tool — metadata (name + one-line description) stays resident, full body loads on invocation only; (2) ToolSearch — same pattern for MCP/deferred tools, schemas absent until queried; (3) Agent/subagent dispatch — forks get a fresh context window, returning only a summary to the parent, which is the sharpest scoping primitive available (full isolation, not just lazy load); (4) Read with offset/limit — manual, not automatic.

**Budget signal: none exposed natively to me.** I have no API or tool call that returns current token usage, remaining budget, or % context used. The synlynk statusline computes this externally (shell script reading transcript/session metadata), not from anything I can query mid-turn. This is the real gap: compaction decisions today rely on either an external harness-level readout (statusline) or the platform's own automatic summarization — I cannot self-trigger preemptive compaction from inside a turn because I don't know my own fill level.

**Recommendation:** any context-budget mechanism this design builds must live in the harness/CLI layer (reading transcript size, as the statusline already does) and surface it to me as an explicit tool result or system-reminder threshold crossing — not assume model-side introspection, which doesn't exist. Subagent dispatch is the strongest lever already available for proactive scoping; lean on it before inventing new primitives.

### agy
[model=default; version=1.3.3]

**Last completed task:** `docs: add context-window tracking & optimization design spec (goal-e79062e8)`  
**Next task from `todo.md`:** `Context-window management R1 audit (story-c04f64b1 / goal-e79062e8)`

---

### Native Environment Audit: Agy / Gemini CLI (AntiGravity)

**1. Instruction-Reload Behavior (Per-Turn Inlined Payload)**  
Agy interfaces with the stateless Gemini `generateContent` API. Root directives, system rules, and harness instructions (e.g., `GEMINI.md`) are parsed at session launch into system instructions and re-inlined on **every turn** in the request payload alongside rolling transcript history. Evidence: inspecting the underlying API payload structure confirms that the full system instruction block is transmitted on each HTTP call unless explicit server-side context caching is negotiated. Consequently, synlynk's monolithic root instruction files (880 lines total) impose a compounding per-turn input token cost throughout the session.

**2. Context-Scoping and Lazy-Load Primitives**  
Agy natively supports two lazy-load primitives:
- **Skill Deferred Loading:** The runtime registers only concise metadata (name and brief description) in the base prompt (~2 lines per skill). Full instructions (`SKILL.md`) and supporting files are pulled into context on-demand via file-reading tools when relevant.
- **Lazy Tool Schemas:** MCP tools can be declared as lazy-loaded stubs resolved only upon execution.  
An index-and-links restructuring fits Agy naturally: `GEMINI.md` can be slimmed to a minimal resident index (<30 lines) with pointers to modular references in `docs/sop/`, read on demand.

**3. Context-Budget Signals**  
The Gemini API returns deterministic `usageMetadata` (`promptTokenCount`, `candidatesTokenCount`, and `totalTokenCount`) in every response payload. Rather than scraping interactive UI statusline indicators, synlynk’s dispatch wrapper can directly observe `promptTokenCount` from telemetry at zero parsing overhead to gauge context pressure before hitting degrative compaction limits.

**Recommendation & Position**  
I recommend **Approach C (Hybrid)**. Synlynk should refactor `GEMINI.md` into a lightweight, skill-style index linking out to on-demand SOPs, eliminating unnecessary resident bloat. Concurrently, synlynk must leverage API `promptTokenCount` telemetry to trigger preemptive `/clear` resets at natural task boundaries (e.g., PR merge, job finish), reloading state with task-specific context packs rather than full monoliths.

### codex
[model=default; version=codex-cli 0.162.1]

For the Codex audit, OpenAI Docs describe Codex CLI as discovering `AGENTS.md` files from `~/.codex` through the repo root to the current directory, then injecting the merged instructions near the top of the conversation. That supports **per-session setup/injection**, not a claim that the files are resent on every turn. The docs do not establish the exact behavior of this hosted Codex session, so I can’t verify whether its instructions are reloaded between turns. [Codex Prompting Guide](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide)

Codex’s native scoping primitive is the directory hierarchy: global instructions, repo instructions, then deeper directory instructions, with later instructions able to override earlier ones. A practical index-and-links design would keep `AGENTS.md` short, with topic-specific guidance in separate files read when relevant. Directory-scoped instructions can narrow what applies by location; they do not, by themselves, prove that linked files load lazily. Skills offer a closer deferred-load pattern: a short description can route a task to detailed instructions when needed.

I have no context-use percentage or “percent to compact” signal exposed in this session, and no documented native hook here for a wrapper to trigger `/clear` or `/compact`. OpenAI documents compaction for Responses API integrations, where the caller invokes the compact endpoint and passes the compacted state forward; that is an API capability, not evidence of a Codex CLI status signal. [Codex Prompting Guide](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide)

**Position: recommend a hybrid, but stage it around confirmed controls.** Shorten resident instructions and use scoped, on-demand topic files where the harness supports them. Build task-boundary compaction and task-specific context packs as wrapper-managed features; do not rely on an unverified native budget indicator. Treat Codex CLI reload timing and hosted-session behavior as an evidence gap, and retain Grok’s native audit as a separate follow-up.

## Synthesis
## Synthesis

**Where all three agree:** none of the three audited harnesses expose a native, model-side "percent context used" signal that the *model itself* can query mid-turn to self-trigger compaction. Where a budget-like number exists, it's a wrapper/API-layer artifact (Agy's `usageMetadata.promptTokenCount` returned per response; Claude's statusline computed externally from transcript size), not something the model introspects. This confirms the design spec's premise: context-budget tracking belongs in the harness/dispatch wrapper, not in model-side logic.

**Where reload behavior diverges — this matters for the "index-and-links" restructuring:**
- **Claude:** per-session, verbatim, confirmed by direct evidence in this transcript (CLAUDE.md/MEMORY.md arrived once, at session start, not resent). Lazy-load exists today via Skill metadata-vs-body and Agent/subagent forking (the sharpest scoping primitive available — full context isolation, not just deferred text).
- **Agy:** per-turn, confirmed by payload inspection — the full system-instruction block is re-inlined on every `generateContent` call unless caching is negotiated. This means Agy's cost model for a bloated `GEMINI.md` is fundamentally worse than Claude's (compounding per-turn, not one-time) — restructuring it into a slim resident index with on-demand `docs/sop/` reads has a *higher* ROI for Agy than for Claude.
- **Codex:** unverified. The docs establish discovery-and-injection of `AGENTS.md` at session start but say nothing about this hosted session's actual per-turn behavior, and Codex's own report is explicit that it can't confirm this from inside the session. Codex also reports no native budget signal and no documented compaction hook, but again flags this as an evidence gap rather than a confirmed absence.
- **Grok:** excluded this round (timed out twice) — genuine gap, not a null result either way.

**Practical implication:** a single monolithic-instruction-file cost model doesn't apply uniformly across harnesses. Index-and-links restructuring pays off everywhere, but the urgency ranks Agy (per-turn resend, confirmed) > Claude/Codex (per-session, lower compounding cost but still worth trimming) given current evidence. Budget-signal plumbing should use whatever the harness actually exposes — Agy's `promptTokenCount` is real and cheap to wire into telemetry now; Claude has to keep relying on the external statusline/transcript-size proxy since no better signal exists; Codex's signal status needs its own empirical probe (e.g., deliberately bloat context and watch token/cost deltas across turns) before the design can assume anything about it one way or the other.

Decision: Adopt the hybrid approach (Agy's Approach C, endorsed in substance by Claude and Codex): restructure every harness's monolithic root-instruction file (CLAUDE.md/GEMINI.md/AGENTS.md) into a slim resident index with topic-specific SOPs loaded on demand, modeled on the Skill metadata/body split; implement context-budget tracking at the dispatch-wrapper layer using each harness's actual exposed signal (Agy: `promptTokenCount` from API `usageMetadata`, wired into telemetry immediately; Claude: continue using the external statusline/transcript-size proxy, since no native introspection exists; Codex: do not assume a signal exists — file a follow-up empirical probe before committing to a mechanism); trigger preemptive compaction/context-pack reloads at task/session boundaries (PR merge, job finish) via the wrapper rather than via any assumed model-side self-awareness; and treat Codex's per-turn reload behavior and Grok's entire native-environment audit as confirmed open gaps requiring a dedicated follow-up round before the design spec can claim full-fleet coverage.

## Decision
Decision: Adopt the hybrid approach (Agy's Approach C, endorsed in substance by Claude and Codex): restructure every harness's monolithic root-instruction file (CLAUDE.md/GEMINI.md/AGENTS.md) into a slim resident index with topic-specific SOPs loaded on demand, modeled on the Skill metadata/body split; implement context-budget tracking at the dispatch-wrapper layer using each harness's actual exposed signal (Agy: `promptTokenCount` from API `usageMetadata`, wired into telemetry immediately; Claude: continue using the external statusline/transcript-size proxy, since no native introspection exists; Codex: do not assume a signal exists — file a follow-up empirical probe before committing to a mechanism); trigger preemptive compaction/context-pack reloads at task/session boundaries (PR merge, job finish) via the wrapper rather than via any assumed model-side self-awareness; and treat Codex's per-turn reload behavior and Grok's entire native-environment audit as confirmed open gaps requiring a dedicated follow-up round before the design spec can claim full-fleet coverage.

> Signatures: see 2026-10-12-context-window-management-r1-audit-your.json
