# Workspace Policy Layer & Autonomous Loop — Design

## Goal

Get synlynk's own repo to full autonomous operation by 2026-08-31: a real story can go
strategy → spec/plan → TPM story → cron-dispatched → verified → PR → role-scoped
non-authoring review → merge, with roadmap/devlog/costs reconciling automatically —
without Claude or Nikhil manually driving any individual step — except at reserved
approval points (major decisions, security-sensitive changes, GitHub policy changes,
irreversible merges, named releases), where the loop parks the item, notifies Nikhil,
and opens a GitHub ticket assigned to him with a context pack, the same shape a ticket
takes when any other agent can't proceed alone.

This closes the "Phase 1" item from the informal full-autonomy roadmap
(`project-docs/memory.md`, 2026-08-22) and advances the "Evidence and GitHub
integration" week of `docs/strategy/road-to-autonomous-ops.md`.

## Scope

**In scope:** synlynk's own repo only. The policy-configuration layer (this is the part
that generalizes), the enforcement wiring, the cron sweep, and the approval-gate
mechanism.

**Out of scope:** actually rolling this out to rxcc or cc-videoreframing (Phase 2/3 —
separate future specs), team/enterprise features beyond reserving schema space for them,
any GitHub Actions/webhook infrastructure (the sweep is polling, not event-driven, for
this cycle).

**Explicitly not re-litigated:** the #423 per-role GitHub App identity mechanism and the
GOVERNS event contract (`job_terminal`, `review_submitted`, `synlynk events tail`) are
both already shipped and are built on top of, not redesigned.

## Why now

PR #1110 (merged 2026-08-23) proved role-scoped GitHub identities work end-to-end but
left two things true: (1) branch protection is not actually turned on for synlynk's own
repo yet — the mechanism is reachable, not enforced — and (2) every policy governing who
can do what (task allocation, merge authority, release authority, roadmap authority) is
still hardcoded prose in `CLAUDE.md`, which means porting the same autonomy pattern to
rxcc or cc-videoreframing would require editing synlynk's own code, not just supplying
different configuration. Both gaps get closed together here because they're the same
underlying mechanism (config-driven gates) viewed from two angles.

## Architecture

### 1. Two-tier policy schema

Workspace-level defaults live above any single repo, matching the existing workspace
construct from `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md`
(`~/.synlynk/workspaces/<name>/state.db`). Repo-level files override sparse fields.

**Workspace defaults — `~/.synlynk/workspaces/<name>/policy.json`:**

```json
{
  "schema_version": 1,
  "org": {
    "org_id": null,
    "teams": [],
    "sso_provider": null,
    "seat_limits": null
  },
  "defaults": {
    "roadmap_authority": {
      "can_edit_roadmap": ["pm"],
      "can_create_goals": ["pm", "architect"]
    },
    "dev_authority": {
      "task_allocation": {
        "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
        "test":      {"harness": "codex", "fallback": ["grok", "agy"]},
        "css":       {"harness": "agy"},
        "templates": {"harness": "agy"},
        "canvas":    {"harness": "grok"},
        "js":        {"harness": "grok"},
        "infra":     {"harness": "grok"},
        "refactor":  {"harness": "codex"},
        "cli-plumbing": {"harness": "codex"},
        "gh_write":  {"harness": "claude", "fallback": ["agy"]}
      }
    },
    "merge_authority": {
      "can_merge": ["qa"],
      "require_non_authoring_review": true,
      "review_fallback": "comment_checklist"
    },
    "release_authority": {
      "can_cut_release": ["pm"],
      "requires_human_approval": true
    },
    "approval_required_for": [
      "security_sensitive_paths:.github/workflows/**,.synlynk/policy.json,.synlynk/github_apps/**",
      "irreversible_merge",
      "named_release",
      "roadmap_authority_change"
    ],
    "agent_roles": {
      "pm":        {"default_harness": "claude", "scope": ["roadmap", "review", "deploy", "brainstorm"]},
      "qa":        {"default_harness": "claude", "scope": ["review", "merge"]},
      "dev":       {"default_harness": "codex",  "scope": ["implement", "test"]},
      "architect": {"default_harness": "claude", "scope": ["roadmap", "brainstorm"]}
    }
  }
}
```

