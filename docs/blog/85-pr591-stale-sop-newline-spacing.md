---
title: "PR #591 — The Blank Line That Broke a Markdown Header"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 85
pr: "#591"
merged: 2026-07-30
---

## The Broader Goal at the End of the Previous PR

With #339 (PR #584) and #583 (PR #588) both merged and the accidental Codex dispatch regression fixed (PR #589), the path was finally clear to run `synlynk sync --repair-sops --confirm` for real and regenerate CLAUDE.md/GEMINI.md/GROK.md.

## Strategic Shifts in This PR

Running that regeneration live, in this repo, immediately surfaced a new bug — found by the PM's own manual verification, not by a dispatched agent or an existing test. The just-merged stale-refresh code path in `synlynk/probe.py` (#583/#588) correctly replaced the stale `## Capability-Based Task Allocation` content, but dropped the blank-line separator before the next header. The result: `...synlynk's default fleet assumptions.## Cost Visibility` — glued together on one line, which broke that header's markdown rendering entirely. The older "fill missing SOP" path was confirmed unaffected, and served as the correctness baseline for the fix. The buggy first regeneration attempt was discarded locally (`git checkout --`) before anything was committed.

## What This PR Shipped

A fix in `synlynk/probe.py` preserving exactly one blank line between a refreshed stale section's body and the next header, reusing the same join normalization already used by the fill-missing path (`_repair_sop_body_parts()`). Plus a regression test pinning this exact boundary case.

Verification for this one was unusually thorough given how easy the bug was to miss with an automated diff: an isolated clone made directly from the GitHub remote URL (not a local-to-local double clone, after an earlier methodology mistake this session showed that path can silently serve stale refs), a full test-suite run (`4 failed, 1444 passed, 2 skipped` — the same 4 pre-existing baseline failures, one new passing test), and a manual repro seeding a fixture with a stale fenced section immediately followed by another header, confirming the exact before/after text at that boundary.

Grok reviewed as non-authoring reviewer, independently re-ran the same checklist (isolated clone, full suite, manual repro), and merged via the sanctioned COMMENT-review fallback (#423/#426) — the PR was in fact merged mid-review, since a killed-but-not-instantly-terminated first dispatch attempt had already completed the work before its kill signal landed; the second dispatch caught this and re-verified independently rather than assuming the "already merged" state was trustworthy on its own.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

This is the third bug in a row where fixing #339/#583 introduced a fresh regression discovered only by actually running the tool end-to-end, not by unit tests alone. The pattern across #589 and #591 is the same: schema/formatting changes to harness-managed, config-driven output need a live dry-run against a real fixture, not just isolated unit coverage, before they're trusted.

## Strategic Note: The Goal at the End of This PR

The stale-refresh path is now correct in both content and formatting. Nothing is left blocking the actual CLAUDE.md/GEMINI.md/GROK.md regeneration (see PR #592) — the original ask this whole chain of fixes existed to unblock.
