# 100. PRs #850/#851 — Closing the two bugs the onboarding guide surfaced

## Goal at the end of the previous PR

PR #731 (post #99) shipped Synlynk UX 1.0: `uxcore` as the shared data/write/RBAC seam behind both the curses TUI and Vizor, with the Slack notifier standing as the reference BYOUX consumer. PR #837 then closed out field-trial readiness — playblazer-ng onboarding verified, all 7 journey maps walked interactively end to end with zero console errors. UX 1.0 was, on paper, done and field-trial-ready.

## What moved the goalpost this PR

Writing step-by-step usage instructions for the TUI, Vizor, and Slack surfaces — intended as starter material for a future "Watching synlynk" onboarding guide — is a different exercise from journey-map verification. Journey maps confirm a surface *renders*. Writing a usage guide requires tracing what actually happens when a user presses a key or reads a message, which surfaced two real bugs that interactive click-through had not caught:

1. **TUI approve/kill keybindings didn't exist.** `synlynk/tui.py`'s main loop only handled `1`/`2`/`3`/`4` (panel switch) and `q` (quit). The status bar even advertised panels, but there was no way to actually approve a pending PR or kill an in-flight job from the terminal — the two write actions `uxcore` was explicitly built to expose.
2. **The Slack notifier's event filter matched nothing.** `NOTIFY_EVENT_TYPES = ["dispatch_complete", "pr_approved", "job_failed"]` never matched `uxcore._execute_write`'s actual logged action strings (`"dispatch"`, `"approve_pr"`, `"kill_job"`). A second, independent check inside `format_message()` used a *third* naming scheme (`"job_completed"`, `"job_failed"`) for the Vizor deep-link. And that deep-link was hardcoded to `localhost:8420` — Vizor's real default port is `8721`.

Rather than quietly working around these while drafting the guide, both were filed as issues (#846, #847) with a third issue (#848) to write the actual guide, explicitly blocked on the first two landing — no point documenting behavior that's about to be fixed out from under the docs.

## What this PR shipped, technically

Both fixes were dispatched to Codex (`synlynk dispatch codex --issue 846/847 --base main`) rather than implemented directly, per this project's PM/implementer role split.

**PR #851 (issue #846) — TUI approve/kill:**
- `synlynk/tui.py`: `a`/`k` keybindings on the Jobs panel. `a` calls `uxcore.approve_pr(pr_number=...)` on the selected pending-approval job; `k` prompts a y/n confirm, then calls `uxcore.kill_job(job_id=...)` on the selected in-flight job. `KEY_UP`/`KEY_DOWN` added for job selection, with a status-message line reporting result or rejection ("No pending-approval job selected", etc.).
- `synlynk/uxcore.py`: `JobRun` gained optional `job_id`, `pr_number`, `status` fields (backward-compatible — older telemetry rows lack them). `get_jobs()` now cross-references live-tracked jobs (`synlynk.jobs._load_jobs()`) so jobs that haven't emitted telemetry yet (still queued/running) are still selectable for approve/kill.
- `docs/superpowers/ux-1.0-surface-checklist.md`'s approve/kill rows updated from "requires live interactive session" to "keybinding implemented, unit-tested; still requires live interactive-session verification" — deliberately *not* marked Pass, since a sandboxed dispatch job cannot perform the live verification the checklist's own header requires.

**PR #850 (issue #847) — Slack notifier event names and deep-link port:**
- `NOTIFY_EVENT_TYPES` corrected to `["dispatch", "approve_pr", "kill_job"]`, matching `uxcore._execute_write`'s real action strings.
- `format_message()`'s separate deep-link check now reuses `NOTIFY_EVENT_TYPES` directly instead of maintaining a third divergent list.
- New `_vizor_port()` reads `.synlynk/config.json`'s `vizor.port`, falling back to `synlynk.viz.DEFAULT_PORT` (`8721`), replacing the hardcoded `8420`.

**Review discipline:** both jobs' self-reported "OK (exit 0)" was treated as a starting point, not proof (per standing memory #202). Before merge: full test suites were re-run directly in each job's worktree (1791 passed/2 skipped for #846; 1789 passed/2 skipped for #847), CI was confirmed green across all three supported Python versions, both diffs were read in full, `synlynk pr check` was run from each worktree, and two anomalies were run down rather than waved through — the unexplained `GEMINI.md` touch turned out to be the harness's own routine `verified:` timestamp bump, and the seemingly-duplicate `tests/test_notifier_slack.py` / `tests/test_slack_notifier.py` pair turned out to be two files that already coexisted on `main` pre-dispatch, not an agent-created orphan. Both PR bodies were auto-generated without a GitHub closing keyword (`Fix GitHub issue #846:` rather than `Fixes #846`), so both were edited to add `Fixes #N` before merge, confirmed by both issues actually closing post-merge. Reviews were posted as the sanctioned non-authoring COMMENT-approve (caveat #423 — all dispatch agents share one GitHub identity, so `gh pr review --approve` fails on self-authored PRs).

One open thread, not yet chased down: both jobs' actual cost came in far above their pre-execution estimates ($5.19 actual vs. ~$0.14 estimated for #846; $4.22 vs. ~$0.05 for #847) — over 30x and 80x. Likely just `structured_output` vs. `prompt_estimate` accounting divergence, but worth a closer look if the pattern recurs on future dispatches.

## Brainstorm visuals

None used for this PR — both fixes were narrowly scoped bug corrections against an already-approved design (the UX 1.0 spec behind #731), not new design surface.

## What this achieved toward the long-arc goal

UX 1.0's premise is that `uxcore` is the single seam behind every surface, so a write action defined once behaves identically everywhere. These two bugs were exactly the kind that premise is supposed to prevent slipping through: the TUI had a write capability defined in `uxcore` that its own UI never exposed, and the Slack consumer was subscribing to event names that didn't exist. Both are now closed, and — more importantly — they were caught by the process the guide-writing work was designed to catch: describing real usage, not just confirming a screen renders.

## New goalpost

Issue #848 ("Watching synlynk" onboarding guide, TUI/Vizor/Slack) is now unblocked — its guard condition (#846 and #847 resolved) is satisfied. It has not been started; per its own explicit dependency framing it should be confirmed with the user as the next step rather than assumed.
