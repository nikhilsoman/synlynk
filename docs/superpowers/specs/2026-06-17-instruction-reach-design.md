# Instruction Reach Design — v0.4.1

**Release slot:** v0.4.1  
**Goal:** Extend synlynk's instruction generation to all major AI tools (Cursor, Copilot, Windsurf) using tool-native formats, append to existing files without overwriting user content, and detect drift in the synlynk-authored sections via a manifest + sentinel extension.

**Architecture:** Three layers — init-time generation (write tool-native instruction blocks into all target files, store SHA manifest), runtime drift detection (hash-check on every `exec`, fire `INSTRUCTION_DRIFT` sentinel on mismatch), and on-demand review (`synlynk instructions status/diff/update`).

**Tech stack:** Python 3 stdlib only. No new dependencies. Extends `bin/synlynk.py` in-place.

---

## 1. AGY / Gemini Cleanup (prerequisite)

These changes land in v0.4.1 since they unblock correct AGY detection.

- Remove `"gemini"` entry from `AGENT_CAPABILITY_BASELINES` and `AGENT_DISCOVERY_DEFAULTS` — Gemini CLI is EOL'd as of 2026-06-18.
- `GEMINI.md` continues to be generated for `agy` (the `_agent_guards` mapping `"GEMINI.md": "agy"` is unchanged).
- Update `GEMINI.md` template:
  - Remove the transition-date note (`"AGY CLI is the sole consumer after 2026-06-18..."`)
  - Change engine label from `gemini-2.x / agy-2.x` → `agy-2.x`
- `AGENT_DISCOVERY_DEFAULTS["agy"]` stays at `~/.agy`.

---

## 2. Instruction File Targets

Seven files are tracked. Detection method determines whether a file is written at `synlynk init`:

| File | Tool | Detection | Marker syntax |
|---|---|---|---|
| `CLAUDE.md` | Claude Code | `claude --version` succeeds | `<!-- synlynk:start -->` |
| `GEMINI.md` | AGY | `agy --version` succeeds | `<!-- synlynk:start -->` |
| `AGENTS.md` | Codex | `codex --version` succeeds | `<!-- synlynk:start -->` |
| `.cursor/rules/synlynk.mdc` | Cursor | `.cursor/` directory exists | entire file (no markers) |
| `.github/copilot-instructions.md` | Copilot | `.github/` directory exists | `<!-- synlynk:start -->` |
| `.windsurfrules` | Windsurf | always | `# synlynk:start` |
| `AI_INSTRUCTIONS.md` | Universal | always | `<!-- synlynk:start -->` |

The three core-trio files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) retain their existing agent-discovery guards — they are only written if the corresponding agent CLI is detected as functional.

The four extended files (`synlynk.mdc`, `copilot-instructions.md`, `.windsurfrules`, `AI_INSTRUCTIONS.md`) are written whenever the detection condition is met, regardless of which agent CLIs are installed.

---

## 3. Section Marker Format

### Markdown files (all except `.windsurfrules`)

```markdown
<!-- synlynk:start version="0.4.1" tool="claude" -->
... synlynk-generated content ...
<!-- synlynk:end -->
```

### `.windsurfrules`

```
# synlynk:start version="0.4.1"
... synlynk-generated content ...
# synlynk:end
```

### `.cursor/rules/synlynk.mdc`

No markers — synlynk owns the entire file. The file itself is the boundary.

### Behaviour on existing files

1. If the file does not exist: write the synlynk block (with markers). No preamble.
2. If the file exists with no synlynk markers: append the synlynk block at the end. User content above is preserved verbatim.
3. If the file exists with synlynk markers: replace only the content between the markers. User content outside the markers is untouched.

`synlynk init` writes files on first run. `synlynk init --force` does NOT re-generate instruction files — `synlynk instructions update` is the deliberate re-generation path.

---

## 4. Manifest

