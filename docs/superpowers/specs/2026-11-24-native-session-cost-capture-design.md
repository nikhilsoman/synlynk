---
title: "Native-Session Cost Capture & Session-Hook Dispatcher Design Specification"
date: 2026-11-24
status: draft
author: "Claude (Home Conductor / PM)"
goal: "goal-62f693b8"
issue: "#5457"
children: "#5498, #5499, #5501, #5503"
milestone: "v0.39.3"
---

# Native-Session Cost Capture & Session-Hook Dispatcher (LIVE-35, gh:#5457)

RCA: `docs/rca/2026-11-23-LIVE-35-native-session-cost-capture.md`.

## 1. Problem

Native Claude Code sessions (PM, review, brainstorm) sit outside the dispatch wrapper, which reads stream-json, and outside the quota scrapers, which read percentages. Nothing in synlynk reads Claude Code's own session transcripts, so native cost is missing or hand-typed. Measured facts that shape this design:

- Transcripts are JSONL at `~/.claude/projects/<slug>/<session-id>.jsonl`; assistant records carry `message.id`, `message.model` and `message.usage` (input, output, cache read, cache creation).
- Streamed messages repeat. Across session 124f8b4d, 283 of 495 message ids repeat, all with identical usage, never more than 8 lines apart. A naive sum overcounts 1.9 to 2.3x. First-seen-wins is correct.
- Transcripts also carry `pr-link` records (`prNumber`, `timestamp`) for PRs the session opened. They are not complete: this session lists 3 PRs and touched about 8.
- The ledger already has `session_id`, `pr_number`, `turn_usage_json`, `cost_source`, `estimate_basis` and `payment_mode` columns. The 291 `estimated_manual` rows leave `session_id` empty, and several name `claude-sonnet-4-6` for work that ran on Sonnet 5.5.
- 106 of the transcript directories belong to dispatched job worktrees (`worktrees/job-*`). Those jobs already have ledger rows from the dispatch adapters. Capturing them again would double count.
- No harness-hook plumbing exists in synlynk. The compaction spec (`2026-10-31-harness-context-compaction-protocol-design.md` section 10) states no per-turn usage data exists anywhere in the ledger and defers any implicit invocation point.

## 2. Decisions (founder, 2026-11-24)

1. **Attribution:** session rows plus a derived session-to-PR view. The ledger never bakes in a guess about which PR a turn belonged to.
2. **Granularity:** one row per (session, model, UTC day).
3. **Trigger:** per-turn `Stop` hook plus a `SessionEnd` hook plus a catch-up sweep.
4. **Hook shape:** a general session-hook dispatcher. Cost capture is its first and only handler in this spec.

## 3. Architecture

| Unit | Responsibility | Depends on |
|---|---|---|
| `synlynk/native_capture.py` | Incremental transcript reader and ledger upsert. No hook logic. | `db.py`, price table |
| `synlynk/session_hooks.py` | Dispatcher: `synlynk hook claude <event>` reads the hook payload and fans out to registered handlers. | `native_capture.py` |
| `synlynk cost capture-session` | CLI over the same function: `--session <id>`, `--transcript <path>`, `--pending`. | `native_capture.py` |
| `synlynk init` / `doctor` | Install and verify the hook entries. | `session_hooks.py` |

The CLI, the hook and the backfill all call one function, so there is one code path to test.

