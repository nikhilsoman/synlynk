# Live Command Selftest — Design

**Status:** Approved (brainstorm session 2026-07-17)

**Source:** GTM checklist item 1 (`docs/superpowers/specs/2026-07-16-gtm-checklist-agenda.md`) — "Deep review of every synlynk command and its testing in a live repo scenario."

## Problem

`COMMAND_TAXONOMY` (`synlynk/taxonomy.py`) lists 59 distinct commands. The existing pytest suite (1218+ tests) exercises most of them, but almost entirely via mocked subprocess calls, mocked DB connections, and `tmp_path` fixtures that don't reproduce a real git repo's filesystem/state.db/config wiring end-to-end. There is no check that confirms every command actually works when run against a real, on-disk host repo the way a user would experience it — including the handful of commands that shell out to real paid agent CLIs (`dispatch`, `exec`, `schedule --execute`, `release`), where "works" means the full chain (context injection → subprocess → telemetry → fencing) actually completes, not just that argparse accepts the flags.

## Goal

A new command, `synlynk selftest`, that:
- Is driven entirely by `COMMAND_TAXONOMY` — no hand-maintained duplicate command list. Adding a taxonomy entry automatically puts it in scope.
- In its default (`synlynk selftest`) form: fast, free, safe to run often — argparse/`--help` wiring checks only, no real repo, no spend.
- In its `--live` form (`synlynk selftest --live`): runs every command from the taxonomy against a real throwaway git repo created fresh in a tempdir, including real invocations of the paid-agent-CLI commands with a trivial one-line prompt, capped at $2 total spend for the run.
- Is a manual, pre-release gate — not wired into CI, not scheduled. Run deliberately by Claude/PM before cutting a Named Release.

## Architecture

### `synlynk/selftest.py` (new module)

**`SELFTEST_SCENARIOS: dict[str, Callable[[ScenarioContext], ScenarioResult]]`**
A registry keyed by the taxonomy's `command` string (e.g. `"goal create"`, `"dispatch"`). Each entry is a scenario function that knows the minimal real args/setup needed to invoke that command meaningfully — e.g. `goal create` needs a title, `dispatch` needs a trivial one-line task, `story list` needs at least one story already created by an earlier scenario in the run.

Commands present in `COMMAND_TAXONOMY` but **without** a registered scenario fall back to a generic smoke check: run the command with `--help`, assert exit code 0. This means every taxonomy command is touched from day one, even before someone writes its bespoke scenario — coverage gaps show up as "generic fallback used" in the report rather than being silently skipped.

**`ScenarioContext`** — passed into every scenario function. Carries: the scratch repo's path, the live vs. dry-run flag, remaining budget (read from the scratch repo's own `.synlynk/config.json`), and a dict of state accumulated from earlier scenarios in the same run (e.g. the goal ID that `goal create`'s scenario returns, so `goal link`'s scenario can use it).

**`ScenarioResult`** — `command: str`, `status: Literal["pass", "fail", "skipped"]`, `detail: str`, `cost_usd: float = 0.0`.

**`run_selftest(live: bool = False) -> list[ScenarioResult]`**
Top-level driver:
1. If `live`, create a scratch git repo under a tempdir (`git init`, one throwaway commit so `HEAD` exists), write a `.synlynk/config.json` there with `budget.limit_usd` set to 2.0.
2. Iterate `COMMAND_TAXONOMY` entries **sorted by `maturity_tier`** (lower tiers first — this mirrors dependency order, since e.g. `init` (tier 0) must run before `dispatch` (tier 2) can find a project to dispatch into).
3. For each entry, look up its scenario in `SELFTEST_SCENARIOS`, or fall back to the generic `--help` check if `live` is False or no scenario is registered.
4. For scenarios that spend money (the paid-agent-CLI commands), check `ScenarioContext.remaining_budget` before invoking; if it would exceed the $2 cap, mark that scenario `"skipped"` with detail `"budget cap reached"` rather than running it — reuses the existing `check_budgets()` exit-on-exceed behavior for the ones that do run, so this pre-check is just an optimization to avoid needlessly invoking one right at the boundary.
5. Collect all `ScenarioResult`s, print a pass/fail summary table plus total spend, and return the list (also used as the function's contract for `cmd_selftest`'s exit code).

**`cmd_selftest(live: bool = False) -> None`**
CLI entry point. Calls `run_selftest(live=live)`, prints the report, and calls `sys.exit(1)` if any result has `status == "fail"`. `"skipped"` (including budget-capped skips) does not fail the run.

### CLI wiring (`synlynk/cli.py`)

New subparser:
```python
selftest_parser = subparsers.add_parser("selftest", help="Exercise every synlynk command (dry by default; --live runs against a real scratch repo)")
selftest_parser.add_argument("--live", action="store_true", help="Run against a real throwaway git repo, including real paid-agent-CLI invocations, capped at $2 total spend")
```
Dispatch: `elif args.command == "selftest": cmd_selftest(live=getattr(args, "live", False))`.

### Paid-agent-CLI scenarios

`dispatch`, `exec`, `schedule --execute`, and `release`'s scenarios each use a fixed trivial prompt (e.g. `"Reply with the single word OK and do nothing else."`) with `--force-agent` pinned to whichever agent is configured as default in the scratch repo's config, so the scenario is deterministic and doesn't depend on live agent-selection heuristics. Each scenario's `ScenarioResult.cost_usd` is populated from the same telemetry/cost-computation path `update_costs()` already uses, so the selftest report's total matches what `.synlynk/telemetry.json` would show for that scratch repo.

## Testing

- `tests/test_selftest.py`: mocked pytest coverage of `run_selftest()`'s orchestration logic (tier ordering, fallback-to-`--help` behavior, budget-cap skip logic, pass/fail aggregation) and `cmd_selftest()`'s exit-code behavior. Individual scenario functions are tested by mocking the underlying command call, the same pattern the existing suite already uses elsewhere.
- The `--live` run itself is not exercised by CI or the automated test suite — it is inherently a manual, spend-incurring, pre-release action, consistent with how `synlynk release` is already only ever run manually.

## Out of scope (deferred)

- **UX/output-quality audit** of each command's `--help` text and output formatting for GTM polish. Once `selftest --live` exists, its own console output becomes a natural place to eyeball every command's real output in one pass — worth revisiting as a lightweight manual follow-up, not built into this tool.
- **Taxonomy correctness audit** (do `governs_stage`/`maturity_tier`/`trigger_phrases` on each of the 59 entries actually match the command's real behavior). Orthogonal concern from "does the command run correctly" — a separate future pass.
