# Synlynk Roadmap and Todo Governance Under High-Velocity Use

**Date:** 2026-08-10  
**Status:** Strategy proposal; implementation requires a separate approved spec  
**Basis:** Project-goals and roadmap alignment review, maintainer operating constraints, State Engine design, and GOVERNS lifecycle design

## Executive conclusion

Synlynk's roadmap drift is not primarily a Markdown problem. SQLite solved an important part of the problem: it can be the authority for structured state and can regenerate roadmap, todo, memory, and cost projections. It does not solve the harder problem of recognizing that meaningful work happened, identifying which goal it served, and recording work that began outside the formal story workflow.

GOVERNS improves this by adding lifecycle checkpoints, events, and goal-contribution checks. It is still mainly a story lifecycle mechanism. It does not yet cover the full set of work that occurs in practice: direct implementation sessions, strategy decisions, review and release work, cross-project investigation, maintenance, and exploratory work that becomes important only after the fact.

The correct response is not more manual documentation. It is a lightweight activity ledger around a **work envelope**:

1. Every meaningful session or dispatched unit starts with a scope and an intended goal.
2. Synlynk automatically collects evidence of what happened.
3. Checkpoint closes the envelope by attributing, parking, or explicitly exempting the work.
4. Roadmap and todo are generated views of the resulting structured state.

The user's devlog remains the narrative spine of this system. The work envelope should index and protect the devlog, not replace it.

The system should tolerate high velocity. It should warn and recover rather than block ordinary work. Stronger gates belong at story readiness, PR check, release, and periodic roadmap review boundaries.

## Product and operating thesis

Synlynk should remain a local-first measurement, continuity, and arbitration layer for heterogeneous coding harnesses. Its near-term operating priority is:

> Ship useful work quickly, with measured cost and quota discipline, while preserving enough structured evidence that the next session can understand what changed and why.

This makes roadmap governance a reliability feature, not a separate PM ceremony. The governance system must protect four things simultaneously:

- frugal token and quota use;
- sustainable quality and low rework;
- high shipping velocity;
- continuity across Synlynk and related projects.

## Why SQLite alone did not eliminate drift

SQLite is authoritative only for events that enter SQLite. Current gaps are at the boundary between human activity and structured state:

### 1. Intent is not captured at session start

A user can begin with a valid goal, discover a more urgent problem, and finish on a different but related outcome. If there is no session-level record, the database sees only fragments: jobs, commits, costs, and perhaps a late story.

### 2. Story attribution is incomplete

Dispatch now creates or resolves stories, and GOVERNS can record whether a story has a goal contribution. But direct edits, design sessions, review work, release work, and some maintenance actions can still occur without a story or goal.

### 3. Generated projections do not create coverage

Regenerating `roadmap.md` and `todo.md` prevents competing edits, but it cannot add work that was never represented in the database. A perfect projection of incomplete input remains incomplete.

### 4. GOVERNS checkpoints are lifecycle gates, not a universal activity ledger

The current GOVERNS direction is correct: use events, goal contributions, story readiness, PR checks, and nudges. The missing layer is a durable record of work envelopes and unresolved attribution. Without that, a soft warning can be repeatedly ignored while the roadmap remains technically consistent but semantically stale.

### 5. Cross-project work has no natural home

Work discovered in rxcc or vdowrx may improve Synlynk, but it should not automatically become a Synlynk roadmap item. The system needs to record the reference and the relationship without forcing premature scope transfer.

### 6. GitHub Issues are a second work surface

GitHub is not merely a publishing destination. Issues are where bugs, requests, live incidents, review findings, and cross-project discoveries enter the system. Synlynk already has partial issue integration: dispatch can associate an issue, story provisioning can derive `story-issue-N`, stories carry `gh_issue`, and the Live Issue SOP defines severity, RCA, action-ticket, and closure behavior.

The gap is that GitHub issue state is not yet treated as a reconciled work stream. An issue can be opened, commented on, linked to a story, implemented through a PR, and closed across several sessions without one durable local work envelope tying the evidence together. Conversely, local work can create a story or PR without an explicit issue disposition.

