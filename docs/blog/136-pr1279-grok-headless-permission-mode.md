# PR #1279 — Eliminating Grok Headless Execution Cancellation via --always-approve

## Where we left off

Across issues #714, #880, #1038, and #1166 (LIVE-8), headless dispatches to Grok repeatedly aborted right before executing terminal actions (e.g. running pytest suites or executing \`gh pr review\`) with:
\`\`\`json
"stopReason": "cancelled"
\`\`\`
Previous root-cause investigations concluded that this was an inscrutable upstream black-box cancellation by xAI or an external session timeout, and Grok was downgraded out of the \`review\` fallback policy in PR #1177.

Earlier today, when Grok was assigned to review PR #1271 in \`job-b3492d49\`, it hit this exact cancellation on turn 4 while attempting to run its test suite.

## The Root Cause: The \`dontAsk\` Trap

Deep forensic inspection of Grok session event logs (\`events.jsonl\`, \`updates.jsonl\`) and binary reverse-engineering (\`crates/codegen/xai-grok-workspace/src/permission/\`) uncovered the exact root cause:

1. **Tool Schema Mismatch:**
   Grok's internal terminal execution tool is named \`run_terminal_command\`, whereas \`synlynk/dispatch.py:_grok_permission_flags()\` was attempting to map Claude tool names (\`Bash\`, \`Edit\`, \`Write\`).

2. **The \`dontAsk\` Cancellation Trap:**
   When a dispatch lacked all 5 full repo permissions (the standard for \`review\`, \`qa\`, or scoped \`dev\`), \`dispatch.py\` emitted \`--permission-mode dontAsk\`.
   Grok incorporates an internal shell AST splitter (\`bash_command_splitting.rs\`) and risk classifier (\`exec_risk.rs\`). When Grok generated compound commands (e.g. \`python3 -m pytest ... ; echo "FILTER_EXIT=\$?"\`), the classifier required confirmation (\`permission_requested\`). Because \`dontAsk\` mode suppresses operator prompts, the resolver immediately issued \`decision: "cancelled"\` (~1ms wait time), which terminated the turn with \`stopReason: "cancelled"\` and \`cancellationCategory: "PermissionCancelled"\`.

3. **Empirical Proof:**
   We tested this against the Grok CLI: running compound commands under \`--permission-mode dontAsk\` reproduced \`stopReason: "cancelled"\` in a single turn. Running the exact same commands under \`--always-approve\` or \`--permission-mode bypassPermissions\` succeeded with \`stopReason: "end_turn"\` and exit code 0.

## What this PR shipped

Following the Design Spec (\`docs/superpowers/specs/2026-08-30-grok-headless-permission-mode-design.md\`) and Implementation Plan (\`docs/superpowers/plans/2026-08-30-grok-headless-permission-mode.md\`), PR #1279 was dispatched to Grok itself (\`job-4ba2fb42\`) to fix its own execution mode:

- **\`synlynk/dispatch.py\`:**
  Updated \`_grok_permission_flags()\`: when \`run:shell\` or \`run:tests\` is present in the granted permission set, emit \`["--always-approve"]\`, eliminating the fatal \`dontAsk\` auto-cancellation path.
- **\`synlynk/_constants.py\`:**
  Added \`--permission-mode\` to Grok's \`valid_flags\`, and added \`--always-approve\` to \`required_flags\` for Grok headless dispatches.
- **Test Suite Updates:**
  - Added \`test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted\` in \`tests/test_dispatch.py\`.
  - Reconciled existing tests in \`tests/test_synlynk.py\` and \`tests/test_agent_quota_tracking.py\` to align with the new flag contract.
- **Documentation:**
  Updated \`docs/harness-capability-baseline.md\` to document the resolution of the historical cancellation pattern.

## Review and Merge Flow

- **Authorship:** Implemented by Grok via \`synlynk dispatch\` (\`job-4ba2fb42\`, commit \`41c8070\`).
- **Review:** Reviewed by Agy (\`synlynk pr check\` passed, all GitHub Actions CI checks passed green across Python 3.8, 3.10, 3.12, and \`qa-gate\`, formal review checklist posted).
- **Merge:** Merged to \`main\` as \`68a7bd4d311bb2ca9ff370cac92f33c6eedf2633\`.

## Where this leaves the fleet

Grok headless dispatch is now stabilized against the multi-command permission cancellation bug. With Codex unblocked and operating with full harness parity (PR #1275), and Grok headless cancellation resolved, synlynk now possesses robust multi-harness redundancy across all execution tracks.