Written to `.synlynk/instructions.json` after every `synlynk init` or `synlynk instructions update`.

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-17T10:00:00",
  "synlynk_version": "0.4.1",
  "files": {
    "CLAUDE.md": {
      "tool": "claude",
      "sha": "<sha256 of synlynk section content only>",
      "last_checked": "2026-06-17T10:00:00"
    },
    "GEMINI.md":                       { "tool": "agy",      "sha": "...", "last_checked": "..." },
    "AGENTS.md":                       { "tool": "codex",    "sha": "...", "last_checked": "..." },
    ".cursor/rules/synlynk.mdc":       { "tool": "cursor",   "sha": "...", "last_checked": "..." },
    ".github/copilot-instructions.md": { "tool": "copilot",  "sha": "...", "last_checked": "..." },
    ".windsurfrules":                  { "tool": "windsurf", "sha": "...", "last_checked": "..." },
    "AI_INSTRUCTIONS.md":              { "tool": "universal","sha": "...", "last_checked": "..." }
  }
}
```

SHA is computed over the synlynk section content only (the text between the markers, not the markers themselves, not content outside). For `.cursor/rules/synlynk.mdc` the SHA covers the entire file content. This ensures user edits outside the synlynk block do not trigger false drift events.

---

## 5. Tool-Native Content

### `CLAUDE.md` and `AGENTS.md`
Existing template content unchanged. Markers added around the synlynk-generated block.

### `GEMINI.md`
Same structure as `CLAUDE.md` after AGY cleanup (section 1). Engine line: `- **Engine:** agy-2.x`.

### `.cursor/rules/synlynk.mdc`
Cursor MDC format with frontmatter. Full file:

```markdown
---
description: synlynk project protocol — session start, task tracking, git discipline
alwaysApply: true
---

# synlynk Protocol

## Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

## During Session
- Mark tasks `[x]` in `project-docs/todo.md` when complete — do not delete them
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a worktree for every feature or fix:
\```
git worktree add .worktrees/<name> feat/<name>
git branch --show-current   # confirm before every commit
\```

## At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
```

### `.github/copilot-instructions.md`
Plain markdown, no frontmatter (Copilot does not support it). Synlynk block appended at end of file. Content mirrors the universal session protocol (same as `AI_INSTRUCTIONS.md` but without the GitHub Projects GraphQL block, which is not relevant in Copilot context).

### `.windsurfrules`
Terse, directive-only format matching Windsurf convention:

```
# synlynk:start version="0.4.1"
Read .synlynk/context.md at session start.
Mark tasks [x] in project-docs/todo.md when complete.
Run `synlynk checkpoint` at task boundaries.
Never commit directly to main or master — use a worktree.
Append decisions to project-docs/memory.md with [@username].
# synlynk:end
```

### `AI_INSTRUCTIONS.md`
Unchanged content from current template. Markers added. Always written.

---

## 6. Learning from Existing Instructions

When reading an existing file before writing, synlynk extracts the **non-synlynk content** (everything outside the markers, or the full file if no markers present). This content is:

1. **Preserved in place** — never modified.
2. **Surfaced in `synlynk instructions diff`** — shown alongside the synlynk section so the developer can compare and decide if any user/tool patterns are worth absorbing into the template.
3. **Never automatically merged** — absorption is a deliberate human step. No LLM involvement in the learning loop.

The intent: if a team member has evolved their Cursor rules or Copilot instructions to capture something valuable that synlynk's template doesn't yet know about, it surfaces visibly. The developer decides what to pull upstream into the template.

---

## 7. Sentinel Extension: `INSTRUCTION_DRIFT`

### `_check_instruction_drift()`

New function called inside `exec_command()` alongside existing sentinel checks.

```python
def _check_instruction_drift() -> list[str]:
    """Returns list of drifted file paths. Fires INSTRUCTION_DRIFT sentinel entries."""
```

Logic:
1. Load `.synlynk/instructions.json`. If absent, return immediately (not yet initialised).
2. For each tracked file in the manifest:
   - If file does not exist on disk: skip (user may have deliberately removed it).
   - Extract synlynk section content using marker regex.
   - Compute SHA256 of section content.
   - Compare to manifest SHA. On mismatch: record drift.
3. For each drifted file: append to `sentinel.md` and `telemetry.json`. Update `last_checked` in manifest.

### Sentinel entry format

```
## ⚠ INSTRUCTION_DRIFT — Sev2 [2026-06-17T10:23:00]
File: CLAUDE.md (tool: claude)
Synlynk section modified externally since last init/update.
Run `synlynk instructions diff CLAUDE.md` to review.
Run `synlynk instructions update CLAUDE.md` to re-generate and reset.
[ack: synlynk instructions ack CLAUDE.md]
```

**Severity:** Sev2. The product works — agents still receive instructions — but the synlynk section may have diverged from the current template. No data loss.

