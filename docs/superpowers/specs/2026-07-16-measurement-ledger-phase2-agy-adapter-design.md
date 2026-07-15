# Measurement Ledger Hardening — Phase 2, Agent 3: Gemini/Agy Structured-Output Adapter

**Status:** Draft for review
**Parent epic:** #210 (Structured Integration Layer)
**Depends on:** Measurement Ledger Hardening Phase 1 (PR #236/#241/#242, merged), Phase 2 Codex pilot (PR #244/#245, merged — establishes the adapter pattern this design reuses), Phase 2 Claude adapter (PR #252, merged — second application of the pattern, precedent for the mapping-decision style used below)
**Scope:** Third of four per-agent structured-output adapters. Grok remains, its own follow-on PR per the Codex pilot's §5 scoping.

---

## 1. Problem

`extract_tokens(output_text, agent=None)` (`synlynk/costs.py`) now has agent-specific branches for `codex` and `claude`, each trying a `_extract_<agent>_structured()` parser first and falling back to the shared regex chain on `None`. The dispatched agent for Gemini in this codebase is `agy` (confirmed below — not `gemini`), and it has no such branch: `agy` job output is parsed by the same regex-pattern chain used for every unstructured agent, subject to the same `regex_pair`/`total_split`/`none` basis ceiling Phase 1 flagged as a guess against unstructured text.

Epic #210's body names `synlynk/local_agent.py` as a template worth reusing for the remaining adapters. Verified live (read in full): that file is config-loading and health-check code for the unrelated `local`/aider/oMLX dispatch path — it contains no token-extraction logic and no structured-output parser. This reference does not apply and is not used below.

## 2. What Already Exists (verified live, not assumed)

Confirmed by running the actual dispatched `agy` binary locally (twice — one plain single-turn prompt, one prompt that required an internal `ls` tool call), by binary-strings analysis of the CLI itself, and by reading `origin/main`'s current `synlynk/_constants.py`, `synlynk/dispatch.py`, `synlynk/probe.py`, and `synlynk/costs.py` directly:

- **The dispatched agent name is `agy`, not `gemini`.** A package-wide grep (`grep -rn '"gemini"\|"agy"' synlynk/*.py`) confirms `"agy"` is the sole dispatch-agent identifier used in `dispatch.py`, `costs.py`, `db.py`, `doctor.py`, `hud.py`, `instructions.py`, `status.py`, `scan.py`, `probe.py`, `viz.py`, `wizard.py`. The string `"gemini"` appears only in a couple of vestigial `known_agents` fallback lists, never as a dispatched identifier.
- **The `agy` binary is not Google's official `gemini` CLI.** `which agy` → `/Users/nikhilsoman/.local/bin/agy`, a genuine Mach-O arm64 executable. `which gemini` → a separate npm-distributed binary under `~/.nvm/...`. They are unrelated; the design below is built against the actual dispatched binary, not assumed from the well-known official CLI's behavior.
- `agy --version` → `1.1.2`. `agy --help` lists `-p`/`--print`/`--prompt`, `--model`, `--add-dir`, `--sandbox`, `--dangerously-skip-permissions`, `--mode`, `--conversation`, `-c`/`--continue`, and others — **no `--output-format`, `--json`, or similar flag appears in the documented help output.**
- **An undocumented `--output-format` flag exists**, discovered via `strings /Users/nikhilsoman/.local/bin/agy | grep -iE "^--?(output|json|format|stream)"`, which surfaced the embedded validation string `"--json-schema can only be used when --output-format is 'json'"`. The flag is real but hidden from `--help`.
- **Live-confirmed behavior of `agy -p "<task>" --output-format json`**: unlike both Codex and Claude (newline-delimited JSON event streams, scanned for a specific terminal event type), **agy emits exactly one JSON object per invocation**, confirmed identically across a plain prompt and a prompt that required the model to internally use a tool (`ls`) — no intermediate per-tool-call events appear in the output; the tool use happens invisibly and only the final single JSON blob is printed. Confirmed schema, both samples:
  ```json
  {
    "conversation_id": "...",
    "status": "SUCCESS",
    "response": "...",
    "duration_seconds": 12.34,
    "num_turns": 1,
    "usage": {
      "input_tokens": 80648,
      "output_tokens": 2390,
      "thinking_tokens": 1922,
      "total_tokens": 83038
    }
  }
  ```
- **`total_tokens == input_tokens + output_tokens`, with `thinking_tokens` excluded from that sum** — verified arithmetically in both live samples (83038 = 80648 + 2390, excluding 1922; 87669 = 84375 + 3294, excluding 2632). `thinking_tokens` is a distinct, unfolded pool, analogous to Codex's `reasoning_output_tokens` (which the shipped Codex adapter folds into `out_tokens`).
- **No cache-read/cache-creation concept appears anywhere in `usage`** — unlike Claude's `cache_read_input_tokens`/`cache_creation_input_tokens`. The eventual parser has no cache-read value to report.
- **`status` was `"SUCCESS"` in both live samples; no failure-mode value has been observed live.** The design below treats any non-`"SUCCESS"` status as an extraction failure (falls through to the regex chain) rather than guessing at an untested failure schema.
- **A critical preflight constraint, not present for Codex or Claude**: `synlynk/probe.py:_run_tc2()` checks every flag listed in an agent's `_constants.py` `valid_flags`/`required_flags` against that agent's literal `--help` output text, and fails preflight (blocking every dispatch with a `HARNESS_PREFLIGHT_FAIL` `RuntimeError`) if a listed flag's text doesn't appear there. `agy`'s current `_constants.py` baseline (`dispatch_flags.valid_flags`) is `["--print", "--model", "--add-dir", "--sandbox"]` — it does **not** include `--output-format`, and it must **not** be added there, since `--output-format` is confirmed absent from `agy --help`'s text and doing so would break TC-2 on every single `agy` dispatch. This mirrors how Codex's and Claude's own `--output-format`/`--json` flags were never added to their `_constants.py` `valid_flags` either — the flag is appended directly in `dispatch_agent()`'s flag-build block, never declared as a TC-2-checked flag.
- `dispatch_agent()` in `synlynk/dispatch.py` already has an `if agent == "grok": flags = flags + ["--output-format", "json"]` block — coincidentally the identical flag/value `agy` needs, though this design keeps `agy` as its own independent sibling block (§3.3) rather than merging the two, matching the established flat-chain pattern (`grok`, `claude`, `codex` are each independent `if` blocks, not merged despite overlap).
- All `extract_tokens()` call sites already pass `agent=` (wired through during the Codex PR). No call-site signature changes needed.
- `cmd_logs()` (`synlynk/__init__.py`) currently special-cases `codex` and `claude`, each with a per-line renderer, falling back to raw passthrough for every other agent. Given agy's single-JSON-object output has no multi-event noise to suppress, this design does not add a renderer for `agy` (§3.4).

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
    if agent == "agy":
        structured = _extract_agy_structured(output_text)
        if structured is not None:
            return structured
    # ... existing regex-pattern chain, unchanged, as fallback
```

Still a flat chain, no registry — third agent, within the budget both prior specs described (a registry becomes worth it at a fourth/fifth agent, not the third).

### 3.2 Agy usage extraction: `_extract_agy_structured()`

```python
def _extract_agy_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses agy -p --output-format json's single JSON object response.

    thinking_tokens is folded into output_tokens (billable output, mirrors
    Codex's reasoning_output_tokens treatment). No cache-read concept exists
    in agy's usage shape, so cache_read_tokens is always 0.
    """
    lines = [l.strip() for l in output_text.splitlines() if l.strip()]
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

Two deliberate choices, made here rather than left ambiguous, both confirmed with the project owner during design:

- **`thinking_tokens` folds into `out_tokens`.** Mirrors Codex's `reasoning_output_tokens` → `out_tokens` treatment: thinking tokens are billed output on the vendor's side, and folding keeps the cost ledger's billable-output accounting consistent across agents rather than silently undercounting.
- **`status != "SUCCESS"` is treated as an extraction failure**, not a distinct code path. No failure-mode JSON shape has been observed live; guessing at one risks building against a schema that doesn't match reality. Falling through to `None` (and therefore the regex chain) is the same "never raise, never guess past what's been verified" posture both prior adapters used for any other unparseable output.
- Only the **last non-empty line** is parsed (not scanned line-by-line like Codex/Claude), since agy's output is confirmed to be a single JSON object, not an event stream. This is a structural difference from both prior adapters' parsers, not an oversight — trailing blank lines are the only variation seen live, so trimming and taking the last line is sufficient and avoids falsely matching against `response` field text that might itself contain embedded newlines and JSON-like substrings if scanned line-by-line instead.

### 3.3 Dispatch flags: enabling `--output-format json`

`synlynk/dispatch.py:dispatch_agent()` gains a new, independent sibling block — not merged with the existing `grok` block despite the identical flag/value, per the established flat-chain convention:

```python
if agent == "agy":
    flags = flags + ["--output-format", "json"]
```

`_constants.py`'s `agy` baseline (`dispatch_flags.valid_flags`) is **not** modified — see §2's TC-2 finding. Adding `--output-format` there would fail preflight on every `agy` dispatch, since the flag is confirmed absent from `agy --help`'s text.

### 3.4 Log readability: no renderer added

Unlike Codex and Claude, agy's output is a single JSON object per invocation, not a multi-event stream — there is no per-line noise (hook events, rate-limit telemetry, tool-result echoes) to selectively suppress. `cmd_logs()`'s existing renderer dispatch (`codex` → `_render_codex_log_line`, `claude` → `_render_claude_log_line`, else → raw passthrough) is left unmodified; `agy` falls into the existing raw-passthrough branch. The one JSON blob printed as-is is already reasonably compact and includes the full `response` text; adding a renderer here would only reformat one object's fields with no noise to filter, which doesn't carry its weight as a task in this adapter's scope. Revisiting this remains possible as a future, separately-scoped enhancement if raw JSON in `synlynk jobs logs` proves hard to read in practice.

### 3.5 Call sites

No changes. `agent=` is already threaded through every `extract_tokens()` call site from the Codex PR. `extract_tokens(text, agent="agy")` now routes to §3.2 automatically.

### 3.6 Fallback behavior (explicit failure modes)

| Scenario | Result |
|---|---|
| `agy` CLI version doesn't support `--output-format json` (flag rejected, nonzero exit before any output) | `log_file` contains agy's stderr about the bad flag → `_extract_agy_structured()`'s `json.loads()` on the last line fails → returns `None` → regex chain runs against whatever text exists (no worse than today) |
| `--output-format json` accepted but `status` is not `"SUCCESS"` (untested failure mode — e.g. refusal, internal error, timeout) | `_extract_agy_structured()` explicitly returns `None` on any non-`"SUCCESS"` status → regex fallback |
| `usage` shape changes in a future agy release (field renamed/removed) | `KeyError`/`ValueError` caught → `None` → regex fallback, same posture as Codex/Claude |
| Job killed mid-run (stall-killer, SIGKILL) before the JSON object is fully written | Last "line" is incomplete/truncated JSON → `json.loads()` fails → `None` → regex fallback |
| Everything works | `basis="structured_output"` → `_resolve_cost_tier()` (unchanged) → same downstream behavior as Codex/Claude today |

No new failure mode can produce a dispatch error or a missing cost row — same invariant Phase 1 established and both prior adapters preserved.

## 4. Testing

- Unit tests for `_extract_agy_structured()` using the two live fixture JSON captures from this design's research (plain prompt, tool-use-requiring prompt) — asserts exact `in_tokens` (= `input_tokens`), `out_tokens` (= `output_tokens` + `thinking_tokens`), `cache_read_tokens == 0`, `basis="structured_output"`.
- Edge cases: empty string → `None`; malformed/truncated JSON on the last line → `None`; `status` present but not `"SUCCESS"` (e.g. `"FAILED"`) → `None`; `usage` missing entirely → `None`; `usage` missing `thinking_tokens` → falls back to `0`, doesn't raise; `usage` with a non-numeric field → `None`; trailing blank lines after the JSON object → still parses correctly (proves last-non-empty-line selection works, not naive `lines[-1]`).
- Unit test: `extract_tokens(text, agent="agy")` with valid structured output returns `basis="structured_output"`; with plain, non-JSON text falls through to the existing regex chain unchanged; `extract_tokens(text, agent="codex")`, `agent="claude"`, or `agent=None` never call the agy path regardless of input content — proves no cross-agent leakage, matching the equivalent Codex/Claude tests.
- Unit test: `dispatch_agent()` flag-build for `agent="agy"` includes `["--output-format", "json"]` in the resulting flags, and preflight (`TC-2`) still passes for `agy` (i.e. confirms `_constants.py`'s `valid_flags` was correctly left unmodified and the flag addition doesn't trip the check).
- No renderer tests — none added, per §3.4.
- Regression: full existing `extract_tokens()` test suite (including Codex and Claude structured-output tests) must still pass unmodified.
- Run `pytest -q --ignore=worktrees` (project convention) with zero new failures.

## 5. Out of Scope (for this design)

- Grok structured adapter — its own follow-on PR, own live investigation of actual CLI output, reusing §3.1's `if agent == "<name>":` pattern directly.
- Any change to `_resolve_cost_tier()`, `update_costs()`, or the `cost_entries` schema — none needed, mirrors both prior specs.
- `cmd_logs()` renderer for `agy` — deliberately deferred, see §3.4.
- `_constants.py` changes for `agy` — deliberately not made, see §2 and §3.3.
- `conversation_id`, `duration_seconds`, `num_turns` capture — present in the parsed JSON but not needed by the ledger; only `usage` and `status` are read.
- The Vizor estimated-flagging UI (separate PR per epic #210's own body) — unrelated to this adapter.
- Retroactively re-extracting tokens for historical `agy` job logs written before this change lands — Phase 1's historical-backfill rule (never retroactively upgrade a row's confidence tier) applies unchanged.

## 6. Release Sequencing

v0.12.0 "Trust & Cost-Aware Routing" already unblocked and shippable as of the Codex pilot; this PR is a fast-follow within the same theme, not a release blocker. No sequencing decision needed beyond "lands whenever it's ready."

## 7. Self-Review Notes

- **Placeholder scan:** none — parser code, flag change, and the fallback table are all fully specified with real code or precise, live-verified behavior.
- **Internal consistency:** §3.2's two mapping decisions (thinking_tokens folding, status-failure handling) are stated with their reasoning, matching the style both prior adapter specs used for their own mapping decisions. §3.3 explicitly notes the TC-2 constraint discovered during design rather than silently working around it.
- **Scope check:** narrowed to one agent, consistent with the "pattern + one agent per PR" cadence Codex's pilot established; §5 makes exclusions explicit, including the deliberately-skipped renderer task.
- **Ambiguity check:** "what if `status` isn't `SUCCESS`" resolved (extraction failure, no invented failure schema). "why not merge the agy/grok dispatch.py blocks despite identical flag values" resolved explicitly (coincidence, not a permanent coupling — kept as independent sibling blocks). "why parse only the last line instead of scanning line-by-line like Codex/Claude" resolved explicitly in §3.2.
