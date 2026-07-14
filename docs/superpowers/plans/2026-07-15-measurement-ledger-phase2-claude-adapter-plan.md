# Measurement Ledger Hardening Phase 2 — Claude Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Claude-specific structured-output token adapter to `extract_tokens()`, following the exact pattern the shipped Codex adapter established, plus a readable-log renderer for `synlynk logs` on Claude jobs.

**Architecture:** `extract_tokens(text, agent=)` gains an `agent == "claude"` branch that tries `_extract_claude_structured()` (parses `claude -p --output-format stream-json --verbose`'s newline-delimited JSON, reads the single `type: "result"` event's cumulative `usage`) before falling back to the existing regex chain on any failure. `dispatch_agent()` gains the flags to actually produce that JSON. `cmd_logs()` gains a Claude-specific line renderer, mirroring the existing Codex one, so `synlynk logs --job <id>` still shows readable prose instead of raw JSONL.

**Tech Stack:** Python 3 stdlib only (`json`, `re`) — no new dependencies. Existing `pytest` suite in `tests/test_cost_ledger.py`.

**Spec:** `docs/superpowers/specs/2026-07-15-measurement-ledger-phase2-claude-adapter-design.md` — read this first for the full rationale on each design choice (§3.2's cache-token mapping, §3.4's log-renderer scoping). This plan implements it verbatim; do not re-derive design decisions, just execute.

---

### Task 1: `_extract_claude_structured()` — the core adapter function

