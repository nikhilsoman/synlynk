# Fleet Parity: Grok `--cwd` and Codex `-C` Working Directory Protection — Implementation Plan

**Goal:** Close Issue #342 by enforcing explicit working-directory flags for Grok (`--cwd`) and Codex (`-C`) in `dispatch_agent()`, and injecting the working directory reminder header into Grok's prompt in `_format_prompt_for_agent()`.

**Architecture:** Defined in `docs/superpowers/specs/2026-08-30-grok-codex-cwd-protection-design.md`.

---

### Task 1: Grok Working Directory Prompt Formatting (TDD)

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing unit test for Grok prompt format**
  In `tests/test_synlynk.py`:
  Add `test_format_prompt_for_grok_includes_working_directory()` asserting `## Working Directory` and `{working_dir}` are present in Grok's prompt when `cwd_hint` is provided.

- [ ] **Step 2: Implement Grok branch in `_format_prompt_for_agent`**
  In `synlynk/dispatch.py`:
  Add `if agent == "grok":` branch returning prompt with `## Working Directory\n{working_dir}\nAll file edits MUST be in this directory.\n\n`.

- [ ] **Step 3: Verify test passes**
  Run `python -m pytest tests/test_synlynk.py -k test_format_prompt_for_grok_includes_working_directory`

---

### Task 2: Grok `--cwd` and Codex `-C` Flag Injection in `dispatch_agent()` (TDD)

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing unit tests for flag injection**
  In `tests/test_synlynk.py`:
  Add `test_grok_dispatch_includes_cwd_flag()` asserting `--cwd <worktree_path>` is present in shell command.
  Add `test_codex_dispatch_includes_c_flag()` asserting `-C <worktree_path>` is present in shell command.

- [ ] **Step 2: Implement flag injection in `dispatch_agent()`**
  In `synlynk/dispatch.py:dispatch_agent()`, right after `worktree_info` creation:
  ```python
  if agent == "grok" and worktree_path and "--cwd" not in flags:
      flags = flags + ["--cwd", worktree_path]
  if agent == "codex" and worktree_path and "-C" not in flags and "--cd" not in flags:
      flags = flags + ["-C", worktree_path]
  ```

- [ ] **Step 3: Verify tests pass**
  Run `python -m pytest tests/test_synlynk.py -k "cwd_flag or includes_c_flag"`

---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run complete `tests/test_synlynk.py` (496 tests)**
- [ ] **Step 2: Run `tests/test_dispatch.py` (107 tests)**
- [ ] **Step 3: Run `tests/test_agent_cli.py` (74 tests)**

---

### Task 4: Housekeeping & PR

- [ ] **Step 1: Write blog post in `docs/blog/`**
- [ ] **Step 2: Append memory entry to `project-docs/memory.md`**
- [ ] **Step 3: Update `project-docs/todo.md` and `project-docs/devlogs/`**
- [ ] **Step 4: Push branch and create PR for Issue #342**
