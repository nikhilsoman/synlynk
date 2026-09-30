# R12: Consolidate `_pkg()` Duplication + Trim `__init__.py` Bloat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 14 duplicate `_pkg()` helper implementations into one shared module, and remove `synlynk/__init__.py`'s dead code and inline data/SQL bloat, with zero behavior change.

**Architecture:** Pure refactor, no logic changes. A new `synlynk/_lazy.py` holds the one canonical `pkg()` lookup helper; 14 command modules switch from defining their own `_pkg()` to importing it. Two new modules (`synlynk/launch_templates.py`, `synlynk/db_schema.py`) hold data/SQL that today lives inline in `synlynk/__init__.py`; `__init__.py` re-imports both so every existing `synlynk.LAUNCH_TASK_TEMPLATES` / `synlynk._DB_SCHEMA` / `synlynk._DB_SCORES_VIEW` access keeps working unchanged. A dead wizard-TUI scaffold in `__init__.py` (duplicated, unused copies of constants that live for real in `synlynk/wizard.py` and `synlynk/scan.py`) is deleted outright.

**Tech Stack:** Python 3 stdlib only, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-r12-init-god-module-decomposition-design.md`

---

## Task 1: Create the shared `_lazy.pkg()` helper

**Files:**
- Create: `synlynk/_lazy.py`
- Test: `tests/test_lazy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lazy.py
import sys
import types

from synlynk._lazy import pkg


def test_pkg_returns_attribute_from_synlynk_module():
    fake = types.ModuleType("synlynk")
    fake.SOME_CONST = "hello"
    sys.modules["synlynk"] = fake
    try:
        assert pkg("SOME_CONST") == "hello"
    finally:
        del sys.modules["synlynk"]


def test_pkg_returns_default_when_attribute_missing():
    fake = types.ModuleType("synlynk")
    sys.modules["synlynk"] = fake
    try:
        assert pkg("MISSING", "fallback") == "fallback"
        assert pkg("MISSING") is None
    finally:
        del sys.modules["synlynk"]


def test_pkg_returns_default_when_synlynk_not_imported_yet():
    saved = sys.modules.pop("synlynk", None)
    try:
        assert pkg("ANYTHING", "fallback") == "fallback"
        assert pkg("ANYTHING") is None
    finally:
        if saved is not None:
            sys.modules["synlynk"] = saved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lazy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk._lazy'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/_lazy.py
"""Shared late-binding lookup into the synlynk package namespace.

synlynk/__init__.py populates its own module namespace lazily, via
_load_legacy_imports(), so that argparse construction and --version stay
fast. Command modules that need a symbol from another command module (both
merged into the synlynk package namespace at different times) must defer
that lookup to call-time rather than import it directly at module load
time, to avoid a circular import. pkg() is the one shared implementation
of that deferred lookup — previously 14 command modules each defined their
own copy of this exact function.
"""

import sys


def pkg(name: str, default=None):
    """Look up ``name`` on the ``synlynk`` package at call time.

    Returns ``default`` if the ``synlynk`` module hasn't been imported yet,
    or if it has no attribute ``name``.
    """
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lazy.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/_lazy.py tests/test_lazy.py
git commit -m "feat: add shared synlynk._lazy.pkg() helper

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr"
```

---

## Task 2: Switch the 13 `default=None`-style files to the shared helper

These 12 files each define:

```python
def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Replace that block with `from synlynk._lazy import pkg as _pkg` in each file, so every existing call site (`_pkg(...)`) keeps working unchanged. Files (with their current `_pkg` def line, confirm with `grep -n "^def _pkg" synlynk/<file>.py` before editing since line numbers shift as earlier files in this task are edited):

- `synlynk/daemon.py` (line 25)
- `synlynk/context.py` (line 79)
- `synlynk/dispatch.py` (line 306)
- `synlynk/costs.py` (line 13)
- `synlynk/doctor.py` (line 42)
- `synlynk/instructions.py` (line 44)
- `synlynk/jobs.py` (line 131)
- `synlynk/quota.py` (line 17)
- `synlynk/scan.py` (line 17)
- `synlynk/support_engineer.py` (line 13)
- `synlynk/story_provisioning.py` (line 29)
- `synlynk/team.py` (line 31)
- `synlynk/wizard.py` (line 22)

