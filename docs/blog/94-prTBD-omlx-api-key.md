# 94: oMLX needs an API key, and the roster ID was wrong too

## Where we left off

PR #665 fixed the oMLX endpoint's port literal — `.agents/local.json`, `synlynk/local_agent.py`'s
`_DEFAULT_LOCAL_CONFIG`, and `synlynk/_constants.py`'s `AGENT_CAPABILITY_BASELINES` all pointed at
8080, but the real oMLX install on this machine binds 8000. That PR closed with the port corrected
in all three places and verified live on `main`.

## What moved the goalpost

With the port fixed, `synlynk local doctor` should have gone green. It didn't — it failed with a
401 Unauthorized. Digging in surfaced two independent problems, not one:

1. **oMLX requires auth.** With `auth.skip_api_key_verification: false` in oMLX's own
   `~/.omlx/settings.json` (the default), every request needs
   `Authorization: Bearer <api_key>`. Nothing in synlynk ever sent that header — `_health_check()`
   built a bare GET request, and a real dispatch's `env_passthrough` allowlist for the `local`
   agent was empty, so even Aider itself would never see a key forwarded to it.
2. **The roster ID was stale.** `.agents/local.json` pinned `ornith-1.0-9b`; oMLX actually serves
   `Ornith-1.0-9B-4bit`, derived from its on-disk HuggingFace-style model directory name. Two
   config-drift bugs discovered in the same investigation, unrelated to each other.

Verified both independently via direct authenticated `curl` — `/v1/models` returned the real model
list, `/v1/chat/completions` returned a real generated response — confirming the underlying
inference stack was never the problem; synlynk's own request-building was.

## What this PR ships

Split into a config-only fix (mine, direct) and a code fix (dispatched to Codex), per this
project's role split:

- `.agents/local.json`: `ornith-1.0-9b` → `Ornith-1.0-9B-4bit`.
- `_health_check()` in `synlynk/local_agent.py` gained an optional `api_key` parameter; when set,
  it sends `Authorization: Bearer <api_key>` as a request header.
- `cmd_local_doctor()` now reads `OPENAI_API_KEY` from the environment and passes it through. A
  401 is now reported distinctly (`"oMLX rejected the request (401 Unauthorized) — export
  OPENAI_API_KEY and retry"`) instead of the old, misleading `"Start it with: omlx serve"` message
  that conflated auth failure with "not running."
- `AGENT_CAPABILITY_BASELINES["local"]["env_passthrough"]` gained `"OPENAI_API_KEY"` — the existing
  `_build_subprocess_env()` allowlist mechanism in `synlynk/dispatch.py` needed no new plumbing,
  just a wider allowlist entry. Aider already reads `OPENAI_API_KEY` natively for OpenAI-compatible
  backends, so doctor and a live dispatch now share one convention.

Both the design spec (`docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md`) and
implementation plan (`docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md`) got backfilled
with an Addendum and a Task Group, following the same pattern set by the earlier Aider-presence-check
gap (PR #657) — narrow post-ship gaps in an already-shipped feature get folded into the original
spec/plan rather than spawning a parallel document.

**Security constraint, kept throughout:** the real API key (found at `~/.omlx/settings.json`) is
never written to the repo, any config file, or a commit. Tests use fake placeholder values
(`sk-test-123`, `sk-env-key`). The operator exports `OPENAI_API_KEY` in their own shell; synlynk
code only ever reads it from the environment at runtime.

4 new tests cover the header-sending behavior and the 401-vs-generic-unreachable distinction. Full
project suite: 1571 passed, 2 skipped, no regressions.

## Where this leaves the local-agent track

The aider+oMLX "Local" 5th agent rollout is now fully functional end-to-end on this machine: correct
port, correct roster ID, and authenticated health checks and dispatch. `synlynk local doctor` with
`OPENAI_API_KEY` exported should report clean.

## Next goalpost

Two threads remain open, neither started: the fleet-parity reliability cluster spec
(`docs/superpowers/specs/2026-08-02-fleet-parity-reliability-cluster-design.md`) is waiting on
review, and the herdr-integration brainstorm (the second half of "Local Agents with Synlynk") hasn't
begun.
