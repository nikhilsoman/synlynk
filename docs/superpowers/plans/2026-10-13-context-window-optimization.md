# Context Window Tracking & Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop synlynk from writing a phantom `GROK.md` nobody reads, split this repo's own bloated `CLAUDE.md` into a lean index + on-demand SOP docs, add a dispatch-wrapper-only task-boundary compaction trigger, and add a job-scoped context-pack mechanism — per the approved R2 decide-panel synthesis (`dec-0d7e75e0`, GOVERNS `goal-e79062e8`).

**Architecture:** Four independent, separately-committable slices. (1) Fix `_INSTRUCTION_TARGETS`/`_build_templates()` in `synlynk/instructions.py` to drop the `GROK.md` target and tag each harness with its confirmed reload tier. (2) Migrate this repo's own root `CLAUDE.md` policy sections (not the generator's output — the generator's skeleton is already ~20 lines; the bloat is in the *committed* file, grown by years of appended PR policy sections) into `docs/sop/*.md` topic files, leaving a lean index behind. (3) Add `check_context_compaction_trigger()` to `synlynk/costs.py`, hooked from `exec_command()`'s existing `finally:` block in `synlynk/dispatch.py`, reading cumulative tokens from `cost_entries` the same way `check_budgets()` already does. (4) Add `write_context_pack(job_id, story_id)` to `synlynk/context.py`, modeled on the existing `_generate_task_context()`, writing `.synlynk/context-packs/<job-id>.md`.

**Tech Stack:** Python 3 stdlib, SQLite (`state.db`, `cost_entries`/`stories`/`backlog_items` tables), pytest.

---

## Context this plan assumes (read before starting)

- **R2 decision** (`project-docs/decisions/2026-10-12-context-window-management-r2-revised-syn.md`, `dec-0d7e75e0`) is the binding design. Key provisions this plan implements:
  - Reload-tier classification: `claude` = `confirmed_per_session`; `agy` = `confirmed_per_turn`; `grok` = `confirmed_per_turn`; `codex` = `probed_no_evidence_of_per_turn_reload` (provisional).
  - Grok does not load a `GROK.md` file — it falls through to `AGENTS.md`. No `GROK.md` should ever be written.
  - Budget/compaction signals live only in the dispatch-wrapper layer (`cost_entries`/telemetry), never duplicated into model-side instruction text.
  - Task-boundary compaction trigger: evaluate accumulated tokens at job/task completion; above a threshold, surface a compaction recommendation (this plan implements it as a printed signal + telemetry flag — firing an actual `/compact`/`/clear` subprocess command is out of scope, see "Out of scope" below).
  - Context-pack: a job-scoped `.synlynk/context-packs/<job-id>.md` bundle built once, containing objective/decisions, findings-with-evidence, changed-files/verification-state, unresolved work, must-survive constraints.
