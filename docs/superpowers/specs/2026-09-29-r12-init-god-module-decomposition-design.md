# R12: Break the `_pkg()` duplication and trim `synlynk/__init__.py`'s inline bloat

**Source:** 2026-09-28 deep architectural review, goal `goal-079e2f37`, story R12.
**Status:** Approved design, awaiting plan.

## Problem

The review flagged "15 `_pkg()` copies" and "~570 function-level imports" as symptoms of a
god-module topology centered on `synlynk/__init__.py`. Investigation during this brainstorm
found the actual locations differ from the review's framing:

- `synlynk/__init__.py` itself has **zero** `_pkg()` definitions and only 33 function-level
  imports. It is not where the duplication lives.
- The 15 `_pkg()` copies and the bulk of the ~570 function-level imports (768 repo-wide) are
  spread across 15 *other* command modules: `daemon.py`, `context.py`, `dispatch.py`, `costs.py`,
  `doctor.py`, `instructions.py`, `logs.py`, `jobs.py`, `platform_status.py`, `quota.py`,
  `scheduler.py`, `scan.py`, `support_engineer.py`, `story_provisioning.py`, `team.py`,
  `wizard.py` (455 `_pkg()` calls total).
- `__init__.py` does still carry real bloat of its own: a 349-line inline data table
  (`LAUNCH_TASK_TEMPLATES`), a ~350-line inline SQL DDL string (`_DB_SCHEMA`/`_DB_SCORES_VIEW`),
  and a dead wizard-TUI scaffold (orphaned constants and blank-line gaps, ~line 3612–3686,
  immediately preceding `init()`) left over from an abandoned Plan B.

R12's scope is widened accordingly to cover both the real `_pkg()` duplication (wherever it
actually lives) and `__init__.py`'s own inline bloat, since both were bundled under the same
review recommendation and both serve the same underlying goal: reduce parse/import-time cost and
make the module graph easier to reason about.

## Why (motivation)

Primary driver is startup/runtime performance: `__init__.py` uses a lazy
`_load_legacy_imports()` specifically to keep argparse construction and `--version` fast by
deferring 30 legacy-module imports until first real use. The 15 duplicated `_pkg()` helpers and
`__init__.py`'s own inline data/SQL tables work against that goal — they add parse-time weight
and duplicate logic that has to be loaded/JIT'd independently per module instead of once.

## Out of scope (new finding, filed separately)

`synlynk/db.py` (3,894 lines, comparable size to `__init__.py`) has its own instance of the same
circular-import problem, but expressed differently: instead of a named `_pkg()` helper, its
functions do late in-body re-imports back into the `synlynk` package (e.g.
`detect_remote_owner_repo()` does `from synlynk import detect_remote_owner_repo as
_detect_remote_owner_repo` inside its own body). This is a second, structurally similar but
distinct problem from R12's — untangling it requires its own investigation into how `db.py`
relates to `__init__.py`'s inline DB connection/schema code (`_get_db`, `open_state_db`,
`get_state_db_path`, lines 596–1327) before any design is possible. It will be filed as a
follow-up issue after this spec is committed, not folded into R12.

`__init__.py`'s large *logic* functions (`cmd_release` ~308 lines, `cmd_status` ~238 lines,
`_update_config` ~191 lines, `_get_db` ~186 lines) are also out of scope for R12. They are large
but not duplicated or import-tangled; moving live logic around carries real behavioral risk for
unclear payoff against the stated performance motivation, and the `db.py` finding above is the
bigger structural issue worth spending that risk budget on later, deliberately, not as a rider on
this cleanup.

## Design

### Part A — Consolidate the 15 `_pkg()` copies

Two near-identical variants exist today:

```python
# 13 of 15 files:
def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)

# logs.py and platform_status.py (2 of 15):
def _pkg(name):
    import synlynk
    return getattr(synlynk, name)
```

Both exist to defer symbol lookup into the `synlynk` package namespace until call-time, avoiding
an import-time circular dependency created by `__init__.py`'s `_load_legacy_imports()`
`globals().update(...)` re-export pattern (confirmed directly in `dispatch.py`, which comments
`"""Load the Agy gh-write preflight lazily to avoid the doctor cycle."""` next to its own
`_pkg()`).

Add one canonical implementation to a new module, `synlynk/_lazy.py`:

```python
import sys

def pkg(name: str, default=None):
    """Look up a symbol in the synlynk package namespace at call time.

    Exists to break import-time circular dependencies created by
    synlynk/__init__.py's lazy _load_legacy_imports() re-export pattern:
    a legacy module that needs a symbol from another legacy module must
    defer the lookup to call-time rather than import it directly.
    """
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Update all 15 files to `from synlynk._lazy import pkg as _pkg`, keeping the call-site name `_pkg`
unchanged so no call site needs editing — only each file's own `def _pkg(...)` block is deleted
and replaced with the one-line import. The two-file no-default variant collapses into the
`default=None` form; since neither of those two files' call sites currently pass a default, this
is behavior-preserving (both currently raise via `getattr(synlynk, name)` with no default only if
`synlynk` itself doesn't have the attr, which the canonical form also allows for by returning
`None` instead — call sites in those two files are checked during implementation to confirm none
rely on the `AttributeError` explicitly).

### Part B — Trim `__init__.py`'s inline bloat

Three independent, behavior-preserving changes:

1. **Delete the dead wizard-TUI scaffold** — the orphaned `_WIZ_SYNAPTIC_BLURB`,
   `_WIZ_PRODUCT_BLURB`, `_STAGE_LABELS`, `_STAGE_COLORS`, `_ROBOT_ASCII` constants and the
   blank-line gaps around them (~line 3612–3686, immediately before `init()`). Confirmed dead:
   leftover from an abandoned "Wizard TUI primitives (BS-17 Plan B Tasks B-1 / B-2)" effort, not
   referenced by any live code path. Pure deletion.

2. **Extract `LAUNCH_TASK_TEMPLATES`** (349 lines of pure data, no logic) into
   `synlynk/launch_templates.py`. `__init__.py` imports it back with
   `from synlynk.launch_templates import LAUNCH_TASK_TEMPLATES`.

3. **Extract `_DB_SCHEMA` / `_DB_SCORES_VIEW`** (~350 lines of inline SQL DDL strings) into
   `synlynk/db_schema.py`. Both `__init__.py` and `synlynk/db.py` import from this new module
   instead of `__init__.py` defining it inline — this removes one small piece of duplication risk
   between the two files without touching either's actual logic.

None of Part B's three changes touch control flow, so no new tests are needed beyond confirming
the existing suite still passes unchanged.

## Testing

- Full existing test suite (`pytest`) must pass unchanged after both Part A and Part B — this is
  a pure refactor with no intended behavior change.
- Manually spot-check `--version` and argparse construction stay fast (no regression in the lazy-
  load discipline `_load_legacy_imports()` already protects).
- Confirm the two no-default `_pkg()` call sites (`logs.py`, `platform_status.py`) still behave
  correctly under the unified `default=None` signature (Part A, final paragraph).

## Follow-up (not part of this plan)

File a new issue after this spec is committed: "`synlynk/db.py` has its own circular-shim
pattern distinct from `__init__.py`'s — needs its own investigation into its relationship with
`__init__.py`'s inline DB code before a design is possible."
