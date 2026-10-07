# Policy Enforcement Maturity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the `governs_authority.require_linked_goal` and `merge_authority.cross_harness_review_required` merge gates run in a non-blocking "observe" mode that still records every verdict, with a streak-based signal for when it's safe to flip a gate back to hard enforcement.

**Architecture:** A new `synlynk/policy_gates.py` module owns gate-mode resolution (reads `.synlynk/policy.json` directly, same pattern as the existing `_cross_harness_review_required()`), verdict normalization (adapts each gate's existing verdict function into a common `pass`/`warn`/`insufficient_data` result), and streak calculation. `synlynk/db.py:cmd_pr_check` is changed to route both existing gate checks through a new `_evaluate_gate()` call instead of branching on the raw verdict directly. A new migration (`m0018_policy_gate_events.py`) adds the `policy_gate_events` table. A new `synlynk policy gate-status` command reads streaks back out.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, argparse) — matches the rest of `synlynk/`. Tests use `pytest` with the existing `project_dir` fixture from `tests/conftest.py`.

---

## Context for the implementer

- `synlynk/db.py` is a single ~4600-line module. Two existing functions are the gates this plan wraps:
  - `_cross_harness_review_verdict(conn, pr_number) -> tuple[bool, str]` at `synlynk/db.py:280-341`. `_cross_harness_review_required()` at `synlynk/db.py:67-76` reads `.synlynk/policy.json`'s `overrides.merge_authority.cross_harness_review_required` directly via its own `open()`/`json.load()` — it does **not** go through `synlynk/policy.py`'s `load_policy()`, because `load_policy()` (see `synlynk/policy.py:116-121`) explicitly skips `merge_authority` and `connector_authority` when merging repo-level `overrides`. This plan's new `*_mode` reads follow the same direct-read pattern for consistency, and because going through `load_policy()` would silently lose `merge_authority`'s mode value the same way it loses `cross_harness_review_required` today.
  - `pr_governs_linkage_violations(conn, pr_number) -> list[dict]` in `synlynk/governs_gate.py:55-160`. Empty list = no violations = pass. Each dict has at least `job_id`, `story_id`, `reason`.
- Both gates are invoked in `cmd_pr_check()` at `synlynk/db.py:4415` — the GOVERNS check at lines 4445-4456, the cross-harness check at lines 4496-4502. Both currently call `raise SystemExit(1)` directly on failure.
- The migrations framework (`synlynk/migrations/`) is the current mechanism for schema changes (gh:#1926). `synlynk/migrations/runner.py` holds a static `MIGRATIONS: list[Migration] = [M0016, M0017]` list — version 18 is next. `synlynk/migrations/m0017_daemon_job_purpose.py` is the idiomatic pattern: a private `_up(conn)` function wrapped in a module-level `MIGRATION = Migration(version=N, name="...", up=_up)`.
- `synlynk/policy_cli.py` is the existing small CLI-surface module for policy commands (`cmd_policy_show`, `cmd_policy_check_merge`, `cmd_policy_sync_branch_protection`). The new `gate-status` command follows this file's pattern.
- CLI wiring for `policy` subcommands lives in `synlynk/cli.py`: the `argparse` subparsers at `synlynk/cli.py:1482-1492`, and the dispatch `elif` chain at `synlynk/cli.py:2734-2739`.
- Test fixture `project_dir(tmp_path, monkeypatch)` in `tests/conftest.py:109` creates a minimal project directory and chdirs into it; `synlynk._get_db()` opens (and migrates) `.synlynk/state.db` relative to the current directory. `tests/test_agent_cli.py:227-271` (`_seed_cross_harness_review_case`) is the existing fixture-seeding pattern for cross-harness-review tests — reuse its policy.json/daemon_jobs/cost_entries/capability_ratings/stories seeding shape for this plan's gate tests.
- This repo's `policy.json` schema (`.synlynk/policy.json`) currently has, among other keys:
  ```json
  "merge_authority": {
    "can_merge": ["qa"],
    "require_non_authoring_review": true,
    "review_fallback": "same_identity_comment_checklist",
    "cross_harness_review_required": true,
    "cross_harness_review_note": "..."
  },
  "governs_authority": {
    "require_linked_goal": true,
    "note": "..."
  }
  ```
  Note these top-level keys (`merge_authority`, `governs_authority`) are **not** nested under an `overrides` key in every historical reader — `_cross_harness_review_required()` specifically reads `policy.get("overrides", {}).get("merge_authority", {})...`, meaning the literal file on disk must have an `"overrides"` wrapper for that function to see it. Check the actual repo policy.json's structure before assuming — see Task 1, Step 1.

## File Structure

- **Create:** `synlynk/migrations/m0018_policy_gate_events.py` — the `policy_gate_events` table migration.
- **Modify:** `synlynk/migrations/runner.py` — register `M0018` in `MIGRATIONS`.
- **Create:** `synlynk/policy_gates.py` — `_read_repo_policy_overrides()`, `gate_mode()`, `classify_cross_harness_verdict()`, `classify_governs_violations()`, `record_gate_event()`, `gate_streak()`, `_evaluate_gate()`.
- **Modify:** `synlynk/db.py` — replace the two direct gate checks in `cmd_pr_check()` (lines 4445-4456 and 4496-4502) with calls to `_evaluate_gate()` from `synlynk/policy_gates.py`.
- **Modify:** `synlynk/policy_cli.py` — add `cmd_policy_gate_status()`.
- **Modify:** `synlynk/cli.py` — wire `policy gate-status` subcommand (parser + dispatch).
- **Create:** `tests/test_policy_gates.py` — all new unit tests for `policy_gates.py`.
- **Modify:** `tests/test_agent_cli.py` — update the two `cmd_pr_check`-level assertions so they still pass under the new observe-mode default (see Task 6).

---

### Task 1: Confirm repo `policy.json` structure, then add `*_mode` fields

**Files:**
- Modify: `.synlynk/policy.json`

- [ ] **Step 1: Read the current file and confirm the `overrides` wrapper**

Run: `cat .synlynk/policy.json | python3 -m json.tool | head -40`

Expected: a top-level `"overrides"` key containing `merge_authority` and `governs_authority` (this was confirmed during design — see `docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md` §3.1). If `overrides` is absent in your checkout, stop and re-read `synlynk/db.py:67-76` and `synlynk/governs_gate.py` call sites before proceeding — the direct-read helper in Task 3 must match whatever structure is actually on disk.

- [ ] **Step 2: Add `*_mode` siblings to `.synlynk/policy.json`**

Edit the `overrides.merge_authority` and `overrides.governs_authority` objects to add the two mode fields, defaulting both to `"observe"` per the approved spec (§3.1):

```json
"merge_authority": {
  "can_merge": ["qa"],
  "require_non_authoring_review": true,
  "review_fallback": "same_identity_comment_checklist",
  "cross_harness_review_required": true,
  "cross_harness_review_required_mode": "observe",
  "cross_harness_review_note": "Reviewer must differ from implementer in harness AND model, not just role identity. Enforced by synlynk pr check from cost_entries/job metadata (gh:#1991)."
},
"governs_authority": {
  "require_linked_goal": true,
  "require_linked_goal_mode": "observe",
  "note": "100% GOVERNS adherence required per Nikhil's 2026-10-04 hardening — every dispatched job must link a GOVERNS goal/story. Hard-fail enforcement shipped via PR #2029 (gh:#1990, closed 2026-10-05). require_linked_goal_mode set to observe 2026-10-07 pending a 100-pass clean streak — see docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md."
}
```

Keep every other existing key in the file unchanged.

- [ ] **Step 3: Validate the JSON is still well-formed**

Run: `python3 -c "import json; json.load(open('.synlynk/policy.json'))" && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .synlynk/policy.json
git commit -m "$(cat <<'EOF'
feat(policy): add observe-mode flags for governs/cross-harness gates

Both gates default to observe mode pending a 100-consecutive-pass
streak, per docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 2: `policy_gate_events` migration

**Files:**
- Create: `synlynk/migrations/m0018_policy_gate_events.py`
- Modify: `synlynk/migrations/runner.py`
- Test: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_migrations_framework.py`:

```python
def test_m0018_creates_policy_gate_events_table(tmp_path):
    import sqlite3
    from synlynk.migrations.m0018_policy_gate_events import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 17")
    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(policy_gate_events)")}
    assert cols == {"id", "pr_number", "gate", "mode", "verdict", "detail", "recorded_at"}

    conn.execute(
        "INSERT INTO policy_gate_events (pr_number, gate, mode, verdict, detail, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (2100, "governs_authority", "observe", "pass", "no violations", "2026-10-07T00:00:00+00:00"),
    )
    conn.commit()
    row = conn.execute("SELECT pr_number, gate, verdict FROM policy_gate_events").fetchone()
    assert row == (2100, "governs_authority", "pass")


def test_m0018_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0018_policy_gate_events import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 17")
    MIGRATION.up(conn)
    MIGRATION.up(conn)  # must not raise on re-apply
    conn.commit()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_migrations_framework.py::test_m0018_creates_policy_gate_events_table -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0018_policy_gate_events'`

- [ ] **Step 3: Create the migration module**

Write `synlynk/migrations/m0018_policy_gate_events.py`:

```python
"""Migration 18: durable observe-mode gate verdict log for synlynk pr check."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS policy_gate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number INTEGER NOT NULL,
            gate TEXT NOT NULL,
            mode TEXT NOT NULL,
            verdict TEXT NOT NULL,
            detail TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_policy_gate_events_gate "
        "ON policy_gate_events(gate, id)"
    )


MIGRATION = Migration(version=18, name="policy_gate_events", up=_up)
```

- [ ] **Step 4: Register the migration in the runner**

Edit `synlynk/migrations/runner.py`:

```python
from synlynk.migrations.m0016_cost_entries_pr_number import MIGRATION as M0016
from synlynk.migrations.m0017_daemon_job_purpose import MIGRATION as M0017
from synlynk.migrations.m0018_policy_gate_events import MIGRATION as M0018

# Static, explicitly-imported registry. Append future Migration entries here
# in ascending version order — no dynamic directory scanning.
MIGRATIONS: list[Migration] = [M0016, M0017, M0018]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_migrations_framework.py -v`
Expected: all PASS, including the two new tests.

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0018_policy_gate_events.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "$(cat <<'EOF'
feat(migrations): add policy_gate_events table (migration 18)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 3: `policy_gates.py` — mode resolution

**Files:**
- Create: `synlynk/policy_gates.py`
- Test: `tests/test_policy_gates.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_policy_gates.py`:

```python
import json

import pytest


def _write_policy(tmp_path, overrides):
    policy_dir = tmp_path / ".synlynk"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy.json").write_text(json.dumps({"overrides": overrides}))


def test_gate_mode_defaults_to_enforce_when_key_absent(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode

    _write_policy(tmp_path, {"merge_authority": {"cross_harness_review_required": True}})
    monkeypatch.chdir(tmp_path)
    assert gate_mode("merge_authority", "cross_harness_review_required_mode") == "enforce"


def test_gate_mode_reads_observe_value(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode

    _write_policy(tmp_path, {
        "merge_authority": {
            "cross_harness_review_required": True,
            "cross_harness_review_required_mode": "observe",
        },
    })
    monkeypatch.chdir(tmp_path)
    assert gate_mode("merge_authority", "cross_harness_review_required_mode") == "observe"


def test_gate_mode_defaults_to_enforce_when_policy_file_missing(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode

    monkeypatch.chdir(tmp_path)
    assert gate_mode("governs_authority", "require_linked_goal_mode") == "enforce"


def test_gate_mode_reads_governs_authority_independently(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode

    _write_policy(tmp_path, {
        "governs_authority": {"require_linked_goal": True, "require_linked_goal_mode": "observe"},
        "merge_authority": {"cross_harness_review_required": True},
    })
    monkeypatch.chdir(tmp_path)
    assert gate_mode("governs_authority", "require_linked_goal_mode") == "observe"
    assert gate_mode("merge_authority", "cross_harness_review_required_mode") == "enforce"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_policy_gates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.policy_gates'`

- [ ] **Step 3: Write the minimal implementation**

Create `synlynk/policy_gates.py`:

```python
"""Observe/enforce mode resolution and verdict logging for synlynk pr check gates.

Reads .synlynk/policy.json directly rather than through synlynk.policy.load_policy(),
matching the existing synlynk.db._cross_harness_review_required() pattern — load_policy()
silently drops repo-level "merge_authority" / "connector_authority" overrides (see
synlynk/policy.py's merge-skip list), so a gate-mode read routed through it would never
see this repo's own override.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def _read_repo_policy_overrides() -> dict[str, Any]:
    try:
        with open(os.path.join(os.getcwd(), ".synlynk", "policy.json"), encoding="utf-8") as fh:
            policy = json.load(fh)
        return policy.get("overrides", {}) or {}
    except (OSError, TypeError, ValueError):
        return {}


def gate_mode(gate_section: str, mode_key: str) -> str:
    """Return 'enforce' (default) or 'observe' for a gate's mode flag."""
    overrides = _read_repo_policy_overrides()
    value = overrides.get(gate_section, {}).get(mode_key)
    return value if value in ("enforce", "observe") else "enforce"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_policy_gates.py -v`
Expected: all 4 PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/policy_gates.py tests/test_policy_gates.py
git commit -m "$(cat <<'EOF'
feat(policy): add gate_mode() for per-gate enforce/observe resolution

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 4: Verdict classifiers and event recording

**Files:**
- Modify: `synlynk/policy_gates.py`
- Test: `tests/test_policy_gates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_policy_gates.py`:

```python
def test_classify_cross_harness_verdict_pass():
    from synlynk.policy_gates import classify_cross_harness_verdict

    verdict, detail = classify_cross_harness_verdict(True, "implementation codex / gpt-5.3-codex reviewed by claude / claude-sonnet-5")
    assert verdict == "pass"
    assert "reviewed by" in detail


def test_classify_cross_harness_verdict_warn_on_same_harness():
    from synlynk.policy_gates import classify_cross_harness_verdict

    verdict, detail = classify_cross_harness_verdict(
        False, "implementing and reviewing jobs use the same harness+model (codex / gpt-5.3-codex)"
    )
    assert verdict == "warn"


@pytest.mark.parametrize("detail", [
    "no implementing job provenance found for PR #2100",
    "no reviewing job provenance found for PR #2100",
    "ambiguous implementation job provenance for PR #2100",
    "incomplete harness/model provenance (implementing=job-1, reviewing=job-2)",
])
def test_classify_cross_harness_verdict_insufficient_data(detail):
    from synlynk.policy_gates import classify_cross_harness_verdict

    verdict, _ = classify_cross_harness_verdict(False, detail)
    assert verdict == "insufficient_data"


def test_classify_governs_violations_pass_on_empty_list():
    from synlynk.policy_gates import classify_governs_violations

    verdict, detail = classify_governs_violations([])
    assert verdict == "pass"
    assert detail == "no GOVERNS linkage violations"


def test_classify_governs_violations_warn_on_violations():
    from synlynk.policy_gates import classify_governs_violations

    violations = [{"job_id": "job-1", "story_id": None, "reason": "missing story_id"}]
    verdict, detail = classify_governs_violations(violations)
    assert verdict == "warn"
    assert "job-1" in detail


def test_record_gate_event_writes_row(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations
    from synlynk.policy_gates import record_gate_event

    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)

    record_gate_event(conn, pr_number=2100, gate="governs_authority", mode="observe", verdict="pass", detail="no violations")
    conn.commit()

    row = conn.execute(
        "SELECT pr_number, gate, mode, verdict, detail FROM policy_gate_events"
    ).fetchone()
    assert row == (2100, "governs_authority", "observe", "pass", "no violations")


def test_record_gate_event_does_not_raise_on_write_failure(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.policy_gates import record_gate_event

    conn = sqlite3.connect(tmp_path / "state.db")  # policy_gate_events table doesn't exist
    # Must not raise even though the INSERT will fail.
    record_gate_event(conn, pr_number=2100, gate="governs_authority", mode="observe", verdict="pass", detail="no violations")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_policy_gates.py -v -k "classify or record_gate_event"`
Expected: FAIL with `ImportError`/`AttributeError` — `classify_cross_harness_verdict`, `classify_governs_violations`, `record_gate_event` don't exist yet.

- [ ] **Step 3: Implement the classifiers and recorder**

Append to `synlynk/policy_gates.py`:

```python
_INSUFFICIENT_DATA_MARKERS = (
    "no implementing job provenance found",
    "no reviewing job provenance found",
    "ambiguous implementation job provenance",
    "incomplete harness/model provenance",
)


def classify_cross_harness_verdict(ok: bool, detail: str) -> tuple[str, str]:
    """Adapt _cross_harness_review_verdict()'s (bool, str) into a 3-way verdict.

    A definite same-harness+model match is a real rule violation ('warn').
    Every other failure mode means the gate couldn't determine provenance at
    all ('insufficient_data') — distinct from a rule violation, but still
    resets the re-hardening streak the same way (see gate_streak()).
    """
    if ok:
        return "pass", detail
    if any(marker in detail for marker in _INSUFFICIENT_DATA_MARKERS):
        return "insufficient_data", detail
    return "warn", detail


def classify_governs_violations(violations: list[dict]) -> tuple[str, str]:
    """Adapt pr_governs_linkage_violations()'s list[dict] into a 3-way verdict."""
    if not violations:
        return "pass", "no GOVERNS linkage violations"
    summary = "; ".join(
        f"{v['job_id']} (story={v.get('story_id') or 'none'}; {v['reason']})"
        for v in violations
    )
    return "warn", summary


def record_gate_event(conn, *, pr_number: int, gate: str, mode: str, verdict: str, detail: str) -> None:
    """Write one policy_gate_events row. Never raises — a logging failure must
    not block the pr check result itself (see design spec §3.6)."""
    try:
        conn.execute(
            "INSERT INTO policy_gate_events (pr_number, gate, mode, verdict, detail, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pr_number, gate, mode, verdict, detail, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except Exception as exc:
        print(f"  ⚠ [PR CHECK] failed to record policy_gate_events row for gate {gate!r}: {exc}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_policy_gates.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/policy_gates.py tests/test_policy_gates.py
git commit -m "$(cat <<'EOF'
feat(policy): add gate verdict classifiers and durable event recording

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 5: `gate_streak()` and `_evaluate_gate()`

**Files:**
- Modify: `synlynk/policy_gates.py`
- Test: `tests/test_policy_gates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_policy_gates.py`:

```python
def _db_with_events(tmp_path, rows):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)
    for pr_number, gate, verdict in rows:
        conn.execute(
            "INSERT INTO policy_gate_events (pr_number, gate, mode, verdict, detail, recorded_at) "
            "VALUES (?, ?, 'observe', ?, 'detail', '2026-10-07T00:00:00+00:00')",
            (pr_number, gate, verdict),
        )
    conn.commit()
    return conn


def test_gate_streak_counts_consecutive_passes(tmp_path):
    from synlynk.policy_gates import gate_streak

    conn = _db_with_events(tmp_path, [
        (1, "governs_authority", "pass"),
        (2, "governs_authority", "pass"),
        (3, "governs_authority", "pass"),
    ])
    assert gate_streak(conn, "governs_authority") == 3


def test_gate_streak_resets_on_warn():
    pass  # placeholder removed below — see next test for the real assertion


def test_gate_streak_resets_on_most_recent_warn(tmp_path):
    from synlynk.policy_gates import gate_streak

    conn = _db_with_events(tmp_path, [
        (1, "governs_authority", "pass"),
        (2, "governs_authority", "warn"),
        (3, "governs_authority", "pass"),
        (4, "governs_authority", "pass"),
    ])
    assert gate_streak(conn, "governs_authority") == 2


def test_gate_streak_resets_on_insufficient_data(tmp_path):
    from synlynk.policy_gates import gate_streak

    conn = _db_with_events(tmp_path, [
        (1, "cross_harness_review", "pass"),
        (2, "cross_harness_review", "insufficient_data"),
    ])
    assert gate_streak(conn, "cross_harness_review") == 0


def test_gate_streak_is_scoped_per_gate(tmp_path):
    from synlynk.policy_gates import gate_streak

    conn = _db_with_events(tmp_path, [
        (1, "governs_authority", "pass"),
        (1, "cross_harness_review", "warn"),
        (2, "governs_authority", "pass"),
    ])
    assert gate_streak(conn, "governs_authority") == 2
    assert gate_streak(conn, "cross_harness_review") == 0


def test_gate_streak_returns_none_when_no_events(tmp_path):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations
    from synlynk.policy_gates import gate_streak

    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)
    assert gate_streak(conn, "governs_authority") is None


