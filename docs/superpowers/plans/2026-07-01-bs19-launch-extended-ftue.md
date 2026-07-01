# BS-19 — synlynk launch: Extended FTUE + 6-Cycle SDLC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `synlynk launch` as an FTUE task-picker TUI that surfaces 3–5 scan-informed first tasks (with R/W/T token estimates), each pre-wired with agent, cycle tag, and editable dispatch prompt.

**Architecture:** All changes land in `synlynk/__init__.py`. A module-level constant `LAUNCH_TASK_TEMPLATES` holds 12 template dicts. Four helper functions (`_template_matches`, `_select_launch_tasks`, `_render_prompt`, three TUI screens) compose into `cmd_launch_ftue()`. The existing `synlynk launch <agent>` interactive command is renamed to `synlynk open <agent>` to free the `launch` name. `wizard_init()` calls `cmd_launch_ftue()` after Screen 6 when `auto_launch_after_wizard: true`.

**Tech Stack:** Python 3 stdlib only — `sys`, `os`, `json`, `sqlite3`, `re`, `datetime`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-01-bs19-launch-extended-ftue-design.md`

---

## File Map

| File | Change |
|------|--------|
| `synlynk/__init__.py` | All new code + modifications (8 tasks below) |
| `tests/test_launch.py` | New — 20 tests |

---

## Task 1: 6-Cycle Constants + DB Migration UPDATEs

**Files:**
- Modify: `synlynk/__init__.py` — add cycle constants near top, add UPDATE statements to `_migrate_db()`

Context: the `cycle_capability` and `harness_verb_map.cycle` DB columns don't exist in the current schema. The UPDATE statements are idempotent no-ops (fail silently via try/except). The Python constants are new and used by the TUI.

- [ ] **Step 1: Write failing test for cycle constants**

In `tests/test_launch.py` (create file):

```python
import sys
import os
import sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_cycle_names_constant_exists():
    assert hasattr(synlynk, 'CYCLE_NAMES')
    assert synlynk.CYCLE_NAMES == ["dream", "design", "plan", "build", "ship", "sustain"]


def test_cycle_colors_constant_exists():
    assert hasattr(synlynk, 'CYCLE_COLORS')
    assert synlynk.CYCLE_COLORS["dream"] == "#a78bfa"
    assert synlynk.CYCLE_COLORS["sustain"] == "#94a3b8"


def test_cycle_rename_migration_idempotent(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    synlynk._migrate_db(conn)
    synlynk._migrate_db(conn)  # second run must not raise
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_launch.py::test_cycle_names_constant_exists tests/test_launch.py::test_cycle_colors_constant_exists -v
```
Expected: `AttributeError: module 'synlynk' has no attribute 'CYCLE_NAMES'`

- [ ] **Step 3: Add constants to `synlynk/__init__.py`**

Find the block around line 15 (after `VERSION = "0.10.0"`). Add after `VERSION`:

```python
CYCLE_NAMES = ["dream", "design", "plan", "build", "ship", "sustain"]

CYCLE_COLORS = {
    "dream":   "#a78bfa",
    "design":  "#60a5fa",
    "plan":    "#34d399",
    "build":   "#fbbf24",
    "ship":    "#f87171",
    "sustain": "#94a3b8",
}

CYCLE_DESCRIPTIONS = {
    "dream":   "What's worth building? Ideate, assess, identify opportunities.",
    "design":  "Brainstorm → spec → UX. Turn ideas into a concrete brief.",
    "plan":    "Implementation plan, story breakdown, agent wave schedule.",
    "build":   "Dispatch agents, run jobs, iterate on diffs.",
    "ship":    "Cut release, changelog, publish.",
    "sustain": "Monitor, patch, community, docs, support.",
}

CYCLE_DEFAULT_AGENTS = {
    "dream":   ["claude"],
    "design":  ["claude"],
    "plan":    ["claude"],
    "build":   ["agy", "codex", "grok"],
    "ship":    ["claude"],
    "sustain": ["claude", "agy", "codex", "grok"],
}
```

- [ ] **Step 4: Add idempotent cycle UPDATEs to `_migrate_db()`**

At the end of `_migrate_db()` (around line 241 after the last `conn.executescript` block), add:

```python
    # Idempotent cycle rename: old names → new names (no-ops if tables/columns absent)
    for sql in [
        "UPDATE cycle_capability SET cycle = 'design'  WHERE cycle = 'plan'",
        "UPDATE cycle_capability SET cycle = 'plan'    WHERE cycle = 'work'",
        "UPDATE cycle_capability SET cycle = 'build'   WHERE cycle = 'ship'",
        "UPDATE cycle_capability SET cycle = 'ship'    WHERE cycle = 'maintain'",
        "UPDATE cycle_capability SET cycle = 'sustain' WHERE cycle = 'engage'",
        "UPDATE harness_verb_map  SET cycle = 'design'  WHERE cycle = 'plan'",
        "UPDATE harness_verb_map  SET cycle = 'plan'    WHERE cycle = 'work'",
        "UPDATE harness_verb_map  SET cycle = 'build'   WHERE cycle = 'ship'",
        "UPDATE harness_verb_map  SET cycle = 'ship'    WHERE cycle = 'maintain'",
        "UPDATE harness_verb_map  SET cycle = 'sustain' WHERE cycle = 'engage'",
    ]:
        try:
            conn.execute(sql)
        except _sqlite3.OperationalError:
            pass  # table or column absent — migration is a no-op
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_launch.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): add cycle constants + idempotent rename migration [T1]"
```

---

## Task 2: Scan Additions — 6 New Fields

**Files:**
- Modify: `synlynk/__init__.py:run_workspace_scan()` (line ~3847, just before the `return` statement)

The 6 new fields are computed from the **primary repo** (first entry in `repos`). They're cheap file-presence checks — no subprocess calls.

- [ ] **Step 1: Write failing test**

Add to `tests/test_launch.py`:

```python
def test_scan_returns_test_ratio(tmp_path, monkeypatch):
    # Create a minimal repo structure with one test file
    (tmp_path / "app.py").write_text("def foo(): pass")
    (tmp_path / "test_app.py").write_text("def test_foo(): pass")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], workspace_name="test")
    assert "test_ratio" in result
    assert isinstance(result["test_ratio"], float)


def test_scan_returns_has_ci_false_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], workspace_name="test")
    assert result["has_ci"] is False


