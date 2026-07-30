---
title: "PR #587 — Harness Compatibility & Capability: A Design Spec That Corrected Itself"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 82
pr: "#587"
merged: status: open (spec approved 2026-07-30; implementation plan committed)
---

## The Broader Goal at the End of the Previous PR

Coming out of PR #549 (LIVE-3 recovery) and the run of state-engine and identity work before it, synlynk's dispatch mechanism was reliable at the level of "does the job run and does a PR come out the other end." What it didn't have was any model of *why* a dispatched job goes quiet without producing anything. The trigger for this PR was a real incident: an Agy dispatch job ran ~72 minutes, took one 3-second turn, hit a shell `command` permission wall that headless mode couldn't prompt for, was silently auto-denied, and produced nothing. Nothing in synlynk's telemetry distinguished that from a job that was still legitimately thinking.

## Strategic Shifts in This PR

The work started as a single research thread (environment discovery, harness capability testing, third-party tool interop, headful-vs-headless adherence) intended to produce one design spec. It became something with a second, load-bearing deliverable: a **canonical, versioned, periodically-recalibrated capability reference** (`docs/reference/harness-capability-matrix.md`), separate from the spec itself. The shift happened because the design spec kept citing specific harness behavior — Codex's config schema, Grok's flag surface, which failure modes are silent vs. loud — as settled fact, when in several cases it was inherited assumption nobody had gone back to the harness's own maintainer to check.

So the process changed twice, mid-PR:

1. **Round 1 — design critique.** `synlynk decide --panel claude,agy,codex,grok` reviewed the spec as critics. Claude, Codex, and Grok converged on four required amendments (mandatory audit logging, a required/optional capability split, presence-only v1 gating, explicit hard-gate references); Agy returned no output.
2. **Round 2 — maintainer self-review.** A second, differently-scoped panel round asked each agent to stop critiquing the design and instead **self-report as maintainer of its own harness** — what it can actually do, per surface, headless vs. interactive, and whether synlynk's assumptions about its config were even correct. This is the round that mattered most, because it's the one that found real errors rather than design opinions.

## What This PR Shipped

**The self-review round surfaced four concrete corrections**, each backed by the harness's own CLI, not inference:

- **Claude's headless permission-wall failure mode is a loud error** (a permission-denied exception surfaces in output), not the silent auto-deny the spec had generalized from Agy's incident. This mattered because §2a's remediation design had assumed a uniform failure shape across harnesses.
- **Grok is not a bare Claude-instruction-inheritor.** It has a real, documented native flag surface (`--permission-mode`, `--allow`/`--deny`, `--yolo`, `~/.grok/config.toml`) that `_permissions_to_flags` in `dispatch.py` simply never maps to — a real gap (confirming #338), but a narrower and more fixable one than "Grok has no config surface at all."
- **Codex's approval flag is `--ask-for-approval`** (`untrusted|on-request|never`), not `--approval-policy` as `AGENT_CAPABILITY_BASELINES` currently has it.
- **Codex's assumed write-back target is unconfirmed.** The spec's §2a remediation mechanism for Codex assumed a `[sandbox_workspace_write]` TOML table with `network_access`/`writable_roots` keys — a target that two prior dispatch attempts had reported as independently confirmed. Queried directly, Codex's own `codex sandbox --help` output could not substantiate it; the real surface exposes `--sandbox-state-disable-network`, `--sandbox-state-readable-root`, `--allow-unix-socket`, `--permission-profile` instead. The spec now flags this as unverified and blocks implementation of that specific write path pending independent confirmation against the actual `config.toml` schema — the same treatment already given to the #339/#578/#580 hard-gates.

**Getting Codex's answer required routing around synlynk's own tooling.** `synlynk decide`'s panel query (`synlynk/team.py:329`) hardcodes a 120-second timeout per agent. Codex failed against it twice — once via a broken local `timeout` wrapper (macOS doesn't ship GNU `timeout`), once against the real internal limit — because a five-section self-review prompt reliably takes Codex several minutes and ~44K tokens to answer completely. The eventual fix was to bypass `synlynk decide` and query `codex exec` directly with no artificial timeout. This is now recorded as a known gap in both the spec (§7) and the canon doc: synlynk's own dispatch tooling should treat >120s silence from Codex as "still working" for non-trivial prompts, not "failed."

