# Grok Agent Support — Design Spec

**Date:** 2026-06-26
**Status:** Approved for implementation
**Target version:** v0.9.7 (or next available slot after v0.9.6)

---

## Context

Grok is a Claude Code-compatible build harness by xAI that runs Cursor Composer and native Grok
models. Key characteristics discovered via `grok inspect`:

- Binary: `grok` (v0.2.67+)
- Auto-reads `CLAUDE.md` natively (listed as project instructions `[claude]`)
- Shares `.claude/settings.local.json` for permissions and skills
- Config dir: `~/.grok/`
- Non-interactive dispatch: `grok -p "<prompt>"`
- Auto-approve flag: `--always-approve`
- Fallback: `--permission-mode bypassPermissions`
- Structured output: `--output-format json` (token extraction)
- Models: `grok-composer-2.5-fast` (Cursor Composer 2.5 Fast, default), `grok-build`

This spec adds Grok as a first-class peer to claude/agy/codex — with its own instruction file,
capability baselines, context injection, and token extraction.

---

## Section 1: Agent Registration

### `AGENT_CAPABILITY_BASELINES`

Add entry alongside existing claude/agy/codex:

```python
"grok": {
    "cli": "grok",
    "non_interactive_flags": ["-p"],
    "dispatch_flags": ["--always-approve"],
    "roles": ["builder", "architect"],
    "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
}
```

### `AGENT_DISCOVERY_DEFAULTS`

```python
"grok": os.path.expanduser("~/.grok"),
```

### `agent_slots` default

Expand from three to four:

```python
{"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"}
```

Update all hardcoded `agent_slots` comment strings that reference the trio.

### Version probe

```python
"grok": [cli, "-v"],
```

Added to the probe dispatch dict in `_probe_model_version`. Parse output for a semver string.

---

## Section 2: Instruction File — `GROK.md`

### File management

`GROK.md` is a first-class synlynk-managed instruction file, identical in structure to
`CLAUDE.md` / `GEMINI.md` / `AGENTS.md`.

**`_KNOWN_INSTRUCTION_FILES` entry:**
```python
("GROK.md", "grok", "html", lambda: True),
```

**`_MARKER_STYLE_FOR_TOOL` entry:**
```python
"grok": "html",
```

**`_agent_guards` entry:**
```python
"GROK.md": "grok",
```

Only written during `synlynk init` when `grok` is in the selected agent set.

### Default `GROK.md` content (written by `synlynk init`)

```markdown
# GROK.md — Grok Session Guide

This file provides guidance to Grok when working in this repository.

<!-- synlynk:start version="{VERSION}" tool="grok" -->

## Identity

- **Commit trailer:** `Co-Authored-By: Grok <noreply@x.ai>`
- **Branch prefix:** `feat/<description>`, `fix/<description>`, `chore/<description>`

## Session Protocol

At session start: read `project-docs/todo.md` for the next task, check
`git branch --show-current` to confirm you are on a feature branch.

During session: update todo checkboxes, run tests before committing.

At session end: append a summary to `project-docs/devlogs/<username>.md`.

## Blog Post Protocol

For every PR, draft a blog post in `docs/blog/` before or immediately after
opening the PR. See `docs/blog/README.md` for the template.

<!-- synlynk:end -->
```

### `synlynk instructions update` for grok

`GROK.md` participates in the instruction manifest and drift detection the same
as other agent files. `synlynk instructions status` shows its sha and drift state.

---

## Section 3: Context Injection at Exec Time

### Headless dispatch (`synlynk exec grok` with prompt / `synlynk dispatch`)

Append both rules flags to the subprocess args:

```
grok -p "<prompt>" --rules GROK.md --rules .synlynk/context.md --always-approve
```

- `GROK.md` first: standing instructions (identity, session protocol, commit conventions)
- `.synlynk/context.md` second: live project state snapshot (roadmap, todos, memory)
- Both skipped silently if the file is absent — no error, Grok still gets `CLAUDE.md` via auto-read

### Interactive mode (`synlynk exec grok` without a prompt)

Append only `--rules GROK.md`:

```
grok --rules GROK.md
```

`.synlynk/context.md` is omitted in interactive mode — it can be large and disrupts the interactive
session. Grok auto-reads `CLAUDE.md` which already carries the synlynk-managed section.

### Fallback dispatch flag