def test_evaluate_gate_enforce_mode_blocks_on_warn(tmp_path, monkeypatch):
    from synlynk.policy_gates import _evaluate_gate

    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True}})  # no mode key -> enforce
    monkeypatch.chdir(tmp_path)
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)

    result = _evaluate_gate(
        conn, pr_number=2100, gate="governs_authority", mode_key="require_linked_goal_mode",
        verdict=("warn", "job-1 missing story"),
    )
    assert result.should_block is True
    assert result.verdict == "warn"


def test_evaluate_gate_observe_mode_does_not_block_on_warn(tmp_path, monkeypatch):
    from synlynk.policy_gates import _evaluate_gate

    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True, "require_linked_goal_mode": "observe"}})
    monkeypatch.chdir(tmp_path)
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)

    result = _evaluate_gate(
        conn, pr_number=2100, gate="governs_authority", mode_key="require_linked_goal_mode",
        verdict=("warn", "job-1 missing story"),
    )
    assert result.should_block is False
    assert "[OBSERVE MODE" in result.message

    row = conn.execute("SELECT verdict, mode FROM policy_gate_events WHERE pr_number=2100").fetchone()
    assert row == ("warn", "observe")


def test_evaluate_gate_pass_never_blocks_regardless_of_mode(tmp_path, monkeypatch):
    from synlynk.policy_gates import _evaluate_gate

    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True}})
    monkeypatch.chdir(tmp_path)
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)

    result = _evaluate_gate(
        conn, pr_number=2100, gate="governs_authority", mode_key="require_linked_goal_mode",
        verdict=("pass", "no violations"),
    )
    assert result.should_block is False
