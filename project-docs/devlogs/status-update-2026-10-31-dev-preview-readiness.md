# Status Update: Dev Preview Readiness — 2026-10-31

**Prepared by:** Claude (PM/review role), on request, prior to convening a `synlynk decide` panel.

---

## 0. Which "Dev Preview" is this about?

Two roadmap items share the name "Developer Preview":

- **v0.10.0 — Developer Preview** — `[shipped]`, long ago. Scoped as installable/daily-driver tooling (pipx install, README, `synlynk migrate`, role formalization, `synlynk status`, `synlynk launch`, `synlynk viz`). Done, not what's in question.
- **The v0.27.x cluster** — `[planned]`, this is what your message is actually asking about:
  - v0.27.0 — VS Code/OpenVSX listing (target 2026-11-01)
  - v0.27.1 — Quickstart and onboarding first win (target 2026-11-02)
  - v0.27.2 — Onboarding clarity and recovery (target 2026-11-03)
  - v0.27.3 — Cross-harness onboarding verification, incl. Muse (target 2026-11-04)
  - v0.27.4 — Developer Preview acceptance run (target 2026-11-05)
  - v0.27.5 — Developer Preview **stable release gate** (target 2026-11-06)

All six are still `[planned]`. v1.0.0-preview is explicitly **superseded** by v0.27.5 — don't cut a separate channel.

**Bottom line up front: no, meaningful progress toward the v0.27.x dev-preview gate has not yet been made.** Every onboarding/quickstart story in `todo.md` is still unchecked (`story-e738edde`, `story-issue-1975`, `story-issue-1973`, `story-ed39ae8f`, `story-5019a85b`, `story-issue-1574`, etc. — none show `[x]`). What *has* progressed is v0.26.8 (the epic immediately upstream of v0.27.x), where this session just wrote and DECIDE-reviewed four implementation plans. Those are necessary scaffolding for v0.27.x but are themselves still unimplemented — zero tasks executed yet.

---

## 1. What's actually in flight (this session)

- Four specs written, DECIDE-reviewed, and turned into implementation plans under v0.26.8 (`Task Boundary Context Protocol, Compaction & Herdr Epic Tabs`, target 2026-10-30 — **already past its target date**, today is 2026-10-31):
  1. Configurability Framework (the dependency all others register against)
  2. Companion v2
  3. Harness Context Compaction Protocol
  4. Herdr Customizations (core half only; plugin repo out of scope)
- **Gap:** none of the four plans implement `synlynk statusline`, which is explicitly named in v0.26.8's own roadmap text ("fenced `synlynk statusline` displaying breadcrumbs, active goal/story, git HEAD, burn rate, sentinel status, and task/cost summaries"). Either this is a real missing plan, or it shipped elsewhere and the roadmap blurb is stale — needs a one-line check before the decide panel, not a new investigation.
- **Scope question:** Companion v2 doesn't appear anywhere in v0.26.8's literal roadmap text. It looks like scope added during brainstorming, not originally-chartered work. Worth the panel confirming it belongs here vs. a separate slot.
- Zero tasks from any of the four plans have been executed yet (Execution Handoff question — subagent-dispatch vs. inline — is still open from before this stock-take; paused per your "before we take this on").

## 2. Repo health signals

