# Local Harness Operationalization Design

**Date:** 2026-10-16
**Status:** Approved by Nikhil on 2026-10-16
**Epic:** gh:#2342
**Design ticket:** gh:#2343
**Goal:** `goal-8d34c416`
**Delivery tickets:** gh:#2344, gh:#2345, gh:#2346, gh:#2347, gh:#2348, gh:#2349

## Purpose

Make the local Ornith + Aider + oMLX path a safe, measurable dispatch backend for a deliberately narrow class of work. The first release selects a model already served by oMLX; it does not manage model loading or server lifecycle.

This design supersedes conclusions in the initial #2343 brainstorm draft where they conflict with verified repository behavior.

## Verified baseline

The local harness is partially present, not operationally complete.

- `omlx` and `aider` are installed on the evaluated host. The oMLX endpoint at `http://127.0.0.1:8000` is reachable but returns HTTP 401 without the configured `OPENAI_API_KEY`.
- `LocalAdapter` is registered, but production dispatch still builds the local invocation through legacy dispatcher logic; it does not consistently use the adapter command/output contract.
- `.agents/local.json` already contains Ornith, Qwen, and Ternary Bonsai profiles; `prism_ml` is absent on the evaluated host, so Bonsai falls back to Ornith. Gemma 4 is not presently a local profile.
- `synlynk local doctor --init` exists. Hardware-tier tests exist. Dispatch already enforces local `max_concurrent: 1`. This work preserves those mechanisms and verifies them end-to-end rather than reimplementing them.
- Current automated coverage passed: 260 tests passed and 5 were expected failures across the local adapter, registry, conformance, and dispatch selection suites.

## Product decisions

### 1. Model selection and lifecycle

Version 1 supports per-dispatch selection only for a model ID currently returned by oMLX `GET /v1/models`.

```text
synlynk dispatch local --model <omlx-model-id> ...
```

The command must reject an ID not in the live inventory before invoking Aider. Its error names the requested ID, shows the discovered IDs, and explains that operators must start oMLX with the model first. It must not download a model, load or unload a model, restart oMLX, or silently fall back to another model.

`max_concurrent: 1` remains the v1 operational limit. The future ability to load/reload models and manage a resident-model pool is explicitly deferred.

### 2. Three authoritative layers

No single source is sufficient. Resolution uses three distinct layers:

| Layer | Authority | Purpose |
| --- | --- | --- |
| Live inventory | oMLX `/v1/models` | What can execute now; required for `--model` validation. |
| Local policy | `.agents/local.json` | Approved profiles, edit format, loader requirements, hardware and concurrency policy. |
| Global catalog | Synlynk model catalog | Stable model metadata, routing defaults, and cross-harness reporting. |

An executable selection is the intersection of live inventory and an approved local policy profile. The catalog enriches the result but never claims that a model is loaded. Drift must fail visibly in doctor/dispatch diagnostics; it must not be silently reconciled by choosing a different model.

### 3. Authentication

Retain the existing OpenAI-compatible `OPENAI_API_KEY` flow for both health checks and Aider. A 401 is classified separately from endpoint-unreachable, timeout, and malformed-response conditions, with a diagnostic that identifies the required configuration without exposing the key. No Synlynk-specific header/token protocol is added in v1: `local_http_auth.py` serves a different daemon/Vizor concern, not oMLX authentication.

### 4. Candidate models

The qualification shortlist is intentionally small:

1. **Qwen3-Coder MLX quantization** — primary coding candidate.
2. **Gemma 4 instruction-tuned MLX quantization** — challenger, only if the installed oMLX version passes compatibility checks.
3. **Ornith** — retained only as a baseline if it passes the same stack gate.
4. **PrismML Ternary Bonsai** — blocked for v1; do not make loader work a prerequisite because oMLX/Prism compatibility is not yet dependable.

The choice is evidence-driven, not a benchmark claim. Aider supports OpenAI-compatible endpoints; oMLX exposes that shape. Qwen3-Coder is the coding-focused candidate. Gemma 4 support is credible but version-sensitive. Bonsai remains a compatibility-risk candidate, not an initial production route.