- [ ] **Step 1: For each file, replace the `_pkg` definition with the shared import**

For `synlynk/daemon.py` as a worked example — the pattern is identical for the other 12 files, only the surrounding imports differ:

```bash
grep -n "^def _pkg" synlynk/daemon.py
```

Confirms the def is still at (or near) line 25. Open the file and replace:

```python
def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

with:

```python
from synlynk._lazy import pkg as _pkg
```

Place the new import line alongside the file's other top-level imports (near the top of the file, not at the old `_pkg` def's location) — check each file's existing import block with `sed -n '1,20p' synlynk/daemon.py` first and add it there, keeping the file's existing import ordering/grouping conventions. If the file's only use of the `sys` module was inside the now-deleted `_pkg` body, also remove the now-unused `import sys` — check with `grep -n "sys\." synlynk/daemon.py` first; if no other `sys.` usage remains, delete the `import sys` line too.

Repeat this exact procedure for each of the 13 files listed above: `context.py`, `dispatch.py`, `costs.py`, `doctor.py`, `instructions.py`, `jobs.py`, `quota.py`, `scan.py`, `support_engineer.py`, `story_provisioning.py`, `team.py`, `wizard.py`.

- [ ] **Step 2: Confirm no file still defines its own `_pkg`**

Run: `grep -rln "^def _pkg" synlynk/`
Expected: only `synlynk/logs.py` and `synlynk/platform_status.py` remain (handled in Task 3).

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, same pass count as before this task started (record the baseline count with `pytest -q 2>&1 | tail -5` before Step 1 if you want an exact diff).

- [ ] **Step 4: Commit**

```bash
git add synlynk/daemon.py synlynk/context.py synlynk/dispatch.py synlynk/costs.py \
        synlynk/doctor.py synlynk/instructions.py synlynk/jobs.py synlynk/quota.py \
        synlynk/scan.py synlynk/support_engineer.py synlynk/story_provisioning.py \
        synlynk/team.py synlynk/wizard.py
git commit -m "refactor: replace 13 duplicate _pkg() defs with shared synlynk._lazy.pkg()

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr"
```

---

## Task 3: Switch the 2 no-default-style files (`logs.py`, `platform_status.py`)

These define:

```python
def _pkg(name):
    import synlynk
    return getattr(synlynk, name)
```

Confirmed during design that every call site in both files (`logs.py`: `_load_jobs`, `_BOLD`, `_RESET`, `_DIM`, `_job_summary_path`; `platform_status.py`: `_get_db`, `_iter_sentinel_alerts`, `load_config`) passes only one argument and none of the call sites are wrapped in a `try/except AttributeError` — so switching to the shared `pkg(name, default=None)` (which returns `None` instead of raising `AttributeError` when the attribute is missing) is behavior-preserving for every real call site in the codebase today.

- [ ] **Step 1: Confirm no call site relies on the AttributeError**

```bash
grep -n "_pkg(" synlynk/logs.py synlynk/platform_status.py
```

Verify every line matches one of the call sites listed above (no `try`/`except AttributeError` wrapping any of them — check with `sed -n '1,120p' synlynk/logs.py` and `sed -n '1,120p' synlynk/platform_status.py` if in doubt).

- [ ] **Step 2: Replace the `_pkg` definitions**

In `synlynk/logs.py`, replace:

```python
def _pkg(name):
    import synlynk
    return getattr(synlynk, name)