**Deduplication:** once an `INSTRUCTION_DRIFT` event is fired for a file, it is not re-fired until the SHA changes again or the user runs `synlynk instructions update` (which resets the manifest SHA).

---

## 8. `synlynk instructions` CLI

Three subcommands wired under `synlynk instructions <subcommand>`:

### `synlynk instructions status`

```
File                               Tool       Status         Last checked
─────────────────────────────────────────────────────────────────────────
CLAUDE.md                          claude     ✓ clean        2026-06-17
GEMINI.md                          agy        ✓ clean        2026-06-17
AGENTS.md                          codex      ✓ clean        2026-06-17
.cursor/rules/synlynk.mdc          cursor     ✓ clean        2026-06-17
.github/copilot-instructions.md    copilot    + user-content 2026-06-17
.windsurfrules                     windsurf   ⚠ drifted      2026-06-17
AI_INSTRUCTIONS.md                 universal  ✓ clean        2026-06-17
```

Status values:
- `✓ clean` — synlynk section matches manifest SHA
- `⚠ drifted` — synlynk section SHA differs from manifest
- `+ user-content` — file has content outside the synlynk markers (informational, not an error)
- `✗ missing` — tracked file not found on disk

### `synlynk instructions diff [file]`

Shows two things per file:
1. **Synlynk section diff** — if drifted, a unified diff of current section vs manifest SHA baseline
2. **User/tool content** — any content outside the synlynk markers, printed verbatim for review

No file argument: runs across all tracked files.

### `synlynk instructions update [file]`

Re-generates the synlynk section for the specified file (or all files), replaces content between markers, writes updated SHAs to manifest. Preserves all content outside markers. Does not re-run agent discovery or static scan.

### `synlynk instructions ack <file>`

Acknowledges a drift event for a specific file. Suppresses re-firing until the SHA changes again. Records the ack in `telemetry.json` (consistent with existing ack pattern in sentinel system).

---

## 9. `_write_instruction_file()` — Core Helper

New internal function replacing the current direct template writes in `init()`:

```python
def _write_instruction_file(
    path: str,
    tool: str,
    content: str,
    marker_style: str = "html",   # "html" | "hash" | "none"
    skip_existing: bool = True,
) -> bool:
    """
    Writes or appends a synlynk instruction block to path.
    Returns True if file was written/updated, False if skipped.

    marker_style="none": whole file is synlynk-owned (Cursor .mdc).
    marker_style="html": <!-- synlynk:start --> ... <!-- synlynk:end -->
    marker_style="hash": # synlynk:start ... # synlynk:end
    """
```

This function is called by `init()` for each target file and by `cmd_instructions_update()`. It handles all three write modes (create / append / replace-section).

---

## 10. Testing

New tests in `tests/test_instruction_reach.py`:

- `test_init_writes_cursor_rules_when_cursor_dir_exists` — creates `.cursor/` dir, runs init, verifies `.cursor/rules/synlynk.mdc` created
- `test_init_skips_cursor_when_no_cursor_dir` — no `.cursor/` dir, verifies file not written
- `test_init_appends_to_existing_copilot_instructions` — pre-existing `.github/copilot-instructions.md`, verifies synlynk block appended and original content preserved
- `test_init_replaces_synlynk_section_on_reinit` — file with existing synlynk markers, runs init again, verifies only the synlynk section is replaced
- `test_manifest_written_after_init` — verifies `.synlynk/instructions.json` exists with correct schema after init
- `test_manifest_sha_covers_only_synlynk_section` — user content outside markers does not change the manifest SHA
- `test_check_instruction_drift_detects_section_change` — modify synlynk section externally, verify drift detected
- `test_check_instruction_drift_ignores_user_content_change` — modify content outside markers, verify no drift
- `test_instruction_drift_sentinel_fires_once_per_change` — verify deduplication: second exec with same SHA does not re-fire
- `test_cmd_instructions_update_replaces_section` — verify update re-generates section and resets manifest SHA
- `test_cmd_instructions_ack_suppresses_sentinel` — verify ack prevents re-firing
- `test_agy_baseline_replaces_gemini` — verify `gemini` no longer in `AGENT_CAPABILITY_BASELINES`
- `test_gemini_md_template_has_no_transition_note` — verify template no longer contains the `2026-06-18` string
