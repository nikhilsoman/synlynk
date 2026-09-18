# Harness parity preflight for decision panels

**Status:** Approved for implementation by Home Harness

## Decision

Decision panels must fail closed when any requested harness cannot authenticate
or cannot execute its headless command. The panel runner must preserve
diagnostics instead of converting failures into empty input, and it must expose
the execution identity used by the subprocess.

## Scope

- Add explicit auth probes to harness baselines where the CLI exposes one.
- Run the probe with the same environment/config identity as the panel command.
- Capture return code, stdout, stderr, timeout, executable path, working
  directory, and non-secret config identity.
- Support an optional explicit model for panel members and record the resolved
  model/version in each panel input.
- Abort before synthesis if any requested member fails preflight or execution.
- Keep `_run_agent_sync`'s string return contract for existing callers.

## Safety

- Never print or persist tokens, API keys, or full environment contents.
- Keep existing panel and decision-record formats compatible.
- Do not touch canonical state.db or repair authentication state in this task.

## Success condition

An unauthenticated or non-zero headless harness produces a deterministic,
actionable failure with diagnostics and no synthesis/decision record. A fully
available panel records the requested/resolved model and harness version.
