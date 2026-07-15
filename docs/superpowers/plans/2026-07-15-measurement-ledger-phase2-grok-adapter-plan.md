# Measurement Ledger Phase 2 — Grok Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured-output token extraction adapter for the Grok CLI, so `extract_tokens()` uses Grok's own vendor-reported `usage` object instead of falling back to regex-scraping.

**Architecture:** A new `_extract_grok_structured(output_text)` function in `synlynk/costs.py` parses grok's single pretty-printed JSON response object (not a line-delimited stream — confirmed via live testing), returning a `_TokenCounts` on success or `None` on any parse/shape failure. `extract_tokens()` gains a new `if agent == "grok":` branch that tries this function first and falls through to the existing regex chain automatically. No other files change: `dispatch.py`'s `--output-format json` flag for grok and `_constants.py`'s corresponding `valid_flags` entry were already shipped in the Agy adapter's PR (#256) and need no modification.

**Tech Stack:** Python 3 stdlib (`json`), pytest.

---

### Task 1: `_extract_grok_structured()` unit tests + implementation

**Files:**
- Modify: `synlynk/costs.py` (insert new function after `_extract_agy_structured`, which ends at line 126, before `def extract_tokens` at line 129)
- Test: `tests/test_cost_ledger.py` (insert new tests after `test_extract_agy_structured_truncated_json_returns_none`, which ends at line 679, before `def test_extract_tokens_agent_codex_uses_structured_output` at line 682)

- [ ] **Step 1: Write the failing tests**

Add these 12 tests to `tests/test_cost_ledger.py`, inserted at line 681 (the blank line between `test_extract_agy_structured_truncated_json_returns_none` and `test_extract_tokens_agent_codex_uses_structured_output`):

```python
def test_extract_grok_structured_basic():
    from synlynk.costs import _extract_grok_structured

    output = (
        '{\n'
        '  "text": "Hi there.",\n'
        '  "stopReason": "EndTurn",\n'
        '  "sessionId": "019f6431-b20a-7060-bece-8ef68badf264",\n'
        '  "requestId": "4a07d1bf-9834-482b-88d5-af7072581354",\n'
        '  "thought": "The user wants a simple greeting.",\n'
        '  "usage": {\n'
        '    "input_tokens": 10118,\n'
        '    "cache_read_input_tokens": 11136,\n'
        '    "output_tokens": 29,\n'
        '    "reasoning_tokens": 22,\n'
        '    "total_tokens": 21283\n'
        '  },\n'
        '  "num_turns": 1,\n'
        '  "modelUsage": {"grok-4.5": {"inputTokens": 10118, "outputTokens": 29}}\n'
        '}\n'
    )
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 10118
    assert result.output_tokens == 29 + 22
    assert result.cache_read_tokens == 11136
    assert result.basis == "structured_output"


def test_extract_grok_structured_tool_use_sample():
    from synlynk.costs import _extract_grok_structured

    output = (
        '{\n'
        '  "text": "Here is what is in the directory.",\n'
        '  "stopReason": "EndTurn",\n'
        '  "sessionId": "019f6431-e8be-7e82-8cfa-0badf0b4bbf5",\n'
        '  "requestId": "81d3e406-f05f-46f6-9832-eeacd85a4c60",\n'
        '  "thought": "The user wants a file listing.",\n'
        '  "usage": {\n'
        '    "input_tokens": 11139,\n'
        '    "cache_read_input_tokens": 32256,\n'
        '    "output_tokens": 603,\n'
        '    "reasoning_tokens": 338,\n'
        '    "total_tokens": 43998\n'
        '  },\n'
        '  "num_turns": 2,\n'
        '  "modelUsage": {"grok-4.5": {"inputTokens": 11139, "outputTokens": 603, "modelCalls": 2}}\n'
        '}\n'
    )
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 11139
    assert result.output_tokens == 603 + 338
    assert result.cache_read_tokens == 32256
    assert result.basis == "structured_output"


def test_extract_grok_structured_cache_read_kept_separate_not_folded():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 100, "cache_read_input_tokens": 9000, "output_tokens": 20}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 100
    assert result.cache_read_tokens == 9000


def test_extract_grok_structured_empty_string_returns_none():
    from synlynk.costs import _extract_grok_structured

    assert _extract_grok_structured("") is None


def test_extract_grok_structured_single_line_json_also_parses():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 10, "output_tokens": 5}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_grok_structured_error_response_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = (
        '{"type":"error","message":"Couldn\'t set model \'bad-model\': '
        'Invalid params: \\"unknown model id\\"."}\n'
    )
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_missing_usage_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = '{"text": "hi", "stopReason": "EndTurn"}\n'
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_missing_reasoning_tokens_defaults_zero():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 10, "output_tokens": 5}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.output_tokens == 5


def test_extract_grok_structured_missing_cache_read_defaults_zero():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 10, "output_tokens": 5}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.cache_read_tokens == 0


def test_extract_grok_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": "not-a-number", "output_tokens": 5}}\n'
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_malformed_json_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = 'not json at all\n'
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_truncated_json_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = '{\n  "usage": {\n    "input_tokens": 10,\n    "outp'
    assert _extract_grok_structured(output) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k extract_grok_structured -v`
Expected: FAIL with `ImportError: cannot import name '_extract_grok_structured'` (or `AttributeError`) for every test.

- [ ] **Step 3: Write the implementation**

Insert this function into `synlynk/costs.py` immediately after `_extract_agy_structured` (which ends at line 126 with `return _TokenCounts(in_tokens, out_tokens, 0, "structured_output")`), before the blank lines preceding `def extract_tokens` at line 129:

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k extract_grok_structured -v`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): add _extract_grok_structured() token adapter"
```

---

### Task 2: Wire `grok` into `extract_tokens()` dispatch chain

**Files:**
- Modify: `synlynk/costs.py` (the `extract_tokens()` function, specifically the region right after the existing `if agent == "agy":` block at lines 143-146, before the blank line and `def _parse_count` helper at line 148)
- Test: `tests/test_cost_ledger.py` (insert new tests after `test_extract_tokens_non_agy_agent_never_uses_agy_structured_path`, before `def test_extract_tokens_default_agent_none_unchanged_behavior`)

- [ ] **Step 1: Write the failing tests**

Add these 3 tests to `tests/test_cost_ledger.py`, inserted immediately before `def test_extract_tokens_default_agent_none_unchanged_behavior`:

```python
def test_extract_tokens_agent_grok_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
    result = extract_tokens(output, agent="grok")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_grok_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="grok")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_grok_agent_never_uses_grok_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis != "structured_output"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "extract_tokens_agent_grok or non_grok_agent" -v`
Expected: FAIL — `test_extract_tokens_agent_grok_uses_structured_output` fails because `extract_tokens()` doesn't yet route `agent="grok"` to the structured extractor (its `basis` will be `"regex_pair"` or fallback, not `"structured_output"`). The other two tests may pass already since they describe current/fallback behavior — that's expected; only the first assertion is the true failing case.

- [ ] **Step 3: Write the implementation**

In `synlynk/costs.py`, modify the `extract_tokens()` function. Locate this existing block (currently at lines 143-146):

```python
    if agent == "agy":
        structured = _extract_agy_structured(output_text)
        if structured is not None:
            return structured
```

Add a new sibling block immediately after it (still before the blank line and `def _parse_count` helper):

```python
    if agent == "agy":
        structured = _extract_agy_structured(output_text)
        if structured is not None:
            return structured
    if agent == "grok":
        structured = _extract_grok_structured(output_text)
        if structured is not None:
            return structured
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "extract_tokens_agent_grok or non_grok_agent" -v`
Expected: `3 passed`

Then run the broader regression to confirm no other agent's routing broke:

Run: `pytest tests/test_cost_ledger.py -k extract_tokens -v`
Expected: all pass (20 tests: the pre-existing 17 plus the 3 new grok ones)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): wire grok into extract_tokens() dispatch chain"
```

---

### Task 3: Full regression and final review

**Files:** None modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q --ignore=worktrees`
Expected: exactly 15 more passing tests than the pre-Grok-adapter baseline (12 from Task 1 + 3 from Task 2), all passing, 0 failures.

