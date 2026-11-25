# Goal-Cohesive Release Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the TPM sweep's flat 12-story cut with goal-cohesive packaging: whole goal per proposal, soft dual ceiling, dependency-safe phase splits, idempotent continuations, visible packaging.

**Spec:** `docs/superpowers/specs/2026-11-25-goal-cohesive-release-packaging-design.md` (approved 2026-11-25, dec-fb8ce5f7). Parent issue gh:#5525, goal-78b42384.

**Architecture:** A pure planner (`synlynk/release_packaging.py`) takes stories, dependency edges and limits, and returns either parts or an escalation. `package_next_release_proposal()` calls it instead of `LIMIT 12`. State additions: `stories.umbrella`, a `story_dependencies` table, a `release_packaging` policy block.

**Tech Stack:** Python 3 stdlib, SQLite, pytest.

## Spec-vs-codebase gaps found while planning (resolved here)

1. **No story dependency data exists.** The spec says "`blocked_by` edges", but `stories` has no such column (`depends_on` exists only on dispatch jobs). Task 1 adds a `story_dependencies(story_id, depends_on_story_id)` table. With no edges, closure is trivially satisfied.
2. **`stories.phase` is overloaded.** It defaults to `'build'` (2492 rows) and holds release labels elsewhere. The planner treats `NULL`, empty and the lifecycle defaults (`build`) as "no phase data", so a goal over the ceiling with only that data escalates, per spec 3.3.3, rather than cutting.
3. **`_cluster_candidate_stories(target_count=...)` also truncates** (silently). Goal-targeted packaging must bypass it (Task 3).
4. **Migration numbering.** m0041 is taken; use the next free number at implementation time (check `ls synlynk/migrations`).

## File Structure

- Create `synlynk/release_packaging.py`: pure planner and limits loader. No DB access except through arguments.
- Create `synlynk/migrations/m00NN_release_packaging.py`: `stories.umbrella`, `story_dependencies`, LIVE-35 backfill.
- Modify `synlynk/tpm_sweep.py` (`package_next_release_proposal`, line ~1123): use planner, remove `LIMIT 12`, packaging section, continuation filing.
- Modify `synlynk/policy.py` `DEFAULT_WORKSPACE_POLICY["defaults"]`: add `release_packaging`.
- Modify `.synlynk/policy.json`: add `release_packaging` block.
- Modify the story CLI: `story update --umbrella/--no-umbrella`, `story depend <id> --on <id>`.
- Tests: `tests/test_release_packaging.py` (planner), additions to `tests/test_tpm_sweep.py`.

---

### Task 1: Schema, policy block, limits loader

**Files:** create migration; modify `synlynk/policy.py`, `.synlynk/policy.json`; create `synlynk/release_packaging.py` (limits only); test `tests/test_release_packaging.py`.

- [ ] **Step 1: Failing tests**

```python
import sqlite3
from synlynk.release_packaging import load_limits, DEFAULT_LIMITS

def test_default_limits():
    assert DEFAULT_LIMITS == {"goal_story_ceiling": 30, "goal_token_ceiling": 1_500_000, "mixed_pool_cap": 5}

def test_load_limits_overrides(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text(
        '{"overrides": {"release_packaging": {"goal_story_ceiling": 10}}}')
    lim = load_limits(str(tmp_path))
    assert lim["goal_story_ceiling"] == 10 and lim["goal_token_ceiling"] == 1_500_000

def test_migration_adds_umbrella_and_deps():
    from synlynk.migrations import m00NN_release_packaging as m   # adjust to real module name
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE stories (story_id TEXT UNIQUE, gh_issue TEXT, status TEXT)")
    m.MIGRATION.up(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(stories)")}
    assert "umbrella" in cols
    conn.execute("INSERT INTO story_dependencies VALUES ('a','b')")
    m.MIGRATION.up(conn)  # idempotent
```

