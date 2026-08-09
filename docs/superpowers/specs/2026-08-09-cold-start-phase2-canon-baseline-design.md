# Cold-Start Phase 2: workspace-canon.md Baseline Generation

**Status:** Draft, pending review
**Parent spec:** `docs/superpowers/specs/2026-08-09-cold-start-design.md`
**Depends on:** Cold-Start Phase 1 (`synlynk start`, PR #855, merged)

## Goal

Phase 1 shipped `synlynk start` for both new and existing projects, but the existing-project
flow explicitly does **not** generate `workspace-canon.md` — the parent spec defers that to
Phase 2. This phase adds a real, generated `workspace-canon.md` baseline to the existing-project
flow, without attempting the full canon vision from the parent spec in one shot.

Two sections get real, generated content in this phase: a **Documentation Index** and a
**3-claim receipt**. The remaining sections the parent spec describes — Retrospective Roadmap,
Current State (active code only), and the five projection views (Functional / Data / Infra /
Ops / UX) — ship as skeleton stubs marked "not yet assessed." Those sections all depend on
capabilities that don't exist in the codebase yet (most notably a reachability/active-code
classifier for Current State — confirmed absent via exhaustive grep across `synlynk/*.py`) and
belong in a future phase, not bolted onto this one.

## Non-goals (explicitly out of scope for Phase 2)

- Building a reachability/entrypoint/call-graph analyzer for the Current State section.
- Generating real content for Retrospective Roadmap or any of the five projection views.
- The Goals Ledger (already deferred by the parent spec).
- The `canon assess --section <name>` progressive-assessment command (parent spec explicitly
  scopes this out of the baseline flow).
- Any change to the new-project flow (`_run_new_project_flow()`) — canon generation is,
  per the parent spec, not produced for brand-new projects.

## Flow change

`_run_existing_project_flow()` in `synlynk/coldstart.py` currently: runs a shallow
(`deep=False`) `run_workspace_scan()`, prints a summary, then immediately asks "What are you
trying to do right now?" and creates a story.

Phase 2 inserts a step between the scan summary and the intent question:

- **If `workspace-canon.md` does not exist yet** (first run): offer the deep-scan consent
  prompt once, then generate and write `workspace-canon.md`. The deep-scan consent is *only*
  ever asked here — accepting it warms the deep-scan cache (via the existing `cmd_scan(deep=True)`
  path) for future phases to consume, but does not unlock any additional canon content in this
  phase; both sections generated here are producible from shallow-scan data alone.
- **If `workspace-canon.md` already exists** (a `start` re-run): skip the consent offer
  entirely — it is never re-asked — and instead run the staleness check, printing an inline
  warning banner if the stamped section is stale.

Either branch falls through to the existing, unchanged intent question.

## New module: `synlynk/canon.py`

| Function | Responsibility |
|---|---|
| `_offer_deep_scan_consent() -> bool` | Single `[y/N]` prompt, shown only when `workspace-canon.md` doesn't yet exist. On accept, calls the existing `cmd_scan(deep=True)` path. |
| `_build_documentation_index(root) -> str` | Walks `project-docs/` and `docs/` recursively for `.md` files; lists what it finds, grouped by directory. No per-file content parsing — file discovery only. |
| `_build_claim_receipt(scan) -> list[dict]` | Produces exactly 3 claims sourced from shallow-scan data already available in `scan` (e.g. stack detection citing the manifest file path, topology citing `.git` presence, harness availability citing the PATH check). Each claim carries a `confidence` tag (`found` / `inferred`) and a one-line shell command the user can run to verify it themselves. |
| `_render_canon(root, scan, head_sha) -> str` | Assembles the full `workspace-canon.md` markdown: Documentation Index + 3-claim receipt (both stamped with one shared `<!-- canon:section=baseline sha=<head_sha> assessed_at=<iso8601> -->` HTML comment), followed by skeleton stubs for the deferred sections. Skeleton sections carry no provenance stamp. |
| `_parse_canon_provenance(path) -> dict \| None` | Reads the `baseline` section's embedded HTML comment back out of an existing `workspace-canon.md`. Returns `None` if the file or the comment is missing/malformed. |
| `_check_canon_staleness(root) -> list[str]` | Compares the stored SHA (via `_parse_canon_provenance`) to `git rev-parse HEAD`. Returns `["baseline"]` if they differ, `[]` otherwise. Only the stamped `baseline` section can ever be reported stale in Phase 2 — skeleton sections have no content that can go stale. |
| `_write_canon(root, content)` | Writes `workspace-canon.md` at the repo root (overwrites on first-run generation only; re-runs never call this — they only read via `_check_canon_staleness`). |

