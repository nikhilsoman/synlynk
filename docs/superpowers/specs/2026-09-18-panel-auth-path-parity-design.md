# Decision-panel auth-path parity

**Status:** Approved for implementation by Home Harness

## Decision

Decision-panel preflight must enforce the same required auth-state paths as
dispatch preflight before invoking a harness. The core harness contract will be
tested parametrically so probe-only receipts distinguish auth/version coverage
from full model execution.

## Scope

- Validate expanded `required_paths` before running each panel auth probe.
- Return the missing paths in the structured diagnostic and terminal output.
- Add deterministic tests for all four core harnesses using isolated baseline
  fixtures and subprocess stubs.
- Add a probe receipt helper/test that records probe-only versus invocation
  coverage without contacting external model services.

## Safety

- Do not change credentials, keychains, canonical state.db, or live harness
  authentication.
- Do not invoke model inference in the regression suite.
- Preserve existing `_run_agent_sync` and decision-panel output contracts.

## Success condition

An absent required auth file fails panel preflight before CLI execution, and
all four core harnesses have passing deterministic coverage for auth, version,
execution failure, and safe identity diagnostics.
