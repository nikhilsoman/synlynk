# #4929 — Compatibility-preserving CLI complexity facade

## Question

Assess Synlynk’s user-visible CLI complexity and propose compatibility-preserving command grouping, defaults, onboarding, progressive disclosure, documentation, and measurable usability outcomes.

## Verdict

**Single-author assessment.** A compatibility-preserving facade remains the right direction, but the issue’s “~155 commands” baseline is stale: the current `COMMAND_TAXONOMY` contains 234 unique entries across 106 top-level names. The repo already defines eight `CORE_COMMANDS` and five help groups, so the next decision should measure the parser’s actual invocable leaf surface and first-run behavior, then close gaps in the existing facade rather than design a second command system.

## Findings

- The five-POV review documents positioning fragmentation, command overload, multi-file onboarding, role/harness jargon, and false-success trust failures.
- Current `synlynk/taxonomy.py` has 234 unique taxonomy entries: 27 tier 0, 67 tier 1, 110 tier 2, 9 tier 3, and 21 latent.
- The same file already declares eight core commands: `init`, `scan`, `dispatch`, `jobs`, `status`, `doctor`, `heal`, and `probe`.
- It also declares help groups `core`, `operational`, `workflow`, `advanced`, and `admin`.
- Taxonomy row count is not the same as the parser’s visible invocable leaf-command count; the latter was **not verified** in this review.
- The five-track plan records guided quickstart and journey-oriented/generated command docs as shipped work, so proposals must begin with an audit of current behavior.
- The useful metrics remain time to first verified dispatch, onboarding completion, explicit flags per dispatch, command concentration, help-seeking load, and a power-user-usage guardrail.

## Recommended follow-ups

- **New ticket: Yes. Proposed title:** “Baseline the live CLI leaf surface and first-run usability metrics.” Capture parser-derived counts and the five adoption metrics before changing help behavior.
- **New ticket: Yes. Proposed title:** “Audit the eight-command facade against current taxonomy growth.” Verify default help, grouped help, `help --all`, and progressive disclosure.
- **New ticket: No. Proposed title:** “Verify quickstart, dispatch preview, and generated journey docs end to end.” Track this as acceptance work on #4929 unless a concrete defect is found.

## Sources

- [GitHub issue #4929](https://github.com/nikhilsoman/synlynk/issues/4929)
- `docs/strategy/2026-10-02-five-pov-review.md`
- `docs/superpowers/plans/2026-10-04-five-track-code-adjacency-plan.md`
- `synlynk/taxonomy.py`
