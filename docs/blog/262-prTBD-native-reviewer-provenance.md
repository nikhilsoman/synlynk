---
title: "Native Reviewers Can Record Cross-Harness Provenance"
date: 2026-10-08
series: "Building the OS for Multi-Agent Development"
post: 262
pr: "#TBD"
status: open
author: "Grok"
version: "0.23.0-dev"
tags: [posts, provenance, review, pr-check]
type: pr
---

## The Broader Goal at the End of the Previous PR

The previous provenance work let a native implementation session record
`cost_entries.pr_number` so `synlynk pr check` could compare implementer and
reviewer harness/model identity. Dispatched reviewers were still the only
review identity the gate could resolve.

## Strategic Shifts in This PR

During PR #2112 a real QA review from a different harness and model posted an
APPROVE, then `synlynk pr check` blocked with `no reviewing job provenance
found`. The gate had no supported way to record an interactive reviewer
without fabricating a dispatch job. This PR adds that path, and it tags the
row with the reviewer role so a QA stub cannot be read as the implementer
(gh:#2095).

## What This PR Shipped

- `synlynk cost log --pr <n> --harness <harness> --role qa --model <model>`
  writes a native reviewer cost row (`job_id` null, `agent_role=qa`).
- `_cross_harness_review_verdict` accepts that row when no dispatched review
  job exists, and only when harness and model both differ from the implementer.
- Native implementer lookup excludes `qa` rows, so a later reviewer stub cannot
  replace implementer identity.
- Dispatched review jobs remain the preferred path when they resolve uniquely.
- Tests cover native accept, missing provenance, untagged rows, same
  harness+model rejection, the #2095 role split, and dispatched-review
  precedence.

No brainstorm visual informed this focused gate fix.

## Summary Toward the Long-Arc Goal

Interactive QA sessions can now participate in the same measured cross-harness
review gate as dispatched work, which is a prerequisite for fail-closed merge
authority without forcing a second review dispatch.

## The New Goalpost

A native reviewer who records role-tagged provenance should pass `synlynk pr
check` on the same terms as a dispatched reviewer: different harness, different
model, and an exact PR-linked cost row.