## Proposed model: work envelopes

Introduce a first-class `work_session` or `activity_envelope` record in the local SQLite state. This is not a replacement for goals or stories.

```text
Goal       = durable outcome and why it matters
Roadmap    = ordered projection of goals and horizons
Story      = concrete executable unit of work
Work       = what actually happened during a session or dispatch
Evidence   = jobs, commits, decisions, plans, PRs, costs, and files touched
```

Each work envelope should contain:

- `session_id`;
- project/repository scope;
- start and end timestamps;
- intended `goal_id`, optional at session opening;
- linked `story_id` values;
- evidence references: job IDs, commits, decisions, plans, PRs, and cost rows;
- final disposition: `completed`, `continued`, `parked`, `maintenance`, `exploration`, or `needs_attribution`;
- attribution confidence and a short human note when inference was used.

The important design choice is that `needs_attribution` is a valid temporary state. It prevents silent loss without forcing the user to stop every time reality changes.

## The devlog is the session record

The devlog was the original answer to continuity: what the user asked, what the harness understood, what it did, what was discovered, what changed direction, and what should happen next. That role should be retained and made more reliable.

There are three distinct layers, and they should not be collapsed:

```text
Raw conversation / harness transcript  = complete evidence of what was said
User devlog                            = durable narrative of intent, reasoning, and outcome
Work envelope                          = structured index linking narrative to goals and artifacts
Roadmap / todo                         = generated planning views
```

Today, `devlog_entries` and the generated per-user devlog file provide durable entries, but the normal protocol asks the harness to append a summary at task boundaries. That means the devlog is often a retrospective summary, not a complete record of every user turn and harness response. The distinction should be explicit rather than accidental.

### Recommended devlog contract

For each work envelope:

1. **Opening entry:** preserve the user's initial intent in the user's own words, plus the selected goal, project scope, and session ID.
2. **Checkpoint entries:** append concise, chronological summaries of decisions, discoveries, changed scope, and evidence. These are the context-efficient working record.
3. **Closing entry:** record what shipped, what did not, cost/quota outcome, quality/verification outcome, unresolved items, and the next recommended action.
4. **Raw transcript pointer:** retain the complete user/harness exchange as an append-only local session artifact when available, with a hash and line/count metadata in SQLite. Do not inject the full transcript into normal context.

The raw transcript is the audit record; the devlog is the readable continuity record. If transcript capture is unavailable, the devlog should say so explicitly rather than implying completeness.

### Database shape

The existing `devlog_entries` table should gain relationships to the work envelope rather than being bypassed:

- `session_id`;
- `goal_id`;
- `scope_repo`;
- `entry_kind` (`open`, `checkpoint`, `close`, `decision`, `handoff`);
- `source` (`user`, `harness`, `system`);
- evidence references or a JSON metadata field.

A separate `session_transcripts` index can point to local JSONL or compressed transcript artifacts with `session_id`, path, hash, byte count, and availability. Keeping raw turns out of generated context preserves quota and latency while retaining recoverability.

### What must be automatic

The user should not have to manually write a devlog entry after every small action. Synlynk should:

- create the opening envelope and initial devlog entry at session start;
- append system evidence automatically when jobs, commits, decisions, PRs, issues, and costs are observed;
- ask the harness for a compact checkpoint summary at natural boundaries;
- append the final close entry through `synlynk checkpoint`;
- regenerate the Markdown devlog from `devlog_entries` when the project is migrated.

The harness still supplies interpretation and narrative, while SQLite supplies identity, timestamps, links, and evidence. This preserves the human-readable devlog without relying on memory or discipline to maintain its links.

### Devlog and roadmap relationship

The devlog should be the first place where new intent and changed direction are recorded. It should not silently mutate the roadmap. At checkpoint, Synlynk classifies the entry:

- existing goal progress;
- new candidate goal;
- maintenance;
- exploration;
- cross-project reference;
- unresolved attribution.

Only the first category updates existing progress automatically. A new candidate goal is proposed for acceptance, and only acceptance promotes it into roadmap/todo state. This keeps the devlog complete without turning every thought, question, or harness suggestion into a commitment.

