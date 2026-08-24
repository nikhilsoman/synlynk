# PM Competitive-Intelligence Sweep — Design Spec

**Status:** Approved by user, 2026-08-24
**Author:** Claude (PM role), via `superpowers:brainstorming`

## Problem

The PM agent's charter today is `"Program management — roadmap, brainstorming, issue triage."` — it has no standing responsibility to track competing products or surface product gaps. Competitive awareness currently exists only as a one-time, now-stale document (`docs/proposals/competitor-comparison-analysis.md`, last touched 2026-06-24) with no update mechanism and no path from "found a gap" to "evaluated it" to "built it."

## Goal

Add a new standing PM-charter responsibility: a weekly, autonomous competitive-intelligence sweep that (1) tracks competing products across synlynk's user segments, (2) maintains a living capability/marketing-gap comparison doc, (3) opens research tickets for candidate features, (4) convenes a `synlynk decide` round per candidate soliciting each provisioned harness's opinion from its own maintainer point of view, and (5) escalates strong-fit candidates to the user as feature-proposal tickets — which the user can then feed into the existing brainstorm → spec → plan → dispatch pipeline manually.

## Non-Goals

- No automated dollar-cost or ticket-count cap. Only post-hoc reporting (total cost, tickets opened, proposals raised) after each run, for manual review. This is a deliberate user choice, made after an automated-cap option was proposed and declined.
- No new `synlynk decide` CLI flags or structural changes. The "harness-maintainer POV" framing is achieved entirely through the `topic` string passed to the existing `decide` command — not a new mode.
- No new generic "periodic/scheduled agent" framework. This does not refactor or generalize `synlynk/support_engineer.py`'s collector model or `synlynk/workspace_agent.py`'s bespoke nudge model — both were evaluated and are a poor semantic fit for research/doc-maintenance work (see "Approaches Considered" below). This ships as its own standalone module following the same `agent run <name>` / `.agents/<name>.json` dispatch convention.
- The proposal → build handoff stays manual. The sweep never auto-starts a brainstorm session or dispatches implementation itself — it stops at opening a `[Proposal]` GitHub issue for the user to review.
- The competitive-config file is manually seeded by the user/PM; the sweep only appends newly discovered segments/competitors, never removes existing ones.

## Approaches Considered

**A. New standalone module + CLI subcommand + GH Actions cron workflow (chosen).** `synlynk/pm_agent.py` implements `synlynk pm sweep`, invoked weekly by a new `.github/workflows/pm-competitive-sweep.yml`, following the same shape as the existing `support-engineer.yml` (cron + `workflow_dispatch`, install Claude CLI, run one `python3 bin/synlynk.py ...` command). The sweep command composes a research prompt from a config file and hands it to a single headless Claude Code invocation with web and Bash tool access.

**B. Extend `support_engineer.py`'s collector framework.** Rejected: that framework's `signals`/`collector_map` model is built around "collect findings → dedup → investigate → draft fix/PR" for operational bugs. Competitive research (open-ended web discovery, doc maintenance, multi-harness opinion gathering) doesn't fit its collector abstraction without distorting it.

**C. Manual, session-triggered only (no cron, no CI).** Rejected: the user's requirement (point 2 of the original request) explicitly calls for a recurring weekly sweep; a manual-only approach can't deliver that without the user remembering to trigger it themselves.

Approach A was confirmed with the user before detailed design (their answer to the trigger-mechanism clarifying question locked in GH Actions cron).

## Architecture

```
.github/workflows/pm-competitive-sweep.yml   (weekly cron + workflow_dispatch)
        │
        ▼
synlynk pm sweep [--dry-run]                  (synlynk/pm_agent.py, new CLI subcommand)
        │
        │  loads config, composes research prompt
        ▼
docs/strategy/competitive-config.json         (segments, competitors, decide panel, labels)
        │
        ▼
claude -p "<prompt>" --allowedTools WebSearch,WebFetch,Bash --output-format json
        │
        │  single headless session performs all of:
        ├─► updates docs/strategy/competitive-landscape.md (living comparison doc)
        ├─► gh issue create  (research tickets, labeled competitive-research + architect)
        ├─► synlynk decide "<candidate>: ... from your own harness-maintainer POV" --panel <harnesses> --record
        └─► gh issue create  (feature-proposal tickets for strong-fit candidates, labeled feature-proposal + needs-user-review)
        │
        ▼
synlynk pm sweep parses the JSON output, prints/logs a summary:
tickets opened, proposals raised, actual cost — no cap enforcement
```

The sweep's "research" step runs as a single headless Claude session (not a `synlynk dispatch` job) because this is PM-role work — competitive research, ticket triage, and convening `decide` rounds are all within the existing Claude=PM/roadmap/brainstorming charter, not implementation work that the role-split policy routes to Codex/Grok/Agy. The `decide` round is the one place execution fans out to other harnesses, and it does so through the existing `synlynk decide --panel` mechanism, not a new one.

## Components

### 1. `synlynk/pm_agent.py` (new)

- `cmd_pm_sweep(dry_run: bool = False)`: loads `docs/strategy/competitive-config.json`, composes the research prompt (charter context + segment/competitor list + doc path + decide-panel + label config), and either prints the prompt (`--dry-run`) or invokes headless Claude via subprocess with `--allowedTools WebSearch,WebFetch,Bash --output-format json`, then parses and prints the run summary.
- Follows the existing headless-invocation flag conventions already used in `synlynk/dispatch.py` (`--output-format json`, `--allowedTools`) — no new invocation pattern.