## Documentation Index generation

Walks two directories recursively for `.md` files, if present: `project-docs/` and `docs/`.
For each file found, lists its relative path grouped under its parent directory heading. No
markdown parsing, no per-file description extraction — this keeps the baseline pass fast and
avoids hand-maintenance drift, matching the parent spec's framing of the index as "the hub, not
a novel document." Repos missing one or both directories simply get a shorter index — no error,
no placeholder text for the missing directory.

## 3-claim receipt content

Each claim is drawn directly from fields already present in the shallow `run_workspace_scan()`
result (`scan.py`'s `base` dict — `stack_labels`, `harnesses`, `repos[].path` / `git` presence).
Claim selection for Phase 2 is fixed to these three, in this order:

1. **Stack detection** — e.g. "Detected Python via `pyproject.toml`" — cites the manifest file
   path found in `repos[0]['stack_labels']`, confidence `found`, verify command
   `cat pyproject.toml | head -20` (or the equivalent manifest file actually detected).
2. **Git repository** — "This is a git repository at `<path>`" — cites `.git` presence,
   confidence `found`, verify command `git -C <path> rev-parse --show-toplevel`.
3. **Harness availability** — "`<harness>` is available on PATH" — cites the harness detected
   in `scan.harnesses`, confidence `found` (or `inferred` if detection came from a config file
   reference rather than a live PATH check — match whatever the existing shallow scan already
   distinguishes), verify command `which <harness>`.

If a repo's shallow scan data is missing a field needed for one of these three claims (e.g. no
stack detected), that claim is skipped and the receipt ships with fewer than 3 claims rather
than fabricating one — never claim something the scan didn't actually find.

## Skeleton stub sections

Retrospective Roadmap, Current State (active code only), and the five projection views
(Functional / Data / Infra / Ops / UX) are each rendered as a heading followed by a single line:
`_Not yet assessed — see docs/superpowers/specs/2026-08-09-cold-start-design.md for the full
canon vision._`. No provenance comment is attached to these sections.

## Staleness banner

On a `start` re-run where `workspace-canon.md` exists, if `_check_canon_staleness()` returns a
non-empty list, print a banner before the intent question, e.g.:

```
⚠ workspace-canon.md's baseline section may be stale (generated at a4f9c21, HEAD is now e88b301).
  Re-run not yet supported in Phase 2 — regenerate manually if needed.
```

Phase 2 does not implement automatic regeneration on staleness — that's a natural Phase 3+
extension once `canon assess` exists. The banner is informational only.

## Testing approach

- **Unit tests** (`tests/test_canon.py`) against tmp git repos for each `canon.py` function:
  documentation index walking (present/absent directories), claim generation (all 3 present,
  partial when scan data is missing a field), provenance round-trip (`_render_canon` →
  `_parse_canon_provenance` recovers the same SHA/timestamp), staleness detection (same SHA →
  `[]`, different SHA → `["baseline"]`, missing/malformed provenance → treated as stale).
  No live harness or network calls, matching existing test conventions in this repo.
- **Integration test**: drive `cmd_start()` twice against the same tmp repo with mocked
  `input()`. First run: assert the deep-scan consent prompt is shown, `workspace-canon.md` is
  written, and it contains both real sections plus the skeleton stubs. Second run (after
  advancing the tmp repo's HEAD with an empty commit): assert the consent prompt is *not* shown
  again and the staleness banner *is* printed.

## Files touched

- Create: `synlynk/canon.py`
- Create: `tests/test_canon.py`
- Modify: `synlynk/coldstart.py` — wire the consent-offer/generate/staleness-check step into
  `_run_existing_project_flow()`, between the scan summary and the intent question.