### 5. Qualification is stack qualification

A model is not qualified merely because it answers a prompt. It must pass:

1. **oMLX/model:** exact ID discovery, authentication, load stability, memory fit, latency, and context behavior.
2. **Aider:** API-key forwarding, model ID forwarding, `diff` and `whole` modes, repository map, prompt files, worktree behavior, scoped diffs, approved test-command behavior, and no-op/error reporting.
3. **Synlynk end-to-end:** `--model` resolution through adapter to Aider and oMLX, then a verified diff/test result and a receipt containing model, mode, timings, and classified failure data.

Negative tests are mandatory: invalid key, unavailable model, timeout, malformed output, and no-op response. Qualification runs in a disposable isolated worktree/environment with no GitHub credentials or secrets and network access limited to the local oMLX endpoint. Until that isolation and the adapter permission contract are implemented, evaluation is restricted to read/summarize work.

## Pilot policy

Eligible initial work is focused test-command and log summaries, test/log diagnosis, bounded codepath/change summaries, and disposable-worktree documentation or mechanical-edit exercises. It excludes production edits, refactors, architectural/spec work, dependency changes, GitHub actions, secrets, merge/review, and broad test execution.

The benchmark contains 24 representative tasks: eight test/log summaries, eight diagnoses, four explanations, and four tightly bounded mechanical or documentation edits. Record correctness, completion, test result, scope adherence, retry count, wall time, memory, and unsafe/no-op events.

| Stage | Entry criteria | Limit |
| --- | --- | --- |
| Qualification | authenticated E2E stack pass; >=85% benchmark correctness; zero unsafe/no-op/out-of-scope edits; memory fits; Ornith baseline assessed | no production routing |
| Pilot | qualification passed | 20% of eligible work |
| Expansion | 30 eligible real or production-equivalent jobs, >=90% accepted, no serious incident | 35% |
| Steady pilot | 75 eligible jobs, >=90% accepted, stable latency/memory, rollback drill passed | 50% |

Any serious safety regression, unexpected edit scope, failed isolation, or material latency/memory regression immediately returns routing to the frontier harness pending investigation.

## Delivery sequence

1. **#2344 — host truth and authenticated E2E:** validate the actual oMLX endpoint, environment forwarding, live inventory, and useful diagnostics.
2. **#2348 — shortlist qualification:** establish the isolated benchmark and compare Qwen3-Coder, Gemma 4 where compatible, and Ornith baseline.
3. **#2345 — adapter parity:** make production local dispatch invoke the HarnessAdapter command/result contract and emit classified failures.
4. **#2346 — unified resolution and telemetry:** implement the three-layer resolver, drift diagnostics, and per-model receipt fields.
5. **#2347 — existing-model selection:** add `--model` validation and pass the selected live ID into Aider; retain max concurrency one.
6. **#2349 — graduated routing:** enforce the isolated-work policy and measured 20%/35%/50% gates.

Each implementation ticket requires an approved plan committed after this design is accepted. No lifecycle automation, Bonsai enablement, or broad local editing is included in the initial delivery.

## Acceptance criteria

- `synlynk local doctor` distinguishes unauthenticated, unreachable, timeout, malformed-inventory, and healthy states without leaking credentials.
- A local dispatch with a selected live, approved ID invokes the adapter path, forwards the exact model ID to Aider/oMLX, and produces a structured receipt.
- A non-live, unknown, or policy-disallowed ID fails before Aider runs and never silently falls back.
- Existing concurrency protection remains effective at one local dispatch.
- The isolated qualification suite passes for an approved model before any live pilot routing.
- Pilot receipts support a decision at each expansion gate and a rollback is demonstrably possible.

## Deferred

- oMLX model download/load/unload/restart and resident-pool management.
- PrismML Ternary Bonsai support.
- Multi-host federation, GPU/CUDA/Metal performance tuning, mTLS, and broad autonomous code-edit routing.
