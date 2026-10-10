# v0.25.0 — Sovereign Silicon: Local oMLX Fleet Design

**Date:** 2026-10-02  
**Author:** Agy (Gemini)  
**Status:** Approved — ready for implementation plan  
**Issues:** [#1710](https://github.com/nikhilsoman/synlynk/issues/1710) (Local oMLX Harness), [#1708](https://github.com/nikhilsoman/synlynk/issues/1708) (Wave 4 Epic)  
**Related specs:**
- `docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md` (prior local harness work — Addenda 1–4 inclusive)
- `docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md`

---

## Context & Prior Work

The `local` harness dispatch path was built and merged across PRs #204, #205, #207 (Task Groups 1–3) and subsequently patched via Addenda 1–4 for auth (OPENAI_API_KEY passthrough), litellm provider prefix (`openai/` prefix), and edit-format correction (`diff` for Ornith). As of main (`8b5f0b0c`), the following is already shipped and should not be rewritten:

| Component | File | Status |
|:---|:---|:---|
| Config loader + flag builder | `synlynk/local_agent.py` | ✅ shipped |
| `synlynk local doctor` | `synlynk/local_agent.py:cmd_local_doctor()` | ✅ shipped |
| Starter capability envelope seeding | `synlynk/local_agent_seed.py` | ✅ shipped |
| Concurrency guard (`max_concurrent: 1`) | `synlynk/local_agent_concurrency.py` | ✅ shipped |
| litellm `openai/` prefix fix | `local_agent.py:_local_dispatch_model_flags()` | ✅ shipped |
| `diff` edit format for Ornith | `.agents/local.json` | ✅ shipped |
| OPENAI_API_KEY passthrough | `_constants.py:HARNESS_CAPABILITY_BASELINES["local"]["env_passthrough"]` | ✅ shipped |
| `$0.00` cost accounting | `synlynk/costs.py:_model_rate_for_version()` | ✅ shipped |

**What has NOT been validated:** A real end-to-end `synlynk dispatch local` call reaching Ornith and producing usable file edits. The last live test was pre-diff-fix (Addendum 4 fixed this but was never re-tested live). v0.25.0 must close this gap first.

---

## Goals

1. **Validate** end-to-end local dispatch on real hardware (Ornith-1.0-9B-4bit, M3/24GB)
2. **Expand** the roster to all three downloaded models with correct per-model config
3. **Harden** `synlynk local doctor` with hardware tier detection and model recommendations
4. **Wire** tier-0 zero-trust auto-routing into `dispatch_agent()` via `synlynk dispatch auto`
5. **Publish** the Orb Stack as a Docker image (`ghcr.io/nikhilsoman/synlynk-sovereign:v0.25.0`)
6. **Preview** the OpenRouter gateway config schema and `synlynk gateway probe` stub
7. **Defer** System 1 decision model integration (Ternary-Bonsai-as-router, Jev local) to v0.27.0

---

## Architecture

### Two-Layer Stack (unchanged from prior spec)

```
┌─────────────────────────────────────────────────┐
│  synlynk dispatch layer                         │
│  _resolve_dispatch_agent() → tier-0 routing     │
│  dispatch_agent() → Aider subprocess            │
└────────────────┬────────────────────────────────┘
                 │  aider --openai-api-base ... --model openai/<id>
┌────────────────▼────────────────────────────────┐
│  oMLX (local inference server, port 8000)       │
│  OpenAI-compatible /v1/chat/completions         │
│  /v1/models (health + roster check)             │
└─────────────────────────────────────────────────┘
```

Aider is the agentic editor (reads/plans/writes files, git-aware). oMLX is inference-only. synlynk owns orchestration. No new spawn path in `dispatch_agent()` — the `local` agent uses the same subprocess lifecycle as `agy`, `codex`, `grok`.

---

## Section 1: Model Roster

### Hardware Target

**MacBook Air M3, 24GB unified RAM, 512GB SSD** → `32gb-pro` hardware tier.

### Three Peer Dispatch Models

All three are full autoregressive LLMs. None is a System 1 classifier.

| Model ID | Architecture | On-disk size | Edit format | Role |
|:---|:---|:---|:---|:---|
| `Ornith-1.0-9B-4bit` | 9B, standard 4-bit quant | ~5 GB | `diff` | Fast, low-footprint coder; default at light tiers |
| `Qwen3.6-27B-4bit` | 27B, standard 4-bit quant | ~18 GB | `whole` | Deep reasoning, architecture tasks |
| `Ternary-Bonsai-2-27B-mlx-2bit` | 27B ternary quant (Qwen3.8-27B base), Prism ML | ~5.9 GB | `diff` | Best quality-per-GB; requires `prism-ml` loader |

### Updated `.agents/local.json`

```json
{
  "name": "local",
  "endpoint": "http://127.0.0.1:8000",
  "models": [
    {
      "id": "Ornith-1.0-9B-4bit",
      "pinned": false,
      "edit_format": "diff",
      "tier": ["8gb-light", "16gb-default"]
    },
    {
      "id": "Qwen3.6-27B-4bit",
      "pinned": false,
      "edit_format": "whole",
      "tier": ["64gb-fleet"]
    },
    {
      "id": "Ternary-Bonsai-2-27B-mlx-2bit",
      "pinned": false,
      "edit_format": "diff",
      "loader": "prism-ml",
      "tier": ["32gb-pro", "64gb-fleet"]
    }
  ],
  "hardware_tier": "32gb-pro",
  "pinned_model": "Ternary-Bonsai-2-27B-mlx-2bit",
  "max_concurrent": 1
}
```

The `pinned` field on individual models is deprecated in favour of the top-level `pinned_model` key, which `synlynk local doctor --init` writes automatically after detecting hardware tier. Existing code that reads `model.get("pinned")` continues to work via backward-compatible fallback.

### Ternary-Bonsai Loader Requirement

Ternary-Bonsai-2-27B-mlx-2bit uses blockwise Hadamard rotation and ternary weights ({-1, 0, +1}) that cannot be loaded by standard MLX or oMLX loaders. The `prism-ml` Python package provides the custom loader.

**synlynk's handling:**
- `synlynk local doctor` detects models with `"loader": "prism-ml"` and checks `import prism_ml` (stdlib `importlib.util.find_spec`).
- If `prism-ml` is missing: prints `⚠ Ternary-Bonsai-2-27B-mlx-2bit: prism-ml loader required — install with: pip install prism-ml`
- Dispatch via Aider is permitted only when the loader check passes; otherwise the model is excluded from the pinned-model selection and `_local_dispatch_model_flags()` skips it with a warning.
- **No prism-ml integration code is vendored into synlynk** — synlynk checks presence and defers loading to oMLX's own plugin mechanism. This is a preflight check, not an import.

---

## Section 2: Hardware Tier Prober

### New function: `_detect_hardware_tier() → str`

Location: `synlynk/local_agent.py`

Reads available RAM using platform-native calls (no new dependencies):
- macOS: `sysctl -n hw.memsize` via `subprocess.check_output` → bytes → GB
- Linux: `/proc/meminfo` → `MemTotal:` line → kB → GB

Tier mapping:

| Tier name | RAM range | Auto-pinned model |
|:---|:---|:---|
| `8gb-light` | < 12 GB | `Ornith-1.0-9B-4bit` |
| `16gb-default` | 12–20 GB | `Ornith-1.0-9B-4bit` |
| `32gb-pro` | 20–48 GB | `Ternary-Bonsai-2-27B-mlx-2bit` (prism-ml present) or `Ornith-1.0-9B-4bit` (prism-ml absent) |
| `64gb-fleet` | > 48 GB | `Qwen3.6-27B-4bit`, `max_concurrent: 2` |

### `synlynk local doctor` enhancements

- `--init` flag: detects hardware tier, writes `hardware_tier` and `pinned_model` back to `.agents/local.json`, then runs the full health check.
- Existing no-flag behaviour: unchanged (endpoint reachability + roster check).
- New output block printed after the endpoint check:

```
  ✓ oMLX reachable at http://127.0.0.1:8000
  ✓ hardware tier: 32gb-pro (24 GB detected)
  ✓ pinned model: Ternary-Bonsai-2-27B-mlx-2bit
  ✓ Ornith-1.0-9B-4bit        [in oMLX roster]
  ✓ Qwen3.6-27B-4bit          [in oMLX roster]
  ✓ Ternary-Bonsai-2-27B-mlx-2bit [in oMLX roster] [prism-ml: ✓]
  ✓ aider installed
  ✓ starter capability envelope seeded
```

---

## Section 3: Live End-to-End Validation

Before any new code ships, the existing post-diff-fix state must be validated on the local machine:

```bash
synlynk dispatch local --task "Add a docstring to synlynk/local_agent.py:_pinned_model()" \
  --story story-v025-validate-01
```

Expected: job completes with `status=done`, `files_touched >= 1`, Aider log shows a real diff applied (not near-empty rewrites). Captured log is reviewed directly — not inferred from job status.

This validation step is **Task Group 1** of the implementation plan and is a **hard gate** — subsequent task groups may only proceed after it passes. If it fails, root cause is diagnosed and fixed before any other v0.25.0 work proceeds.

---

## Section 4: Tier-0 Zero-Trust Auto-Routing

### Design

New function `_resolve_dispatch_agent(requested_agent, task_type, db) → str` in `synlynk/dispatch.py`:

```
if requested_agent is not None and requested_agent != "auto":
    return requested_agent   # explicit always wins

# auto-routing logic:
local_health = _preflight_local(silent=True)   # existing function, new silent= flag
if not local_health.ok:
    return config.local_fallback               # "agy" by default

cap = _get_capability_score("local", task_type, db)
threshold = config.local_auto_threshold        # default: 0.5

if cap >= threshold:
    return "local"
else:
    return config.local_fallback
```

**New config keys** in `.synlynk/config.json` (written by `synlynk init` if absent, never overwriting existing):
```json
{
  "local_auto_threshold": 0.5,
  "local_fallback": "agy"
}
```

### CLI surface

```bash
synlynk dispatch auto --task "..."
# equivalent to synlynk dispatch <resolved-agent> --task "..."
# prints: "Routing to: local (tier-0, capability score: 0.72)"
# or:      "Routing to: agy (local unhealthy)"
# or:      "Routing to: agy (capability score 0.3 < threshold 0.5)"
```

`synlynk dispatch` without `--agent` continues to require explicit agent specification; `auto` is only activated by passing `auto` as the agent name. No silent behaviour changes for existing explicit dispatches.

### Eligibility gate

`_resolve_dispatch_agent` only routes to `local` if the task_type is in the local capability envelope (currently: `docs`, `testing`, `execute` stage tasks). Architecture/platform tasks continue to require explicit agent specification.

---

## Section 5: Orb Stack Docker Image

### Purpose

A single OCI image containing synlynk + Aider pre-installed, ready to attach to a running oMLX instance (which serves the models from the host). The image does **not** bundle models — models stay on the host machine and oMLX is accessed via `host.docker.internal` (Docker/Orbstack bridge).

### Dockerfile: `docker/Dockerfile.sovereign`

Multi-stage build:
```
Stage 1 (builder): python:3.12-slim
  - pip install synlynk aider-chat prism-ml
  - copy docker/entrypoint.sh

Stage 2 (runtime): python:3.12-slim
  - COPY --from=builder installed packages
  - ENV OMLX_ENDPOINT=http://host.docker.internal:8000
  - ENTRYPOINT ["/entrypoint.sh"]
```

### Entrypoint: `docker/entrypoint.sh`

```bash
#!/bin/bash
set -e
# 1. Write .agents/local.json pointing at $OMLX_ENDPOINT
# 2. synlynk local doctor   (health check, exits 1 if unhealthy)
# 3. If $TASK is set: synlynk dispatch local --task "$TASK"
# 4. Otherwise: exec bash (interactive)
```

### Image registry

`ghcr.io/nikhilsoman/synlynk-sovereign:v0.25.0`

Built and pushed via GitHub Actions workflow `docker/sovereign-build.yml` on tag push `v0.25.*`.

### CI smoke test

`docker build -f docker/Dockerfile.sovereign -t synlynk-sovereign-test .`
`docker run --rm synlynk-sovereign-test synlynk local doctor --help`

Runs on `ubuntu-latest` in CI. Does not require a real oMLX instance.

---

## Section 6: OpenRouter Config Preview

### Purpose

Lay the schema groundwork for v0.26.0 Universal Gateway without adding any dispatch code. Allows users to configure their OpenRouter key now and validate connectivity before v0.26.0 ships.

### Registry schema addition

`.synlynk/registry.json` gains a top-level `"gateways"` key (alongside the existing `"products"` key):

```json
{
  "gateways": {
    "openrouter": {
      "enabled": false,
      "base_url": "https://openrouter.ai/api/v1",
      "api_key_env": "OPENROUTER_API_KEY",
      "models": [],
      "note": "Dispatch integration ships in v0.26.0. Use synlynk gateway probe to test connectivity."
    }
  }
}
```

`synlynk init` and `synlynk upgrade` write this schema if the `"gateways"` key is absent; they do not overwrite existing values.

### New command: `synlynk gateway probe [--gateway openrouter]`

Location: `synlynk/cli.py` + `synlynk/gateway.py` (new module, ~60 lines)

Behaviour:
1. Reads `.synlynk/registry.json`
2. For each enabled gateway (or the specified `--gateway`):
   - Reads `api_key_env`, checks `os.environ.get(api_key_env)`
   - GETs `base_url/models` with `Authorization: Bearer <key>` (urllib, no new deps)
   - Prints model count + first 5 model IDs
3. Exits 0 if all probed gateways are reachable, 1 otherwise

Example output:
```
synlynk gateway probe --gateway openrouter
  ✓ openrouter reachable (312 models available)
    top models: openai/gpt-4o, anthropic/claude-sonnet-4-5, ...
  ⚠ dispatch integration not yet active (ships in v0.26.0)
```

---

## Section 7: Testing Strategy

| Test file | What it covers | CI tier |
|:---|:---|:---|
| `tests/test_local_agent.py` (extend) | `_detect_hardware_tier()` — mocked `sysctl`/`meminfo`; prism-ml loader check; `--init` flag; new roster schema backward compat | standard (mocked) |
| `tests/test_dispatch_auto_routing.py` (new) | `_resolve_dispatch_agent()` — local healthy/unhealthy, cap score above/below threshold, explicit agent bypass | standard (mocked) |
| `tests/test_gateway.py` (new) | `cmd_gateway_probe()` — mocked HTTP, missing key, disabled gateway, schema validation | standard (mocked) |
| `tests/test_local_agent.py` (extend) | Ternary-Bonsai loader skip when prism-ml absent; dispatch flag exclusion | standard (mocked) |
| `@pytest.mark.local_hardware` | Live Ornith dispatch: real `omlx serve`, real Aider, real file edit; confirms `files_touched >= 1` | opt-in only (not in CI matrix) |
| Docker smoke test | `docker build` + `synlynk local doctor --help` inside container | `ubuntu-latest` CI |

All standard-tier tests must pass on Python 3.10, 3.11, 3.12 on both Linux and macOS runners with no real oMLX or Aider instance.

---

## Section 8: Non-Goals for v0.25.0

- **System 1 decision routing** (Ternary-Bonsai-as-classifier, Jev API, local LoRA fine-tune on repo corpus) → v0.27.0, separate spec
- **OpenRouter dispatch** (actual `synlynk dispatch openrouter --task "..."`) → v0.26.0
- **Meta Muse CLI adapter** (#1709) → v0.26.0/v0.27.0
- **Multi-Mac Thunderbolt fleet** (oMLX distributed serving) → future, not scoped
- **Q&A / read-only dispatch mode** for local agent (non-file-edit tasks) → future

---

## Section 9: Implementation Task Breakdown (for writing-plans)

| Task Group | Description | Files | Harness |
|:---|:---|:---|:---|
| TG-1 | Live end-to-end validation of existing dispatch (hard gate) | none (validation only) | agy (local) |
| TG-2 | Roster expansion: update `.agents/local.json` + prism-ml loader detection in doctor | `.agents/local.json`, `local_agent.py`, `tests/test_local_agent.py` | Codex |
| TG-3 | Hardware tier prober: `_detect_hardware_tier()` + doctor `--init` flag | `local_agent.py`, `tests/test_local_agent.py` | Codex |
| TG-4 | Tier-0 auto-routing: `_resolve_dispatch_agent()` + `synlynk dispatch auto` | `dispatch.py`, `cli.py`, `tests/test_dispatch_auto_routing.py` | Codex |
| TG-5 | OpenRouter config preview: registry schema + `synlynk gateway probe` | `gateway.py` (new), `cli.py`, `registry.py`, `tests/test_gateway.py` | Codex |
| TG-6 | Orb Stack Docker image: Dockerfile + entrypoint + CI smoke test | `docker/Dockerfile.sovereign`, `docker/entrypoint.sh`, `.github/workflows/sovereign-build.yml` | Grok (infra) |
| TG-7 | End-to-end integration, docs, version bump | `project-docs/`, `CHANGELOG.md`, `pyproject.toml` | Codex |

TG-1 is a live hardware validation step run by the operator (Nikhil), not a dispatch job. All other TGs dispatch via `synlynk dispatch`.

---

## Decision Log

| Decision | Rationale |
|:---|:---|
| Keep Aider-over-oMLX (no direct HTTP chat) | Aider provides file-edit semantics + git integration; plain `/v1/chat/completions` returns text only, cannot edit files |
| Three peer models (not one pinned) | Hardware auto-detection selects the best available model; `pinned_model` set by `doctor --init` |
| Ternary-Bonsai: dispatch peer, not System 1 router | It is a full autoregressive LLM (Qwen3.8-27B base) — System 1 exploration deferred to v0.27.0 |
| `prism-ml` loader: preflight check only, not vendored | Keeps synlynk's dependency surface clean; oMLX owns the actual model loading |
| `synlynk dispatch auto` as explicit opt-in | No silent behaviour changes; explicit agent always wins; zero risk of unexpected local routing |
| OpenRouter: schema preview only | Validates config groundwork for v0.26.0 without introducing premature dispatch complexity |
| Docker image does not bundle models | Models are large (5–18 GB each); host-served oMLX via `host.docker.internal` is the right boundary |
| TG-1 is a hard gate | The last real dispatch test pre-dates the diff-format fix; must confirm working before building on top |
