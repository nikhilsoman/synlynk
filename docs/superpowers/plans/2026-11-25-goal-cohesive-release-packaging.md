# Goal-Cohesive Release Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the TPM sweep's flat 12-story cut with goal-cohesive packaging: whole goal per proposal, soft dual ceiling, dependency-safe phase splits, idempotent continuations, visible packaging.

**Spec:** `docs/superpowers/specs/2026-11-25-goal-cohesive-release-packaging-design.md` (approved 2026-11-25, dec-fb8ce5f7). Parent issue gh:#5525, goal-78b42384.

**Revision 2 (review round 1, Codex CHANGES_REQUESTED):** open-PR stories added as context (T2/T3); dependency rule made strict (no edge may cross a cut); operator confirmation for an oversized phase and the independent-phases escape hatch added (T1/T2/T5); join-and-leave drift and packaging metadata (count, tokens, ceilings) made explicit (T2/T4).

**Architecture:** A pure planner (`synlynk/release_packaging.py`) takes stories, dependency edges and limits, and returns either parts or an escalation. `package_next_release_proposal()` calls it instead of `LIMIT 12`. State additions: `stories.umbrella`, a `story_dependencies` table, a `release_packaging` policy block.

**Tech Stack:** Python 3 stdlib, SQLite, pytest.

## Spec-vs-codebase gaps found while planning (resolved here)

1. **No story dependency data exists.** The spec says "`blocked_by` edges", but `stories` has no such column (`depends_on` exists only on dispatch jobs). Task 1 adds a `story_dependencies(story_id, depends_on_story_id)` table. With no edges, closure is trivially satisfied.
2. **`stories.phase` is overloaded.** It defaults to `'build'` (2492 rows) and holds release labels elsewhere. The planner treats `NULL`, empty and the lifecycle defaults (`build`) as "no phase data", so a goal over the ceiling with only that data escalates, per spec 3.3.3, rather than cutting.
3. **`_cluster_candidate_stories(target_count=...)` also truncates** (silently). Goal-targeted packaging must bypass it (Task 3).
4. **Migration numbering.** m0041 is taken; use the next free number at implementation time (check `ls synlynk/migrations`).

## File Structure

- New tables (migration): `story_dependencies`, `release_split_approvals(goal_id, phase, approved_by, approved_at)`, `goal_packaging_flags(goal_id PRIMARY KEY, independent_phases INTEGER NOT NULL DEFAULT 0)`. A separate flags table is used because `goals` may be a view.
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
    conn.execute("INSERT INTO release_split_approvals (goal_id, phase) VALUES ('g','p1')")
    conn.execute("INSERT INTO goal_packaging_flags (goal_id, independent_phases) VALUES ('g',1)")
    m.MIGRATION.up(conn)  # idempotent
```

- [ ] **Step 2:** `pytest -q tests/test_release_packaging.py` -> FAIL (module missing).
- [ ] **Step 3: Implement.** Migration: `ALTER TABLE stories ADD COLUMN umbrella INTEGER NOT NULL DEFAULT 0` guarded by `PRAGMA table_info`; `CREATE TABLE IF NOT EXISTS story_dependencies (story_id TEXT NOT NULL, depends_on_story_id TEXT NOT NULL, PRIMARY KEY (story_id, depends_on_story_id))`; `CREATE TABLE IF NOT EXISTS release_split_approvals (goal_id TEXT NOT NULL, phase TEXT NOT NULL, approved_by TEXT, approved_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (goal_id, phase))`; `CREATE TABLE IF NOT EXISTS goal_packaging_flags (goal_id TEXT PRIMARY KEY, independent_phases INTEGER NOT NULL DEFAULT 0)`; backfill `UPDATE stories SET umbrella=1 WHERE gh_issue IN ('5498','5499','5500','5501','5502','5503','5504')`. `load_limits(repo_path)` = `{**DEFAULT_LIMITS, **load_policy(repo_path).get("release_packaging", {})}` with int coercion. Add the block to `DEFAULT_WORKSPACE_POLICY["defaults"]` and `.synlynk/policy.json`.
- [ ] **Step 4:** `pytest -q tests/test_release_packaging.py` -> PASS.
- [ ] **Step 5: Commit** `feat(packaging): umbrella flag, story_dependencies, release_packaging limits`.

### Task 2: Pure planner

**Files:** extend `synlynk/release_packaging.py`; test `tests/test_release_packaging.py`.

Interface (use exactly these names in later tasks):

```python
@dataclass
class PackagePlan:
    parts: list[list[str]]            # story_ids per release part, in order
    context: list[str]                # in_progress / umbrella / open-PR ids: listed, not counted
    escalation: Optional[str]         # None, or reason; parts is empty when set
    split_reasons: list[str]          # one per boundary between parts
    total_stories: int                # packageable stories across all parts
    total_tokens: int                 # sum of estimated_tokens (null -> 25,000)
    limits: dict                      # the ceilings actually used
    part_stats: list[dict]            # per part: {"stories": n, "tokens": n}

