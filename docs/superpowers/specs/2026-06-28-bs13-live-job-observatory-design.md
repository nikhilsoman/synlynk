# BS-13: Live Job Observatory / Watch Overlay
## Design Spec

**Date:** 2026-06-28  
**Session:** BS-13 (Nikhil + Claude)  
**Status:** Drafted for review  
**Target:** Pre-v1.0 observability layer, with `synlynk viz` reuse later

---

## Problem Statement

`synlynk jobs` is useful for a repo-local list, but it does not answer the question that matters once the system scales beyond one repository:

> What jobs are running right now, across all repos, what stage is each one in, and what is the live cost so far?

Today, jobs are distributed across multiple repos and multiple agents over time. The operator needs a single monitoring surface that behaves more like `htop` or `mtop`:

- live, not historical
- read-only, not a control plane
- cross-repo, not repo-local
- stage-aware, not just status-aware
- cost-aware, including dollars, tokens, and requests

This spec introduces a shared observability layer for both a terminal board and a web board. The first version is monitoring only. There are no action CTAs beyond links out to the relevant terminal or web target.

---

## Goals

1. Show every currently running job across every repo in the current synlynk workspace.
2. Refresh the view at a near-real-time cadence, targeting about 10 seconds.
3. Group jobs by workspace, then repo, then stage.
4. Show provenance for every job:
   - originating agent
   - executing agent
   - dispatch source, when available
5. Show live cost signals per job and per group:
   - USD spend so far
   - token usage so far
   - request count so far
6. Show input context size per job as a first-class metric.
7. Provide two surfaces with the same underlying model:
   - terminal full-screen board
   - web dashboard
8. Keep the surface read-only.
9. Make it easy to jump to the relevant terminal session or web page via top-level links only.

---

## Non-Goals

- No job control actions
- No pause/resume/retry buttons
- No dispatch scheduling features
- No write path to state.db beyond whatever existing job telemetry already records
- No per-job edit actions from the board
- No replacement for `synlynk jobs`
- No workspace mutation actions from the board

---

## Foundational Job Fields

These fields are the minimum useful shape for the observatory. If a field is missing, the board should surface that fact explicitly rather than flattening it away.

- workspace: the multi-repo project that owns the work
- originating agent: who created the job or requested dispatch
- executing agent: who is actually running the job
- input context size: the size of the prompt/context payload at dispatch time
- repo: where the job belongs
- stage: where the job sits in its lifecycle
- runtime: how long it has been running
- cost: how much it has consumed so far

This is the foundational synlynk job model. Everything else is optional refinement.

---

## Workspace Aggregation

Workspace is the right aggregation unit above repo because synlynk already treats it as the project boundary for multi-repo work.

Each workspace row should be collapsible and should summarize:

- running jobs
- total USD spend
- total input tokens
- total output tokens
- total requests
- agent hours
- average or total input context size
- stage distribution

Suggested workspace row presentation:

- `workspace name`
- `jobs`
- `cost`
- `tokens`
- `requests`
- `agent hours`
- `active agents`

The workspace row should be toggleable on/off so operators can choose between:

- workspace-first view
- repo-first view
- compact job-only view

Default should be workspace-first for multi-repo projects.

---

## Design Principles

### 1. Monitoring, not control

This board should answer "what is happening?" and not "what should I do next?" The only permitted CTA is to open the terminal/web target that already owns the job or to inspect the repo more closely.

### 2. Shared model, multiple skins

The terminal and web versions should render the same data model. The UI differs, but the job grouping, cost rollups, and refresh semantics must stay consistent.

### 3. Readable at a glance

The primary use case is an always-visible operator board. The board should compress many jobs into a small number of useful buckets:

- repo
- stage
- running job
- live cost

### 4. Cheap to update

The board should refresh quickly without becoming a polling tax. Ten seconds is the target cadence for the first pass because it is frequent enough to feel live and slow enough to be polite.

---

## Proposed User Experience

### Terminal board

The terminal surface is a full-screen dashboard, similar in feel to `htop`:

- top summary line with totals
- repo sections stacked vertically
- within each repo, stage groupings
- each job row shows:
  - job id
  - agent
  - stage
  - age / runtime
  - cost so far
  - token count
  - request count
- color and compact typography should make the current shape obvious without reading every field

Suggested controls:

- `q` exit
- `r` force refresh
- `1` toggle compact view
- `2` toggle cost emphasis
- `3` toggle stage emphasis

These are view controls only. They do not mutate job state.

### Web board

The web surface mirrors the same structure:

- summary header
- repo cards or expandable repo sections
- stage clusters inside each repo
- live job rows or tiles
- top-level links to open:
  - the terminal board
  - the underlying repo
  - the job log or context page when available

The web version should feel like a monitoring console, not a task manager.

---

## Data Model

The observatory should consume normalized job records that can be rendered consistently by both surfaces.

### Canonical job shape

