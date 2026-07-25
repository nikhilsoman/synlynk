---
title: "PR #479 — The Agy Jetski Investigation: An RCA With No Fix"
date: 2026-07-24
series: "Building the OS for Multi-Agent Development"
post: 75
pr: "#479"
merged: 2026-07-24
---

## The Broader Goal at the End of the Previous PR

PR #475 had just shipped a warning for the *generic* silent-no-op failure mode: `agy` dispatched with no write/run permissions produces a clean-looking success that actually did nothing. That fix assumed the underlying cause was always "permissions were never granted." A follow-up handoff note from the rxcc session — the same one that surfaced PR #475's bugs — reported a *more specific* failure: permissions correctly granted, but a headless-runtime "jetski" auto-deny for the command/shell tool specifically, four different mitigation attempts all failing identically.

## Strategic Shifts in This PR

This PR is the result of a shift the user made explicitly mid-investigation: rather than speccing an engineering fix from the rxcc handoff note alone, reproduce the bug locally first. Two rounds of reproduction attempts (four dispatched `agy` jobs total, covering every permission-granting mechanism synlynk has: `--grant`-based flag injection, `.agents/agy.json` harness-overrides matching rxcc's exact config, with and without a global `~/.gemini/settings.json` allow-rule, and one job explicitly forced to invoke the shell/command tool the jetski error names) all succeeded cleanly — zero repro. Given that, the user's second explicit call was to drop the planned spec entirely rather than write a fix for a bug that couldn't be shown to exist in synlynk's own code.

## What This PR Shipped

`docs/rca/2026-07-24-agy-jetski-headless-permission-investigation.md` — not a code change, a closed investigation record. It documents:

- The exact reported symptom: a dispatched `agy` job completing `status: OK (exit 0)` with zero file changes and a job log containing Antigravity CLI's own `jetski: no output produced — a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied` message.
- rxcc's four failed mitigation attempts (default `.agents/agy.json` override, `--grant "command(*)" --skip-preflight`, project-scoped `.gemini/settings.json`, global `~/.gemini/settings.json`) — all ruled out settings.json scope as the blocker, since even the machine-wide grant didn't clear it.
- This session's four reproduction attempts against the confirmed *identical* machine, OS build, `agy` version (1.1.6), and `~/.gemini/antigravity-cli/` state directory as the rxcc session — all four succeeded, including the one built specifically to exercise the named "command" permission.
- The conclusion: no synlynk-side code path (neither the `--grant`-to-flag resolution nor the `.agents/<agent>.json` harness-overrides path) could be found or triggered that silently drops `--dangerously-skip-permissions`. Both mechanisms correctly reached `agy` and were honored every time.
- A named suspect for what actually happened: `~/.gemini/antigravity-cli/jetski_state.pbtxt`, a session/auth token file populated by interactive login, flagged by rxcc's own handoff as unexamined. A stale or momentarily invalid token there is consistent with all four of rxcc's fixes failing identically (none of them touch auth state) and with this session's inability to reproduce it on the same install.
- Explicit next-step guidance for if it recurs: capture the raw job log (not a narrative summary), check `agy --version` against 1.1.6, and force a fresh interactive login before retrying — rather than re-running the same settings.json/`--grant`/harness-overrides permutations this investigation already covered exhaustively.

## Brainstorm Visuals Used

None — this was a reproduction-and-write-up task, not a design decision; no visual companion was used or needed.

## What This Achieved on the Path to Autonomy

The discipline exercised here — reproduce before speccing, and write down a negative result with the same rigor as a positive one — matters more than the specific conclusion. A cross-repo bug report relayed secondhand, with a plausible-sounding root cause already proposed, is exactly the kind of input that could have produced a spec for a fix to a bug that doesn't exist in this repo's code. The RCA closes the loop honestly: no engineering fix was specced or implemented, the existing PR #475 warning remains the correct and sufficient mitigation for the failure mode it actually addresses, and a concrete, falsifiable theory (stale auth token) is recorded for whoever hits this next, instead of the investigation simply evaporating from institutional memory once the chat session that ran it ends.

## Strategic Note: The Goal at the End of This PR

This investigation is closed, not resolved — if the jetski auto-deny recurs, the fix (if one exists) belongs to Google's Antigravity CLI, not synlynk, and the RCA's own "If this recurs" section is the runbook for confirming that before anyone re-opens dispatch-side investigation. No follow-up work is scheduled from this PR; it's a terminal node in this session's thread, distinct from the still-open dispatch-reliability work (issue #461's job-status misreporting pattern) that PR #463 left unresolved.
