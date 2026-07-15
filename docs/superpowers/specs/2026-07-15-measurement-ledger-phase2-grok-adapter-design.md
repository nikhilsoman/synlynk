# Measurement Ledger Hardening Phase 2 — Grok Structured-Output Adapter

## 1. Problem

`extract_tokens()` (`synlynk/costs.py`) falls back to regex-scraping and an 80/20 input/output heuristic split whenever an agent's raw CLI stdout doesn't match a known pattern. Codex (#244), Claude (#252), and Agy (#256) have already been upgraded to a structured-output-first extraction path that tries a real, vendor-reported usage object before ever touching the regex chain. Grok — the fourth and final agent named in epic #210 — still has no structured adapter, despite `dispatch.py` already invoking it with `--output-format json` (that flag, and its `_constants.py` `valid_flags` entry, were added incidentally during the Agy adapter's Task 3 dispatch and confirmed still present and unused by any parser).

## 2. What Already Exists

- `_TokenCounts(input_tokens, output_tokens, cache_read_tokens, basis)` — the common return type all three adapters produce, with `basis="structured_output"` on success.
- `extract_tokens(output_text, agent=None)` — tries `_extract_<agent>_structured()` first (returns `None` on any failure, never raises), falls through to the existing regex chain automatically.
- `dispatch.py:754` — `if agent == "grok": flags = flags + ["--output-format", "json"]`, already shipped and live-verified.
- `synlynk/_constants.py`'s `grok` entry — `"--output-format"` is already listed in `dispatch_flags.valid_flags` (line 95), meaning TC-2 preflight already accepts this flag for Grok. No `_constants.py` change is needed by this PR.

## 3. Design

### 3.1 Live-verified output shape

Running `grok -p "<prompt>" --output-format json` directly (three separate invocations, including one multi-turn tool-use case and one deliberately-broken `--model` case) confirmed:

**Success shape** — exactly one **pretty-printed, multi-line** JSON object per invocation (not NDJSON like Codex/Claude, not single-line like Agy):

```json
{
  "text": "...",
  "stopReason": "EndTurn",
  "sessionId": "...",
  "requestId": "...",
  "thought": "...",
  "usage": {
    "input_tokens": 10119,
    "cache_read_input_tokens": 11136,
    "output_tokens": 35,
    "reasoning_tokens": 26,
    "total_tokens": 21290
  },
  "num_turns": 1,
  "modelUsage": { "grok-4.5": { "...": "..." } }
}
```

Verified arithmetically across all three live runs: `total_tokens == input_tokens + cache_read_input_tokens + output_tokens` (reasoning_tokens excluded from the total in every case). This confirms `cache_read_input_tokens` is an **additive** pool, not a subset of `input_tokens` — unlike Codex's `cached_input_tokens`, which the existing Codex adapter treats as a subset (folded out of `in_tokens`, tracked only in `cache_read_tokens`). Grok's shape is closer to Claude's `cache_read_input_tokens`, which is also additive and kept as its own tier.

**Failure shape** (triggered live with an invalid `--model`):

```json
{"type":"error","message":"Couldn't set model '...': Invalid params: \"unknown model id\". ..."}
```

No `usage` key, no `stopReason`, exit code 1. There is no explicit status field on success either (unlike Agy's `status: "SUCCESS"`) — the presence of a well-formed `usage` dict is itself the success signal, since the only observed failure shape lacks it entirely.

A multi-turn tool-use invocation (prompting Grok to run `ls` and count files) produced identical structure — a single aggregate JSON object with `num_turns: 2` and no interleaved tool-call noise in stdout. This confirms Grok, like Agy, has nothing for `synlynk logs` to suppress.

### 3.2 `_extract_grok_structured()` (`synlynk/costs.py`)

```python
def _extract_grok_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses grok -p --output-format json's single, pretty-printed JSON object.

    Unlike Codex/Claude (newline-delimited event streams) or Agy (single-line
    JSON), grok emits one multi-line pretty-printed JSON object per invocation,
    so the entire captured text is parsed as one document rather than scanned
    line by line. reasoning_tokens is folded into output_tokens (mirrors
    Codex's reasoning_output_tokens and Agy's thinking_tokens treatment).
    cache_read_input_tokens is kept as its own tier rather than folded into
    input_tokens: live testing confirmed total_tokens == input_tokens +
    cache_read_input_tokens + output_tokens across three separate runs, so
    it is a genuine additive pool (like Claude's cache_read_input_tokens),
    not a subset of input_tokens (unlike Codex's cached_input_tokens). A
    failure response (`{"type": "error", ...}`) has no "usage" key, so a
    missing or malformed usage object is the extraction-failure signal —
    there is no explicit status field to check on success.
    """
    try:
        event = json.loads(output_text.strip())
    except (ValueError, TypeError):
        return None
    if not isinstance(event, dict):
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        in_tokens = int(usage["input_tokens"])
        out_tokens = int(usage["output_tokens"]) + int(usage.get("reasoning_tokens", 0))
        cache_read_tokens = int(usage.get("cache_read_input_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")
```

### 3.3 Wire into `extract_tokens()`

New sibling branch, positioned after the existing `if agent == "agy":` block (matching the established insertion order: codex, claude, agy, grok):

```python
if agent == "grok":
    structured = _extract_grok_structured(output_text)
    if structured is not None:
        return structured
```

### 3.4 Dispatch flag — no change

`dispatch.py:754`'s `if agent == "grok": flags = flags + ["--output-format", "json"]` and `_constants.py`'s `"--output-format"` entry in Grok's `valid_flags` already exist and are already correct. This PR makes no changes to either file — it only adds the parser that finally makes the already-live flag useful.

### 3.5 No `cmd_logs()` renderer

Same reasoning as the Agy adapter: a single pretty-printed JSON object has no multi-event noise (no interleaved `tool_use`/`system`/`rate_limit_event` chatter) for `synlynk logs` to suppress, and it's already human-readable as raw passthrough. No `_render_grok_log_line()` is added.

### 3.6 Failure-mode handling

Any of the following causes `_extract_grok_structured()` to return `None`, falling through to the existing regex chain automatically — no invented failure schema, matching every prior adapter's contract:

- Malformed/truncated JSON (parse failure)
- Parsed value is not a dict
- `usage` key missing or not a dict (covers the live-verified `{"type":"error",...}` shape)
- Any of `input_tokens`/`output_tokens` missing or non-numeric

## 4. Testing

Unit tests for `_extract_grok_structured()` mirror the Agy adapter's 11-test shape (basic success, tool-use sample, empty string, malformed JSON, truncated JSON, missing usage, malformed usage, missing reasoning_tokens defaults to zero, missing cache_read_input_tokens defaults to zero, the live-verified error shape, and a two-turn/tool-use sample matching the live `num_turns: 2` case). Cross-agent `extract_tokens()` tests mirror the other three adapters' 3-test shape (uses structured output for `agent="grok"`, falls back to regex on plain text, non-grok agents never use Grok's structured path).

No dispatch-flags test is needed — the flag was already tested and shipped in the Agy adapter's Task 3 (`test_dispatch_agent_agy_flags_include_output_format_json`'s sibling assertion doesn't exist for grok specifically, but the flag itself was live-verified working in that same PR's dispatched job, which ran as agent `grok`).

## 5. Out of Scope

- `_resolve_cost_tier()` / `update_costs()` / schema changes — none needed, `_TokenCounts`'s existing `cache_read_tokens` tier already supports Grok's shape.
- `cmd_logs()` renderer for grok — deliberately not added (§3.5).
- `dispatch.py` / `_constants.py` changes — both already correct, no changes needed (§3.4).
- `sessionId`/`requestId`/`stopReason`/`num_turns`/`thought`/`modelUsage` capture — not needed for cost extraction.
- Vizor UI, estimated-flagging UI — separate PR per epic #210's own scope note.
- Retroactive re-extraction of already-logged Grok cost rows — Phase 1's rule applies unchanged: new extraction logic only affects rows written after this ships.

## 6. Release Sequencing

Fourth and final per-agent adapter of epic #210's structured-output layer. Independently shippable, no dependency on the estimated-flagging UI PR. Closes epic #210's adapter-PR scope entirely once merged; the estimated-flagging UI (costs.md/Vizor) remains as epic #210's one non-adapter deliverable, not addressed here.

## 7. Self-Review Notes

- Placeholder scan: none found — every code block above is complete and runnable, no TBD/TODO markers.
- Internal consistency: §3.2's docstring claims match §3.1's live-verified findings exactly (additive cache-read pool, reasoning_tokens fold, no status field). §3.6's failure list matches §3.2's actual `return None` branches one-to-one.
- Scope check: single adapter, three code changes reduced to one (costs.py only, since dispatch.py/_constants.py already ship the flag) — appropriately small for one implementation plan.
- Ambiguity check: the "additive vs subset" cache-read question was the one genuine judgment call in this spec and was resolved by live arithmetic verification (three separate runs, same formula each time) rather than assumption, then confirmed with the user against Claude's established precedent for the same shape.
