---
title: "PR #244 — Measurement Ledger Phase 2: The Codex Structured-Output Adapter"
date: 2026-07-14
series: "Building the OS for Multi-Agent Development"
post: 56
pr: "#244"
merged: 2026-07-14
---

## The Broader Goal at the End of the Previous PR

Measurement Ledger Hardening Phase 1 (PR #236/#241/#242) shipped the cost ledger's provenance system: every `cost_entries` row now carries an explicit `cost_source` tag (`actual`, `estimated_token_rate`, `estimated_tshirt`, `estimated_manual`, `legacy_unknown`) and an `estimate_basis` sub-tier, enforced through a single write chokepoint (`_insert_cost_row()`) that SQLite itself rejects if the tag is omitted. The user's stated invariant — *never miss capturing cost of any implementation, even as an estimate, and never blend a guess in silently as if it were metered billing* — was structurally guaranteed by that point.

But Phase 1 also named its own biggest remaining weakness. `extract_tokens()` still produced its numbers by running five regex families against unstructured CLI stdout, falling back to an 80/20 input/output split heuristic when nothing matched. For subscription-billed agents — most of the fleet — `estimated_token_rate`'s accuracy was entirely downstream of how good that regex guess was. Phase 1's spec explicitly reserved a fourth `estimate_basis` value, `structured_output`, for exactly this gap, and scoped closing it out as Phase 2: one PR per agent, each wiring in that agent's own CLI-native structured-output mode. Codex — the most-dispatched agent in synlynk's own dispatch chain — was named as the pilot.

## Strategic Shifts in This PR

One real correction happened mid-design, caught before any code was written against it. The original draft of §3.3 (log readability) proposed a live Python background thread that would render Codex's `--json` output into human-readable prose as it streamed, writing to a `.jsonl` sibling file alongside the existing log. That mechanism doesn't work: `dispatch_agent()`'s background job path is fire-and-forget — the shell command is spawned via `subprocess.Popen(["sh", "-c", shell_cmd], stdout=DEVNULL, ..., start_new_session=True)`, and the parent CLI process exits almost immediately after spawning the detached shell. There is no live Python process left to host a rendering thread for the life of the job.

The design was revised in place (not silently rewritten — the correction is documented inline in the spec) to render lazily, at *read* time instead of write time. `log_file` stays raw JSONL for Codex jobs — the only copy, serving both as the parse source for token extraction and the render source for `synlynk logs`. The readability fix moved entirely into `cmd_logs()`, a synchronous, foreground, on-demand function with no process-lifetime problem to solve. This eliminated the `.jsonl` sibling-file convention before it ever existed: one file, one format, two consumers, nothing to keep in sync.

## What This PR Shipped

The adapter pattern: `extract_tokens()` gained an optional `agent: str = None` parameter. When `agent == "codex"`, it tries `_extract_codex_structured()` first; a `None` return (any failure — no valid JSON, no `turn.completed` event, missing `usage` key, non-numeric values) falls straight through to the existing regex chain, unchanged. No caller has to know which path fired; the fallback is automatic and silent, exactly matching Phase 1's "regex heuristic becomes an explicit last resort" language.

`_extract_codex_structured()` scans every line of the captured output (not just the last line — trailing blank lines and shell artifacts would break that assumption), looking for `{"type": "turn.completed", "usage": {...}}` events from `codex exec --json`. Live-verified schema, not guessed: `usage.input_tokens`, `usage.output_tokens` (plus `reasoning_output_tokens`, billed separately by the provider and folded into `out_tokens`), and `usage.cached_input_tokens` (mapped to the existing `cache_read_tokens` concept). Exactly one `turn.completed` event fires per invocation regardless of how many tool calls happen inside it — `usage` is cumulative, not per-turn.

Five files changed, six commits landed on top of the design/plan docs:

- **`synlynk/costs.py`** — `_extract_codex_structured()` added; confirmed `_resolve_cost_tier()` already handled `basis in ("regex_pair", "structured_output")` identically from Phase 1 — zero changes needed there, the extensibility point Phase 1 promised turned out to be real.
- **`synlynk/dispatch.py`** — `extract_tokens(output_text, agent=cmd_args[0])` at the foreground `exec_command()` call site; `--json` added to Codex's flag list in the existing `if agent == "codex":` block, additive alongside the pre-existing `--add-dir` injection.
- **`synlynk/jobs.py`** — all four `extract_tokens()` call sites across the reconcile/stall paths updated to pass `agent=`.
- **`synlynk/support_engineer.py`** — the one investigation-flow call site updated; `agent` was already in scope from `agent_cfg.get("investigator", "claude")`.
- **`synlynk/__init__.py`** — new `_render_codex_log_line()` helper, wired into `cmd_logs()`'s Codex branch. Renders `agent_message` items as prose, `command_execution` items as `$ <command>` + output, and intentionally omits `thread.started`/`turn.started`/`item.started`/`turn.completed` metadata events. Anything that fails to parse as JSON or isn't a recognized shape prints as-is, so a crashed job's raw stderr (e.g. an old Codex version rejecting `--json`) stays visible instead of disappearing.
- **`tests/test_cost_ledger.py`** — grew from 52 to 63 tests across the six implementation tasks.

**Process note, since it's part of what this PR actually demonstrates:** every task was dispatched to Codex via `synlynk dispatch codex --task "..." --force-agent`, and every dispatch was independently verified before being accepted — not by trusting Codex's self-reported pass/fail count, but by reading the actual `git diff` against the plan's spec and running `pytest` myself. That discipline caught two real defects. First, in an earlier segment: Codex's initial attempt at `_extract_codex_structured()` matched on `turn_completed` (underscore) instead of the live-verified `turn.completed` (dot notation) — a silent-failure bug that would have made every Codex job fall through to the regex heuristic while looking correct. Second, in this PR's final task: a full-suite regression pass (`pytest -q --ignore=worktrees`, run directly rather than trusting a task-scoped green result) surfaced a collateral break in `tests/test_ecosystem_status.py` — a test outside the plan's declared file scope that mocked `extract_tokens` with a positional-only lambda, broken by the new `agent=` keyword argument threaded through every call site. A scoped one-line fix (`lambda text, agent=None: (0, 0)`) resolved it, verified independently: 0 failed, 1079 passed, 2 skipped.

The dispatch chain itself ended up eight levels of nested job-worktrees deep by the time the fix landed, a byproduct of dispatching each task from inside the prior task's worktree. Despite the nesting, git history stayed strictly linear the whole way through — confirmed via `git log --all --graph` before merge — which is what made a clean `git merge --ff-only` (rather than a tangle of merge commits) possible when folding the chain back into the PR branch.

## Brainstorm Visuals Used

None — this design moved directly from the Phase 1 spec's reserved extension point through brainstorming dialogue to a written spec, without a visual-companion session. The JSONL schema and the fire-and-forget process-lifetime constraint that drove the §3.3 revision were both established by reading live code and running `codex exec --json` directly, not by diagramming.

## What This Achieved on the Path to Autonomy

This is the first of four planned per-agent structured-output adapters, and it validates the pattern end to end: an `if agent == "<name>":` branch inside `extract_tokens()`, a per-agent `_extract_<agent>_structured()` that returns `None` on any failure rather than raising, and a fallback to the existing regex chain that requires zero cooperation from the caller. Claude, Gemini, and Grok can each reuse this shape directly — investigate their own CLI's structured-output mode the same way Codex's was here (live-verified, not guessed from memory), write one function, add one branch, done.

More directly relevant to the PM/reviewer role this project runs under: this PR is itself evidence for the subagent-dispatch discipline it depends on. Every line of implementation code in this PR was written by Codex, not by Claude — and the two real defects that got caught (the `turn_completed` typo, the collateral `test_ecosystem_status.py` break) were both invisible to Codex's own self-report and only surfaced because the review step re-derives ground truth (reading diffs, running tests) instead of trusting a status field. That's the same lesson project memory already carries from issue #202 — never trust `synlynk jobs` status alone — now validated in the token-accuracy domain rather than the job-lifecycle domain.

## Strategic Note: The Goal at the End of This PR

v0.12.0 ("Trust & Cost-Aware Routing") was explicitly held for this PR — everything else in the theme was already on `main`, and the release was deliberately sequenced to ship with at least one real structured-output adapter live, not just the Phase 1 groundwork. With PR #244 merged, that release is unblocked.

The next goalpost is the same pattern, three more times: Claude's `-p --output-format stream-json`, Codex's now-proven approach reused as a template. Each is independently shippable, independently testable, and — per this PR's own out-of-scope list — deliberately not designed here, so each gets its own live-verified investigation rather than an assumption carried over from Codex's shape. Until all four land, a meaningful share of subscription-billed rows will keep resolving to `estimated_tshirt` (a coarse guess) rather than `estimated_token_rate` (a precise number, just relabeled) — that gap is the metric Phase 2's remaining PRs are closing.
