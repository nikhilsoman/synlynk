# GOVERNS Lifecycle Checkpoint Directives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixed "Lifecycle checkpoint directives" subsection to synlynk's generated instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`, `AI_INSTRUCTIONS.md`) that tells agents to suggest `synlynk goal create` at two specific moments — brainstorming-skill completion and writing-plans-skill completion — when no GOVERNS goal is linked to the work.

**Architecture:** One new pure function, `render_lifecycle_checkpoint_section()`, added next to the existing `render_trigger_phrase_section()` in `synlynk/instructions.py`. It returns a fixed string (no parameters, no dependency on `COMMAND_TAXONOMY`). `_build_templates()` calls it once and appends its output, via a blank line, after the existing `_trigger_registry_section` in all five template strings that currently include the trigger registry.

**Tech Stack:** Python 3, pytest. No new dependencies, no CLI changes, no schema changes.

---

### Task 1: Write the failing test for `render_lifecycle_checkpoint_section()`

**Files:**
- Test: `tests/test_instructions.py`

- [ ] **Step 1: Add the failing test**

Add this test to `tests/test_instructions.py`, directly after `test_tier2_fixture_gets_tier0_through_tier2_phrases` (currently ending at line 67):

```python
def test_render_lifecycle_checkpoint_section_returns_fixed_block():
    from synlynk.instructions import render_lifecycle_checkpoint_section

    section = render_lifecycle_checkpoint_section()
    assert section == (
        "## Lifecycle checkpoint directives\n"
        "\n"
        "- When a brainstorming session (per the brainstorming skill) concludes with\n"
        "  an approved, written spec, and no active GOVERNS goal is linked to the\n"
        "  work: suggest `synlynk goal create --outcome <spec's one-line thesis>\n"
        "  --criterion <spec's stated success condition>` before transitioning to\n"
        "  implementation planning. This is a suggestion, not a gate — proceed if\n"
        "  the user declines or the work is explicitly one-shot/maintenance.\n"
        "- When an implementation plan (per the writing-plans skill) is approved\n"
        "  and about to enter execution, and the plan's spec has no linked goal:\n"
        "  same suggestion, offered once.\n"
        "- Do not suggest goal creation at any other point in a session (not on\n"
        "  ordinary command usage, not on phrase matches, not mid-brainstorm)."
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_instructions.py::test_render_lifecycle_checkpoint_section_returns_fixed_block -v`
Expected: FAIL with `ImportError: cannot import name 'render_lifecycle_checkpoint_section' from 'synlynk.instructions'`

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_instructions.py
git commit -m "test: add failing test for render_lifecycle_checkpoint_section"
```

---

### Task 2: Implement `render_lifecycle_checkpoint_section()`

**Files:**
- Modify: `synlynk/instructions.py:47` (immediately after `render_trigger_phrase_section`, before the blank line and `def _generate_ai_context_files`)

- [ ] **Step 1: Add the function**

In `synlynk/instructions.py`, the file currently reads (lines 37-49):

```python
def render_trigger_phrase_section(current_tier: int) -> str:
    """Render the trigger-registry subsection injected into instruction files."""
    entries = [
        entry for entry in entries_up_to_tier(current_tier)
        if entry["audience"] == "human" and entry["trigger_phrases"]
    ]
    lines = ["## Trigger registry", ""]
    for entry in entries:
        phrases = ", ".join(f'"{phrase}"' for phrase in entry["trigger_phrases"])
        lines.append(f"- {phrases} -> `synlynk {entry['command']}`")
    return "\n".join(lines)

def _generate_ai_context_files(arch_context: str, git_summary: str) -> None:
    """Appends a context snapshot section to CLAUDE.md, GEMINI.md, AGENTS.md.
```

Replace it with (inserting the new function and a blank line between `render_trigger_phrase_section` and `_generate_ai_context_files`):

