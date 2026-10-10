# Status Writer Inventory & Canonical Enum (Phase 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a committed, self-verifying inventory of every place the codebase writes a job-completion status value, and a canonical enum + alias map that every one of those values resolves to — with zero change to runtime behavior. This is Phase 0 of amending PR #1949 per the 2026-10-03 decide panel (dec-5d37b005): it makes the current naming mess visible and classified so the oracle rewrite itself (causal attribution, evidence ranking, state machine) can be specified against solid ground in a later plan.

**Architecture:** Three new artifacts, built in this order because the spec requires it: (1) a committed inventory data file listing every job-status write call site, classified as `literal` / `dynamic` / `dynamic: unresolved`; (2) a canonical status enum + alias map derived from reading what the inventory actually found; (3) a test that re-scans the codebase at test time, diffs against the committed inventory (catching undocumented new writers), and asserts every inventoried value resolves to canonical-or-alias. No existing code path changes what it writes — only what a reviewer/consumer can call it.

**Tech Stack:** Python 3 stdlib only (this project has no other runtime deps), `pytest`, `grep`/`ast` for the scan.

---

## Scope note (read before starting)

**"Status" in this plan means job-completion status only** — the values written to the
`daemon_jobs` table's `status` column, and the richer verification/decision-status vocabulary in
`synlynk/job_truth.py` and `synlynk/jobs.py` that feeds into it (e.g. `failed_verification`,
`circuit_breaker_tripped`, `gh_write_verified`). It does NOT mean every column named `status`
anywhere in the schema. A pre-flight grep for this plan found unrelated `status` columns on
`stories`, `worktree_leases`, `approval_tickets`, `sessions`, `backlog_items`, and
`harness_reservations` (`synlynk/board.py`, `synlynk/worktree_lease.py`, `synlynk/events.py`,
`synlynk/db.py`, `synlynk/quota.py`, `synlynk/backlog.py`) — these are separate domains (story
readiness, lease lifecycle, ticket consumption, etc.) and are **out of scope**. Do not include
them in the inventory. If you're unsure whether a hit belongs, check whether it's writing to
`daemon_jobs` or to the job-truth/decision machinery in `job_truth.py`/`jobs.py`/`dispatch.py` —
if not, it's out of scope.

Primary scan targets, confirmed via grep during planning (`synlynk/dispatch.py`,
`synlynk/jobs.py`, `synlynk/job_truth.py`, `synlynk/testbed/state_db_soak.py` all write to
`daemon_jobs.status`), but **do not limit the scan to only these files** — Task 1 Step 1 re-runs
the scan across the whole `synlynk/` tree so nothing is missed by assumption.

---

### Task 1: Build the status-writer inventory

**Files:**
- Create: `synlynk/_status_writer_inventory.py`

- [ ] **Step 1: Run the scan**

Run these three greps from the repo root and capture the combined output — this is the raw
candidate list you'll classify in Step 2:

```bash
grep -rn "daemon_jobs SET status" synlynk/ --include="*.py"
grep -rn "\.status\s*=\s*['\"]" synlynk/ --include="*.py"
grep -rnE "def (update_.*status|set_.*status|_mark_[a-z_]*job)" synlynk/ --include="*.py"
```

Also search `synlynk/job_truth.py`, `synlynk/jobs.py`, and `synlynk/dispatch.py` specifically for
string literals that look like status/decision values (the planning pre-flight found a long list
concentrated in these three files — values like `failed_verification`, `circuit_breaker_tripped`,
`gh_write_verified`, `task_delivery_failed`, `failed_noop_denied`, `permission_denied`,
`verified`, `unknown`, `unknown_contract`, `succeeded_gh_write_failed`, `failed_unverified`,
`pending_verification`, `done`, `running`, `queued`, `cancelled`, `timeout`). Use:

```bash
grep -noE "\"[a-z_]+\"" synlynk/job_truth.py synlynk/jobs.py synlynk/dispatch.py | sort -u
```

and manually read each hit in context to decide: is this string actually assigned to or compared
against a job-status/decision field, or is it an unrelated literal (a log message, a key name, a
config value)? Discard anything that isn't a status/decision value assignment.

For every remaining hit, record the file and line number where it's assigned (not just compared).

- [ ] **Step 2: Classify every hit**

For each call site found in Step 1, decide one of three classifications:

- **`literal`** — the status value being written is a string literal right there at the write
  site (e.g. `"UPDATE daemon_jobs SET status='running', ..."`). Record the exact string.
