# OpenRouter Dispatch Plan

Issue: #1711 (W4-T1.3)

## Scope and behavior

- Add an explicit `synlynk gateway dispatch` entry point for OpenRouter chat completions.
- Require the OpenRouter gateway to be enabled and `dispatch_active`; probe-only registries continue to use `gateway probe` without dispatch side effects.
- Read credentials from the configured `api_key_env`, matching the existing probe contract.
- Try the requested model first, then distinct model IDs in the registry's `gateways.openrouter.models` order. Return the first successful response; report failure if all attempts fail.
- Use the OpenRouter `/chat/completions` endpoint with bounded connect/read behavior using the standard-library HTTP client timeout.

## Implementation

1. Add a small OpenRouter request helper and dispatch function to `synlynk/gateway.py`.
2. Add the CLI command and JSON message input in `synlynk/cli.py`.
3. Extend `tests/test_gateway.py` for success, fallback, and inactive dispatch behavior; inspect the Vizor scanner against unchanged registry keys.
4. Run the focused gateway tests and relevant CLI parsing checks.
