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

Add `synlynk/harness_adapters/generic_api.py` implementing `GenericAPIAdapter`, conforming to the same adapter interface the 6 registered CLI adapters already implement (same method signatures as `synlynk/harness_adapters/claude.py` or `codex.py` — read one of those first as the reference implementation before writing this one).

1. **Config resolution.** A harness name dispatches to `GenericAPIAdapter` when it matches an entry under a new `generic_endpoints` map in `.synlynk/config.json`, e.g.:
   ```json
   "generic_endpoints": {
     "openrouter": {"base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY", "model": "anthropic/claude-sonnet-5"},
     "local-litellm": {"base_url": "http://localhost:4000/v1", "api_key_env": "LITELLM_API_KEY", "model": "gpt-4o-mini"}
   }
   ```
   `api_key_env` names an environment variable to read the key from — the key itself is never written into `config.json` (matches this project's existing secrets-not-in-dotfiles-or-config discipline).
2. **Invocation.** Build and POST an OpenAI-compatible `/chat/completions` request: `{"model": ..., "messages": [{"role": "user", "content": <task text>}]}`. Use Python's stdlib `urllib.request` (no new dependency — this project has none beyond stdlib per `CLAUDE.md`'s "No dependencies beyond Python 3 stdlib").
3. **Receipt marker.** Emit the same structured completion marker the CLI adapters emit on success (find the exact marker format in `synlynk/harness_adapters/claude.py` and reuse it verbatim) so downstream job-status reconciliation (`_reconcile_terminal_jobs_json`, `_verify_daemon_terminal_status`) treats a `GenericAPIAdapter` job identically to a CLI-adapter job.
4. **Cost-entry write-through.** The HTTP response's `usage.prompt_tokens` / `usage.completion_tokens` (standard OpenAI-compatible response fields) feed into the same `cost_entries` write path the CLI adapters use — locate that call in the CLI adapter you used as reference and mirror it, substituting the HTTP response's usage fields for the CLI-parsed token counts.
5. **Timeout handling.** Wrap the HTTP call in the same timeout/retry wrapper pattern already used elsewhere for network calls in this codebase (search for an existing `urllib`/`requests`-style timeout wrapper before inventing a new one — if none exists, use `urllib.request.urlopen(req, timeout=120)` and catch `URLError`/`socket.timeout`, mapping to the adapter's standard failure-status marker).
6. **Registry wiring.** `synlynk/harness_adapters/registry.py` registers each adapter at module load via `register_adapter(name, adapter)` into a plain dict (`_ADAPTERS`); `get_adapter(name)` does a direct lookup and raises `KeyError` on a miss, which `dispatch.py:3717-3722` converts to a `ValueError`. For each key present in `.synlynk/config.json`'s `generic_endpoints` map, register a `GenericAPIAdapter` instance (constructed with that key's `base_url`/`api_key_env`/`model`) under that key's name, the same way the 6 CLI adapters register themselves — e.g. `register_adapter("openrouter", GenericAPIAdapter(base_url=..., api_key_env=..., model=...))`. No fallback logic needed: once registered, `"openrouter"` dispatches exactly like `"codex"` or `"grok"` through the existing `get_adapter()` path.

## Conformance testing

Per #2062's existing adapter-conformance-test suite (`tests/test_adapter_conformance.py`), add `GenericAPIAdapter` as a new parametrized case alongside the 6 CLI adapters, mocking the HTTP call (no real network access in tests — use `unittest.mock.patch` on the `urllib.request.urlopen` call or equivalent). The conformance suite already defines what "passing" means for an adapter (receipt marker present, cost entry written, timeout handled) — reuse those exact assertions, don't write new ones.

## Out of scope (explicitly, per the issue)

- IDE-embedded assistants (Cursor, VS Code Copilot, Pi) — interactive/human-attended, not dispatch targets, not modeled as adapters here.
- Hardening the unregistered-harness error path — already a hard `ValueError` today (see Problem correction above), not a silent catch-all; no further work needed here. Note this as resolved when closing out #2076's original scope.
- Any UI/CLI surface for *configuring* `generic_endpoints` interactively (e.g. a `synlynk config add-endpoint` wizard) — out of scope; `.synlynk/config.json` is hand-edited for now, matching how the project already treats most of this file.
- Streaming responses — single-shot request/response only, matching how the existing CLI adapters already capture one full completion per dispatch rather than streaming.

## Testing

1. Unit: mocked-HTTP conformance test (see above) added to the existing adapter-conformance suite.
2. Integration (manual, not automated in CI): one real dispatch against a real OpenRouter key set via `OPENROUTER_API_KEY`, run locally by whoever implements this, confirming an actual round-trip — not part of the automated test suite since it requires a live credential.
