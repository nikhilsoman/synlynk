# BS-19 — synlynk launch: Extended FTUE + 6-Cycle SDLC Design

> **Status:** Design approved 2026-07-01  
> **Target release:** v0.11.0  
> **Author:** Nikhil Soman (brainstorm), Claude (spec)

---

## Problem

`synlynk init --wizard` completes and drops the user at a terminal prompt with a static command cheat sheet. There is no "now what?" — the user has been onboarded but has nothing to run, no frame for how to work, and no reason to believe their fleet of agents is useful yet. The tool's power is invisible until the user already knows how to use it.

## Goal

Close the gap between wizard completion and first productive work. Introduce the 6-cycle SDLC model as the conceptual frame for multi-agent development, and immediately surface 3-5 concrete first tasks tailored to the user's repo — each pre-wired with the right agent, prompt, and token budget estimate.

---

## The 6 Cycles

Rename the existing 6-cycle model throughout the codebase:

| Old name | New name | Colour token | Default agents |
|----------|----------|-------------|----------------|
| Dream | **Dream** | `#a78bfa` (purple) | claude |
| Plan | **Design** | `#60a5fa` (blue) | claude |
| Work | **Plan** | `#34d399` (green) | claude |
| Ship | **Build** | `#fbbf24` (yellow) | agy · codex · grok |
| Maintain | **Ship** | `#f87171` (red) | claude |
| Engage | **Sustain** | `#94a3b8` (slate) | all |

**Migration:** rename all `cycle_capability` table rows, `harness_verb_map` cycle values, and any cycle references in `_verb_cycle_map` from the old names to the new names. The DB migration runs in `_migrate_db()` via `UPDATE` statements wrapped in a try/except (idempotent).

---

## `synlynk launch` Command

### Invocation

```bash
synlynk launch           # show task selection screen
synlynk launch --dry-run  # print selected tasks without launching TUI
synlynk launch --list     # print task pool with trigger conditions (debug)
```

### Config flag

`.synlynk/config.json` gains one new key:

```json
{
  "auto_launch_after_wizard": true
}
```

Default: `true` for fresh installs (`synlynk init --wizard`). When true, `wizard_init()` calls `cmd_launch()` immediately after Screen 6 completes (before returning to the shell). The effect is seamless: wizard → launch feels like one continuous flow. Users who set `false` get the original Screen 6 exit with a "run `synlynk launch` to pick your first task" hint.

### Wizard Screen 6 update

`_wiz_screen_launch()` gains two changes:
1. Footer line: `  run synlynk launch to pick your first task` (shown regardless of config)
2. After `_wiz_read_key()`: if `auto_launch_after_wizard` is true, call `cmd_launch()` directly

---

## TUI: Three Screens

### Screen 1 — Task selection

**Header line:** workspace name · stack labels · topology · test count · installed agents

**Task cards (3–5 items):**

Each card shows:
```
[N]  Task title                                  [Cycle tag]
     One-line description. Agent leads.
     ~Xh  │  R 80K · W 8K · T 12
```

- Cycle tag is colour-coded (purple/blue/green/yellow/red/slate)
- Scan-triggered tasks show `⚡ scan found: <reason>` instead of the description line
- R/W/T values are constants from the template definition (not computed live)

**Footer:**
```
R read · W write · T tool calls · estimates based on task template
[1–N] pick   [?] cycles   [s] skip
```

**Keys:**
- `1`–`5` → go to Screen 2 (dispatch preview) for that task
- `?` → go to Screen 3 (cycles explainer)
- `s` / `q` / `Ctrl-C` → exit launch without dispatching

### Screen 2 — Dispatch preview

Shown after user presses a task number.

