# Marketing Goal Ownership — Design

**Status:** Approved by Nikhil, 2026-08-30
**Related:** `goal-0c4e96ff` (book/blog readership growth), `.synlynk/github_apps/`,
`docs/glossary-agent-vs-harness.md`, `docs/charters/corpus-references.md` (marketing section)

## Problem

A new Business Goal, `goal-0c4e96ff`, was created to grow readership of the book
manuscript (`docs/book/`) and the blog series (`docs/blog/`), with 22 existing
stories linked to it (18 primary, 4 secondary). The user asked whether this goal
can become a **permanent responsibility** of the `marketing` charter, with the
agent working **autonomously** against it, rather than requiring Claude to
manually dispatch marketing per task.

Today's `marketing` charter (`synlynk/agent_cli.py:154-175`) is `dispatch-only`
durability, triggered exclusively by an explicit Claude dispatch, scoped to
"the Blog/Comms pass of the Named Release stage" — a per-task output, not a
standing outcome. The charter corpus review
(`docs/charters/corpus-references.md`) found no track record supporting a
broader or self-initiating marketing function, and explicitly struck an
unsupported "every PR" universal claim. Making marketing "permanently
responsible" for an ongoing goal is therefore a real capability change, not a
wording tweak.

## Decisions

Three questions were resolved with the user before this design was written:

1. **Autonomy mechanism:** TPM-driven sweep. `marketing`'s own `durability`
   stays `dispatch-only` — autonomy comes from `tpm_sweep.py`'s existing
   ready-story scanner recognizing stories linked to `goal-0c4e96ff` and
   auto-dispatching `marketing` (routed to Agy) the same way it already
   auto-dispatches other ready stories, with no Claude-in-the-loop trigger.
   This reuses a proven pattern instead of inventing standing agent state,
   which has no precedent in any existing charter.

2. **Backlog authorship:** Claude (PM) proposes new book/blog stories tied to
   `goal-0c4e96ff` at Periodic Maintenance checkpoints (or ad hoc), the user
   approves, then they're linked via `synlynk goal link` and picked up
   automatically by the TPM sweep extension above. Marketing itself is **not**
   granted story-creation authority — that would be new ground with no
   supporting charter precedent, and conflicts with Claude's PM-only
   story-authorship role.

3. **Metrics gap:** The goal's criterion ("increase timespent and per-user
   book downloads/blog post reads") is currently unmeasurable — a repo-wide
   check found no analytics integration (`plausible`, `google-analytics`,
   `gtag`, or a dedicated analytics module), only incidental prose mentions of
   the word "analytics" in unrelated docs. A prerequisite story for real
   readership instrumentation is filed under the goal (see Follow-up below);
   nothing else in the goal is measurable until it lands.

## Changes

### 1. Charter: `synlynk/agent_cli.py`, `SEED_CHARTERS["marketing"]`

Add one line to the **Workflow Ownership** section naming `goal-0c4e96ff` as a
standing outcome, alongside the existing per-release Blog/Comms pass:

```
## Workflow Ownership

Owns the Blog/Comms pass of the Named Release stage. Also owns the standing
readership-growth outcome tracked as goal-0c4e96ff (book manuscript + blog
series), fed by stories the PM links to that goal — dispatched automatically
per the TPM sweep extension below, not on every PR.
```

**Authority & Escalation** and **Instructions** are unchanged: marketing still
cannot author its own stories, still cannot publish anything that commits to
an unapproved roadmap claim, and still only acts on an approved technical
summary per task. Frontmatter (`durability: dispatch-only`) is unchanged.

`docs/charters/corpus-references.md`'s marketing section should get a short
addendum noting this addition and its evidence basis (this design doc + the
goal's creation), matching the file's existing per-role format.

### 2. TPM sweep extension: `synlynk/tpm_sweep.py`

Extend the existing ready-story scan so that a story linked (primary or
secondary) to `goal-0c4e96ff` is eligible for auto-dispatch the same way any
other ready, unblocked story already is — no special-casing beyond resolving
the story's linked goal and confirming the role/harness routing
(`marketing` → Agy) via the existing policy/authority checks. This is the only
piece of this design that is real code; it goes through the normal
Design→Plan→Build sequence (this doc → implementation plan → dispatched
implementer, per the `cli-plumbing`/`refactor` capability lane — Codex or
Grok, not Claude directly) and normal PR review (non-authoring reviewer,
per PR Review Discipline).

### 3. Backlog process (process change, no code)

At Periodic Maintenance checkpoints (or ad hoc, e.g. after a PR ships new
book/blog content), Claude proposes candidate new stories against
`goal-0c4e96ff`. The user approves or declines. Approved stories are linked
via `synlynk goal link <story_id> --goal goal-0c4e96ff [--secondary]`, after
which the TPM sweep extension in (2) picks them up automatically once ready.

## Follow-up (tracked separately, not part of this design's implementation)

- **Analytics instrumentation story** — filed under `goal-0c4e96ff`, routed to
  Grok (infra/js) once its own spec exists per Brainstorm-First Policy. Real
  privacy-respecting site analytics (time-spent) plus book PDF / blog
  download-or-read counts. Blocking: the goal's criterion cannot be evaluated
  until this lands.

## Non-Goals

- No change to marketing's `durability` field or its inability to hold state
  between dispatches.
- No change to marketing's authority to publish or commit to roadmap claims.
- No new story-creation authority for marketing.
- No interim proxy metrics (e.g. GitHub raw-file fetch counts) — explicitly
  declined in favor of filing real instrumentation as a prerequisite.
