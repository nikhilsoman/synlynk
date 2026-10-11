# Federated Quota Capture & Calibration — Design Spec

**Date:** 2026-10-10
**Status:** Approved for implementation planning
**Author:** Claude (PM session), with Nikhil

## Problem

Claude was at 98% of its weekly quota (resets Monday 1530h) while carrying a
disproportionate share of PM/roadmap/review/brainstorm work. synlynk has no
live view of quota headroom across Claude/Codex/Agy/Grok (and future
harnesses), so task allocation cannot route work to whichever harness
actually has capacity right now — it defaults to whichever harness happens
to be "home." This spec covers the mechanism for capturing each harness's
real subscription-quota percentage at (or near) task boundaries, storing it,
and making it queryable for allocation decisions.

**Explicitly out of scope:** this is not a replacement for API-key-based $
cost tracking (`cost_entries`), which continues to answer "what did this job
cost," not "does this harness have room to take more work." The two systems
are complementary and read side-by-side by allocation logic, never merged.

## Feasibility findings (validated this session, not assumed)

| Harness | Non-interactive quota read | Mechanism |
|---|---|---|
| Claude | Yes | `claude -p "/usage" --output-format text` — weekly %, 5h %, reset times |
| Agy | Yes | `agy -p "/usage" --output-format text` — per-model-family weekly/5h % |
| Codex | Yes (log scrape, not a command) | Every session (interactive or `exec`) writes a `payload.rate_limits` snapshot into `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. Verified live: `{"plan_type":"plus","primary":{"used_percent":14.0,"window_minutes":10080,"resets_at":...},"secondary":null}`. `secondary` (5h bucket) was `null` in the verified sample — unconfirmed whether it ever populates; treat Codex 5h as unknown until proven otherwise in production. |
| Grok | No non-interactive path exists | `/usage` is TUI-only. The weekly % (`creditUsagePercent`) is written to `~/.grok/logs/unified.jsonl` as a `billing: fetched credits config` line, verified live (`21.0%`, `USAGE_PERIOD_TYPE_WEEKLY`), but **only when an interactive session starts or refreshes billing** — a headless-only machine never writes this line. **No 5-hour quota field exists anywhere for Grok, client-side or logged** — this is a permanent product gap, not a missing integration. |

Checked and ruled out:
- **Official web APIs**: Anthropic's Rate Limits API is admin/org-only and explicitly excludes consumer Pro/Max/Team plans. No public API exists for Grok's SuperGrok weekly pool. Codex has one undocumented internal endpoint (`chatgpt.com/backend-api/wham/usage`, callable with the token in `~/.codex/auth.json`) — a possible fallback, but unsupported and liable to break without notice; the JSONL log path is preferred as the stable, intentionally-written source.
- **Existing open-source tools** (`openusage`, `caut`): both auto-detect this exact harness set, but verified live (installed `openusage` via Homebrew, ran `export` against real local credentials) that they report self-computed proxies (`ai_code_percentage`, `cache_hit_ratio`, token/cost estimates) — not the authoritative plan-quota %. `openusage` explicitly labels its Claude Code numbers "API-equivalent estimates, not subscription charges." These tools solve a different problem (local cost estimation) and are not adopted here.

## Architecture

### Data model

New table `quota_snapshots` in `state.db`, alongside `cost_entries`/`capability_ratings`:

```sql
CREATE TABLE quota_snapshots (
  id INTEGER PRIMARY KEY,
  harness TEXT NOT NULL,          -- free text, not enum: claude | agy | codex | grok | <future>
  window TEXT NOT NULL,           -- '5h' | 'weekly'
  used_percent REAL NOT NULL,
  resets_at TEXT,                 -- ISO8601, nullable
  captured_at TEXT NOT NULL,      -- ISO8601
  source TEXT NOT NULL,           -- 'task_boundary' | 'poller'
  staleness_seconds INTEGER,      -- null for task_boundary (always fresh), set for poller
  job_id TEXT                     -- nullable FK-by-convention to the dispatch/exec job that triggered capture
);
```

`harness` is free text specifically so onboarding Muse or any future harness
never requires a schema migration — see Capture Registry below.

### Capture registry

A new `quota_capture.json` (or a section of `.synlynk/policy.json`) declares,
per harness:

```json
{
  "claude": { "cli_usage_cmd": "claude -p \"/usage\" --output-format text", "log_scrape": null, "has_5h_window": true, "interactive_pane_id": null },
  "agy":    { "cli_usage_cmd": "agy -p \"/usage\" --output-format text",    "log_scrape": null, "has_5h_window": true, "interactive_pane_id": null },
  "codex":  { "cli_usage_cmd": null, "log_scrape": {"path": "~/.codex/sessions/**/*.jsonl", "jq_filter": ".payload.rate_limits"}, "has_5h_window": "unknown", "interactive_pane_id": null },
  "grok":   { "cli_usage_cmd": null, "log_scrape": {"path": "~/.grok/logs/unified.jsonl", "jq_filter": "select(.msg == \"billing: fetched credits config\")"}, "has_5h_window": false, "interactive_pane_id": null }
}
```

Onboarding a new harness (Muse, etc.) means adding one entry here. A harness
absent from the registry never gets snapshot rows; allocation logic treats
its capacity as permanently unknown and falls back to manual
`synlynk quota calibrate`, same as Grok's 5h window does today.

### Capture mechanisms

**Boundary capturer** — called from `exec_command()`/dispatch, async and
non-blocking, immediately after a harness task completes:
- Claude/Agy: spawns the registry's `cli_usage_cmd`, parses weekly/5h %.
- Codex: no process spawned — tails the last `rate_limits` line from the
  rollout JSONL the just-completed task already wrote (side effect, free).
- Writes one or two rows per capture: `source: task_boundary`,
  `staleness_seconds: 0`, `job_id` set.
- Failures (parse error, missing file, process error) are logged and never
  block the dispatch/exec call that triggered them.

**Poller + persistent-session refresh** — new loop in the existing synlynk
daemon, default interval 15 min, covers every harness in the registry:
- For harnesses with a cheap passive source (Codex's log, Claude/Agy's CLI
  call), the poller is a redundant backstop catching gaps where the boundary
  capture failed or the triggering task crashed before completion.
- For Grok, the poller is the *primary* (only) source: it drives the
  harness's standing persistent interactive Herdr pane (`interactive_pane_id`
  in the registry, populated once that harness's per-harness tab exists per
  the federation setup) via `herdr pane send-text <pane_id> "/usage"` +
  Enter, then re-tails `unified.jsonl`. This reuses infrastructure that
  exists anyway for interactive home-session work — no throwaway
  spawn-and-kill sessions, no added cost beyond what the standing session
  already incurs.
- Writes `source: poller`, `staleness_seconds` = age of the underlying log
  line/reading at capture time.
- A harness with no `interactive_pane_id` registered simply skips the
  pane-driven refresh and relies on whatever passive capture it has (which,
  for Grok specifically, means no refresh happens at all until a pane is
  set up — an explicit, visible gap rather than a silent one).
- **Today, no per-harness Herdr panes exist yet** — that setup is a
  separate, not-yet-brainstormed piece of work. Until it lands, every
  harness's registry entry simply has `interactive_pane_id: null`, so Grok
  gets zero automated weekly-quota refreshes and `synlynk quota federated`
  correctly reports Grok as permanently "unknown" until either the panes
  are set up or someone runs manual `synlynk quota calibrate`. This is not
  a blocker for shipping the rest of this design — Claude/Agy/Codex capture
  works fully without any Herdr pane existing.

### Query / allocation integration

- New `synlynk quota federated` view: latest `quota_snapshots` row per
  harness × window, shown alongside each harness's `cost_entries`-derived $
  burn.
- Task-allocation logic (wherever PM/review/brainstorm/implementation
  dispatch decisions are made) consults this view before defaulting to
  Claude, closing the loop on the original problem.
- **Staleness rule**: a snapshot older than 2× its harness's poll interval
  is treated as "unknown," not "0% used." Routing falls back to the
  existing manual `synlynk quota calibrate` reading rather than assuming
  fresh capacity.
- **Missing snapshot** (new unregistered harness, or Grok's permanent 5h
  gap) is treated identically to "unknown" — never as 0% or 100%.

## Testing

- Unit tests per harness parser, fed real captured samples (the Codex and
  Grok JSONL lines verified live during this design's research).
- Unit test for the staleness-threshold → "unknown" fallback logic.
- Integration test: mock a completed dispatch, assert a `quota_snapshots`
  row is written asynchronously without blocking the dispatch's return.
- Integration test: mock `herdr pane send-text`/`pane read`, assert the
  poller only triggers a Grok refresh when the existing log line is stale,
  and correctly parses the resulting line.
- Regression test: a harness with no registry entry never writes a row, and
  routing correctly falls back to manual calibration rather than erroring.

## Explicitly deferred

- **Herdr as a bundled core dependency / standard UX layer for synlynk
  workflows.** Raised during this design's review but is a separate,
  larger architectural decision (install-mechanism change, needs its own
  arch-council round, needs a new pillar in the October dev-preview
  roadmap). Tracked as the next piece of work after this spec; not part of
  this design. This design's Grok-refresh mechanism depends on a persistent
  Herdr pane per harness existing, but does not depend on Herdr being a
  *bundled* dependency — if Herdr is unavailable, Grok simply has no
  `interactive_pane_id` registered and falls back to manual calibration,
  same as any other harness without one.
