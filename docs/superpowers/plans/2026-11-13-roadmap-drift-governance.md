# Roadmap Drift Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect and gate on drift between `decisions`, `goals`, and `roadmap_arcs` — a decision linked to a goal that was never placed on the roadmap, or a roadmap arc that claims a goal with no backing approved decision — reusing the existing `require_linked_goal_mode` observe/enforce toggle, surfaced via `synlynk doctor`, `synlynk roadmap check`, and `synlynk pr check`.

**Architecture:** A new pure-function module (`synlynk/roadmap_drift.py`) computes drift findings and a pass/warn classification from a DB connection, with zero DB-write side effects (remediation is manual triage, not auto-repair, since no automatic fix can safely infer which goal a decision *should* have pointed at). Three thin call sites wire it in: a `doctor.py` health check (informational), a `pr_check.py` gate function (triggered only when a PR touches `project-docs/decisions/`), and `cmd_pr_check()`'s existing gate-chaining sequence in `db.py` (blocking, governed by the same `require_linked_goal_mode` policy key the GOVERNS-linkage gate already uses). A new `synlynk roadmap check` CLI subcommand exposes the same findings for ad hoc inspection outside a PR.

**Tech Stack:** Python 3 stdlib only (`sqlite3` via `synlynk._get_db()`), pytest, argparse (existing `synlynk/cli.py` subparser pattern).

**Scope note:** This plan implements spec Section 2 ("Roadmap Drift Gate") and the Remediation section of `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md`, plus a small Section 4 process-doc update. Spec Section 1 (Intent Capture Layer), the full Section 3 Orphan Sweep (docgraph/AST-based), and Sections 5-6 (Semantic Laws seed doc, Uber-Roadmap reorg) are deliberately out of scope — each needs its own grounded plan (see "Deferred" in the spec).

---

## File Structure

