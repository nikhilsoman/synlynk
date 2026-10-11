# GenericAPIAdapter — Design Spec

**Date:** 2026-10-11
**Issue:** gh:#2076
**Epic:** gh:#1708 (Wave 4: Synlynk Model Hub & Provider Aggregator), gh:#1711 (Universal Provider Aggregators)
**Roadmap:** docs/strategy/2026-10-10-dev-preview-revised-roadmap.md, Week 2 "provider/BYOK plumbing" item

## Problem

`synlynk`'s `harness_adapters` registry (`synlynk/harness_adapters/registry.py`) only supports CLI-wrapped harnesses (claude, codex, agy, grok, local, muse — 6 registered as of 2026-10-11). `get_adapter()` is a plain dict lookup; `dispatch.py:3717-3722` already hard-errors (`ValueError: Harness '<name>' has no registered dispatch adapter`) on any unregistered name.

**Correction vs. the original issue text:** #2076 was filed 2026-10-06 against a `LegacyAdapter` silent-catch-all that no longer exists in the codebase as of this spec — `grep -rn LegacyAdapter synlynk/` finds nothing, and the current `get_adapter()`/`dispatch.py` KeyError-to-ValueError path already hard-fails on unknown harness names. This makes the issue's step 3 ("revisit whether LegacyAdapter's catch-all can be replaced with a hard error") **already resolved independently** — note this in the implementation PR and in a closing comment on whichever issue introduced the hard-error path, so it isn't re-litigated. The real, still-open gap is step 1: there is no adapter at all for a non-CLI, HTTP-API-reachable backend (OpenRouter, a self-hosted LiteLLM proxy, direct OpenAI-compatible endpoints) — dispatching to one today just hard-errors instead of working.

OpenRouter, a self-hosted LiteLLM proxy, and any direct OpenAI-compatible endpoint are a distinct class: reachable over an OpenAI-compatible chat-completions HTTP API, selected by `base_url` + `api_key` + `model`, with no vendor CLI involved.

## Approach

**Correction (2026-10-11, post-commit `f4d20c7a`):** Two research passes established that the `HarnessAdapter` Protocol (`synlynk/harness_adapters/base.py`) is CLI-subprocess-shaped only (`build_cmd`/`parse_output`/`translate_permissions`/`classify_failure`/`resolve_model` — no HTTP-invocation method), and that the *live* `dispatch_agent()` path in `synlynk/dispatch.py` never calls `registry.py`'s adapters or `dispatch_pipeline.py`'s `spawn()` at all — it reads `HARNESS_CAPABILITY_BASELINES[agent]["cli"]` directly (`dispatch.py:3878-3879`) and `subprocess.Popen`s it (`dispatch.py:4394-4400`). Registering a `GenericAPIAdapter` only into `registry.py` (the original step 6 below) would be Protocol-conformant but **would not make it dispatchable** — `baselines_map` is a static, non-mergeable module dict with no config-driven extension mechanism anywhere in the codebase.

Separately, this project already has dormant, closer-fit prior art for exactly this shape of problem: `synlynk/gateway.py` + `synlynk/registry.py`'s `DEFAULT_REGISTRY["gateways"]["openrouter"]`. `gateway.py`'s `dispatch_openrouter()` already does the OpenAI-compatible `/chat/completions` POST via stdlib `urllib.request`, with `base_url`/`api_key_env`/`models`-fallback-chain read from `.synlynk/registry.json`, and `cmd_gateway_dispatch()` already prints the raw JSON response (including the standard `usage: {prompt_tokens, completion_tokens, total_tokens}` OpenAI shape) to stdout. It is marked `dispatch_active: False` ("ships in v0.26.0") and is entirely unwired from `dispatch.py`/`HARNESS_CAPABILITY_BASELINES` today (`grep "gateway" synlynk/dispatch.py` → zero hits).

Revised approach: bridge through this existing gateway subsystem instead of inventing a second, parallel `generic_endpoints` config concept and a second urllib call site.

