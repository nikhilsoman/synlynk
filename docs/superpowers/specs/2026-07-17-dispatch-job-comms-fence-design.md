# Task-Boundary Cost Fence — Design

**Status:** Approved (brainstorm session 2026-07-17)
**Story:** story-615bc8f4, GOVERNS goal-85656c82 (Developer Experience v1.0 (launch))
**Supersedes/absorbs:** GTM checklist item 6 (`docs/superpowers/specs/2026-07-16-gtm-checklist-agenda.md`) — "Add a header/footer row with a fence to every synlynk response at task boundary, to show the value of capability & cost optimization."

## Problem

synlynk already computes token/cost data at two points — a rough estimate before dispatch (`estimate_dispatch_tokens()`, `_estimate_story_cost_usd()`) and a real actual after a job completes (`_format_job_summary()`) — but neither is consistently surfaced to the user in a labeled, predictable format:

1. Dispatch-start messages (`cli.py:683`) print job id/PID but no cost estimate.
2. Job-completion summaries (`dispatch.py:_format_job_summary()`) print actual tokens/cost, but only when reconciliation runs (i.e., only if the user happens to invoke `jobs`/`watch`/`status` afterward) — not proactively, and with no reminder to check the fuller picture.
3. No other cost-incurring command (`exec`, `schedule --execute`, `release`) uses a consistent visual format for this data — each prints ad hoc.

This causes two adoption problems: users can't see the cost/value of an action before committing to it, and after a job completes they have no prompt to go check `watch`/`viz` for the fuller picture — cost visibility is passive rather than ambient.

## Scope

In scope: a shared fence-rendering module, wired into a **configurable allowlist** of commands, covering both pre-action estimates and post-action actuals, plus an always-on watch/viz reminder on completion-kind fences. This absorbs GTM item 6's full "every response at task boundary" ambition, bounded by the allowlist rather than hardcoded to all ~58 commands.

Out of scope (unchanged from the command-taxonomy spec, `docs/superpowers/specs/2026-07-17-command-taxonomy-and-trigger-registry-design.md`, "Out of scope" section): ambient ordinary-time HUD surfacing, taxonomy-browsing UI inside `watch`/`viz`. This design deliberately keeps the HUD manual — no fence ever auto-launches `viz`/`watch`; it only reminds the user to run it themselves.

## Data model — `synlynk/fencing.py` (new)

```python
from dataclasses import dataclass, field

@dataclass
class FenceData:
    command: str                          # e.g. "dispatch", "jobs"
    kind: str                             # "estimate" | "actual"
    in_tokens: int
    out_tokens: int
    cost_usd: float
    basis: str                            # "structured_output" | "tshirt" | "prompt_estimate" — reuses cost_source/estimate_basis vocabulary already established in costs.py (Measurement Ledger Hardening, epic #210)
    hints: list = field(default_factory=list)   # freeform lines appended below the cost line, e.g. ["Run `synlynk watch` for a live overview"]
    label: str = None                     # optional override for the fence header, e.g. job id. Defaults to command name.


def render_task_fence(data: FenceData) -> str:
    """Render a bordered fence block. Format:

    -- {label or command} {kind == 'estimate' and 'estimate' or 'complete'} ------
    cost:   {'~$' if estimate else '$'}{cost_usd:.2f}  ({in_tokens} in / {out_tokens} out, {basis})
    tip:    {hint}          # one line per hint, omitted entirely if hints is empty
    ------------------------------------
    """


def is_fenced_command(command: str, config: dict) -> bool:
    """True if `command` is in config['fenced_commands']. Missing key => empty allowlist (no fences), not an error."""
```

Two fence examples:

```
-- dispatch estimate ------------
cost:   ~$0.42  (28,000 in / 4,000 out, prompt_estimate)
------------------------------------
```

```
-- job-d63c4cf4 complete --------
cost:   $0.61  (3,916,492 in / 33,996 out, structured_output)
tip:    synlynk watch  —  live overview of all running jobs
------------------------------------
```

Formatting matches the existing `_format_job_summary()` fence style (`-- ... ---` header/footer) so it reads as one visual family rather than a competing format.

## Config — allowlist

`.synlynk/config.json` gains a `fenced_commands` key:

```json
{
  "fenced_commands": ["dispatch", "jobs", "exec", "schedule", "release"]
}
```