```

with:

```python
from synlynk._lazy import pkg as _pkg
```

In `synlynk/platform_status.py`, replace the identical block the same way.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, same count as Task 2's Step 3.

- [ ] **Step 4: Commit**

```bash
git add synlynk/logs.py synlynk/platform_status.py
git commit -m "refactor: replace logs.py/platform_status.py _pkg() with shared helper

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr"
```

---

## Task 4: Delete the dead wizard-TUI scaffold from `__init__.py`

Confirmed during planning: `_WIZ_SYNAPTIC_BLURB`, `_WIZ_PRODUCT_BLURB`, `_STAGE_LABELS`, `_STAGE_COLORS` all have live, actually-used definitions in `synlynk/wizard.py` (lines 238, 246, 294, 296) and `_STAGE_LABELS`/`_STAGE_COLORS` also in `synlynk/scan.py` (lines 1940, 1942) — completely separate from `__init__.py`'s copies. `_ROBOT_ASCII` similarly has a live copy in `wizard.py` (line 801). None of `__init__.py`'s copies (at lines 3616, 3624, 3638, 3639, 3668) are referenced anywhere else in the repo. This block, plus its header comment and the surrounding blank-line gap, runs from line 3607 to line 3686 (immediately before `def init(` at line 3687).

- [ ] **Step 1: Confirm the block is still dead and re-locate exact boundaries**

```bash
grep -n "Wizard TUI primitives\|_WIZ_SYNAPTIC_BLURB\|_WIZ_PRODUCT_BLURB\|_STAGE_LABELS\|_STAGE_COLORS\|_ROBOT_ASCII\|^def init(" synlynk/__init__.py
grep -rn "_WIZ_SYNAPTIC_BLURB\|_WIZ_PRODUCT_BLURB" --include="*.py" | grep -v "synlynk/__init__.py\|synlynk/wizard.py"
```

Second command's expected output: empty (confirms still unreferenced outside `__init__.py`'s own dead copy and `wizard.py`'s live copy).

- [ ] **Step 2: Delete the block**

Open `synlynk/__init__.py`. Delete everything from the `# ── Wizard TUI primitives (BS-17 Plan B Tasks B-1 / B-2) ──` comment line through the blank lines immediately preceding `def init(force: bool = False, agents: list = None,` — i.e. delete lines 3607–3686 inclusive, leaving exactly one blank line between the previous code and `def init(`. Re-run the `grep -n` from Step 1 after deleting to confirm zero matches for `_WIZ_SYNAPTIC_BLURB|_WIZ_PRODUCT_BLURB|_STAGE_LABELS|_STAGE_COLORS|_ROBOT_ASCII` in `synlynk/__init__.py`.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, same count as Task 3's Step 3.

- [ ] **Step 4: Commit**

```bash
git add synlynk/__init__.py
git commit -m "chore: delete dead wizard-TUI scaffold from __init__.py

Duplicated constants with no references outside their own dead copy;
live versions already exist in synlynk/wizard.py and synlynk/scan.py.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr"
```

---

## Task 5: Extract `LAUNCH_TASK_TEMPLATES` into `synlynk/launch_templates.py`

`LAUNCH_TASK_TEMPLATES` is defined at `synlynk/__init__.py:130`–`478` (a list literal, 349 lines, pure data — confirm current boundaries with `grep -n "^LAUNCH_TASK_TEMPLATES" synlynk/__init__.py` and `awk 'NR>130 && /^\]/{print NR; exit}' synlynk/__init__.py` since Task 4's deletion shifts line numbers above 3607 but not below 478, so this task's line numbers are unaffected by Task 4). All existing usages access it as `synlynk.LAUNCH_TASK_TEMPLATES` (`tests/test_launch.py`, `tests/test_capability_scoring.py`) or `from synlynk import LAUNCH_TASK_TEMPLATES` (`tests/test_launch_templates.py`) — both keep working once `__init__.py` re-imports the name.

- [ ] **Step 1: Cut the list literal into its own module**

```bash
sed -n '130,478p' synlynk/__init__.py > /tmp/launch_templates_body.py
```

Create `synlynk/launch_templates.py`:

```python
"""Launch task template catalog for ``synlynk launch``.

Extracted from synlynk/__init__.py (R12, 2026-09-29) — pure data, no logic.
"""

from synlynk.hud import CYCLES
```

Then append the cut content from `/tmp/launch_templates_body.py` (the `LAUNCH_TASK_TEMPLATES = [ ... ]` list literal) to the end of `synlynk/launch_templates.py`. Before appending, check whether the list literal references any names not already imported (e.g. `CYCLES` if any template dict uses a `"cycle": CYCLES.something` reference, or any other package-level name) — inspect with `grep -nE '[A-Z_]{3,}' /tmp/launch_templates_body.py | grep -v '"' ` to catch bare uppercase identifiers used as values rather than as string literals, and add the corresponding import from wherever that name is actually defined (check with `grep -rn "^CYCLES = \|^<NAME> = " synlynk/*.py`) for each one found.

- [ ] **Step 2: Remove the original block from `__init__.py` and replace with an import**

Delete lines 130–478 (the `LAUNCH_TASK_TEMPLATES = [ ... ]` block) from `synlynk/__init__.py`. In its place, add near `__init__.py`'s other top-of-file imports (not at line 130 — check `sed -n '1,30p' synlynk/__init__.py` for the existing import block and add it there):

```python
from synlynk.launch_templates import LAUNCH_TASK_TEMPLATES
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, including `tests/test_launch.py`, `tests/test_launch_templates.py`, `tests/test_capability_scoring.py` — same total count as Task 4's Step 3.

- [ ] **Step 4: Commit**

```bash
git add synlynk/launch_templates.py synlynk/__init__.py
git commit -m "refactor: extract LAUNCH_TASK_TEMPLATES into synlynk/launch_templates.py

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr"
```

---

## Task 6: Extract `_DB_SCHEMA` and `_DB_SCORES_VIEW` into `synlynk/db_schema.py`

`_DB_SCHEMA` is defined at `synlynk/__init__.py:677`–`1027` (a triple-quoted SQL string) and `_DB_SCORES_VIEW` immediately follows at `1029`–`1049` (confirm current boundaries the same way as Task 5, via `grep -n "^_DB_SCHEMA\|^_DB_SCORES_VIEW" synlynk/__init__.py` and locating each string's closing `"""`). Both are consumed today by `synlynk/db.py` via a late in-function `from synlynk import HARNESS_CAPABILITY_BASELINES, _DB_SCHEMA, _DB_SCORES_VIEW, _seed_verb_map` (line 548) and by two test files (`tests/test_fleet_scheduler.py` via `from synlynk import _DB_SCHEMA`, `tests/test_agent_quota_tracking.py` via `sl._DB_SCHEMA`) — all three keep working once `__init__.py` re-exports both names, so `synlynk/db.py` needs **no changes** in this task.

- [ ] **Step 1: Cut both strings into their own module**

```bash
sed -n '677,1049p' synlynk/__init__.py > /tmp/db_schema_body.py
```

Create `synlynk/db_schema.py`:

```python
"""SQLite schema DDL for the synlynk state database.

Extracted from synlynk/__init__.py (R12, 2026-09-29) — pure SQL strings,
no logic. Consumed by synlynk/db.py and synlynk/__init__.py's own DB
connection helpers via a re-export in __init__.py.
"""
```

Append the cut content from `/tmp/db_schema_body.py` (both `_DB_SCHEMA = """..."""` and `_DB_SCORES_VIEW = """..."""` blocks, and anything between them) to the end of `synlynk/db_schema.py`.

- [ ] **Step 2: Remove the original block from `__init__.py` and replace with an import**

Delete lines 677–1049 from `synlynk/__init__.py` (re-confirm exact end boundary first — the two strings are adjacent with no unrelated code between them, so this should be a single contiguous deletion; verify with `sed -n '670,1055p' synlynk/__init__.py` before deleting that nothing unrelated is caught in the range). In its place, add near `__init__.py`'s other top-of-file imports:

```python
from synlynk.db_schema import _DB_SCHEMA, _DB_SCORES_VIEW
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, including `tests/test_fleet_scheduler.py` and `tests/test_agent_quota_tracking.py` — same total count as Task 5's Step 3.

- [ ] **Step 4: Commit**

```bash
git add synlynk/db_schema.py synlynk/__init__.py
git commit -m "refactor: extract _DB_SCHEMA/_DB_SCORES_VIEW into synlynk/db_schema.py

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run the full test suite one more time end-to-end**

Run: `pytest -q`
Expected: all tests pass, same total count as the pre-Task-1 baseline recorded in Task 2 Step 3.

- [ ] **Step 2: Confirm no file outside `synlynk/_lazy.py` defines `_pkg` anymore**

Run: `grep -rln "^def _pkg" synlynk/`
Expected: empty output.

- [ ] **Step 3: Confirm `--version` and argparse construction still succeed fast**

Run: `time python3 bin/synlynk.py --version`
Expected: prints a version string, completes in well under 1 second (no regression in `_load_legacy_imports()`'s lazy-load discipline — this refactor doesn't touch that function, but the new `synlynk.launch_templates`/`synlynk.db_schema` imports are unconditional top-of-file imports in `__init__.py`, so confirm they don't reintroduce eager-loading of anything `_load_legacy_imports()` was deferring).

- [ ] **Step 4: Confirm `synlynk/__init__.py`'s line count dropped as expected**

Run: `wc -l synlynk/__init__.py`
Expected: roughly 3937 − 80 (dead scaffold) − 349 (LAUNCH_TASK_TEMPLATES) − 373 (_DB_SCHEMA/_DB_SCORES_VIEW) ≈ 3135 lines, give or take a few from exact blank-line handling in Tasks 4–6.

- [ ] **Step 5: File the `synlynk/db.py` circular-shim follow-up issue**

Per the spec's "Follow-up" section — this is a PM/review-role action (not implementation), so use `synlynk gh --role pm -- issue create`:

```bash
synlynk gh --role pm -- issue create \
  --title "synlynk/db.py has its own circular-shim pattern, distinct from __init__.py's _pkg() duplication (R12)" \
  --body "Found during R12 (goal-079e2f37) brainstorm/design: synlynk/db.py (~3,894 lines) has the same underlying circular-import problem as the 14 files R12 consolidated via synlynk._lazy.pkg(), but expressed differently — functions do late in-body re-imports back into the synlynk package (e.g. detect_remote_owner_repo() does 'from synlynk import detect_remote_owner_repo as _detect_remote_owner_repo' inside its own body) instead of using a named _pkg() helper. Needs its own investigation into db.py's relationship with __init__.py's inline DB connection/schema code (_get_db, open_state_db, get_state_db_path) before a design is possible. Deliberately out of scope for R12 — see docs/superpowers/specs/2026-09-29-r12-init-god-module-decomposition-design.md's 'Out of scope' section." \
  --label tech-debt
```

Record the resulting issue number in a follow-up note to whoever picks this plan back up (e.g. in the PR description for this plan's work).

- [ ] **Step 6: No commit needed for this task** — Steps 1–4 are verification-only (no file changes), and Step 5's issue filing has no repo-side artifact to commit.

---

## Notes for the executing agent

- Every task in this plan is independently revertible and independently testable — if Task N's test suite run fails, stop and fix before starting Task N+1 rather than proceeding.
- Per this project's CLAUDE.md, work happens on a feature branch (not `main`) with a dedicated worktree (`superpowers:using-git-worktrees`), e.g. branch `feat/r12-init-decomposition` — do not commit to `main` at any point in this plan.
- Per CLAUDE.md's Capability-Based Task Allocation, implementation work (Tasks 1–6) routes to Codex/Agy/Grok via `synlynk dispatch`, not directly to a Claude session — the executing skill (`subagent-driven-development`) handles this routing; Task 7 Step 5 (filing the follow-up issue) is PM-role work and stays with Claude.
- Commit trailer for every commit in this plan: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` + `Claude-Session: https://claude.ai/code/session_01UA58sGobMckaQ5Huv9P9Sr` when authored by this session; a dispatched implementer substitutes its own harness's trailer per CLAUDE.md's Repo Hygiene section if it authors the commit instead.
