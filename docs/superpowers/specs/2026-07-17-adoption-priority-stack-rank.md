# Adoption & GA-Readiness Priority Stack Rank

**Date:** 2026-07-17
**Status:** Prioritized backlog — consolidates open issues, the GTM checklist agenda, and Fable's Horizon 0/1 strategic roadmap into a single stack-ranked list. Not yet broken into specs/plans; items are sourced from existing docs and issues, ranked by urgency, effort, and blocking relationships.

## Sources consolidated

- GitHub issues #202, #260, #261, #262, #263
- `docs/superpowers/specs/2026-07-16-gtm-checklist-agenda.md` (GTM checklist, items 1–7)
- `docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md` (Horizon 0 items 2–4, Horizon 1 items 1–4)
- `project-docs/roadmap.md` (BS-7 benchmark, Public Utilities row)
- `project-docs/todo.md` (`story-b4a90209` flatline, `story-cb2c1d93` git-drift)

## Ranked list (most important first)

1. **Run the BS-7 skill-pack benchmark** — fully designed since 2026-06-27, scheduled for the week of 2026-06-30, now overdue. Lowest effort of anything here (spec already exists), directly named as the HN launch asset. *(roadmap BS-7)*
2. **Fix #202 — `synlynk jobs` stale status display** — parked trust bug that directly contradicts the "every number is trustworthy" gate the whole v0.12.0 theme was built on. Should not still be open once pushing for adoption. *(issue #202)*
3. **Fix #263 — Vizor `viz.py` stage-vocabulary bug** — small, mechanical, patch-sized; three inconsistent stage vocabularies undermine the same trust gate. *(issue #263)*
4. **Ship #262 — surface consolidation (5 daily commands)** — patch-sized, and narrows the CLI front door before the onboarding-hardening work below starts. *(issue #262)*
5. **GTM item 5 — harden onboarding (`scan`/`doctor`/`init`) for robust, scalable host-repo inventory (mono & multi-repo)** — core early-adopter conversion path; sequenced after #262 so it starts from a narrowed command surface. *(GTM checklist)*
6. **GTM item 4 — harden triggers so synlynk is invoked at every developer interaction, in any harness** — core stickiness/retention lever, directly feeds the WAU/D30 gate. *(GTM checklist)*
7. **#261 — unify the two dispatch paths (interactive vs. daemon queue)** — correctness debt that compounds with every new agent; needs its own design pass. *(issue #261)*
8. **Spec + build `flatline` standalone** — named top-of-funnel wedge tool, smaller/more self-contained than `git-drift`, no spec exists yet. *(todo story-b4a90209)*
9. **Spec + build `git-drift` standalone** — second named top-of-funnel tool, needs a manifest schema so it's a larger lift than `flatline`. *(todo story-cb2c1d93)*
10. **#260 — Savings Ledger** — the "headline metric" crown feature; blocks v1.0 GA's positioning line, but needs its own brainstorm/design pass before it can be scoped. *(issue #260)*
11. **GTM item 1 — deep review of every synlynk command + its testing in a live repo scenario** — foundational GA-readiness audit. *(GTM checklist)*
12. **GTM item 2 — articulate where each command sits in the SDLC (GOVERNS)** — taxonomy documentation work. *(GTM checklist)*
13. **GTM item 3 — ensure GOVERNS is the only SDLC framework in use** — consistency cleanup, overlaps with #263's root cause. *(GTM checklist)*
14. **The Benchmark Asset — publish local-vs-frontier quality-parity dataset by task class** — needs real telemetry from the Savings Ledger (#260) to be credible, so it's sequenced after it. *(Horizon 1 item 2)*
15. **Opt-in anonymized telemetry, designed in at GA (consent-first)** — feeds the long-term capability-intelligence flywheel; needed before GA ships. *(Horizon 1 item 3)*
16. **v1.0 GA distribution — PyPI + Homebrew, signed releases + SBOM, docs site** — the actual launch; comes last because it depends on the Savings Ledger, benchmark asset, and telemetry above. *(Horizon 1 item 1)*
17. **GTM item 6 — header/footer fence row at every synlynk response showing capability & cost optimization value** — UX/output-format enhancement, lower urgency. *(GTM checklist)*
18. **GTM item 7 — understand long-term impact of context buildup in large/multi-repos or team/enterprise implementations** — long-horizon research question, not urgent. *(GTM checklist)*
19. **GTM item 7a — rolling context/memory files by size/word-count, with an index/graph/glossary** — sub-item of #18, depends on its research conclusions. *(GTM checklist)*
20. **Monitor: <500 WAU / <25% D30 retention gate by mid-2027** — not a build task, a tracked go/no-go checkpoint for whether this stays a company thesis or reverts to sustainable OSS. *(Horizon 1 item 4, ongoing)*
