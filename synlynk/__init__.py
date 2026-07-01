#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import shutil
import time
import json
import re
import threading
import urllib.request
from typing import Optional
import sqlite3 as _sqlite3

VERSION = "0.10.0"

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
    "dream":   "What's worth building\nIdeate, assess, identify opportunities\n",
    "design":  "Brainstorm -> spec -> UX\nTurn ideas into a concrete brief\n",
    "plan":    "Implementation plan, story breakdown, agent wave schedule\n",
    "build":   "Dispatch agents, run jobs, iterate on diffs\n",
    "ship":    "Cut release, changelog, publish\n",
    "sustain": "Monitor, patch, community, docs, support\n",
}

CYCLE_DEFAULT_AGENTS = {
    "dream":   ["claude"],
    "design":  ["claude"],
    "plan":    ["claude"],
    "build":   ["agy", "codex", "grok"],
    "ship":    ["claude"],
    "sustain": ["claude", "agy", "codex", "grok"],
}

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
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["python", "node", "ruby"]
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
    """Returns ordered list of 3-5 matching templates (core first, bonus sorted by specificity)."""
    eligible = [t for t in LAUNCH_TASK_TEMPLATES if _template_matches(t, scan)]
    core = [t for t in eligible if t["id"] in CORE_TEMPLATE_IDS]
    bonus = [t for t in eligible if t["id"] not in CORE_TEMPLATE_IDS]
    return (core + bonus)[:5]


def _render_prompt(template: dict, scan: dict) -> str:
    """Substitutes {variables} in prompt_template from scan data. Missing vars become ''."""
    import datetime as _datetime
    import re as _re

    repos = scan.get("repos", [])
    primary = repos[0] if repos else {}
    variables = {
        "workspace": scan.get("workspace_name", ""),
        "stack": ", ".join(primary.get("stack_labels", [])) or "unknown",
        "repo_name": primary.get("name", ""),
        "topology": scan.get("topology", "single"),
        "test_count": str(scan.get("test_ratio", 0)),
        "date": _datetime.date.today().isoformat(),
        "agent": template.get("agent", "claude"),
    }
    text = template.get("prompt_template", "")

    def _replace(match):
        key = match.group(1)
        return variables.get(key, "")

    return _re.sub(r"\{(\w+)\}", _replace, text)


TASK_STATUSES = {
    "[ ]": "active",
    "[x]": "done",
    "[-]": "deferred",
    "[~]": "superseded",
    "[>]": "absorbed",
}


def _resolve_db_path() -> str:
    """Centralise DB at ~/.synlynk/projects/<key>/state.db so all worktrees share one DB.

    Key is an 8-char MD5 of the git repo root (common dir parent), falling back to CWD.
    This avoids the .synlynk/state flat-file collision and the per-worktree isolation bug.
    """
    import hashlib as _h
    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"], stderr=subprocess.DEVNULL
        ).decode().strip()
        root = os.path.abspath(os.path.join(common, ".."))
    except Exception:
        root = os.getcwd()
    key = _h.md5(root.encode()).hexdigest()[:8]
    return os.path.expanduser(f"~/.synlynk/projects/{key}/state.db")


DB_PATH = _resolve_db_path()

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS stories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL UNIQUE,
    title         TEXT,
    estimated_tokens INTEGER,
    actual_tokens INTEGER,
    engg_domain   TEXT DEFAULT 'unknown',
    org_domain    TEXT DEFAULT 'unknown',
    org_domain_tags TEXT DEFAULT '[]',
    industry      TEXT DEFAULT 'unknown',
    phase         TEXT DEFAULT 'build',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS capability_ratings (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id              TEXT NOT NULL REFERENCES stories(story_id),
    agent                 TEXT NOT NULL,
    model_version         TEXT NOT NULL DEFAULT 'unknown',
    model_at_dispatch     TEXT,
    model_at_completion   TEXT,
    split_model           INTEGER DEFAULT 0,
    engg_domain           TEXT NOT NULL DEFAULT 'unknown',
    org_domain            TEXT NOT NULL DEFAULT 'unknown',
    org_domain_tags       TEXT DEFAULT '[]',
    industry              TEXT NOT NULL DEFAULT 'unknown',
    phase                 TEXT NOT NULL DEFAULT 'build',
    signal_source         TEXT NOT NULL DEFAULT 'auto',
    quality               REAL NOT NULL DEFAULT 0.0,
    quality_auto          REAL,
    verifier_agent        TEXT,
    verifier_model        TEXT,
    test_pass_rate        REAL,
    build_success         INTEGER,
    dispatch_rework       INTEGER DEFAULT 0,
    micro_rework          INTEGER DEFAULT 0,
    pr_review_cycles      INTEGER DEFAULT 0,
    duration_vs_estimate  REAL,
    verified_by_ci        INTEGER,
    correct               INTEGER DEFAULT 1,
    note                  TEXT,
    ed25519_sig           TEXT,
    ts                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    head_sha    TEXT NOT NULL,
    file        TEXT NOT NULL,
    language    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    line        INTEGER,
    scanned_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_symbols_head ON source_symbols(head_sha);
CREATE INDEX IF NOT EXISTS idx_source_symbols_file ON source_symbols(file);

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
    story_id      TEXT,
    ts            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_hash ON autopilot_runs(signal_hash, ts);

CREATE TABLE IF NOT EXISTS daemon_jobs (
    job_id       TEXT PRIMARY KEY,
    agent        TEXT NOT NULL,
    task         TEXT NOT NULL,
    story_id     TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',
    priority     INTEGER NOT NULL DEFAULT 5,
    depends_on   TEXT NOT NULL DEFAULT '[]',
    pid          INTEGER,
    enqueued_at  TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    exit_code    INTEGER,
    log_path     TEXT
);
CREATE INDEX IF NOT EXISTS idx_daemon_jobs_status ON daemon_jobs(status);
"""

_DB_SCORES_VIEW = """
CREATE VIEW IF NOT EXISTS capability_scores AS
SELECT
    agent,
    model_version,
    engg_domain,
    org_domain,
    industry,
    phase,
    SUM(quality * pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER))) /
      SUM(pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER)))
      AS weighted_score,
    COUNT(*) AS sample_count,
    MAX(ts) AS last_seen
FROM capability_ratings
WHERE split_model = 0
GROUP BY agent, model_version, engg_domain, org_domain, industry, phase;
"""

def _get_db() -> _sqlite3.Connection:
    """Returns a WAL-mode SQLite connection to state.db, running migrations."""
    db_path = DB_PATH
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except PermissionError:
        db_path = os.path.join(os.getcwd(), ".synlynk", "state.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = _sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_db(conn)
    return conn

def _migrate_db(conn: _sqlite3.Connection) -> None:
    """Idempotent schema migrations. Adds tables/views if absent."""
    conn.executescript(_DB_SCHEMA)
    story_cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    if "estimated_tokens" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN estimated_tokens INTEGER")
    if "actual_tokens" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN actual_tokens INTEGER")
    if "status" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
    try:
        conn.executescript(_DB_SCORES_VIEW)
    except _sqlite3.OperationalError:
        pass  # view already exists with same definition
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS harness_baselines (
            harness_name TEXT NOT NULL,
            cli_version TEXT NOT NULL DEFAULT 'any',
            headless_contract TEXT NOT NULL DEFAULT '{}',
            dispatch_flags TEXT NOT NULL DEFAULT '{}',
            network_deps TEXT NOT NULL DEFAULT '{}',
            baseline_source TEXT NOT NULL DEFAULT 'curated',
            PRIMARY KEY (harness_name, cli_version)
        );

        CREATE TABLE IF NOT EXISTS harness_records (
            agent_name TEXT PRIMARY KEY,
            harness_name TEXT NOT NULL,
            installed_version TEXT NOT NULL DEFAULT 'unknown',
            compliance_status TEXT NOT NULL DEFAULT 'unknown',
            active_contract TEXT NOT NULL DEFAULT '{}',
            active_flags TEXT NOT NULL DEFAULT '{}',
            last_probe_at TEXT,
            capability_hash TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS harness_verb_map (
            synlynk_verb TEXT NOT NULL,
            verb_category TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            agent_command TEXT,
            supported TEXT NOT NULL DEFAULT 'none',
            partial_notes TEXT,
            min_cli_version TEXT,
            PRIMARY KEY (synlynk_verb, agent_name)
        );

        CREATE TABLE IF NOT EXISTS harness_command_palette (
            harness_name TEXT NOT NULL,
            cli_version TEXT NOT NULL,
            command TEXT NOT NULL,
            command_type TEXT NOT NULL,
            synlynk_verb TEXT,
            help_text TEXT,
            first_seen_version TEXT NOT NULL,
            last_seen_version TEXT,
            PRIMARY KEY (harness_name, cli_version, command)
        );

        CREATE TABLE IF NOT EXISTS harness_version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            cli_version TEXT NOT NULL,
            event_type TEXT NOT NULL,
            prev_hash TEXT,
            new_hash TEXT,
            recorded_at TEXT NOT NULL
        );
    """)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memory_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            section     TEXT NOT NULL,
            body        TEXT NOT NULL,
            author      TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS roadmap_arcs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            version     TEXT NOT NULL UNIQUE,
            title       TEXT,
            status      TEXT DEFAULT 'planned',
            target_date TEXT,
            notes       TEXT
        );
        CREATE TABLE IF NOT EXISTS roadmap_phases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
            phase_title TEXT NOT NULL,
            status      TEXT DEFAULT 'planned',
            priority    TEXT,
            story_id    TEXT REFERENCES stories(story_id),
            notes       TEXT
        );
        CREATE TABLE IF NOT EXISTS cost_entries (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date      TEXT NOT NULL,
            agent             TEXT,
            model             TEXT,
            input_tokens      INTEGER,
            output_tokens     INTEGER,
            cache_read_tokens INTEGER,
            total_cost_usd    REAL,
            notes             TEXT,
            recorded_at       TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS devlog_entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            author        TEXT NOT NULL,
            entry_date    TEXT NOT NULL,
            session_title TEXT,
            body          TEXT NOT NULL,
            recorded_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_devlog_author ON devlog_entries(author);
        CREATE INDEX IF NOT EXISTS idx_devlog_date   ON devlog_entries(entry_date);
    """)
    # Idempotent cycle rename: old names -> new names (no-ops if tables/columns absent)
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
    import json as _json
    _HARNESS_MAP = {"claude": "claude-cli", "agy": "agy", "grok": "grok", "codex": "codex"}
    for _agent_name, _baseline in AGENT_CAPABILITY_BASELINES.items():
        _harness_name = _HARNESS_MAP.get(_agent_name, _agent_name)
        conn.execute("""
            INSERT OR IGNORE INTO harness_baselines
                (harness_name, cli_version, headless_contract, dispatch_flags, network_deps, baseline_source)
            VALUES (?, 'any', ?, ?, ?, 'curated')
        """, (
            _harness_name,
            _json.dumps(_baseline.get("headless_contract", {})),
            _json.dumps(_baseline.get("dispatch_flags", {})),
            _json.dumps(_baseline.get("network_deps", {})),
        ))
    try:
        conn.execute("ALTER TABLE stories ADD COLUMN gh_issue TEXT")
    except Exception:
        pass
    conn.commit()
    # v0.9.2: token budget columns on stories
    for _col, _typedef in [("estimated_tokens", "INTEGER"), ("actual_tokens", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE stories ADD COLUMN {_col} {_typedef}")
        except Exception:
            pass  # column already exists
    conn.commit()
    _seed_verb_map(conn)


def _parse_memory_md(content: str) -> list:
    sections = []
    current_section = None
    current_body = []
    for line in content.splitlines(keepends=True):
        m = re.match(r'^## (.+)', line)
        if m:
            if current_section is not None:
                body = ''.join(current_body).strip()
                author_m = re.search(r'\[@(\w+)\]', body)
                sections.append({'section': current_section, 'body': body,
                                 'author': author_m.group(1) if author_m else None})
            current_section = m.group(1).strip()
            current_body = []
        elif current_section is not None:
            current_body.append(line)
    if current_section is not None and current_body:
        body = ''.join(current_body).strip()
        author_m = re.search(r'\[@(\w+)\]', body)
        sections.append({'section': current_section, 'body': body,
                         'author': author_m.group(1) if author_m else None})
    return sections


def _parse_roadmap_md(content: str) -> tuple:
    arcs, phases, current_arc = [], [], None
    for line in content.splitlines():
        arc_m = re.match(r'^## (v[\d.]+[\w.-]*)\s*[-—]?\s*(.*)', line)
        if arc_m:
            version = arc_m.group(1).strip()
            title = arc_m.group(2).strip() or None
            status = ('shipped' if ('✅' in line or 'shipped' in line.lower()) else
                      'in_progress' if ('🚧' in line or 'in progress' in line.lower()) else 'planned')
            current_arc = {'version': version, 'title': title, 'status': status}
            arcs.append(current_arc)
            continue
        if current_arc is None:
            continue
        phase_m = re.match(r'^[-*]\s+(.+)', line)
        if phase_m:
            text = phase_m.group(1).strip()
            priority = next((p for p in ('P0', 'P1', 'daily-driver')
                             if f'({p})' in text or f'[{p}]' in text), None)
            status = ('shipped' if '✅' in text else
                      'in_progress' if '🚧' in text else 'planned')
            phases.append({'arc_version': current_arc['version'], 'phase_title': text,
                           'status': status, 'priority': priority, 'story_id': None, 'notes': None})
    return arcs, phases


def _parse_costs_md(content: str) -> list:
    rows = []
    for line in content.splitlines():
        if not line.startswith('|') or '---' in line:
            continue
        cells = [c.strip().lstrip('~') for c in line.split('|')[1:-1]]
        if len(cells) < 2:
            continue
        date = cells[0]
        if not date or not re.match(r'\d{4}', date) or date.lower() in ('date', 'session', 'timestamp'):
            continue
        def _int(v):
            try: return int(v.replace(',', ''))
            except: return None
        def _float(v):
            try: return float(v.replace('$', '').replace(',', ''))
            except: return None
        rows.append({'session_date': date,
                     'agent': cells[1] if len(cells) > 1 else None,
                     'model': cells[2] if len(cells) > 2 else None,
                     'input_tokens': _int(cells[3]) if len(cells) > 3 else None,
                     'output_tokens': _int(cells[4]) if len(cells) > 4 else None,
                     'cache_read_tokens': _int(cells[5]) if len(cells) > 5 else None,
                     'total_cost_usd': _float(cells[6]) if len(cells) > 6 else None,
                     'notes': cells[7] if len(cells) > 7 else None})
    return rows


def _parse_devlog_file(content: str, author: str) -> list:
    entries, current_date, current_title, current_body = [], None, None, []
    for line in content.splitlines(keepends=True):
        m = re.match(r'^## (\d{4}-\d{2}-\d{2})(?:\s*[—-]\s*(?:Session:\s*)?(.+))?', line)
        if m:
            if current_date and current_body:
                entries.append({'author': author, 'entry_date': current_date,
                                 'session_title': current_title, 'body': ''.join(current_body).strip()})
            current_date = m.group(1)
            raw = m.group(2)
            current_title = raw.strip() if raw else None
            current_body = []
        elif current_date is not None:
            current_body.append(line)
    if current_date and current_body:
        entries.append({'author': author, 'entry_date': current_date,
                         'session_title': current_title, 'body': ''.join(current_body).strip()})
    return entries


def _parse_todo_metadata(content: str) -> list:
    results = []
    for line in content.splitlines():
        id_m = re.search(r'<!--\s*id:(story-[\w-]+)\s*-->', line)
        if not id_m:
            continue
        gh_m = re.search(r'<!--\s*gh:(#\d+)\s*-->', line)
        pri_m = re.search(r'<!--\s*priority:([\w-]+)\s*-->', line)
        if gh_m or pri_m:
            results.append({'story_id': id_m.group(1),
                             'gh_issue': gh_m.group(1) if gh_m else None,
                             'priority': pri_m.group(1) if pri_m else None})
    return results


def _is_migrated() -> bool:
    return os.path.exists(os.path.join('.synlynk', '.synlynk_migrated'))


def _synlynk_project_docs_dir() -> str:
    return os.path.join('.synlynk', 'project-docs')


def _dr_sync(relative_path: str) -> None:
    try:
        cfg_path = os.path.join('.synlynk', 'config.json')
        if not os.path.exists(cfg_path):
            return
        with open(cfg_path) as f:
            cfg = json.load(f)
        dr_path = cfg.get('dr_sync_path')
        if not dr_path:
            return
        dr_path = os.path.expanduser(str(dr_path))
        if not os.path.isdir(dr_path):
            return
        src = os.path.join('.synlynk', 'project-docs', relative_path)
        if not os.path.exists(src):
            return
        dst = os.path.join(dr_path, 'project-docs', relative_path)
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        import shutil as _shutil
        _shutil.copy2(src, dst)
    except Exception:
        pass


def _migrate_import(docs_dir: str, dry_run: bool = False) -> None:
    """Parse flat files in docs_dir -> state.db. Prints import summary."""
    conn = _get_db()
    counts = {}

    memory_path = os.path.join(docs_dir, "memory.md")
    if os.path.exists(memory_path):
        with open(memory_path) as f:
            sections = _parse_memory_md(f.read())
        counts["memory_entries"] = len(sections)
        if not dry_run:
            for s in sections:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO memory_entries (section, body, author) VALUES (?,?,?)",
                        (s["section"], s["body"], s["author"]),
                    )
                except Exception as e:
                    print(f"  ⚠ memory.md section skipped: {e}")

    roadmap_path = os.path.join(docs_dir, "roadmap.md")
    if os.path.exists(roadmap_path):
        with open(roadmap_path) as f:
            arcs, phases = _parse_roadmap_md(f.read())
        counts["roadmap_arcs"] = len(arcs)
        counts["roadmap_phases"] = len(phases)
        if not dry_run:
            for a in arcs:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO roadmap_arcs (version, title, status) VALUES (?,?,?)",
                        (a["version"], a["title"], a["status"]),
                    )
                except Exception as e:
                    print(f"  ⚠ roadmap arc skipped: {e}")
            for p in phases:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO roadmap_phases "
                        "(arc_version, phase_title, status, priority) VALUES (?,?,?,?)",
                        (p["arc_version"], p["phase_title"], p["status"], p["priority"]),
                    )
                except Exception as e:
                    print(f"  ⚠ roadmap phase skipped: {e}")

    costs_path = os.path.join(docs_dir, "costs.md")
    if os.path.exists(costs_path):
        with open(costs_path) as f:
            rows = _parse_costs_md(f.read())
        counts["cost_entries"] = len(rows)
        if not dry_run:
            for r in rows:
                try:
                    conn.execute(
                        """INSERT INTO cost_entries
                           (session_date, agent, model, input_tokens, output_tokens,
                            cache_read_tokens, total_cost_usd, notes)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            r["session_date"],
                            r["agent"],
                            r["model"],
                            r["input_tokens"],
                            r["output_tokens"],
                            r["cache_read_tokens"],
                            r["total_cost_usd"],
                            r["notes"],
                        ),
                    )
                except Exception as e:
                    print(f"  ⚠ cost row skipped: {e}")

    devlogs_dir = os.path.join(docs_dir, "devlogs")
    devlog_count = 0
    if os.path.isdir(devlogs_dir):
        for fname in sorted(os.listdir(devlogs_dir)):
            if not fname.endswith(".md") or fname == "README.md":
                continue
            author = fname[:-3]
            with open(os.path.join(devlogs_dir, fname)) as f:
                entries = _parse_devlog_file(f.read(), author)
            devlog_count += len(entries)
            if not dry_run:
                for e in entries:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO devlog_entries "
                            "(author, entry_date, session_title, body) VALUES (?,?,?,?)",
                            (e["author"], e["entry_date"], e["session_title"], e["body"]),
                        )
                    except Exception as ex:
                        print(f"  ⚠ devlog entry skipped ({fname}): {ex}")
    counts["devlog_entries"] = devlog_count

    todo_path = os.path.join(docs_dir, "todo.md")
    todo_sync_count = 0
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            meta_rows = _parse_todo_metadata(f.read())
        todo_sync_count = len(meta_rows)
        if not dry_run:
            for m in meta_rows:
                try:
                    if m["gh_issue"]:
                        conn.execute(
                            "UPDATE stories SET gh_issue=? WHERE story_id=?",
                            (m["gh_issue"], m["story_id"]),
                        )
                except Exception:
                    pass
    counts["todo_metadata"] = todo_sync_count

    conn.commit()
    conn.close()

    prefix = "Would import" if dry_run else "Imported"
    if "memory_entries" in counts:
        print(f"  {prefix}: memory.md     → {counts['memory_entries']} sections → memory_entries")
    if "roadmap_arcs" in counts:
        print(
            f"  {prefix}: roadmap.md    → {counts['roadmap_arcs']} arcs, "
            f"{counts['roadmap_phases']} phases → roadmap_arcs + roadmap_phases"
        )
    if "cost_entries" in counts:
        print(f"  {prefix}: costs.md      → {counts['cost_entries']} rows → cost_entries")
    if "devlog_entries" in counts:
        print(f"  {prefix}: devlogs/      → {counts['devlog_entries']} entries → devlog_entries")
    if counts.get("todo_metadata", 0):
        print(f"  {prefix}: todo.md       → {counts['todo_metadata']} stories with metadata synced")
    if dry_run:
        print("\n  No files moved. No git changes.")


def _migrate_dr_mirror(backup_dir: str) -> None:
    """Mirror backup_dir -> dr_sync_path/project-docs/ if configured."""
    import shutil as _shutil

    try:
        cfg_path = os.path.join(".synlynk", "config.json")
        if not os.path.exists(cfg_path):
            return
        with open(cfg_path) as f:
            cfg = json.load(f)
        dr_path = cfg.get("dr_sync_path")
        if not dr_path:
            return
        dr_path = os.path.expanduser(str(dr_path))
        if not os.path.isdir(dr_path):
            return
        dst = os.path.join(dr_path, "project-docs")
        if os.path.exists(dst):
            _shutil.rmtree(dst)
        _shutil.copytree(backup_dir, dst)
        print(f"  ✓ DR mirror written to {dst}")
    except Exception as e:
        print(f"  ⚠ DR mirror failed (continuing): {e}")


def cmd_migrate(dry_run: bool = False, recover: bool = False, setup_dr: bool = False) -> None:
    """Migrate project-docs/ -> .synlynk/project-docs/ and state.db."""
    import shutil as _shutil

    if setup_dr:
        path = input(
            "DR sync folder path "
            "(e.g. ~/Library/Mobile Documents/com~apple~CloudDocs/synlynk): "
        ).strip()
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            print(f"  ✗ Path not found: {path}")
            return
        cfg_path = os.path.join(".synlynk", "config.json")
        cfg = {}
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = json.load(f)
        cfg["dr_sync_path"] = path
        with open(cfg_path, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"  ✓ DR sync path set: {path}")
        return

    sentinel = os.path.join(".synlynk", ".synlynk_migrated")

    if recover:
        backup_dir = _synlynk_project_docs_dir()
        if not os.path.isdir(backup_dir):
            print("  ✗ No backup at .synlynk/project-docs/ — cannot recover")
            return
        print("  ▶ Re-importing from .synlynk/project-docs/ ...")
        _migrate_import(backup_dir)
        print("  ✓ Recovery complete")
        return

    if os.path.exists(sentinel):
        print("  Already migrated. Use --recover to re-import from backup.")
        return

    docs_dir = _docs_dir()
    if not os.path.isdir(docs_dir):
        print(f"  ✗ {docs_dir}/ not found — nothing to migrate")
        return

    if dry_run:
        print("  DRY RUN — no files written, no git changes\n")
        _migrate_import(docs_dir, dry_run=True)
        return

    print("  ▶ Importing flat files → state.db ...")
    _migrate_import(docs_dir)

    backup_dir = _synlynk_project_docs_dir()
    print(f"  ▶ Copying {docs_dir}/ → {backup_dir}/ ...")
    if os.path.exists(backup_dir):
        _shutil.rmtree(backup_dir)
    _shutil.copytree(docs_dir, backup_dir)

    _migrate_dr_mirror(backup_dir)

    try:
        subprocess.run(
            ["git", "rm", "--cached", "-r", "--quiet", docs_dir],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        print(f"  ✓ git rm --cached {docs_dir}/")
    except subprocess.CalledProcessError:
        print("  ⚠ git rm --cached failed (may not be tracked) — continuing")

    gitignore = ".gitignore"
    entry = f"{docs_dir}/\n"
    already = False
    if os.path.exists(gitignore):
        with open(gitignore) as f:
            already = any(docs_dir in line for line in f)
    if not already:
        with open(gitignore, "a") as f:
            f.write(entry)
        print(f"  ✓ Added {docs_dir}/ to .gitignore")

    with open(sentinel, "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print("  ✓ Sentinel written")

    try:
        subprocess.run(["git", "add", ".gitignore", sentinel], check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "chore: synlynk migrate — project-docs moved to .synlynk, "
                "state.db is now source of truth",
            ],
            check=True,
        )
        print("  ✓ Committed")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Git commit failed (continuing): {e}")


def _seed_verb_map(db_conn):
    db_conn.executemany("""
        INSERT OR IGNORE INTO harness_verb_map
            (synlynk_verb, verb_category, agent_name, agent_command, supported, partial_notes)
        VALUES (?,?,?,?,?,?)
    """, _VERB_MAP_SEED)
    db_conn.commit()


def _check_verb_support(verb: str, agent_name: str, db_conn) -> dict:
    row = db_conn.execute(
        "SELECT supported, partial_notes, agent_command FROM harness_verb_map WHERE synlynk_verb=? AND agent_name=?",
        (verb, agent_name)
    ).fetchone()
    if not row:
        return {"supported": "unknown", "block": False, "warn": False, "notes": None, "command": None}
    supported, notes, cmd = row
    return {
        "supported": supported,
        "block": supported == "none",
        "warn": supported == "partial",
        "notes": notes,
        "command": cmd,
    }



def cmd_story_create(title: str, engg_domain: str = "unknown",
                     org_domain: str = "unknown", phase: str = "build",
                     org_domain_tags: list = None,
                     estimated_tokens: int = None) -> str:
    """Creates a story record in state.db. Returns the generated story_id."""
    import hashlib as _hashlib
    import json as _json
    story_id = "story-" + _hashlib.md5(
        f"{title}{time.time()}".encode()
    ).hexdigest()[:8]
    config = load_config()
    industry = config.get("industry", "unknown")
    tags_json = _json.dumps(org_domain_tags or [])
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, "
        "org_domain_tags, industry, phase, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, title, engg_domain, org_domain, tags_json, industry, phase, estimated_tokens)
    )
    conn.commit()
    conn.close()
    _generate_todo_md()
    print(f"  {_GREEN}✓{_RESET} Story created: {story_id}  [{engg_domain} · {org_domain} · {industry}]")
    return story_id

def cmd_story_list() -> None:
    """Prints all stories in state.db."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, title, engg_domain, org_domain, industry, phase, "
        "estimated_tokens, actual_tokens, created_at "
        "FROM stories ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("  No stories yet. Use: synlynk story create --title '...'")
        return
    print(f"\n  {'ID':<14} {'Title':<28} {'Engg':<12} {'EST TOK':>9} {'ACTUAL':>9}")
    print("  " + "-" * 80)
    for r in rows:
        est = f"{r[6]:,}" if r[6] is not None else "—"
        actual = f"{r[7]:,}" if r[7] is not None else "—"
        print(f"  {r[0]:<14} {(r[1] or '')[:27]:<28} {r[2]:<12} {est:>9} {actual:>9}")


def _load_agent_config(name: str) -> dict:
    """Load .agents/<name>.json. Raises FileNotFoundError with clear message."""
    import json as _json
    candidates = [os.path.join(".agents", f"{name}.json"), os.path.join("agents", f"{name}.json")]
    path = next((candidate for candidate in candidates if os.path.exists(candidate)), candidates[0])
    if not os.path.exists(path):
        raise FileNotFoundError(f"No agent config found at {path}")
    with open(path) as f:
        return _json.load(f)


def _load_agent_profile(agent_name: str, agents_dir: str = ".agents") -> dict:
    """Load an agent profile and normalize harness/model defaults."""
    import json as _json

    candidates = [
        os.path.join(agents_dir, f"{agent_name}.json"),
        os.path.join(".agents", f"{agent_name}.json"),
        os.path.join("agents", f"{agent_name}.json"),
    ]
    path = next((candidate for candidate in candidates if os.path.exists(candidate)), candidates[0])
    if not os.path.exists(path):
        return {"agent": agent_name, "harness": agent_name, "model": "unknown"}
    try:
        with open(path) as f:
            profile = _json.load(f)
    except (OSError, ValueError, TypeError):
        return {"agent": agent_name, "harness": agent_name, "model": "unknown"}
    profile.setdefault("harness", agent_name)
    profile.setdefault("model", "unknown")
    return profile


def _dispatch_flags_for_agent(agent: str) -> list:
    """Return the executable dispatch flags for an agent baseline.

    Supports both the legacy list form and the structured mapping form.
    """
    baselines = AGENT_CAPABILITY_BASELINES.get(agent, {})
    dispatch_flags = baselines.get("dispatch_flags", [])
    if isinstance(dispatch_flags, dict):
        ordered = []
        for flag in dispatch_flags.get("required_flags", []) or []:
            if flag not in ordered:
                ordered.append(flag)
        return ordered
    return list(dispatch_flags or [])


def _compute_capability_hash(headless_contract: dict, dispatch_flags) -> str:
    import hashlib as _hashlib
    import json as _json

    payload = _json.dumps({"contract": headless_contract, "flags": dispatch_flags}, sort_keys=True)
    return _hashlib.sha256(payload.encode()).hexdigest()[:16]


_re = re


def _scan_command_palette(agent_name: str, harness_name: str, cli_version: str, db_conn) -> list:
    """Parse --help output and populate harness_command_palette."""
    try:
        result = subprocess.run([agent_name, "--help"], capture_output=True, text=True, timeout=5)
        help_text = (result.stdout or "") + (result.stderr or "")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    found_commands = {}
    for line in help_text.splitlines():
        line = line.strip()
        if not line:
            continue

        flag_match = _re.match(r"^(--[\w-]+(?:=\S+)?)(?:\s+\S+)?\s{2,}(.*)", line)
        if flag_match:
            cmd = flag_match.group(1).split("=")[0]
            desc = flag_match.group(2).strip()
            found_commands[cmd] = {"type": "flag", "help": desc}
            continue

        sub_match = _re.match(r"^([\w][\w\s-]{1,30}?)\s{2,}(.*)", line)
        if sub_match:
            cmd = sub_match.group(1).strip()
            desc = sub_match.group(2).strip()
            if cmd and len(cmd.split()) <= 3 and not cmd.startswith("-"):
                found_commands[cmd] = {"type": "subcommand", "help": desc}

    prev_rows = db_conn.execute(
        "SELECT command, cli_version FROM harness_command_palette WHERE harness_name=? AND last_seen_version IS NULL",
        (harness_name,),
    ).fetchall()
    prev_commands = {row[0] for row in prev_rows}
    prev_versions = {row[0]: row[1] for row in prev_rows}
    removed = prev_commands - set(found_commands.keys())
    for cmd in removed:
        db_conn.execute(
            """
            UPDATE harness_command_palette
            SET last_seen_version=?
            WHERE harness_name=? AND command=? AND last_seen_version IS NULL
            """,
            (prev_versions.get(cmd, cli_version), harness_name, cmd),
        )

    for cmd, meta in found_commands.items():
        db_conn.execute(
            """
            INSERT OR IGNORE INTO harness_command_palette
                (harness_name, cli_version, command, command_type, help_text, first_seen_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (harness_name, cli_version, cmd, meta["type"], meta["help"], cli_version),
        )

    db_conn.commit()
    return list(found_commands.keys())

_FENCE_OPEN_PATTERN = _re.compile(
    r"<!-- synlynk:harness v\S+ verified:\S+ -->.*?<!-- /synlynk:harness -->",
    _re.DOTALL,
)

def _build_fence_content(harness_version: str, body: str) -> str:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"<!-- synlynk:harness v{harness_version} verified:{ts} -->\n"
        f"# Harness Instructions (synlynk-managed — do not edit)\n\n"
        f"{body}\n"
        f"<!-- /synlynk:harness -->"
    )

def _upsert_harness_fence(file_path: str, harness_version: str, body: str) -> None:
    if not os.path.exists(file_path):
        print(f"  warning: {file_path} not found — fence skipped. Run synlynk init to create it.", file=sys.stderr)
        return

    fence = _build_fence_content(harness_version, body)
    with open(file_path, "r", encoding="utf-8") as f:
        current = f.read()

    if _FENCE_OPEN_PATTERN.search(current):
        updated = _FENCE_OPEN_PATTERN.sub(fence, current, count=1)
    else:
        sep = "\n" if current.endswith("\n") else "\n\n"
        updated = current + sep + fence + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)


def _build_fence_body_from_record(agent_name: str, db_conn=None) -> str:
    import json as _j
    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    contract = baseline.get("headless_contract", {})
    flags_spec = baseline.get("dispatch_flags", {})
    net_deps = baseline.get("network_deps", {})

    if db_conn:
        row = db_conn.execute(
            "SELECT active_contract, active_flags FROM harness_records WHERE agent_name=?",
            (agent_name,)
        ).fetchone()
        if row:
            contract = _j.loads(row[0]) or contract
            flags_spec = _j.loads(row[1]) or flags_spec

    mode = "pty" if contract.get("requires_pty") else "pipe"
    flush = contract.get("stdout_flush_method", "native")
    ni_flag = contract.get("non_interactive_flag", "")
    env_vars = contract.get("env_vars_required", [])
    if isinstance(flags_spec, dict):
        valid = " ".join(flags_spec.get("valid_flags", []))
        invalid = " ".join(flags_spec.get("invalid_flags", []))
    else:
        valid = " ".join(flags_spec) if isinstance(flags_spec, list) else ""
        invalid = ""
    endpoints = "\n".join(f"- Required: {e}" for e in net_deps.get("required_endpoints", []))
    env_line = f"- Stdout flush: unbuffered (set {' '.join(env_vars)})" if env_vars else f"- Stdout flush: {flush}"

    return f"""## Headless Execution Contract
- Execution mode: {mode}
- Non-interactive flag: {ni_flag}
{env_line}

## Active Dispatch Flags
- Valid: {valid}
- Invalid (do not use): {invalid}

## Network Dependencies
{endpoints or '- None required'}"""


def _probe_agent(agent_name: str, db_conn, fast_path_ok: bool = True) -> dict:
    import json as _json
    import socket as _sock
    import time as _time

    harness_map = {"claude": "claude-cli", "agy": "agy", "grok": "grok", "codex": "codex"}
    harness_name = harness_map.get(agent_name, agent_name)
    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})

    try:
        result = subprocess.run([agent_name, "--version"], capture_output=True, text=True, timeout=5)
        installed_version = result.stdout.strip().split()[-1] if result.stdout.strip() else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        installed_version = "unavailable"

    contract = baseline.get("headless_contract", {})
    flags = baseline.get("dispatch_flags", {})
    new_hash = _compute_capability_hash(contract, flags)

    if fast_path_ok:
        row = db_conn.execute(
            "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
            (agent_name,),
        ).fetchone()
        if row and row[0] == installed_version and row[1] == new_hash:
            return {"skipped": True, "version": installed_version, "status": "ok"}

    network_ok = True
    for endpoint in baseline.get("network_deps", {}).get("required_endpoints", []):
        host, _, port_s = endpoint.rpartition(":")
        try:
            s = _sock.create_connection((host, int(port_s or 443)), timeout=2)
            s.close()
        except OSError:
            network_ok = False

    compliance = "ok" if network_ok else "degraded"

    prev_row = db_conn.execute(
        "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
        (agent_name,),
    ).fetchone()

    now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    event_type = None
    if prev_row:
        if prev_row[0] != installed_version:
            event_type = "version_change"
        elif prev_row[1] != new_hash:
            event_type = "drift_detected"

    db_conn.execute(
        """
        INSERT INTO harness_records
            (agent_name, harness_name, installed_version, compliance_status, active_contract, active_flags, capability_hash, last_probe_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_name) DO UPDATE SET
            harness_name=excluded.harness_name,
            installed_version=excluded.installed_version,
            compliance_status=excluded.compliance_status,
            active_contract=excluded.active_contract,
            active_flags=excluded.active_flags,
            capability_hash=excluded.capability_hash,
            last_probe_at=excluded.last_probe_at
        """,
        (
            agent_name,
            harness_name,
            installed_version,
            compliance,
            _json.dumps(contract),
            _json.dumps(flags),
            new_hash,
            now,
        ),
    )

    if event_type:
        db_conn.execute(
            """
            INSERT INTO harness_version_history (agent_name, cli_version, event_type, prev_hash, new_hash, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                agent_name,
                installed_version,
                event_type,
                prev_row[1] if prev_row else None,
                new_hash,
                now,
            ),
        )

    _INSTRUCTION_FILES = {
        "claude": "CLAUDE.md",
        "agy": "GEMINI.md",
        "grok": "GROK.md",
        "codex": "AGENTS.md",
    }
    instr_file = _INSTRUCTION_FILES.get(agent_name)
    if instr_file and os.path.exists(instr_file):
        body = _build_fence_body_from_record(agent_name, db_conn)
        _upsert_harness_fence(instr_file, installed_version, body)

    _scan_command_palette(agent_name, harness_name, installed_version, db_conn)

    db_conn.commit()
    return {"skipped": False, "version": installed_version, "status": compliance}


def _run_tc1(agent_name: str, timeout: int = 5) -> dict:
    """TC-1: Headless stdout contract."""
    import sys as _sys

    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    contract = baseline.get("headless_contract", {})
    if not contract:
        return {"requires_pty": False, "passed": True, "stdout_method": "not_applicable"}

    non_interactive_flag = contract.get("non_interactive_flag", "--version")
    env = os.environ.copy()
    for var in contract.get("env_vars_required", []):
        if "=" in var:
            key, value = var.split("=", 1)
            env[key] = value

    try:
        proc = subprocess.Popen(
            [agent_name, non_interactive_flag],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        proc.communicate(timeout=timeout)
        return {"requires_pty": False, "passed": True, "stdout_method": "pipe"}
    except subprocess.TimeoutExpired:
        proc.kill()
        if _sys.platform == "win32":
            return {"requires_pty": True, "passed": False, "stdout_method": "pty"}
        return {"requires_pty": True, "passed": False, "stdout_method": "unavailable"}
    except FileNotFoundError:
        return {"requires_pty": False, "passed": False, "stdout_method": "not_found"}


def _run_tc2(agent_name: str, flags_spec: dict) -> dict:
    """TC-2: Flag compliance."""
    if isinstance(flags_spec, dict):
        invalid_flags = list(flags_spec.get("invalid_flags", []))
        valid_flags = list(flags_spec.get("valid_flags", []))
    else:
        invalid_flags, valid_flags = [], []

    failed = list(invalid_flags)
    try:
        result = subprocess.run([agent_name, "--help"], capture_output=True, text=True, timeout=5)
        help_text = (result.stdout or "") + (result.stderr or "")
        for flag in valid_flags:
            flag_name = flag.lstrip("-")
            if flag_name and flag_name not in help_text and flag not in help_text:
                failed.append(flag)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"failed_flags": failed, "passed": len(failed) == 0}


def _run_tc3(endpoints: list) -> dict:
    """TC-3: Network reachability."""
    import socket as _sock

    reachable, unreachable = [], []
    for host, port in endpoints or []:
        try:
            conn = _sock.create_connection((host, port), timeout=2)
            conn.close()
            reachable.append((host, port))
        except OSError:
            unreachable.append((host, port))
    return {"reachable": reachable, "unreachable": unreachable, "passed": len(unreachable) == 0}


def _run_tc4(agent_name: str, db_conn) -> dict:
    """TC-4: Verb map validation."""
    failed = []
    rows = db_conn.execute(
        """
        SELECT synlynk_verb, agent_command, supported
        FROM harness_verb_map
        WHERE agent_name=?
        """,
        (agent_name,),
    ).fetchall()
    for verb, cmd_template, supported in rows:
        if supported == "none" or not cmd_template:
            continue
        cmd = cmd_template.split()[0]
        try:
            subprocess.run([cmd, "--help"], capture_output=True, timeout=3)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(verb)
    return {"failed_verbs": failed, "passed": len(failed) == 0}


def cmd_probe(agent: str = None) -> None:
    agents = [agent] if agent else list(AGENT_CAPABILITY_BASELINES.keys())
    db_conn = _get_db()
    try:
        for agent_name in agents:
            result = _probe_agent(agent_name, db_conn)
            status = "skipped (up to date)" if result["skipped"] else result["status"]
            print(f"  probe [{agent_name}] {result['version']} → {status}")
    finally:
        db_conn.close()


def _fence_exists(file_path: str) -> bool:
    """Returns True if file_path contains a synlynk harness fence."""
    try:
        with open(file_path) as f:
            return "<!-- synlynk:harness" in f.read()
    except IOError:
        return False


def cmd_roles(fix: bool = False) -> None:
    """Print current agent role table from config.

    With --fix, regenerate role fences.
    """
    _DIRECTIVE_MAP = {
        "claude": "CLAUDE.md",
        "agy": "GEMINI.md",
        "grok": "GROK.md",
        "codex": "AGENTS.md",
    }
    cfg = load_config()
    roles = cfg.get("roles", {})

    print(f"\n  {_BOLD}synlynk roles{_RESET}\n")
    print(f"  {'agent':<10}  {'roles':<40}  {'directive file':<12}  fence")
    print(f"  {'─' * 10}  {'─' * 40}  {'─' * 12}  {'─' * 10}")

    for agent, role_list in roles.items():
        fname = _DIRECTIVE_MAP.get(agent, f"{agent}.md")
        roles_str = ", ".join(role_list) if isinstance(role_list, list) else str(role_list)
        file_exists = os.path.exists(fname)
        fence_present = False
        if file_exists:
            try:
                with open(fname) as f:
                    fence_present = "<!-- synlynk:harness" in f.read()
            except IOError:
                pass
        file_status = fname if file_exists else f"{fname} (missing)"
        fence_status = f"{_GREEN}✓{_RESET}" if fence_present else f"{_YELLOW}missing{_RESET}"
        print(f"  {agent:<10}  {roles_str:<40}  {file_status:<12}  {fence_status}")

        if fix and file_exists and not fence_present:
            roles_line = ", ".join(role_list) if isinstance(role_list, list) else str(role_list)
            try:
                _upsert_harness_fence(
                    fname,
                    harness_version="roles",
                    body=f"## Your Role\n{roles_line}\n",
                )
                print(f"    {_GREEN}✓{_RESET} wrote role fence to {fname}")
            except Exception as exc:
                print(f"    {_YELLOW}⚠{_RESET} could not write {fname}: {exc}")

    print()
    if not fix:
        missing = [
            _DIRECTIVE_MAP.get(a, f"{a}.md")
            for a, _ in roles.items()
            if os.path.exists(_DIRECTIVE_MAP.get(a, f"{a}.md"))
            and not _fence_exists(_DIRECTIVE_MAP.get(a, f"{a}.md"))
        ]
        if missing:
            print(f"  {_DIM}Run `synlynk roles --fix` to write missing role fences{_RESET}\n")


def cmd_score_add(story_id: str, rating: float, note: str = None,
                  rework: bool = False) -> None:
    """Add a human quality rating for a story. Inserts a new 'human' row."""
    if not 0.0 <= rating <= 10.0:
        raise ValueError(f"Rating must be 0–10, got {rating}")
    conn = _get_db()
    story = conn.execute(
        "SELECT engg_domain, org_domain, industry, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found. Create it first with: synlynk story create")
        return
    engg, org, industry, phase = story
    prev = conn.execute(
        "SELECT agent, model_version FROM capability_ratings "
        "WHERE story_id=? ORDER BY ts DESC LIMIT 1", (story_id,)
    ).fetchone()
    agent = prev[0] if prev else "unknown"
    model_version = prev[1] if prev else "unknown"
    dispatch_rework = 1 if rework else 0
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, dispatch_rework, note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (story_id, agent, model_version, engg, org, industry, phase,
         "human", rating, dispatch_rework, note)
    )
    conn.commit()
    conn.close()
    flag = " [rework]" if rework else ""
    print(f"  {_GREEN}✓{_RESET} Score recorded: {rating}/10{flag} for {story_id}")
    if note:
        print(f"    Note: {note}")


def cmd_score_list(engg: str = None, org: str = None, industry: str = None) -> None:
    """Display capability_scores for a domain coordinate."""
    conn = _get_db()
    where_parts, params = [], []
    if engg:
        where_parts.append("engg_domain=?"); params.append(engg)
    if org:
        where_parts.append("org_domain=?"); params.append(org)
    if industry:
        where_parts.append("industry=?"); params.append(industry)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = conn.execute(
        f"SELECT agent, model_version, engg_domain, org_domain, industry, phase, "
        f"weighted_score, sample_count FROM capability_scores {where} "
        f"ORDER BY weighted_score DESC",
        params
    ).fetchall()
    conn.close()
    if not rows:
        print("  No capability data yet for this coordinate.")
        return
    print(f"\n  {'Agent':<10} {'Model':<22} {'Engg':<12} {'Org':<14} "
          f"{'Industry':<12} {'Phase':<10} {'Score':>6} {'N':>4}")
    print("  " + "-" * 96)
    for r in rows:
        score_str = f"{r[6]:.2f}" if r[6] is not None else "  n/a"
        print(f"  {r[0]:<10} {r[1]:<22} {r[2]:<12} {r[3]:<14} "
              f"{r[4]:<12} {r[5]:<10} {score_str:>6} {r[7]:>4}")


def cmd_pr_check() -> None:
    """Hard-blocks merge if any capability_ratings row has model_version='unknown'.

    Exit code 1 if blocked. Exit code 0 if clean.
    """
    conn = _get_db()
    rows = conn.execute(
        "SELECT DISTINCT story_id, agent FROM capability_ratings WHERE model_version='unknown'"
    ).fetchall()
    conn.close()
    if rows:
        print("\n  🚫 [PR CHECK BLOCKED] Unattested model versions found:")
        for story_id, agent in rows:
            print(f"    story: {story_id}  agent: {agent}")
        print("\n  Fix with: synlynk score attest <story-id> --model <version>")
        raise SystemExit(1)
    print(f"  {_GREEN}✓{_RESET} PR check passed — all model versions attested.")


def cmd_scan(deep: bool = False, status: bool = False,
             refresh: bool = False, add_path: str = None,
             remove_path: str = None, dry_run: bool = False,
             workspace_name: str = None) -> None:
    """synlynk scan — workspace environment scan + context generation.

    No flags: first-time workspace scan (discover topology, harnesses,
              agents, skills; write workspace config + context.md).
    --refresh: re-run scan on existing workspace.
    --add <path>: add a repo to the current workspace config.
    --remove <path>: remove a repo from the current workspace config.
    --dry-run: print what would change; write nothing.
    --deep: (original) full source-tree walk → state.db + source-map.md.
    --status: (original) show skeleton cache status.
    """
    import json as _json

    # ── Preserved: --status ───────────────────────────────────────────────
    if status:
        meta = _load_scan_meta()
        if not meta:
            print("Source scan status: not scanned yet — run `synlynk scan` to populate")
            return
        sha_short = meta.get("head_sha", "unknown")[:7]
        file_count = meta.get("file_count", 0)
        scanned_at = meta.get("scanned_at", "unknown")
        print("Source scan status:")
        print(f"  Skeleton:    {file_count} files · cached · HEAD {sha_short} · {scanned_at}")
        deep_meta = meta.get("deep")
        if deep_meta:
            tf = deep_meta.get("total_files", "?")
            ts = deep_meta.get("total_symbols", "?")
            da = deep_meta.get("scanned_at", "unknown")
            print(f"  source-map:  {tf} files · {ts} symbols · {da}")
        else:
            print("  source-map:  not generated — run `synlynk scan --deep`")
        return

    # ── Preserved: --deep ─────────────────────────────────────────────────
    if deep:
        print(f"  {_GREEN}▶{_RESET} Deep scanning source tree...")
        skeleton, total_files, total_syms = _scan_full_repo()
        sha_short = (_git_head_sha() or "unknown")[:7]
        print(f"  {_GREEN}✓{_RESET} Scanned {total_files} files · {total_syms} symbols · HEAD {sha_short}")
        print(f"  {_CYAN}→{_RESET} project-docs/source-map.md updated")
        return

    # ── --remove ──────────────────────────────────────────────────────────
    if remove_path:
        abs_remove = os.path.abspath(remove_path)
        ws_dir = _workspace_config_dir(workspace_name or "default")
        cfg_path = os.path.join(ws_dir, "config.json")
        if not os.path.exists(cfg_path):
            print(f"  ⚠ No workspace config found at {cfg_path}")
            return
        cfg = _json.loads(open(cfg_path).read())
        before = len(cfg.get("repos", []))
        cfg["repos"] = [r for r in cfg.get("repos", [])
                        if os.path.abspath(r["path"]) != abs_remove]
        after = len(cfg["repos"])
        if dry_run:
            print(f"  [dry-run] would remove {os.path.basename(abs_remove)} from workspace")
            return
        open(cfg_path, "w").write(_json.dumps(cfg, indent=2))
        print(f"  {_GREEN}✓{_RESET} Removed {before - after} repo(s) from workspace")
        return

    # ── --add ─────────────────────────────────────────────────────────────
    if add_path:
        abs_add = os.path.abspath(add_path)
        if not os.path.isdir(os.path.join(abs_add, ".git")):
            print(f"  ⚠ {abs_add} is not a git repository")
            return
        ws_dir = _workspace_config_dir(workspace_name or "default")
        cfg_path = os.path.join(ws_dir, "config.json")
        if not os.path.exists(cfg_path):
            print(f"  ⚠ No workspace config at {cfg_path} — run `synlynk scan` first")
            return
        cfg = _json.loads(open(cfg_path).read())
        existing_paths = {os.path.abspath(r["path"]) for r in cfg.get("repos", [])}
        if abs_add in existing_paths:
            print(f"  {_YELLOW}⚠{_RESET} {os.path.basename(abs_add)} already in workspace")
            return
        new_entry = {
            "path": abs_add,
            "name": os.path.basename(abs_add),
            "stack_labels": fingerprint_stack(abs_add),
        }
        if dry_run:
            print(f"  [dry-run] would add {new_entry['name']} "
                  f"({', '.join(new_entry['stack_labels'])}) to workspace")
            return
        cfg["repos"].append(new_entry)
        open(cfg_path, "w").write(_json.dumps(cfg, indent=2))
        print(f"  {_GREEN}✓{_RESET} Added {new_entry['name']} to workspace")
        return

    # ── Compatibility: non-git working tree keeps legacy source scan ─────
    in_git_repo = os.path.isdir(os.path.join(os.getcwd(), ".git"))
    if not in_git_repo and not refresh:
        head_sha = _git_head_sha()
        if head_sha is None:
            print("  ⚠ Not in a git repository — scan requires git")
            return
        skeleton = _scan_source_skeleton()
        _save_scan_meta(head_sha, skeleton)
        sha_short = head_sha[:7]
        print(f"  {_GREEN}✓{_RESET} Skeleton refreshed · {len(skeleton)} files · HEAD {sha_short}")
        return

    # ── Default / --refresh: full workspace scan ──────────────────────────
    print(f"  {_CYAN}›{_RESET} scanning your environment...")
    scan = run_workspace_scan(workspace_name=workspace_name, dry_run=dry_run)

    # Print scan summary
    repo_names = ", ".join(r["name"] for r in scan["repos"])
    harness_names = ", ".join(h["name"] for h in scan["harnesses"]) or "none"
    stacks = sorted({lbl for r in scan["repos"] for lbl in r["stack_labels"]})
    print(f"  repos found: {len(scan['repos'])}  ·  "
          f"harnesses: {harness_names}  ·  "
          f"stacks: {', '.join(stacks) or 'unknown'}")

    if not dry_run:
        config_path = write_workspace_config(scan, scan["workspace_name"])
        generate_structured_context(scan)
        print(f"  {_GREEN}✓{_RESET} workspace: {scan['workspace_name']}")
        print(f"  {_GREEN}✓{_RESET} repos: {repo_names}")
        if scan["skills"]:
            skill_names = ", ".join(s["name"] for s in scan["skills"])
            print(f"  {_GREEN}✓{_RESET} skills: {skill_names}")
        print(f"\n  next: synlynk dispatch {scan['home_harness'] or 'claude'} "
              f'"what\'s the current task?"')
    else:
        print("  [dry-run] no files written")


def cmd_score_attest(story_id: str, model_version: str) -> None:
    """Retroactively sets model_version on all 'unknown' rows for a story.

    Also recalculates split_model — if model_at_dispatch differs from the attested
    completion model, the row is a split-model run and must be excluded from scoring.
    """
    conn = _get_db()
    updated = conn.execute(
        """UPDATE capability_ratings
           SET model_version = ?,
               model_at_completion = ?,
               split_model = CASE
                   WHEN model_at_dispatch != ? AND model_at_dispatch != 'unknown' THEN 1
                   ELSE 0
               END
           WHERE story_id = ? AND model_version = 'unknown'""",
        (model_version, model_version, model_version, story_id)
    ).rowcount
    conn.commit()
    conn.close()
    if updated:
        print(f"  {_GREEN}✓{_RESET} Attested {updated} row(s) for {story_id} → {model_version}")
    else:
        print(f"  No 'unknown' rows found for {story_id}")


_ENGG_DOMAIN_PATTERNS = [
    ("data",         [r"etl", r"pipeline/", r"schema\.sql", r"migrations/", r"dbt/"]),
    ("ml",           [r"ml/", r"models/", r"train\.", r"inference/", r"embeddings/"]),
    ("security",     [r"auth/", r"oauth", r"jwt", r"crypto", r"certs/"]),
    ("devops",       [r"\.github/", r"dockerfile", r"terraform", r"pulumi", r"k8s/", r"helm/"]),
    ("frontend",     [r"components/", r"pages/", r"\.tsx?", r"\.vue", r"\.svelte", r"styles/"]),
    ("backend",      [r"api/", r"routes/", r"handlers/", r"controllers/", r"services/"]),
    ("testing",      [r"tests/", r"test_", r"spec/", r"\.spec\.", r"fixtures/"]),
    ("docs",         [r"docs/", r"readme", r"\.md$", r"changelogs?"]),
    ("architecture", [r"design/", r"specs/", r"adr/", r"diagrams/"]),
]

def _infer_engg_domain(log_text: str) -> str:
    """Infers engineering domain from file path patterns in job log output."""
    lower = log_text.lower()
    for domain, patterns in _ENGG_DOMAIN_PATTERNS:
        if any(re.search(p, lower) for p in patterns):
            return domain
    return "unknown"


JOBS_FILE = ".synlynk/jobs.json"
LOGS_DIR = ".synlynk/logs"
PROMPTS_DIR = ".synlynk/prompts"

# Known baseline capabilities per agent CLI.
# Roles: "architect" (design/docs), "builder" (implement), "verifier" (test/review)
AGENT_CAPABILITY_BASELINES = {
    "claude": {
        "cli": "claude",
        "non_interactive_flags": ["--print"],
        "dispatch_flags": ["--dangerously-skip-permissions"],
        "roles": ["architect", "builder"],
        "strengths": ["long context", "reasoning", "code review", "planning"],
    },
    "codex": {
        "cli": "codex",
        # 'exec' subcommand + '-' reads prompt from stdin without requiring a TTY.
        # 'codex exec' sets approval:never by default — no bypass flag needed.
        # '-s workspace-write' confines writes to workdir + /tmp while allowing
        # model-generated file edits. Do NOT add --dangerously-bypass-approvals-and-sandbox:
        # it silently overrides -s and runs at danger-full-access (full host access).
        "non_interactive_flags": [
            "exec", "-",
            "-s", "workspace-write",
        ],
        "roles": ["builder"],
        "strengths": ["code completion", "inline edits", "fast iteration"],
    },
    "agy": {
        "cli": "agy",
        "non_interactive_flags": [],
        "prompt_flag": "-p",     # placed last: agy -p "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--print", "--model", "--output-format", "--add-dir"],
            "invalid_flags": ["--always-approve", "--dangerously-skip-permissions", "--non-interactive"],
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "unbuffered",
            "env_vars_required": ["PYTHONUNBUFFERED=1"],
            "non_interactive_flag": "-p",
        },
        "network_deps": {
            "required_endpoints": ["generativelanguage.googleapis.com:443", "oauth2.googleapis.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
    "grok": {
        "cli": "grok",
        "non_interactive_flags": [],
        "prompt_flag": "--single",  # placed last: grok --always-approve --single "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--always-approve", "--output-format", "--model", "--single"],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            "required_flags": ["--always-approve"],
        },
        "network_deps": {
            "required_endpoints": ["cli-chat-proxy.grok.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "architect"],
        "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
    },
}

_VERB_MAP_SEED = [
    # (synlynk_verb, category, agent, agent_command, supported, partial_notes)
    ("dispatch.task",     "dispatch",      "claude", "claude --print {task} --dangerously-skip-permissions", "full", None),
    ("dispatch.task",     "dispatch",      "agy",    "agy -p {task}", "full", None),
    ("dispatch.task",     "dispatch",      "grok",   "grok --always-approve --single {task}", "full", None),
    ("dispatch.task",     "dispatch",      "codex",  "codex exec - -s workspace-write", "full", None),
    ("dispatch.headless", "dispatch",      "claude", "claude --print {task}", "full", None),
    ("dispatch.headless", "dispatch",      "agy",    "agy -p {task}", "partial", "May hang without PTY on some agy versions"),
    ("dispatch.headless", "dispatch",      "grok",   "grok --always-approve --single {task}", "partial", "Network dep required"),
    ("dispatch.headless", "dispatch",      "codex",  "codex exec - -s workspace-write", "full", None),
    ("dispatch.resume",   "dispatch",      "claude", "claude --resume {session_id}", "full", None),
    ("dispatch.resume",   "dispatch",      "agy",    None, "none", None),
    ("dispatch.resume",   "dispatch",      "grok",   None, "none", None),
    ("dispatch.resume",   "dispatch",      "codex",  None, "none", None),
    ("dispatch.approve",  "dispatch",      "claude", "claude --allowedTools {tools}", "full", None),
    ("dispatch.approve",  "dispatch",      "agy",    None, "none", None),
    ("dispatch.approve",  "dispatch",      "grok",   None, "none", None),
    ("dispatch.approve",  "dispatch",      "codex",  None, "partial", "approval-policy=none only"),
    ("dispatch.model",    "dispatch",      "claude", "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "agy",    "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "grok",   "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "codex",  "--model {model}", "full", None),
    ("dispatch.tools",    "dispatch",      "claude", "--allowedTools {tools}", "full", None),
    ("dispatch.tools",    "dispatch",      "agy",    None, "partial", "No tool_list flag"),
    ("dispatch.tools",    "dispatch",      "grok",   None, "none", None),
    ("dispatch.tools",    "dispatch",      "codex",  None, "partial", "approval-policy only"),
    ("dispatch.context",  "dispatch",      "claude", "claude --print {task}", "full", None),
    ("dispatch.context",  "dispatch",      "agy",    "agy -p {task}", "full", None),
    ("dispatch.context",  "dispatch",      "grok",   "grok --prompt {task}", "partial", "No explicit context file flag"),
    ("dispatch.context",  "dispatch",      "codex",  "codex exec - -s workspace-write", "full", None),
    ("jobs",              "observability", "claude", None, "partial", "No native jobs subcommand"),
    ("jobs",              "observability", "agy",    None, "none", None),
    ("jobs",              "observability", "grok",   None, "none", None),
    ("jobs",              "observability", "codex",  None, "none", None),
    ("status",            "observability", "claude", None, "partial", None),
    ("status",            "observability", "agy",    None, "none", None),
    ("status",            "observability", "grok",   None, "none", None),
    ("status",            "observability", "codex",  None, "none", None),
    ("telemetry",         "observability", "claude", None, "none", None),
    ("telemetry",         "observability", "agy",    None, "none", None),
    ("telemetry",         "observability", "grok",   None, "none", None),
    ("telemetry",         "observability", "codex",  None, "none", None),
    ("costs",             "observability", "claude", None, "partial", "Token count via /cost"),
    ("costs",             "observability", "agy",    None, "none", None),
    ("costs",             "observability", "grok",   None, "none", None),
    ("costs",             "observability", "codex",  None, "none", None),
    ("probe",             "harness",       "claude", "claude --version", "full", None),
    ("probe",             "harness",       "agy",    "agy --version", "full", None),
    ("probe",             "harness",       "grok",   "grok --version", "full", None),
    ("probe",             "harness",       "codex",  "codex --version", "full", None),
    ("doctor",            "harness",       "claude", None, "full", None),
    ("doctor",            "harness",       "agy",    None, "full", None),
    ("doctor",            "harness",       "grok",   None, "full", None),
    ("doctor",            "harness",       "codex",  None, "full", None),
    ("story",             "pm",            "claude", None, "none", None),
    ("story",             "pm",            "agy",    None, "none", None),
    ("story",             "pm",            "grok",   None, "none", None),
    ("story",             "pm",            "codex",  None, "none", None),
    ("epic",              "pm",            "claude", None, "none", None),
    ("epic",              "pm",            "agy",    None, "none", None),
    ("epic",              "pm",            "grok",   None, "none", None),
    ("epic",              "pm",            "codex",  None, "none", None),
    ("decide",            "pm",            "claude", None, "none", None),
    ("decide",            "pm",            "agy",    None, "none", None),
    ("decide",            "pm",            "grok",   None, "none", None),
    ("decide",            "pm",            "codex",  None, "none", None),
    ("workspace",         "workspace",     "claude", None, "none", None),
    ("workspace",         "workspace",     "agy",    None, "none", None),
    ("workspace",         "workspace",     "grok",   None, "none", None),
    ("workspace",         "workspace",     "codex",  None, "none", None),
    ("upgrade",           "workspace",     "claude", None, "partial", "Via /upgrade slash command"),
    ("upgrade",           "workspace",     "agy",    None, "partial", "Via agy update"),
    ("upgrade",           "workspace",     "grok",   None, "partial", None),
    ("upgrade",           "workspace",     "codex",  None, "partial", None),
]

RELAY_EVENT_TYPES = frozenset({
    "story_updated",
    "job_dispatched",
    "job_completed",
    "alert_raised",
    "context_checkpoint",
    "table_changed",
    "broadcast",
})


def _build_relay_event(event_type: str, payload: dict) -> dict:
    """Constructs a relay event dict with required base fields."""
    if event_type not in RELAY_EVENT_TYPES:
        raise ValueError(
            f"unknown event type '{event_type}'. Valid: {sorted(RELAY_EVENT_TYPES)}"
        )
    import socket as _socket

    event = {
        "type": event_type,
        "ts": int(time.time()),
        "origin_node": _socket.gethostname(),
    }
    event.update(payload)
    return event

# Default paths scanned for agent CLI config directories.
# Overridable in .synlynk/config.json under "agent_discovery_paths".
AGENT_DISCOVERY_DEFAULTS = {
    "claude": os.path.expanduser("~/.claude"),
    "codex": os.path.expanduser("~/.codex"),
    "agy": os.path.expanduser("~/.agy"),
    "grok": os.path.expanduser("~/.grok"),
}

# ANSI helpers used by the wizard.
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def get_username() -> str:
    """Resolves current user's GitHub login via gh CLI, falling back to git config."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True
        )
        login = result.stdout.strip()
        if login and result.returncode == 0:
            return login
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True
        )
        name = result.stdout.strip()
        return name.lower().replace(" ", "") if name else "unknown"
    except Exception:
        return "unknown"


def get_mode() -> str:
    """Returns 'single' or 'team' from <docs_dir>/.synlynk_config.json."""
    config_path = os.path.join(_docs_dir(), ".synlynk_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f).get("mode", "single")
        except (json.JSONDecodeError, IOError):
            pass
    return "single"


def _docs_dir() -> str:
    """Returns the configured project docs directory (defaults to 'project-docs').

    Reads project_docs_dir from .synlynk/config.json. Pass --docs-dir to
    synlynk init to set a custom location (e.g. '.' for repos that keep docs
    at the root).
    """
    config_file = ".synlynk/config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                return json.load(f).get("project_docs_dir", "project-docs")
        except (json.JSONDecodeError, IOError):
            pass
    return "project-docs"


def load_config() -> dict:
    """Loads .synlynk/config.json with schema-v1 defaults."""
    defaults = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "watch_interval_seconds": 30,
        "auto_launch_after_wizard": True,
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "project_docs_dir": "project-docs",
        "agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex"},  # AGY CLI binary is named 'agy' — update when binary is renamed
        "team": None,
        "sync_endpoint": None,
        "exec_timeout_minutes": 30,
        "stall_timeout_minutes": 30,
        "agents": {},
        "roles": {
            "claude": ["pm", "review", "deploy"],
            "agy": ["implement", "test", "css", "templates", "content"],
            "grok": ["implement", "test", "canvas", "js", "infra"],
            "codex": ["implement", "test", "refactor"],
        },
    }
    config_file = ".synlynk/config.json"
    if not os.path.exists(config_file):
        return defaults
    try:
        with open(config_file) as f:
            config = json.load(f)
        for key, val in defaults.items():
            if key not in config:
                config[key] = val
        for key, val in defaults["budget"].items():
            if key not in config.get("budget", {}):
                config.setdefault("budget", {})[key] = val
        return config
    except (json.JSONDecodeError, IOError):
        return defaults


def _load_jobs() -> list:
    """Reads .synlynk/jobs.json; returns [] if missing or corrupt."""
    if not os.path.exists(JOBS_FILE):
        return []
    try:
        with open(JOBS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_jobs(jobs: list) -> None:
    """Writes jobs list to .synlynk/jobs.json."""
    os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


def _spawn_with_pty_fallback(cmd, env, cwd):
    """Try pipe mode first; fall back to PTY if stdout hangs (POSIX only)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, cwd=cwd)
    try:
        out, _ = proc.communicate(timeout=5)
        if out:
            return proc, out
    except subprocess.TimeoutExpired:
        proc.kill()
    # PTY fallback (POSIX only)
    if sys.platform != "win32":
        import pty
        import select
        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                cwd=cwd,
                close_fds=True
            )
            os.close(slave_fd)
            out_chunks = []
            while True:
                r, _, _ = select.select([master_fd], [], [], 5)
                if not r:
                    proc.kill()
                    break
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    out_chunks.append(data)
                except OSError:
                    break
            proc.wait(timeout=5)
            return proc, b"".join(out_chunks)
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
    return None, b""


def _probe_model_version(agent_name: str, cli: str) -> str:
    """Tier 2: probe the agent's active model from its statusline before dispatch.

    Times out after 3s to avoid blocking dispatch.
    """
    probe_cmds = {
        "claude": [cli, "/status"],
        "agy":    [cli, "--version"],
        "codex":  [cli, "--version"],
        "grok":   [cli, "-v"],
    }
    cmd = probe_cmds.get(agent_name, [cli, "--version"])
    patterns = [
        r"(claude-[\d.a-z-]*(?:opus|sonnet|haiku)[\w.-]*)",
        r"(agy-[\w.-]+)",
        r"(gemini-[\w.-]+)",
        r"(gpt-[\d.]+-[\w.-]+)",
        r"(codex-[\w-]+)",
        r"(grok-[\w.-]+)",
    ]

    def _extract_version(text: str) -> str:
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).lower()
        return "unknown"

    try:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
        contract = baseline.get("headless_contract", {})
        env = os.environ.copy()
        for var in contract.get("env_vars_required", []):
            if "=" in var:
                k, v = var.split("=", 1)
                env[k] = v

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
            cwd=os.getcwd(),
        )
        text = "\n".join(
            part for part in (getattr(result, "stdout", ""), getattr(result, "stderr", ""))
            if part
        )
        version = _extract_version(text)
        if version != "unknown":
            return version
    except Exception:
        pass

    try:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
        contract = baseline.get("headless_contract", {})
        env = os.environ.copy()
        for var in contract.get("env_vars_required", []):
            if "=" in var:
                k, v = var.split("=", 1)
                env[k] = v
        _proc, out = _spawn_with_pty_fallback(cmd, env, os.getcwd())
        text = out.decode("utf-8", errors="ignore") if out else ""
        version = _extract_version(text)
        if version != "unknown":
            return version
    except Exception:
        pass
    return "unknown"


def _count_dispatch_rework(story_id: str) -> int:
    """Counts completed jobs for this story_id — each represents one dispatch cycle."""
    if not story_id:
        return 0
    jobs = _load_jobs()
    return sum(1 for j in jobs
               if j.get("story_id") == story_id and j.get("status") == "completed")


def _extract_micro_rework(log_text: str) -> int:
    """Counts sub-task retry signals in agent log output."""
    patterns = [r"retrying step", r"retry attempt", r"re-trying", r"attempt \d+"]
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, log_text, re.IGNORECASE))
    return count


def _write_capability_rating(job: dict, log_text: str) -> None:
    """Writes a capability_ratings row for a completed job."""
    story_id = job.get("story_id", "")
    if not story_id:
        return

    conn = _get_db()
    exists = conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone()
    if not exists:
        conn.close()
        return

    agent = job.get("agent", "unknown")
    # Tier 1 only — synlynk-meta header, no config fallback (agent=None prevents Tier 3 contamination)
    tier1_completion = extract_model_version(log_text, agent=None)
    model_at_dispatch = job.get("model_at_dispatch", "unknown")
    # Tier 3: config default — used only as last resort label, never for split_model detection
    tier3_config = extract_model_version("", agent=agent)

    # Resolve hierarchy: Tier 1 > Tier 2 (live dispatch probe) > Tier 3 (config default)
    if tier1_completion != "unknown":
        model_at_completion = tier1_completion
        model_version = tier1_completion
    elif model_at_dispatch != "unknown":
        model_at_completion = model_at_dispatch
        model_version = model_at_dispatch
    else:
        model_at_completion = tier3_config
        model_version = tier3_config

    # Only flag split_model when BOTH Tier 1 and Tier 2 are concretely known and differ
    split_model = 1 if (
        tier1_completion != "unknown"
        and model_at_dispatch != "unknown"
        and tier1_completion != model_at_dispatch
    ) else 0

    signals = _extract_auto_signals(
        log_text,
        started_at=job.get("started_at"),
        ended_at=job.get("ended_at"),
        exit_code=job.get("exit_code"),
    )
    engg_domain = _infer_engg_domain(log_text)
    dispatch_rework = job.get("dispatch_rework", 0)
    micro_rework = job.get("micro_rework", 0)

    story_row = conn.execute(
        "SELECT org_domain, industry, phase FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    org_domain = story_row[0] if story_row else "unknown"
    industry = story_row[1] if story_row else load_config().get("industry", "unknown")
    phase = story_row[2] if story_row else "build"

    weighted_sum, total_weight = 0.0, 0.0
    if signals["test_pass_rate"] is not None:
        weighted_sum += signals["test_pass_rate"] * 10 * 0.35
        total_weight += 0.35
    if signals["build_success"] is not None:
        weighted_sum += (10.0 if signals["build_success"] else 0.0) * 0.30
        total_weight += 0.30
    rework_penalty = min(dispatch_rework * 2.0, 10.0)
    weighted_sum += max(0.0, 10.0 - rework_penalty) * 0.35
    total_weight += 0.35
    quality_auto = (weighted_sum / total_weight) if total_weight else 5.0

    # Anti-gaming: cap quality_auto at 5.0 when < 3 tests ran with perfect pass rate.
    test_count = signals.get("test_count")
    if (signals["test_pass_rate"] == 1.0
            and test_count is not None
            and test_count < 3):
        quality_auto = min(quality_auto, 5.0)

    # Check for verifier meta block — upgrades signal_source from 'auto' to 'verifier'
    verifier_meta = extract_verifier_meta(log_text)
    if verifier_meta:
        signal_source = "verifier"
        quality = verifier_meta["quality"]
        verifier_model = verifier_meta.get("verifier_model")
        verifier_agent_val = agent
        correct = 0 if verifier_meta.get("correct") is False else 1
    else:
        signal_source = "auto"
        quality = quality_auto
        verifier_model = None
        verifier_agent_val = None
        # Auto: infer correctness from build success (default 1 if unknown)
        correct = 1 if signals.get("build_success") is not False else 0

    sig_payload = {
        "story_id": story_id, "agent": agent, "model_version": model_version,
        "quality": quality, "quality_auto": quality_auto,
        "signal_source": signal_source, "engg_domain": engg_domain,
    }
    ed25519_sig = _sign_capability_rating(sig_payload)

    conn.execute(
        """INSERT INTO capability_ratings
           (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
            engg_domain, org_domain, industry, phase,
            signal_source, quality, quality_auto,
            verifier_agent, verifier_model,
            test_pass_rate, build_success,
            dispatch_rework, micro_rework,
            duration_vs_estimate, verified_by_ci, correct, ed25519_sig)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
         engg_domain, org_domain, industry, phase,
         signal_source, quality, quality_auto,
         verifier_agent_val, verifier_model,
         signals["test_pass_rate"], 1 if signals["build_success"] else 0,
         dispatch_rework, micro_rework,
         None, None, correct, ed25519_sig)
    )
    conn.commit()
    conn.close()

def _ensure_identity_key() -> str:
    key_dir = os.path.expanduser("~/.synlynk")
    key_path = os.path.join(key_dir, "identity.key")
    if not os.path.exists(key_path):
        os.makedirs(key_dir, exist_ok=True)
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", key_path, "-C", "synlynk-identity"],
                capture_output=True
            )
        except (FileNotFoundError, OSError):
            pass
    return key_path


def _sign_capability_rating(data: dict) -> str:
    import json as _json, tempfile as _tmp
    key_path = _ensure_identity_key()
    if not os.path.exists(key_path):
        return ""
    canonical = _json.dumps(data, sort_keys=True).encode()
    msg_file = None
    sig_file = None
    try:
        with _tmp.NamedTemporaryFile(mode="wb", suffix=".rating", delete=False) as f:
            f.write(canonical)
            msg_file = f.name
        sig_file = msg_file + ".sig"
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", key_path, "-n", "synlynk-rating", msg_file],
            capture_output=True
        )
        if os.path.exists(sig_file):
            with open(sig_file) as fh:
                return fh.read().strip()
    except Exception:
        pass
    finally:
        if msg_file:
            try:
                os.unlink(msg_file)
            except Exception:
                pass
        if sig_file and os.path.exists(sig_file):
            try:
                os.unlink(sig_file)
            except Exception:
                pass
    return ""


def _run_agent_sync(agent: str, prompt: str, timeout: int = 120) -> str:
    """Run an agent synchronously and return its stdout. Returns '' on any failure."""
    import tempfile as _tmp

    if agent not in AGENT_CAPABILITY_BASELINES:
        print(f"  ⚠ Unknown agent '{agent}' — skipping")
        return ""

    baselines = AGENT_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")

    prompt_file = None
    try:
        with _tmp.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as pf:
            pf.write(prompt)
            prompt_file = pf.name

        if prompt_via_arg:
            if prompt_flag:
                cmd = [cli] + flags + [prompt_flag, prompt]
            else:
                cmd = [cli] + flags + [prompt]
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout
            )
        else:
            with open(prompt_file) as stdin_file:
                result = subprocess.run(
                    [cli] + flags,
                    stdin=stdin_file, capture_output=True,
                    text=True, timeout=timeout
                )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"  ⚠ Agent '{agent}' failed: {e}")
        return ""
    finally:
        if prompt_file:
            try:
                os.unlink(prompt_file)
            except Exception:
                pass


def _write_decision_record(
    decision_id: str, topic: str, date: str, panel: list,
    inputs: dict, synthesis: str, decision_text: str,
    decisions_dir: str, slug: str
) -> None:
    """Write MD + JSON sidecar for a Decision record. Signs JSON with local identity key."""
    base = os.path.join(decisions_dir, f"{date}-{slug}")

    record = {
        "decision_id": decision_id,
        "topic": topic,
        "date": date,
        "panel": panel,
        "status": "approved",
        "inputs": inputs,
        "synthesis": synthesis,
        "decision": decision_text,
    }

    sig = _sign_capability_rating(record)
    if sig:
        record["signature"] = sig
    else:
        print("  ⚠ No identity key — decision written unsigned. "
              "Run `synlynk identity init` first.")

    with open(f"{base}.json", "w") as f:
        json.dump(record, f, indent=2)

    panel_inputs_md = ""
    for member, text in inputs.items():
        panel_inputs_md += f"\n### {member}\n{text}\n"

    md_content = (
        f"---\n"
        f"decision_id: {decision_id}\n"
        f"topic: \"{topic}\"\n"
        f"date: {date}\n"
        f"panel: [{', '.join(panel)}]\n"
        f"status: approved\n"
        f"---\n\n"
        f"## Topic\n{topic}\n\n"
        f"## Panel Inputs\n{panel_inputs_md}\n"
        f"## Synthesis\n{synthesis}\n\n"
        f"## Decision\n{decision_text}\n\n"
        f"> Signatures: see {date}-{slug}.json\n"
    )
    with open(f"{base}.md", "w") as f:
        f.write(md_content)


def cmd_decide(topic: str, panel: list, record: bool = False) -> None:
    """Convene a multi-agent panel on topic and optionally record the Decision."""
    import hashlib as _hashlib

    print(f"\n  {_CYAN}▶{_RESET} Convening panel on: {topic}")
    print(f"  Panel: {', '.join(panel)}\n")

    panel_prompt = (
        f"You are part of a decision panel. Topic: \"{topic}\"\n\n"
        f"Provide your analysis and recommendation in 200-400 words. "
        f"State your position clearly in the final paragraph."
    )

    inputs = {}
    for member in panel:
        print(f"  {_CYAN}▶{_RESET} Querying {member}...")
        output = _run_agent_sync(member, panel_prompt)
        if output:
            inputs[member] = output
            print(f"  {_GREEN}✓{_RESET} {member} responded ({len(output.split())} words)")
        else:
            print(f"  ⚠ {member} returned no output — skipping")

    if not inputs:
        print("Error: all panel members failed — cannot produce a decision")
        sys.exit(1)

    synthesis_parts = [
        f"The following are inputs from a decision panel on: \"{topic}\"\n"
    ]
    for member, text in inputs.items():
        synthesis_parts.append(f"### {member}\n{text}\n")
    synthesis_parts.append(
        "Synthesize these into a single decision. In the final paragraph, "
        "state the decision clearly starting with \"Decision:\"."
    )
    synthesis_prompt = "\n".join(synthesis_parts)

    print(f"\n  {_CYAN}▶{_RESET} Synthesizing...")
    synthesis = _run_agent_sync(panel[0], synthesis_prompt)
    if not synthesis:
        synthesis = "Synthesis unavailable — see individual panel inputs above."

    decision_text = ""
    for line in synthesis.split("\n"):
        if line.strip().lower().startswith("decision:"):
            decision_text = line.strip()
            break
    if not decision_text:
        lines = [l.strip() for l in synthesis.split("\n") if l.strip()]
        decision_text = lines[-1] if lines else synthesis

    sep = "─" * 50
    print(f"\n{sep}\nSYNTHESIS\n\n{synthesis}\n{sep}\n")

    if not record:
        print("  (Use --record to save this as a Decision record)")
        return

    _check_upstream_divergence()

    decision_id = "dec-" + _hashlib.md5(
        f"{topic}{time.time()}".encode()
    ).hexdigest()[:8]

    today = time.strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40].strip('-')

    decisions_dir = os.path.join(_docs_dir(), "decisions")
    os.makedirs(decisions_dir, exist_ok=True)

    _write_decision_record(
        decision_id, topic, today, panel,
        inputs, synthesis, decision_text, decisions_dir, slug
    )

    print(f"  {_GREEN}✓{_RESET} Decision recorded: {decisions_dir}/{today}-{slug}.md")


def _check_upstream_divergence() -> None:
    """Warn if remote has commits the local branch hasn't pulled. Silent no-op otherwise."""
    try:
        local = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        upstream = subprocess.check_output(
            ["git", "rev-parse", "@{u}"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, AttributeError):
        return  # no upstream configured, detached HEAD, or not in git repo
    if local != upstream:
        try:
            behind = subprocess.check_output(
                ["git", "rev-list", "--count", "HEAD..@{u}"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, AttributeError):
            behind = "?"
        print(f"⚠  Remote has {behind} commit(s) you haven't pulled. "
              f"Consider `git pull` before writing.\n   Continuing anyway...")


def _seed_devlog(username: str) -> None:
    """Creates project-docs/devlogs/<username>.md if absent. Idempotent."""
    devlog_dir = os.path.join(_docs_dir(), "devlogs")
    os.makedirs(devlog_dir, exist_ok=True)
    devlog_path = os.path.join(devlog_dir, f"{username}.md")
    if os.path.exists(devlog_path):
        return
    today = time.strftime("%Y-%m-%d")
    with open(devlog_path, "w") as f:
        f.write(f"# Devlog — @{username}\n\n")
        f.write(f"## {today} — Joined project\n")
        f.write("Joined via `synlynk join`.\n")


def _generate_ai_context_files(arch_context: str, git_summary: str) -> None:
    """Appends a context snapshot section to CLAUDE.md, GEMINI.md, AGENTS.md.
    Creates files if absent. Never overwrites existing content."""
    today = time.strftime("%Y-%m-%d")
    snapshot = (
        f"\n## Context Snapshot (joined {today})\n\n"
        f"### Recent Git Activity\n```\n{git_summary}\n```\n\n"
        f"### Source Architecture\n{arch_context}\n"
    )
    for fname in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        if os.path.exists(fname):
            with open(fname, "a") as f:
                f.write(snapshot)
        else:
            with open(fname, "w") as f:
                f.write(f"# {fname.replace('.md', '')} — Project Context\n")
                f.write(snapshot)


def _build_team_digest() -> dict:
    """Reads devlogs + SQLite to build a team status digest.
    SQLite section silently skipped if state.db absent."""
    members = []
    devlogs_dir = os.path.join(_docs_dir(), "devlogs")
    if os.path.exists(devlogs_dir):
        for fname in sorted(os.listdir(devlogs_dir)):
            if fname.endswith(".md") and fname != "README.md":
                fpath = os.path.join(devlogs_dir, fname)
                user = fname[:-3]
                last_active = _get_last_devlog_date(fpath) or "unknown"
                shipped = 0
                try:
                    with open(fpath) as fh:
                        for line in fh:
                            if re.match(r'^## \d{4}-\d{2}-\d{2}', line):
                                shipped += 1
                except IOError:
                    pass
                members.append({
                    "user": user,
                    "last_active": last_active,
                    "stories_shipped": shipped,
                })

    in_progress = []
    recently_completed = []

    try:
        conn = _get_db()
        stories = conn.execute(
            "SELECT story_id, title, estimated_tokens FROM stories ORDER BY created_at DESC LIMIT 20"
        ).fetchall()

        telemetry = []
        tel_path = ".synlynk/telemetry.json"
        if os.path.exists(tel_path):
            try:
                with open(tel_path) as f:
                    telemetry = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        def _actual_tokens_for_story(sid):
            total = sum(
                e.get("in_tokens", 0) + e.get("out_tokens", 0)
                for e in telemetry
                if e.get("story_id") == sid
            )
            return total if total > 0 else None

        for story_id, title, est_tokens in stories:
            actual = _actual_tokens_for_story(story_id)
            has_rating = conn.execute(
                "SELECT id FROM capability_ratings WHERE story_id=? AND correct=1 LIMIT 1",
                (story_id,)
            ).fetchone()
            entry = {
                "story_id": story_id,
                "title": title,
                "estimated_tokens": est_tokens,
                "actual_tokens": actual,
            }
            if has_rating:
                recently_completed.append(entry)
            else:
                in_progress.append(entry)
        conn.close()
    except Exception:
        pass  # state.db absent or unreadable — skip SQLite section

    top_todo = None
    todo_path = os.path.join(_docs_dir(), "todo.md")
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[\s*\]', line):
                    top_todo = re.sub(r'\s*-\s*\[\s*\]\s*', '', line).strip()
                    top_todo = re.sub(r'<!--.*?-->', '', top_todo).strip()
                    break

    return {
        "members": members,
        "in_progress": in_progress[:5],
        "recently_completed": recently_completed[:3],
        "top_todo": top_todo,
    }


def cmd_join() -> None:
    """Onboards the current user to an existing synlynk project."""
    docs_dir = _docs_dir()
    if not os.path.exists(docs_dir):
        print("Error: project not initialized — run 'synlynk init' first")
        sys.exit(1)

    username = get_username()
    if not username:
        print("Error: git config user.name not set — run: git config user.name 'Your Name'")
        sys.exit(1)

    print(f"  {_GREEN}▶{_RESET} Joining project as @{username}...")

    arch_context = ""
    try:
        cmd_scan()
        ctx_path = ".synlynk/context.md"
        if os.path.exists(ctx_path):
            arch_context = open(ctx_path).read()[:2000]
    except Exception:
        pass

    git_summary = ""
    try:
        git_summary = subprocess.check_output(
            ["git", "log", "--oneline", "-20"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except subprocess.CalledProcessError:
        pass

    _generate_ai_context_files(arch_context, git_summary)
    print(f"  {_GREEN}✓{_RESET} Updated CLAUDE.md, GEMINI.md, AGENTS.md")

    _seed_devlog(username)
    print(f"  {_GREEN}✓{_RESET} Seeded devlog at {docs_dir}/devlogs/{username}.md")

    config_path = os.path.join(docs_dir, ".synlynk_config.json")
    try:
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
        cfg["mode"] = "team"
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

    print(f"  {_GREEN}✓{_RESET} Joined project as @{username}\n")

    digest = _build_team_digest()

    n = len(digest["members"])
    print(f"TEAM ({n} member{'s' if n != 1 else ''})")
    for m in digest["members"]:
        flag = ("· joined now"
                if m["user"] == username and m["stories_shipped"] <= 1
                else f"· {m['stories_shipped']} entries")
        print(f"  @{m['user']:<12} · last active {m['last_active']}  {flag}")

    if digest["in_progress"]:
        print("\nIN PROGRESS")
        for s in digest["in_progress"]:
            est = (f"~{s['estimated_tokens']:,} tokens est"
                   if s["estimated_tokens"] else "no budget set")
            print(f"  {s['story_id']}  {(s['title'] or '')[:40]}   {est}")

    if digest["top_todo"]:
        print(f"\nRECOMMENDED FIRST TASK\n  → {digest['top_todo']}")
    print()


def cmd_team_status() -> None:
    """Prints a full team digest: members, stories, budget, top todo."""
    project_name = os.path.basename(os.path.abspath("."))
    mode = get_mode()
    print(f"\nTEAM STATUS · {project_name} · {mode} mode\n")

    digest = _build_team_digest()

    print(f"MEMBERS ({len(digest['members'])})")
    for m in digest["members"]:
        last = m["last_active"]
        if last == time.strftime("%Y-%m-%d"):
            last = "today"
        print(f"  @{m['user']:<12} · last active {last:<14} · {m['stories_shipped']} entries")

    if digest["in_progress"]:
        print("\nIN-PROGRESS STORIES")
        for s in digest["in_progress"]:
            est = (f"~{s['estimated_tokens']:,} est"
                   if s["estimated_tokens"] else "no budget set")
            act = (f"· {s['actual_tokens']:,} actual so far"
                   if s["actual_tokens"] else "")
            print(f"  {s['story_id']:<14} {(s['title'] or '')[:38]:<40} {est} {act}")
    else:
        print("\nIN-PROGRESS STORIES\n  No in-progress stories")

    if digest["recently_completed"]:
        print("\nRECENTLY COMPLETED (last 7 days)")
        for s in digest["recently_completed"]:
            est = s["estimated_tokens"]
            act = s["actual_tokens"]
            if est and act:
                delta_pct = round((act - est) / est * 100)
                sign = "+" if delta_pct >= 0 else ""
                delta_str = f"{est:,} est · {act:,} actual ({sign}{delta_pct}%)"
            elif act:
                delta_str = f"{act:,} actual"
            else:
                delta_str = "no data"
            print(f"  {s['story_id']:<14} {(s['title'] or '')[:38]:<40} {delta_str}")

    if digest["top_todo"]:
        print(f"\nTOP TODO\n  → {digest['top_todo']}")
    print()


def cmd_identity_init() -> None:
    key_path = _ensure_identity_key()
    pub_path = key_path + ".pub"
    print(f"  identity key: {key_path}")
    if os.path.exists(pub_path):
        with open(pub_path) as fh:
            pub = fh.read().strip()
        print(f"  Public key: {pub}")
    else:
        print("  (public key file not found)")


# ---------------------------------------------------------------------------
# synlynk doctor — health checks
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _dataclass
from typing import List as _List

@_dataclass
class HealthCheck:
    name: str
    status: str        # "ok" | "warn" | "fail"
    message: str
    fix: str = ""      # suggested remediation


def _hc_python_version() -> HealthCheck:
    import sys
    vi = sys.version_info
    ver_str = f"Python {vi[0]}.{vi[1]}.{vi[2]}"
    if vi[:2] >= (3, 9):
        return HealthCheck("python_version", "ok", ver_str)
    return HealthCheck(
        "python_version", "fail",
        f"{ver_str} is below minimum (3.9)",
        fix="Upgrade to Python 3.9 or later",
    )


def _hc_project_init() -> HealthCheck:
    if os.path.exists(".synlynk/config.json"):
        return HealthCheck("project_init", "ok", ".synlynk/config.json present")
    return HealthCheck(
        "project_init", "fail",
        "Project not initialized — .synlynk/config.json missing",
        fix="Run: synlynk init",
    )


def _hc_docs_dir() -> HealthCheck:
    try:
        docs = _docs_dir()
    except Exception:
        return HealthCheck(
            "docs_dir", "warn",
            "Could not resolve docs directory (project may not be initialized)",
            fix="Run: synlynk init",
        )
    required = ["roadmap.md", "todo.md", "memory.md"]
    missing = [f for f in required if not os.path.exists(os.path.join(docs, f))]
    if not missing:
        return HealthCheck("docs_dir", "ok", f"project-docs complete ({docs})")
    return HealthCheck(
        "docs_dir", "warn",
        f"project-docs missing: {', '.join(missing)}",
        fix="Run: synlynk init",
    )


def _hc_identity_key() -> HealthCheck:
    key_path = os.path.join(os.path.expanduser("~/.synlynk"), "identity.key")
    if os.path.exists(key_path):
        pub_path = key_path + ".pub"
        if os.path.exists(pub_path):
            return HealthCheck("identity_key", "ok", f"Ed25519 identity key present")
        return HealthCheck(
            "identity_key", "warn",
            "identity.key exists but identity.key.pub is missing",
            fix="Run: synlynk identity init",
        )
    return HealthCheck(
        "identity_key", "warn",
        "No identity key — capability ratings will be unsigned",
        fix="Run: synlynk identity init",
    )


def _hc_agent_profiles() -> HealthCheck:
    """Checks that each agent in config's agent_slots has a .agents/<name>.json profile."""
    try:
        cfg = load_config()
    except Exception:
        return HealthCheck(
            "agent_profiles", "warn",
            "Could not load config — skipping agent profile check",
            fix="Run: synlynk init",
        )
    slots = cfg.get("agent_slots", {})
    if not slots:
        return HealthCheck("agent_profiles", "warn", "No agent slots configured", fix="Run: synlynk init")
    missing = [name for name in slots if not os.path.exists(os.path.join(".agents", f"{name}.json"))]
    if not missing:
        return HealthCheck("agent_profiles", "ok", f"Agent profiles present: {', '.join(sorted(slots))}")
    return HealthCheck(
        "agent_profiles", "warn",
        f"Missing .agents/ profiles: {', '.join(missing)}",
        fix=f"Run: synlynk agent configure <name> — for: {', '.join(missing)}",
    )


def _hc_instruction_files() -> HealthCheck:
    """Checks that per-agent instruction files exist at the repo root."""
    expected = {"claude": "CLAUDE.md", "agy": "GEMINI.md", "codex": "AGENTS.md", "grok": "GROK.md"}
    missing = [fname for fname in expected.values() if not os.path.exists(fname)]
    if not missing:
        return HealthCheck("instruction_files", "ok", "Agent instruction files present")
    return HealthCheck(
        "instruction_files", "warn",
        f"Missing instruction files: {', '.join(missing)}",
        fix="Run: synlynk init",
    )


def _hc_version_current() -> HealthCheck:
    """Compares installed VERSION against latest GitHub release tag (best-effort, timeout 5s)."""
    import urllib.request
    import urllib.error
    import json as _json
    url = "https://api.github.com/repos/nikhilsoman/synlynk/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"synlynk/{VERSION}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
        latest_tag = data.get("tag_name", "").lstrip("v")
        if not latest_tag:
            return HealthCheck("version_current", "warn", "Could not parse latest release tag")
        if latest_tag == VERSION:
            return HealthCheck("version_current", "ok", f"synlynk {VERSION} is up to date")
        # Simple semver comparison via tuple
        def _ver(s):
            try:
                return tuple(int(x) for x in s.split("."))
            except ValueError:
                return (0,)
        if _ver(latest_tag) > _ver(VERSION):
            return HealthCheck(
                "version_current", "warn",
                f"Update available: {VERSION} → {latest_tag}",
                fix="Run: synlynk upgrade",
            )
        return HealthCheck("version_current", "ok", f"synlynk {VERSION} (latest: {latest_tag})")
    except (urllib.error.URLError, OSError):
        return HealthCheck("version_current", "warn", f"Version check skipped (offline or timeout)")
    except Exception:
        return HealthCheck("version_current", "warn", "Version check failed (unexpected error)")


# Registry — ordered from most fundamental to least
HEALTH_CHECKS = [
    _hc_python_version,
    _hc_project_init,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_agent_profiles,
    _hc_instruction_files,
    _hc_version_current,
]


def cmd_doctor(args=None, checks: _List = None) -> int:
    """Runs all registered health checks and prints a formatted report.

    Returns exit code: 0 if all checks ok/warn, 1 if any check fails.
    """
    if checks is not None:
        _STATUS_ICON = {"ok": f"{_GREEN}✓{_RESET}", "warn": f"{_YELLOW}⚠{_RESET}", "fail": f"\033[31m✗{_RESET}"}

        results = [fn() for fn in checks]
        failed = [r for r in results if r.status == "fail"]
        warned = [r for r in results if r.status == "warn"]

        print(f"\n{_BOLD}synlynk doctor{_RESET}\n")
        for r in results:
            icon = _STATUS_ICON.get(r.status, "?")
            print(f"  {icon}  {r.name}: {r.message}")
            if r.fix and r.status != "ok":
                print(f"     {_DIM}→ {r.fix}{_RESET}")

        print()
        if failed:
            print(f"  {len(failed)} check(s) failed — fix these before running synlynk.")
        elif warned:
            print(f"  {len(warned)} advisory warning(s). Everything should still work.")
        else:
            print(f"  {_GREEN}All checks passed.{_RESET}")
        print()
        return 1 if failed else 0

    agent_filter = getattr(args, "agent", None) if args is not None else None
    db_conn = _get_db()
    agents = [agent_filter] if agent_filter else list(AGENT_CAPABILITY_BASELINES.keys())
    any_failed = False
    try:
        for agent in agents:
            print(f"\n  doctor [{agent}]")
            baseline = AGENT_CAPABILITY_BASELINES.get(agent, {})

            tc1 = _run_tc1(agent)
            tc2 = _run_tc2(agent, baseline.get("dispatch_flags", {}))
            endpoints = []
            for ep in baseline.get("network_deps", {}).get("required_endpoints", []):
                host, _, port_s = ep.rpartition(":")
                endpoints.append((host, int(port_s) if port_s.isdigit() else 443))
            tc3 = _run_tc3(endpoints)
            tc4 = _run_tc4(agent, db_conn)

            all_passed = tc1["passed"] and tc2["passed"] and tc3["passed"] and tc4["passed"]
            if not all_passed:
                any_failed = True
            status = "ok" if all_passed else "degraded"
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            capability_hash = _compute_capability_hash(baseline.get("headless_contract", {}), baseline.get("dispatch_flags", {}))

            db_conn.execute(
                """
                INSERT INTO harness_records
                    (agent_name, harness_name, installed_version, compliance_status,
                     active_contract, active_flags, last_probe_at, capability_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
                    harness_name=excluded.harness_name,
                    installed_version=excluded.installed_version,
                    compliance_status=excluded.compliance_status,
                    active_contract=excluded.active_contract,
                    active_flags=excluded.active_flags,
                    last_probe_at=excluded.last_probe_at,
                    capability_hash=excluded.capability_hash
                """,
                (
                    agent,
                    baseline.get("cli", agent),
                    "unknown",
                    status,
                    json.dumps(baseline.get("headless_contract", {})),
                    json.dumps(baseline.get("dispatch_flags", {})),
                    now,
                    capability_hash,
                ),
            )
            try:
                db_conn.execute(
                    """
                    INSERT INTO harness_version_history (agent_name, cli_version, event_type, recorded_at)
                    VALUES (?, ?, 'doctor_run', ?)
                    """,
                    (agent, "unknown", now),
                )
            except _sqlite3.IntegrityError:
                pass
            db_conn.commit()

            print(f"    TC-1 stdout:  {'✓' if tc1['passed'] else '✗ requires_pty=' + str(tc1.get('requires_pty'))}")
            print(f"    TC-2 flags:   {'✓' if tc2['passed'] else '✗ failed=' + str(tc2['failed_flags'])}")
            print(f"    TC-3 network: {'✓' if tc3['passed'] else '✗ unreachable=' + str(tc3['unreachable'])}")
            print(f"    TC-4 verbs:   {'✓' if tc4['passed'] else '✗ failed=' + str(tc4['failed_verbs'])}")

        # Roles fence check
        _DIRECTIVE_MAP = {
            "claude": "CLAUDE.md",
            "agy": "GEMINI.md",
            "grok": "GROK.md",
            "codex": "AGENTS.md",
        }
        cfg_roles = load_config().get("roles", {})
        roles_issues = []
        for agent_name in cfg_roles:
            fname = _DIRECTIVE_MAP.get(agent_name, f"{agent_name}.md")
            if os.path.exists(fname) and not _fence_exists(fname):
                roles_issues.append(fname)
        if roles_issues:
            for fname in roles_issues:
                print(f"  {_YELLOW}⚠{_RESET}  roles: {fname} is missing role fence "
                      f"{_DIM}— run `synlynk roles --fix` to regenerate{_RESET}")
    finally:
        db_conn.close()
    return 1 if any_failed else 0


def _strip_synlynk_section(path: str, marker_style: str) -> bool:
    """Remove the synlynk-managed block from a file, leaving surrounding content.

    Returns True if a section was found and removed, False otherwise.
    """
    if not os.path.exists(path):
        return False
    with open(path) as f:
        content = f.read()
    if marker_style == "none":
        os.remove(path)
        return True
    if marker_style == "html":
        pattern = r'\n?[ \t]*<!-- synlynk:start[^>]* -->[ \t]*\n.*?\n[ \t]*<!-- synlynk:end -->[ \t]*\n?'
    else:
        pattern = r'\n?[ \t]*# synlynk:start[^\n]*\n.*?\n[ \t]*# synlynk:end[ \t]*\n?'
    new_content, n = re.subn(pattern, "", content, flags=re.DOTALL)
    if n:
        with open(path, "w") as f:
            f.write(new_content.rstrip("\n") + "\n" if new_content.strip() else "")
    return bool(n)


def cmd_exit(dry_run: bool = True, remove_docs: bool = False) -> int:
    """Reverse synlynk onboarding: strip instruction sections, remove .synlynk/ and .agents/.

    Writes SYNLYNK_HANDOFF.md summarising what was configured before removal.
    Dry-run by default — pass --confirm to execute.
    """
    manifest_data = _load_instruction_manifest()
    docs = None
    try:
        docs = _docs_dir()
    except Exception:
        pass

    cfg = {}
    if os.path.exists(".synlynk/config.json"):
        try:
            cfg = json.load(open(".synlynk/config.json"))
        except Exception:
            pass

    # Build action list
    strip_targets = []
    for fpath, info in manifest_data.items():
        style = _MARKER_STYLE_FOR_TOOL.get(info.get("tool", ""), "html")
        strip_targets.append((fpath, style, info.get("tool", "?")))

    agent_profiles = []
    if os.path.isdir(".agents"):
        agent_profiles = [os.path.join(".agents", f) for f in os.listdir(".agents") if f.endswith(".json")]

    synlynk_dir = ".synlynk"
    docs_dir_path = docs if (remove_docs and docs and os.path.isdir(docs)) else None

    print(f"\n{_BOLD}synlynk exit{_RESET} {'(dry run — pass --confirm to execute)' if dry_run else '(executing)'}\n")

    # Instruction files
    print("  Instruction files:")
    if strip_targets:
        for fpath, style, tool in strip_targets:
            exists = os.path.exists(fpath)
            tag = "remove" if style == "none" else "strip synlynk section"
            label = f"{_DIM}(not found){_RESET}" if not exists else ""
            print(f"    {'→' if dry_run else '✓'} {fpath} [{tool}] — {tag} {label}")
            if not dry_run and exists:
                _strip_synlynk_section(fpath, style)
    else:
        print(f"    {_DIM}no tracked instruction files{_RESET}")

    # Agent profiles
    print("  Agent profiles:")
    if agent_profiles:
        for p in agent_profiles:
            print(f"    {'→' if dry_run else '✓'} remove {p}")
            if not dry_run:
                os.remove(p)
        if not dry_run and os.path.isdir(".agents"):
            try:
                os.rmdir(".agents")
            except OSError:
                pass
    else:
        print(f"    {_DIM}no .agents/ profiles found{_RESET}")

    # .synlynk/ directory
    print(f"  Config & state:")
    print(f"    {'→' if dry_run else '✓'} remove {synlynk_dir}/")
    if not dry_run and os.path.isdir(synlynk_dir):
        import shutil as _shutil
        _shutil.rmtree(synlynk_dir)

    # project-docs (optional)
    if docs_dir_path:
        print(f"  Project docs:")
        print(f"    {'→' if dry_run else '✓'} remove {docs_dir_path}/")
        if not dry_run:
            import shutil as _shutil
            _shutil.rmtree(docs_dir_path)
    elif remove_docs:
        print(f"  Project docs: {_DIM}not found or already absent{_RESET}")

    # Handoff doc
    handoff_path = "SYNLYNK_HANDOFF.md"
    handoff_lines = [
        f"# synlynk handoff — {time.strftime('%Y-%m-%d')}",
        "",
        "synlynk was removed from this repository. This file records what was configured.",
        "",
        "## Configuration",
        f"- Version: {cfg.get('synlynk_version', VERSION)}",
        f"- Mode: {cfg.get('mode', 'unknown')}",
        f"- Agents: {', '.join(cfg.get('agent_slots', {}).keys()) or 'unknown'}",
        f"- Org: {cfg.get('org', 'unknown')} / {cfg.get('repo', 'unknown')}",
        f"- Docs dir: {docs or 'unknown'}",
        "",
        "## Removed",
    ]
    for fpath, style, tool in strip_targets:
        handoff_lines.append(f"- `{fpath}` ({tool}) — synlynk section stripped")
    for p in agent_profiles:
        handoff_lines.append(f"- `{p}` — removed")
    handoff_lines += [
        f"- `.synlynk/` — removed",
        "",
        "## To re-initialize",
        "```",
        f"synlynk init --agents {','.join(cfg.get('agent_slots', {}).keys()) or 'claude,agy,codex,grok'}",
        "```",
        "",
    ]
    print(f"  Handoff doc:")
    print(f"    {'→' if dry_run else '✓'} write {handoff_path}")
    if not dry_run:
        with open(handoff_path, "w") as f:
            f.write("\n".join(handoff_lines))

    print()
    if dry_run:
        print(f"  Dry run complete. Run with {_CYAN}--confirm{_RESET} to apply changes.")
    else:
        print(f"  {_GREEN}synlynk removed.{_RESET} See {handoff_path} for re-init instructions.")
    print()
    return 0


def cmd_repair(dry_run: bool = True) -> int:
    """Exit synlynk and immediately re-initialize from the current configuration.

    Reads config before exit so re-init uses the same agents/mode/org/repo/docs-dir.
    Dry-run by default — pass --confirm to execute.
    """
    cfg = {}
    if os.path.exists(".synlynk/config.json"):
        try:
            cfg = json.load(open(".synlynk/config.json"))
        except Exception:
            pass

    agents_str = ",".join(cfg.get("agent_slots", {}).keys()) or "claude,agy,codex,grok"
    mode = cfg.get("mode", "solo")
    org = cfg.get("org") or None
    repo = cfg.get("repo") or None
    project_id = cfg.get("project_id") or None
    docs_dir_arg = cfg.get("docs_dir") or None

    print(f"\n{_BOLD}synlynk repair{_RESET} {'(dry run — pass --confirm to execute)' if dry_run else '(executing)'}\n")
    print(f"  Captured config: agents={agents_str}  mode={mode}  org={org or '—'}  docs-dir={docs_dir_arg or 'project-docs'}")
    print()

    print("  Step 1: exit")
    cmd_exit(dry_run=dry_run)

    print("  Step 2: re-init")
    if dry_run:
        print(f"    → synlynk init --agents {agents_str} --mode {mode}"
              + (f" --org {org}" if org else "")
              + (f" --repo {repo}" if repo else "")
              + (f" --project-id {project_id}" if project_id else "")
              + (f" --docs-dir {docs_dir_arg}" if docs_dir_arg else ""))
        print()
        print(f"  Dry run complete. Run with {_CYAN}--confirm{_RESET} to apply.")
    else:
        init(
            agents=[a.strip() for a in agents_str.split(",") if a.strip()],
            mode=mode,
            org=org,
            repo=repo,
            project_id=project_id,
            docs_dir=docs_dir_arg,
        )
        print(f"\n  {_GREEN}Repair complete.{_RESET}")
    print()
    return 0


def cmd_sync(dry_run: bool = True) -> int:
    """Propagate updated synlynk artifacts to an existing repo without full re-init.

    Updates: instruction file sections (CLAUDE.md, GEMINI.md, etc.), .agents/ profile
    defaults for any slots missing from .agents/. Does NOT touch project-docs/.
    Dry-run by default — pass --confirm to execute.
    """
    print(f"\n{_BOLD}synlynk sync{_RESET} {'(dry run — pass --confirm to execute)' if dry_run else '(executing)'}\n")

    # --- instruction files ---
    manifest_data = _load_instruction_manifest()
    print("  Instruction files:")
    if not manifest_data:
        print(f"    {_DIM}no tracked instruction files — run synlynk init first{_RESET}")
    else:
        _tool_content_builders = {
            "cursor":    (_build_cursor_mdc,            "none"),
            "copilot":   (_build_copilot_instructions,  "html"),
            "windsurf":  (_build_windsurf_rules,        "hash"),
            "universal": (lambda: _build_templates().get("AI_INSTRUCTIONS.md", ""), "html"),
        }
        updated_manifest = {}
        for fpath, info in manifest_data.items():
            tool = info.get("tool", "unknown")
            marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")
            if dry_run:
                print(f"    → {fpath} [{tool}]")
                continue
            if tool in _tool_content_builders:
                builder, _ = _tool_content_builders[tool]
                content = builder()
            else:
                templates = _build_templates()
                content = templates.get(os.path.basename(fpath), "")
            _write_instruction_file(fpath, tool, content, marker_style)
            if os.path.exists(fpath):
                section = _extract_synlynk_section(open(fpath).read(), marker_style)
                if section:
                    updated_manifest[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}
            print(f"    {_GREEN}✓{_RESET} {fpath} [{tool}]")
        if not dry_run and updated_manifest:
            _write_instruction_manifest(updated_manifest)

    # --- agent profiles ---
    print("  Agent profiles (.agents/):")
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    slots = cfg.get("agent_slots", {})
    if not slots:
        print(f"    {_DIM}no agent slots in config{_RESET}")
    else:
        os.makedirs(".agents", exist_ok=True) if not dry_run else None
        for name in slots:
            profile_path = os.path.join(".agents", f"{name}.json")
            if os.path.exists(profile_path):
                print(f"    {_DIM}· {profile_path} already present — skipped{_RESET}")
                continue
            print(f"    {'→' if dry_run else _GREEN + '✓' + _RESET} {profile_path} — create default profile")
            if not dry_run:
                _load_agent_config(name)  # writes default profile if absent

    print()
    if dry_run:
        print(f"  Dry run complete. Run with {_CYAN}--confirm{_RESET} to apply.")
    else:
        print(f"  {_GREEN}Sync complete.{_RESET}")
    print()
    return 0


def _best_agent_for_story(story_id: str) -> Optional[str]:
    """Returns the agent with the highest capability score for the story's coordinate.

    Falls back through progressively wider coordinates. Returns None on cold start.
    """
    if not story_id:
        return None
    conn = _get_db()
    story = conn.execute(
        "SELECT engg_domain, org_domain, industry, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        return None

    engg, org, industry, phase = story

    queries = [
        ("full",       "engg_domain=? AND org_domain=? AND industry=? AND phase=?",
                       (engg, org, industry, phase)),
        ("no-industry","engg_domain=? AND org_domain=? AND phase=?",
                       (engg, org, phase)),
        ("engg-only",  "engg_domain=? AND phase=?",
                       (engg, phase)),
    ]
    for _, where, params in queries:
        row = conn.execute(
            f"SELECT agent FROM capability_scores WHERE {where} "
            "ORDER BY weighted_score DESC LIMIT 1",
            params
        ).fetchone()
        if row:
            conn.close()
            return row[0]

    conn.close()
    return None


def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    import signal as _signal
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False
    if os.path.getsize(log_file) > 0:
        return False  # has output, not stalled

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)

    started_val = job.get("started_at")
    if isinstance(started_val, str):
        try:
            import datetime as _dt
            started_ts = _dt.datetime.strptime(started_val, "%Y-%m-%dT%H:%M:%S").timestamp()
        except Exception:
            started_ts = time.time()
    elif isinstance(started_val, (int, float)):
        started_ts = started_val
    else:
        started_ts = time.time()

    elapsed_minutes = (time.time() - started_ts) / 60

    if elapsed_minutes < timeout:
        return False

    pid = job.get("pid")
    if pid:
        try:
            os.kill(pid, _signal.SIGKILL)
        except ProcessLookupError:
            pass

    job["status"] = "failed"
    job["exit_code"] = -1
    job["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    _write_sentinel_alert(
        "CRITICAL", "STALL_NO_OUTPUT",
        f"Job {job.get('id')} on agent '{agent}' stalled with zero output after {timeout}min. Process killed.",
        sentinel_path,
    )
    return True


def _reconcile_jobs() -> None:
    """Probes PIDs of running jobs; marks unreachable ones as failed or completed.

    Called on every synlynk invocation before any command runs.
    Prevents stale jobs surviving reboots or external kills.
    """
    jobs = _load_jobs()
    changed = False
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    config = load_config()
    sentinel_path = ".synlynk/sentinel.md"
    for job in jobs:
        if job.get("status") not in ("running",):
            continue
        if _check_job_stall(job, config, sentinel_path):
            changed = True
            continue
        pid = job.get("pid")
        if pid is None:
            continue
        try:
            os.kill(pid, 0)  # signal 0: check existence only, no actual signal
        except ProcessLookupError:
            # PID is dead. Check if wrapper wrote an exit code.
            log_file = job.get("log_file")
            exit_code = None
            if log_file:
                exit_file = log_file + ".exit"
                if os.path.exists(exit_file):
                    try:
                        with open(exit_file) as f:
                            exit_code = int(f.read().strip())
                        os.remove(exit_file)
                    except Exception:
                        pass

            if exit_code == 0:
                job["status"] = "completed"
                job["exit_code"] = 0
            else:
                job["status"] = "failed"
                job["exit_code"] = exit_code if exit_code is not None else -1
            job["ended_at"] = now
            changed = True

            if log_file and os.path.exists(log_file):
                log_text = open(log_file).read()
                job["micro_rework"] = _extract_micro_rework(log_text)
                _write_capability_rating(job, log_text)

        except PermissionError:
            # Process exists but is owned by another user — keep status as running.
            pass
    if changed:
        _save_jobs(jobs)


def _reconcile_daemon_jobs() -> None:
    """Reaps finished daemon_jobs; updates status/exit_code/completed_at in state.db."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT job_id, pid, log_path FROM daemon_jobs WHERE status='running'"
    ).fetchall()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        for job_id, pid, log_path in rows:
            if pid is None:
                continue
            exited = False
            raw_exit_status = None
            try:
                wpid, wstatus = os.waitpid(pid, os.WNOHANG)
                if wpid != 0:
                    exited = True
                    raw_exit_status = wstatus
            except ChildProcessError:
                # Process was adopted by init (daemon restart) — fall back to kill(0)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    exited = True

            if exited:
                exit_code = -1
                if raw_exit_status is not None:
                    if os.WIFEXITED(raw_exit_status):
                        exit_code = os.WEXITSTATUS(raw_exit_status)
                    elif os.WIFSIGNALED(raw_exit_status):
                        exit_code = -os.WTERMSIG(raw_exit_status)
                elif log_path:
                    exit_file = log_path + ".exit"
                    if os.path.exists(exit_file):
                        try:
                            with open(exit_file) as f:
                                exit_code = int(f.read().strip())
                            os.remove(exit_file)
                        except Exception:
                            pass
                status = "done" if exit_code == 0 else "failed"
                conn.execute(
                    "UPDATE daemon_jobs SET status=?, exit_code=?, completed_at=? "
                    "WHERE job_id=?",
                    (status, exit_code, now, job_id)
                )
        conn.commit()
    finally:
        conn.close()


def _dispatch_ready_jobs(max_parallel: int = 4) -> int:
    """Launches queued daemon_jobs up to max_parallel concurrently. Returns count launched."""
    import json as _json
    import shlex as _shlex
    conn = _get_db()
    try:
        running_count = conn.execute(
            "SELECT COUNT(*) FROM daemon_jobs WHERE status='running'"
        ).fetchone()[0]
        if running_count >= max_parallel:
            return 0

        slots = max_parallel - running_count
        candidates = conn.execute(
            "SELECT job_id, agent, task, story_id, depends_on, log_path "
            "FROM daemon_jobs WHERE status='queued' "
            "ORDER BY priority ASC, enqueued_at ASC"
        ).fetchall()

        launched = 0
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for job_id, agent, task, story_id, depends_on_json, log_path in candidates:
            if launched >= slots:
                break
            deps = _json.loads(depends_on_json or "[]")
            if deps:
                placeholders = ",".join("?" * len(deps))
                dep_rows = conn.execute(
                    f"SELECT job_id, status FROM daemon_jobs WHERE job_id IN ({placeholders})",
                    deps
                ).fetchall()
                dep_statuses = {r[0]: r[1] for r in dep_rows}
                if any(dep_statuses.get(d) == "failed" for d in deps):
                    conn.execute(
                        "UPDATE daemon_jobs SET status='failed', completed_at=? WHERE job_id=?",
                        (now, job_id)
                    )
                    conn.commit()
                    continue
                done_ids = {jid for jid, st in dep_statuses.items() if st == "done"}
                if done_ids != set(deps):
                    continue

            if not log_path:
                os.makedirs(LOGS_DIR, exist_ok=True)
                log_path = os.path.join(LOGS_DIR, f"{job_id}.log")

            baselines = AGENT_CAPABILITY_BASELINES.get(agent, {})
            cli = baselines.get("cli", agent)
            flags = baselines.get("non_interactive_flags", [])
            prompt_via_arg = baselines.get("prompt_via_arg", False)
            prompt_flag = baselines.get("prompt_flag")
            prompt_file = os.path.join(PROMPTS_DIR, f"{job_id}.md")
            os.makedirs(PROMPTS_DIR, exist_ok=True)
            context_text = ""
            context_path = ".synlynk/context.md"
            if os.path.exists(context_path):
                with open(context_path) as f:
                    context_text = f.read()
            prompt = _format_prompt_for_agent(
                agent, context_text, story_id or "", task, "", ""
            )
            with open(prompt_file, "w") as pf:
                pf.write(prompt)

            if prompt_via_arg and prompt_flag:
                cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
            else:
                cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
            if prompt_via_arg:
                shell_cmd = (
                    f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
                    f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_path)} 2>&1; "
                    f"echo $? > {_shlex.quote(log_path)}.exit"
                )
            else:
                shell_cmd = (
                    f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_path)} 2>&1; "
                    f"echo $? > {_shlex.quote(log_path)}.exit"
                )

            proc = subprocess.Popen(
                ["sh", "-c", shell_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            conn.execute(
                "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, log_path=? "
                "WHERE job_id=?",
                (proc.pid, now, log_path, job_id)
            )
            conn.commit()
            launched += 1

        return launched
    finally:
        conn.close()


def _check_agent_functional(cli: str) -> Optional[str]:
    """Runs `<cli> --version` to confirm CLI is installed and executable.

    Returns version string (stdout stripped) on success, None otherwise.
    """
    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def discover_agents(config: dict = None) -> list:
    """Scans for installed agent CLIs and checks each is functional.

    Returns list of dicts: {name, cli, version, functional, capabilities,
    roles, discovery_path}.
    Agents not found on disk are omitted. Agents found but failing --version
    are included with functional=False.
    """
    if config is None:
        config = load_config()

    # Allow per-project overrides of discovery paths.
    discovery_paths = {**AGENT_DISCOVERY_DEFAULTS}
    discovery_paths.update(config.get("agent_discovery_paths", {}))

    found = []
    for name, defaults in AGENT_CAPABILITY_BASELINES.items():
        path = discovery_paths.get(name)
        if path and not os.path.exists(path):
            continue  # config dir not present — skip entirely
        cli = defaults["cli"]
        version = _check_agent_functional(cli)
        found.append({
            "name": name,
            "cli": cli,
            "version": version,
            "functional": version is not None,
            "roles": defaults["roles"],
            "capabilities": defaults["strengths"],
            "non_interactive_flags": defaults["non_interactive_flags"],
            "discovery_path": path or "",
        })
    return found


def _static_scan(root: str = ".") -> dict:
    """Scans repo for project context: git log, README, file tree.

    Best-effort: repos without structured commits produce a lower-quality result.
    Returns dict with keys: project_name, description, commit_count,
    has_structured_commits, recent_topics, top_dirs, languages, readme_summary.
    """
    result = {
        "project_name": os.path.basename(os.path.abspath(root)),
        "description": "",
        "commit_count": 0,
        "has_structured_commits": False,
        "recent_topics": [],
        "top_dirs": [],
        "languages": [],
        "readme_summary": "",
    }

    # README extraction — project name from H1, summary from first paragraph.
    for readme in ("README.md", "README.rst", "README.txt", "README"):
        readme_path = os.path.join(root, readme)
        if os.path.exists(readme_path):
            try:
                text = open(readme_path).read(2000)
                lines = text.splitlines()
                for line in lines:
                    if line.startswith("# "):
                        result["project_name"] = line[2:].strip()
                        break
                # First non-heading, non-empty paragraph as description.
                para_lines = []
                in_para = False
                for line in lines[1:]:
                    if line.startswith("#"):
                        if in_para:
                            break
                        continue
                    if line.strip():
                        para_lines.append(line.strip())
                        in_para = True
                    elif in_para:
                        break
                result["description"] = " ".join(para_lines)[:300]
                result["readme_summary"] = text[:500]
            except IOError:
                pass
            break

    # Git log — commit count, structured commit detection, recent topics.
    try:
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-50", "--no-merges"],
            capture_output=True, text=True, cwd=root
        )
        if log_result.returncode == 0:
            messages = [l.split(" ", 1)[1] for l in log_result.stdout.strip().splitlines()
                        if " " in l]
            result["commit_count"] = int(subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, cwd=root
            ).stdout.strip() or "0")
            cc_prefixes = ("feat:", "fix:", "chore:", "docs:", "test:", "refactor:", "perf:")
            structured = sum(1 for m in messages if any(m.startswith(p) for p in cc_prefixes))
            result["has_structured_commits"] = structured >= max(1, len(messages) // 2)
            result["recent_topics"] = messages[:10]
    except (FileNotFoundError, ValueError):
        pass

    # File tree — top-level directories and language hints.
    try:
        entries = os.listdir(root)
        result["top_dirs"] = sorted([
            e for e in entries
            if os.path.isdir(os.path.join(root, e))
            and not e.startswith(".") and e not in ("node_modules", "__pycache__", "venv")
        ])
        lang_map = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
                    ".js": "JavaScript", ".go": "Go", ".rs": "Rust", ".rb": "Ruby"}
        langs = set()
        for e in entries:
            ext = os.path.splitext(e)[1]
            if ext in lang_map:
                langs.add(lang_map[ext])
        result["languages"] = sorted(langs)
    except OSError:
        pass

    return result


_INDUSTRY_KEYWORDS = {
    "ott": ["ott", "over-the-top", "streaming service", "video platform"],
    "streaming": ["streaming", "live stream", "media delivery"],
    "fintech": ["fintech", "financial", "payment", "trading", "investment"],
    "banking": ["banking", "bank", "loan", "mortgage", "deposit"],
    "securities": ["securities", "stock", "equity", "portfolio", "brokerage"],
    "healthcare": ["healthcare", "medical", "patient", "clinical", "health"],
    "ecommerce": ["ecommerce", "e-commerce", "shop", "cart", "marketplace"],
    "edtech": ["edtech", "education", "learning", "course", "student"],
    "gaming": ["gaming", "game", "player", "leaderboard", "matchmaking"],
}

def _infer_industry(root: str = ".") -> str:
    """Infers industry vertical from README content. Returns 'unknown' if no match."""
    for fname in ("README.md", "README.rst", "README.txt"):
        path = os.path.join(root, fname)
        if os.path.exists(path):
            try:
                text = open(path).read().lower()
                for industry, keywords in _INDUSTRY_KEYWORDS.items():
                    if any(kw in text for kw in keywords):
                        return industry
            except Exception:
                pass
    return "unknown"


_STACK_FINGERPRINTS = [
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("next.config.js", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("Pulumi.yaml", "Pulumi"),
    ("Pulumi.yml", "Pulumi"),
    ("Dockerfile", "Docker"),
    ("docker-compose.yml", "Docker"),
    ("docker-compose.yaml", "Docker"),
]

_STACK_EXT_MAP = {
    ".go": "Go",
    ".rs": "Rust",
}


def find_git_roots(search_dirs: list, max_depth: int = 2, exclude_names: set = None) -> list:
    """Return absolute paths of directories containing a .git entry.

    Search is breadth-first from each search directory and stops at max_depth.
    """
    exclude_names = set(exclude_names or {"node_modules", "__pycache__", ".venv", "venv"})
    found = []
    seen = set()
    queue = []

    for base in search_dirs or []:
        if not base:
            continue
        abs_base = os.path.abspath(os.path.expanduser(base))
        if os.path.isdir(abs_base):
            queue.append((abs_base, 0))

    while queue:
        current, depth = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        name = os.path.basename(current)
        if depth > 0 and (name.startswith(".") or name in exclude_names):
            continue

        if os.path.isdir(os.path.join(current, ".git")):
            if current not in found:
                found.append(current)

        if depth >= max_depth:
            continue

        try:
            entries = sorted(os.listdir(current))
        except OSError:
            continue

        for entry in entries:
            if entry.startswith(".") or entry in exclude_names:
                continue
            child = os.path.join(current, entry)
            if os.path.isdir(child):
                queue.append((child, depth + 1))

    return found


def fingerprint_stack(repo_path: str) -> list:
    """Return a deduplicated list of stack labels for a repository path."""
    labels = []
    seen = set()

    def _add(label: str) -> None:
        if label not in seen:
            seen.add(label)
            labels.append(label)

    if not repo_path or not os.path.isdir(repo_path):
        return labels

    for filename, label in _STACK_FINGERPRINTS:
        if os.path.exists(os.path.join(repo_path, filename)):
            _add(label)

    has_pkg = os.path.exists(os.path.join(repo_path, "package.json"))
    has_ts = any(
        os.path.exists(os.path.join(repo_path, candidate))
        for candidate in ("tsconfig.json", "tsconfig.base.json", "tsconfig.app.json")
    )
    if has_pkg and has_ts:
        _add("TypeScript")
    elif has_pkg:
        _add("JavaScript")

    if os.path.isdir(os.path.join(repo_path, ".github", "workflows")):
        _add("CI/CD")

    if os.path.isdir(os.path.join(repo_path, "migrations")):
        _add("SQL")
    else:
        try:
            if any(fname.endswith(".sql") for fname in os.listdir(repo_path)):
                _add("SQL")
        except OSError:
            pass

    try:
        for entry in os.listdir(repo_path):
            ext = os.path.splitext(entry)[1]
            if ext in _STACK_EXT_MAP:
                _add(_STACK_EXT_MAP[ext])
    except OSError:
        pass

    return labels


_KNOWN_SKILL_PATTERNS = [
    "~/.claude/plugins/cache/superpowers-marketplace/superpowers/*/",
    "~/.config/gstack/plugins/*/",
]
_SKILL_MANIFEST_NAMES = ("manifest.json", "package.json", "skill.json")


def scan_skills(extra_paths: list = None) -> list:
    """Discover installed skill packs from known plugin cache paths."""
    import glob as _glob
    import json as _json

    patterns = list(_KNOWN_SKILL_PATTERNS)
    if extra_paths:
        patterns.extend(extra_paths)

    found = []
    seen_paths = set()
    for pattern in patterns:
        for candidate in _glob.glob(os.path.expanduser(pattern)):
            if not os.path.isdir(candidate):
                continue
            abs_path = os.path.abspath(candidate)
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)

            name = os.path.basename(candidate)
            version = "unknown"
            for manifest_name in _SKILL_MANIFEST_NAMES:
                manifest_path = os.path.join(candidate, manifest_name)
                if not os.path.exists(manifest_path):
                    continue
                try:
                    with open(manifest_path) as f:
                        data = _json.load(f)
                    name = data.get("name") or name
                    version = data.get("version") or version
                    break
                except (OSError, ValueError, TypeError):
                    continue

            found.append({"name": name, "version": version, "path": abs_path})

    found.sort(key=lambda item: (item["name"], item["path"]))
    return found


def detect_home_harness(harnesses: list) -> "str | None":
    """Choose the preferred harness using env override, then claude, then first."""
    env_name = os.environ.get("SYNLYNK_HOME_HARNESS", "").strip().lower()
    normalized = [(h.get("name", ""), h) for h in harnesses or []]
    if env_name:
        for name, _entry in normalized:
            if name.lower() == env_name:
                return name

    for name, _entry in normalized:
        if name.lower() == "claude":
            return name

    return normalized[0][0] if normalized else None


def parse_context_sections(repo_path: str) -> dict:
    """Extract ## sections from agent context files in a repository."""
    sections = {}
    for fname in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        path = os.path.join(repo_path, fname)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                text = f.read(4000)
        except OSError:
            continue

        current_title = None
        current_lines = []
        for line in text.splitlines():
            if line.startswith("## "):
                if current_title and current_lines:
                    sections.setdefault(current_title, "\n".join(current_lines).strip())
                current_title = line[3:].strip()
                current_lines = []
                continue
            if current_title is not None:
                current_lines.append(line)

        if current_title and current_lines:
            sections.setdefault(current_title, "\n".join(current_lines).strip())

    return sections


_MONOREPO_MARKERS = ("packages", "apps", "services", "modules", "libs")


def run_workspace_scan(roots: list = None, workspace_name: str = None,
                       dry_run: bool = False) -> dict:
    """Scan a workspace and return the contract payload used by init --wizard.

    roots: explicit list of repo paths. If omitted, discover git roots from
           common workspace locations plus the current directory.
    dry_run: accepted for contract parity; this implementation only returns
             the scan payload and does not write to disk.
    """
    import shutil as _shutil
    import time as _time

    if roots is None:
        search_dirs = [
            os.path.expanduser("~/dev"),
            os.path.expanduser("~/projects"),
            os.getcwd(),
        ]
        roots = find_git_roots(search_dirs, max_depth=2)

    normalized_roots = []
    seen_roots = set()
    for root in roots or []:
        if not root:
            continue
        abs_root = os.path.abspath(os.path.expanduser(root))
        if abs_root in seen_roots or not os.path.isdir(abs_root):
            continue
        seen_roots.add(abs_root)
        normalized_roots.append(abs_root)

    repos = []
    for repo_path in normalized_roots:
        readme_excerpt = ""
        readme_path = os.path.join(repo_path, "README.md")
        if os.path.exists(readme_path):
            try:
                with open(readme_path) as fh:
                    readme_excerpt = fh.read(200)
            except OSError:
                readme_excerpt = ""

        repos.append({
            "path": repo_path,
            "name": os.path.basename(repo_path),
            "stack_labels": fingerprint_stack(repo_path),
            "readme_excerpt": readme_excerpt,
            "context_sections": parse_context_sections(repo_path),
        })

    if len(repos) > 1:
        topology = "multi"
    elif repos and any(
        os.path.isdir(os.path.join(repos[0]["path"], marker))
        for marker in _MONOREPO_MARKERS
    ):
        topology = "monorepo"
    else:
        topology = "single"

    harnesses = []
    for name in ("claude", "agy", "codex", "grok", "gemini", "aider"):
        cli_path = _shutil.which(name)
        if not cli_path:
            continue
        version = "unknown"
        try:
            proc = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (proc.stdout or proc.stderr or "").strip().splitlines()
            if output:
                version = output[0]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        harnesses.append({
            "name": name,
            "cli": name,
            "version": version,
            "path": cli_path,
        })

    try:
        agents = discover_agents()
    except Exception:
        agents = []

    skills = scan_skills()
    home_harness = detect_home_harness(harnesses)

    if workspace_name is None:
        if normalized_roots:
            parent = os.path.basename(os.path.dirname(normalized_roots[0]))
            workspace_name = parent if parent and parent not in (os.sep, "~") else repos[0]["name"]
        else:
            workspace_name = os.path.basename(os.getcwd()) or "workspace"

    # ── BS-19 launch task trigger fields ─────────────────────────────────────
    primary_root = normalized_roots[0] if normalized_roots else os.getcwd()

    # test_ratio: test files / total source files (0.0 if no source files)
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
    test_count_files = _count_files(primary_root, ["test_*.py", "*_test.py", "*.test.ts",
                                                    "*.test.tsx", "*.test.js", "*.spec.ts", "*.spec.js"])
    test_ratio = test_count_files / src_count if src_count > 0 else 0.0

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

    # has_type_hints: Python repo + any .pyi files or >30% of .py files have annotations
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
                    if ("from __future__ import annotations" in content or
                            re.search(r"def \w+\([^)]*: \w|-> \w", content)):
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


def _workspace_config_dir(workspace_name: str) -> str:
    """Return a writable workspace config directory, preferring ~/.synlynk."""
    preferred = os.path.expanduser(f"~/.synlynk/workspaces/{workspace_name}")
    try:
        os.makedirs(preferred, exist_ok=True)
        return preferred
    except PermissionError:
        fallback = os.path.abspath(os.path.join(".synlynk", "workspaces", workspace_name))
        os.makedirs(fallback, exist_ok=True)
        return fallback


def write_workspace_config(scan_result: dict, workspace_name: str) -> str:
    """Write workspace config to ~/.synlynk/workspaces/<name>/config.json.

    Returns the path written.
    """
    import json as _json
    ws_dir = _workspace_config_dir(workspace_name)
    config = {
        "workspace_name": workspace_name,
        "topology": scan_result.get("topology", "single"),
        "home_harness": scan_result.get("home_harness"),
        "repos": [
            {
                "path": r["path"],
                "name": r["name"],
                "stack_labels": r["stack_labels"],
            }
            for r in scan_result.get("repos", [])
        ],
        "agent_roles": {},  # populated by wizard Screen 5
        "created_at": scan_result.get("scanned_at", ""),
        "last_scanned_at": scan_result.get("scanned_at", ""),
    }
    config_path = os.path.join(ws_dir, "config.json")
    open(config_path, "w").write(_json.dumps(config, indent=2))
    return config_path


def generate_structured_context(scan_result: dict,
                                 out_path: str = None) -> str:
    """Write structured context.md from a ScanResult dict.

    This replaces generate_context() when a workspace scan has been run.
    Falls back to generate_context() if scan_result is None.
    """
    context_file = out_path or ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)

    lines = []
    ws_name = scan_result.get("workspace_name", "workspace")
    lines.append(f"# synlynk context — {ws_name}")
    lines.append(f"generated: {scan_result.get('scanned_at', '')}")
    lines.append("")
    lines.append("## workspace")
    lines.append(f"name: {ws_name}")
    home_h = scan_result.get("home_harness") or "none"
    lines.append(f"home harness: {home_h}")
    repo_list = scan_result.get("repos", [])
    lines.append(f"repos: {len(repo_list)}")
    lines.append("")

    if repo_list:
        lines.append("## repos")
        for repo in repo_list:
            lines.append(f"### {repo['name']}")
            lines.append(f"path: {repo['path']}")
            stack = ", ".join(repo.get("stack_labels", [])) or "unknown"
            lines.append(f"stack: {stack}")
            excerpt = (repo.get("readme_excerpt") or "").replace("\n", " ").strip()
            if excerpt:
                lines.append(f"readme: {excerpt[:200]}")
            for title, content in (repo.get("context_sections") or {}).items():
                lines.append(f"\n### {title} (from {repo['name']})")
                lines.append(content[:300])
            lines.append("")

    harnesses = scan_result.get("harnesses", [])
    agents = scan_result.get("agents", [])
    if harnesses or agents:
        lines.append("## agent fleet")
        for h in harnesses:
            lines.append(f"{h['name']}: {h['version']} — {h['path']}")
        lines.append("")

    skills = scan_result.get("skills", [])
    if skills:
        lines.append("## skills")
        for s in skills:
            lines.append(f"{s['name']}: {s['version']} — {s['path']}")
        lines.append("")

    content = "\n".join(lines)
    try:
        open(context_file, "w").write(content)
        print(f"  ✓ context.md updated ({len(content)} chars) → {context_file}")
    except OSError as e:
        print(f"  ⚠ Could not write context.md: {e}")

    return content


def _extract_synlynk_section(content: str, marker_style: str = "html") -> Optional[str]:
    """Return the text inside synlynk markers, or the whole content for marker_style='none'."""
    if marker_style == "none":
        return content
    if marker_style == "html":
        m = re.search(
            r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$(.*?)^[ \t]*<!-- synlynk:end -->[ \t]*$',
            content, re.DOTALL | re.MULTILINE
        )
    else:  # hash
        m = re.search(
            r'^[ \t]*# synlynk:start[^\n]*\n(.*?)\n[ \t]*# synlynk:end[ \t]*$',
            content, re.DOTALL | re.MULTILINE
        )
    return m.group(1) if m else None


def _compute_section_sha(content: str) -> str:
    """Return first 16 hex chars of SHA-256 of content string."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _write_instruction_file(path: str, tool: str, content: str,
                             marker_style: str = "html") -> bool:
    """Write or update the synlynk block in an instruction file.

    marker_style='none': synlynk owns the whole file (overwrites).
    marker_style='html': <!-- synlynk:start --> markers.
    marker_style='hash': # synlynk:start markers.

    Behaviour:
    1. File absent            → create with markers
    2. File present, no marks → append block at end
    3. File present, has marks → replace section between markers
    Returns True always.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    if marker_style == "none":
        with open(path, "w") as f:
            f.write(content)
        return True

    start = f'<!-- synlynk:start version="{VERSION}" tool="{tool}" -->'
    end = "<!-- synlynk:end -->"
    start_pattern = "<!-- synlynk:start"
    if marker_style == "hash":
        start = f'# synlynk:start version="{VERSION}"'
        end = "# synlynk:end"
        start_pattern = "# synlynk:start"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(f"{start}\n{content}\n{end}\n")
        return True

    with open(path) as f:
        existing = f.read()

    if start_pattern in existing:
        # Replace section between markers — anchored to line boundaries so inline
        # mentions of the marker strings (e.g. in prose or code blocks) are ignored.
        if marker_style == "html":
            pattern = r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$.*?^[ \t]*<!-- synlynk:end -->[ \t]*$'
        else:
            pattern = r'^[ \t]*# synlynk:start[^\n]*$.*?^[ \t]*# synlynk:end[ \t]*$'
        replacement = f"{start}\n{content}\n{end}"
        new_content = re.sub(pattern, replacement, existing, flags=re.DOTALL | re.MULTILINE)
        with open(path, "w") as f:
            f.write(new_content)
        return True

    # Append block
    with open(path, "a") as f:
        f.write(f"\n{start}\n{content}\n{end}\n")
    return True


def _find_existing_doc(basename: str, target_dir: str, project_name: str) -> Optional[str]:
    """Searches for existing project doc content at alternate locations.

    Checks: root-level, project-docs/, project-prefixed variants (rxcc_memory.md),
    and uppercase variants. Returns the first path with >200 bytes of content,
    or None if nothing substantial exists.
    """
    slug = re.sub(r"[^a-z0-9]", "", project_name.lower()) if project_name else ""
    candidates = []
    # Root level (if target isn't already root)
    if target_dir not in (".", ""):
        candidates.append(basename)
    # project-docs/ (if target isn't project-docs)
    if target_dir != "project-docs":
        candidates.append(os.path.join("project-docs", basename))
    # Project-prefixed variants: rxcc_memory.md, rxcc-memory.md
    stem, ext = os.path.splitext(basename)
    if slug:
        candidates += [f"{slug}_{stem}{ext}", f"{slug}-{stem}{ext}"]
        candidates += [os.path.join("project-docs", f"{slug}_{stem}{ext}")]
    # Uppercase / alternative names
    candidates.append(basename.upper())
    for c in candidates:
        if os.path.exists(c):
            try:
                if os.path.getsize(c) > 200:
                    return c
            except OSError:
                pass
    return None


def _write_informed_skeleton(scan: dict, skip_existing: bool = True) -> list:
    """Writes project-docs skeleton, seeding from existing docs when available.

    Priority order for each file:
    1. File already exists at target path → skip (when skip_existing=True)
    2. Rich existing doc found at an alternate location → migrate content
    3. No existing content → generate skeleton from git history

    Returns list of (path, source) tuples describing what was written and why.
    """
    name = scan.get("project_name", "this project")
    desc = scan.get("description") or f"A project named {name}."
    topics = scan.get("recent_topics", [])
    langs = ", ".join(scan.get("languages", [])) or "unknown"
    commit_count = scan.get("commit_count", 0)
    caveat = (
        "\n> ⚠ Skeleton generated from git history — results vary by commit style. "
        "Review before proceeding.\n"
        if not scan.get("has_structured_commits") else ""
    )

    recent_work = "\n".join(f"- {t}" for t in topics[:5]) or "- (no commits found)"

    fallback_roadmap = f"""\
# {name} Roadmap
{caveat}
**Positioning:** [Describe what {name} is building toward]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
| v0.1.0 | Initial release | ✅ Shipped | — |
| v0.2.0 | [Next milestone] | 🔜 Next | — |

## Recent work (from git history — {commit_count} commits, {langs})
{recent_work}
"""

    fallback_memory = f"""\
# {name} Memory

## Project Overview
- **Name:** {name}
- **Description:** {desc}
- **Languages:** {langs}
- **Directories:** {", ".join(scan.get("top_dirs", [])) or "—"}

## Decisions
[Document key decisions here with [@username] attribution in team mode]

## Architecture
[Document key architectural decisions here]
"""

    fallback_todo = f"""\
# {name} — Todo

<!-- Status: [ ] active  [x] done  [-] deferred  [~] superseded  [>] absorbed -->

## Active Tasks
- [ ] Review and refine the generated roadmap.md <!-- id: 1 -->
- [ ] Review and update memory.md with actual decisions <!-- id: 2 -->
- [ ] Define first milestone in roadmap <!-- id: 3 -->

## Completed
"""

    dd = _docs_dir()
    targets = [
        (os.path.join(dd, "roadmap.md"), fallback_roadmap),
        (os.path.join(dd, "memory.md"),  fallback_memory),
        (os.path.join(dd, "todo.md"),    fallback_todo),
    ]

    written = []
    for path, fallback in targets:
        if skip_existing and os.path.exists(path):
            continue

        basename = os.path.basename(path)
        source = _find_existing_doc(basename, dd, name)
        if source:
            with open(source) as fh:
                content = fh.read()
            label = f"migrated from {source}"
        else:
            content = fallback
            label = "generated from git history"

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        written.append((path, label))
    return written


def _llm_enrich(agent_name: str, agent_cli: str, scan: dict) -> bool:
    """Calls the configured agent non-interactively to enrich project-docs.

    Passes the static scan result + current doc drafts as context.
    Writes enriched roadmap.md if the agent responds successfully.
    Returns True on success, False on failure.
    """
    name = scan.get("project_name", "this project")
    topics = "\n".join(f"- {t}" for t in scan.get("recent_topics", []))
    langs = ", ".join(scan.get("languages", [])) or "unknown"
    readme = scan.get("readme_summary", "")[:400]

    prompt = f"""\
You are helping initialise a synlynk project context for a software project.

Project: {name}
Description: {scan.get('description', '')}
Languages: {langs}
Commit count: {scan.get('commit_count', 0)}
Recent commit messages:
{topics}

README excerpt:
{readme}

Based on this, write a concise `roadmap.md` for this project in this exact format:

# {name} Roadmap

**Positioning:** [one sentence describing the product goal]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
[3-5 plausible milestone rows based on the commit history]

Keep it short. Infer from the evidence. Do not invent features not supported by the commits.
"""

    # Write prompt to a temp file to avoid shell escaping issues.
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    prompt_file = os.path.join(PROMPTS_DIR, "llm-enrich.md")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    baselines = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    flags = baselines.get("non_interactive_flags", ["--print"])
    cmd = [agent_cli] + flags

    try:
        with open(prompt_file) as pf:
            result = subprocess.run(cmd, stdin=pf, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not result.stdout.strip():
            return False
        enriched = result.stdout.strip()
        with open("project-docs/roadmap.md", "w") as f:
            f.write(enriched + "\n")
        return True
    except Exception:
        return False


def _relevant_files_for_story(story_id: str) -> list:
    """Returns up to 10 source file paths relevant to the story's engg_domain."""
    if not story_id:
        return []
    conn = _get_db()
    row = conn.execute(
        "SELECT engg_domain FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    if not row or row[0] == "unknown":
        return []
    engg = row[0]
    # Try to load cached scan meta first (faster, avoids git operations)
    meta = _load_scan_meta()
    skeleton = meta.get("skeleton", []) if meta else None
    # If no cached meta, try to check scan cache (may re-scan if HEAD changed)
    if skeleton is None:
        try:
            skeleton = _check_scan_cache()
        except Exception:
            skeleton = []
    if not skeleton:
        return []
    relevant = []
    for entry in skeleton:
        path = entry.get("file", "")
        symbols_str = " ".join(entry.get("symbols") or [])
        if engg in path or engg in symbols_str:
            relevant.append(path)
    return relevant[:10]


def _verify_contract_for_story(story_id: str, task: str) -> str:
    """Returns a ## How to Verify section with a pytest invocation. Empty string if no tests/ dir."""
    if not os.path.exists("tests"):
        return ""

    conn = _get_db()
    row = conn.execute(
        "SELECT title FROM stories WHERE story_id=?", (story_id,)
    ).fetchone() if story_id else None
    conn.close()
    title = (row[0] if row else "") or task

    # Derive test pattern: lowercase, alphanumeric + underscores, max 40 chars
    pattern = re.sub(r"[^a-z0-9_]", "", title.lower().replace(" ", "_"))[:40]
    if not pattern:
        return ""

    # Find first test file
    test_file = None
    for root, _dirs, files in os.walk("tests"):
        for f in sorted(files):
            if f.startswith("test_") and f.endswith(".py"):
                test_file = os.path.join(root, f)
                break
        if test_file:
            break

    if not test_file:
        return ""

    cmd = f"pytest {test_file} -k '{pattern}' -v" if pattern else f"pytest {test_file} -v"
    return (
        "\n\n## How to Verify\n"
        f"Run: `{cmd}`\n"
        "Expected: all matched tests pass, no new failures.\n"
    )


def _format_prompt_for_agent(agent: str, context_text: str, story_id: str,
                              task: str, file_section: str, verify_section: str) -> str:
    """Returns a prompt formatted for the agent's preferred input style.

    Codex: criteria list + file list first (ignores narrative prose).
    AGY: concise directive (prompt_via_arg — shell-escaping limits length).
    Claude: full context narrative (default).
    """
    story_ref = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""

    if agent == "codex":
        # Codex works best with explicit, scannable criteria and a concrete file list
        sentences = [s.strip() for s in re.split(r"[.!?]", task) if s.strip()]
        criteria = "\n".join(f"- {s}" for s in sentences) if sentences else f"- {task}"
        return (
            f"## Task Criteria\n{criteria}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"## Context\n{context_text}"
            f"{story_ref}\n"
        )

    if agent == "agy":
        # AGY receives the prompt as a CLI arg — keep short, lead with directive.
        # Working directory is explicit because agy resets CWD to its own scratch on startup.
        return (
            f"## Working Directory\n{os.getcwd()}\n"
            f"All file edits MUST be in this directory.\n\n"
            f"Task: {task}\n"
            f"{story_ref}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"Context summary:\n{context_text}"
        )

    # Default (claude): full context narrative
    return (
        f"{context_text}"
        f"{story_ref}"
        f"{file_section}"
        f"\n\n## Your Task\n{task}"
        f"{verify_section}\n"
    )


_CONTEXT_WARN_BYTES = 81920  # 80KB soft limit — warn but continue


def _warn_context_size(context_text: str) -> None:
    size = len(context_text.encode("utf-8"))
    if size > _CONTEXT_WARN_BYTES:
        print(f"  ⚠ context: full ({size // 1024}KB) — exceeds soft limit "
              f"({_CONTEXT_WARN_BYTES // 1024}KB)")
        print("    Use --context-mode task to reduce size")


def _preflight_dispatch(agent_name: str, dispatch_flags: list, db_conn=None) -> dict:
    """
    Fast preflight guard before every dispatch (~2s, no CLI spawn).

    Falls back to AGENT_CAPABILITY_BASELINES when harness_records are not yet
    available (v0.10.1). Returns:
    {"passed": bool, "sentinel": str|None, "reason": str|None}
    """
    import json as _json
    import socket as _socket

    baseline = {}
    if db_conn:
        try:
            row = db_conn.execute(
                "SELECT active_flags, active_contract FROM harness_records WHERE agent_name=?",
                (agent_name,),
            ).fetchone()
        except Exception:
            row = None
        if row:
            try:
                baseline["dispatch_flags"] = _json.loads(row[0]) if row[0] else {}
                baseline["headless_contract"] = _json.loads(row[1]) if row[1] else {}
                baseline["network_deps"] = baseline["headless_contract"].get("network_deps", {})
            except Exception:
                baseline = {}
    if not baseline:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})

    import time as _time
    _STALE_THRESHOLD = 3600  # 1hr

    if db_conn:
        try:
            _row = db_conn.execute(
                "SELECT installed_version, last_probe_at FROM harness_records WHERE agent_name=?",
                (agent_name,),
            ).fetchone()
        except Exception:
            _row = None
        if _row:
            _recorded_version, _last_probe_at = _row
            _is_stale = True
            if _last_probe_at:
                try:
                    _probe_ts = _time.mktime(_time.strptime(_last_probe_at, "%Y-%m-%dT%H:%M:%SZ"))
                    _is_stale = (_time.time() - _probe_ts) > _STALE_THRESHOLD
                except ValueError:
                    _is_stale = True

            if _is_stale:
                try:
                    _ver_result = subprocess.run(
                        [agent_name, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    _live_version = _ver_result.stdout.strip().split()[-1] if _ver_result.stdout.strip() else "unknown"
                    if _live_version != _recorded_version:
                        _write_sentinel_alert(
                            "WARNING",
                            "HARNESS_VERSION_DRIFT",
                            f"Agent '{agent_name}' version changed: {_recorded_version} -> {_live_version}. Run synlynk probe to update.",
                        )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

    flags_spec = baseline.get("dispatch_flags", {})
    if isinstance(flags_spec, dict):
        invalid_flags = set(flags_spec.get("invalid_flags", []))
    else:
        invalid_flags = set()

    for flag in dispatch_flags or []:
        f = flag.split("=", 1)[0]
        if f in invalid_flags:
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Flag {f!r} is invalid for agent '{agent_name}' (LIVE-1 class error)",
            }

    required = baseline.get("network_deps", {}).get("required_endpoints", [])
    for endpoint in required:
        host, _, port_str = endpoint.rpartition(":")
        if not host:
            host = endpoint
        port = int(port_str) if port_str.isdigit() else 443
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            sock.close()
        except (OSError, ConnectionRefusedError, _socket.timeout):
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Required endpoint {endpoint!r} unreachable for agent '{agent_name}'",
            }

    return {"passed": True, "sentinel": None, "reason": None}


def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None) -> dict:
    """Dispatches an agent to run a task in the background.

    Uses non-interactive agent mode (no PTY). Stdout captured to
    .synlynk/logs/<job_id>.log. Returns the job dict.
    Raises ValueError for unknown agent names.

    When force_agent=False (default) and a story_id is given, the capability
    router may override 'agent' with a better-scoring one. Set force_agent=True
    to disable the router override and dispatch to the exact agent specified.
    force_agent has no effect when story_id is None (no routing can occur).
    """
    if story_id and not force_agent:
        best = _best_agent_for_story(story_id)
        if best and best in AGENT_CAPABILITY_BASELINES:
            agent = best

    if agent not in AGENT_CAPABILITY_BASELINES:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")

    baselines = AGENT_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]
    flags = flags + _dispatch_flags_for_agent(agent)
    preflight = _preflight_dispatch(agent_name=agent, dispatch_flags=flags, db_conn=None)
    if isinstance(preflight, dict):
        if not preflight.get("passed", False):
            sentinel_path = os.path.join(".synlynk", "sentinel.md")
            _write_sentinel_alert(
                "CRITICAL",
                preflight["sentinel"],
                preflight["reason"],
                sentinel_path,
            )
            raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight['reason']}")
    elif preflight:
        sentinel_path = os.path.join(".synlynk", "sentinel.md")
        _write_sentinel_alert("CRITICAL", "HARNESS_PREFLIGHT_FAIL", str(preflight), sentinel_path)
        raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight}")

    profile = _load_agent_profile(agent)
    if agent == "grok" and profile.get("always_approve_unsupported"):
        flags = [flag for flag in flags if flag != "--always-approve"]
        flags = flags + ["--permission-mode", "bypassPermissions"]
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    model_at_dispatch = _probe_model_version(agent, cli)
    if context_mode is None:
        context_mode = profile.get("context_mode", "task")
    # else: explicit caller value wins; profile is default-only

    import hashlib as _hashlib
    job_id = "job-" + _hashlib.md5(
        f"{agent}{task}{time.time()}".encode()
    ).hexdigest()[:8]

    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    contexts_dir = os.path.join(".synlynk", "contexts")
    os.makedirs(contexts_dir, exist_ok=True)

    log_file = os.path.join(LOGS_DIR, f"{job_id}.log")
    prompt_file = os.path.join(PROMPTS_DIR, f"{job_id}.md")
    context_file = os.path.join(contexts_dir, f"{job_id}.md")

    context_text = ""
    if context_mode != "none":
        if context_mode == "task":
            scope = f"task:{story_id}" if story_id else "full"
        else:
            scope = "full"
        try:
            context_text = generate_context(scope=scope, out_path=context_file) or ""
        except Exception:
            pass
    _warn_context_size(context_text)
    context_max_bytes = profile.get("context_max_bytes")
    if context_max_bytes is not None:
        try:
            context_max_bytes = int(context_max_bytes)
        except (TypeError, ValueError):
            context_max_bytes = None
    if context_max_bytes is not None:
        encoded_context = context_text.encode("utf-8")
        if len(encoded_context) > context_max_bytes:
            context_text = encoded_context[:context_max_bytes].decode("utf-8", errors="ignore")
            print(f"  context truncated to {context_max_bytes}B (agent profile limit)")

    # Inject relevant file list
    file_list = _relevant_files_for_story(story_id) if story_id else []
    file_section = ""
    if file_list:
        file_section = "\n\n## Relevant Files\n" + "\n".join(f"- `{f}`" for f in file_list)

    verify_section = _verify_contract_for_story(story_id, task) if story_id else ""

    prompt = _format_prompt_for_agent(
        agent, context_text, story_id or "", task, file_section, verify_section
    )
    with open(prompt_file, "w") as f:
        f.write(prompt)

    import shlex as _shlex
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")
    if prompt_via_arg:
        # Agent takes prompt as a flag value, not stdin.
        # prompt_flag ("--single", "-p") is placed last so it immediately precedes "$PROMPT",
        # preventing other flags from being consumed as the prompt value.
        # e.g. grok --yes --output-format json --single "$PROMPT"
        if prompt_flag:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
        else:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"

    contract = baselines.get("headless_contract", {})
    env = os.environ.copy()
    for var in contract.get("env_vars_required", []):
        if "=" in var:
            k, v = var.split("=", 1)
            env[k] = v

    proc = subprocess.Popen(
        ["sh", "-c", shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=os.getcwd(),
        env=env,
    )

    job = {
        "id": job_id,
        "agent": agent,
        "story_id": story_id or "",
        "task": task,
        "pid": proc.pid,
        "log_file": log_file,
        "prompt_file": prompt_file,
        "context_file": context_file if context_mode != "none" else "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_rework": _count_dispatch_rework(story_id or ""),
        "micro_rework": 0,
        "model_at_dispatch": model_at_dispatch,
    }

    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)

    dconn = None
    try:
        dconn = _get_db()
        dconn.execute(
            "INSERT OR REPLACE INTO daemon_jobs "
            "(job_id, agent, task, story_id, status, priority, depends_on, pid, "
            "enqueued_at, started_at, log_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                agent,
                task,
                story_id,
                "running",
                5,
                "[]",
                proc.pid,
                job["started_at"],
                job["started_at"],
                log_file,
            ),
        )
        dconn.commit()
    finally:
        if dconn is not None:
            try:
                dconn.close()
            except Exception:
                pass

    log_telemetry_event({"type": "dispatch", "agent": agent,
                         "story_id": story_id, "job_id": job_id})
    return job


def cmd_jobs(all_jobs: bool = False, watch: bool = False) -> None:
    """Prints jobs from daemon_jobs in state.db; --all includes done/failed; --watch refreshes."""
    import time as _time

    def _parse_age(enqueued_at: str) -> str:
        try:
            enq = _time.mktime(_time.strptime(enqueued_at, "%Y-%m-%dT%H:%M:%S"))
            age_s = int(_time.time() - enq)
            if age_s < 60:
                return f"{age_s}s"
            if age_s < 3600:
                return f"{age_s // 60}m{age_s % 60:02d}s"
            return f"{age_s // 3600}h{(age_s % 3600) // 60}m"
        except Exception:
            return "?"

    def _render_legacy_jobs() -> None:
        _reconcile_jobs()
        jobs = _load_jobs()
        if not jobs:
            print("No jobs found. Use `synlynk dispatch <agent> --task <task>` to start one.")
            return
        visible = jobs if all_jobs else [j for j in jobs if j["status"] == "running"]
        if not visible:
            completed = len([j for j in jobs if j["status"] in ("completed", "failed")])
            print(f"No running jobs. ({completed} completed/failed — use `synlynk jobs --all` to see)")
            return
        header = f"{'ID':12}  {'AGENT':10}  {'STATUS':10}  {'STORY':6}  TASK"
        print(f"{_BOLD}{header}{_RESET}")
        print("─" * 70)
        for j in visible:
            sid = (j.get("story_id") or "—")[:6]
            task = (j.get("task") or "")[:40]
            status = j["status"]
            color = _GREEN if status == "running" else (_DIM if status == "completed" else _YELLOW)
            print(f"{j['id']:12}  {j['agent']:10}  {color}{status:10}{_RESET}  {sid:6}  {task}")

    def _render() -> None:
        _reconcile_daemon_jobs()
        conn = _get_db()
        rows = conn.execute(
            "SELECT job_id, agent, story_id, status, enqueued_at, exit_code "
            "FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 50"
        ).fetchall()
        conn.close()

        if not rows:
            _render_legacy_jobs()
            return

        if all_jobs:
            visible = rows
        else:
            visible = [r for r in rows if r[3] in ("queued", "running")]
            if not visible:
                done = sum(1 for r in rows if r[3] in ("done", "failed"))
                print(f"  No active jobs. ({done} completed — use synlynk jobs --all)")
                return

        header = f"{'ID':14}  {'AGENT':8}  {'STORY':12}  {'STATUS':10}  {'AGE':8}  {'EXIT':4}"
        print(f"{_BOLD}{header}{_RESET}")
        print("  " + "─" * 64)
        for job_id, agent, story_id, status, enqueued_at, exit_code in visible:
            sid = (story_id or "—")[:12]
            age = _parse_age(enqueued_at)
            color = _GREEN if status == "running" else (_DIM if status in ("done", "failed") else _YELLOW)
            exit_str = str(exit_code) if exit_code is not None else "—"
            print(
                f"  {job_id:14}  {agent:8}  {sid:12}  "
                f"{color}{status:10}{_RESET}  {age:8}  {exit_str:4}"
            )

    if watch:
        try:
            while True:
                print("\033[H\033[J", end="")
                try:
                    _render()
                except Exception as e:
                    print(f"  render error: {e}")
                print(f"\n  {_DIM}Refreshing every 2s... Ctrl-C to exit{_RESET}")
                _time.sleep(2)
        except KeyboardInterrupt:
            pass
    else:
        _render()


def cmd_agent_configure(agent_name: str) -> None:
    """Interactively write .agents/<agent_name>.json context-profile settings."""
    import json as _json

    if agent_name not in AGENT_CAPABILITY_BASELINES:
        print(f"  Unknown agent '{agent_name}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")
        return

    os.makedirs(".agents", exist_ok=True)
    path = os.path.join(".agents", f"{agent_name}.json")

    existing = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                existing = _json.load(f)
            print(f"  Existing profile at {path}:")
            for key, value in existing.items():
                print(f"    {key}: {value}")
        except Exception:
            existing = {}

    print(f"\n  Configuring context profile for '{agent_name}' (press Enter to keep current)\n")

    def _ask(default, desc):
        shown = "" if default is None else str(default)
        value = input(f"  {desc} [{shown}]: ").strip()
        return value if value else default

    context_mode = _ask(existing.get("context_mode", "task"),
                        "context_mode (none / task / full)")
    max_bytes_raw = _ask(existing.get("context_max_bytes", None),
                         "context_max_bytes (int, leave blank for no limit)")

    profile = {
        "agent": agent_name,
        "harness": existing.get("harness", agent_name),
        "model": existing.get("model", "unknown"),
        "context_mode": context_mode,
    }
    if max_bytes_raw not in ("", None):
        try:
            profile["context_max_bytes"] = int(max_bytes_raw)
        except (TypeError, ValueError):
            pass

    with open(path, "w") as f:
        _json.dump(profile, f, indent=2)
        f.write("\n")
    print(f"\n  {_GREEN}✓{_RESET} Written {path}")


def cmd_relay_start(port: int = None) -> None:
    """Starts the relay broker in the foreground (Ctrl-C to stop)."""
    relay = SynlynkRelay(port=port)
    relay.start()


def cmd_relay_broadcast(kind: str, body: str, relay_url: str = None) -> None:
    """Publishes a broadcast event to the relay."""
    import json as _json
    import socket as _socket
    import urllib.request as _req

    url = relay_url or f"http://localhost:{SynlynkRelay.RELAY_PORT}/publish"
    event = _build_relay_event("broadcast", {
        "kind": kind,
        "body": body,
        "from": f"cli@{_socket.gethostname()}",
    })
    data = _json.dumps(event).encode()
    req = _req.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with _req.urlopen(req, timeout=5) as resp:
            result = _json.loads(resp.read())
        fans = result.get("fans", 0)
        print(f"  {_GREEN}✓{_RESET} broadcast sent ({kind}) → {fans} subscriber(s)")
    except Exception as e:
        print(f"  {_YELLOW}⚠{_RESET} relay not reachable: {e}")
        print(f"  Start relay: synlynk relay start")


def cmd_agent_run(name: str, dry_run: bool = False, install_cron: bool = False) -> None:
    """Run named agent: collect signals → dedup → investigate → file → fix."""
    import hashlib as _hashlib

    cfg = _load_agent_config(name)
    if install_cron:
        _install_cron_entry(name)
        return

    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    print(f"  [agent:{name}] {'DRY RUN — ' if dry_run else ''}collecting signals{' (CI mode)' if is_ci else ''}")

    collector_map = {
        "test_suite": _collect_test_suite,
        "sentinel_alerts": _collect_sentinel_alerts,
        "telemetry_anomaly": _collect_telemetry_anomaly,
        "capability_drop": _collect_capability_drop,
        "github_issues": _collect_github_issues,
    }
    ci_skip = {"sentinel_alerts", "telemetry_anomaly"}

    all_findings: list = []
    for signal_cfg in cfg.get("signals", []):
        stype = signal_cfg.get("type")
        if is_ci and stype in ci_skip:
            continue
        collector = collector_map.get(stype)
        if collector is None:
            print(f"  [agent:{name}] unknown signal type: {stype}")
            continue
        try:
            found = collector(signal_cfg)
            all_findings.extend(found)
        except Exception as e:
            print(f"  [agent:{name}] collector {stype} error: {e}")

    new_findings = _dedup_findings(all_findings)
    print(f"  [agent:{name}] {len(all_findings)} signals, {len(new_findings)} new after dedup")

    if dry_run:
        for f in new_findings:
            print(f"  [{f['severity'].upper()}] {f['type']}: {f['summary']}")
        return

    severity_order = {"high": 0, "medium": 1, "low": 2}
    new_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 2))
    to_process = new_findings[:5]

    run_summary_lines = []
    conn = _get_db()

    for finding in to_process:
        print(f"  [agent:{name}] investigating: {finding['summary'][:80]}")
        investigation = _run_investigation(finding, cfg)
        gh_issue_url = _file_gh_issue(finding, investigation, dry_run=False)
        status = "filed"

        fix_pr_url = ""
        if investigation["fix_signal"]:
            fix_status, fix_pr_url = _attempt_fix(
                finding, investigation,
                fixer=cfg.get("fixer", "claude"), dry_run=False
            )
            if fix_status == "fix_attempted":
                status = "fix_attempted"
            elif fix_status == "fix_failed":
                status = "fix_failed"

        run_id = "run-" + _hashlib.md5(
            f"{finding['signal_hash']}{time.time()}".encode()
        ).hexdigest()[:8]
        pr_url_to_store = fix_pr_url if investigation["fix_signal"] else ""
        conn.execute(
            "INSERT INTO autopilot_runs "
            "(id, agent_name, signal_type, signal_hash, severity, summary, status, gh_issue_url, pr_url, story_id, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (run_id, name, finding["type"], finding["signal_hash"],
             finding["severity"], finding["summary"][:200],
             status, gh_issue_url, pr_url_to_store, investigation.get("story_id", ""))
        )
        conn.commit()
        run_summary_lines.append(
            f"  [{finding['severity'].upper()}] {finding['type']}: {finding['summary'][:60]} → {status}"
        )
        print(f"  [agent:{name}] {finding['type']} → {status}")

    conn.close()

    devlog_dir = os.path.join(_docs_dir(), "devlogs")
    if os.path.exists(devlog_dir):
        devlog_path = os.path.join(devlog_dir, f"{name}.md")
        n_high = sum(1 for f in to_process if f.get("severity") == "high")
        n_med = sum(1 for f in to_process if f.get("severity") == "medium")
        n_fix = sum(1 for l in run_summary_lines if "fix_attempted" in l)
        n_filed = sum(1 for l in run_summary_lines if " filed" in l)
        run_id_short = _hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        entry = (
            f"\n{time.strftime('%Y-%m-%dT%H:%M:%S')} · "
            f"{len(to_process)} findings ({n_high} high, {n_med} medium) · "
            f"{n_filed} filed · {n_fix} fix_attempted · run-{run_id_short}\n"
        )
        with open(devlog_path, "a") as f:
            f.write(entry)

    print(f"  [agent:{name}] done — {len(to_process)} findings processed")


def _install_cron_entry(name: str) -> None:
    """Install local crontab entry for the named agent (idempotent)."""
    repo_path = os.path.abspath(".")
    synlynk_bin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "bin",
        "synlynk.py",
    )
    entry = (
        f"0 */6 * * * cd {repo_path} && "
        f"python3 {synlynk_bin} agent run {name} "
        f">> ~/.synlynk/autopilot.log 2>&1"
    )
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = result.stdout if result.returncode == 0 else ""
    if entry in current:
        print("  [cron] Entry already installed (idempotent)")
        return
    new_crontab = current.rstrip("\n") + "\n" + entry + "\n"
    result2 = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if result2.returncode != 0:
        print(f"  [cron] Failed to install crontab entry (exit {result2.returncode})")
        return
    print(f"  [cron] Installed: {entry}")


def cmd_agent_list() -> None:
    """List .agents/ config files and their last run status."""
    agents_dir = ".agents"
    if not os.path.exists(agents_dir):
        print("  No .agents/ directory found")
        return
    files = [f for f in os.listdir(agents_dir) if f.endswith(".json")]
    if not files:
        print("  No agent configs in .agents/")
        return
    conn = _get_db()
    for fname in sorted(files):
        agent_name = fname[:-5]
        row = conn.execute(
            "SELECT ts, status FROM autopilot_runs WHERE agent_name=? ORDER BY ts DESC LIMIT 1",
            (agent_name,)
        ).fetchone()
        last_run = f"{row[0]}  status={row[1]}" if row else "never run"
        print(f"  {agent_name:<25}  {last_run}")
    conn.close()


def _collect_test_suite(signal_cfg: dict) -> list:
    """Run pytest; return a high-severity finding if any test fails."""
    import hashlib as _hashlib
    cmd = signal_cfg.get("command", "pytest tests/ -q --tb=short").split()
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode == 0:
        return []
    output = result.stdout or ""
    signal_hash = _hashlib.md5(output[:500].encode()).hexdigest()[:16]
    return [{
        "type": "test_suite",
        "severity": "high",
        "summary": f"Test suite failure: {output.splitlines()[-1][:120] if output.splitlines() else 'unknown'}",
        "detail": output[:3000],
        "signal_hash": signal_hash,
    }]


def _collect_sentinel_alerts(signal_cfg: dict) -> list:
    """Read sentinel.md, return a finding per ⚠ alert line."""
    import hashlib as _hashlib
    path = signal_cfg.get("path", ".synlynk/sentinel.md")
    if not os.path.exists(path):
        return []
    lines = [l for l in open(path).read().splitlines() if "⚠" in l]
    findings = []
    for line in lines:
        upper = line.upper()
        if "FLATLINE" in upper or "QUOTA_EXHAUSTED" in upper or "CRITICAL" in upper:
            severity = "high"
        else:
            severity = "medium"
        signal_hash = _hashlib.md5(line.encode()).hexdigest()[:16]
        findings.append({
            "type": "sentinel_alerts",
            "severity": severity,
            "summary": line.strip()[:200],
            "detail": line.strip(),
            "signal_hash": signal_hash,
        })
    return findings


def _collect_telemetry_anomaly(signal_cfg: dict) -> list:
    """Compute failure rate over last 20 telemetry entries; return finding if above threshold."""
    import json as _json, hashlib as _hashlib
    path = ".synlynk/telemetry.json"
    if not os.path.exists(path):
        return []
    try:
        entries = _json.loads(open(path).read())
    except Exception:
        return []
    recent = entries[-20:]
    if len(recent) < 5:
        return []
    failures = sum(1 for e in recent if e.get("exit_code", 0) != 0)
    threshold = signal_cfg.get("failure_rate_threshold", 0.30)
    rate = failures / len(recent)
    if rate < threshold:
        return []
    severity = "high" if rate >= 0.60 else "medium"
    summary = f"High failure rate: {failures}/{len(recent)} sessions failed ({rate:.0%})"
    signal_hash = _hashlib.md5(summary.encode()).hexdigest()[:16]
    return [{
        "type": "telemetry_anomaly",
        "severity": severity,
        "summary": summary,
        "detail": summary,
        "signal_hash": signal_hash,
    }]


def _collect_capability_drop(signal_cfg: dict) -> list:
    """Compare each agent's avg quality: last 7 days vs. prior 7 days.
    Skip agents with fewer than 2 ratings in either window."""
    import hashlib as _hashlib
    drop_threshold = signal_cfg.get("drop_threshold", 1.5)
    conn = _get_db()
    agents = [r[0] for r in conn.execute(
        "SELECT DISTINCT agent FROM capability_ratings"
    ).fetchall()]
    findings = []
    for agent in agents:
        recent = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM capability_ratings "
            "WHERE agent=? AND ts > datetime('now', '-7 days')",
            (agent,)
        ).fetchone()
        prior = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM capability_ratings "
            "WHERE agent=? AND ts <= datetime('now', '-7 days') "
            "  AND ts > datetime('now', '-14 days')",
            (agent,)
        ).fetchone()
        if not recent or not prior:
            continue
        recent_avg, recent_n = recent
        prior_avg, prior_n = prior
        if recent_n < 2 or prior_n < 2:
            continue
        if recent_avg is None or prior_avg is None:
            continue
        drop = prior_avg - recent_avg
        if drop < drop_threshold:
            continue
        severity = "high" if drop >= 3.0 else "medium"
        summary = f"Capability drop for {agent}: {prior_avg:.1f} → {recent_avg:.1f} (Δ{drop:.1f}pts)"
        signal_hash = _hashlib.md5(f"{agent}{round(drop, 1)}".encode()).hexdigest()[:16]
        findings.append({
            "type": "capability_drop",
            "severity": severity,
            "summary": summary,
            "detail": summary,
            "signal_hash": signal_hash,
        })
    conn.close()
    return findings


def _collect_github_issues(signal_cfg: dict) -> list:
    """List open GitHub issues with matching labels via `gh issue list`."""
    import json as _json, hashlib as _hashlib
    labels = signal_cfg.get("labels", ["bug"])
    label_str = ",".join(labels)
    result = subprocess.run(
        ["gh", "issue", "list", "--label", label_str,
         "--json", "number,title,body,createdAt,labels", "--limit", "20"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [support] gh issue list failed: {result.stderr[:100]}")
        return []
    try:
        issues = _json.loads(result.stdout)
    except Exception:
        return []
    findings = []
    for issue in issues:
        issue_labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        if "support-engineer" in issue_labels:
            continue
        signal_hash = _hashlib.md5(str(issue.get("number", "")).encode()).hexdigest()[:16]
        findings.append({
            "type": "github_issues",
            "severity": "medium",
            "summary": f"#{issue['number']}: {issue.get('title', '')[:100]}",
            "detail": issue.get("body", "")[:500],
            "signal_hash": signal_hash,
        })
    return findings


def _dedup_findings(findings: list) -> list:
    """Filter findings whose signal_hash appeared in autopilot_runs within dedup window.
    github_issues uses 30-day window to avoid re-filing same issue every 8 days."""
    if not findings:
        return []
    conn = _get_db()
    new_findings = []
    for f in findings:
        days = 30 if f.get("type") == "github_issues" else 7
        row = conn.execute(
            "SELECT id FROM autopilot_runs WHERE signal_hash=? AND ts > datetime('now', ?)",
            (f["signal_hash"], f"-{days} days")
        ).fetchone()
        if row is None:
            new_findings.append(f)
    conn.close()
    return new_findings


def _run_investigation(finding: dict, agent_cfg: dict) -> dict:
    """Build prompt, dispatch investigator foreground (5-min timeout), parse output."""
    import hashlib as _hashlib, shlex as _shlex

    agent = agent_cfg.get("investigator", "claude")
    if agent not in AGENT_CAPABILITY_BASELINES:
        agent = "claude"

    # Create story in DB
    story_id = "support-" + _hashlib.md5(finding["signal_hash"].encode()).hexdigest()[:8]
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, engg_domain, phase) VALUES (?, ?, ?, ?)",
            (story_id, finding["summary"][:100], "test", "scale")
        )
        conn.commit()
    finally:
        conn.close()

    # Build prompt
    try:
        generate_context(scope="full")
    except Exception:
        pass
    context_text = ""
    if os.path.exists(".synlynk/context.md"):
        context_text = open(".synlynk/context.md").read()

    prompt = (
        f"## Signal: {finding['type']} (severity={finding['severity']})\n\n"
        f"{finding['detail']}\n\n"
        f"---\n\n{context_text}\n\n"
        "## Task\n"
        "Identify the root cause. If a code fix is possible, produce a unified diff with "
        "exact file paths. If not fixable, summarise your investigation findings. "
        "If providing a fix, include a line starting with `# FIX:` before the diff block."
    )

    # Write prompt file
    job_id = "support-" + _hashlib.md5(
        f"{finding['signal_hash']}{time.time()}".encode()
    ).hexdigest()[:8]
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, f"{job_id}.log")
    prompt_file = os.path.join(PROMPTS_DIR, f"{job_id}.md")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    # Build shell command (same pattern as dispatch_agent)
    baselines = AGENT_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")
    if prompt_via_arg and prompt_flag:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
    else:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)

    if prompt_via_arg:
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        shell_cmd = (
            f"{cmd_str} < {_shlex.quote(prompt_file)} "
            f"> {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )

    try:
        subprocess.run(["sh", "-c", shell_cmd], timeout=300)
    except subprocess.TimeoutExpired:
        pass

    log_text = ""
    if os.path.exists(log_file):
        log_text = open(log_file).read()

    import re as _re
    fix_signal = "# FIX:" in log_text or bool(
        _re.search(r"^--- a/", log_text, _re.MULTILINE)
    )

    return {
        "summary": log_text[:500] if log_text else "(no output)",
        "fix_signal": fix_signal,
        "log_text": log_text,
        "story_id": story_id,
        "log_file": log_file,
    }


def _file_gh_issue(finding: dict, investigation: dict, dry_run: bool) -> str:
    """File a GitHub issue via `gh issue create`. Returns issue URL or '' in dry-run."""
    if dry_run:
        return ""
    title = f"[support] {finding['type']}: {finding['summary'][:80]}"
    body = (
        f"## Signal\n\n**Type:** {finding['type']}  \n**Severity:** {finding.get('severity', '?')}\n\n"
        f"## Investigation\n\n{investigation['summary']}\n\n"
        f"**Story:** `{investigation.get('story_id', 'n/a')}`\n"
    )
    result = subprocess.run(
        ["gh", "issue", "create",
         "--title", title,
         "--body", body,
         "--label", "bug,support-engineer"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [support] gh issue create failed: {result.stderr[:200]}")
        return ""
    return result.stdout.strip()


def _extract_diff(text: str) -> Optional[str]:
    """Extract first unified diff block from text (fenced or raw)."""
    import re as _re
    # Prefer fenced ```diff block
    m = _re.search(r"```(?:diff)?\n(---[\s\S]+?)```", text)
    if m:
        return m.group(1)
    # Fall back to raw unified diff
    m = _re.search(r"(--- a/[\s\S]+?)(?=\n[^+\-@ \t]|\Z)", text)
    if m:
        return m.group(1)
    return None


def _attempt_fix(finding: dict, investigation: dict, fixer: str, dry_run: bool) -> tuple:
    """Branch, apply diff, run tests. Returns (status, pr_url) tuple.
    status: 'fix_attempted'|'fix_failed'|'no_diff'|'dry_run'"""
    import tempfile as _tempfile

    if dry_run:
        return "dry_run", ""

    diff = _extract_diff(investigation.get("log_text", ""))
    if diff is None:
        return "no_diff", ""

    branch = f"support/fix-{finding['signal_hash'][:8]}"
    base_branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    base_branch = base_branch_result.stdout.strip() or "main"

    # Create fix branch
    br = subprocess.run(["git", "checkout", "-b", branch], capture_output=True)
    if br.returncode != 0:
        subprocess.run(["git", "checkout", branch], capture_output=True)

    # Write diff to temp file and apply
    with _tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tf:
        tf.write(diff)
        patch_path = tf.name

    try:
        apply = subprocess.run(["git", "apply", patch_path], capture_output=True)
    finally:
        try:
            os.unlink(patch_path)
        except OSError:
            pass

    if apply.returncode != 0:
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        return "fix_failed", ""

    # Commit the patch
    subprocess.run(["git", "add", "-A"], capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"[support] fix: {finding['summary'][:60]}"],
        capture_output=True,
    )

    # Run tests
    test_result = subprocess.run(
        ["pytest", "tests/", "-q", "--tb=no"],
        capture_output=True, text=True,
    )

    if test_result.returncode == 0:
        pr_result = subprocess.run(
            ["gh", "pr", "create", "--draft",
             "--title", f"[support] fix: {finding['summary'][:60]}",
             "--body", (
                 f"Auto-generated fix.\n\n"
                 f"**Story:** `{investigation.get('story_id', 'n/a')}`\n\n"
                 f"**Investigation:**\n{investigation.get('summary', '')[:300]}"
             )],
            capture_output=True, text=True,
        )
        if pr_result.returncode != 0:
            print(f"  [support] gh pr create failed: {pr_result.stderr[:200]}")
        pr_url = pr_result.stdout.strip() if pr_result.returncode == 0 else ""
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        return "fix_attempted", pr_url
    else:
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        return "fix_failed", ""


def cmd_logs(job_id: str, tail: int = 50) -> None:
    """Prints the captured stdout of a dispatched job."""
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        print(f"No job found with id '{job_id}'. Run `synlynk jobs` to list jobs.")
        return
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        print(f"Log file not found for job {job_id}.")
        return
    print(f"{_BOLD}── logs: {job_id} ({job['agent']}) ─────────────────────────{_RESET}")
    with open(log_file) as f:
        lines = f.readlines()
    for line in lines[-tail:]:
        print(line, end="")
    if len(lines) > tail:
        print(f"\n{_DIM}(showing last {tail} of {len(lines)} lines){_RESET}")


def cmd_shell(story_id: str = None) -> None:
    """Spawns an interactive subshell with synlynk context env vars injected.

    The shell runs in the current directory (worktree-per-story lands in v0.5.0).
    On exit the calling process resumes normally.
    """
    shell = os.environ.get("SHELL", "/bin/bash")
    env = {**os.environ,
           "SYNLYNK_PROJECT_DIR": os.path.abspath("."),
           "SYNLYNK_STORY_ID": story_id or "",
           "SYNLYNK_CONTEXT": os.path.abspath(".synlynk/context.md")}
    label = f"story #{story_id}" if story_id else "synlynk"
    print(f"{_BOLD}Entering synlynk shell ({label}).{_RESET} "
          f"Type {_CYAN}exit{_RESET} to return.")
    subprocess.run([shell], env=env)
    print(f"{_DIM}Returned from synlynk shell.{_RESET}")


def cmd_launch(agent: str, story_id: str = None) -> None:
    """Launches an agent CLI interactively in the current directory.

    Pre-generates .synlynk/context-<agent>.md and starts the CLI so the
    agent reads it as initial context. Stdout/stderr are not captured —
    this is an interactive session. Telemetry is logged on exit.
    """
    if agent not in AGENT_CAPABILITY_BASELINES:
        print(f"Unknown agent '{agent}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")
        return

    cli = AGENT_CAPABILITY_BASELINES[agent]["cli"]

    try:
        generate_context(scope="full")
    except Exception:
        pass
    src = ".synlynk/context.md"
    dest = f".synlynk/context-{agent}.md"
    if os.path.exists(src):
        import shutil as _shutil
        _shutil.copy(src, dest)

    label = f"story #{story_id}" if story_id else "interactive session"
    print(f"{_BOLD}Launching {agent} — {label}.{_RESET}")
    print(f"  Context: {_CYAN}{dest}{_RESET}")
    print(f"  Exit the agent to return to synlynk.\n")

    start = time.time()
    result = subprocess.run([cli])
    duration = time.time() - start

    log_telemetry_event({"type": "launch", "agent": agent,
                         "story_id": story_id, "exit_code": result.returncode,
                         "duration_s": round(duration, 1)})
    update_costs(cli, 0, 0, duration)
    print(f"\n{_DIM}Returned from {agent}. Duration: {duration:.0f}s{_RESET}")


def cmd_launch_ftue(dry_run: bool = False, list_mode: bool = False) -> None:
    """FTUE task picker TUI - Screen 1 -> Screen 2 -> dispatch
    - dry_run: print selected tasks without TUI or dispatch
    - list_mode: print full template pool with trigger conditions
    """
    if list_mode:
        print(f"\n  {_BOLD}synlynk launch - task template pool ({len(LAUNCH_TASK_TEMPLATES)} templates){_RESET}\n")
        for t in LAUNCH_TASK_TEMPLATES:
            cond = t.get("trigger_condition")
            cond_str = "always" if cond is None else "(scan condition)"
            marker = "●" if t["id"] in CORE_TEMPLATE_IDS else "○"
            print(f"  {marker} {t['id']:<24}  {t['cycle']:<8}  {t['agent']:<8}  {cond_str}")
        print()
        return

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
        print(f"\n  {_BOLD}synlynk launch - dry run{_RESET}  "
              f"{_DIM}workspace: {scan.get('workspace_name', 'unknown')}{_RESET}\n")
        for i, t in enumerate(tasks, 1):
            est = t.get("est_hours", 1)
            est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
            print(f"  [{i}] {t['id']:<24} {t['cycle']:<8}  {t['agent']:<8}  {est_str}")
        print()
        return

    while True:
        chosen = _launch_screen_tasks(tasks, scan)
        if chosen is None:
            return

        confirmed, prompt = _launch_screen_preview(chosen, scan)
        if not confirmed:
            continue

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


def cmd_run_trio(task: str, story_id: str = None) -> None:
    """Dispatches all functional agents in parallel — one job per agent.

    This is a parallel convenience wrapper, NOT the sequential Trio pipeline.
    Each agent gets the same task description and full context. For the
    sequential Architect→Build→Verify pipeline, see the Trio Protocol spec.
    """
    agents = [a for a in discover_agents() if a["functional"]]
    if not agents:
        print("No functional agents found. Run `synlynk init` to set up your Hybrid Workgroup.")
        return
    if len(agents) < 3:
        print(f"  {_YELLOW}Only {len(agents)} agent(s) available "
              f"(trio needs 3). Dispatching what's configured.{_RESET}")

    print(f"{_BOLD}✨ Dispatching {len(agents)} agents in parallel{_RESET}")
    print(f"  Task: {task}\n")

    jobs = []
    for ag in agents:
        job = dispatch_agent(ag["name"], task, story_id=story_id)
        jobs.append(job)
        role = ag["roles"][0] if ag["roles"] else "worker"
        print(f"  {_GREEN}▶{_RESET} [{job['id']}] {ag['name']:10} → {role}  PID {job['pid']}")

    print(f"\n  {_DIM}All agents running in background.{_RESET}")
    print(f"  Monitor with: {_CYAN}synlynk jobs{_RESET}")
    print(f"  View output:  {_CYAN}synlynk logs <job-id>{_RESET}")


def parse_costs_md() -> tuple:
    """Returns (total_usd, total_requests) by parsing costs.md column 6."""
    costs_file = os.path.join(_docs_dir(), "costs.md")
    total_usd = 0.0
    total_requests = 0
    if not os.path.exists(costs_file):
        return total_usd, total_requests
    with open(costs_file) as f:
        for line in f:
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8:
                continue
            cost_str = parts[5].lstrip("$")
            try:
                total_usd += float(cost_str)
                total_requests += 1
            except ValueError:
                continue
    return total_usd, total_requests

def set_state(state: str) -> None:
    """Writes synlynk state to .synlynk/state and updates terminal title."""
    icons = {"watching": "●", "active": "⚡", "stopped": "○"}
    state_file = ".synlynk/state"
    if not os.path.exists(".synlynk"):
        return
    with open(state_file, "w") as f:
        f.write(state)
    if sys.stdout.isatty():
        project = os.path.basename(os.getcwd())
        title = f"{icons.get(state, '○')} synlynk: {state}  ·  {project}"
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()

def detect_remote_owner_repo() -> tuple:
    """Returns (owner, repo) from git remote origin URL, or (None, None)."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None, None
        url = result.stdout.strip().rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if "github.com/" in url:
            path = url.split("github.com/")[-1]
        elif "github.com:" in url:
            path = url.split("github.com:")[-1]
        else:
            return None, None
        parts = path.split("/")
        return (parts[0], parts[1]) if len(parts) >= 2 else (None, None)
    except Exception:
        return None, None


def _update_config(updates: dict) -> None:
    """Merges updates into .synlynk/config.json in-place."""
    config_file = ".synlynk/config.json"
    if not os.path.exists(".synlynk"):
        return
    config = load_config()
    config.update(updates)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


# Task 3-5: Repo scanning, maturity detection, section signals, semantic matching, GH ID extraction
_PROJECT_DOC_NAMES = {"roadmap.md", "todo.md", "memory.md", "costs.md", "devlog.md"}
_AGENT_FILE_NAMES = {"CLAUDE.md", "GEMINI.md", "AGENTS.md", "AI_INSTRUCTIONS.md"}
_SCAN_SKIP_DIRS = {
    ".git", "node_modules", ".synlynk", "project-docs",
    "__pycache__", ".venv", "venv", "env", ".next", "dist", "build",
    "vendor", ".worktrees", "coverage", ".nyc_output", "target", "out", "tmp",
}

_SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".sh": "shell",
}

_SOURCE_ENTRY_POINTS = {
    "main.py", "app.py", "server.py", "index.js", "index.ts", "main.go",
    "lib.rs", "main.rs", "app.rb", "manage.py", "wsgi.py", "asgi.py", "__init__.py",
}

_SYMBOL_PATTERNS = {
    "python": [
        (re.compile(r"^async def (\w+)"), "async_function"),
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^([A-Z_]{2,})\s*="), "constant"),
    ],
    "javascript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "typescript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export interface (\w+)"), "interface"),
        (re.compile(r"^export type (\w+)"), "type"),
        (re.compile(r"^export enum (\w+)"), "enum"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "go": [
        (re.compile(r"^func (?:\(\w+ \*?\w+\) )?(\w+)"), "function"),
        (re.compile(r"^type (\w+) struct"), "struct"),
        (re.compile(r"^type (\w+) interface"), "interface"),
    ],
    "rust": [
        (re.compile(r"^pub fn (\w+)"), "function"),
        (re.compile(r"^pub struct (\w+)"), "struct"),
        (re.compile(r"^pub trait (\w+)"), "trait"),
        (re.compile(r"^pub enum (\w+)"), "enum"),
        (re.compile(r"^pub type (\w+)"), "type"),
    ],
    "ruby": [
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^module (\w+)"), "module"),
    ],
    "java": [
        (re.compile(r"(?:public|protected) (?:class|interface|enum) (\w+)"), "class"),
        (re.compile(r"(?:public|protected) \w+ (\w+)\s*\("), "function"),
    ],
    "kotlin": [
        (re.compile(r"^fun (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^object (\w+)"), "class"),
        (re.compile(r"^interface (\w+)"), "interface"),
    ],
    "shell": [
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^(\w+)\(\)"), "function"),
    ],
}

SECTION_SIGNALS: dict = {
    "## Live Issues SOP": [
        "live issue", "live-issue", "sev1", "sev2", "sev3", "rca", "[live-",
    ],
    "## Mid-Session Anti-Amnesia Protocol": [
        "25,000 tokens", "25k tokens", "compaction", "compaction imminent",
        "mid-session", "checkpoint every",
    ],
    "## Mandatory 4-Doc Discipline": [
        "roadmap.md", "devlog", "costs.md", "memory.md",
        "mandatory document", "four doc", "4-doc",
    ],
    "## GitHub Projects v2 Integration": [
        "updateProjectV2", "projectId", "PVT_", "PVTSSF_",
        "github projects", "programme board",
    ],
    "## Git Worktree-First Policy": [
        "git worktree", "worktree add", "never commit to main",
        "never commit to master",
    ],
}


def _extract_symbols(file_path: str) -> list:
    """Returns [{"symbol": str, "symbol_type": str, "line": int}] from file_path.

    Reads at most 300 lines. Returns [] for unknown extensions or unreadable files.
    """
    ext = os.path.splitext(file_path)[1].lower()
    lang = _SOURCE_EXTENSIONS.get(ext)
    if not lang:
        return []
    patterns = _SYMBOL_PATTERNS.get(lang, [])
    if not patterns:
        return []
    results = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, 1):
                if lineno > 300:
                    break
                for pattern, sym_type in patterns:
                    m = pattern.match(line)
                    if m:
                        results.append({
                            "symbol": m.group(1),
                            "symbol_type": sym_type,
                            "line": lineno,
                        })
                        break
    except (OSError, IOError):
        pass
    return results


def _git_head_sha() -> Optional[str]:
    """Returns the full SHA of HEAD, or None if not in a git repo or no commits."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha if len(sha) == 40 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _load_scan_meta() -> Optional[dict]:
    """Reads .synlynk/scan-meta.json. Returns None if absent or malformed."""
    path = os.path.join(".synlynk", "scan-meta.json")
    if not os.path.exists(path):
        return None
    try:
        return json.loads(open(path).read())
    except (ValueError, OSError):
        return None


def _save_scan_meta(head_sha: str, skeleton: list, deep: Optional[dict] = None) -> None:
    """Writes skeleton + metadata to .synlynk/scan-meta.json."""
    os.makedirs(".synlynk", exist_ok=True)
    existing = _load_scan_meta()
    meta = {
        "schema_version": 1,
        "head_sha": head_sha,
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_count": len(skeleton),
        "skeleton": skeleton,
    }
    if deep is not None:
        meta["deep"] = deep
    elif existing and existing.get("deep"):
        meta["deep"] = existing["deep"]
    with open(os.path.join(".synlynk", "scan-meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)


def _score_source_files(root: str = ".") -> list:
    """Returns [(score, rel_path), ...] for all source files, sorted score descending.

    Scoring: +3 if filename is a known entry point, +1 per appearance in last-50
    git commits, -1 per directory level beyond 2.
    """
    # Collect git activity: count file appearances in last 50 commits
    git_counts: dict = {}
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "-50"],
            capture_output=True, text=True, cwd=root, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    git_counts[line] = git_counts.get(line, 0) + 1
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    scored = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SOURCE_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            # Depth = number of directory separators
            depth = rel_path.count(os.sep)
            # Entry point bonus: filename match OR cmd/main.go path
            entry_bonus = 3 if (fname in _SOURCE_ENTRY_POINTS or rel_path in ("cmd/main.go",)) else 0
            git_score = git_counts.get(rel_path, 0)
            depth_penalty = max(0, depth - 2)
            score = entry_bonus + git_score - depth_penalty
            scored.append((score, rel_path))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored


def _scan_source_skeleton(root: str = ".") -> list:
    """Top-15 prioritised files with up to 8 symbols each.

    Returns list of {"file": str, "language": str, "symbols": [str]} where
    symbols are display strings ("name()" for functions, "name" for others).
    """
    scored = _score_source_files(root)
    top = scored[:15]
    skeleton = []
    for _score, rel_path in top:
        ext = os.path.splitext(rel_path)[1].lower()
        lang = _SOURCE_EXTENSIONS.get(ext, "generic")
        abs_path = os.path.join(root, rel_path)
        raw_syms = _extract_symbols(abs_path)[:8]
        display_syms = []
        for s in raw_syms:
            name = s["symbol"]
            if s["symbol_type"] in ("function", "async_function"):
                display_syms.append(f"{name}()")
            else:
                display_syms.append(name)
        skeleton.append({"file": rel_path, "language": lang, "symbols": display_syms})
    return skeleton


def _scan_full_repo(root: str = ".") -> tuple:
    """Deep scan: extracts all symbols, writes DB + project-docs/source-map.md.

    Returns (skeleton, total_files, total_symbols).
    Clears rows for any head_sha != current HEAD before inserting.
    """
    head_sha = _git_head_sha() or "unknown"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    all_entries = []  # list of {"file": str, "language": str, "symbols": [raw_dict]}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SOURCE_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            lang = _SOURCE_EXTENSIONS[ext]
            raw_syms = _extract_symbols(abs_path)
            all_entries.append({"file": rel_path, "language": lang, "symbols": raw_syms})

    total_files = len(all_entries)
    total_syms = sum(len(e["symbols"]) for e in all_entries)

    # Write DB
    try:
        conn = _get_db()
        conn.execute("DELETE FROM source_symbols WHERE head_sha != ?", (head_sha,))
        rows = []
        for entry in all_entries:
            for sym in entry["symbols"]:
                rows.append((
                    head_sha, entry["file"], entry["language"],
                    sym["symbol"], sym["symbol_type"], sym.get("line"), now,
                ))
        conn.executemany(
            "INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, line, scanned_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception as e:
        print(f"  ⚠ source_symbols DB write failed: {e}")

    # Write project-docs/source-map.md
    source_map_path = os.path.join(_docs_dir(), "source-map.md")
    try:
        os.makedirs("project-docs", exist_ok=True)
        sha_short = head_sha[:7] if head_sha != "unknown" else "unknown"
        lines = [
            "# Source Map",
            f"_Generated: {now} · HEAD: {sha_short} · {total_files} files_",
            "",
        ]
        # Group by directory
        groups: dict = {}
        for entry in sorted(all_entries, key=lambda e: e["file"]):
            dirname = os.path.dirname(entry["file"])
            groups.setdefault(dirname, []).append(entry)

        for dirname, entries in sorted(groups.items()):
            lang_counts: dict = {}
            for e in entries:
                lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
            lang_str = ", ".join(
                f"{lg} · {cnt}" for lg, cnt in sorted(lang_counts.items())
            )
            label = dirname if dirname else "[root]"
            lines.append(f"## {label}/  [{lang_str}]")
            for entry in entries:
                sym_count = len(entry["symbols"])
                lines.append(f"`{entry['file']}` · {sym_count} symbols")
                display_parts = []
                for s in entry["symbols"]:
                    name = s["symbol"]
                    disp = f"{name}()" if s["symbol_type"] in ("function", "async_function") else name
                    disp += f" [{s['symbol_type']}:{s.get('line', '?')}]"
                    display_parts.append(disp)
                if display_parts:
                    lines.append("  " + ", ".join(display_parts))
                lines.append("")

        with open(source_map_path, "w") as fh:
            fh.write("\n".join(lines))
    except OSError as e:
        print(f"  ⚠ source-map.md write failed: {e}")

    # Build and persist skeleton
    skeleton = _scan_source_skeleton(root)
    deep_meta = {"total_files": total_files, "total_symbols": total_syms, "scanned_at": now}
    _save_scan_meta(head_sha, skeleton, deep=deep_meta)

    return skeleton, total_files, total_syms


def _check_scan_cache(root: str = ".") -> list:
    """Returns skeleton from cache if HEAD unchanged, else re-scans.

    Returns [] if not in a git repo (no commits). On re-scan, writes updated
    scan-meta.json but does NOT write source-map.md or the DB — that's --deep only.
    """
    current_sha = _git_head_sha()
    if current_sha is None:
        return []
    meta = _load_scan_meta()
    if meta and meta.get("head_sha") == current_sha:
        return meta.get("skeleton", [])
    skeleton = _scan_source_skeleton(root)
    _save_scan_meta(current_sha, skeleton)
    return skeleton


def _format_source_architecture(skeleton: list, head_sha: str, cache_hit: bool,
                                 total_files: int = 0) -> str:
    """Formats the ## Source Architecture block for context.md."""
    if not skeleton:
        return ""
    status = "cache hit" if cache_hit else "refreshed"
    sha_short = head_sha[:7] if head_sha and head_sha != "unknown" else "unknown"
    lines = [
        "## Source Architecture",
        f"_Scanned: {time.strftime('%Y-%m-%dT%H:%M')} · HEAD: {sha_short}"
        f" · {len(skeleton)} files · {status}_",
        "",
    ]
    # Group by directory
    groups: dict = {}
    for entry in skeleton:
        dirname = os.path.dirname(entry["file"])
        groups.setdefault(dirname, []).append(entry)

    for dirname in sorted(groups):
        entries = groups[dirname]
        lang_counts: dict = {}
        for e in entries:
            lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
        lang_str = ", ".join(
            f"{lg} · {cnt} {'file' if cnt == 1 else 'files'}"
            for lg, cnt in sorted(lang_counts.items())
        )
        label = dirname if dirname else "[root]"
        lines.append(f"### {label}/  [{lang_str}]")
        for entry in entries:
            syms = entry.get("symbols") or []
            if syms:
                lines.append(f"`{entry['file']}` — {', '.join(syms)}")
            else:
                lines.append(f"`{entry['file']}`")
        lines.append("")

    if total_files > len(skeleton):
        overflow = total_files - len(skeleton)
        noun = "file" if overflow == 1 else "files"
        lines.append(
            f"> {overflow} more {noun} in source-map.md"
            " — run `synlynk scan --deep` to refresh"
        )
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _scan_repo_for_docs(root: str = ".") -> dict:
    """Scans repo tree for project docs and agent files outside expected locations.

    Returns {"docs": [absolute_paths], "agent_files": {name: absolute_path}}.
    """
    docs = []
    agent_files = {}
    abs_root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(abs_root):
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, abs_root)
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if fname.lower() in _PROJECT_DOC_NAMES:
                docs.append(fpath)
            if rel_dir == "." and fname in _AGENT_FILE_NAMES:
                agent_files[fname] = fpath
    return {"docs": docs, "agent_files": agent_files}


def _is_evolved_repo(content: str) -> bool:
    """Returns True if file content indicates evolved (non-template) agent instructions."""
    if len(content.splitlines()) > 100:
        return True
    unknown = sum(
        1 for line in content.splitlines()
        if line.startswith("## ") and line.rstrip() not in SECTION_SIGNALS
    )
    return unknown >= 3


def _is_section_covered(content: str, section_header: str) -> bool:
    """Returns True if file content semantically covers a synlynk section (2+ signals)."""
    signals = SECTION_SIGNALS.get(section_header, [])
    content_lower = content.lower()
    matches = sum(1 for sig in signals if sig.lower() in content_lower)
    return matches >= 2


def _extract_gh_ids(content: str) -> dict:
    """Extracts GH Projects v2 node IDs from file content.

    Returns {"project_id": str | None}.
    """
    result = {"project_id": None}
    match = re.search(r'(PVT_[A-Za-z0-9_]+)', content)
    if match:
        result["project_id"] = match.group(1)
    return result


def _build_templates(org: str = None, repo: str = None, project_id: str = None,
                     owner: str = None, agent_slots: dict = None) -> dict:
    """Returns TEMPLATES dict with parameterized values filled in."""
    _pid = project_id or "TODO: PROJECT_ID"
    _agent_slots = agent_slots or {"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"}

    _session_protocol = """\
## Session Start (every session, no exceptions)
1. Run: `git config user.name` — this is your @username for all attribution
2. Run: `synlynk watch status` — if stopped, run `synlynk watch start`
3. Read: `.synlynk/context.md` — your full project state snapshot
4. Check `.synlynk/sentinel.md` for any active alerts
5. Greet with 3 rows:
   - Row 1: Last task YOU completed [by @username] — from your devlog entry
   - Row 2: Your next active task — from project-docs/todo.md
   - Row 3 (team mode only): Last 1 entry per teammate from project-docs/devlogs/

## During the session
- Update task status in project-docs/todo.md — do NOT delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to project-docs/memory.md with [@username] attribution
- Run `synlynk checkpoint` at every task boundary
- In team mode: always `git pull` before editing any project-docs file
- Log costs in project-docs/costs.md after each significant AI operation

## At session end
- Append a summary entry to project-docs/devlogs/<username>.md
- Run `synlynk checkpoint` one final time
- Run `synlynk status` and include the output in your closing message
"""

    _worktree_policy = """\
## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a dedicated worktree for every feature or fix:
```
git worktree add ../feat+<name> feat/<agent-prefix>/<name>
git branch --show-current   # confirm before every commit
```
Delete the worktree only after its branch is merged.
"""

    _live_issues_sop = """\
## Live Issues SOP
Production defects use `[LIVE-N]` issues. N increments per project per incident.

| Severity | Trigger | RCA |
|:---|:---|:---|
| Sev1 | Core broken / data loss / correctness bug | `docs/rca/YYYY-MM-DD-LIVE-N-<slug>.md` |
| Sev2 | Major feature degraded, workaround exists | Comment-level RCA on ticket |
| Sev3 | Minor UX / edge case | None required |

Process: Declare → Investigate (no fixes before root cause confirmed) → Post findings as issue comment → Sev1: write RCA doc → Action tickets (`live-issue sev<N> priority:p0`) → Resolution comment → Close.
"""

    _anti_amnesia = """\
## Mid-Session Anti-Amnesia Protocol
**Phase 1 (context ≤ 75%):** Every ~25,000 tokens — write devlog entry + memory update.
Commit: `docs: mid-session checkpoint [N] — <topic>`

**Phase 2 (context > 75%):** Every ~5,000 tokens — same + add `⚠️ Compaction imminent:` rescue bullet listing open threads and "about to do X" states.

Any numbered list of fixes, options, or recommendations: write to devlog in the same response — never wait.
"""

    _four_doc = """\
## Mandatory 4-Doc Discipline
Update all four during the session, not only at session end:
- `project-docs/roadmap.md` — status on in-progress items
- `project-docs/devlogs/<username>.md` — append at each task boundary
- `project-docs/costs.md` — log each significant AI operation
- `project-docs/memory.md` — decisions with `[@username]` attribution
"""

    _ghp_block = (
        "## GitHub Projects v2 Integration\n"
        "Move board items via GraphQL. Replace TODO values with your project's IDs.\n\n"
        "```graphql\n"
        "mutation MoveItem {\n"
        "  updateProjectV2ItemFieldValue(input: {\n"
        f'    projectId: "{_pid}"\n'
        '    itemId: "<item-node-id>"\n'
        '    fieldId: "TODO: STATUS_FIELD_ID"\n'
        '    value: { singleSelectOptionId: "TODO: IN_PROGRESS_OPTION_ID" }\n'
        "  }) { projectV2Item { id } }\n"
        "}\n"
        "```\n\n"
        "Look up field/option IDs:\n"
        "```bash\n"
        f"gh api graphql -f query='{{ node(id: \"{_pid}\") {{ ... on ProjectV2 {{"
        " fields(first: 20) { nodes { ... on ProjectV2SingleSelectField"
        " { id name options { id name } } } } } } } }'\n"
        "```\n"
    )

    _synlynk_start = """\
## synlynk Start
```bash
synlynk start <issue-id>    # claims board item, injects context, launches agent session
```
"""

    _claude_md = (
        "# synlynk Claude Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** claude-sonnet-4-6\n"
        "- **Commit trailer:** `Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`\n"
        "- **Branch prefix:** `feat/claude/` or `fix/claude/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/claude/<description>` — new functionality\n"
        "- `fix/claude/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol
    )

    _gemini_md = (
        "# synlynk AGY (AntiGravity) Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** agy-2.x\n"
        "- **Commit trailer:** `Co-Authored-By: AGY <noreply@antigravity.dev>`\n"
        "- **Branch prefix:** `feat/agy/` or `fix/agy/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/agy/<description>` — new functionality\n"
        "- `fix/agy/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol
    )

    _agents_md = (
        "# synlynk Codex Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** openai-codex\n"
        "- **Commit trailer:** `Co-Authored-By: Codex <noreply@openai.com>`\n"
        "- **Branch prefix:** `feat/codex/` or `fix/codex/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/codex/<description>` — new functionality\n"
        "- `fix/codex/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol
    )

    _grok_md = (
        "# synlynk Grok Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** grok-composer-2.5-fast\n"
        "- **Commit trailer:** `Co-Authored-By: Grok <noreply@x.ai>`\n"
        "- **Branch prefix:** `feat/grok/` or `fix/grok/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/grok/<description>` — new functionality\n"
        "- `fix/grok/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol
    )

    _ai_instructions_md = (
        "# synlynk Universal AI Instructions\n\n"
        "Apply the following as your system prompt or custom instructions "
        "before starting any session in this repository.\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol
    )

    return {
        "roadmap.md": (
            "# synlynk Roadmap\n\n"
            "| Priority | Feature | Description | Status | Target Release | Owner |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| P0 | Project Setup | Initialize synlynk and project-docs. | In Progress | v0.1.0 | [Unassigned] |\n"
        ),
        "todo.md": (
            "# Project Todo List\n## Active Tasks\n"
            "- [ ] Initialize repository with synlynk <!-- id: 0 -->\n"
        ),
        "memory.md": (
            "# synlynk Memory\n\n## Decisions\n"
            "- **Structure:** Uses `/project-docs` for core records.\n\n"
            "## Conventions\n- **Session Protocol:** Use synlynk project-docs for context.\n"
        ),
        "costs.md": (
            "# synlynk Costs\n\n"
            "| Date | Type | Task/Command | Tokens (I/O) | Requests | Cost (USD) | Notes |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        ),
        "CLAUDE.md": _claude_md,
        "GEMINI.md": _gemini_md,
        "AGENTS.md": _agents_md,
        "GROK.md": _grok_md,
        "AI_INSTRUCTIONS.md": _ai_instructions_md,
        "config.json": json.dumps({
            "schema_version": 1,
            "budget": {"limit_usd": 10.0, "limit_requests": 100},
            "watch_interval_seconds": 30,
            "org": org,
            "owner": owner,
            "repo": repo,
            "project_id": project_id,
            "agent_slots": _agent_slots,
            "team": None,
            "sync_endpoint": None,
            "exec_timeout_minutes": 30,
            "stall_timeout_minutes": 30,
            "agents": {},
        }, indent=2),
    }

def _build_cursor_mdc() -> str:
    """Returns content for .cursor/rules/synlynk.mdc (Cursor MDC format, no markers)."""
    return """\
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
- Update task status in `project-docs/todo.md` — do not delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a worktree for every feature or fix:
```
git worktree add .worktrees/<name> feat/<name>
git branch --show-current   # confirm before every commit
```

## At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
"""


def _build_copilot_instructions() -> str:
    """Returns content for .github/copilot-instructions.md synlynk block (plain markdown)."""
    return """\
## synlynk Session Protocol

### Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

### During Session
- Update task status in `project-docs/todo.md` — do not delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary
- Never commit directly to `main`/`master` — create a worktree or branch first

### At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
"""


def _build_windsurf_rules() -> str:
    """Returns content for .windsurfrules synlynk block (terse directive format)."""
    return """\
Read .synlynk/context.md at session start.
Update task status in project-docs/todo.md ([ ] active [x] done [-] deferred [~] superseded [>] absorbed).
Run `synlynk checkpoint` at task boundaries.
Never commit directly to main or master — use a worktree.
Append decisions to project-docs/memory.md with [@username].
Check .synlynk/sentinel.md for active alerts before starting work.
"""

_INSTRUCTIONS_MANIFEST = ".synlynk/instructions.json"

_INSTRUCTION_TARGETS = [
    # (path, tool, marker_style, detection_fn)
    # detection_fn: called in init() to decide whether to write the file.
    ("CLAUDE.md",                          "claude",    "html", lambda: True),
    ("GEMINI.md",                          "agy",       "html", lambda: True),
    ("AGENTS.md",                          "codex",     "html", lambda: True),
    ("GROK.md",                            "grok",      "html", lambda: True),
    (".cursor/rules/synlynk.mdc",          "cursor",    "none", lambda: os.path.isdir(".cursor")),
    (".github/copilot-instructions.md",    "copilot",   "html", lambda: os.path.isdir(".github")),
    (".windsurfrules",                     "windsurf",  "hash", lambda: True),
    ("AI_INSTRUCTIONS.md",                 "universal", "html", lambda: True),
]


def _load_instruction_manifest() -> dict:
    """Returns files dict from .synlynk/instructions.json, or {} if absent."""
    if not os.path.exists(_INSTRUCTIONS_MANIFEST):
        return {}
    try:
        return json.load(open(_INSTRUCTIONS_MANIFEST)).get("files", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def _write_instruction_manifest(entries: dict) -> None:
    """Write .synlynk/instructions.json with schema_version, synlynk_version, and file SHAs."""
    os.makedirs(os.path.dirname(_INSTRUCTIONS_MANIFEST), exist_ok=True)
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    existing = _load_instruction_manifest()
    existing.update({
        path: {
            "tool": info["tool"],
            "sha": info["sha"],
            "last_checked": ts,
        }
        for path, info in entries.items()
    })
    manifest = {
        "schema_version": 1,
        "generated_at": ts,
        "synlynk_version": VERSION,
        "files": existing,
    }
    with open(_INSTRUCTIONS_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

_MARKER_STYLE_FOR_TOOL = {
    "claude":    "html",
    "agy":       "html",
    "codex":     "html",
    "grok":      "html",
    "cursor":    "none",
    "copilot":   "html",
    "windsurf":  "hash",
    "universal": "html",
}


def _check_instruction_drift() -> list:
    """Check tracked instruction files for external modifications to the synlynk section.

    Fires INSTRUCTION_DRIFT sentinel entries for any drifted file.
    Updates manifest SHA after each check (deduplicates re-firing).
    Returns list of drifted file paths.
    """
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        return []

    drifted = []
    updated_entries = {}
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')

    for fpath, info in manifest_data.items():
        tool = info.get("tool", "unknown")
        recorded_sha = info.get("sha", "")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if not os.path.exists(fpath):
            updated_entries[fpath] = {**info, "last_checked": ts}
            continue

        file_content = open(fpath).read()
        section = _extract_synlynk_section(file_content, marker_style)
        if section is None:
            updated_entries[fpath] = {**info, "last_checked": ts}
            continue

        current_sha = _compute_section_sha(section)
        updated_entries[fpath] = {**info, "sha": current_sha, "last_checked": ts}

        if current_sha != recorded_sha:
            drifted.append(fpath)
            _write_sentinel_alert(
                "WARN", "INSTRUCTION_DRIFT",
                f"{fpath} (tool: {tool}) — synlynk section modified externally. "
                f"Run `synlynk instructions diff {fpath}` to review. "
                f"Run `synlynk instructions update {fpath}` to reset. "
                f"[ack: synlynk instructions ack {fpath}]"
            )

    _write_instruction_manifest(updated_entries)
    return drifted


def cmd_instructions_status() -> None:
    """Print status table for all tracked instruction files."""
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        print("  No instruction manifest found. Run `synlynk init` first.")
        return

    col = {"file": 38, "tool": 10, "status": 16, "checked": 12}
    header = (f"{'File':<{col['file']}}{'Tool':<{col['tool']}}"
              f"{'Status':<{col['status']}}{'Last checked':<{col['checked']}}")
    print(f"\n{_BOLD}{header}{_RESET}")
    print("─" * (col["file"] + col["tool"] + col["status"] + col["checked"]))

    for fpath, info in sorted(manifest_data.items()):
        tool = info.get("tool", "?")
        recorded_sha = info.get("sha", "")
        checked = info.get("last_checked", "")[:10]
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if not os.path.exists(fpath):
            status = f"{_YELLOW}✗ missing{_RESET}"
        else:
            file_content = open(fpath).read()
            section = _extract_synlynk_section(file_content, marker_style)
            if section is None:
                status = f"{_YELLOW}? no markers{_RESET}"
            elif _compute_section_sha(section) != recorded_sha:
                status = f"{_YELLOW}⚠ drifted{_RESET}"
            else:
                has_user = bool(re.sub(
                    r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$.*?^[ \t]*<!-- synlynk:end -->[ \t]*$',
                    '', file_content, flags=re.DOTALL | re.MULTILINE
                ).strip() if marker_style == "html" else re.sub(
                    r'^[ \t]*# synlynk:start[^\n]*$.*?^[ \t]*# synlynk:end[ \t]*$',
                    '', file_content, flags=re.DOTALL | re.MULTILINE
                ).strip())
                status = (f"{_DIM}+ user-content{_RESET}" if has_user
                          else f"{_GREEN}✓ clean{_RESET}")

        print(f"{fpath:<{col['file']}}{tool:<{col['tool']}}"
              f"{status:<{col['status'] + 10}}{checked}")
    print()


def cmd_instructions_diff(file_path: Optional[str] = None) -> None:
    """Show user/tool content outside the synlynk section for deliberate review."""
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        print("  No instruction manifest found. Run `synlynk init` first.")
        return

    targets = ([file_path] if file_path else list(manifest_data.keys()))
    for fpath in targets:
        if fpath not in manifest_data:
            print(f"  {fpath}: not tracked in manifest")
            continue
        if not os.path.exists(fpath):
            print(f"  {fpath}: {_YELLOW}missing{_RESET}")
            continue
        info = manifest_data[fpath]
        tool = info.get("tool", "unknown")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")
        file_content = open(fpath).read()

        print(f"\n{_BOLD}── {fpath} (tool: {tool}) ──{_RESET}")

        if marker_style == "html":
            user_content = re.sub(
                r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$.*?^[ \t]*<!-- synlynk:end -->[ \t]*$',
                '', file_content, flags=re.DOTALL | re.MULTILINE
            ).strip()
        elif marker_style == "hash":
            user_content = re.sub(
                r'^[ \t]*# synlynk:start[^\n]*$.*?^[ \t]*# synlynk:end[ \t]*$',
                '', file_content, flags=re.DOTALL | re.MULTILINE
            ).strip()
        else:
            user_content = ""

        if user_content:
            print(f"{_DIM}User/tool content outside synlynk section:{_RESET}")
            print(user_content)
        else:
            print(f"{_DIM}No user content outside synlynk section.{_RESET}")


def cmd_instructions_update(file_path: Optional[str] = None,
                             new_content: Optional[str] = None) -> None:
    """Re-generate the synlynk section for file(s) and refresh manifest SHAs.

    file_path=None updates all tracked files.
    new_content is used in tests; production callers pass None and content
    is rebuilt from the relevant template function.
    """
    manifest_data = _load_instruction_manifest()
    targets = ([file_path] if file_path else list(manifest_data.keys()))

    _tool_content_builders = {
        "cursor":    (_build_cursor_mdc,            "none"),
        "copilot":   (_build_copilot_instructions,  "html"),
        "windsurf":  (_build_windsurf_rules,        "hash"),
        "universal": (lambda: _build_templates().get("AI_INSTRUCTIONS.md", ""), "html"),
    }

    updated = {}
    for fpath in targets:
        if fpath not in manifest_data:
            print(f"  {fpath}: not tracked — skipping")
            continue
        info = manifest_data[fpath]
        tool = info.get("tool", "unknown")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if new_content is not None:
            content = new_content
        elif tool in _tool_content_builders:
            builder, _ = _tool_content_builders[tool]
            content = builder()
        else:
            templates = _build_templates()
            fname = os.path.basename(fpath)
            content = templates.get(fname, "")

        _write_instruction_file(fpath, tool, content, marker_style)

        if os.path.exists(fpath):
            section = _extract_synlynk_section(open(fpath).read(), marker_style)
            if section:
                updated[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}

        print(f"  {_GREEN}✓{_RESET} Updated {fpath}")

    if updated:
        _write_instruction_manifest(updated)


def cmd_instructions_ack(file_path: str) -> None:
    """Acknowledge an INSTRUCTION_DRIFT event for a specific file.

    Removes matching INSTRUCTION_DRIFT lines from sentinel.md.
    """
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        return
    with open(sentinel_file) as f:
        lines = f.readlines()
    filtered = [
        l for l in lines
        if not ("INSTRUCTION_DRIFT" in l and file_path in l)
    ]
    with open(sentinel_file, "w") as f:
        f.writelines(filtered)
    print(f"  {_GREEN}✓{_RESET} Acknowledged drift for {file_path}")


def log_telemetry_event(event: dict) -> None:
    """Appends a structured event to .synlynk/telemetry.json (capped at 100)."""
    telemetry_file = ".synlynk/telemetry.json"
    if not os.path.exists(".synlynk"):
        return
    data = []
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    data.append(event)
    data = data[-100:]
    with open(telemetry_file, "w") as f:
        json.dump(data, f, indent=2)


def _check_costs_freshness() -> None:
    """Warns if costs.md hasn't been updated in the current session (>1 hour)."""
    costs_file = os.path.join(_docs_dir(), "costs.md")
    if not os.path.exists(costs_file):
        return
    if time.time() - os.path.getmtime(costs_file) > 3600:
        print("  ⚠ costs.md not updated this session — AI may have missed logging")

def _write_sentinel_alert(severity: str, code: str, message: str, sentinel_path: Optional[str] = None) -> None:
    """Appends a structured alert line to .synlynk/sentinel.md."""
    sentinel_file = sentinel_path or ".synlynk/sentinel.md"
    if not sentinel_path and not os.path.exists(".synlynk"):
        return
    existing = ""
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            existing = f.read()
    if "# Sentinel Alerts" not in existing:
        existing = "# Sentinel Alerts\n"
    ts = time.strftime('%Y-%m-%d %H:%M')
    line = f"- [{severity}] [{ts}] {code}: {message}\n"
    if sentinel_path:
        parent = os.path.dirname(sentinel_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
    with open(sentinel_file, "w") as f:
        f.write(existing + line)


def _read_sentinel_alerts(severity: Optional[str] = None) -> list:
    """Returns alert lines from sentinel.md, optionally filtered by severity."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        return []
    alerts = []
    with open(sentinel_file) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("- ["):
                continue
            if severity is None:
                alerts.append(line)
            else:
                m = re.match(r'^- \[([A-Z]+)\]', line)
                if m and m.group(1) == severity:
                    alerts.append(line)
    return alerts


def extract_tokens(output_text: str) -> tuple:
    """Regex-scrapes token counts from AI CLI stdout. Returns (in_tokens, out_tokens)."""
    patterns = [
        (r'Input tokens:\s*(\d+).*?Output tokens:\s*(\d+)', re.DOTALL | re.IGNORECASE),
        (r'"usage"\s*:\s*\{[^}]*"input_tokens"\s*:\s*(\d+)[^}]*"output_tokens"\s*:\s*(\d+)', re.DOTALL | re.IGNORECASE),
        (r'"input_tokens":\s*(\d+).*?"output_tokens":\s*(\d+)', re.DOTALL | re.IGNORECASE),
        (r'Tokens used:\s*(\d+)\s+input,\s*(\d+)\s+output', re.IGNORECASE),
        (r'prompt_tokens:\s*(\d+).*?completion_tokens:\s*(\d+)', re.DOTALL | re.IGNORECASE),
    ]
    for pat, flags in patterns:
        m = re.search(pat, output_text, flags)
        if m:
            return int(m.group(1)), int(m.group(2))
    m = re.search(r'Total tokens:\s*(\d+)', output_text, re.IGNORECASE)
    if m:
        total = int(m.group(1))
        return int(total * 0.8), int(total * 0.2)
    return 0, 0


def extract_model_version(output_text: str, agent: str = None) -> str:
    """
    Tier 1: Parse model_version from # synlynk-meta block in agent output.
    Tier 2: read model from the agent profile.
    Tier 3 fallback: read default_model from .synlynk/config.json for the agent.
    Returns 'unknown' if neither source provides a value.
    """
    # Tier 1: structured header
    m = re.search(r"#\s*synlynk-meta.*?model_version\s*=\s*(\S+)", output_text,
                  re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Tier 2: agent profile override
    if agent:
        profile = _load_agent_profile(agent)
        model = profile.get("model")
        if model and model != "unknown":
            return model

    # Tier 3: config default
    if agent:
        config = load_config()
        agents_cfg = config.get("agents", {})
        default = agents_cfg.get(agent, {}).get("default_model")
        if default:
            return default

    return "unknown"


def extract_verifier_meta(output_text: str) -> Optional[dict]:
    """Parses the # synlynk-meta block from a verifier agent's output.

    Returns dict with quality, correct, rework_needed, verifier_model — or None if absent.
    """
    m = re.search(r"#\s*synlynk-meta\s*\n((?:[^\n]+\n?)+)", output_text, re.IGNORECASE)
    if not m:
        return None
    block = m.group(1)
    meta = {}
    for line in block.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k == "quality":
                try:
                    meta["quality"] = float(v)
                except ValueError:
                    pass
            elif k == "correct":
                meta["correct"] = v.lower() in ("true", "yes", "1")
            elif k == "rework_needed":
                meta["rework_needed"] = v.lower() in ("true", "yes", "1")
            elif k == "verifier_model":
                meta["verifier_model"] = v
    return meta if "quality" in meta else None


def _extract_auto_signals(log_text: str, started_at: str = None,
                           ended_at: str = None, exit_code: int = None) -> dict:
    """Extracts objective quality signals from a completed job's log text."""
    signals = {
        "test_pass_rate": None,
        "build_success": None,
        "duration_seconds": None,
        "test_count": None,
    }

    # Test pass rate — multiple runner formats
    patterns = [
        r"(\d+)\s+passed.*?(\d+)\s+(?:failed|error)",   # pytest: "47 passed, 3 failed"
        r"Tests:\s+(\d+)\s+passed.*?(\d+)\s+failed",     # jest variant
        r"(\d+)/(\d+)\s+tests?\s+passed",                # generic "47/50 tests passed"
    ]
    for pat in patterns:
        m = re.search(pat, log_text, re.IGNORECASE)
        if m:
            passed = int(m.group(1))
            second = int(m.group(2))
            if "passed" in pat and "failed" in pat:
                total = passed + second
            else:
                total = second
            signals["test_pass_rate"] = passed / total if total else None
            signals["test_count"] = passed
            break

    # All-passed shortcut: "X passed" with no failures mentioned
    if signals["test_pass_rate"] is None:
        m = re.search(r"(\d+)\s+passed", log_text, re.IGNORECASE)
        if m and "failed" not in log_text.lower() and "error" not in log_text.lower():
            signals["test_pass_rate"] = 1.0
            signals["test_count"] = int(m.group(1))

    # Build success from exit code
    if exit_code is not None:
        signals["build_success"] = (exit_code == 0)

    # Duration
    if started_at and ended_at:
        try:
            fmt = "%Y-%m-%dT%H:%M:%S"
            import datetime as _dt
            delta = _dt.datetime.strptime(ended_at, fmt) - _dt.datetime.strptime(started_at, fmt)
            signals["duration_seconds"] = delta.total_seconds()
        except Exception:
            pass

    return signals




def update_costs(command: str, in_tokens: int, out_tokens: int, duration: float) -> None:
    """Appends a cost row. Post-migration: writes to state.db + .synlynk/project-docs/costs.md.
    Pre-migration: writes to project-docs/costs.md. Rates: $0.003/1K in, $0.015/1K out."""
    est_cost = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    user = get_username()
    entry = (f"| {ts} | {user} | 1 | {in_tokens}/{out_tokens} "
             f"| ${est_cost:.4f} | exec: {short_cmd} |\n")

    if _is_migrated():
        conn = _get_db()
        try:
            conn.execute(
                """INSERT INTO cost_entries
                   (session_date, agent, input_tokens, output_tokens, total_cost_usd, notes)
                   VALUES (?,?,?,?,?,?)""",
                (ts, user, in_tokens, out_tokens, est_cost, f"exec: {short_cmd}")
            )
            conn.commit()
        finally:
            conn.close()
        costs_file = os.path.join(_synlynk_project_docs_dir(), "costs.md")
        os.makedirs(os.path.dirname(costs_file), exist_ok=True)
        with open(costs_file, "a") as f:
            f.write(entry)
        _dr_sync("costs.md")
    else:
        _check_upstream_divergence()
        costs_file = os.path.join(_docs_dir(), "costs.md")
        if not os.path.exists(costs_file):
            return
        with open(costs_file, "a") as f:
            f.write(entry)


def _is_interactive(cmd_args: list) -> bool:
    """Returns True if the command needs a real TTY (no stdout capture)."""
    NON_INTERACTIVE = ["--no-tty", "--output-format json", "--print",
                       "--non-interactive", "-p "]
    cmd_str = " ".join(cmd_args)
    return not any(flag in cmd_str for flag in NON_INTERACTIVE)


def _inject_grok_rules(cmd_args: list) -> list:
    """Adds Grok rules flags when invoking grok and the rule files exist."""
    if not cmd_args or cmd_args[0] != "grok":
        return list(cmd_args)

    injected = [cmd_args[0]]
    if os.path.exists("GROK.md"):
        injected.extend(["--rules", "GROK.md"])
    if "-p" in cmd_args and os.path.exists(os.path.join(".synlynk", "context.md")):
        injected.extend(["--rules", os.path.join(".synlynk", "context.md")])
    injected.extend(cmd_args[1:])
    return injected


def _tee_process(process, buffer: list) -> None:
    """Reads process stdout line-by-line, writes to terminal and appends to buffer."""
    for line in iter(process.stdout.readline, b''):
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        buffer.append(line.decode('utf-8', errors='replace'))
    process.stdout.close()


def _check_pre_exec_gate(force: bool = False) -> bool:
    """Checks for active sentinel alerts. Returns False to abort if CRITICAL and not forced."""
    warns = _read_sentinel_alerts(severity="WARN")
    criticals = _read_sentinel_alerts(severity="CRITICAL")
    for w in warns:
        print(f"  ⚠ {w}")
    if criticals:
        for c in criticals:
            print(f"  🚨 {c}")
        if not force:
            print("  Exec blocked by CRITICAL sentinel alert. "
                  "Fix the issue or re-run with --force to bypass.")
            return False
    return True


QUOTA_PATTERNS = [
    "rate limit", "quota exceeded", "resource exhausted",
    "billing", "insufficient_quota", "too many requests",
    "RESOURCE_EXHAUSTED",
]


def _extract_compliance_tags(output_text: str) -> dict:
    """Scans agent output for compliance evidence. Returns a dict of bool flags.

    These tags are informational for v0.9.4 — they build the adherence dataset
    for the Agent Behaviour epic (AB) without blocking job completion.
    """
    lower = output_text.lower()
    import re as _re

    ran_tests_patterns = [
        r"\btests\s+pass",
        r"\bpassed\b",
        r"\bpytest\b",
        r"\btest\s+suite\b",
        r"\brunning\s+tests\b",
    ]
    verify_patterns = [
        r"\bverif",
        r"\blgtm\b",
        r"\breviewed\b",
        r"\bchecked\b",
    ]
    ran_tests = any(_re.search(pat, lower) for pat in ran_tests_patterns)
    verify_before_commit = any(_re.search(pat, lower) for pat in verify_patterns)
    return {
        "ran_tests": ran_tests,
        "verify_before_commit": verify_before_commit,
    }


def check_sentinel_patterns(output_text: str = "", exit_code: int = 0,
                             cmd: str = "") -> None:
    """Detects flatline, success loop, and quota-exhausted; writes sentinel alerts."""
    telemetry_file = ".synlynk/telemetry.json"
    data = []
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    execs = [e for e in data if e.get("type") == "exec"]

    # Pattern 1: Flatline — last 3 execs same command, all non-zero exit
    if len(execs) >= 3:
        last3 = execs[-3:]
        if (all(e.get("exit_code", 0) != 0 for e in last3) and
                all(e.get("command") == last3[0].get("command") for e in last3)):
            fail_cmd = last3[0].get("command", "unknown")
            _write_sentinel_alert(
                "CRITICAL", "FLATLINE",
                f"`{fail_cmd}` failed 3 times in a row — possible hallucination loop."
            )
            print(f"\n  \U0001f6a8 [FLATLINE] `{fail_cmd}` failed 3x — consider manual intervention.")

    # Pattern 2: Success loop — last 5 execs same command, all exit 0, within 10 min
    if len(execs) >= 5:
        last5 = execs[-5:]
        if (all(e.get("exit_code", 1) == 0 for e in last5) and
                all(e.get("command") == last5[0].get("command") for e in last5)):
            ts_first = last5[0].get("_ts", 0)
            ts_last = last5[-1].get("_ts", 0)
            window_min = (ts_last - ts_first) / 60 if ts_first else 999
            if window_min < 10:
                _write_sentinel_alert(
                    "WARN", "SUCCESS_LOOP",
                    f"Same command succeeded 5x in {window_min:.1f} min — "
                    "possible automated loop burning tokens."
                )
                print(f"\n  ⚠ [SUCCESS_LOOP] Same command 5x in {window_min:.1f} min.")

    # Pattern 3: Quota-exhausted — keyword in captured output
    if output_text:
        lower = output_text.lower()
        for phrase in QUOTA_PATTERNS:
            if phrase.lower() in lower:
                cli = cmd.split()[0] if cmd else "agent"
                _write_sentinel_alert(
                    "CRITICAL", "QUOTA_EXHAUSTED",
                    f"`{cli}` — matched \"{phrase}\". "
                    "Check plan limits or switch agent CLI."
                )
                print(f"\n  \U0001f6a8 [QUOTA_EXHAUSTED] Matched \"{phrase}\" in output.")
                break

    # Pattern 4: VERIFY_SKIP — job succeeded but no test/verify evidence in output
    # Informational only (v0.9.4). Builds AB-epic compliance dataset.
    if output_text and exit_code == 0:
        tags = _extract_compliance_tags(output_text)
        if not tags["ran_tests"] and not tags["verify_before_commit"]:
            _write_sentinel_alert(
                "INFO", "VERIFY_SKIP",
                "Job exited 0 but no test or verify evidence found in output. "
                "Review before commit and capture verification signals next time."
            )
            print("  ℹ [VERIFY_SKIP] No test/verify evidence (informational — see sentinel.md)")


def check_daemon_health() -> None:
    """Writes CRITICAL alert if watch daemon pidfile exists but process is dead."""
    daemon = WatchDaemon()
    if daemon._health() == "zombie":
        _write_sentinel_alert(
            "CRITICAL", "ZOMBIE_DAEMON",
            "Watch daemon pidfile exists but process is dead. "
            "Run: synlynk watch stop && synlynk watch start"
        )
        print("  🚨 [ZOMBIE_DAEMON] Watch daemon is dead — "
              "run: synlynk watch stop && synlynk watch start")


def check_stall() -> None:
    """Writes WARN alert if .synlynk/state has been 'active' longer than exec_timeout_minutes."""
    state_file = ".synlynk/state"
    if not os.path.exists(state_file):
        return
    try:
        with open(state_file) as f:
            state = f.read().strip()
        if state != "active":
            return
        age_minutes = (time.time() - os.path.getmtime(state_file)) / 60
        timeout = load_config().get("exec_timeout_minutes", 30)
        if age_minutes > timeout:
            _write_sentinel_alert(
                "WARN", "STALL",
                f"Exec has been running for {age_minutes:.0f} min "
                f"(threshold: {timeout} min). May be stalled."
            )
            print(f"  ⚠ [STALL] Exec has been active for {age_minutes:.0f} min — "
                  f"consider checking or restarting.")
    except (IOError, OSError):
        pass


def sentinel_list() -> None:
    """Prints all active sentinel alerts."""
    alerts = _read_sentinel_alerts()
    if not alerts:
        print("  No active sentinel alerts.")
        return
    print(f"  {len(alerts)} active alert(s):")
    for a in alerts:
        print(f"    {a}")


def sentinel_clear(severity: Optional[str] = None, code: Optional[str] = None) -> None:
    """Removes matching alerts from sentinel.md. No args = clear all structured alerts."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        print("  No sentinel file found.")
        return
    with open(sentinel_file) as f:
        lines = f.readlines()

    kept = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- ["):
            kept.append(line)
            continue
        # Only handle structured format: - [SEVERITY] [TIMESTAMP] CODE: message
        m = re.match(r'^- \[([A-Z]+)\]', stripped)
        if not m:
            kept.append(line)  # old format — keep as-is
            continue
        line_sev = m.group(1)
        if severity and line_sev != severity:
            kept.append(line)
            continue
        if code and code not in stripped:
            kept.append(line)
            continue
        removed += 1

    with open(sentinel_file, "w") as f:
        f.writelines(kept)
    print(f"  Cleared {removed} alert(s).")


def _compute_burn_rate() -> tuple:
    """Returns (avg_usd_per_exec, estimated_execs_remaining) from telemetry.
    Returns (0.0, None) if fewer than 3 costed events."""
    telemetry_file = ".synlynk/telemetry.json"
    if not os.path.exists(telemetry_file):
        return 0.0, None
    try:
        with open(telemetry_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return 0.0, None

    costed = [
        e for e in data
        if e.get("type") == "exec" and e.get("in_tokens", 0) > 0
    ][-10:]

    if len(costed) < 3:
        return 0.0, None

    costs = [
        (e["in_tokens"] / 1000 * 0.003) + (e["out_tokens"] / 1000 * 0.015)
        for e in costed
    ]
    avg = sum(costs) / len(costs)

    total_usd, _ = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    remaining_usd = limit_usd - total_usd
    remaining_execs = int(remaining_usd / avg) if avg > 0 else None

    return avg, remaining_execs


def check_budgets() -> None:
    """Warns if cumulative spend from costs.md approaches config limits."""
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]
    total_usd, _ = parse_costs_md()

    # Request count from telemetry exec events
    total_reqs = 0
    telemetry_file = ".synlynk/telemetry.json"
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
            total_reqs = sum(1 for e in data if e.get("type") == "exec")
        except (json.JSONDecodeError, IOError):
            pass

    if total_usd >= limit_usd:
        print(f"\n🛑 [Budget Alert] CRITICAL: Spent ${total_usd:.2f} / ${limit_usd:.2f}.")
    elif total_usd >= limit_usd * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of cost budget (${total_usd:.2f} / ${limit_usd:.2f}).")

    if total_reqs >= limit_reqs:
        print(f"\n🛑 [Budget Alert] CRITICAL: {total_reqs} / {limit_reqs} request limit.")
    elif total_reqs >= limit_reqs * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of request limit ({total_reqs} / {limit_reqs}).")

def _get_last_devlog_date(filepath: str) -> Optional[str]:
    """Returns the most recent ## YYYY-MM-DD heading from a devlog file."""
    if not os.path.exists(filepath):
        return None
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    last_date = None
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                last_date = m.group(1)
    return last_date


def _write_recent_devlog_entries(out, filepath: str, cutoff: float) -> None:
    """Writes devlog ## sections newer than cutoff timestamp to out."""
    import calendar
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    current_lines = []
    in_section = False
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if in_section and current_lines:
                    out.writelines(current_lines)
                try:
                    ts = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d"))
                    in_section = ts >= cutoff
                except ValueError:
                    in_section = False
                current_lines = [line]
            elif in_section:
                current_lines.append(line)
    if in_section and current_lines:
        out.writelines(current_lines)


def _write_last_devlog_section(out, filepath: str) -> None:
    """Writes only the last ## section from a devlog file."""
    if not os.path.exists(filepath):
        return
    pattern = re.compile(r'^## \d{4}-\d{2}-\d{2}')
    sections = []
    current = []
    with open(filepath) as f:
        for line in f:
            if pattern.match(line) and current:
                sections.append(current)
                current = [line]
            else:
                current.append(line)
    if current:
        sections.append(current)
    if sections:
        out.writelines(sections[-1])


def _generate_todo_md() -> None:
    """Writes todo.md as a generated view of stories.
    Post-migration: writes to .synlynk/project-docs/todo.md.
    Pre-migration: writes to project-docs/todo.md."""
    if _is_migrated():
        todo_path = os.path.join(_synlynk_project_docs_dir(), "todo.md")
        os.makedirs(os.path.dirname(todo_path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        todo_path = os.path.join(docs_dir, "todo.md")

    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, title, engg_domain, status FROM stories ORDER BY created_at ASC"
    ).fetchall()
    conn.close()

    lines = [
        "# Tasks (generated - source of truth is state.db)\n",
        "# Edit via: synlynk story create/update | Do NOT hand-edit this file\n\n",
    ]
    for story_id, title, engg_domain, status in rows:
        if status == "done":
            check = "x"
        elif status == "deferred":
            check = "-"
        else:
            check = " "
        domain = f" [{engg_domain}]" if engg_domain and engg_domain != "unknown" else ""
        lines.append(f"- [{check}] {title or story_id}{domain} <!-- id:{story_id} -->\n")

    with open(todo_path, "w") as f:
        f.writelines(lines)

    if _is_migrated():
        _dr_sync("todo.md")


def _write_memory_md() -> None:
    """Regenerate .synlynk/project-docs/memory.md from memory_entries table."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT section, body FROM memory_entries ORDER BY id"
    ).fetchall()
    conn.close()
    lines = ["# synlynk Memory\n\n"]
    for section, body in rows:
        lines.append(f"## {section}\n\n{body}\n\n")
    path = os.path.join(_synlynk_project_docs_dir(), "memory.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.writelines(lines)


def cmd_memory_add(section: str, body: str, author: str = None) -> None:
    """Add or update a memory entry. Writes through to flat file if migrated."""
    conn = _get_db()
    existing = conn.execute(
        "SELECT id FROM memory_entries WHERE section=?", (section,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE memory_entries SET body=?, author=?, updated_at=datetime('now') WHERE section=?",
            (body, author, section)
        )
    else:
        conn.execute(
            "INSERT INTO memory_entries (section, body, author) VALUES (?,?,?)",
            (section, body, author)
        )
    conn.commit()
    conn.close()
    if _is_migrated():
        _write_memory_md()
        _dr_sync("memory.md")


def _write_devlog_file(author: str) -> None:
    """Regenerate .synlynk/project-docs/devlogs/<author>.md from devlog_entries."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT entry_date, session_title, body FROM devlog_entries "
        "WHERE author=? ORDER BY entry_date ASC",
        (author,)
    ).fetchall()
    conn.close()
    lines = [f"# {author} Devlog\n\n"]
    for entry_date, session_title, body in rows:
        header = f"## {entry_date}"
        if session_title:
            header += f" — {session_title}"
        lines.append(f"{header}\n\n{body}\n\n")
    devlog_dir = os.path.join(_synlynk_project_docs_dir(), "devlogs")
    os.makedirs(devlog_dir, exist_ok=True)
    with open(os.path.join(devlog_dir, f"{author}.md"), "w") as f:
        f.writelines(lines)


def cmd_devlog_append(author: str, entry_date: str, body: str,
                      session_title: str = None) -> None:
    """Append a devlog entry to DB and write through to flat file if migrated."""
    conn = _get_db()
    conn.execute(
        "INSERT INTO devlog_entries (author, entry_date, session_title, body) VALUES (?,?,?,?)",
        (author, entry_date, session_title, body)
    )
    conn.commit()
    conn.close()
    if _is_migrated():
        _write_devlog_file(author)
        _dr_sync(f"devlogs/{author}.md")


def _import_todo_to_stories() -> int:
    """Reads '- [ ]' lines from todo.md and inserts missing story rows."""
    import hashlib as _hashlib

    docs_dir = _docs_dir()
    todo_path = os.path.join(docs_dir, "todo.md")
    if not os.path.exists(todo_path):
        return 0

    conn = _get_db()
    existing_ids = {row[0] for row in conn.execute("SELECT story_id FROM stories")}

    imported = 0
    with open(todo_path) as f:
        for line in f:
            if "- [ ]" not in line:
                continue
            id_match = re.search(r'<!--\s*id:(story-[a-f0-9]+)\s*-->', line)
            if id_match and id_match.group(1) in existing_ids:
                continue

            title_match = re.match(
                r'\s*-\s*\[\s*\]\s*(.+?)(?:\s*\[.*?\])?(?:\s*<!--.*-->)?\s*$',
                line,
            )
            if not title_match:
                continue
            title = title_match.group(1).strip()
            story_id = "story-" + _hashlib.md5(title.encode()).hexdigest()[:8]
            if story_id in existing_ids:
                continue
            if conn.execute("SELECT 1 FROM stories WHERE title=?", (title,)).fetchone():
                continue
            try:
                conn.execute(
                    "INSERT INTO stories (story_id, title, status) VALUES (?, ?, 'open')",
                    (story_id, title),
                )
                imported += 1
                existing_ids.add(story_id)
            except _sqlite3.IntegrityError:
                pass

    conn.commit()
    conn.close()
    return imported


def _generate_task_context(story_id: str, out_path: str = None) -> str:
    """Writes minimal scoped context for a single story dispatch. Returns context string.

    out_path: write to this path instead of the global .synlynk/context.md.
    Used by dispatch_agent to isolate per-job context and avoid concurrent overwrites.
    """
    import io as _io
    buf = _io.StringIO()

    conn = _get_db()
    row = conn.execute(
        "SELECT title, engg_domain, org_domain, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    conn.close()

    buf.write("# synlynk Context Snapshot (task-scoped)\n\n")
    buf.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    if row:
        buf.write("## Story\n")
        buf.write(f"**ID:** {story_id}  \n")
        buf.write(f"**Title:** {row[0] or ''}  \n")
        buf.write(
            f"**Domain:** {row[1] or 'unknown'} · "
            f"{row[2] or 'unknown'} · {row[3] or 'build'}  \n\n---\n\n"
        )

    # Active tasks only (not deferred, not done)
    todo_path = os.path.join("project-docs", "todo.md")
    if os.path.exists(todo_path):
        active = [l for l in open(todo_path) if "- [ ]" in l]
        if active:
            buf.write("## Active Tasks\n")
            buf.writelines(active)
            buf.write("\n---\n\n")

    # Source architecture (relevant files only, up to 20 entries)
    source_skeleton = _check_scan_cache()
    if source_skeleton:
        engg = row[1] if row and row[1] != "unknown" else None
        if engg:
            relevant = [
                f for f in source_skeleton
                if engg in f.get("file", "")
                or engg in " ".join(f.get("symbols", []))
            ]
            if not relevant:
                relevant = source_skeleton
        else:
            relevant = source_skeleton
        meta = _load_scan_meta()
        current_sha = _git_head_sha() or ""
        cache_hit = bool(meta and meta.get("head_sha") == current_sha)
        arch = _format_source_architecture(relevant[:20], current_sha, cache_hit, len(relevant))
        if arch:
            buf.write(arch)

    context_text = buf.getvalue()

    context_file = out_path if out_path else ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)
    with open(context_file, "w") as out:
        out.write(context_text)

    print(f"  ✓ Task-scoped context saved to {context_file}")
    return context_text


def _generate_context_from_db(out_path: str = None) -> str:
    """Build context.md from state.db (post-migration path)."""
    context_file = out_path if out_path else ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)
    username = get_username()
    mode = get_mode()

    conn = _get_db()
    top_story = conn.execute(
        "SELECT title FROM stories WHERE status='open' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    recent_devlogs = conn.execute(
        "SELECT author, entry_date, session_title, body FROM devlog_entries "
        "ORDER BY entry_date DESC, id DESC LIMIT 5"
    ).fetchall()
    memory_sections = conn.execute(
        "SELECT section, body FROM memory_entries ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    conn.close()

    with open(context_file, "w") as out:
        out.write("# synlynk Context Snapshot\n\n")
        out.write(
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"| User: @{username} | Mode: {mode}\n\n"
        )
        if top_story:
            out.write("## Next Task\n")
            out.write(f"- {top_story[0]}\n\n---\n\n")
        if recent_devlogs:
            out.write("## Recent Activity\n")
            for author, entry_date, session_title, body in recent_devlogs:
                title_part = f" — {session_title}" if session_title else ""
                out.write(f"\n### @{author} · {entry_date}{title_part}\n")
                out.write(body[:500])
                if len(body) > 500:
                    out.write("\n...(truncated)")
                out.write("\n")
            out.write("\n---\n\n")
        if memory_sections:
            out.write("## Project Memory\n")
            for section, body in memory_sections:
                out.write(f"\n### {section}\n{body[:300]}\n")

    with open(context_file) as f:
        return f.read()


def _generate_context_from_db(out_path: str = None) -> str:
    """Build context.md from state.db (post-migration path)."""
    context_file = out_path if out_path else ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)
    username = get_username()
    mode = get_mode()
    conn = _get_db()
    top_story = conn.execute(
        "SELECT title FROM stories WHERE status='open' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    recent_devlogs = conn.execute(
        "SELECT author, entry_date, session_title, body FROM devlog_entries "
        "ORDER BY entry_date DESC, id DESC LIMIT 5"
    ).fetchall()
    memory_sections = conn.execute(
        "SELECT section, body FROM memory_entries ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    with open(context_file, "w") as out:
        out.write("# synlynk Context Snapshot\n\n")
        out.write(
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"| User: @{username} | Mode: {mode}\n\n"
        )
        if top_story:
            out.write("## Next Task\n")
            out.write(f"- {top_story[0]}\n\n---\n\n")
        if recent_devlogs:
            out.write("## Recent Activity\n")
            for author, entry_date, session_title, body in recent_devlogs:
                title_part = f" — {session_title}" if session_title else ""
                out.write(f"\n### @{author} · {entry_date}{title_part}\n")
                out.write(body[:500])
                if len(body) > 500:
                    out.write("\n...(truncated)")
                out.write("\n")
            out.write("\n---\n\n")
        if memory_sections:
            out.write("## Project Memory\n")
            for section, body in memory_sections:
                out.write(f"\n### {section}\n{body[:300]}\n")
    with open(context_file) as f:
        return f.read()


def generate_context(scope: str = "full", out_path: str = None) -> str:
    """Aggregates project-docs into .synlynk/context.md (active items only).

    Returns the context string. The file is still written for daemon HTTP
    endpoint and external tooling compatibility.

    out_path: when set, write to this path instead of .synlynk/context.md.
    Passed through to _generate_task_context for per-job isolation in dispatch.
    """
    if _is_migrated():
        return _generate_context_from_db(out_path=out_path)

    docs_dir = _docs_dir()
    context_file = out_path if out_path else ".synlynk/context.md"
    sentinel_file = ".synlynk/sentinel.md"

    if not os.path.exists(docs_dir):
        return ""

    if scope != "full":
        if scope.startswith("task:"):
            return _generate_task_context(scope[5:], out_path=out_path)
        print(f"  ⚠ scope='{scope}' not yet implemented, falling back to full context")
        scope = "full"

    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)

    username = get_username()
    mode = get_mode()

    with open(context_file, "w") as out:
        out.write("# synlynk Context Snapshot\n\n")
        out.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} | User: @{username} | Mode: {mode}\n\n")

        # Sentinel alerts at top (omit section if empty)
        if os.path.exists(sentinel_file):
            content = open(sentinel_file).read().strip()
            lines = [l for l in content.splitlines() if l.startswith("- [")]
            if lines:
                out.write("# Sentinel Alerts\n")
                out.write("\n".join(lines) + "\n\n---\n\n")

        # Active + deferred tasks; superseded/absorbed/done excluded
        todo_path = os.path.join(docs_dir, "todo.md")
        if os.path.exists(todo_path):
            active, deferred = [], []
            with open(todo_path) as f:
                for line in f:
                    if "- [ ]" in line:
                        active.append(line)
                    elif "- [-]" in line:
                        deferred.append(line)
            if active or deferred:
                out.write("## Active Tasks\n")
                out.writelines(active)
                if deferred:
                    out.write("\n### Deferred\n")
                    out.writelines(deferred)
                out.write("\n---\n\n")

        # Source architecture (passive cache — re-scans if HEAD changed)
        source_skeleton = _check_scan_cache()
        if source_skeleton:
            meta = _load_scan_meta()
            current_sha = _git_head_sha() or ""
            cache_hit = bool(meta and meta.get("head_sha") == current_sha)
            total_files = 0
            if meta and meta.get("deep"):
                total_files = meta["deep"].get("total_files", 0)
            arch_section = _format_source_architecture(
                source_skeleton, current_sha or "unknown", cache_hit, total_files
            )
            if arch_section:
                out.write(arch_section)

        # Roadmap: header rows + In Progress rows only
        roadmap_path = os.path.join(docs_dir, "roadmap.md")
        if os.path.exists(roadmap_path):
            out.write("## Roadmap (active)\n")
            with open(roadmap_path) as f:
                for line in f:
                    if (line.startswith("| Priority") or "| :---" in line or
                            "In Progress" in line):
                        out.write(line)
            out.write("\n---\n\n")

        # Memory (decisions) — full, it's already curated
        memory_path = os.path.join(docs_dir, "memory.md")
        if os.path.exists(memory_path):
            out.write("## Decisions\n")
            out.write(open(memory_path).read())
            out.write("\n---\n\n")

        # Recent devlog (last 7 days)
        cutoff = time.time() - (7 * 24 * 3600)
        devlog_path = os.path.join(docs_dir, "devlogs", f"{username}.md")
        if os.path.exists(devlog_path):
            out.write(f"## Recent Devlog (@{username})\n")
            _write_recent_devlog_entries(out, devlog_path, cutoff)
            out.write("\n---\n\n")

        # Teammates (team mode): last 1 entry per teammate devlog
        if mode == "team":
            devlogs_dir = os.path.join(docs_dir, "devlogs")
            if os.path.exists(devlogs_dir):
                for fname in sorted(os.listdir(devlogs_dir)):
                    if (fname.endswith(".md") and
                            fname not in (f"{username}.md", "README.md")):
                        out.write(f"## Teammate Activity (@{fname[:-3]})\n")
                        _write_last_devlog_section(out, os.path.join(devlogs_dir, fname))
                        out.write("\n---\n\n")

    print(f"  ✓ Context saved to {context_file}")
    try:
        size_kb = os.path.getsize(".synlynk/context.md") / 1024
        if size_kb > 64:
            print(f"  ⚠ Context is very large ({size_kb:.0f} KB) — strongly consider "
                  "archiving completed todos and old devlog entries to reduce token cost.")
        elif size_kb > 32:
            print(f"  ⚠ Context is large ({size_kb:.0f} KB) — consider archiving "
                  "completed todos and old devlog entries.")
    except OSError:
        pass
    try:
        return open(context_file).read()
    except OSError:
        return ""

def _archive_old_devlog_entries(devlog_path: str) -> None:
    """Moves devlog entries older than 30 days to devlogs/archive/YYYY-MM.md."""
    import calendar
    if not os.path.exists(devlog_path):
        return
    cutoff = time.time() - (30 * 24 * 3600)
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    sections = []
    current_lines, current_date = [], None
    with open(devlog_path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if current_lines:
                    sections.append((current_date, current_lines))
                current_date = m.group(1)
                current_lines = [line]
            else:
                current_lines.append(line)
    if current_lines:
        sections.append((current_date, current_lines))

    keep, archive_by_month = [], {}
    for date_str, lines in sections:
        if date_str is None:
            keep.append((date_str, lines))
            continue
        try:
            ts = calendar.timegm(time.strptime(date_str, "%Y-%m-%d"))
            if ts < cutoff:
                month_key = date_str[:7]
                archive_by_month.setdefault(month_key, []).extend(lines)
            else:
                keep.append((date_str, lines))
        except ValueError:
            keep.append((date_str, lines))

    if not archive_by_month:
        return

    archive_dir = os.path.join(os.path.dirname(devlog_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    for month_key, lines in archive_by_month.items():
        with open(os.path.join(archive_dir, f"{month_key}.md"), "a") as f:
            f.writelines(lines)

    with open(devlog_path, "w") as f:
        for _, lines in keep:
            f.writelines(lines)

def checkpoint() -> None:
    """Archives done tasks, refreshes context, and emits a telemetry event."""
    set_state("active")
    _check_upstream_divergence()
    username = get_username()
    todo_path = "project-docs/todo.md"
    devlog_path = f"project-docs/devlogs/{username}.md"

    # Collect resolved tasks (done/superseded/absorbed) and keep the rest
    completed, active_lines = [], []
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[(x|~|>)\]', line, re.IGNORECASE):
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[(x|~|>)\]\s*', '', line, flags=re.IGNORECASE).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    completed.append({"id": id_m.group(1) if id_m else None, "text": text})
                else:
                    active_lines.append(line)

    # Append resolved tasks to devlog
    if completed:
        os.makedirs(os.path.dirname(devlog_path), exist_ok=True)
        with open(devlog_path, "a") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d')}\n### Resolved (checkpoint)\n")
            for task in completed:
                f.write(f"- {task['text']}\n")
        with open(todo_path, "w") as f:
            f.writelines(active_lines)

    _archive_old_devlog_entries(devlog_path)
    generate_context()

    completed_ids = [t["id"] for t in completed if t["id"]]
    log_telemetry_event({
        "type": "checkpoint",
        "schema_version": 1,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "user": username,
        "completed_task_count": len(completed),
        "completed_task_ids": completed_ids,
        "devlog_entry_appended": bool(completed),
    })

    total_usd, total_requests = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    pct = (total_usd / limit_usd * 100) if limit_usd else 0

    daemon = WatchDaemon()
    set_state("watching" if daemon._is_running() else "stopped")

    print(f"\n✓ checkpoint [@{username}] — {len(completed)} tasks archived, context refreshed")
    if completed:
        names = "  ·  ".join(f'"{t["text"][:40]}"' for t in completed[:3])
        print(f"  Archived: {names}")
    print(f"  Budget: ${total_usd:.2f} / ${limit_usd:.2f} ({pct:.0f}%)  ·  {total_requests} requests")

def cmd_status(json_output: bool = False) -> None:
    """Displays project state dashboard. Exits 1 if sentinel active or budget exceeded."""
    username = get_username()
    mode = get_mode()

    # Active tasks
    active_tasks = []
    todo_path = "project-docs/todo.md"
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if "- [ ]" in line:
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[ \]\s*', '', line).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    active_tasks.append({"id": id_m.group(1) if id_m else None, "text": text})

    # Last checkpoint from telemetry
    last_checkpoint = None
    telemetry_file = ".synlynk/telemetry.json"
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                events = json.load(f)
            for e in reversed(events):
                if e.get("type") == "checkpoint":
                    last_checkpoint = e
                    break
        except (json.JSONDecodeError, IOError):
            pass

    # Sentinel alerts
    sentinel_alerts = []
    sentinel_file = ".synlynk/sentinel.md"
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            for line in f:
                if line.startswith("- ["):
                    sentinel_alerts.append(line.strip())

    # Budget
    total_usd, total_requests = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]

    # Watcher
    daemon = WatchDaemon()
    watcher_running = daemon._is_running()
    last_trigger_file = None
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                events = json.load(f)
            for e in reversed(events):
                if e.get("type") == "watch_trigger":
                    last_trigger_file = e.get("changed_file")
                    break
        except (json.JSONDecodeError, IOError):
            pass

    # Teammates (team mode)
    teammates = []
    if mode == "team":
        devlogs_dir = "project-docs/devlogs"
        if os.path.exists(devlogs_dir):
            for fname in sorted(os.listdir(devlogs_dir)):
                if fname.endswith(".md") and fname not in (f"{username}.md", "README.md"):
                    fpath = os.path.join(devlogs_dir, fname)
                    teammates.append({
                        "user": fname[:-3],
                        "last_active": _get_last_devlog_date(fpath),
                    })

    has_alert = bool(sentinel_alerts) or total_usd >= limit_usd or total_requests >= limit_reqs

    if json_output:
        data = {
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "user": username,
            "mode": mode,
            "active_tasks": active_tasks,
            "last_checkpoint": last_checkpoint,
            "sentinel": {"alerts": sentinel_alerts},
            "budget": {
                "used_usd": round(total_usd, 4),
                "limit_usd": limit_usd,
                "requests": total_requests,
                "limit_requests": limit_reqs,
            },
            "watcher": {"running": watcher_running, "last_trigger_file": last_trigger_file},
            "teammates": teammates,
        }
        print(json.dumps(data, indent=2))
        sys.exit(1 if has_alert else 0)

    # Human output
    sep = "─" * 45
    print(sep)
    print(f" synlynk status · @{username} · {mode} mode")
    print(sep)
    print(f" ACTIVE TASKS ({len(active_tasks)})")
    for t in active_tasks:
        tid = f"#{t['id']}" if t['id'] else ""
        print(f"   [ ] {t['text']:<40} {tid}")
    print()
    print(" LAST CHECKPOINT")
    if last_checkpoint:
        print(f"   @{last_checkpoint.get('user')} · {last_checkpoint.get('timestamp')} · "
              f"{last_checkpoint.get('completed_task_count', 0)} tasks archived")
    else:
        print("   No checkpoints yet")
    print()
    print(" SENTINEL")
    if sentinel_alerts:
        for alert in sentinel_alerts:
            print(f"   ⚠ {alert}")
    else:
        print("   ✓ No alerts")
    print()
    pct = (total_usd / limit_usd * 100) if limit_usd else 0
    print(" BUDGET")
    print(f"   ${total_usd:.2f} / ${limit_usd:.2f} ({pct:.0f}%)  ·  {total_requests} / {limit_reqs} requests")
    avg_cost, remaining_execs = _compute_burn_rate()
    if avg_cost > 0:
        runway = f"~{remaining_execs:,} execs remaining" if remaining_execs is not None else "N/A"
        print(f"   Burn:   ${avg_cost:.4f}/exec avg  |  {runway} at current pace")
    print()
    icon = "●" if watcher_running else "○"
    state = "Running" if watcher_running else "Stopped"
    trigger = f"  ·  last trigger {last_trigger_file}" if last_trigger_file else ""
    print(f" WATCHER\n   {icon} {state}{trigger}")
    check_daemon_health()
    check_stall()
    if mode == "team" and teammates:
        print()
        print(" TEAMMATES")
        for tm in teammates:
            print(f"   @{tm['user']:<12} · last active {tm['last_active']}")
    print()
    print(f" {_CYAN}CAPABILITY LEDGER{_RESET}")
    try:
        _cl_conn = _get_db()
        _cl_rows = _cl_conn.execute(
            "SELECT agent, model_version, engg_domain, phase, weighted_score, sample_count "
            "FROM capability_scores ORDER BY weighted_score DESC LIMIT 3"
        ).fetchall()
        _cl_conn.close()
    except Exception:
        _cl_rows = []
    if _cl_rows:
        print(f"   {'Agent':<10} {'Model':<22} {'Domain':<8} {'Phase':<10} {'Score':>6}  N")
        for _ag, _mv, _dom, _ph, _sc, _n in _cl_rows:
            _sc_str = f"{_sc:.2f}" if _sc is not None else "  —  "
            print(f"   {_GREEN}{_ag:<10}{_RESET} {_mv:<22} {_dom:<8} {_ph:<10} {_sc_str:>6}  {_n}")
    else:
        print("   No capability data yet.")
    print(sep)
    sys.exit(1 if has_alert else 0)

class WatchDaemon:
    """Polls project-docs/ and regenerates context.md on change.

    Subclass and override on_change() for the v1.3.0 LCP JSON-RPC daemon.
    """

    def __init__(self):
        self.pidfile = ".synlynk/watch.pid"
        self.logfile = ".synlynk/watch.log"
        self.settle_seconds = 3

    def start(self) -> None:
        if self._is_running():
            print("  synlynk watch is already running.")
            return
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        if not hasattr(os, "fork"):
            print("  ⚠ watch daemon requires Unix (macOS/Linux). Not supported on Windows.")
            return
        pid = os.fork()
        if pid > 0:
            print("  ● synlynk watch started.")
            return
        os.setsid()
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        # Daemon process: redirect stdio to log
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.logfile, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        with open(self.pidfile, "w") as f:
            f.write(str(os.getpid()))
        set_state("watching")
        self._run_loop()

    def stop(self) -> None:
        if not os.path.exists(self.pidfile):
            print("  synlynk watch is not running.")
            set_state("stopped")
            return
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)  # SIGTERM
            os.remove(self.pidfile)
            set_state("stopped")
            print("  ✓ synlynk watch stopped.")
        except (ProcessLookupError, ValueError):
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            set_state("stopped")
            print("  synlynk watch was not running (cleaned stale pidfile).")
        except OSError as e:
            print(f"  Error stopping watch daemon: {e}")

    def status(self) -> None:
        if self._is_running():
            with open(self.pidfile) as f:
                pid = f.read().strip()
            print(f"  ● synlynk watch running (PID {pid})")
            if os.path.exists(self.logfile):
                with open(self.logfile) as f:
                    lines = f.readlines()
                if lines:
                    print(f"    Last log: {lines[-1].strip()}")
        else:
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            print("  ○ synlynk watch stopped")

    def _health(self) -> str:
        """Returns 'running', 'stopped', or 'zombie' (pidfile exists but process dead)."""
        if not os.path.exists(self.pidfile):
            return "stopped"
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return "running"
        except (ProcessLookupError, ValueError, OSError):
            return "zombie"

    def _is_running(self) -> bool:
        return self._health() == "running"

    def _get_mtimes(self, directory: str) -> dict:
        mtimes = {}
        if not os.path.exists(directory):
            return mtimes
        for root, _, files in os.walk(directory):
            for fname in files:
                if fname.endswith((".md", ".json")):
                    path = os.path.join(root, fname)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except OSError:
                        pass
        return mtimes

    def on_change(self, filepath: str) -> None:
        """Called when a project-docs file changes. Override in v1.3.0 LCP daemon."""
        generate_context()
        log_telemetry_event({
            "type": "watch_trigger",
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "user": get_username(),
            "changed_file": filepath,
        })

    def _run_loop(self) -> None:
        config = load_config()
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                set_state("active")
                self.on_change(changed[0])
                set_state("watching")
                last_mtimes = self._get_mtimes("project-docs")


def _make_daemon_handler(daemon_instance):
    """Returns a BaseHTTPRequestHandler class with daemon_instance bound via closure."""
    import http.server as _http_server
    import json as _json
    import urllib.parse as _urlparse

    class DaemonHTTPHandler(_http_server.BaseHTTPRequestHandler):
        _daemon = daemon_instance

        def log_message(self, fmt, *args):
            pass  # silence access log

        def _send_json(self, code: int, data) -> None:
            body = _json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, code: int, text: str) -> None:
            body = text.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _parse_path(self):
            parsed = _urlparse.urlparse(self.path)
            return parsed.path, dict(_urlparse.parse_qsl(parsed.query))

        def do_GET(self):
            path, params = self._parse_path()
            try:
                if path == "/context":
                    self._handle_context()
                elif path == "/status":
                    self._handle_status()
                elif path == "/jobs":
                    self._handle_jobs(params)
                elif path.startswith("/jobs/"):
                    self._handle_job_detail(path[6:])
                elif path == "/stories":
                    self._handle_stories()
                elif path.startswith("/stories/"):
                    self._handle_story_detail(path[9:])
                elif path == "/capability":
                    self._handle_capability()
                elif path == "/sentinel":
                    self._handle_sentinel()
                else:
                    self._send_json(404, {"error": "not found"})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        def do_POST(self):
            path, _ = self._parse_path()
            try:
                if path == "/dispatch":
                    self._handle_dispatch()
                elif path == "/checkpoint":
                    self._handle_checkpoint()
                else:
                    self._send_json(404, {"error": "not found"})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        def _handle_context(self):
            context_path = ".synlynk/context.md"
            content = ""
            if os.path.exists(context_path):
                with open(context_path) as f:
                    content = f.read()
            accept = self.headers.get("Accept", "")
            if "text/plain" in accept:
                self._send_text(200, content)
            else:
                self._send_json(200, {"content": content})

        def _handle_status(self):
            uptime = int(time.time() - getattr(self._daemon, "_start_time", time.time()))
            conn = _get_db()
            try:
                counts = {}
                for status in ("queued", "running", "done", "failed"):
                    counts[status] = conn.execute(
                        "SELECT COUNT(*) FROM daemon_jobs WHERE status=?", (status,)
                    ).fetchone()[0]
            finally:
                conn.close()
            self._send_json(200, {
                "running": True,
                "uptime_s": uptime,
                "pid": os.getpid(),
                "jobs": counts,
            })

        def _handle_jobs(self, params):
            conn = _get_db()
            try:
                status_filter = params.get("status")
                if status_filter:
                    rows = conn.execute(
                        "SELECT job_id, agent, task, story_id, status, priority, "
                        "depends_on, pid, enqueued_at, started_at, completed_at, exit_code "
                        "FROM daemon_jobs WHERE status=? ORDER BY enqueued_at DESC",
                        (status_filter,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT job_id, agent, task, story_id, status, priority, "
                        "depends_on, pid, enqueued_at, started_at, completed_at, exit_code "
                        "FROM daemon_jobs ORDER BY enqueued_at DESC"
                    ).fetchall()
            finally:
                conn.close()
            cols = ["job_id", "agent", "task", "story_id", "status", "priority",
                    "depends_on", "pid", "enqueued_at", "started_at", "completed_at", "exit_code"]
            self._send_json(200, [dict(zip(cols, r)) for r in rows])

        def _handle_job_detail(self, job_id):
            conn = _get_db()
            try:
                row = conn.execute(
                    "SELECT job_id, agent, task, story_id, status, priority, depends_on, "
                    "pid, enqueued_at, started_at, completed_at, exit_code, log_path "
                    "FROM daemon_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            finally:
                conn.close()
            if not row:
                self._send_json(404, {"error": f"job {job_id!r} not found"})
                return
            cols = ["job_id", "agent", "task", "story_id", "status", "priority",
                    "depends_on", "pid", "enqueued_at", "started_at", "completed_at",
                    "exit_code", "log_path"]
            data = dict(zip(cols, row))
            log_tail = []
            if data.get("log_path") and os.path.exists(data["log_path"]):
                with open(data["log_path"]) as f:
                    log_tail = f.readlines()[-100:]
            data["log_tail"] = "".join(log_tail)
            self._send_json(200, data)

        def _handle_dispatch(self):
            import hashlib as _hashlib
            import json as _json
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            try:
                payload = _json.loads(body)
            except Exception:
                self._send_json(400, {"error": "invalid JSON body"})
                return
            agent = payload.get("agent")
            task = payload.get("task")
            if not agent or not task:
                self._send_json(400, {"error": "agent and task are required"})
                return
            job_id = "djob-" + _hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            conn = _get_db()
            try:
                conn.execute(
                    "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                    "priority, depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?,?)",
                    (job_id, agent, task, payload.get("story_id"),
                     "queued", payload.get("priority", 5),
                     _json.dumps(payload.get("depends_on", [])),
                     time.strftime("%Y-%m-%dT%H:%M:%S"))
                )
                conn.commit()
            finally:
                conn.close()
            self._send_json(200, {"job_id": job_id})

        def _handle_stories(self):
            conn = _get_db()
            try:
                rows = conn.execute(
                    "SELECT story_id, title, engg_domain, org_domain, industry, phase, "
                    "estimated_tokens, actual_tokens, created_at "
                    "FROM stories ORDER BY created_at DESC"
                ).fetchall()
            finally:
                conn.close()
            cols = ["story_id", "title", "engg_domain", "org_domain", "industry",
                    "phase", "estimated_tokens", "actual_tokens", "created_at"]
            self._send_json(200, [dict(zip(cols, r)) for r in rows])

        def _handle_story_detail(self, story_id):
            conn = _get_db()
            try:
                row = conn.execute(
                    "SELECT story_id, title, engg_domain, org_domain, industry, phase, "
                    "estimated_tokens, actual_tokens, created_at "
                    "FROM stories WHERE story_id=?", (story_id,)
                ).fetchone()
            finally:
                conn.close()
            if not row:
                self._send_json(404, {"error": f"story {story_id!r} not found"})
                return
            cols = ["story_id", "title", "engg_domain", "org_domain", "industry",
                    "phase", "estimated_tokens", "actual_tokens", "created_at"]
            self._send_json(200, dict(zip(cols, row)))

        def _handle_capability(self):
            conn = _get_db()
            try:
                rows = conn.execute(
                    "SELECT agent, engg_domain, AVG(quality), COUNT(*) "
                    "FROM capability_ratings GROUP BY agent, engg_domain"
                ).fetchall()
            finally:
                conn.close()
            result = [
                {"agent": r[0], "domain": r[1], "avg_quality": r[2], "count": r[3]}
                for r in rows
            ]
            self._send_json(200, result)

        def _handle_sentinel(self):
            sentinel_file = ".synlynk/sentinel.md"
            alerts = []
            if os.path.exists(sentinel_file):
                with open(sentinel_file) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("- ["):
                            alerts.append(line)
            self._send_json(200, alerts)

        def _handle_checkpoint(self):
            with daemon_instance._context_lock:
                generate_context()
            self._send_json(200, {"regenerated": True})

    return DaemonHTTPHandler


def _daemon_install_service(daemon_instance) -> None:
    import textwrap as _textwrap

    synlynk_path = shutil.which("synlynk") or sys.argv[0]
    home = os.path.expanduser("~")

    try:
        if sys.platform == "darwin":
            launchagents_dir = os.path.join(home, "Library", "LaunchAgents")
            os.makedirs(launchagents_dir, exist_ok=True)
            log_dir = os.path.join(home, ".synlynk")
            os.makedirs(log_dir, exist_ok=True)
            plist_path = os.path.join(launchagents_dir, "com.synlynk.daemon.plist")
            log_path = os.path.join(log_dir, "launchd.log")
            plist = _textwrap.dedent(f"""\
                <?xml version="1.0" encoding="UTF-8"?>
                <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                <plist version="1.0">
                  <dict>
                    <key>Label</key>
                    <string>com.synlynk.daemon</string>
                    <key>ProgramArguments</key>
                    <array>
                      <string>{synlynk_path}</string>
                      <string>daemon</string>
                      <string>start</string>
                    </array>
                    <key>RunAtLoad</key>
                    <true/>
                    <key>KeepAlive</key>
                    <false/>
                    <key>StandardOutPath</key>
                    <string>{log_path}</string>
                    <key>StandardErrorPath</key>
                    <string>{log_path}</string>
                  </dict>
                </plist>
            """)
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist)
            subprocess.run(["launchctl", "load", "-w", plist_path], check=False)
            print(f"  ✓ installed launchd service: {plist_path}")
            return

        if shutil.which("systemctl"):
            unit_dir = os.path.join(home, ".config", "systemd", "user")
            os.makedirs(unit_dir, exist_ok=True)
            synlynk_dir = os.path.join(home, ".synlynk")
            os.makedirs(synlynk_dir, exist_ok=True)
            unit_path = os.path.join(unit_dir, "synlynk-daemon.service")
            unit = _textwrap.dedent(f"""\
                [Unit]
                Description=Synlynk daemon
                After=default.target

                [Service]
                Type=forking
                ExecStart={synlynk_path} daemon start
                PIDFile=%h/.synlynk/daemon.pid
                Restart=on-failure

                [Install]
                WantedBy=default.target
            """)
            with open(unit_path, "w", encoding="utf-8") as f:
                f.write(unit)
            subprocess.run(["systemctl", "--user", "enable", "--now", "synlynk-daemon"], check=False)
            print(f"  ✓ installed systemd user service: {unit_path}")
            return

        synlynk_dir = os.path.join(home, ".synlynk")
        os.makedirs(synlynk_dir, exist_ok=True)
        entry = f"@reboot {synlynk_path} daemon start"
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = result.stdout if result.returncode == 0 else ""
        if entry not in current:
            new_crontab = current.rstrip("\n")
            if new_crontab:
                new_crontab += "\n"
            new_crontab += entry + "\n"
            subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=False)
        print("  ✓ installed @reboot crontab entry")
    except FileNotFoundError:
        print("  not installed")


def _daemon_uninstall_service() -> None:
    home = os.path.expanduser("~")

    try:
        if sys.platform == "darwin":
            plist_path = os.path.join(home, "Library", "LaunchAgents", "com.synlynk.daemon.plist")
            subprocess.run(["launchctl", "unload", plist_path], check=False)
            os.remove(plist_path)
            print(f"  ✓ uninstalled launchd service: {plist_path}")
            return

        if shutil.which("systemctl"):
            unit_path = os.path.join(home, ".config", "systemd", "user", "synlynk-daemon.service")
            subprocess.run(["systemctl", "--user", "disable", "--now", "synlynk-daemon"], check=False)
            os.remove(unit_path)
            print(f"  ✓ uninstalled systemd user service: {unit_path}")
            return

        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = result.stdout if result.returncode == 0 else ""
        filtered = "\n".join(
            line for line in current.splitlines()
            if not (line.strip().startswith("@reboot ") and line.strip().endswith(" daemon start"))
        )
        if filtered:
            filtered += "\n"
        subprocess.run(["crontab", "-"], input=filtered, text=True, check=False)
        print("  ✓ uninstalled @reboot crontab entry")
    except FileNotFoundError:
        print("  not installed")


def _make_relay_handler(subscribers: list, sub_lock) -> type:
    """Returns an HTTP handler class for the stateless relay broker."""
    import http.server as _http
    import json as _json
    import queue as _queue_mod

    class RelayHandler(_http.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # suppress access logs

        def do_GET(self):
            if self.path == "/health":
                self._send_json({"ok": True})
            elif self.path == "/events":
                self._stream_sse()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/publish":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    event = _json.loads(body)
                except ValueError:
                    self.send_error(400, "invalid JSON")
                    return
                data = f"data: {_json.dumps(event)}\n\n"
                with sub_lock:
                    dead = []
                    for q in subscribers:
                        try:
                            q.put_nowait(data)
                        except _queue_mod.Full:
                            pass  # slow subscriber — skip event, keep alive
                        except Exception:
                            dead.append(q)
                    for d in dead:
                        subscribers.remove(d)
                    fans = len(subscribers)
                self._send_json({"ok": True, "fans": fans})
            else:
                self.send_error(404)

        def _send_json(self, obj):
            body = _json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream_sse(self):
            import queue as _q
            q = _q.Queue(maxsize=256)
            with sub_lock:
                subscribers.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                while True:
                    try:
                        data = q.get(timeout=30)
                        self.wfile.write(data.encode())
                        self.wfile.flush()
                    except _q.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with sub_lock:
                    try:
                        subscribers.remove(q)
                    except ValueError:
                        pass

    return RelayHandler


class SynlynkRelay:
    """Stateless HTTP relay broker for synlynk node events."""

    RELAY_PORT = 27472

    def __init__(self, port: int = None):
        import threading as _threading
        self.port = port or self.RELAY_PORT
        self._subscribers: list = []
        self._sub_lock = _threading.Lock()
        self._server = None

    def start(self) -> None:
        """Starts the relay HTTP server in a background thread."""
        import http.server as _http
        import threading as _threading

        handler = _make_relay_handler(self._subscribers, self._sub_lock)
        self._server = _http.HTTPServer(("", self.port), handler)
        t = _threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        print(f"  {_GREEN}✓{_RESET} Relay started on port {self.port}")
        print(f"  {_DIM}Subscribe: GET http://localhost:{self.port}/events{_RESET}")
        print(f"  {_DIM}Publish:   POST http://localhost:{self.port}/publish{_RESET}")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            self._server.shutdown()
            print("\n  Relay stopped.")

    def is_alive(self, relay_url: str = None) -> bool:
        """Checks if the relay at relay_url (or localhost) is responding."""
        import urllib.request as _req

        url = relay_url or f"http://localhost:{self.port}/health"
        try:
            _req.urlopen(url, timeout=1)
            return True
        except Exception:
            return False


class SynlynkDaemon(WatchDaemon):
    """Always-running daemon: mtime polling + HTTP API + persistent job queue.

    Subclasses WatchDaemon (double-fork, pidfile, mtime loop) and adds:
    - HTTP server thread on localhost:27471
    - _reconcile_daemon_jobs() + _dispatch_ready_jobs() on each poll tick
    """

    HTTP_PORT = 27471

    def __init__(self):
        import threading as _threading
        super().__init__()
        self.pidfile = ".synlynk/daemon.pid"
        self.logfile = ".synlynk/daemon.log"
        self._start_time = time.time()
        self._context_lock = _threading.Lock()

    def start(self) -> None:
        if self._is_running():
            print("  synlynk daemon is already running.")
            return
        watch_pid = ".synlynk/watch.pid"
        if os.path.exists(watch_pid):
            print("  ⚠ synlynk watch is also running — both will poll project-docs/.")
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        if not hasattr(os, "fork"):
            print("  ⚠ daemon requires Unix (macOS/Linux). Not supported on Windows.")
            return
        pid = os.fork()
        if pid > 0:
            print("  ● synlynk daemon started.")
            return
        os.setsid()
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.logfile, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        with open(self.pidfile, "w") as f:
            f.write(str(os.getpid()))
        start_time = time.time()
        self._start_time = start_time
        start_file = self.pidfile.replace(".pid", ".start")
        with open(start_file, "w") as f:
            f.write(str(start_time))
        self._run_loop()

    def stop(self) -> None:
        if not os.path.exists(self.pidfile):
            print("  ✦ daemon not running")
            return
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)
            os.remove(self.pidfile)
            start_file = self.pidfile.replace(".pid", ".start")
            if os.path.exists(start_file):
                os.remove(start_file)
            print("  ✓ synlynk daemon stopped.")
        except (ProcessLookupError, ValueError):
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            start_file = self.pidfile.replace(".pid", ".start")
            if os.path.exists(start_file):
                os.remove(start_file)
            print("  ✦ daemon not running (cleaned stale pidfile).")
        except OSError as e:
            print(f"  Error stopping daemon: {e}")

    def status(self) -> None:
        if not self._is_running():
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            print("  ✦ synlynk daemon not running")
            return
        with open(self.pidfile) as f:
            pid = int(f.read().strip())
        start_file = self.pidfile.replace(".pid", ".start")
        try:
            with open(start_file) as f:
                start_time = float(f.read().strip())
        except (OSError, ValueError):
            start_time = time.time()
        uptime_s = int(time.time() - start_time)
        h, rem = divmod(uptime_s, 3600)
        m = rem // 60
        uptime_str = f"{h}h {m}m" if h else f"{m}m"
        conn = _get_db()
        try:
            counts = {s: conn.execute(
                "SELECT COUNT(*) FROM daemon_jobs WHERE status=?", (s,)
            ).fetchone()[0] for s in ("queued", "running", "done", "failed")}
        finally:
            conn.close()
        print(f"  ✦ synlynk daemon running  (pid {pid}, up {uptime_str})")
        print(f"    jobs: {counts['queued']} queued · {counts['running']} running "
              f"· {counts['done']} done · {counts['failed']} failed")
        print(f"    http: http://localhost:{self.HTTP_PORT}")

    def _run_loop(self) -> None:
        import threading as _threading
        import http.server as _http_server
        import traceback as _traceback

        class _ReuseAddrHTTPServer(_http_server.HTTPServer):
            allow_reuse_address = True

        handler_class = _make_daemon_handler(self)
        http_server = _ReuseAddrHTTPServer(("127.0.0.1", self.HTTP_PORT), handler_class)
        t = _threading.Thread(target=http_server.serve_forever, daemon=True)
        t.start()

        config = load_config()
        max_parallel = config.get("max_parallel", 4)
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                try:
                    with self._context_lock:
                        self.on_change(changed[0])
                except Exception:
                    _traceback.print_exc()
                last_mtimes = self._get_mtimes("project-docs")
            _reconcile_daemon_jobs()
            _dispatch_ready_jobs(max_parallel=max_parallel)


# ── Wizard TUI primitives (BS-17 Plan B Tasks B-1 / B-2) ────────────────────
# Inserted before init() per plan. Pure stdlib TUI for FTUE.

_WIZ_SYNAPTIC_BLURB = (
    "In the brain, a synaptic link is the tiny gap where one neuron passes\n"
    "  its signal to the next. Alone, neurons are just cells. Connected, they\n"
    "  produce thought. Your AI tools are the same — powerful in isolation,\n"
    "  transformative when they share a signal. synlynk is the gap that makes\n"
    "  them think together."
)

_WIZ_PRODUCT_BLURB = (
    "You already have great AI tools. The problem is they don't know about\n"
    "  each other — or your project. synlynk fixes that: it injects shared\n"
    "  context before every dispatch, routes tasks to the right agent, and\n"
    "  keeps score on what's working. Your fleet, finally coordinated."
)


def _wiz_clear() -> None:
    """Clear the terminal screen."""
    os.system("clear" if os.name != "nt" else "cls")


def _wiz_read_key() -> str:
    """Read a single keypress without requiring Enter.

    Falls back to input()[0] when stdin is not a TTY (e.g. tests, pipes).
    """
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line[0] if line else "\r"
    try:
        import tty as _tty
        import termios as _termios
        fd = sys.stdin.fileno()
        old = _termios.tcgetattr(fd)
        try:
            _tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
    except (ImportError, Exception):
        # Windows or no termios — fall back to Enter-terminated input
        line = input()
        return line[0] if line else "\r"


def _wiz_header(step: int, total: int, sub_active: bool = False) -> None:
    """Print the wizard progress header.

    Active step shown as a wider pill. Sub-active steps use teal colour.
    """
    _TEAL = "\033[36m"
    dots = []
    for i in range(1, total + 1):
        if i < step:
            dots.append(f"{_CYAN}●{_RESET}")
        elif i == step:
            color = _TEAL if sub_active else _CYAN
            dots.append(f"{color}━━{_RESET}")
        else:
            dots.append(f"{_DIM}·{_RESET}")
    dot_str = "  ".join(dots)
    sub_note = " (multi-repo)" if sub_active else ""
    print(f"\n  step {_CYAN}{step}{_RESET}/{total}{sub_note}   {dot_str}\n")


def _wiz_prompt(hint: str, color: str = None) -> None:
    """Print the bottom prompt line."""
    c = color or _CYAN
    print(f"\n  {c}›{_RESET} {_DIM}{hint}{_RESET}")


def _wiz_screen_landing() -> None:
    """Landing screen — brand intro + synaptic link explainer. Waits for Enter."""
    _wiz_clear()
    print(f"\n  {_BOLD}{_CYAN}syn{_RESET}{_CYAN}l{_RESET}{_DIM}y{_RESET}"
          f"{_CYAN}n{_RESET}k  {_DIM}·  synaptic link for AI development{_RESET}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}")
    print(f"\n  {_BOLD}What is a synaptic link?{_RESET}")
    print(f"  {_DIM}{_WIZ_SYNAPTIC_BLURB}{_RESET}\n")
    print(f"  {_WIZ_PRODUCT_BLURB}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}")
    print(f"\n  {_GREEN}✦ One brain{_RESET}  {_DIM}Every agent works from the same project memory.{_RESET}")
    print(f"  {_GREEN}✦ 4× efficiency{_RESET}  {_DIM}Headless dispatch — no wasted tokens on chat.{_RESET}")
    print(f"  {_GREEN}✦ Always watching{_RESET}  {_DIM}Costs, drift, and jobs tracked automatically.{_RESET}")
    _wiz_prompt("press enter to start setup — takes about 2 minutes")
    _wiz_read_key()


def _wiz_screen_harness(scan: dict) -> str:
    """Screen 1 — choose home harness. Returns chosen harness name."""
    _wiz_clear()
    _wiz_header(step=1, total=6)
    print(f"  {_BOLD}Choose your home harness{_RESET}\n")
    print(f"  {_DIM}Your home harness is the AI CLI synlynk treats as primary —{_RESET}")
    print(f"  {_DIM}where it orchestrates jobs, reads costs, and runs health checks.{_RESET}")
    print(f"  {_DIM}You can dispatch to any agent regardless of this choice.{_RESET}\n")

    harnesses = scan.get("harnesses", [])
    home = scan.get("home_harness")

    if not harnesses:
        print(f"  {_YELLOW}⚠ No harnesses found on PATH.{_RESET}")
        print(f"  {_DIM}Install claude, gemini, or codex then re-run `synlynk scan`.{_RESET}")
        _wiz_prompt("press enter to continue with no home harness")
        _wiz_read_key()
        return ""

    print(f"  {_DIM}scan found:{_RESET}")
    for h in harnesses:
        marker = f"{_GREEN}●{_RESET}" if h["name"] == home else f"{_DIM}○{_RESET}"
        print(f"    {marker} {h['name']:12} {_DIM}{h['version']}  {h['path']}{_RESET}")
    print()

    for i, h in enumerate(harnesses, 1):
        default_note = "  (default)" if h["name"] == home else ""
        print(f"  {_CYAN}[{i}]{_RESET} {h['name']}{_DIM}{default_note}{_RESET}")

    _wiz_prompt("enter number to select · enter to use default")
    key = _wiz_read_key()

    if key in ("\r", "\n", ""):
        return home or (harnesses[0]["name"] if harnesses else "")
    try:
        idx = int(key) - 1
        if 0 <= idx < len(harnesses):
            return harnesses[idx]["name"]
    except ValueError:
        pass
    return home or (harnesses[0]["name"] if harnesses else "")


def _wiz_screen_topology(scan: dict) -> str:
    """Screen 2 — repo topology. Returns 'single', 'monorepo', or 'multi'."""
    _wiz_clear()
    _wiz_header(step=2, total=6)
    print(f"  {_BOLD}How are your repos arranged?{_RESET}\n")
    print(f"  {_DIM}synlynk organises your work into workspaces — named containers{_RESET}")
    print(f"  {_DIM}that share a context database, agent fleet, and budget.{_RESET}\n")

    repos = scan.get("repos", [])
    if repos:
        print(f"  {_DIM}scan found {len(repos)} git repo(s) nearby:{_RESET}")
        for r in repos[:5]:
            stack = ", ".join(r["stack_labels"]) or "unknown"
            print(f"    {_CYAN}●{_RESET} {r['name']:20} {_DIM}{stack}{_RESET}")
        if len(repos) > 5:
            print(f"    {_DIM}… and {len(repos) - 5} more{_RESET}")
        print()

    print(f"  {_CYAN}[1]{_RESET} Single repo  {_DIM}— just this repo{_RESET}")
    print(f"  {_CYAN}[2]{_RESET} Monorepo     {_DIM}— one repo with packages/ or apps/ sub-dirs{_RESET}")
    print(f"  {_CYAN}[3]{_RESET} Multi-repo   {_DIM}— multiple repos sharing one workspace{_RESET}")

    # Pre-select based on scan result
    auto = scan.get("topology", "single")
    auto_num = {"single": "1", "monorepo": "2", "multi": "3"}.get(auto, "1")
    _wiz_prompt(f"enter 1/2/3 · enter for auto-detected ({auto_num})")
    key = _wiz_read_key()

    if key in ("\r", "\n", ""):
        return auto
    mapping = {"1": "single", "2": "monorepo", "3": "multi"}
    return mapping.get(key, auto)


def _wiz_screen_workspace_name_pick(scan: dict) -> dict:
    """Screen 2ab — combined workspace name input + repo picker (multi-repo).

    Returns dict: {workspace_name: str, repos: list[dict]}
    """
    _TEAL = "\033[36m"
    _wiz_clear()
    _wiz_header(step=2, total=6, sub_active=True)
    print(f"  {_BOLD}Name & assemble your workspace{_RESET}\n")
    print(f"  {_DIM}All selected repos share one state.db, agent fleet, and budget.{_RESET}")
    print(f"  {_DIM}synlynk found these git roots nearby — include everything your{_RESET}")
    print(f"  {_DIM}agents need to see together.{_RESET}\n")

    # Workspace name
    suggested = scan.get("workspace_name", "my-workspace")
    print(f"  {_DIM}workspace name{_RESET}  [{_CYAN}{suggested}{_RESET}]  "
          f"{_DIM}(enter to accept, or type new name){_RESET}")
    _wiz_prompt("workspace name")

    if sys.stdin.isatty():
        import tty as _tty, termios as _termios
        # Restore normal line editing for text input
        fd = sys.stdin.fileno()
        try:
            old = _termios.tcgetattr(fd)
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
        except Exception:
            pass
    raw_name = input().strip()
    workspace_name = raw_name if raw_name else suggested

    # Repo picker
    repos = scan.get("repos", [])
    _DOTFILE_NAMES = {"dotfiles", ".dotfiles", "dotfile"}
    selected = [r["name"] not in _DOTFILE_NAMES for r in repos]

    print(f"\n  {_DIM}repos to include:{_RESET}  "
          f"{_DIM}(space to toggle, enter to confirm){_RESET}\n")
    for i, (r, sel) in enumerate(zip(repos, selected)):
        stack = ", ".join(r["stack_labels"]) or "unknown"
        check = f"{_TEAL}[✓]{_RESET}" if sel else f"{_DIM}[ ]{_RESET}"
        print(f"  {check} {i+1}. {r['name']:20} {_DIM}{stack}{_RESET}")

    print(f"\n  {_DIM}[a] add repo from another path{_RESET}")
    _wiz_prompt("number to toggle · a to add · enter to confirm")

    while True:
        key = _wiz_read_key()
        if key in ("\r", "\n", ""):
            break
        if key == "a":
            print(f"\n  {_DIM}path to repo:{_RESET} ", end="", flush=True)
            extra = input().strip()
            if extra and os.path.isdir(os.path.join(extra, ".git")):
                repos.append({
                    "path": os.path.abspath(extra),
                    "name": os.path.basename(extra),
                    "stack_labels": fingerprint_stack(extra),
                    "readme_excerpt": "",
                    "context_sections": {},
                })
                selected.append(True)
                print(f"  {_GREEN}✓{_RESET} added {os.path.basename(extra)}")
        try:
            idx = int(key) - 1
            if 0 <= idx < len(selected):
                selected[idx] = not selected[idx]
        except ValueError:
            pass

    chosen_repos = [r for r, s in zip(repos, selected) if s]
    return {"workspace_name": workspace_name, "repos": chosen_repos}


def _wiz_screen_workspace_confirm(workspace: dict) -> bool:
    """Screen 2c — confirm workspace structure.

    Returns True = confirmed (continue), False = go back to 2ab.
    """
    _TEAL = "\033[36m"
    _wiz_clear()
    _wiz_header(step=2, total=6, sub_active=True)
    print(f"  {_BOLD}Here's your workspace{_RESET}\n")

    ws_name = workspace.get("workspace_name", "workspace")
    repos = workspace.get("repos", [])
    print(f"  {_TEAL}{ws_name}/{_RESET}")
    print(f"  {_DIM}├─ state.db{_RESET}")
    print(f"  {_DIM}├─ config.json{_RESET}")
    print(f"  {_DIM}└─ repos{_RESET}")
    for r in repos:
        print(f"  {_GREEN}    ✓{_RESET} {r['name']:20} {_DIM}{r['path']}{_RESET}")

    print(f"\n  {_DIM}state lives at: ~/.synlynk/workspaces/{ws_name}/state.db{_RESET}")
    print(f"  {_DIM}add more later: synlynk scan --add ~/path/to/repo{_RESET}\n")

    print(f"  {_TEAL}[enter]{_RESET} Create workspace · "
          f"{_DIM}[e]{_RESET} Edit")
    _wiz_prompt("enter to create · e to edit")
    key = _wiz_read_key()
    return key not in ("e", "E")


def _wiz_screen_skills(scan: dict) -> None:
    """Screen 3 — skills/plugins education (no required choice)."""
    _wiz_clear()
    _wiz_header(step=3, total=6)
    print(f"  {_BOLD}synlynk and your skill packs work together{_RESET}\n")
    print(f"  {_DIM}synlynk injects project context before skills run — it never overrides{_RESET}")
    print(f"  {_DIM}them. If you use Superpowers or GStack, your skill routes stay intact.{_RESET}")
    print(f"  {_DIM}synlynk adds the layer below: shared state, dispatch coordination,{_RESET}")
    print(f"  {_DIM}cost tracking.{_RESET}\n")

    skills = scan.get("skills", [])
    if skills:
        print(f"  {_DIM}scan found:{_RESET}")
        for s in skills:
            print(f"    {_GREEN}●{_RESET} {s['name']:20} {_DIM}v{s['version']}  {s['path']}{_RESET}")
    else:
        print(f"  {_DIM}No skill packs found. You can install them later —{_RESET}")
        print(f"  {_DIM}synlynk works great without them.{_RESET}")

    _wiz_prompt("press enter to continue")
    _wiz_read_key()


_ROBOT_ASCII = "[~]"  # ASCII robot stand-in for terminal (no emoji)


def _wiz_screen_agents(scan: dict) -> None:
    """Screen 4 — agent fleet display (no required choice)."""
    _wiz_clear()
    _wiz_header(step=4, total=6)
    print(f"  {_BOLD}Your agent fleet{_RESET}\n")
    print(f"  {_DIM}Each agent has different strengths. synlynk's dispatch command routes{_RESET}")
    print(f"  {_DIM}tasks to the right agent and tracks what they cost you.{_RESET}\n")

    agents = [a for a in scan.get("agents", []) if a.get("functional")]
    if agents:
        print(f"  {_DIM}installed agents:{_RESET}\n")
        for a in agents:
            caps = ", ".join((a.get("capabilities") or a.get("roles") or [])[:3])
            print(f"  {_CYAN}{_ROBOT_ASCII}{_RESET}  {_BOLD}{a['name']:12}{_RESET}"
                  f"  {_DIM}{a.get('version', 'unknown'):10}{_RESET}  {caps}")
    else:
        print(f"  {_YELLOW}No functional agents found.{_RESET}")
        print(f"  {_DIM}Install claude, gemini, or codex to form your agent fleet.{_RESET}")

    _wiz_prompt("press enter to continue")
    _wiz_read_key()


def _wiz_screen_roles(scan: dict) -> dict:
    """Screen 5 — agent role assignment.

    Returns dict: {agent_name: role_description}
    """
    _wiz_clear()
    _wiz_header(step=5, total=6)
    print(f"  {_BOLD}Who does what?{_RESET}\n")
    print(f"  {_DIM}Consistent role assignment stops agents stomping on each other's work.{_RESET}")
    print(f"  {_DIM}synlynk writes a role block into each agent's directive file so every{_RESET}")
    print(f"  {_DIM}agent knows its lane from token one.{_RESET}\n")

    agents = [a for a in scan.get("agents", []) if a.get("functional")]
    _DEFAULT_ROLES = {
        "claude": "PM · code review · deployments",
        "agy": "implementation · testing · templates",
        "codex": "CLI plumbing · refactoring",
        "grok": "canvas/JS · infra scaffold · complex data structures",
    }
    roles = {}
    for a in agents:
        name = a["name"]
        existing = _DEFAULT_ROLES.get(name, ", ".join(a.get("roles", [])) or "general")
        roles[name] = existing
        print(f"  {_CYAN}{name:12}{_RESET} {_DIM}→{_RESET}  {existing}")

    print()
    print(f"  {_CYAN}[enter]{_RESET} use these roles  "
          f"{_DIM}[e]{_RESET} edit (opens per-agent prompts)")
    _wiz_prompt("enter to accept · e to edit")
    key = _wiz_read_key()

    if key in ("e", "E"):
        for name in list(roles.keys()):
            print(f"\n  {name} role [{roles[name]}]: ", end="", flush=True)
            entered = input().strip()
            if entered:
                roles[name] = entered

    return roles


def _wiz_screen_launch(workspace: dict, scan: dict, auto_launch: bool = False) -> None:
    """Screen 6 — launch cheat sheet. Final screen."""
    _wiz_clear()
    _wiz_header(step=6, total=6)
    ws_name = workspace.get("workspace_name", "workspace")
    home_h = workspace.get("home_harness") or scan.get("home_harness") or "claude"
    print(f"  {_BOLD}{_GREEN}You're set up.{_RESET}  "
          f"{_DIM}workspace: {ws_name}{_RESET}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}\n")
    cmds = [
        (f"synlynk dispatch {home_h}", f'"ask {home_h} something"', "dispatch a task"),
        ("synlynk scan --refresh", "", "re-scan all repos"),
        ("synlynk status", "", "platform health + agent availability"),
        ("synlynk jobs", "", "list running/recent jobs"),
        ("synlynk help", "", "full command reference"),
    ]
    for cmd, arg, desc in cmds:
        suffix = f" {arg}" if arg else ""
        print(f"  {_CYAN}{cmd}{suffix}{_RESET}  {_DIM}{desc}{_RESET}")
    print(f"\n  {_DIM}{'─' * 52}{_RESET}")
    _wiz_prompt("done · run `synlynk launch` to pick your first task")
    _wiz_read_key()
    if auto_launch:
        cmd_launch_ftue()


def _launch_screen_cycles() -> None:
    """Screen 3 — cycles explainer. Any key returns to Screen 1."""
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


def _launch_screen_preview(task: dict, scan: dict) -> tuple:
    """Screen 2 — dispatch preview.
    Returns (confirmed: bool, prompt: str).
    [enter/space] → (True, prompt); [e] → edit prompt inline; [esc/q] → (False, prompt)
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


def _launch_screen_tasks(tasks: list, scan: dict):
    """Screen 1 — task selection TUI. Returns chosen template dict or None if user skips."""
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


def wizard_init(scan: dict = None, dry_run: bool = False) -> None:
    """Run the FTUE wizard. All state is held in memory until Screen 6.

    scan: pre-built ScanResult dict (used by tests and when called from init()).
          If None, runs run_workspace_scan() automatically (Phase 0).
    dry_run: if True, skip writing workspace config + context.md at the end.
    """
    # ── Phase 0: silent scan (skipped if scan provided) ───────────────────
    if scan is None:
        print(f"\n  {_CYAN}›{_RESET} scanning your environment...")
        try:
            scan = run_workspace_scan()
            repo_names = ", ".join(r["name"] for r in scan["repos"])
            harness_names = ", ".join(h["name"] for h in scan["harnesses"]) or "none"
            stacks = sorted({l for r in scan["repos"] for l in r["stack_labels"]})
            print(f"  repos found: {len(scan['repos'])}  ·  "
                  f"harnesses: {harness_names}  ·  "
                  f"stacks: {', '.join(stacks) or 'unknown'}\n")
        except Exception as e:
            print(f"  {_YELLOW}⚠ Scan failed: {e}. Continuing with empty scan.{_RESET}")
            scan = {"workspace_name": "my-workspace", "topology": "single",
                    "repos": [], "harnesses": [], "agents": [], "skills": [],
                    "home_harness": None, "scanned_at": ""}

    # ── Landing ────────────────────────────────────────────────────────────
    _wiz_screen_landing()

    # ── Screen 1: Home harness ─────────────────────────────────────────────
    home_harness = _wiz_screen_harness(scan)

    # ── Screen 2: Topology ────────────────────────────────────────────────
    topology = _wiz_screen_topology(scan)

    # ── Screens 2ab + 2c (multi-repo sub-flow) ────────────────────────────
    if topology == "multi":
        while True:
            workspace_pick = _wiz_screen_workspace_name_pick(scan)
            workspace = {
                "workspace_name": workspace_pick["workspace_name"],
                "repos": workspace_pick["repos"],
                "topology": "multi",
                "home_harness": home_harness,
            }
            if _wiz_screen_workspace_confirm(workspace):
                break
    else:
        workspace = {
            "workspace_name": scan.get("workspace_name", "my-workspace"),
            "repos": scan.get("repos", []),
            "topology": topology,
            "home_harness": home_harness,
        }

    # ── Screen 3: Skills ──────────────────────────────────────────────────
    _wiz_screen_skills(scan)

    # ── Screen 4: Agents ─────────────────────────────────────────────────
    _wiz_screen_agents(scan)

    # ── Screen 5: Roles ───────────────────────────────────────────────────
    roles = _wiz_screen_roles(scan)
    workspace["agent_roles"] = roles

    # ── Screen 6: Launch cheat sheet ─────────────────────────────────────
    cfg = load_config()
    _wiz_screen_launch(workspace, scan,
                       auto_launch=cfg.get("auto_launch_after_wizard", True))

    # ── Commit-on-complete: write all state ───────────────────────────────
    if not dry_run:
        ws_name = workspace["workspace_name"]
        config_path = write_workspace_config(workspace, ws_name)
        generate_structured_context({**scan, **workspace})
        print(f"\n  {_GREEN}✓{_RESET} workspace config → {config_path}")

        # Write role blocks into agent directive files
        for agent_name, role_desc in roles.items():
            fname_map = {"claude": "CLAUDE.md", "agy": "GEMINI.md",
                         "grok": "GROK.md", "codex": "AGENTS.md"}
            fname = fname_map.get(agent_name)
            if fname and os.path.exists(fname):
                try:
                    _upsert_harness_fence(
                        fname,
                        harness_version="wizard",
                        body=f"## Your Role\n{role_desc}\n",
                    )
                    print(f"  {_GREEN}✓{_RESET} wrote role to {fname}")
                except Exception:
                    pass


def init(force: bool = False, agents: list = None,
         org: str = None, repo: str = None, project_id: str = None,
         mode: str = "solo") -> None:
    """Progressive wizard: semantic scan → agent discovery → doc bootstrap → nudge."""

    def _print_step(n: int, label: str) -> None:
        print(f"\n{_BOLD}{_CYAN}Step {n}/{_TOTAL_STEPS} — {label}{_RESET}")

    _TOTAL_STEPS = 6

    # ── Step 1: Detect existing state ──────────────────────────────────────
    _print_step(1, "Scanning repository")
    synlynk_exists = os.path.exists(".synlynk")
    if synlynk_exists and not force:
        print(f"  {_YELLOW}⚠ .synlynk/ already exists.{_RESET} "
              "Use --force to reinitialise.\n  Updating agent files only.")

    scan = _static_scan(".")
    print(f"  Project : {_BOLD}{scan['project_name']}{_RESET}")
    print(f"  Commits : {scan['commit_count']}")
    print(f"  Languages: {', '.join(scan['languages']) or 'unknown'}")
    if scan["recent_topics"]:
        print(f"  Recent  : {scan['recent_topics'][0]}")
    if not scan["has_structured_commits"] and scan["commit_count"] > 0:
        print(f"  {_DIM}⚠ Commit messages don't follow a structured convention — "
              "skeleton quality may be lower. Review generated docs before proceeding.{_RESET}")

    # ── Step 2: Agent discovery ─────────────────────────────────────────────
    _print_step(2, "Discovering agents")
    discovered = discover_agents()
    functional = [a for a in discovered if a["functional"]]
    non_functional = [a for a in discovered if not a["functional"]]

    if functional:
        print(f"\n  {_BOLD}{_GREEN}✨ Your Hybrid Workgroup is ready:{_RESET}")
        for ag in functional:
            roles = ", ".join(ag["roles"])
            print(f"    {_GREEN}✓ {ag['name']:10}{_RESET} {ag['version']}  "
                  f"roles: {roles}")
    else:
        print(f"  {_YELLOW}No agents detected. Install Claude, Gemini, or Codex to form your Hybrid Workgroup.{_RESET}")

    if non_functional:
        print(f"\n  {_DIM}Found but not configured (run --version failed):{_RESET}")
        for ag in non_functional:
            print(f"    {_DIM}✗ {ag['name']} — check API key / install{_RESET}")

    # ── Step 3: Create directories + write skeleton ─────────────────────────
    dd = _docs_dir()
    _print_step(3, f"Bootstrapping {dd}/")
    for d in [dd, os.path.join(dd, "devlogs"), ".synlynk",
              LOGS_DIR, PROMPTS_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

    written = _write_informed_skeleton(scan, skip_existing=not force)
    if written:
        for p, label in written:
            print(f"  {_GREEN}✓{_RESET} {p}  {_DIM}({label}){_RESET}")
    else:
        print(f"  {_DIM}All docs already exist — skipped (use --force to overwrite){_RESET}")

    # Write agent instruction files using _write_instruction_file().
    agent_set = set(agents) if agents is not None else {a["name"] for a in functional} or {"claude", "agy", "codex", "grok"}
    templates = _build_templates(org=org, repo=repo, project_id=project_id)

    # Core trio: only write if agent was discovered as functional.
    trio_content = {
        "CLAUDE.md":   (templates.get("CLAUDE.md", ""), "html"),
        "GEMINI.md":   (templates.get("GEMINI.md", ""), "html"),
        "AGENTS.md":   (templates.get("AGENTS.md", ""), "html"),
        "GROK.md":     (templates.get("GROK.md", ""), "html"),
    }
    _agent_guards = {"CLAUDE.md": "claude", "GEMINI.md": "agy", "AGENTS.md": "codex", "GROK.md": "grok"}
    for fname, (content, mstyle) in trio_content.items():
        required = _agent_guards[fname]
        if required not in agent_set:
            continue
        _write_instruction_file(fname, required, content, mstyle)

    # Extended targets: written based on environment detection.
    # Guards are sourced from _INSTRUCTION_TARGETS[i][3] (detection_fn).
    _target_detection = {fpath: fn for fpath, _, _, fn in _INSTRUCTION_TARGETS}
    extended = [
        (".cursor/rules/synlynk.mdc",       "cursor",    "none", _build_cursor_mdc()),
        (".github/copilot-instructions.md",  "copilot",   "html", _build_copilot_instructions()),
        (".windsurfrules",                   "windsurf",  "hash", _build_windsurf_rules()),
        ("AI_INSTRUCTIONS.md",              "universal",  "html", templates.get("AI_INSTRUCTIONS.md", "")),
    ]
    for fpath, tool, mstyle, content in extended:
        if _target_detection[fpath]():
            # marker_style='none' means synlynk owns the whole file — always overwrites
            _write_instruction_file(fpath, tool, content, mstyle)

    # Write manifest of all tracked files with their SHAs.
    manifest_entries = {}
    for fpath, tool, mstyle, _ in _INSTRUCTION_TARGETS:
        if not os.path.exists(fpath):
            continue
        file_content = open(fpath).read()
        section = _extract_synlynk_section(file_content, mstyle)
        if section is not None:
            manifest_entries[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}
    if manifest_entries:
        _write_instruction_manifest(manifest_entries)

    # Write config.json if needed.
    config_json_content = templates.get("config.json", "")
    if config_json_content:
        config_path = os.path.join(".synlynk", "config.json")
        if not os.path.exists(config_path) or force:
            with open(config_path, "w") as f:
                f.write(config_json_content)

    # ── Step 4: LLM enrichment offer ────────────────────────────────────────
    _print_step(4, "LLM enrichment (optional)")
    if functional:
        enricher = functional[0]
        print(f"  I found {scan['commit_count']} commits and {len(scan['recent_topics'])} "
              f"recent topics.\n  Want me to ask {enricher['name']} to synthesise a roadmap "
              f"from this? (costs tokens)")
        try:
            answer = input("  [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer == "y":
            print(f"  {_DIM}Calling {enricher['cli']} --print...{_RESET}", end=" ", flush=True)
            ok = _llm_enrich(enricher["name"], enricher["cli"], scan)
            print(f"{_GREEN}done{_RESET}" if ok else f"{_YELLOW}failed — keeping skeleton{_RESET}")
    else:
        print(f"  {_DIM}No functional agent available — skipping enrichment{_RESET}")

    # ── Step 5: Cloud directory nudge ────────────────────────────────────────
    _print_step(5, "Team & cloud setup (optional)")
    print("  Add a collaborator or share this workspace with your team.")
    print("  Leave blank to skip.")
    try:
        email = input("  Email or synlynk ID: ").strip()
    except EOFError:
        email = ""

    # Industry vertical
    inferred = _infer_industry()
    try:
        industry = input(f"  Industry vertical [{inferred}]: ").strip() or inferred
    except EOFError:
        industry = inferred
    if industry not in list(_INDUSTRY_KEYWORDS.keys()) + ["unknown"]:
        industry = "unknown"

    # ── Step 6: Finalise config ──────────────────────────────────────────────
    _print_step(6, "Finalising")
    synlynk_config_path = os.path.join("project-docs", ".synlynk_config.json")
    if not os.path.exists(synlynk_config_path) or force:
        config_data = {"mode": mode, "version": VERSION,
                       "init_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(synlynk_config_path, "w") as f:
            json.dump(config_data, f, indent=2)

    _update_config({
        "workgroup_agents": [a["name"] for a in functional],
        "workgroup_invite_email": email or None,
        "industry": industry,
    })

    set_state("stopped")

    print(f"\n{_BOLD}{_GREEN}✓ synlynk initialised — your Hybrid Workgroup is ready.{_RESET}")
    if functional:
        agent_names = " + ".join(a["name"] for a in functional)
        print(f"\n  {_BOLD}✨ Magic Moment 2 — dispatch agents now:{_RESET}")
        print(f"    {_CYAN}synlynk dispatch {functional[0]['name']} --task \"your task\"{_RESET}")
        if len(functional) >= 3:
            print(f"    {_CYAN}synlynk run --trio --task \"your task\"{_RESET}  "
                  f"← runs {agent_names} in parallel")
    print(f"\n  Next: {_DIM}synlynk status  ·  synlynk jobs  ·  synlynk dispatch --help{_RESET}\n")

_INSTALL_SCRIPT_URL = (
    "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh"
)


def _detect_install_type() -> str:
    """Returns 'pipx', 'pip', 'script', or 'unknown'."""
    try:
        import importlib.metadata as _meta

        loc = str(_meta.distribution("synlynk").locate_file(""))
        if "pipx" in loc:
            return "pipx"
        return "pip"
    except Exception:
        pass
    if os.path.exists(os.path.expanduser("~/.synlynk/bin/synlynk")):
        return "script"
    return "unknown"


def _run_upgrade(latest: str) -> None:
    print(f"  ✦ New version available: v{latest} — upgrading from v{VERSION}")
    install_type = _detect_install_type()
    if install_type == "pipx":
        result = subprocess.run(["pipx", "upgrade", "synlynk"], text=True)
        if result.returncode == 0:
            print(f"  ✓ Upgraded to v{latest} via pipx")
        else:
            print("  ⚠ pipx upgrade failed — run manually: pipx upgrade synlynk")
        return
    try:
        req = urllib.request.Request(
            _INSTALL_SCRIPT_URL, headers={"User-Agent": f"synlynk/{VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            script = resp.read().decode()
        result = subprocess.run(["bash", "-c", script], text=True)
        if result.returncode == 0:
            print(f"  ✓ Upgraded to v{latest}")
            print("  Restart your shell or run: source ~/.zshrc")
        else:
            print(f"  ⚠ Install script exited {result.returncode} — run manually:")
            print(f"  curl -sSL {_INSTALL_SCRIPT_URL} | bash")
    except Exception as e:
        print(f"  ⚠ Auto-install failed ({e}) — run manually:")
        print(f"  curl -sSL {_INSTALL_SCRIPT_URL} | bash")


def upgrade() -> None:
    """Checks GitHub releases for a newer version and auto-installs if one is found."""
    print(f"Checking for updates... (current: v{VERSION})")
    # Try gh CLI first — works for private repos and avoids unauthenticated rate limits.
    try:
        result = subprocess.run(
            ["gh", "api", "repos/nikhilsoman/synlynk/releases/latest", "--jq", ".tag_name"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            latest = result.stdout.strip().lstrip("v")
            if latest and latest != VERSION:
                _run_upgrade(latest)
            else:
                print(f"  ✓ You are on the latest version (v{VERSION}).")
            return
    except Exception:
        pass
    # Fall back to unauthenticated GitHub API (works for public repos).
    url = "https://api.github.com/repos/nikhilsoman/synlynk/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"synlynk/{VERSION}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get("tag_name", "").lstrip("v")
        if latest and latest != VERSION:
            _run_upgrade(latest)
        else:
            print(f"  ✓ You are on the latest version (v{VERSION}).")
    except Exception as e:
        print(f"  ⚠ Could not check for updates: {e}")
        print("  Check manually: https://github.com/nikhilsoman/synlynk/releases")

def exec_command(cmd_args: list, force: bool = False) -> int:
    if not cmd_args:
        print("Error: No command provided to exec.")
        return 1

    generate_context()
    cmd_args = _inject_grok_rules(cmd_args)
    check_budgets()

    if not _check_pre_exec_gate(force=force):
        return 1

    set_state("active")
    print(f"  Executing: {' '.join(cmd_args)}")
    start_time = time.time()
    exit_code = 0
    output_text = ""

    try:
        interactive = _is_interactive(cmd_args)
        if interactive:
            process = subprocess.Popen(cmd_args)
            process.wait()
            exit_code = process.returncode
        else:
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            buffer: list = []
            tee_thread = threading.Thread(target=_tee_process, args=(process, buffer))
            tee_thread.start()
            process.wait()
            tee_thread.join()
            exit_code = process.returncode
            output_text = "".join(buffer)
    except FileNotFoundError:
        exit_code = 127
        print(f"  Error: Command '{cmd_args[0]}' not found.")
    except Exception as e:
        exit_code = 1
        print(f"  Error: {e}")
    finally:
        duration = time.time() - start_time
        print(f"\n  ✓ Execution finished in {duration:.2f}s")

        in_tokens, out_tokens = extract_tokens(output_text)
        if in_tokens > 0:
            est_cost = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
            print(f"  ⚡ Tokens: {in_tokens:,} in / {out_tokens:,} out  |  est. ${est_cost:.4f}")
            update_costs(' '.join(cmd_args), in_tokens, out_tokens, duration)
        elif not _is_interactive(cmd_args):
            pass  # non-interactive but no tokens found — silent
        else:
            print("  ⚡ Token count unavailable (interactive mode)")

        _check_costs_freshness()
        log_telemetry_event({
            "type": "exec",
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "_ts": time.time(),
            "user": get_username(),
            "command": ' '.join(cmd_args),
            "duration": round(duration, 2),
            "exit_code": exit_code,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
        })
        check_sentinel_patterns(output_text=output_text, exit_code=exit_code,
                                cmd=' '.join(cmd_args))
        _check_instruction_drift()
        daemon = WatchDaemon()
        set_state("watching" if daemon._is_running() else "stopped")

    return exit_code

def main() -> None:
    _reconcile_jobs()
    parser = argparse.ArgumentParser(
        description="synlynk: The Universal Context Switchboard for AI Devs"
    )
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize synlynk in a repository")
    init_parser.add_argument("--force", action="store_true",
                             help="Overwrite existing template files")
    init_parser.add_argument("--agents", default="claude,agy,codex,grok",
                             help="Comma-separated agent set to generate files for (claude,agy,codex,grok)")
    init_parser.add_argument("--mode", choices=["solo", "team"], default="solo",
                             help="Project mode written to project-docs/.synlynk_config.json")
    init_parser.add_argument("--org", default=None,
                             help="GitHub organization name (stored in .synlynk/config.json)")
    init_parser.add_argument("--repo", default=None,
                             help="GitHub repository name (stored in .synlynk/config.json)")
    init_parser.add_argument("--project-id", default=None, dest="project_id",
                             help="GitHub Projects v2 node ID (fills TODO: PROJECT_ID in agent files)")
    init_parser.add_argument("--docs-dir", default=None, dest="docs_dir",
                             help="Directory for project docs (default: project-docs). "
                                  "Use '.' for repos that keep docs at the repo root.")
    init_parser.add_argument("--wizard", action="store_true",
                             help="Run the FTUE guided setup wizard")

    subparsers.add_parser("upgrade", help="Check for and apply updates")

    subparsers.add_parser("join", help="Onboard as a new member to an existing project")

    team_parser = subparsers.add_parser("team", help="Team status and management")
    team_sub = team_parser.add_subparsers(dest="team_action")
    team_sub.add_parser("status", help="Show team digest: members, stories, budget")

    decide_parser = subparsers.add_parser(
        "decide", help="Convene a multi-agent panel and optionally record a Decision"
    )
    decide_parser.add_argument("topic", help="Decision topic (quoted string)")
    decide_parser.add_argument(
        "--panel", required=True,
        help="Comma-separated agent names, e.g. claude,agy,codex"
    )
    decide_parser.add_argument(
        "--record", action="store_true",
        help="Write the Decision record to project-docs/decisions/"
    )

    scan_parser = subparsers.add_parser(
        "scan", help="Scan workspace environment (repos, harnesses, agents, skills)")
    scan_parser.add_argument("--deep", action="store_true",
                             help="Full source-tree walk: populate state.db + source-map.md")
    scan_parser.add_argument("--status", action="store_true",
                             help="Show source-skeleton cache status")
    scan_parser.add_argument("--refresh", action="store_true",
                             help="Re-run workspace scan on existing workspace")
    scan_parser.add_argument("--add", default=None, dest="add_path", metavar="PATH",
                             help="Add a repo path to the current workspace")
    scan_parser.add_argument("--remove", default=None, dest="remove_path", metavar="PATH",
                             help="Remove a repo path from the current workspace")
    scan_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                             help="Preview changes without writing")
    scan_parser.add_argument("--workspace", default=None, dest="workspace_name",
                             help="Workspace name (default: inferred from parent dir)")

    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate project-docs markdown into state.db and .synlynk/project-docs"
    )
    migrate_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                help="Preview migration without writing")
    migrate_parser.add_argument("--recover", action="store_true",
                                help="Re-import from .synlynk/project-docs")
    migrate_parser.add_argument("--setup-dr", action="store_true", dest="setup_dr",
                                help="Configure a DR sync path for mirroring")

    probe_parser = subparsers.add_parser(
        "probe", help="Probe agent harness capability and record compatibility"
    )
    probe_parser.add_argument("--agent", default=None,
                              help="Probe a single agent instead of all known agents")

    subparsers.add_parser("doctor", help="Run health checks on your synlynk installation")

    exit_parser = subparsers.add_parser(
        "exit", help="Remove synlynk from this repository (reversible via repair)")
    exit_parser.add_argument(
        "--confirm", action="store_true",
        help="Execute removal (default is dry-run)")
    exit_parser.add_argument(
        "--remove-docs", action="store_true", dest="remove_docs",
        help="Also remove project-docs/ directory (destructive)")

    repair_parser = subparsers.add_parser(
        "repair", help="Remove and re-initialize synlynk using current configuration")
    repair_parser.add_argument(
        "--confirm", action="store_true",
        help="Execute repair (default is dry-run)")

    sync_parser = subparsers.add_parser(
        "sync", help="Propagate updated synlynk artifacts without full re-init")
    sync_parser.add_argument(
        "--confirm", action="store_true",
        help="Execute sync (default is dry-run)")

    identity_parser = subparsers.add_parser("identity", help="Manage synlynk agent identity")
    identity_sub = identity_parser.add_subparsers(dest="identity_action")
    identity_sub.add_parser("init", help="Create local Ed25519 identity key")

    agent_parser = subparsers.add_parser("agent", help="Manage and run autopilot agents")
    agent_sub = agent_parser.add_subparsers(dest="agent_action")
    agent_configure_parser = agent_sub.add_parser(
        "configure", help="Interactively write .agents/<name>.json context profile"
    )
    agent_configure_parser.add_argument("name", help="Agent name: claude, agy, codex, grok")
    agent_run_parser = agent_sub.add_parser("run", help="Run a named agent once")
    agent_run_parser.add_argument("name", help="Agent name (matches .agents/<name>.json)")
    agent_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                  help="Collect signals and print findings; no dispatch/issue/PR")
    agent_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron",
                                  help="Install local crontab entry for this agent")
    agent_sub.add_parser("list", help="List .agents/ configs and last run status")

    exec_parser = subparsers.add_parser("exec", help="Execute an AI CLI with synlynk context")
    exec_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")
    exec_parser.add_argument("--force", action="store_true",
                             help="Bypass CRITICAL sentinel gate")

    watch_parser = subparsers.add_parser("watch", help="Manage the file watcher daemon")
    watch_parser.add_argument("action", choices=["start", "stop", "status"],
                              help="Daemon action")

    daemon_parser = subparsers.add_parser("daemon", help="Manage the always-on context daemon")
    daemon_parser.add_argument(
        "action", nargs="?", choices=["start", "stop", "status", "restart"],
        help="Daemon action"
    )
    daemon_parser.add_argument(
        "--install-service", action="store_true", dest="install_service",
        help="Register daemon with launchd (macOS) / systemd (Linux) / crontab (fallback)"
    )
    daemon_parser.add_argument(
        "--uninstall-service", action="store_true", dest="uninstall_service",
        help="Deregister daemon service"
    )

    subparsers.add_parser("checkpoint",
                          help="Archive done tasks, refresh context, emit telemetry")

    status_parser = subparsers.add_parser("status", help="Show project state dashboard")
    status_parser.add_argument("--json", action="store_true", dest="json_output",
                               help="Output machine-readable JSON")

    sentinel_parser = subparsers.add_parser("sentinel",
                                             help="View and manage sentinel alerts")
    sentinel_sub = sentinel_parser.add_subparsers(dest="sentinel_action")
    sentinel_sub.add_parser("list", help="List all active sentinel alerts")
    sentinel_clear_parser = sentinel_sub.add_parser("clear", help="Clear sentinel alerts")
    sentinel_clear_parser.add_argument("--severity",
                                       choices=["CRITICAL", "WARN", "INFO"],
                                       help="Clear only alerts of this severity")
    sentinel_clear_parser.add_argument("--code",
                                       help="Clear only alerts with this code")

    dispatch_parser = subparsers.add_parser(
        "dispatch", help="Dispatch an agent to run a task in the background")
    dispatch_parser.add_argument("agent",
        help="Agent name: claude, agy, codex")
    dispatch_parser.add_argument("--task", required=True,
        help="Task description for the agent")
    dispatch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story/task ID for context labelling")
    dispatch_parser.add_argument("--force-agent", action="store_true", dest="force_agent",
        help="Bypass capability routing — dispatch to the exact agent specified")
    dispatch_parser.add_argument(
        "--context-mode", choices=["none", "task", "full"], default="task",
        dest="context_mode", help="Context injection mode"
    )

    jobs_parser = subparsers.add_parser("jobs", help="List dispatched background jobs")
    jobs_parser.add_argument("--all", action="store_true", dest="all_jobs",
        help="Include completed and failed jobs")
    jobs_parser.add_argument("--watch", action="store_true",
        help="Refresh table every 2 seconds until Ctrl-C")

    relay_parser = subparsers.add_parser("relay", help="Relay event broker commands")
    relay_sub = relay_parser.add_subparsers(dest="relay_action")

    relay_start_p = relay_sub.add_parser("start", help="Start relay broker (foreground)")
    relay_start_p.add_argument("--port", type=int, default=None,
        help=f"Port to listen on (default: {SynlynkRelay.RELAY_PORT})")

    relay_broadcast_p = relay_sub.add_parser("broadcast", help="Send a broadcast event to the relay")
    relay_broadcast_p.add_argument("body", help="Message body")
    relay_broadcast_p.add_argument("--kind", default="message",
        choices=["motd", "wellness", "message", "joke", "custom"],
        help="Broadcast kind (default: message)")
    relay_broadcast_p.add_argument("--relay-url", default=None, dest="relay_url",
        help="Relay URL (default: http://localhost:27472)")

    logs_parser = subparsers.add_parser("logs", help="Tail the output log of a job")
    logs_parser.add_argument("--job", required=True, dest="job_id",
        help="Job ID (from `synlynk jobs`)")
    logs_parser.add_argument("--tail", type=int, default=50,
        help="Number of lines to show (default: 50)")

    shell_parser = subparsers.add_parser(
        "shell", help="Spawn a subshell with synlynk context injected")
    shell_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID to label the shell session")

    open_parser = subparsers.add_parser(
        "open", help="Open an agent CLI interactively with pre-loaded context")
    open_parser.add_argument("agent", help="Agent name: claude, agy, codex, grok")
    open_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")

    launch_parser = subparsers.add_parser(
        "launch", help="Pick your first task and dispatch it (FTUE task picker)")
    launch_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
        help="Print selected tasks without TUI or dispatching")
    launch_parser.add_argument("--list", action="store_true", dest="list_mode",
        help="Print full template pool with trigger conditions")

    run_parser = subparsers.add_parser(
        "run", help="Convenience wrappers for common dispatch patterns")
    run_sub = run_parser.add_subparsers(dest="run_action")
    trio_parser = run_sub.add_parser("--trio",
        help="Dispatch all functional agents in parallel (not the sequential Trio pipeline)")
    trio_parser.add_argument("--task", required=True,
        help="Task description sent to all agents")
    trio_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")

    story_parser = subparsers.add_parser("story", help="Manage stories")
    story_sub = story_parser.add_subparsers(dest="story_action")
    story_create_parser = story_sub.add_parser("create", help="Create a story")
    story_create_parser.add_argument("--title", required=True)
    story_create_parser.add_argument("--engg", default="unknown", dest="engg_domain")
    story_create_parser.add_argument("--org", default="unknown", dest="org_domain")
    story_create_parser.add_argument("--phase", default="build")
    story_create_parser.add_argument("--org-tags", nargs="*", default=[],
                                      dest="org_domain_tags",
                                      help="Secondary org domain tags (Tokq discoverability only)")
    story_create_parser.add_argument(
        "--tokens", type=int, default=None, dest="estimated_tokens",
        help="Estimated token budget (set by AI planner)"
    )
    story_sub.add_parser("list", help="List all stories")

    score_parser = subparsers.add_parser("score", help="Manage capability scores")
    score_sub = score_parser.add_subparsers(dest="score_action")
    score_add_parser = score_sub.add_parser("add", help="Add a human quality rating")
    score_add_parser.add_argument("story_id")
    score_add_parser.add_argument("rating", type=float)
    score_add_parser.add_argument("--note", default=None)
    score_add_parser.add_argument("--rework", action="store_true")
    score_list_parser = score_sub.add_parser("list", help="Show capability scores")
    score_list_parser.add_argument("--engg", default=None)
    score_list_parser.add_argument("--org", default=None)
    score_list_parser.add_argument("--industry", default=None)
    attest_parser = score_sub.add_parser("attest", help="Retroactively attest model version")
    attest_parser.add_argument("story_id")
    attest_parser.add_argument("--model", required=True)

    pr_parser = subparsers.add_parser("pr", help="PR workflow commands")
    pr_sub = pr_parser.add_subparsers(dest="pr_action")
    pr_sub.add_parser("check", help="Block PR if model versions are unattested")

    instructions_parser = subparsers.add_parser(
        "instructions", help="Manage synlynk instruction files across AI tools"
    )
    instructions_sub = instructions_parser.add_subparsers(dest="instructions_action")
    instructions_sub.add_parser("status", help="Show status of all tracked instruction files")
    instr_diff_parser = instructions_sub.add_parser(
        "diff", help="Show user/tool content outside synlynk sections"
    )
    instr_diff_parser.add_argument("file", nargs="?", default=None,
                                   help="Specific file to diff (default: all)")
    instr_update_parser = instructions_sub.add_parser(
        "update", help="Re-generate synlynk sections and refresh manifest"
    )
    instr_update_parser.add_argument("file", nargs="?", default=None,
                                     help="Specific file to update (default: all)")
    instr_ack_parser = instructions_sub.add_parser(
        "ack", help="Acknowledge an INSTRUCTION_DRIFT sentinel event"
    )
    instr_ack_parser.add_argument("file", help="File to acknowledge drift for")

    roles_parser = subparsers.add_parser(
        "roles", help="Show agent role table and directive file fence status")
    roles_parser.add_argument(
        "--fix", action="store_true",
        help="Write missing role fences into agent directive files")

    args = parser.parse_args()

    if args.command == "init":
        if getattr(args, "wizard", False):
            wizard_init()
        else:
            agents = [a.strip() for a in args.agents.split(",") if a.strip()]
            if getattr(args, "docs_dir", None):
                # Write docs_dir to config before init() runs so _docs_dir() picks it up
                os.makedirs(".synlynk", exist_ok=True)
                _update_config({"project_docs_dir": args.docs_dir})
            init(force=args.force, agents=agents, mode=args.mode,
                 org=args.org, repo=args.repo, project_id=args.project_id)
    elif args.command == "exec":
        force = getattr(args, 'force', False)
        sys.exit(exec_command(args.cmd, force=force))
    elif args.command == "upgrade":
        upgrade()
    elif args.command == "watch":
        daemon = WatchDaemon()
        if args.action == "start":
            daemon.start()
        elif args.action == "stop":
            daemon.stop()
        elif args.action == "status":
            daemon.status()
    elif args.command == "daemon":
        d = SynlynkDaemon()
        if getattr(args, "install_service", False):
            _daemon_install_service(d)
        elif getattr(args, "uninstall_service", False):
            _daemon_uninstall_service()
        else:
            action = getattr(args, "action", None) or "status"
            if action == "start":
                d.start()
            elif action == "stop":
                d.stop()
            elif action == "status":
                d.status()
            elif action == "restart":
                d.stop()
                d.start()
            else:
                daemon_parser.print_help()
    elif args.command == "checkpoint":
        checkpoint()
    elif args.command == "status":
        cmd_status(json_output=args.json_output)
    elif args.command == "sentinel":
        action = getattr(args, 'sentinel_action', None)
        if action == "clear":
            sentinel_clear(
                severity=getattr(args, 'severity', None),
                code=getattr(args, 'code', None),
            )
        else:
            sentinel_list()  # default: list
    elif args.command == "dispatch":
        try:
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 context_mode=getattr(args, "context_mode", "task"))
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "jobs":
        cmd_jobs(all_jobs=getattr(args, "all_jobs", False),
                 watch=getattr(args, "watch", False))
    elif args.command == "relay":
        action = getattr(args, "relay_action", None)
        if action == "start":
            cmd_relay_start(port=getattr(args, "port", None))
        elif action == "broadcast":
            cmd_relay_broadcast(
                kind=getattr(args, "kind", "message"),
                body=args.body,
                relay_url=getattr(args, "relay_url", None),
            )
        else:
            relay_parser.print_help()
    elif args.command == "logs":
        cmd_logs(args.job_id, tail=getattr(args, "tail", 50))
    elif args.command == "shell":
        cmd_shell(story_id=getattr(args, "story_id", None))
    elif args.command == "open":
        cmd_launch(args.agent, story_id=getattr(args, "story_id", None))
    elif args.command == "launch":
        cmd_launch_ftue(
            dry_run=getattr(args, "dry_run", False),
            list_mode=getattr(args, "list_mode", False),
        )
    elif args.command == "run":
        action = getattr(args, "run_action", None)
        if action == "--trio":
            cmd_run_trio(args.task, story_id=getattr(args, "story_id", None))
        else:
            run_parser.print_help()
    elif args.command == "story":
        if args.story_action == "create":
            cmd_story_create(args.title, args.engg_domain, args.org_domain, args.phase,
                             org_domain_tags=getattr(args, "org_domain_tags", []),
                             estimated_tokens=getattr(args, "estimated_tokens", None))
        elif args.story_action == "list":
            cmd_story_list()
    elif args.command == "score":
        if args.score_action == "add":
            cmd_score_add(args.story_id, args.rating, note=args.note, rework=args.rework)
        elif args.score_action == "list":
            cmd_score_list(engg=args.engg, org=args.org, industry=args.industry)
        elif args.score_action == "attest":
            cmd_score_attest(args.story_id, args.model)
    elif args.command == "pr":
        if args.pr_action == "check":
            cmd_pr_check()
    elif args.command == "instructions":
        action = getattr(args, "instructions_action", None)
        if action == "status" or action is None:
            cmd_instructions_status()
        elif action == "diff":
            cmd_instructions_diff(getattr(args, "file", None))
        elif action == "update":
            cmd_instructions_update(getattr(args, "file", None))
        elif action == "ack":
            cmd_instructions_ack(args.file)
        else:
            instructions_parser.print_help()
    elif args.command == "agent":
        action = getattr(args, "agent_action", None)
        if action == "configure":
            cmd_agent_configure(args.name)
        elif action == "run":
            cmd_agent_run(
                args.name,
                dry_run=getattr(args, "dry_run", False),
                install_cron=getattr(args, "install_cron", False),
            )
        elif action == "list":
            cmd_agent_list()
        else:
            agent_parser.print_help()
    elif args.command == "join":
        cmd_join()
    elif args.command == "team":
        action = getattr(args, "team_action", None)
        if action == "status" or action is None:
            cmd_team_status()
        else:
            team_parser.print_help()
    elif args.command == "decide":
        panel_members = [p.strip() for p in args.panel.split(",") if p.strip()]
        cmd_decide(args.topic, panel=panel_members, record=args.record)
    elif args.command == "scan":
        cmd_scan(
            deep=getattr(args, "deep", False),
            status=getattr(args, "status", False),
            refresh=getattr(args, "refresh", False),
            add_path=getattr(args, "add_path", None),
            remove_path=getattr(args, "remove_path", None),
            dry_run=getattr(args, "dry_run", False),
            workspace_name=getattr(args, "workspace_name", None),
        )
    elif args.command == "migrate":
        cmd_migrate(
            dry_run=getattr(args, "dry_run", False),
            recover=getattr(args, "recover", False),
            setup_dr=getattr(args, "setup_dr", False),
        )
    elif args.command == "probe":
        cmd_probe(agent=getattr(args, "agent", None))
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "roles":
        cmd_roles(fix=getattr(args, "fix", False))
    elif args.command == "exit":
        sys.exit(cmd_exit(dry_run=not args.confirm, remove_docs=args.remove_docs))
    elif args.command == "repair":
        sys.exit(cmd_repair(dry_run=not args.confirm))
    elif args.command == "sync":
        sys.exit(cmd_sync(dry_run=not args.confirm))
    elif args.command == "identity":
        action = getattr(args, "identity_action", None)
        if action == "init" or action is None:
            cmd_identity_init()
        else:
            identity_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
