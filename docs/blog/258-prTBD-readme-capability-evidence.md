---
title: "README Capability Claims Now Carry Their Evidence Threshold"
date: 2026-10-07
series: "Building the OS for Multi-Agent Development"
post: 258
pr: "TBD"
issue: "2098"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts, policy, capability-assessment]
type: pr
---

# README Capability Claims Now Carry Their Evidence Threshold

## The Broader Goal at the End of the Previous PR

The empirical-routing policy now sets a five-merged-job minimum for each
harness and task type, and keeps the configured allocation as an interim
default until that evidence exists. The capability report and cross-workspace
measurement still depend on #1993 and canonical state work in #1926. The README
should explain that evidence boundary wherever it describes harness routing.

## Strategic Shifts in This PR (if any)

No strategy change. This is a correction to the product description so it
matches the policy already committed in `.synlynk/policy.json` and explained in
the empirical capability policy article.

## What This PR Shipped

- Replaced the README's vague “best-measured harness” and “minimum sample size”
  wording with the explicit requirement of at least five completed, merged jobs
  for the relevant task type.
- Stated that routing follows the documented interim policy below that
  threshold.
- Linked the README claim to the empirical capability policy and the routing
  policy file.
- Audited the source `website/` tree; it had no matching external claim to
  update.
- No code or runtime behavior changed. The check reviewed Markdown links,
  searched the README and website source for the old claim forms, and checked
  the diff for whitespace errors.

Design: `docs/superpowers/specs/2026-10-07-readme-capability-evidence-design.md`.
Plan: `docs/superpowers/plans/2026-10-07-readme-capability-evidence-copy.md`.

## Brainstorm Visuals Used

None. The wording follows the approved design spec and the existing empirical
policy.

## What This Achieved on the Path to Autonomy

Readers can distinguish measured harness allocation from the interim policy
used while task-specific evidence is sparse. The copy no longer presents a
future report as a shipped capability.

## Strategic Note: The Goal at the End of This PR

The external routing claim now matches the five-sample policy. The next
measurement milestone remains canonical state consolidation (#1926), followed
by the capability report (#1993). This PR does not claim those measurements
are already available.