- **Create:** `synlynk/roadmap_drift.py` — `find_roadmap_drift(conn)` (returns findings) and `classify_roadmap_drift(findings)` (returns `(status, detail)` tuple, mirroring `policy_gates.classify_governs_violations`).
- **Create:** `tests/test_roadmap_drift.py` — unit tests for `find_roadmap_drift()` and `classify_roadmap_drift()`, covering all three finding types.
- **Modify:** `synlynk/doctor.py` — add `_hc_roadmap_decision_drift() -> HealthCheck` (after `repair_roadmap_merge_parity()`, around line 517) and register it in `HEALTH_CHECKS` (after `_hc_roadmap_merge_parity,`, around line 1556).
- **Modify:** `tests/test_doctor_roadmap_drift.py` — add `test_doctor_warns_on_roadmap_decision_drift`.
- **Modify:** `synlynk/pr_check.py` — add `check_pr_roadmap_gate(conn, repo_root=".", pr_number=None, changed_files=None) -> dict`, mirroring `check_pr_spec_gate`'s filter-then-delegate shape.
- **Create:** `tests/test_pr_check_roadmap_gate.py` — unit tests for `check_pr_roadmap_gate()`.
- **Modify:** `synlynk/db.py` — wire the gate into `cmd_pr_check()` (after the existing GOVERNS-linkage block, around line 5728) and add `cmd_roadmap_check() -> int` (after `cmd_roadmap_update()`, around line 4532).
- **Modify:** `tests/test_pr_check.py` — add a test for the new gate's wiring into `cmd_pr_check()`.
- **Modify:** `synlynk/cli.py` — add `roadmap check` subparser (after `roadmap_render_parser`, around line 1809), add `cmd_roadmap_check` to the `from synlynk.db import (...)` block (around line 2534-2535), add the dispatch branch (after the `render` branch, around line 3418).
- **Create:** `tests/test_cli_roadmap_check.py` — smoke test that the CLI subcommand parses and calls through.
- **Modify:** `CLAUDE.md` (this worktree's copy) — add a short note under an appropriate existing section pointing at `synlynk roadmap check` / `synlynk doctor` for drift, and the Remediation findings below.

---

### Task 1: `find_roadmap_drift()` and `classify_roadmap_drift()`

**Files:**
- Create: `synlynk/roadmap_drift.py`
- Test: `tests/test_roadmap_drift.py`

**Finding shape:** each finding is a `dict` with keys `kind` (one of `"DECISION_GOAL_UNPLACED"`, `"ARC_NO_DECISION"`, `"DECISION_GOAL_MISSING"`), `detail` (a one-line human-readable string), and the relevant IDs (`decision_id`/`goal_id` or `arc_version`/`goal_id`).

- [ ] **Step 1: Write the failing test for `DECISION_GOAL_UNPLACED`**

```python
# tests/test_roadmap_drift.py
from __future__ import annotations


def _fresh_db(tmp_path, monkeypatch):
    import synlynk
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    return synlynk._get_db()


def test_finds_decision_linked_to_unplaced_goal(tmp_path, monkeypatch):
    from synlynk.roadmap_drift import find_roadmap_drift

    conn = _fresh_db(tmp_path, monkeypatch)
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-unplaced-1', 'ship X', 'X ships', 'unplaced')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-test-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-unplaced-1')"
        )
        conn.commit()

        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    matches = [f for f in findings if f["kind"] == "DECISION_GOAL_UNPLACED"]
    assert len(matches) == 1
    assert matches[0]["decision_id"] == "dec-test-1"
    assert matches[0]["goal_id"] == "goal-unplaced-1"
    assert "goal-unplaced-1" in matches[0]["detail"]
    assert "unplaced" in matches[0]["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roadmap_drift.py::test_finds_decision_linked_to_unplaced_goal -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.roadmap_drift'`

- [ ] **Step 3: Write the module with the `DECISION_GOAL_UNPLACED` check**

```python
# synlynk/roadmap_drift.py
"""Detect drift between decisions, goals, and roadmap arcs (gh:#5020-adjacent)."""

from __future__ import annotations

from typing import Any


def find_roadmap_drift(conn) -> list[dict[str, Any]]:
    """Return a list of drift findings across decisions/goals/roadmap_arcs.

    Three finding kinds:
    - DECISION_GOAL_UNPLACED: an approved decision links a goal whose
      placement_status is not 'placed' (the goal was never actually put
      on the roadmap).
    - ARC_NO_DECISION: a roadmap arc claims a goal_id with no backing
      approved decision (the arc's authority is unverifiable).
    - DECISION_GOAL_MISSING: a decision's goal_id does not resolve in
      goals at all. The decisions.goal_id foreign key normally prevents
      this, but it is checked defensively in case FK enforcement was
      bypassed for a sentinel write (see synlynk/db.py's
      _record_goal_link_status).
    """
    findings: list[dict[str, Any]] = []

    unplaced_rows = conn.execute(
        "SELECT d.decision_id, d.goal_id, g.placement_status "
        "FROM decisions d JOIN goals g ON g.goal_id = d.goal_id "
        "WHERE d.goal_id IS NOT NULL AND g.placement_status != 'placed'"
    ).fetchall()
    for decision_id, goal_id, placement_status in unplaced_rows:
        findings.append({
            "kind": "DECISION_GOAL_UNPLACED",
            "decision_id": decision_id,
            "goal_id": goal_id,
            "detail": (
                f"decision {decision_id} links goal {goal_id}, but that goal's "
                f"placement_status is {placement_status!r} (not 'placed')"
            ),
        })

    no_decision_rows = conn.execute(
        "SELECT ra.version, ra.goal_id FROM roadmap_arcs ra "
        "WHERE ra.goal_id IS NOT NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM decisions d WHERE d.goal_id = ra.goal_id AND d.status = 'approved'"
        ")"
    ).fetchall()
    for arc_version, goal_id in no_decision_rows:
        findings.append({
            "kind": "ARC_NO_DECISION",
            "arc_version": arc_version,
            "goal_id": goal_id,
            "detail": (
                f"roadmap arc {arc_version} claims goal {goal_id}, but no approved "
                f"decision links that goal"
            ),
        })

    missing_rows = conn.execute(
        "SELECT d.decision_id, d.goal_id FROM decisions d "
        "WHERE d.goal_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM goals g WHERE g.goal_id = d.goal_id)"
    ).fetchall()
    for decision_id, goal_id in missing_rows:
        findings.append({
            "kind": "DECISION_GOAL_MISSING",
            "decision_id": decision_id,
            "goal_id": goal_id,
            "detail": (
                f"decision {decision_id} references goal_id {goal_id}, which does "
                f"not exist in goals"
            ),
        })

    return findings


def classify_roadmap_drift(findings: list[dict[str, Any]]) -> tuple[str, str]:
    """Mirror policy_gates.classify_governs_violations's (status, detail) shape."""
    if not findings:
        return "pass", "no roadmap drift detected"
    summary = "; ".join(f["detail"] for f in findings)
    return "warn", summary
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_roadmap_drift.py::test_finds_decision_linked_to_unplaced_goal -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for `ARC_NO_DECISION`**

```python
# tests/test_roadmap_drift.py (append)


def test_finds_arc_with_no_backing_decision(tmp_path, monkeypatch):
    from synlynk.roadmap_drift import find_roadmap_drift

    conn = _fresh_db(tmp_path, monkeypatch)
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-no-dec-1', 'ship Y', 'Y ships', 'placed')"
        )
        conn.execute(
            "INSERT INTO roadmap_arcs (version, goal_id) VALUES ('v9.9.0', 'goal-no-dec-1')"
        )
        conn.commit()

        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    matches = [f for f in findings if f["kind"] == "ARC_NO_DECISION"]
    assert len(matches) == 1
    assert matches[0]["arc_version"] == "v9.9.0"
    assert matches[0]["goal_id"] == "goal-no-dec-1"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_roadmap_drift.py::test_finds_arc_with_no_backing_decision -v`
Expected: FAIL — `AssertionError: assert 1 == 1` would actually pass already since Step 3's implementation covers both checks; run it anyway to confirm. If it unexpectedly passes, that confirms Step 3 already covers this path (expected — both checks were implemented together in Step 3 because they share the same module). Proceed to Step 7 regardless.

- [ ] **Step 7: Confirm test passes**

Run: `pytest tests/test_roadmap_drift.py -v`
Expected: PASS (both tests)

- [ ] **Step 8: Write the failing test for `DECISION_GOAL_MISSING` (the FK-bypass case)**

This finding type requires inserting a decision with a dangling `goal_id` — but `synlynk._get_db()` enables `PRAGMA foreign_keys=ON` and `decisions.goal_id REFERENCES goals(goal_id)`, so a normal insert through that connection raises `sqlite3.IntegrityError`. Bypass FK enforcement with a separate raw connection to the same file, mirroring the existing `synlynk/db.py` `_record_goal_link_status()` precedent.

```python
# tests/test_roadmap_drift.py (append)


