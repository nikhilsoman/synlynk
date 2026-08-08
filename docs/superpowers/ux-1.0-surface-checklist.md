# UX 1.0 Surface Test Checklist

Durable, reusable verification record for the 3 UX 1.0 surfaces (TUI, Vizor, Slack notifier)
shipped in PR #731. An item is not checked off until exercised on at least one real project
with a real dispatch job — synthetic/staged runs don't count (see
docs/superpowers/specs/2026-08-06-ux-1.0-field-trial-readiness-design.md Phase 1).

## TUI (`synlynk/tui.py`)

curses-based interactive UI — cannot be driven headlessly via Bash/CI in this pass. All rows
require a live interactive terminal session to verify; tracked as a follow-up, not blocking
Phase 1 sign-off on its own (see Follow-up section).

| Item | Pass/Fail | Evidence | Project |
|---|---|---|---|
| Job list panel renders with active jobs | Not yet verified | requires live interactive session | — |
| Job detail panel renders full job metadata | Not yet verified | requires live interactive session | — |
| Approve keybinding works on a pending-approval job | Not yet verified | requires live interactive session | — |
| Kill keybinding works on an in-flight job | Not yet verified | requires live interactive session | — |
| RBAC-denied state renders correctly for a non-privileged actor | Not yet verified | requires live interactive session | — |
| Empty state renders when no jobs exist | Not yet verified | requires live interactive session | — |

## Vizor (`synlynk/viz.py`)

| Item | Pass/Fail | Evidence | Project |
|---|---|---|---|
| `/` index route renders | Pass | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8731/` -> 200; `manifest.json` -> 200 | synlynk |
| `/` index route renders | Pass | Re-verified post-fix: `synlynk viz --serve < /dev/null` — no crash, `curl -s -o /dev/null -w "%{http_code}" http://localhost:<port>/` -> 200. Was `EOFError` on unconfigured `.synlynk/config.json` (`_ftue_prompts()` called `input()` unconditionally); fixed by [#822](https://github.com/nikhilsoman/synlynk/issues/822) / [PR #824](https://github.com/nikhilsoman/synlynk/pull/824), merged to main | rxcc, cc-videoreframing |
| `/` index route renders | N/A | project has no `.synlynk/` directory — not yet onboarded to synlynk | playblazer-ng |
| `/dispatch` POST creates a job | Not yet verified | requires a safe test dispatch against a live project; deferred to avoid polluting real job history mid-trial | — |
| Job list/detail views render live data | Not yet verified | route surface is manifest.json + static gantt/tube/journeys/observatory/effort/efficiency views, not a REST job-list API as originally assumed — re-scope this checklist row in a follow-up edit | synlynk |
| `/approve` POST approves a pending job | Not yet verified | no pending-approval job was in-flight during this pass; testing this destructively against real work was avoided | — |
| `/kill` POST kills an in-flight job | Not yet verified | no in-flight job was live during this pass; testing this destructively against real work was avoided | — |
| Capability-manifest-gated controls hide/show correctly per actor role | Not yet verified | requires multi-actor RBAC session | — |
| `subscribe()`-driven live updates reflect a new event within one poll cycle | Not yet verified | requires a live dispatch during an open browser session | — |

## Slack notifier (`synlynk/notifiers/slack.py`)

No Slack webhook URL is configured in this environment for any of the 4 projects (checked
`.synlynk/config.json` and environment for `SLACK_WEBHOOK*`, none found). Per this checklist's
own Step 2 instruction, these rows are marked N/A rather than left blank.

| Item | Pass/Fail | Evidence | Project |
|---|---|---|---|
| Job-started message delivered to a real webhook | N/A | no webhook URL configured | rxcc, cc-videoreframing, playblazer-ng, synlynk |
| Job-completed message delivered to a real webhook | N/A | no webhook URL configured | rxcc, cc-videoreframing, playblazer-ng, synlynk |
| Job-failed message delivered to a real webhook | N/A | no webhook URL configured | rxcc, cc-videoreframing, playblazer-ng, synlynk |
| Approval-needed message delivered to a real webhook | N/A | no webhook URL configured | rxcc, cc-videoreframing, playblazer-ng, synlynk |

## Follow-up (not a blocker)

Filed as a separate ticket: automated smoke-test suite (headless curses driver for TUI,
HTTP client for Vizor, webhook mock for Slack) — deferred until surfaces stabilize
post-trial, per spec Phase 1.
