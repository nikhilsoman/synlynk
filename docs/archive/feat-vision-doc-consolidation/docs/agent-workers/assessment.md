# Synlynk Agent Workers — Capability Assessment

> **Date:** 2026-05-24  
> **Assessed by:** Claude (Sonnet 4.6)  
> **Evidence base:** PRs #218, #228, #230, #231, #235, #244, #245, #250 + devlog entries S-020 through S-028  
> **Policy verdict:** Current allocation maintained — reassess at 5+ PRs per agent.

---

## Codex

**Confidence: 6.5 / 10** *(provisional — 1 PR data point)*  
**Plan:** Free tier (considering Go plan). Practical capacity ~1 PR/week at current quota.

### Evidence — PR #250 (`test/api`: QO-1 integration tests, +543/-60 LOC)

**What was good:**
- `buildApp()` extraction clean and idiomatic — no runtime regressions
- Test coverage comprehensive: OTP auth, upload/confirm, timeline, share token, family invite, consent grant/revoke
- Cascade delete analysis correct — cleanup function safe
- Nullable phone fix in `family.ts` functionally correct

**Findings from review:**
| Severity | Finding | Category |
|----------|---------|----------|
| Must fix | CI workflow `on: push` with no `paths:` filter — every docs commit spins up Postgres+Redis | CI convention gap |
| Must fix | `family.ts` null-phone social users receive `403 phone_mismatch` — misleading error code | Semantic error |
| Should fix | `vitest --exclude` bare path may not match without `**/` prefix | Configuration |
| Should fix | `beforeAll` doesn't flush Redis OTP keys — cross-run flakiness on crashed runs | Test hygiene |
| Nice to have | Shared `ADMIN_PHONE` across both `it()` blocks — hidden ordering dependency | Test design |

**Assessment:** No runtime crashes, no data corruption, no security issues. Bugs were convention gaps and semantic concerns. Solid first PR for a test-infrastructure task. The CI paths filter omission is the most common agent blind spot on this project.

---

## Gemini

**Confidence: 6 / 10**  
**Evidence base:** 8 PRs across frontend, API-adjacent, research, and autonomous execution tasks.

### PR-level evidence

| PR | Task | LOC +/- | Time to merge | Errors found at review | Rework | Autonomy |
|----|------|---------|--------------|----------------------|--------|----------|
| #218 | Global OAuth sign-in | +876/-22 | 21 min | 4 blockers: implicit `any` on `tx`, missing `OAuth2Namespace` augmentation, missing `phone: null` in JWT payload, inappropriate Fitness scope | 0 (Claude fixed directly) | ❌ Claude intervention |
| #228 | 6-box OTP input | +213/-10 | 31 min | 0 | 0 | ✅ Clean merge |
| #230 | Bulk upload-urls + bulk-confirm endpoints | +517/-1 | 6 min | 1 (order preservation bug, surfaced via #231) | 1 (separate fix PR) | ⚠️ Fix required |
| #231 | Bulk import order fix + CLI OAuth | +3456/-15 | 27 min | 1 (CLI OAuth pattern outdated) | 0 (Claude fixed at review) | ⚠️ Claude fix |
| #235 | Dashboard UX refinements | +249/-266 | 53 min | 2: divide-by-zero in trend calc, `LucideIcon` type error | 1 (Gemini fixed on feedback) | ⚠️ Agent fixed |
| #244 | LIVE-002-B onboarding container | +43/-40 | — | 0 | 0 | ✅ Clean merge |
| #245 | LIVE-002-C DateCell alignment | +16/-15 | — | 0 | 0 | ✅ Clean merge |
| #239, #246 | Demo recording (autonomous execution) | n/a | — | 0 | 0 | ✅ Clean output |

### Pattern analysis

**Consistent weaknesses:**
- TypeScript type discipline — implicit `any`, missing type augmentations, wrong argument types
- Arithmetic edge cases — divide-by-zero on first-user data in medical trend chart
- Auth payload completeness — missing `phone: null` in JWT was the most dangerous: a field absent from the token silently breaks downstream phone checks

**Consistent strengths:**
- Ships working code every time — no PR has required full revert or rewrite
- Autonomous execution tasks (Playwright pipelines, research reports) come back clean
- Responds to review feedback and pushes fixes when asked
- Small focused PRs (#244, #245) are essentially error-free

**Risk gradient by task type:**

| Task type | Gemini confidence | Notes |
|-----------|------------------|-------|
| UI component (isolated) | 8/10 | OTP input, DateCell, onboarding container — clean |
| Frontend with calculations | 6/10 | Trend calc divide-by-zero; arithmetic in health data is high-stakes |
| API endpoints | 6/10 | Bulk upload was functional but needed an order fix |
| Auth / token payloads | 4/10 | Missing JWT field, wrong OAuth scope — review mandatory |
| Autonomous execution | 8/10 | Demo pipeline, research — strongest domain |

---

## Allocation Policy (current — maintained)

| Domain | Agent | Confidence | Review gate |
|--------|-------|-----------|-------------|
| Backend, infra, auth, FHIR, payments | Claude | — | — |
| Frontend UI components, data viz | Gemini | 6/10 | Required before merge |
| Auth flows, token payloads | Claude | — | Gemini must not own alone |
| Research spikes, autonomous execution | Gemini | 8/10 | Light review |
| Test infrastructure (API, E2E) | Codex | 6.5/10 | Required before merge |
| CI/CD, Pulumi infra | Claude | — | — |

**Policy trigger:** Reassess allocation after Codex accumulates 5 PRs or after Gemini's next auth-adjacent PR.

---

## Practical notes

**Codex quota:** On free plan — approximately 1 PR/week capacity. Assign at start of week with a self-contained spec; pick up the PR at end of week. Do not assign anything on the critical path for a same-week deploy. Consider Go plan to increase cadence on QO-* testing tasks before committing to Plus.

**Review overhead:** Both agents require ~15–30 min code review before merge. Factor this into sprint planning — agent PRs are not zero-cost.

**CI paths filter:** Both agents have omitted `paths:` filters when creating GitHub Actions workflows. Add this to the per-agent brief (GEMINI.md, future CODEX.md) as an explicit rule.