## Minimal operating loop

### 1. Open a session in one line

At session start, Synlynk should ask or accept:

```text
synlynk session open --goal <goal-id> --scope synlynk
```

For a normal continuation, the command can infer the last active goal and ask only for confirmation. For exploratory work, the user can open a session with `--mode exploration` and no goal.

This should take less than 15 seconds. It is the only intentional PM action required at session start.

### 2. Auto-link normal work

- Dispatches inherit the active session, goal, and project scope.
- A new story inherits the active goal unless explicitly overridden.
- Specs, plans, decisions, and release work created during the session inherit the session ID through command context or a lightweight local session marker.
- Commits and PRs are linked by branch/worktree, job ID, or explicit evidence discovered during reconciliation.
- Cost rows inherit job/story/session attribution whenever available.

No user should have to manually update both a todo item and a roadmap row after every dispatch.

### 3. Close with checkpoint reconciliation

`synlynk checkpoint` should reconcile the active envelope against local evidence:

- completed and failed jobs;
- commits since session open;
- changed files;
- new specs, plans, decisions, and devlogs;
- PR and release activity where available;
- costs and quota usage.

It should then show a compact result:

```text
Session sess-123
Goal: goal-abc  Scope: synlynk
Evidence: 2 jobs, 3 commits, 1 decision, $1.42 measured cost
Disposition: [completed / continued / parked / maintenance / needs attribution]
```

If evidence is unlinked, Synlynk should propose an attribution rather than ask the user to reconstruct the whole session:

```text
Unattributed evidence: docs/strategy/X.md, commit abc123
Suggested goal: goal-abc (0.82 confidence)
[accept] [choose another goal] [park] [mark maintenance]
```

The same reconciliation must include the configured GitHub repositories. It should inspect issues and PRs relevant to the active scope, including:

- issues explicitly supplied to dispatch or mentioned as `#N`;
- issues created, updated, or closed during the envelope;
- PRs linked to those issues;
- `live-issue`, severity, priority, and agent-routing labels;
- issue comments that contain findings, RCA links, action tickets, or resolution evidence.

GitHub lookup must be best-effort and capability-aware. A missing network credential or unavailable GitHub API must produce `github_sync_unavailable`, not erase or downgrade local state.

### 4. Enforce at meaningful boundaries

The system should remain permissive during work and stricter at boundaries:

- `story ready`: must have a goal link or an explicit skip reason;
- `pr check`: warns on missing goal/session attribution;
- `release`: requires no unresolved `needs_attribution` items in the release scope;
- weekly or every 5-10 sessions: roadmap review of active goals, stale items, and parked work.

This extends the existing GOVERNS model instead of creating a second tracker. GOVERNS should consume work-envelope events and own the lifecycle warnings and nudges. The activity ledger remains the source of evidence; GOVERNS remains the enforcement and attention layer.

## Roadmap and todo responsibilities

The two views should have deliberately different jobs:

- `todo.md`: the next executable stories, including status, readiness, attribution, and blockers;
- `roadmap.md`: durable goals, arcs, sequencing, and release horizons.

A completed story should not automatically create a roadmap row. A new roadmap row should be created only when the work represents a durable outcome, a new strategic commitment, or a changed priority. This avoids roadmap inflation from every maintenance task.

The database should store the distinction explicitly:

- `goal` and `roadmap_arc` for durable direction;
- `story` for planned execution;
- `activity_envelope` for observed work;
- `maintenance` and `exploration` dispositions for valid work that should not become roadmap commitments.

## GitHub Issues as an external work surface

GitHub Issues should be modeled as an external coordination surface with a synchronized local mirror, not as a competing source of truth.

### Authority boundaries

- **GitHub owns:** issue number, title/body, labels, comments, assignees, open/closed state, PR links, and external collaboration history.
- **Synlynk SQLite owns:** goal meaning, roadmap placement, story readiness, session attribution, cost/quota evidence, local disposition, and GOVERNS lifecycle state.
- **The reconciler owns:** detecting divergence, creating link candidates, and emitting events. It must not silently overwrite either system's semantic state.

