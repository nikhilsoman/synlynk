---
title: "The qa App can now rerun failed Actions"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 188
pr: "TBD"
---

## The Broader Goal at the End of the Previous PR

The #1436 identity-routing work gave merge-authority roles their required
`administration: write` permission. One optional hole remained: qa could not
rerun a failed GitHub Actions workflow because its manifest requested only
`actions: read`.

## Strategic Shifts in This PR

None. The approved design treats `actions: write` as an optional qa charter
grant for flaky-workflow recovery, not as a requirement for merging clean PRs.

## What This PR Shipped

When a role appears in `merge_authority.can_merge`, `_build_app_manifest_url`
now requests both `administration: write` and `actions: write` in the generated
GitHub App manifest. Other roles, such as `dev`, receive neither elevated
permission.

This changes manifests used by new `synlynk init` flows. It does not
re-provision the installed qa GitHub App: Nikhil still needs to grant
`actions: write` in the GitHub App settings and re-approve the installation
before the live qa App can use `gh run rerun --failed`.

## What This Achieved on the Path to Autonomy

The manifest now describes the complete optional permission needed for qa to
recover from failed workflow runs while keeping the elevated grant scoped to
merge-authority roles.

## Strategic Note: The Goal at the End of This PR

The remaining #1436 work is operational approval of the installed qa App and
the broader defaulting of role-authenticated GitHub writes.
