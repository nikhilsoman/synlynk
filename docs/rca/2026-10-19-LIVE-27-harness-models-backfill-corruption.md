# [LIVE-27] RCA: PR #2434 Backfill Corrupted `harness_models`, Breaking Fleet-Wide Dispatch for Codex, Grok, and Agy

**Declared:** 2026-10-19  
**Severity:** Sev1 — Critical fleet-wide dispatch failure (Codex, Grok, and Agy completely down; only Claude and Muse operational)  
**Parent Issue:** [#2441](https://github.com/nikhilsoman/synlynk/issues/2441)  
**Related PRs & Issues:** [#2434](https://github.com/nikhilsoman/synlynk/pull/2434) (root cause), [#2443](https://github.com/nikhilsoman/synlynk/pull/2443) (partial fix), [#2440](https://github.com/nikhilsoman/synlynk/issues/2440), [#2442](https://github.com/nikhilsoman/synlynk/issues/2442), [#2445](https://github.com/nikhilsoman/synlynk/issues/2445)  
**Author / Harness:** Agy (`agy-2.x`, powered by Gemini)  

---

## Executive Summary

On 2026-10-19 at 06:30 UTC, PR #2434 (*feat(capability): Phase 2A Historical Capability Backfill & SFIA Taxonomy Expansion*) merged to `main`. As part of the Phase 2A verification drill run just prior to commit (`2026-10-19 05:52:48 UTC`), `run_capability_backfill()` in `synlynk/capability_backfill.py` called `sync_harness_models_window()` in `synlynk/capability_window.py`.

`sync_harness_models_window()` performed an unfiltered query across historical `cost_entries` and `daemon_jobs` tables and blindly inserted 75 distinct `(agent, model)` strings into `harness_models` with `discovery_source='execution_log'`. Because `discovered_at` was omitted from the `INSERT` column list, SQLite set `discovered_at` to its column default (`CURRENT_TIMESTAMP`), stamping all 75 rows with the exact same second-level timestamp: `2026-10-19 05:52:48`.

When downstream dispatch attempted to resolve models via `resolve_tier_model()` in `synlynk/models.py`, `get_active_harness_models()` executed `ORDER BY discovered_at DESC`. Because 75 newly created rows shared the newest timestamp, SQLite broke ties by internal rowid order. For Codex, Grok, and Agy, garbage log scrapes and retired models won the tie-break:
- **Codex** resolved to `"'unknown'\nsynlynk/db.py:3772:"`
- **Grok** resolved to `'grok-3'` (retired)
- **Agy** resolved to `'gemini-1.5-pro'` (retired)

Every dispatch to Codex, Grok, or Agy failed immediately with `"unknown model id"`. Claude and Muse only survived by lucky internal row storage order resolving to real models (`claude-sonnet-4-6` and `muse-spark-1.3`).

An initial fix in PR #2443 added `is_plausible_model_id()` to reject code/log syntax shapes, but that fix was incomplete: Codex fell through to another unvalidated row (`'None,'`), while Grok and Agy remained pinned to validly shaped but retired models (`grok-3` and `gemini-1.5-pro`). This RCA establishes the root cause, investigates why review failed to intercept it, and provides a complete 3-layer defense-in-depth fix.

---

## 1. Timeline & Incident Manifestation

| Timestamp (UTC) | Event | Details / Evidence |
|:---|:---|:---|
| **2026-10-19 05:52:48** | **Corruption Ingested into `state.db`** | `synlynk capability backfill` executed as part of Phase 2A production verification. `sync_harness_models_window()` executed lines 104–159 of `synlynk/capability_window.py`, inserting 75 unvetted rows into `harness_models` with identical default `CURRENT_TIMESTAMP` `2026-10-19 05:52:48`. |
| **2026-10-19 06:30:11** | **PR #2434 Formal Review** | PR #2434 self-reviewed by `nikhilsoman` under same-identity-collision fallback checklist (#423/PR #417 pattern). |
| **2026-10-19 06:30:19** | **PR #2434 Merged** | PR #2434 merged to `main` (commit `5a38b28b`). |
| **2026-10-19 11:45:12** | **First External Failure (Grok)** | Job `job-573f985d` (grok) failed with `Couldn't set model 'grok-3': Invalid params: "unknown model id"`. Followed by `job-ba4d5b7a` (11:49 UTC) and `job-ca35cc28` (14:20 UTC). |
| **2026-10-19 14:23:53** | **First External Failure (Codex)** | Job `job-cb6a2dc5` (codex) dispatched with `--model "'unknown'\nsynlynk/db.py:3772:"`. Between 16:11 and 16:47 UTC, 8 consecutive Codex jobs failed (`job-a8170ec4`, `job-8e0dd608`, `job-eedb1bd2`, `job-f05eac3d`, `job-34e7a9c5`, `job-3af8e70b`, `job-c075eb79`, `job-2fbe9fa3`). |
| **2026-10-19 16:52:43** | **Issue #2441 Declared** | Issue #2441 filed documenting the `harness_models` corruption and timestamp tie-break. Grok workaround attempt (`job-1d1e1967`) failed. Work redirected to Muse. |
| **2026-10-19 17:12:56** | **Agy Failures Confirmed** | Jobs `job-7f09cf6c` and `job-d080f27b` (agy) failed immediately when dispatched with `--model gemini-1.5-pro`. |
| **2026-10-19 17:19:10** | **PR #2443 Implemented & Dispatched** | Muse implemented PR #2443 (`is_plausible_model_id()`). Dispatched to Claude for QA review (`job-f43f4d33`). |
| **2026-10-19 17:42:09** | **PR #2443 Merged (Partial Fix)** | PR #2443 merged to `main` (commit `05a2ab50`). |
| **2026-10-19 17:50:00** | **Incomplete Fix Verified Live; Issue Reopened** | Live DB test post-merge confirmed Codex resolves to `'None,'`, Grok resolves to `'grok-3'`, and Agy resolves to `'gemini-1.5-pro'`. Issue #2441 reopened by PM. Sev1 incident declared. |

---

## 2. Root Cause Analysis

### Step 1: Confirmation of `sync_harness_models_window()` as the Ingestion Culprit

Inspection of `/Users/nikhilsoman/.synlynk/workspaces/synlynk/state.db` confirmed:
1. Exactly **75 rows** in `harness_models` share the identical timestamp `2026-10-19 05:52:48`.
2. **100% of these 75 rows** have `discovery_source = 'execution_log'`.
3. Every single garbage string matches an exact entry in `cost_entries` and `daemon_jobs`.

The causal mechanism is traced directly to `synlynk/capability_window.py:104-159`:

```python
# synlynk/capability_window.py:104-149
def sync_harness_models_window(conn: sqlite3.Connection, lookback_days: int = 30) -> list[dict[str, Any]]:
    # 1. Discover models from cost_entries
    try:
        cost_rows = conn.execute("""
            SELECT agent, model, MIN(recorded_at), MAX(recorded_at)
            FROM cost_entries
            WHERE agent IS NOT NULL AND model IS NOT NULL AND model != ''
            GROUP BY agent, model
        """).fetchall()
    except sqlite3.OperationalError:
        cost_rows = []

    # 2. Discover models from daemon_jobs
    try:
        job_rows = conn.execute("""
            SELECT agent, resolved_model, MIN(completed_at), MAX(completed_at)
            FROM daemon_jobs
            WHERE agent IS NOT NULL AND resolved_model IS NOT NULL AND resolved_model != ''
            GROUP BY agent, resolved_model
        """).fetchall()
    except sqlite3.OperationalError:
        job_rows = []

    observed: dict[tuple[str, str], tuple[str, str]] = {}
    for agent, model, first_seen, last_seen in cost_rows + job_rows:
        key = (str(agent).strip(), str(model).strip())
        ...
        observed[key] = ...

    # Insert newly observed models into harness_models
    for (harness, model), (first_seen, last_seen) in observed.items():
        try:
            conn.execute("""
                INSERT INTO harness_models (
                    harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source
                ) VALUES (?, ?, ?, ?, 'active', 'execution_log')
                ON CONFLICT(harness_name, model_id, provider) DO UPDATE SET
                    last_seen_at = MAX(harness_models.last_seen_at, excluded.last_seen_at)
            """, (harness, model, first_seen, last_seen))
        except sqlite3.OperationalError:
            pass
```

### The Ingestion Flaws
1. **Blind Trust of Raw Log Data:** `cost_entries` and `daemon_jobs` historically stored unparsed log fragments from prior logging/scraping bugs (e.g. `"'unknown'\nsynlynk/db.py:3772:"`, `'_pkg("extract_model_version")(log_text,'`, `'None,'`). `sync_harness_models_window()` treated every non-empty string in these historical logs as an authoritative model candidate.
2. **Omission of `discovered_at` in the `INSERT` Statement:**
   The `harness_models` schema specifies:
   `discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
   Because `discovered_at` was not explicitly supplied in the `INSERT` statement, SQLite assigned the transaction default `CURRENT_TIMESTAMP` (`2026-10-19 05:52:48`) to all 75 new rows in bulk.
3. **Automatic Active Promotion:**
   Lines 152–159 ran:
   ```python
   conn.execute(
       f"UPDATE harness_models SET status = 'active' "
       f"WHERE last_seen_at >= datetime('now', '-{int(lookback_days)} days')"
   )
   ```
   Any garbage row with recent activity or defaulted timestamps was promoted to `status = 'active'`.

### Downstream Resolution Collision
In `synlynk/models.py:279-282`:
```python
harness_rows = get_active_harness_models(conn, harness=harness)
if harness_rows:
    return harness_rows[0]["model_id"]
```
Where `get_active_harness_models()` in `synlynk/db.py:918-921` executes:
```sql
SELECT * FROM harness_models WHERE status='active' AND harness_name=? ORDER BY discovered_at DESC
```
Because the 75 corrupted rows were stamped `2026-10-19 05:52:48` (newer than legitimate models discovered on 2026-10-15 or 2026-10-17), they tied for first place. SQLite broke the tie by internal storage rowid order, deterministically returning garbage or retired models for Codex, Grok, and Agy.

---

## 3. Why Review Didn't Catch It

### The Same-Identity Review Gap
PR #2434 was authored, reviewed, and merged entirely under the same GitHub account (`nikhilsoman`):
- Review submitted: `2026-10-19T06:30:11Z`
- PR merged: `2026-10-19T06:30:19Z` (8-second elapsed review window)
- Review body: formal same-identity-collision fallback checklist per #423 / PR #417.

### What an Independent Cross-Harness Review Would Have Caught
When the author is the reviewer, confirmation bias dominates: the review checklist verified that the new SFIA classifier had tests and that CI was green, but asked zero adversarial questions about state mutation.

A genuine cross-harness reviewer (e.g. Codex, Grok, or Claude reviewing Agy's PR) would have flagged:
1. **Unsanitized Dynamic Ingestion:** Why is a dynamic window function pulling unvalidated strings directly from historical execution logs into the canonical `harness_models` catalog?
2. **Timestamp Tie Hazard:** In SQLite, bulk inserts default to the exact same second-level `CURRENT_TIMESTAMP`. In a table ordered by `discovered_at DESC`, bulk inserts will cause non-deterministic tie-breaks that clobber curated models.
3. **Synthetic Unit Test Blind Spot:** `tests/test_capability_window.py` tested `sync_harness_models_window()` solely against clean, mocked in-memory databases with pristine values like `"gpt-4"` and `"claude-3"`. It never tested realistic dirty strings or verified that existing curated models maintain priority over scraped execution logs.
4. **Missing Catalog Invariant Assertions:** No test asserted that `resolve_tier_model()` output was unaffected by dynamic window synchronization, or that `resolve_tier_model()` always produces a model from the maintained allowlist.

---

## 4. Complete Fix Proposal: 3-Layer Defense-in-Depth

PR #2443 was an emergency symptom-level fix (`is_plausible_model_id()`). It attempted to filter garbage strings at the output gate using basic character checks. It failed because:
1. It only looked for whitespace, quotes, backticks, parens, and `.py:123` file line references. It missed comma-terminated strings like `'None,'`.
2. It fundamentally cannot distinguish between a current valid model and a retired/stale model (`grok-3`, `gemini-1.5-pro`), because retired models are syntactically valid model names.

A durable, complete fix requires three coordinated layers:

### Layer 1: Ingestion Hardening in `sync_harness_models_window()` (Root Cause Fix)
- **Allowlist & Baseline Validation:** Disallow inserting any model into `harness_models` unless it is known to the harness baseline (`HARNESS_CAPABILITY_BASELINES`, `models.json`) or passes a per-harness allowlist.
- **Never Overwrite Curated/CLI Discoveries:** If a model has `discovery_source IN ('curated', 'config_file', 'cli:*')`, dynamic execution logs must not alter its precedence or restamp its discovery metadata.
- **Explicit `discovered_at` Handling:** Never rely on default `CURRENT_TIMESTAMP` during bulk synchronization. Stagger or preserve authentic first-seen timestamps.

### Layer 2: State DB Data Remediation (State Cleansing)
- Execute a database migration / remediation script on the canonical `state.db`:
  - Delete or mark `status = 'deprecated'` for all invalid or retired rows with `discovery_source = 'execution_log'`. Specifically purge `'None,'`, `'''unknown''...'`, `_pkg(...)`, `grok-3`, `gemini-1.5-pro`, etc.
  - Re-run `synlynk probe` or restore curated models to reset active models to legitimate current versions:
    - Codex: `gpt-5.6-luna` / `gpt-6-luna` / `gpt-5.6-terra`
    - Grok: `grok-4.5` / `grok-4.6` / `grok-4.7`
    - Agy: `gemini-3.8-flash-high` / `gemini-3.8-flash-medium`

### Layer 3: Catalog Resolution Hardening in `resolve_tier_model()` (Resolution Gate)
- **Source-Tiered Ordering:** Update `get_active_harness_models()` or `resolve_tier_model()` to sort candidates by discovery authority before timestamp:
  ```sql
  ORDER BY 
    CASE discovery_source 
      WHEN 'curated' THEN 1 
      WHEN 'config_file' THEN 2 
      WHEN 'cli:grok' THEN 3 
      WHEN 'self_report' THEN 4 
      ELSE 5 
    END ASC, 
    discovered_at DESC
  ```
- **Allowlist Validation:** Replace naive regex shape filtering with validation against a maintained per-harness valid model list. If the top discovered model is not in the allowlist, fall through to static curated tier models (`_static_tier_model`).

---

## 5. Prevention & Invariant Tests

To guarantee this defect class cannot recur:

1. **Database Invariant Test (`tests/test_harness_model_invariants.py`):**
   - Assert `harness_models` contains zero rows with whitespace, commas, backticks, quotes, or code references.
   - Assert `harness_models` has no two active rows for the same harness sharing an identical `discovered_at` timestamp unless explicitly verified.
   - Assert curated models always have precedence over `execution_log` models.
2. **Resolution Invariant Test (`tests/test_model_resolution_allowlist.py`):**
   - For every supported harness (`codex`, `grok`, `agy`, `claude`, `muse`), `resolve_tier_model("balanced", harness)` must return an active, non-retired model present in the harness's current configuration.
3. **Dirty Ingestion Test (`tests/test_capability_window_dirty_input.py`):**
   - Test `sync_harness_models_window()` against dirty databases seeded with Python exception snippets, commas, `None`, and retired models. Verify that none are inserted into `harness_models` as active models.
4. **Enforce Cross-Harness Review on Core Systems:**
   - Any PR touching `synlynk/models.py`, `synlynk/capability_window.py`, `synlynk/dispatch.py`, or `synlynk/db.py` must require review from an alternate harness, strictly forbidding same-identity approval.

---

## 6. Action Items

| Ticket ID | Description | Severity | Priority | Component |
|:---|:---|:---|:---|:---|
| **#2447** | `[LIVE-27] Cleanse corrupted execution_log rows from harness_models in canonical state.db` | Sev1 | P0 | Database / Ops |
| **#2448** | `[LIVE-27] Harden sync_harness_models_window() candidate ingestion and timestamp handling` | Sev1 | P0 | Backend (`capability_window.py`) |
| **#2449** | `[LIVE-27] Prioritize authoritative discovery sources and enforce allowlist in resolve_tier_model()` | Sev1 | P0 | Backend (`models.py`, `db.py`) |
| **#2450** | `[LIVE-27] Add fleet-wide model resolution and catalog invariant test suite` | Sev1 | P0 | Testing |

---

## Conclusion & Next Steps

This RCA confirms `sync_harness_models_window()` in PR #2434 was the primary culprit that bulk-stamped corrupted rows into `harness_models`, triggering a fleet-wide dispatch failure due to `ORDER BY discovered_at DESC` tie-breaking. PR #2443's partial fix addressed only surface syntax and left the fleet broken.

Per synlynk review policy, the corrective implementation PR must be reviewed and approved by an independent non-author harness (Claude or Muse, while Codex/Grok remain blocked) prior to merge.