```
  ◆ Dispatch preview

  agent     claude
  cycle     Dream
  mode      full context
  est.      ~2h  │  R 80K · W 8K · T 12

  task prompt:
  ┌──────────────────────────────────────────────────────┐
  │ Review the architecture of synlynk (Python CLI,      │
  │ single repo). Identify: structural patterns in use,  │
  │ top 5 tech debt hotspots (name files + functions),   │
  │ component coupling risks, and 3 concrete improvement │
  │ opportunities with effort estimates. Write findings  │
  │ to .synlynk/project-docs/memory.md under             │
  │ "## Architecture Review 2026-07-01". Be specific.    │
  └──────────────────────────────────────────────────────┘

  [enter] dispatch now   [e] edit prompt   [esc] back to tasks
```

**Template variable substitution:** `{workspace}`, `{stack}`, `{date}`, `{repo_name}`, `{topology}`, `{test_count}` are filled from the scan result at render time. The box above shows a rendered example — the template uses `{var}` Python format syntax.

**[e] edit prompt:** drops the user into a single-line readline input pre-filled with the prompt text. User edits and presses enter to return to the preview with the modified prompt. The modified prompt is used for dispatch — it is not persisted back to the template.

**[enter]:** calls `dispatch_agent(agent, task=prompt, context_mode="full", story_id=None)` and prints the standard dispatch confirmation line, then exits.

### Screen 3 — Cycles explainer (`[?]`)

Replaces Screen 1 temporarily. Any key returns to Screen 1.

```
  ◆ The 6 cycles — your multi-agent SDLC

  Dream    What's worth building? Ideate, assess, identify opportunities.  → claude
  Design   Brainstorm → spec → UX. Turn ideas into a concrete brief.       → claude
  Plan     Implementation plan, story breakdown, agent wave schedule.      → claude
  Build    Dispatch agents, run jobs, iterate on diffs.                    → agy · codex · grok
  Ship     Cut release, changelog, publish.                                → claude
  Sustain  Monitor, patch, community, docs, support.                       → all agents

  Tasks in synlynk launch are tagged to the cycle they open. Any cycle can dispatch any agent.

  [any key] back to tasks
```

---

## Task Template Pool

12 templates. Each template defines: `id`, `title`, `description`, `cycle`, `agent`, `context_mode`, `prompt_template`, `est_hours`, `r_tokens`, `w_tokens`, `tool_calls`, `trigger_condition`.

**Core templates (always shown — every new synlynk user starts here):**

| id | title | cycle | agent | est | R | W | T |
|----|-------|-------|-------|-----|---|---|---|
| `arch-review` | Workspace architecture review | Dream | claude | 2h | 80K | 8K | 12 |
| `product-assessment` | Product + opportunity assessment | Dream | claude | 1h | 40K | 6K | 8 |
| `lifecycle-setup` | Set up 6-cycle workflow for this repo | Plan | claude | 30m | 15K | 3K | 6 |

**Scan-triggered templates (shown only when condition matches):**

| id | title | cycle | agent | trigger condition |
|----|-------|-------|-------|-------------------|
| `add-tests` | Add test coverage | Plan | agy | `test_ratio < 0.1` (test files / total source files) |
| `setup-ci` | Set up CI/CD pipeline | Plan | codex | no `.github/workflows/` and no `.gitlab-ci.yml` |
| `docs-audit` | Documentation audit + gap fill | Design | agy | no `docs/` dir or README word count < 200 |
| `security-scan` | Dependency security scan | Dream | claude | `requirements.txt` or `package.json` or `Gemfile` present |
| `perf-baseline` | Performance baseline + profiling plan | Dream | claude | web stack detected (next/fastapi/django/express/flask) |
| `cross-repo-map` | Cross-repo dependency map | Dream | claude | topology = `mono` or `multi` |
| `type-safety` | Add type annotations to public API | Design | codex | Python repo + no `.pyi` stubs + `type_hint_ratio < 0.3` |
| `a11y-audit` | Accessibility audit | Design | agy | frontend stack (react/next/vue/svelte/angular) |
| `db-schema-review` | Database schema review | Dream | claude | ORM detected (sqlalchemy/prisma/django-orm/activerecord) |