- **`dynamic`** — the value is a variable, parameter, or expression (e.g.
  `"UPDATE daemon_jobs SET status=?, ..."` with `(decision.status, ...)` bound later, or
  `status = compute_result()`). Read the surrounding function to trace where that variable's
  value actually comes from, and manually write out every literal value it can take. If the
  function has an early return or multiple branches, you must trace all of them — don't guess
  that a `dynamic` site only has the values you've seen once.
- **`dynamic: unresolved`** — the value truly cannot be enumerated by reading the code (e.g. it's
  built from fully runtime/unbounded input, or passed in from a caller several layers away that
  you cannot trace in a reasonable amount of time). Write a one-line reason. These require extra
  handling in Task 3 — don't classify something `dynamic: unresolved` just because tracing it is
  mildly annoying; only use it when genuinely unenumerable.

- [ ] **Step 3: Write the inventory file**

Create `synlynk/_status_writer_inventory.py` with one entry per call site found in Steps 1-2.
Structure it as a list of dicts so Task 3's test can iterate it directly:

```python
"""Committed inventory of every job-completion status write site in synlynk.

Built by re-running the scan described in docs/superpowers/plans/2026-10-11-status-writer-inventory.md
Task 1. Do not hand-edit entries without re-verifying against the actual source line — this file
is diffed against a live re-scan by tests/test_status_writer_inventory.py, so an out-of-date entry
will cause a spurious or missed test failure.

kind: "literal" | "dynamic" | "dynamic_unresolved"
"""

STATUS_WRITER_INVENTORY = [
    {
        "file": "synlynk/dispatch.py",
        "line": 863,
        "kind": "literal",
        "values": ["queued"],
        "writer": "dispatch_agent",
    },
    {
        "file": "synlynk/job_truth.py",
        "line": 331,
        "kind": "dynamic",
        "values": ["<fill in from tracing decision.status in Task 1 Step 2>"],
        "writer": "apply_job_decision",
    },
    # ... one entry per call site found in Step 1, fully filled in with real
    # values traced in Step 2. Do not leave any entry with a placeholder value —
    # every "values" list must contain the actual literal strings you traced.
]
```

The example above shows the shape only — `job_truth.py:331`'s actual `values` list must be filled
in with the real strings traced from `decision.status`'s call sites, not left as the placeholder
shown. Every entry in the real file must have concrete, traced values.

For any `dynamic_unresolved` entry, add a `"reason"` key instead of a complete `values` list:

```python
    {
        "file": "synlynk/some_file.py",
        "line": 123,
        "kind": "dynamic_unresolved",
        "reason": "value is forwarded from an external CLI's stdout parse with no closed vocabulary",
        "writer": "some_function",
    },
```

- [ ] **Step 4: Commit**

```bash
git add synlynk/_status_writer_inventory.py
git commit -m "feat(status): add status-writer inventory data file

Co-Authored-By: <harness attribution per CLAUDE.md>"
```

---

### Task 2: Derive the canonical enum and alias map

**Files:**
- Create: `synlynk/status_enum.py`

- [ ] **Step 1: List every distinct value across the inventory**

Read through `synlynk/_status_writer_inventory.py` and list every distinct string across all
`values` lists (ignore `dynamic_unresolved` entries — they have no values list). This is your
complete vocabulary to classify.

- [ ] **Step 2: Decide canonical members vs. aliases**

For each distinct value, decide: is it a true synonym of another value already on your canonical
list (becomes an alias), or does it represent a state no canonical member yet covers (becomes a
new canonical member)?

Default to **not** collapsing two values unless you can point to code showing they're handled
identically everywhere they're checked (e.g. grep every `if status == "x"` / `if status == "y"`
site and confirm the surrounding logic treats them the same way). In particular, do not assume
`failed_noop_denied` and `circuit_breaker_tripped` are the same thing without checking — the
2026-10-03 decide panel's RCA trail indicates they're genuinely different failure classes (a
denied no-op action vs. a circuit breaker killing a live process).

- [ ] **Step 3: Write the enum + alias map**

```python
"""Canonical job-completion status enum + alias map for legacy status strings.

Phase 0 of amending PR #1949 (dec-5d37b005, 2026-10-03 decide panel). This module defines
*names only* — it does not change what any existing code path writes. See
docs/superpowers/specs/2026-10-11-status-writer-inventory-design.md.
"""

from enum import Enum


class CanonicalJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    UNKNOWN = "unknown"
    FAILED = "failed"
    # ... add every canonical member you decided on in Step 2. Each member's
    # value should be the string you consider canonical (often the most common
    # or most descriptive of the synonymous spellings it represents).


# Maps a legacy/alias string (as actually found in the inventory) to the
# CanonicalJobStatus member it's a synonym of. Every key here MUST be a string
# that appears in some inventory entry's `values` list, and every value MUST
# be a CanonicalJobStatus member — the test in Task 3 enforces both directions.
STATUS_ALIAS_MAP: dict[str, CanonicalJobStatus] = {
    # Example — replace with your real decisions from Step 2:
    # "failed_unverified": CanonicalJobStatus.FAILED,  # reason: both land in the
    #   same "job did not complete and no verified effect exists" bucket, confirmed
    #   by reading synlynk/jobs.py:3596-3601 where both are handled by the same
    #   `if status in ("failed", "failed_unverified"):` branch.
}
```

