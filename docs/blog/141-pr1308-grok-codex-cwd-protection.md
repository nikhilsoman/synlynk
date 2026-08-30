---
title: "PR #1308 — Fleet Parity: Enforce --cwd for Grok and -C for Codex with Working-Directory Protection"
date: 2026-08-30
series: "Building the OS for Multi-Agent Development"
post: 141
pr: "#1308"
issue: "#342"
merged: 2026-08-30
---

# PR #1308 — Fleet Parity: Enforce --cwd for Grok and -C for Codex with Working-Directory Protection

## The Broader Goal at the End of the Previous PR

PR #1306 established the canonical distinction between **Workspace Agents** (persistent org-chart roles like `dev`, `qa`, `architect`, `pm`) and **Harnesses** (swappable model execution backends like Claude, Codex, Grok, Agy, and Local). With that boundary stabilized, the next priority on the roadmap was addressing the remaining fleet-parity vulnerabilities under issue #342.

## What Was Missing

In early autonomous development experiments (commit `8c1e124`), Agy (Gemini CLI) reset its working directory to an internal scratch path upon launch, ignoring the target git worktree. Because Gemini CLI lacked a command-line `--cwd` flag, synlynk mitigated this by injecting an explicit `## Working Directory` prompt header reminding the model of its required root.

Issue #342 identified that Grok CLI (`grok`) carries the identical auto-relocation risk (`-w, --worktree`), yet was completely undefended:
1. `synlynk/dispatch.py` never passed Grok's native `--cwd <CWD>` flag.
2. Grok fell into the generic prompt formatter branch without the working-directory reminder.
3. Codex CLI similarly exposed `-C, --cd <DIR>` to lock its execution root, but was also dispatched without it.

If a harness resets or misinterprets its working root, file edits and tool executions can land silently outside the assigned worktree—a dangerous multi-agent failure mode.

## What Shipped

1. **Grok Structural Flag & Defense-in-Depth:**
   - In `synlynk/dispatch.py:dispatch_agent()`, dynamically appends `["--cwd", worktree_path]` to Grok's execution flags upon worktree creation.
   - Added a dedicated Grok prompt branch in `_format_prompt_for_agent()` that injects the `## Working Directory` reminder header.
2. **Codex Working Directory Root:**
   - In `synlynk/dispatch.py:dispatch_agent()`, dynamically appends `["-C", worktree_path]` to Codex's execution flags.
3. **Comprehensive Test Suite:**
   - Added unit test `test_format_prompt_for_grok_includes_working_directory` in `tests/test_synlynk.py`.
   - Added unit tests `test_grok_dispatch_includes_cwd_flag` and `test_codex_dispatch_includes_c_flag` in `tests/test_synlynk.py`.
   - Verified that all 499 tests in `tests/test_synlynk.py`, 107 in `tests/test_dispatch.py`, and 74 in `tests/test_agent_cli.py` pass cleanly.
