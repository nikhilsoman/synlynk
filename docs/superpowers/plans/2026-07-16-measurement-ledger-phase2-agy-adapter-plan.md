# Measurement Ledger Hardening Phase 2 — Agy Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an agy-specific structured-output token adapter to `extract_tokens()`, following the exact pattern the shipped Codex (`_extract_codex_structured`) and Claude (`_extract_claude_structured`) adapters established.

**Architecture:** `extract_tokens(text, agent=)` gains an `agent == "agy"` branch that tries `_extract_agy_structured()` (parses `agy -p --output-format json`'s single JSON object response — not an event stream like Codex/Claude — reads its `usage` object) before falling back to the existing regex chain on any failure. `dispatch_agent()` gains the flag to actually produce that JSON. No log renderer is added (§3.4 of the design spec): unlike Codex/Claude, agy's output has no multi-event noise to suppress, so `cmd_logs()`'s existing raw-passthrough fallback already handles it.

**Tech Stack:** Python 3 stdlib only (`json`) — no new dependencies. Existing `pytest` suite in `tests/test_cost_ledger.py`.

**Spec:** `docs/superpowers/specs/2026-07-16-measurement-ledger-phase2-agy-adapter-design.md` — read this first for the full rationale on each design choice (§3.2's `thinking_tokens` folding and `status != "SUCCESS"` handling, §3.3's TC-2 preflight constraint, §3.4's no-renderer decision). This plan implements it verbatim; do not re-derive design decisions, just execute.

---

### Task 1: `_extract_agy_structured()` — the core adapter function

**Files:**
- Modify: `synlynk/costs.py` (add function after `_extract_claude_structured`, which ends at line 94, before `def extract_tokens` at line 97)
- Test: `tests/test_cost_ledger.py` (add tests after the last Claude-adapter parser test, `test_extract_claude_structured_last_result_wins`, which ends around line 542, before `def test_extract_tokens_agent_codex_uses_structured_output` at line 545)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cost_ledger.py`:

```python
def test_extract_agy_structured_basic():
    from synlynk.costs import _extract_agy_structured

    output = (
        '{"conversation_id":"c1","status":"SUCCESS","response":"hello",'
        '"duration_seconds":12.34,"num_turns":1,'
        '"usage":{"input_tokens":80648,"output_tokens":2390,'
        '"thinking_tokens":1922,"total_tokens":83038}}\n'
    )
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 80648
    assert result.output_tokens == 2390 + 1922
    assert result.cache_read_tokens == 0
    assert result.basis == "structured_output"


def test_extract_agy_structured_tool_use_sample():
    from synlynk.costs import _extract_agy_structured

    output = (
        '{"conversation_id":"c2","status":"SUCCESS","response":"there are 5 files",'
        '"duration_seconds":18.02,"num_turns":1,'
        '"usage":{"input_tokens":84375,"output_tokens":3294,'
        '"thinking_tokens":2632,"total_tokens":87669}}\n'
    )
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 84375
    assert result.output_tokens == 3294 + 2632
    assert result.cache_read_tokens == 0
    assert result.basis == "structured_output"


def test_extract_agy_structured_empty_string_returns_none():
    from synlynk.costs import _extract_agy_structured

    assert _extract_agy_structured("") is None


def test_extract_agy_structured_trailing_blank_lines_still_parses():
    from synlynk.costs import _extract_agy_structured

    output = (
        '{"status":"SUCCESS","usage":{"input_tokens":10,"output_tokens":5}}\n'
        '\n'
        '   \n'
    )
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_agy_structured_status_not_success_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"FAILED","usage":{"input_tokens":10,"output_tokens":5}}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_missing_status_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"usage":{"input_tokens":10,"output_tokens":5}}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_missing_usage_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","response":"hi"}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_missing_thinking_tokens_defaults_zero():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","usage":{"input_tokens":10,"output_tokens":5}}\n'
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.output_tokens == 5


