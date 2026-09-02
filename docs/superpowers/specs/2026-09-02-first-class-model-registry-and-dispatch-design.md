# Design Spec: First-Class Model Registry, Environment Discovery, Entitlements, and Complexity-Aware Dispatch

**Date:** 2026-09-02  
**Status:** Approved  
**Decision Ref:** [`project-docs/decisions/2026-09-02-making-model-and-model-family-first-clas.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-09-02-making-model-and-model-family-first-clas.md)  
**Authors:** [@nikhilsoman], [@agy], [@codex], [@claude]  

---

## 1. Executive Summary & Objective

Elevate **`ModelFamily`** and **`Model`** to first-class architectural primitives within Synlynk across Core and Local harnesses. 

This establishes a strict three-dimensional resource separation:
1. **Workspace Agent:** Identity, tenant governance, charter, and workflow stage ownership.
2. **Harness (Core / Local):** Execution runtime, OS sandbox, tool adapter, and permission boundary.
3. **Model / ModelFamily:** Cognitive reasoning geometry, context ceilings, tokenization semantics, entitlement tier, and differential rate cards.

---

## 2. Core Architectural Components

### A. Canonical Model & ModelFamily Registry Schema

The model catalog is managed declaratively under `.synlynk/models/` and stored in SQLite `state.db`:

- **`ModelFamily`:**
  - `family_id` (e.g., `claude-3-5`, `gemini-1-5`, `gemini-2-0`, `gpt-4o`, `gemma-2`, `deepseek-r1`, `qwen2-5`)
  - `provider` (`anthropic`, `google`, `openai`, `xai`, `meta`, `alibaba`, `local`)
  - `context_geometry`: Max input tokens, max output tokens, reasoning token support.
  - `native_features`: Native tool calling, JSON schema output, vision/multimodal, prompt caching.
  - `prompt_adapter`: Template markers, role formatting, and receipt verification protocols.

- **`ModelSpec`:**
  - `model_id` (e.g., `claude-3-5-sonnet-20241022`, `gemini-1.5-flash`, `gpt-4o-2024-11-20`, `gemma-2-9b-it-q4`)
  - `family_id`
  - `harness_binding` (`claude`, `agy`, `codex`, `grok`, `local`)
  - `locality` (`remote_api` vs `on_device_local`)
  - `quantization` (e.g., `None`, `4bit`, `Q4_K_M`, `FP16`)
  - `rates`: `input_per_1k`, `output_per_1k`, `cache_read_per_1k`, `reasoning_per_1k`
  - `entitlement_tier`:
    - `included_in_base`: Covered by flat monthly subscription.
    - `subscription_capped`: Capped requests per window; fallback to extra usage.
    - `metered_extra_usage_only`: Frontier models billed at differential API list rates.
    - `zero_cost_local`: On-device inference ($0.00 marginal software spend).

### B. Dual Discovery Engine

1. **Local Environment Probing (`init`, `doctor`, `onboard`, `install`):**
   - Active CLI subcommands: `claude models`, `codex --list-models`, `agy --help`, `grok models`.
   - Local engine discovery: HTTP queries against Ollama (`/api/tags`), vLLM, and oMLX listing installed model weights.
2. **Autonomous Public Release Radar (PM Durable Sweep):**
   - Periodic background sweep across vendor changelogs, model hubs, and release APIs.
   - Automatically registers new model families as candidate entities ready for requisition.

### C. Task Complexity-Aware Model Requisition Policy

Dispatch matches task complexity tiers to required model capability classes:

- **Tier 1 (Frontier Reasoning):** `synlynk decide` panels, architectural design, root-cause forensics $\rightarrow$ Requisitions Claude 3.5 Sonnet/Opus, Gemini 1.5/2.0 Pro, OpenAI o3/o1.
- **Tier 2 (Code & Tool Specialized):** Feature authorship, bug fixes, TDD refactoring, PR reviews $\rightarrow$ Requisitions Codex (GPT-4o), Claude Sonnet, Gemini Pro, Grok.
- **Tier 3 (Fast / High-Volume / Zero-Cost):** AST parsing, repo-wide search, log parsing, documentation sweeps $\rightarrow$ Requisitions Gemini Flash/Flash-Lite, Local Gemma/Qwen.

### D. Dual-State Telemetry Attribution

Every dispatch event and cost entry captures:
- `requested_model`: The model requested by the task spec or router.
- `resolved_model`: The actual model version confirmed by runtime receipt.
- `cost_source`: `amortized_subscription`, `subscription_extra_usage_metered`, or `zero_cost_local`.

---

## 3. Security & Permission Decoupling

- Model capability acts strictly as an **eligibility constraint** (e.g. code tasks require tool-calling support; regulated tasks require `locality: on_device_local`).
- Model identity **never grants authorization or permissions**. Filesystem, shell, merge, and credential permissions remain anchored to the Workspace Agent and enforced by the Harness sandbox.