The local record should retain at least `github_repo`, `gh_issue`, `gh_issue_url`, `gh_state`, `gh_updated_at`, `last_synced_at`, and `sync_status`. The existing `stories.gh_issue` field is a starting point, but it is not sufficient for sync provenance or multiple repositories.

### Import and promotion rules

1. An explicit `--issue N`, a `#N` reference in a task, or a configured issue sync can create or resolve a local story.
2. Issue import creates a story or an `external_issue` inbox item, never an active roadmap goal by default.
3. Promotion from issue to goal requires an explicit human decision or an existing goal match with visible confidence and confirmation.
4. A local story without a GitHub issue is valid when its disposition is `maintenance`, `exploration`, or `local-only`.
5. A GitHub issue without a local story is visible as `external_untriaged` until it is linked, parked, or deliberately marked out of scope.

This prevents GitHub backlog volume from automatically expanding the product roadmap while ensuring that external work cannot disappear from the continuity system.

### Outbound rules

Issue creation should normally originate from a local story, goal, or explicit live-issue workflow. Generated issue bodies should include a small machine-readable provenance block containing:

- `story_id`;
- `goal_id` when present;
- `session_id` when present;
- source repository and originating command.

The block is a link, not a replacement for the human issue body. GitHub-write actions remain subject to the existing role-scoped identity and fail-closed routing rules.

### Closure and PR behavior

Closing a GitHub issue should emit an external event and update the local mirror. It should not automatically mark a goal complete. A merged PR can mark a story complete only after the normal verification and GOVERNS checks pass. The issue, story, and goal therefore have separate but linked lifecycles:

```text
GitHub issue  <-->  local story  <-->  goal / roadmap arc
       \                 |
        \                +--> jobs, commits, PRs, costs, sessions
         +--> comments, RCA, action tickets, closure evidence
```

For live incidents, the Live Issue SOP remains authoritative: declare, investigate, write the RCA where required, create action tickets, implement, post resolution evidence, and close. The local work envelope should collect each of those artifacts without replacing the SOP.

### GOVERNS integration

GOVERNS should consume issue and PR events alongside story events:

- `github_issue_opened` / `github_issue_updated`;
- `github_issue_closed`;
- `github_pr_opened` / `github_pr_merged`;
- `github_issue_unlinked` or `external_untriaged`.

At the attention layer, GOVERNS should nudge on external work that has no local disposition, a local story whose GitHub issue has materially changed, and a closed issue whose linked story or goal remains inconsistent. It should soft-warn during ordinary work and use stronger gates at `story ready`, `pr check`, release, and periodic review.

### GitHub alignment metrics

Add GitHub-specific measures to the governance dashboard:

- 100% of dispatched work with an explicit issue reference has a local story link;
- 100% of GitHub issues discovered in the configured scope have `linked`, `external_untriaged`, `parked`, or `out_of_scope` disposition;
- no issue remains `external_untriaged` beyond one checkpoint or seven days, whichever comes first;
- no local story claims completion while its required GitHub issue or PR remains unresolved without an explicit explanation;
- GitHub sync failures are counted and surfaced, never treated as zero work;
- all issue/PR evidence for a release is attributable to a goal, maintenance, or explicit incident track.

The generated Markdown must expose any unresolved attribution prominently. A clean-looking projection must never hide an incomplete ledger.

## Cross-project session protocol

Cross-project references should be recorded in three stages:

1. **Reference:** record that another project surfaced evidence relevant to Synlynk.
2. **Assessment:** decide whether the reference is a dependency, reusable insight, defect report, or unrelated context.
3. **Promotion:** only explicit promotion creates a Synlynk goal or roadmap/story item.

Each session should have one primary project scope. Work in rxcc or vdowrx can be cited as evidence, but it does not silently become Synlynk work. If a session genuinely spans projects, create one primary envelope plus linked secondary evidence, rather than duplicating the same work into multiple roadmaps.

## Operating metrics

The governance mechanism should be judged by small, observable measures:

