# Design Spec: Eliminate Grok Headless Cancellation by Adopting --always-approve / bypassPermissions

- **Topic:** Eliminate Grok headless execution cancellation failure (\`stopReason: "cancelled"\`)
- **Author:** Agy (Gemini)
- **Status:** Approved / In Implementation
- **Target Release:** v0.18.1 / Fleet Parity
- **Issue:** #1277
- **Related Issues:** #714, #880, #1038, #1166 (LIVE-8), #1177

---

## 1. Problem Statement & Background

Headless dispatches to Grok (such as \`job-b3492d49\` for PR #1271 review, \`job-06a4f16f\` for PR #1176 review, and \`job-bd704d36\` for PR #1164 review) have repeatedly aborted mid-task with:
\`\`\`json
"stopReason": "cancelled",
"cancellationCategory": "PermissionCancelled"
\`\`\`
Previous investigations (e.g. \`docs/rca/2026-08-13-dispatched-pr-review-cancellation-714.md\`) concluded this was an inscrutable upstream black-box cancellation by xAI or an external session timeout.

### Root Cause
Deep inspection of Grok session event logs (\`events.jsonl\`, \`updates.jsonl\`) and binary reverse-engineering (\`crates/codegen/xai-grok-workspace/src/permission/\`) confirmed:
1. Grok uses \`run_terminal_command\` as its terminal execution tool name, while \`synlynk/dispatch.py\` maps permission flags using Claude tool names (\`Bash\`, \`Edit\`, \`Write\`).
2. When a dispatch lacks the full set of 5 permission grants (\`read:*\`, \`write:src/\`, \`write:docs/\`, \`run:tests\`, \`run:shell\`), \`_grok_permission_flags()\` emits:
   \`\`\`bash
   --permission-mode dontAsk --allow Bash ...
   \`\`\`
3. Grok's internal shell AST parser (\`bash_command_splitting.rs\`) and risk classifier (\`exec_risk.rs\`) parse multi-command shell lines (e.g. \`python3 -m pytest ... ; echo "FILTER_EXIT=\$?"\`). Because the command contains chaining or un-whitelisted patterns, Grok emits a permission prompt (\`permission_requested\`).
4. In \`dontAsk\` mode, Grok cannot prompt an operator. The prompt resolver immediately issues \`decision: "cancelled"\` (wait time 1ms), and Grok terminates the turn with \`stopReason: "cancelled"\`.

---

## 2. Proposed Architecture & Changes

### Layer 1: Dispatch Flag Generation (\`synlynk/dispatch.py\`)
Update \`_grok_permission_flags(permissions)\` in \`synlynk/dispatch.py\`:
- When running in headless mode, `--permission-mode dontAsk` is fatal whenever shell commands are executed.
- If `run:shell` or `run:tests` is granted (or whenever `permissions` is non-empty), emit `--always-approve` (or `--permission-mode bypassPermissions`), ensuring Grok executes authorized shell commands without triggering the fatal permission prompter auto-cancel.
- Align `_GROK_PERMISSION_RULES` to acknowledge Grok's native execution tool names.

### Layer 2: Constants & Baseline Specs (\`synlynk/_constants.py\`)
- In `HARNESS_CAPABILITY_BASELINES["grok"]["dispatch_flags"]`:
  - Ensure `--always-approve` and `--permission-mode bypassPermissions` are recognized as valid dispatch flags.
  - Set `"required_flags": ["--always-approve"]` for headless execution where appropriate.

### Layer 3: Living Baseline Records (\`docs/harness-capability-baseline.md\`)
- Update Grok capability notes to document that the historical `stopReason: "cancelled"` failure mode was traced to `--permission-mode dontAsk` in the dispatch wrapper and resolved via `--always-approve` / `bypassPermissions`.

---

## 3. Test & Verification Strategy

### TDD Plan
1. **Unit Tests (\`tests/test_dispatch.py\`):**
   - Add test asserting that `_grok_permission_flags(["read:*", "run:tests"])` and `_grok_permission_flags(["read:*", "run:shell"])` return `["--always-approve"]` (or `["--permission-mode", "bypassPermissions"]`) instead of `dontAsk`.
   - Verify that no headless Grok dispatch configuration produces `--permission-mode dontAsk` when test or shell permissions are granted.
2. **Empirical Validation:**
   - Execute live Grok dispatch running compound pytest and shell commands to verify that `stopReason: "end_turn"` is received cleanly.
