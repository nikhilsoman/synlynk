# Full-Fleet Operability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make fleet claims falsifiable: Core 4 + fail-closed doctor + `selftest --matrix` (dry then live) so Supported/Proven tiers are real, not marketing.

**Architecture:** Add `CORE_FLEET` / experimental membership in `_constants.py`. Extend `doctor` with fail-closed checks (instruction files, nested product `state.db`, TC-2/TC-3 drive exit 1; TC-5 warn-only for exit). Harden `_get_db` / a nested-DB detector so worktree product ledgers error. Replace terminal `UNKNOWN` job summaries with `FAILED_UNVERIFIED`. New dry/live matrix in `selftest` writing `fleet_matrix_runs`; `status` reads freshness for Proven (7 days). Live tier budget-capped at $10/week.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest, existing `synlynk` package (`doctor.py`, `selftest.py`, `jobs.py`, `dispatch.py`, `status.py`, `__init__.py` `_get_db`, `cli.py`).

**Spec:** `docs/superpowers/specs/2026-08-02-fleet-operability-design.md` (approved).

**Routing:** Python/CLI/tests → Codex (or Grok/Agy fallback). Docs-only bits can ride with code PRs.

---

## Spec coverage map

| Spec section | Tasks |
|--------------|-------|
| §3 Core 4 / local experimental / codex builder-only labels | T1, T8 |
| §3.3 Hard freeze | process (not code); note in status after T7 |
| §5.1 Doctor FAIL/WARN | T2 |
| §5.2 Canonical state.db refuse | T3 |
| §5.3 UNKNOWN ban | T4 |
| §5.4 Dispatch preflight | T9 |
| §4 Matrix dry + storage | T5, T6, T7 |
| §4 Matrix live + $10 budget + Proven 7d | T8, T10 |
| §7 S5 GH-write+grants | Out of plan (placeholder only) |

---

## File structure

| File | Responsibility |
|------|----------------|
| `synlynk/_constants.py` | `CORE_FLEET`, `EXPERIMENTAL_FLEET`, `PROVEN_FRESHNESS_DAYS`, `MATRIX_LIVE_BUDGET_USD`, codex builder-only claim flags |
| `synlynk/fleet.py` (new) | Nested state.db scan, matrix cell runners, budget, `fleet_matrix_runs` I/O, tier labels |
| `synlynk/doctor.py` | Fail-closed exit; instruction + nested DB checks; TC-5 does not fail exit |
| `synlynk/__init__.py` | `_get_db`: refuse nested product path when cwd is under a job worktree with alternate DB intent; export helpers if needed |
| `synlynk/jobs.py` | Never emit terminal `UNKNOWN (exit unknown)` — use `FAILED_UNVERIFIED` |
| `synlynk/dispatch.py` | `_write_job_summary` guard; preflight doctor FAIL block |
| `synlynk/selftest.py` | `run_matrix(dry/live)`, wire into `cmd_selftest` |
| `synlynk/cli.py` | `--matrix`, `--budget`; open/dispatch help text Core 4 |
| `synlynk/status.py` | Print Supported/Proven/Experimental from matrix + doctor |
| `synlynk/db.py` / `_migrate_db` | `fleet_matrix_runs` table |
| `tests/test_fleet_operability.py` (new) | Unit/integration for constants, doctor, nested DB, UNKNOWN, matrix dry |
| `tests/test_fleet_matrix_live.py` (new) | Live tier with mocked agents + budget abort |

---

## Task dependency graph

```
T1 constants + help text
  ├─→ T2 doctor fail-closed
  ├─→ T3 nested state.db refuse
  ├─→ T4 UNKNOWN ban
  └─→ T5 schema fleet_matrix_runs
        └─→ T6 dry matrix runner
              ├─→ T7 CLI --matrix + selftest wire
              ├─→ T8 status labels + codex builder-only display
              ├─→ T9 dispatch preflight doctor FAIL
              └─→ T10 live matrix + budget
```

