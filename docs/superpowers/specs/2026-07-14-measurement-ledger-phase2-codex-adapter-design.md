# Measurement Ledger Hardening — Phase 2 Pilot: Codex Structured-Output Adapter

**Status:** Draft for review
**Parent epic:** #210 (Structured Integration Layer)
**Depends on:** Measurement Ledger Hardening Phase 1 (PR #236/#241/#242, merged to `main`)
**Scope:** Establish the per-agent structured-output adapter pattern, and ship it for one agent (Codex) as the pilot. Claude, Gemini, and Grok adapters are follow-on PRs using the same pattern — not designed here.

---

## 1. Problem

Phase 1 built the cost ledger's provenance system: every `cost_entries` row is tagged with a `cost_source` (`actual` / `estimated_token_rate` / `estimated_tshirt` / `estimated_manual` / `legacy_unknown`) and an `estimate_basis` sub-tier. `extract_tokens()` currently produces one of three bases: `regex_pair` (a labeled "Input tokens: N / Output tokens: N" style match), `total_split` (an 80/20 guess off a single "Total tokens" line), or `none` (nothing matched).

Both `regex_pair` and `total_split` are guesses against unstructured CLI text. For subscription-billed agents (most of them), `estimated_token_rate`'s accuracy is entirely dependent on extraction accuracy — there's no invoice to cross-check against. Phase 1's spec (§4) already anticipated this and reserved a fourth basis value, `structured_output`, to be added per-agent as each agent's CLI native structured-output mode is wired in.

This design wires it in for Codex — the most-dispatched agent in this project's own workflow — and establishes the adapter pattern the other three agents will reuse.

## 2. What Already Exists (verified on `main`, not assumed)

Confirmed by reading `origin/main`'s current `synlynk/costs.py` and `synlynk/dispatch.py` directly (not from the Phase 1 plan document, which may drift from what actually shipped):

- `_resolve_cost_tier(agent, basis)` in `synlynk/costs.py` **already** handles `basis in ("regex_pair", "structured_output")` identically — both map to `estimated_token_rate` (or `actual`, if `_resolve_billing_mode(agent)` returns `"actual"`). **No changes needed to `_resolve_cost_tier()` or `update_costs()` for this design.** The extensibility point Phase 1 promised is real.
- `extract_tokens(output_text)` returns a `_TokenCounts` object (`input_tokens`, `output_tokens`, `cache_read_tokens`, `basis`) via a fixed regex-pattern list, with no `agent` parameter today.
- Two distinct call paths read job output and call `extract_tokens()`:
  - `dispatch.py:exec_command()` — the foreground `synlynk exec <agent>` path. Spawns the process itself via `subprocess.Popen(..., stdout=PIPE)`, tees output live to the terminal and an in-memory buffer via `_tee_process()`, then calls `extract_tokens(output_text)` on the accumulated buffer after the process exits.
  - `jobs.py:_reconcile_jobs()` (4 call sites) — the background `synlynk dispatch` path used for real implementation work. The job process is launched via a **raw shell redirect**: `f"{cmd_str} > {log_file} 2>&1"`, so the log file *is* the process's raw stdout/stderr, with no Python-side interception while it runs. Reconciliation later reads the log file's text and calls `extract_tokens(log_text)`.
- Codex is currently invoked (both paths) via `codex exec - -s workspace-write --add-dir <git-common-dir>` — no `--json` flag anywhere today.
- `codex exec --json` is a real, working flag (verified by running it locally). It switches Codex's stdout from a human-readable colored transcript to newline-delimited JSON events. Verified schema from two live runs:
  ```json
  {"type":"thread.started","thread_id":"019f609a-..."}
  {"type":"turn.started"}
  {"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello"}}
  {"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"...","aggregated_output":"","exit_code":null,"status":"in_progress"}}
  {"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"...","aggregated_output":"test1\n","exit_code":0,"status":"completed"}}
  {"type":"turn.completed","usage":{"input_tokens":39286,"cached_input_tokens":29824,"output_tokens":167,"reasoning_output_tokens":42}}
  ```
  Confirmed: exactly **one** `turn.completed` event per `codex exec` invocation, even when the run does multiple tool calls across several `command_execution` items — `usage` is cumulative for the whole invocation, not per-turn-of-conversation. `cached_input_tokens` is a subset of `input_tokens` (matches the existing `cache_read_tokens` concept). `reasoning_output_tokens` is billed separately from `output_tokens` by the provider.

## 3. Design

### 3.1 Adapter pattern: `extract_tokens()` becomes agent-aware

```python
def extract_tokens(output_text: str, agent: str = None) -> _TokenCounts:
    if agent == "codex":
        structured = _extract_codex_structured(output_text)
        if structured is not None:
            return structured
    # ... existing regex-pattern chain, unchanged, as fallback
```

`_extract_codex_structured(output_text)` returns a `_TokenCounts` with `basis="structured_output"` on success, or `None` on **any** failure (no valid JSON lines, no `turn.completed` event found, missing `usage` key, non-numeric values) — never raises. A `None` return falls straight through to the existing regex chain, which then runs against whatever text is available exactly as it does today for every other agent. This is the "regex heuristic becomes an explicit last-resort fallback" language from the Phase 1 spec, made concrete: the fallback is automatic and silent to the caller, not a separate code path callers have to invoke.

Future agents (Claude, Gemini, Grok) plug into the same `if agent == "<name>": ...` chain in `extract_tokens()`, each with their own `_extract_<agent>_structured()` — no new files, no registry abstraction needed for four agents. If a fifth or sixth agent is added later and this chain gets unwieldy, that's the trigger to extract a registry — not before (YAGNI).

**Call site changes** (mechanical, `agent` is already available at every one of these):
- `dispatch.py:exec_command()` — already computes `agent=cmd_args[0]` for `update_costs()`; pass the same value to `extract_tokens()`.
- `jobs.py:_reconcile_jobs()` (4 call sites) — each already has `job.get("agent")` in scope (used elsewhere in the same function, e.g. `_check_job_stall`). Pass `agent=job.get("agent")`.

### 3.2 Codex usage extraction: `_extract_codex_structured()`

```python
def _extract_codex_structured(output_text: str) -> Optional[_TokenCounts]:
    usage = None
    for line in output_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed":
            candidate = event.get("usage")
            if isinstance(candidate, dict):
                usage = candidate  # keep the last one seen
    if usage is None:
        return None
    try:
        in_tokens = int(usage["input_tokens"])
        out_tokens = int(usage["output_tokens"]) + int(usage.get("reasoning_output_tokens", 0))
        cache_read_tokens = int(usage.get("cached_input_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")
}
```

Scans every line rather than assuming the last line of output is the event (trailing blank lines, shell prompt artifacts, or a stray warning after the JSONL stream would otherwise break a last-line assumption). If multiple `turn.completed` events somehow appear (not observed in testing, but not proven impossible), the last one wins — consistent with "final state of the run" semantics used elsewhere in the codebase (e.g. `job["status"]` reflects the last known state).

### 3.3 Enabling `--json` and preserving log readability

Two things change for Codex's dispatch flags:

1. Add `--json` to Codex's flags in `dispatch_agent()`, in the same `if agent == "codex":` block that already appends `--add-dir`.
2. With `--json`, `log_file` becomes raw JSONL for Codex jobs. That's fine for `_extract_codex_structured()` (§3.2 already parses raw JSONL directly) but would be unreadable in `synlynk logs --job <id>` — a real UX regression from what every other agent's log looks like today.

**Revision from the originally-drafted design:** an earlier draft of this section proposed a live Python background thread (`_render_codex_jsonl_to_log`) that rendered JSONL into readable text as it streamed, plus a dual-write to a `.jsonl` sibling file. That mechanism doesn't work: Codex's job launch goes through `dispatch_agent()`'s fire-and-forget path — the shell command is spawned via `subprocess.Popen(["sh", "-c", shell_cmd], stdout=DEVNULL, stderr=DEVNULL, start_new_session=True, ...)`, and the parent CLI process (the one running `synlynk dispatch codex ...`) returns and exits almost immediately after. There is no live Python process left to host a rendering thread for the duration of a background job — log capture is owned entirely by the detached shell's own `>` redirect, independent of the parent's lifetime. This was caught during implementation planning, before any code was written against it.

**Corrected approach: render lazily, at read time, not write time.** Codex's job-launch shell command is completely unchanged from every other agent's — no new subprocess path, no sibling file, no dual-write. `log_file` simply contains raw JSONL for Codex jobs; it is the only copy of the log and serves as both the parse source for `_extract_codex_structured()` during reconciliation and the render source for display. The readability fix lives entirely in `cmd_logs()` (`synlynk/__init__.py:1978`, the `synlynk logs --job <id>` command), which is a synchronous, foreground, on-demand function with no lifetime problem:

- If `job["agent"] == "codex"`, `cmd_logs()` parses each line it's about to print as JSON and renders it instead of printing raw JSON:
  - `item.completed` with `item.type == "agent_message"` → render `item["text"]` followed by a blank line.
  - `item.completed` with `item.type == "command_execution"` → render `$ {item["command"]}` then `item["aggregated_output"]` (trimmed of trailing whitespace) then a blank line.
  - `item.started` and `turn.completed` events are recognized and intentionally not rendered (matches the original transcript intent: only completed/final item state and human-facing text belong in a log transcript, not metadata or partial state).
  - A line that fails to parse as JSON, or parses but isn't a recognized event shape, is printed **as-is** rather than dropped — this keeps a crashed job's raw stderr (e.g. "unrecognized flag: --json" from an old Codex version) visible instead of silently disappearing. Only lines that are valid, recognized, intentionally-suppressed events are omitted.
- For every other agent, `cmd_logs()`'s behavior is unchanged (prints `log_file` lines as-is).

This eliminates the `.jsonl` sibling-file convention entirely — one file, one format, two consumers, no dual-write to keep in sync. Trade-off: reading `log_file` directly outside `synlynk logs` (e.g. `tail -f` on the raw file) shows raw JSONL rather than prose. Accepted, since the stated requirement was that `synlynk logs --job <id>` show readable text, not that the raw file itself be prose.

Other agents' launch path (the shell-redirect string) is untouched.

### 3.4 Fallback behavior (explicit failure modes)

| Scenario | Result |
|---|---|
| Codex CLI version doesn't support `--json` (flag rejected, process exits nonzero immediately) | `log_file` contains Codex's stderr about the bad flag, not JSONL → `_extract_codex_structured()` finds no `turn.completed` line → returns `None` → regex chain runs against `log_file` (no usable output, but this is no worse than today's behavior for a crashed job); `cmd_logs()`'s Codex branch also just skips every unparseable line, so the raw stderr still prints as-is since it fails the JSON-parse check and falls through unrendered — same graceful degradation |
| `--json` accepted but `usage` object shape changes in a future Codex version (e.g. field renamed) | `KeyError`/`ValueError` caught → returns `None` → regex fallback (silently degrades to `total_split` or `none`, exactly like Phase 1's existing behavior for any unparseable agent output) |
| Job killed mid-run (stall-killer, SIGKILL) before a `turn.completed` event is emitted | No `turn.completed` line found → `None` → regex fallback. No behavior change from Phase 1. |
| Everything works | `basis="structured_output"` → `_resolve_cost_tier()` (unchanged) → `estimated_token_rate` or `actual` depending on billing mode |

No new failure mode can produce a dispatch error or a missing cost row — this preserves Phase 1's core invariant ("never miss capturing cost, even as an estimate").

## 4. Testing

- Unit tests for `_extract_codex_structured()` using real fixture JSONL (the two samples captured live during this design's research — one single-turn, one multi-tool-call) — asserts exact `in_tokens`/`out_tokens`/`cache_read_tokens`/`basis`.
- Edge cases: empty string → `None`; garbage/non-JSON lines mixed with a valid `turn.completed` line → still extracts correctly (proves line-by-line scanning, not whole-text parsing); `usage` missing `reasoning_output_tokens` (older Codex versions may not emit it) → falls back to `0`, doesn't raise; malformed `usage` (non-numeric value) → returns `None`.
- Unit test: `extract_tokens(text, agent="codex")` with valid Codex JSONL returns `basis="structured_output"`; `extract_tokens(text, agent="codex")` with plain-text (non-JSONL) input falls through to the existing regex chain unchanged; `extract_tokens(text, agent="claude")` (or any other/no agent) never calls the Codex path at all, regardless of input content — proves no cross-agent leakage.
- Unit test for `cmd_logs()`'s Codex rendering branch: feed fixture JSONL lines through the renderer, assert `agent_message`/`command_execution` items render as expected prose, `item.started`/`turn.completed` lines are omitted, and a non-JSON line (simulating a crashed pre-`--json` job or a stderr line) is printed as-is rather than dropped.
- Regression: full existing `extract_tokens()` test suite (all current regex-pattern tests) must still pass unmodified — the `agent` parameter defaults to `None` and every existing call site that doesn't pass it keeps today's behavior exactly.
- Run `pytest -q --ignore=worktrees` (project convention) with zero new failures.

## 5. Out of Scope (for this pilot design)

- Claude, Gemini, Grok structured adapters — each gets its own PR, own investigation of its actual CLI output (live-verified the same way Codex's was here, not guessed from memory), and can reuse §3.1's `if agent == "<name>":` pattern directly.
- Any change to `_resolve_cost_tier()`, `update_costs()`, or the `cost_entries` schema — none needed, per §2.
- IDE-embedded assistants, capability matrix hardening, local-agent scheduler — unchanged from Phase 1's own out-of-scope list (still out of scope, not re-litigated here).
- Retroactively re-extracting tokens for historical Codex job logs already written before this change lands — those rows keep whatever basis they were written with (Phase 1's historical-backfill rule: never retroactively upgrade a row's confidence tier).

## 6. Release Sequencing

Per explicit decision: this PR (the Codex pilot) **holds the v0.12.0 "Trust & Cost-Aware Routing" release**. Everything else in the theme (#236/#241/#242) is already merged to `main`; v0.12.0 is cut once this PR lands, giving the release at least one real structured-output adapter rather than shipping the groundwork alone.

## 7. Self-Review Notes

- **Placeholder scan:** none — every mechanism (adapter dispatch, usage-field mapping, read-time rendering, fallback table) is fully specified with real code or precise behavior, not sketched.
- **Internal consistency:** §3.3 was revised after an architectural flaw was caught during implementation planning (the originally-drafted live-thread renderer cannot survive `dispatch_agent()`'s fire-and-forget job-launch model, where the parent CLI process exits almost immediately after spawning the detached shell). The revision is noted inline in §3.3 rather than silently rewritten, consistent with this project's practice of flagging design corrections transparently. §3.4's fallback table and §4's tests were updated to match the corrected mechanism — no remaining reference to the `.jsonl` sibling file or the background rendering thread anywhere in the doc.
- **Scope check:** deliberately narrowed to one agent per the "pattern + pilot" decision; §5 makes the exclusion of the other three agents explicit rather than silent.
- **Ambiguity check:** "which `usage` object wins if multiple `turn.completed` events appear" is resolved explicitly (last one wins) even though not observed in testing, to avoid an undefined case later. "What happens to a line that isn't a recognized event" is resolved explicitly in §3.3 (printed as-is, not dropped) so a crashed job's raw error output stays visible in `synlynk logs` rather than disappearing silently.
