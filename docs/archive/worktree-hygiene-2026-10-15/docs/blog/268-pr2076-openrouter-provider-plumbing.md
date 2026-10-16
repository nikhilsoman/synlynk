# PR #2076 - OpenRouter Dispatch Makes Provider Plumbing Real

**Date:** 2026-10-12

The previous goal was to make provider and BYOK plumbing the first dependable layer of the revised developer-preview roadmap. Multi-interface clients and swarm/quota behavior should consume that provider surface, rather than each growing its own authentication path.

The R2 panel decision sharpened that sequencing: provider access comes first in pillar 1/7. This PR turns that decision into a runnable dispatch path by connecting the existing OpenRouter gateway to `dispatch_agent()`.

## What shipped

`.synlynk/registry.json` now enables the OpenRouter gateway with an environment-based `OPENROUTER_API_KEY` and a model fallback list. The new `openrouter` harness baseline makes the legacy dispatch subprocess invoke:

```text
synlynk gateway dispatch --model <model> --prompt <task>
```

The gateway continues to own the OpenAI-compatible HTTP request, timeout, and fallback behavior. No API key is stored in the registry, and this branch does not make a live provider call.

The cost ledger now recognizes the gateway's standard `usage.prompt_tokens` and `usage.completion_tokens` JSON shape. A small `GenericAPIAdapter` also satisfies the shared `HarnessAdapter` method contract so the provider can participate in adapter-conformance coverage while the live legacy path remains baseline-driven.

Verification was test-first: the OpenRouter cost test failed before the parser existed, then passed after implementation. The targeted suites pass, including the existing expected adapter xfails, and a mocked gateway response round-trips through `cmd_gateway_dispatch` and token extraction.

## What changed strategically

This is deliberately a bridge through the dormant `synlynk/gateway.py` subsystem rather than a second generic-endpoint configuration model. The result keeps base URL, API-key environment, model fallback, and HTTP timeout decisions in one place. It also leaves the already-hard error for unknown harness names untouched; the missing capability was a real API-backed harness, not a silent catch-all.

No brainstorm visual informed this implementation. The governing artifacts are the GenericAPIAdapter design spec and implementation plan for gh:#2076.

## The new goalpost

Synlynk now has a provider/BYOK dispatch seam that multi-interface clients can target. The next goal is to deepen that seam across additional OpenAI-compatible endpoints and then let swarm/quota logic consume the same provider accounting, without reversing the R2 provider-plumbing-first order.