**Parallel after T1:** T2, T3, T4, T5 (different files).  
**After T5+T6:** T7, T8, T9 can parallelize carefully.  
**T10 last** (depends on T6–T7).

---

### Task 1: Core fleet constants + help text

**Files:**
- Modify: `synlynk/_constants.py`
- Modify: `synlynk/cli.py` (open + dispatch agent help)
- Modify: `synlynk/dispatch.py` if agent list help string is duplicated
- Test: `tests/test_fleet_operability.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fleet_operability.py
from synlynk._constants import (
    CORE_FLEET,
    EXPERIMENTAL_FLEET,
    PROVEN_FRESHNESS_DAYS,
    MATRIX_LIVE_BUDGET_USD,
    AGENT_BUILDER_ONLY,
)


def test_core_fleet_is_four():
    assert CORE_FLEET == frozenset({"claude", "agy", "codex", "grok"})
    assert "local" in EXPERIMENTAL_FLEET
    assert "local" not in CORE_FLEET


def test_proven_and_budget_defaults():
    assert PROVEN_FRESHNESS_DAYS == 7
    assert MATRIX_LIVE_BUDGET_USD == 10.0


def test_codex_builder_only_flag():
    assert "codex" in AGENT_BUILDER_ONLY
```

- [ ] **Step 2: Run tests — expect fail (imports missing)**

```bash
pytest tests/test_fleet_operability.py::test_core_fleet_is_four -v
```

Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Add constants**

In `synlynk/_constants.py` (near `AGENT_CAPABILITY_BASELINES`):

```python
CORE_FLEET = frozenset({"claude", "agy", "codex", "grok"})
EXPERIMENTAL_FLEET = frozenset({"local"})
PROVEN_FRESHNESS_DAYS = 7
MATRIX_LIVE_BUDGET_USD = 10.0
# Agents that must not claim GH-write / package-install / heavy sandbox until matrix Proven
AGENT_BUILDER_ONLY = frozenset({"codex"})
CORE_INSTRUCTION_FILES = {
    "claude": "CLAUDE.md",
    "agy": "GEMINI.md",
    "codex": "AGENTS.md",
    "grok": "GROK.md",
}
```

- [ ] **Step 4: Update CLI help strings**

`synlynk/cli.py` open help:

```python
open_parser.add_argument(
    "agent",
    choices=sorted(CORE_FLEET),  # import CORE_FLEET
    help="Core fleet agent: claude, agy, codex, grok (local is experimental — not openable)",
)
```

Ensure `dispatch` agent `choices=` remains all baselines (including local for advanced) **or** document experimental still dispatchable with `--force-agent` — **decision for implementer:** keep dispatch accepting `local` but help epilog says experimental; open rejects local.

- [ ] **Step 5: Tests pass + commit**

```bash
pytest tests/test_fleet_operability.py -v
git add synlynk/_constants.py synlynk/cli.py tests/test_fleet_operability.py
git commit -m "feat: Core 4 fleet constants and open allowlist"
```

---

### Task 2: Doctor fail-closed (S1)

**Files:**
- Modify: `synlynk/doctor.py` (`cmd_doctor` ~468–600)
- Modify: `synlynk/probe.py` only if TC helpers need return shape tweaks
- Test: `tests/test_fleet_operability.py`

**Behaviour:**
- For each agent in `CORE_FLEET` (or `--agent` filter): missing `CORE_INSTRUCTION_FILES[agent]` → **FAIL** (exit contributes to 1).
- Nested product state.db under repo `worktrees/` or `.worktrees/` → **FAIL** (once per doctor run, not per agent).
- TC-2, TC-3 failures → **FAIL** (already in `all_passed`; keep).
- TC-5 failures → print ⚠ but **do not** set `any_failed` from TC-5 alone.
- Experimental agents (`local`): still probed if no filter, but missing instruction is not a Core FAIL; TC-1/TC-3 failures still fail doctor when local is included — OK.