```

Remove the empty `test_gate_streak_resets_on_warn` placeholder you just added — it was scaffolding to keep the diff readable step-by-step; `test_gate_streak_resets_on_most_recent_warn` is the real assertion. Delete that one function before running the suite.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_policy_gates.py -v -k "gate_streak or evaluate_gate"`
Expected: FAIL — `gate_streak` and `_evaluate_gate` don't exist yet.

- [ ] **Step 3: Implement `gate_streak()` and `_evaluate_gate()`**

Append to `synlynk/policy_gates.py`:

```python
from dataclasses import dataclass


def gate_streak(conn, gate: str) -> int | None:
    """Count consecutive 'pass' verdicts for `gate`, walking back from the most
    recent event. Returns None if there are no recorded events at all (distinct
    from a streak of 0, which means the most recent event was not a pass)."""
    rows = conn.execute(
        "SELECT verdict FROM policy_gate_events WHERE gate=? ORDER BY id DESC",
        (gate,),
    ).fetchall()
    if not rows:
        return None
    streak = 0
    for (verdict,) in rows:
        if verdict != "pass":
            break
        streak += 1
    return streak


RE_HARDEN_THRESHOLD = 100


@dataclass
class GateEvaluation:
    should_block: bool
    verdict: str
    message: str


def _evaluate_gate(
    conn, *, pr_number: int, gate: str, mode_key: str, verdict: tuple[str, str],
) -> GateEvaluation:
    """Record `verdict` for `gate` and decide whether it should block the merge.

    `verdict` is the already-classified (verdict, detail) pair from
    classify_cross_harness_verdict() / classify_governs_violations().
    """
    mode = gate_mode(gate, mode_key)
    status, detail = verdict
    record_gate_event(conn, pr_number=pr_number, gate=gate, mode=mode, verdict=status, detail=detail)

    if status == "pass":
        return GateEvaluation(should_block=False, verdict=status, message=detail)

    if mode == "enforce":
        return GateEvaluation(should_block=True, verdict=status, message=detail)

    return GateEvaluation(
        should_block=False,
        verdict=status,
        message=f"[OBSERVE MODE — not blocking] {detail}",
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_policy_gates.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/policy_gates.py tests/test_policy_gates.py
git commit -m "$(cat <<'EOF'
feat(policy): add gate_streak() and _evaluate_gate() enforce/observe routing

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 6: Wire `_evaluate_gate()` into `cmd_pr_check()`

**Files:**
- Modify: `synlynk/db.py:4445-4456` and `synlynk/db.py:4496-4502`
- Test: `tests/test_agent_cli.py`

- [ ] **Step 1: Write the failing tests**

The existing tests `test_pr_check_cross_harness_review_rejects_same_harness_and_model` (line 274) and the governs tests around line 69-223 in `tests/test_agent_cli.py` call the *verdict functions* directly (`_cross_harness_review_verdict`, `pr_governs_linkage_violations`), not `cmd_pr_check()` itself — those stay valid unchanged, since this task doesn't touch either verdict function's own logic.

Add a new test that exercises `cmd_pr_check()` end-to-end in observe mode, proving a real violation no longer raises `SystemExit`. Append to `tests/test_agent_cli.py`:

```python
def test_pr_check_governs_gate_observe_mode_does_not_block(project_dir, monkeypatch):
    import json
    import synlynk
    from synlynk.db import cmd_pr_check

    monkeypatch.setattr("synlynk.db._is_github_remote", lambda: False)

    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.write_text(json.dumps({
        "overrides": {
            "governs_authority": {"require_linked_goal": True, "require_linked_goal_mode": "observe"},
            "merge_authority": {"cross_harness_review_required": False},
        }
    }))
    monkeypatch.chdir(project_dir)

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, harness, task, status, enqueued_at, purpose) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-unlinked", "codex", "codex", "implement issue #2100", "done", "2026-10-07T00:00:00", "implementation"),
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, model, story_id, cost_source, job_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-10-07", "codex", "codex", "gpt-5.3-codex", None, "test", "job-unlinked"),
    )
    conn.commit()
    conn.close()

    # Must NOT raise SystemExit despite the unlinked job above.
    cmd_pr_check(pr_number=2100)

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT gate, mode, verdict FROM policy_gate_events WHERE pr_number=2100 AND gate='governs_authority'"
    ).fetchone()
    conn.close()
    assert row == ("governs_authority", "observe", "warn")


