# Support Engineer Agent — Design Spec

**Date:** 2026-06-21  
**Status:** Approved for implementation  
**Version target:** v0.8.0  
**Scope:** Definition B, Phase 1 of 3 (Support Engineer → PM Agent → Marketing Intern)

---

## Goal

Implement the Support Engineer — a broad health monitor that collects signals from multiple sources (test suite, sentinel alerts, telemetry, capability ledger, GitHub issues), dispatches Claude/AGY to investigate findings, files GitHub issues with findings, and opens draft fix PRs for actionable regressions. Triggered by both GitHub Actions (push to main + schedule) and local crontab.

---

## Architecture

**Approach:** Agent config files (`.agents/<name>.yaml`) + `synlynk agent run <name>` engine command.

Each agent is a YAML config file. The engine reads the config, collects signals, deduplicates against `state.db`, and runs the investigation pipeline. PM Agent and Marketing Intern are future `.agents/` files — no engine changes needed to add them.

**New files:**
- `.agents/support.yaml` — Support Engineer persona and config
- `.github/workflows/support-engineer.yml` — GitHub Actions trigger

**Modified files:**
- `bin/synlynk.py` — `agent` subcommand + engine + signal collectors + `autopilot_runs` table
- `tests/test_synlynk.py` — ~15 new tests

---

## Agent Config Schema

`.agents/support.yaml`:

```yaml
name: support-engineer
description: Broad health monitor — tests, sentinel alerts, telemetry, capability ledger, GitHub issues
investigator: claude     # agent dispatched to investigate findings
fixer: claude            # agent dispatched to attempt fix PRs

signals:
  - type: test_suite
    command: "pytest tests/ -q --tb=short"
  - type: sentinel_alerts
    path: .synlynk/sentinel.md
  - type: telemetry_anomaly
    failure_rate_threshold: 0.30   # flag if >30% of last 20 sessions failed
  - type: capability_drop
    drop_threshold: 1.5            # flag if any agent's weighted score drops >1.5pts
  - type: github_issues
    labels: [bug, needs-triage]

hitl:
  auto_merge: false     # B mode — draft PRs only; flip to true for C mode
  auto_approve:
    - github.create_issue
    - github.create_draft_pr
    - synlynk.dispatch
```

The `hitl.auto_merge` field is the B→C upgrade toggle. No code changes needed to promote.

---

## Database: `autopilot_runs` Table

New table in `state.db`, created alongside existing tables in `_init_db()`:

```sql
CREATE TABLE IF NOT EXISTS autopilot_runs (
    id            TEXT PRIMARY KEY,
    agent_name    TEXT NOT NULL,
    signal_type   TEXT NOT NULL,
    signal_hash   TEXT NOT NULL,
    severity      TEXT NOT NULL,
    summary       TEXT NOT NULL,
    status        TEXT NOT NULL,
    gh_issue_url  TEXT,
    pr_url        TEXT,
    ts            TEXT NOT NULL
);
```

`signal_hash` = md5 of the finding's key fields (failure message, alert text, issue number, etc.). Used for deduplication: skip any finding whose hash appears in `autopilot_runs` with `ts > now - 7 days`.

---

## Signal Collectors

Each collector returns a list of `Finding` dicts: `{type, severity, summary, detail, signal_hash}`.

| Signal | Collection method | Severity logic |
|---|---|---|
| `test_suite` | `subprocess.run(["pytest", "tests/", "-q", "--tb=short"])` | Any failure → `high` |
| `sentinel_alerts` | Read `.synlynk/sentinel.md`, extract lines starting with `⚠` | FLATLINE/QUOTA_EXHAUSTED → `high`, others → `medium` |
| `telemetry_anomaly` | Read `.synlynk/telemetry.json`, compute failure rate over last 20 sessions | >60% → `high`, >30% → `medium` |
| `capability_drop` | Query `capability_ratings` for each agent, compute weighted average over last 7 days vs. prior 7 days. If either window has fewer than 2 ratings, skip (insufficient data). | Drop >3pts → `high`, >1.5pts → `medium` |
| `github_issues` | `gh issue list --label bug,needs-triage --json number,title,body,createdAt` | All new → `medium` |

**CI vs. local distinction**: `sentinel_alerts` and `telemetry_anomaly` require local `.synlynk/` state. When `GITHUB_ACTIONS=true`, these two collectors are skipped. `test_suite`, `capability_drop`, and `github_issues` run in both environments.

**Cap**: maximum 5 findings processed per run, highest severity first. Additional findings are logged to the run summary but not investigated — prevents runaway dispatch cost on catastrophic days.

---

## Investigation Pipeline

For each new finding (not in dedup window):

**1. Create story**
```python
story_id = f"support-{signal_type}-{signal_hash[:8]}"
cmd_story_create(title=summary, engg_domain="test", phase="scale")
```