If `.agents/grok.json` contains `"always_approve_unsupported": true`, replace `--always-approve`
with `--permission-mode bypassPermissions`. This future-proofs against Grok CLI version changes
that may drop the flag.

```json
// .agents/grok.json
{
  "model": "grok-composer-2.5-fast",
  "always_approve_unsupported": false
}
```

---

## Section 4: Token & Model Version Extraction

### Token extraction

Grok supports `--output-format json` for headless invocations. Append this flag in dispatch mode
to capture structured output. Add a Grok-specific pattern to `extract_tokens()`:

```python
# Grok JSON output — exact key names to be confirmed against live output during implementation
# Expected shape: {"usage": {"input_tokens": N, "output_tokens": N}, "model": "...", ...}
r'"input_tokens"\s*:\s*(\d+)',   # input
r'"output_tokens"\s*:\s*(\d+)',  # output
```

If keys are absent or JSON is malformed, fall back to `(0, 0)` — same silent fallback as all agents.

**Implementation note:** Before writing the extraction regex, run `grok -p "hello" --output-format
json` and inspect the actual JSON schema. Update the key names to match.

### Model version extraction — three-tier resolution

| Tier | Source | Mechanism |
|---|---|---|
| 1 | Completion output | Regex on `--output-format json` response — `"model"` key |
| 2 | Dispatch-time config | `.agents/grok.json` → `"model"` field |
| 3 | Global probe | `grok -v` output parsed for version string |

If all three miss → `model_version = "unknown"`, handled by existing `cmd_score_attest` flow.

### `--output-format json` injection scope

- **Headless / dispatch:** always append `--output-format json`
- **Interactive:** never append — JSON output in interactive sessions is noisy

---

## Section 5: `synlynk init` Wizard

Grok added as a fourth selectable agent in the init wizard, alongside claude/agy/codex.

When selected:
1. Creates `GROK.md` with default content and synlynk markers
2. Writes `.agents/grok.json` stub: `{"model": "grok-composer-2.5-fast", "always_approve_unsupported": false}`
3. Adds `"grok": "grok"` to `agent_slots` in `.synlynk/config.json`
4. Probes `grok -v` — prints `✓ grok <version> detected` or `⚠ grok not found (install to enable)`

---

## Section 6: Tests

| Test | What it verifies |
|---|---|
| `test_agent_capability_baselines_includes_grok` | grok entry present, correct flags, roles, strengths |
| `test_agent_discovery_defaults_includes_grok` | `~/.grok` in discovery defaults |
| `test_write_instruction_file_creates_grok_md` | `synlynk init` writes GROK.md with synlynk markers |
| `test_grok_md_default_content` | Default GROK.md contains commit trailer, session protocol |
| `test_exec_grok_headless_appends_rules_and_json` | `--rules GROK.md --rules .synlynk/context.md --always-approve --output-format json` in subprocess args |
| `test_exec_grok_interactive_omits_context_md` | Interactive mode: only `--rules GROK.md`, no context.md, no output-format |
| `test_exec_grok_skips_missing_rules_files` | No error when GROK.md or context.md absent |
| `test_probe_grok_version` | `grok -v` output parsed, version string extracted |
| `test_grok_dispatch_uses_always_approve` | `--always-approve` present in dispatch subprocess args |
| `test_grok_fallback_permission_mode` | `--permission-mode bypassPermissions` used when `always_approve_unsupported: true` |
| `test_extract_tokens_grok_json` | Token extraction from Grok JSON output (mocked) |
| `test_model_version_tier1_grok` | Model version extracted from completion JSON |
| `test_model_version_tier2_grok` | Model version read from `.agents/grok.json` |
| `test_model_version_tier3_grok` | Model version probed from `grok -v` |
| `test_init_wizard_adds_grok_to_agent_slots` | `agent_slots` includes `"grok": "grok"` after init with grok selected |

---

## Files Changed

| File | Change |
|---|---|
| `synlynk/__init__.py` | Add grok to `AGENT_CAPABILITY_BASELINES`, `AGENT_DISCOVERY_DEFAULTS`, `_KNOWN_INSTRUCTION_FILES`, `_MARKER_STYLE_FOR_TOOL`, `_agent_guards`, version probe dict, `agent_slots` default, exec context injection logic, token extraction patterns, model version tiers |
| `tests/test_synlynk.py` | 15 new tests covering all the above |

No new files beyond `GROK.md` (written by `synlynk init` at runtime, not committed to the synlynk repo itself).
