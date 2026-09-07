# Sentinel Persistence, Deduplication, and Expiry Review (#1488)

**Date:** 2026-09-07  
**Status:** Design-only review  
**Scope:** Sentinel persistence, alert generation, deduplication, expiry, and selftest interactions  
**Tracking issue:** #1488

## Executive conclusion

The sentinel system currently has one append-only markdown event log but several
different definitions of “active alert.” That is the root design problem behind
#1488. Writers append on every detection; context rendering performs a temporary
presentation-only collapse; status, `sentinel list`, and the pre-exec gate read
all structured lines; and platform operations alone applies a time window.
Repeated telemetry scans therefore grow the file and can keep an old CRITICAL
alert blocking execution indefinitely, even when the operational report treats
the same alert as expired.

The smallest safe implementation is to preserve `.synlynk/sentinel.md` and its
human-readable format, but introduce one shared parser/active-alert policy and
make writes idempotent for the same alert identity within a configurable
deduplication window. Expiry should affect “active” views and gates, while old
records remain available for audit and platform-history reporting. Existing
`sentinel clear` remains an explicit operator action.

## Findings and root causes

### 1. Persistence is append-only and non-atomic

`synlynk.sentinel._write_sentinel_alert()` reads the whole file, appends one
line, and rewrites it. It creates `# Sentinel Alerts` when needed, but has no
bounded retention, file lock, atomic replace, or write-failure policy. Multiple
reconciliation/watch processes can lose updates through read-modify-write
races. The file is gitignored, so it is local runtime state rather than a
portable source of truth.

The existing `log_telemetry_event()` is also a capped JSON list (100 events),
but sentinel records are not capped or linked to telemetry event IDs. A scan of
historical telemetry can consequently re-emit the same finding each time
`check_sentinel_patterns()` runs.

### 2. Deduplication is presentation-only

`_summarize_sentinel_alerts()` groups by exact `(code, message)` and keeps the
latest line, but only callers such as context generation use it. It does not
change the persisted file, `sentinel_list()`, `_read_sentinel_alerts()`, or the
pre-exec gate. Small message changes (job ID, token total, or timestamp-derived
wording) also produce separate groups. The result is unbounded duplicate
generation with no stable event identity.

### 3. Expiry is inconsistent across consumers

`platform_ops.count_sentinel_critical_lines()` filters timestamped CRITICAL,
FLATLINE, and QUOTA_EXHAUSTED lines to a report window and retains lifetime
counts for diagnostics. In contrast:

- `_check_pre_exec_gate()` blocks on every CRITICAL line, regardless of age.
- `sentinel_list()` reports every bullet as active.
- `status` reports every bullet and treats any bullet as a health alert.
- `_read_sentinel_alerts()` has no timestamp or age policy.
- `sentinel clear` is the only general way to remove old records.

This causes contradictory UX: platform ops may be green while a stale local
CRITICAL still blocks `exec`.

The parser also has compatibility edges: canonical lines use `[SEVERITY]
[timestamp]`, legacy lines omit severity, and some producers use `WARNING`
while several readers filter for `WARN`. Untimestamped legacy records cannot be
safely expired and should remain visible/auditable rather than silently being
treated as fresh.

### 4. Alert generation is distributed and has a path inconsistency

Detection is spread across model-rate checks, circuit breaker, token-bloat and
cost checks, pattern checks, dispatch preflight/stall handling, instruction
checks, jobs reconciliation, probe, and handoff. Jobs generally pass an
explicit `sentinel_path`, but the daemon reconciliation token-bloat call site
does not pass one. The effective destination therefore depends on the current
working directory. The design should standardize path resolution before adding
new persistence behavior.

`check_sentinel_patterns()` calls the telemetry-wide token-bloat scan on every
pattern check. Since the scan has no “already evaluated” marker and each alert
message includes job-specific values, it is a direct duplicate amplifier.

### 5. Selftest isolation is good but sentinel behavior is unverified

Live selftest runs in a temporary scratch workspace and temporarily points
state DB access at a scratch DB, restoring the caller’s directory/DB afterward.
That prevents ordinary sentinel and telemetry writes from reaching the host
workspace. However, the selftest suite does not assert that the scratch
`sentinel.md` and telemetry files are clean after normal scenarios, does not
exercise duplicate detection or expiry, and does not assert that a stale
CRITICAL is non-blocking while a fresh CRITICAL remains blocking.

The word “sentinel” in the migrate scenarios refers to the migration marker
`.synlynk/.synlynk_migrated`, not alert state; the two concepts must remain
separate in both implementation and tests.

## Smallest safe implementation

### A. Introduce one parsed alert model and policy helpers

In `synlynk/sentinel.py`, add private helpers (names illustrative):

- `_parse_sentinel_alert(line) -> Optional[dict]`, accepting canonical and
  legacy formats and normalizing `WARNING` to `WARN` for comparisons.
- `_alert_identity(alert)`, based on normalized severity, code, message, and a
  producer/job identity when available. Do not include the write timestamp.
- `_alert_is_active(alert, now=None, expiry_seconds=None)`, with explicit
  handling for missing/invalid timestamps. Untimestamped legacy alerts remain
  active until explicitly cleared, preserving safety.
- `_iter_sentinel_alerts(path, active_only=False, now=None, policy=None)` as the
  single reader used by context, status, list, gate, and support-facing reads.

Keep the existing line format so old files remain readable. Do not migrate to a
database in this change; the existing state DB is not currently a canonical
sentinel store and introducing one would expand the blast radius.