```python
def render_trigger_phrase_section(current_tier: int) -> str:
    """Render the trigger-registry subsection injected into instruction files."""
    entries = [
        entry for entry in entries_up_to_tier(current_tier)
        if entry["audience"] == "human" and entry["trigger_phrases"]
    ]
    lines = ["## Trigger registry", ""]
    for entry in entries:
        phrases = ", ".join(f'"{phrase}"' for phrase in entry["trigger_phrases"])
        lines.append(f"- {phrases} -> `synlynk {entry['command']}`")
    return "\n".join(lines)


def render_lifecycle_checkpoint_section() -> str:
    """Render the fixed GOVERNS-lifecycle checkpoint subsection injected into
    instruction files, directly beneath the trigger registry.

    Unlike render_trigger_phrase_section, this is not derived from
    COMMAND_TAXONOMY — it's a small, hand-written set of skill-completion
    checkpoints (brainstorming-skill and writing-plans-skill conclusion),
    not a per-command phrase-matching registry.
    """
    return (
        "## Lifecycle checkpoint directives\n"
        "\n"
        "- When a brainstorming session (per the brainstorming skill) concludes with\n"
        "  an approved, written spec, and no active GOVERNS goal is linked to the\n"
        "  work: suggest `synlynk goal create --outcome <spec's one-line thesis>\n"
        "  --criterion <spec's stated success condition>` before transitioning to\n"
        "  implementation planning. This is a suggestion, not a gate — proceed if\n"
        "  the user declines or the work is explicitly one-shot/maintenance.\n"
        "- When an implementation plan (per the writing-plans skill) is approved\n"
        "  and about to enter execution, and the plan's spec has no linked goal:\n"
        "  same suggestion, offered once.\n"
        "- Do not suggest goal creation at any other point in a session (not on\n"
        "  ordinary command usage, not on phrase matches, not mid-brainstorm)."
    )


