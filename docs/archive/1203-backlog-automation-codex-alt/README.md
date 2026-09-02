# Archived: alternate implementation of #1203 (GOVERNS backlog automation)

**Status:** Not merged. Superseded by #1313 (merged 2026-08-31, `cc218fb5`).

## What this is

This directory preserves the Codex-implemented alternate design for #1203, dispatched
via `synlynk dispatch --role dev` (job `job-45231bd5`) on branch
`dispatch/codex/job-45231bd5`, PR #1304. While that dispatch was in flight, #1203 was
independently implemented and merged through a different track as PR #1313, which
shipped a different design:

| | This archive (PR #1304, closed) | Shipped (#1313, merged) |
|---|---|---|
| Ledger | `backlog_proposals` table | `stories` table schema extension |
| Core module | `synlynk/backlog_automation.py` | `synlynk/backlog.py` + `synlynk/backlog_extractor.py` |
| Entry paths | `synlynk backlog note` / `synlynk backlog scan-session` (explicit CLI calls) | `synlynk backlog capture` / `list` / `sync` + auto-staging integrated into `checkpoint()` |
| Dedup | Local ledger hash + GitHub title-search (`skipped_duplicate_gh`) | 4-layer dedup (see #1313 description) |

PR #1304 was closed rather than merged to avoid reintroducing a conflicting/duplicate
implementation. This directory keeps the code and diff available in case any piece
(e.g. the GitHub-title-search dedup layer, `skipped_duplicate_gh` status, added as a
functional-gap fix during this session's plan self-review) is worth cross-checking
against or cherry-picking into the shipped #1313 implementation later.

## Contents

- `backlog_automation.py` — the core module as implemented by job-45231bd5
- `test_backlog_automation.py` — its 15-test suite (all passing in isolation)
- `full-diff.patch` — complete seven-file diff of PR #1304 (`856f0283` -> `1b61df22`), including `synlynk/taxonomy.py`
- `commits.txt` — the 5 commits from `dispatch/codex/job-45231bd5`

## Related

- Spec: `docs/superpowers/specs/2026-08-29-governs-backlog-automation-design.md` (merged via #1281)
- Plan: `docs/superpowers/plans/2026-08-29-governs-backlog-automation.md` (merged via #1281)
- Shipped implementation: PR #1313, issue #1203 (closed)
- Closed PR: https://github.com/nikhilsoman/synlynk/pull/1304