- [ ] **Step 1: Failing tests**

```python
import os
from pathlib import Path
from unittest.mock import patch

from synlynk.doctor import cmd_doctor
from synlynk import doctor as doctor_mod


def test_doctor_fails_on_missing_core_instruction(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # no AGENTS.md
    (tmp_path / "CLAUDE.md").write_text("x")
    (tmp_path / "GEMINI.md").write_text("x")
    (tmp_path / "GROK.md").write_text("x")
    monkeypatch.setattr(doctor_mod, "AGENT_CAPABILITY_BASELINES", {
        "codex": {
            "cli": "codex",
            "dispatch_flags": {"valid_flags": [], "invalid_flags": [], "required_flags": []},
            "network_deps": {"required_endpoints": []},
            "headless_contract": {},
        }
    })
    # stub TCs pass except instruction
    with patch.object(doctor_mod, "_pkg") as pkg:
        # minimal: call helper once implemented
        from synlynk.fleet import check_core_instruction_files
        missing = check_core_instruction_files(tmp_path, agents=["codex"])
        assert "codex" in missing


def test_doctor_tc5_does_not_fail_exit_alone(monkeypatch):
    """Document expected: any_failed ignores tc5 when other TCs pass."""
    # Implement as unit test of severity aggregation helper
    from synlynk.fleet import doctor_hard_fail

    assert doctor_hard_fail(
        tc_results={"tc2": True, "tc3": True, "tc5": False},
        missing_instructions=[],
        nested_state_dbs=[],
    ) is False
    assert doctor_hard_fail(
        tc_results={"tc2": False, "tc3": True, "tc5": True},
        missing_instructions=[],
        nested_state_dbs=[],
    ) is True
    assert doctor_hard_fail(
        tc_results={"tc2": True, "tc3": True, "tc5": True},
        missing_instructions=["codex"],
        nested_state_dbs=[],
    ) is True
```

- [ ] **Step 2: Implement helpers in `synlynk/fleet.py`**

```python
# synlynk/fleet.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Sequence

from synlynk._constants import CORE_FLEET, CORE_INSTRUCTION_FILES


def check_core_instruction_files(
    root: str | Path, agents: Iterable[str] | None = None
) -> List[str]:
    root = Path(root)
    agents = list(agents) if agents is not None else sorted(CORE_FLEET)
    missing = []
    for agent in agents:
        if agent not in CORE_FLEET:
            continue
        rel = CORE_INSTRUCTION_FILES.get(agent)
        if not rel:
            continue
        if not (root / rel).is_file():
            missing.append(agent)
    return missing


def find_nested_product_state_dbs(root: str | Path) -> List[str]:
    """Paths under worktrees that look like product ledgers (not #650 intentional empty)."""
    root = Path(root)
    hits = []
    for base in ("worktrees", ".worktrees", ".claude/worktrees"):
        d = root / base
        if not d.is_dir():
            continue
        for p in d.rglob("state.db"):
            # product marker: sibling of .synlynk or path contains .synlynk
            parts = set(p.parts)
            if ".synlynk" in parts or p.parent.name == ".synlynk":
                hits.append(str(p))
    return hits


def doctor_hard_fail(
    *,
    tc_results: dict,
    missing_instructions: Sequence[str],
    nested_state_dbs: Sequence[str],
) -> bool:
    if missing_instructions or nested_state_dbs:
        return True
    if not tc_results.get("tc2", True):
        return True
    if not tc_results.get("tc3", True):
        return True
    # tc5 intentionally ignored for hard fail
    return False
```

- [ ] **Step 3: Wire into `cmd_doctor`**

After running TCs per agent, compute:

```python
from synlynk.fleet import (
    check_core_instruction_files,
    find_nested_product_state_dbs,
    doctor_hard_fail,
)

missing_instr = check_core_instruction_files(".", agents=agents)
nested = find_nested_product_state_dbs(".")
# print FAIL lines for missing_instr / nested
hard = doctor_hard_fail(
    tc_results={"tc2": tc2["passed"], "tc3": tc3["passed"], "tc5": tc5["passed"]},
    missing_instructions=missing_instr if agent in CORE_FLEET else [],
    nested_state_dbs=nested,
)
# any_failed |= hard for core agents
# IMPORTANT: do not use `all_passed = ... and tc5["passed"]` for exit code.
# Keep printing TC-5 as ⚠ when missing sections.
```

At end of `cmd_doctor`, return `1 if any_failed else 0` (already does via health checks path — ensure agent loop sets exit).

- [ ] **Step 4: pytest + commit**

```bash
pytest tests/test_fleet_operability.py -v
git add synlynk/fleet.py synlynk/doctor.py tests/test_fleet_operability.py
git commit -m "feat(doctor): fail-closed instruction, nested DB, TC-2/3; TC-5 warn-only"
```

---

### Task 3: Refuse nested product state.db (S2a)

**Files:**
- Modify: `synlynk/__init__.py` `_get_db` (~1003)
- Modify: `synlynk/fleet.py` (shared detector already from T2)
- Test: `tests/test_fleet_operability.py`

**Behaviour:**
- Canonical path remains `DB_PATH` from `_resolve_db_path()`.
- If `DB_PATH` resolves inside a repo worktree’s `.synlynk/` **and** a canonical home path exists/usable, prefer canonical (existing design).
- New: if code would open `cwd/.synlynk/state.db` as product ledger **while** nested under `worktrees/` and home path is writable → **raise** `RuntimeError` / `OSError` with message pointing at #330 / fleet design — **except** when primary open failed with OSError/OperationalError and we are in the #650 sandbox fallback (print warning; empty local OK).

Algorithm refinement for `_get_db`:

```python
def _is_nested_worktree_state_path(path: str) -> bool:
    norm = os.path.abspath(path)
    return any(seg in norm for seg in ("/worktrees/", "/.worktrees/", "/.claude/worktrees/"))

# On successful open of fallback_path:
if tried_fallback and _is_nested_worktree_state_path(db_path):
    # only allowed when primary failed for sandbox reasons (already tried_fallback)
    pass  # #650
# If primary DB_PATH itself is nested worktree path (misconfigured), refuse:
if _is_nested_worktree_state_path(DB_PATH) and not os.environ.get("SYNLYNK_ALLOW_NESTED_STATE"):
    # if home-canonical would differ, error
    ...
```

Keep it simple for tests:

```python
def test_refuse_opening_nested_product_db_when_home_writable(tmp_path, monkeypatch):
    from synlynk.fleet import assert_not_nested_product_ledger
    nested = tmp_path / "worktrees" / "job-x" / ".synlynk" / "state.db"
    nested.parent.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="nested product state"):
        assert_not_nested_product_ledger(str(nested), home_writable=True)
```

```python
def assert_not_nested_product_ledger(path: str, *, home_writable: bool) -> None:
    if home_writable and _is_nested_worktree_state_path(path):
        raise RuntimeError(
            f"nested product state.db refused ({path}); use canonical ~/.synlynk/projects/<key>/state.db"
        )
```

Call from `_get_db` before `connect` when `not tried_fallback` and path is nested.

- [ ] **Step: tests, implement, commit**

```bash
git commit -m "fix: refuse nested product state.db when home ledger is usable"
```

---

### Task 4: Ban UNKNOWN as terminal status (S2b)

**Files:**
- Modify: `synlynk/jobs.py` (all `summary_status = "UNKNOWN (exit unknown)"` → `FAILED_UNVERIFIED`)
- Modify: `synlynk/dispatch.py` `_write_job_summary` / `_format_job_summary` if UNKNOWN can be synthesized from bare exit_code
- Test: `tests/test_fleet_operability.py` or extend existing jobs tests