def test_pr_check_governs_gate_enforce_mode_still_blocks(project_dir, monkeypatch):
    import json
    import synlynk
    from synlynk.db import cmd_pr_check

    monkeypatch.setattr("synlynk.db._is_github_remote", lambda: False)

    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.write_text(json.dumps({
        "overrides": {
            "governs_authority": {"require_linked_goal": True, "require_linked_goal_mode": "enforce"},
            "merge_authority": {"cross_harness_review_required": False},
        }
    }))
    monkeypatch.chdir(project_dir)

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, harness, task, status, enqueued_at, purpose) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-unlinked2", "codex", "codex", "implement issue #2101", "done", "2026-10-07T00:00:00", "implementation"),
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, model, story_id, cost_source, job_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-10-07", "codex", "codex", "gpt-5.3-codex", None, "test", "job-unlinked2"),
    )
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit):
        cmd_pr_check(pr_number=2101)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_agent_cli.py -v -k "governs_gate_observe or governs_gate_enforce"`
Expected: FAIL — `test_pr_check_governs_gate_observe_mode_does_not_block` fails because `cmd_pr_check` still raises `SystemExit` unconditionally on any violation (current code at `synlynk/db.py:4456`).

- [ ] **Step 3: Replace the GOVERNS gate block in `cmd_pr_check()`**

In `synlynk/db.py`, replace lines 4445-4456:

```python
    from synlynk.governs_gate import pr_governs_linkage_violations
    governs_violations = pr_governs_linkage_violations(conn, pr_number)
    if governs_violations:
        print("\n  🚫 [PR CHECK BLOCKED] dispatched jobs missing linked GOVERNS story/goal:")
        for violation in governs_violations:
            print(
                f"    {violation['job_id']} "
                f"(story={violation.get('story_id') or 'none'}; {violation['reason']})"
            )
        print("  Link with: synlynk goal link <story-id> --goal <goal-id>\n")
        conn.close()
        raise SystemExit(1)
