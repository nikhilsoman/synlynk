# Context Window Tracking & Optimization — Design Spec

**GOVERNS:** `goal-e79062e8` (filed as its own goal, not nested under the dev-preview roadmap tree — this is a cross-cutting process/tooling improvement, not a dev-preview feature)

**Status:** Draft — pending decide-panel R1/R2 synthesis before an implementation plan is written.

## Problem

synlynk dispatches work across four harness CLIs (Claude, Codex, Agy/Gemini, Grok) and runs its own interactive PM/home sessions on top of them. Both layers accumulate context over a session until the harness forces compaction, which is expensive, disruptive, and currently reactive rather than managed. The user asked for:

1. Visibility into and control over how large a context window gets before compaction triggers.
2. The ability to preemptively fire `/clear` or `/compact` as part of the workflow, not just react to a forced compaction.
3. Compaction to happen at natural task boundaries (dispatch job finish, story-done, PR merge) rather than mid-task.
4. After a clear, the ability to reload a *task-specific* context pack instead of the full memory/roadmap/todo stack, when that's cheaper.
5-8. A suspicion that harness instruction files (CLAUDE.md, AGENTS.md, GEMINI.md, AI_INSTRUCTIONS.md) and synlynk's own generated context are a major, possibly avoidable, source of per-turn bloat — needing validation, a line-count audit, and consideration of an index+links structure instead of full inlining.

## What's already confirmed (this repo, pre-panel investigation)

- **synlynk's own `generate_context()` (`synlynk/context.py:315`) is a real, provable bloat source**, independent of harness behavior: every `synlynk exec` invocation regenerates `.synlynk/context.md` from scratch by concatenating the full contents of `project-docs/todo.md`, `project-docs/memory.md`, and `project-docs/roadmap.md`, plus sentinel alerts, the charter section, and a runtime-authority banner. These files grow monotonically and are never summarized, aged, or truncated before injection.
- **Instruction-file sizes synlynk's own `init()` writes at project root** (this repo, current state): `CLAUDE.md` 335 lines, `AI_INSTRUCTIONS.md` 320 lines, `GEMINI.md` 116 lines, `AGENTS.md` 109 lines — 880 lines total, written once per `init()` but potentially reloaded by each harness every session or every turn.
- **Whether each external harness CLI (Claude Code, Codex, Gemini CLI, Grok CLI) resends its instruction file in full on every turn vs. once per session is NOT established anywhere in this repo.** `HARNESS_CAPABILITY_BASELINES`, `HARNESS_TIMEOUT_PATTERNS`, and `docs/harness-capability-baseline.md` contain no per-harness context-reload documentation. This is the open question R1 exists to close — nothing in this spec should be built on an unconfirmed assumption about per-turn resend behavior.
- **`synlynk decide` is single-round only** (`synlynk/cli.py:499-514`, impl `synlynk/team.py:792`): `synlynk decide "<topic>" --panel claude,agy,codex,grok --record`. There is no native multi-round/agenda construct — a two-round process means two separate `decide --record` calls, with R2's topic string explicitly referencing R1's recorded decision file. gh:#1226 (decide writing outside the invoking worktree) is closed, so decision files land correctly in the worktree's tracked `project-docs/decisions/`.

## Proposed approaches

**A. Index + links restructuring.** Collapse the monolithic instruction files into a short index plus topic files fetched on demand — the same deferred-load pattern Claude Code's own `ToolSearch` already uses for tool schemas. Strong fit if a harness can cheaply fetch files mid-session; unproven for Codex/Gemini/Grok CLIs. This is an R1 question, not a built-in assumption.

**B. Budget-driven compaction triggers.** Instrument `synlynk exec`/dispatch wrappers to track a running context-size estimate off existing token telemetry (`cost_entries`) and preemptively fire `/clear` or `/compact` at task boundaries (story-done, dispatch-finish, PR-merge) once a threshold is crossed. Works regardless of what R1 finds about per-turn resend behavior, and directly addresses points 1-4.

**C. Hybrid (recommended).** Both A and B — restructure the instruction files to cut resident size *and* add task-boundary compaction triggers plus a task-specific context-pack reload mechanism (point 4): a minimal per-job bundle (relevant story/goal, file list, prior decisions) written to `.synlynk/context-packs/<job-id>.md` at dispatch time, reloaded after a `/clear` instead of the full memory/roadmap/todo stack.

## Decide-panel plan

This spec does not pick between A/B/C or commit to implementation specifics — that's deliberately deferred to the panel, since (a) the per-harness resend behavior is unconfirmed and (b) each harness may have different native lazy-load primitives that should shape the final design rather than be retrofitted to it.

**R1 — native-environment audit.** Each panel member (claude, agy, codex, grok) reports on their own native environment:
- Does your instruction file (CLAUDE.md/AGENTS.md/GEMINI.md/equivalent) get resent in full every turn, or loaded once per session? Cite how you know (not a guess).
- What context-scoping or lazy-load primitives does your environment natively support (e.g. Claude Code's nested/directory-scoped CLAUDE.md and deferred tool-schema loading via ToolSearch)?
- What would an index+links restructuring of your instruction file look like concretely, if your environment supports on-demand fetch?
- Any harness-specific compaction/context-budget signal you can expose (e.g. Claude Code's "% to compact" statusline figure) that a wrapper like synlynk could hook into for preemptive `/clear`/`/compact`?

Command:
```
synlynk decide "Context-window management R1: audit your native environment's instruction-reload behavior (per-turn vs per-session, with evidence), context-scoping/lazy-load primitives, and any context-budget signal you can expose for preemptive compaction" --panel claude,agy,codex,grok --record
```

**R2 — synthesis.** After R1 lands, feed its recorded decision file back in and ask the panel to converge on one cohesive modification to synlynk's per-harness instruction-writer (the templates `init()` generates for CLAUDE.md/AGENTS.md/GEMINI.md/AI_INSTRUCTIONS.md), plus a shared design for the task-boundary compaction trigger and context-pack mechanism from approach B/C above.

Command (topic references the R1 decision file path once known):
```
synlynk decide "Context-window management R2: given R1's findings (see project-docs/decisions/<r1-decision-file>), synthesize one cohesive modification to synlynk's instruction-writer for each harness, plus a shared task-boundary compaction-trigger and context-pack design" --panel claude,agy,codex,grok --record
```

## Next steps after R2

Once R2's synthesis lands, write an implementation plan (`superpowers:writing-plans`) covering: the instruction-writer template changes, the `generate_context()` size-bounding/summarization change, the compaction-trigger wrapper, and the context-pack format — scoped as a normal dev-preview-track implementation PR (or its own small release), dispatched per the standard role split.

## Out of scope for this spec

- Actually modifying `generate_context()`, `init()`, or any instruction-writer code — deferred to the plan written after R2.
- Billing/quota implications of more frequent `/clear`/`/compact` calls — not raised by the user, not addressed here.
- Any change to the `synlynk decide` CLI itself to natively support multi-round agendas — out of scope; this spec works around that with two sequential calls.