def plan_goal_release(stories, deps, limits, approved_splits=frozenset(), independent_phases=False) -> PackagePlan
```

`stories`: list of dicts `{story_id, status, umbrella, has_open_pr, phase, estimated_tokens}`; `deps`: iterable of `(story_id, depends_on_story_id)`; `approved_splits`: set of phase labels an operator approved for mid-phase splitting.

- [ ] **Step 1: Failing tests** (each a separate test function):
  1. 13 plain stories -> one part of 13; `total_stories == 13`, `limits` echoes the ceilings, `part_stats[0]["tokens"] == 13 * 25000`.
  2. Exactly 30 stories -> one part (inclusive).
  3. 12 plain + 7 (`in_progress` or `umbrella`) -> one part of 12, `context` has the 7.
  4. A story with `has_open_pr=True` goes to `context` and is excluded from both ceilings (spec 3.1); a 31-story goal where one has an open PR ships whole.
  5. 40 stories, phases `p1`(15) `p2`(15) `p3`(10) -> parts `[p1, p2]` (30) and `[p3]`; `split_reasons` names the p2->p3 boundary; no phase split mid-way.
  6. **Strict dependency rule:** any edge `(a depends on b)` where `a` and `b` land in different parts, in either direction, makes that cut invalid. With a p3->p1 edge the only valid cut is rejected and the plan escalates ("phase cut severs dependency"); `parts == []`. Test both directions (p3 depends on p1, and p1 depends on p3).
  7. 40 stories all phase `build`/`None`/`""` -> escalation "no phase data"; never `rowid` slices.
  8. Cyclic dependency within the goal -> escalation "cyclic dependency".
  9. Single phase of 35 with no approval -> escalation "phase exceeds ceiling; operator confirmation required"; with `approved_splits={"p1"}` it splits that phase into ceiling-sized parts in `story_id` order and records `split_reasons` mentioning the approval. Dependencies are still honored: an edge inside the phase forces its endpoints into the same part, and if that is impossible it escalates.
  10. `independent_phases=True` (spec 3.3.5): each phase becomes its own part with no cross-part dependency check, no continuation coupling flag (`PackagePlan.split_reasons` says "independent phases").
  11. 20 stories at 100k tokens each -> splits at a phase boundary on the token ceiling (15 per part); null tokens default to 25,000, so only the story ceiling binds.
  12. An edge pointing to a story outside the goal is ignored by the planner (surfaced separately in Task 4).
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement.** Split input into `context` (status `in_progress`, `umbrella`, or `has_open_pr`) and `packageable`. Compute count and token sum (`estimated_tokens or 25000`) and fill `total_*`, `limits`, `part_stats`. If both within limits return one part. If `independent_phases`, return one part per phase (each phase over the ceiling still follows the oversized-phase rule). Else: build the in-goal edge set; detect cycles with a DFS (escalate "cyclic dependency"); group packageable by `phase`, treating `None`, `""` and `"build"` as no phase data (escalate "no phase data"); order phases with `sorted()`; greedily fill parts with whole phases, closing a part before a phase that would breach either ceiling; a phase that alone breaches the ceiling escalates unless its label is in `approved_splits`, in which case it is split by `story_id` order while keeping edge endpoints together; after cutting, verify that **no** edge has endpoints in different parts, else escalate "phase cut severs dependency". Return parts in order with `split_reasons`.
- [ ] **Step 4:** run -> PASS.
- [ ] **Step 5: Commit** `feat(packaging): pure goal release planner`.

### Task 3: Integrate into `package_next_release_proposal`

**Files:** modify `synlynk/tpm_sweep.py` (goal branch near line 1203); test `tests/test_tpm_sweep.py`.

- [ ] **Step 1: Failing tests** (in-memory DB, patterned on `test_package_next_release_proposal_derives_version_from_active_arc`): 13-story goal returns all 13; 19-story goal with 7 `in_progress` returns 12 plus the 7 in context; the goal-less path still caps at 5; an escalating goal returns a proposal-less result carrying `escalation` text (no stories dropped).
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 2b: Additional failing tests:** a story whose branch or open PR references its story id is passed with `has_open_pr=True` and lands in context (PR lookup is a single best-effort `gh pr list --state open` call per sweep, injectable for tests; on failure the sweep adds a warning and treats all as no-open-PR); a goal flagged in `goal_packaging_flags.independent_phases` is packaged one phase per part; an operator approval row in `release_split_approvals` unlocks the oversized-phase split.
- [ ] **Step 3: Implement.** In the `resolved_target_goal` branch: drop `LIMIT 12`, select `status, umbrella, phase` too, read `story_dependencies` for those ids (guard with `sqlite_master` check for old DBs), pass `approved_splits` (from `release_split_approvals`) and `independent_phases` (from `goal_packaging_flags`), and call `plan_goal_release`. If `escalation`, return `{"escalation": reason, "goal_id": ..., "proposal": None}`-shaped result consistent with how callers treat `None` today (check the caller at line ~1303 and surface it as a sweep warning). Otherwise use `parts[0]` as candidates and **skip `_cluster_candidate_stories` truncation** for goals (call it with `target_count=len(candidates)`). Keep the orphan branch using `load_limits()["mixed_pool_cap"]`.
- [ ] **Step 4:** run `pytest -q tests/test_tpm_sweep.py tests/test_tpm_l1_advisory.py` -> PASS.
- [ ] **Step 5: Commit** `feat(sweep): package whole goal via planner, no silent LIMIT`.

### Task 4: Packaging section, continuations, drift

**Files:** modify `synlynk/tpm_sweep.py`; test `tests/test_tpm_sweep.py`.

- [ ] **Step 1: Failing tests:** **independent phases (spec 3.3.5):** with `goal_packaging_flags.independent_phases=1`, a 3-phase goal yields three separate proposals, none titled "(part N)", none with a part-1 dependency, each with its own Packaging line "independent phase <p>", and they do not count as continuations for the `max_active_proposals` exemption (normal cap applies, overflow is reported not dropped); without the flag the coupled continuation behavior is unchanged; the Packaging section asserts the exact story count, token estimate and ceilings used; proposal ticket body contains a "Packaging" section ("complete goal" or "part N of M, split at phase <p>, remainder tracked in <ticket>"); a split goal files exactly one continuation titled "<theme> (part 2)"; running the sweep twice creates no second continuation (key = goal, theme, part); continuation is created when open proposals already equal `max_active_proposals`; **drift, both directions:** a story added after the cut shows up on re-run in the right part, and a story removed from the goal or marked `done` disappears from its part ticket, with "part N of M" recomputed on every ticket and the continuation retitled if M changes; the refreshed Packaging section matches the new plan; a dependency to a story in another goal is listed under "cross-goal dependencies" and not pulled in; a goal with unpackaged stories and neither continuation nor escalation raises.
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement.** Render the Packaging section from `PackagePlan`: story count, token estimate, ceilings used (`total_stories`, `total_tokens`, `limits`, `part_stats`) and either "complete goal" or "part N of M ...". On every sweep, refresh the Packaging section and part membership of existing proposal and continuation tickets (Roadmap Studio edits to a ticket's own constituents keep precedence per `roadmap_studio.py`). Branch on `independent_phases`: when set, file each phase as its own uncoupled proposal (no part numbering, no ordering dependency); otherwise coupled continuation as follows. File the continuation in the same DB transaction as the original proposal, with a lookup keyed on `(goal_id, theme, part)` for idempotency; inherit owner and priority; record `split_reasons[0]`. Make the `max_active_proposals` check (line ~1333) skip continuation tickets. Part 2 depends on part 1 (sequential version slots).
- [ ] **Step 4:** run -> PASS.
- [ ] **Step 5: Commit** `feat(sweep): packaging section and idempotent continuations`.

### Task 5: CLI, umbrella warning, operator split approval

**Files:** modify the story CLI module; test alongside existing story CLI tests.

- [ ] **Step 1: Failing tests:** `synlynk release-split approve --goal <id> --phase <p>` writes `release_split_approvals` (pm role only, per `check_authority`) and the next sweep splits that oversized phase; `synlynk goal packaging --goal <id> --independent-phases` / `--no-independent-phases` sets the flag; `synlynk story update <id> --umbrella` sets the flag and `--no-umbrella` clears it; `synlynk story depend <id> --on <other>` inserts an edge and rejects self-edges; a goal story whose text matches "Fixes/part of #N" while unflagged yields a warning (never changes counts).
- [ ] **Step 2:** run -> FAIL.
- [ ] **Step 3: Implement** the story subcommands, the two operator commands (`release-split approve`, `goal packaging`) and the reference-parse warning, emitted in the sweep result `warnings`.
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

- **Spec coverage:** 3.1 (incl. open-PR context) -> T2+T3; 3.2 -> T1+T2; 3.3.1-3 -> T2; 3.3.4 operator confirmation -> T2+T5; 3.3.5 independent phases -> T2+T3+T5; 3.3.6-8 (incl. join and leave drift) -> T4; 3.4 metadata (count, tokens, ceilings) -> T2+T4; 3.5 -> T3; 3.6 -> T1+T5; testing list -> T2/T3/T4/T6.
- **No deviations from the approved spec.**
