# Synlynk Agent Performance Tracker

> Per-task heuristic metrics for agent contribution tracking. Input to Synlynk agent evaluation.  
> **Updated:** 2026-05-24 | **Maintainer:** Claude (update at PR merge or issue close)

---

## Scoring Schema

### Raw metrics (collected per issue/PR)

| Metric | Source | Notes |
|--------|--------|-------|
| `effort` | Issue label (`effort:XS/S/M/L/XL`) | Estimated at assignment |
| `loc_added` | `gh pr view --json additions` | Lines added |
| `loc_deleted` | `gh pr view --json deletions` | Lines deleted |
| `loc_net` | `additions - deletions` | Net code change |
| `time_to_pr_h` | PR `createdAt` − issue assigned timestamp | Hours; `~` if estimated |
| `time_to_merge_h` | PR `mergedAt` − PR `createdAt` | Hours including review wait |
| `review_cycles` | Push counts after first review request | 0 = clean first pass |
| `errors_critical` | Review findings: data loss, security, crash | Count |
| `errors_major` | Review findings: wrong behaviour, type errors blocking compile | Count |
| `errors_minor` | Review findings: naming, style, non-blocking | Count |
| `rework_type` | `agent` \| `claude` \| `none` | Who applied the fixes |
| `pr_review_comments` | `gh api pulls/:pr/reviews \| length` | Formal review count |
| `tokens_est` | From `rxcc_costs.md` session row | `~` prefix = estimated |

### Derived scores

```
quality   = max(0, 10 − (3 × errors_critical) − (2 × errors_major) − (1 × errors_minor) − (0.5 × review_cycles))
velocity  = (loc_added + loc_deleted) / time_to_pr_h          # LOC per hour; omit if time unknown
autonomy  = 2 (clean merge) | 1 (agent fixed on feedback) | 0 (Claude intervention required)
composite = (quality × 0.5) + (autonomy × 2.5) + min(velocity/50, 2.5)   # max 10
```

> `composite` is indicative only — weight it against `effort` and task type. A 10-LOC fix can score higher than a 500-LOC feature; normalise within effort tier when comparing.

---

## Data

### Gemini

| Issue | PR | Title | Effort | LOC+/- | Time→PR (h) | Time→Merge (h) | Rev. cycles | Err C/M/m | Rework | Review cmts | Tokens est | Quality | Velocity | Autonomy | Composite |
|-------|----|-------|--------|--------|------------|---------------|-------------|-----------|--------|------------|-----------|---------|----------|----------|-----------|
| #179 | #218 | Global OAuth sign-in | L | +876/-22 | ~ | 0.3 | 0 | 1/2/1 | claude | 0 | ~$2 | 3.0 | ~45 LOC/h | 0 | 3.5 |
| #82 | #228 | 6-box OTP input | S | +213/-10 | ~ | 0.5 | 0 | 0/0/0 | none | 1 | ~$1 | 10.0 | ~45 LOC/h | 2 | 7.5 |
| #224 | #230 | Bulk upload-urls + bulk-confirm | M | +517/-1 | ~ | 0.1 | 1 | 0/1/0 | claude | 0 | ~$1 | 7.5 | ~90 LOC/h | 0 | 4.5 |
| #225/#226 | #231 | Bulk import order fix + CLI | M | +3456/-15 | ~ | 0.4 | 0 | 0/1/0 | claude | 0 | ~$1 | 7.5 | ~870 LOC/h | 0 | 4.5 |
| #233 | #235 | Dashboard UX refinements | M | +249/-266 | ~ | 0.9 | 1 | 0/1/1 | agent | 1 | ~$2 | 6.5 | ~57 LOC/h | 1 | 5.5 |
| #242 | #244 | LIVE-002-B onboarding container | XS | +43/-40 | ~ | — | 0 | 0/0/0 | none | 0 | ~$0.50 | 10.0 | — | 2 | 7.5 |
| #243 | #245 | LIVE-002-C DateCell alignment | XS | +16/-15 | ~ | — | 0 | 0/0/0 | none | 0 | ~$0.50 | 10.0 | — | 2 | 7.5 |
| #185–191 | — | Research: clinical/nutrition/fitness/India OCR | M | n/a | ~ | — | 0 | 0/0/0 | none | 0 | ~$1 | 10.0 | — | 2 | 7.5 |
| #239 | — | Demo recording V1 (autonomous) | M | n/a | ~ | — | 0 | 0/0/0 | none | 0 | ~$1 | 10.0 | — | 2 | 7.5 |
| #246 | — | Demo recording V2 (autonomous) | M | n/a | ~ | — | 0 | 0/0/0 | none | 0 | ~$1 | 10.0 | — | 2 | 7.5 |