- Written as this default list by `init()` (`synlynk/__init__.py`), alongside the existing `limit_usd`/`limit_requests` keys.
- `is_fenced_command()` treats a missing key as an empty list (fences disabled), not an error — keeps existing projects that pre-date this feature working unchanged until they re-run `init` or hand-edit the config.
- Adding a command later is a one-line config change plus one `render_task_fence()` call site in that command's handler — no new code path.

## Call sites

All four are additive changes to existing print statements; none alter control flow or return values.

**1. Dispatch start** — `cli.py:683`, immediately after `job = dispatch_agent(...)` and before the existing `▶ [...] dispatched` line:
- New helper `estimate_dispatch_cost(prompt: str, context_md: str, agent: str, story_id: Optional[str]) -> FenceData` in `fencing.py`.
- Layered estimation: if `prompt`/`context_md` are available (i.e., `context_mode != "none"`), call `estimate_dispatch_tokens()` (`status.py:74`) for a payload-aware estimate, `basis="prompt_estimate"`. Otherwise fall back to `_estimate_story_cost_usd()` (`quota.py:294`)/t-shirt sizing (`costs.py:362`) keyed off the linked story's discipline/phase, `basis="tshirt"`.
- `kind="estimate"`, no hints (nothing to overview yet before the job has run).
- Only rendered if `is_fenced_command("dispatch", config)`.

**2. Job completion** — `dispatch.py:_format_job_summary()`, called from the four reconciliation sites in `jobs.py` (lines 905, 1002, 1170, 1278):
- `_format_job_summary()` already receives `in_tokens`, `out_tokens`, `cost_usd` computed from real data (`extract_tokens()` + `update_costs()` + `_job_cost_usd()`), `basis="structured_output"` (or whatever `extract_tokens()` reports).
- Gains a call to `render_task_fence()` internally, replacing the current bespoke `tokens:` line — same data, now routed through the shared renderer.
- `kind="actual"`, `hints=["Run `synlynk watch` for a live overview"]` — **always** appended (per brainstorm decision: every completion summary, not conditional on failure/multi-job state).
- Gated by `is_fenced_command("jobs", config)` — if `jobs` isn't in the allowlist, `_format_job_summary()` falls back to its current pre-fence format (no regression for projects that opt out).

**3. `exec`** — wherever `exec`'s existing cost/budget-pulse output is printed (`update_costs()` call site in `synlynk/__init__.py`'s `exec_command()`): wrap the already-computed `in_tokens`/`out_tokens`/cost in a `FenceData(kind="actual", basis=...)` and call `render_task_fence()` instead of the current ad hoc print. No new cost computation — this data already exists.

**4. `schedule --execute` / `release`** — same pattern: locate each command's existing cost-logging call site and swap the print for `render_task_fence()`. Both already compute cost via `synlynk cost log`-equivalent paths; this design does not add new cost computation for these two, only reformats what's already computed. (Exact call sites to be confirmed against current code at implementation time — `schedule.py` and the `release` command handler in `cli.py`.)

## Testing

- `tests/test_fencing.py` (new): `render_task_fence()` output format for estimate vs actual, with/without hints, label override; `is_fenced_command()` allowlist membership incl. missing-key default.
- `tests/test_dispatch.py`: assert the fence appears in dispatch-start stdout when `dispatch` is in `fenced_commands`, absent when it isn't.
- `tests/test_jobs.py`: assert `_format_job_summary()` output includes the fence + watch/viz tip line on completion; assert the allowlist gate falls back to the pre-existing format when `jobs` is not in `fenced_commands`.

## Non-goals (explicit)

- No fence auto-triggers the full HUD (`viz`/`watch`) — the tip line is text, always. This keeps the design outside the command-taxonomy spec's declared "ambient HUD surfacing" out-of-scope boundary.
- No new estimation math — `estimate_dispatch_tokens()`, `_estimate_story_cost_usd()`, `_estimate_tshirt_tokens()`, and `extract_tokens()`/`update_costs()`/`_job_cost_usd()` are reused as-is; this design is a presentation/wiring layer over existing cost machinery.
- `exec`/`schedule`/`release` call-site details are named at the function/file level here but not fully pinned to line numbers — the implementation plan's task for these three must re-verify current line numbers against `main` at dispatch time, since command-taxonomy Task 1 (build_parser extraction, PR #304) and Task 2 (in flight, job-5164f9a0) are landing on `cli.py` concurrently with this work.