```json
{
  "id": "job-1234abcd",
  "repo": "nikhilsoman/rxcc",
  "originating_agent": "claude",
  "agent": "codex",
  "executing_agent": "codex",
  "story_id": "665",
  "stage": "review",
  "status": "running",
  "started_at": "2026-06-28T09:15:28Z",
  "updated_at": "2026-06-28T09:15:38Z",
  "runtime_seconds": 610,
  "input_context_bytes": 56012,
  "input_context_tokens": 13284,
  "cost_usd": 1.42,
  "input_tokens": 18321,
  "output_tokens": 4920,
  "requests": 37,
  "log_path": ".synlynk/logs/job-1234abcd.log",
  "context_path": ".synlynk/contexts/job-1234abcd.md",
  "target": {
    "kind": "terminal",
    "label": "rxcc worktree"
  }
}
```

### Grouping keys

- **Repo group:** `repo`
- **Stage group:** `stage`
- **Job identity:** `id`

### Stage mapping

The stage is a display-oriented summary derived from existing synlynk job metadata. The initial mapping should be conservative and based on data already present in the job store, prompt, context, or logs.

Examples:

- `queued`
- `dispatching`
- `running`
- `review`
- `blocked`
- `done`
- `failed`

The exact stage vocabulary can expand later, but the board should always collapse to a manageable set of labels.

### Provenance

The observatory should distinguish between:

- **originating agent**: the agent that was chosen to start the work
- **executing agent**: the agent process currently running the work
- **workgroup name**: the operator-visible name used to identify the collaborative unit, such as `nikhil`

These are often the same, but not always. The split matters when jobs are delegated, retried, or resumed by a different agent.

The row label should be able to display a compact workgroup-agent identity such as `nikhil:claude`, with expansion revealing more detail.

### Context Size

Input context size should be displayed as both:

- a raw value in bytes
- an approximate token value when available

The board should always carry the raw shape in the snapshot model, even if the UI chooses a compact representation.

---

## Expanded Row Detail

Clicking or expanding a row should show a dense detail panel with:

- workspace
- repo
- workgroup name
- originating agent
- executing agent
- story or epic reference
- dispatch source
- stage history
- runtime
- cost rollup
- token rollup
- request rollup
- input context size
- log link
- context link
- repo link

This expansion is the place for detail. The collapsed row should stay readable.

---

## Refresh Strategy

### Target cadence

Refresh every ~10 seconds.

### Terminal implementation

The terminal board can use a simple redraw loop:

1. Read the current job snapshot.
2. Group and sort jobs.
3. Render a full-screen board.
4. Sleep for the refresh interval.

If the underlying data source changes more slowly than the refresh cadence, the board should still redraw on schedule and show stable values.

### Web implementation

The web board should reuse the same snapshot format and refresh it on a timer or via server push later.

Phase 1 can be polling-based.

Phase 2 can move to SSE or another push path if the existing relay becomes the right distribution layer.

---

## Cost Display

Each job row should show current spend in a compact format:

- `$.42`
- `12.4k tok`
- `18 req`

The top summary should also roll up:

- total cost across running jobs
- total token usage across running jobs
- total request count across running jobs

If a job has incomplete telemetry, the board should show a neutral placeholder rather than hiding the row.

---

## Read-Only Interaction Model

No actionable CTAs are allowed in the main board surface.

Allowed:

- open terminal target
- open repo
- open log file
- open related web page

Not allowed:

- stop
- rerun
- cancel
- approve
- reassign
- edit

This keeps the observatory purely diagnostic.

---

## synlynk viz Relationship

This feature should be treated as the monitoring seed for `synlynk viz`.

The observability board can later inform a richer visualization layer:

- repo topology
- active job distribution
- stage flow
- cost pressure
- agent concentration

That later viz should not replace the live board. The live board is the operational surface; viz is the analytical one.

---

## Implementation Sketch

### Shared snapshot builder

Introduce a snapshot builder that returns the normalized job list plus rollups:

- `build_job_observatory_snapshot()`

This should aggregate from the existing job store and any related telemetry the system already tracks.

### Terminal command

Add or extend a CLI command:

- `synlynk watch`

Potential behavior:

- `synlynk watch` → full-screen live board
- `synlynk watch --all` → include completed jobs for history view
- `synlynk watch --repo <name>` → scoped board

The first release should default to the live running-job board.

### Web route

Add a web page under the existing synlynk visual layer, likely under the `viz` / observability section.

The route should render the same snapshot and should not require the user to manually refresh.

---

## Risks

1. **Telemetry gaps:** some jobs may not have all cost fields available in real time.
2. **Workspace normalization:** some projects may not yet have a clean workspace-repo mapping in the snapshot layer.
3. **Cross-repo normalization:** repos may report different job metadata shapes until the shared snapshot layer exists.
4. **Provenance gaps:** originating agent and executing agent may be missing in some paths and should be surfaced as unknown, not inferred silently.
5. **UI overload:** too many columns can make the board unreadable, especially in terminal mode.
6. **Refresh churn:** a 10s cadence is fine for a first pass, but the implementation should not assume polling is the final transport.

---

## Success Criteria

The feature is successful if:

- the operator can see all active jobs across repos in one board
- the board updates fast enough to feel live
- cost is visible without opening a detail view
- terminal and web surfaces stay consistent
- the board remains read-only
- the output is useful at a glance without becoming noisy

---

## Next Step

Turn this spec into a scoped implementation plan for the terminal board first, then reuse the same snapshot and grouping logic for the web view.