The dispatcher routes events to a handler registry. Only `cost_capture` ships; no extension-point code, stubs or config for other handlers is added in this work. Compaction triggers and intent capture (`synlynk/intent.py`, gh:#5382) can register later without changing the dispatcher's interface.

## 4. Data flow

1. `Stop` fires after each turn. The dispatcher receives `session_id` and `transcript_path` and calls the cost handler.
2. The handler reads only bytes after a stored cursor (byte offset plus the last 16 message ids). Hook budget: the `Stop` path targets under 200 ms at the 95th percentile on a 50 MB transcript, measured in a test; over budget the handler records progress and defers the rest to the sweep.
3. For each assistant record: skip `<synthetic>` models, skip an id already seen, record first-seen usage.
4. Bucket by (session_id, model, UTC day) and upsert one `cost_entries` row per bucket:
   - `cost_source='transcript_derived'`, `harness='claude'`, `session_id` set, `pr_number` NULL, `story_id` NULL.
   - `input_tokens`, `output_tokens`, `cache_read_tokens` from the bucket; cache-creation tokens go in `turn_usage_json`, with per-message usage keyed by `message.id`. Counts only.
   - `total_cost_usd` from the price table (gh:#5501), computed from input, output, cache-read **and cache-creation** tokens (a test pins this); if the model is not in the table the row is stored with `estimate_basis='unpriced'` and a NULL cost, never another model's rate.
   - `payment_mode` from `billing.json` until gh:#5500 supplies detection; rows captured before then carry `payment_mode_provisional=1` (stored in `turn_usage_json` metadata or a column, plan decides) so gh:#5500 can correct them.
5. The cursor advances in the same transaction as the upsert, so a crash re-reads at worst one chunk and the unique key prevents a double count.
6. `SessionEnd` runs the same handler once more and marks the cursor final.
7. The catch-up sweep (`capture-session --pending`, run by `doctor` and the daemon) captures transcripts that have no cursor or new bytes. This covers killed terminals, `kill -9` and multi-day sessions.

### 4.0 De-duplication boundary and recovery

The 16-id window is an optimisation, not the correctness guarantee. If the cursor is lost, the transcript shrinks or is rewritten (size below `byte_offset`, or the byte at `byte_offset` no longer starts a record), or a repeat is found further back than the window, capture does a full re-scan of that transcript and replaces its rows (same unique key, so it is idempotent). If the full re-scan itself cannot reconcile, it fails loudly into the error log and `doctor`. It never continues silently with a possibly drifted count.

### 4.1 Exclusions (no double counting)

Skip a transcript when any of these holds:
- its project path contains `/worktrees/job-` (a dispatched job worktree, including ones nested under `.claude/worktrees/`);
- its `session_id` already appears on a ledger row that has a `job_id`.

Interactive sessions in Claude-managed worktrees (`.claude/worktrees/<name>`) are native and are captured. The plan must verify the exclusion rule against a sample of job transcripts before the backfill runs. The rule is re-evaluated on every sweep, not only at first capture, and a reconcile step flags any `session_id` that has both `transcript_derived` and `job_id` rows (a `doctor` finding, never an auto-delete).

### 4.2 Session-to-PR view

A table `session_pr_links(session_id, pr_number, first_seen_ts, source)` is filled from three sources: `pr-link` records (`source='pr-link'`), PR numbers extracted from `gh pr` tool-use records in the transcript (`source='tool-use'`; only the number is kept, never the command text), and `synlynk cost link-session --session <id> --pr <n>` (`source='manual'`). Links are never complete, so an absent link means *unknown*, not *none*: `pr check` must not conclude "no native cost" from a missing link. `synlynk pr check` consults it: a PR is considered to have native provenance when a linked session has captured rows. In v1 `pr check` reports the whole linked-session cost labelled as shared across the session's PRs. It does not split the cost. Invariant, enforced by a test: no consumer sums a session's cost once per linked PR (that would multiply it); per-PR figures are always labelled "shared across N PRs".

## 5. Schema changes

- New unique partial index on `cost_entries (session_id, model, substr(session_date,1,10)) WHERE cost_source='transcript_derived'`.
- New table `native_capture_cursor(session_id PRIMARY KEY, transcript_path, byte_offset, recent_ids_json, final, updated_at)`.
- New table `session_pr_links` (above).
- New `estimate_basis` value `superseded_by_transcript` for backfilled manual rows, hidden by a new view `cost_entries_effective` (`cost_entries` minus superseded rows). Every reader (`cost_audit.py`, quota, capability reporting, `costs.md` regeneration, `pr check`) reads the view, not the table. A repo test fails on any raw `FROM cost_entries` read outside the allow-list (writers, the view definition, migrations). This is a gating requirement: the view and the test land before any backfill `--apply`.
- Migrations follow the repo's existing lazy-migration convention; sparse and legacy databases must not fail.

## 6. Hook installation

The hook edits `~/.claude/settings.json`, which is outside the repo, so installation is consent-gated: `init` offers it and `doctor --fix` installs it. It never installs silently. The merge preserves existing hooks (including `auto-checkpoint-docs.sh`), tags synlynk's entries so they can be found and removed, and is idempotent. `doctor` reports: hook present, hook firing (recent cursor updates), transcripts with no ledger rows, and the capture-error log.

## 7. Privacy

Only counts, model ids, timestamps, session ids and PR numbers are read into memory structures that are persisted. Message content is never stored, logged or placed in test fixtures. A test asserts the persisted rows and the error log contain no message text. Transcript format belongs to Claude Code, so a fixture-based format-drift test fails loudly when the usage shape changes.

## 8. Failure behaviour

- The hook always exits 0 and has a hard time budget. Failures go to a local capture-error log that `doctor` reports; the session never sees an error.
- A missing or rotated transcript raises an explicit error, never a zero row.
- An unknown model is stored unpriced and flagged by `doctor`.
- A transcript that grows while being read is handled by the cursor: bytes past the last complete line are left for the next run.

## 9. Backfill (gh:#5503)

`synlynk cost backfill-native` is dry-run by default and prints old versus new per row; `--apply` writes.
- Match `estimated_manual` native rows (`harness='claude'`, `job_id` NULL, note identifies a native session) to transcripts by date window; recompute with the capture function and the price table.
- Matched manual rows get `estimate_basis='superseded_by_transcript'`; their values are never altered or deleted. Unmatched rows are relabelled as unverified estimates.
- The model is corrected from the transcript (the manual rows often say `claude-sonnet-4-6`).
- Unblocks cost rows for #5420, #5425, #5433, #5447 and #5453, each with a `--note` stating the derivation.
- Applying twice is a no-op. Check `git diff --numstat origin/main` before committing a regenerated `costs.md`, because `cost log` rewrites the whole file.

## 10. Scope

**In:** `native_capture.py`, `session_hooks.py`, `capture-session`, `link-session`, hook install and `doctor` checks, price-table interface (data lives in gh:#5501), backfill, the consumer audit.
**Separate PRs:** gh:#5500 account-type detection, gh:#5502 `pr check` warning, gh:#5504 `calc_costs.py`.
**Out of scope:** compaction triggers and intent capture on the dispatcher; Codex, Grok and Agy interactive transcripts (the reader sits behind an adapter interface so they can follow, but only Claude is implemented); a Vizor per-turn growth view; splitting a session's cost across PRs.

## 11. Testing

- Fixture transcripts with message text removed and usage kept.
- De-dup: repeated ids count once, including across a chunk boundary.
- Idempotency: capturing twice, or partially then fully, yields identical rows.
- Multi-day and multi-model splits.
- Exclusions: a job-worktree transcript produces no rows.
- Format drift: a renamed or missing usage field fails loudly.
- Hook safety: exits 0 on garbage input; settings merge preserves existing hooks; install is idempotent.
- Privacy: persisted rows and the error log contain no message text.
- Effective view: superseded rows are invisible to every reader; the raw-read guard test fails on a new raw read.
- Cache-creation tokens contribute to `total_cost_usd`.
- Cursor loss, a rewritten transcript and a far-apart repeat each trigger a full re-scan or a loud failure.
- Reconcile flags a session with both `transcript_derived` and `job_id` rows.
- Hook latency budget (section 4, step 2) is measured.
- No consumer sums a session's cost per linked PR.
- Acceptance: a pinned fixture (a fixed snapshot of session 124f8b4d's usage records, text stripped, at the RCA measurement point) reproduces the RCA's de-duplicated totals (output 243,094; cache_read 54,415,618). A live session keeps growing, so it is never the fixture.

## 12. Risks and open items

- **Transcript format drift** is the main risk; covered by the drift test and the `doctor` check, but it needs an owner.
- **Double counting** between hook rows and legacy manual rows is solved by the backfill's supersede mark, but only for sessions with surviving transcripts. Until the backfill runs, totals include both. The plan orders the work: effective view and guard test, then capture, then backfill, and only then any report that sums native cost.
- **DECIDE record:** `project-docs/decisions/2026-11-24-native-session-cost-capture-per-session.md`, conditional approval; the 11 amendments are incorporated in this revision.
- **Roadmap drift:** `roadmap check` reports `ARC_NO_DECISION` for v0.39.3 until this spec's DECIDE record is approved and links `goal-62f693b8`.
