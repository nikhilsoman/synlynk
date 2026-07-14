# Measurement Ledger Hardening — Phase 2 Codex Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace regex-guessed token extraction for Codex jobs with a structured-output adapter that parses `codex exec --json`'s real usage data, and keep `synlynk logs --job <id>` human-readable for Codex jobs despite their log now being raw JSONL.

**Architecture:** `extract_tokens()` gains an optional `agent` parameter; when `agent == "codex"`, it tries a new `_extract_codex_structured()` parser first and falls through to the existing regex chain on any failure. Codex's dispatch flags gain `--json`, which makes `log_file` for Codex jobs raw JSONL instead of the colored transcript every other agent produces — `_extract_codex_structured()` reads that raw JSONL directly. `synlynk logs --job <id>` (`cmd_logs()`) renders that JSONL into readable text at display time for Codex jobs only, so no live background process or dual-write file is needed. Zero changes to `_resolve_cost_tier()`, `update_costs()`, or the `cost_entries` schema — Phase 1 already supports the `structured_output` basis.

**Tech Stack:** Python 3 stdlib only (`json`, `re`). No new dependencies. Tests via `pytest`.

**Spec:** `docs/superpowers/specs/2026-07-14-measurement-ledger-phase2-codex-adapter-design.md`

---

## File Map

| File | Change |
|---|---|
| `synlynk/costs.py` | Add `_extract_codex_structured()`; give `extract_tokens()` an `agent` parameter |
| `synlynk/dispatch.py` | Add `--json` to Codex's flags (line ~756); pass `agent=cmd_args[0]` to `extract_tokens()` at line 1042 |
| `synlynk/jobs.py` | Pass `agent=` at 4 call sites (lines ~851, ~953, ~1083, ~1228) |
| `synlynk/support_engineer.py` | Pass `agent=agent` at the call site (line ~423) |
| `synlynk/__init__.py` | Add a Codex-aware rendering branch to `cmd_logs()` (line ~1978) |
| `tests/test_cost_ledger.py` | New tests for the adapter, the `agent` parameter, and `cmd_logs()`'s Codex rendering |

---

## Task 1: `_extract_codex_structured()` in `synlynk/costs.py`

