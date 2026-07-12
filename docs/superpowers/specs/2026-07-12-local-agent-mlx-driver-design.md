# Local Agent (5th Agent) — oMLX/MLX Driver — Design

**Date:** 2026-07-12
**Author:** Claude (PM role)
**Goal:** `goal-56d4beee` — "Local agent (5th agent) offloads granular implementation
work to zero-cost on-device MLX inference via oMLX" (deadline 2026-09-01)
**Status:** Approved for write-up, pending user review of this doc

## Problem

Every dispatched task today costs money — Claude, Codex, Agy, and Grok are all paid-API
agents. There's no way to offload implementation work onto local, zero-marginal-cost
compute, and no precedent in this codebase for an agent that isn't a CLI subprocess.

## Goal

Add a 5th agent, `local`, that runs inference on-device via [oMLX](https://github.com/jundot/omlx)
(verified via GitHub API: Apache-2.0, active, MLX/Apple-Silicon/OpenAI-API), swapping
between three coding models — Ornith-1.0-9B, Gemma Coder, Qwen Coder — behind one
OpenAI-compatible local endpoint. It slots into the existing capability→quota→cost
router with **no new gating mechanism**: conservative capability-score seeding restricts
it to granular tasks initially, and it self-widens as real `capability_ratings` accrue,
exactly like every other agent.

## Non-Goals (this spec)

- **Linux/Windows support.** oMLX/MLX is Apple-Silicon-only. Cross-platform is a future
  driver (most likely llama.cpp, since Ornith/Gemma-Coder/Qwen-Coder all ship GGUF too)
  behind the same interface — not built here.
- **Dev-onboarding TUI wizard.** Explicitly deferred by the user to a later goal, tracked
  as a side-goal on autonomy of the current instruction-to-release loop. This spec's
  onboarding surface is a CLI health-check command only (`synlynk local doctor`), not a
  guided setup wizard.
- **oMLX menubar app / admin panel.** synlynk drives oMLX headless (`omlx serve`), not
  the GUI. The dev may also run the GUI for their own visibility; synlynk doesn't depend
  on it.

## Model Roster & Hardware Tier

Target hardware baseline: **8–24GB unified memory, most devs at 16GB.** This rules out
Ornith-35B (needs 64GB+ even at aggressive quant) for the default roster.

| Model | Source | Quant (16GB default) | Est. weight footprint |
|---|---|---|---|
| `ornith-1.0-9b` | `mlx-community/Ornith-1.0-9B` | 4-bit | ~5-6GB |
| `qwen-coder` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | 4-bit | ~4GB |
| `gemma-coder` | `mlx-community/codegemma-7b-it-4bit` (or nearest MLX CodeGemma build) | 4-bit | ~4GB |

`.agents/local.json` declares the roster plus hardware-tier presets (24GB+ can bump to
6-bit or add Ornith-35B at aggressive quant later) so upgrading hardware doesn't require
a code change — just a config edit.

## Architecture

### Dispatch: new HTTP driver path, not a CLI subprocess

Every existing agent (`claude`, `codex`, `agy`, `grok`) is dispatched as a CLI subprocess
(`dispatch_agent()` in `synlynk/dispatch.py`, spawning `claude --print`, `codex exec -`,
etc.). `local` has no CLI to spawn — it's a long-running local HTTP server. This needs a
genuinely new branch, not a new set of `dispatch_flags`:

```
dispatch_agent(agent="local", ...)
  → _preflight_local()          # GET /v1/models on the oMLX endpoint; fail fast if down
  → _format_prompt_for_agent()  # reuse existing generic fallback branch — plain
                                 #  instruction-following, no local-specific formatting
                                 #  needed at launch
  → POST {endpoint}/v1/chat/completions
        {"model": <pinned or story-selected roster name>, "messages": [...]}
  → capture response text, token usage from the OpenAI-shaped response body
       (no regex scraping needed — extract_tokens() gets a direct-JSON fast path)
  → everything downstream (worktree creation, verify, job summary) is unchanged
```

`AGENT_CAPABILITY_BASELINES["local"]` (`synlynk/_constants.py`) gets a `driver: "http"`
marker instead of `cli`/`dispatch_flags`, so `_dispatch_flags_for_agent()` and
`_permissions_to_flags()` short-circuit to empty for this agent (permissions are enforced
by oMLX running with filesystem access scoped to the job's worktree, passed as a
working-directory hint in the prompt, same pattern already used for `agy`).

### `.agents/local.json`

Same file-per-agent pattern as `.agents/support.json`, but describing driver config
instead of investigator/fixer signals:

```json
{
  "name": "local",
  "driver": "http",
  "endpoint": "http://127.0.0.1:8080",
  "models": [
    {"id": "ornith-1.0-9b", "pinned": true},
    {"id": "qwen-coder", "pinned": false},
    {"id": "gemma-coder", "pinned": false}
  ],
  "hardware_tier": "16gb-default"
}
```

`pinned: true` models stay resident in oMLX's RAM tier; others load on demand and can be
evicted under memory pressure — this is oMLX's own behavior, synlynk just declares intent.

## Capability Envelope (granular-tasks-first rollout)

No new gating code. `capability_scores` rows are seeded for `agent="local"`:

- **Low/absent everywhere by default** — cold-start-equivalent, so `_best_agent_for_story()`
  simply won't surface it for most coordinates (mirrors existing cold-start behavior:
  "no capability data → not a candidate").