def _generate_ai_context_files(arch_context: str, git_summary: str) -> None:
    """Appends a context snapshot section to CLAUDE.md, GEMINI.md, AGENTS.md.
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_instructions.py::test_render_lifecycle_checkpoint_section_returns_fixed_block -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add synlynk/instructions.py
git commit -m "feat: add render_lifecycle_checkpoint_section"
```

---

### Task 3: Wire the new section into `_build_templates()`

**Files:**
- Modify: `synlynk/instructions.py:409` (assignment) and lines `529, 554, 579, 604, 617` (five template-string usages)

- [ ] **Step 1: Write the failing integration test**

Add this test to `tests/test_instruction_reach.py`, directly after `test_gemini_md_template_has_no_transition_note` (currently ending at line 20):

```python
def test_build_templates_includes_lifecycle_checkpoint_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _build_templates
    templates = _build_templates()
    for key in ("CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md", "AI_INSTRUCTIONS.md"):
        content = templates[key]
        assert "## Lifecycle checkpoint directives" in content
        assert "synlynk goal create" in content
        # Checkpoint section must come after the trigger registry, in the same block
        assert content.index("## Trigger registry") < content.index("## Lifecycle checkpoint directives")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_instruction_reach.py::test_build_templates_includes_lifecycle_checkpoint_section -v`
Expected: FAIL — `AssertionError` (`"## Lifecycle checkpoint directives" in content` is False) for `CLAUDE.md` (first key checked).

- [ ] **Step 3: Add the assignment in `_build_templates()`**

In `synlynk/instructions.py`, line 409 currently reads:

```python
    _trigger_registry_section = render_trigger_phrase_section(_current_trigger_registry_tier())
```

Change it to:

```python
    _trigger_registry_section = render_trigger_phrase_section(_current_trigger_registry_tier())
    _lifecycle_checkpoint_section = render_lifecycle_checkpoint_section()
```

- [ ] **Step 4: Append the section in all five templates**

Each of the five templates ends with `... + _session_protocol + "\n\n" + _trigger_registry_section` (or, for `_ai_instructions_md`, the same pattern without the preceding domain-ownership block). Update each occurrence to append `+ "\n\n" + _lifecycle_checkpoint_section` after `_trigger_registry_section`.

In `_claude_md` (currently lines 527-530):

```python
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section
    )
```

becomes:

```python
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )
```

Apply the identical change (replace `+ _trigger_registry_section\n    )` with `+ _trigger_registry_section + "\n\n"\n        + _lifecycle_checkpoint_section\n    )`) to the closing of `_gemini_md` (currently lines 552-555), `_agents_md` (currently lines 577-580), `_grok_md` (currently lines 602-605), and `_ai_instructions_md` (currently lines 615-618). All five have the exact same trailing three lines:

```python
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section
    )
```

Each becomes:

```python
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_instruction_reach.py::test_build_templates_includes_lifecycle_checkpoint_section -v`
Expected: PASS

- [ ] **Step 6: Run the full instructions-related test suite to check for regressions**

Run: `python -m pytest tests/test_instructions.py tests/test_instruction_reach.py -v`
Expected: All tests PASS (no prior test asserts an exact full-file string that this appended content would break — existing tests only check for substring presence/absence, e.g. `test_gemini_md_template_has_no_transition_note` checks `"2026-06-18" not in templates["GEMINI.md"]` and `"agy-2.x" in templates["GEMINI.md"]`, neither of which the new section affects).

- [ ] **Step 7: Commit**

```bash
git add synlynk/instructions.py tests/test_instruction_reach.py
git commit -m "feat: wire lifecycle checkpoint section into generated instruction templates"
```

---

### Task 4: Run the full test suite

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `python -m pytest -q`
Expected: All tests pass, 0 failures. (This catches any other test in `tests/test_synlynk.py` or elsewhere that asserts exact template content — if one fails, update it to account for the new trailing section following the same pattern as Task 3.)

- [ ] **Step 2: Commit if any fixes were needed**

Only if Step 1 required changes:

```bash
git add -A
git commit -m "test: fix template-content assertions for lifecycle checkpoint section"
```

---

## Self-Review

**Spec coverage:**
- "New section: lifecycle checkpoint directives" with the exact fixed text block → Task 1 (test) + Task 2 (implementation), text matches the spec verbatim.
- "This block is appended into the same fenced region... directly beneath `## Trigger registry`" → Task 3 wires it after `_trigger_registry_section` in all five templates and asserts ordering.
- "No new skills catalog" / "no new CLI command or flag" / "no schema changes" → nothing in this plan touches `synlynk/cli.py`, `synlynk/taxonomy.py`, or any config schema. Confirmed no such task exists.
- "Testing" section's requirement (assert function returns the fixed block verbatim, assert it appears in generated `CLAUDE.md` content) → Task 1 covers the verbatim-return assertion; Task 3 covers the generated-content assertion, extended to all five instruction files per the spec's "ships now" scope (not just `CLAUDE.md`) since all five already carry `_trigger_registry_section`.
- "No behavioral/integration test... needed" → no such test was added.
- Non-Goals (no `COMMAND_TAXONOMY` change, no CLI change, no Tier-2 fallback change, no domain-adaptivity) → none of the four tasks touch `synlynk/taxonomy.py`, `synlynk/cli.py`, or `_current_trigger_registry_tier()`.

**Placeholder scan:** No TBD/TODO, no "similar to Task N," no vague error-handling steps. All code blocks are complete and copy-pasteable.

**Type consistency:** `render_lifecycle_checkpoint_section()` takes no arguments and returns `str`, consistent with its single call site in `_build_templates()` (Task 3, Step 3) and its test (Task 1). Variable name `_lifecycle_checkpoint_section` is used identically in the assignment (Task 3 Step 3) and all five append sites (Task 3 Step 4).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-23-governs-lifecycle-engagement-design.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
