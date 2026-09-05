---
title: "PR #1415 — Testing the Thing That Keeps Lying About Itself"
date: 2026-09-04
series: "Building the OS for Multi-Agent Development"
post: 175
pr: "#1415"
merged: 2026-09-04
---

## The Broader Goal at the End of the Previous PR

The #1377 RCA had just closed: five independent false-negative fingerprints in job-status reporting (#1379–#1383), each root-caused and fixed in its own PR (#1384–#1388). The goalpost at that point was verification, not code — confirm every fix actually landed on `origin/main` and the fixes hold under the real test suite, rather than trusting the tickets' own "closed" labels. That validation passed. But the RCA itself flagged an acknowledged gap: none of the five fixes had an end-to-end regression test proving the *whole* status pipeline — dispatch → child process → GitHub ground truth → `daemon_jobs` row → `synlynk jobs` output — agrees with reality across all four ways a dispatched job can actually end.

## Strategic Shift in This PR

The instinct after closing an RCA is to move on. The call here was the opposite: file the missing regression test as its own tracked issue (#1414) *before* closing #1377, then close #1377 referencing it — so the gap the RCA itself admitted to wouldn't quietly disappear the moment the ticket closed. #1414 was then dispatched to Codex, consistent with this project's PM/implementer split.

## What This PR Shipped

`tests/test_agent_cli.py` gained a parametrized end-to-end test (`test_job_status_add_realghwrite_endtoend_regr`) exercising all four terminal states a `--requires-gh-write` dispatch can land in: `pr_open`, `killed_zombie`, `timed_out`, `review_posted`. Rather than mocking `gh` at the Python level, the test fakes it at the process boundary — a JSON state file plus a fake executable `gh` script that reads/writes that state based on argv, and a fake harness binary that shells out to it with scenario-specific fixed arguments. `dispatch_mod.HARNESS_CAPABILITY_BASELINES["codex"]` gets monkeypatched to point at the fake harness, `dispatch_agent(...)` is called for real, and the test reaps the actual spawned child process to assert its exit code and the resulting status convergence against fake-GitHub ground truth.

This design choice — testing against the process boundary instead of a Python-level mock — was also exactly what surfaced this PR's own CI failures. The first dispatch (`job-be18ebe7`) shipped a working test that called `os.waitstatus_to_exitcode(wait_status)` to check the reaped child's exit code — a function that doesn't exist before Python 3.9. CI's `test (3.8)` matrix leg failed deterministically with `AttributeError`; `test (3.10)` failed too, but with no captured traceback (`gh run view --log-failed` came back empty), because GitHub Actions had cancelled the job mid-run rather than a real assertion failing. Reproducing the same four scenarios locally on both the default interpreter (3.14) and a genuine pyenv-managed 3.10.20 passed cleanly, twice — evidence pointing at CI-timing flakiness in the blocking `os.waitpid(pid, 0)` call rather than a logic bug, though not conclusive proof.

A second dispatch (`job-ea80bad9`), stacked on the same branch via `--base` rather than opened as a new PR, fixed both: the 3.8 incompatibility was replaced with a 3.8-safe `os.WIFEXITED`/`os.WEXITSTATUS`/`os.WIFSIGNALED` decode of the raw `waitpid` status tuple, and the single blocking wait was replaced with a bounded `os.WNOHANG` poll loop so CI timing variance can't produce a false failure. `gh pr checks 1415` went green across `test (3.8)`, `test (3.10)`, `test (3.12)`, and `qa-gate` after the second dispatch.

Review and merge landed cleanly through the project's `qa`-role GitHub App identity — genuinely distinct from the `dev`-role identity that authored the dispatch work, so for the first time in this whole PR sequence, no `--admin` merge fallback was needed for the identity-sharing caveat (#423).

## What This Surfaced, Unplanned

While verifying `job-be18ebe7`'s outcome independently rather than trusting its self-reported status (standing project discipline), a live example of exactly the bug class under test showed up: the job's own status was internally inconsistent — `OK (exit 0)` in one output block, `permission_denied` in the jobs table, and `permission_denied` persisted directly in the `daemon_jobs.status` column — despite `gh_write_verified=1` and a real, correctly-scoped PR having opened. This is a sixth false-negative fingerprint, structurally similar to but not yet root-caused as the same bug as #1379–#1383, so it's tracked fresh as #1429 rather than folded back into the closed #1377 RCA.

## Brainstorm Visuals Used

None — this was a diagnosis-and-fix cycle, not a design decision.

## What This Achieved on the Path to Autonomy

The status pipeline this project depends on for trusting dispatched work now has an end-to-end regression test covering all four terminal paths, closing the one gap the #1377 RCA itself flagged as open. It also produced fresh, concrete evidence (#1429) that the underlying bug class isn't fully closed — which is the point of writing the test in the first place: it's already doing its job of catching what manual verification alone would eventually have missed.

## Strategic Note: The Goal at the End of This PR

The next goalpost is #1429 itself: root-cause the specific `daemon_jobs.status` code path that can persist `permission_denied` on a job with `gh_write_verified=1` and a real merged PR — a narrower, now well-evidenced target rather than the broad "job status is sometimes wrong" framing #1377 started from.
