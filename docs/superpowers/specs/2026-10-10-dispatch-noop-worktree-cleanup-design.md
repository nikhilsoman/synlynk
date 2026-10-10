# Dispatch No-Op Worktree Cleanup Design

## Problem

One-off diagnostics and other completed dispatches that produce no changes leave
their job worktree and branch behind.

## Decision

Run cleanup in the existing completed-job finalization hook in `synlynk/jobs.py`.
For a job with no landed work, verify the worktree has empty `git status --short`
and that `git diff origin/main HEAD` is empty. Preserve its log in the central
daemon log directory, then remove the worktree and delete the branch with
`git branch -d`. Any failed check or command leaves remaining Git state intact
and emits a warning.

## Verification

Automated tests cover successful cleanup, dirty worktrees, and branches with a
diff from `origin/main`.