def test_scan_returns_readme_word_count(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text("Hello world this is a README with ten words total")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], workspace_name="test")
    assert result["readme_word_count"] >= 9
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_scan_returns_test_ratio tests/test_launch.py::test_scan_returns_has_ci_false_when_absent tests/test_launch.py::test_scan_returns_readme_word_count -v
```
Expected: `KeyError: 'test_ratio'`

- [ ] **Step 3: Add scan field computation to `run_workspace_scan()`**

Find the `return {` block at line ~3847. Add 6 new fields computed before the return.

Insert before `return {`:

```python
    # ── BS-19 launch task trigger fields ─────────────────────────────────────
    primary_root = normalized_roots[0] if normalized_roots else os.getcwd()

    # test_ratio: test files / total .py source files (0.0 if no source files)
    def _count_files(root, patterns):
        import fnmatch as _fnmatch
        count = 0
        for dirpath, _, filenames in os.walk(root):
            if any(p in dirpath for p in (".git", "__pycache__", "node_modules", ".venv", "venv")):
                continue
            for fn in filenames:
                if any(_fnmatch.fnmatch(fn, p) for p in patterns):
                    count += 1
        return count

    src_count = _count_files(primary_root, ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.rb", "*.go"])
    test_count = _count_files(primary_root, ["test_*.py", "*_test.py", "*.test.ts", "*.test.tsx",
                                              "*.test.js", "*.spec.ts", "*.spec.js"])
    test_ratio = test_count / src_count if src_count > 0 else 0.0

    # readme_word_count
    readme_path = os.path.join(primary_root, "README.md")
    readme_word_count = 0
    if os.path.exists(readme_path):
        try:
            readme_word_count = len(open(readme_path).read().split())
        except OSError:
            pass

    # has_ci
    has_ci = (
        os.path.isdir(os.path.join(primary_root, ".github", "workflows"))
        or os.path.exists(os.path.join(primary_root, ".gitlab-ci.yml"))
        or os.path.isdir(os.path.join(primary_root, ".circleci"))
    )

    # has_docs: docs/ dir with at least one .md file
    docs_dir = os.path.join(primary_root, "docs")
    has_docs = False
    if os.path.isdir(docs_dir):
        for fn in os.listdir(docs_dir):
            if fn.endswith(".md"):
                has_docs = True
                break

    # has_type_hints: Python repo + any .pyi files or any .py with annotations import
    has_type_hints = False
    py_files_with_hints = 0
    py_files_total = 0
    for dirpath, _, filenames in os.walk(primary_root):
        if any(p in dirpath for p in (".git", "__pycache__", "node_modules", ".venv", "venv")):
            continue
        for fn in filenames:
            if fn.endswith(".pyi"):
                has_type_hints = True
            elif fn.endswith(".py"):
                py_files_total += 1
                try:
                    content = open(os.path.join(dirpath, fn)).read(1000)
                    if "from __future__ import annotations" in content or ": " in content:
                        py_files_with_hints += 1
                except OSError:
                    pass
    if py_files_total > 0 and not has_type_hints:
        has_type_hints = (py_files_with_hints / py_files_total) > 0.3

    # has_orm
    orm_markers = ("sqlalchemy", "from django.db", "import prisma", "activerecord", "ActiveRecord")
    has_orm = False
    for dep_file in ("requirements.txt", "requirements-dev.txt", "pyproject.toml",
                     "Gemfile", "package.json", "go.mod"):
        dep_path = os.path.join(primary_root, dep_file)
        if os.path.exists(dep_path):
            try:
                content = open(dep_path).read()
                if any(m in content for m in orm_markers):
                    has_orm = True
                    break
            except OSError:
                pass
```

Then add the 6 new keys to the `return` dict:

```python
    return {
        "workspace_name": workspace_name,
        "topology": topology,
        "repos": repos,
        "harnesses": harnesses,
        "agents": agents,
        "skills": skills,
        "home_harness": home_harness,
        "scanned_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "test_ratio": test_ratio,
        "readme_word_count": readme_word_count,
        "has_ci": has_ci,
        "has_docs": has_docs,
        "has_type_hints": has_type_hints,
        "has_orm": has_orm,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_launch.py -v
```
Expected: all scan tests PASS.

- [ ] **Step 5: Run full suite to check for regressions**

```
pytest tests/ -x -q 2>&1 | tail -10
```
Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): extend run_workspace_scan with 6 launch-trigger fields [T2]"
```

---

## Task 3: `LAUNCH_TASK_TEMPLATES` Constant

**Files:**
- Modify: `synlynk/__init__.py` — add module-level constant after `CYCLE_DEFAULT_AGENTS`

The constant is a list of 12 dicts. `trigger_condition` is a callable `(scan) -> bool`. Core templates always match (`trigger_condition=None`). Scan-triggered templates have a lambda.

- [ ] **Step 1: Write failing test**

Add to `tests/test_launch.py`:

```python
def test_launch_task_templates_count():
    assert len(synlynk.LAUNCH_TASK_TEMPLATES) == 12


def test_launch_task_templates_have_required_fields():
    required = {"id", "title", "description", "cycle", "agent", "context_mode",
                "prompt_template", "est_hours", "r_tokens", "w_tokens", "tool_calls"}
    for t in synlynk.LAUNCH_TASK_TEMPLATES:
        missing = required - set(t.keys())
        assert not missing, f"Template '{t.get('id')}' missing fields: {missing}"


def test_launch_task_templates_core_ids():
    ids = {t["id"] for t in synlynk.LAUNCH_TASK_TEMPLATES}
    for core_id in ("arch-review", "product-assessment", "lifecycle-setup"):
        assert core_id in ids
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_launch_task_templates_count tests/test_launch.py::test_launch_task_templates_have_required_fields tests/test_launch.py::test_launch_task_templates_core_ids -v
```
Expected: `AttributeError: module 'synlynk' has no attribute 'LAUNCH_TASK_TEMPLATES'`

- [ ] **Step 3: Add `LAUNCH_TASK_TEMPLATES` constant**

Add after `CYCLE_DEFAULT_AGENTS` in `synlynk/__init__.py`. This constant also needs `CORE_TEMPLATE_IDS`:

```python
CORE_TEMPLATE_IDS = {"arch-review", "product-assessment", "lifecycle-setup"}

LAUNCH_TASK_TEMPLATES = [
    # ── Core templates (always shown) ───────────────────────────────────────
    {
        "id": "arch-review",
        "title": "Workspace architecture review",
        "description": "Analyse structure, patterns, tech debt. Claude writes findings to memory.md.",
        "cycle": "dream",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Review the architecture of {workspace} ({stack}, {topology} repo). "
            "Identify: structural patterns in use, top 5 tech debt hotspots (name files "
            "and functions), component coupling risks, and 3 concrete improvement "
            "opportunities with effort estimates. Write your findings as a new section "
            'in .synlynk/project-docs/memory.md under "## Architecture Review {date}". '
            "Be specific — no generic advice."
        ),
        "est_hours": 2,
        "r_tokens": 80000,
        "w_tokens": 8000,
        "tool_calls": 12,
        "trigger_condition": None,
    },
    {
        "id": "product-assessment",
        "title": "Product + opportunity assessment",
        "description": "Scope, features, market fit, growth levers. 1-page brief to memory.md.",
        "cycle": "dream",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Assess the product potential of {workspace}. Cover: what problem it solves, "
            "current feature set vs. gaps, market positioning, top 3 growth levers, and "
            "1 concrete opportunity to pursue in the next sprint. Write a 1-page brief to "
            '.synlynk/project-docs/memory.md under "## Product Assessment {date}".'
        ),
        "est_hours": 1,
        "r_tokens": 40000,
        "w_tokens": 6000,
        "tool_calls": 8,
        "trigger_condition": None,
    },
    {
        "id": "lifecycle-setup",
        "title": "Set up 6-cycle workflow for this repo",
        "description": "Initialise lifecycle tracking in state.db. Label open stories by cycle.",
        "cycle": "plan",
        "agent": "claude",
        "context_mode": "task",
        "prompt_template": (
            "Set up the 6-cycle SDLC workflow for {workspace}. "
            "Run `synlynk story list` to see existing stories. "
            "For each story, assign a cycle phase (dream/design/plan/build/ship/sustain) "
            "based on its title and update it with `synlynk story update`. "
            "Then write a short SDLC setup note in "
            '.synlynk/project-docs/memory.md under "## Lifecycle Setup {date}" '
            "explaining which stories belong to which cycle and why."
        ),
        "est_hours": 0.5,
        "r_tokens": 15000,
        "w_tokens": 3000,
        "tool_calls": 6,
        "trigger_condition": None,
    },
    # ── Scan-triggered templates ─────────────────────────────────────────────
    {
        "id": "add-tests",
        "title": "Add test coverage",
        "description": "Bootstrap a test suite for the most critical untested modules.",
        "cycle": "plan",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "The {workspace} repo has low test coverage (test_ratio < 0.1). "
            "Identify the 3 most critical untested modules in {repo_name}. "
            "For each, write a test file with at least 5 meaningful tests covering "
            "happy path, edge cases, and error handling. Commit each test file "
            "with a message like 'test: add coverage for <module>'. "
            "Do not mock the database or filesystem unless unavoidable."
        ),
        "est_hours": 3,
        "r_tokens": 60000,
        "w_tokens": 20000,
        "tool_calls": 30,
        "trigger_condition": lambda scan: scan.get("test_ratio", 1.0) < 0.1,
    },
    {
        "id": "setup-ci",
        "title": "Set up CI/CD pipeline",
        "description": "Create a GitHub Actions workflow for tests and linting.",
        "cycle": "plan",
        "agent": "codex",
        "context_mode": "task",
        "prompt_template": (
            "Set up CI/CD for {workspace} ({stack}). "
            "Create .github/workflows/ci.yml that: runs tests on every push to main "
            "and on PRs, runs a linter if one is configured, and fails fast on error. "
            "Use the appropriate test runner for the stack ({stack}). "
            "Commit the workflow file with a message: 'ci: add GitHub Actions workflow'."
        ),
        "est_hours": 1,
        "r_tokens": 20000,
        "w_tokens": 5000,
        "tool_calls": 10,
        "trigger_condition": lambda scan: not scan.get("has_ci", False),
    },
    {
        "id": "docs-audit",
        "title": "Documentation audit + gap fill",
        "description": "Audit docs coverage and write missing sections.",
        "cycle": "design",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "Audit the documentation for {workspace}. "
            "Check: README completeness, API/function docstrings, architecture docs, "
            "contributing guide, and changelog. "
            "For each gap: write the missing content inline (do not use placeholders). "
            "Commit each doc file separately with a message like 'docs: add <section>'."
        ),
        "est_hours": 2,
        "r_tokens": 50000,
        "w_tokens": 15000,
        "tool_calls": 20,
        "trigger_condition": lambda scan: (
            not scan.get("has_docs", False) or scan.get("readme_word_count", 999) < 200
        ),
    },
    {
        "id": "security-scan",
        "title": "Dependency security scan",
        "description": "Check for known CVEs and outdated dependencies.",
        "cycle": "dream",
        "agent": "claude",
        "context_mode": "task",
        "prompt_template": (
            "Run a dependency security audit for {workspace} ({stack}). "
            "Use `pip-audit` (Python), `npm audit` (Node), or `bundle audit` (Ruby) "
            "depending on the stack. List all HIGH and CRITICAL vulnerabilities found. "
            "For each: state the package, CVE, severity, and recommended fix. "
            'Write findings to .synlynk/project-docs/memory.md under "## Security Audit {date}". '
            "If no vulnerabilities: confirm that explicitly."
        ),
        "est_hours": 1,
        "r_tokens": 25000,
        "w_tokens": 4000,
        "tool_calls": 8,
        "trigger_condition": lambda scan: any(
            any(lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
                for lbl in ["python", "node", "ruby"])
            for _ in [1]
        ),
    },
    {
        "id": "perf-baseline",
        "title": "Performance baseline + profiling plan",
        "description": "Identify hot paths and draft a performance improvement plan.",
        "cycle": "dream",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Profile the performance of {workspace} ({stack}). "
            "Identify: the 3 slowest request paths or CLI operations, any N+1 query patterns, "
            "memory allocation hot spots, and opportunities for caching. "
            "Write a performance improvement plan to "
            '.synlynk/project-docs/memory.md under "## Performance Baseline {date}" '
            "with specific file + line references."
        ),
        "est_hours": 2,
        "r_tokens": 70000,
        "w_tokens": 8000,
        "tool_calls": 15,
        "trigger_condition": lambda scan: any(
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["next", "fastapi", "django", "express", "flask"]
        ),
    },
    {
        "id": "cross-repo-map",
        "title": "Cross-repo dependency map",
        "description": "Map inter-repo dependencies for the multi-repo workspace.",
        "cycle": "dream",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Map the inter-repo dependencies of {workspace} ({topology} workspace). "
            "For each repo pair: identify shared interfaces, shared types/schemas, "
            "shared infra, and any circular dependencies. "
            "Write a dependency map to "
            '.synlynk/project-docs/memory.md under "## Cross-Repo Map {date}" '
            "using a table: Repo A → Repo B → Dependency type → Notes."
        ),
        "est_hours": 1,
        "r_tokens": 40000,
        "w_tokens": 6000,
        "tool_calls": 10,
        "trigger_condition": lambda scan: scan.get("topology") in ("mono", "multi", "monorepo"),
    },
    {
        "id": "type-safety",
        "title": "Add type annotations to public API",
        "description": "Annotate public functions and classes to improve tooling and safety.",
        "cycle": "design",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "Add type annotations to the public API of {workspace} ({stack}). "
            "Target: all functions and methods that are exported or called from tests. "
            "Use Python type hints (PEP 484). Do not annotate private (_-prefixed) helpers "
            "unless they are called by public functions. "
            "Commit each annotated file separately with 'refactor: add type hints to <module>'."
        ),
        "est_hours": 3,
        "r_tokens": 120000,
        "w_tokens": 30000,
        "tool_calls": 45,
        "trigger_condition": lambda scan: (
            any(lbl == "python" for lbl in
                scan.get("repos", [{}])[0].get("stack_labels", []))
            and not scan.get("has_type_hints", False)
        ),
    },
    {
        "id": "a11y-audit",
        "title": "Accessibility audit",
        "description": "Audit the frontend for WCAG 2.1 AA compliance gaps.",
        "cycle": "design",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "Audit {workspace} ({stack}) for accessibility issues (WCAG 2.1 AA). "
            "Check: missing alt text, keyboard navigation, ARIA roles, colour contrast, "
            "and form labels. List each issue with: component file, line number, "
            "WCAG criterion, and fix. "
            'Write findings to .synlynk/project-docs/memory.md under "## A11y Audit {date}". '
            "Fix the top 5 most critical issues and commit each fix separately."
        ),
        "est_hours": 2,
        "r_tokens": 60000,
        "w_tokens": 15000,
        "tool_calls": 25,
        "trigger_condition": lambda scan: any(
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["react", "next", "vue", "svelte", "angular"]
        ),
    },
    {
        "id": "db-schema-review",
        "title": "Database schema review",
        "description": "Review schema design for correctness, indexes, and N+1 risks.",
        "cycle": "dream",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Review the database schema for {workspace} ({stack}). "
            "Identify: missing indexes, nullable columns that should be NOT NULL, "
            "foreign keys without cascades, N+1 query risks, and migration gaps. "
            "Write a schema review to "
            '.synlynk/project-docs/memory.md under "## Schema Review {date}" '
            "with a table: Issue → Table/Column → Severity → Fix."
        ),
        "est_hours": 1,
        "r_tokens": 40000,
        "w_tokens": 6000,
        "tool_calls": 10,
        "trigger_condition": lambda scan: scan.get("has_orm", False),
    },
]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_launch.py::test_launch_task_templates_count tests/test_launch.py::test_launch_task_templates_have_required_fields tests/test_launch.py::test_launch_task_templates_core_ids -v
```
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): add LAUNCH_TASK_TEMPLATES constant (12 templates) [T3]"
```

---

## Task 4: Template Matching + Selection

**Files:**
- Modify: `synlynk/__init__.py` — add `_template_matches()` and `_select_launch_tasks()` near the other `_launch_*` functions (insert after `LAUNCH_TASK_TEMPLATES`)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_launch.py`:

```python
def _minimal_scan(**kwargs):
    """Returns a scan dict with sensible defaults for testing."""
    base = {
        "workspace_name": "test-ws",
        "topology": "single",
        "repos": [{"name": "test-repo", "stack_labels": ["python"]}],
        "test_ratio": 0.5,
        "readme_word_count": 500,
        "has_ci": True,
        "has_docs": True,
        "has_type_hints": True,
        "has_orm": False,
    }
    base.update(kwargs)
    return base


def test_template_matches_core_always_eligible():
    scan = _minimal_scan()
    for t in synlynk.LAUNCH_TASK_TEMPLATES:
        if t["id"] in synlynk.CORE_TEMPLATE_IDS:
            assert synlynk._template_matches(t, scan), f"Core template '{t['id']}' should always match"


def test_template_matches_add_tests_triggered():
    scan = _minimal_scan(test_ratio=0.05)
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "add-tests")
    assert synlynk._template_matches(tmpl, scan)


def test_template_matches_add_tests_not_triggered():
    scan = _minimal_scan(test_ratio=0.5)
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "add-tests")
    assert not synlynk._template_matches(tmpl, scan)


def test_template_matches_setup_ci_triggered():
    scan = _minimal_scan(has_ci=False)
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "setup-ci")
    assert synlynk._template_matches(tmpl, scan)


def test_template_matches_type_safety_python_only():
    scan = _minimal_scan(has_type_hints=False,
                         repos=[{"name": "r", "stack_labels": ["node"]}])
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "type-safety")
    assert not synlynk._template_matches(tmpl, scan)


def test_select_tasks_returns_max_5():
    # Force all scan-triggered templates to match
    scan = _minimal_scan(
        test_ratio=0.0, has_ci=False, has_docs=False, readme_word_count=10,
        topology="multi", has_orm=True, has_type_hints=False,
        repos=[{"name": "r", "stack_labels": ["python", "react", "django", "next"]}]
    )
    tasks = synlynk._select_launch_tasks(scan)
    assert len(tasks) <= 5


def test_select_tasks_core_always_first():
    scan = _minimal_scan(test_ratio=0.0)  # triggers add-tests
    tasks = synlynk._select_launch_tasks(scan)
    core_ids = synlynk.CORE_TEMPLATE_IDS
    core_positions = [i for i, t in enumerate(tasks) if t["id"] in core_ids]
    non_core_positions = [i for i, t in enumerate(tasks) if t["id"] not in core_ids]
    if core_positions and non_core_positions:
        assert max(core_positions) < min(non_core_positions)


def test_select_tasks_empty_scan_returns_core_3():
    scan = {
        "workspace_name": "x", "topology": "single",
        "repos": [{"name": "r", "stack_labels": []}],
        "test_ratio": 1.0, "readme_word_count": 999, "has_ci": True,
        "has_docs": True, "has_type_hints": True, "has_orm": False,
    }
    tasks = synlynk._select_launch_tasks(scan)
    assert len(tasks) == 3
    assert {t["id"] for t in tasks} == synlynk.CORE_TEMPLATE_IDS
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_template_matches_core_always_eligible -v
```
Expected: `AttributeError: module 'synlynk' has no attribute '_template_matches'`

- [ ] **Step 3: Implement `_template_matches` and `_select_launch_tasks`**

Add after `LAUNCH_TASK_TEMPLATES` in `synlynk/__init__.py`:

```python
def _template_matches(template: dict, scan: dict) -> bool:
    """Returns True if the template's trigger condition is met by scan."""
    condition = template.get("trigger_condition")
    if condition is None:
        return True
    try:
        return bool(condition(scan))
    except Exception:
        return False


def _select_launch_tasks(scan: dict) -> list:
    """Returns ordered list of 3–5 matching templates (core first, bonus sorted by specificity)."""
    eligible = [t for t in LAUNCH_TASK_TEMPLATES if _template_matches(t, scan)]
    core = [t for t in eligible if t["id"] in CORE_TEMPLATE_IDS]
    bonus = [t for t in eligible if t["id"] not in CORE_TEMPLATE_IDS]
    return (core + bonus)[:5]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_launch.py -k "template_matches or select_tasks" -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): add _template_matches + _select_launch_tasks [T4]"
```

---

## Task 5: Prompt Rendering

**Files:**
- Modify: `synlynk/__init__.py` — add `_render_prompt()`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_launch.py`:

```python
def test_render_prompt_substitutes_all_variables():
    template = {
        "prompt_template": "Review {workspace} ({stack}) topology={topology} date={date} repo={repo_name}.",
    }
    scan = {
        "workspace_name": "myws",
        "repos": [{"name": "myrepo", "stack_labels": ["python", "fastapi"]}],
        "topology": "single",
    }
    result = synlynk._render_prompt(template, scan)
    assert "myws" in result
    assert "python, fastapi" in result
    assert "single" in result
    assert "{workspace}" not in result
    assert "{date}" not in result
    assert "myrepo" in result


def test_render_prompt_missing_variable_uses_empty_string():
    template = {"prompt_template": "Hello {unknown_var} world."}
    result = synlynk._render_prompt(template, {})
    assert "{unknown_var}" not in result
    assert "Hello" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_render_prompt_substitutes_all_variables -v
```
Expected: `AttributeError: module 'synlynk' has no attribute '_render_prompt'`

- [ ] **Step 3: Implement `_render_prompt`**

Add after `_select_launch_tasks` in `synlynk/__init__.py`:

```python
def _render_prompt(template: dict, scan: dict) -> str:
    """Substitutes {variables} in prompt_template from scan data. Missing vars → ''."""
    import datetime as _datetime
    repos = scan.get("repos", [])
    primary = repos[0] if repos else {}
    variables = {
        "workspace":  scan.get("workspace_name", ""),
        "stack":      ", ".join(primary.get("stack_labels", [])) or "unknown",
        "repo_name":  primary.get("name", ""),
        "topology":   scan.get("topology", "single"),
        "test_count": str(scan.get("test_ratio", 0)),
        "date":       _datetime.date.today().isoformat(),
        "agent":      template.get("agent", "claude"),
    }
    text = template.get("prompt_template", "")
    # Replace each {var} — missing vars become empty string (no KeyError)
    import re as _re
    def _replace(match):
        key = match.group(1)
        return variables.get(key, "")
    return _re.sub(r"\{(\w+)\}", _replace, text)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_launch.py::test_render_prompt_substitutes_all_variables tests/test_launch.py::test_render_prompt_missing_variable_uses_empty_string -v
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): add _render_prompt with variable substitution [T5]"
```

---

## Task 6: TUI Screen 1 — Task Selection

**Files:**
- Modify: `synlynk/__init__.py` — add `_launch_screen_tasks()` in the `_wiz_*` function region (after `_wiz_screen_launch`)

Terminal color constants (`_BOLD`, `_RESET`, `_CYAN`, `_GREEN`, `_DIM`, `_YELLOW`) already exist in `synlynk/__init__.py`. Check with `grep -n "_BOLD\|_RESET\|_CYAN" synlynk/__init__.py | head -5` if unsure of names.

- [ ] **Step 1: Write failing test**

Add to `tests/test_launch.py`:

```python
def test_launch_screen_tasks_skip_returns_none(monkeypatch):
    tasks = synlynk._select_launch_tasks(_minimal_scan())
    scan = _minimal_scan()
    # Simulate user pressing 's' (skip)
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: 's')
    result = synlynk._launch_screen_tasks(tasks, scan)
    assert result is None
```

- [ ] **Step 2: Run test to confirm it fails**

```
pytest tests/test_launch.py::test_launch_screen_tasks_skip_returns_none -v
```
Expected: `AttributeError: module 'synlynk' has no attribute '_launch_screen_tasks'`

- [ ] **Step 3: Implement `_launch_screen_tasks`**

Add after the `_wiz_*` helper functions block in `synlynk/__init__.py` (just before `wizard_init`):

```python
def _launch_screen_tasks(tasks: list, scan: dict):
    """Screen 1 — task selection TUI.

    Returns the chosen template dict, or None if user skips.
    Pressing [?] temporarily shows Screen 3 (cycles explainer) then returns here.
    """
    while True:
        _wiz_clear()
        ws_name = scan.get("workspace_name", "workspace")
        repos = scan.get("repos", [])
        primary = repos[0] if repos else {}
        stack = ", ".join(primary.get("stack_labels", [])) or "unknown"
        topology = scan.get("topology", "single")
        harnesses = scan.get("harnesses", [])
        agent_names = ", ".join(h["name"] for h in harnesses) or "none"

        print(f"\n  {_BOLD}{_CYAN}◆ synlynk launch{_RESET}")
        print(f"  {_DIM}{ws_name} · {stack} · {topology} repo · {agent_names}{_RESET}\n")
        print(f"  Where do you want to start?\n")

        cycle_ansi = {
            "dream":   "\033[38;5;141m",
            "design":  "\033[38;5;117m",
            "plan":    "\033[38;5;120m",
            "build":   "\033[38;5;221m",
            "ship":    "\033[38;5;210m",
            "sustain": "\033[38;5;246m",
        }

        for i, task in enumerate(tasks, 1):
            cycle = task.get("cycle", "dream")
            cycle_color = cycle_ansi.get(cycle, "")
            cycle_tag = f"{cycle_color}[{cycle.capitalize()}]{_RESET}"
            num_color = cycle_ansi.get(cycle, _CYAN)
            print(f"  {num_color}[{i}]{_RESET} {_BOLD}{task['title']}{_RESET}  {cycle_tag}")
            if task.get("trigger_condition") is not None:
                print(f"     {_YELLOW}⚡ scan found: {task['description']}{_RESET}")
            else:
                print(f"     {_DIM}{task['description']}{_RESET}")
            est = task.get("est_hours", 1)
            est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
            r = task.get("r_tokens", 0)
            w = task.get("w_tokens", 0)
            t = task.get("tool_calls", 0)
            r_str = f"{r // 1000}K" if r >= 1000 else str(r)
            w_str = f"{w // 1000}K" if w >= 1000 else str(w)
            print(f"     {_DIM}{est_str}  │  "
                  f"\033[38;5;117mR\033[0m {r_str} · "
                  f"\033[38;5;120mW\033[0m {w_str} · "
                  f"\033[38;5;221mT\033[0m {t}{_RESET}")
            print()

        print(f"  {_DIM}{'─' * 52}{_RESET}")
        print(f"  {_DIM}\033[38;5;117mR\033[0m{_DIM} read · "
              f"\033[38;5;120mW\033[0m{_DIM} write · "
              f"\033[38;5;221mT\033[0m{_DIM} tool calls · estimates based on task template{_RESET}")
        valid_keys = "".join(str(i) for i in range(1, len(tasks) + 1))
        print(f"  {_DIM}[{valid_keys}] pick   [?] cycles   [s] skip{_RESET}\n")

        key = _wiz_read_key()

        if key in ("s", "q", "\x03"):
            return None
        if key == "?":
            _launch_screen_cycles()
            continue
        if key.isdigit() and 1 <= int(key) <= len(tasks):
            return tasks[int(key) - 1]
        # invalid key — redraw
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_launch.py::test_launch_screen_tasks_skip_returns_none -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): add _launch_screen_tasks TUI [T6]"
```

---

## Task 7: TUI Screens 2 + 3

**Files:**
- Modify: `synlynk/__init__.py` — add `_launch_screen_preview()` and `_launch_screen_cycles()`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_launch.py`:

```python
def test_launch_screen_cycles_returns_on_any_key(monkeypatch, capsys):
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: 'x')
    synlynk._launch_screen_cycles()  # must not raise, must return
    out = capsys.readouterr().out
    assert "Dream" in out or "dream" in out.lower()


def test_launch_screen_preview_returns_confirmed_and_prompt(monkeypatch):
    task = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "arch-review")
    scan = _minimal_scan()
    # Simulate user pressing Enter (confirm)
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: '\r')
    confirmed, prompt = synlynk._launch_screen_preview(task, scan)
    assert confirmed is True
    assert isinstance(prompt, str)
    assert len(prompt) > 10


def test_launch_screen_preview_esc_returns_not_confirmed(monkeypatch):
    task = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "arch-review")
    scan = _minimal_scan()
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: '\x1b')
    confirmed, prompt = synlynk._launch_screen_preview(task, scan)
    assert confirmed is False
```

Note: `test_launch_screen_preview_edit_replaces_prompt` requires interactive `input()` — skip in unit tests (it will be manually verified).

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_launch_screen_cycles_returns_on_any_key tests/test_launch.py::test_launch_screen_preview_returns_confirmed_and_prompt -v
```
Expected: `AttributeError: module 'synlynk' has no attribute '_launch_screen_cycles'`

- [ ] **Step 3: Implement `_launch_screen_cycles`**

Add to `synlynk/__init__.py` (before `_launch_screen_tasks`):

```python
def _launch_screen_cycles() -> None:
    """Screen 3 — cycles explainer. Replaces Screen 1 temporarily; any key returns."""
    _wiz_clear()
    cycle_ansi = {
        "Dream":   "\033[38;5;141m",
        "Design":  "\033[38;5;117m",
        "Plan":    "\033[38;5;120m",
        "Build":   "\033[38;5;221m",
        "Ship":    "\033[38;5;210m",
        "Sustain": "\033[38;5;246m",
    }
    print(f"\n  {_BOLD}{_CYAN}◆ The 6 cycles — your multi-agent SDLC{_RESET}\n")
    cycle_agents = {
        "Dream":   "→ claude",
        "Design":  "→ claude",
        "Plan":    "→ claude",
        "Build":   "→ agy · codex · grok",
        "Ship":    "→ claude",
        "Sustain": "→ all agents",
    }
    for name, desc in [
        ("Dream",   "What's worth building? Ideate, assess, identify opportunities."),
        ("Design",  "Brainstorm → spec → UX. Turn ideas into a concrete brief."),
        ("Plan",    "Implementation plan, story breakdown, agent wave schedule."),
        ("Build",   "Dispatch agents, run jobs, iterate on diffs."),
        ("Ship",    "Cut release, changelog, publish."),
        ("Sustain", "Monitor, patch, community, docs, support."),
    ]:
        color = cycle_ansi.get(name, "")
        agents = cycle_agents.get(name, "")
        print(f"  {color}{_BOLD}{name:<8}{_RESET}  {_DIM}{desc}  {agents}{_RESET}")

    print(f"\n  {_DIM}Tasks in synlynk launch are tagged to the cycle they open.")
    print(f"  Any cycle can dispatch any agent.{_RESET}\n")
    print(f"  {_DIM}[any key] back to tasks{_RESET}\n")
    _wiz_read_key()