```

with:

```python
    from synlynk.governs_gate import pr_governs_linkage_violations
    from synlynk.policy_gates import _evaluate_gate, classify_governs_violations
    governs_violations = pr_governs_linkage_violations(conn, pr_number)
    governs_eval = _evaluate_gate(
        conn, pr_number=pr_number, gate="governs_authority",
        mode_key="require_linked_goal_mode",
        verdict=classify_governs_violations(governs_violations),
    )
    if governs_eval.verdict != "pass":
        label = "🚫 [PR CHECK BLOCKED]" if governs_eval.should_block else "⚠ [PR CHECK]"
        print(f"\n  {label} dispatched jobs missing linked GOVERNS story/goal: {governs_eval.message}")
        print("  Link with: synlynk goal link <story-id> --goal <goal-id>\n")
        if governs_eval.should_block:
            conn.close()
            raise SystemExit(1)
    else:
        print(f"  {_GREEN}✓{_RESET} GOVERNS linkage passed — {governs_eval.message}")
```

- [ ] **Step 4: Replace the cross-harness gate block in `cmd_pr_check()`**

Replace the (now shifted) lines matching:

```python
    if pr_number is not None:
        cross_harness_ok, cross_harness_message = _cross_harness_review_verdict(conn, pr_number)
        if not cross_harness_ok:
            conn.close()
            print(f"\n  🚫 [PR CHECK BLOCKED] Cross-harness review required: {cross_harness_message}\n")
            raise SystemExit(1)
        print(f"  {_GREEN}✓{_RESET} Cross-harness review passed — {cross_harness_message}")
