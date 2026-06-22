# Release Agent Design Spec

**Date:** 2026-06-22  
**Status:** Approved for implementation  
**Target release:** v0.8.2 (part of Agent Ecosystem Epic v0.8.1–v0.8.4)  

---

## Problem

synlynk's release process is ad-hoc: manually bump `VERSION` in two files, run tests, tag, push, update the installed binary. No changelog generation, no GitHub Release, no blog post trigger. Steps are forgotten under time pressure and there is no record of what was done.

## Goal

A config-driven release pipeline that:
- detects when a release is ready (cron + on-demand)
- surfaces a suggestion with version, changelog, and step plan for human review
- executes the approved pipeline step by step with per-step consent control
- is fully configurable at the repo level without code changes

---

## Architecture

Three concerns with clean boundaries:

```
Detection        →   Suggestion        →   Execution
─────────────────    ─────────────────     ──────────────────────────────
Reads roadmap        Presents version,     Walks steps in config order.
+ git state.         changelog, step       Per-step: auto-run, notify,
Determines if        plan. Writes          or block for human approval.
a release is         release-state.json.   State persisted — resumable
ready.               Waits for human       across cron invocations.
                     to trigger run.
```

**Config-as-SOP:** `project-docs/release-agent.json` is the source of truth. It defines which steps exist, their order, executor type, and consent level. The SOP is versioned with the repo and editable without touching code.

**Runtime state:** `.synlynk/release-state.json` (gitignored) tracks the in-flight release: target version, per-step status, generated changelog path. Makes the pipeline resumable — cron re-invocations skip completed steps.

---

## Command Surface

```
synlynk release suggest           # detect readiness + present plan (also called by cron)
synlynk release run               # execute pipeline from current state
synlynk release run --step <id>   # run a single named step
synlynk release status            # show step completion table
synlynk release --install-cron    # register cron job via existing agent-run infrastructure
```

---

## Release Config Schema

**Path:** `project-docs/release-agent.json`

```json
{
  "release_agent": {
    "cron": "0 9 * * 1",
    "version_files": [
      {"path": "synlynk/__init__.py", "pattern": "VERSION = \"{version}\""},
      {"path": "install.sh",          "pattern": "VERSION=\"{version}\""}
    ],
    "changelog_source": "git_log",
    "steps": [
      {
        "id": "run_tests",
        "name": "Run full test suite",
        "executor": "shell",
        "command": "python -m pytest tests/ -q",
        "consent": "auto",
        "fail_blocks_release": true
      },
      {
        "id": "bump_version",
        "name": "Bump VERSION to {version}",
        "executor": "synlynk",
        "command": "release _bump-version",
        "consent": "approve"
      },
      {
        "id": "git_tag",
        "name": "Tag and push v{version}",
        "executor": "shell",
        "command": "git tag v{version} && git push origin main --tags",
        "consent": "approve"
      },
      {
        "id": "github_release",
        "name": "Create GitHub Release",
        "executor": "shell",
        "command": "gh release create v{version} --title 'synlynk v{version}' --notes-file .synlynk/release-notes.md",
        "consent": "approve"
      },
      {
        "id": "update_binary",
        "name": "Update installed binary",
        "executor": "shell",
        "command": "./install.sh",
        "consent": "notify"
      },
      {
        "id": "blog_post",
        "name": "Draft blog post via Marketing Intern",
        "executor": "agent",
        "agent": "marketing-intern",
        "prompt_template": "docs/superpowers/prompts/release-blog-prompt.md",
        "consent": "approve",
        "output_file": "docs/blog/{date}-release-{version}.md"
      }
    ]
  }
}
```

### Field reference

| Field | Type | Description |
|---|---|---|
| `cron` | string | Cron expression for readiness check schedule |
| `version_files` | array | Files to rewrite on version bump. `pattern` uses `{version}` placeholder |
| `changelog_source` | string | `git_log` (only supported value in v0.9.3) |
| `steps[].id` | string | Stable identifier, used by `--step` flag and state tracking |
| `steps[].executor` | string | `shell`, `synlynk`, or `agent` |
| `steps[].command` | string | Command string; `{version}`, `{date}`, `{changelog}` interpolated at runtime |
| `steps[].consent` | string | `auto`, `notify`, or `approve` |
| `steps[].fail_blocks_release` | bool | If true, pipeline aborts on non-zero exit even for `auto` steps |
| `steps[].prompt_template` | string | For `agent` executor: path to markdown prompt file |
| `steps[].output_file` | string | For `agent` executor: where to write agent output |

---

## Readiness Detection

Two signals must both be true for the agent to suggest a release:

1. **Version gap** — `VERSION` string in `synlynk/__init__.py` (read directly, not via import) is strictly less than the version marked with `🔜` in `project-docs/roadmap.md`. Roadmap version extracted with regex on the version table.

