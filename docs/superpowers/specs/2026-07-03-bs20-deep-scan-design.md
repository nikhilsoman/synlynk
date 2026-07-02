# BS-20: Deep Scan — Architect-Grade Interactive Workspace Analysis

**Date:** 2026-07-03
**Session:** BS-20 (Nikhil + Claude)
**Status:** Approved for implementation
**Target:** v0.11.0
**Replaces:** shallow `run_workspace_scan()` trigger-field approach (BS-19)

---

## Problem Statement

`run_workspace_scan()` currently reads at most 1000 bytes per file and returns six boolean flags (`has_type_hints`, `has_ci`, etc.). These flags drive `synlynk launch` task suggestions, but they produce generic prompts — "add tests to your project" rather than "add tests for `cmd_probe` and 7 other untested functions in `__init__.py`."

A senior architect pointing at a codebase needs to see: file sizes, hotspot functions, untested public API, git churn, import structure. The current scan cannot produce that picture.

The goal of BS-20 is to make `synlynk scan` the normalization layer between a raw codebase and an AI agent's working context. Every agent that touches this repo gets a precise, machine-readable summary of what's large, what's risky, what's missing — injected automatically into their instruction files.

---

## Goals

1. Replace the shallow 1000-byte scan with a full AST-powered deep scan running by default.
2. Surface architect-grade findings in an interactive Stage Cards TUI (6 parallel threads, cards reveal as stages complete).
3. Auto-write a `## Codebase Context` fence section into CLAUDE.md, GEMINI.md, AGENTS.md on every scan.
4. Persist rich scan results to `.synlynk/scan-result.json` for downstream consumers.
5. Upgrade `LAUNCH_TASK_TEMPLATES` trigger conditions to use specific deep-scan fields (gap count, hotspot lines, typed %) rather than booleans.
6. Keep `deep=False` path intact for programmatic callers (wizard Screen 0, test fixtures).

---

## Non-Goals

- Import graph visualization — that is `git-connectome` (separate standalone tool).
- Cyclomatic complexity scoring — AST line count per function is a sufficient proxy.
- Duplicate code detection.
- Security/vulnerability scanning of dependencies.
- Multi-language AST parsing — Source and Architecture stages are Python-only; Stack detection remains multi-language via file-presence heuristics.

---

## Architecture

### Layers

```
cmd_scan()
    │
    ├─ deep=True (default)
    │       ├─ spawn 6 threads → shared results dict
    │       ├─ _run_scan_tui(results, threads)   ← interactive Stage Cards
    │       ├─ _write_scan_fences(results)        ← update agent directive files
    │       └─ persist → .synlynk/scan-result.json
    │
    └─ deep=False (programmatic / wizard Screen 0)
            └─ run_workspace_scan(deep=False)     ← existing shallow path, unchanged
```

### Agent vs. Harness identity

No change. Scan is workspace-centric, not harness-centric. The fence writer reuses `_upsert_harness_fence()` with a new `## Codebase Context` body.

---

## Scan Pipeline — 6 Stages

All 6 run as Python `threading.Thread` instances against `primary_root`. Each writes one key into a shared `results` dict (starts `None`, set to a dict on completion, set to `{"error": str}` on failure). The TUI polls this dict every 200ms.

### Stage 1 — Stack (`_scan_stage_stack`)

**Input:** `primary_root`
**Tool:** file-presence + dep file parsing (existing `fingerprint_stack` + extended)

```python
results["stack"] = {
    "language": str,          # "python" | "node" | "go" | "ruby" | …
    "version": str,           # from .python-version / pyproject.toml / .nvmrc
    "frameworks": [str],      # ["pytest", "django", …]
    "package_manager": str,   # "pyproject.toml" | "package.json" | "go.mod" | …
    "ci": bool,
    "ci_workflows": int,
    "dep_count": {"prod": int, "dev": int},
    "lockfile_fresh": bool,   # lockfile exists and is newer than dep manifest
}
```

### Stage 2 — Source Structure (`_scan_stage_source`)

**Input:** `primary_root`
**Tool:** `ast.parse()` per `.py` file; regex line-count for non-Python

```python
results["source"] = [   # one dict per source file, sorted by lines desc
    {
        "path": str,            # relative to primary_root
        "lines": int,
        "functions": int,       # ast.FunctionDef count
        "classes": int,         # ast.ClassDef count
        "typed_pct": int,       # % of functions with at least one annotation or ->
        "docstring_pct": int,   # % of public functions (no leading _) with docstring
        "largest_fns": [        # top 3 by line count (end_lineno - lineno)
            {"name": str, "lines": int, "lineno": int},
        ],
    },
    # …
]
```

AST parse is best-effort: `SyntaxError` → store `{"path": …, "lines": line_count, "parse_error": True}`.

### Stage 3 — Complexity Hotspots (`_scan_stage_complexity`)

**Input:** `primary_root`
**Tool:** AST node count per function; regex for marker comments

