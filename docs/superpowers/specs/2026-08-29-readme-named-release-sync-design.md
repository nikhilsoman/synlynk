# README Named-Release Sync — Design

**Status:** Implementation-ready (issue #1242)
**Date:** 2026-08-29
**Issue:** [#1242](https://github.com/nikhilsoman/synlynk/issues/1242)

## Problem

The root README is a named-release surface, but nothing in `synlynk release` or CLAUDE.md gates it. After v0.12.0 the file kept advertising `v0.12.0` / `1,140 tests` while `VERSION` moved to `0.18.0` and pytest collection grew past 2,300. Hero copy, install instructions, and shipped-vs-planned command claims can drift the same way.

## Goal

Make stale README metadata visible and blocking before a named release is tagged, without turning every mid-cycle PR into a docs rewrite.

## Decision

Add a **release-time README consistency validator**, invoked by:

- `synlynk release --check-docs` — companion preflight; does not bump VERSION, write CHANGELOG, or create a blog stub
- `synlynk release` (actual cut, including `--dry-run`) — same validator against the version about to be written; **fail closed** on unwaived errors so a cut cannot complete while the README still advertises an older release version

Keep the implementation in `synlynk/release_readme.py`. Do not auto-edit README (marketing copy stays human-authored). Reuse `scripts/generate_command_docs.py` for the generated command block already delimited by `<!-- commands:start -->` / `<!-- commands:end -->`.

## Checks

| Check id | What | Waivable |
|---|---|---|
| `version` | Version badge (`badge/version-X.Y.Z`) equals expected version. Expected version is the version the cut would write, or current `VERSION` for `--check-docs` without `--version`/`--minor`. | **No.** An older advertised version after a named release is the bug. |
| `test_count` | Numeric claims (`tests-N` badge and `N tests passing` / `N tests collected` prose) must agree with each other and with `pytest --collect-only` (or `0` when `tests/` is absent). A repo that collects `> 0` tests must advertise that count. Collection failure is reported as unverified. **Collection is a count check only** — it does not run the suite and does not attest that tests pass. README wording such as “tests passing” is treated as a collected-count claim. | Yes, with a recorded reason |
| `hero` | First `**vX.Y.Z:**` summary matches expected version and has a non-empty summary. | Yes |
| `install` | README still documents at least one current install path: `pipx install`, `install.sh`, or `python3 bin/synlynk.py`. | Yes |
| `links` | Relative markdown links resolve to files under the **abspath-normalized** repo root. `http(s)`/`mailto`/anchors are skipped. GitHub README UI routes such as `../../discussions` are skipped (not local files). | Yes |
| `commands` | Generated command block matches `render_readme_section()`. `synlynk <cmd>` mentions **outside** that block are taken only from **inline code** (`` `synlynk …` ``) and **fenced code blocks**, not ordinary prose. Mentions must be in `COMMAND_TAXONOMY` unless the same line marks them as planned (`coming soon`, `planned`, `not yet`, `unreleased`, `will ship`). Claiming a command that is not in the taxonomy and is not marked planned is an error. | Yes |

## Review corrections (job-1a7b2c52)

1. Do not treat prose such as “synlynk is a Python CLI”, “synlynk globally”, or “synlynk before” as commands.
2. Normalize `root` (including `root="."`) before join/containment so valid relative links are not reported as escaping the repo.
3. `../../discussions` (and sibling GitHub UI tabs) are valid README routes, not missing files.
4. Never describe collect-only as proof that N tests are passing.

## When a README update is unnecessary

Recorded explicitly, never implied:

1. **Already in sync** — every check is green for the version being released. No edit, no waiver.
2. **Waived check** — a waivable check is skipped only via `--waive <check>=<reason>` with a non-empty reason. The reason is printed on the checklist. `version` cannot be waived.
3. **No advertised test suite** — `tests/` missing or collection count `0` and the README states no numeric test count. Not an error.

A patch/hotfix still needs a README version that matches the version being tagged. Internal-only changes are not a reason to leave a previous named-release version in the badge.

## CLI

```
synlynk release --check-docs
synlynk release --check-docs --version 0.18.0
synlynk release --check-docs --waive test_count=collect unavailable in this environment
synlynk release --minor          # validates against the version about to be written, then cuts
```

`--check-docs` does not require `release_cut` authority (read-only validation). A real cut still does.

Exit: `0` when there are no unwaived errors; `1` from `--check-docs` on failure; a real cut raises `RuntimeError` (same as unauthorized `release_cut`) and writes nothing.

## Protocol

CLAUDE.md gains a **Named Release README Sync** standing instruction listing the six checklist items and the waiver rule. `cmd_release`'s printed checklist includes a README line plus the per-check results.

## Out of scope

- Rewriting current README marketing copy to v0.18.0 in this change (the gate will fail the next cut until that edit happens)
- Website/changelog/PDF bundle refresh
- Auto-updating badges from CI
- Blog Post Protocol (still paused)
- Running the full pytest suite as part of `synlynk release` (the test-count gate is collection only)

## Test plan

- Fixture README with stale version/test-count → errors
- Matching README → no errors
- Planned command mention → no `commands` error; unmarked unshipped command in inline code → error
- Prose “synlynk is a Python CLI” / “synlynk globally” → no `commands` error
- `root="."` with a valid in-repo relative link → no escape finding
- `../../discussions` → no escape finding; a true `../outside.md` escape still errors
- “N tests passing” matching collect-only count is green as a **count** claim; report labels it collect-only / not pass/fail
- `--waive test_count=...` records the reason; `--waive version=...` still fails
- `cmd_release` does not write VERSION when README version is stale
- `synlynk release --check-docs` is parsed and fails closed
- Real README: still flags stale version/test-count; does not flag the prose/GitHub-route patterns above