```

with:

```python
    if pr_number is not None:
        from synlynk.policy_gates import classify_cross_harness_verdict
        cross_harness_ok, cross_harness_message = _cross_harness_review_verdict(conn, pr_number)
        cross_harness_eval = _evaluate_gate(
            conn, pr_number=pr_number, gate="cross_harness_review",
            mode_key="cross_harness_review_required_mode",
            verdict=classify_cross_harness_verdict(cross_harness_ok, cross_harness_message),
        )
        if cross_harness_eval.verdict != "pass":
            label = "🚫 [PR CHECK BLOCKED]" if cross_harness_eval.should_block else "⚠ [PR CHECK]"
            print(f"\n  {label} Cross-harness review required: {cross_harness_eval.message}\n")
            if cross_harness_eval.should_block:
                conn.close()
                raise SystemExit(1)
        else:
            print(f"  {_GREEN}✓{_RESET} Cross-harness review passed — {cross_harness_eval.message}")
```

Note `_evaluate_gate` is already imported from the GOVERNS block edit above (Step 3) — do not duplicate the import.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_agent_cli.py -v -k "governs_gate_observe or governs_gate_enforce or cross_harness_review"`
Expected: all PASS, including the pre-existing `test_pr_check_cross_harness_review_*` tests (unchanged — they test the verdict function directly, not `cmd_pr_check`).