```

- [ ] **Step 4: Implement `_launch_screen_preview`**

Add to `synlynk/__init__.py` (after `_launch_screen_cycles`):

```python
def _launch_screen_preview(task: dict, scan: dict) -> tuple:
    """Screen 2 — dispatch preview.

    Returns (confirmed: bool, prompt: str).
    [enter] → (True, prompt)
    [e]     → drop into readline edit, then return (True, edited_prompt)
    [esc]   → (False, prompt)
    """
    prompt = _render_prompt(task, scan)

    while True:
        _wiz_clear()
        cycle = task.get("cycle", "dream")
        agent = task.get("agent", "claude")
        est = task.get("est_hours", 1)
        est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
        r = task.get("r_tokens", 0)
        w = task.get("w_tokens", 0)
        t = task.get("tool_calls", 0)
        r_str = f"{r // 1000}K" if r >= 1000 else str(r)
        w_str = f"{w // 1000}K" if w >= 1000 else str(w)

        cycle_ansi = {
            "dream":   "\033[38;5;141m",
            "design":  "\033[38;5;117m",
            "plan":    "\033[38;5;120m",
            "build":   "\033[38;5;221m",
            "ship":    "\033[38;5;210m",
            "sustain": "\033[38;5;246m",
        }
        cycle_color = cycle_ansi.get(cycle, "")

        print(f"\n  {_BOLD}{_CYAN}◆ Dispatch preview{_RESET}\n")
        print(f"  {_DIM}{'agent':<8}{_RESET}{agent}")
        print(f"  {_DIM}{'cycle':<8}{_RESET}{cycle_color}{cycle.capitalize()}{_RESET}")
        print(f"  {_DIM}{'mode':<8}{_RESET}{task.get('context_mode', 'full')} context")
        print(f"  {_DIM}{'est.':<8}{_RESET}{est_str}  │  "
              f"\033[38;5;117mR\033[0m {r_str} · "
              f"\033[38;5;120mW\033[0m {w_str} · "
              f"\033[38;5;221mT\033[0m {t}\n")

        print(f"  {_DIM}task prompt:{_RESET}")
        # Wrap prompt at 56 chars for the box
        words = prompt.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > 56:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)

        print(f"  ┌{'─' * 58}┐")
        for line in lines:
            print(f"  │ {line:<56} │")
        print(f"  └{'─' * 58}┘\n")

        print(f"  {_DIM}[enter] dispatch now   [e] edit prompt   [esc] back to tasks{_RESET}\n")

        key = _wiz_read_key()

        if key in ("\r", "\n", " "):
            return True, prompt
        if key in ("\x1b", "q"):
            return False, prompt
        if key in ("e", "E"):
            print(f"\n  Edit prompt (press Enter to confirm):\n  > ", end="", flush=True)
            try:
                edited = input().strip()
                if edited:
                    prompt = edited
            except (EOFError, KeyboardInterrupt):
                pass
            continue
        # any other key — redraw
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_launch.py::test_launch_screen_cycles_returns_on_any_key tests/test_launch.py::test_launch_screen_preview_returns_confirmed_and_prompt tests/test_launch.py::test_launch_screen_preview_esc_returns_not_confirmed -v
```
Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): add _launch_screen_cycles + _launch_screen_preview TUI [T7]"
```

