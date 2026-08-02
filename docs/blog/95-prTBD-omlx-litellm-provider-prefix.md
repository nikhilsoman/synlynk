# 95: exit 0 lied — a real dispatch never reached Ornith

## Where we left off

PR #672 fixed two independent gaps in the local-agent stack: the port literal (8080→8000,
carried over from PR #665) and oMLX's mandatory `Authorization: Bearer` auth, which
`synlynk local doctor` now sends correctly. With that PR merged, `synlynk local doctor`
went fully green — oMLX reachable, roster matched, aider installed.

## What moved the goalpost

Doctor passing looked like "done." It wasn't. The first real end-to-end test — actually
dispatching a task to the `local` agent (`synlynk dispatch local --task "Scan this repo
and give me a summary"`) — reported `OK (exit 0)`, `0 tokens in / 0 tokens out`, `0 files
touched`. That last number should have been the tell: Aider ran, but did nothing.

The captured log told the real story:

```
litellm.BadRequestError: LLM Provider NOT provided. Pass in the LLM provider you
are trying to call. You passed model=Ornith-1.0-9B-4bit
```

Aider doesn't talk to the OpenAI-compatible endpoint directly — it goes through a library
called litellm, which infers the request format from the `--model` string. Known OpenAI
model names resolve automatically. An arbitrary local name like `Ornith-1.0-9B-4bit` does
not, even with `--openai-api-base` pointed at oMLX — litellm needs an explicit provider
prefix (`openai/Ornith-1.0-9B-4bit`) to route the call at all. Without it, litellm errors
*before* sending anything, and Aider's subprocess still exits 0 because from its own
perspective, nothing crashed.

This bug has existed since the `local` agent's original ship (PR #204/205/207) — every
real dispatch to it has been silently failing at the litellm layer the entire time. It
was only caught now because this was the first time anyone actually ran a live dispatch
against a real, authenticated oMLX instance instead of just checking `doctor`.

## What this PR ships

One functional line, in `_local_dispatch_model_flags()` (`synlynk/local_agent.py`):

```python
"--model", f"openai/{model_id}",
```

`.agents/local.json`'s roster IDs are untouched — they still store the bare oMLX-native
name (`Ornith-1.0-9B-4bit`), matching what `/v1/models` actually returns, which is what
`cmd_local_doctor()`'s roster check depends on. The prefix is added only at the point the
Aider CLI flags are built, so doctor and dispatch each use the form the tool they're
talking to actually needs.

Caught a real regression along the way: a stale assertion in
`tests/test_dispatch_local_agent.py` (a different test file than the one the first
dispatch touched) still expected the un-prefixed model flag. The full project suite
(1575 tests) surfaced it; a second small Codex dispatch fixed the one-line assertion.
Verified directly — not from job-status alone — before merging either commit.

Backfilled as Addendum 3 / Task Group 8 into the same design spec and implementation
plan that already carry Addenda 1 and 2, continuing this project's pattern of folding
narrow post-ship gaps into the original document rather than spawning new ones.

## Where this leaves the local-agent track

Doctor going green was necessary but not sufficient — this is the fix that makes a real
dispatch actually reach the model. Next verification step: re-run the same test dispatch
(`"Scan this repo and give me a summary"`) on `main` after this merges, and confirm Ornith
produces an actual response this time.

## Next goalpost

Same two open threads as before this PR: user review of the fleet-parity reliability
cluster spec, and the not-yet-started herdr-integration brainstorm.