- [ ] **Step 1: Test**

```python
def test_no_unknown_terminal_label_helper():
    from synlynk.fleet import terminal_status_label
    assert terminal_status_label(exit_code=None, job_status="unknown") == (
        "FAILED_UNVERIFIED (exit unknown)"
    )
    assert "UNKNOWN" not in terminal_status_label(exit_code=None, job_status="unknown")
```

```python
def terminal_status_label(*, exit_code, job_status: str) -> str:
    if job_status == "unknown" or exit_code in (None, -1) and job_status not in ("completed", "failed"):
        return "FAILED_UNVERIFIED (exit unknown)"
    ...
```

- [ ] **Step 2: Replace string literals in `jobs.py`**

Every:

```python
summary_status = "UNKNOWN (exit unknown)"
```

becomes:

```python
summary_status = "FAILED_UNVERIFIED (exit unknown)"
```

And set note if missing: `"job ended without a verified exit code — inspect worktree before trusting success"`.

- [ ] **Step 3: `_write_job_summary` guard**

In `dispatch.py`, treat existing OK vs new FAILED_UNVERIFIED same as OK vs UNKNOWN (do not downgrade OK).

```python
if existing_status == "OK (exit 0)" and new_status and new_status.startswith("FAILED_UNVERIFIED"):
    return existing_summary
if existing_status == "OK (exit 0)" and new_status == "UNKNOWN (exit unknown)":
    return existing_summary  # keep for old summaries
```

- [ ] **Step 4: commit**

```bash
git commit -m "fix: ban UNKNOWN terminal job status; use FAILED_UNVERIFIED"
```

---

### Task 5: Schema `fleet_matrix_runs`

**Files:**
- Modify: migration site used by `_migrate_db` / `synlynk/db.py` (follow existing pattern from capability tables)
- Test: `tests/test_fleet_operability.py`

```sql
CREATE TABLE IF NOT EXISTS fleet_matrix_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tier INTEGER NOT NULL,
    home TEXT NOT NULL,
    cell TEXT NOT NULL,
    status TEXT NOT NULL,  -- green|red|incomplete|na
    detail TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fleet_matrix_runs_lookup
    ON fleet_matrix_runs(home, cell, tier, ts);
```

- [ ] **Step 1: Test table exists after `_get_db()` / `_migrate_db`**

```python
def test_fleet_matrix_runs_table(project_dir):
    from synlynk import _get_db
    conn = _get_db()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fleet_matrix_runs)").fetchall()}
    assert {"run_id", "tier", "home", "cell", "status", "detail", "cost_usd", "ts"} <= cols
    conn.close()
```

- [ ] **Step 2: Add to schema migration string / executescript**

- [ ] **Step 3: commit**

```bash
git commit -m "feat(db): fleet_matrix_runs table for operability matrix"
```

---

### Task 6: Dry matrix runner (S3 core)

**Files:**
- Modify: `synlynk/fleet.py`
- Test: `tests/test_fleet_operability.py`

- [ ] **Step 1: API**

```python
@dataclass
class MatrixCellResult:
    home: str
    cell: str
    tier: int
    status: str  # green|red|incomplete|na
    detail: str = ""
    cost_usd: float = 0.0


def run_matrix_dry(root: str = ".") -> list[MatrixCellResult]:
    """Tier-1 cells for each home in CORE_FLEET."""
    ...
```

Dry cells per home (minimum set for Phase 1):

| cell | check |
|------|--------|
| `instruction` | file exists |
| `doctor_tc2` | `_run_tc2` passed (may mock in unit tests) |
| `doctor_tc3` | `_run_tc3` for required endpoints |
| `nested_state` | no nested product DBs under root |
| `dispatch_dry` | agent in baselines + non_interactive_flags listable |
| `codex_builder_only` | for home=codex, cell GH-write = `na` |

- [ ] **Step 2: Persist**