---

## Task 8: `cmd_launch_ftue` + Config + Wizard + CLI Wiring

**Files:**
- Modify: `synlynk/__init__.py` (5 separate changes)

This task has the most moving parts. Work in this order: config → wizard → new cmd → CLI parser → CLI dispatch.

### 8a: Config default

- [ ] **Step 1: Write failing test**

Add to `tests/test_launch.py`:

```python
def test_auto_launch_config_default_true(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = synlynk.load_config()
    assert config.get("auto_launch_after_wizard") is True
```

- [ ] **Step 2: Run test to confirm it fails**

```
pytest tests/test_launch.py::test_auto_launch_config_default_true -v
```
Expected: `AssertionError`

- [ ] **Step 3: Add `auto_launch_after_wizard` to `load_config()` defaults**

In `load_config()` at line ~1721, in the `defaults = {` dict, add:

```python
        "auto_launch_after_wizard": True,
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_launch.py::test_auto_launch_config_default_true -v
```

### 8b: New `cmd_launch_ftue`

- [ ] **Step 5: Write failing tests**

Add to `tests/test_launch.py`:

```python
def test_cmd_launch_dry_run_prints_tasks_no_dispatch(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(synlynk, 'dispatch_agent', lambda *a, **kw: called.append(a))
    synlynk.cmd_launch_ftue(dry_run=True, list_mode=False)
    out = capsys.readouterr().out
    assert "arch-review" in out or "architecture" in out.lower()
    assert not called


def test_cmd_launch_list_prints_all_12_templates(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    synlynk.cmd_launch_ftue(dry_run=False, list_mode=True)
    out = capsys.readouterr().out
    for tmpl in synlynk.LAUNCH_TASK_TEMPLATES:
        assert tmpl["id"] in out
```