- **Already fixed, no work needed here:** gh:#2237 (`_generate_todo_md()` leaking a project-wide `todo.md` snapshot into dispatch worktrees) was fixed by PR #2238 — verified in this plan's own grounding: `synlynk/db.py:2992`'s `_generate_todo_md()` now writes via `_write_generated_project_doc()`, not a raw cwd-relative open(). `generate_context()`'s DB-backed path (`synlynk/context.py:220`, used whenever `_is_migrated()` is true — true for this repo) is already bounded: 5 devlog entries × 500 chars, 5 memory entries × 300 chars, one active goal, one open story. The *legacy* flat-file path (`_is_migrated() == False`) is the literal unbounded-concatenation bloat source the spec describes, but it is dead code in this already-migrated repo. **This plan does not touch `generate_context()` or the legacy path** — there is no regression to fix and no placeholder task would be honest here.
- **Revised understanding of the instruction-file bloat** (supersedes the spec's framing that `init()`'s generator itself is the bloat source): `_build_templates()` in `synlynk/instructions.py` generates a short `_tool_header()` skeleton (~20 lines) per harness file. The 335/116/109-line sizes the spec cites are **this repo's own committed `CLAUDE.md`/`GEMINI.md`/`AGENTS.md`**, grown over time by dozens of appended policy sections (Capability-Based Task Allocation, Hardened PR Review Policy, Worktree Hygiene Protocol, etc.) — not by the generator. So: Task 1 fixes the generator (`GROK.md` + reload-tier tagging). Tasks 2-4 migrate *this repo's actual root `CLAUDE.md`* content into `docs/sop/`, which is the concrete, content-level version of "index + links restructuring" the R2 decision asks for.

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/instructions.py` | `_INSTRUCTION_TARGETS`, `_AGENT_FILE_NAMES`, `_MARKER_STYLE_FOR_TOOL`, `_build_templates()` — drop `GROK.md`, add reload-tier metadata |
| `docs/sop/capability-task-allocation.md` (new) | Capability-Based Task Allocation table + Empirical Capability Assessment Policy, moved out of root `CLAUDE.md` |
| `docs/sop/pr-review-discipline.md` (new) | Hardened PR Review Policy + PR Review Discipline sections, moved out of root `CLAUDE.md` |
| `docs/sop/worktree-and-cost-hygiene.md` (new) | Worktree Hygiene Protocol + Cost Capture/Visibility Protocols, moved out of root `CLAUDE.md` |
| `CLAUDE.md` (repo root) | Trimmed to identity, pointers to `docs/sop/*.md`, and sections that are genuinely short already |
| `synlynk/costs.py` | New `check_context_compaction_trigger(cmd_args, in_tokens, out_tokens)` function |
| `synlynk/dispatch.py` | `exec_command()` — one new call site in the existing `finally:` block |
| `synlynk/context.py` | New `write_context_pack(job_id, story_id=None, out_path=None)` function |
| `tests/test_instructions.py` | New tests for Task 1 |
| `tests/test_costs.py` | New tests for Task 3 |
| `tests/test_context.py` | New tests for Task 4 |

---

### Task 1: Drop the phantom `GROK.md` target and tag harness reload tiers

**Files:**
- Modify: `synlynk/instructions.py:327-328` (the `("GEMINI.md", "agy"), ("AGENTS.md", "codex")` list — need to see the full list this line belongs to before editing; read lines 300-335 first)
- Modify: `synlynk/__init__.py:2487-2498` (`_INSTRUCTION_TARGETS`)
- Modify: `synlynk/__init__.py:2347` (`_AGENT_FILE_NAMES`)
- Modify: `synlynk/__init__.py:2504-2510` (`_MARKER_STYLE_FOR_TOOL`)
- Modify: `synlynk/instructions.py:641-647, 666-691` (`_grok_md` build + `"GROK.md": _grok_md` dict entry)
- Test: `tests/test_instructions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_templates_does_not_emit_grok_md():
    """R2 decision dec-0d7e75e0: Grok does not discover a GROK.md file at
    all (it falls through to AGENTS.md), so init() must never write one."""
    from synlynk.instructions import _build_templates
    templates = _build_templates()
    assert "GROK.md" not in templates


def test_instruction_targets_has_no_grok_md_entry():
    from synlynk import _INSTRUCTION_TARGETS
    paths = [t[0] for t in _INSTRUCTION_TARGETS]
    assert "GROK.md" not in paths


def test_agent_file_names_has_no_grok_md():
    from synlynk import _AGENT_FILE_NAMES
    assert "GROK.md" not in _AGENT_FILE_NAMES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_instructions.py -k grok_md -v`
Expected: FAIL — `test_build_templates_does_not_emit_grok_md` fails because `"GROK.md"` is currently a key in the dict; `test_instruction_targets_has_no_grok_md_entry` and `test_agent_file_names_has_no_grok_md` fail because the entry/name is present.

- [ ] **Step 3: Remove the GROK.md template and all four registry entries**

In `synlynk/instructions.py`, delete the `_grok_md` assignment block (currently lines 641-647):

```python
    _grok_md = (
        _tool_header(
            "synlynk Grok Instructions", "grok-composer-2.5-fast",
            "Co-Authored-By: Grok <noreply@x.ai>",
            "grok",
        )
    )

```

and delete the `"GROK.md": _grok_md,` line from the returned dict (currently line 690).

In `synlynk/__init__.py`, in `_INSTRUCTION_TARGETS` (currently lines 2487-2498), delete the line:

```python
    ("GROK.md",                            "grok",      "html", lambda: True),
```

In `synlynk/__init__.py`, in `_AGENT_FILE_NAMES` (currently line 2347):

```python
_AGENT_FILE_NAMES = {"CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md", "AI_INSTRUCTIONS.md"}
```

becomes:

```python
_AGENT_FILE_NAMES = {"CLAUDE.md", "GEMINI.md", "AGENTS.md", "AI_INSTRUCTIONS.md"}
```

In `synlynk/__init__.py`, in `_MARKER_STYLE_FOR_TOOL` (currently around line 2504-2510), delete the line:

```python
    "grok":      "html",
```

Finally, run `grep -rn '"GROK.md"' synlynk/*.py` and remove any remaining reference (there may be one in the `rollback_checkpoint` untracked_paths list in `init()`, currently around `synlynk/__init__.py:3316` — delete the `"GROK.md",` line from that list too, since there is nothing left for rollback to track).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_instructions.py -k grok_md -v`
Expected: PASS (all 3 tests)

Also run the existing instruction-writer test suite to make sure nothing else assumed `GROK.md` existed:

Run: `pytest tests/test_instructions.py tests/test_init.py -v`
Expected: PASS (fix any test that asserted `GROK.md` was written — update that assertion to assert it is absent, following the same pattern as the three new tests above)

- [ ] **Step 5: Add reload-tier metadata and assert it against R2's classification**

In `synlynk/instructions.py`, add a new module-level constant directly above `_build_templates`'s definition:

```python
# R2 decision dec-0d7e75e0 (2026-10-12): per-harness instruction-reload
# confirmation tier. "confirmed_per_turn" and "confirmed_per_session" are
# evidence-backed; "probed_no_evidence_of_per_turn_reload" is provisional
# pending a second independent confirmation method for Codex.
HARNESS_RELOAD_TIER = {
    "claude": "confirmed_per_session",
    "agy": "confirmed_per_turn",
    "grok": "confirmed_per_turn",
    "codex": "probed_no_evidence_of_per_turn_reload",
}
```

Write the test first:

```python
def test_harness_reload_tier_matches_r2_decision():
    from synlynk.instructions import HARNESS_RELOAD_TIER
    assert HARNESS_RELOAD_TIER == {
        "claude": "confirmed_per_session",
        "agy": "confirmed_per_turn",
        "grok": "confirmed_per_turn",
        "codex": "probed_no_evidence_of_per_turn_reload",
    }
```

Run: `pytest tests/test_instructions.py -k reload_tier -v`
Expected: FAIL before the constant exists, PASS after adding it.

- [ ] **Step 6: Commit**

```bash
git add synlynk/instructions.py synlynk/__init__.py tests/test_instructions.py
git commit -m "fix: stop writing phantom GROK.md, add R2 harness reload-tier metadata

Grok does not discover a GROK.md file (falls through to AGENTS.md per
dec-0d7e75e0 R1 audit), so init() writing one was dead weight nobody
reads. Also records each harness's confirmed instruction-reload tier
from the R2 decide-panel synthesis for future tooling to reference.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 2: Split root `CLAUDE.md` into a lean index + `docs/sop/*.md`

**Files:**
- Create: `docs/sop/capability-task-allocation.md`
- Create: `docs/sop/pr-review-discipline.md`
- Create: `docs/sop/worktree-and-cost-hygiene.md`
- Modify: `CLAUDE.md` (repo root)
- Test: `tests/test_docs_structure.py`

This task moves *content*, verbatim, out of the root `CLAUDE.md` into three new topic files under `docs/sop/`, then replaces the moved sections in `CLAUDE.md` with a one-line pointer each. No wording changes — this is a relocation, not a rewrite, so there is zero risk of silently changing a policy while moving it.

- [ ] **Step 1: Write the failing test**

```python
import os

def test_sop_docs_exist_and_are_referenced_from_claude_md():
    sop_files = [
        "docs/sop/capability-task-allocation.md",
        "docs/sop/pr-review-discipline.md",
        "docs/sop/worktree-and-cost-hygiene.md",
    ]
    for path in sop_files:
        assert os.path.exists(path), f"{path} should exist"

    with open("CLAUDE.md") as f:
        claude_md = f.read()
    for path in sop_files:
        assert path in claude_md, f"CLAUDE.md should point to {path}"


def test_claude_md_is_leaner_than_before():
    with open("CLAUDE.md") as f:
        line_count = sum(1 for _ in f)
    # Was ~335 lines pre-migration (per gh:#2243 audit); the moved
    # sections alone are well over 150 lines, so this is a conservative
    # ceiling that still catches a no-op "refactor".
    assert line_count < 250, f"CLAUDE.md still has {line_count} lines"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_docs_structure.py -v`
Expected: FAIL — `docs/sop/*.md` don't exist yet.

- [ ] **Step 3: Create `docs/sop/capability-task-allocation.md`**

Move the root `CLAUDE.md` sections titled `## Empirical Capability Assessment Policy (2026-10-04)` and `## Capability-Based Task Allocation` (including their `<details>` sub-block and the suspended-heuristic note) verbatim into this new file, prefixed with a one-line header:

```markdown
# Capability-Based Task Allocation & Empirical Capability Assessment Policy

> Moved out of root `CLAUDE.md` (2026-10-13, context-window-optimization plan) — same content, loaded on demand instead of resident in every session's root instruction file.

<!-- PASTE: the full "## Empirical Capability Assessment Policy (2026-10-04)" section and the full "## Capability-Based Task Allocation" section from CLAUDE.md here, verbatim, including the suspended-heuristic <details> block -->
```

(The executing agent: copy the two sections byte-for-byte from the current root `CLAUDE.md` — do not paraphrase. Use `Read` on `CLAUDE.md` to get the exact current text before writing this file, since the content is this repo's live policy text and must not drift during the move.)

- [ ] **Step 4: Create `docs/sop/pr-review-discipline.md`**

Move the root `CLAUDE.md` sections titled `## Hardened PR Review Policy (2026-10-04)` and the `## PR Review Discipline` block (including the `**GitHub identity note (#423)**` and `**Merge authority is enforced...**` paragraphs) verbatim into this new file, with the same one-line provenance header pattern as Step 3.

- [ ] **Step 5: Create `docs/sop/worktree-and-cost-hygiene.md`**

Move the root `CLAUDE.md` sections titled `## Worktree Hygiene Protocol`, `## Cost Capture Protocol`, and `## Cost Visibility` verbatim into this new file, with the same one-line provenance header pattern.

- [ ] **Step 6: Replace the moved sections in `CLAUDE.md` with pointers**

In `CLAUDE.md`, replace each moved section's full body with a single line in its place:

```markdown
## Capability-Based Task Allocation & Empirical Capability Assessment Policy

See `docs/sop/capability-task-allocation.md`.
```

```markdown
## PR Review Discipline & Hardened PR Review Policy

See `docs/sop/pr-review-discipline.md`.
```

```markdown
## Worktree Hygiene, Cost Capture & Cost Visibility

See `docs/sop/worktree-and-cost-hygiene.md`.
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_docs_structure.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md docs/sop/ tests/test_docs_structure.py
git commit -m "docs: move capability/PR-review/worktree-hygiene SOPs out of root CLAUDE.md

Root CLAUDE.md had grown to ~335 lines of resident instruction text
that Claude Code resends every session (dec-0d7e75e0, R1 audit:
claude = confirmed_per_session reload). Relocates three large,
rarely-changing policy sections to docs/sop/, loaded on demand, and
leaves a one-line pointer in their place. Content unchanged, only
relocated.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 3: Task-boundary compaction trigger in the dispatch wrapper

**Files:**
- Modify: `synlynk/costs.py` (add new function, near `check_budgets()` at line 1198)
- Modify: `synlynk/dispatch.py:5053` (`exec_command()`'s `finally:` block, right after the existing `if check_costs:` call)
- Test: `tests/test_costs.py`

This adds a wrapper-layer-only signal — per the R2 decision, nothing is written into any harness instruction file. `check_budgets()` already shows the exact pattern (query `cost_entries`, print a signal) for a dollar-budget check; this task adds the same pattern for a token-based compaction threshold.

- [ ] **Step 1: Write the failing test**

```python
def test_check_context_compaction_trigger_fires_above_threshold(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.costs import check_context_compaction_trigger

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cost_entries (id INTEGER PRIMARY KEY, job_id TEXT, "
        "input_tokens INTEGER, output_tokens INTEGER)"
    )
    conn.execute(
        "INSERT INTO cost_entries (job_id, input_tokens, output_tokens) VALUES (?, ?, ?)",
        ("job-abc", 50_000, 10_000),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk.costs._get_db", lambda: sqlite3.connect(str(db_path)))

    signal = check_context_compaction_trigger(job_id="job-abc", threshold_tokens=40_000)
    assert signal is not None
    assert signal["should_compact"] is True
    assert signal["cumulative_tokens"] == 60_000


def test_check_context_compaction_trigger_silent_below_threshold(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.costs import check_context_compaction_trigger

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cost_entries (id INTEGER PRIMARY KEY, job_id TEXT, "
        "input_tokens INTEGER, output_tokens INTEGER)"
    )
    conn.execute(
        "INSERT INTO cost_entries (job_id, input_tokens, output_tokens) VALUES (?, ?, ?)",
        ("job-abc", 1_000, 500),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk.costs._get_db", lambda: sqlite3.connect(str(db_path)))

    signal = check_context_compaction_trigger(job_id="job-abc", threshold_tokens=40_000)
    assert signal["should_compact"] is False
    assert signal["cumulative_tokens"] == 1_500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_costs.py -k compaction_trigger -v`
Expected: FAIL with `ImportError: cannot import name 'check_context_compaction_trigger'`

- [ ] **Step 3: Implement `check_context_compaction_trigger()`**

Add to `synlynk/costs.py`, directly below `check_budgets()` (after its closing lines, i.e. after the block ending around line 1260):

```python
def check_context_compaction_trigger(job_id: str = None, threshold_tokens: int = 60_000) -> dict:
    """Task-boundary compaction signal (dec-0d7e75e0 R2 synthesis).

    Evaluates accumulated tokens for the given job (or, if job_id is None,
    across the whole cost_entries table for the current process's session)
    and returns a signal dict the caller can act on. This function never
    shells out to fire /compact or /clear itself — it only reports whether
    the threshold was crossed, so the decision to act stays with the
    dispatch wrapper (exec_command()) rather than being baked in here.
    Wrapper-layer-only per R2: this signal is never written into any
    harness instruction file (CLAUDE.md/AGENTS.md/GEMINI.md/AI_INSTRUCTIONS.md).
    """
    conn = _pkg("_get_db")()
    try:
        if job_id:
            row = conn.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) "
                "FROM cost_entries WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) "
                "FROM cost_entries"
            ).fetchone()
    finally:
        conn.close()

    cumulative_tokens = row[0] or 0
    should_compact = cumulative_tokens >= threshold_tokens

    if should_compact:
        print(
            f"\n  💭 [Compaction Signal] {cumulative_tokens:,} tokens "
            f">= {threshold_tokens:,} threshold for this task boundary. "
            "Consider /compact or /clear before the next handoff."
        )

    return {
        "should_compact": should_compact,
        "cumulative_tokens": cumulative_tokens,
        "threshold_tokens": threshold_tokens,
        "job_id": job_id,
    }
```

Note: `_pkg` is already imported/used throughout `synlynk/costs.py` (see `check_budgets()`'s own use of `_pkg("_get_db")()` and `_pkg("load_config")()` immediately above) — no new import is needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_costs.py -k compaction_trigger -v`
Expected: PASS (both tests)

- [ ] **Step 5: Hook it into `exec_command()`'s finally block**

In `synlynk/dispatch.py`, inside `exec_command()`'s `finally:` block, directly after the existing:

```python
        if check_costs:
            check_costs()
```

(currently around line 5053-5054) add:

```python
        compaction_check = _pkg("check_context_compaction_trigger")
        if compaction_check and not _is_interactive(cmd_args):
            try:
                compaction_check(job_id=os.environ.get("SYNLYNK_JOB_ID"))
            except Exception:
                pass
```

This follows the exact same `_pkg(...)` lazy-resolution + best-effort-non-fatal pattern already used by every other post-execution hook in this `finally:` block (`check_costs`, `log_telemetry`, `refresh_quotas`) — a failure here must never fail the whole `exec_command()` call, matching the existing `refresh_quotas()` `try/except Exception: pass` immediately below it.

- [ ] **Step 6: Write a test exercising the hook from `exec_command()`**

```python
def test_exec_command_invokes_compaction_trigger(monkeypatch):
    from synlynk import dispatch

    calls = []
    monkeypatch.setattr(
        dispatch, "_pkg",
        lambda name, default=None: (
            (lambda **kw: calls.append(kw)) if name == "check_context_compaction_trigger"
            else default
        ),
    )
    # Minimal stub so exec_command's other _pkg() lookups don't explode;
    # relies on exec_command's existing tolerance for missing hooks (each
    # is retrieved via _pkg(name, default) and guarded with `if hook:`).
    dispatch.exec_command(["echo", "hi"])

    assert len(calls) == 1
    assert "job_id" in calls[0]
```

Run: `pytest tests/test_dispatch.py -k invokes_compaction_trigger -v` (or add to `tests/test_costs.py` if `tests/test_dispatch.py` doesn't already exist for `exec_command` — check with `ls tests/test_dispatch*.py` first)
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/costs.py synlynk/dispatch.py tests/test_costs.py
git commit -m "feat: add task-boundary compaction trigger to the dispatch wrapper

check_context_compaction_trigger() evaluates accumulated cost_entries
tokens at job-completion time (exec_command()'s existing finally
block, same hook point as check_budgets()/update_costs()) and prints
a compaction recommendation above a token threshold. Wrapper-layer
only per dec-0d7e75e0 R2 synthesis — never duplicated into any
harness instruction file. Does not itself fire /compact or /clear;
only reports the signal.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 4: Context-pack mechanism (`.synlynk/context-packs/<job-id>.md`)

**Files:**
- Modify: `synlynk/context.py` (new function, modeled on `_generate_task_context()` at line 135)
- Test: `tests/test_context.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import sqlite3

def test_write_context_pack_contains_required_sections(tmp_path, monkeypatch):
    from synlynk import context as context_mod

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, "
        "engg_domain TEXT, org_domain TEXT, phase TEXT, role TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO stories VALUES ('story-1', 'Add widget', 'backend', "
        "'core', 'build', 'dev', 'open')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(context_mod, "_get_db", lambda: sqlite3.connect(str(db_path)))

    out_path = tmp_path / "context-packs" / "job-xyz.md"
    context_mod.write_context_pack(
        job_id="job-xyz",
        story_id="story-1",
        out_path=str(out_path),
    )

    assert out_path.exists()
    text = out_path.read_text()
    assert "## Objective" in text
    assert "## Findings" in text
    assert "## Changed Files / Verification State" in text
    assert "## Unresolved Work" in text
    assert "## Must-Survive Constraints" in text
    assert "Add widget" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context.py -k write_context_pack -v`
Expected: FAIL with `AttributeError: module 'synlynk.context' has no attribute 'write_context_pack'`

- [ ] **Step 3: Implement `write_context_pack()`**

Add to `synlynk/context.py`, directly after `_generate_task_context()`'s closing lines (after line ~219, before `_generate_context_from_db` at line 220):

```python
def write_context_pack(job_id: str, story_id: str = None, out_path: str = None,
                        findings: list = None, changed_files: list = None,
                        unresolved: list = None, constraints: list = None) -> str:
    """Writes a job-scoped context-pack bundle (dec-0d7e75e0 R2 synthesis).

    Built once at dispatch time from the relevant story, rather than
    regenerated project-wide mid-job — this is the structural fix for the
    failure class gh:#2219/#2237 found (see
    docs/superpowers/specs/2026-10-12-context-window-optimization-design.md's
    "Corroborating evidence" section): a project-wide regenerated doc
    landing as an unasked-for diff inside an isolated job worktree.

    Returns the path written to.
    """
    out_path = out_path or os.path.join(".synlynk", "context-packs", f"{job_id}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    objective_line = f"(no story_id provided for job {job_id})"
    if story_id:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT title, engg_domain, org_domain, phase, role, status "
                "FROM stories WHERE story_id = ?",
                (story_id,),
            ).fetchone()
        finally:
            conn.close()
        if row:
            title, engg_domain, org_domain, phase, role, status = row
            objective_line = (
                f"{title} (story: {story_id}, domain: {engg_domain or 'unknown'}, "
                f"phase: {phase or 'unknown'}, role: {role or 'unknown'}, "
                f"status: {status or 'unknown'})"
            )

    def _bullet_list(items: list, empty_label: str) -> str:
        if not items:
            return f"- {empty_label}\n"
        return "".join(f"- {item}\n" for item in items)

    content = (
        f"# Context Pack — job {job_id}\n\n"
        "## Objective\n"
        f"{objective_line}\n\n"
        "## Findings\n"
        f"{_bullet_list(findings, 'No findings recorded yet.')}\n"
        "## Changed Files / Verification State\n"
        f"{_bullet_list(changed_files, 'No files changed yet.')}\n"
        "## Unresolved Work\n"
        f"{_bullet_list(unresolved, 'Nothing unresolved recorded yet.')}\n"
        "## Must-Survive Constraints\n"
        f"{_bullet_list(constraints, 'No constraints recorded yet.')}\n"
    )

    with open(out_path, "w") as f:
        f.write(content)

    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_context.py -k write_context_pack -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/context.py tests/test_context.py
git commit -m "feat: add write_context_pack() for job-scoped post-clear reload

Writes .synlynk/context-packs/<job-id>.md — objective/findings/changed-
files/unresolved-work/must-survive-constraints — built once at dispatch
time from the relevant story, per dec-0d7e75e0 R2 synthesis's
context-pack design. Modeled on the existing _generate_task_context(),
but produces the fuller section set R2 specifies rather than just a
todo-line + file-list dump.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-10-12-context-window-optimization-design.md`'s "Next steps after R2" and the R2 decision record):
- Instruction-writer template changes → Task 1 (GROK.md removal + reload-tier tagging) + Task 2 (actual content de-bloating of this repo's CLAUDE.md, since the generator's own skeleton was already lean — documented explicitly in "Context this plan assumes").
- `generate_context()` size-bounding/summarization → explicitly scoped out with evidence (already bounded on the migrated/DB path; legacy path is dead code in this repo) rather than left silent — see "Context this plan assumes."
- Dispatch-wrapper-layer-only budget/compaction logic → Task 3.
- Context-pack mechanism → Task 4.

**Placeholder scan:** no "TBD"/"similar to Task N"/unshown code — every step has literal before/after text or complete new function bodies. The one deliberately-marked manual step is Task 2 Step 3-5's `<!-- PASTE: ... -->` instruction, which is not a placeholder for *logic* — it's an explicit, correct instruction to copy exact live policy text byte-for-byte rather than have the plan itself embed a stale copy that could drift from the real file between plan-writing and execution.

**Type/signature consistency:** `check_context_compaction_trigger(job_id=None, threshold_tokens=60_000) -> dict` is defined once (Task 3 Step 3) and called identically in Task 3 Step 5 and tested identically in Steps 1 and 6. `write_context_pack(job_id, story_id=None, out_path=None, findings=None, changed_files=None, unresolved=None, constraints=None) -> str` is defined once (Task 4 Step 3) and called with matching keyword names in Step 1's test.

## Out of scope for this plan

- Actually shelling out to run `/compact` or `/clear` — Task 3's trigger only prints a recommendation and returns a signal dict; wiring that signal to an actual harness-specific compaction command is a separate follow-up (the R2 decision's compaction-trigger design describes *when* to fire, not a cross-harness `/compact` invocation mechanism, which doesn't exist yet for Codex/Agy/Grok).
- Reloading a context-pack automatically after a `/clear` — Task 4 only writes the pack; wiring it into a post-clear reload path is a separate follow-up once a compaction-firing mechanism exists.
- A second independent confirmation method for Codex's provisional reload tier (R2's own stated open item) — tracked separately, not blocking this plan, since Task 1 Step 5 already records the tier as explicitly provisional (`probed_no_evidence_of_per_turn_reload`), not silently upgraded to confirmed.
- Migrating `AI_INSTRUCTIONS.md` content — R2 explicitly says it stays the canonical, lazy-loaded shared reference doc as-is; no restructuring needed.
