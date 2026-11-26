# #4935 — Context-window management R2

## Question

Synthesize the R1 context findings into a degrade-safe instruction-writer change, task-boundary context pack, compaction trigger, and empirical probes for unconfirmed harnesses.

## Verdict

**Derived from the recorded synthesis.** Ship the lean index-and-links instruction format, task-scoped context pack, and wrapper-owned task-boundary regeneration together without waiting for Codex or Grok reload probes. Keep both harnesses on the worst-case `unconfirmed` treatment until the specified probes produce at least five merged-job samples.

## Findings

### Recorded panel synthesis (verbatim)

> Decision: Adopt the hybrid synthesis — ship one degrade-safe instruction-writer change now, don't gate on Codex/Grok probes.
>
> **Instruction-writer:** Restructure every `init()`-generated template (CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md) into an index-and-links format: a lean resident core (harness identity, repo hygiene/branching/commit trailers, routing pointers, shared task-boundary rules) under ~40 lines, with domain SOPs (PR review checklist, Herdr conventions, etc.) extracted to on-demand files under `docs/sop/`. Parameterize by a `reload_confidence` enum — `confirmed_per_turn` (Agy), `confirmed_per_session` (Claude), `unconfirmed` (Codex, Grok). `unconfirmed` defaults to the Agy worst-case treatment by construction, not by estimate, until a probe confirms otherwise. This is the one change that correctly resolves R1's wrapper-vs-model-side finding against the per-harness reload uncertainty: the generator can't special-case what it hasn't measured, so "unknown" must cost the same as "expensive."
>
> **Context-pack:** Dispatch wrapper assembles `.synlynk/context-pack/<task-id>.md` at task-boundary time — GOVERNS linkage, current story/goal, last devlog entry, diff-relevant file list only, not the full roadmap/memory/todo concatenation `generate_context()` produces today. Instruction files reference it by path; a harness that reloads its instructions every turn now reloads a pointer, not the payload.
>
> **Compaction trigger:** Lives in the wrapper, fires at task boundaries (dispatch job start/end, story sign-off, PR open/merge) — not on a token-percentage heuristic. `exec_command()` regenerates the pack and archives the prior one at each boundary, bounding staleness by task granularity.
>
> **Empirical probes (ship alongside, non-blocking):**
> - *Codex:* fixed-transcript multi-turn dispatch job; record/compare per-turn input-token telemetry from `cost_entries`, and separately mutate `AGENTS.md` mid-session to see if the change takes effect without restart. Flat tokens + no-effect-without-restart ⇒ per-session caching; growing tokens or live pickup ⇒ per-turn reload.
> - *Grok:* same telemetry instrumentation plus a one-line capability probe in `capability_probe.py` (alongside `CAP_GH_WRITE`) checking whether its native environment exposes any persistent-context/caching/compaction primitive at all — currently unknown, not just unmeasured.
>
> Both probes land in the same PR as the generator/wrapper change. Codex/Grok only move off `unconfirmed` once they clear ≥5 merged-job samples under the Empirical Capability Assessment Policy — no earlier.

- The issue-cited R1 decision path is absent at its stated location on this branch; its contents are **not verified** here.
- The issue-cited design spec is absent at its stated live path; an archived copy was read and matches the synthesis’s problem framing.

## Recommended follow-ups

- **New ticket: Yes. Proposed title:** “Generate lean harness instruction indexes and task-scoped context packs.”
- **New ticket: Yes. Proposed title:** “Probe Codex and Grok instruction reload behavior with merged-job telemetry.”
- **New ticket: No. Proposed title:** “Gate reload-confidence promotion on five merged-job samples.” Include this in the implementation acceptance criteria.

## Sources

- [GitHub issue #4935](https://github.com/nikhilsoman/synlynk/issues/4935)
- `docs/archive/worktree-hygiene-2026-10-15/docs/superpowers/specs/2026-10-12-context-window-optimization-design.md`
- Cited but absent: `project-docs/decisions/2026-10-12-context-window-management-r1-audit-your.md`
