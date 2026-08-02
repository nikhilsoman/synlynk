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

- **A dedicated Linux/Windows inference driver.** Not needed as a separate future-work
  item: Aider talks to any OpenAI-compatible endpoint, so v1 is already cross-platform at
  the dispatch/agent layer. The only Apple-Silicon-specific piece is oMLX itself (the
  inference server) — a Linux/Windows dev just points `.agents/local.json`'s `endpoint`
  at a different OpenAI-compatible local server (e.g. `llama.cpp`'s server mode) and
  nothing else changes. Documenting and testing that swap is still out of scope for this
  spec, but no new driver code is required to support it later.
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

### Two layers: oMLX (inference) + Aider (agentic editor) — not a bespoke HTTP driver

**Revised after external review (Fable, 2026-07-12) surfaced a blocker in the original
single-shot-HTTP-call design: a plain `POST /v1/chat/completions` call returns text but
cannot edit files, which meant `_write_capability_rating()` had no real outcome to score
and the whole "self-widening envelope" premise had nothing to widen from.**

oMLX's role is unchanged from the original design — it is the inference/serving layer:
runs `omlx serve`, swaps/pins models across the Ornith-9B/Qwen-Coder/Gemma-Coder roster,
owns the tiered RAM+SSD KV cache. It does no editing.

[Aider](https://github.com/Aider-AI/aider) (verified via GitHub API: Apache-2.0, active,
47K stars, last push 2026-05-22) sits in front of it as the agentic editor: reads files,
plans edits, writes files, git-aware — talking to oMLX purely as an OpenAI-compatible
model backend, exactly as it would talk to any other OpenAI-compatible provider. Aider
does no inference; oMLX does no editing. Neither replaces the other.

Critically, this means `local` is dispatched as a **CLI subprocess**, exactly like
`claude`, `codex`, `agy`, and `grok` already are — there is no new "HTTP driver" branch
in `dispatch.py` at all:

```
dispatch_agent(agent="local", ...)
  → _preflight_local()          # GET oMLX /v1/models; fail fast with an actionable
                                 #  message if oMLX isn't running (Aider itself would
                                 #  otherwise surface a raw connection error)
  → _format_prompt_for_agent()  # existing generic fallback branch, unchanged
  → spawn `aider` as a subprocess inside the job's worktree, pointed at the oMLX
        endpoint + pinned/selected roster model:
        aider --openai-api-base {endpoint}/v1 --model <roster-name>
              --edit-format <per-model, from .agents/local.json>
              --no-auto-commits --yes-always <other non-interactive flags>
  → Aider reads/edits/writes real files in the worktree; capture stdout for
        token/cost extraction, exit code for success/failure
  → everything downstream (worktree creation, verify, job summary) is unchanged
```

`--no-auto-commits` is required: Aider's default behavior is to commit after each edit,
which would fight the dispatch pipeline's own worktree-commit ownership. `--edit-format`
is set per-model rather than globally, because Aider's `whole` format (full-file
replacement) is documented as more reliable for smaller/weaker models that struggle to
produce clean unified diffs, while stronger models in the roster can use `diff`.