def test_finds_decision_with_dangling_goal_id(tmp_path, monkeypatch):
    import sqlite3
    import synlynk
    from synlynk.roadmap_drift import find_roadmap_drift

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    # Create schema via the normal path first.
    conn = synlynk._get_db()
    conn.close()

    # Insert the dangling row with FK enforcement off, bypassing the
    # REFERENCES goals(goal_id) constraint on decisions.goal_id.
    raw = sqlite3.connect(str(db_path))
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-dangling-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-does-not-exist')"
        )
        raw.commit()
    finally:
        raw.close()

    conn = synlynk._get_db()
    try:
        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    matches = [f for f in findings if f["kind"] == "DECISION_GOAL_MISSING"]
    assert len(matches) == 1
    assert matches[0]["decision_id"] == "dec-dangling-1"
    assert matches[0]["goal_id"] == "goal-does-not-exist"
```

- [ ] **Step 9: Run test to verify it fails**

Run: `pytest tests/test_roadmap_drift.py::test_finds_decision_with_dangling_goal_id -v`
Expected: FAIL if Step 3's `missing_rows` query has a bug, or PASS if it's already correct (the query was written in Step 3). Either way, this step exists to independently verify the FK-bypass path — run it before assuming Step 3's third query block is correct, since it was not exercised by Steps 1-7.

- [ ] **Step 10: Fix implementation if needed, then confirm all three pass**

Run: `pytest tests/test_roadmap_drift.py -v`
Expected: PASS (3 tests)

- [ ] **Step 11: Write the failing test for `classify_roadmap_drift()`**

```python
# tests/test_roadmap_drift.py (append)


def test_classify_roadmap_drift_pass_when_empty():
    from synlynk.roadmap_drift import classify_roadmap_drift

    status, detail = classify_roadmap_drift([])
    assert status == "pass"
    assert "no roadmap drift" in detail


def test_classify_roadmap_drift_warn_when_findings_present():
    from synlynk.roadmap_drift import classify_roadmap_drift

    status, detail = classify_roadmap_drift([
        {"kind": "DECISION_GOAL_UNPLACED", "decision_id": "dec-1", "goal_id": "goal-1",
         "detail": "decision dec-1 links goal goal-1, but that goal's placement_status is 'unplaced'"},
    ])
    assert status == "warn"
    assert "dec-1" in detail