**Selection algorithm:**

```python
def _select_launch_tasks(scan: dict) -> list[dict]:
    eligible = [t for t in TASK_TEMPLATES if _template_matches(t, scan)]
    # Core 3 always first (if eligible)
    core = [t for t in eligible if t["id"] in CORE_TEMPLATE_IDS]
    bonus = [t for t in eligible if t["id"] not in CORE_TEMPLATE_IDS]
    # Cap at 5 total; bonus tasks sorted by trigger specificity (more specific = higher priority)
    return (core + bonus)[:5]
```

`_template_matches(template, scan)` evaluates the trigger condition against scan fields: `stack_labels`, `topology`, `test_ratio`, `has_ci`, `readme_word_count`, `has_docs`, `has_type_hints`, `has_orm`.

**`scan` additions required:** `test_ratio` (float), `readme_word_count` (int), `has_ci` (bool), `has_docs` (bool), `has_type_hints` (bool — Python only), `has_orm` (bool). These are cheap file-presence checks added to `run_workspace_scan()`.

---

## Prompt Template Variables

Each `prompt_template` string may contain:

| Variable | Source |
|----------|--------|
| `{workspace}` | `scan["workspace_name"]` |
| `{stack}` | `", ".join(scan["stack_labels"])` |
| `{repo_name}` | primary repo name from scan |
| `{topology}` | single / mono / multi |
| `{test_count}` | total test count from state.db or scan |
| `{date}` | `datetime.date.today().isoformat()` |
| `{agent}` | template's default agent name |

Example — `arch-review` prompt template:
```
Review the architecture of {workspace} ({stack}, {topology} repo).
Identify: structural patterns in use, top 5 tech debt hotspots (name files
and functions), component coupling risks, and 3 concrete improvement
opportunities with effort estimates. Write your findings as a new section
in .synlynk/project-docs/memory.md under "## Architecture Review {date}".
Be specific — no generic advice.
```

---

## Data Model

No new DB tables required. `cmd_launch()` is a pure read + dispatch operation:
- Reads scan data from state.db (`workspace` table + `repos` table) if available; falls back to calling `run_workspace_scan()` if not yet scanned
- Dispatches via existing `dispatch_agent()` function
- The dispatched job appears in `jobs` table as normal

**Template storage:** templates are defined as a module-level constant `LAUNCH_TASK_TEMPLATES` (list of dicts) in `synlynk/__init__.py`. No DB table needed — templates don't change at runtime.

---

## Config Schema Addition

`load_config()` gains one new default key:

```python
defaults = {
    ...existing keys...,
    "auto_launch_after_wizard": True,
}
```

`write_workspace_config()` (called by wizard on Screen 6 completion) writes `auto_launch_after_wizard: true` into `.synlynk/config.json` for new installs.

---

## Implementation Scope

**Files modified:**
- `synlynk/__init__.py` — all changes (new constant, new functions, DB migration update, wizard Screen 6 update, CLI parser, dispatch)
- `tests/test_launch.py` — new test file

**New functions:**
| Function | Responsibility |
|----------|---------------|
| `LAUNCH_TASK_TEMPLATES` | Module-level constant: list of 12 template dicts |
| `_template_matches(template, scan)` | Evaluates trigger condition; returns bool |
| `_select_launch_tasks(scan)` | Returns ordered list of 3–5 matching templates |
| `_render_prompt(template, scan)` | Substitutes variables into prompt_template string |
| `_launch_screen_tasks(tasks, scan)` | Renders Screen 1 TUI; returns chosen template or None |
| `_launch_screen_preview(task, scan)` | Renders Screen 2; returns (confirmed: bool, prompt: str) |
| `_launch_screen_cycles()` | Renders Screen 3 ([?] explainer); returns on any key |
| `cmd_launch(dry_run, list_mode)` | Top-level entry point; orchestrates screens → dispatch |