2. **Commits since last tag** — `git log v{last_tag}..HEAD --oneline` returns at least one commit. If there are no commits since the last tag, there is nothing to release regardless of the version gap.

The agent does **not** verify that individual feature branches are merged. The human is the authority on readiness. The agent's role is to notice the version gap and new commits, surface the suggestion, and wait.

### Changelog generation

When `changelog_source: "git_log"`, the agent runs:

```bash
git log v{last_tag}..HEAD --pretty="format:- %s" --no-merges
```

Merge commits are excluded (too noisy). Output written to `.synlynk/release-notes.md` for human review. The `github_release` step reads from this file — if the human edits it before approving that step, the edited version is used.

---

## Consent Mechanics

Each step's `consent` level determines runtime behaviour:

| Level | Interactive (`synlynk release run`) | Non-interactive (cron) |
|---|---|---|
| `auto` | Runs immediately, prints result | Runs immediately |
| `notify` | Runs immediately, prints `✓ [step] done` | Writes completion notice to `sentinel.md` |
| `approve` | Prints step details + `[y/N]` prompt, blocks | Writes pending notice to `sentinel.md`, halts pipeline |

### Sentinel notices (cron mode)

When a step requires approval and the pipeline is running non-interactively, the agent writes to `sentinel.md`:

```
⏳ RELEASE v0.9.2 — waiting approval: bump_version
   Review: cat .synlynk/release-notes.md
   Approve: synlynk release run --step bump_version
```

The human sees this at next `synlynk checkpoint` and acts on it. Subsequent cron runs skip completed steps and check for unblocked pending steps.

---

## Pipeline State

**Path:** `.synlynk/release-state.json` (gitignored)

```json
{
  "version": "0.9.2",
  "detected_at": "2026-06-22T09:00:00",
  "last_tag": "v0.9.1",
  "changelog_path": ".synlynk/release-notes.md",
  "steps": {
    "run_tests":      {"status": "done",    "completed_at": "2026-06-22T09:01:12"},
    "bump_version":   {"status": "pending", "completed_at": null},
    "git_tag":        {"status": "pending", "completed_at": null},
    "github_release": {"status": "pending", "completed_at": null},
    "update_binary":  {"status": "pending", "completed_at": null},
    "blog_post":      {"status": "pending", "completed_at": null}
  }
}
```

Step statuses: `pending` → `approved` (for approve-consent steps, after human confirms) → `done` or `failed`.

A `fail_blocks_release: true` failure sets all subsequent steps back to `pending` and writes a failure notice to `sentinel.md`. The pipeline can be resumed after the root cause is fixed.

---

## Executor Types

### `shell`
Runs `command` via `subprocess.run(shell=True)` with `{version}`, `{date}`, `{changelog}` interpolated. Stdout/stderr captured. Non-zero exit = failure.

### `synlynk`
Calls an internal `cmd_*` function directly (no subprocess). Used for the `bump_version` step to rewrite version files in-process using the `version_files` config, avoiding shell quoting issues with regex patterns.

### `agent`
Calls `_run_agent_sync(agent, prompt, timeout=300)` (already implemented in v0.9.2). Prompt is read from `prompt_template` file, with `{version}`, `{changelog}`, `{date}` interpolated. Output written to `output_file`.

---

## Cron Integration

`synlynk release --install-cron` registers a cron entry using the existing `_install_cron_entry()` pattern (same as `synlynk agent run --install-cron`). The cron job calls `synlynk release suggest`, which:

1. Runs readiness detection
2. If not ready: exits silently
3. If ready and no in-flight release: writes `release-state.json`, appends suggestion to `sentinel.md`
4. If in-flight release with pending `approve` steps: re-emits the pending notice to `sentinel.md` (idempotent)
5. If in-flight release with no pending steps: does nothing (pipeline complete)

---

## Files Changed

| File | Change |
|---|---|
| `synlynk/__init__.py` | `cmd_release_suggest()`, `cmd_release_run()`, `cmd_release_status()`, `_release_detect_readiness()`, `_release_bump_version()`, `_release_load_config()`, `_release_run_step()`, argparse `release` subcommand |
| `tests/test_synlynk.py` | New tests for all release functions |
| `project-docs/release-agent.json` | Default release config (created by `synlynk init` for new projects, manually added for existing ones) |
| `docs/superpowers/prompts/release-blog-prompt.md` | Blog post prompt template for the `blog_post` agent step |

---

## What Is Not In Scope (v0.9.3)

- **Social posting** — Marketing Intern blog draft is the extent of content automation. Actual publishing to external platforms is a future step (requires platform API keys in Secrets Manager, not in stdlib scope).
- **PR-based release flow** — bump commit goes directly to main. A PR-based flow is a future option configurable per repo.
- **Multi-repo releases** — single repo only.
- **Rollback** — no automated rollback on failure. Human resolves and resumes.
