---
title: "PR #1375 — The Fix That Broke the Fix It Was Fixing"
date: 2026-09-04
series: "Building the OS for Multi-Agent Development"
post: 171
pr: "#1375"
merged: 2026-09-04
---

## The Broader Goal at the End of the Previous PR

PR #1271 and PR #1275 (posts [134](./134-pr1271-codex-direct-gh-write-network-access.md) and [135](./135-pr1275-codex-full-harness-parity.md)) had closed the book on Codex's GitHub-write network access: a live sandbox probe proved the block was a configurable Codex CLI option, not a structural sandbox limitation, and `-c sandbox_workspace_write.network_access=true` gave Codex full harness parity with Claude, Grok, and Agy on review and gh-write tasks. That finding shipped as a high-confidence, tested fix. The goalpost at the end of #1275 was: Codex can now do everything the other three harnesses can do for GitHub writes — case closed.

## Strategic Shifts in This PR

It wasn't closed. Three days later, a routine review dispatch on PR #1374 (the book-manuscript integration branch) sent Codex to post a `gh pr review`, and it failed twice with `error connecting to api.github.com` — the exact symptom #1271/#1275 had supposedly eliminated. The instinct was to treat this as a flaky-environment retry. Instead, per the repo's own systematic-debugging discipline, the dispatched RCA task refused that shortcut and root-caused it properly, per the standing Harness Capability Reassessment Protocol's rule that a regression discovered during a live-issue investigation is an ad hoc trigger for reassessment, not something to patch blind.

The actual cause turned out to be a second, unrelated PR: #1331 (post [157](./157-pr1328-review-dispatch-readonly-scope.md)), merged 2026-09-02 to fix issue #937 — a review-dispatch job that had written files outside its intended read-only scope. To close that hole, #1331 forced Codex review dispatches into `-s read-only` and, in the process, invented a config key that doesn't exist in the real Codex CLI: `sandbox_workspace_read_only.network_access=true`. Codex's `v0.150.1` binary has no `sandbox_workspace_read_only` struct at all — it silently ignores the override — and its `-s read-only` Seatbelt profile unconditionally blocks all outbound network at both the DNS layer (the `mDNSResponder` socket denial) and the TCP layer (port 443 denial), regardless of any `-c` flag passed alongside it. #1271's fix and #1331's fix were both individually correct for the problem each was solving, and together they silently canceled each other out for exactly one case: Codex review dispatches that also need `--requires-gh-write`.

The existing regression test added by #1331 (`test_review_codex_gh_write_keeps_repository_read_only`) had asserted only that the string `sandbox_workspace_read_only.network_access=true` appeared in the emitted command — via a mocked `subprocess.Popen`. It never asked whether Codex actually understood that string. It passed while shipping a config key that meant nothing to the tool it was configuring.

## What This PR Shipped

The RCA (dispatched to Agy under `--task-type review --gh-write-target-kind issue`, posted to issue #1274) did the diagnostic work first: it inspected Codex's binary schema, ran `codex sandbox --log-denials` probes confirming the exact DNS/TCP denial mechanics, and traced the regression to `synlynk/dispatch.py`'s three call sites (`_permissions_to_flags()`, `dispatch_agent()`'s `read_only` resolution, and the flag-emission block) via `git blame` on commit `8995ae1f581b`.

The fix, dispatched separately to Codex under `--task-type cli-plumbing`, replaces the broken combination with one Codex actually supports: `-s workspace-write` plus `sandbox_workspace_write.network_access=true` plus `sandbox_workspace_write.writable_roots=[]` — network egress allowed, external directory writes denied by an empty writable-roots list. Critically, `#937`'s original no-write guarantee for review dispatches doesn't depend on this Seatbelt configuration at all: `_resolve_dispatch_permissions()` already strips every `write:*` grant whenever `task_type == "review"`, at the synlynk permission layer, independent of whatever sandbox flag Codex is handed.

The non-authoring reviewer dispatched to check this PR (Agy, since Codex can't review its own PR under the identity-sharing caveat from #423, and Codex-authored review dispatches would in any case still hit the very bug being fixed while it remained unmerged) surfaced one more layer worth recording: `writable_roots=[]` does **not** seal the workspace's own current directory at the OS Seatbelt level — Codex's `workspace-write` profile always treats the CWD as a default writable root, and `writable_roots` only controls *additional* directories outside it. The reviewer live-probed this directly: `touch <workspace>/test_probe_write.txt` under `writable_roots=[]` succeeded (exit 0); `touch /Users/nikhilsoman/dev/rxcc/test_probe.txt` from the same sandbox failed with `Operation not permitted`. So the real write-isolation guarantee for review dispatches was never the Seatbelt sandbox — it's synlynk's own permission-stripping code, and the sandbox config is only there to gate *network*, not writes. The PR's own description slightly overstated this ("writes still structurally blocked via empty writable_roots"); the review corrected the record without treating it as a blocker, since the actual guarantee (permission-layer grant stripping) was independently confirmed intact.

## Brainstorm Visuals Used

None — this was a pure regression-diagnosis-and-fix chain, no design-phase visuals involved.

## What This Achieved on the Path to Autonomy

This is the second time in this book's own Part Three material (see the harness-capability-baseline chapters and the LIVE-8/#1166 gh-write stall saga) that a fix in one place silently regressed a fix in another, and the second time the catch came from independently verifying a dispatched job's claimed outcome rather than trusting its self-reported status — except this time the pattern ran in *both* directions in the same session: the merge dispatch for PR #1374 self-reported `timed_out` (exit -9) after the merge had actually already landed, and the review dispatch for PR #1375 self-reported `succeeded_gh_write_failed` after the review had actually already posted. Neither job's own status label matched ground truth on GitHub. Every verification in this chain — the original regression, the RCA, the fix, and the fix's review — went through direct `gh` calls rather than `synlynk jobs` output, and every one of those checks caught something the job status alone would have missed or misreported. That gap (dispatched-job status reliability, not harness capability per se) is now the more interesting open question than anything about Codex's sandbox.

## Strategic Note: The Goal at the End of This PR

Codex has real harness parity on review-and-gh-write tasks again, this time with the actual write-isolation mechanism documented correctly (permission-layer grant stripping, not Seatbelt sandboxing) rather than assumed. The next goalpost is narrower than "does Codex have network access" — it's "can `synlynk jobs` status be trusted at all for gh-write-target dispatches," which this PR's own merge and review both quietly demonstrated it currently cannot.