- [ ] **Step 6: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_cmd_launch_dry_run_prints_tasks_no_dispatch -v
```
Expected: `AttributeError: module 'synlynk' has no attribute 'cmd_launch_ftue'`

- [ ] **Step 7: Implement `cmd_launch_ftue`**

Add after `_launch_screen_preview` in `synlynk/__init__.py`:

```python
def cmd_launch_ftue(dry_run: bool = False, list_mode: bool = False) -> None:
    """FTUE task picker — Screen 1 → Screen 2 → dispatch.

    dry_run: print selected tasks without showing TUI or dispatching.
    list_mode: print the full template pool with trigger conditions, then exit.
    """
    if list_mode:
        print(f"\n  {_BOLD}synlynk launch — task template pool ({len(LAUNCH_TASK_TEMPLATES)} templates){_RESET}\n")
        for t in LAUNCH_TASK_TEMPLATES:
            cond = t.get("trigger_condition")
            cond_str = "always" if cond is None else "(scan condition)"
            marker = "●" if t["id"] in CORE_TEMPLATE_IDS else "○"
            print(f"  {marker} {t['id']:<24}  {t['cycle']:<8}  {t['agent']:<8}  {cond_str}")
        print()
        return

    # Load scan from state.db if available; fall back to fresh scan
    try:
        scan = run_workspace_scan()
    except Exception:
        scan = {
            "workspace_name": os.path.basename(os.getcwd()) or "workspace",
            "topology": "single",
            "repos": [{"name": os.path.basename(os.getcwd()), "stack_labels": []}],
            "harnesses": [], "agents": [], "skills": [],
            "test_ratio": 1.0, "readme_word_count": 0,
            "has_ci": False, "has_docs": False,
            "has_type_hints": False, "has_orm": False,
        }

    tasks = _select_launch_tasks(scan)

    if dry_run:
        print(f"\n  {_BOLD}synlynk launch — dry run{_RESET}  "
              f"{_DIM}workspace: {scan.get('workspace_name', 'unknown')}{_RESET}\n")
        for i, t in enumerate(tasks, 1):
            est = t.get("est_hours", 1)
            est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
            print(f"  [{i}] {t['id']:<24} {t['cycle']:<8}  {t['agent']:<8}  {est_str}")
        print()
        return

    # TUI loop: Screen 1 → (Screen 2 or Screen 3) → dispatch or exit
    while True:
        chosen = _launch_screen_tasks(tasks, scan)
        if chosen is None:
            return  # user skipped

        confirmed, prompt = _launch_screen_preview(chosen, scan)
        if not confirmed:
            continue  # back to Screen 1

        # Dispatch
        try:
            job = dispatch_agent(
                agent=chosen["agent"],
                task=prompt,
                story_id=None,
                force_agent=True,
                context_mode=chosen.get("context_mode", "full"),
            )
            job_id = job.get("job_id", "unknown") if isinstance(job, dict) else "dispatched"
            print(f"\n  {_GREEN}▶{_RESET} [{job_id}] {chosen['agent']} dispatched\n"
                  f"  {_DIM}Log: synlynk logs --job {job_id}{_RESET}\n")
        except Exception as exc:
            print(f"\n  {_YELLOW}⚠ Dispatch failed: {exc}{_RESET}\n")
        return