- [ ] **Step 6: Run the full existing test_agent_cli.py suite to check for regressions**

Run: `pytest tests/test_agent_cli.py -v`
Expected: all PASS. If any pre-existing `cmd_pr_check`-level test now fails because it asserted a bare `SystemExit` for a condition that this repo's `.synlynk/policy.json` now defaults to observe mode, that test was implicitly relying on enforce-mode being the only behavior — update its policy.json fixture to pass `"require_linked_goal_mode": "enforce"` / `"cross_harness_review_required_mode": "enforce"` explicitly rather than changing the gate logic.

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py tests/test_agent_cli.py
git commit -m "$(cat <<'EOF'
feat(pr-check): route GOVERNS and cross-harness gates through _evaluate_gate()

Both gates now record a policy_gate_events row on every check and only
block the merge when their policy.json mode is "enforce" (the default).
This repo's own policy.json was already flipped to "observe" for both
gates in a prior commit on this branch.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 7: `synlynk policy gate-status` command

**Files:**
- Modify: `synlynk/policy_cli.py`
- Modify: `synlynk/cli.py:1482-1492` and `synlynk/cli.py:2734-2739`
- Test: `tests/test_policy_gates.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_policy_gates.py`:

```python
def test_cmd_policy_gate_status_reports_streak_and_threshold(tmp_path, monkeypatch, capsys):
    from synlynk.policy_cli import cmd_policy_gate_status

    monkeypatch.chdir(tmp_path)
    conn = _db_with_events(tmp_path, [
        (1, "governs_authority", "pass"),
        (2, "governs_authority", "pass"),
    ])
    conn.close()
    monkeypatch.setattr("synlynk.policy_cli._get_db", lambda: __import__("sqlite3").connect(tmp_path / "state.db"))

    exit_code = cmd_policy_gate_status()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "governs_authority" in out
    assert "streak: 2" in out
    assert "100" in out


def test_cmd_policy_gate_status_reports_no_data_for_unrecorded_gate(tmp_path, monkeypatch, capsys):
    from synlynk.migrations.runner import run_pending_migrations
    from synlynk.policy_cli import cmd_policy_gate_status
    import sqlite3

    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)
    conn.close()
    monkeypatch.setattr("synlynk.policy_cli._get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    exit_code = cmd_policy_gate_status()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "no data yet" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_policy_gates.py -v -k "gate_status"`
Expected: FAIL — `cmd_policy_gate_status` doesn't exist yet.

- [ ] **Step 3: Implement `cmd_policy_gate_status()`**

Edit `synlynk/policy_cli.py` — add the import and the new function:

```python
from synlynk import _get_db
from synlynk.policy_gates import RE_HARDEN_THRESHOLD, gate_streak

GATES = ("governs_authority", "cross_harness_review")


def cmd_policy_gate_status() -> int:
    """Print each observe-mode gate's current clean-pass streak.

    Crossing RE_HARDEN_THRESHOLD is a recommendation only — flipping a gate's
    *_mode back to "enforce" in .synlynk/policy.json remains a manual, reviewed
    edit (see docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md §3.4).
    """
    conn = _get_db()
    for gate in GATES:
        streak = gate_streak(conn, gate)
        if streak is None:
            print(f"  {gate}: no data yet")
            continue
        print(f"  {gate}: streak: {streak} / {RE_HARDEN_THRESHOLD}")
        if streak >= RE_HARDEN_THRESHOLD:
            print(f"    → {streak} consecutive clean passes. Consider flipping this gate's mode to \"enforce\" in .synlynk/policy.json.")
    conn.close()
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_policy_gates.py -v -k "gate_status"`
Expected: both PASS

- [ ] **Step 5: Wire the CLI subcommand**

In `synlynk/cli.py`, edit the `policy` parser block at line 1482-1492:

```python
    policy_parser = subparsers.add_parser("policy", help="Check policy authority")
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command")
    policy_subparsers.add_parser("show", help="Show the resolved policy")
    policy_check_merge_parser = policy_subparsers.add_parser(
        "check-merge", help="Check merge authority for a role per policy.json"
    )
    policy_check_merge_parser.add_argument(
        "--role", required=True, help="Role identity attempting to merge"
    )
    policy_sync_bp_parser = policy_subparsers.add_parser("sync-branch-protection", help="Configure GitHub branch protection from policy.json")
    policy_sync_bp_parser.add_argument("--dry-run", action="store_true")
    policy_subparsers.add_parser("gate-status", help="Show observe-mode gate streaks and the re-harden threshold")
```

In `synlynk/cli.py`, edit the dispatch chain at line 2734-2739:

```python
    elif args.command == "policy" and args.policy_command == "show":
        sys.exit(cmd_policy_show())
    elif args.command == "policy" and args.policy_command == "check-merge":
        sys.exit(cmd_policy_check_merge(role=args.role))
    elif args.command == "policy" and args.policy_command == "sync-branch-protection":
        sys.exit(cmd_policy_sync_branch_protection(dry_run=args.dry_run))
    elif args.command == "policy" and args.policy_command == "gate-status":
        sys.exit(cmd_policy_gate_status())
```

