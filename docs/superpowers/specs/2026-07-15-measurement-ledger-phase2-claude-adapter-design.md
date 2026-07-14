# Measurement Ledger Hardening — Phase 2, Agent 2: Claude Structured-Output Adapter

**Status:** Draft for review
**Parent epic:** #210 (Structured Integration Layer)
**Depends on:** Measurement Ledger Hardening Phase 1 (PR #236/#241/#242, merged), Phase 2 Codex pilot (PR #244/#245, merged — establishes the adapter pattern this design reuses)
**Scope:** Second of four per-agent structured-output adapters. Gemini/Agy and Grok remain, each its own follow-on PR per the Codex pilot's §5 scoping.

---

## 1. Problem

Phase 2's Codex pilot (`docs/superpowers/specs/2026-07-14-measurement-ledger-phase2-codex-adapter-design.md`) established `extract_tokens(output_text, agent=None)` as an agent-aware dispatcher: pass `agent="codex"` and it tries `_extract_codex_structured()` first, falling back to the existing regex chain on any failure. `claude` is the most-dispatched agent's Phase-1 sibling in usage frequency and, per epic #210's own body, the next adapter in sequence (`claude -p --output-format stream-json`).

Today `extract_tokens()` has no Claude-specific branch — Claude job output is parsed by the same regex-pattern chain used for every unstructured agent, with the same `regex_pair`/`total_split`/`none` basis ceiling Phase 1 flagged as a guess against unstructured text.

## 2. What Already Exists (verified live, not assumed)

Confirmed by running `claude -p --output-format stream-json --verbose` locally (twice — one plain single-turn prompt, one two-turn prompt that used the Bash tool) and by reading `origin/main`'s current `synlynk/dispatch.py`, `synlynk/costs.py`, and `synlynk/__init__.py` directly:

- `claude -p --output-format stream-json` **requires** `--verbose` — the CLI refuses to run without it (`Error: When using --print, --output-format=stream-json requires --verbose`). This is not optional tuning; it's a hard flag dependency.
- With `--verbose`, the stream includes `SessionStart` hook events (`system`/`hook_started`/`hook_response`) before any assistant output — this project's own hooks fire and get dumped into the JSONL. This is noisier than Codex's stream, which has no equivalent hook-event category.
- Confirmed event shape from two live runs:
  ```json
  {"type":"system","subtype":"hook_started", "...": "..."}
  {"type":"system","subtype":"hook_response", "...": "..."}
  {"type":"system","subtype":"init","cwd":"...","tools":[...],"model":"claude-sonnet-5", "...": "..."}
  {"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"hello"}],"usage":{...}}, "...": "..."}
  {"type":"rate_limit_event","rate_limit_info":{...}}
  {"type":"result","subtype":"success","is_error":false,"num_turns":1,"result":"hello","total_cost_usd":0.1175592,"usage":{"input_tokens":2,"cache_creation_input_tokens":18810,"cache_read_input_tokens":15444,"output_tokens":4,"...":"..."}}
  ```
  A two-turn run (prompt asked the model to run `ls` via Bash, then reply) produced `num_turns:2`, two `assistant` events (first with a `tool_use` content block, second with the final `text` block), an intervening `user`-role event carrying the `tool_result` content block, and still **exactly one** `result` event at the end with cumulative `usage`.
- `usage.input_tokens` and `usage.cache_creation_input_tokens` are **separate, additive** pools, not one nested in the other — unlike Codex's `cached_input_tokens`, which is a subset of `input_tokens`. In the two-turn sample: `input_tokens: 4`, `cache_creation_input_tokens: 14177`, `cache_read_input_tokens: 55170`. Treating `cache_creation_input_tokens` as free would undercount actual token volume by orders of magnitude.
- `usage.total_cost_usd` (top-level, sibling of `usage`, not inside it) is a CLI-computed dollar figure — present in both live samples ($0.1175592 and $0.10485). No other agent's structured output reports a dollar amount.
- `synlynk/_constants.py`'s `claude` baseline: `"non_interactive_flags": ["--print"]`, `"dispatch_flags": ["--dangerously-skip-permissions"]`.
- `dispatch_agent()` in `synlynk/dispatch.py` already has an `if agent == "codex": flags = flags + ["--json"] ...` block (and a separate `if agent == "grok": flags = flags + ["--output-format", "json"]` block, pre-existing and unrelated to token extraction) — a sibling `if agent == "claude":` block is the established insertion point.
- All three `extract_tokens()` call sites (`dispatch.py:exec_command()`, `jobs.py:_reconcile_jobs()` ×4, `support_engineer.py`'s investigate flow) already pass `agent=` — wired through during the Codex PR. No call-site signature changes needed here.
- `cmd_logs()` (`synlynk/__init__.py:2005`) already special-cases `job.get("agent") == "codex"` and delegates to `_render_codex_log_line()` (`synlynk/__init__.py:1978`) per-line, printing raw lines for every other agent. This is the extension point for Claude's renderer.

## 3. Design

### 3.1 Adapter dispatch: extend the existing `if` chain

```python
def extract_tokens(output_text: str, agent: str = None) -> _TokenCounts:
    if agent == "codex":
        structured = _extract_codex_structured(output_text)
        if structured is not None:
            return structured
    if agent == "claude":
        structured = _extract_claude_structured(output_text)
        if structured is not None:
            return structured
    # ... existing regex-pattern chain, unchanged, as fallback
```

No registry introduced — per the Codex spec's §3.1 note, that's the trigger for a fifth/sixth agent, not the second.

### 3.2 Claude usage extraction: `_extract_claude_structured()`

```python
def _extract_claude_structured(output_text: str) -> Optional[_TokenCounts]:
    usage = None
    for line in output_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            candidate = event.get("usage")
            if isinstance(candidate, dict):
                usage = candidate  # keep the last one seen
    if usage is None:
        return None
    try:
        in_tokens = int(usage["input_tokens"]) + int(usage.get("cache_creation_input_tokens", 0))
        out_tokens = int(usage["output_tokens"])
        cache_read_tokens = int(usage.get("cache_read_input_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")
```

Mirrors `_extract_codex_structured()`'s shape exactly (line-by-line scan, last-`result`-wins, never raises). Two deliberate mapping choices, made here rather than left ambiguous:

- **`cache_creation_input_tokens` folds into `in_tokens`.** Live testing showed it can be 3-4 orders of magnitude larger than `input_tokens` alone (18810 vs 2). Phase 1's rate table (`_model_rate_for_version()`) has exactly three tiers — `input`, `output`, `cache_read` — with no cache-write tier. Folding cache-creation into `input_tokens` prices it at the plain input rate, which undercounts Anthropic's actual cache-write premium (roughly 1.25x–2x input, depending on TTL) but is the only mapping available without adding a new rate-table column and new `_insert_cost_row()` field — out of scope for an adapter PR that Phase 1 spec's §5 already closed off (schema changes). Dropping it entirely (treating cache-creation as free) was rejected: it would make Claude jobs with large cache writes look artificially cheap, which is a worse error than a modest underestimate.
- **`total_cost_usd` is read but discarded.** Confirmed present and accurate to Anthropic's actual per-token accounting in both live samples. Not wired into `update_costs()` — per explicit decision, keeping every agent's adapter emit token-counts-only preserves `_resolve_cost_tier()`'s existing contract (basis in → cost_source out, no per-agent special-casing) and keeps the pattern identical for the two adapters still to come (Gemini, Grok), neither of which is known yet to report a dollar figure. Revisiting this is a future, separately-scoped enhancement if Claude's own reported cost proves materially more accurate than the rate-table math in practice.

### 3.3 Dispatch flags: enabling `--output-format stream-json --verbose`

`synlynk/dispatch.py:dispatch_agent()` gains a sibling block to the existing Codex one:

```python
if agent == "claude":
    flags = flags + ["--output-format", "stream-json", "--verbose"]
```

`--verbose` is not optional (§2) — omitting it is not a valid alternative flag combination to consider. `claude`'s baseline already includes `--print` via `non_interactive_flags`, so the full invocation becomes `claude --print --dangerously-skip-permissions --output-format stream-json --verbose ...` (permission/role flags from `_permissions_to_flags()` still append after, unchanged).

`log_file` becomes raw JSONL for Claude jobs, same as it does for Codex jobs post-`--json`. Same UX problem, same fix location: `cmd_logs()`, not the write path (Claude jobs go through the identical fire-and-forget `dispatch_agent()` → detached-shell-redirect launch as Codex; the Codex spec's §3.3 architectural finding — no live Python process survives to host a streaming renderer — applies identically here, so this design renders lazily at read time from the start rather than repeating that discovery).

### 3.4 Log readability: `_render_claude_log_line()`

Added alongside `_render_codex_log_line()` in `synlynk/__init__.py`. `cmd_logs()`'s dispatch changes from a single `if job.get("agent") == "codex":` check to:

```python
if job.get("agent") == "codex":
    renderer = _render_codex_log_line
elif job.get("agent") == "claude":
    renderer = _render_claude_log_line
else:
    renderer = None
if renderer is not None:
    for line in display_lines:
        rendered = renderer(line)
        if rendered is not None:
            print(rendered, end="")
else:
    for line in display_lines:
        print(line, end="")
```

```python
def _render_claude_log_line(line: str):
    """Renders one line of a Claude --output-format stream-json log into
    human-readable text."""
    stripped = line.strip()
    if not stripped:
        return line
    try:
        event = json.loads(stripped)
    except (ValueError, TypeError):
        return line
    if not isinstance(event, dict):
        return line
    event_type = event.get("type")
    if event_type in {"system", "rate_limit_event", "result", "user"}:
        return None
    if event_type == "assistant":
        message = event.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(content, list):
            return None
        rendered_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "")
                if text:
                    rendered_parts.append(f"{text}\n\n")
            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                try:
                    args = json.dumps(tool_input, separators=(",", ":"))
                except (TypeError, ValueError):
                    args = str(tool_input)
                rendered_parts.append(f"$ {tool_name}({args})\n\n")
        return "".join(rendered_parts) if rendered_parts else None
    return line
```

Coverage of the 7 event types confirmed live in §2:
- `system` (any subtype) → suppressed (hook noise, session init metadata — not transcript content)
- `rate_limit_event` → suppressed (telemetry, not transcript content)
- `result` → suppressed (its `usage`/`total_cost_usd` feed the ledger via §3.2, not the log; its `result` text duplicates the final `assistant` turn's text, already rendered)
- `user` → suppressed. This is where `tool_result` content blocks land in the stream (confirmed in the two-turn live sample). Not correlated back to the `tool_use` call that produced it — matches Codex's renderer, which also only shows `aggregated_output`, a single field, not a full request/response pairing. Scoped identically: show what the agent said and what it ran, not the full round-trip of every tool call.
- `assistant` → `text` blocks render as prose; `tool_use` blocks render as `` $ ToolName({...}) `` — mirrors Codex's `` $ {command} `` line for `command_execution` items.
- Any line that fails JSON parsing, or parses but isn't a recognized `type` → printed as-is (unrecognized future event types, or a pre-`--verbose`/pre-flag-change job's plain-text crash output, stay visible rather than silently vanishing — same rule as Codex's renderer).

### 3.5 Call sites

No changes. `agent=` is already threaded through all three call sites from the Codex PR (`dispatch.py:exec_command()`, `jobs.py:_reconcile_jobs()` ×4, `support_engineer.py`). `extract_tokens(text, agent="claude")` now routes to §3.2 automatically.

### 3.6 Fallback behavior (explicit failure modes)

| Scenario | Result |
|---|---|
| Claude CLI version doesn't support `--output-format stream-json` (flag rejected, nonzero exit before any output) | `log_file` contains Claude's stderr about the bad flag → `_extract_claude_structured()` finds no `result` line → returns `None` → regex chain runs against whatever text exists (no worse than today); `_render_claude_log_line()` fails the JSON-parse check on that stderr line and returns it as-is, so it's still visible in `synlynk logs` |
| `--output-format stream-json` accepted but the `result` event's `usage` shape changes in a future Claude Code release (field renamed/removed) | `KeyError`/`ValueError` caught → `None` → regex fallback (degrades to `total_split` or `none`, same as Phase 1's existing behavior for any unparseable output) |
| Job killed mid-run (stall-killer, SIGKILL) before the `result` event is emitted | No `result` line found → `None` → regex fallback. No behavior change from Phase 1. |
| Everything works | `basis="structured_output"` → `_resolve_cost_tier()` (unchanged) → `estimated_token_rate` or `actual` depending on billing mode, exactly as it does for Codex today |

No new failure mode can produce a dispatch error or a missing cost row — same invariant Phase 1 established and Codex's pilot preserved.

## 4. Testing

- Unit tests for `_extract_claude_structured()` using the two live fixture JSONL captures from this design's research (single-turn plain-text run, two-turn run with a Bash tool call) — asserts exact `in_tokens` (= `input_tokens` + `cache_creation_input_tokens`), `out_tokens`, `cache_read_tokens` (= `cache_read_input_tokens`), and `basis="structured_output"`.
- Edge cases: empty string → `None`; garbage/non-JSON lines mixed with a valid `result` line → still extracts correctly (proves line-by-line scanning); `usage` missing `cache_creation_input_tokens` or `cache_read_input_tokens` (older CLI versions may omit) → falls back to `0` for each, doesn't raise; malformed `usage` (non-numeric value) → returns `None`; multiple `result` events in one log (not observed live, but not proven impossible, same posture as Codex's spec) → last one wins.
- Unit test: `extract_tokens(text, agent="claude")` with valid stream-json returns `basis="structured_output"`; with plain-text (non-JSONL, e.g. a pre-flag-change job's log) falls through to the existing regex chain unchanged; `extract_tokens(text, agent="codex")` or `agent=None` never calls the Claude path regardless of input content — proves no cross-agent leakage, matching the equivalent Codex test.
- Unit tests for `_render_claude_log_line()` covering all 7 branches: `system`/`rate_limit_event`/`result`/`user` suppressed; `assistant` with a `text` block renders prose; `assistant` with a `tool_use` block renders `$ ToolName({...})`; a non-JSON line (simulating a crashed pre-flag job) prints as-is.
- Regression: full existing `extract_tokens()` test suite (including the Codex structured-output tests) must still pass unmodified.
- Run `pytest -q --ignore=worktrees` (project convention) with zero new failures.

## 5. Out of Scope (for this design)

- Gemini/Agy and Grok structured adapters — each is its own follow-on PR, own live investigation of actual CLI output, reusing §3.1's `if agent == "<name>":` pattern directly (per Codex spec's own §5 and this design's §1).
- `total_cost_usd` capture and any rate-table-bypass mechanism — deliberately deferred, see §3.2.
- Any change to `_resolve_cost_tier()`, `update_costs()`, or the `cost_entries` schema — none needed, mirrors Codex spec's §5.
- Correlating `tool_use`/`tool_result` pairs in the log renderer, or rendering full tool output content — scoped down to match Codex's single-field `aggregated_output` simplicity (§3.4).
- The Vizor estimated-flagging UI (separate PR per epic #210's own body) — unrelated to this adapter.
- Retroactively re-extracting tokens for historical Claude job logs written before this change lands — Phase 1's historical-backfill rule (never retroactively upgrade a row's confidence tier) applies unchanged.

## 6. Release Sequencing

v0.12.0 "Trust & Cost-Aware Routing" already unblocked and shippable as of the Codex pilot (PR #244/#245); this PR is a fast-follow within the same theme, not a release blocker. No sequencing decision needed beyond "lands whenever it's ready."

## 7. Self-Review Notes

- **Placeholder scan:** none — adapter code, renderer code, flag changes, and the fallback table are all fully specified with real code or precise behavior.
- **Internal consistency:** §3.2's two mapping decisions (cache-creation folding, cost-bypass deferral) are stated with their rejected alternatives and reasons, not left implicit. §3.3 explicitly reuses the Codex spec's §3.3 architectural finding rather than re-deriving it, since the same fire-and-forget dispatch model applies.
- **Scope check:** narrowed to one agent, consistent with the "pattern + one agent per PR" cadence Codex's pilot established; §5 makes exclusions explicit.
- **Ambiguity check:** "which `usage` object wins if multiple `result` events appear" resolved (last wins, same as Codex). "What happens to a `tool_result` (`user`-role) event" resolved explicitly (suppressed, not correlated) rather than left to reviewer judgment during implementation.