```python
results["complexity"] = {
    "hotspots": [               # functions >50 lines OR standalone files >500 lines
        {
            "path": str,
            "fn": str | None,   # None = file-level hotspot
            "lines": int,
            "lineno": int,
        },
    ],
    "todo_counts": {            # counts across all source files
        "TODO": int, "FIXME": int, "HACK": int, "XXX": int,
    },
}
```

Hotspots sorted by line count descending.

### Stage 4 — Test Coverage Map (`_scan_stage_tests`)

**Input:** `primary_root`
**Tool:** name-matching heuristic (`test_<fn_name>` in test files)

```python
results["tests"] = {
    "gap_functions": [          # public fns (no leading _) with no matching test
        {"name": str, "file": str, "lineno": int},
    ],
    "covered_count": int,
    "gap_count": int,
    "ratio": float,             # test files / all source files
}
```

"Covered" = a test file exists that contains `def test_<fn_name>` or calls `fn_name(`. Not a runtime coverage tool — purely structural name-matching. Clearly labelled as such in fence output.

### Stage 5 — Git Churn (`_scan_stage_git`)

**Input:** `primary_root`
**Tool:** `git log --name-only -n 30 --pretty=format:` (subprocess, 5s timeout)

```python
results["git"] = {
    "churn": [                  # sorted by commit_count desc
        {
            "path": str,
            "commits": int,
            "last_days_ago": int,
            "temp": "hot" | "warm" | "cold",   # hot: >20 commits, warm: 5-20, cold: <5
        },
    ],
    "total_commits_scanned": int,
}
```

If git is unavailable or times out: `results["git"] = {"error": "git unavailable"}`. Card shows degraded state; scan continues.

### Stage 6 — Architecture Signals (`_scan_stage_arch`)

**Input:** `primary_root`
**Tool:** AST import analysis + entry point detection

```python
results["arch"] = {
    "entry_points": [           # main(), CLI commands, if __name__ == "__main__"
        {"name": str, "file": str, "lineno": int},
    ],
    "import_graph": {           # file (relative) → list of local files it imports
        str: [str],
    },
    "dead_candidates": [str],   # relative paths with zero inbound local imports
    "public_api_count": int,    # total public functions + classes across all files
    "pattern": str,             # "monolith" | "modular" | "library"
                                # monolith: 1 file >50% of total lines
                                # modular: no file >20% of total lines
                                # library: no entry point, only __init__.py exports
}
```

`import_graph` covers local imports only (relative imports + imports of project modules). Third-party imports not tracked here.

---

## Interactive TUI — `_run_scan_tui(results, threads)`

### Layout

6 cards in a 2-column grid, rendered with `_wiz_clear()` + full repaint every 200ms.

```
◆ synlynk scan  workspace: <name>  [⟳ scanning… | ✓ complete · Ns]

┌─ STACK ────────────────────┐  ┌─ SOURCE ────────────────────┐
│ Python 3.11 · pytest · CI  │  │ 44 files · 432 fns · 34% ty │
│ 0 prod · 8 dev · fresh     │  │ ⚠ __init__.py 10,651 lines  │
└────────────────────────────┘  └────────────────────────────┘
┌─ COMPLEXITY ───────────────┐  ┌─ TESTS ─────────────────────┐
│ 3 hotspots · 14 TODO       │  │ 39% · 8 untested functions  │
│ wizard_init · cmd_doctor   │  │ cmd_probe · +6 more         │
└────────────────────────────┘  └────────────────────────────┘
┌─ GIT CHURN ────────────────┐  ┌─ ARCHITECTURE ──────────────┐
│ 🔥 __init__.py · 47 cmts   │  │ monolith · 12 CLI entries   │
│ warm: GEMINI.md            │  │ 0 dead modules · stdlib     │
└────────────────────────────┘  └────────────────────────────┘

[1–6] expand card  ·  [enter] proceed (active when all done)  ·  [r] re-scan  ·  [q] quit
```

**Pending card:** dimmed, spinner `⟳` in top-right corner, body shows `scanning…`.
**Error card:** red left border, body shows truncated error message.
**Expanded card:** replaces grid with a detail view. Any key collapses back.

### Polling loop

```python
while not all_done:
    _wiz_clear()
    _render_cards(results, expanded)
    all_done = all(results[k] is not None for k in STAGE_KEYS)
    if _kbhit():                     # non-blocking key check via termios
        key = _wiz_read_key()
        if key.isdigit() and 1 <= int(key) <= 6:
            expanded = STAGE_KEYS[int(key) - 1] if not expanded else None
        elif key in ("\r", "\n") and all_done:
            break
        elif key == "r":
            restart_scan()
        elif key in ("q", "\x03"):
            sys.exit(0)
    time.sleep(0.2)
```

`_kbhit()` uses `select.select([sys.stdin], [], [], 0)` — non-blocking, no busy loop.

### Completion sequence

Once all threads complete:
1. Final repaint (all cards showing ✓).
2. Call `_write_scan_fences(results)` — update agent directive files.
3. Persist `json.dumps(results)` → `.synlynk/scan-result.json`.
4. Print fence update summary (green block, one line per file updated).
5. Activate `[enter]` prompt: `[enter] synlynk launch`.
6. On `[enter]`: call `cmd_launch_ftue()`.

