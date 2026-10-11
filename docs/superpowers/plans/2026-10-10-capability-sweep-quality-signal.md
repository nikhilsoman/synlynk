# Capability Sweep Quality Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `synlynk capability sweep` from silently writing a plausible-looking `quality=5.0` when a verifier harness's output fails to parse — make the fallback loud (stderr warning with raw output) and distinguishable in the data (`quality_verified` flag), without touching the dispatch/prompt/parsing logic itself.

**Architecture:** `_verify_calibration_result` in `synlynk/capability_sweep.py` gains a `quality_verified: bool` key in its returned verdict dict, computed from whether `extract_verifier_meta` actually found a `quality` key (not from the fallback-defaulted value). Both call sites that persist a verdict (`cmd_capability_sweep_for_harness_model`'s `capability_calibration_results` INSERT, and `_run_sweep`'s `capability_ratings` INSERT) thread this flag into a new `quality_verified INTEGER` column on each table, added via an idempotent `ALTER TABLE` migration matching the existing pattern in `synlynk/db.py`. `quality_auto` is left untouched — it has unrelated, pre-existing test-pass-rate semantics (`synlynk/jobs.py:1664-1691`) and must not be repurposed.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `re` via existing `extract_verifier_meta`), pytest with `monkeypatch`/`tmp_path` fixtures (existing project conventions).

**Fixes:** gh:#2170

