# Adoption & GA-Readiness Priority Stack Rank

**Date:** 2026-07-17 (resequenced 2026-07-17 during working session)
**Status:** Prioritized backlog — consolidates open issues, the GTM checklist agenda, and Fable's Horizon 0/1 strategic roadmap into a single stack-ranked list. Not yet broken into specs/plans; items are sourced from existing docs and issues, ranked by urgency, effort, and blocking relationships.

## Sources consolidated

- GitHub issues #202, #260, #261, #262, #263
- `docs/superpowers/specs/2026-07-16-gtm-checklist-agenda.md` (GTM checklist, items 1–7)
- `docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md` (Horizon 0 items 2–4, Horizon 1 items 1–4)
- `project-docs/roadmap.md` (BS-7 benchmark, Public Utilities row)
- `project-docs/todo.md` (`story-b4a90209` flatline, `story-cb2c1d93` git-drift)

## Completed

- ✅ **Fix #202 — `synlynk jobs` stale status display** — already closed before this list's working session started.
- ✅ **Fix #263 — Vizor stage-vocabulary bug (expanded scope)** — merged PR #301 (2026-07-17). Scope grew beyond the original `viz.py`-only framing after a grep pass found the same stale vocabulary live in `synlynk/status.py:CYCLES` (feeding `cli.py`'s `selected_cycle`) and dead code in `synlynk/__init__.py:CYCLE_NAMES`. All four locations reconciled to GOVERNS's canonical seven stages (`goal/open/visualize/execute/release/notify/sustain`); `status.py` now imports `CYCLES` from `hud.py` instead of duplicating it. This substantially satisfies GTM item 3 below for the Python codebase — one known remnant left in an archived brainstorm mockup (`docs/brainstorm/bs16-ecosystem-status/hud-v3.html`), not live product surface, not worth blocking on.

## Resequencing note (2026-07-17)

**BS-7 moved from #1 to the bottom of the list.** Re-reading the BS-7 spec (`docs/superpowers/specs/2026-06-27-bs7-skill-pack-interoperability-design.md`) surfaced that R4 — the "synlynk + Superpowers" round, the whole point of the benchmark — requires `git-drift` active, and `git-drift` doesn't exist yet (no code, no package; it's item 6 below). Phase 0 validation (dispatch Agy/Codex to install Superpowers/GStack in sandboxes and diff instruction files) is also an unstarted prerequisite per the spec. BS-7 is therefore blocked on `git-drift` shipping, not just "low effort and overdue" — it cannot actually execute R4 as designed today.

## Ranked list (most important first)

1. **Ship #262 — surface consolidation (5 daily commands)** — patch-sized, and narrows the CLI front door before the onboarding-hardening work below starts. *(issue #262)*
2. **GTM item 5 — harden onboarding (`scan`/`doctor`/`init`) for robust, scalable host-repo inventory (mono & multi-repo)** — core early-adopter conversion path; sequenced after #262 so it starts from a narrowed command surface. *(GTM checklist)*
3. **GTM item 4 — harden triggers so synlynk is invoked at every developer interaction, in any harness** — core stickiness/retention lever, directly feeds the WAU/D30 gate. *(GTM checklist)*
4. **#261 — unify the two dispatch paths (interactive vs. daemon queue)** — correctness debt that compounds with every new agent; needs its own design pass. *(issue #261)*
5. **Spec + build `flatline` standalone** — named top-of-funnel wedge tool, smaller/more self-contained than `git-drift`, no spec exists yet. *(todo story-b4a90209)*
6. **Spec + build `git-drift` standalone** — second named top-of-funnel tool, needs a manifest schema (BS-7's own spec, Section 2, already defines one) so it's a larger lift than `flatline`. **Promoted in practice: this is now the hard blocker for BS-7's R4 round** — shipping it unblocks the benchmark below. *(todo story-cb2c1d93)*
7. **#260 — Savings Ledger** — the "headline metric" crown feature; blocks v1.0 GA's positioning line, but needs its own brainstorm/design pass before it can be scoped. *(issue #260)*
8. **GTM item 1 — deep review of every synlynk command + its testing in a live repo scenario** — foundational GA-readiness audit. *(GTM checklist)*
9. **GTM item 2 — articulate where each command sits in the SDLC (GOVERNS)** — taxonomy documentation work. *(GTM checklist)*
10. **GTM item 3 — ensure GOVERNS is the only SDLC framework in use** — largely satisfied by the #263 fix above for the Python codebase; remaining work is a sweep of HTML/JS/templates/docs for stray legacy vocabulary. *(GTM checklist)*
11. **The Benchmark Asset — publish local-vs-frontier quality-parity dataset by task class** — needs real telemetry from the Savings Ledger (#260) to be credible, so it's sequenced after it. *(Horizon 1 item 2)*
12. **Opt-in anonymized telemetry, designed in at GA (consent-first)** — feeds the long-term capability-intelligence flywheel; needed before GA ships. *(Horizon 1 item 3)*
13. **v1.0 GA distribution — PyPI + Homebrew, signed releases + SBOM, docs site** — the actual launch; comes last because it depends on the Savings Ledger, benchmark asset, and telemetry above. *(Horizon 1 item 1)*
14. **GTM item 6 — header/footer fence row at every synlynk response showing capability & cost optimization value** — UX/output-format enhancement, lower urgency. *(GTM checklist)*
15. **GTM item 7 — understand long-term impact of context buildup in large/multi-repos or team/enterprise implementations** — long-horizon research question, not urgent. *(GTM checklist)*
16. **GTM item 7a — rolling context/memory files by size/word-count, with an index/graph/glossary** — sub-item of #15, depends on its research conclusions. *(GTM checklist)*
17. **Monitor: <500 WAU / <25% D30 retention gate by mid-2027** — not a build task, a tracked go/no-go checkpoint for whether this stays a company thesis or reverts to sustainable OSS. *(Horizon 1 item 4, ongoing)*
18. **Run the BS-7 skill-pack benchmark** — spec complete since 2026-06-27, but blocked: R4 needs `git-drift` (item 6) and Phase 0 validation is unstarted. Re-run once item 6 ships. *(roadmap BS-7)*