- [ ] **Step 2: Run the cross-agent regression slice**

Run: `pytest tests/test_cost_ledger.py -k "codex or claude or agy or grok" -v`
Expected: all pass — confirms no collateral impact on any previously shipped adapter.

- [ ] **Step 3: Confirm no renderer was added**

Run: `grep -n 'agent") == "grok"' synlynk/__init__.py`
Expected: empty output (no `cmd_logs()` renderer branch for grok, per spec §3.5 — Grok's single JSON object needs no noise suppression).

- [ ] **Step 4: Confirm dispatch.py and _constants.py are untouched**

Run: `git diff origin/main --stat -- synlynk/dispatch.py synlynk/_constants.py`
Expected: empty output — both files already shipped grok's `--output-format json` flag and `valid_flags` entry in PR #256; this plan makes no changes to either.

- [ ] **Step 5: Confirm overall diff scope**

Run: `git diff origin/main --stat`
Expected: exactly the design spec, this plan, `synlynk/costs.py`, and `tests/test_cost_ledger.py` changed — no other files.

No commit needed if all steps pass cleanly — this task is verification-only.

---

## Self-Review Notes

**Spec coverage:**
- §3.1 (live-verified shapes) → directly reflected in Task 1's test fixtures (pretty-printed multi-line JSON, the confirmed additive cache-read arithmetic, the live-verified error shape).
- §3.2 (`_extract_grok_structured()`) → Task 1, code given verbatim, matches the spec's function exactly.
- §3.3 (wire into `extract_tokens()`) → Task 2, code given verbatim.
- §3.4 (dispatch flag — no change) → Task 3 Step 4 explicitly verifies this rather than silently assuming it.
- §3.5 (no renderer) → Task 3 Step 3 explicitly verifies this.
- §3.6 (failure-mode handling) → covered by Task 1's error/malformed/truncated/missing-usage tests.
- §4 (testing) → Task 1 has 12 tests (one more than Agy's 11, adding the cache-read-separation-specific test per the genuinely new dimension in this adapter), Task 2 has 3 tests, matching the spec's stated shape.
- §5 (out of scope) → no tasks touch schema, renderer, dispatch.py, _constants.py, Vizor, or retroactive re-extraction — consistent.

**Placeholder scan:** No TBD/TODO markers; every step has complete, runnable code or an exact command with expected output.

**Type consistency:** `_extract_grok_structured(output_text: str) -> Optional[_TokenCounts]` matches the signature pattern of `_extract_codex_structured`/`_extract_claude_structured`/`_extract_agy_structured` exactly. `_TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")` constructor call matches the class defined at the top of `costs.py` (`__init__(self, input_tokens, output_tokens, cache_read_tokens, basis="none")`) — argument order and names consistent across both tasks.
