---
title: "LIVE-22 — Closing the GitHub-Identity Zone-Boundary Gap"
date: 2026-10-03
series: "Building the OS for Multi-Agent Development"
post: 241
pr: "1964"
issue: "1960"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, live-issue, gh-identity, bugfix]
type: story
---

## The Broader Goal at the End of the Previous PR

The previous post (#1959) had just fixed Grok's shell-capability routing drift, clearing the
way back to the adapter migration's next planned port. This PR is also not a planned migration
step — it's LIVE-22, a declared live issue (gh:#1960) that needed a full RCA-grade fix before
anything else could safely continue, under the standing Live Issues SOP.

## Strategic Shifts in This PR

None beyond the live-issue interrupt itself. The fix is scoped to exactly the two confirmed
root causes of LIVE-22, nothing else.

## What LIVE-22 Was

The GitHub-identity zone boundary — the discipline that every `gh` call inside a harness
session resolves through a role-scoped App token rather than falling back to shared host
identity — had two independent gaps:

1. **Nested worktrees miss `.synlynk/github_apps/`.** A worktree created under another worktree
   (e.g. a dispatch sub-job nested under a parent dispatch) doesn't inherit the symlink that
   gives it access to the role token store, so any `gh` call from inside it would either fail
   closed incorrectly or, worse, silently fall through to host auth.
2. **Internal Python callers bypassing the shell shim.** The `SYNLYNK_GH_ROLE` fail-closed rule
   was enforced by the shell-level `gh` shim, but Python code that shelled out to `gh` directly
   — skipping the PATH-prefixed shim entirely — had no equivalent guard, so it could resolve to
   ambient host credentials instead of the intended role identity.

## What This PR Shipped

- **`synlynk/gh_shim.py`**: added `run_gh()`, an internal-caller guard mirroring the shell
  shim's fail-closed rule exactly. Any Python code calling `gh` directly now resolves
  `SYNLYNK_GH_ROLE` to its cached App token the same way the shim does, or refuses outright in a
  harness session with no token and no explicit host-auth opt-in — closing gap 2.
- **`synlynk/dispatch.py`**: added `_provision_job_github_apps()`, wired into job creation so a
  nested worktree gets the `.synlynk/github_apps/` symlink provisioned at creation time instead
  of inheriting (or failing to inherit) it implicitly — closing gap 1.

## Blocking a CI Gate Along the Way

Landing this PR also surfaced — for the first time this cycle — the `release-docs` README
test-count gate firing on a non-release PR branch: the gate checks the *branch's own*
`pytest --collect-only` count against README's claimed count, not just at release time. #1964's
new tests pushed the branch's true count from 3719 to 3722; the README badge and hero line were
patched directly on the PR's own branch to match, rather than deferred to a separate docs PR,
since the gate blocks exactly that branch's merge.

## What Was Achieved Toward the Long-Arc Goal

Both confirmed root causes of a sev1 identity-boundary gap are closed, the standing "nested
worktree" gap first surfaced in `worktree-github-apps-gap` memory now has code enforcing the
fix rather than just a manual symlink workaround, and the internal-caller guard removes an
entire class of silent host-identity fallback that no amount of shell-shim discipline alone
could have caught.

## The New Goalpost

Live issue resolved — back to the adapter migration: PR4 ports Agy, the subject of the next
post in this series.

Refs #1960 (LIVE-22).
