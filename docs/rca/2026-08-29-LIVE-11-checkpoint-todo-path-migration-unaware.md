# LIVE-11: checkpoint() hardcodes project-docs/todo.md, ignoring migration state

**Date:** 2026-08-29
**Severity:** Sev1
**Issue:** [#1217](https://github.com/nikhilsoman/synlynk/issues/1217)
**Related:** [#936](https://github.com/nikhilsoman/synlynk/issues/936) (reopened — parent divergence issue this is a confirmed instance of)

## Summary

`checkpoint()` writes to a hardcoded `project-docs/todo.md` path regardless of whether the repo has been migrated to `.synlynk/project-docs/`. The real, state.db-driven `todo.md` generator (`_generate_todo_md()`) writes to the correct migration-aware path — but `checkpoint()` never calls it and never touches that file. The result is two disconnected `todo.md`-shaped files in every migrated repo, with no reconciliation, no warning, and no error. One is git-tracked and hand-edited by every PM/Claude session; the other is stamped "generated — source of truth is state.db, do NOT hand-edit" but has never received real backlog content.

## Timeline

- **2026-08-14** — Divergence in devlogs/decisions first surfaced from a cc-videoreframing session, filed as #936.
- **2026-08-17** — #936 closed as COMPLETED with no closing comment. The sweep it called for ("audit every `_docs_dir()` call site") was scoped but, per this RCA, not completed — `checkpoint()`'s `todo_path` was never audited or fixed.
- **2026-08-29** — This session hand-wrote a resync of `project-docs/todo.md` (PR #1216) using GitHub issue state, not state.db. The user asked whether that resync should instead have come from state.db, prompting an audit that found `_generate_todo_md()` exists, is migration-aware, and writes to a different path than the one every session actually uses. #936 reopened; this RCA and #1217 filed the same day.

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

This is the same defect *class* as root cause #2 already documented in #936 (`cmd_decide()` in `synlynk/team.py` resolving a migration-unaware path via `_docs_dir()` with no `_is_migrated()` check). #936's own scope section named this exact gap — "every other `_docs_dir()`-style call site needs the same audit" — but `checkpoint()`'s `todo_path` (which doesn't even call `_docs_dir()`, it's a bare literal, an even more basic miss) was never audited before #936 was closed.

## Why this went undetected for so long

- No error, warning, or doctor check exists for `todo.md` drift between the two paths. `synlynk doctor` was not extended with a check for this (per #936's own scope, item (b) "doctor/checkpoint reconciling opportunistically" was proposed but never built).
- `.synlynk/project-docs/todo.md` is gitignored, so nobody reviewing diffs or PRs ever sees it or notices it isn't changing.
- The hand-maintained `project-docs/todo.md` file *looks* functional and has been actively, successfully used as the real backlog surface for months — there's no crash, no visible failure, just silent absence of the DB-authority relationship the file's own governance strategy doc describes as already decided.
- #936 was closed without a resolving comment, and without the (a)/(b) decision it explicitly required being made — an SOP violation (Live Issues SOP requires a resolution comment stating what was fixed and criteria met) that let the sweep's incomplete state get marked done.

## Impact

- Confirmed in synlynk itself (this repo). The same defect class (migration-unaware path resolution for a project-docs constituent) was already independently confirmed in cc-videoreframing for devlogs/decisions (#936's origin report), so this is not synlynk-specific — any migrated repo using `synlynk`'s checkpoint/story workflow is affected.
- The `stories` table and its capability-scoring/routing machinery (`create_story`, capability_grants, learned scoring per PR #1030) have been operating against a `stories` table that has never received real backlog content in this repo, because nothing ever wrote real stories into it — the actual backlog has lived entirely in hand-edited markdown this whole time.
- No data loss: `project-docs/todo.md`'s content is intact and git-tracked. The impact is architectural — the state.db-as-authority model this project's own strategy doc claims is already true for todo.md has never actually been true in practice.

## Action items

1. **#1218** — Make `checkpoint()`'s `todo_path` migration-aware, matching the `devlog_path` pattern two lines below it in the same function (mechanical fix, narrow scope — the specific bug this RCA root-caused).
2. **#1219** — Resolve the (a)/(b) authority decision #936 originally called for and never made: either make `state.db` genuinely authoritative for todo.md/devlogs/decisions (backfill `project-docs/todo.md`'s real content into the `stories` table, retire the hand-edit path) or formally accept markdown as authoritative and stop stamping `.synlynk/project-docs/todo.md` as "generated, do NOT hand-edit" when it demonstrably isn't the real source. Needs a brainstorm per Brainstorm-First Policy before implementation, same as #936 originally scoped.
3. **#1220** — Add a `synlynk doctor` check that flags todo.md drift between `project-docs/todo.md` and `.synlynk/project-docs/todo.md` (or their post-(a)/(b)-decision equivalent) so this class of silent divergence surfaces automatically instead of requiring a manual audit to notice.

## Prevention

- The Live Issues SOP resolution-comment requirement should have caught #936 being closed incomplete — reinforcing that closure comments must state the specific criteria met, not just a status change, is the direct prevention here.
- The Harness Capability Reassessment Protocol's cadence-based re-check pattern is a reasonable model to extend to *documentation-authority* claims too: any doc that asserts "X is generated from Y" should have that claim spot-checked periodically, not assumed permanently true once written.
