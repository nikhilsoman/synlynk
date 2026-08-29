---
title: "PR #1199 — Grounding Charters in the Corpus, Not the Spec"
date: 2026-08-29
series: "Building the OS for Multi-Agent Development"
post: 133
pr: "#1199"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

PR #1202 (post #132) finished a mechanical terminology sweep — replacing stray "agent" with
"harness" across `synlynk/*.py` so the Agent/Harness distinction (agents are *who*, harnesses are
*how*) held consistently in code, not just in docs. That PR closed one gap on tracking issue #1198
("[Tracking] Autonomous Operations Activation"): the terminology was now internally consistent, but
several sub-issues under #1198 remained — including #1199, which #1202's own investigation had
flagged as still open. The goal at that point was simply: work through #1198's remaining sub-issues
in priority order, starting with whichever was shovel-ready.

## Strategic Shifts in This PR

None. #1199 was picked over #1203 (GOVERNS backlog automation) specifically because #1203 requires
a `superpowers:brainstorming` pass first per its own issue text, while #1199 — "Document corpus
references used to derive workspace agent charter content" — could go straight to a plan. No
goalpost moved; this was the next item in the queue, taken in the order its own preconditions
allowed.

## What This PR Shipped

The real discovery this PR made was architectural, not textual: charter content lives in **two
places**, and #1199 only owns one of them.

1. `synlynk/agent_cli.py`'s `SEED_CHARTERS` dict — the git-tracked, durable seed source used only
   when `cmd_agent_init()` provisions a brand-new agent.
2. Each live agent's actual runtime charter at
   `~/.synlynk/workspaces/<workspace_id>/agents/<agent_id>/charter.md`, written by
   `agent_store.propose_charter_revision()` — not git-tracked, workspace-local state.

PR #1196 had already restored `pm`'s charter text from a real record; #1199's job was to do the
same derivation exercise — for real, from the actual corpus, not spec-guessed prose — for the other
six roles: `dev`, `qa`, `architect`, `tpm`, `designer`, `marketing`. `synlynk-bot` was explicitly
out of scope (infra catch-all, no real corpus to mine).

Per this repo's locked role split, the actual charter authorship was dispatched, not written by
Claude:

- **Task 1** (dispatched to Codex, job `job-8a37f307`): audited `dev`, `qa`, `architect` against
  `project-docs/devlogs/nikhilsoman.md`, `project-docs/memory.md`, and targeted
  `git log --oneline --grep=` searches. Result: `qa`'s and `architect`'s charter bodies were
  rewritten — `qa` to describe policy-gated (`.synlynk/policy.json`), currently
  docs-only-demonstrated merge authority rather than an unrestricted claim; `architect` to describe
  the role as provisioned-but-largely-unexercised, since the corpus shows Claude actually operating
  in a pm/reviewer capacity, not a separately exercised architect identity. `dev`'s charter was left
  unchanged — the corpus confirmed the existing text was already accurate. "No change" was an
  explicitly valid finding, not a failure to find something.
- **Task 2** (dispatched to Codex, job `job-f4c16542`): same treatment for `tpm`, `designer`,
  `marketing`. `tpm`'s charter now precisely describes the implemented ready-story-scan /
  policy-gate-check / ticket-create-or-reuse / daemon-dispatch loop (`synlynk/tpm_sweep.py`), citing
  the 2026-08-24 "ticket-driven approval auto-resume" devlog entry, rather than the vaguer prior
  framing. `marketing`'s Instructions dropped an unsupported universal claim ("writes every PR's
  blog post") in favor of dispatch-conditional framing. `designer` was left unchanged — no
  fabricated track record found.

Every changed section only touched charter body prose — `Instructions`, `Authority & Escalation`,
`Workflow Ownership`. Frontmatter (`schema_version`, `role`, `description`, `durability`, `tools`,
`credentials`) was verified byte-identical to `origin/main` for all 8 roles, including the 6
touched ones, by the spec-compliance review pass.

`docs/charters/corpus-references.md` documents the sourcing for all 6 roles — per-role
**Sources consulted** / **Findings** / **Charter changes made**, with specific devlog dates, memory
section names, and grep commands, all independently verified to exist against the real corpus (not
just asserted) by the review passes.

Both required review stages ran: a spec-compliance pass confirmed frontmatter integrity and citation
accuracy; a code-quality pass confirmed internal consistency across sibling charters (no conflicting
merge-authority claims between `qa`/`architect`/`tpm`), Python string-literal correctness in the
`SEED_CHARTERS` dict, a clean `charter_schema.validate_charter()` run for all 6 changed roles, and a
clean full-suite test run — 2322 passed, 2 skipped, 2 pre-existing `database is locked` failures
(unrelated to this change, present on `origin/main` too).

## Brainstorm Visuals Used

None — #1199 had no brainstorm gate; it went straight from issue to plan per the Design → Plan →
Build sequence.

## What This Achieved on the Path to Autonomy

A charter that claims authority the corpus doesn't back is worse than no charter — it tells a
dispatched agent (or a human reading the roster) that a role can do something it has never actually
been exercised to do. Grounding six charters in real devlog/git history closes that trust gap ahead
of any push toward more autonomous, charter-driven dispatch: the `SEED_CHARTERS` seed text a
brand-new agent gets on `synlynk agent init` now matches what the role has actually demonstrated,
not what the original spec guessed it might.

## Strategic Note: The Goal at the End of This PR

Task 3 — bumping the 6 already-provisioned live agents' runtime charters
(`~/.synlynk/workspaces/.../charter.md`) to match the updated `SEED_CHARTERS` text via
`propose_charter_revision()` — is an explicit post-merge operational step performed directly by
Claude (PM/deploy role), not dispatched, mirroring how PR #1196 handled the same step for `pm`. Once
that's done and the worktree/branch are cleaned up, the next and final open item under #1198 is
#1203 (GOVERNS backlog automation), which still needs its own `superpowers:brainstorming` pass
before a plan can be written.
