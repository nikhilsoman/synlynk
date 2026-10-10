# Consolidated Roadmap + Home Harness Transition (2026-10-07)

## 0. Why this document exists

This session (Claude, interactive PM role) hit a hard capability ceiling: the Claude Code
auto-mode classifier blocked a protocol-authorized bulk worktree cleanup (`git worktree remove`
/ `git branch -D` / `git push origin --delete` across 54 confirmed-safe worktrees — see the audit
below) with "Interfere With Workloads," and separately blocked a plain read-only `ls && head &&
git status && git branch` chain with the same reason. Both actions were pre-authorized by this
repo's own Worktree Hygiene Protocol and are not destructive relative to anything live. This is
the second class of classifier-scope failure surfaced this week (the first: `gh issue create`
blocked even when routed through role-scoped tokens — see Track 3's "recurring autonomous-flow
friction" item in the five-track plan). Nikhil's conclusion, stated directly: Claude's capability
as home harness is compromised enough to warrant moving the interactive PM/conductor seat to a
different harness.

This document is the handoff artifact: a consolidated agenda across cleanup, the two open
strategic reviews, and five new forward-looking initiatives, plus a harness recommendation and a
ready-to-paste prompt for whichever harness becomes the new home conductor.

---

## 1. Harness Recommendation: Codex

**Recommendation: move the home/interactive-conductor seat to Codex. Keep Grok as a secondary
implementation lane (not home). Do not promote Agy to home.**

Reasoning, from this repo's own accumulated evidence (`MEMORY.md` + CLAUDE.md), not vibes:

| Harness | Evidence | Verdict for home/PM seat |
|---|---|---|
| **Codex** | Already the *default* for GitHub-write-heavy work — CLAUDE.md's "GitHub write routing (#426)" section: "Route any task that requires GitHub write actions to **Codex by default**, Claude/Agy as fallbacks" (verified live, job-836e13a4). Resolved its own base-branch bug cleanly (#616/#617). No open reliability complaints in memory. | **Promote to home.** PM/review/deploy is mostly git/gh plumbing — Codex's strongest documented lane. |
| **Grok** | Two distinct reliability concerns on record: (a) session-expiry/billing (402) auth failures (PR #880, `feedback_grok_auth_agy_fallback.md`); (b) mid-task `stopReason: cancelled` on **review**-type dispatches specifically, 3x on PR #1186 (`grok-dispatch-cancelled-pattern.md`) — looks like a turn-budget/infra cutoff, not a content problem, but it's exactly the review/PM workload a home harness would run constantly. The LIVE-13 sandbox-denial bug *was* fixed (2026-09-22, PRs #1734/#1735) but that's a different failure mode than the cancellation pattern. | **Keep as implementation lane** (canvas/js/infra per existing routing), not home — unresolved review-task reliability risk. |
| **Agy** | `feedback_prefer_codex_grok_over_agy.md`: "Agy repeatedly hits 'timeout waiting for response'; default to Codex/Grok... don't retry Agy twice on same task." | **Do not promote.** Standing guidance already deprioritizes Agy for exactly this reason. |

Caveat per this repo's own **Empirical Capability Assessment Policy** (CLAUDE.md, 2026-10-04):
this recommendation is itself a reasoned interim default, not a 5-sample-verified routing
decision — none of Claude/Codex/Grok/Agy have ≥5 merged-job samples on the *PM/review/deploy*
task type specifically (only on implementation task types). Treat this as the next interim
default to run under the same empirical-reassessment discipline once `synlynk capability report`
(gh:#1993) ships. The classifier failures that triggered this move are a Claude-Code-harness-level
problem (not a synlynk-application bug), so moving host harness plausibly routes around this
specific failure class — but should still be watched for the new home harness's own failure
modes (Grok's cancellation pattern, Codex's own sandboxed-`pr-check` bug noted in open issues)
rather than assumed solved.

---

## 2. Priority 0 — Worktree Audit Cleanup (ready to execute, blocked only by classifier)

Full periodic audit (Worktree Hygiene Protocol step 3) is **complete** — categorization done,
nothing deleted yet:

- **Bucket A — 4 active, do not touch:** `.worktrees/docs+five-track-status-refresh` (PR #2084,
  open), `worktrees/docs-blog-pr1967` (PR #1970, open), `worktrees/job-2a2b25fa` (PR #2081, open,
  branch `test/grok/2062-adapter-conformance-suite`), `.worktrees/docs+three-lens-followups-design`
  (no PR, design work in flight).
- **Bucket B — 33 clean, stale-baseline, zero diff vs `origin/main`, no PR:** trivially safe.
- **Bucket C — 14 dirty, abandoned capability-probe scratch** (`story-adhoc-*` jobs, exit
  `1 unknown_contract`, 0 files reported touched, uncommitted edits to a shared
  `synlynk/examples.py` playground never committed to any branch): safe per Worktree Hygiene
  Protocol item 4 (one-off diagnostic dispatches that made no real changes).
- **Bucket D — 7 "real diff, no PR," individually content-diff-verified, all confirmed duplicates
  or superseded drafts:**
  - `job-1c15cfb7`, `job-8065e86b` → superseded drafts of merged PR #2083
  - `job-1f39d517`, `job-3cdfe453` → superseded drafts of merged PR #2082 (byte-identical
    `synlynk/capability.py`)
  - `job-291e3bb1` → byte-identical duplicate of the still-open PR #2081's own worktree content
  - `job-bdb0043a`, `job-cea2890a` → superseded drafts of merged PR #2080 (`job-cea2890a`'s
    `config_schema.py` byte-identical to `origin/main`)
  - **None require archiving under protocol item 2a** — nothing here is genuinely unique
    unmerged work.

**54 of 58 non-main worktrees are confirmed safe to delete** (Buckets B+C+D). The exact branch
list (all `dispatch/<harness>/job-*`, plus `dispatch/codex/job-291e3bb1` and
`dispatch/grok/job-3cdfe453`'s actual ref `fix/grok/2063-empirical-routing-fallback-main`) and a
ready-to-run cleanup script are saved at:
`/private/tmp/claude-501/-Users-nikhilsoman-dev-synlynk/bf5a8b29-83bf-4df8-b8a2-3e96ef93325e/scratchpad/cleanup_worktrees.sh`
(session-scoped scratch path — copy it out if it needs to survive past this session). The script:
removes each worktree (`git worktree remove --force` after a final dirty-check), deletes the
local branch (`git branch -D`), and deletes the matching remote branch if `git ls-remote --heads
origin <branch>` shows it exists.

**This is the first thing the new home harness should run** — it's pure mechanical git plumbing,
exactly Codex's strongest documented lane, and was blocked here purely by the Claude Code
classifier, not by anything about the operation itself.

---

## 3. Priority 1 — Five-Track Roadmap: remaining open items

Source: `docs/superpowers/plans/2026-10-04-five-track-code-adjacency-plan.md` (refreshed
2026-10-06, PR #2084). Already-closed items are omitted here — see that doc for full history.

**Still open (issue exists):**

| # | Track | Title | Note |
|---|---|---|---|
| #1993 | 1 — Dispatch/Harness | Capability report → task_allocation routing | Highest-leverage open item; makes Grok/Muse calibration self-service. Blocked on #1926. |
| #1926 | 3 — Data/Display | state.db consolidation | Blocks #1993's aggregate measurement across 11,000+ sharded state.db files (gh:#1831). |
| #1937 | 3 — Data/Display | Cost-inflation record ($133/44M tokens) | #1969's fix (PR #2021) did not reduce Codex job costs ($5.58–$15.93/job observed) — needs fresh investigation, not a re-close. |
| #2023 | 3 — Data/Display | Root-cause ticket for write-through regen bug family | Check whether it should close alongside #1995/#1999/#1917/#1915 (all already shipped) or is tracking a residual piece. |
| #1927 | 2 — CLI Surface | CLI core/packs split | Still real. |
| #1943 | 2 — CLI Surface | Move cold-start/EPUB tests out of required CI | Still real. |
| #1980 | 5 — Go-to-Market | `route --report` + 5-way benchmark kit | Sequence after Track 1 lands. |
| #1981 | 5 — Go-to-Market | 90-day design-partner program | Open. |
| #1982 | 5 — Go-to-Market | Competitive matrix + agent-authorship framing | Open. |
| #1983 | 5 — Go-to-Market | Partnership moves (narrowed) | Open. |
| #1914 | (unplaced) | Version drift, CI/release | Standalone, revisit if it recurs. |

**Not yet filed** (converged on by the claude/codex/grok review panel 2026-10-06, filing itself
was blocked by the auto-mode classifier — **the new home harness should file these first**, then
work them):

| Track | Title |
|---|---|
| 1 | Adapter conformance test suite + retire `LegacyAdapter` dual dispatch path (all 3 panelists ranked #1) |
| 1 | `_preflight_local_silent()` should fail closed instead of swallowing a missing MLX/OrbStack setup |
| 1 | Auto-mode classifier blocks role-scoped GH writes already authorized via `.synlynk/github_apps` + explicit user go-ahead — **the exact bug class that forced this harness transition; file it from whichever harness's classifier allows it** |
| 2 | Schema validation of `.synlynk/config.json` / `policy.json` in `synlynk doctor` |
| 2 | `synlynk doctor` pipx/version-freshness check |
| 2 | Marketing-role docs-freshness pass as mandatory `synlynk release` step |
| 2 | Upgrade-available notice on startup (notify-only default) |
| 2 | Opt-in `--auto-upgrade` daemon setting (deferred until notify-only path is validated) |
| 4 | Correct README/site "live capability ledger / best harness" language — contradicts `policy.json`'s empirical-routing status; **highest-leverage, lowest-cost item in the whole three-lens review** |

**Incidental finding worth a one-line fix once in there:** `origin/main`'s `.synlynk/policy.json`
no longer has a `suspended_since` field — PR #2082 already un-suspended empirical routing with a
sample-size fallback. The README-language item above should account for this: the contradiction
is no longer "suspended but claims live," it's "just un-suspended with a 5-sample floor, zero
samples banked yet" — still an overclaim if README implies proven routing today.

---

## 4. Priority 2 — Three-Lens Strategic Review: open recommendations

Source: `docs/reviews/2026-10-05-three-lens-strategic-review.md`. Items already folded into
Section 3's tables above are not repeated; this section covers what's **not yet tracked
anywhere**.

**P0/P1 items already covered by Section 3:** P0-1 (routing/#1926+#1993+README), P0-2 (adapter
strangler), P0-3 (host-auth audit — **already closed**, #1992/PR #2050), P1-1 (config schema),
P1-3 (GOVERNS hard-fail — **already closed**, #1990/PR #2046), P1-5 (adapter conformance, same as
P0-2).

**Not yet tracked anywhere — need new issues:**

| Ref | Title | Detail |
|---|---|---|
| P1-2 | Config decomposition | Split `.synlynk/config.json` into `workspace.json` / `billing.json` / `policy.json` — current ~120-line blob mixes concerns, error-prone. |
| P1-4 | SQLite fleet scale soak test | 20–50 concurrent writers against `state.db` to prove WAL mode holds under real fleet load — currently untested. |
| P2-1 | VS Code extension thin client | One-click `dispatch` + `jobs` + `logs`. Cross-Lens Opportunity #2 ("ship a distribution surface") — CLI alone won't reach venture scale. |
| P2-2 | External eval wiring | SWE-bench / HumanEval via `testbed/` identities — turns capability telemetry into a marketing asset. |
| P2-3 | Hosted relay → managed service | Promote `relay.py` + Cloudflare Tunnel spec to a managed service. **This is the seed of Section 7 (Priority 7) below — don't file as a separate small ticket, fold into that initiative's design.** |
| Opp #4 (partial) | RBAC for merge authority | Cross-Lens Opportunity #4 lists this alongside GOVERNS/audit-log (both already closed) — RBAC itself is still unbuilt. |
| Opp #5 | Standalone ledger product | `costs` + `capability` observability that works even for teams not using `synlynk dispatch` — widens TAM, creates a data moat. |
| Opp #7 | Narrative + pricing | 2-minute demo (same task dispatched to 3 harnesses, ledger picks winner, PR merged) + `synlynk.com/pricing` with seat + fleet tiers. |

**Verdict reminder** (Part 5 of the review, for context when prioritizing): VC lens says *pass at
venture terms, reconsider at seed only if distribution + empirical proof land in 90 days*; M&A
lens says *partner now, acqui-hire later, $3–8M tuck-in after a milestone sprint, do not pay
platform multiples*; Engineer lens says *top-quartile solo engineering craft, but routing/
distribution/enterprise-controls are planned, not shipped*. The fastest lever across all three
lenses is still Cross-Lens Opportunity #1: prove the routing thesis (#1926 → #1993 → 30 days of
real median `pr_review_cycles`/`total_cost_usd` per harness×task_type) or drop the claim.

---

## 5. Priority 3 — Re-run both consult tracks after changes land

Once Sections 3 and 4's items are substantially worked (at minimum: #1926, #1993, the adapter
conformance suite, the README correction, and RBAC/config-decomposition if feasible in the same
window), re-run:

1. **The five-track plan refresh** — same panel structure as the 2026-10-06 refresh (claude/
   codex/grok synthesis), re-score each track's remaining open count and fold-in list.
2. **The three-lens strategic review** — same three personas (VC/M&A/Engineer), explicitly asked
   to re-score Part 5's verdict table against the new evidence (closed P0s, any banked capability
   samples, any shipped distribution surface). The review's own framing makes this the right
   trigger: "reconsider at seed only if distribution + empirical proof land in 90 days" — this
   re-run is the check for whether that 90-day bar was cleared.

Do not re-run either review until there's genuinely new evidence to score — re-running against an
unchanged state just reproduces the same verdict at a token cost.

---

## 6. Priority 4 — Add Muse (Meta) as a new core harness

Muse is listed in CLAUDE.md's Default Agent Role table as "not yet calibrated on any task type —
eligible for measurement, not yet assigned a lane." Promoting it to core-harness status means:

1. Provision a Muse identity/role App token the same way Agy/Grok/Codex have one
   (`.synlynk/github_apps`-equivalent), scoped per the Hardened PR Review Policy's
   cross-harness+model rules.
2. Wire it into `synlynk/harness_adapters/` following whichever adapter interface the strangler
   migration (Section 4, P0-2/P1-5) lands on — **sequence this after the adapter conformance
   suite, not before**, so Muse's adapter is born conformance-tested rather than adding a fifth
   drift-prone implementation to retrofit later.
3. Run the minimum-5-sample calibration dispatches across at least 2-3 task types per the
   Empirical Capability Assessment Policy before routing anything production-critical to it.
4. Update CLAUDE.md's Capability-Based Task Allocation table and `.synlynk/policy.json`'s
   `task_allocation` once real samples exist — not before.

This is new scope with no existing issue; file as a fresh epic once the adapter strangler
(Section 4) is far enough along that a new harness isn't being wired into two dispatch paths at
once.

---

## 7. Priority 5 — Expand Local harness + model path

Builds on already-shipped work: #1984 (Hermes-class local roster, closed 2026-10-05) and the
existing `Dockerfile.sovereign` + MLX roster groundwork the three-lens review flagged as "a real
enterprise wedge" (Cross-Lens Opportunity #6: "Productize local/sovereign"). Concrete next steps:

1. One-click `synlynk local up` command (the review's specific ask) — currently local/MLX setup
   requires manual OrbStack/MLX configuration; `_preflight_local_silent()`'s fail-closed fix
   (Section 3, Track 1 not-yet-filed item) is a direct prerequisite — don't build a one-click path
   on top of a check that silently swallows setup failures.
2. A case study with a regulated/air-gapped customer profile, once the one-click path exists —
   this is the piece that actually moves the M&A lens's verdict (local/sovereign as enterprise
   wedge is "planned, not shipped" per the review).
3. Expand the model roster beyond Hermes-class — evaluate what a broader local-model path adds
   (quantization tiers, hardware-tier detection) once usage data from the Hermes roster exists.

File as a fresh epic; it extends #1984 rather than reopening it.

---

## 8. Priority 6 — Add OpenRouter / LiteLLM / Fal.ai as additional providers

New scope, no existing issue or design. Before filing implementation tickets, this needs a short
brainstorm (per CLAUDE.md's Brainstorm-First Policy — spec in `docs/superpowers/specs/` before any
code) covering at minimum:

1. **Where these sit relative to existing harness adapters** — are OpenRouter/LiteLLM/Fal.ai
   *harnesses* (new `harness_adapters/*.py` entries, dispatched like Claude/Codex/Grok/Agy/Muse)
   or *model providers underneath* an existing harness (e.g. a Claude/Codex session routed through
   OpenRouter instead of direct API)? These have different blast radii — the second is much
   smaller scope.
2. **Cost/capability tracking implications** — `cost_entries`/`capability_ratings` currently key
   on harness+model; a provider layer adds a third dimension (harness × model × provider) that
   the schema and `synlynk capability report` (gh:#1993, still open) need to account for.
3. **Sequencing relative to Section 6 (Muse)** — if the adapter strangler is mid-migration when
   this starts, decide whether new providers land on the old or new adapter interface.

Recommend: **sequence this after Section 6 (Muse)**, since Muse's onboarding will validate whether
the post-strangler adapter interface actually generalizes to a harness that isn't one of the
original four — cheaper to find gaps once than twice.

---

## 9. Priority 7 — New exploratory goal: managed execution via synlynk-hosted nodes/swarms

This is the most open-ended item on the agenda and maps directly onto the three-lens review's
P2-3 ("Hosted relay → managed service": promote `relay.py` + Cloudflare Tunnel spec to a managed
service) and Cross-Lens Opportunity #5 (turn the ledger into a product) — but goes further than
either: those are about *remote access to a user's own fleet*, this is about *synlynk operating
hosted execution nodes/swarms on the user's behalf*.

This needs its own brainstorm before any design work — it's a genuinely new product surface
(managed compute, not just managed relay), with real new questions: multi-tenant isolation model,
billing/metering for hosted compute (vs. today's local-only cost ledger), what "swarm" means
operationally (a pool of hosted harness workers? auto-scaled dispatch targets?), and how it
relates to the existing `synlynk.com` Team/Enterprise NATS gate/sync plan already on record
(memory: `vizor-strategic-position.md`). **Do not scope this from this document alone** — it's
flagged here as an agenda item for the new home harness to brainstorm properly, not a spec.

---

## Appendix: full worktree audit raw categorization

Available in the cleanup script referenced in Section 2 and in this session's transcript. The 4
Bucket-A paths, 33 Bucket-B branches, 14 Bucket-C branches, and 7 Bucket-D branches are enumerated
in `cleanup_worktrees.sh`'s `SAFE_DIRS` variable (54 entries) plus the Bucket-A exclusion list in
Section 2 above.
