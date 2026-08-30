# Fleet Parity: Grok `--cwd` and Codex `-C` Working Directory Protection — Design

**Date:** 2026-08-30
**Status:** Approved
**Author:** Agy (implementer), brainstormed with Nikhil Soman
**Issue:** Resolves #342
**Tracking Story:** `story-e66de65c`
**Linked Goals:** `goal-a222b393`

---

## 1. Motivation & Problem Statement

Commit `8c1e124` fixed a critical issue where Agy (Gemini CLI) reset its internal working directory to a scratch location on startup, ignoring the intended worktree passed to `dispatch_agent()`. Because Gemini CLI had no CLI flag to enforce working directory root, the mitigation was a prompt header injected into `_format_prompt_for_agent`:
```markdown
## Working Directory
{working_dir}
All file edits MUST be in this directory.
```

Issue #342 identified that Grok CLI (`grok`) carries the identical risk surface:
1. Grok exposes an interactive auto-worktree flag (`-w, --worktree [<WORKTREE>]`), which can trigger auto-relocation away from the intended dispatch worktree.
2. Unlike Gemini CLI, Grok explicitly provides a structural flag: `--cwd <CWD>` ("Working directory").
3. However, `synlynk/dispatch.py` never passed `--cwd <worktree_path>` when dispatching Grok, and Grok fell into the default prompt formatter branch without a working directory reminder.
4. Similarly, Codex CLI provides `-C, --cd <DIR>` ("Tell the agent to use the specified directory as its working root, used for profile resolution and command execution"), which was also not passed explicitly in `dispatch_agent()`.

Without explicit flags and prompt guidance, dispatched jobs risk executing tools or placing edits in arbitrary directories outside their assigned worktree.

---

## 2. Design Decisions

### A. Grok Structural & Defense-in-Depth Protection
1. **CLI Flag Injection:**
   In `synlynk/dispatch.py:dispatch_agent()`, after the job worktree is resolved/created (`worktree_path`), append `["--cwd", worktree_path]` to `flags` when `agent == "grok"`.
   Guard with `if "--cwd" not in flags:` to prevent duplicate flag injection.
2. **Prompt Header:**
   In `_format_prompt_for_agent()` in `synlynk/dispatch.py`, add an explicit branch for `agent == "grok"` that includes the working directory header:
   ```markdown
   ## Working Directory
   {working_dir}
   All file edits MUST be in this directory.
   ```
   This ensures that even if Grok subagents or subshells are spawned, the model maintains situational awareness of its assigned root.

### B. Codex Working Directory Root Flag
1. **CLI Flag Injection:**
   In `synlynk/dispatch.py:dispatch_agent()`, after `worktree_path` is resolved/created, append `["-C", worktree_path]` to `flags` when `agent == "codex"`.
   Guard with `if "-C" not in flags and "--cd" not in flags:`.
   Codex already has its own structured prompt format (`## Task Criteria`, `## Context`), so the explicit CLI root `-C` provides structural enforcement.

### C. Claude & Local Harnesses
1. Claude and Local (aider) do not expose `--cwd`-equivalent flags in their CLIs and rely on the `cwd=worktree_path` passed to `subprocess.Popen()`. No CLI flag changes are needed for them.

---

## 3. Verification & Test Plan (TDD)

1. **Prompt Formatting Test:**
   * Test `_format_prompt_for_agent("grok", ...)` asserts `"## Working Directory"` and the provided `cwd_hint` are present in the formatted prompt.
2. **Flag Construction Tests:**
   * Test `dispatch_agent("grok", ...)` asserts `--cwd <worktree_path>` appears in the generated shell command before prompt execution.
   * Test `dispatch_agent("codex", ...)` asserts `-C <worktree_path>` appears in the generated shell command.
3. **Full Regression Suite:**
   * Verify all existing Grok and Codex dispatch tests pass without regression.