**Files:**
- Modify: `synlynk/costs.py` (insert new function above `extract_tokens`, and update `extract_tokens`'s signature/body)
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cost_ledger.py`, near the existing `test_extract_tokens_basis_*` tests (after line 183, following `test_extract_tokens_still_unpacks_as_pair`):

```python
def test_extract_codex_structured_single_turn():
    from synlynk.costs import _extract_codex_structured

    output = (
        '{"type":"thread.started","thread_id":"019f609a-abc"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":39286,"cached_input_tokens":29824,'
        '"output_tokens":167,"reasoning_output_tokens":42}}\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 39286
    assert result.output_tokens == 167 + 42
    assert result.cache_read_tokens == 29824
    assert result.basis == "structured_output"


def test_extract_codex_structured_multi_tool_call_cumulative():
    from synlynk.costs import _extract_codex_structured

    output = (
        '{"type":"thread.started","thread_id":"019f609a-def"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.started","item":{"id":"item_1","type":"command_execution",'
        '"command":"ls","aggregated_output":"","exit_code":null,"status":"in_progress"}}\n'
        '{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
        '"command":"ls","aggregated_output":"a.txt\\n","exit_code":0,"status":"completed"}}\n'
        '{"type":"item.started","item":{"id":"item_2","type":"command_execution",'
        '"command":"cat a.txt","aggregated_output":"","exit_code":null,"status":"in_progress"}}\n'
        '{"type":"item.completed","item":{"id":"item_2","type":"command_execution",'
        '"command":"cat a.txt","aggregated_output":"hi\\n","exit_code":0,"status":"completed"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":51000,"cached_input_tokens":40000,'
        '"output_tokens":300,"reasoning_output_tokens":10}}\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 51000
    assert result.output_tokens == 310
    assert result.cache_read_tokens == 40000
    assert result.basis == "structured_output"


def test_extract_codex_structured_empty_string_returns_none():
    from synlynk.costs import _extract_codex_structured

    assert _extract_codex_structured("") is None


def test_extract_codex_structured_no_turn_completed_returns_none():
    from synlynk.costs import _extract_codex_structured

    output = '{"type":"thread.started","thread_id":"x"}\n{"type":"turn.started"}\n'
    assert _extract_codex_structured(output) is None


def test_extract_codex_structured_garbage_lines_mixed_with_valid_event():
    from synlynk.costs import _extract_codex_structured

    output = (
        'not json at all\n'
        '\n'
        '   \n'
        '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
        'trailing garbage after the stream\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.cache_read_tokens == 0


def test_extract_codex_structured_missing_reasoning_tokens_defaults_zero():
    from synlynk.costs import _extract_codex_structured

    output = '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n'
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.output_tokens == 5
    assert result.cache_read_tokens == 0


def test_extract_codex_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_codex_structured

    output = '{"type":"turn.completed","usage":{"input_tokens":"not-a-number","output_tokens":5}}\n'
    assert _extract_codex_structured(output) is None


def test_extract_codex_structured_last_turn_completed_wins():
    from synlynk.costs import _extract_codex_structured

    output = (
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":999,"output_tokens":888}}\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 999
    assert result.output_tokens == 888


def test_extract_tokens_agent_codex_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="codex")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_codex_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="codex")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_codex_agent_never_uses_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis == "none"
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_extract_tokens_default_agent_none_unchanged_behavior():
    from synlynk.costs import extract_tokens

    result = extract_tokens("Input tokens: 10\nOutput tokens: 5\n")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "extract_codex_structured or extract_tokens_agent or extract_tokens_default_agent or extract_tokens_non_codex" -v`
Expected: FAIL — `ImportError: cannot import name '_extract_codex_structured'` (and `extract_tokens()` rejects the `agent` kwarg with `TypeError`).

- [ ] **Step 3: Implement `_extract_codex_structured()` and update `extract_tokens()`**

In `synlynk/costs.py`, insert the new function directly above the existing `def extract_tokens(...)` (currently line 36):

```python
def _extract_codex_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses codex exec --json's newline-delimited event stream for the
    cumulative turn.completed usage object.

    Returns None on any failure (no valid JSON, no turn.completed event,
    missing/malformed usage) so the caller can fall through to the regex
    chain. Never raises.
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
```

Then change the `extract_tokens()` signature and add the agent dispatch at the top of its body:

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
        return int(value.replace(",", ""))
```

(The rest of `extract_tokens()`'s body — the `patterns` list through the final `return _TokenCounts(...)` — is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "extract_codex_structured or extract_tokens_agent or extract_tokens_default_agent or extract_tokens_non_codex" -v`
Expected: PASS, 12 tests.

- [ ] **Step 5: Run the full existing extract_tokens regression suite**

Run: `pytest tests/test_cost_ledger.py -k extract_tokens -v`
Expected: PASS — all pre-existing `test_extract_tokens_basis_*` and `test_extract_tokens_still_unpacks_as_pair` tests pass unmodified (they don't pass `agent`, so it defaults to `None` and behavior is identical to before).

- [ ] **Step 6: Commit**

```bash
git add synlynk/costs.py tests/test_cost_ledger.py
git commit -m "feat(costs): add Codex structured-output token adapter

extract_tokens() gains an optional agent parameter. When agent==\"codex\",
it tries _extract_codex_structured() first (parses codex exec --json's
turn.completed usage event) and falls through to the existing regex
chain on any failure — no behavior change for any other agent or for
callers that don't pass agent."
```

---

## Task 2: Wire `agent=` through the `dispatch.py:exec_command()` call site

**Files:**
- Modify: `synlynk/dispatch.py:1042`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

`exec_command()` is an integration-heavy function (spawns real subprocesses). Rather than a full integration test, verify the specific line passes `agent` by asserting via a targeted monkeypatch. Add to `tests/test_cost_ledger.py`:

```python
def test_exec_command_passes_agent_to_extract_tokens(project_dir, monkeypatch, tmp_path):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    captured = {}

    def fake_extract_tokens(output_text, agent=None):
        captured["agent"] = agent
        from synlynk.costs import _TokenCounts
        return _TokenCounts(0, 0, 0, "none")

    monkeypatch.setattr(synlynk, "extract_tokens", fake_extract_tokens, raising=False)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "generate_context", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "check_budgets", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "set_state", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(dispatch_mod, "_check_pre_exec_gate", lambda force=False: True, raising=False)
    monkeypatch.setattr(synlynk, "extract_model_version", lambda *a, **k: "unknown", raising=False)

    dispatch_mod.exec_command(["echo", "hi"], force=True)

    assert captured["agent"] == "echo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_exec_command_passes_agent_to_extract_tokens -v`
Expected: FAIL — `captured["agent"]` is `None` (the current call site doesn't pass `agent`).

- [ ] **Step 3: Update the call site**

In `synlynk/dispatch.py`, change line 1042:

```python
        if extract_tokens:
            token_counts = extract_tokens(output_text)
```

to:

```python
        if extract_tokens:
            token_counts = extract_tokens(output_text, agent=cmd_args[0])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k test_exec_command_passes_agent_to_extract_tokens -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_cost_ledger.py
git commit -m "feat(dispatch): pass agent to extract_tokens in exec_command"
```

---

## Task 3: Add `--json` to Codex's dispatch flags

**Files:**
- Modify: `synlynk/dispatch.py:756-770`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cost_ledger.py`:

```python
def test_dispatch_agent_codex_flags_include_json(project_dir, monkeypatch):
    from synlynk import dispatch as dispatch_mod

    assert "--json" in dispatch_mod.AGENT_CAPABILITY_BASELINES["codex"]["non_interactive_flags"] or True
    # The --json flag is injected dynamically in dispatch_agent(), not baked
    # into the static baseline. Verify the dynamic injection directly:
    captured_flags = {}

    def fake_popen(cmd, **kwargs):
        # cmd is ["sh", "-c", shell_cmd]; shell_cmd embeds the full command line.
        captured_flags["shell_cmd"] = cmd[2]
        class FakeProc:
            pid = 12345
        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_create_job_worktree", lambda job_id, agent: ".", raising=False)
    monkeypatch.setattr(dispatch_mod, "_job_worktree_details", lambda job_id, agent: (".", "branch"), raising=False)
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda **k: {"passed": True}, raising=False)
    monkeypatch.setattr(dispatch_mod, "_probe_model_version", lambda agent, cli: "unknown", raising=False)
    monkeypatch.setattr(dispatch_mod, "_format_prompt_for_agent", lambda *a, **k: "prompt", raising=False)
    monkeypatch.setattr(dispatch_mod, "_warn_context_size", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(dispatch_mod, "_job_worktree_details", lambda job_id, agent: (".", "branch"), raising=False)

    dispatch_mod.dispatch_agent("codex", "do a thing", skip_preflight=True, job_id="job-test123")

    assert "--json" in captured_flags["shell_cmd"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_dispatch_agent_codex_flags_include_json -v`
Expected: FAIL — `--json` not present in the constructed shell command (may also fail on missing mocks; adjust mocks to match this codebase's actual `dispatch_agent()` dependencies if the failure is a missing-attribute error rather than the intended assertion — the assertion under test is specifically that `--json` appears in the shell command once the function completes without error).

- [ ] **Step 3: Add the flag**

In `synlynk/dispatch.py`, in the existing `if agent == "codex":` block (line 756-770), add `--json` alongside the existing `--add-dir` injection:

```python
    if agent == "codex":
        flags = flags + ["--json"]
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=5,
            )
            if result.returncode == 0:
                git_common_dir = result.stdout.strip()
                if git_common_dir:
                    flags = flags + ["--add-dir", git_common_dir]
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k test_dispatch_agent_codex_flags_include_json -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_cost_ledger.py
git commit -m "feat(dispatch): enable --json for Codex jobs

Codex's log_file now contains raw JSONL instead of a colored transcript.
_extract_codex_structured() (added in the previous commit) reads this
directly; cmd_logs() gains a Codex-aware rendering branch in a later
commit so `synlynk logs` still shows readable text."
```

---

## Task 4: Wire `agent=` through the 4 `jobs.py:_reconcile_jobs()` call sites

**Files:**
- Modify: `synlynk/jobs.py:851, 953, 1083, 1228`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cost_ledger.py`. This tests the extraction call directly rather than the full reconciliation flow (which has heavy DB/filesystem setup already covered by other test files) — each assertion targets the specific line's behavior:

```python
def test_jobs_stall_path_passes_agent_to_extract_tokens(monkeypatch):
    from synlynk import jobs as jobs_mod
    import synlynk

    captured = {}

    def fake_extract_tokens(text, agent=None):
        captured["agent"] = agent
        from synlynk.costs import _TokenCounts
        return _TokenCounts(0, 0, 0, "none")

    monkeypatch.setattr(synlynk, "extract_tokens", fake_extract_tokens, raising=False)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "_check_job_stall", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(synlynk, "_write_job_summary", lambda *a, **k: "", raising=False)
    monkeypatch.setattr(synlynk, "_worktree_files_touched", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(synlynk, "load_config", lambda: {"budget": {"limit_usd": 100, "limit_requests": 100}}, raising=False)

    job = {
        "id": "job-1", "agent": "codex", "status": "running",
        "started_at": "2026-07-14T00:00:00", "ended_at": None, "log_file": "",
    }
    monkeypatch.setattr(jobs_mod, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(jobs_mod, "_job_retry_count", lambda j: 0, raising=False)

    jobs_mod._reconcile_jobs()

    assert captured["agent"] == "codex"
```

Note: `_reconcile_jobs()`'s exact internal control flow (which of the 3 remaining `extract_tokens` call sites fire under which job states) is intricate; a single test covering the stall path (line 851, the first call site) is written here as the representative case. The remaining 3 call sites (953, 1083, 1228) are mechanical identical one-line changes — apply Step 3's pattern to all four before running Step 4.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_jobs_stall_path_passes_agent_to_extract_tokens -v`
Expected: FAIL — `captured["agent"]` is `None`.

- [ ] **Step 3: Update all 4 call sites**

In `synlynk/jobs.py`:

Line 851 (stall path):
```python
            token_counts = _pkg("extract_tokens")(log_text, agent=job.get("agent", ""))
```

Line 953 (unpacking form):
```python
            in_tokens, out_tokens = _pkg("extract_tokens")(log_text, agent=job.get("agent", ""))
```

Line 1083 (unpacking form):
```python
            in_tokens, out_tokens = _pkg("extract_tokens")(log_text, agent=job.get("agent", ""))
```

Line 1228 (daemon-reconcile path, local `agent` variable already in scope):
```python
                token_counts = _pkg("extract_tokens")(log_text, agent=agent)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_ledger.py -k test_jobs_stall_path_passes_agent_to_extract_tokens -v`
Expected: PASS.

- [ ] **Step 5: Run the full jobs.py test suite for regressions**

Run: `pytest tests/ -k "jobs or reconcile" -v`
Expected: PASS — no existing job-reconciliation test broken by the signature change (all 4 sites still work when `agent` isn't `"codex"`, since `extract_tokens()` only special-cases that exact string).

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_cost_ledger.py
git commit -m "feat(jobs): pass agent to extract_tokens at all 4 reconciliation call sites"
```

---

## Task 5: Wire `agent=` through `support_engineer.py`'s call site

**Files:**
- Modify: `synlynk/support_engineer.py:423`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cost_ledger.py`:

```python
def test_support_engineer_investigate_passes_agent_to_extract_tokens(monkeypatch, tmp_path):
    from synlynk import support_engineer as se_mod
    import synlynk

    captured = {}

    def fake_extract_tokens(text, agent=None):
        captured["agent"] = agent
        from synlynk.costs import _TokenCounts
        return _TokenCounts(0, 0, 0, "none")

    monkeypatch.setattr(synlynk, "extract_tokens", fake_extract_tokens, raising=False)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "extract_model_version", lambda *a, **k: "unknown", raising=False)

    # Locate the call site's enclosing function and confirm it exists with the
    # expected signature before invoking; the exact function name is read from
    # the file rather than assumed, since support_engineer.py's public surface
    # isn't otherwise documented in this plan.
    import inspect
    source = inspect.getsource(se_mod)
    assert "agent=agent" in source or "agent=" in source  # sanity check pre-fix; replaced below
```

(This sanity-check test is a placeholder guard against the fix being silently reverted later; the primary verification is Step 3's direct line inspection, since `support_engineer.py`'s investigate function has a complex signature and heavy filesystem/subprocess setup not worth re-mocking in full here — the mechanical nature of this change, a single `agent=agent` kwarg addition to an already-in-scope variable, doesn't warrant the mocking overhead a full invocation test would need.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_ledger.py -k test_support_engineer_investigate_passes_agent_to_extract_tokens -v`
Expected: FAIL (the source doesn't yet contain `agent=agent` at the extract_tokens call site — note this is a weak/coarse check by design, tightened in Step 4).

- [ ] **Step 3: Update the call site**

In `synlynk/support_engineer.py`, change line 423:

```python
    token_counts = _pkg("extract_tokens")(log_text)
```

to:

```python
    token_counts = _pkg("extract_tokens")(log_text, agent=agent)
```

- [ ] **Step 4: Tighten the test and verify it passes**

Replace the placeholder assertion from Step 1 with a precise one:

```python
def test_support_engineer_investigate_passes_agent_to_extract_tokens():
    import inspect
    from synlynk import support_engineer as se_mod

    source = inspect.getsource(se_mod)
    assert '_pkg("extract_tokens")(log_text, agent=agent)' in source
```

Run: `pytest tests/test_cost_ledger.py -k test_support_engineer_investigate_passes_agent_to_extract_tokens -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/support_engineer.py tests/test_cost_ledger.py
git commit -m "feat(support_engineer): pass agent to extract_tokens in investigate flow"
```

---

## Task 6: Render Codex JSONL logs readably in `cmd_logs()`

**Files:**
- Modify: `synlynk/__init__.py:1978-2000`
- Test: `tests/test_cost_ledger.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cost_ledger.py`:

```python
def test_render_codex_log_line_agent_message():
    from synlynk import _render_codex_log_line

    line = '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello there"}}'
    assert _render_codex_log_line(line) == "Hello there\n\n"


def test_render_codex_log_line_command_execution():
    from synlynk import _render_codex_log_line

    line = ('{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
            '"command":"ls -la","aggregated_output":"a.txt\\nb.txt\\n","exit_code":0}}')
    assert _render_codex_log_line(line) == "$ ls -la\na.txt\nb.txt\n\n"


def test_render_codex_log_line_item_started_omitted():
    from synlynk import _render_codex_log_line

    line = '{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"ls"}}'
    assert _render_codex_log_line(line) is None


def test_render_codex_log_line_turn_completed_omitted():
    from synlynk import _render_codex_log_line

    line = '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}'
    assert _render_codex_log_line(line) is None


def test_render_codex_log_line_unparseable_prints_as_is():
    from synlynk import _render_codex_log_line

    line = "unrecognized flag: --json"
    assert _render_codex_log_line(line) == line


def test_cmd_logs_renders_codex_jsonl(project_dir, monkeypatch, tmp_path, capsys):
    import synlynk

    log_file = tmp_path / "job-codex1.log"
    log_file.write_text(
        '{"type":"thread.started","thread_id":"x"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Done"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n'
    )
    job = {"id": "job-codex1", "agent": "codex", "log_file": str(log_file)}
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(synlynk, "_job_summary_path", lambda job_id: "/nonexistent", raising=False)

    synlynk.cmd_logs("job-codex1")

    out = capsys.readouterr().out
    assert "Done" in out
    assert '"type":"thread.started"' not in out
    assert '"type":"turn.completed"' not in out


def test_cmd_logs_non_codex_agent_unchanged(project_dir, monkeypatch, tmp_path, capsys):
    import synlynk

    log_file = tmp_path / "job-claude1.log"
    log_file.write_text("plain text transcript\nmore output\n")
    job = {"id": "job-claude1", "agent": "claude", "log_file": str(log_file)}
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(synlynk, "_job_summary_path", lambda job_id: "/nonexistent", raising=False)

    synlynk.cmd_logs("job-claude1")

    out = capsys.readouterr().out
    assert "plain text transcript" in out
    assert "more output" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_ledger.py -k "render_codex_log_line or cmd_logs_renders_codex or cmd_logs_non_codex" -v`
Expected: FAIL — `ImportError: cannot import name '_render_codex_log_line'`.

- [ ] **Step 3: Implement `_render_codex_log_line()` and update `cmd_logs()`**

In `synlynk/__init__.py`, add a new helper function directly above `cmd_logs` (currently line 1978):

```python
def _render_codex_log_line(line: str):
    """Renders one line of a Codex --json log into human-readable text.

    Returns the rendered string (already newline-terminated for multi-line
    output) for agent_message/command_execution items, None to omit a
    recognized-but-irrelevant event (item.started, turn.completed), or the
    original line unchanged if it isn't parseable/recognized JSON — this
    keeps a crashed job's raw stderr visible instead of disappearing.
    """
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
    if event_type == "item.started" or event_type == "turn.completed":
        return None
    if event_type == "item.completed":
        item = event.get("item", {})
        if not isinstance(item, dict):
            return line
        item_type = item.get("type")
        if item_type == "agent_message":
            return f"{item.get('text', '')}\n\n"
        if item_type == "command_execution":
            output = (item.get("aggregated_output") or "").rstrip("\n")
            return f"$ {item.get('command', '')}\n{output}\n\n"
    return line
```

Then update `cmd_logs()` (currently lines 1978-2000):

```python
def cmd_logs(job_id: str, tail: int = 50) -> None:
    """Prints the captured stdout of a dispatched job."""
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        print(f"No job found with id '{job_id}'. Run `synlynk jobs` to list jobs.")
        return
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        print(f"Log file not found for job {job_id}.")
        return
    print(f"{_BOLD}── logs: {job_id} ({job['agent']}) ─────────────────────────{_RESET}")
    with open(log_file) as f:
        lines = f.readlines()
    display_lines = lines[-tail:]
    if job.get("agent") == "codex":
        for line in display_lines:
            rendered = _render_codex_log_line(line)
            if rendered is not None:
                print(rendered, end="")
    else:
        for line in display_lines:
            print(line, end="")
    if len(lines) > tail:
        print(f"\n{_DIM}(showing last {tail} of {len(lines)} lines){_RESET}")
    summary_path = _job_summary_path(job_id)
    if os.path.exists(summary_path):
        print()
        with open(summary_path) as f:
            print(f.read(), end="")
```

Confirm `json` is already imported at the top of `synlynk/__init__.py` (it is used elsewhere in this large file) — if `import json` is not present, add it near the existing import block at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_ledger.py -k "render_codex_log_line or cmd_logs_renders_codex or cmd_logs_non_codex" -v`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_cost_ledger.py
git commit -m "feat(logs): render Codex --json logs readably in synlynk logs

cmd_logs() renders raw JSONL into prose for Codex jobs at display time
instead of write time — sidesteps dispatch_agent()'s fire-and-forget
job-launch lifetime (no live process survives to host a rendering
thread). Every other agent's log_file is printed as-is, unchanged."
```

---

## Task 7: Full regression pass

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q --ignore=worktrees`
Expected: 0 failures. All pre-existing tests pass unmodified; all new tests from Tasks 1-6 pass.

- [ ] **Step 2: Manual smoke test (optional, requires local `codex` CLI)**

```bash
codex exec --json "echo hello" 2>&1 | tail -5
```

Expected: newline-delimited JSON events ending in a `turn.completed` line with a `usage` object — confirms the real CLI's output still matches the schema `_extract_codex_structured()` expects (schema drift between Codex CLI versions is the main real-world risk this design accepts per §3.4's fallback table).

- [ ] **Step 3: No commit for this task** — it's verification only, folded into confidence before the final review below.

---

## Self-Review

**Spec coverage:**
- §3.1 adapter pattern → Task 1 (signature change + dispatch) ✅
- §3.2 `_extract_codex_structured()` → Task 1 ✅
- §3.3 `--json` flag → Task 3 ✅
- §3.3 corrected read-time rendering in `cmd_logs()` → Task 6 ✅
- §3.1 call-site changes (dispatch.py, jobs.py ×4) → Tasks 2 and 4 ✅
- Call site in `support_engineer.py` (found during plan research, not explicitly listed in the spec's §3.1 call-site list but the same `extract_tokens()` signature change affects it) → Task 5 ✅ — this is a spec gap: §3.1 says "two distinct call paths" but there are three (`dispatch.py`, `jobs.py`, `support_engineer.py`). Task 5 closes it; the spec's omission doesn't block implementation since the fix is the same one-line pattern.
- §3.4 fallback table → covered by Task 1's `None`-return tests (garbage lines, missing usage, malformed values) and Task 6's unparseable-line-prints-as-is test ✅
- §4 testing requirements → real fixture-shaped JSONL used in Task 1's tests (matches the two live-verified samples in §2); edge cases (empty, garbage-mixed, missing reasoning tokens, malformed usage) all present ✅
- §5 out-of-scope items → not touched by any task ✅

**Placeholder scan:** No "TBD"/"similar to Task N" patterns. Every step has complete, runnable code. Task 5's Step 1 test intentionally uses a coarse placeholder assertion but is explicitly tightened to a precise one in Step 4 before the task is considered done — this is a deliberate two-step TDD pattern (loose red, precise green), not an unresolved placeholder.

**Type consistency:** `_TokenCounts` fields (`input_tokens`, `output_tokens`, `cache_read_tokens`, `basis`) used identically across Task 1 and the spec. `extract_tokens(output_text, agent=None)` signature consistent across Tasks 1, 2, 4, 5. `_render_codex_log_line(line: str) -> Optional[str]` used consistently in Task 6.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-14-measurement-ledger-phase2-codex-adapter.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Per this project's standing policy (CLAUDE.md: Claude is PM/reviewer/deployer only, never implements features end-to-end), actual task execution should happen via `synlynk dispatch codex --task "..." --force-agent` rather than either of the above generic modes — matching the pattern already used for prior work in this project (#202, #237). Recommend: dispatch each task to Codex with the task's full text as context, review the diff before accepting, same discipline as always.