```python
def record_matrix_run(conn, run_id: str, results: list[MatrixCellResult]) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for r in results:
        conn.execute(
            "INSERT INTO fleet_matrix_runs (run_id, tier, home, cell, status, detail, cost_usd, ts) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, r.tier, r.home, r.cell, r.status, r.detail, r.cost_usd, ts),
        )
    conn.commit()
```

- [ ] **Step 3: Tests with tmp_path fixtures + mocked TC helpers**

```python
def test_run_matrix_dry_marks_missing_instruction_red(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("CLAUDE.md", "GEMINI.md", "GROK.md"):
        (tmp_path / name).write_text("ok")
    # no AGENTS.md
    from synlynk.fleet import run_matrix_dry
    results = run_matrix_dry(str(tmp_path))
    codex_instr = [r for r in results if r.home == "codex" and r.cell == "instruction"]
    assert codex_instr and codex_instr[0].status == "red"
```

- [ ] **Step 4: commit**

```bash
git commit -m "feat: dry fleet matrix runner and persistence"
```

---

### Task 7: CLI `selftest --matrix`

**Files:**
- Modify: `synlynk/cli.py` argparse + dispatch
- Modify: `synlynk/selftest.py` `cmd_selftest` signature

- [ ] **Step 1: CLI flags**

```python
selftest_parser.add_argument("--matrix", action="store_true",
    help="Run fleet operability matrix (dry by default)")
selftest_parser.add_argument("--budget", type=float, default=None,
    help="Live matrix budget USD (default 10 when --matrix --live)")
```

- [ ] **Step 2: `cmd_selftest(live=False, matrix=False, budget=None)`**

```python
def cmd_selftest(live: bool = False, matrix: bool = False, budget: float | None = None) -> int:
    if matrix:
        from synlynk.fleet import run_matrix_dry, run_matrix_live, record_matrix_run, new_run_id
        from synlynk import _get_db
        run_id = new_run_id()
        results = run_matrix_dry(".")
        if live:
            cap = budget if budget is not None else MATRIX_LIVE_BUDGET_USD
            results.extend(run_matrix_live(".", budget_usd=cap))
        conn = _get_db()
        record_matrix_run(conn, run_id, results)
        conn.close()
        # print table; return 1 if any red at tier 1
        reds = [r for r in results if r.status == "red" and r.tier == 1]
        ...
        return 1 if reds else 0
    return existing_path(...)
```

Wire `cli.py` main branch for selftest to pass `matrix=` and `budget=`.

- [ ] **Step 3: Test parser**

```python
def test_selftest_matrix_flag_parsed():
    from synlynk.cli import build_parser
    args = build_parser().parse_args(["selftest", "--matrix"])
    assert args.matrix is True
```

- [ ] **Step 4: commit**

```bash
git commit -m "feat: synlynk selftest --matrix CLI entrypoint"
```

---

### Task 8: Status Supported / Proven labels

**Files:**
- Modify: `synlynk/status.py`
- Modify: `synlynk/fleet.py` (`tier_for_agent`)

```python
def tier_for_agent(conn, agent: str, now=None) -> str:
    """Return experimental|unsupported|supported|proven."""
    if agent in EXPERIMENTAL_FLEET:
        return "experimental"
    if agent not in CORE_FLEET:
        return "unsupported"
    # latest dry red for agent → unsupported
    # else if live green within PROVEN_FRESHNESS_DAYS → proven
    # else supported
```

Print a small table in `cmd_status` (platform or ecosystem path — pick the human dashboard path that already lists harnesses).

- [ ] **Tests** with seeded `fleet_matrix_runs` rows

- [ ] **commit**

```bash
git commit -m "feat(status): Supported/Proven/Experimental fleet tier labels"
```

---

### Task 9: Dispatch preflight on doctor FAIL (#112)

**Files:**
- Modify: `synlynk/dispatch.py` near existing TC-2 preflight (~1477)

