# Personal Hosted Relay Task 10 evidence

Date: 2026-10-13. Worker: Codex, job-6da6bd82. Estimated cost: $1.00;
actual billing unavailable to the worker (dispatch telemetry is authoritative).
Issue: #2201. Goal: goal-f4ce526a. Story: story-f1639150.
Base: 468db56c. Worktree: dispatch/codex/job-6da6bd82.

## Scoped fixes

- Registered the six hosted-relay CLI commands without weakening taxonomy tests.
- Kept the broker's 256-entry queue and eviction defaults. The bridge detects
  eviction, reports overflow/loss through last_error and a local hub_disconnected
  marker carrying its device identity, and resubscribes. Lost events are not
  replayed; later events forward. Local failure markers never feed back to NATS.
- Resolve the trusted operator preview base, including symlinked ancestors.
  Remote components still use directory descriptors and O_NOFOLLOW; source-root
  allowlists, destination checks, atomic replacement and mode 0444 remain.
  Overlong remote components terminate before storage; local storage/configuration
  exceptions retry and remove the event from the dedupe cache.
- Move inbound callbacks, cursor initialization/writes and gap callbacks off the
  NATS loop. Each consumer awaits persistence and its acknowledgement serially.
  Shutdown finishes an in-flight delivery's disposition before unsubscribing and
  joins executor workers. A permanently blocked local callback can still delay
  shutdown; no new hard-cancellation or durable retry subsystem was introduced.
- Document workspace-wide device trust and descriptive, unauthenticated origin
  labels. QA findings 7-9 remain outside scope except identity wiring required
  for the overflow marker and lifecycle work directly required by finding 4.

## TDD and verification

All pytest runs use `/private/tmp/synlynk-relay-test-env/bin/python -m pytest`
with `/private/tmp/synlynk-relay-bin` prepended to PATH. Logs reside in this
worktree's `.synlynk/logs/`. Sparse checkout was disabled before testing.
No `.synlynk/active_session.json` is present; the parent marker was untouched.

- RED: `tests/test_relay_hub.py tests/test_taxonomy.py -q`: exit 1,
  **7 failed, 215 passed in 11.92s**, `task10-red.log`. Failures cover taxonomy,
  trusted symlink write/receive, overflow recovery, callback/cursor loop progress,
  and retry of a local ValueError.
- First targeted run: **2 failed, 250 passed in 20.99s**, `task10-green.log`.
  The live NATS restart tests exposed cancellation between persistence and ack.
  Fixed by shielding the full delivery/disposition operation during detach.
- Targeted GREEN: hub, live integration, onboarding, existing relay, P2P,
  GOVERNS relay events and taxonomy: exit 0, **252 passed in 12.89s**,
  `task10-green-final.log`. All real NATS integration cases executed (no skips).
- Core CLI and relay_hub imports run in subprocesses with `-S` (no site packages)
  and `sys.modules['nats'] = None`; NATS is deliberately unavailable.
- Added two further parameter cases for detach while callback/cursor work is
  blocked; final full-suite and requested verification results recorded below.

## Final regression results

- First complete full run: `python -m pytest -q`, exit 1, **2 failed, 4418
  passed, 4 skipped, 5 xfailed in 770.52s (0:12:50)**, `task10-full.log`.
  The previous interrupted job is not counted as a completed run.
  - `tests/test_docs_sync.py::test_generated_reference_doc_matches_taxonomy`:
    relay-caused stale generated reference after adding the six commands. Ran
    `python scripts/generate_command_docs.py`; only the six reference entries
    changed (README content stayed unchanged).
  - `tests/test_vizor_daemon.py::test_poll_once_isolates_failures`: unrelated
    sandbox `PermissionError` writing
    `/Users/nikhilsoman/.synlynk/vizor-daemon/daemon.log`, matching the reported
    baseline home-write restriction. No unrelated code change made. Elevated
    validation needs write access to that log and its parent directory.
- Documentation fix GREEN: `tests/test_docs_sync.py tests/test_taxonomy.py -q`,
  exit 0, **11 passed in 0.27s**, `task10-docs-green.log`.
- Requested verification set (all 33 supplied test paths, `-v`): exit 0,
  **1606 passed, 1 skipped in 92.20s (0:01:32)**,
  `job-6da6bd82-verify-1.log`. All ten real NATS integration cases passed.
  The skip is the existing sentinel process-identity check. Both blocked-storage
  stages passed with and without concurrent detach; no premature ack, loop
  progress maintained, subscriptions/bridge/transport threads cleaned up.
- Final full run after regenerating the reference: `python -m pytest -q`,
  exit 1, **1 failed, 4419 passed, 4 skipped, 5 xfailed in 612.05s
  (0:10:12)**, `task10-full-final.log` (exit recorded in
  `task10-full-final.exit`). The only failure is
  `tests/test_vizor_daemon.py::test_poll_once_isolates_failures`, the same
  unrelated home-log write denial above. No relay-caused failures remain.
  Real servers executed successfully; no server-binding escalation was needed.
- `git diff --check` passed. Task implementation is DONE with the explicitly
  recorded unrelated sandbox limitation; this is not a claim of an all-green
  full suite. No full-suite failures were hidden or deselected.

## Conductor integration verification

- Worker source commit: 468b3cb8. Integrated with current main 6aaab228; generated
  command reference retains the PM/TPM charter commands from main.
- The sole worker full-suite failure passes with required home-log permissions:
  `tests/test_vizor_daemon.py::test_poll_once_isolates_failures`, 1 passed.
- Additional cancellation regression: 4 cases failed before correction, covering
  single/repeated cancellation of local work and durable delivery when storage
  subsequently raises. Shield-and-drain cleanup now preserves cancellation and
  awaits owned work. All 4 pass; independent non-author review approved the fix.
- Final focused verification: 260 passed in 11.70s, including all ten real NATS
  integration tests, onboarding, existing relay, taxonomy and generated docs.
- Declared nats-py 2.6.0 lacks the consumer filter_subjects API and fails two real
  authentication tests (2 failed, 8 passed in minimum-version probe). Raised the
  optional dependency floor to tested 2.16.0; core dependencies remain empty.
- Combined full-suite verification: **4436 passed, 3 skipped, 5 xfailed in
  273.59s**, exit 0. Command: `pytest -q -n 4 --dist loadfile`; no test exclusions.
  Isolated checkout includes main 6aaab228 and all final code/test changes, with
  required permissions and real NATS available. Log: `/private/tmp/relay-final-full.log`.
  The conductor session marker is preserved. Stdlib-only imports also passed.
- CI exposed a Python 3.10-only test assertion mismatch: concurrent.futures uses
  its distinct TimeoutError class there. Reproduced on Python 3.10.20 (1 failed,
  3 passed), corrected the test to assert that exact exception, and reran all four
  cleanup cases successfully on Python 3.10.20 and 3.14. Production is unchanged.

## Worker handoff

No subtasks, PR creation, merge, story completion, generated todo edits, global
configuration changes, or deployment. Prior task commits remain intact.
Conductor owns integration and re-review. `synlynk status` exited 0: no active
sentinels; existing capability/smoke checks are overdue.
