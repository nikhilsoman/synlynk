---
title: "PR #880 — Agent vs Harness: Phase 0 of the Roles & Charters Roadmap"
date: 2026-08-10
series: "Building the OS for Multi-Agent Development"
post: 113
pr: "#880"
---

# Agent vs Harness — Phase 0 Terminology

## Broader goal (previous)

The agent-roles-charters-design spec (§10) laid out a 5-phase roadmap to formalize two concepts synlynk had been conflating: **Agent** (a persistent role identity with a charter — pm/architect/tpm/dev/designer/qa/marketing/synlynk-bot) versus **Harness** (a swappable execution backend — Claude/Agy/Grok/Codex/local) that runs a dispatched task. Phase 0 was scoped narrowly: fix the terminology and its most visible conflation point, the Capability-Based Task Allocation table, with no new infrastructure.

## Why this PR

The table in every directive file (CLAUDE.md/GEMINI.md/AGENTS.md/GROK.md) was headed `| Role | Agent | Tasks |`, mapping roles to Claude/Agy/Grok/Codex — which is actually a Role-to-Harness mapping. Left uncorrected, that heading would keep training every dispatched agent (and every human reading it) to use "Agent" for the wrong concept right as the later phases (manifests, memory, capability registry, portability) start building real infrastructure on the correct one.

## What shipped

1. **`docs/glossary-agent-vs-harness.md`** — the canonical definition, written once so every later phase and every directive file can link to it instead of re-explaining the distinction.
2. **`synlynk/probe.py`** — the capability-table generator and its `_repair_capability_allocation_sop()` counterpart both fixed: header is now `| Role | Harness | Tasks |`, with a glossary link and corrected empty-fallback wording. TDD: `test_capability_allocation_table_uses_harness_not_agent_header` added first.
3. **`doctor --fix` regen** — CLAUDE.md/GEMINI.md/AGENTS.md/GROK.md resynced. This pulled in more than just the table fix, since two of the four files were on stale template versions from as far back as 2026-07-30 — accepted as legitimate tool output rather than hand-reverted, since editing inside a `synlynk-managed — do not edit` fence by hand would violate its own convention.
4. **Hand-written section** — a "Terminology: Agent vs Harness" section added directly to this repo's own CLAUDE.md, outside the generated fence.
5. **Wording sweep** — `.synlynk/roles.yaml`, `README.md`, `SYNLYNK_GUIDE.md` fixed to stop saying "agent" where "harness" was meant.

Execution was subagent-driven per the role split: 5 tasks, each dispatched to Codex (Task 2, Python + test) or Agy (Tasks 1/3/4/5, docs/YAML), independently verified and cherry-picked onto the branch one at a time. Two non-blocking complications along the way: an unrelated auto-generated `.agents/*.json` side-commit excluded from the cherry-pick, and a stale untracked `.synlynk/roles.yaml` copy that had to be removed before Task 5's commit would apply cleanly.

**Review hit its own infrastructure gap.** Per PR Review Discipline, review was dispatched to Grok first (GitHub-write default per #426) — it failed immediately with a 402 "Grok Build usage balance exhausted," $0 cost, no work done. Fallback to Agy (the established headless-gh-write pattern from PRs #589/#594) hit a second, quieter failure on the first attempt: the job returned `SYNLYNK_TASK_RECEIVED: <hash>` and exit 0 with no actual review — traced to `--requires-gh-write`, which needs a role-scoped GitHub App token that wasn't provisioned for this dispatch, and appears to fail closed silently rather than raising an error. Dropping that flag (Agy already had scoped local `gh` allow-rules) produced a real review: full 1856-test suite run, a formal checklist review comment, and a genuine merge conflict caught and — in a race with Claude's own concurrent conflict-resolution attempt — resolved and merged by Agy itself before Claude's push landed.

## On the long arc

Phase 0 is the cheapest, lowest-risk phase in the roadmap by design — pure terminology and doc wiring, no schema, no new CLI surface. It exists so Phases 1–4 (agent manifests, memory, capability registry, portability) build on a vocabulary that's already correct rather than requiring a rename mid-flight. It also produced two live data points for the dispatch-reliability backlog: Grok's build-quota exhaustion as a distinct failure mode from its previously-documented session-expiry, and `--requires-gh-write`'s silent no-op path — filed as follow-up rather than fixed inline, since fixing dispatch-harness internals is out of scope for a docs-terminology PR.

## New goalpost

Terminology is correct across code, docs, roles.yaml, and the capability table. Phase 1 (agent manifests) is next and is where the roadmap starts adding real structure rather than just naming it correctly.