- [ ] **Step 2:** `pytest -q tests/test_release_packaging.py` -> FAIL (module missing).
- [ ] **Step 3: Implement.** Migration: `ALTER TABLE stories ADD COLUMN umbrella INTEGER NOT NULL DEFAULT 0` guarded by `PRAGMA table_info`; `CREATE TABLE IF NOT EXISTS story_dependencies (story_id TEXT NOT NULL, depends_on_story_id TEXT NOT NULL, PRIMARY KEY (story_id, depends_on_story_id))`; backfill `UPDATE stories SET umbrella=1 WHERE gh_issue IN ('5498','5499','5500','5501','5502','5503','5504')`. `load_limits(repo_path)` = `{**DEFAULT_LIMITS, **load_policy(repo_path).get("release_packaging", {})}` with int coercion. Add the block to `DEFAULT_WORKSPACE_POLICY["defaults"]` and `.synlynk/policy.json`.
- [ ] **Step 4:** `pytest -q tests/test_release_packaging.py` -> PASS.
- [ ] **Step 5: Commit** `feat(packaging): umbrella flag, story_dependencies, release_packaging limits`.

### Task 2: Pure planner

**Files:** extend `synlynk/release_packaging.py`; test `tests/test_release_packaging.py`.

Interface (use exactly these names in later tasks):

```python
@dataclass
class PackagePlan:
    parts: list[list[str]]            # story_ids per release part, in order
    context: list[str]                # in_progress/umbrella ids, listed not counted
    escalation: Optional[str]         # None, or reason; parts is empty when set
    split_reasons: list[str]          # one per boundary between parts

def plan_goal_release(stories, deps, limits) -> PackagePlan
```

`stories`: list of dicts `{story_id, status, umbrella, phase, estimated_tokens}`; `deps`: iterable of `(story_id, depends_on_story_id)`; `limits`: dict from `load_limits`.

- [ ] **Step 1: Failing tests** (each a separate test function):
  1. 13 plain stories -> one part of 13.
  2. Exactly 30 stories -> one part (inclusive).
  3. 12 plain + 7 (`in_progress` or `umbrella`) -> one part of 12, `context` has the 7.
  4. 40 stories, phases `p1`(15) `p2`(15) `p3`(10) -> parts `[p1, p2]` (30) and `[p3]`; `split_reasons` names phase `p2`->`p3`; no story split mid-phase.
  5. Same but a dependency edge from a `p3` story to a `p1`... crossing edge (earlier part depends on later) -> escalation mentions dependency; `parts == []`.
  6. 40 stories all phase `build`/`None` -> escalation "no phase data"; never `rowid` slices.
  7. Cyclic dependency within the goal -> escalation "cyclic".
  8. Single phase of 35 -> escalation "phase exceeds ceiling".
  9. 20 stories at 100k tokens each -> splits on token ceiling (1.5M => 15 per part) at a phase boundary; with null tokens defaulting to 25,000 only the story ceiling binds.
  10. Edge pointing to a story outside the goal is ignored by the planner (surfaced separately in Task 4).
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement.** Algorithm: split input into `context` (status `in_progress` or `umbrella`) and `packageable`. Compute count and token sum (`estimated_tokens or 25000`); if both within limits return one part. Else: build the in-goal edge set; detect cycles with a DFS (escalate "cyclic dependency"); group packageable by `phase`, treating `None`, `""` and `"build"` as no phase data (escalate "no phase data" if any packageable story lacks usable phase); order phases ascending by `sorted()` of the labels; greedily fill parts with whole phases, closing a part before a phase that would breach either ceiling; a single phase breaching the ceiling alone escalates; after cutting, verify no edge `(a depends on b)` has `part(b) > part(a)`; if violated escalate "phase cut severs dependency". Return parts in order with `split_reasons`.
- [ ] **Step 4:** run -> PASS.
- [ ] **Step 5: Commit** `feat(packaging): pure goal release planner`.

### Task 3: Integrate into `package_next_release_proposal`

**Files:** modify `synlynk/tpm_sweep.py` (goal branch near line 1203); test `tests/test_tpm_sweep.py`.

