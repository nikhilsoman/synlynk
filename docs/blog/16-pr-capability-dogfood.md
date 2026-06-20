# Blog Post 16 — Capability Dogfood: Seeding the Routing Brain

## Broader Goal (End of Previous PR)

At the end of v0.7.0 (Static Scan Quality), synlynk gained the ability to enrich every AI session with a live `## Source Architecture` snapshot — function signatures, constants, import graph — generated without any AI calls. The routing engine existed (`dispatch_agent()` with `capability_scores` view), but the ledger was empty. Every dispatch was effectively random because no agent had ever been scored. The goal for this PR: feed the ledger real signal from real work, so routing becomes data-driven.

## Strategic Shift: Two-Phase Dogfood

The original capability dogfood concept was vague — "give agents real tasks." This PR sharpened it into two concrete phases:

**Phase A — Backfill + Attest:** 20 merged PRs represent real engineering work with known outcomes. Retrospectively scoring them gives the ledger a meaningful history across three agents (Claude, AGY, Codex) and three phases (bootstrap, build, scale) without waiting months for fresh dispatches. This is a one-time bootstrap, not an ongoing pattern.

**Phase B — Live Dispatches:** Run actual tasks against AGY and Codex via `synlynk dispatch`, capture output, and attest scores. This seeds the "live" side of the ledger and exercises the dispatch infrastructure end-to-end.

The user stated plainly: "Definition B is the path to autonomous operations — can't begin that without some data from A." So Phase A came first, Phase B followed, and Definition B (three-agent Autopilot) is deferred until ledger data is available.

## What This PR Shipped

### Backfill Script (`bin/backfill_capability.py`)

Reads all merged PRs via `gh pr list --json number,title,mergedAt,files,reviews`, infers `engg_domain` from title prefix then file paths, infers `phase` from PR number (1–10 bootstrap, 11–25 build, 26+ scale), and inserts `stories` + `capability_ratings` rows with `signal_source='backfill'` and `quality=0.0`. Supports `--dry-run`.

### Attestation Script (`bin/attest_capability.py`)

A static `ATTESTATIONS` dict maps each `story-pr{N}` to `{model, quality, note}`. Model versions follow the actual chronology: `claude-opus-4-5` for PRs 1–28, `claude-sonnet-4-5` for 29–42, `claude-sonnet-4-6` for 43–49. Quality scores range from 6.0 (version bump PRs) to 9.0 (E2E suite, Static Scan Quality). Running the script UPDATEs existing backfill rows in-place — 20 rows attested successfully.

### Routing Fix: `--force-agent`

A critical discovery during live dispatches: `dispatch_agent()` was routing every `synlynk dispatch agy` to `claude` because backfill gave Claude the highest scores for every coordinate. This defeated the purpose of running real AGY/Codex tasks. Fix: added `force_agent: bool = False` to `dispatch_agent()` and a `--force-agent` CLI flag that bypasses the `_best_agent_for_story()` override. Without this, capability dogfood is impossible — the routing brain immediately hijacks every dispatch to the highest-scored agent.

### AGY Dispatch Fix: `prompt_via_arg`

AGY's `-p` flag takes the prompt as a value (`agy -p "..."`) not via stdin. The original baseline had `non_interactive_flags: ["--quiet"]` which is wrong (AGY doesn't have `--quiet`). Fix: `non_interactive_flags: ["-p"]` with `prompt_via_arg: True` in the baseline. When this flag is set, `dispatch_agent()` builds:

```bash
PROMPT=$(cat /path/to/prompt.txt); agy -p "$PROMPT" > log.txt 2>&1; echo $? > log.txt.exit
```

instead of `agy < prompt.txt`. This is the pattern needed for any CLI that takes prompts as arguments rather than stdin.

### AGY Live Dispatch — Autopilot Gap Analysis

AGY was dispatched with `--force-agent` to produce `docs/proposals/autopilot-gap-analysis-agy.md` — a structured gap analysis of the Autopilot Initiative against v0.7.0. The task embedded the autopilot proposal and relevant context directly in the prompt (avoiding filesystem navigation issues in AGY's print mode). Exit 0, 125 lines of output covering:

- **Ownership Model** — no `assigned_agent_id` in `state.db`; recommends Option A (DB integration) for long-term, Option B (flat-file `@mentions`) for rapid bridge
- **Human-in-the-Loop Thresholds** — no entitlements policy file; recommends `.synlynk/entitlements.yaml`
- **Agent Personas** — no cryptographic identity; recommends Ed25519 keypairs per agent
- **Feedback Loops** — no agent-to-agent messaging; recommends `agent_messages` table in `state.db`
- **Cold Start** — no bootstrap templates; recommends `synlynk init-autopilot` command
- **Recommended First Agent:** Support Engineer — deterministic inputs/outputs, lowest blast radius

Quality score 8.0 attested for `story-4adc797d` (gemini-2.5-flash).

### Codex Dispatch — Confirmed TTY-Blocked

Codex requires an interactive terminal and cannot be dispatched headlessly. Error: `stdin is not a terminal`. Codex tasks will require `synlynk exec codex` (interactive session) followed by manual score attestation. The `story-99f6a867` Codex placeholder remains with a backfill score until an interactive session is run.

### Capability Ledger in `synlynk status`

Added a CAPABILITY LEDGER section to `cmd_status()` showing top-3 weighted scores. Every `synlynk status` call now surfaces live routing signal:

```
 CAPABILITY LEDGER
   Agent      Model                  Domain   Phase       Score  N
   agy        gemini-2.5-flash       unknown  build       10.00  1
   claude     claude-opus-4-8        unknown  build       10.00  3
   ...
```

This section is covered by `test_status_shows_capability_ledger` (test count: 317).

## What Was Achieved

The routing brain now has real data. 20 PRs of Claude history are attested with model-version precision. AGY has 3 scores across docs and unknown domains. The dispatch infrastructure (prompt file generation, shell command construction, `--force-agent` override) is proven end-to-end. `synlynk status` surfaces this signal on every invocation. The ledger is live.

## New Goalpost

The ledger has enough signal to begin **Definition B: three-agent Autopilot**. The AGY gap analysis identified the five unresolved questions (ownership model, HITL thresholds, agent personas, feedback loops, cold start) that Definition B must answer through implementation. The Support Engineer agent — deterministic, low blast radius, infrastructure-ready — is the recommended first agent to build. The next PR will brainstorm and spec that agent.
