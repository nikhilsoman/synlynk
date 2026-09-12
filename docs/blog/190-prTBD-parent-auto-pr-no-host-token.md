---
title: "PR #TBD - #1436: Parent Auto-PRs Must Not Inherit Host GitHub Tokens"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 190
pr: "TBD"
status: open
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Remaining Identity-Routing Hole

Child dispatch already removed ambient GitHub tokens, but the parent daemon's
auto-finalization path still copied its full environment. When a role App token
was unavailable, an inherited `GH_TOKEN` could make `gh` authenticate as the
human operator.

## What This PR Shipped

Parent auto-PR environments now remove `GH_TOKEN` and `GITHUB_TOKEN` before
role-token resolution. A role token is injected only when one is available;
host authentication remains an explicit opt-in. Merge-shaped jobs also skip
automatic PR creation, so a merge operation cannot create a second PR from its
worktree.

## Verification

Regression tests cover missing role tokens, role-token precedence over an
inherited host token, and merge jobs with changed worktrees. The targeted test
command is:

```text
pytest tests/test_agent_cli.py -k 'implement_1436_leftover_charter_patch_so' -v
```

## What This Achieved on the Path to Autonomy

Parent and child GitHub-write paths now share the same fail-closed identity
boundary: role-scoped credentials are used when available, and a human token
cannot be selected accidentally.