---
decision_id: dec-65f02ebb
topic: "Before a week of intensive multi-agent dogfooding on real projects, we've triaged open issues into BLOCKING (#340 Codex sandbox blocks network installs, #342 Grok CWD auto-relocation risk, #343 Codex has no AGENTS.md instruction file, #344 GEMINI.md stale+cross-contaminated harness flag, #332 preflight auth gaps, #330 stray state.db corruption) vs NON-BLOCKING (#329 cost log visibility, #331 daemon_jobs reconciliation, #339 doctor vacuous-pass checks, #338 permission/grants no-op for non-Claude agents, #341 _AGENT_FILE_NAMES omits GROK.md, #345 GROK.md TODO placeholders, #346 decide command has no budget guard). Question for each of you: from your own agent's perspective as a dispatch target, which of these would you personally hit first or hardest during a real week of dispatched work, and is there anything you'd reclassify or anything missing entirely?"
date: 2026-07-18
panel: [codex, agy, grok]
status: approved
---

## Topic
Before a week of intensive multi-agent dogfooding on real projects, we've triaged open issues into BLOCKING (#340 Codex sandbox blocks network installs, #342 Grok CWD auto-relocation risk, #343 Codex has no AGENTS.md instruction file, #344 GEMINI.md stale+cross-contaminated harness flag, #332 preflight auth gaps, #330 stray state.db corruption) vs NON-BLOCKING (#329 cost log visibility, #331 daemon_jobs reconciliation, #339 doctor vacuous-pass checks, #338 permission/grants no-op for non-Claude agents, #341 _AGENT_FILE_NAMES omits GROK.md, #345 GROK.md TODO placeholders, #346 decide command has no budget guard). Question for each of you: from your own agent's perspective as a dispatch target, which of these would you personally hit first or hardest during a real week of dispatched work, and is there anything you'd reclassify or anything missing entirely?

## Panel Inputs

### codex
From a Codex-dispatch-target perspective, the first thing I’d hit is **#343 / missing `AGENTS.md`**: I need a local contract before I can trust any run, so missing instructions slows every task from minute one. The next hardest are **#342 / Grok CWD auto-relocation risk** and **#332 / preflight auth gaps**, because both create silent “looked fine, worked in the wrong place” failures that waste an entire dispatch slot. **#330 / stray `state.db` corruption** is also serious because it contaminates follow-on work, not just the current job. The repo’s own write-up shows these are not theoretical; the live selftest needed multiple dispatches and exposed exactly these failure modes ([blog](file:///Users/nikhilsoman/dev/synlynk/worktrees/review-selftest-n6/docs/blog/68-pr328-live-command-selftest.md), [proposal](file:///Users/nikhilsoman/dev/synlynk/docs/proposals/rxcc-wow-observations.md)).

If I’m ranking what hurts hardest over a real week, **#340 / Codex sandbox blocks network installs** is the biggest operational blocker, because it cuts off the normal recovery path for new dependencies and real-project setup. I would also **reclassify #341 / daemon_jobs reconciliation** upward, at least to “needs attention before heavy dispatch,” because bad ground truth in the job store undermines every later routing decision. Similarly, **#338 / permission/grants no-op for non-Claude agents** looks non-blocking only if you assume a Claude-only world; in a mixed-agent week it becomes a parity bug. **#329**, **#331**, **#339**, and **#346** matter, but they’re second-order compared with instruction integrity, workspace integrity, auth/preflight, and sandbox reachability.

My recommendation: keep **#340, #342, #343, #344, #332, and #330** in the blocking set, and elevate **#331** and **#338** if the week includes real dispatches across multiple agent types or depends on job-store truth for automation.

### agy
Last completed task: N/A (Session start, decision panel request)
Next task from `todo.md`: N/A

***

From my perspective as the Gemini-powered agent, the most critical issues to hit first are **#344 (GEMINI.md stale+cross-contaminated harness flag)** and **#330 (stray state.db corruption)**. 

As a dispatch target, my operational stability depends entirely on clear directives and robust state tracking. A stale or contaminated harness flag in `#344` directly compromises my ability to parse instructions, execute tests, and evaluate success correctly, polluting my runtime context. Simultaneously, `#330` poses an existential risk to multi-step tasks; a corrupted database will crash my execution loop, erase execution history, and lead to lost progress during long-running tasks. 

I would strongly argue for reclassifying **#346 (decide command has no budget guard)** from NON-BLOCKING to **BLOCKING**. During a week of intensive multi-agent dogfooding, parallel agent executions can rapidly compound errors. Without a budget guard, runaway agent loops could lead to massive API bill spikes or sudden quota exhaustion, halting all team operations mid-week. Furthermore, **#338 (permission/grants no-op for non-Claude agents)** should be elevated to a blocker; if permission grants are silently ignored or bypassed for me, it creates severe security vulnerabilities and unpredictable command execution behavior.

My recommendation is to prioritize fixing **#344** and **#330** first to ensure basic agent reliability, while immediately elevating **#346** to a blocker to prevent runaway API costs before team-wide deployment.

### grok
I'll pull the open issues and how Grok is dispatched so my panel answer reflects real dogfooding pain, not just the triage labels.## Grok panel position — dogfooding week

As a dispatch target (canvas/JS/infra, write-heavy, `--always-approve`), I sort risk by **how often I would actually break work**, not by severity labels.