**Repo override — `<repo>/.synlynk/policy.json`, sparse, field-level merge:**

```json
{
  "schema_version": 1,
  "repo_id": "synlynk",
  "overrides": {}
}
```

Merge rule: for each top-level key under `defaults`, if the repo's `overrides` supplies
that key, the repo's value replaces the workspace default's value for that key
*entirely* (not deep-merged further) — e.g. a repo overriding `merge_authority` supplies
the whole `merge_authority` object, not just the one field it wants to change. This
keeps the merge logic simple (one level of override) and matches how policy differences
between repos tend to be — usually one whole concern differs (e.g. rxcc's merge rules),
not one field inside a concern.

A repo with no `.synlynk/policy.json` at all inherits workspace defaults unchanged —
this is how rxcc and cc-videoreframing stay on current (fully manual) behavior until
they explicitly opt in.

**Team/enterprise stubs:** `org.teams[]`, `org.sso_provider`, `org.seat_limits` are
reserved fields, always present, always null/empty in this cycle. Nothing reads or
writes them beyond schema validation. They exist so that when team sync (NATS at Tokq
Alpha, per the workspace design doc) lands, `policy.json` doesn't need a breaking
migration.

### 2. `synlynk/policy.py` — enforcement module

New module, single entry point:

```python
def check_authority(action: str, role: str, repo_path: str) -> AuthorityResult:
    """
    action: one of "roadmap_edit", "goal_create", "task_dispatch:<task_type>",
            "merge", "release_cut"
    Returns AuthorityResult(allowed: bool, requires_approval: bool, reason: str)
    """
```

Loads and merges the two-tier config (cached per-process, re-read if either file's mtime
changes — same staleness pattern already used for `.synlynk/config.json`). Checks the
action against the relevant policy section, then checks `approval_required_for` against
the action/path to decide `requires_approval`.

**Call sites gated before any `gh`/subprocess action:**

| Call site | File | Gate |
|---|---|---|
| `dispatch_agent()` | `synlynk/dispatch.py` | `task_dispatch:<task_type>` — resolves the harness from `dev_authority.task_allocation` instead of the hardcoded capability matrix defaults |
| Worktree PR merge path | `synlynk/jobs.py`, `_maybe_open_worktree_pr` and the actual merge call | `merge` |
| `synlynk release` | wherever release-cut logic lives | `release_cut` |
| `synlynk roadmap` / `synlynk goal create` | `synlynk/cli.py` | `roadmap_edit` / `goal_create` |

If `check_authority` returns `allowed=False`, the action raises the same
`RuntimeError`-style fail-closed pattern established by #569's role resolution — no
silent skip.

If `requires_approval=True`, the caller does not proceed to the gated action; instead it
hands off to the approval-gate flow (Section 4).

### 3. `synlynk policy sync-branch-protection` — GitHub backstop

New CLI command. Reads the merged policy's `merge_authority` and
`approval_required_for`, calls the GitHub API (`PUT /repos/{owner}/{repo}/branches/{branch}/protection`)
to configure: required PR reviews (count derived from
`require_non_authoring_review`), required status checks (existing CI job names, read
from `.github/workflows/`), and restricts direct pushes to `main`. This is the mechanism
that actually flips branch protection on for synlynk — closing Phase 1's originally
stated exit criterion — and is also the backstop against the #1109 direct-gh/MCP-bypass
concern: even if something calls `gh`/the GitHub API directly, bypassing synlynk's own
`check_authority` gate, GitHub itself still enforces the same policy.

Run manually once per policy change (not on every sweep pass) — idempotent, safe to
re-run.

### 4. `synlynk tpm sweep` — the loop trigger

New CLI command. One pass:

1. Query `stories` for `status = 'ready'`.
2. For each story, walk its next lifecycle step (dispatch → verify → PR → review →
   merge), calling `check_authority` before each.
3. If allowed: perform the step via existing machinery (`dispatch_agent()`,
   `synlynk pr check`-equivalent, merge). Emit the existing `job_terminal` /
   `review_submitted` GOVERNS events as today.
4. If `requires_approval`: set story status to `awaiting_approval`, emit a new
   `approval_requested` GOVERNS event `{story_id, action, reason}`, run the
   approval-gate flow (Section 5), and move to the next story — never blocks the batch.
5. Log a per-pass summary (stories advanced, stories parked, stories failed) — surfaced
   via `synlynk status`.

For this cycle, `synlynk tpm sweep` is invoked by a recurring external trigger (a real
`cron` entry, or — until that's set up — a ScheduleWakeup-style periodic call from a
Claude PM session acting purely as the timer, not as the driver of individual steps).
The distinction that matters for the exit criterion: **the timer doesn't decide
anything** — every decision inside a sweep pass is made by `check_authority` and the
existing lifecycle machinery, not by whoever/whatever triggered the pass.

### 5. Approval gate

When a sweep step trips `requires_approval`:

1. `awaiting_approval` GOVERNS event recorded (extends the existing event-contract
   pattern from PR #922 — same shape as `job_terminal`, new `event_type`).
2. `gh issue create` opens a ticket assigned to Nikhil (`--assignee`), titled
   `[APPROVAL] <action> — <story_id>`, body containing: the goal/story context, the
   diff or PR link if one exists yet, and *why* it tripped the gate (which
   `approval_required_for` rule matched).
3. A PushNotification fires with a one-line summary and the ticket link.
4. Resolution: Nikhil comments a defined keyword (`approve` / `deny <reason>`) on the
   ticket, or merges/acts directly on GitHub. The next sweep pass detects resolution via
   the existing `scan_local_events()` pattern (already extended once for
   `review_submitted` in PR #922) watching for the comment or the direct action, updates
   story status accordingly, and closes the ticket.

This treats Nikhil as a first-class assignee in the same lifecycle any dispatched agent
already uses when it can't proceed alone — no separate human-only UI.

## Release sequencing

**v0.15.0 "Workspace Policy Layer"** (target ~2026-08-26/27):
- `policy.json` schema (workspace + repo tiers), `synlynk/policy.py` with
  `check_authority()`.
- Migrate synlynk's own `CLAUDE.md` tables (Capability-Based Task Allocation, PR Review
  Discipline, Named Release Policy authority) into its own `policy.json`; `CLAUDE.md`
  keeps a short pointer instead of the full tables.
- Wire `check_authority` into the four call sites above.
- `synlynk policy sync-branch-protection` command; run it once against synlynk's repo —
  **branch protection actually enabled**, closing Phase 1's original exit criterion.

**v0.16.0 "Autonomous Loop"** (target ~2026-08-30/31):
- `synlynk tpm sweep` command, `awaiting_approval` GOVERNS event, GitHub-ticket +
  PushNotification approval-gate flow, resolution-detection via `scan_local_events()`.
- Live proof: one real story run start-to-finish through the sweep unattended, including
  at least one approval-gate pause and resolution, as the Aug 31 demo.

If v0.15.0 slips past ~08-27, v0.16.0's window compresses — flagged now rather than
discovered on the 30th.

## Testing

Each release gets real dispatch-based unit/integration tests (delegated to
Codex/Grok/Agy per this project's own task-allocation rules — Claude's role stays
PM/review/deploy). `check_authority()` gets direct unit tests for allow/deny/
requires_approval across both schema tiers and the override-merge rule. Both releases
get one live dogfood run before merge, matching the two-independent-harness validation
pattern already used for #423.

## Open risks

- **8-day window is tight** for two Named Releases plus a live unattended demo; the
  sequencing above is the fallback-conscious ordering (policy layer, which has
  standalone value, ships first regardless of whether the sweep makes it in time).
- **Polling cron vs. event-driven** is a deliberate simplification for this cycle; a
  GitHub Actions-based reactive trigger is a natural v0.17.0+ follow-up, not blocking
  Aug 31.
- **`check_authority` call-site coverage** — if a future code path performs a
  merge/release/roadmap action without routing through one of the four gated call
  sites, it silently bypasses policy. Mitigated short-term by the branch-protection
  backstop (Section 3); full closure of the bypass surface is #1109's scope, not this
  spec's.
