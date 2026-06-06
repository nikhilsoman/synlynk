# Live Issue Handling — Synlynk SOP Proposal

**Status:** Proposal  
**Author:** Nikhil Soman  
**Date:** 2026-05-22  
**Applies to:** All Synlynk product repositories and agent workflows

---

## Overview

A **live issue** is any defect, data correctness bug, or UX degradation that affects the primary product experience of a live or beta system. This SOP defines how live issues are declared, investigated, escalated, resolved, and prevented — in a multi-agent development environment where Claude, Gemini, and Codex agents work alongside human engineers.

The goals:
1. **Single source of truth** — every live issue has one canonical ticket with the original observations, investigation findings, and action items as structured comments.
2. **Root cause first** — no fixes are deployed without a confirmed root cause. Symptom patches mask real problems.
3. **Severity-gated escalation** — the investment in RCA documentation scales with the severity of the incident.
4. **Agent-native process** — the SOP is written so AI agents can execute it without human intervention for Sev2 and Sev3 issues, while escalating Sev1 to the human owner.

---

## Severity Levels

| Level | Definition | RCA Doc Required? | Human Review Required? |
|-------|-----------|-------------------|----------------------|
| **Sev1** | Core product broken, data loss/corruption, security incident, or correctness bug visible to users | Yes — full RCA in `docs/rca/` | Yes — human must approve action items before deploy |
| **Sev2** | Major feature significantly degraded; workaround exists | Optional — comment-level RCA on ticket | No — agent can implement fixes autonomously |
| **Sev3** | Minor UX issue or edge case; no functional impact | No | No |

**Severity call heuristic:** If a user (or the founder) would look at the affected screen and immediately question whether the product works — it's Sev1. If a feature is visibly broken but the user can still accomplish their goal — Sev2. If the issue is cosmetic or affects < 1% of flows — Sev3.

---

## Infrastructure Requirements

Each Synlynk product repository needs:

1. **Labels:**
   - `live-issue` — all live issue tickets and their action tickets
   - `sev1`, `sev2`, `sev3` — severity
   - `rca` — ticket has a linked RCA document

2. **GitHub Project:** "Live Issues" board (separate from Programme/Sprint board)
   - All live issue tickets + action tickets go here
   - Filtered view shows only `live-issue` labelled items

3. **Directory:** `docs/rca/` in the repo root — stores Sev1 RCA documents

### Setup commands
```bash
gh label create "live-issue" --description "Production incident or live issue" --color "D93F0B"
gh label create "sev1" --description "Severity 1 — core product broken" --color "B60205"
gh label create "sev2" --description "Severity 2 — major feature degraded" --color "E4A700"
gh label create "sev3" --description "Severity 3 — minor issue" --color "0075CA"
gh label create "rca" --description "Has a linked RCA document" --color "8250DF"
gh project create --owner <org> --title "Live Issues"
mkdir -p docs/rca
```

---

## Issue Numbering

GitHub issues share global numbering and cannot be independently sequenced. Use a title prefix:

```
[LIVE-N] <short description>
```

Where `N` starts at 1 and increments per incident. The prefix makes live issues visually distinct in any list and allows referencing by LIVE number in Slack, comments, and docs.

The action tickets spawned from an RCA also carry `[LIVE-N]` in their title so they're traceable to the originating incident.

---

## Full Process

### Step 1 — Declare

When a live issue is identified (by a human or an agent during a session):

1. Create a GitHub issue:
   - **Title:** `[LIVE-N] <one-line description>`
   - **Labels:** `live-issue`, `sev1/2/3`, `rca` (if Sev1)
   - **Body:** Original observations only — exactly as reported, no analysis yet
   - **Add to:** Live Issues board

2. Announce to the team (Slack / async) if Sev1.

### Step 2 — Investigate

**Before writing any fix:**

- Use `superpowers:systematic-debugging` skill (or equivalent systematic process)
- Trace the full data flow from symptom to source
- Do not propose fixes until root cause is confirmed

### Step 3 — Post Findings

Post findings as a **comment** on the live issue (not in the body — the body preserves original observations):

```markdown
## Root Cause Analysis — Findings

### RC-1: <short label>
**Root cause:** [confirmed mechanism]
**Files:** [file:line references]
**Fix:** [one-sentence description of the fix]

### RC-2: ...

### Severity Assessment: Sev<N>
[Justification]
```

### Step 4 — Write RCA (Sev1 only)