- [ ] **Step 1: Failing tests** (in-memory DB, patterned on `test_package_next_release_proposal_derives_version_from_active_arc`): 13-story goal returns all 13; 19-story goal with 7 `in_progress` returns 12 plus the 7 in context; the goal-less path still caps at 5; an escalating goal returns a proposal-less result carrying `escalation` text (no stories dropped).
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement.** In the `resolved_target_goal` branch: drop `LIMIT 12`, select `status, umbrella, phase` too, read `story_dependencies` for those ids (guard with `sqlite_master` check for old DBs), call `plan_goal_release`. If `escalation`, return `{"escalation": reason, "goal_id": ..., "proposal": None}`-shaped result consistent with how callers treat `None` today (check the caller at line ~1303 and surface it as a sweep warning). Otherwise use `parts[0]` as candidates and **skip `_cluster_candidate_stories` truncation** for goals (call it with `target_count=len(candidates)`). Keep the orphan branch using `load_limits()["mixed_pool_cap"]`.
- [ ] **Step 4:** run `pytest -q tests/test_tpm_sweep.py tests/test_tpm_l1_advisory.py` -> PASS.
- [ ] **Step 5: Commit** `feat(sweep): package whole goal via planner, no silent LIMIT`.

### Task 4: Packaging section, continuations, drift

**Files:** modify `synlynk/tpm_sweep.py`; test `tests/test_tpm_sweep.py`.

- [ ] **Step 1: Failing tests:** proposal ticket body contains a "Packaging" section ("complete goal" or "part N of M, split at phase <p>, remainder tracked in <ticket>"); a split goal files exactly one continuation titled "<theme> (part 2)"; running the sweep twice creates no second continuation (key = goal, theme, part); continuation is created when open proposals already equal `max_active_proposals`; a story added after cut appears in the next part's count on re-run; a dependency to a story in another goal is listed under "cross-goal dependencies" and not pulled in; a goal with unpackaged stories and neither continuation nor escalation raises.
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement.** Render the Packaging section from `PackagePlan`. File the continuation in the same DB transaction as the original proposal, with a lookup keyed on `(goal_id, theme, part)` for idempotency; inherit owner and priority; record `split_reasons[0]`. Make the `max_active_proposals` check (line ~1333) skip continuation tickets. Part 2 depends on part 1 (sequential version slots).
- [ ] **Step 4:** run -> PASS.
- [ ] **Step 5: Commit** `feat(sweep): packaging section and idempotent continuations`.

### Task 5: CLI and umbrella warning

**Files:** modify the story CLI module; test alongside existing story CLI tests.

- [ ] **Step 1: Failing tests:** `synlynk story update <id> --umbrella` sets the flag and `--no-umbrella` clears it; `synlynk story depend <id> --on <other>` inserts an edge and rejects self-edges; a goal story whose text matches "Fixes/part of #N" while unflagged yields a warning (never changes counts).
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement** the two subcommands and the reference-parse warning, emitted in the sweep result `warnings`.
- [ ] **Step 4:** run -> PASS.
- [ ] **Step 5: Commit** `feat(story): umbrella and dependency CLI`.

### Task 6: LIVE-35 regression and rollout verification

**Files:** `tests/test_tpm_sweep.py`; run against the real DB read-only.

- [ ] **Step 1:** Add the fixture test: 12 task stories + 7 umbrella/`in_progress` parents under one goal -> one proposal of 12 with 7 context entries and a "complete goal" packaging line.
- [ ] **Step 2:** `pytest -q` (full suite, quiet, per the dispatch cost rule) -> PASS.
- [ ] **Step 3:** Dry-run the packager for goal-62f693b8 against a copy of the state DB; confirm one proposal covering all non-umbrella plan stories and that no story is omitted.
- [ ] **Step 4:** Note in the PR that rollout needs no flag (spec section 6), and that no manual doc edits are needed (roadmap/todo/costs are not git-tracked).
- [ ] **Step 5: Commit** `test(sweep): LIVE-35 packaging regression`.

## Self-review

- **Spec coverage:** 3.1 -> T3; 3.2 -> T1+T2; 3.3.1-5 -> T2; 3.3.6-8 -> T4; 3.4 -> T4; 3.5 -> T3; 3.6 -> T1+T5; testing list -> T2/T3/T4/T6.
- **Deviation recorded:** spec 3.3.5 (independently releasable phases escape hatch) is not implemented here; it needs goal metadata that does not exist yet. Track as a follow-up if wanted.