```

- [ ] **Step 8: Run tests to verify they pass**

```
pytest tests/test_launch.py::test_cmd_launch_dry_run_prints_tasks_no_dispatch tests/test_launch.py::test_cmd_launch_list_prints_all_12_templates -v
```

### 8c: Wizard Screen 6 update

- [ ] **Step 9: Write failing test**

Add to `tests/test_launch.py`:

```python
def test_wizard_calls_cmd_launch_when_auto_launch_true(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = []

    def fake_cmd_launch_ftue(**kwargs):
        called.append(kwargs)

    monkeypatch.setattr(synlynk, 'cmd_launch_ftue', fake_cmd_launch_ftue)
    # Patch _wiz_read_key to return immediately on Screen 6
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: '\r')

    scan = {
        "workspace_name": "test-ws", "topology": "single",
        "repos": [{"name": "r", "stack_labels": []}],
        "harnesses": [], "agents": [], "skills": [], "home_harness": "claude",
        "scanned_at": "", "test_ratio": 1.0, "readme_word_count": 0,
        "has_ci": False, "has_docs": False, "has_type_hints": False, "has_orm": False,
    }
    config = synlynk.load_config()
    config["auto_launch_after_wizard"] = True
    monkeypatch.setattr(synlynk, 'load_config', lambda: config)

    synlynk._wiz_screen_launch(
        workspace={"workspace_name": "test-ws", "home_harness": "claude"},
        scan=scan,
        auto_launch=True,
    )
    assert called, "cmd_launch_ftue should have been called"


def test_wizard_skips_cmd_launch_when_auto_launch_false(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(synlynk, 'cmd_launch_ftue', lambda **kw: called.append(kw))
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: '\r')

    synlynk._wiz_screen_launch(
        workspace={"workspace_name": "test-ws", "home_harness": "claude"},
        scan={"workspace_name": "test-ws", "home_harness": "claude"},
        auto_launch=False,
    )
    assert not called