- **A narrow starter whitelist gets seeded moderate scores** — small `estimated_tokens`,
  `discipline IN (docs, testing)`, `stage=execute`. These are the "granular tasks" the
  agent proves itself on first.
- As real jobs complete, `_write_capability_rating()` writes real signals for `local`
  exactly like any other agent — the envelope widens itself via the existing 5-signal
  scoring formula. No local-specific widening logic.

## Cost & Quota

- `cost_usd = 0.0` always for `local` jobs (verified user decision: true $0, not a
  synthetic floor — rollout pacing is entirely capability-score-driven, not cost-driven).
  It wins every stage-3 cost tie-break it's already capability-eligible for in stage 1.
- Still logged into `agent_quotas` and telemetry for observability, but the quota type is
  a **concurrency guard, not a $ limit** — one Mac, one GPU/unified-memory pool, so a
  `local_concurrency` quota_type caps in-flight local jobs (default 1) rather than
  tracking spend against a budget.

## Testing — two-tier, not all-mocked

Standard CI (`pytest tests/`, runs on every PR, must work on any machine including
non-Apple-Silicon) stays **mocked**: the oMLX HTTP endpoint is faked, covering dispatch
routing, prompt formatting, capability-score seeding, cost/quota accounting, and
preflight failure handling (endpoint down → clean error, not a hang).

A second, **opt-in real-hardware tier** covers actual inference correctness:

- Tests marked `@pytest.mark.local_hardware`, skipped by default in the standard run.
- Runs against a real `omlx serve` instance with the real roster, invoked via
  `pytest -m local_hardware` or a `synlynk local verify` command.
- Not part of the PR gate — run manually by whoever has oMLX + models installed, or on a
  self-hosted Apple-Silicon runner if one is added later. Documented as such so no one
  expects it to run in standard CI.

`synlynk local doctor` — a small standalone health-check command — verifies oMLX is
installed, reachable, and the roster models are present, printing actionable next steps
if not (this *is* the onboarding surface for this spec; the guided wizard is future work).

## Rollout / PR Sequence

Implementation dispatches to Codex/Agy/Grok per the locked role split (Claude: design,
review, git integration only). Planned as 4 PRs:

1. **Driver interface + `.agents/local.json` + dispatch HTTP path** — `_preflight_local()`,
   the new dispatch branch, `AGENT_CAPABILITY_BASELINES["local"]`, `synlynk local doctor`.
2. **Capability-score seeding + quota concurrency guard** — starter whitelist rows,
   `local_concurrency` quota type.
3. **Tests** — mocked CI tier + `local_hardware`-marked real tier.
4. **Docs** — `capability-matrix-taxonomy.md` local-agent example, `docs/blog/` post(s)
   per the Blog Post Protocol, README note that this is opt-in (nothing breaks without
   it — consistent with `[[agent-design-principles]]`: opt-in at init, measurable ROI
   required).

Each PR follows normal branch/worktree discipline (`feat/local-agent-<n>-<slug>`,
one worktree per branch, off `main`).

## Open Risks

- **oMLX is a young (~5 month old at time of writing), single-maintainer project.** It's
  Apache-2.0 and verifiably real/active, but not Apple-official — API surface or the
  tiered-cache behavior could change. Mitigation: the driver interface is thin
  specifically so a switch to plain `mlx_lm` or llama.cpp later is a config/driver-file
  change, not a `dispatch.py` rewrite.
- **MLX conversions of newly-released models (like Ornith) can lag or disappear** if the
  community maintainer stops updating. Mitigation: roster is config (`.agents/local.json`),
  not hardcoded — swapping a model requires no code change.
- **16GB is a tight baseline** for a 9B model plus oMLX's own RAM-tier cache plus normal
  dev machine load (browser, IDE, etc.). If real-world testing shows memory pressure,
  the fallback is dropping the default roster to smaller models (e.g. Qwen-Coder at a
  smaller size) — flagged here so it's not a surprise during PR 3's real-hardware testing.