1. **Config resolution — reuse, don't duplicate.** Drop the previously-proposed `generic_endpoints` key in `.synlynk/config.json`. Use `.synlynk/registry.json`'s existing `gateways` map (already has `base_url`/`api_key_env`/`models`/`enabled`/`dispatch_active` per entry) as the single source of config for this feature. No new config schema.
2. **Make the gateway actually dispatchable.** Flip `dispatch_active` semantics from a hardcoded guard (`gateway.py:102-103` raises `RuntimeError` when `False`) to something the implementer can set `True` for a configured, probed-reachable gateway (`synlynk gateway probe` already verifies reachability before this). `dispatch_openrouter()`/`cmd_gateway_dispatch()` need no other change — they already build the right request and print a parseable JSON response.
3. **Wire a new harness baseline entry.** Add an entry to `HARNESS_CAPABILITY_BASELINES` (`synlynk/_constants.py`) — name it after the gateway, e.g. `"openrouter"` — whose `"cli"` is the `synlynk` binary itself, with `dispatch_flags`/`non_interactive_flags` constructed so the real spawn command becomes `synlynk gateway dispatch <model> <prompt>` (mirror exactly how the `local` harness's baseline entry is shaped — it's the closest existing precedent for a non-vendor-CLI backend, including its `network_deps.required_endpoints` key, which here should hold the gateway's `base_url`). This is what makes `--force-harness openrouter` actually spawn a real subprocess through the unchanged `dispatch.py:3878-4400` legacy path — no changes to that path itself are needed, only a new baseline entry.
4. **Cost-entry write-through — new structured parser.** `synlynk/costs.py`'s `extract_tokens` (lines 166-399) dispatches to a per-harness structured JSON parser for 5 of 6 harnesses; `local` is the only one falling through to the generic regex chain. Add a 6th structured parser for this harness's stdout shape: `cmd_gateway_dispatch` prints `json.dumps(response, indent=2)` where `response` is the raw OpenRouter/OpenAI-compatible object — parse the top-level `usage.prompt_tokens`/`usage.completion_tokens` fields directly (standard, not nested like Codex's `reasoning_output_tokens` fold-in).
5. **Receipt marker / terminal-status parity.** Confirm (read `_reconcile_terminal_jobs_json`/`_verify_daemon_terminal_status` before writing the plan task) whether terminal-status reconciliation keys off `extract_tokens` succeeding or off a separate stdout marker; if the latter, `cmd_gateway_dispatch` needs one more line appended to its printed output matching that marker format, not a new mechanism.
6. **Optional: Protocol-conformant adapter class.** `synlynk/harness_adapters/generic_api.py`'s `GenericAPIAdapter` can still be written as a thin wrapper satisfying `HarnessAdapter`'s 5 methods (for `tests/test_adapter_conformance.py` parity and any future migration to the `dispatch_pipeline.py`/`spawn()` path) — but it is not what makes this dispatchable today; step 3's baseline entry is. Scope this as a smaller, separate task, not the critical path.

## Conformance testing

Per #2062's existing adapter-conformance-test suite (`tests/test_adapter_conformance.py`), add `GenericAPIAdapter` (the optional class from step 6) as a new parametrized case alongside the existing adapters, mocking the HTTP call (`unittest.mock.patch` on `urllib.request.urlopen`). Separately, and more importantly since it's what's actually load-bearing: add a unit test for the new `extract_tokens` parser (step 4) and an integration-style test (real `subprocess.Popen` of the new baseline's `cli`+flags, mocked HTTP response) proving `--force-harness openrouter` round-trips through the unchanged `dispatch.py` legacy path end-to-end.

## Out of scope (explicitly, per the issue)

- IDE-embedded assistants (Cursor, VS Code Copilot, Pi) — interactive/human-attended, not dispatch targets, not modeled as adapters here.
- Hardening the unregistered-harness error path — already a hard `ValueError` today (see Problem correction above), not a silent catch-all; no further work needed here. Note this as resolved when closing out #2076's original scope.
- Any UI/CLI surface for *configuring* `generic_endpoints` interactively (e.g. a `synlynk config add-endpoint` wizard) — out of scope; `.synlynk/config.json` is hand-edited for now, matching how the project already treats most of this file.
- Streaming responses — single-shot request/response only, matching how the existing CLI adapters already capture one full completion per dispatch rather than streaming.

## Testing

1. Unit: mocked-HTTP conformance test (see above) added to the existing adapter-conformance suite.
2. Integration (manual, not automated in CI): one real dispatch against a real OpenRouter key set via `OPENROUTER_API_KEY`, run locally by whoever implements this, confirming an actual round-trip — not part of the automated test suite since it requires a live credential.
