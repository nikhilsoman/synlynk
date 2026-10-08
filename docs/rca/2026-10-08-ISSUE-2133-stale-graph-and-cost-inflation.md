# ISSUE-2133: Stale Graphify graph + disabled sparse worktrees — cost inflation is not scope-driven

- **Severity:** Sev2/3 — platform-health/cost observability, not a correctness bug. Follows the
  `2026-09-09-ISSUE-1531-dispatch-token-inflation.md` precedent format rather than a full LIVE-N RCA.
- **Issue:** gh:#2133 (cross-referenced: gh:#1937 cost-inflation record, gh:#2130, gh:#2121)
- **Date:** 2026-10-08
- **Status:** Partially remediated. Fix #1 (sparse worktrees) already shipped via merged PR #2134.
  Fixes #2-#3 below are still open.

## Finding

Four separate things were checked as candidate drivers of the recurring ~80x-style dispatch
cost-inflation pattern (gh:#1937):

1. **Context packs are fine.** `synlynk/pack.py`'s `_cut_to_token_budget` enforces a real, tight
   default budget (1500 tokens) on every dispatch prompt. This is not the driver — ruled out.
2. **`worktree.mode` defaulted to `"full"`**, not sparse, because `.synlynk/config.json` simply had no
   `worktree.mode` key set at all (the "sparse" code path existed but was never turned on). **Fixed**:
   PR #2134 (merged 2026-10-08) added `"worktree": {"mode": "sparse"}` to config — a clean 4-line
   change, confirmed via `gh pr diff 2134`.
3. **The Graphify dependency graph (`.synlynk/graphify-out/graph.json`) was 195 commits / 13 days
   stale.** The auto-refresh logic in `synlynk/dispatch.py`'s `_format_prompt_for_agent` (~line 2023)
   only regenerates the graph when the file is *absent*, never when it is merely stale relative to
   HEAD. Still open.
4. **Both the graph-extraction and pack-synthesis steps around that code are wrapped in bare
   `except Exception: pass`.** A silent failure in either path degrades a dispatch's context quality
   with zero visible signal — no log line, no sentinel flag, nothing. Still open.

## Why useful work was marked expensive, not failed (the ISSUE-1531 pattern, inverted)

ISSUE-1531 documented genuine work being marked *failed*. This issue is the cost-side mirror: genuine,
*correctly completed* work being billed at wildly inflated token counts for reasons that turned out to
have nothing to do with task ambiguity or scope creep. The clearest data point: **job-1c91a47c**, a
single-key JSON edit to `.synlynk/config.json` (the sparse-worktree fix itself, PR #2134) — a
zero-ambiguity, zero-exploration-surface task — cost **$2.19 actual vs. $0.09 estimated**
(701,531 input tokens), and tripped the TOKEN_BLOAT sentinel (707,232 tokens / 1 touched file). A task
this trivial having no plausible scope-driven explanation for 700K+ input tokens points directly at
context assembly (stale/bloated graph data, full non-sparse worktree context, or both) rather than at
the model "doing too much work." This reframes gh:#1937's prior finding that cost-inflation issues
keep closing "without a hard cap" — the cap isn't the missing piece; the context-assembly pipeline
feeding the dispatch is.

## Affected components

- `synlynk/pack.py` — confirmed healthy, no change needed.
- `.synlynk/config.json` — `worktree.mode` now explicitly `"sparse"` (PR #2134, merged).
- `synlynk/dispatch.py` `_format_prompt_for_agent` (~line 2023) — graph staleness check, still absent.
- Graph-extraction and pack-synthesis exception handling around the same code path — still silent.
- `.synlynk/graphify-out/graph.json` — the stale artifact itself; needs a staleness policy (e.g.
  regenerate if `git rev-list HEAD --count` has advanced by more than N commits since the graph's own
  recorded commit, or simply on every daemon poll tick / every M dispatches).

## Prioritized remediation

- **Done — P0:** Enable sparse worktree mode (PR #2134, merged 2026-10-08).
- **P1:** Add a staleness check to the Graphify auto-refresh trigger in `_format_prompt_for_agent` —
  regenerate when stale (commit-count or mtime threshold), not only when the file is missing.
- **P1:** Replace the bare `except Exception: pass` around graph-extraction/pack-synthesis with at
  minimum a logged warning (ideally a sentinel-visible counter), so a silently-degraded dispatch
  context is observable instead of invisible.
- **P2:** Once P1 lands, re-run a deliberately trivial single-file-edit dispatch (same shape as
  job-1c91a47c) and compare actual token count against the $0.09-class estimate to confirm the fix
  actually closes the gap, rather than assuming it from code inspection alone.
- **P2:** Fold this into the gh:#1937 cost-inflation record as a closing note once P1/P2 are verified
  — this is very likely the actual mechanism behind that issue's recurring pattern, not merely a
  contributing factor.

## Verification

- PR #2134's effect: not yet empirically re-measured post-merge (no trivial-edit dispatch has been
  run against the new sparse-mode config yet). Treat "sparse mode enabled" as a shipped mitigation,
  not a confirmed fix, until a same-shape trivial task is re-run and shows materially fewer input
  tokens than job-1c91a47c's 701,531.
- Graph staleness and silent-exception fixes: no code changes yet — verification is pending their
  implementation.