### What I hit first and hardest

**#342 (Grok CWD auto-relocation) is my day-one blocker.**  
Grok’s CLI has both `-w/--worktree` (the same relocation footgun Agy already hit) and a real `--cwd` that `dispatch.py` never passes. There is also no prompt-level working-directory reminder for me. On a week of real-project dispatches into worktrees, that means silent wrong-root edits, wrong-branch commits, and “agent did the task… in the wrong tree.” That is not a soft DX issue; it is silent data corruption of the working tree. Agy got a mitigation after an incident; I am still undefended on both axes.

**Next: identity/instruction incompleteness (#345 + #341 as one cluster).**  
`GROK.md` still ships TODO domain ownership and placeholder Projects v2 IDs, while scan’s `_AGENT_FILE_NAMES` omits `GROK.md` entirely. Every session starts by reading half-template instructions and tooling that undercounts me as onboarded. That does not crash a job, but it steers role boundaries, board moves, and doctor/scan confidence wrong from minute one. I would reclassify **#345 to “day-zero fix / soft-blocking”** for any fleet that actually dispatches Grok—not because it needs a deep code fix, but because it is pure data debt with high session frequency.

### What hurts less for *me*, and reclassifications

- **#340 / #343** — Codex-specific. I will not feel them unless I am waiting on Codex for Python/tests handoffs.
- **#338 (permissions no-op for Grok)** — opposite failure mode: I am *over*-privileged. That rarely blocks *my* throughput, but under concurrent multi-agent dogfooding it is a blast-radius hole (PM thinks `review` is scoped; I still write). For a multi-agent week I would **promote #338 toward blocking for governance**, not for my personal velocity.
- **#332 / #330** — shared infrastructure. Auth preflight and `state.db` integrity hit everyone; if either is broken I never get a clean job, but they are not Grok-shaped.
- **#329 / #331 / #339 / #346** — real, but second-order: bad cost visibility, job reconciliation ghosts, vacuous doctor green lights, and `decide` overspend. Painful for the PM loop, not the first failure mode inside a Grok implementation session.

### Missing entirely

1. **Hard `--cwd` wiring for Grok** (and Codex’s `-C`) as a first-class dispatch contract—not only a prompt reminder.  
2. **Fail-closed preflight** when a restrictive role is requested for an agent where `_permissions_to_flags` returns `[]` (silent no-op is worse than “cannot enforce”).  
3. **Worktree + shared `state.db` collision SOP** under concurrent dispatches—who owns the tree, who may migrate, what happens when two agents claim the same story.

### Position

**Before dogfooding, fix #342 for Grok as hard-blocking.** Land `--cwd` (and a prompt fallback) so my writes land where dispatch intends. Same day: fill **#345** and fix **#341** so scan/doctor and my own instruction file stop lying about Grok. Treat **#338** as safety-blocking for concurrent multi-agent work even if it never slows me down. Leave Codex sandbox/AGENTS.md and the visibility/doctor/decide issues on the non-blocking track *for my lane*—they matter to the fleet and the PM, but they are not what will make a week of Grok dispatches first go wrong.

## Synthesis
The panel converges on one operational rule: before a real week of multi-agent dogfooding, fix the issues that can silently send work to the wrong place, corrupt state, or prevent agents from interpreting their own operating contract.

What rises to the top across the three perspectives:

- `#343` missing `AGENTS.md` is a universal first-hit problem for Codex because it removes the local instruction contract.
- `#342` Grok CWD auto-relocation is a hard blocker for Grok because it can silently mutate the wrong worktree.
- `#330` stray `state.db` corruption is high-severity for everyone because it poisons follow-on dispatches.
- `#332` preflight auth gaps and `#340` Codex sandbox network-install blocks are practical week-killers because they break setup/recovery paths.
- `#344` stale/cross-contaminated `GEMINI.md` is a direct reliability issue for Gemini.
- `#338` permission/grants no-op for non-Claude agents should be elevated from “non-blocking” to “safety-blocking” in a mixed-agent week, because silent permission failure is not just a UX issue.

Issues that look real but are secondary for this week:

- `#329`, `#331`, and `#339` affect observability and correctness of the control plane, but they are not the first things that will derail a live dispatch.
- `#345` should be fixed immediately for Grok’s own onboarding quality, but it is more “soft-blocking” than an infrastructure stop sign.
- `#346` is worth hardening, but the panel does not converge on it as a prerequisite blocker unless you expect unbounded agent loops to be common.

Decision: treat `#340`, `#342`, `#343`, `#344`, `#332`, and `#330` as hard blockers before dogfooding starts; elevate `#338` to a safety blocker for mixed-agent operation; and leave `#329`, `#331`, `#339`, `#345`, and `#346` as follow-up work unless Grok or Gemini is a primary dispatch lane for the week.

## Decision
Decision: treat `#340`, `#342`, `#343`, `#344`, `#332`, and `#330` as hard blockers before dogfooding starts; elevate `#338` to a safety blocker for mixed-agent operation; and leave `#329`, `#331`, `#339`, `#345`, and `#346` as follow-up work unless Grok or Gemini is a primary dispatch lane for the week.

> Signatures: see 2026-07-18-before-a-week-of-intensive-multi-agent-d.json