Every alias decision must carry an inline comment explaining the reasoning (as shown in the
example), citing the file:line evidence you used to confirm it's a true synonym. If you decided a
value is NOT an alias of anything, it becomes its own `CanonicalJobStatus` member instead — do not
leave any inventoried value unaccounted for in either the enum or the alias map.

- [ ] **Step 4: Commit**

```bash
git add synlynk/status_enum.py
git commit -m "feat(status): add canonical status enum and alias map

Co-Authored-By: <harness attribution per CLAUDE.md>"
```

---

### Task 3: Write the self-verifying test

**Files:**
- Create: `tests/test_status_writer_inventory.py`

- [ ] **Step 1: Write the test**

```python
"""Verifies the status-writer inventory stays honest and every inventoried
value resolves to a canonical status or a documented alias.

Phase 0 of amending PR #1949 (dec-5d37b005). See
docs/superpowers/specs/2026-10-11-status-writer-inventory-design.md.
"""

import re
import subprocess

import pytest

from synlynk._status_writer_inventory import STATUS_WRITER_INVENTORY
from synlynk.status_enum import CanonicalJobStatus, STATUS_ALIAS_MAP

# Call sites that are deliberately unresolved (see spec Design §2). Adding an
# entry to synlynk/_status_writer_inventory.py with kind "dynamic_unresolved"
# requires also adding its (file, line) here — this is what stops someone from
# silently dodging classification.
ALLOWED_UNRESOLVED = {
    # ("synlynk/some_file.py", 123),
}


def _canonical_values() -> set[str]:
    return {member.value for member in CanonicalJobStatus}


def _resolvable_values() -> set[str]:
    return _canonical_values() | set(STATUS_ALIAS_MAP.keys())


def test_alias_map_targets_are_all_canonical():
    for alias, target in STATUS_ALIAS_MAP.items():
        assert isinstance(target, CanonicalJobStatus), (
            f"alias {alias!r} maps to {target!r}, which is not a CanonicalJobStatus member"
        )


def test_every_literal_inventory_value_resolves():
    resolvable = _resolvable_values()
    for entry in STATUS_WRITER_INVENTORY:
        if entry["kind"] != "literal":
            continue
        for value in entry["values"]:
            assert value in resolvable, (
                f"{entry['file']}:{entry['line']} writes unresolved status {value!r} "
                f"(not in CanonicalJobStatus and not in STATUS_ALIAS_MAP)"
            )


def test_every_dynamic_inventory_value_resolves():
    resolvable = _resolvable_values()
    for entry in STATUS_WRITER_INVENTORY:
        if entry["kind"] != "dynamic":
            continue
        for value in entry["values"]:
            assert value in resolvable, (
                f"{entry['file']}:{entry['line']} ({entry['writer']}) can write unresolved "
                f"status {value!r} (not in CanonicalJobStatus and not in STATUS_ALIAS_MAP)"
            )


def test_unresolved_entries_are_explicitly_allowlisted():
    for entry in STATUS_WRITER_INVENTORY:
        if entry["kind"] != "dynamic_unresolved":
            continue
        key = (entry["file"], entry["line"])
        assert key in ALLOWED_UNRESOLVED, (
            f"{entry['file']}:{entry['line']} is marked dynamic_unresolved but is not in "
            f"ALLOWED_UNRESOLVED in tests/test_status_writer_inventory.py — add it explicitly "
            f"to acknowledge the gap, per the design spec's anti-silent-dodge requirement"
        )
    for file, line in ALLOWED_UNRESOLVED:
        matching = [
            e for e in STATUS_WRITER_INVENTORY
            if e["file"] == file and e["line"] == line and e["kind"] == "dynamic_unresolved"
        ]
        assert matching, (
            f"ALLOWED_UNRESOLVED lists {file}:{line} but no matching dynamic_unresolved "
            f"inventory entry exists — remove the stale allowlist entry"
        )


def _rescan_daemon_jobs_sql_sites() -> set[tuple[str, int]]:
    """Re-run the SQL-write half of the Task 1 scan and return (file, line) pairs."""
    result = subprocess.run(
        ["grep", "-rn", "daemon_jobs SET status", "synlynk/", "--include=*.py"],
        capture_output=True, text=True, check=False,
    )
    found = set()
    for raw_line in result.stdout.splitlines():
        if not raw_line.strip():
            continue
        path, lineno, _ = raw_line.split(":", 2)
        found.add((path, int(lineno)))
    return found


def test_inventory_covers_every_current_daemon_jobs_sql_write():
    """Catches a new daemon_jobs status write added without updating the inventory.

    This only re-checks the SQL-write half of the scan (the part that's cheaply
    and reliably re-derivable with grep); the broader literal/helper-function
    scan from Task 1 Step 1 is not re-run here since it requires human judgment
    to filter false positives, same as it did when the inventory was built.
    """
    rescanned = _rescan_daemon_jobs_sql_sites()
    inventoried = {(e["file"], e["line"]) for e in STATUS_WRITER_INVENTORY}
    missing = rescanned - inventoried
    assert not missing, (
        f"Found daemon_jobs status write(s) not in synlynk/_status_writer_inventory.py: "
        f"{sorted(missing)}. Add them to the inventory (see Task 1 of "
        f"docs/superpowers/plans/2026-10-11-status-writer-inventory.md) before this test can pass."
    )
```

