# Plan: harness parity preflight for decision panels

1. Extend harness baselines with safe auth probes and model/version metadata.
2. Add structured subprocess diagnostics and fail-closed panel orchestration.
3. Add regression tests for auth failure, non-zero/stderr-only failure,
   environment identity, model selection, and successful panel compatibility.
4. Run focused and full relevant tests, open PR linked to #1654, then use the
   QA merge gates and clean the worktree.