| Signal | Reading | Verdict |
|---|---|---|
| Worktrees | 160 local, **33 look stale** | 🔴 overdue for `synlynk worktree audit` — Worktree Hygiene Protocol says audit every ~20 jobs; this is far past that |
| Capability sweep | **overdue — 185 jobs since last sweep** | 🔴 blocks the Empirical Capability Assessment Policy from being anything but aspirational right now |
| Smoke test | **overdue** (`synlynk selftest --live` not run, `auto_smoke_test` off) | 🔴 no recent evidence the daily build actually works end-to-end |
| Cost rates | **never updated, hardcoded defaults** | 🟡 cost visibility is approximate, not wrong-dangerous |
| GH host auth | none recorded | 🟡 informational, expected under the role-token-only policy |
| Sentinels | 13 active, including **2 CRITICAL `TOKEN_CIRCUIT_BREAKER_TRIPPED`** events (codex zero-file runaway, 697K and 915K tokens burned, 0 files touched, 2026-10-28) | 🔴 real money burned with no output — worth a one-line note to the decide panel, not a new investigation unless it recurs |
| Open PRs | **30 open**, oldest 13 days, median age 9 days | 🔴 PR backlog is not draining; several titles look like malformed/off-topic dispatch jobs (e.g. #2540 "Analyze these two public YouTube videos directly," #2436 "IT services CxO brief on Devin and Synlynk") — smells like noise accumulating in the queue, not real blockers, but worth a cheap triage pass before release |
| Open sev1/sev2 live issues | **4 open**, including one sev1 (#2139) | 🔴 see below — this is the one finding that changes a standing memory |

**Correction to standing memory:** `feedback.md`/project memory states v0.25.4 "revalidated and closed #2138, #2139 (PR #2589)." Verified directly via `gh issue view 2139`: **it is still OPEN** (sev1, `live-issue`), with comments dated 2026-10-10/10-11 explicitly saying PR #2160 did *not* resolve it and that it was consolidated into `story-25872226` (goal-bde24050) alongside #2137/#2138/#2163/#2130, tracking moved to #2137. The memory is stale — I'll fix it after you've seen this. The other three open live issues are #2090 (LIVE-24, sev2, concurrent-dispatch lock PermissionError), #2088 (LIVE-23b, sev2, `todo.md` truncation breaking the hand-edit gate), #2087 (LIVE-23, sev2, `cost_entries` missing `pr_number` breaking cross-harness PR-check gate), and #1686 (LIVE-1, sev1, state.db DR restore validation — long-standing, since 2026-09-18).

None of these four are onboarding/quickstart blockers per se, but #2087/#2088 both degrade `synlynk pr check` itself — which is the exact gate the Hardened PR Review Policy and every merge in this repo depends on. That's a credibility risk for "release-ready," not just a backlog item.

## 3. Gap analysis vs. "a cohesive dev experience with a great first use"

Mapping your stated goal onto the roadmap's own acceptance criteria:

- **v0.27.1 gate** ("fresh-project journeys reach a verified first dispatch in under 15 minutes"): no evidence this has been run even once. `story-issue-1973` ("baseline metrics capture before any onboarding/dispatch UX change") is itself still unchecked — meaning there isn't even a *baseline* to measure "15 minutes" against yet.
- **v0.27.2 gate** (install/update failure paths, prerequisites, harness choice, common errors explained end-to-end): no dedicated work started; closest related item is the generic onboarding guide story (`story-issue-2565`), unchecked.
- **v0.27.3 gate** (five independent fresh-project journeys incl. Muse): blocked on Muse GA promotion, which is itself still `[planned]` under v0.27.0.
- **v0.27.4 gate** (GOVERNS + model/capability/cost + job-status truth + onboarding, all green together): can't be green if the capability sweep is 185 jobs overdue and the smoke test hasn't run.
- **v0.27.5 gate** ("no unresolved release-blocking Sev1/Sev2 defect remains"): currently fails outright — 4 open live issues, one sev1, two of them degrading the PR-check gate itself.

**Net read:** the "cohesive first-use" work hasn't started as its own tracked effort. The nearest-term unlock is finishing v0.26.8 (statusline, compaction, Herdr tabs, Companion v2, config framework) since v0.27.1-5 gates explicitly carry `goal-85656c82` forward — but v0.26.8 itself is already a day past its own target date with zero tasks executed.

## 4. What "release-ready" concretely requires (housekeeping priority order)

1. **Clear the PR-check-degrading live issues (#2087, #2088)** — these corrode confidence in every other merge decision between now and the gate, cheap fix, highest leverage.
2. **Run `synlynk worktree audit`** and the overdue **capability sweep** — both are stale by a wide margin and both feed the acceptance-run gate (v0.27.4) directly.
3. **Run a smoke test** (`synlynk selftest --live`) — currently the daily build has no live-verified evidence it works.
4. **Resolve the v0.26.8 statusline gap** (confirm missing vs. shipped-elsewhere) and the Companion v2 scope question — both are one-line checks, not new work, but block closing v0.26.8 cleanly.
5. **Decide execution path** for the four written plans and actually start v0.26.8 task execution — nothing ships until this starts.
6. **Only then** does v0.27.1 (baseline metrics + first-win onboarding) become realistic to start, since it explicitly depends on goal-85656c82 (same goal as v0.26.8).
7. Triage the 30-PR backlog for genuine noise (malformed dispatch titles) separately — lower priority, doesn't block the gate, but will keep compounding if left.

## 5. Answer to your key question

**Has meaningful progress been made toward the dev-preview release?** Only at the scaffolding layer (v0.26.8 planning), not at the onboarding/first-use layer (v0.27.x) that's the actual subject of "cohesive dev experience with a great first use" — that work hasn't started as tracked stories yet, and the baseline needed to even measure it against is itself unchecked. Repo health has accumulated enough housekeeping debt (stale worktrees, overdue capability sweep/smoke test, two live issues degrading the merge gate itself) that it should be cleared before — or alongside — the first v0.27.x work, not after, since v0.27.4's acceptance-run gate requires all of it green simultaneously anyway.

---

*Next step, per your instruction: you review this, then we convene `synlynk decide --record` to judge readiness + gaps against this evidence.*