- [ ] **Step 2: Run it, confirm it fails for the right reason (if run before Tasks 1-2) or passes (if run after)**

Run: `pytest tests/test_status_writer_inventory.py -v`

If you're doing Task 3 after Tasks 1-2 are already committed (the normal order), expected:
`PASS` on all 5 tests. If any test fails, the failure message tells you exactly which inventory
entry or alias-map entry is incomplete — go back and fix Task 1 or Task 2's file, don't weaken
the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_status_writer_inventory.py
git commit -m "test(status): add self-verifying status-writer inventory test

Co-Authored-By: <harness attribution per CLAUDE.md>"
```

---

### Task 4: Full regression check

- [ ] **Step 1: Run the full suite**

Run: `pytest -x`

Expected: every test that passed before this plan's changes still passes; the only new passing
test is the 5 tests in `tests/test_status_writer_inventory.py`. No existing test's expected
outcome should change — this plan makes zero runtime behavior changes, only adds new files.

- [ ] **Step 2: If anything unrelated fails**

Stop and check whether the failure pre-dates this work (`git stash`, re-run, `git stash pop` to
confirm) rather than assuming your changes caused it — this plan doesn't touch any existing
production code path, so a regression here would be surprising and worth investigating before
blaming Tasks 1-3.

---

## Execution Handoff

Per this project's Default Agent Role policy (CLAUDE.md, 2026-10-04 Empirical Capability
Assessment Policy, interim default under reassessment), implementation work routes to Agy/Grok/
Codex via `synlynk dispatch`, not to Claude directly. Unlike the two other plans landed this
session (TPM-daemon-fix, Muse-config-fix), this plan is judgment-heavy rather than mechanical —
Tasks 1-2 require reading unfamiliar code to trace dynamic status values and make alias-collapse
calls, which is closer to the "integration and judgment" tier than the "mechanical, 1-2 files"
tier in the Capability-Based Task Allocation guidance.

Before any implementation starts: create a new worktree for branch
`fix/claude/status-writer-inventory` off `main` via `superpowers:using-git-worktrees` — this is
independent of both the TPM-daemon-autonomy work and the Muse-config-fix already in flight from
this session, and per the project's Git Workflow (one feature per branch) must not land on either
of those branches.

**Two execution options:**

**1. Subagent-Driven via `synlynk dispatch` (recommended)** — dispatch Task 1 (inventory-building)
as its own job first, since Tasks 2-3 depend entirely on what Task 1 actually finds and can't be
meaningfully scoped until it's done. Review Task 1's output (the inventory file + the alias
decisions it implies) before dispatching Tasks 2+3 together as a second job to the same
implementer harness for continuity. Claude runs Task 4 (regression check) directly.

**2. Single combined dispatch** — all of Tasks 1-3 to one implementer in one job, accepting that
the implementer will need to do the Task 1 scan and Task 2 classification in the same sitting
without a review checkpoint in between. Faster but removes the chance to catch a bad alias
decision before the test is written to lock it in.

Given how much judgment Task 2's alias-collapse decisions require (the spec explicitly warns
against assuming `failed_noop_denied`/`circuit_breaker_tripped` collapse), option 1's checkpoint
after Task 1 is worth the extra round-trip. Which approach?
