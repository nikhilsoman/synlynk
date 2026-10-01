# LIVE-21: `synlynk launch` hard-blocks dispatch with "no probe data for agent"

Date: 2026-10-01

Issue: #1901

## Conclusion

Dispatch to `claude` from the `synlynk launch` wizard's "dispatch now" screen
is hard-blocked in any environment where `synlynk probe claude` has never
been run, because the TC-2 flag preflight check requires a live row in
`harness_records` and that table is populated only by `synlynk probe`. The
wizard confirms a dispatch with only a non-blocking "degraded" warning and
then fails the user at the actual preflight stage, with no way to override
via `--force-agent`. This is not Warp-specific or terminal-specific —
onboarding (`synlynk init`, the wizard) never calls `cmd_probe` regardless of
which shell wraps `synlynk`.

A second, unrelated concern raised during the same investigation — whether
`CLAUDE.md`'s "Harness Instructions (synlynk-managed)" block was
prompt-injected — was ruled out as a tool-layer classifier false positive;
see "Related, ruled out" below.

## Evidence

- Reported output:
  ```
  ⚠ capability gate degraded: no explicit `--requires` declaration
  ⚠ Dispatch failed: Dispatch blocked — preflight failed: no probe data for agent; run synlynk probe claude
  ```
  produced from the `synlynk launch` task-picker TUI (`[enter] dispatch now`
  screen in `synlynk/wizard.py`).

- `synlynk/wizard.py:214-230` — the wizard calls
  `dispatch_agent(agent=chosen["agent"], task=prompt, story_id=None,
  force_agent=True, context_mode=...)` with no `requires` argument, and
  catches any exception into `⚠ Dispatch failed: {exc}`.

- Two independent gates run inside `dispatch_agent` before a harness
  subprocess is spawned (`synlynk/dispatch.py`):
  1. `_dispatch_capability_preflight` (`dispatch.py:2321`) looks up
     `harness_records` for a probe row. With none found and no explicit
     `--requires` declared, it classifies the state as `no_coverage` and
     *passes with a degraded status* (`dispatch.py:2432`), which is printed
     as the first warning at `dispatch.py:3244`. This gate is non-blocking
     by design.
  2. The TC-2 flag preflight inside `_preflight_dispatch`
     (`dispatch.py:2611-2636`) runs next. For any harness whose
     `HARNESS_CAPABILITY_BASELINES` entry declares `valid_flags` or
     `required_flags` — `claude` does: `--dangerously-skip-permissions`,
     `--model`, `--output-format` (`synlynk/_constants.py:50`) — it requires
     an actual row in `harness_records`. If none exists it returns
     `passed: False` with
     `reason = "no probe data for agent; run synlynk probe {harness_name}"`.
     `dispatch.py` turns this into
     `RuntimeError("Dispatch blocked — preflight failed: …")`
     (`dispatch.py:~3268`), which the wizard surfaces as `⚠ Dispatch
     failed: …`.

- `harness_records` is written only by `synlynk probe <agent>`
  (`INSERT INTO harness_records …`, `synlynk/probe.py:651`). Nothing in
  `init()` (`synlynk/__init__.py:2878`) seeds it — the only table seeded
  during migration is the separate static `harness_baselines` table
  (`synlynk/db.py:1478`), not the live probe-state table.

- `_preflight_dispatch`'s `force_agent` parameter
  (`synlynk/dispatch.py:2479`) is consulted only for the Core-4
  instruction-file check (`dispatch.py:2541-2549`) and the Agy/Stitch MCP
  check (`dispatch.py:2552-2561`). The probe-row lookup at
  `dispatch.py:2611-2636` does not check `force_agent` at all, so the
  wizard's `force_agent=True` cannot bypass this block.

- Confirmed via `grep` that neither `init()` nor `synlynk/wizard.py` calls
  `cmd_probe` anywhere; only `cmd_agent_add()` (`synlynk/__init__.py:1641`,
  the `synlynk agent add <agent>` retrofit command) auto-probes.

- `tests/test_selftest.py:505-582` has existing coverage that reproduces
  this exact failure mode (dispatch against an unprobed harness raising
  `"no probe data for agent; run synlynk probe {agent}"`), confirming this
  is expected, by-design gate behavior rather than a regression.

- `_probe_agent` (`synlynk/probe.py:578`) is a cheap, safe, idempotent
  fix: it shells out to `claude --version` (5s timeout, tolerates
  `FileNotFoundError`/timeout by recording `installed_version="unavailable"`
  without raising), runs a local schema check, and for the `claude`
  baseline has no required network endpoints
  (`network_deps.required_endpoints` is empty in `_constants.py:50`), so it
  reliably inserts a `compliance_status='ok'` row.

## Related, ruled out

A second signal from the same investigation — another session flagging
`CLAUDE.md`'s `# Harness Instructions (synlynk-managed — do not edit)`
block (including the `--dangerously-skip-permissions` dispatch-flags line
and the PR auto-approve default) as possible prompt injection, with Claude
Code's own tool-layer permission classifier independently blocking a
`git add CLAUDE.md` as "Instruction Poisoning" — was investigated and ruled
out as a classifier false positive, not evidence of a compromised repo:

- The exact text (including the `qa APPROVE is the default…` paragraph) is
  a hardcoded Python template, `_PR_REVIEW_SOP` in `synlynk/probe.py:29-38`,
  and the `<!-- synlynk:harness v… -->` fence/footer generator lives in
  `synlynk/probe.py:529` and `synlynk/parity.py:156-157`.
- The same block is mirrored into `GEMINI.md`, `AGENTS.md`, `GROK.md` with
  per-harness substitution ("escalate to Claude" vs. "escalate to the Home
  Harness"), consistent with a sync/templating feature, not organic
  hand-written prose repeated four times.
- `git blame CLAUDE.md` traces the content to a single coherent commit
  (`f2141ea`, authored by the repo owner, 2026-09-27); `git status` /
  `git diff HEAD -- CLAUDE.md` in the affected checkout was clean — nothing
  staged, modified, or injected.
- Dedicated test coverage exists for this parity feature:
  `tests/test_instructions.py`, `tests/test_parity.py`,
  `tests/test_probe.py`.

No action required on this thread beyond noting the classifier's
pattern-match (dangerous-sounding flag + "do not edit" + approval language)
as a known false-positive shape, should it recur.

## Resolution

Not yet implemented. Immediate workaround (verified safe, see Evidence):

```
synlynk probe claude   # or: synlynk probe   (probes all 4 harnesses at once)
```

This populates `harness_records` with `compliance_status='ok'`, which
clears both the capability-gate degraded warning and the TC-2 hard block.

Recommended fix, tracked on #1901: either (a) have `init()` run `synlynk
probe` for configured harnesses as part of onboarding, or (b) have the
wizard's "dispatch now" screen check probe coverage and offer to probe
inline before confirming a dispatch that is guaranteed to hard-fail.
Switching onboarding from Warp to the native Claude CLI does not address
the root cause — neither onboarding entry point calls `cmd_probe`,
regardless of the wrapping terminal.

## Next test

Once the onboarding fix lands, add a wizard-level test asserting that a
fresh `.synlynk/state.db` (no prior `synlynk probe` run) either gets probed
automatically during `synlynk init`, or that the "dispatch now" screen
blocks *before* confirmation with an actionable prompt rather than after.
