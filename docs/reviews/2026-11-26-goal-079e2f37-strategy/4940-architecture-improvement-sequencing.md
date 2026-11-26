# #4940 — Architecture improvement sequencing

## Question

Rank the Architect POV improvements by fastest practical execution, including effort, deferral risk, and dependencies.

## Verdict

**Derived from the recorded synthesis.** Stop observed data loss and unbounded state/worktree growth first, then replace fragile telemetry before refactoring the dispatch pipeline. Run the isolated visualization split in parallel, and defer canonical-state consolidation and CLI packs until the required seams and product evidence exist.

## Findings

### Recorded panel synthesis (verbatim)

> Both panels agree on the ends of the list: stop the active data loss first, and defer the CLI reduction last. They differ on the middle. I resolved those differences as follows.
>
> - **State GC vs. state.db consolidation:** Claude scoped `state.db` scaling as retention and GC (S). Codex scoped it as full single-owner consolidation (L). These are two separate items. GC ships now. Consolidation waits until after the dispatch refactor, because the pipeline defines the transaction boundaries.
> - **Worktree proliferation:** only Codex raised it. It shares a cleanup and lifecycle mechanism with state GC, so I folded it into item 1.
> - **Telemetry vs. regen guard:** Codex ranked telemetry first. Claude ranked the regen guard first. The guard is a small defensive fix for observed data loss (PR #1878). Telemetry is per-harness work with a larger payoff. I put the guard first and telemetry right behind it, since they don't depend on each other.
> - **`viz.py` timing:** Codex made it depend on the telemetry and state contracts. Claude said it has none. The `status --json` seam already exists, so I treat it as parallel work.
>
> These assessments come from section 2 of the review. Neither panel checked them against the code.
>
> **Ranked list, fastest practical execution first**
>
> | # | Item | Effort | Depends on | Risk if deferred |
> |---|---|---|---|---|
> | 1 | State and worktree GC: `synlynk gc`, a size budget, and a worktree retention policy (#1831) | S | none | Medium-high. The 8.3 GB `state.db` shards keep growing silently. |
> | 2 | Regen-bug guard: diff `costs.md` and `memory.md` against `origin/main` before writing, plus round-trip tests. Ship in the same PR as 1 if practical. | S | none | High. Data loss has already happened. |
> | 3 | Structured telemetry and `verify_effects` as the completion oracle, using `--output-format json` for Claude and Codex first, with scraping kept as a fallback | S–M | none (it touches the cost ledger, so land 2 first) | High. Stdout scraping drives the false-status and sentinel incidents. |
> | 4 | `viz.py` split by domain, consuming `status --json` | M | none (run in parallel) | Low. It is isolated. |
> | 5 | `dispatch_agent` pipeline, a `DispatchRequest` dataclass and a `HarnessAdapter` | M–L | 3, plus characterization tests written first | Medium. Every change gets slower and riskier, but nothing is broken today. |
> | 6 | `state.db` consolidation: single workspace owner, DAO and unit-of-work transactions, migrations, and making SQLite canonical with Markdown as a generated export | L | 2 and 5 | Medium. The contention and lock-cascade risk remains. |
> | 7 | CLI core/packs split | L | 4 and 5, usage telemetry, and a product decision | Medium, as maintenance drag. It is not urgent. |
>
> Decision: Execute in the order above. Items 1 and 2 go first as one small PR, since they stop the active data loss and disk growth. Item 3 follows, and item 4 runs alongside both. Item 5 comes only after item 3 and a set of characterization tests, because the `dispatch_agent` refactor is the riskiest change. Items 6 and 7 are deferred until the seams from items 3 to 5 exist. Item 7 additionally needs a product decision backed by usage data. Per the global role split, implementation goes to Codex and Grok through `synlynk dispatch`, with Claude as reviewer. I haven't persisted this to the devlog or run `decide --record`. Say if you want either.

## Recommended follow-ups

- **New ticket: Yes. Proposed title:** “Add state/worktree GC and generated-ledger regen guards.”
- **New ticket: Yes. Proposed title:** “Replace completion scraping with structured telemetry and verified effects.”
- **New ticket: Yes. Proposed title:** “Split viz.py by domain over status JSON.”
- **New ticket: Yes. Proposed title:** “Refactor dispatch_agent into a characterized request pipeline.”
- **New ticket: No. Proposed title:** “Defer canonical-state consolidation and CLI packs behind telemetry and dispatch seams.” Record as dependency gates rather than immediate work.

## Sources

- [GitHub issue #4940](https://github.com/nikhilsoman/synlynk/issues/4940)
- `docs/strategy/2026-10-02-five-pov-review.md`