- **Attribution coverage:** at least 95% of completed jobs and meaningful session evidence linked to a goal, maintenance disposition, or exploration disposition within one checkpoint.
- **Cost coverage:** 100% of terminal jobs have a cost row or explicit `cost_missing` status.
- **Quota discipline:** no dispatch bypasses reservations or hard quota gates.
- **Quality:** no increase in verified rework or failed-unverified jobs after adding governance prompts.
- **Velocity:** session closeout overhead stays below one minute for ordinary sessions.
- **Roadmap freshness:** no active goal or todo item remains untouched beyond a chosen threshold, such as 14 days, without a visible stale/parked status.
- **Scope control:** every cross-project reference has a disposition; no automatic sibling-goal creation.

## Recommended implementation sequence

This should be a small, staged reliability initiative:

1. Add the activity-envelope schema and `session open/status/close` commands.
2. Propagate session and goal IDs through dispatch, story creation, decisions, plans, and checkpoint evidence.
3. Add GitHub issue/PR mirror fields, sync provenance, and `external_untriaged` disposition.
4. Add reconciliation and `needs_attribution` / `external_untriaged` reporting.
5. Extend GOVERNS events and nudges to consume unresolved attribution, stale-goal, and GitHub divergence signals.
6. Add release and periodic-review gates only after real usage measures prompt friction and false positives.

Do not begin with a large rewrite of roadmap generation, a hosted sync system, or a universal automatic intent classifier. The first milestone is closed-loop evidence capture with a low-friction escape hatch.

## Decision proposal

SQLite remains the source of truth, but it must be fed by a first-class activity envelope. GOVERNS should enforce attention at lifecycle boundaries, while ordinary work stays fast and permissive. Roadmap and todo should be generated projections of goals and stories, augmented by an explicit unresolved-attribution queue so that no meaningful work disappears merely because it began outside the formal workflow.

GitHub Issues must participate in that same loop as an external work surface: synchronized, provenance-linked, and dispositioned, but not allowed to silently become roadmap commitments. GitHub owns external collaboration state; SQLite owns local meaning and evidence; reconciliation and GOVERNS expose the gaps between them.

The success condition is not that every shell command becomes a task. It is that every meaningful unit of work ends in one of four visible states: attributed to a goal, attributed to maintenance, attributed to exploration, or explicitly parked for later review.

---

## Addendum: Review against the Agent Roles & Charters design (Claude, 2026-08-10)

**Context:** `synlynk decide` timed out (120s) attempting to gather a multi-agent panel opinion on this document — flagging that as a separate, minor operational gap (panel timeout should either extend for genuinely long-running deliberation or degrade to an async/best-effort result rather than producing nothing). Adding a direct review here instead, cross-checked against `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` (approved 2026-08-09, one day before this document was drafted).

### Where this document is right

The core diagnosis holds up under scrutiny: SQLite alone can't create coverage for events that never entered it, GOVERNS is a lifecycle gate rather than a universal ledger, and the three-layer devlog/work-envelope/roadmap decomposition is the correct shape — collapsing them is what makes today's devlog a retrospective summary instead of a reliable record. The GitHub-as-external-work-surface model (GitHub owns collaboration state, SQLite owns meaning, a reconciler owns divergence, never silently overwriting either) is fully consistent with how the charter design already treats GitHub identity and writes (charter §3.2) and should be adopted close to as written.

### The gap: this document has no owner

The activity-envelope model specifies *what* needs to happen — capture intent, collect evidence, reconcile, disposition — but treats the reconciliation loop as ambient infrastructure that simply runs, rather than someone's job. It isn't ambient. The charter design already assigns this exact responsibility to a named, durable role:

> **tpm** — "Operations role: turns architect's finished plan into tracked, dispatched tickets; does actual tasking/tracking; reports status back to pm... **Durable.** Continuous tasking/tracking/reporting loop. Consumes GOVERNS' existing lifecycle-enforcement event contract (PR #817) as its data source rather than building independent tracking... Lightweight periodic reconciliation is kept only as a correctness backstop, never the primary source of truth." (charter §2, §4)