**DB migration** (in `_migrate_db()`):
```sql
UPDATE cycle_capability SET cycle = 'design' WHERE cycle = 'plan';
UPDATE cycle_capability SET cycle = 'plan'   WHERE cycle = 'work';
UPDATE cycle_capability SET cycle = 'build'  WHERE cycle = 'ship';
UPDATE cycle_capability SET cycle = 'ship'   WHERE cycle = 'maintain';
UPDATE cycle_capability SET cycle = 'sustain' WHERE cycle = 'engage';
UPDATE harness_verb_map  SET cycle = 'design' WHERE cycle = 'plan';
-- (same pattern for harness_verb_map)
```

**Scan additions** to `run_workspace_scan()`:
- `test_ratio`: count files matching `test_*.py` / `*.test.*` / `__tests__/` divided by total source files
- `readme_word_count`: word count of README.md if present
- `has_ci`: presence of `.github/workflows/` or `.gitlab-ci.yml` or `.circleci/`
- `has_docs`: presence of `docs/` directory with at least 1 `.md` file
- `has_type_hints`: Python repos — presence of `.pyi` files or `from __future__ import annotations` in >30% of `.py` files
- `has_orm`: presence of `sqlalchemy` / `prisma` / `django.db` / `activerecord` in dependency files

**CLI:**
```python
p = subparsers.add_parser("launch", help="Pick your first task and dispatch it")
p.add_argument("--dry-run", action="store_true", help="Print selected tasks without TUI")
p.add_argument("--list",    action="store_true", help="Print full template pool with trigger conditions")
```

---

## Tests

`tests/test_launch.py` — 20 tests covering:

- `test_template_matches_core_always_eligible` — core 3 templates match any scan
- `test_template_matches_add_tests_triggered` — `add-tests` matches when test_ratio < 0.1
- `test_template_matches_add_tests_not_triggered` — `add-tests` excluded when test_ratio >= 0.1
- `test_template_matches_setup_ci_triggered` — no CI files present
- `test_template_matches_type_safety_python_only` — not triggered for non-Python repos
- `test_select_tasks_returns_max_5` — never returns more than 5
- `test_select_tasks_core_always_first` — core templates precede bonus
- `test_select_tasks_empty_scan_returns_core_3` — fallback to core 3 when scan is empty
- `test_render_prompt_substitutes_all_variables` — all `{var}` tokens replaced
- `test_render_prompt_missing_variable_uses_empty_string` — no KeyError on missing var
- `test_cycle_rename_migration_idempotent` — migration safe to run twice
- `test_cycle_rename_migration_updates_cycle_capability` — verifies new names in table
- `test_cmd_launch_dry_run_prints_tasks_no_dispatch` — dry-run doesn't call dispatch_agent
- `test_cmd_launch_list_prints_all_12_templates` — --list output includes all 12
- `test_auto_launch_config_default_true` — `load_config()` default
- `test_wizard_calls_cmd_launch_when_auto_launch_true` — Screen 6 triggers launch
- `test_wizard_skips_cmd_launch_when_auto_launch_false` — Screen 6 does not trigger launch
- `test_launch_screen_preview_returns_confirmed_and_prompt` — happy path
- `test_launch_screen_preview_edit_replaces_prompt` — [e] substitution
- `test_launch_screen_tasks_skip_returns_none` — [s] exit without dispatch

---

## Out of Scope

- Persisting "task done" state after a launch task is dispatched — the job in `jobs` table is the record; no separate tracking needed
- Custom task templates defined by the user — v0.11.0 ships the fixed pool of 12; user-defined templates are a future story
- AI-generated task descriptions — all prompts are template-based; no LLM call in `cmd_launch` itself
- Token estimate accuracy — R/W/T values are static per-template constants; actual usage will vary
