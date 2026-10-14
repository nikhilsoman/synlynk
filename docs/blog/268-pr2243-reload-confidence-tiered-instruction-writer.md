---
title: "PR #2243 — The instruction writer now knows which harnesses pay per turn"
date: 2026-10-14
series: "Building the OS for Multi-Agent Development"
post: 268
pr: "#TBD"
status: open
author: "synlynk team"
version: "0.25.0"
tags: [posts]
type: pr
---

## The Broader Goal at the End of the Previous PR

`goal-e79062e8` is about bounding context growth instead of reacting to forced
compaction. The R1 decide-panel audit established something the repo had never
written down: instruction-file reload behaviour differs per harness. Claude
loads `CLAUDE.md` once per session. Agy and Grok have their instruction file
resent on every turn. Codex showed no evidence of per-turn reload, but with no
independent confirmation method — provisional, not confirmed.

R2 synthesised that into a plan with four slices. Four PRs landed on
2026-10-13 against the integration branch: #2247 stopped writing a phantom
Grok-specific instruction file, #2248 moved this repo's own policy SOPs out of
root `CLAUDE.md` into `docs/sop/`, #2249 added the task-boundary compaction
trigger, #2250 added job-scoped context packs.

## Strategic Shifts in This PR (if any)

No shift in direction — a correction of record. The reload tiers R2 decided
were committed as a dict (`HARNESS_RELOAD_TIER`) and asserted by one test, and
nothing read it. `synlynk/instructions.py` had zero references to
`reload_confidence`, `confirmed_per_turn`, or `confirmed_per_session` outside
that dict. Every harness still got the same template body, so the per-turn
harnesses paid the same resident cost as the per-session one.

That is the `gh:#1831` failure mode in a different costume: a decision recorded
in a document (or, here, in a constant) while the code that was supposed to act
on it kept its old behaviour. Having the tier written down is not the same as
having it applied.

## What This PR Shipped

`synlynk/instructions.py` now tiers its own output.

**Tier lookup.** `get_reload_confidence(tool)` resolves a tier for any harness
or editor tool. Core harnesses come from R2's record. Cursor, Copilot and
Windsurf were never audited, so they resolve to a new
`unaudited_assume_per_turn` tier rather than silently inheriting the cheap one.
`pays_resend_cost_per_turn()` collapses the tiers into the one bit the writer
needs.

**Tiered bodies.** `render_harness_instructions(harness)` renders a lean body
for per-turn harnesses — identity/attribution, branch naming, critical
guardrails, and a load-on-demand SOP index pointing at `AI_INSTRUCTIONS.md` and
the `docs/sop/*.md` files #2248 created. Session-tier harnesses additionally get
the session protocol and the domain-ownership table inline, because they pay for
that text once per session. Policy SOP prose is inlined in no tier at all; it is
referenced from the index. Each generated file opens with a provenance comment
recording its tool, tier, body shape and `gh:#2243`, so the shape of a file is
explainable from the file itself.

**Shared files resolve to their most expensive reader.** Since #2247, Grok reads
Codex's `AGENTS.md`. A file is only as cheap as the costliest harness that loads
it, so `resolve_file_reload_tier("AGENTS.md")` returns `confirmed_per_turn` and
`AGENTS.md` gets the lean body even though Codex alone would have qualified for
the full one. The banner records that resolution explicitly, including that
Codex's own tier is still provisional, and the identity block tells both readers
the file is shared so edits stay harness-neutral.

**Filename table.** `HARNESS_INSTRUCTION_FILENAMES` is sourced from
`CORE_INSTRUCTION_FILES` (claude → `CLAUDE.md`, agy → `GEMINI.md`, codex →
`AGENTS.md`, grok → `AGENTS.md`) rather than duplicated, so
`get_instruction_file_for_agent()` and the writer cannot drift apart.
`_build_templates()` derives its per-harness keys from that table instead of
hardcoding three filenames and three near-identical header calls.

Measured on the generated output: `CLAUDE.md` 62 lines, `GEMINI.md` 34,
`AGENTS.md` 36. Before this change all three were the same ~20-line header, so
the absolute saving is small today — the point is that the tier is now the thing
that decides, which is what makes the next content addition safe. Anything added
to the session-tier body no longer lands in the files that are resent every turn.

Tests in `tests/test_instructions.py` cover tier lookup for all four harnesses
plus the unaudited default, leanness of the agy/grok bodies (no inlined session
or SOP prose, under 40 lines), richness of the claude/codex bodies, the
shared-file tier resolution, filename resolution per harness, and the absence of
a Grok-specific filename in every generated artefact. Two older assertions that
pinned the exact prose of the superseded "Shared synlynk Protocol" pointer were
updated to assert the SOP index instead.

## Brainstorm Visuals Used

None. The binding artefacts are the R2 decision record (`dec-0d7e75e0`), the
spec `docs/superpowers/specs/2026-10-12-context-window-optimization-design.md`,
and the plan `docs/superpowers/plans/2026-10-13-context-window-optimization.md`.

## What This Achieved on the Path to Autonomy

Per-harness cost asymmetry is now a property the code acts on, not a note in a
decision file. A harness that pays per turn gets a lean file by construction.

## The New Goalpost

Two gaps stay open and are deliberately out of scope here. `run_parity_remediation()`
in `synlynk/parity.py` and the SOP-fence repair path in `synlynk/probe.py` still
inject the full SOP body into all three per-harness files regardless of tier,
which partly re-inflates `GEMINI.md` in adopted repos. And this repo's own root
`GROK.md` is still a committed file nothing reads since #2247 — dead weight with
a domain-ownership table that was never merged into `AGENTS.md`. Both want their
own small PRs.

## Related Docs

- `docs/superpowers/specs/2026-10-12-context-window-optimization-design.md`
- `docs/superpowers/plans/2026-10-13-context-window-optimization.md`
- `docs/sop/capability-task-allocation.md`, `docs/sop/pr-review-discipline.md`, `docs/sop/worktree-and-cost-hygiene.md`
- GOVERNS story-c04f64b1, goal-e79062e8