This is close to a literal description of the "work envelope" reconciliation loop proposed above. Charter §4 even names the exact drift failure mode this document is solving — repo memory #202, "never trust `synlynk jobs` status alone" — as the specific reason tpm builds a *derived read model* on top of GOVERNS instead of a second independent tracker. Right now these are two unreconciled descriptions of the same mechanism: this document's `activity_envelope` schema and `session open/checkpoint/close` commands are a reasonable literal implementation of tpm's derived read model, but nothing in this document says tpm is the one running it.

### Recommendation: make tpm the accountable executor, not a fourth standalone system

1. **Assign ownership explicitly, not just schema.** `activity_envelope` should be tpm's internal state, not a freestanding subsystem. The `synlynk checkpoint` reconciliation described above should be something tpm's durable loop runs on its own cadence — not something that depends on a human or harness remembering to invoke it at session end. That is the actual fix for roadmap and todo falling behind: the missing piece was never a better schema, it was a named, durable, accountable actor whose job is specifically that this doesn't drift — which is exactly what "durable" already means in tpm's charter.
2. **GitHub issue reconciliation is tpm's operational surface, not a third pillar.** "Tasking/tracking" already implies triaging `external_untriaged` issues. Fold the GitHub-issues section above into tpm's charter description rather than standing it up as a separate mechanism alongside roadmap/todo.
3. **pm is the escalation backstop, not the enforcer.** tpm's reconciliation output feeds pm's already-durable, narrowly-scoped triage loop (charter §2). Anything tpm can't resolve on its own — ambiguous attribution, an item stale past threshold, a promotion decision from `external_untriaged` to a real goal — should surface to pm as a queued item through the same "major decision blocks for the human" mechanism pm already has, rather than inventing a second escalation path.
4. **GOVERNS stays the enforcement authority; tpm stays the read model.** This document's own framing already agrees with charter §4's boundary ("GOVERNS remains the sole enforcement authority over lifecycle validity; tpm builds a derived read model"). Keep that split explicit in the merged version so a second, competing enforcement path doesn't get built inside tpm later by accident.

### On "100% coverage at all times"

Don't target literal 100%-always-on coverage — that framing invites exactly the over-gating this document itself warns against ("warn and recover rather than block ordinary work"). A promise of unconditional 100% either hardens into a block on everyday work (which this document explicitly rejects) or becomes a silently-broken promise the moment reconciliation lags by even one session — which is just today's failure mode wearing a new label. The operating metrics already proposed above are the right shape for this: ≥95% attribution coverage within one checkpoint, no stale item beyond 14 days, 100% of *terminal jobs* carrying a cost row or an explicit `cost_missing` status. The target should be 100% coverage of *disposition* — every meaningful unit of work always lands in one of attributed / maintenance / exploration / parked, never silent — not 100% coverage of completion.

The most effective path to that target is accountability paired with a hard backstop, not tooling alone:

- Ship the smallest slice first, exactly as this document's own sequence proposes (activity-envelope schema + `session open/status/close`), but land it as tpm's first real durable-loop responsibility rather than a standalone feature. That is the difference between "a tool that could reduce drift" and "a role whose job is that drift does not happen on their watch."
- Reuse tpm's own cadence pattern rather than inventing a new one — charter §3.3 already specifies staleness triggers for the dispatch-calibration ledger (volume-based reconciliation every ~100–200 completed dispatches, a daily staleness check forcing action on anything idle 30+ days). Apply the same trigger shape to activity-envelope reconciliation.
- Keep GOVERNS' harder gates (story-ready, pr-check, release) as the backstop for anything tpm's soft loop misses. A durable accountable owner plus an independent hard gate gets closer to "always" than either mechanism alone, without either one becoming a bottleneck by itself.

### Sequencing note

When this document goes through Design → Plan → Build, the resulting plan should name tpm as the executor of the reconciliation loop in its first task — not leave role assignment as a TBD to be discovered later during dev/qa dispatch. Treating the reconciliation loop as anonymous infrastructure is exactly how the org chart and the roadmap-governance mechanism would end up as two more unreconciled models of the same problem — the same failure category this document exists to fix.