**Files:**
- Modify: `synlynk/costs.py` (add function after `_extract_codex_structured`, which ends at line 62, before `def extract_tokens` at line 65)
- Test: `tests/test_cost_ledger.py` (add tests after the last Codex-adapter test, `test_extract_codex_structured_last_turn_completed_wins`, which ends around line 409, before `def test_extract_tokens_agent_codex_uses_structured_output`)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cost_ledger.py`:

```python
def test_extract_claude_structured_single_turn():
    from synlynk.costs import _extract_claude_structured

    output = (
        '{"type":"system","subtype":"init","cwd":"/tmp"}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"hello"}]}}\n'
        '{"type":"result","subtype":"success","is_error":false,"num_turns":1,"result":"hello",'
        '"total_cost_usd":0.1175592,"usage":{"input_tokens":2,"cache_creation_input_tokens":18810,'
        '"cache_read_input_tokens":15444,"output_tokens":4}}\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 2 + 18810
    assert result.output_tokens == 4
    assert result.cache_read_tokens == 15444
    assert result.basis == "structured_output"


def test_extract_claude_structured_multi_turn_tool_call_cumulative():
    from synlynk.costs import _extract_claude_structured

    output = (
        '{"type":"system","subtype":"init","cwd":"/tmp"}\n'
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls"}}]}}\n'
        '{"type":"user","message":{"role":"user","content":['
        '{"type":"tool_result","tool_use_id":"toolu_1","content":"a.txt\\nb.txt"}]}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"done"}]}}\n'
        '{"type":"result","subtype":"success","is_error":false,"num_turns":2,"result":"done",'
        '"total_cost_usd":0.10485,"usage":{"input_tokens":4,"cache_creation_input_tokens":14177,'
        '"cache_read_input_tokens":55170,"output_tokens":215}}\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 4 + 14177
    assert result.output_tokens == 215
    assert result.cache_read_tokens == 55170
    assert result.basis == "structured_output"


def test_extract_claude_structured_empty_string_returns_none():
    from synlynk.costs import _extract_claude_structured

    assert _extract_claude_structured("") is None


def test_extract_claude_structured_no_result_event_returns_none():
    from synlynk.costs import _extract_claude_structured

    output = '{"type":"system","subtype":"init","cwd":"/tmp"}\n{"type":"assistant","message":{}}\n'
    assert _extract_claude_structured(output) is None


def test_extract_claude_structured_garbage_lines_mixed_with_valid_event():
    from synlynk.costs import _extract_claude_structured

    output = (
        'not json at all\n'
        '\n'
        '   \n'
        '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
        'trailing garbage after the stream\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.cache_read_tokens == 0


def test_extract_claude_structured_missing_cache_fields_default_zero():
    from synlynk.costs import _extract_claude_structured

    output = '{"type":"result","usage":{"input_tokens":10,"output_tokens":5}}\n'
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.cache_read_tokens == 0


def test_extract_claude_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_claude_structured

    output = '{"type":"result","usage":{"input_tokens":"not-a-number","output_tokens":5}}\n'
    assert _extract_claude_structured(output) is None


def test_extract_claude_structured_last_result_wins():
    from synlynk.costs import _extract_claude_structured

    output = (
        '{"type":"result","usage":{"input_tokens":10,"output_tokens":5}}\n'
        '{"type":"result","usage":{"input_tokens":999,"output_tokens":888}}\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 999
    assert result.output_tokens == 888
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k extract_claude_structured -v`
Expected: FAIL — `ImportError: cannot import name '_extract_claude_structured'` (function doesn't exist yet) for every test in this batch.

- [ ] **Step 3: Implement `_extract_claude_structured()`**

In `synlynk/costs.py`, add this function immediately after `_extract_codex_structured` (which ends at line 62) and before `def extract_tokens` (line 65):

```python
def _extract_claude_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses claude -p --output-format stream-json --verbose's event stream.

    Returns the cumulative result-event usage object, or None on any failure.
    cache_creation_input_tokens is folded into input_tokens (both are
    non-cache-read, billable token pools in the CLI's own accounting; the
    rate table has no separate cache-write tier).
    """
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
                usage = candidate
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k extract_claude_structured -v`
Expected: PASS — all 8 tests green.

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): add _extract_claude_structured() adapter

Parses claude -p --output-format stream-json's result event for
cumulative token usage, following the pattern established by the
Codex structured-output adapter. Not yet wired into extract_tokens()."
```

---

### Task 2: Wire `_extract_claude_structured()` into `extract_tokens()`

**Files:**
- Modify: `synlynk/costs.py:65-73` (the top of `extract_tokens`, right after the existing `if agent == "codex":` block)
- Test: `tests/test_cost_ledger.py` (add after `test_extract_tokens_non_codex_agent_never_uses_structured_path`, the last test in the file's codex-adapter block)

- [ ] **Step 1: Write the failing tests**

```python
def test_extract_tokens_agent_claude_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_claude_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="claude")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_claude_agent_never_uses_claude_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="codex")
    assert result.basis != "structured_output"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "agent_claude_uses_structured or agent_claude_falls_back or non_claude_agent_never" -v`
Expected: FAIL — `test_extract_tokens_agent_claude_uses_structured_output` fails because `extract_tokens` doesn't yet call `_extract_claude_structured` (falls through to regex, `basis` comes back `"regex_pair"` or `"none"` instead of `"structured_output"`). The other two tests pass already (existing regex/fallback behavior is unaffected) — that's expected; only the first is the new-behavior assertion.

- [ ] **Step 3: Wire the dispatch**

In `synlynk/costs.py`, `extract_tokens()` currently starts:

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

    def _parse_count(value: str) -> int:
```

Change the `if agent == "codex":` block to add a sibling `if agent == "claude":` block right after it:

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

    def _parse_count(value: str) -> int:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "extract_tokens" -v`
Expected: PASS — every `extract_tokens`-prefixed test passes, including the pre-existing `test_extract_tokens_non_codex_agent_never_uses_structured_path` (still passes: that test's input has `"type":"turn.completed"`, not `"type":"result"`, so `_extract_claude_structured` correctly finds nothing and falls through to the regex chain, same as before this change).

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): wire claude agent into extract_tokens() dispatch

extract_tokens(text, agent=\"claude\") now tries the structured adapter
first, falling back to the existing regex chain on any failure —
identical dispatch shape to the codex branch added in PR #244."
```

---

### Task 3: Dispatch flags — enable `--output-format stream-json --verbose` for Claude

**Files:**
- Modify: `synlynk/dispatch.py:754-756` (the `if agent == "grok":` / `if agent == "codex":` flag-append block inside `dispatch_agent()`)
- Test: `tests/test_cost_ledger.py` (add after `test_dispatch_agent_codex_flags_include_json`, around line 274)

- [ ] **Step 1: Write the failing test**

```python
def test_dispatch_agent_claude_flags_include_stream_json_verbose(project_dir, monkeypatch):
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

    dispatch_mod.dispatch_agent("claude", "do a thing", skip_preflight=True, job_id="job-test456")

    assert "--output-format" in captured_flags["shell_cmd"]
    assert "stream-json" in captured_flags["shell_cmd"]
    assert "--verbose" in captured_flags["shell_cmd"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_dispatch_agent_claude_flags_include_stream_json_verbose -v`
Expected: FAIL — `assert "--output-format" in captured_flags["shell_cmd"]` fails, flag not present yet.

- [ ] **Step 3: Add the flag block**

In `synlynk/dispatch.py`, the existing block reads (around line 754):

```python
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    if agent == "codex":
        flags = flags + ["--json"]
```

Change to add a `claude` block between them:

```python
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    if agent == "claude":
        flags = flags + ["--output-format", "stream-json", "--verbose"]
    if agent == "codex":
        flags = flags + ["--json"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k test_dispatch_agent_claude_flags_include_stream_json_verbose -v`
Expected: PASS.

- [ ] **Step 5: Run the full dispatch-related test batch to check for regressions**

Run: `pytest tests/test_cost_ledger.py -k dispatch_agent -v`
Expected: PASS — both the new claude test and the existing `test_dispatch_agent_codex_flags_include_json` pass; no other dispatch_agent test asserts on `claude`'s flag list, so nothing else should be affected.

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_cost_ledger.py
git commit -m "feat(dispatch): claude jobs run with --output-format stream-json --verbose

--verbose is required by the Claude CLI whenever --print is combined
with --output-format stream-json (verified: the CLI refuses to start
without it). This makes claude job logs raw JSONL, matching what the
codex --json change already did — the log-readability fix for this
lands in the next commit."
```

---

### Task 4: `_render_claude_log_line()` — readable rendering for `synlynk logs`

**Files:**
- Modify: `synlynk/__init__.py` (add function after `_render_codex_log_line`, which ends at line 1999, before `def cmd_logs` at line 2005)
- Test: `tests/test_cost_ledger.py` (add after `test_render_codex_log_line_unparseable_prints_as_is`, around line 1050)

- [ ] **Step 1: Write the failing tests**

```python
def test_render_claude_log_line_text_block():
    from synlynk import _render_claude_log_line

    line = '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hello there"}]}}'
    assert _render_claude_log_line(line) == "Hello there\n\n"


def test_render_claude_log_line_tool_use_block():
    from synlynk import _render_claude_log_line

    line = (
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls -la"}}]}}'
    )
    assert _render_claude_log_line(line) == '$ Bash({"command":"ls -la"})\n\n'


def test_render_claude_log_line_multiple_content_blocks_concatenated():
    from synlynk import _render_claude_log_line

    line = (
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"text","text":"Running it now."},'
        '{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls"}}]}}'
    )
    assert _render_claude_log_line(line) == '$ Bash({"command":"ls"})\n\n'.join(
        ["Running it now.\n\n", ""]
    )


def test_render_claude_log_line_system_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"system","subtype":"init","cwd":"/tmp"}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_rate_limit_event_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed"}}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_result_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"result","subtype":"success","result":"done","usage":{"input_tokens":10,"output_tokens":5}}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_user_tool_result_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"a.txt"}]}}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_unparseable_prints_as_is():
    from synlynk import _render_claude_log_line

    line = "unrecognized flag: --output-format"
    assert _render_claude_log_line(line) == line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k render_claude_log_line -v`
Expected: FAIL — `ImportError: cannot import name '_render_claude_log_line'`.

- [ ] **Step 3: Implement `_render_claude_log_line()`**

In `synlynk/__init__.py`, add this function immediately after `_render_codex_log_line` (ends at line 1999) and before `def cmd_logs` (line 2005):

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k render_claude_log_line -v`
Expected: PASS — all 8 tests green.

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "feat(logs): add _render_claude_log_line() for readable stream-json

Renders assistant text/tool_use content blocks as prose and
\"\$ Tool(args)\" lines respectively; suppresses system/rate_limit_event/
result/user noise; passes unparseable lines through as-is. Not yet
wired into cmd_logs()."
```

---

### Task 5: Wire the renderer into `cmd_logs()`

**Files:**
- Modify: `synlynk/__init__.py:2015-2024` (the `if job.get("agent") == "codex":` branch inside `cmd_logs`)
- Test: `tests/test_cost_ledger.py` (add after `test_cmd_logs_non_codex_agent_unchanged`)

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_logs_renders_claude_stream_json(project_dir, monkeypatch, tmp_path, capsys):
    import synlynk

    log_file = tmp_path / "job-claude2.log"
    log_file.write_text(
        '{"type":"system","subtype":"init","cwd":"/tmp"}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done"}]}}\n'
        '{"type":"result","subtype":"success","result":"Done","usage":{"input_tokens":10,"output_tokens":5}}\n'
    )
    job = {"id": "job-claude2", "agent": "claude", "log_file": str(log_file)}
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(synlynk, "_job_summary_path", lambda job_id: "/nonexistent", raising=False)

    synlynk.cmd_logs("job-claude2")

    out = capsys.readouterr().out
    assert "Done" in out
    assert '"type":"system"' not in out
    assert '"type":"result"' not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_cmd_logs_renders_claude_stream_json -v`
Expected: FAIL — `cmd_logs()` currently only special-cases `agent == "codex"`, so for `agent == "claude"` it prints every raw JSONL line unchanged; `'"type":"system"' not in out` fails because the raw line is printed verbatim.

- [ ] **Step 3: Update the dispatch in `cmd_logs()`**

In `synlynk/__init__.py`, `cmd_logs()` currently has (around line 2015):

```python
    display_lines = lines[-tail:]
    if job.get("agent") == "codex":
        for line in display_lines:
            rendered = _render_codex_log_line(line)
            if rendered is not None:
                print(rendered, end="")
    else:
        for line in display_lines:
            print(line, end="")
```

Change to:

```python
    display_lines = lines[-tail:]
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k test_cmd_logs_renders_claude_stream_json -v`
Expected: PASS.

- [ ] **Step 5: Run the full cmd_logs test batch to check for regressions**

Run: `pytest tests/test_cost_ledger.py -k cmd_logs -v`
Expected: PASS — including `test_cmd_logs_renders_codex_jsonl` (codex path untouched) and `test_cmd_logs_non_codex_agent_unchanged` (that test uses `agent: "claude"` with plain-text, non-JSON lines — `_render_claude_log_line` returns non-JSON lines as-is, so the output is identical to the old raw-passthrough behavior; the test still passes without modification even though `claude` now goes through the renderer).

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "feat(logs): route claude job logs through _render_claude_log_line()

synlynk logs --job <id> now renders Claude's stream-json output as
readable prose, mirroring the codex branch shipped in PR #244."
```

---

### Task 6: Full regression run and final review

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -q --ignore=worktrees`
Expected: All tests pass, zero failures, zero errors. Note the total test count before and after (compare against the pre-change baseline) — every test added in Tasks 1–5 should be counted, nothing should have been silently skipped.

- [ ] **Step 2: Confirm no other agent's behavior changed**

Run: `pytest tests/test_cost_ledger.py -k "codex or grok" -v`
Expected: PASS — this plan touches no codex or grok code paths; this run is a sanity check that the `if agent == "claude":` insertions (Task 2, Task 3) were correctly placed as siblings, not accidentally nested inside or replacing the codex/grok blocks.

- [ ] **Step 3: Manual smoke check of the adapter against a real fixture (optional but recommended)**

If a `claude` CLI is available in the implementation environment:

```bash
claude -p "reply with exactly: hello" --output-format stream-json --verbose > /tmp/claude-smoke.jsonl 2>&1
python3 -c "
from synlynk.costs import _extract_claude_structured
text = open('/tmp/claude-smoke.jsonl').read()
result = _extract_claude_structured(text)
print(result.input_tokens, result.output_tokens, result.cache_read_tokens, result.basis)
"
```
Expected: prints four values, `basis` is `structured_output`, `input_tokens` and `output_tokens` are both positive integers. If the `claude` CLI isn't available in this environment, skip this step — the fixture-based unit tests in Task 1 already cover this using real captured output from the design's own research.

- [ ] **Step 4: Final commit if any cleanup was needed**

Only if Steps 1–3 surfaced an issue requiring a fix. If everything passed cleanly, no commit needed here — Tasks 1–5's commits are the complete change set.

---

## Self-Review Notes (writing-plans skill checklist)

**Spec coverage:**
- §3.1 (dispatch chain) → Task 2
- §3.2 (`_extract_claude_structured`, cache-token mapping, `total_cost_usd` discarded) → Task 1 (function omits `total_cost_usd` entirely — never read from the `usage`/`result` object anywhere in the implementation)
- §3.3 (dispatch flags) → Task 3
- §3.4 (`_render_claude_log_line`, all 7 event-type branches) → Task 4, Task 5
- §3.5 (call sites) → no task; spec confirms these already pass `agent=` from the Codex PR, verified by Task 2's regression run exercising `extract_tokens(agent=...)` through the same signature
- §3.6 (fallback table) → covered implicitly: every `_extract_claude_structured` failure path (Task 1's tests) returns `None`, which Task 2 proves falls through to the existing regex chain, never raises
- §4 (testing) → every bullet has a corresponding test in Tasks 1, 2, 4, 5, or the full-suite run in Task 6
- §5 (out of scope) → no task implements Gemini/Grok adapters, `total_cost_usd` capture, schema changes, tool_result correlation, or the Vizor UI — consistent with the plan's task list touching only `costs.py`, `dispatch.py`, and `__init__.py`'s log renderer

**Placeholder scan:** none — every step has complete, exact code (copied from the spec, which itself was live-verified against real `claude` CLI output).

**Type consistency:** `_TokenCounts(input_tokens, output_tokens, cache_read_tokens, basis)` constructor signature used identically in Task 1's implementation as the existing `_extract_codex_structured` and the class definition at the top of `costs.py`. `_render_claude_log_line(line: str)` return type (`Optional[str]`, though not type-annotated to match `_render_codex_log_line`'s existing untyped signature) matches its three call patterns in Task 5's `cmd_logs()` wiring (`None` → skip, string → print).