**Out of scope (do not implement):** the root-cause fix for *why* verifier output fails to parse (deferred — Approach B, informed by evidence this fix produces on the next real sweep run); backfilling historical rows; `synlynk capability report` (gh:#1993); gh:#2169 (worktree cleanup, unrelated).

---

## File Structure

| File | Change |
|---|---|
| `synlynk/db.py` | Add idempotent migration: `capability_calibration_results.quality_verified INTEGER`, `capability_ratings.quality_verified INTEGER` |
| `synlynk/capability_sweep.py` | Rewrite `_verify_calibration_result` to compute and return `quality_verified`; thread it into both INSERT statements |
| `tests/test_db.py` | Migration test (idempotent, columns present after upgrade) |
| `tests/test_capability_sweep.py` | Update existing verifier-fake dicts to include `quality_verified`; add new tests for the warning path and INSERT correctness |

No new files. No new dependencies.

---

### Task 1: Migrate `capability_calibration_results` and `capability_ratings` schemas

**Files:**
- Modify: `synlynk/db.py:1741-1757` (existing `capability_ratings` migration block — add alongside it)
- Modify: `synlynk/db.py` near line 1478 (end of the `capability_calibration_results` `CREATE TABLE IF NOT EXISTS` block, inside the same `conn.executescript` this table is defined in) — add a migration check immediately after that `executescript(...)` call, in the same style as the `capability_ratings` block a few hundred lines later in the same function.
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Find the existing `_get_db`/migration test setup convention first:

```bash
grep -n "def test_.*migrat\|PRAGMA table_info" tests/test_db.py | head -5
```

Add this test to `tests/test_db.py` (append at end of file):

```python
def test_quality_verified_column_added_idempotently(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    from synlynk import db

    conn1 = db._get_db()
    conn1.close()

    # Re-running DB init against the same file must not raise, and the
    # column must be present (covers both fresh-create and re-open paths).
    conn2 = db._get_db()
    rating_cols = {row[1] for row in conn2.execute("PRAGMA table_info(capability_ratings)")}
    result_cols = {row[1] for row in conn2.execute("PRAGMA table_info(capability_calibration_results)")}
    conn2.close()

    assert "quality_verified" in rating_cols
    assert "quality_verified" in result_cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_quality_verified_column_added_idempotently -v`
Expected: FAIL — `assert "quality_verified" in rating_cols` raises `AssertionError` (column doesn't exist yet).

- [ ] **Step 3: Add the migration for `capability_ratings`**

In `synlynk/db.py`, immediately after the existing block at line 1753-1757 (the `pr_number` migration, the last one in that `rating_cols` group), add:

```python
        if "quality_verified" not in rating_cols:
            try:
                conn.execute("ALTER TABLE capability_ratings ADD COLUMN quality_verified INTEGER")
            except sqlite3.OperationalError:
                pass
```

- [ ] **Step 4: Add the migration for `capability_calibration_results`**

`capability_calibration_results` has no existing migration block (it's only ever created via the static `CREATE TABLE IF NOT EXISTS` at `db.py:1469-1478` — rows already exist in deployed `state.db` files from prior sweep runs, so a `CREATE TABLE IF NOT EXISTS` edit alone will not add the column to those). Immediately after the `conn.executescript("""...""")` call that contains the `capability_calibration_results` table (the one ending at line 1480, right before `from synlynk.capability_sweep import _seed_calibration_tasks` at line 1481), add:

```python
        calib_result_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_calibration_results)")}
        if "quality_verified" not in calib_result_cols:
            try:
                conn.execute("ALTER TABLE capability_calibration_results ADD COLUMN quality_verified INTEGER")
            except sqlite3.OperationalError:
                pass
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_db.py::test_quality_verified_column_added_idempotently -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat(db): add quality_verified column to capability_ratings and capability_calibration_results

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 2: Make `_verify_calibration_result` report whether it actually parsed a verdict

Note: the spec's Testing section also calls for a regression test locking in `extract_verifier_meta`'s "returns `None`, doesn't raise" contract on malformed/missing input. That test already exists — `tests/test_capability_scoring.py::test_extract_verifier_meta_returns_none_when_absent` — so it is not duplicated here.

**Files:**
- Modify: `synlynk/capability_sweep.py:217-243` (`_verify_calibration_result`)
- Test: `tests/test_capability_sweep.py`

- [ ] **Step 1: Write the failing tests**

Add these to `tests/test_capability_sweep.py` (after the existing `test_pick_verifier_harness_is_not_executor`, before `test_calibration_pool_has_all_role_difficulty_combinations`):

```python
def test_verify_calibration_result_marks_verified_on_valid_meta(monkeypatch):
    from synlynk import capability_sweep

    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda verifier, task, **kwargs: {
            "output": "# synlynk-meta\nquality=7\ncorrect=true\n"
        },
    )

    verdict = capability_sweep._verify_calibration_result(
        "codex", "agy", "gemini-2.5-pro", "PROG", {"output": "some code"}
    )

    assert verdict == {"quality": 7.0, "correct": True, "quality_verified": True}


def test_verify_calibration_result_falls_back_and_warns_on_unparseable_output(monkeypatch, capsys):
    from synlynk import capability_sweep

    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda verifier, task, **kwargs: {"output": "I reviewed it, looks fine."},
    )

    verdict = capability_sweep._verify_calibration_result(
        "codex", "agy", "gemini-2.5-pro", "PROG", {"output": "some code"}
    )

    assert verdict == {"quality": 5.0, "correct": True, "quality_verified": False}
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "codex" in captured.err
    assert "agy" in captured.err
    assert "I reviewed it, looks fine." in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capability_sweep.py::test_verify_calibration_result_marks_verified_on_valid_meta tests/test_capability_sweep.py::test_verify_calibration_result_falls_back_and_warns_on_unparseable_output -v`
Expected: FAIL — `assert verdict == {...}` fails because the current return dict has no `quality_verified` key, and no warning is printed.

- [ ] **Step 3: Rewrite `_verify_calibration_result`**

Replace `synlynk/capability_sweep.py:217-243` (the full existing function body) with:

```python
def _verify_calibration_result(
    verifier_harness: str,
    executor_harness: str,
    model: str,
    skill: str,
    executor_output: dict,
) -> dict:
    """Ask a different harness to score the executor output and parse its verdict.

    `quality_verified` distinguishes a real parsed verdict from the 5.0/True
    fallback (gh:#2170) — callers must not treat a fallback as a real score.
    """
    label = SFIA_CODES.get(skill, {}).get("label", skill)
    verify_task = (
        f"Review this {label} calibration task output from another harness and score it "
        "0-10 for quality.\n"
        "Respond with a line '# synlynk-meta' followed by 'quality=<N>' "
        "and 'correct=<true|false>'.\n\n"
        f"Executor harness: {executor_harness}\n"
        f"Executor model: {model}\n"
        f"Verifier harness: {verifier_harness}\n\n"
        f"Output to review:\n{executor_output.get('output', '')}"
    )
    result = _dispatch_calibration_task(verifier_harness, verify_task)
    from synlynk.costs import extract_verifier_meta

    raw_output = result.get("output", "")
    meta = extract_verifier_meta(raw_output) or {}
    quality_verified = "quality" in meta

    if not quality_verified:
        print(
            f"  [sweep] WARNING: verifier {verifier_harness} output for "
            f"{executor_harness}/{model} ({skill}) had no parseable "
            f"'# synlynk-meta' quality block — falling back, marking unverified.\n"
            f"  --- raw verifier output (first 2000 chars) ---\n"
            f"{raw_output[:2000]}\n"
            f"  --- end raw verifier output ---",
            file=sys.stderr,
        )

    return {
        "quality": float(meta.get("quality", 5.0)),
        "correct": bool(meta.get("correct", True)),
        "quality_verified": quality_verified,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_capability_sweep.py::test_verify_calibration_result_marks_verified_on_valid_meta tests/test_capability_sweep.py::test_verify_calibration_result_falls_back_and_warns_on_unparseable_output -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_sweep.py tests/test_capability_sweep.py
git commit -m "fix(capability-sweep): distinguish parsed verifier verdicts from the 5.0 fallback

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 3: Update existing verifier-mocking tests to return `quality_verified`

The three existing tests that monkeypatch `_verify_calibration_result` directly (bypassing the real function from Task 2) return verdict dicts without `quality_verified`. Once Task 4 reads `verdict["quality_verified"]` with no default, these fakes must supply it — update them now so Task 4's step 2 (run-tests-to-verify-fail) isn't muddied by unrelated breakage in tests that aren't the ones under test.

**Files:**
- Modify: `tests/test_capability_sweep.py:122-124`, `:180`, `:209`

- [ ] **Step 1: Update `test_run_sweep_writes_baseline_seed_rows_with_independent_verifier`'s fake**

Change line 122-124 from:

```python
    def fake_verify(verifier_agent, executor_agent, model, skill, executor_output):
        assert verifier_agent != executor_agent
        return {"quality": 8.0, "correct": True}
```

to:

```python
    def fake_verify(verifier_agent, executor_agent, model, skill, executor_output):
        assert verifier_agent != executor_agent
        return {"quality": 8.0, "correct": True, "quality_verified": True}
```

- [ ] **Step 2: Update `test_sweep_for_harness_model_writes_calibration_result`'s fake**

Change line 180 from:

```python
        lambda verifier_agent, executor_agent, model, skill, executor_output: {"quality": 8.0, "correct": True},
```

to:

```python
        lambda verifier_agent, executor_agent, model, skill, executor_output: {
            "quality": 8.0, "correct": True, "quality_verified": True,
        },
```

- [ ] **Step 3: Update `test_sweep_for_harness_model_dispatches_selected_model`'s fake**

Change line 209 from:

```python
        lambda *args: {"quality": 8.0, "correct": True},
```

to:

```python
        lambda *args: {"quality": 8.0, "correct": True, "quality_verified": True},
```

- [ ] **Step 4: Run the three updated tests to confirm they still pass as-is (pre-Task-4 baseline)**

Run: `pytest tests/test_capability_sweep.py -v -k "run_sweep_writes_baseline_seed or writes_calibration_result or dispatches_selected_model"`
Expected: PASS (these tests don't yet assert on `quality_verified` being persisted — that's Task 4)

- [ ] **Step 5: Commit**

```bash
git add tests/test_capability_sweep.py
git commit -m "test(capability-sweep): add quality_verified to existing verifier-mock fixtures

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 4: Thread `quality_verified` into both INSERT call sites

**Files:**
- Modify: `synlynk/capability_sweep.py:176-190` (`cmd_capability_sweep_for_harness_model`'s `capability_calibration_results` INSERT)
- Modify: `synlynk/capability_sweep.py:286-306` (`_run_sweep`'s `capability_ratings` INSERT loop)
- Test: `tests/test_capability_sweep.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_capability_sweep.py` (after the Task 3 edits, before `test_pick_verifier_harness_is_not_executor`... actually place after `test_sweep_for_harness_model_dispatches_selected_model`, i.e. near the end of the file before `test_dispatch_calibration_task_passes_model_to_dispatch_agent`):

```python
def test_sweep_for_harness_model_persists_quality_verified_false_on_fallback(tmp_path, monkeypatch):
    from synlynk import db, capability_sweep

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    monkeypatch.setattr(capability_sweep, "_get_db", lambda: conn)
    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda agent, task, **kwargs: {"output": "example output"},
    )
    monkeypatch.setattr(
        capability_sweep, "_verify_calibration_result",
        lambda verifier_agent, executor_agent, model, skill, executor_output: {
            "quality": 5.0, "correct": True, "quality_verified": False,
        },
    )
    monkeypatch.setattr(capability_sweep, "_pick_verifier_agent", lambda executor, available: "codex")

    capability_sweep.cmd_capability_sweep_for_harness_model("agy", "gemini-3-pro")

    rows = conn.execute(
        "SELECT quality_verified FROM capability_calibration_results WHERE harness_name='agy'"
    ).fetchall()
    assert len(rows) >= 1
    assert all(r[0] == 0 for r in rows)


def test_run_sweep_persists_quality_verified_true_on_real_verdict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _run_sweep

    monkeypatch.setattr(
        "synlynk.capability_sweep._dispatch_calibration_task",
        lambda agent, task, **kwargs: {"exit_code": 0, "output": "task complete", "agent": agent},
    )
    monkeypatch.setattr(
        "synlynk.capability_sweep._verify_calibration_result",
        lambda verifier_agent, executor_agent, model, skill, executor_output: {
            "quality": 8.0, "correct": True, "quality_verified": True,
        },
    )

    discovered = {"codex": ["gpt-5-codex"], "agy": ["gemini-2.5-pro"]}
    _run_sweep(discovered, ["PROG"])

    conn = sl._get_db()
    rows = conn.execute(
        "SELECT quality_verified FROM capability_ratings WHERE signal_source='baseline_seed'"
    ).fetchall()
    conn.close()

    assert len(rows) >= 2
    assert all(r[0] == 1 for r in rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capability_sweep.py::test_sweep_for_harness_model_persists_quality_verified_false_on_fallback tests/test_capability_sweep.py::test_run_sweep_persists_quality_verified_true_on_real_verdict -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: quality_verified` is NOT expected (Task 1 added the column); instead expect the `SELECT quality_verified` to return `NULL`/`None` rows rather than `0`/`1`, since nothing writes the column yet. Confirm the actual failure is an assertion mismatch (`None != 0` / `None != 1`), not a missing-column error — if it's a missing-column error, Task 1 wasn't applied correctly in this branch.

- [ ] **Step 3: Update the `capability_calibration_results` INSERT**

In `synlynk/capability_sweep.py`, replace the block at lines 176-190:

```python
        conn.execute(
            "INSERT INTO capability_calibration_results "
            "(result_id, harness_name, model_id, task_id, score, cost_usd, verified_by, run_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                harness_name,
                model_id,
                task_id,
                verdict["quality"] / 10.0,
                cost_usd,
                verifier_agent,
                now,
            ),
        )
```

with:

```python
        conn.execute(
            "INSERT INTO capability_calibration_results "
            "(result_id, harness_name, model_id, task_id, score, cost_usd, verified_by, run_at, quality_verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                harness_name,
                model_id,
                task_id,
                verdict["quality"] / 10.0,
                cost_usd,
                verifier_agent,
                now,
                1 if verdict["quality_verified"] else 0,
            ),
        )
