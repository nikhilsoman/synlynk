# LIVE-11: checkpoint() hardcodes project-docs/todo.md, ignoring migration state

**Date:** 2026-08-29
**Severity:** Sev1
**Issue:** [#1217](https://github.com/nikhilsoman/synlynk/issues/1217)
**Related:** [#936](https://github.com/nikhilsoman/synlynk/issues/936) (briefly reopened during this investigation on a mistaken premise, since re-closed — see Correction below; its two stated root causes were already fixed by PR #1038 and are unrelated to this issue's scope)

> **Correction (2026-08-29, same day):** The original version of this RCA claimed devlogs and decision records shared this same migration-unaware, non-DB-backed defect, and that #936's own sweep had never been completed. Direct code investigation (during implementation-plan drafting for the follow-up spec) found that claim false: `devlog_entries` and `decisions` already exist as state.db tables, are already fully wired into `checkpoint()` (via `cmd_devlog_append()`/`_write_devlog_file()`) and `cmd_decide()` (via `_write_decision_record_md()`), and are already migration-aware. This was fixed properly, in full, by commit `c3951e4` (PR #1038, "fix: workspace context write-through for decisions + devlogs (#936)", merged 2026-08-17) — #936 was correctly resolved, just closed without a resolution comment linking that PR, which is what made it look unresolved on reopening. Only `checkpoint()`'s handling of `todo.md` remains broken; it was out of PR #1038's scope. This revision removes the incorrect claims and narrows scope to the verified bug. #1219 and #1220 (opened on the original, wider premise) have been closed/rescoped accordingly — see their closing comments. #936 itself has been re-closed with an accurate comment linking PR #1038.

## Summary

`checkpoint()` writes to a hardcoded `project-docs/todo.md` path regardless of whether the repo has been migrated to `.synlynk/project-docs/`. The real, state.db-driven `todo.md` generator (`_generate_todo_md()`) writes to the correct migration-aware path — but `checkpoint()` never calls it and never touches that file. The result is two disconnected `todo.md`-shaped files in every migrated repo, with no reconciliation, no warning, and no error. One is git-tracked and hand-edited by every PM/Claude session; the other is stamped "generated — source of truth is state.db, do NOT hand-edit" but has never received real backlog content.

## Timeline

- **2026-08-14** — Divergence in devlogs/decisions first surfaced from a cc-videoreframing session, filed as #936.
- **2026-08-17** — PR #1038 (commit `c3951e4`) merged, fixing #936's two confirmed root causes: `checkpoint()` write-through to `devlog_entries`, and `cmd_decide()`'s migration-aware path resolution. #936 closed the same day, but without a resolution comment linking the fix — this omission is what made the issue look unresolved on reopening (see 2026-08-29 entry).
- **2026-08-29** — This session hand-wrote a resync of `project-docs/todo.md` (PR #1216) using GitHub issue state, not state.db. The user asked whether that resync should instead have come from state.db, prompting an audit that found `_generate_todo_md()` exists, is migration-aware, and writes to a different path than the one every session actually uses. #936 reopened on the (mistaken) assumption its sweep was incomplete; this RCA and #1217 filed the same day. Later the same day, direct code investigation found #936's fix had in fact landed correctly via PR #1038 — #936 was re-closed with an accurate comment, and this RCA corrected to narrow scope to the genuinely unfixed `todo.md` case.

## Root cause

Two independent write paths exist for "the project's todo.md," and they were never unified:

**Path 1 — `checkpoint()`, `synlynk/__init__.py:2901-2907`:**
```python
def checkpoint() -> None:
    ...
    todo_path = "project-docs/todo.md"
    if _is_migrated():
        devlog_path = os.path.join(_synlynk_project_docs_dir(), "devlogs", f"{canonical_id}.md")
    else:
        devlog_path = os.path.join(_docs_dir(), "devlogs", f"{canonical_id}.md")
```
`todo_path` is a single, unconditional literal. `devlog_path`, defined two lines later in the *same function*, correctly branches on `_is_migrated()`. This is an internal inconsistency within one function, not an environmental or timing issue — proven by direct comparison of the two assignments.

`checkpoint()` reads this file to archive completed (`[x]`/`[~]`/`[>]`) lines into the devlog, and rewrites it with the remainder. In a migrated repo, this means every checkpoint operates on `project-docs/todo.md` — a path that, post-migration, is not the canonical location at all, yet nothing prevents or flags writing to it.

**Path 2 — `_generate_todo_md()`, `synlynk/db.py:1766-1804`:**
```python
def _generate_todo_md() -> None:
    if _is_migrated():
        todo_path = os.path.join(_synlynk_project_docs_dir(), "todo.md")
        ...
    else:
        docs_dir = _docs_dir()
        ...
        todo_path = os.path.join(docs_dir, "todo.md")
    ...
    lines = [
        "# Tasks (generated - source of truth is state.db)\n",
        "# Edit via: synlynk story create/update | Do NOT hand-edit this file\n\n",
    ]
    for story_id, title, engg_domain, status in rows:
        ...
    with open(todo_path, "w") as f:
        f.writelines(lines)
```
This function is correctly migration-aware. It is called from exactly one place: `create_story()` (`synlynk/db.py:2329`), i.e. only when a new `stories` row is inserted via `synlynk story create/update`. Confirmed via `grep -rn "_generate_todo_md()" synlynk/*.py` — no other call site exists (test/selftest references aside).

**Consequence:** In this (migrated) repo, `.synlynk/project-docs/todo.md` exists, is gitignored, and contains exactly two rows — `Story one` and `Story two` — placeholder/test stories, because nothing in this repo's real backlog has ever been represented as a `stories` table row. Meanwhile `project-docs/todo.md` — the file `checkpoint()` operates on, and the file every human/Claude PM session reads, hand-edits, and lands via PR (confirmed via `git log -- project-docs/todo.md` showing prior syncs landing through PRs #1031, #1010, #882, and this session's own #1216) — has no connection to `state.db` at all.

**On #936 and the devlog/decision comparison:** #936 originally claimed two root causes — `checkpoint()` never writing devlog entries to state.db, and `cmd_decide()` resolving a migration-unaware path via `_docs_dir()` with no `_is_migrated()` check. Both were real when filed (2026-08-14) and both were correctly fixed by PR #1038 (`c3951e4`, merged 2026-08-17): `cmd_devlog_append()`/`_write_devlog_file()` (devlogs) and `cmd_decision_record()`/`_write_decision_record_md()` (decisions) are, in current code, DB-backed (via the `devlog_entries` and `decisions` tables respectively) and correctly branch on `_is_migrated()`. `checkpoint()`'s `todo_path`, by contrast, is a bare literal with no `_is_migrated()` branch at all, and — unlike devlogs, which delegate to the DB-backed `cmd_devlog_append()` — bypasses the `stories` table entirely, hand-parsing and rewriting the flat file with regex. `todo.md` was out of PR #1038's scope. This is genuinely a narrower, todo.md-only miss, not an instance of a wider unaudited pattern or a sign #936's fix was incomplete.

## Why this went undetected for so long

- No error, warning, or doctor check exists for `todo.md` drift between the two paths. `synlynk doctor` was never extended with a check for this.
- `.synlynk/project-docs/todo.md` is gitignored, so nobody reviewing diffs or PRs ever sees it or notices it isn't changing.
- The hand-maintained `project-docs/todo.md` file *looks* functional and has been actively, successfully used as the real backlog surface for months — there's no crash, no visible failure, just silent absence of the DB-authority relationship the file's own governance strategy doc describes as already decided.
- #936's fix (PR #1038) was scoped to devlogs and decisions specifically — `todo.md` wasn't part of that sweep, and nothing flagged it as a remaining gap once #936 closed. #936 being closed without a resolution comment linking PR #1038 (a Live Issues SOP miss — the SOP requires a comment stating what was fixed and criteria met) made the issue look unresolved when reopened during this investigation, which is what led to this RCA initially over-claiming its scope.

## Impact

- Confirmed in synlynk itself (this repo). Scope is `checkpoint()`'s `todo.md` handling only — devlogs and decisions are already DB-backed and migration-aware (see Correction note above), so this is not the wider cross-file pattern originally suspected.
- The `stories` table and its capability-scoring/routing machinery (`create_story`, capability_grants, learned scoring per PR #1030) have been operating against a `stories` table that has never received real backlog content in this repo, because nothing ever wrote real stories into it — the actual backlog has lived entirely in hand-edited markdown this whole time.
- No data loss: `project-docs/todo.md`'s content is intact and git-tracked. The impact is architectural — the state.db-as-authority model already achieved for devlogs/decisions was never extended to todo.md, and `_generate_todo_md()`'s own header claims a source of truth that `checkpoint()` doesn't honor.

## Action items

1. **#1218** — Wire `checkpoint()`'s todo.md handling through the `stories` table and `_generate_todo_md()`, mirroring the already-proven `cmd_devlog_append()`/`_write_devlog_file()` pattern used for devlogs — not just a path-literal fix in isolation. Evaluate reusing/extending the existing `_import_todo_to_stories()` backfill parser (`synlynk/db.py:2207`, currently only wired into the one-time `_migrate_import()` flow) rather than designing a new backfill mechanism.
2. ~~**#1219**~~ — Closed: the state.db-authority decision this issue asked for was already made and implemented for devlogs/decisions (PR #1038, `c3951e4`); only todo.md was left out, and that is tracked as the narrower #1218 above. No open decision remains.
3. **#1220** — Rescoped/closed: see issue for final disposition (todo.md-only drift check, folded into #1218, or closed as unnecessary given the scope reduction).

## Prevention

- The Live Issues SOP resolution-comment requirement, if followed for #936's original closure, would have prevented this RCA's initial mistake: a closing comment linking PR #1038 would have made it immediately clear the fix had landed and what it covered, instead of requiring a fresh code audit to reconstruct that during this investigation. Reinforcing that closure comments must state the specific criteria met and link the fixing PR, not just a status change, is the direct prevention here.
- The Harness Capability Reassessment Protocol's cadence-based re-check pattern is a reasonable model to extend to *documentation-authority* claims too: any doc that asserts "X is generated from Y" should have that claim spot-checked periodically, not assumed permanently true once written.
- More broadly: this RCA's own first draft repeated the same failure mode it's about — asserting code behavior from an issue's stated-but-unverified claims rather than fresh reading. Any RCA or spec that generalizes a finding across multiple files/components should independently re-verify each one against current code, not extrapolate from a single confirmed instance.