### 2. `synlynk/cli.py` (modified)

- New `pm` subparser sibling to the existing `tpm` subparser, with a `sweep` action and a `--dry-run` flag, dispatching to `cmd_pm_sweep`.

### 3. `docs/strategy/competitive-config.json` (new)

```json
{
  "segments": [
    {"name": "solo indie devs building with AI agents", "competitors": ["Superpowers", "GStack"]},
    {"name": "enterprise eng platform teams", "competitors": []}
  ],
  "decide_panel": "auto",
  "research_issue_labels": ["competitive-research", "architect"],
  "proposal_issue_labels": ["feature-proposal", "needs-user-review"]
}
```

Seeded once from the content of `docs/proposals/competitor-comparison-analysis.md`; that file is then archived per the standing "archive before branch/doc removal" policy. Each sweep run may append new segments/competitors discovered during research; it never removes existing entries.

### 4. `docs/strategy/competitive-landscape.md` (new, living doc)

One file, matrix-style, one section per segment:

```markdown
# Competitive Landscape

_Last swept: <date>_

## Segment: <segment name>
Competitors: <comma-separated list>

### Capability Gaps
| Capability | synlynk | <Competitor A> | <Competitor B> | Gap? |
|---|---|---|---|---|

### Marketing Gaps
| Positioning vector | synlynk | <Competitor A> | <Competitor B> | Gap? |
|---|---|---|---|---|
```

Updated in place each sweep: existing rows refreshed, new segments/competitors appended as new sections, "Last swept" bumped.

### 5. `.github/workflows/pm-competitive-sweep.yml` (new)

Weekly cron (`0 13 * * 1`) plus `workflow_dispatch: {}` for manual runs. `permissions: {contents: write, issues: write, pull-requests: write}`. Installs the Claude Code CLI, then runs `python3 bin/synlynk.py pm sweep` with `GITHUB_TOKEN` and `ANTHROPIC_API_KEY` env vars — same shape as `.github/workflows/support-engineer.yml`.

### 6. PM charter revision

Via `agent_store.propose_charter_revision` against the live `pm` agent, and updating `SEED_CHARTERS["pm"]` in `synlynk/agent_cli.py` (currently line 14) for future inits:

> `"Program management — roadmap, brainstorming, issue triage. Runs a weekly competitive-intelligence sweep: tracks products serving synlynk's user segments, maintains a living capability/marketing-gap comparison doc, opens research tickets for candidate features, convenes harness-maintainer decide rounds, and escalates strong-fit candidates to the user as feature proposals."`

## Data Flow: One Candidate, End to End

1. Sweep's headless research step discovers or re-confirms a capability gap in a segment (e.g. competitor X has feature Y, synlynk doesn't).
2. Updates the relevant row in `competitive-landscape.md`.
3. Opens a research issue: `gh issue create --title "<feature Y>" --label competitive-research,architect --body "<what X does, why it's a gap, link to doc row>"`, delivery-confirmed via the existing `gh_write_verified` path.
4. Runs `synlynk decide "<feature Y>: should synlynk build this? Answer from your own harness-maintainer POV — implementation cost, maintenance burden, fit with your role's workflow." --panel <resolved harnesses> --record`, persisting the round to `project-docs/decisions/`.
5. Judges fit against synlynk's stated vision using the decide-round opinions plus its own research. If judged strong fit, opens a second issue: `gh issue create --title "[Proposal] <feature Y>" --label feature-proposal,needs-user-review --body "<summary of research ticket + decide-round opinions + fit rationale>"`.
6. User reviews `[Proposal]` issues at their own pace. Approving one is a manual action: the user (or Claude, on the user's instruction) starts a normal `superpowers:brainstorming` session referencing the issue, which flows into the existing spec → plan → dispatch pipeline unchanged.

## Error Handling

- If the headless Claude invocation fails outright (non-zero exit, malformed JSON output), `cmd_pm_sweep` reports the failure and exits non-zero — the GH Actions run shows as failed, same as any other CI step failure. No partial-state recovery logic is needed: the comparison doc and any tickets already written by that point remain as-is (git-tracked doc changes are committed by the same run; a failed run simply doesn't commit).
- `gh issue create` calls go through the existing `gh_write_verified` delivery-verification path, so a silently-failed issue creation is caught the same way it already is for other gh-write paths in this repo, rather than needing new verification logic.
- No retry logic is added — a failed weekly run simply reports failure; the next week's cron trigger is the natural retry.

## Testing Approach

- `cmd_pm_sweep(dry_run=True)` is unit-testable without any subprocess or network calls: given a config file, assert the composed prompt contains the expected segments/competitors/panel/labels, and assert no subprocess is invoked.
- The subprocess invocation and JSON-summary parsing are tested with a mocked `subprocess.run`, following the existing mocking pattern already used for other headless-Claude-invocation call sites in this codebase's test suite.
- The GH Actions workflow itself is validated by a manual `workflow_dispatch` run against a real (or scoped-down) config before the first scheduled cron fire, rather than by automated CI — consistent with how `support-engineer.yml` was validated.