### B. Make writes idempotent without deleting history

Update `_write_sentinel_alert()` to:

1. Resolve the target path once at the caller boundary and create its parent.
2. Parse existing structured lines.
3. If the same normalized identity is already present within the configured
   deduplication window, do not append another line; return a structured
   result indicating `deduplicated`.
4. Otherwise append the canonical line using the existing format.
5. Use a lock plus temporary-file-and-`os.replace` write path where supported;
   if locking is unavailable, preserve current best-effort behavior and emit no
   new destructive cleanup.

The first implementation should use a bounded default dedup window (for
example, 24 hours) and allow a config override. A duplicate after the window
should create a new occurrence so recurring incidents remain observable.
Deduplication must not suppress distinct job IDs, agents, or materially
different messages. Prefer an explicit `job_id`/`agent` field in future call
sites; for this compatibility pass, derive identity from the normalized
message when no structured metadata exists.

### C. Apply a shared expiry policy only to active consumers

Add a documented default active-alert TTL by severity/code, with a conservative
initial policy: CRITICAL operational alerts expire from blocking/UI views only
after a configurable period; INFO/WARN may use a shorter period. The exact
defaults must be config-backed and tested at boundary timestamps. Platform ops
may continue to use its report-window override.

Use the helper for `_check_pre_exec_gate()`, `sentinel_list()`, status/context
active display, and any support collector claiming to show active alerts.
Retain historical lines in the file and retain platform lifetime counts. A
stale CRITICAL must not block a new exec; a fresh CRITICAL must still block
unless `--force` is supplied. Untimestamped legacy CRITICAL remains blocking
until manually cleared, avoiding a fail-open conversion of unknown state.

Normalize `WARN`/`WARNING` consistently in filters, while preserving the
original severity text only when rendering legacy lines.

### D. Make all producers pass an explicit sentinel path

Audit the sentinel-producing call sites and pass the workspace-local path into
the daemon reconciliation token-bloat check and any remaining implicit writer.
Do not change the path format or relocate existing files. This removes cwd
dependence and makes scratch selftest behavior deterministic.

## Regression test plan

Tests should be added/updated only after this design is approved. The expected
focused verification command is:

```text
pytest tests/test_sentinel.py tests/test_sentinel_quota_exhaustion.py tests/test_platform_ops.py tests/test_selftest.py tests/test_synlynk.py
```

Required cases:

1. **Persistence compatibility:** canonical and legacy lines parse; malformed
   lines survive reads and clears; file creation preserves the header.
2. **Write deduplication:** repeated identical alert within the window writes
   one line; same code with a different job/agent remains distinct; the same
   identity after the window writes a new occurrence.
3. **Telemetry scan idempotence:** repeated `check_token_bloat()` scans do not
   grow `sentinel.md` for the same telemetry event; distinct events still alert.
4. **Expiry boundaries:** fresh timestamp is active, exact TTL boundary follows
   the documented inclusive/exclusive rule, stale timestamp is inactive, and
   untimestamped legacy CRITICAL remains active.
5. **Consumer consistency:** list, status/context, and pre-exec gate agree on
   active versus expired alerts; fresh CRITICAL blocks and stale CRITICAL does
   not; `force` continues to bypass fresh CRITICAL.
6. **Platform compatibility:** report-window and lifetime counts retain their
   current semantics, including untimestamped and legacy records.
7. **Path isolation:** daemon reconciliation writes to the supplied workspace
   sentinel path, not the process cwd.
8. **Selftest:** live selftest leaves no alert leakage in the host workspace,
   records expected scratch-only state when a scenario intentionally triggers
   an alert, and restores DB/cwd even if an alert write fails.
9. **Concurrency/failure behavior:** two writers do not lose unrelated alerts;
   a failed atomic replacement leaves the previous file readable.

No new pytest selector should be inferred from the issue title; run the named
files or collected test node IDs.

## Migration and rollback

No data migration is required. Existing markdown files are read in place, and
the first write after upgrade may normalize only the newly appended line. Do
not rewrite or prune historical files automatically. Config defaults should be
backward-compatible and opt-out/override capable.

Rollback is a code/config rollback: the old reader can continue to parse the
canonical lines emitted by the new writer, and deduplicated occurrences are
semantically equivalent to repeated lines for existing consumers. If a rollout
shows false blocking or missed alerts, disable the expiry policy via config and
roll back the code; historical files remain intact. Any future compaction must
be a separately approved, backup-producing operation.

## Acceptance criteria

- A single, documented definition of an active alert is used by the pre-exec
  gate, list/status/context, and support-facing active views.
- Repeated evaluation of one telemetry/job event does not append unbounded
  duplicate records, while recurring incidents and distinct jobs remain
  observable.
- Expired timestamped alerts remain auditable but do not block execution or
  claim to be active; unknown untimestamped CRITICAL remains fail-safe.
- Every sentinel-producing reconciliation path writes to the intended
  workspace-local file, including daemon reconciliation and live selftest.
- Existing canonical/legacy files, `sentinel clear`, platform-window counts,
  and `--force` behavior remain compatible.
- The focused pytest files pass with no new failures, and selftest verifies
  sentinel/telemetry isolation.

## Non-goals

- Replacing markdown with SQLite or a remote alert service.
- Automatically deleting, truncating, or rewriting historical sentinel data.
- Changing alert thresholds for token bloat, cost inflation, quota, flatline,
  or stall detection.
- Changing the separate migration marker `.synlynk/.synlynk_migrated`.