def test_extract_agy_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","usage":{"input_tokens":"not-a-number","output_tokens":5}}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_malformed_json_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = 'not json at all\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_truncated_json_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","usage":{"input_tokens":10,"outp'
    assert _extract_agy_structured(output) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k extract_agy_structured -v`
Expected: FAIL — `ImportError: cannot import name '_extract_agy_structured'` (function doesn't exist yet) for every test in this batch.

- [ ] **Step 3: Implement `_extract_agy_structured()`**

In `synlynk/costs.py`, add this function immediately after `_extract_claude_structured` (which ends at line 94) and before `def extract_tokens` (line 97):

```python
def _extract_agy_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses agy -p --output-format json's single JSON object response.

    Unlike Codex/Claude, agy emits exactly one JSON object per invocation,
    not a newline-delimited event stream, so only the last non-empty line
    needs parsing. thinking_tokens is folded into output_tokens (billable
    output, mirrors Codex's reasoning_output_tokens treatment). No
    cache-read concept exists in agy's usage shape, so cache_read_tokens
    is always 0. A non-"SUCCESS" status is treated as extraction failure
    (falls back to the regex chain) since no failure-mode schema has been
    observed live.
    """
    lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        event = json.loads(lines[-1])
    except (ValueError, TypeError):
        return None
    if not isinstance(event, dict) or event.get("status") != "SUCCESS":
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        in_tokens = int(usage["input_tokens"])
        out_tokens = int(usage["output_tokens"]) + int(usage.get("thinking_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, 0, "structured_output")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k extract_agy_structured -v`
Expected: PASS — 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): add _extract_agy_structured() token adapter"
```

---

### Task 2: Wire `_extract_agy_structured()` into `extract_tokens()`

**Files:**
- Modify: `synlynk/costs.py:107-110` (the `if agent == "claude":` block inside `extract_tokens()`)
- Test: `tests/test_cost_ledger.py` (add tests after `test_extract_tokens_non_claude_agent_never_uses_claude_structured_path`, which ends around line 600, before `def test_extract_tokens_default_agent_none_unchanged_behavior` at line 603)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cost_ledger.py`:

```python
def test_extract_tokens_agent_agy_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"status":"SUCCESS","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="agy")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_agy_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="agy")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_agy_agent_never_uses_agy_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"status":"SUCCESS","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis != "structured_output"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "extract_tokens_agent_agy or non_agy_agent" -v`
Expected: FAIL — `test_extract_tokens_agent_agy_uses_structured_output` fails because `extract_tokens()` has no `agy` branch yet (falls through to regex, `basis` won't be `"structured_output"`). The other two pass already (no regression, but run them anyway to confirm baseline).

- [ ] **Step 3: Add the `agy` branch to `extract_tokens()`**

In `synlynk/costs.py`, modify the `extract_tokens()` function (currently lines 97-110):

```python
def extract_tokens(output_text: str, agent: str = None) -> tuple:
    """Regex-scrapes token counts from AI CLI stdout, or delegates to a
    per-agent structured-output adapter when one exists.

    Returns a pair-compatible object with .cache_read_tokens for cache-aware output.
    """
    if agent == "codex":
        structured = _extract_codex_structured(output_text)
        if structured is not None:
            return structured
    if agent == "claude":
        structured = _extract_claude_structured(output_text)
        if structured is not None:
            return structured
    if agent == "agy":
        structured = _extract_agy_structured(output_text)
        if structured is not None:
            return structured
```

(Leave everything below this point — the `_parse_count` helper and the regex `patterns` list — unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "extract_tokens_agent_agy or non_agy_agent" -v`
Expected: PASS — all 3 tests pass.

- [ ] **Step 5: Run the full cross-agent regression block**

Run: `pytest tests/test_cost_ledger.py -k extract_tokens -v`
Expected: PASS — every existing `extract_tokens` test (codex, claude, default/none, regex-basis tests) still passes unmodified.

- [ ] **Step 6: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): wire agy into extract_tokens() dispatch chain"
```

---

### Task 3: Dispatch flags — enable `--output-format json` for agy

**Files:**
- Modify: `synlynk/dispatch.py:754-757` (the sibling `if agent == "grok":` / `if agent == "claude":` blocks inside `dispatch_agent()`)
- Test: `tests/test_cost_ledger.py` (add test after `test_dispatch_agent_claude_flags_include_stream_json_verbose`, which ends around line 307, before `def test_extract_tokens_basis_regex_pair` at line 310)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cost_ledger.py`:

```python
def test_dispatch_agent_agy_flags_include_output_format_json(project_dir, monkeypatch):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    captured_flags = {}

    def fake_popen(cmd, **kwargs):
        captured_flags["shell_cmd"] = cmd[2]

        class FakeProc:
            pid = 12345

        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(synlynk, "_create_job_worktree", lambda job_id, agent: str(project_dir / "worktree"), raising=False)
    monkeypatch.setattr(synlynk, "_job_worktree_details", lambda job_id, agent: ("", "branch"), raising=False)
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [], raising=False)
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: None, raising=False)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda agent: {}, raising=False)
    monkeypatch.setattr(synlynk, "generate_context", lambda **kwargs: "", raising=False)
    monkeypatch.setattr(synlynk, "_format_prompt_for_agent", lambda *a, **k: "prompt", raising=False)
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda agent, cli: "unknown", raising=False)

    dispatch_mod.dispatch_agent("agy", "do a thing", skip_preflight=True, job_id="job-test789")

    assert "--output-format" in captured_flags["shell_cmd"]
    assert "json" in captured_flags["shell_cmd"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_dispatch_agent_agy_flags_include_output_format_json -v`
Expected: FAIL — `assert "--output-format" in captured_flags["shell_cmd"]` fails because `dispatch_agent()` has no `agy` flag block yet.

- [ ] **Step 3: Add the `agy` flag block**

In `synlynk/dispatch.py`, modify the sibling `if` chain (currently lines 754-757):

```python
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    if agent == "claude":
        flags = flags + ["--output-format", "stream-json", "--verbose"]
    if agent == "agy":
        flags = flags + ["--output-format", "json"]
    if agent == "codex":
```

(This adds a new `if agent == "agy":` block as its own independent sibling — deliberately not merged with the `grok` block despite the identical flag/value, per the design spec's §3.3. Do not modify `synlynk/_constants.py`'s `agy` baseline — its `dispatch_flags.valid_flags` must stay exactly `["--print", "--model", "--add-dir", "--sandbox"]`, unchanged, since `--output-format` is confirmed absent from `agy --help`'s text and adding it there would fail the TC-2 preflight check on every `agy` dispatch.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k test_dispatch_agent_agy_flags_include_output_format_json -v`
Expected: PASS.

- [ ] **Step 5: Run the full dispatch-flags regression block**

Run: `pytest tests/test_cost_ledger.py -k dispatch_agent -v`
Expected: PASS — the existing `codex`, `claude`, and any `grok`-flags tests all still pass unmodified.

- [ ] **Step 6: Confirm `synlynk/_constants.py` was not touched**

Run: `git diff --stat synlynk/_constants.py`
Expected: empty output (no changes to this file).

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_cost_ledger.py
git commit -m "feat(dispatch): enable --output-format json for agy"
```

---

### Task 4: Full regression run and final review

**Files:** None modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q --ignore=worktrees`
Expected: All tests pass (no new failures beyond the pre-existing baseline skip count). Compare the pass count to the pre-change baseline — it should be exactly 11 (Task 1) + 3 (Task 2) + 1 (Task 3) = 15 higher.

- [ ] **Step 2: Run the codex/claude/agy-scoped regression together**

Run: `pytest tests/test_cost_ledger.py -k "codex or claude or agy" -v`
Expected: PASS — proves no cross-agent interference between all three shipped structured adapters.

- [ ] **Step 3: Manually verify no `cmd_logs()` renderer branch was added for agy**

Run: `grep -n 'agent") == "agy"' synlynk/__init__.py`
Expected: no output (empty) — confirms `synlynk/__init__.py` was not touched, per the design spec's §3.4 decision not to add a renderer.

- [ ] **Step 4: Review the full diff against the design spec**

Run: `git diff origin/main --stat`
Expected: exactly three files changed — `synlynk/costs.py`, `synlynk/dispatch.py`, `tests/test_cost_ledger.py`. No changes to `synlynk/_constants.py` or `synlynk/__init__.py`.

- [ ] **Step 5: Commit if any cleanup was needed, otherwise this task requires no commit**

(This task is verification-only; skip committing if steps 1-4 all passed without needing fixes.)

---

## Self-Review Notes (writing-plans skill checklist)

**1. Spec coverage:**
- §3.1 (dispatch chain) → Task 2.
- §3.2 (`_extract_agy_structured()`, thinking_tokens folding, status-failure handling, last-line parsing) → Task 1.
- §3.3 (dispatch flags, TC-2 constraint, independent sibling block) → Task 3.
- §3.4 (no renderer) → verified explicitly in Task 4 Step 3 (absence check), not a task that adds code.
- §3.5 (call sites) → no task needed; spec confirms no changes required, consistent with Task 2's minimal diff.
- §3.6 (fallback table) → covered by Task 1's `status != "SUCCESS"`, malformed-JSON, and missing-usage tests.
- §4 (testing) → all listed test categories present across Tasks 1-3; renderer tests correctly omitted per §3.4/§5.
- §5 (out of scope) → no task touches `_constants.py`, `__init__.py`, `_resolve_cost_tier()`, or `update_costs()`.

**2. Placeholder scan:** none found — every step has complete code, exact file paths, and exact commands with expected output.

**3. Type consistency:** `_TokenCounts(in_tokens, out_tokens, cache_read_tokens, basis)` constructor call in Task 1 matches the existing class signature used by `_extract_codex_structured`/`_extract_claude_structured` (verified against `synlynk/costs.py:19-34`, unchanged by this plan). `_extract_agy_structured` is referenced with the same name in Task 1 (definition) and Task 2 (call site) — no drift.
