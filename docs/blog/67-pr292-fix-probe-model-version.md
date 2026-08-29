---
title: "PR #292 — Fix Tier-2 Model Probe (#287)"
date: 2026-07-16
series: "Building the OS for Multi-Agent Development"
post: 67
pr: "#292"
merged: status open
---

## The Broader Goal at the End of the Previous PR

After v0.12.0 (Measurement & Reliability), model identity is a first-class ledger field: `model_at_dispatch` is probed before every job, capability ratings key on it, and cost rates resolve through `_model_rate_for_version()`. That only works if the Tier-2 probe actually returns a real model id.

## Strategic Shifts in This PR (if any)

None. This is a correctness fix for an existing measurement path — no API or roadmap change.

## What This PR Shipped

**Bug (#287):** `_probe_model_version()` shelled out to agent CLIs (`claude /status`, `agy --version`, `codex --version`, `grok -v`) and regex-scraped stdout. Live results:

| Agent | Before | Root cause |
|---|---|---|
| claude | `unknown` | `/status` is interactive-only |
| agy | `unknown` | `--version` is CLI version, not model |
| codex | `codex-cli` | matched CLI *name*, not `model` |
| grok | `unknown` | `-v` is CLI version, not model |

**Fix:** read each agent's own home config instead of shelling out:

- **codex** → `~/.codex/config.toml` top-level `model`
- **grok** → `~/.grok/config.toml` `[models] default`
- **claude** → `~/.claude/settings.json` `model` key; absent → `"uses Claude Code's built-in default, no override"`
- **agy** → `"session-scoped, no fixed default"` (no persistent model file)

Helper `_read_toml_string_value()` is stdlib-only: tries `tomllib` when present (3.11+), falls back to a small section/key regex so 3.8–3.10 CI stays green.

**Tests:** config-file cases in `tests/test_probe.py`; obsolete subprocess-scrape tests in `test_capability_scoring.py` and `test_synlynk.py` rewritten.

Live verification after the fix: `codex → gpt-5.4-mini`, `grok → grok-build`, `claude → built-in default`, `agy → session-scoped`.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Dispatch telemetry and capability scoring stop collapsing three of four agents into `model_version='unknown'`. Accurate `model_at_dispatch` is a prerequisite for trustworthy cost ledger rows, split-model detection, and any future routing that weights agents by model performance.

## Strategic Note: The Goal at the End of This PR

Tier-2 model identity is config-truthful. Follow-ons stay out of scope here: Tier-1 CLI-version parsing (separate bug), optional attenuation of the long descriptive strings for agy/claude if the ledger prefers short tokens, and ambient `synlynk probe` drift publish (BS-8).
