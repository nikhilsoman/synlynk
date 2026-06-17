#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import time
import json
import re
import threading
import urllib.request
from typing import Optional
import sqlite3 as _sqlite3

VERSION = "0.4.1"

DB_PATH = ".synlynk/state/state.db"

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS stories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL UNIQUE,
    title         TEXT,
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
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_db(conn)
    return conn

def _migrate_db(conn: _sqlite3.Connection) -> None:
    """Idempotent schema migrations. Adds tables/views if absent."""
    conn.executescript(_DB_SCHEMA)
    try:
        conn.executescript(_DB_SCORES_VIEW)
    except _sqlite3.OperationalError:
        pass  # view already exists with same definition
    conn.commit()


def cmd_story_create(title: str, engg_domain: str = "unknown",
                     org_domain: str = "unknown", phase: str = "build",
                     org_domain_tags: list = None) -> str:
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
        "org_domain_tags, industry, phase) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, title, engg_domain, org_domain, tags_json, industry, phase)
    )
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Story created: {story_id}  [{engg_domain} · {org_domain} · {industry}]")
    return story_id

def cmd_story_list() -> None:
    """Prints all stories in state.db."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, title, engg_domain, org_domain, industry, phase, created_at "
        "FROM stories ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("  No stories yet. Use: synlynk story create --title '...'")
        return
    print(f"\n  {'ID':<14} {'Title':<30} {'Engg':<12} {'Org':<14} {'Industry':<12} Phase")
    print("  " + "-" * 90)
    for r in rows:
        print(f"  {r[0]:<14} {(r[1] or '')[:29]:<30} {r[2]:<12} {r[3]:<14} {r[4]:<12} {r[5]}")


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
        "roles": ["architect", "builder"],
        "strengths": ["long context", "reasoning", "code review", "planning"],
    },
    "codex": {
        "cli": "codex",
        "non_interactive_flags": [],
        "roles": ["builder"],
        "strengths": ["code completion", "inline edits", "fast iteration"],
    },
    "agy": {
        "cli": "agy",
        "non_interactive_flags": ["--quiet"],
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
}

# Default paths scanned for agent CLI config directories.
# Overridable in .synlynk/config.json under "agent_discovery_paths".
AGENT_DISCOVERY_DEFAULTS = {
    "claude": os.path.expanduser("~/.claude"),
    "codex": os.path.expanduser("~/.codex"),
    "agy": os.path.expanduser("~/.agy"),
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
    """Returns 'single' or 'team' from project-docs/.synlynk_config.json."""
    config_path = "project-docs/.synlynk_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f).get("mode", "single")
        except (json.JSONDecodeError, IOError):
            pass
    return "single"


def load_config() -> dict:
    """Loads .synlynk/config.json with schema-v1 defaults."""
    defaults = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "watch_interval_seconds": 30,
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex"},  # AGY CLI binary is named 'agy' — update when binary is renamed
        "team": None,
        "sync_endpoint": None,
        "exec_timeout_minutes": 30,
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


def _probe_model_version(agent_name: str, cli: str) -> str:
    """Tier 2: probe the agent's active model from its statusline before dispatch.

    Times out after 3s to avoid blocking dispatch.
    """
    probe_cmds = {
        "claude": [cli, "/status"],
        "agy":    [cli, "--version"],
        "codex":  [cli, "--version"],
    }
    cmd = probe_cmds.get(agent_name, [cli, "--version"])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        text = (result.stdout or "") + (getattr(result, "stderr", "") or "")
        patterns = [
            r"(claude-[\d.a-z-]*(?:opus|sonnet|haiku)[\w.-]*)",
            r"(agy-[\w.-]+)",
            r"(gemini-[\w.-]+)",
            r"(gpt-[\d.]+-[\w.-]+)",
            r"(codex-[\w-]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).lower()
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

    conn.execute(
        """INSERT INTO capability_ratings
           (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
            engg_domain, org_domain, industry, phase,
            signal_source, quality, quality_auto,
            verifier_agent, verifier_model,
            test_pass_rate, build_success,
            dispatch_rework, micro_rework,
            duration_vs_estimate, verified_by_ci, correct)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
         engg_domain, org_domain, industry, phase,
         signal_source, quality, quality_auto,
         verifier_agent_val, verifier_model,
         signals["test_pass_rate"], 1 if signals["build_success"] else 0,
         dispatch_rework, micro_rework,
         None, None, correct)
    )
    conn.commit()
    conn.close()


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


def _reconcile_jobs() -> None:
    """Probes PIDs of running jobs; marks unreachable ones as failed or completed.

    Called on every synlynk invocation before any command runs.
    Prevents stale jobs surviving reboots or external kills.
    """
    jobs = _load_jobs()
    changed = False
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for job in jobs:
        if job.get("status") not in ("running",):
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