Create `docs/rca/YYYY-MM-DD-LIVE-N-<slug>.md` with:

```markdown
# RCA: <title>

| Field | Value |
| Severity | Sev1 |
| Date | YYYY-MM-DD |
| Impact | ... |

## Timeline
## Root Cause Analysis
## Impact Assessment
## Action Items (table with issue links)
## Prevention
## Resolution Criteria
```

Commit the RCA doc on the current working branch and push. Add `rca` label to the live issue.

### Step 5 — Create Action Tickets

One GitHub issue per fix:
- **Title:** `[LIVE-N] Fix: <description>`
- **Labels:** `live-issue`, `sev<N>`, `priority:p0`, `agent:<who>`, `domain:<area>`
- **Body:** Which root cause this addresses, exact files/lines, acceptance criteria
- **Add to:** Live Issues board

### Step 6 — Post Action Items Comment

Post a final comment on the live issue linking all action tickets:

```markdown
## Action Items Created
| Ticket | Root Cause | Fix |
| #NNN | RC-1 | ... |
```

### Step 7 — Implement

For Sev2/Sev3: agents implement autonomously following the standard feature-branch + PR workflow.

For Sev1: human reviews and approves each action ticket before implementation begins.

### Step 8 — Resolve

When all action tickets are closed:
1. Post a resolution comment on the live issue: what was fixed, resolution criteria met
2. Close the live issue
3. If Sev1: update the RCA doc with actual resolution date

---

## Agent Behaviour

When an agent (Claude, Gemini, Codex) identifies a live issue during a session:

1. **Stop feature work.** Live issues take priority over scheduled features.
2. **Assess severity immediately.** Use the heuristic above.
3. **If Sev1:** declare the issue, investigate, write RCA, create action tickets — then **pause and surface to the human owner** before implementing fixes.
4. **If Sev2/Sev3:** declare, investigate, post findings, create action tickets, implement.
5. **Always post findings as comments**, never edit the original issue body.

Agents must never deploy a fix for a Sev1 issue without explicit human approval, even if the fix looks trivial. Trivial-looking Sev1 fixes often have non-obvious side effects.

---

## RCA Document Template

```markdown
# RCA: <title>

| Field | Value |
|-------|-------|
| Live Issue | LIVE-N / GitHub Issue #NNN |
| Severity | Sev1 |
| Date Detected | YYYY-MM-DD |
| Date Resolved | YYYY-MM-DD or Pending |
| Impact | <who and what> |
| Reporter | <name / agent> |
| Investigator | <name / agent> |

## Executive Summary
<2–3 sentences>

## Timeline
| Time | Event |

## Root Cause Analysis
### RC-1: <label>
**Symptom:**
**Root cause:**
**Fix:**
**Affected files:**

## Impact Assessment
| Dimension | Impact |

## Action Items
| Action | Issue | Priority | Owner |

## Prevention
<bulleted list of process/test changes>

## Resolution Criteria
- [ ] ...
```

---

## Relationship to Programme Board

The Live Issues board is **separate** from the Programme/Sprint board. Live issues are not feature work — they are incidents. Mixing them with feature backlog creates noise and incorrect prioritisation signals.

- Programme Board: planned features, enhancements, spec work
- Live Issues Board: incidents, their action tickets, and resolution tracking

Action tickets from live issues carry `priority:p0` and always jump to the top of implementation queue. They appear on the Live Issues board only, not the Programme Board.

---

## Metrics to Track

| Metric | Target |
|--------|--------|
| Time to declare (from observation to ticket) | < 30 minutes |
| Time to root cause (Sev1) | < 2 hours |
| Time to RCA doc published | < 4 hours of detection |
| Time to first fix deployed (Sev1) | < 24 hours |
| Repeat incidents (same root cause) | 0 |

---

## Appendix — Synlynk Agent Routing for Live Issues

| Agent | Role in live issues |
|-------|-------------------|
| **Claude** | Primary investigator. Runs systematic-debugging, writes RCA, creates action tickets, implements backend/infra fixes |
| **Gemini** | Frontend/data investigation and fixes where domain:frontend or domain:data applies |
| **Codex** | Writes/updates tests that reproduce the live issue and verify the fix |
| **Human** | Approves Sev1 action items before deploy; provides system access (credentials, console) when agents can't |

All agents follow the same declaration and posting process above. Agent identity is recorded via `agent:claude`, `agent:gemini`, `agent:codex` labels on action tickets.