`AGENT_CAPABILITY_BASELINES["local"]` (`synlynk/_constants.py`) follows the exact same
shape as `codex`/`agy`/`grok` — `cli: "aider"`, `non_interactive_flags`, `dispatch_flags`
— no `driver` marker, no special-case in `_dispatch_flags_for_agent()` or
`_permissions_to_flags()`. Permissions/scope are enforced by Aider itself (its edits are
confined to the worktree it's launched in, same containment as every other agent).

### `.agents/local.json`

Same file-per-agent pattern as `.agents/support.json`, now describing both layers of the
stack — the oMLX roster/endpoint, and the Aider invocation config per model:

```json
{
  "name": "local",
  "endpoint": "http://127.0.0.1:8080",
  "models": [
    {"id": "ornith-1.0-9b", "pinned": true, "edit_format": "whole"},
    {"id": "qwen-coder", "pinned": false, "edit_format": "whole"},
    {"id": "gemma-coder", "pinned": false, "edit_format": "diff"}
  ],
  "hardware_tier": "16gb-default"
}
```

`pinned: true` models stay resident in oMLX's RAM tier; others load on demand and can be
evicted under memory pressure — this is oMLX's own behavior, synlynk just declares intent.
`edit_format` is read by the dispatch layer to build the `aider --edit-format ...` flag
per job.

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

1. **Agent registration + `.agents/local.json` + Aider CLI wiring** — `_preflight_local()`,
   `AGENT_CAPABILITY_BASELINES["local"]` (`cli: "aider"`, same shape as codex/agy/grok),
   `synlynk local doctor`.
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
  tiered-cache behavior could change. Mitigation: oMLX is only ever addressed through its
  OpenAI-compatible endpoint (by Aider, and by `_preflight_local()`'s health check) — a
  switch to plain `mlx_lm` or another OpenAI-compatible server later is a config change
  to `.agents/local.json`, not a `dispatch.py` rewrite.
- **Aider is a large, actively-maintained project (verified via GitHub API: Apache-2.0,
  47K stars, last push 2026-05-22) but still a third-party dependency synlynk doesn't
  control.** Apache-2.0 permits forking/modifying it if a synlynk-specific patch is ever
  needed (no copyleft obligation — see license note below). Its default auto-commit
  behavior must be disabled (`--no-auto-commits`) to avoid fighting the dispatch
  pipeline's own commit ownership; this is a documented Aider flag, not a patch.
- **License note (Apache-2.0, both oMLX and Aider):** permits forking, modifying, and
  private/internal use with no requirement to publish changes. Only obligations are
  preserving the copyright/license notice and noting which files were changed if
  redistributed. No patent or trademark concerns for internal use. Confirmed sufficient
  for this project's needs (2026-07-12).
- **Small local models (7-9B) are the weak link for agentic editing, not the model access
  path.** Aider's edit-format selection (`whole` vs `diff`) mitigates but doesn't
  eliminate this — a model can still misunderstand instructions or produce broken code.
  This is an acceptable and expected failure mode: `_write_capability_rating()` scores it
  down naturally, same as any other agent's bad output, and the granular-tasks-first
  starter whitelist limits blast radius while the envelope is still narrow.
- **MLX conversions of newly-released models (like Ornith) can lag or disappear** if the
  community maintainer stops updating. Mitigation: roster is config (`.agents/local.json`),
  not hardcoded — swapping a model requires no code change.
- **16GB is a tight baseline** for a 9B model plus oMLX's own RAM-tier cache plus normal
  dev machine load (browser, IDE, etc.). If real-world testing shows memory pressure,
  the fallback is dropping the default roster to smaller models (e.g. Qwen-Coder at a
  smaller size) — flagged here so it's not a surprise during PR 3's real-hardware testing.

## Addendum (2026-08-02): `synlynk local doctor` doesn't check for Aider itself

**Found during:** brainstorming the follow-on "Local Agents with Synlynk" goal (herdr +
aider + oMLX), while verifying this spec's rollout was actually complete on a real
machine. All 4 planned PRs (Rollout / PR Sequence, above) had already shipped — but
`cmd_local_doctor()` (`synlynk/local_agent.py:77`) only ever checked oMLX reachability
and the model roster (the Testing section's own description above: "verifies oMLX is
installed, reachable, and the roster models are present"). It never checked whether
`aider` — the agentic editor this entire design depends on (see "Two layers" above) — is
even on `PATH`. Confirmed no existing test covers `cmd_local_doctor()` at all, so this
gap had no regression coverage either. Net effect: on a machine with oMLX running but
Aider not installed, doctor reports fully healthy, yet dispatching a `local` job fails
immediately with a raw "command not found" instead of the actionable guidance every
other doctor failure path already gives.

**Fix (implementation plan Task Group 6):** add a `shutil.which("aider")` check to
`cmd_local_doctor()`, printed and scored alongside the existing oMLX/model-roster checks
rather than short-circuiting before them, so a single doctor run surfaces every gap in
one pass. See `docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md`, Task Group 6.
No architecture change — this is a gap in the already-approved design's own onboarding
surface, not a new decision.