def _extract_synlynk_section(content: str, marker_style: str = "html") -> Optional[str]:
    """Return the text inside synlynk markers, or the whole content for marker_style='none'."""
    if marker_style == "none":
        return content
    if marker_style == "html":
        m = re.search(
            r'<!-- synlynk:start[^>]* -->(.*?)<!-- synlynk:end -->',
            content, re.DOTALL
        )
    else:  # hash
        m = re.search(
            r'# synlynk:start[^\n]*\n(.*?)\n# synlynk:end',
            content, re.DOTALL
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
        # Replace section between markers
        if marker_style == "html":
            pattern = r'<!-- synlynk:start[^>]* -->.*?<!-- synlynk:end -->'
        else:
            pattern = r'# synlynk:start[^\n]*\n.*?\n# synlynk:end'
        replacement = f"{start}\n{content}\n{end}"
        new_content = re.sub(pattern, replacement, existing, flags=re.DOTALL)
        with open(path, "w") as f:
            f.write(new_content)
        return True

    # Append block
    with open(path, "a") as f:
        f.write(f"\n{start}\n{content}\n{end}\n")
    return True


def _write_informed_skeleton(scan: dict, skip_existing: bool = True) -> list:
    """Writes project-docs skeleton informed by static scan results.

    Returns list of file paths written. Skips files that already exist
    when skip_existing=True. The wizard surfaces a caveat for repos
    without structured commits.
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

    roadmap_content = f"""\
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

    memory_content = f"""\
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

    todo_content = f"""\
# {name} — Todo

## Active Tasks
- [ ] Review and refine the generated roadmap.md <!-- id: 1 -->
- [ ] Review and update memory.md with actual decisions <!-- id: 2 -->
- [ ] Define first milestone in roadmap <!-- id: 3 -->

## Completed
"""

    files = {
        "project-docs/roadmap.md": roadmap_content,
        "project-docs/memory.md": memory_content,
        "project-docs/todo.md": todo_content,
    }

    written = []
    for path, content in files.items():
        if skip_existing and os.path.exists(path):
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        written.append(path)
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


def dispatch_agent(agent: str, task: str, story_id: str = None) -> dict:
    """Dispatches an agent to run a task in the background.

    Uses non-interactive agent mode (no PTY). Stdout captured to
    .synlynk/logs/<job_id>.log. Returns the job dict.
    Raises ValueError for unknown agent names.
    """
    if story_id:
        best = _best_agent_for_story(story_id)
        if best and best in AGENT_CAPABILITY_BASELINES:
            agent = best

    if agent not in AGENT_CAPABILITY_BASELINES:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")

    baselines = AGENT_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]
    model_at_dispatch = _probe_model_version(agent, cli)

    import hashlib as _hashlib
    job_id = "job-" + _hashlib.md5(
        f"{agent}{task}{time.time()}".encode()
    ).hexdigest()[:8]

    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    log_file = os.path.join(LOGS_DIR, f"{job_id}.log")
    prompt_file = os.path.join(PROMPTS_DIR, f"{job_id}.md")

    try:
        generate_context(scope="full")
    except Exception:
        pass
    context_path = ".synlynk/context.md"
    context_text = ""
    if os.path.exists(context_path):
        context_text = open(context_path).read()

    story_line = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""
    prompt = f"{context_text}{story_line}\n\n## Your Task\n{task}\n"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    cmd = [cli] + flags
    import shlex as _shlex
    cmd_str = " ".join(_shlex.quote(c) for c in cmd)
    shell_cmd = f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"

    proc = subprocess.Popen(
        ["sh", "-c", shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    job = {
        "id": job_id,
        "agent": agent,
        "story_id": story_id or "",
        "task": task,
        "pid": proc.pid,
        "log_file": log_file,
        "prompt_file": prompt_file,
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

    log_telemetry_event({"type": "dispatch", "agent": agent,
                         "story_id": story_id, "job_id": job_id})
    return job


def cmd_jobs(all_jobs: bool = False) -> None:
    """Prints active (and optionally completed) jobs."""
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
    costs_file = "project-docs/costs.md"
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
_SCAN_SKIP_DIRS = {".git", "node_modules", ".synlynk", "project-docs",
                   "__pycache__", ".venv", ".next", "dist", "build"}

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
    _agent_slots = agent_slots or {"claude": "claude", "agy": "agy", "codex": "codex"}  # AGY CLI binary is named 'agy' — update when binary is renamed

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
- Mark tasks `[x]` in project-docs/todo.md when complete — do NOT delete them
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
- Mark tasks `[x]` in `project-docs/todo.md` when complete — do not delete them
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
- Mark tasks `[x]` in `project-docs/todo.md` when complete — do not delete them
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
Mark tasks [x] in project-docs/todo.md when complete.
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
                    r'<!-- synlynk:start.*?<!-- synlynk:end -->', '', file_content, flags=re.DOTALL
                ).strip() if marker_style == "html" else re.sub(
                    r'# synlynk:start.*?# synlynk:end', '', file_content, flags=re.DOTALL
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
                r'<!-- synlynk:start.*?<!-- synlynk:end -->', '', file_content, flags=re.DOTALL
            ).strip()
        elif marker_style == "hash":
            user_content = re.sub(
                r'# synlynk:start.*?# synlynk:end', '', file_content, flags=re.DOTALL
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
    costs_file = "project-docs/costs.md"
    if not os.path.exists(costs_file):
        return
    if time.time() - os.path.getmtime(costs_file) > 3600:
        print("  ⚠ costs.md not updated this session — AI may have missed logging")

def _write_sentinel_alert(severity: str, code: str, message: str) -> None:
    """Appends a structured alert line to .synlynk/sentinel.md."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(".synlynk"):
        return
    existing = ""
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            existing = f.read()
    if "# Sentinel Alerts" not in existing:
        existing = "# Sentinel Alerts\n"
    ts = time.strftime('%Y-%m-%d %H:%M')
    line = f"- [{severity}] [{ts}] {code}: {message}\n"
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
    Tier 3 fallback: read default_model from .synlynk/config.json for the agent.
    Returns 'unknown' if neither source provides a value.
    """
    # Tier 1: structured header
    m = re.search(r"#\s*synlynk-meta.*?model_version\s*=\s*(\S+)", output_text,
                  re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

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
            break

    # All-passed shortcut: "X passed" with no failures mentioned
    if signals["test_pass_rate"] is None:
        m = re.search(r"(\d+)\s+passed", log_text, re.IGNORECASE)
        if m and "failed" not in log_text.lower() and "error" not in log_text.lower():
            signals["test_pass_rate"] = 1.0

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
    """Appends a cost row to project-docs/costs.md. Rates: $0.003/1K in, $0.015/1K out."""
    costs_file = "project-docs/costs.md"
    if not os.path.exists(costs_file):
        return
    est_cost = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    user = get_username()
    entry = (f"| {ts} | {user} | 1 | {in_tokens}/{out_tokens} "
             f"| ${est_cost:.4f} | exec: {short_cmd} |\n")
    with open(costs_file, "a") as f:
        f.write(entry)


def _is_interactive(cmd_args: list) -> bool:
    """Returns True if the command needs a real TTY (no stdout capture)."""
    NON_INTERACTIVE = ["--no-tty", "--output-format json", "--print",
                       "--non-interactive", "-p "]
    cmd_str = " ".join(cmd_args)
    return not any(flag in cmd_str for flag in NON_INTERACTIVE)


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


def generate_context(scope: str = "full") -> None:
    """Aggregates project-docs into .synlynk/context.md (active items only)."""
    docs_dir = "project-docs"
    context_file = ".synlynk/context.md"
    sentinel_file = ".synlynk/sentinel.md"

    if not os.path.exists(docs_dir):
        return

    if scope != "full":
        # TODO(v1.3.0): implement task-scoped context slices for sub-agent routing
        print(f"  ⚠ scope='{scope}' not yet implemented, falling back to full context")
        scope = "full"

    if not os.path.exists(".synlynk"):
        os.makedirs(".synlynk")

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

        # Active tasks only ([ ] lines)
        todo_path = os.path.join(docs_dir, "todo.md")
        if os.path.exists(todo_path):
            out.write("## Active Tasks\n")
            with open(todo_path) as f:
                for line in f:
                    if "- [ ]" in line:
                        out.write(line)
            out.write("\n---\n\n")

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
    username = get_username()
    todo_path = "project-docs/todo.md"
    devlog_path = f"project-docs/devlogs/{username}.md"

    # Collect completed tasks and remaining active lines
    completed, active_lines = [], []
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[x\]', line, re.IGNORECASE):
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[x\]\s*', '', line, flags=re.IGNORECASE).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    completed.append({"id": id_m.group(1) if id_m else None, "text": text})
                else:
                    active_lines.append(line)

    # Append completed tasks to devlog
    if completed:
        os.makedirs(os.path.dirname(devlog_path), exist_ok=True)
        with open(devlog_path, "a") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d')}\n### Completed (checkpoint)\n")
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
    _print_step(3, "Bootstrapping project-docs")
    for d in ["project-docs", "project-docs/devlogs", ".synlynk",
              LOGS_DIR, PROMPTS_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

    written = _write_informed_skeleton(scan, skip_existing=not force)
    if written:
        for p in written:
            print(f"  {_GREEN}✓{_RESET} Created {p}")
    else:
        print(f"  {_DIM}All project-docs already exist — skipped (use --force to overwrite){_RESET}")

    # Write agent instruction files using _write_instruction_file().
    agent_set = set(agents) if agents is not None else {a["name"] for a in functional} or {"claude", "agy", "codex"}
    templates = _build_templates(org=org, repo=repo, project_id=project_id)

    # Core trio: only write if agent was discovered as functional.
    trio_content = {
        "CLAUDE.md":   (templates.get("CLAUDE.md", ""), "html"),
        "GEMINI.md":   (templates.get("GEMINI.md", ""), "html"),
        "AGENTS.md":   (templates.get("AGENTS.md", ""), "html"),
    }
    _agent_guards = {"CLAUDE.md": "claude", "GEMINI.md": "agy", "AGENTS.md": "codex"}
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

def upgrade() -> None:
    """Checks GitHub releases for a newer version and prints upgrade instructions."""
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
                print(f"  ✦ New version available: v{latest}")
                print("  Upgrade: curl -sSL https://raw.githubusercontent.com/"
                      "nikhilsoman/synlynk/main/install.sh | bash")
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
            print(f"  ✦ New version available: v{latest}")
            print("  Upgrade: curl -sSL https://raw.githubusercontent.com/"
                  "nikhilsoman/synlynk/main/install.sh | bash")
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
    init_parser.add_argument("--agents", default="claude,agy,codex",
                             help="Comma-separated agent set to generate files for (claude,agy,codex)")
    init_parser.add_argument("--mode", choices=["solo", "team"], default="solo",
                             help="Project mode written to project-docs/.synlynk_config.json")
    init_parser.add_argument("--org", default=None,
                             help="GitHub organization name (stored in .synlynk/config.json)")
    init_parser.add_argument("--repo", default=None,
                             help="GitHub repository name (stored in .synlynk/config.json)")
    init_parser.add_argument("--project-id", default=None, dest="project_id",
                             help="GitHub Projects v2 node ID (fills TODO: PROJECT_ID in agent files)")

    subparsers.add_parser("upgrade", help="Check for and apply updates")

    exec_parser = subparsers.add_parser("exec", help="Execute an AI CLI with synlynk context")
    exec_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")
    exec_parser.add_argument("--force", action="store_true",
                             help="Bypass CRITICAL sentinel gate")

    watch_parser = subparsers.add_parser("watch", help="Manage the file watcher daemon")
    watch_parser.add_argument("action", choices=["start", "stop", "status"],
                              help="Daemon action")

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

    jobs_parser = subparsers.add_parser("jobs", help="List dispatched background jobs")
    jobs_parser.add_argument("--all", action="store_true", dest="all_jobs",
        help="Include completed and failed jobs")

    logs_parser = subparsers.add_parser("logs", help="Tail the output log of a job")
    logs_parser.add_argument("--job", required=True, dest="job_id",
        help="Job ID (from `synlynk jobs`)")
    logs_parser.add_argument("--tail", type=int, default=50,
        help="Number of lines to show (default: 50)")

    shell_parser = subparsers.add_parser(
        "shell", help="Spawn a subshell with synlynk context injected")
    shell_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID to label the shell session")

    launch_parser = subparsers.add_parser(
        "launch", help="Launch an agent CLI interactively with pre-loaded context")
    launch_parser.add_argument("agent", help="Agent name: claude, agy, codex")
    launch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")

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

    args = parser.parse_args()

    if args.command == "init":
        agents = [a.strip() for a in args.agents.split(",") if a.strip()]
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
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id)
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "jobs":
        cmd_jobs(all_jobs=getattr(args, "all_jobs", False))
    elif args.command == "logs":
        cmd_logs(args.job_id, tail=getattr(args, "tail", 50))
    elif args.command == "shell":
        cmd_shell(story_id=getattr(args, "story_id", None))
    elif args.command == "launch":
        cmd_launch(args.agent, story_id=getattr(args, "story_id", None))
    elif args.command == "run":
        action = getattr(args, "run_action", None)
        if action == "--trio":
            cmd_run_trio(args.task, story_id=getattr(args, "story_id", None))
        else:
            run_parser.print_help()
    elif args.command == "story":
        if args.story_action == "create":
            cmd_story_create(args.title, args.engg_domain, args.org_domain, args.phase,
                             org_domain_tags=getattr(args, "org_domain_tags", []))
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
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