```

- [ ] **Step 4: Update the `capability_ratings` INSERT in `_run_sweep`**

Replace the block at lines 286-306:

```python
                for _ in range(phantom_sample_count):
                    conn.execute(
                        """INSERT INTO capability_ratings
                           (story_id, agent, model_version, discipline, org_domain, industry, phase,
                            signal_source, quality, quality_auto, verifier_agent, correct)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "__baseline_seed__",
                            harness,
                            model,
                            discipline_value,
                            "platform",
                            "unknown",
                            "build",
                            "baseline_seed",
                            verdict["quality"],
                            verdict["quality"],
                            verifier_harness,
                            1 if verdict.get("correct", True) else 0,
                        ),
                    )
```

with:

```python
                for _ in range(phantom_sample_count):
                    conn.execute(
                        """INSERT INTO capability_ratings
                           (story_id, agent, model_version, discipline, org_domain, industry, phase,
                            signal_source, quality, quality_auto, verifier_agent, correct, quality_verified)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "__baseline_seed__",
                            harness,
                            model,
                            discipline_value,
                            "platform",
                            "unknown",
                            "build",
                            "baseline_seed",
                            verdict["quality"],
                            verdict["quality"],
                            verifier_harness,
                            1 if verdict.get("correct", True) else 0,
                            1 if verdict.get("quality_verified", True) else 0,
                        ),
                    )