**Gemini running totals (code PRs only):**
- Mean quality (code): **7.4** (excl. research/execution)
- Mean quality (all): **8.2** (incl. research/execution)
- Weighted quality by effort: **6.5** (L/M PRs drag the average)
- Issues requiring Claude intervention: **3 / 7** code PRs (43%)
- Total LOC contributed (net): **~4,819**

---

### Codex

| Issue | PR | Title | Effort | LOC+/- | Time→PR (h) | Time→Merge (h) | Rev. cycles | Err C/M/m | Rework | Review cmts | Tokens est | Quality | Velocity | Autonomy | Composite |
|-------|----|-------|--------|--------|------------|---------------|-------------|-----------|--------|------------|-----------|---------|----------|----------|-----------|
| #131 | #250 | QO-1 API integration tests | L | +543/-60 | ~ | open | 0 | 0/2/3 | pending | 0 | ~$2 | 5.5 | — | pending | pending |

**Codex running totals:**
- Mean quality: **5.5** (1 PR, provisional)
- Issues requiring Claude intervention: **0 / 1** (pending merge)
- Total LOC contributed (net): **~483**

---

## Trend view (rolling, last 10 tasks per agent)

```
Gemini quality by task (chronological):
  #179 OAuth    ████░░░░░░  3.0  ← worst: JWT + TypeScript blockers
  #82  OTP      ██████████  10.0 ← clean
  #224 BulkAPI  ███████░░░  7.5
  #225 BulkCLI  ███████░░░  7.5
  #233 UX       ██████▌░░░  6.5
  #242 LIVE-B   ██████████  10.0 ← clean
  #243 LIVE-C   ██████████  10.0 ← clean
  Research      ██████████  10.0 ← clean

Codex quality by task (chronological):
  #131 QO-1     █████▌░░░░  5.5  ← first PR, provisional
```

---

## Update protocol

Add a row when:
- A PR is **merged** (fill all columns; mark `~` estimates where exact data unavailable)
- An issue is **closed without a PR** (research, execution tasks — fill effort/tokens/autonomy)

Update `tokens_est` retroactively when session cost data is available in `rxcc_costs.md`.

**Git log command for LOC:** `gh pr view <N> --json additions,deletions`  
**Comment count:** `gh api repos/Dialify/rxcc/pulls/<N>/reviews | jq 'length'`  
**Review cycles:** count commits after first review via `gh pr view <N> --json commits | jq '[.commits[].committedDate] | length'` minus commits before review.

---

## Glossary

| Term | Definition |
|------|-----------|
| **errors_critical** | Bug that could cause data loss, security regression, production crash, or wrong medical data stored |
| **errors_major** | Bug causing incorrect behaviour, TypeScript compile failure, or logic error visible to users |
| **errors_minor** | Non-blocking: naming, convention, style, plausible-but-low-probability risk |
| **rework_type: claude** | Claude fixed the errors directly on the branch — agent did not self-correct |
| **rework_type: agent** | Agent pushed fixes after review feedback |
| **rework_type: none** | PR merged without error fixes needed |
| **autonomy 2** | Merged clean — no review findings requiring changes |
| **autonomy 1** | Agent fixed issues on feedback — productive loop |
| **autonomy 0** | Required Claude intervention — agent could not or did not self-correct |
