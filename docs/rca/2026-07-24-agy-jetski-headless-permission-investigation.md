# Investigation: Agy "jetski" headless permission auto-deny

**Date:** 2026-07-24
**Status:** Closed — not reproducible, no synlynk-side fix identified
**Origin:** Handoff note from a separate Claude Code session working in `Dialify/rxcc` (issue #1000), relayed into this repo's session for investigation and spec consideration.

## Symptom reported (rxcc, issue #1000)

`synlynk dispatch agy --story 1000 ...` completed with `status: OK (exit 0)` but produced zero file changes. The job log contained:

```
jetski: no output produced — a tool required the "command" permission that
headless mode cannot prompt for, so it was auto-denied. Add an allow-rule
under permissions.allow in settings.json (e.g. command(<target>)).
Alternatively, re-run with --dangerously-skip-permissions to auto-approve
all tools.
```

"jetski" is internal to Google's Antigravity CLI (`agy`) headless runtime, not synlynk's own code.

## rxcc session's mitigation attempts (all failed identically)

1. Default dispatch relying on `.agents/agy.json`'s `dangerously-skip-permissions: ""` override — failed.
2. `synlynk dispatch agy --grant "command(*)" --skip-preflight` — failed.
3. Project-scoped `~/dev/rxcc/.gemini/settings.json` with `permissions.allow: ["command(*)"]` — failed; root-caused as untracked and absent from the ephemeral per-job worktree.
4. Global `~/.gemini/settings.json` edited to add the same allow-rule (machine-wide) — still failed, ruling out settings.json scope as the blocker.

Running `agy --dangerously-skip-permissions -p "..."` directly (outside synlynk's dispatch) worked and wrote real output, isolating the reported failure to synlynk's spawn pattern specifically (`start_new_session=True`, no PTY, `stdout`/`stderr` to `DEVNULL` at the `Popen` level).

## This session's reproduction attempt (synlynk repo, same machine)

Confirmed this is the **same machine and installation** as the rxcc session: identical macOS build (26.5.2 / 25F84), identical `agy` version (1.1.6), identical `~/.gemini/antigravity-cli/` state directory, same user account.

Four dispatched `agy` jobs were run through the real production spawn path (`synlynk/dispatch.py`, `start_new_session=True`, no TTY) to try to trigger the same auto-deny:

| # | Setup | Result |
|---|---|---|
| 1 | `--grant write:.` (permission→flag path adds `--dangerously-skip-permissions`), global `~/.gemini/settings.json` allow-rule present | SUCCESS — file written |
| 2 | Same as #1, with the global `~/.gemini/settings.json` allow-rule temporarily removed | SUCCESS — file written |
| 3 | `.agents/agy.json` with `harness_overrides.dispatch_flags` — exact copy of rxcc's config (`dangerously-skip-permissions: ""`, `model: gemini-3.6-flash-high`, `print-timeout: 15m0s`), no `--grant` | SUCCESS — file written |
| 4 | Same as #3, task explicitly required agy to invoke its **command/shell tool** (the specific permission named in the reported jetski message), not just a file-write tool | SUCCESS — command executed, correct output captured |

All four ran cleanly to completion (`status: SUCCESS`, exit 0) with no jetski auto-deny message in any job log. Test artifacts and worktrees were cleaned up after each run; no code changes were made to `synlynk/dispatch.py` or `synlynk/_constants.py`.

## Conclusion

No synlynk-side code path could be found or triggered that causes `--dangerously-skip-permissions` (via either the `--grant` flag-resolution path or the `.agents/<agent>.json` harness-overrides path) to be silently ignored under the detached/no-TTY dispatch spawn. Both mechanisms correctly reach the `agy` invocation and are honored in every reproduction attempt, including one that specifically exercised the "command" tool named in the original failure.

Given the failure was reported on the identical machine/install and could not be reproduced here, the most likely explanation is a **transient Antigravity CLI auth/session-state issue**, not a structural dispatch bug. The rxcc session's own handoff flagged `~/.gemini/antigravity-cli/jetski_state.pbtxt` (a session/auth token populated by interactive login) as unexamined — a stale or momentarily invalid token there would explain why all four of rxcc's mitigation attempts failed identically (none of them touch auth state) and why it did not recur here.

## Decision

No engineering fix was specced or implemented. The existing shallow fix from PR #475 (warn when `agy` is dispatched with no write/run permissions, so the flag is never silently empty) remains in place and is sufficient for the failure mode it addresses.

## If this recurs

- Capture the raw job log (`.synlynk/logs/job-<id>.log`) showing the literal jetski message, not just a narrative summary.
- Check `agy --version` at the time of failure against the version in this note (1.1.6).
- Inspect `~/.gemini/antigravity-cli/jetski_state.pbtxt` timestamp / re-run `agy` interactively once to force a fresh login, then retry the same dispatched job — if that clears it, the auth-token theory is confirmed and the fix belongs in Antigravity CLI (Google), not synlynk.
- Do not re-attempt settings.json/`--grant`/harness-overrides permutations again without new evidence — this investigation covered all three exhaustively with no repro.