```

Note: `verdict.get("quality_verified", True)` (not a bare `verdict["quality_verified"]`) here only — this INSERT is also reached by any caller that hasn't been updated to the new verdict shape; defaulting to `True` preserves prior behavior for such a caller rather than raising `KeyError`. The real `_verify_calibration_result` (Task 2) always includes the key, so this default is a safety net, not the expected path.

`quality_auto` is deliberately left as `verdict["quality"]` on both lines — unchanged. Per the design spec, `quality_auto` has distinct pre-existing test-pass-rate semantics (`synlynk/jobs.py:1664-1691`) unrelated to this fix; do not touch it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_capability_sweep.py::test_sweep_for_harness_model_persists_quality_verified_false_on_fallback tests/test_capability_sweep.py::test_run_sweep_persists_quality_verified_true_on_real_verdict -v`
Expected: PASS

- [ ] **Step 6: Run the full capability sweep test file to confirm no regressions**

Run: `pytest tests/test_capability_sweep.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/capability_sweep.py tests/test_capability_sweep.py
git commit -m "fix(capability-sweep): persist quality_verified on both calibration write paths

Fixes gh:#2170

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 5: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass (same pass/fail/skip counts as the pre-change baseline, plus the new tests from Tasks 1, 2, and 4).

- [ ] **Step 2: If anything outside `test_capability_sweep.py` / `test_db.py` fails**

Check whether it references `capability_ratings` or `capability_calibration_results` column lists (e.g. a `SELECT *` or a hardcoded column-count assertion) — the new `quality_verified` column is additive and nullable, so a failure here indicates a test with a brittle column assumption, not a logic error in this fix. Fix the test's assumption (e.g. an explicit column list) rather than the migration.

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "test: fix brittle column-count assumptions surfaced by quality_verified migration

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

(Skip this task's commit if Step 1 passed clean with no fixes needed.)

---

## Execution Handoff

**Per this project's Default Agent Role policy (CLAUDE.md, interim default under the 2026-10-04 Empirical Capability Assessment reassessment): this implementation must be dispatched via `synlynk dispatch` to Agy, Codex, or Grok — not implemented directly by Claude in this session.**

This is a small, backend-only, single-file-plus-migration change (pure stdlib/sqlite3, no new dependencies) with tight internal coupling: the `capability_sweep.py` verdict-shape change (Task 2) and the `db.py` column migration (Task 1) must land together for Task 4's INSERTs to work, and Task 4 itself touches both call sites in one coherent change. **Dispatch all 5 tasks as a single implementer job, not split across multiple dispatches.**

Plan complete and saved to `docs/superpowers/plans/2026-10-10-capability-sweep-quality-signal.md`.

Recommended dispatch command (adjust harness per current routing — Codex or Grok preferred per the GitHub-write routing note in CLAUDE.md if the job needs to open a PR itself; Agy as fallback):

```bash
synlynk dispatch --as-agent dev --story <story-id-or-create-one-linked-to-gh:2170> \
  --task "Implement the plan at docs/superpowers/plans/2026-10-10-capability-sweep-quality-signal.md in full, task by task, with tests passing at each step. Fixes gh:#2170." \
  codex
```

(Fill in `--story` with a real GOVERNS-linked story ID per the Hardened PR Review Policy's 100% GOVERNS adherence rule — do not dispatch without one.)

After dispatch, standard PR Review Discipline applies: a non-authoring, cross-harness+model reviewer runs `synlynk pr check`, and the reviewer's own dispatched job performs the merge per CLAUDE.md's PR Review Discipline section.