- [ ] Before spawn, for Core 4 targets: if last harness_records compliance is degraded **or** quick `check_core_instruction_files` fails → raise/exit unless `force_agent`.

Keep existing TC-2 probe path; add instruction missing + document.

```python
def test_preflight_blocks_missing_instruction(monkeypatch, tmp_path):
    # unit-test the pure helper used by dispatch
    from synlynk.fleet import preflight_blocks_dispatch
    assert preflight_blocks_dispatch(
        agent="codex",
        missing_instructions=["codex"],
        force_agent=False,
    )
    assert not preflight_blocks_dispatch(
        agent="codex",
        missing_instructions=["codex"],
        force_agent=True,
    )
```

- [ ] **commit**

```bash
git commit -m "feat(dispatch): fail-closed preflight for Core 4 doctor hard fails"
```

---

### Task 10: Live matrix + budget (S4)

**Files:**
- Modify: `synlynk/fleet.py` `run_matrix_live`
- Test: `tests/test_fleet_matrix_live.py`

**Behaviour:**
- For each home×target in CORE_FLEET×CORE_FLEET (or home×target where target is headless worker): run a **mocked** trivial agent in unit tests; real `dispatch` only under `--live` manual.
- Track `spent`; if next cell would exceed budget → mark remaining `incomplete`, stop.
- Codex×GH-write cells → `na` while `codex in AGENT_BUILDER_ONLY`.
- Live cell green requires: mocked exit 0 + not UNKNOWN status + cost_usd recorded (0.0 allowed with detail `zero_cost_mock`).

```python
def test_live_matrix_budget_abort():
    from synlynk.fleet import run_matrix_live
    calls = {"n": 0}
    def fake_dispatch(...):
        calls["n"] += 1
        return MatrixCellResult(..., cost_usd=6.0, status="green")
    results = run_matrix_live(".", budget_usd=10.0, dispatch_fn=fake_dispatch)
    # first cell 6, second 6 would exceed → incomplete
    assert any(r.status == "incomplete" for r in results)
```

Default live cell set for Phase 2: **one trivial self-dispatch per Core 4 agent** (4 cells) before full 4×4 — document in code comment to control cost. Spec allows full grid; implement **4 self-dispatch cells first** (home=target) to stay under $10; expand later.

- [ ] **commit**

```bash
git commit -m "feat: live fleet matrix with $10/week budget hard stop"
```

---

### Task 11: Docs + design status (S1–S4 wrap)

**Files:**
- Modify: `docs/superpowers/specs/2026-08-02-fleet-operability-design.md` status → Implemented (as PRs land)
- Optional: CHANGELOG under next release notes (not a named release alone)

- [ ] Note hard freeze process in PR templates or CONTRIBUTING one-liner if exists; else skip.

- [ ] **commit**

```bash
git commit -m "docs: mark fleet operability phases as landing"
```

---

## Out of plan (Phase 3 — S5)

Do **not** implement in this plan:

- Full Core 4 GH-write / role tokens epic  
- Grants for all Core 4  
- Native harness go/no-go  

After first Proven week of live matrix data, open a **new** design+plan for S5.

---

## Self-review (plan author)

| Spec requirement | Task |
|------------------|------|
| Supported/Proven/Experimental | T1, T8 |
| Core 4, local experimental | T1 |
| Codex builder-only | T1, T6/T10 `na` cells |
| Hard freeze | process + T11 note |
| Doctor FAIL set | T2 |
| Nested DB refuse | T3 |
| UNKNOWN ban | T4 |
| Dispatch preflight | T9 |
| Dry matrix + table | T5–T7 |
| Live + $10 + 7d Proven | T8, T10 |
| S5 GH/grants | excluded by design |

No TBD steps; live grid intentionally scoped to 4 self-dispatch cells for budget safety (spec-compatible minimum).

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-08-02-fleet-operability.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session with executing-plans checkpoints  

Which approach?