**The canon doc itself** (`docs/reference/harness-capability-matrix.md`) captures, per harness: a capability matrix broken out by surface (CLI/IDE/web/desktop/API), interactive-vs-headless behavior, confirmed config/control surfaces, known gaps, and a self-correction section against this spec's original claims — plus real CLI version numbers captured via each vendor's own `--version` output (Claude 2.1.220, Agy 1.1.8, Codex 0.144.1, Grok 0.2.106), with a "Maintenance & calibration" section framing it explicitly as a recurring task: recalibrate on any minor version bump, on any unexpected capability wall, or quarterly at minimum. It was also published as a standalone Artifact — separate from its life as a committed repo doc — for a scannable, presentable copy of the same data.

One structural finding from cross-referencing all four self-reviews: **surface-capability asymmetry**. Claude and Agy are the only two harnesses whose non-CLI surfaces (IDE extensions) add genuinely new capability rather than just rehosting the CLI. Codex is the most CLI-concentrated of the four — every other surface either shares the identical stack or has no confirmed presence at all. That means dispatch-time capability assumptions ported from one harness's IDE/desktop behavior don't generalize, and Codex specifically should be treated as CLI-only for capability detection until proven otherwise.

## Brainstorm Visuals Used

None — this PR's brainstorm ran headless (dispatched via `synlynk dispatch claude`, HEADLESS-SAFE mode) and explicitly skipped the Visual Companion offer, since two prior dispatch attempts (`job-a58018b8`, `job-3b0fb176`) had demonstrated that an interactive Visual Companion prompt is itself an instance of the exact headless/headful adherence gap this goal targets.

## What This Achieved on the Path to Autonomy

This PR is the first time synlynk's own design process caught itself asserting a harness behavior that turned out to be wrong, and fixed the assertion using the harness's own CLI as the source of truth rather than tribal knowledge or a prior dispatch's confident-but-mistaken research note. That's a small instance of the larger goal: a dispatched harness should either succeed at a granted capability headless, or fail loud with a specific, operator-actionable remediation step (`goal-6ebfe9b5`). Before this PR, synlynk's own design docs weren't holding themselves to that standard about the harnesses they describe.

## Strategic Note: The Goal at the End of This PR

Nikhil approved the design spec on 2026-07-30. The implementation plan (`docs/superpowers/plans/2026-07-30-harness-compatibility-capability.md`) is now committed, per the Design → Plan → Build Sequence. It surfaced one finding the spec itself had anticipated but this session confirmed as live: the spec's own hard-gate dependency, #339, is closed, but its actual fix PRs (**#578, #580**) are still open and unmerged. That means the preflight-gating phase in the plan is scoped to run its "no-coverage" fallback path — never trusting a literal TC1-5 probe result — until those land, and the plan calls out re-checking their merge status immediately before that phase is dispatched rather than trusting this snapshot. Similarly, #419 (permission-denial telemetry misclassification) is confirmed open with no fix yet, so the plan tracks the `UNVERIFIED_CAPABILITY` telemetry tag as blocked follow-up rather than scheduling it now. Two smaller follow-ups remain explicitly deferred, not forgotten: the Version Snapshot table's IDE/web/desktop/API version cells for all four harnesses (captured only for CLI this pass), and making `synlynk/team.py:329`'s 120s panel timeout configurable so Codex doesn't need a manual bypass on every future self-review round — the plan schedules that as its own low-risk, dependency-free phase.