---

## Agent Fence Content — `_write_scan_fences(results)`

Calls `_upsert_harness_fence(fname, harness_version=f"scan-{date}", body=...)` for each present directive file (CLAUDE.md, GEMINI.md, AGENTS.md, GROK.md). Does not create files that don't exist.

### Fence body format

```
## Codebase Context
- Architecture: <pattern> · <language> · <entry_point_summary>
- Source: <file_count> files · <total_fns> functions · <largest_file> <N> lines
- Type coverage: <typed_pct>% · Docstring coverage: <docstring_pct>%

## Complexity Hotspots
<top 3 hotspots as bullet points: fn_name() — N lines (path:lineno)>

## Test Gaps
- <gap_count> untested public functions: <top 5 names> [+N more]

## Hot Files (last 30 commits)
<top 3 churn entries: 🔥/warm/cold · path — N commits>

## Tech Debt
- <TODO count> TODO · <FIXME count> FIXME · <HACK count> HACK
```

Content is capped to keep fence tokens reasonable (~300 words max). If a stage errored, its section is omitted with a note: `# <Stage> unavailable (scan error)`.

---

## Signal Schema — `run_workspace_scan(deep=True)`

The top-level return dict gains all 6 stage results as direct keys:

```python
{
    # existing shallow fields (always present, deep=False compatible):
    "workspace_name": str,
    "topology": str,
    "repos": [...],
    "harnesses": [...],
    "agents": [...],
    "skills": [...],
    "home_harness": str,
    "scanned_at": str,
    # existing BS-19 trigger fields (retained for backwards compat):
    "test_ratio": float,
    "readme_word_count": int,
    "has_ci": bool,
    "has_docs": bool,
    "has_type_hints": bool,
    "has_orm": bool,

    # new deep-scan fields (None when deep=False):
    "stack": dict | None,
    "source": list | None,
    "complexity": dict | None,
    "tests": dict | None,
    "git": dict | None,
    "arch": dict | None,
}
```

Backwards compat: all existing shallow fields are still populated even in deep mode (derived from stack/source stages). `has_type_hints` is now derived from `source[*].typed_pct` instead of the 1000-byte heuristic.

---

## Launch Task Template Upgrades

Trigger conditions updated to use deep fields. Prompt templates gain named substitution variables populated from the scan.

| Template ID | New trigger | New prompt variable |
|---|---|---|
| `add-tests` | `tests.gap_count > 5` | `{gap_functions}` — top 5 names |
| `add-type-hints` | `source[*].typed_pct < 40` (Python) | `{typed_pct}`, `{untyped_count}` |
| `refactor-module` | `source[*].lines > 5000` | `{largest_file}`, `{largest_fn}` |
| `document-api` | `source[*].docstring_pct < 30` | `{undocumented_count}` |
| `reduce-complexity` | `len(complexity.hotspots) > 2` | `{top_hotspot}` |
| `fix-churn-debt` | `git.churn[0].commits > 30` | `{hot_file}`, `{commit_count}` |

Prompt example (add-tests):
> "Add pytest tests for the following untested public functions in `{largest_file}`: {gap_functions}. Use the existing test file pattern in `tests/`. Each function needs at least one happy-path test and one edge-case test."

---

## Files Changed

| File | Change |
|---|---|
| `synlynk/__init__.py` | 6 new `_scan_stage_*` functions; `_run_scan_tui()`; `_write_scan_fences()`; `_kbhit()` helper; `run_workspace_scan()` gains `deep` param; `cmd_scan()` updated; `LAUNCH_TASK_TEMPLATES` trigger + prompt updates |
| `tests/test_workspace_scan.py` | Existing tests updated for new schema; new tests for each stage function and TUI |
| `tests/test_launch.py` | Trigger condition tests updated for deep-scan fields |

No new files. No new dependencies (stdlib only: `ast`, `threading`, `select`, `subprocess`).

---

## Implementation Stories (v0.11.0)

| Story ID | Scope |
|---|---|
| `story-bs20-stages` | 6 `_scan_stage_*` functions + signal schema + `run_workspace_scan(deep=True)` |
| `story-bs20-tui` | `_run_scan_tui()` + `_kbhit()` + card renderer + polling loop |
| `story-bs20-fences` | `_write_scan_fences()` + fence body format + has_type_hints fix |
| `story-bs20-launch` | `LAUNCH_TASK_TEMPLATES` trigger + prompt upgrades |
| `story-bs20-tests` | Full test suite for all 4 stories |

---

## Testing Strategy

- Stage functions tested in isolation with `tmp_path` fixtures (controlled file trees, controlled git repos via `git init` + commits).
- `_run_scan_tui()` tested with monkeypatched `_wiz_clear`, `_wiz_read_key`, pre-populated `results` dict.
- `_write_scan_fences()` tested against temp directive files — verify fence content matches signal schema.
- No integration test that runs all 6 threads live (too slow, too env-dependent). Each stage gets its own focused test.
- `test_ratio`, `has_type_hints` etc. backwards-compat fields tested to verify they still populate correctly in deep mode.