Find the existing import line for `synlynk.policy_cli` in `synlynk/cli.py` (search `from synlynk.policy_cli import`) and add `cmd_policy_gate_status` to it.

- [ ] **Step 6: Manually verify the CLI wiring**

Run: `python3 bin/synlynk.py policy gate-status`
Expected: `governs_authority: no data yet` and `cross_harness_review: no data yet` (no events recorded yet in this checkout's own `state.db`), exit code 0.

- [ ] **Step 7: Commit**

```bash
git add synlynk/policy_cli.py synlynk/cli.py tests/test_policy_gates.py
git commit -m "$(cat <<'EOF'
feat(cli): add synlynk policy gate-status command

Reports each observe-mode gate's consecutive clean-pass streak against
the 100-pass re-harden threshold. Recommendation only — flipping a
gate's mode back to enforce remains a manual policy.json edit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

### Task 8: Full-suite regression check and documentation touch-up

**Files:**
- Modify: `AI_INSTRUCTIONS.md` or wherever the Hardened PR Review Policy gate descriptions live (locate via `grep -rn "cross_harness_review_required\|require_linked_goal" --include=*.md .` from repo root), if that search finds a doc asserting these gates are unconditionally hard-fail.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: all tests PASS. If any test outside `tests/test_agent_cli.py` or `tests/test_policy_gates.py` fails, it's a regression from this plan's `db.py` edit (Task 6) — diagnose before proceeding; do not silence a failing test by deleting it.

- [ ] **Step 2: Search for stale "hard-fail only" doc claims**

Run: `grep -rln "cross_harness_review_required\|require_linked_goal" --include=*.md . | grep -v docs/superpowers`

For each file found (excluding the design spec and this plan itself), check whether it claims the gate is unconditionally hard-fail with no observe-mode mention. If so, add one sentence noting the gate can run in `observe` mode per `.synlynk/policy.json`'s `*_mode` field, pointing at `docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md`. Do not rewrite the whole section — a single added sentence per file is sufficient.

- [ ] **Step 3: Commit any doc touch-ups**

```bash
git add -A
git status --short  # confirm only the intended doc files changed
git commit -m "$(cat <<'EOF'
docs: note observe-mode option on GOVERNS/cross-harness gate docs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

If Step 2 found nothing to change, skip this commit.

- [ ] **Step 4: Open the PR**

```bash
git push -u origin docs/claude/policy-enforcement-maturity
gh pr create --title "feat(policy): observe-mode gates for GOVERNS and cross-harness review" --body "$(cat <<'EOF'
## Summary
- Adds `*_mode` fields (`enforce`|`observe`, default `enforce`) to `.synlynk/policy.json`'s `governs_authority` and `merge_authority` gates; this repo's own policy.json is set to `observe` for both, per gh:#1990/#1991/#2095 friction documented in the design spec.
- Every `synlynk pr check` run now records a `policy_gate_events` row per gate (migration 18), regardless of mode.
- `observe` mode prints the same diagnostic text but does not block `qa`'s merge; `enforce` mode is unchanged from current behavior.
- New `synlynk policy gate-status` command reports each gate's consecutive clean-pass streak against a 100-pass re-harden recommendation threshold.

## Test plan
- [ ] `pytest -v` passes in full
- [ ] `synlynk policy gate-status` runs cleanly against this repo's own state.db
- [ ] Manual: flip `.synlynk/policy.json`'s `require_linked_goal_mode` to `enforce` locally, confirm `pr check` still raises `SystemExit` on a real violation (no regression to existing enforce-mode behavior)

Design: docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md
Plan: docs/superpowers/plans/2026-10-07-policy-enforcement-maturity.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

Per PR Review Discipline: assign a non-authoring, cross-harness+model reviewer; the reviewer runs `synlynk pr check` from this PR's own worktree and merges alone.

---

## Self-Review Notes

- **Spec coverage:** §3.1 schema → Task 1. §3.2 table → Task 2. §3.3 `_evaluate_gate` wrapper → Tasks 3-6. §3.4 streak + `gate-status` → Tasks 5 and 7. §3.6 error handling (missing `*_mode` defaults to enforce; failed event write doesn't block) → Task 3 Step 3 (`gate_mode` default) and Task 4 Step 3 (`record_gate_event`'s try/except). §3.7 testing bullets → covered across Tasks 3-5's parametrized/streak tests. §4 non-goals (no fix to #2095/#2118/#2119, no GOVERNS-hard-fail implementation, no audit-log work, no automatic mode flip) — none of this plan's tasks touch those areas.
- **Placeholder scan:** the one intentional scaffolding placeholder (`test_gate_streak_resets_on_warn` empty function in Task 5) is explicitly called out with a deletion instruction in the same step — not a silent gap.
- **Type consistency:** `gate_mode(gate_section, mode_key)` signature is used identically in Task 3's tests, Task 5's `_evaluate_gate`, and Task 6's `db.py` call sites. `classify_cross_harness_verdict(ok, detail)` / `classify_governs_violations(violations)` signatures match between Task 4's definitions and Task 6's call sites. `_evaluate_gate(conn, *, pr_number, gate, mode_key, verdict)` keyword-only signature matches between Task 5's definition and Task 6's two call sites. `GateEvaluation.should_block`/`.verdict`/`.message` field names match between Task 5's dataclass and Task 6's usage.