**2. Build prompt**
Three parts concatenated:
- Signal context: raw finding detail (pytest output, sentinel text, telemetry stats, etc.)
- Project context: `generate_context()` output (memory, roadmap, source architecture)
- Task: "Identify root cause. If a code fix is possible, describe it with exact file path and line numbers. If not fixable, summarise the investigation findings."

**3. Dispatch investigator** (foreground, 5-minute timeout)

The engine calls `dispatch_agent()` directly in Python (not via subprocess) and polls the job log file until the process exits or timeout is reached. This is distinct from background dispatch — the engine blocks here so the log output is available before proceeding to step 4.

**4. Parse output**
- First 500 chars → GitHub issue body summary
- Presence of unified diff block or `# FIX:` marker → triggers fix step

**5. File GitHub issue**
```
gh issue create --title "[support] <signal_type>: <summary>" \
  --body "<investigation findings>" \
  --label "bug,support-engineer"
```
Issue URL stored in `autopilot_runs.gh_issue_url`. Row status set to `filed`.

**6. Attempt fix** (if fix signal present)
- Dispatch fixer agent with investigation output + instruction to produce minimal diff
- Capture stdout, extract unified diff block
- `git apply <diff>` in a temp branch `support/fix-<signal_hash[:8]>`
- Run `pytest tests/ -q --tb=no`
- **Tests pass**: `gh pr create --draft --title "[support] fix: <summary>" --body "<diff + investigation link>"`; status → `fix_attempted`, `pr_url` stored
- **Tests fail**: post comment on the GitHub issue with the attempted diff and failure output; status → `fix_failed`

---

## Run Summary

After each `synlynk agent run support` invocation, append to `project-docs/devlogs/support-engineer.md`:

```
2026-06-21T14:00:00 · 2 findings (1 high, 1 medium) · 1 filed · 1 fix_attempted · run-a3f2b1
```

---

## Triggers

**GitHub Actions** (`.github/workflows/support-engineer.yml`):

```yaml
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'

jobs:
  support-engineer:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pytest
      - run: python3 bin/synlynk.py agent run support
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Local crontab** (installed via `synlynk agent run support --install-cron`):
```
0 */6 * * * cd /path/to/repo && python3 bin/synlynk.py agent run support >> ~/.synlynk/autopilot.log 2>&1
```

`--install-cron` reads current crontab, appends the entry if not present (idempotent), writes back via `crontab -`.

---

## `synlynk agent` Subcommand

New subcommand added to `main()`:

```
synlynk agent run <name>          # run named agent once
synlynk agent run <name> --dry-run  # collect signals, print findings, no dispatch/issue/PR
synlynk agent run <name> --install-cron  # install local crontab entry
synlynk agent list                 # list .agents/ config files and their last run status
```

Config file loaded from `.agents/<name>.yaml`. Raises a clear error if file not found.

---

## Tests (~15 new)

**Signal collectors:**
- `test_collect_test_suite_high_on_failure` — mock subprocess failure, assert `severity=high`
- `test_collect_test_suite_no_finding_on_pass` — mock passing pytest, assert empty list
- `test_collect_sentinel_alerts_flatline` — write sentinel.md with `⚠ FLATLINE`, assert `severity=high`
- `test_collect_sentinel_alerts_empty` — no `⚠` lines, assert empty list
- `test_collect_telemetry_anomaly_medium` — 40% failure rate, assert `severity=medium`
- `test_collect_telemetry_anomaly_no_finding` — 10% failure rate, assert empty
- `test_collect_github_issues` — mock `gh issue list` JSON output, assert one finding per issue

**Deduplication:**
- `test_dedup_skips_recent_signal` — insert matching row 3 days old, assert skipped
- `test_dedup_reinvestigates_after_7_days` — same row 8 days old, assert finding returned

**Engine flow:**
- `test_agent_run_files_issue_on_test_failure` — mock failure signal + `gh issue create`, assert `autopilot_runs` row with `status=filed`
- `test_agent_run_opens_draft_pr_on_fix_signal` — mock investigation log with `# FIX:` + passing tests, assert `gh pr create --draft` called
- `test_agent_run_fix_failed_comments_on_issue` — mock fix that fails tests, assert `gh issue comment` called
- `test_agent_run_dry_run_no_side_effects` — assert no `gh` calls, no DB writes in `--dry-run`
- `test_install_cron_idempotent` — call twice, assert entry appears exactly once

**Agent config:**
- `test_agent_run_unknown_agent_raises` — `synlynk agent run nonexistent`, assert clean error

---

## Future Agents

Adding PM Agent or Marketing Intern = create `.agents/pm.yaml` or `.agents/marketing.yaml`. The engine is signal-type agnostic — new signal types are new collector functions registered by name. No engine changes for adding agents.

`auto_merge: true` in `.agents/support.yaml` promotes Support Engineer from B to C mode.
