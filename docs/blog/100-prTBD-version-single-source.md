---
title: "PR #TBD — CI release gate and version single source"
date: 2026-10-03
status: open
post: 100
---

## The Broader Goal at the End of the Previous PR

Architecture item #9 called for a release process that makes documentation and package metadata trustworthy rather than relying on a manual checklist.

## Strategic Shifts in This PR

The manual named-release README checklist is now a required CI job, and the version is no longer duplicated in Python source, packaging metadata, the installer, or README content.

## What This PR Shipped

- Root `VERSION` is the canonical editable version source.
- Runtime Python code reads that file, with installed-package metadata as the wheel fallback.
- setuptools reads `VERSION` directly; the release command updates only that file.
- `install.sh` reports the installed package metadata without a second hardcoded version.
- README badge and release hero are synchronized to `0.25.0` and the current collected-test count.
- Pull requests, workflow dispatches, and `v*` tag builds run `synlynk release --check-docs` as `release-docs`.
- Tests fail if runtime, packaging, README, or source modules drift from the canonical file.

## What This Achieved on the Path to Autonomy

Release automation now has a deterministic, fail-closed signal for named-release documentation and version consistency.

## Strategic Note: The Goal at the End of This PR

The next release can promote one version value through packaging, runtime, documentation, and CI without hand-editing parallel copies.