```

- [ ] **Step 12: Run test to verify it fails**

Run: `pytest tests/test_roadmap_drift.py::test_classify_roadmap_drift_pass_when_empty tests/test_roadmap_drift.py::test_classify_roadmap_drift_warn_when_findings_present -v`
Expected: PASS already (implemented in Step 3) — confirm, since `classify_roadmap_drift` was written alongside `find_roadmap_drift` in Step 3.

- [ ] **Step 13: Run full test file and commit**

Run: `pytest tests/test_roadmap_drift.py -v`
Expected: PASS (5 tests)

```bash
git add synlynk/roadmap_drift.py tests/test_roadmap_drift.py
git commit -m "feat: add roadmap drift detection (decision<->goal<->arc)"
```

---

### Task 2: `doctor.py` health check

**Files:**
- Modify: `synlynk/doctor.py`
- Modify: `tests/test_doctor_roadmap_drift.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctor_roadmap_drift.py (append to existing file)


def test_doctor_warns_on_roadmap_decision_drift(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-drift-1', 'ship Z', 'Z ships', 'unplaced')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-drift-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-drift-1')"
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_decision_drift()
    assert result.status == "warn"
    assert "dec-drift-1" in result.message
    assert "goal-drift-1" in result.message


def test_doctor_passes_when_no_roadmap_decision_drift(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    conn.close()

    result = doctor._hc_roadmap_decision_drift()
    assert result.status == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctor_roadmap_drift.py::test_doctor_warns_on_roadmap_decision_drift -v`
Expected: FAIL with `AttributeError: module 'synlynk.doctor' has no attribute '_hc_roadmap_decision_drift'`

- [ ] **Step 3: Add the health check to `synlynk/doctor.py`**

Insert immediately after `repair_roadmap_merge_parity()` (currently ends at line 517, right before `def _hc_identity_key():` at line 520):

```python
def _hc_roadmap_decision_drift() -> HealthCheck:
    """Warn when a decision's linked goal was never placed on the roadmap,
    or a roadmap arc claims a goal with no backing approved decision."""
    try:
        conn = _pkg("_get_db")()
        try:
            from synlynk.roadmap_drift import find_roadmap_drift, classify_roadmap_drift
            findings = find_roadmap_drift(conn)
        finally:
            conn.close()
    except Exception as exc:
        return HealthCheck("roadmap_decision_drift", "warn", f"roadmap drift check unavailable: {exc}")
    status, detail = classify_roadmap_drift(findings)
    if status == "pass":
        return HealthCheck("roadmap_decision_drift", "ok", detail)
    return HealthCheck(
        "roadmap_decision_drift", "warn", detail,
        fix="Review with: synlynk roadmap check",
    )
```

- [ ] **Step 4: Register it in `HEALTH_CHECKS`**

In the `HEALTH_CHECKS = [` list, change:

```python
    _hc_todo_drift,
    _hc_roadmap_merge_parity,
    _hc_identity_key,
```

to:

```python
    _hc_todo_drift,
    _hc_roadmap_merge_parity,
    _hc_roadmap_decision_drift,
    _hc_identity_key,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_doctor_roadmap_drift.py -v`
Expected: PASS (3 tests — the one pre-existing plus the two new ones)

- [ ] **Step 6: Run full doctor test suite to check for regressions**

Run: `pytest tests/test_doctor*.py -v`
Expected: PASS (no regressions from the `HEALTH_CHECKS` list change)

- [ ] **Step 7: Commit**

```bash
git add synlynk/doctor.py tests/test_doctor_roadmap_drift.py
git commit -m "feat: surface roadmap decision drift in synlynk doctor"
```

---

### Task 3: `pr_check.py` gate function

**Files:**
- Modify: `synlynk/pr_check.py`
- Create: `tests/test_pr_check_roadmap_gate.py`

- [ ] **Step 1: Write the failing test for the "not triggered" path**

```python
# tests/test_pr_check_roadmap_gate.py
from __future__ import annotations


def test_roadmap_gate_not_triggered_when_no_decisions_changed(tmp_path, monkeypatch):
    import synlynk
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    from synlynk.pr_check import check_pr_roadmap_gate

    conn = synlynk._get_db()
    try:
        result = check_pr_roadmap_gate(
            conn, changed_files=["synlynk/db.py", "README.md"],
        )
    finally:
        conn.close()

    assert result["passed"] is True
    assert result["triggered"] is False
    assert "decision records" in result["message"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pr_check_roadmap_gate.py::test_roadmap_gate_not_triggered_when_no_decisions_changed -v`
Expected: FAIL with `ImportError: cannot import name 'check_pr_roadmap_gate'`

- [ ] **Step 3: Add `check_pr_roadmap_gate()` to `synlynk/pr_check.py`**

Append to the end of the file (after `check_pr_spec_gate`):

```python
def check_pr_roadmap_gate(
    conn,
    repo_root: str = ".",
    pr_number: Optional[int] = None,
    changed_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check decision<->goal<->roadmap-arc drift when a PR touches decision records.

    Only triggers when the PR modifies files under project-docs/decisions/ —
    otherwise returns passed=True, triggered=False immediately, since drift
    in unrelated PRs is not this PR's concern to block on.

    Returns a dict with:
        passed: bool
        triggered: bool
        findings: List[Dict[str, Any]]
        message: str
    """
    if changed_files is None:
        changed_files = _get_changed_files_in_pr(repo_root, pr_number)

    decision_files: List[str] = []
    for f in (changed_files or []):
        norm_f = f.replace("\\", "/").lstrip("./")
        if norm_f.startswith("project-docs/decisions/") and norm_f.endswith(".md"):
            decision_files.append(norm_f)

    if not decision_files:
        return {
            "passed": True,
            "triggered": False,
            "findings": [],
            "message": "No decision records modified in this PR.",
        }

    from synlynk.roadmap_drift import find_roadmap_drift, classify_roadmap_drift

    findings = find_roadmap_drift(conn)
    status, detail = classify_roadmap_drift(findings)

    return {
        "passed": status == "pass",
        "triggered": True,
        "findings": findings,
        "message": detail,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pr_check_roadmap_gate.py::test_roadmap_gate_not_triggered_when_no_decisions_changed -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for the "triggered, drift found" path**

```python
# tests/test_pr_check_roadmap_gate.py (append)


def test_roadmap_gate_triggered_and_fails_on_drift(tmp_path, monkeypatch):
    import synlynk
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    from synlynk.pr_check import check_pr_roadmap_gate

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-gate-1', 'ship W', 'W ships', 'unplaced')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-gate-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-gate-1')"
        )
        conn.commit()

        result = check_pr_roadmap_gate(
            conn,
            changed_files=["project-docs/decisions/dec-gate-1.md"],
        )
    finally:
        conn.close()

    assert result["triggered"] is True
    assert result["passed"] is False
    assert "dec-gate-1" in result["message"]
    assert len(result["findings"]) == 1
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_pr_check_roadmap_gate.py::test_roadmap_gate_triggered_and_fails_on_drift -v`
Expected: PASS already (Step 3's implementation covers this) — run to confirm, since this is the first test exercising the "triggered" branch.

- [ ] **Step 7: Run full test file**

Run: `pytest tests/test_pr_check_roadmap_gate.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add synlynk/pr_check.py tests/test_pr_check_roadmap_gate.py
git commit -m "feat: add check_pr_roadmap_gate for decision-record PRs"
```

---

### Task 4: Wire the gate into `cmd_pr_check()`

**Files:**
- Modify: `synlynk/db.py:5712-5728` (insert after this block)
- Modify: `tests/test_pr_check.py`

This mirrors the existing GOVERNS-linkage gate's use of `_evaluate_gate`/`gate_mode`, reusing `policy_section="governs_authority"` and `mode_key="require_linked_goal_mode"` per the spec's instruction to gate this on the same toggle rather than inventing a new one.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pr_check.py (append)


def test_pr_check_blocks_on_roadmap_drift_when_decisions_changed(project_dir, capsys):
    from unittest.mock import patch
    from synlynk.db import cmd_pr_check

    triggered_fail = {
        "passed": False,
        "triggered": True,
        "findings": [{"kind": "DECISION_GOAL_UNPLACED", "decision_id": "dec-x", "goal_id": "goal-x",
                       "detail": "decision dec-x links goal goal-x, but that goal's placement_status is 'unplaced'"}],
        "message": "decision dec-x links goal goal-x, but that goal's placement_status is 'unplaced'",
    }
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False), \
         patch("synlynk.db.check_pr_roadmap_gate", return_value=triggered_fail):
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_check()
    assert exc_info.value.code == 1
    assert "dec-x" in capsys.readouterr().out


def test_pr_check_passes_when_roadmap_gate_not_triggered(project_dir, capsys):
    from unittest.mock import patch
    from synlynk.db import cmd_pr_check

    not_triggered = {
        "passed": True,
        "triggered": False,
        "findings": [],
        "message": "No decision records modified in this PR.",
    }
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False), \
         patch("synlynk.db.check_pr_roadmap_gate", return_value=not_triggered):
        cmd_pr_check()
    captured = capsys.readouterr()
    assert "roadmap drift" not in captured.out.lower() or "no decision records" in captured.out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pr_check.py::test_pr_check_blocks_on_roadmap_drift_when_decisions_changed -v`
Expected: FAIL — `check_pr_roadmap_gate` is not yet imported/called in `cmd_pr_check()`, so the mock's return value never reaches the assertion (the test fails with `SystemExit` never being raised, or similar).

- [ ] **Step 3: Insert the gate call in `synlynk/db.py`**

In `cmd_pr_check()`, immediately after the existing GOVERNS-linkage block (after the `else:` branch printing `GOVERNS linkage passed`, i.e. right after this existing code at line 5728):

```python
    else:
        print(f"  {_GREEN}✓{_RESET} GOVERNS linkage passed — {governs_eval.message}")
```

insert:

```python
    from synlynk.pr_check import check_pr_roadmap_gate
    roadmap_gate_res = check_pr_roadmap_gate(conn, repo_root=".", pr_number=pr_number)
    if roadmap_gate_res.get("triggered"):
        roadmap_eval = _evaluate_gate(
            conn, pr_number=pr_number, gate="roadmap_drift",
            mode_key="require_linked_goal_mode",
            verdict=(
                ("pass", roadmap_gate_res["message"]) if roadmap_gate_res.get("passed")
                else ("warn", roadmap_gate_res["message"])
            ),
            policy_section="governs_authority",
        )
        if roadmap_eval.verdict != "pass":
            label = "🚫 [PR CHECK BLOCKED]" if roadmap_eval.should_block else "⚠ [PR CHECK]"
            print(f"\n  {label} roadmap drift detected: {roadmap_eval.message}")
            print("  Review with: synlynk roadmap check\n")
            if roadmap_eval.should_block:
                conn.close()
                raise SystemExit(1)
        else:
            print(f"  {_GREEN}✓{_RESET} Roadmap drift check passed — {roadmap_eval.message}")
    else:
        print(f"  {_GREEN}✓{_RESET} Roadmap drift check skipped — {roadmap_gate_res.get('message')}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pr_check.py -v`
Expected: PASS (all tests, including the two new ones and all pre-existing ones — this confirms no regression in the GOVERNS-linkage or qa-gate blocks that follow)

- [ ] **Step 5: Run the full roadmap-drift-related test files together**

Run: `pytest tests/test_roadmap_drift.py tests/test_doctor_roadmap_drift.py tests/test_pr_check_roadmap_gate.py tests/test_pr_check.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_pr_check.py
git commit -m "feat: block pr check on roadmap drift when decisions change"
```

---

### Task 5: `synlynk roadmap check` CLI subcommand

**Files:**
- Modify: `synlynk/db.py` (add `cmd_roadmap_check`, after `cmd_roadmap_update()` ending at line 4532)
- Modify: `synlynk/cli.py` (add subparser, import, dispatch branch)
- Create: `tests/test_cli_roadmap_check.py`

- [ ] **Step 1: Write the failing test for `cmd_roadmap_check()`**

```python
# tests/test_cli_roadmap_check.py
from __future__ import annotations


def test_cmd_roadmap_check_reports_no_drift(tmp_path, monkeypatch, capsys):
    import synlynk
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    from synlynk.db import cmd_roadmap_check

    exit_code = cmd_roadmap_check()
    assert exit_code == 0
    assert "no roadmap drift" in capsys.readouterr().out.lower()


def test_cmd_roadmap_check_reports_drift_and_returns_nonzero(tmp_path, monkeypatch, capsys):
    import synlynk
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-cli-1', 'ship V', 'V ships', 'unresolved')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-cli-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-cli-1')"
        )
        conn.commit()
    finally:
        conn.close()

    from synlynk.db import cmd_roadmap_check

    exit_code = cmd_roadmap_check()
    assert exit_code == 1
    assert "dec-cli-1" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_roadmap_check.py -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_roadmap_check'`

- [ ] **Step 3: Add `cmd_roadmap_check()` to `synlynk/db.py`**

Insert immediately after `cmd_roadmap_update()` ends (after line 4532's `print(...)` call, before the two blank lines leading into `def cmd_story_list():`):

```python
def cmd_roadmap_check() -> int:
    """Report decision<->goal<->roadmap-arc drift. Read-only; returns 1 if drift found."""
    from synlynk import _get_db
    from synlynk.roadmap_drift import find_roadmap_drift, classify_roadmap_drift

    conn = _get_db()
    try:
        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    status, detail = classify_roadmap_drift(findings)
    if status == "pass":
        print(f"  ✓ {detail}")
        return 0

    print(f"  ⚠ roadmap drift detected ({len(findings)} finding(s)):")
    for f in findings:
        print(f"    - [{f['kind']}] {f['detail']}")
    return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_roadmap_check.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add the `roadmap check` subparser to `synlynk/cli.py`**

After the existing `roadmap_render_parser` block (currently lines 1808-1809):

```python
    roadmap_render_parser = roadmap_sub.add_parser("render", help="Render roadmap.md from state.db")
    roadmap_render_parser.add_argument("--role", default="pm")
```

insert:

```python
    roadmap_sub.add_parser("check", help="Report decision<->goal<->roadmap-arc drift")
```

- [ ] **Step 6: Add `cmd_roadmap_check` to the `from synlynk.db import (...)` block**

In the import block (currently lines 2534-2535):

```python
        cmd_roadmap_add,
        cmd_roadmap_update,
```

change to:

```python
        cmd_roadmap_add,
        cmd_roadmap_check,
        cmd_roadmap_update,
```

- [ ] **Step 7: Add the dispatch branch**

After the existing `render` branch (currently lines 3415-3418):

```python
        elif args.roadmap_action == "render":
            from synlynk.db import _generate_roadmap_md
            _generate_roadmap_md()
            print("Rendered roadmap.md from state.db")
```

insert:

```python
        elif args.roadmap_action == "check":
            sys.exit(cmd_roadmap_check())
```

- [ ] **Step 8: Smoke-test the CLI wiring end-to-end**

Run: `python3 bin/synlynk.py roadmap check --help`
Expected: argparse help output for the `check` subcommand, no traceback.

Run (from a scratch dir with a throwaway `SYNLYNK_STATE_DB_PATH`, to avoid touching the real project DB):
```bash
SYNLYNK_STATE_DB_PATH=/tmp/synlynk-plan-smoketest.db python3 bin/synlynk.py roadmap check
```
Expected: prints `✓ no roadmap drift detected` (fresh empty DB has no decisions/goals yet) and exits 0.

- [ ] **Step 9: Run full test suite for regressions**

Run: `pytest tests/ -v -k "roadmap or cli"`
Expected: PASS (no regressions in existing roadmap/CLI tests)

- [ ] **Step 10: Commit**

```bash
git add synlynk/db.py synlynk/cli.py tests/test_cli_roadmap_check.py
git commit -m "feat: add synlynk roadmap check CLI subcommand"
```

---

### Task 6: Remediation — fix `story-ca8afaf8` and document the unresolvable decision IDs

This task applies the spec's own Remediation section against the real production `state.db` at `~/.synlynk/workspaces/synlynk/state.db`, not a test fixture. No code changes — this is a data-correction + documentation task.

**Files:**
- No source files modified.
- Modify: `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md` (Remediation section — record outcomes)

- [ ] **Step 1: Verify current state of `story-ca8afaf8` before changing it**

Run: `synlynk story show story-ca8afaf8` (or, if no `story show` command exists, query directly: `python3 -c "import synlynk; conn=synlynk._get_db(); print(conn.execute(\"SELECT story_id, status, readiness FROM stories WHERE story_id='story-ca8afaf8'\").fetchone()); conn.close()"`)
Expected output: `status='open', readiness='draft'` (matching the state confirmed earlier via `gh pr view 2596`, which showed PR #2596 merged on `2026-10-24T10:43:00Z`).

- [ ] **Step 2: Apply the fix**

Run: `synlynk story done story-ca8afaf8`

Expected: command exits 0, prints confirmation. This calls `cmd_story_done()` (`synlynk/db.py:4653-4707`), which sets both `status='done'` and `readiness='done'` together — the only existing command that does both, which is why `story ready` alone would be insufficient here.

- [ ] **Step 3: Verify the fix took effect**

Run: `python3 -c "import synlynk; conn=synlynk._get_db(); print(conn.execute(\"SELECT story_id, status, readiness FROM stories WHERE story_id='story-ca8afaf8'\").fetchone()); conn.close()"`
Expected: `('story-ca8afaf8', 'done', 'done')`

- [ ] **Step 4: Document the unresolvable `dec-9b41a7c3`/`dec-4e81b29a` finding**

These two decision IDs were searched for exhaustively (file search across the repo and `~/.synlynk`, and a direct `decisions` table query) and do not exist anywhere — neither as rows nor as JSON files on disk. They are unresolvable legacy residue from an earlier "takeover brief" review. Append a short note to the spec's Remediation section recording this as a closed, non-actionable finding (edit the committed spec file directly):

In `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md`, in the Remediation section, add:

```markdown
**Resolved 2026-11-13:**
- `story-ca8afaf8` fixed via `synlynk story done story-ca8afaf8` (PR #2596 confirmed merged 2026-10-24).
- `dec-9b41a7c3` / `dec-4e81b29a`: exhaustively searched (repo + `~/.synlynk`, both filesystem and `decisions` table) — confirmed not to exist anywhere. Legacy residue from the original takeover-brief review; no further action, no row to repair.
```

- [ ] **Step 5: Run the pre-existing spec-lint gate against the edited spec to confirm the edit itself is valid**

Run: `python3 -c "
from synlynk.spec_lint import lint_spec_file, load_known_decision_ids, load_known_goal_ids
findings = lint_spec_file(
    'docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md',
    repo_root='.',
    known_goals=load_known_goal_ids(repo_root='.'),
    known_decisions=load_known_decision_ids(repo_root='.'),
)
for f in findings:
    print(f.severity, f.rule, f.message)
print('done,', len(findings), 'findings')
"`
Expected: no `ERROR`-severity findings (matches the same gate `check_pr_spec_gate()` would run in CI).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md
git commit -m "docs(spec): record roadmap-drift remediation outcomes for story-ca8afaf8 and dec-9b41a7c3/dec-4e81b29a"
```

---

### Task 7: Process-layer doc update

**Files:**
- Modify: `CLAUDE.md` (this worktree's copy, at the repo root)

- [ ] **Step 1: Add a short note under the existing "## Hardened PR Review Policy (2026-10-04)" section**

Read the current section first:

Run: `grep -n "## Hardened PR Review Policy" CLAUDE.md`

Then, immediately after that section's existing numbered list (after its item `2.` on cross-harness+model review), add a new top-level subsection:

```markdown
## Roadmap Drift Gate (2026-11-13)

A PR that modifies `project-docs/decisions/*.md` is checked for drift between `decisions`, `goals`, and `roadmap_arcs` — e.g. a decision linking a goal that was never placed on the roadmap, or a roadmap arc claiming a goal with no backing approved decision. `synlynk pr check` runs this automatically (via `check_pr_roadmap_gate`) and blocks when `require_linked_goal_mode` (the same toggle the GOVERNS-linkage gate uses, in `.synlynk/policy.json`'s `governs_authority` block) is `enforce`. Inspect drift ad hoc with `synlynk roadmap check`, or see it flagged passively in `synlynk doctor`. There is no auto-repair command — remediation requires a human to determine which goal a decision or arc *should* actually reference, so each finding is resolved manually (e.g. placing the goal on the roadmap via `synlynk roadmap add`/`update`, or correcting the arc's `goal_id`).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the roadmap drift gate in CLAUDE.md"
```

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md`):
- Section 2 (Roadmap Drift Gate: the three finding types, `require_linked_goal_mode` reuse, `pr check`/`doctor` surfacing) → Tasks 1-5.
- Remediation section's two named cases (`story-ca8afaf8`, `dec-9b41a7c3`/`dec-4e81b29a`) → Task 6.
- Section 4 (Enforcement Model, process-layer doc note) → Task 7.
- Sections 1, 3, 5, 6 → explicitly deferred per the Scope note above; not covered here by design.

**2. Placeholder scan:** No TBD/TODO markers. Every step has runnable code or an exact command with an expected result. The one soft spot — Task 6 Step 1's `synlynk story show` command — is hedged with a concrete fallback one-liner in case that subcommand doesn't exist, rather than left vague.

**3. Type/signature consistency:**
- `find_roadmap_drift(conn) -> list[dict]` (Task 1) is called identically in Task 2 (`doctor.py`), Task 3 (`pr_check.py`), and Task 5 (`cmd_roadmap_check`).
- `classify_roadmap_drift(findings) -> tuple[str, str]` (Task 1) is called identically in Tasks 2, 3, and 5.
- `check_pr_roadmap_gate(conn, repo_root=".", pr_number=None, changed_files=None) -> dict` (Task 3) keyword signature matches its call site in Task 4 (`check_pr_roadmap_gate(conn, repo_root=".", pr_number=pr_number)`).
- Finding dict keys (`kind`, `detail`, plus `decision_id`/`goal_id` or `arc_version`/`goal_id`) are used consistently across Tasks 1, 2, 3, 5, 6.
- `_evaluate_gate(... policy_section="governs_authority")` in Task 4 matches the exact signature read from `synlynk/policy_gates.py` (`policy_section: str | None = None` parameter, defaults to `gate` if omitted — explicitly overridden here so the new `roadmap_drift` gate name doesn't fork a new, unconfigured policy section).

No gaps found.

---

**Plan complete and saved to `docs/superpowers/plans/2026-11-13-roadmap-drift-governance.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
