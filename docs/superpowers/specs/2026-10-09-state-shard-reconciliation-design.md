# State Shard Reconciliation — Design

**Status:** Approved (Nikhil, 2026-10-09)
**Issue:** gh:#1831 ("Cleanup: 11,384 legacy state.db shards under `~/.synlynk/projects/`")
**Blocks:** gh:#1993 (`synlynk capability report`) per `.synlynk/policy.json`'s `capability_policy.blocking_dependency`

## Background

gh:#1831 proposed reclaiming ~6.1GB across 11,384 legacy `~/.synlynk/projects/<hash>/state.db`
shards, on the premise that they're dead weight with "no active writes since 2026-09-15." A
spot-check performed before this design (empirical verification, not assumption) found that
claim incomplete in a load-bearing way:

- 136 of the 11,383 shards have mtimes after 2026-09-15; the newest is 2026-09-28.
- Of those 136, only 4 contain real (non-empty) `stories` data. One is a synthetic seed row.
  One (`2eb5458a`, 162 rows) belongs to a different project (rxcc), not synlynk.
- The other two are both **synlynk's own project**, under different legacy hash keys:
  `d8a234b7` (93 stories, the shard gh:#1831's own body calls "canonical") and `13267207`
  (**975 stories** — ten times more rows, last written 2026-09-18, with real content: "#914
  Wave 2 work graph and policy", "add product repo registration", etc.).
- Neither legacy shard has a `state_identity` table — both predate that schema, which is why
  they were never fingerprint-matched to each other or to the real canonical ledger
  (`~/.synlynk/workspaces/<slug>/state.db`, which currently holds 1145 stories — see
  `[[stray-local-state-db]]` memory).
- `13267207`'s last write (2026-09-18) falls *between* the two git-common-dir resolution fixes
  (`79a81027`, 2026-08-19, and `dade0c4b`, 2026-09-25) that were intended to close the
  CWD-hash-per-directory bug class (the same class root-caused for the daemon pidfile/
  github_apps lookup in gh:#1228). No writes to either legacy synlynk shard after
  `dade0c4b` — consistent with that fix actually closing the *common* case.
- `_project_root()` (`synlynk/__init__.py:265-278`) still has a bare `except Exception: pass`
  that falls back to raw `os.getcwd()` whenever the `git rev-parse --git-common-dir`
  subprocess call fails for any reason. That is a residual, currently-dormant path by which a
  future environment (e.g. a sandboxed dispatch job with a restricted PATH) could silently
  mint a new stray shard the same way `13267207`/`d8a234b7` were minted.

**Conclusion:** this is reconciliation of real, unmerged work-tracking history — not routine
cleanup of dead files — and the "one project → one legacy hash" assumption behind gh:#1831's
original asks is empirically false. gh:#1831's own instruction stands: **do not bulk-delete
`~/.synlynk/projects/*` before reconciling.**

## Goals

1. Close the residual live-bleed path by hardening `_project_root()`'s silent `getcwd()`
   fallback.
2. Extend the existing `synlynk state inventory --all` command (it already classifies shards,
   computes sha256/integrity, and reads `state_identity` when present — see
   `synlynk/state_inventory.py`) with: row/story counts, staleness, and a best-effort project
   match for every legacy shard.
3. Add a `--reconcile <project-slug>` mode to the same command that computes a union-merge
   plan (dry-run by default), snapshots the canonical DB before any write, and only writes
   with `--apply`.
4. Explicitly defer deletion: reclaiming the 6.1GB is a separate, later, manual step once
   reconciliation and a human review pass are complete.

## Non-Goals

- A general-purpose SQLite diff/merge library. First cut covers the `stories` table only —
  the concrete case found in `13267207`/`2eb5458a`. Other tables (capability_ratings,
  cost_entries, etc.) are explicitly out of scope for this round; extending the same mechanism
  to them is a natural follow-up once the `stories` path is proven.
- Changing `migrate_state_db_if_needed()`'s single-`old_key` migration-at-startup mechanism.
  That function's job is one-time adoption of *the* legacy shard at startup; this design's
  tooling is the offline sweep for shards that mechanism never saw or adopted.
- Reconciling other projects' shards (e.g. rxcc's `2eb5458a`) from synlynk's own repo. The
  tool is generic — rxcc runs it from its own checkout — but driving that work is out of scope
  here.

## Architecture

```
synlynk/__init__.py
  _project_root()              # hardened: raises RuntimeError on git-resolution failure
                                # unless SYNLYNK_ALLOW_CWD_FALLBACK=1 is set

synlynk/state_inventory.py
  inventory()                  # existing — gains per-row: row_count, mtime_iso,
                                #   staleness_days, project_match
                                #   ({slug, method: "fingerprint"|"heuristic"|"none", confidence})
  _match_project()             # NEW — fingerprint lookup against state_identity rows across
                                #   ~/.synlynk/workspaces/*/state.db; falls back to a
                                #   keyword/issue-number heuristic scan of stories.title/body
                                #   for shards with no state_identity table
  _reconcile_plan()            # NEW — computes a union-merge plan for one project:
                                #   {to_add: [...], already_present: [...], conflicts: [...]}
  cmd_state_inventory()        # existing — gains --reconcile <slug>, --apply,
                                #   --cutoff-days, --ignore-conflicts
```

### `_project_root()` hardening

```python
def _project_root() -> str:
    import subprocess
    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if common:
            return os.path.abspath(os.path.join(common, ".."))
    except Exception as exc:
        if os.environ.get("SYNLYNK_ALLOW_CWD_FALLBACK") == "1":
            return os.getcwd()
        raise RuntimeError(
            "could not resolve git-common-dir; refusing to fall back to CWD "
            "(would risk minting a stray per-directory state shard — see gh:#1831). "
            "Set SYNLYNK_ALLOW_CWD_FALLBACK=1 to override."
        ) from exc
    return os.getcwd()
```

If `common` resolves to an empty string (no exception, but also no output), the existing
behavior of falling through to `os.getcwd()` is preserved unchanged — the hardening only
applies to the exception path, since an empty-but-successful resolution is a different
(and not yet observed) failure mode that doesn't need a behavior change here.

### Project matching (`_match_project()`)

1. **Fingerprint path** — for shards with a `state_identity` table: read `product_id` /
   `canonical_path`, compare against every `~/.synlynk/workspaces/*/state.db`'s own
   `state_identity` row. An exact `product_id` match yields `confidence: "exact"`.
2. **Heuristic path** — for pre-schema shards (`13267207`, `d8a234b7`, `2eb5458a`, and any
   other shard lacking `state_identity`): pull the 20 most recent `stories.title`/`body`
   values, extract `#NNNN` issue references and distinctive keyword n-grams, and compare
   against the same window of recent stories in each candidate canonical DB. A match above a
   fixed similarity floor yields `confidence: "heuristic"`; below it, `project_match: null`
   and the row is surfaced as `"unmatched — needs manual triage"` rather than guessed.
3. Every inventory row carries `project_match`, so `--reconcile` targets can be filtered
   directly from `state inventory --all --json`.

### Merge plan (`_reconcile_plan(shard_path, canonical_path)`)

- Key rows by `(id, created_at)` first; on collision, fall back to normalized-title
  similarity — this handles the case actually observed between `d8a234b7`'s 93 rows and
  `13267207`'s 975, whose autoincrement `id` spaces don't correspond to the same stories.
- `to_add`: rows present in the shard with no reasonable match in canonical.
- `already_present`: rows that match an existing canonical row closely enough to skip (same
  id/title/timestamp within a small tolerance).
- `conflicts`: same key, differing content (e.g. a title or status edited independently in
  each copy). These are **never auto-resolved** — written to a `conflicts.json` sidecar next
  to the dry-run output for manual review. `--apply` refuses to proceed if any conflicts exist
  unless `--ignore-conflicts` is passed, in which case conflicting rows are skipped (never
  overwritten), not force-merged.

### Safety

- Default invocation (`--reconcile <slug>`) is dry-run: prints the plan, writes nothing.
- `--apply` first copies the canonical DB to `<canonical_path>.pre-reconcile-<timestamp>.bak`,
  then runs the merge inside a single transaction; any exception rolls back, leaving the
  `.bak` in place.
- The legacy shard itself is never modified or deleted by this command. Cleanup/deletion of
  `~/.synlynk/projects/*` stays a distinct, manual, later step, per gh:#1831's own instruction.

## Testing Plan

- `_match_project()`: exact fingerprint match, heuristic match above/below the similarity
  floor, and no-match case, using small fixture DBs (never the real `~/.synlynk` tree).
- `_reconcile_plan()`: no-overlap union, full-overlap no-op, conflicting-row detection, and
  the id-collision-different-shard-space case mirroring the `d8a234b7`/`13267207` mismatch
  actually observed.
- Integration test: dry-run then `--apply` against fixture shards, asserting the `.bak` file
  is created and that transaction atomicity holds (inject a failure mid-merge; assert the
  canonical DB is untouched afterward).
- `_project_root()` hardening: mock `subprocess.check_output` to raise, assert `RuntimeError`
  without `SYNLYNK_ALLOW_CWD_FALLBACK`; assert the `getcwd()` fallback with it set.
- No test touches the real `~/.synlynk/projects/` tree or the live canonical workspace DB.

## Rollout

1. Land `_project_root()` hardening + its tests.
2. Land `state_inventory.py` extensions (row counts, staleness, `_match_project`) + tests —
   read-only, no behavior change to existing output besides new fields.
3. Land `--reconcile`/`--apply`/`_reconcile_plan` + tests.
4. Run `synlynk state inventory --all --json` for real, triage `project_match: null` rows
   manually, then run `--reconcile` dry-runs for each matched project (starting with
   synlynk's own `13267207`/`d8a234b7` case) and review the plans before any `--apply`.
5. Only after reconciliation is reviewed and applied project-by-project does bulk deletion of
   `~/.synlynk/projects/*` become a candidate follow-up — tracked separately, not in this
   design's scope.
