"""Launch task template catalog for ``synlynk launch``
Extracted from synlynk/__init__.py (R12, 2026-09-29) - pure data, no logic
"""
LAUNCH_TASK_TEMPLATES = [
    # ── Core templates (always shown) ───────────────────────────────────────
    {
        "id": "arch-review",
        "title": "Workspace architecture review",
        "description": "Analyse structure, patterns, tech debt. Claude writes findings to memory.md.",
        "cycle": "visualize",
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
        "cycle": "goal",
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
        "title": "Set up 7-stage GOVERNS workflow for this repo",
        "description": "Initialise GOVERNS lifecycle tracking in state.db. Label open stories by stage.",
        "cycle": "open",
        "agent": "claude",
        "context_mode": "task",
        "prompt_template": (
            "Set up the 7-stage GOVERNS workflow for {workspace}. "
            "Run `synlynk story list` to see existing stories. "
            "For each story, assign a cycle phase (goal/open/visualize/execute/release/notify/sustain) "
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
        "cycle": "execute",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "Add pytest tests for {workspace}. "
            "Target the following untested public functions in {repo_name}: "
            "{gap_functions}. "
            "For each function: write a test file if one doesn't exist, add at minimum "
            "one happy-path test and one edge-case test. Use the existing test patterns "
            "in tests/. Do not mock internal functions or the filesystem unless unavoidable. "
            "Commit each test file with 'test: add coverage for <function>'."
        ),
        "est_hours": 3,
        "r_tokens": 60000,
        "w_tokens": 20000,
        "tool_calls": 30,
        "trigger_condition": lambda scan: (
            (scan.get("tests") or {}).get("gap_count", 0) > 5
            or scan.get("test_ratio", 1.0) < 0.1
        ),
    },
    {
        "id": "setup-ci",
        "title": "Set up CI/CD pipeline",
        "description": "Create a GitHub Actions workflow for tests and linting.",
        "cycle": "execute",
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
        "cycle": "notify",
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
        "cycle": "sustain",
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
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["python", "node", "ruby"]
        ),
    },
    {
        "id": "perf-baseline",
        "title": "Performance baseline + profiling plan",
        "description": "Identify hot paths and draft a performance improvement plan.",
        "cycle": "sustain",
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
        "cycle": "visualize",
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
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "Add type annotations to the public API of {workspace} ({stack}). "
            "The codebase is currently {typed_pct}% typed. "
            "Target all functions and methods exported or called from tests. "
            "Use Python type hints (PEP 484). Do not annotate private (_-prefixed) helpers "
            "unless they are called by public functions. "
            "Commit each annotated file separately with 'refactor: add type hints to <module>'."
        ),
        "est_hours": 3,
        "r_tokens": 120000,
        "w_tokens": 30000,
        "tool_calls": 45,
        "trigger_condition": lambda scan: (
            any(lbl == "python" for lbl in scan.get("repos", [{}])[0].get("stack_labels", []))
            and (
                (
                    scan.get("source") is not None
                    and sum(f.get("typed_pct", 0) for f in scan["source"]) / max(len(scan["source"]), 1) < 40
                )
                or not scan.get("has_type_hints", True)
            )
        ),
    },
    {
        "id": "a11y-audit",
        "title": "Accessibility audit",
        "description": "Audit the frontend for WCAG 2.1 AA compliance gaps.",
        "cycle": "release",
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
        "cycle": "visualize",
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
    {
        "id": "refactor-module",
        "title": "Refactor large module",
        "description": "Split monolithic source file into focused modules.",
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "The file {largest_file} in {workspace} has grown to {largest_file_lines} lines "
            "with {largest_file_fns} functions. Refactor it: "
            "identify 3-5 logical groupings of functions, extract each group into a new "
            "module under the same package directory, update all imports, and ensure the "
            "test suite still passes. The largest function is {largest_fn} at {largest_fn_lines} lines - "
            "break it down if it has multiple responsibilities. "
            "Commit each extracted module separately."
        ),
        "est_hours": 4,
        "r_tokens": 200000,
        "w_tokens": 50000,
        "tool_calls": 60,
        "trigger_condition": lambda scan: (
            bool(scan.get("source"))
            and any(f.get("lines", 0) > 5000 for f in (scan.get("source") or []))
        ),
    },
    {
        "id": "reduce-complexity",
        "title": "Reduce complexity hotspots",
        "description": "Break down functions >50 lines into focused helpers.",
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "Reduce complexity in {workspace}. The top hotspot is {top_hotspot} "
            "({top_hotspot_lines} lines). For each of the top 3 complexity hotspots: "
            "extract sub-responsibilities into named helper functions, add a docstring "
            "explaining what each piece does, and ensure tests still pass. "
            "Do not change observable behaviour. "
            "Commit each refactored function separately."
        ),
        "est_hours": 3,
        "r_tokens": 120000,
        "w_tokens": 40000,
        "tool_calls": 40,
        "trigger_condition": lambda scan: (
            len((scan.get("complexity") or {}).get("hotspots", [])) > 2
        ),
    },
    {
        "id": "fix-churn-debt",
        "title": "Address hot file tech debt",
        "description": "Stabilise the most-changed file with tests + docstrings.",
        "cycle": "sustain",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "The file {hot_file} in {workspace} has been modified {commit_count} times "
            "in the last 30 commits - it is the highest-churn file in the repo. "
            "Stabilise it by: adding docstrings to all public functions that lack them, "
            "writing tests for any public function with no test (check test_ratio first), "
            "and adding a module-level docstring explaining the file's responsibility. "
            "Commit each category of change separately."
        ),
        "est_hours": 2,
        "r_tokens": 80000,
        "w_tokens": 20000,
        "tool_calls": 25,
        "trigger_condition": lambda scan: (
            bool((scan.get("git") or {}).get("churn"))
            and (scan.get("git") or {}).get("churn", [{}])[0].get("commits", 0) > 30
        ),
    },
]
