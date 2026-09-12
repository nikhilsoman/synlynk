---
title: "Review jobs that could not run pr check or the tests they were told to run"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 180
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

#1447 closed the Agy `## Permissions` title leak (#1427 / #1421). Review dispatch still could not finish its own contract: `synlynk pr check` died writing a shared todo file, and the injected pytest `-k` selector matched 0 tests.

## Strategic Shifts in This PR

None. #1446 already named both fingerprints from live QA reviews. This PR implements that direction rather than treating the failures as defects in the PRs under review.

## What This PR Shipped

`_detect_hand_edit` renders generators into a temp directory and never opens the live `.synlynk/project-docs/*.md` path for write, so Codex `writable_roots=[]` review sandboxes can run `synlynk pr check`. `_verify_contract_for_story` no longer derives a pytest `-k` slug from the story title; it points at test files the worktree actually changed, or tells the agent to run those files without a guessed selector.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

QA review jobs can evaluate CI and run real tests instead of failing closed on sandbox writes and pytest exit 5.

## Strategic Note: The Goal at the End of This PR

#1446 closed. Remaining review-dispatch hygiene: #1432 (`pr check` from the reviewer's own job branch) and #1436 (workspace identity, including QA `actions:read` unable to rerun flaky CI).