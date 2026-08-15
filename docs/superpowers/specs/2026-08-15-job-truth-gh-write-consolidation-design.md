# Job Truth + GH-Write Consolidation — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to turn
> this spec into an implementation plan before any code is written. Per Brainstorm-First
> Policy, no implementation may begin until this spec is committed and Nikhil signs off.

**Origin:** gh:#701 ("Consolidate + permanently fix: daemon_jobs status untruthfulness
and sandboxed gh-write unreliability"), reopened for a second pass because gh:#935
("Reviewer-dispatch reliability gap: 3 of 4 PR-review dispatches failed to complete
this session") was filed *after* the prior epics plan
(`docs/superpowers/plans/2026-08-09-job-truth-and-gh-write-epics.md`) shipped fixes for
several of #701's cited issues (PRs #857, #867, #868, #925-#929), showing the problem
class recurred despite that work.

**Goal (as stated by the user):** figure out why the previous fix didn't hold, and
design a fix that is durable rather than another point patch.

**Method:** a 4-round evidence-driven investigation, grounded directly in the current
codebase (`synlynk/jobs.py`, `synlynk/dispatch.py`, `synlynk/doctor.py`), the git
history of the prior epics plan's PRs, and the full text/comment history of every
named issue (#331, #579, #426, #569, #577, #659, #935, #701), read via `gh issue view`
rather than summarized from memory. This mirrors the process and doc structure of
`docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md`, with one
deliberate deviation: that spec's rounds were conducted via `synlynk decide --panel
codex,grok --record` (a live multi-agent panel); this spec's rounds were conducted as
direct single-agent evidence review (code reads + `gh` CLI queries), recorded in the
same decision-record format but with `panel: [claude-direct-evidence]` rather than a
multi-agent panel, to keep this investigation's own cost/turnaround proportionate to a
scoping question rather than a multi-week cross-repo governance redesign. All 4 raw
decision records are committed at `project-docs/decisions/2026-08-15-round-{1..4}-*.md`
and are the primary source for this synthesis.

---

## 1. Investigation findings (what's actually true right now, not what #701 assumed)

Concrete, code-and-issue-grounded evidence gathered before any conclusion:

- **The prior epics plan's fixes are real and present in the current tree**, not
  regressed. `_reconcile_daemon_jobs()` (`synlynk/jobs.py:2049`) demonstrably calls
  ground-truth verification (`_inspect_worktree_git_state`, `_worktree_files_touched`)
  today. `_build_subprocess_env()` (`synlynk/dispatch.py:356`) demonstrably fail-closes
  `--requires-gh-write` identity (isolated `GH_CONFIG_DIR`, stripped `GITHUB_TOKEN`).
  `synlynk doctor` demonstrably implements TC-6 (gh-auth preflight). Issues #569 and
  #577 are closed and stay closed.
- **#331 and #579 are still open in GitHub despite their fix landing** (PR #867's own
  issue comments confirm the fix; the issues were simply never closed). This is itself
  a small instance of the exact problem class this spec is about — status truth,
  applied to issue-tracker hygiene rather than job status.
- **#935 is not a recurrence of #331/#579/#569/#577.** Nikhil's own investigation
  comment on #935 (2026-08-14) independently root-caused it to `_check_job_stall()`
  (`synlynk/dispatch.py:517`) — a SIGKILL-after-log-staleness mechanism neither epic
  touched. Its escape hatch only recognizes git-worktree evidence, which a
  read/verify/test/report/write review task produces none of until its final step —
  so the escape hatch structurally cannot fire during the long verify/test phase of
  exactly the task shape #701's PR-review workflow uses.
- **A same-day point-fix already shipped** (PR #939: `review_stall_timeout_minutes`,
  default 90, gated on `task_type == "review"`) but is fragile: `task_type` is a
  manually-passed `--task-type` CLI flag (`cli.py:594`), never inferred, and unrelated
  to `--requires-gh-write` (an already-present, already-enforced flag that is a
  stronger and more general signal for "this job's success is defined by an external
  state change").
- **#426's premise is now stale.** Independent, cross-verified evidence (job-381edf13,
  a second agent confirming via `gh pr view --json reviews` rather than trusting
  self-report) shows Agy *can* complete headless GitHub writes correctly once
  `~/.gemini/antigravity-cli/settings.json` has the right scoped allow-rules. The real
  remaining gap is that synlynk cannot verify that precondition automatically before
  routing — CLAUDE.md already documents this as "operator-confirmed, not reliably
  verifiable mid-task."
- **#659 has no fix attempted and no automated detection.** A GitHub MCP connector
  write (`github.add_review_to_pr`/`add_comment_to_issue`) failed 4/4 times with a
  misleading "user cancelled" error, while the dispatched job's own top-level status
  reported `OK, exit 0` every time. Nothing in the codebase checks whether the
  declared write actually landed.
- **Four independent code surfaces, one repeated architectural flaw.** Status
  reconciliation, gh-write identity, MCP delivery, and pre-exit liveness are separate
  code paths with no shared call graph — but each one, when broken, is broken the same
  way: trusting a local, cheap proxy signal (exit code, log mtime, "job status: OK")
  instead of checking the external ground truth (git state, GitHub API state) the
  proxy stands in for. Problem 1 (status reconciliation) already generalized correctly
  to this principle. The other three had not, until this spec.

## 2. Root cause of recurrence (Round 1)

**Not an incomplete fix and not a new instance of the same bug.** Both epics held.
#935 is a third, structurally distinct failure mode (pre-exit liveness/stall-kill)
in a code path neither epic was scoped to touch. It reads as "the fix didn't hold"
because all of these mechanisms share one flaw — trusting absence-of-signal as
evidence of outcome — and fixing that flaw at one lifecycle checkpoint (post-exit
reconciliation) does not automatically fix it at another (pre-exit liveness). The
durable fix is to generalize the *principle*, not just patch the next place it shows
up (which is what PR #939 did, and why it's an interim mitigation, not the answer).

## 3. One problem or two? (Round 2)

**Four independently-fixable surfaces, one shared principle — not one root cause and
not a false consolidation.** Status truth (`jobs.py`), gh-write identity/environment
(`dispatch.py` env-building + `doctor.py` preflight), gh-write delivery verification
(no code today — this is the actual gap), and pre-exit liveness (`dispatch.py`
stall-kill) each live in different code with no shared state. They get perceived as
"one problem" because they co-occur in the same dispatched-PR-review workflow, not
because a single diff could fix all four. The spec keeps them as four separate fix
surfaces but adopts one unifying constraint: **any code path that decides a job's
terminal status or whether to kill it must consult, or explicitly and auditably skip
with a documented reason, an external ground-truth check — never trust only a local
proxy signal.**

## 4. Durable verification mechanism (Round 3)

Extend ground-truth verification from git-worktree state (already solved for
reconciliation) to **GitHub API delivery-of-effect state**, keyed off the
already-existing, already-load-bearing `--requires-gh-write` flag rather than a new,
easy-to-forget flag:

- **At the stall-kill decision:** before killing a log-stale job dispatched with
  `--requires-gh-write`, run one cheap `gh api`/`gh pr view --json ...` check (using
  the orchestrator's identity, not the sandboxed job's) against the job's declared
  target. If the expected write already landed, the job finished and just failed to
  exit cleanly — mark it terminal from that evidence instead of killing it. Only fall
  through to the existing git-state check and timeout if there's no gh-write target
  declared. Keep PR #939's `task_type == "review"` timeout as a secondary fallback for
  jobs without `--requires-gh-write`, not the primary defense.
- **At terminal reconciliation, for `--requires-gh-write` jobs:** run the same check
  and record `gh_write_verified: true/false/unknown` alongside `status`. A job that
  exits 0 but fails this check becomes the `succeeded_gh_write_failed` status #701
  originally proposed but never wired to an actual check — this is what would have
  caught #659's failures automatically the same session, not via manual log grep.
- **Surface it in job summaries** (`synlynk jobs`/`synlynk logs`) the same way GTV's
  git evidence is already surfaced, so "did the effect actually happen" doesn't
  require re-deriving by hand — directly automating the workaround #701's own summary
  describes Nikhil performing manually every session.
- **CI guard:** a shared test fixture asserts every terminal-status-deciding code
  path for a `--requires-gh-write` job consults (or documents skipping) the
  delivery-of-effect check, so a fifth code path can't silently reopen this gap the
  way `_check_job_stall` did un-noticed by the original epic.

This mechanism is durable because it keys off a flag that already exists and is
already used for routing, generalizes to any future task whose success is an
external state change (not just "review"), and directly automates the exact manual
check the human workaround already performs — rather than adding another manual
flag or another hardcoded task-type string.

## 5. Per-issue disposition (Round 4)

| Issue | Disposition | Action |
|---|---|---|
| #331 | Close | Fixed in PR #867 (confirmed in current tree); close with reference; add parity regression test between `_reconcile_daemon_jobs` and legacy `_reconcile_jobs` if not already present (#701's original guard (B) — confirm status during planning). |
| #579 | Close | Same fix as #331; close alongside it. |
| #426 | Reframe, keep open on narrower scope | Premise ("Agy cannot do gh-write headless") is stale per cross-verified evidence. Retitle to the real remaining gap: synlynk cannot automatically verify Agy's local allow-rule precondition before routing. Add a preflight check (extend TC-6, or add TC-7) that inspects `~/.gemini/antigravity-cli/settings.json` for the required scoped entries and fails routing loudly instead of dispatching blind. |
| #659 | Keep open, attach concrete next step | Ship §4's delivery-of-effect check as an immediate detection fix (independent of root cause). As a parallel mitigation, route Codex's PR-review GitHub write through plain `gh pr review`/`gh pr comment` CLI instead of the MCP `add_review_to_pr`/`add_comment_to_issue` tools, since the CLI path has a confirmed working track record (via Agy) and the MCP path has a confirmed 100% (4/4) failure rate. |
| #935 | Implement durable mechanism, then close | §4's `--requires-gh-write`-gated check inside `_check_job_stall`'s escape hatch, keeping PR #939's task_type timeout as fallback. Close only after independent verification against a freshly dispatched reviewer job — not code inspection or self-report alone. |
| #701 | Becomes parent tracking issue | Close only once all five dispositions above are shipped and independently verified. |

## 6. Explicitly out of scope

- Root-causing the GitHub MCP connector's credential/session handling itself (#659's
  "suspected root cause, not yet confirmed" section) — the delivery-of-effect check
  and CLI-routing mitigation both sidestep needing that root cause to ship a fix.
  Root-causing it remains a valid follow-up but is not required for this spec's
  action items to close the user-visible gap.
- Any change to the Round 3 `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md`
  work (doc-lifecycle manifest, `audit-docs`, agent artifact storage) — that spec's
  action items are independent of this one and already scoped separately.
- Splitting the reviewer-dispatch task (read plan → verify → test → `pr check` → post
  review → merge) into multiple smaller dispatches, per #935's "medium-term, not
  blocking" idea 2 — the delivery-of-effect mechanism removes the urgency for this,
  since it fixes the false-positive-kill problem without requiring a task-shape
  redesign. Worth reconsidering separately if job cost/duration becomes the binding
  constraint instead of correctness.

## 7. Action items (not yet scoped into a plan)

These require a follow-up `superpowers:writing-plans` pass before any implementation:

1. Implement the `--requires-gh-write`-gated delivery-of-effect check
   (`gh_write_verified`) as a shared helper, callable from both `_check_job_stall`'s
   escape hatch and `_reconcile_daemon_jobs`'s terminal-status path.
2. Wire the `succeeded_gh_write_failed` status (originally proposed in #701) to that
   check, and surface `gh_write_verified` in `synlynk jobs`/`synlynk logs` summaries.
3. Add the CI parity/coverage guard asserting every terminal-status-deciding code
   path for a `--requires-gh-write` job consults or documents-skips the check.
4. Add a TC-6-adjacent (or new TC-7) preflight that inspects
   `~/.gemini/antigravity-cli/settings.json` for the scoped `command(gh pr review)`
   etc. allow-rules before routing a gh-write task to Agy; fail routing loudly if
   absent instead of dispatching blind.
5. Route Codex's PR-review GitHub write step through `gh pr review`/`gh pr comment`
   CLI instead of the MCP `add_review_to_pr`/`add_comment_to_issue` tools.
6. Close #331 and #579 with references to PR #867; confirm/add the reconciliation
   parity regression test.
7. Retitle/refocus #426 onto the routing-precondition-verification gap; close the
   stale "Agy cannot do gh-write" framing.
8. After items 1-5 ship, verify against a freshly dispatched reviewer job (not code
   inspection alone), then close #935 and #701 together.

---

**Decision records (full evidence and reasoning):**
- `project-docs/decisions/2026-08-15-round-1-4-root-cause-of-935-recurrence.md`
- `project-docs/decisions/2026-08-15-round-2-4-one-problem-or-two.md`
- `project-docs/decisions/2026-08-15-round-3-4-durable-verification-mechanism.md`
- `project-docs/decisions/2026-08-15-round-4-4-per-issue-disposition.md`
