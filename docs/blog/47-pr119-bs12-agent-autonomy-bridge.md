# PR #119 — BS-12: The Agent Autonomy Bridge

**Date:** 2026-07-05
**PR:** [#119](https://github.com/nikhilsoman/synlynk/pull/119)
**Branch:** `feat/bs12-agent-autonomy-bridge` → `main`

---

## The Goal at the End of the Previous PR

After Vizor's Efficiency tab shipped (BS-22, PR #118), every partially-visible feature in the HUD was complete enough for Developer Preview. The outstanding strategic gap was the **trust boundary between synlynk and its agents**: synlynk could dispatch agents and watch them run, but it had no way to control what they were *allowed* to do, adjust their configuration per-project, recover when they stalled, guide users through fixing health check failures, or guarantee that agents had internalized the workflow discipline needed to operate autonomously.

That gap is BS-12.

---

## What Moved the Goalpost in This PR

Brainstorming BS-12 surfaced a scope question: the original ticket covered only permissions and harness config. But the session also identified that agent directive files (CLAUDE.md, GEMINI.md, AGENTS.md, GROK.md) were missing explicit SOP coverage for the six workflow disciplines the team had committed to — PR review discipline, brainstorm-first policy, design-spec sequencing, capability-based allocation, cost visibility, and repo hygiene.

These SOPs weren't in a separate ticket. They belong in BS-12 because `synlynk init` and `synlynk sync` are the delivery mechanism, and the doctor wizard (Scope D) is the enforcement surface. Adding them as Scope E made BS-12 the complete trust-boundary release.

The session also produced a firm priority for the two engagement drivers:
1. **Completeness of every visible feature** — no skeleton tabs, no placeholder commands
2. **No drop in engagement** — every new command and surface should make agents easier to use, not harder

Both shaped scope decisions throughout. The handoff protocol (Scope C) addresses engagement continuity when agents stall. The doctor wizard (Scope D) addresses completeness of the health-check experience.

---

## What Shipped

### Scope A — Permission Grants

Role entries in `.synlynk/config.json` now carry a default permission set, defined in `synlynk/_constants.py` as `_ROLE_PERMISSION_DEFAULTS`. Twelve roles are mapped to named capability tiers: `pm`/`review`/`deploy` get `read:*`; `implement`/`test`/`refactor` get `read:*,write:src/,run:tests`; `css`/`templates`/`content` add `write:docs/`; `canvas`/`js`/`infra` add `run:shell`.

`synlynk dispatch` gains `--grant <perm>` and `--revoke <perm>` flags for per-task overrides. Resolution order: role defaults → `.agents/<agent>.json` grants/revokes → per-call flags.

Translation to agent CLI flags via `_permissions_to_flags()` in `synlynk/dispatch.py`:
- Claude: `--allowedTools` list
- Codex: `--approval-policy` (`none` / `untrusted` / `all`)
- Agy: injected as a `## Permissions` section in the task context header (no CLI flag available)

### Scope B — Per-Project Harness Config

New subcommand: `synlynk configure agent <name> [--flag k=v] [--env K=V] [--network-dep host:port]`

Writes to `.agents/<agent>.json` under a new `harness_overrides` key. `dispatch_agent()` merges at call time: baseline → `.agents/harness_overrides` → per-call grant/revoke. `synlynk doctor` TC-2 now reads the merged config rather than the hardcoded baseline.

### Scope C — Handoff Protocol

When a running job accumulates a `STALL_NO_OUTPUT`, `FLATLINE`, or `QUOTA_EXHAUSTED` sentinel, synlynk now writes a `HANDOFF_PENDING` sentinel and surfaces the job in:

```
synlynk jobs --stalled
```

The stalled view shows: job ID, agent, failure sentinel, elapsed time, and the recommended next agent derived from the cycle-capability matrix.

Transfer command:

```
synlynk jobs handoff <job_id> [--to <agent>]
```

On handoff:
1. Job context file (`.synlynk/contexts/<job_id>.md`) gets a `## Handoff Note` appended with failure reason + previous agent
2. `jobs.handoff_count` incremented, `jobs.previous_agents` (JSON array) updated
3. New dispatch launched with the updated context file + new agent
4. `HANDOFF_PENDING` sentinel cleared

**Schema additions:**
```sql
ALTER TABLE jobs ADD COLUMN handoff_count INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN previous_agents TEXT;  -- JSON array
```
Both columns are added via migration in `_get_db()` on first access — no manual migration required.

### Scope D — Doctor Guided Fix Wizard + Escalate

After each TC check failure, `synlynk doctor` now enters an interactive fix loop rather than just printing and exiting. The wizard uses the existing `termios`-based TUI pattern from `cmd_wizard`.

Structured fix paths per TC:

| TC | Failure | Fix offered |
|---|---|---|
| TC-1 | Requires PTY | Show PTY workaround + offer to write config note |
| TC-2 | Bad flags | Apply recommended flags to `.agents/<agent>.json` |
| TC-3 | Network unreachable | Show endpoint list, offer to skip or proxy |
| TC-4 | Missing verbs | Run `synlynk configure agent <name>` |
| TC-5 | Missing SOP sections | Run `synlynk sync --repair-sops` (targeted, not full sync) |

Always-available escape: **"I'm stuck"** — assembles a failure context string from TC results + agent config + last 5 telemetry rows, then calls `dispatch_agent("claude", task=<context>)`. Claude handles the diagnosis conversationally from the same terminal.

### Scope E — SOP Codification

Six SOP string constants added to `synlynk/probe.py`:

| Constant | Section header |
|---|---|
| `_PR_REVIEW_SOP` | `## PR Review Discipline` |
| `_BRAINSTORM_SOP` | `## Brainstorm-First Policy` |
| `_DESIGN_SEQUENCE_SOP` | `## Design → Plan → Build Sequence` |
| `_CAPABILITY_ALLOCATION_SOP` | `## Capability-Based Task Allocation` |
| `_COST_VISIBILITY_SOP` | `## Cost Visibility` |
| `_REPO_HYGIENE_SOP` | `## Repo Hygiene` |

All six are injected into CLAUDE.md, GEMINI.md, AGENTS.md, and GROK.md at `synlynk init` and `synlynk sync` time via `_build_templates()`.

**TC-5 in `synlynk doctor`:** Scans each directive file for all six section headers. Warning (not failure) if absent — non-blocking, matches the existing status philosophy.

**`synlynk sync --repair-sops`:** Reads the existing harness fence body, appends only the missing SOP sections, writes back the merged body. Idempotent: running twice produces no change on the second run.

### Tests

28 new tests added; suite went from **837 → 868 passing** (including 3 added in the review fix pass).

### Review Fixes Applied

A code review after initial implementation caught 6 issues fixed before merge:

1. **Blocking:** `--repair-sops` called `_upsert_harness_fence` with only the missing block as body, replacing the entire existing fence. Fixed: reads existing fence body, merges missing sections in.
2. **Blocking:** TC-5 result omitted from `all_passed` in `cmd_doctor`. Doctor exited 0 despite SOP failures. Fixed: `all_passed` now includes `tc5['passed']`.
3. **Warning:** Handoff note appended to context file but not included in `handoff_task` sent to new agent. Fixed: `handoff_task` rebuilt after append.
4. **Warning:** TC-5 fix menu appeared for every agent in the loop, even those with no missing sections. Fixed: check `tc5['missing'].get(agent)` per-agent.
5. **Warning:** `--flag KEY` (boolean flag without `=`) in `synlynk configure agent` raised `ValueError`. Fixed: `item.partition('=')` with `True` as fallback value.
6. **Warning:** TC-5 doctor fix called full `cmd_sync` instead of targeted SOP repair. Fixed: extracted `_repair_sops_only()` helper.

---

## Brainstorm Visuals

The architecture, scope decisions, and task allocation were developed in a visual brainstorm session. Key frames:

- **Architecture overview** — 5 scopes, 3 shared data foundations, 5-phase delivery
- **Task allocation** — Codex owns Python/TUI/CLI plumbing, Agy owns SOP prose and UX copy
- **Handoff option selection** — prompt-then-handoff chosen over silent auto-handoff

Full brainstorm HTML: [`docs/brainstorm/bs12-agent-autonomy-bridge/`](../brainstorm/bs12-agent-autonomy-bridge/)

---

## What This Achieved

BS-12 closes the trust boundary. synlynk can now:

- **Control what agents can do** — role defaults prevent accidental writes or shell execution by review-only agents
- **Configure agents per project** — no more editing source to adjust a flag for a specific repo
- **Recover from stalls** — HANDOFF_PENDING + `jobs handoff` keeps work moving when an agent quota-exhausts or flatlines
- **Guide users through failures** — the doctor wizard replaces manual diagnosis with structured fix paths and a Claude escalation escape hatch
- **Enforce workflow discipline at init time** — every new repo gets the full SOP playbook baked into all four directive files

Combined with the Live Job Observatory (BS-13) and Vizor (BS-21/22), the Developer Preview now has a complete operational layer: dispatch, observe, diagnose, repair, and hand off — all from the CLI.

---

## The New Goalpost

BS-12 and BS-22 together represent the completion of the **v0.11.0 milestone**: the Agent Ecosystem Operational Layer. The next focus is the **v0.11.0 named release** — CHANGELOG entry, VERSION bump, GitHub Release, and a release blog post capturing the full arc from BS-13 through BS-12.

After that: `chore/modularise-init` (prerequisite for BS-16), then BS-16 Ecosystem Status + Capacity to replace the `is_placeholder` data paths in Vizor with live telemetry.
