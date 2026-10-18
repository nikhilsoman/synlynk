# Synlynk for Visual Studio Code

Autonomous multi-agent engineering inside VS Code, Cursor, and Windsurf.

## Key capabilities

- **Non-Disruptive Leased Worktrees:** Dispatches run in isolated git
  worktrees, so your open file buffers and editor state remain untouched.
- **Adversarial Non-Author Review:** One model family writes (for example,
  Codex), while an independent model family audits (for example, Grok or
  Claude).
- **Invariant 1 Verification:** A task is complete only when it has a real git
  diff, a passing test oracle, and an AST change.
- **Goal-Linked Dispatch (GOVERNS):** Connect dispatches directly to project
  milestones and tracked spend.

## Quickstart

1. Install the Synlynk CLI: `pipx install synlynk`.
2. Open the Synlynk sidebar from the Activity Bar.
3. Run `Synlynk: Run Doctor Diagnostics` to verify installed agents.
4. Press `Cmd+Shift+P`, then select `Synlynk: Dispatch Task` to run your first
   worktree task.
