# Plan: Deduplicate Grok Boolean Dispatch Flags

Date: 2026-09-02
Issue: #1327

1. Add a stable boolean-flag normalization helper in `synlynk/dispatch.py`.
2. Apply it after all dispatch and permission flags are assembled, including
   harness-specific additions.
3. Add a regression test that captures a Grok launch and asserts one
   `--always-approve` when both sources provide it.
4. Update the blog index, memory, and Codex devlog with the design,
   implementation, and verification result.
5. Run the targeted test and `pytest tests/`.