```

- [ ] **Step 10: Run tests to confirm they fail**

```
pytest tests/test_launch.py::test_wizard_calls_cmd_launch_when_auto_launch_true -v
```
Expected: `TypeError: _wiz_screen_launch() got an unexpected keyword argument 'auto_launch'`

- [ ] **Step 11: Update `_wiz_screen_launch` signature and body**

Current signature at line ~9023:
```python
def _wiz_screen_launch(workspace: dict, scan: dict) -> None:
```

Change to:
```python
def _wiz_screen_launch(workspace: dict, scan: dict, auto_launch: bool = False) -> None:
```

At the end of `_wiz_screen_launch`, after `_wiz_read_key()`, add:

```python
    if auto_launch:
        cmd_launch_ftue()
```

Also update the footer line to include the launch hint. Find this line:
```python
    _wiz_prompt("done · run `synlynk help` for all commands")
```
Change to:
```python
    _wiz_prompt("done · run `synlynk launch` to pick your first task")
```

- [ ] **Step 12: Update `wizard_init()` to pass `auto_launch`**

In `wizard_init()`, find the line:
```python
    _wiz_screen_launch(workspace, scan)
```

Change to:
```python
    cfg = load_config()
    _wiz_screen_launch(workspace, scan,
                       auto_launch=cfg.get("auto_launch_after_wizard", True))
```

- [ ] **Step 13: Run wizard tests**

```
pytest tests/test_launch.py::test_wizard_calls_cmd_launch_when_auto_launch_true tests/test_launch.py::test_wizard_skips_cmd_launch_when_auto_launch_false -v
```
Expected: both PASS.

### 8d: CLI parser — rename `launch` → `open`, add new `launch`

- [ ] **Step 14: Rename existing launch parser and handler**

In `synlynk/__init__.py`, find (line ~9684):
```python
    launch_parser = subparsers.add_parser(
        "launch", help="Launch an agent CLI interactively with pre-loaded context")
    launch_parser.add_argument("agent", help="Agent name: claude, agy, codex, grok")
    launch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")
```

Change to:
```python
    open_parser = subparsers.add_parser(
        "open", help="Open an agent CLI interactively with pre-loaded context")
    open_parser.add_argument("agent", help="Agent name: claude, agy, codex, grok")
    open_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")
```

Add the new `launch` subparser directly after:
```python
    launch_parser = subparsers.add_parser(
        "launch", help="Pick your first task and dispatch it (FTUE task picker)")
    launch_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
        help="Print selected tasks without showing TUI or dispatching")
    launch_parser.add_argument("--list", action="store_true", dest="list_mode",
        help="Print full template pool with trigger conditions (debug)")
```

- [ ] **Step 15: Update CLI dispatch block**

In `main()`, find (line ~9842):
```python
    elif args.command == "launch":
        cmd_launch(args.agent, story_id=getattr(args, "story_id", None))
```

Change to:
```python
    elif args.command == "open":
        cmd_launch(args.agent, story_id=getattr(args, "story_id", None))
    elif args.command == "launch":
        cmd_launch_ftue(
            dry_run=getattr(args, "dry_run", False),
            list_mode=getattr(args, "list_mode", False),
        )
```

- [ ] **Step 16: Run the full test suite**

```
pytest tests/ -x -q 2>&1 | tail -15
```
Expected: all tests pass. Check `test_launch.py` count: should be 20.

- [ ] **Step 17: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat(bs19): cmd_launch_ftue + wizard auto_launch + CLI wiring (launch/open) [T8]"
```

---

## Final Validation

- [ ] **Smoke test — dry run**

```
python3 bin/synlynk.py launch --dry-run
```
Expected: prints 3–5 task rows with id, cycle, agent, est.

- [ ] **Smoke test — list mode**

```
python3 bin/synlynk.py launch --list
```
Expected: prints all 12 template IDs.

- [ ] **Smoke test — help**

```
python3 bin/synlynk.py launch --help
python3 bin/synlynk.py open --help
```
Expected: both parsers print usage.

- [ ] **Run full suite + count**

```
pytest tests/ -q 2>&1 | tail -5
```
Expected: 20 new tests in test_launch.py + all existing tests pass.

- [ ] **Final commit**

```bash
git add -A
git commit -m "feat(bs19): smoke test validation pass" --allow-empty
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|-----------------|------|
| 6-cycle rename + constants | T1 |
| Scan additions (6 fields) | T2 |
| `LAUNCH_TASK_TEMPLATES` (12 templates) | T3 |
| `_template_matches` / `_select_launch_tasks` | T4 |
| `_render_prompt` with variable substitution | T5 |
| Screen 1 TUI with cycle colors + R/W/T | T6 |
| Screen 2 dispatch preview + [e] edit | T7 |
| Screen 3 cycles explainer | T7 |
| `cmd_launch_ftue` with dry-run + list modes | T8 |
| `auto_launch_after_wizard` config default | T8 |
| `_wiz_screen_launch` footer + auto_launch | T8 |
| `wizard_init()` passes auto_launch | T8 |
| CLI `launch` subparser (new) | T8 |
| CLI `open` subparser (renamed from `launch`) | T8 |
| All 20 tests | T1–T8 |

**All 20 spec tests covered:**

| Test | Task |
|------|------|
| `test_cycle_names_constant_exists` | T1 |
| `test_cycle_colors_constant_exists` | T1 |
| `test_cycle_rename_migration_idempotent` | T1 |
| `test_scan_returns_test_ratio` | T2 |
| `test_scan_returns_has_ci_false_when_absent` | T2 |
| `test_scan_returns_readme_word_count` | T2 |
| `test_launch_task_templates_count` | T3 |
| `test_launch_task_templates_have_required_fields` | T3 |
| `test_launch_task_templates_core_ids` | T3 |
| `test_template_matches_core_always_eligible` | T4 |
| `test_template_matches_add_tests_triggered` | T4 |
| `test_template_matches_add_tests_not_triggered` | T4 |
| `test_template_matches_setup_ci_triggered` | T4 |
| `test_template_matches_type_safety_python_only` | T4 |
| `test_select_tasks_returns_max_5` | T4 |
| `test_select_tasks_core_always_first` | T4 |
| `test_select_tasks_empty_scan_returns_core_3` | T4 |
| `test_render_prompt_substitutes_all_variables` | T5 |
| `test_render_prompt_missing_variable_uses_empty_string` | T5 |
| `test_launch_screen_tasks_skip_returns_none` | T6 |
| `test_launch_screen_cycles_returns_on_any_key` | T7 |
| `test_launch_screen_preview_returns_confirmed_and_prompt` | T7 |
| `test_launch_screen_preview_esc_returns_not_confirmed` | T7 |
| `test_cmd_launch_dry_run_prints_tasks_no_dispatch` | T8 |
| `test_cmd_launch_list_prints_all_12_templates` | T8 |
| `test_auto_launch_config_default_true` | T8 |
| `test_wizard_calls_cmd_launch_when_auto_launch_true` | T8 |
| `test_wizard_skips_cmd_launch_when_auto_launch_false` | T8 |
