from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time

from synlynk.hud import CYCLES
from synlynk.taxonomy_standards import _taxonomy_label

_ORG_DOMAINS = (
    "personalization",
    "monetization",
    "adtech",
    "workflow",
    "analytics",
    "growth",
    "content",
    "platform",
    "identity",
)

_DISCIPLINES = (
    "architecture",
    "frontend",
    "backend",
    "data",
    "ml",
    "testing",
    "security",
    "devops",
    "docs",
)

_ROLES = ("architect", "dev", "pm", "tpm", "qa", "designer")
_STAGES = tuple(CYCLES)
_ORG_DOMAIN_DRIFT_MAP = {
    "developer_experience": "platform",
    "marketing": "growth",
}

_PROJECT_DOC_KEEP_N = 50

_GENERATORS_BY_FILENAME = {
    "todo.md": "_generate_todo_md",
    "roadmap.md": "_generate_roadmap_md",
    "memory.md": "_write_memory_md",
    "costs.md": "_generate_costs_md",
}


def _validate_enum_value(field_name: str, value: str, allowed: tuple[str, ...]) -> str:
    normalized = str(value).strip()
    if normalized not in allowed:
        allowed_list = ", ".join(allowed)
        raise ValueError(f"Invalid {field_name} {value!r}. Allowed values: {allowed_list}")
    return normalized


def _normalize_capability_tags(
    engg_domain: str | None,
    org_domain: str | None,
    *,
    discipline: str | None = None,
    role: str | None = None,
    stage: str | None = None,
) -> tuple[str, str, str, str, str]:
    if discipline is not None and engg_domain is not None and discipline != engg_domain:
        raise ValueError(
            "engg_domain and discipline must match while engg_domain remains the legacy alias"
        )

    discipline_value = discipline if discipline is not None else engg_domain
    if discipline_value is None:
        discipline_value = "backend"
    org_value = org_domain if org_domain is not None else "platform"
    role_value = role if role is not None else "dev"
    stage_value = stage if stage is not None else "open"

    discipline_value = _validate_enum_value("discipline", discipline_value, _DISCIPLINES)
    org_value = _validate_enum_value("org_domain", org_value, _ORG_DOMAINS)
    role_value = _validate_enum_value("role", role_value, _ROLES)
    stage_value = _validate_enum_value("stage", stage_value, _STAGES)
    return discipline_value, org_value, role_value, stage_value


def _resolve_workspace_root() -> str:
    """Return the git workspace root, falling back to the current directory."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return os.getcwd()


def _normalize_stack_tags(stack_tags: list) -> list:
    """Return a deduplicated list of stack tags with surrounding whitespace trimmed."""
    normalized = []
    seen = set()
    for tag in stack_tags or []:
        value = str(tag).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _detect_stack_tags(workspace_root: str = None) -> list:
    """Detect stack tags via the existing repository fingerprint helper."""
    from synlynk import fingerprint_stack

    root = workspace_root or _resolve_workspace_root()
    return _normalize_stack_tags(fingerprint_stack(root))

class MigrationImportError(RuntimeError):
    pass

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
            goal_m = re.search(r'<!--\s*goal:(\S+)\s*-->', line)
            goal_id = goal_m.group(1) if goal_m else None
            if title:
                title = re.sub(r'<!--\s*goal:\S+\s*-->', '', title).strip() or None
            status = ('shipped' if ('✅' in line or 'shipped' in line.lower()) else
                      'in_progress' if ('🚧' in line or 'in progress' in line.lower()) else 'planned')
            current_arc = {'version': version, 'title': title, 'status': status, 'goal_id': goal_id}
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
            for prefix in ("[est] ", "[est?] ", "[legacy] "):
                if v.startswith(prefix):
                    v = v[len(prefix):]
                    break
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

def _migrate_db(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations. Adds tables/views if absent."""
    from synlynk import AGENT_CAPABILITY_BASELINES, _DB_SCHEMA, _DB_SCORES_VIEW, _seed_verb_map
    conn.executescript(_DB_SCHEMA)
    story_cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    if "discipline" not in story_cols:
        try:
            conn.execute("ALTER TABLE stories ADD COLUMN discipline TEXT NOT NULL DEFAULT 'backend'")
        except sqlite3.OperationalError:
            pass
    if "role" not in story_cols:
        try:
            conn.execute("ALTER TABLE stories ADD COLUMN role TEXT NOT NULL DEFAULT 'dev'")
        except sqlite3.OperationalError:
            pass
    if "stage" not in story_cols:
        try:
            conn.execute("ALTER TABLE stories ADD COLUMN stage TEXT NOT NULL DEFAULT 'open'")
        except sqlite3.OperationalError:
            pass
    if "estimated_tokens" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN estimated_tokens INTEGER")
    if "actual_tokens" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN actual_tokens INTEGER")
    if "stack_tags" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN stack_tags TEXT DEFAULT '[]'")
    if "status" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
    if "goal_id" not in story_cols:
        try:
            conn.execute("ALTER TABLE stories ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)")
        except sqlite3.OperationalError:
            pass
    conn.execute(
        "UPDATE stories SET discipline = COALESCE(NULLIF(discipline, ''), NULLIF(engg_domain, ''), 'backend') "
        "WHERE discipline IS NULL OR discipline = ''"
    )
    conn.execute(
        "UPDATE stories SET role = COALESCE(NULLIF(role, ''), 'dev') "
        "WHERE role IS NULL OR role = ''"
    )
    conn.execute(
        "UPDATE stories SET stage = COALESCE(NULLIF(stage, ''), 'open') "
        "WHERE stage IS NULL OR stage = ''"
    )
    conn.execute(
        "UPDATE stories SET engg_domain = COALESCE(NULLIF(engg_domain, ''), discipline, 'backend') "
        "WHERE engg_domain IS NULL OR engg_domain = ''"
    )
    gc_cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    if "link_status" not in gc_cols:
        try:
            conn.execute(
                "ALTER TABLE goal_contributions ADD COLUMN link_status TEXT NOT NULL DEFAULT 'linked'"
            )
        except sqlite3.OperationalError:
            pass
    if "skip_reason" not in gc_cols:
        try:
            conn.execute("ALTER TABLE goal_contributions ADD COLUMN skip_reason TEXT")
        except sqlite3.OperationalError:
            pass
    daemon_job_cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    if "handoff_count" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN handoff_count INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    if "previous_agents" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN previous_agents TEXT")
        except sqlite3.OperationalError:
            pass
    if "dispatch_context" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN dispatch_context TEXT")
        except sqlite3.OperationalError:
            pass
    if "blocked_reason" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN blocked_reason TEXT")
        except sqlite3.OperationalError:
            pass
    if "context_mode" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN context_mode TEXT")
        except sqlite3.OperationalError:
            pass
    if "context_bytes" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN context_bytes INTEGER")
        except sqlite3.OperationalError:
            pass
    if "session_id" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN session_id TEXT")
        except sqlite3.OperationalError:
            pass
    if "agent_id" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN agent_id TEXT")
        except sqlite3.OperationalError:
            pass
    if "requires_gh_write" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN requires_gh_write INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    if "gh_write_target" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN gh_write_target TEXT")
        except sqlite3.OperationalError:
            pass
    if "gh_write_verified" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN gh_write_verified TEXT")
        except sqlite3.OperationalError:
            pass
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    if "session_id" not in cost_cols:
        try:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN session_id TEXT")
        except sqlite3.OperationalError:
            pass
    conn.execute("DROP VIEW IF EXISTS capability_scores")
    conn.executescript(_DB_SCORES_VIEW)
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
            synlynk_verb TEXT,
            verb_category TEXT,
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
        CREATE TABLE IF NOT EXISTS capability_watch (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_probe_at TEXT,
            last_green_probe_at TEXT,
            last_smoke_test_at TEXT,
            last_green_smoke_at TEXT
        );

        CREATE TABLE IF NOT EXISTS gh_write_capability (
            harness TEXT NOT NULL,
            mode TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unknown',
            checked_at TEXT,
            PRIMARY KEY (harness, mode, action)
        );

        CREATE TABLE IF NOT EXISTS capability_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            harness TEXT NOT NULL,
            failing_path TEXT NOT NULL,
            classification TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            detected_at TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO capability_watch (id, last_probe_at, last_green_probe_at, "
        "last_smoke_test_at, last_green_smoke_at) VALUES (1, NULL, NULL, NULL, NULL)"
    )
    harness_verb_cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_verb_map)")}
    if "verb" not in harness_verb_cols:
        try:
            conn.execute("ALTER TABLE harness_verb_map ADD COLUMN verb TEXT")
        except sqlite3.OperationalError:
            pass
    if "cycle_hint" not in harness_verb_cols:
        try:
            conn.execute("ALTER TABLE harness_verb_map ADD COLUMN cycle_hint TEXT")
        except sqlite3.OperationalError:
            pass
    if "support" not in harness_verb_cols:
        try:
            conn.execute("ALTER TABLE harness_verb_map ADD COLUMN support TEXT")
        except sqlite3.OperationalError:
            pass
    if "notes" not in harness_verb_cols:
        try:
            conn.execute("ALTER TABLE harness_verb_map ADD COLUMN notes TEXT")
        except sqlite3.OperationalError:
            pass
    if "updated_at" not in harness_verb_cols:
        try:
            conn.execute("ALTER TABLE harness_verb_map ADD COLUMN updated_at TEXT")
        except sqlite3.OperationalError:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycle_capability (
            agent_name    TEXT NOT NULL,
            cycle         TEXT NOT NULL,
            support       TEXT NOT NULL DEFAULT 'none',
            notes         TEXT,
            verb_count    INTEGER DEFAULT 0,
            full_count    INTEGER DEFAULT 0,
            partial_count INTEGER DEFAULT 0,
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (agent_name, cycle)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS harness_status (
            agent_name             TEXT PRIMARY KEY,
            attach_rate_24h        REAL DEFAULT 0.0,
            attach_point_in_time   INTEGER DEFAULT 0,
            adherence_score        REAL DEFAULT NULL,
            completion_rate_24h    REAL DEFAULT NULL,
            rescue_count_24h       INTEGER DEFAULT 0,
            output_velocity_p50    REAL DEFAULT NULL,
            installed_version      TEXT DEFAULT '',
            latest_version         TEXT DEFAULT NULL,
            plan_tier              TEXT DEFAULT 'unknown',
            plan_type              TEXT DEFAULT 'd2c',
            ctx_window_tokens      INTEGER DEFAULT NULL,
            read_budget_tokens     INTEGER DEFAULT NULL,
            write_budget_tokens    INTEGER DEFAULT NULL,
            tool_budget_count      INTEGER DEFAULT NULL,
            tc1_status             TEXT DEFAULT 'unknown',
            tc2_status             TEXT DEFAULT 'unknown',
            tc3_status             TEXT DEFAULT 'unknown',
            tc4_status             TEXT DEFAULT 'unknown',
            harness_compat_score   REAL DEFAULT NULL,
            last_probe_at          TEXT DEFAULT NULL,
            last_telemetry_at      TEXT DEFAULT NULL
        )
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
            story_id          TEXT REFERENCES stories(story_id),
            epic_id           INTEGER REFERENCES roadmap_arcs(id),
            phase_id          INTEGER REFERENCES roadmap_phases(id),
            total_cost_usd    REAL,
            api_equivalent_usd REAL,
            actual_usd        REAL,
            payment_mode      TEXT,
            notes             TEXT,
            cost_source       TEXT NOT NULL,
            estimate_basis    TEXT,
            job_id            TEXT,
            recorded_at       TEXT DEFAULT (datetime('now')),
            dispatch_context  TEXT,
            context_mode      TEXT,
            session_id        TEXT REFERENCES sessions(session_id)
        );
        CREATE TABLE IF NOT EXISTS remediation_actions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            agent       TEXT NOT NULL,
            target_file TEXT NOT NULL,
            exact_diff  TEXT NOT NULL,
            operator    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_remediation_actions_timestamp
            ON remediation_actions(timestamp);
        CREATE TABLE IF NOT EXISTS devlog_entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            author        TEXT NOT NULL,
            entry_date    TEXT NOT NULL,
            session_title TEXT,
            session_id    TEXT,
            goal_id       TEXT REFERENCES goals(goal_id),
            member_id     TEXT,
            body          TEXT NOT NULL,
            recorded_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_devlog_author ON devlog_entries(author);
        CREATE INDEX IF NOT EXISTS idx_devlog_date   ON devlog_entries(entry_date);
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id   TEXT PRIMARY KEY,
            topic         TEXT NOT NULL,
            date          TEXT NOT NULL,
            panel         TEXT NOT NULL,
            status        TEXT NOT NULL,
            inputs        TEXT NOT NULL,
            synthesis     TEXT NOT NULL,
            decision_text TEXT NOT NULL,
            signature     TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS members (
            member_id      TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            created_at     TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS member_aliases (
            alias      TEXT PRIMARY KEY,
            member_id  TEXT NOT NULL REFERENCES members(member_id),
            alias_type TEXT NOT NULL DEFAULT 'manual',
            added_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    devlog_cols = {row[1] for row in conn.execute("PRAGMA table_info(devlog_entries)")}
    if "session_id" not in devlog_cols:
        try:
            conn.execute("ALTER TABLE devlog_entries ADD COLUMN session_id TEXT")
        except sqlite3.OperationalError:
            pass
    if "member_id" not in devlog_cols:
        conn.execute("ALTER TABLE devlog_entries ADD COLUMN member_id TEXT")

    if "goal_id" not in devlog_cols:
        try:
            conn.execute("ALTER TABLE devlog_entries ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)")
        except sqlite3.OperationalError:
            pass

    conn.execute(
        "INSERT OR IGNORE INTO members (member_id, canonical_name) VALUES (?, ?)",
        ("nikhilsoman", "Nikhil Soman"),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO member_aliases (alias, member_id, alias_type) VALUES (?, ?, 'seed')",
        [("nikhil", "nikhilsoman"), ("nikhilsoman", "nikhilsoman")],
    )
    arc_cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    if "goal_id" not in arc_cols:
        try:
            conn.execute("ALTER TABLE roadmap_arcs ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)")
        except sqlite3.OperationalError:
            pass
    rating_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    for col, default in [("discipline", "backend"), ("role", "dev"), ("stage", "open")]:
        if col not in rating_cols:
            try:
                conn.execute(f"ALTER TABLE capability_ratings ADD COLUMN {col} TEXT NOT NULL DEFAULT '{default}'")
            except sqlite3.OperationalError:
                pass
    if "stack_tags" not in rating_cols:
        try:
            conn.execute("ALTER TABLE capability_ratings ADD COLUMN stack_tags TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass
    if "pr_number" not in rating_cols:
        try:
            conn.execute("ALTER TABLE capability_ratings ADD COLUMN pr_number INTEGER")
        except sqlite3.OperationalError:
            pass
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    for col, typedef in [
        ("story_id", "TEXT REFERENCES stories(story_id)"),
        ("epic_id", "INTEGER REFERENCES roadmap_arcs(id)"),
        ("phase_id", "INTEGER REFERENCES roadmap_phases(id)"),
    ]:
        if col not in cost_cols:
            try:
                conn.execute(f"ALTER TABLE cost_entries ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    for col in ("api_equivalent_usd", "actual_usd", "payment_mode"):
        if col not in cost_cols:
            typedef = "TEXT" if col == "payment_mode" else "REAL"
            try:
                conn.execute(f"ALTER TABLE cost_entries ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
    if "cost_source" not in cost_cols:
        conn.execute("ALTER TABLE cost_entries RENAME TO cost_entries_pre_provenance")
        conn.execute("""
            CREATE TABLE cost_entries (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date      TEXT NOT NULL,
                agent             TEXT,
                model             TEXT,
                input_tokens      INTEGER,
                output_tokens     INTEGER,
                cache_read_tokens INTEGER,
                story_id          TEXT REFERENCES stories(story_id),
                epic_id           INTEGER REFERENCES roadmap_arcs(id),
                phase_id          INTEGER REFERENCES roadmap_phases(id),
                total_cost_usd    REAL,
                api_equivalent_usd REAL,
                actual_usd        REAL,
                payment_mode      TEXT,
                notes             TEXT,
                cost_source       TEXT NOT NULL,
                estimate_basis    TEXT,
                job_id            TEXT,
                recorded_at       TEXT DEFAULT (datetime('now')),
                dispatch_context  TEXT
            )
        """)
        old_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries_pre_provenance)")}
        select_cols = ", ".join(
            c if c in old_cols else "NULL"
            for c in (
                "session_date",
                "agent",
                "model",
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "story_id",
                "epic_id",
                "phase_id",
                "total_cost_usd",
                "notes",
            )
        )
        conn.execute(f"""
            INSERT INTO cost_entries
                (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                 story_id, epic_id, phase_id, total_cost_usd, api_equivalent_usd, actual_usd,
                 payment_mode, notes, cost_source, estimate_basis, job_id, recorded_at)
            SELECT {select_cols}, NULL, NULL, NULL, 'legacy_unknown', NULL, NULL, recorded_at
            FROM cost_entries_pre_provenance
        """)
        conn.execute("DROP TABLE cost_entries_pre_provenance")
        cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    if "job_id" not in cost_cols:
        try:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN job_id TEXT")
        except sqlite3.OperationalError:
            pass
    if "dispatch_context" not in cost_cols:
        try:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN dispatch_context TEXT")
        except sqlite3.OperationalError:
            pass
    if "context_mode" not in cost_cols:
        try:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN context_mode TEXT")
        except sqlite3.OperationalError:
            pass
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cost_entries_job_id "
        "ON cost_entries(job_id) WHERE job_id IS NOT NULL"
    )
    conn.execute(
        "UPDATE capability_ratings SET discipline = COALESCE(NULLIF(discipline, ''), NULLIF(engg_domain, ''), 'backend') "
        "WHERE discipline IS NULL OR discipline = ''"
    )
    conn.execute(
        "UPDATE capability_ratings SET role = COALESCE(NULLIF(role, ''), 'dev') "
        "WHERE role IS NULL OR role = ''"
    )
    conn.execute(
        "UPDATE capability_ratings SET stage = COALESCE(NULLIF(stage, ''), 'open') "
        "WHERE stage IS NULL OR stage = ''"
    )
    for table in ("stories", "capability_ratings"):
        valid_org_values = set(_ORG_DOMAINS) | set(_ORG_DOMAIN_DRIFT_MAP) | {"unknown"}
        placeholders = ", ".join("?" for _ in valid_org_values)
        unknown_rows = [
            row[0]
            for row in conn.execute(
                f"SELECT DISTINCT org_domain FROM {table} "
                f"WHERE org_domain IS NOT NULL AND org_domain NOT IN ({placeholders})",
                tuple(valid_org_values),
            ).fetchall()
            if row[0]
        ]
        for old_value, new_value in _ORG_DOMAIN_DRIFT_MAP.items():
            conn.execute(
                f"UPDATE {table} SET org_domain=? WHERE org_domain=?",
                (new_value, old_value),
            )
        conn.execute(
            f"UPDATE {table} SET org_domain='unknown' "
            f"WHERE org_domain IS NULL OR org_domain = '' OR org_domain NOT IN ({placeholders})",
            tuple(valid_org_values),
        )
        if unknown_rows:
            print(
                f"  ⚠ {table} org_domain values remapped to unknown: "
                + ", ".join(sorted(set(unknown_rows)))
            )
    # BS-22 introduced erroneous cycle renames; delete any rows with the wrong names
    # so they don't block migration on databases that ran the bad migration.
    for sql in [
        "DELETE FROM cycle_capability WHERE cycle IN ('design','build','sustain')",
    ]:
        try:
            conn.execute(sql)
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            pass
    cycle_remap = {
        "dream": "goal", "design": "visualize", "plan": "open",
        "work": "execute", "build": "execute", "ship": "release",
        "maintain": "sustain", "engage": "execute",
    }
    for old, new in cycle_remap.items():
        try:
            conn.execute(
                "UPDATE cycle_capability SET cycle=? WHERE cycle=?",
                (new, old)
            )
        except sqlite3.IntegrityError:
            # A row for (agent_name, new) already exists — the old-named row
            # is a stale duplicate now that both map to the same cycle.
            conn.execute("DELETE FROM cycle_capability WHERE cycle=?", (old,))
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
    # #141: agent_quotas base table (also in _DB_SCHEMA; re-assert for older DBs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_quotas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            agent        TEXT NOT NULL,
            model        TEXT NOT NULL DEFAULT 'unknown',
            quota_type   TEXT NOT NULL,
            unit         TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL,
            used_tokens  INTEGER NOT NULL DEFAULT 0,
            reset_at     TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent, model, quota_type, unit)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pr_multiplier_applied (
            pr_number  INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_quotas_agent ON agent_quotas(agent)"
    )
    # Quota-aware dispatch reservation: agent_reservations base table
    # (also in _DB_SCHEMA; re-assert for older DBs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_reservations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            harness        TEXT NOT NULL,
            tokens         INTEGER NOT NULL,
            scope          TEXT NOT NULL,
            scope_id       TEXT,
            job_id         TEXT,
            status         TEXT NOT NULL DEFAULT 'open',
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            released_at    TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_reservations_harness "
        "ON agent_reservations(harness, status)"
    )
    quota_cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_quotas)")}
    if quota_cols and "unit" not in quota_cols:
        try:
            conn.execute(
                "ALTER TABLE agent_quotas ADD COLUMN unit TEXT NOT NULL DEFAULT 'tokens'"
            )
        except sqlite3.OperationalError:
            pass
    if quota_cols and "model" not in quota_cols:
        try:
            conn.execute(
                "ALTER TABLE agent_quotas ADD COLUMN model TEXT NOT NULL DEFAULT 'unknown'"
            )
        except sqlite3.OperationalError:
            pass
    # #141 follow-up: fleet scheduler columns on stories
    for _col, _typedef in [
        ("priority", "INTEGER NOT NULL DEFAULT 5"),
        ("readiness", "TEXT NOT NULL DEFAULT 'draft'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE stories ADD COLUMN {_col} {_typedef}")
        except Exception:
            pass  # column already exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_grants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent           TEXT NOT NULL,
            face_value_usd  REAL NOT NULL,
            remaining_usd   REAL NOT NULL,
            granted_at      TEXT NOT NULL,
            expires_at      TEXT,
            note            TEXT
        )
    """)
    # Fleet operability matrix (Supported / Proven tracking)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fleet_matrix_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            tier INTEGER NOT NULL,
            home TEXT NOT NULL,
            cell TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT,
            cost_usd REAL NOT NULL DEFAULT 0,
            ts TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fleet_matrix_runs_lookup
            ON fleet_matrix_runs(home, cell, tier, ts);
    """)
    # capability-sweep-taxonomy: crosswalk legacy free-text values to NAICS/APQC/SFIA codes
    from synlynk.taxonomy_standards import (
        LEGACY_DISCIPLINE_CROSSWALK,
        LEGACY_ORG_DOMAIN_CROSSWALK,
        LEGACY_INDUSTRY_CROSSWALK,
    )
    # capability-sweep-taxonomy: one-time gate so the crosswalk only ever
    # rewrites pre-migration legacy data, not fresh rows written afterward
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _taxonomy_crosswalk_state ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), completed INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO _taxonomy_crosswalk_state (id, completed) VALUES (1, 0)"
    )
    already_done = conn.execute(
        "SELECT completed FROM _taxonomy_crosswalk_state WHERE id = 1"
    ).fetchone()[0]
    for table in ("stories", "capability_ratings"):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "legacy_unmapped" not in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN legacy_unmapped INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

    if not already_done:
        for table, col, crosswalk in (
            ("stories", "discipline", LEGACY_DISCIPLINE_CROSSWALK),
            ("stories", "org_domain", LEGACY_ORG_DOMAIN_CROSSWALK),
            ("stories", "industry", LEGACY_INDUSTRY_CROSSWALK),
            ("capability_ratings", "discipline", LEGACY_DISCIPLINE_CROSSWALK),
            ("capability_ratings", "org_domain", LEGACY_ORG_DOMAIN_CROSSWALK),
            ("capability_ratings", "industry", LEGACY_INDUSTRY_CROSSWALK),
        ):
            for legacy_value, code in crosswalk.items():
                conn.execute(
                    f"UPDATE {table} SET {col}=?, legacy_unmapped=0 WHERE {col}=?",
                    (code, legacy_value),
                )
            known_codes = set(crosswalk.values())
            rows = conn.execute(f"SELECT DISTINCT {col} FROM {table}").fetchall()
            for (value,) in rows:
                if value is not None and value not in known_codes and value not in crosswalk:
                    conn.execute(
                        f"UPDATE {table} SET legacy_unmapped=1 WHERE {col}=? AND legacy_unmapped=0",
                        (value,),
                    )
        conn.execute(
            "UPDATE _taxonomy_crosswalk_state SET completed = 1 WHERE id = 1"
        )
    conn.commit()
    _seed_verb_map(conn)


_VALID_COST_SOURCES = {
    "actual",
    "estimated_token_rate",
    "estimated_tshirt",
    "estimated_manual",
    "legacy_unknown",
}


def _insert_cost_row(
    session_date: str,
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cost_source: str,
    total_cost_usd: float,
    notes: str = None,
    story_id: str = None,
    epic_id: int = None,
    phase_id: int = None,
    estimate_basis: str = None,
    job_id: str = None,
    api_equivalent_usd: float = None,
    actual_usd: float = None,
    payment_mode: str = None,
    dispatch_context: str = None,
    context_mode: str = None,
    session_id: str = None,
) -> None:
    """Insert or update a cost_entries row through the single sanctioned path."""
    from synlynk import _get_db

    if cost_source not in _VALID_COST_SOURCES:
        raise ValueError(
            f"Invalid cost_source: {cost_source!r}, must be one of {_VALID_COST_SOURCES}"
        )

    # Distinguish home vs headless dispatch context; detection logic itself is future work (issue #740).
    if dispatch_context is None:
        dispatch_context = "unknown"

    conn = _get_db()
    try:
        # Inherit context_mode from the job row when the caller did not pass one
        # so cost rollups can segment by task/full/none without plumbing every path.
        if context_mode is None and job_id is not None:
            try:
                row = conn.execute(
                    "SELECT context_mode FROM daemon_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row and row[0]:
                    context_mode = row[0]
            except sqlite3.Error:
                pass
        if session_id is None and job_id is not None:
            try:
                row = conn.execute(
                    "SELECT session_id FROM daemon_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row and row[0]:
                    session_id = row[0]
            except sqlite3.Error:
                pass
        if job_id is not None:
            existing = conn.execute(
                "SELECT id FROM cost_entries WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE cost_entries SET
                        session_date=?,
                        agent=?,
                        model=?,
                        input_tokens=?,
                        output_tokens=?,
                        cache_read_tokens=?,
                        cost_source=?,
                        estimate_basis=?,
                        total_cost_usd=?,
                        api_equivalent_usd=?,
                        actual_usd=?,
                        payment_mode=?,
                        notes=?,
                        story_id=?,
                        epic_id=?,
                        phase_id=?,
                        dispatch_context=COALESCE(?, dispatch_context),
                        context_mode=COALESCE(?, context_mode),
                        session_id=COALESCE(?, session_id)
                    WHERE job_id=?""",
                    (
                        session_date,
                        agent,
                        model,
                        input_tokens,
                        output_tokens,
                        cache_read_tokens,
                        cost_source,
                        estimate_basis,
                        total_cost_usd,
                        api_equivalent_usd,
                        actual_usd,
                        payment_mode,
                        notes,
                        story_id,
                        epic_id,
                        phase_id,
                        dispatch_context,
                        context_mode,
                        session_id,
                        job_id,
                    ),
                )
                conn.commit()
                return
        conn.execute(
            """INSERT INTO cost_entries
                (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                 cost_source, estimate_basis, total_cost_usd, api_equivalent_usd, actual_usd, payment_mode, notes, story_id, epic_id, phase_id, job_id, dispatch_context, context_mode, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_date,
                agent,
                model,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cost_source,
                estimate_basis,
                total_cost_usd,
                api_equivalent_usd,
                actual_usd,
                payment_mode,
                notes,
                story_id,
                epic_id,
                phase_id,
                job_id,
                dispatch_context,
                context_mode,
                session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

def _migrate_import(docs_dir: str, dry_run: bool = False) -> None:
    """Parse flat files in docs_dir -> state.db. Prints import summary.

    Loud-fail (MigrationImportError) when a non-empty source lands zero new rows
    *and* none of the attempted rows already exist under their natural keys.
    Idempotent re-runs (INSERT OR IGNORE no-ops on already-present keys) are
    treated as success — see #276.
    """
    from synlynk import _get_db, _parse_costs_md, _parse_devlog_file, _parse_memory_md, _parse_roadmap_md, _parse_todo_metadata
    conn = _get_db()
    counts = {}
    inserted_counts = {}
    attempted_counts = {}
    # Rows whose natural key already exists — not a failure on re-run (#276).
    already_present_counts = {}

    memory_path = os.path.join(docs_dir, "memory.md")
    if os.path.exists(memory_path):
        with open(memory_path) as f:
            sections = _parse_memory_md(f.read())
        counts["memory_entries"] = len(sections)
        attempted_counts["memory_entries"] = len(sections)
        inserted_counts["memory_entries"] = 0
        already_present_counts["memory_entries"] = 0
        if not dry_run:
            for s in sections:
                try:
                    # Natural key: section title (cmd_memory_add treats it as unique).
                    existing = conn.execute(
                        "SELECT 1 FROM memory_entries WHERE section=? LIMIT 1",
                        (s["section"],),
                    ).fetchone()
                    if existing:
                        already_present_counts["memory_entries"] += 1
                        continue
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO memory_entries (section, body, author) VALUES (?,?,?)",
                        (s["section"], s["body"], s["author"]),
                    )
                    if getattr(cursor, "rowcount", 0) > 0:
                        inserted_counts["memory_entries"] += 1
                except Exception as e:
                    print(f"  ⚠ memory.md section skipped: {e}")

    roadmap_path = os.path.join(docs_dir, "roadmap.md")
    if os.path.exists(roadmap_path):
        with open(roadmap_path) as f:
            arcs, phases = _parse_roadmap_md(f.read())
        counts["roadmap_arcs"] = len(arcs)
        counts["roadmap_phases"] = len(phases)
        attempted_counts["roadmap_arcs"] = len(arcs)
        attempted_counts["roadmap_phases"] = len(phases)
        inserted_counts["roadmap_arcs"] = 0
        inserted_counts["roadmap_phases"] = 0
        already_present_counts["roadmap_arcs"] = 0
        already_present_counts["roadmap_phases"] = 0
        if not dry_run:
            for a in arcs:
                try:
                    # Natural key: version (UNIQUE on roadmap_arcs).
                    existing = conn.execute(
                        "SELECT 1 FROM roadmap_arcs WHERE version=? LIMIT 1",
                        (a["version"],),
                    ).fetchone()
                    if existing:
                        already_present_counts["roadmap_arcs"] += 1
                        continue
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO roadmap_arcs (version, title, status, goal_id) VALUES (?,?,?,?)",
                        (a["version"], a["title"], a["status"], a.get("goal_id")),
                    )
                    if getattr(cursor, "rowcount", 0) > 0:
                        inserted_counts["roadmap_arcs"] += 1
                except Exception as e:
                    print(f"  ⚠ roadmap arc skipped: {e}")
            for p in phases:
                try:
                    # Natural key: (arc_version, phase_title).
                    existing = conn.execute(
                        "SELECT 1 FROM roadmap_phases "
                        "WHERE arc_version=? AND phase_title=? LIMIT 1",
                        (p["arc_version"], p["phase_title"]),
                    ).fetchone()
                    if existing:
                        already_present_counts["roadmap_phases"] += 1
                        continue
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO roadmap_phases "
                        "(arc_version, phase_title, status, priority) VALUES (?,?,?,?)",
                        (p["arc_version"], p["phase_title"], p["status"], p["priority"]),
                    )
                    if getattr(cursor, "rowcount", 0) > 0:
                        inserted_counts["roadmap_phases"] += 1
                except Exception as e:
                    print(f"  ⚠ roadmap phase skipped: {e}")

    costs_path = os.path.join(docs_dir, "costs.md")
    if os.path.exists(costs_path):
        with open(costs_path) as f:
            rows = _parse_costs_md(f.read())
        counts["cost_entries"] = len(rows)
        attempted_counts["cost_entries"] = len(rows)
        inserted_counts["cost_entries"] = 0
        already_present_counts["cost_entries"] = 0
        if not dry_run:
            for r in rows:
                try:
                    # Legacy cost rows have no stable unique key (job_id is null).
                    # Match a prior import by the flat-file fingerprint fields.
                    existing = conn.execute(
                        "SELECT 1 FROM cost_entries "
                        "WHERE session_date=? AND IFNULL(agent,'')=IFNULL(?, '') "
                        "AND IFNULL(model,'')=IFNULL(?, '') "
                        "AND IFNULL(input_tokens, -1)=IFNULL(?, -1) "
                        "AND IFNULL(output_tokens, -1)=IFNULL(?, -1) "
                        "AND IFNULL(notes,'')=IFNULL(?, '') "
                        "LIMIT 1",
                        (
                            r["session_date"],
                            r["agent"],
                            r["model"],
                            r["input_tokens"],
                            r["output_tokens"],
                            r["notes"],
                        ),
                    ).fetchone()
                    if existing:
                        already_present_counts["cost_entries"] += 1
                        continue
                    cursor = conn.execute(
                        """INSERT INTO cost_entries
                           (session_date, agent, model, input_tokens, output_tokens,
                            cache_read_tokens, story_id, epic_id, phase_id,
                            total_cost_usd, notes, cost_source, estimate_basis, job_id)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            r["session_date"],
                            r["agent"],
                            r["model"],
                            r["input_tokens"],
                            r["output_tokens"],
                            r["cache_read_tokens"],
                            r.get("story_id"),
                            r.get("epic_id"),
                            r.get("phase_id"),
                            r["total_cost_usd"],
                            r["notes"],
                            "legacy_unknown",
                            None,
                            None,
                        ),
                    )
                    if getattr(cursor, "rowcount", 0) > 0:
                        inserted_counts["cost_entries"] += 1
                except Exception as e:
                    print(f"  ⚠ cost row skipped: {e}")

    devlogs_dir = os.path.join(docs_dir, "devlogs")
    devlog_count = 0
    inserted_counts["devlog_entries"] = 0
    attempted_counts["devlog_entries"] = 0
    already_present_counts["devlog_entries"] = 0
    if os.path.isdir(devlogs_dir):
        for fname in sorted(os.listdir(devlogs_dir)):
            if not fname.endswith(".md") or fname == "README.md":
                continue
            author = fname[:-3]
            with open(os.path.join(devlogs_dir, fname)) as f:
                entries = _parse_devlog_file(f.read(), author)
            devlog_count += len(entries)
            attempted_counts["devlog_entries"] += len(entries)
            if not dry_run:
                for e in entries:
                    try:
                        # Natural key: author + date + session title.
                        existing = conn.execute(
                            "SELECT 1 FROM devlog_entries "
                            "WHERE author=? AND entry_date=? "
                            "AND IFNULL(session_title,'')=IFNULL(?, '') "
                            "LIMIT 1",
                            (e["author"], e["entry_date"], e["session_title"]),
                        ).fetchone()
                        if existing:
                            already_present_counts["devlog_entries"] += 1
                            continue
                        cursor = conn.execute(
                            "INSERT OR IGNORE INTO devlog_entries "
                            "(author, entry_date, session_title, body) VALUES (?,?,?,?)",
                            (e["author"], e["entry_date"], e["session_title"], e["body"]),
                        )
                        if getattr(cursor, "rowcount", 0) > 0:
                            inserted_counts["devlog_entries"] += 1
                    except Exception as ex:
                        print(f"  ⚠ devlog entry skipped ({fname}): {ex}")
    counts["devlog_entries"] = devlog_count

    if not dry_run:
        _import_todo_to_stories(docs_dir, conn=conn)

    todo_path = os.path.join(docs_dir, "todo.md")
    todo_sync_count = 0
    inserted_counts["todo_metadata"] = 0
    attempted_counts["todo_metadata"] = 0
    already_present_counts["todo_metadata"] = 0
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            meta_rows = _parse_todo_metadata(f.read())
        todo_sync_count = len(meta_rows)
        if not dry_run:
            for m in meta_rows:
                if not m["gh_issue"]:
                    continue
                attempted_counts["todo_metadata"] += 1
                try:
                    existing = conn.execute(
                        "SELECT gh_issue FROM stories WHERE story_id=?",
                        (m["story_id"],),
                    ).fetchone()
                    if existing is not None and existing[0] == m["gh_issue"]:
                        already_present_counts["todo_metadata"] += 1
                        continue
                    cursor = conn.execute(
                        "UPDATE stories SET gh_issue=? WHERE story_id=?",
                        (m["gh_issue"], m["story_id"]),
                    )
                    if getattr(cursor, "rowcount", 0) > 0:
                        inserted_counts["todo_metadata"] += 1
                except Exception as e:
                    print(f"  ⚠ todo.md story sync skipped ({m['story_id']}): {e}")
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

    if dry_run:
        return

    failures = []
    for key, parsed_total in counts.items():
        attempted_total = attempted_counts.get(key, parsed_total)
        inserted_total = inserted_counts.get(key, 0)
        already_total = already_present_counts.get(key, 0)
        # Genuine 0-of-N failure: rows were attempted, none inserted, and not every
        # attempted row was already present (idempotent no-op). #276
        if attempted_total > 0 and inserted_total == 0 and already_total < attempted_total:
            if key == "todo_metadata":
                failures.append(
                    f"{key} ({parsed_total} parsed, {attempted_total} attempted, 0 inserted)"
                )
            else:
                failures.append(f"{key} ({parsed_total} parsed/attempted, 0 inserted)")
    if failures:
        raise MigrationImportError(
            "0 rows inserted for non-empty source file(s): " + "; ".join(failures)
        )

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
    from synlynk import DB_PATH, _docs_dir, _get_project_root, _migrate_import, _synlynk_project_docs_dir
    import shutil as _shutil

    print(f"  DB path: {DB_PATH}")
    project_root = _get_project_root()

    if setup_dr:
        path = input(
            "DR sync folder path "
            "(e.g. ~/Library/Mobile Documents/com~apple~CloudDocs/synlynk): "
        ).strip()
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            print(f"  ✗ Path not found: {path}")
            return
        cfg_path = os.path.join(project_root, ".synlynk", "config.json")
        cfg = {}
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = json.load(f)
        cfg["dr_sync_path"] = path
        with open(cfg_path, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"  ✓ DR sync path set: {path}")
        return

    sentinel = os.path.join(project_root, ".synlynk", ".synlynk_migrated")

    if recover:
        backup_dir = _synlynk_project_docs_dir()
        if not os.path.isdir(backup_dir):
            print("  ✗ No backup at .synlynk/project-docs/ — cannot recover")
            return
        print("  ▶ Re-importing from .synlynk/project-docs/ ...")
        try:
            _migrate_import(backup_dir)
        except MigrationImportError as exc:
            print(f"  ✗ {exc}")
            raise SystemExit(1)
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

    backup_dir = _synlynk_project_docs_dir()
    from synlynk.rollback import rollback_checkpoint
    abs_db_path = os.path.abspath(DB_PATH)
    cwd = os.path.abspath(os.getcwd())
    db_path_for_rollback = DB_PATH
    if os.path.commonpath([abs_db_path, cwd]) == cwd:
        db_path_for_rollback = os.path.relpath(abs_db_path, cwd)
    untracked_paths = [
        db_path_for_rollback,
        f"{db_path_for_rollback}-wal",
        f"{db_path_for_rollback}-shm",
        f"{db_path_for_rollback}-journal",
        backup_dir,
        sentinel,
        docs_dir,
    ]

    try:
        with rollback_checkpoint(
            "migrate",
            untracked_paths=untracked_paths,
        ):
            print("  ▶ Importing flat files → state.db ...")
            try:
                _migrate_import(docs_dir)
            except MigrationImportError as exc:
                print(f"  ✗ {exc}")
                raise

            print(f"  ▶ Copying {docs_dir}/ → {backup_dir}/ ...")
            if os.path.exists(backup_dir):
                _shutil.rmtree(backup_dir)
            _shutil.copytree(docs_dir, backup_dir)

            _migrate_dr_mirror(backup_dir)

            subprocess.run(
                ["git", "rm", "--cached", "-r", "--quiet", docs_dir],
                check=True,
                stderr=subprocess.DEVNULL,
            )
            print(f"  ✓ git rm --cached {docs_dir}/")

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

            subprocess.run(["git", "add", ".gitignore"], check=True)
            subprocess.run(["git", "add", "-f", sentinel], check=True)
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
    except MigrationImportError:
        raise SystemExit(1)

def _generate_todo_md() -> None:
    """Writes todo.md as a generated view of stories.
    Post-migration: writes to .synlynk/project-docs/todo.md.
    Pre-migration: writes to project-docs/todo.md."""
    from synlynk import _docs_dir, _dr_sync, _get_db, _is_migrated, _synlynk_project_docs_dir
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


def _rotate_project_doc(file_stem: str, all_rows: list, keep_n: int = None) -> list:
    """Rotate older generated project-doc rows into archive files."""
    from synlynk import _docs_dir, _is_migrated, _synlynk_project_docs_dir

    n = keep_n if keep_n is not None else _PROJECT_DOC_KEEP_N
    if len(all_rows) <= n:
        return all_rows

    archived_rows = all_rows[:-n]
    live_rows = all_rows[-n:]

    base_dir = _synlynk_project_docs_dir() if _is_migrated() else _docs_dir()
    archive_dir = os.path.join(base_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    period = time.strftime("%Y-H%m")
    archive_filename = f"{file_stem}-{period}.md"
    archive_path = os.path.join(archive_dir, archive_filename)
    with open(archive_path, "a") as f:
        for row in archived_rows:
            f.write(str(row) + "\n")

    index_path = os.path.join(archive_dir, "INDEX.md")
    existing_index = ""
    if os.path.exists(index_path):
        with open(index_path) as f:
            existing_index = f.read()
    if archive_filename not in existing_index:
        with open(index_path, "a") as f:
            if not existing_index:
                f.write("# Archive Index\n\n")
            f.write(
                f"- [{archive_filename}]({archive_filename}) — {file_stem} entries older than the live window\n"
            )

    return live_rows


def _detect_hand_edit(filename: str) -> str | None:
    """Detect a genuine uncommitted hand-edit for a generated project doc."""
    from synlynk import _docs_dir, _is_migrated, _synlynk_project_docs_dir

    if _is_migrated():
        file_path = os.path.join(_synlynk_project_docs_dir(), filename)
    else:
        file_path = os.path.join(_docs_dir(), filename)
    if not os.path.exists(file_path):
        return None

    with open(file_path) as f:
        working_tree_content = f.read()

    committed_blob = None
    workspace_root = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(workspace_root, ".git")):
            rel_path = os.path.relpath(file_path, workspace_root).replace(os.sep, "/")
            try:
                proc = subprocess.run(
                    ["git", "show", f"HEAD:{rel_path}"],
                    cwd=workspace_root,
                    capture_output=True,
                    text=True,
                )
                if proc.returncode == 0:
                    committed_blob = proc.stdout
            except Exception:
                committed_blob = None
            break
        parent = os.path.dirname(workspace_root)
        if parent == workspace_root:
            break
        workspace_root = parent

    if committed_blob is not None and working_tree_content == committed_blob:
        return None

    generator_name = _GENERATORS_BY_FILENAME.get(filename)
    generator = globals().get(generator_name)
    if not callable(generator):
        return None

    try:
        generator()
        if os.path.exists(file_path):
            with open(file_path) as f:
                regenerated_content = f.read()
        else:
            regenerated_content = ""
    except Exception:
        regenerated_content = None
    finally:
        with open(file_path, "w") as f:
            f.write(working_tree_content)

    if regenerated_content is None:
        return None
    if working_tree_content == regenerated_content:
        return None
    return (
        f"⚠ hand-edit detected in {filename}: working-tree content differs from "
        "git HEAD and fresh regeneration output"
    )

def _generate_roadmap_md() -> None:
    """Writes roadmap.md as a generated view of roadmap_arcs/roadmap_phases.
    Post-migration: writes to .synlynk/project-docs/roadmap.md.
    Pre-migration: writes to project-docs/roadmap.md."""
    from synlynk import _docs_dir, _dr_sync, _get_db, _is_migrated, _synlynk_project_docs_dir
    if _is_migrated():
        roadmap_path = os.path.join(_synlynk_project_docs_dir(), "roadmap.md")
        os.makedirs(os.path.dirname(roadmap_path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        roadmap_path = os.path.join(docs_dir, "roadmap.md")

    conn = _get_db()
    arcs = conn.execute(
        "SELECT version, title, status, target_date, notes FROM roadmap_arcs ORDER BY id ASC"
    ).fetchall()
    phases_by_arc = {}
    for arc_version, phase_title, status, priority, story_id, notes in conn.execute(
        "SELECT arc_version, phase_title, status, priority, story_id, notes "
        "FROM roadmap_phases ORDER BY id ASC"
    ).fetchall():
        phases_by_arc.setdefault(arc_version, []).append((phase_title, status, priority, story_id, notes))
    conn.close()
    arcs = _rotate_project_doc("roadmap", arcs)

    lines = [
        "# Roadmap (generated - source of truth is state.db)\n",
        "# Edit via: synlynk roadmap add | Do NOT hand-edit this file\n\n",
    ]
    for version, title, status, target_date, notes in arcs:
        date_str = f" (target: {target_date})" if target_date else ""
        lines.append(f"## {version} — {title or version} [{status}]{date_str}\n\n")
        if notes:
            lines.append(f"{notes}\n\n")
        for phase_title, p_status, priority, story_id, p_notes in phases_by_arc.get(version, []):
            check = "x" if p_status == "done" else ("-" if p_status == "deferred" else " ")
            prio = f" ({priority})" if priority else ""
            story = f" <!-- story:{story_id} -->" if story_id else ""
            lines.append(f"- [{check}] {phase_title}{prio}{story}\n")
            if p_notes:
                lines.append(f"  {p_notes}\n")
        lines.append("\n")

    with open(roadmap_path, "w") as f:
        f.writelines(lines)

    if _is_migrated():
        _dr_sync("roadmap.md")

def _generate_costs_md() -> None:
    """Writes costs.md as a generated view of cost_entries.
    Post-migration: writes to .synlynk/project-docs/costs.md.
    Pre-migration: writes to project-docs/costs.md."""
    from synlynk import _docs_dir, _dr_sync, _get_db, _is_migrated, _synlynk_project_docs_dir
    if _is_migrated():
        costs_path = os.path.join(_synlynk_project_docs_dir(), "costs.md")
        os.makedirs(os.path.dirname(costs_path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        costs_path = os.path.join(docs_dir, "costs.md")

    conn = _get_db()
    cursor = conn.execute(
        "SELECT session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, story_id, notes FROM cost_entries ORDER BY id ASC"
    )
    rows = cursor.fetchall() if hasattr(cursor, "fetchall") else []
    conn.close()
    rows = _rotate_project_doc("costs", rows)

    lines = [
        "# Costs (generated - source of truth is state.db)\n",
        "# Edit via: synlynk cost log | Do NOT hand-edit this file\n\n",
        "| Date | Agent | Model | Tokens In | Tokens Out | Cost | Source | Story | Notes |\n",
        "|---|---|---|---|---|---|---|---|---|\n",
    ]
    for session_date, agent, model, input_tokens, output_tokens, total_cost_usd, cost_source, story_id, notes in rows:
        cost_str = f"${total_cost_usd:.4f}" if total_cost_usd is not None else "-"
        lines.append(
            f"| {session_date} | {agent} | {model or '-'} | {input_tokens} | {output_tokens} | "
            f"{cost_str} | {cost_source} | {story_id or '-'} | {notes or ''} |\n"
        )

    with open(costs_path, "w") as f:
        f.writelines(lines)

    if _is_migrated():
        _dr_sync("costs.md")

def _write_memory_md() -> None:
    """Regenerate memory.md from memory_entries table.
    Post-migration: writes to .synlynk/project-docs/memory.md.
    Pre-migration: writes to project-docs/memory.md."""
    from synlynk import _docs_dir, _get_db, _is_migrated, _synlynk_project_docs_dir

    if _is_migrated():
        path = os.path.join(_synlynk_project_docs_dir(), "memory.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        path = os.path.join(docs_dir, "memory.md")

    conn = _get_db()
    rows = conn.execute("SELECT section, body FROM memory_entries ORDER BY id").fetchall()
    conn.close()
    rows = _rotate_project_doc("memory", rows)
    lines = [
        "# synlynk Memory (generated - source of truth is state.db)\n",
        "# Edit via: synlynk memory add | Do NOT hand-edit this file\n\n",
    ]
    for section, body in rows:
        lines.append(f"## {section}\n\n{body}\n\n")
    with open(path, "w") as f:
        f.writelines(lines)

def cmd_memory_add(section: str, body: str, author: str = None) -> None:
    """Add or update a memory entry. Always writes through to the flat file;
    DR sync only fires once this repo is migrated."""
    from synlynk import _dr_sync, _get_db, _is_migrated
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
    _write_memory_md()
    if _is_migrated():
        _dr_sync("memory.md")

def _write_devlog_file(author: str) -> None:
    """Regenerate .synlynk/project-docs/devlogs/<author>.md from devlog_entries."""
    from synlynk import _get_db, _synlynk_project_docs_dir
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
                      session_title: str = None, session_id: str = None,
                      goal_id: str = None) -> None:
    """Append a devlog entry to DB and write through to flat file if migrated."""
    from synlynk import _dr_sync, _get_db, _is_migrated
    from synlynk.session import _read_active_session
    if session_id is None:
        session_id = _read_active_session()
    conn = _get_db()
    conn.execute(
        "INSERT INTO devlog_entries (author, entry_date, session_title, session_id, goal_id, body) "
        "VALUES (?,?,?,?,?,?)",
        (author, entry_date, session_title, session_id, goal_id, body)
    )
    conn.commit()
    conn.close()
    if _is_migrated():
        _write_devlog_file(author)
        _dr_sync(f"devlogs/{author}.md")

def _import_todo_to_stories(docs_dir: str = None, conn=None) -> int:
    """Reads checkbox lines from todo.md and inserts missing story rows."""
    from synlynk import _docs_dir, _get_db
    import hashlib as _hashlib

    if docs_dir is None:
        docs_dir = _docs_dir()
    todo_path = os.path.join(docs_dir, "todo.md")
    if not os.path.exists(todo_path):
        return 0

    owns_conn = conn is None
    if conn is None:
        conn = _get_db()

    def _fetchall(cursor):
        fetchall = getattr(cursor, "fetchall", None)
        if callable(fetchall):
            return fetchall()
        return []

    def _fetchone(cursor):
        fetchone = getattr(cursor, "fetchone", None)
        if callable(fetchone):
            return fetchone()
        return None

    existing_ids = {row[0] for row in _fetchall(conn.execute("SELECT story_id FROM stories"))}
    checkbox_status = {
        " ": "open",
        "x": "done",
        "-": "deferred",
        "~": "superseded",
        ">": "absorbed",
    }

    imported = 0
    with open(todo_path) as f:
        for line in f:
            checkbox_match = re.match(r"\s*-\s*\[(?P<mark>[ x\-~>])\]\s*(?P<body>.+?)\s*$", line)
            if not checkbox_match:
                continue
            mark = checkbox_match.group("mark")
            status = checkbox_status.get(mark)
            if status is None:
                continue
            id_match = re.search(r'<!--\s*id:(story-[\w-]+)\s*-->', line)
            if id_match and id_match.group(1) in existing_ids:
                continue

            title_match = re.match(
                r"(?P<title>.+?)(?:\s*\[.*?\])?(?:\s*<!--.*-->)?\s*$",
                checkbox_match.group("body"),
            )
            if not title_match:
                continue
            title = title_match.group("title").strip()
            story_id = (
                id_match.group(1)
                if id_match is not None
                else "story-" + _hashlib.md5(title.encode()).hexdigest()[:8]
            )
            if story_id in existing_ids:
                continue
            try:
                if _fetchone(conn.execute("SELECT 1 FROM stories WHERE title=?", (title,))):
                    continue
                conn.execute(
                    "INSERT INTO stories (story_id, title, status) VALUES (?, ?, ?)",
                    (story_id, title, status),
                )
                imported += 1
                existing_ids.add(story_id)
            except sqlite3.IntegrityError:
                pass
            except Exception as e:
                print(f"  ⚠ todo.md story import skipped ({story_id}): {e}")

    if owns_conn:
        conn.commit()
        conn.close()
    return imported

def cmd_story_create(title: str, engg_domain: str = None,
                     org_domain: str = None, phase: str = "build",
                     org_domain_tags: list = None,
                     estimated_tokens: int = None,
                     stack_tags: list = None,
                     discipline: str = None,
                     role: str = None,
                     stage: str = None,
                     story_id: str = None) -> str:
    """Creates a story record in state.db. Returns the generated story_id."""
    from synlynk import _GREEN, _RESET, _generate_todo_md, _get_db, load_config
    import hashlib as _hashlib
    import json as _json
    if story_id is None:
        story_id = "story-" + _hashlib.md5(
            f"{title}{time.time()}".encode()
        ).hexdigest()[:8]
    config = load_config()
    industry = config.get("industry", "unknown")
    tags_json = _json.dumps(org_domain_tags or [])
    stack_tags_json = _json.dumps(_detect_stack_tags() if stack_tags is None else _normalize_stack_tags(stack_tags))
    discipline, org_domain, role, stage = _normalize_capability_tags(
        engg_domain,
        org_domain,
        discipline=discipline,
        role=role,
        stage=stage,
    )[0:4]
    if engg_domain is None:
        engg_domain = discipline
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, discipline, org_domain, role, stage, "
        "org_domain_tags, stack_tags, industry, phase, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, title, engg_domain, discipline, org_domain, role, stage,
         tags_json, stack_tags_json, industry, phase, estimated_tokens)
    )
    conn.commit()
    conn.close()
    _generate_todo_md()
    print(
        f"  {_GREEN}✓{_RESET} Story created: {story_id}  "
        f"[{_taxonomy_label('sfia', engg_domain)} · {_taxonomy_label('apqc', org_domain)} · {_taxonomy_label('naics', industry)}]"
    )
    return story_id

def cmd_roadmap_add(
    version: str,
    title: str = None,
    status: str = "planned",
    target_date: str = None,
    notes: str = None,
    phase_title: str = None,
    priority: str = None,
    story_id: str = None,
) -> None:
    """Add or update a roadmap arc, or a phase within an existing arc.

    If phase_title is None: create/update the arc row identified by `version`.
    If phase_title is set: add a phase to the arc `version` (which must already exist).
    """
    from synlynk import _GREEN, _RESET, _get_db

    conn = _get_db()
    try:
        arc_row = conn.execute(
            "SELECT version FROM roadmap_arcs WHERE version=?", (version,)
        ).fetchone()

        if phase_title is None:
            if arc_row:
                conn.execute(
                    "UPDATE roadmap_arcs SET title=?, status=?, target_date=?, notes=? WHERE version=?",
                    (title, status, target_date, notes, version),
                )
            else:
                conn.execute(
                    "INSERT INTO roadmap_arcs (version, title, status, target_date, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (version, title, status, target_date, notes),
                )
        else:
            if not arc_row:
                raise ValueError(f"no roadmap arc with version={version!r}; create it first")
            conn.execute(
                "INSERT INTO roadmap_phases (arc_version, phase_title, status, priority, story_id, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (version, phase_title, status, priority, story_id, notes),
            )
        conn.commit()
    finally:
        conn.close()

    _generate_roadmap_md()
    label = phase_title if phase_title else (title or version)
    print(f"  {_GREEN}✓{_RESET} Roadmap updated — {version}: {label}")

def cmd_story_list() -> None:
    """Prints all stories in state.db."""
    from synlynk import _get_db
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

def cmd_story_ready(story_id, all_stories: bool = False) -> None:
    """Marks one story (or every draft story, with all_stories=True) as ready
    for scheduling. Only 'ready' stories are candidates for synlynk schedule.

    Also records the story's current GOVERNS goal-link status at the plan
    approval checkpoint.
    """
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    if all_stories:
        ready_ids = [
            row[0]
            for row in conn.execute(
                "SELECT story_id FROM stories WHERE readiness='draft'"
            ).fetchall()
        ]
        cur = conn.execute("UPDATE stories SET readiness='ready' WHERE readiness='draft'")
        conn.commit()
        for sid in ready_ids:
            _record_goal_link_status(conn, sid)
        conn.close()
        print(f"  {_GREEN}✓{_RESET} Marked {cur.rowcount} draft stories ready")
        return
    if not story_id:
        conn.close()
        print("  Error: story_id required unless --all is given")
        return
    conn.execute("UPDATE stories SET readiness='ready' WHERE story_id=?", (story_id,))
    conn.commit()
    _record_goal_link_status(conn, story_id)
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Story {story_id} marked ready")


def _record_goal_link_status(conn, story_id: str) -> None:
    """Records the story's current primary goal-link status."""
    story = conn.execute(
        "SELECT goal_id FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    if not story:
        return

    primary_goal_id = story[0]
    secondary = conn.execute(
        "SELECT goal_id FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    if primary_goal_id:
        conn.execute(
            "INSERT OR IGNORE INTO goal_contributions "
            "(goal_id, story_id, link_status) VALUES (?, ?, 'linked')",
            (primary_goal_id, story_id),
        )
        conn.commit()
        return
    if secondary:
        return

    # The historical schema has a foreign-key reference, while the GOVERNS
    # checkpoint intentionally uses the literal 'none' sentinel.  Connections
    # opened by current synlynk enable FK enforcement, so briefly disable it
    # for this deliberate audit row and restore the connection setting after.
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(
            "INSERT OR IGNORE INTO goal_contributions "
            "(goal_id, story_id, link_status, skip_reason) "
            "VALUES ('none', ?, 'skipped', ?)",
            (story_id, "no active goal specified at plan-approval time"),
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def cmd_story_draft(story_id: str) -> None:
    """Reverts a story to draft, excluding it from scheduling until re-readied."""
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    conn.execute("UPDATE stories SET readiness='draft' WHERE story_id=?", (story_id,))
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Story {story_id} reverted to draft")

def cmd_story_done(story_id: str) -> None:
    """Marks a story done and emits a story_done event carrying its linked goal ids."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.events import emit_event
    conn = _get_db()
    story = conn.execute(
        "SELECT story_id, goal_id FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found.")
        return
    conn.execute("UPDATE stories SET status='done' WHERE story_id=?", (story_id,))
    conn.commit()
    goal_ids = []
    if story[1]:
        goal_ids.append(story[1])
    secondary = conn.execute(
        "SELECT goal_id FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    conn.close()
    goal_ids.extend(g[0] for g in secondary if g[0] not in goal_ids)
    emit_event(
        "story_done",
        {"story_id": story_id, "goal_ids": goal_ids},
        emitted_by="cmd_story_done",
    )
    print(f"  {_GREEN}✓{_RESET} Story {story_id} marked done")

def cmd_goal_create(outcome: str, criterion: str, deadline: str = None) -> str:
    """Creates a Business Goal record in state.db. Returns the generated goal_id."""
    from synlynk import _GREEN, _RESET, _get_db
    import hashlib as _hashlib
    goal_id = "goal-" + _hashlib.md5(
        f"{outcome}{time.time()}".encode()
    ).hexdigest()[:8]
    conn = _get_db()
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, deadline) VALUES (?, ?, ?, ?)",
        (goal_id, outcome, criterion, deadline)
    )
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Goal created: {goal_id}  [{outcome}]")
    return goal_id

def cmd_goal_list() -> None:
    """Prints all active goals in state.db."""
    from synlynk import _get_db
    conn = _get_db()
    rows = conn.execute(
        "SELECT goal_id, outcome, criterion, deadline, status "
        "FROM goals WHERE status='active' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("  No active goals. Use: synlynk goal create --outcome '...' --criterion '...'")
        return
    print(f"\n  {'ID':<12} {'Outcome':<40} {'Deadline':<12}")
    print("  " + "-" * 80)
    for r in rows:
        deadline = r[3] or "ongoing"
        print(f"  {r[0]:<12} {(r[1] or '')[:39]:<40} {deadline:<12}")


_VALID_SESSION_DISPOSITIONS = {
    "goal_progress", "maintenance", "exploration", "parked", "needs_attribution"
}


def cmd_session_open(title: str, goal_id: str = None) -> str:
    """Opens a new session, writes the active-session marker. Returns session_id."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.session import _write_active_session
    import hashlib as _hashlib
    session_id = "session-" + _hashlib.md5(
        f"{title}{time.time()}".encode()
    ).hexdigest()[:8]
    opened_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, title, goal_id, status, opened_at) "
        "VALUES (?, ?, ?, 'open', ?)",
        (session_id, title, goal_id, opened_at),
    )
    conn.commit()
    conn.close()
    _write_active_session(session_id)
    print(f"  {_GREEN}✓{_RESET} Session opened: {session_id}  [{title}]")
    return session_id


def cmd_session_status() -> None:
    """Prints the active session (if any), its goal, and evidence counts."""
    from synlynk import _get_db
    from synlynk.session import _read_active_session
    session_id = _read_active_session()
    if not session_id:
        print("  No active session. Run: synlynk session open --title \"...\"")
        return
    conn = _get_db()
    row = conn.execute(
        "SELECT title, goal_id, opened_at, last_checkpoint_at FROM sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if not row:
        conn.close()
        print(f"  Active session marker points to {session_id}, but no matching row exists.")
        return
    title, goal_id, opened_at, last_checkpoint_at = row
    job_count = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    devlog_count = conn.execute(
        "SELECT COUNT(*) FROM devlog_entries WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    unattributed_jobs = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE session_id IS NULL"
    ).fetchone()[0]
    conn.close()
    print(f"  Session: {session_id}  [{title}]")
    print(f"  Goal: {goal_id or '(none linked)'}")
    print(f"  Opened: {opened_at}   Last checkpoint: {last_checkpoint_at or '(never)'}")
    print(f"  Jobs attributed: {job_count}   Devlog entries: {devlog_count}")
    if unattributed_jobs:
        print(f"  NUDGE: {unattributed_jobs} job(s) in daemon_jobs have no session_id — "
              f"dispatched with no session open. Run 'synlynk session open' before dispatching, "
              f"or pass --session explicitly.")


def cmd_session_checkpoint() -> None:
    """Reports jobs/costs/devlog entries since the last checkpoint. Read-only."""
    from synlynk import _get_db
    from synlynk.session import _read_active_session
    session_id = _read_active_session()
    if not session_id:
        print("  No active session to checkpoint.")
        return
    conn = _get_db()
    row = conn.execute(
        "SELECT last_checkpoint_at, opened_at FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if not row:
        conn.close()
        print(f"  Active session marker points to {session_id}, but no matching row exists.")
        return
    since = row[0] or row[1]
    jobs = conn.execute(
        "SELECT job_id, agent, status FROM daemon_jobs "
        "WHERE session_id=? AND enqueued_at>?",
        (session_id, since),
    ).fetchall()
    devlogs = conn.execute(
        "SELECT id, author, entry_date FROM devlog_entries "
        "WHERE session_id=? AND recorded_at>?",
        (session_id, since),
    ).fetchall()
    orphaned_jobs = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE session_id IS NULL AND enqueued_at>?",
        (since,),
    ).fetchone()[0]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "UPDATE sessions SET last_checkpoint_at=? WHERE session_id=?", (now, session_id)
    )
    conn.commit()
    conn.close()
    print(f"  Checkpoint for {session_id} since {since}:")
    print(f"  Jobs attributed to this session: {len(jobs)}")
    for job_id, agent, status in jobs:
        print(f"    - {job_id}  {agent}  {status}")
    print(f"  Devlog entries linked: {len(devlogs)}")
    if orphaned_jobs:
        print(f"  NUDGE: {orphaned_jobs} job(s) dispatched since {since} have no session_id — "
              f"likely dispatched with no session open.")


def cmd_session_close(disposition: str, summary: str = None) -> None:
    """Closes the active session with a disposition. Clears the active-session marker."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.session import _read_active_session, _clear_active_session
    if disposition not in _VALID_SESSION_DISPOSITIONS:
        raise ValueError(
            f"Invalid disposition: {disposition!r}, must be one of {sorted(_VALID_SESSION_DISPOSITIONS)}"
        )
    session_id = _read_active_session()
    if not session_id:
        print("  No active session to close.")
        return
    closed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = _get_db()
    conn.execute(
        "UPDATE sessions SET status='closed', disposition=?, closed_at=?, closing_summary=? "
        "WHERE session_id=?",
        (disposition, closed_at, summary, session_id),
    )
    conn.commit()
    conn.close()
    _clear_active_session()
    print(f"  {_GREEN}✓{_RESET} Session closed: {session_id}  [{disposition}]")

def cmd_goal_link(story_id: str, goal_id: str, secondary: bool = False) -> None:
    """Links a story to a goal. Primary (default) sets stories.goal_id;
    secondary inserts a goal_contributions row for cross-cutting traceability."""
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    story = conn.execute("SELECT story_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    goal = conn.execute("SELECT goal_id FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found.")
        return
    if not goal:
        conn.close()
        print(f"  Goal '{goal_id}' not found.")
        return
    if secondary:
        conn.execute(
            "INSERT OR IGNORE INTO goal_contributions (goal_id, story_id) VALUES (?, ?)",
            (goal_id, story_id)
        )
        print(f"  {_GREEN}✓{_RESET} {story_id} linked to {goal_id} (secondary)")
    else:
        conn.execute("UPDATE stories SET goal_id=? WHERE story_id=?", (goal_id, story_id))
        print(f"  {_GREEN}✓{_RESET} {story_id} linked to {goal_id} (primary)")
    conn.commit()
    conn.close()

def cmd_goal_status() -> None:
    """Prints a rollup of each active goal: story completion, linked arcs, deadline."""
    from synlynk import _get_db
    conn = _get_db()
    goals = conn.execute(
        "SELECT goal_id, outcome, deadline FROM goals WHERE status='active' ORDER BY created_at DESC"
    ).fetchall()
    if not goals:
        conn.close()
        print("  No active goals.")
        return
    print()
    for goal_id, outcome, deadline in goals:
        total = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE goal_id=?", (goal_id,)
        ).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE goal_id=? AND status='done'", (goal_id,)
        ).fetchone()[0]
        arcs = conn.execute(
            "SELECT version FROM roadmap_arcs WHERE goal_id=?", (goal_id,)
        ).fetchall()
        deadline_s = deadline or "ongoing"
        arc_s = ", ".join(a[0] for a in arcs) if arcs else "—"
        print(f"  {goal_id}  {outcome}")
        print(f"    Stories: {done}/{total} done   Deadline: {deadline_s}   Arcs: {arc_s}\n")
    conn.close()

def cmd_score_add(story_id: str, rating: float, note: str = None,
                  rework: bool = False) -> None:
    """Add a human quality rating for a story. Inserts a new 'human' row."""
    from synlynk import _GREEN, _RESET, _get_db
    if not 0.0 <= rating <= 10.0:
        raise ValueError(f"Rating must be 0–10, got {rating}")
    conn = _get_db()
    story = conn.execute(
        "SELECT engg_domain, discipline, org_domain, role, stage, industry, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found. Create it first with: synlynk story create")
        return
    engg, discipline, org, role, stage, industry, phase = story
    prev = conn.execute(
        "SELECT agent, model_version FROM capability_ratings "
        "WHERE story_id=? ORDER BY ts DESC LIMIT 1", (story_id,)
    ).fetchone()
    agent = prev[0] if prev else "unknown"
    model_version = prev[1] if prev else "unknown"
    dispatch_rework = 1 if rework else 0
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, discipline, org_domain, role, stage, industry, phase, "
        " signal_source, quality, quality_auto, dispatch_rework, note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (story_id, agent, model_version, engg, discipline, org, role, stage, industry, phase,
         "human", rating, None, dispatch_rework, note)
    )
    conn.commit()
    conn.close()
    flag = " [rework]" if rework else ""
    print(f"  {_GREEN}✓{_RESET} Score recorded: {rating}/10{flag} for {story_id}")
    if note:
        print(f"    Note: {note}")

def cmd_score_list(engg: str = None, org: str = None, industry: str = None) -> None:
    """Display capability_scores for a discipline coordinate."""
    from synlynk import _get_db
    conn = _get_db()
    where_parts, params = [], []
    if engg:
        where_parts.append("discipline=?"); params.append(engg)
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
        print(
            f"  {r[0]:<10} {r[1]:<22} {_taxonomy_label('sfia', r[2]):<12} "
            f"{_taxonomy_label('apqc', r[3]):<14} {_taxonomy_label('naics', r[4]):<12} "
            f"{r[5]:<10} {score_str:>6} {r[7]:>4}"
        )

def cmd_cost_log(
    agent: str,
    tokens_in: int,
    tokens_out: int,
    story_id: str = None,
    note: str = None,
) -> None:
    """Log a manually reported cost row for native/unwrapped sessions."""
    from synlynk import (
        _GREEN,
        _RESET,
        _dr_sync,
        _get_db,
        _is_migrated,
        _insert_cost_row,
        extract_model_version,
        _generate_costs_md,
    )
    from synlynk.costs import resolve_payment_value

    if tokens_in < 0 or tokens_out < 0:
        raise ValueError("tokens-in and tokens-out must be non-negative")

    conn = _get_db()
    phase = None
    if story_id:
        row = conn.execute(
            "SELECT discipline, phase FROM stories WHERE story_id=?",
            (story_id,),
        ).fetchone()
        if row:
            _, phase = row
    conn.close()

    model_version = extract_model_version("", agent=agent)
    payment_value = resolve_payment_value(agent, tokens_in, tokens_out)
    est_cost = payment_value.api_equivalent_usd
    ts = time.strftime("%Y-%m-%d %H:%M")

    _insert_cost_row(
        session_date=ts,
        agent=agent,
        model=model_version,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cache_read_tokens=0,
        cost_source="estimated_manual",
        estimate_basis="cli_manual_entry",
        total_cost_usd=est_cost,
        notes=note,
        story_id=story_id,
        api_equivalent_usd=payment_value.api_equivalent_usd,
        actual_usd=payment_value.actual_usd,
        payment_mode=payment_value.mode,
    )
    _generate_costs_md()
    if _is_migrated():
        _dr_sync("costs.md")
    label = f"story {story_id}" if story_id else f"phase={phase or 'dream/plan'} (no story)"
    print(
        f"  {_GREEN}✓{_RESET} Manual cost entry logged for {agent} — {label}: "
        f"{tokens_in:,} in / {tokens_out:,} out, est ${est_cost:.4f}"
    )

def cmd_remediation_log(
    agent: str,
    target_file: str,
    exact_diff: str,
    operator: str = "non-interactive --yes",
    timestamp: str = None,
) -> None:
    """Append a remediation audit row to the canonical DB log."""
    from synlynk import _get_db

    logged_at = timestamp or time.strftime("%Y-%m-%d %H:%M")
    conn = _get_db()
    conn.execute(
        """INSERT INTO remediation_actions
            (timestamp, agent, target_file, exact_diff, operator)
           VALUES (?, ?, ?, ?, ?)""",
        (logged_at, agent, target_file, exact_diff, operator),
    )
    conn.commit()
    conn.close()

def cmd_credit_grant(
    agent: str,
    amount: float,
    expires: str = None,
    note: str = None,
) -> None:
    """Record a new credit grant for an agent."""
    from synlynk import _GREEN, _RESET, _get_db

    if amount < 0:
        raise ValueError("amount must be non-negative")

    granted_at = time.strftime("%Y-%m-%d %H:%M")
    conn = _get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at, expires_at, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (agent, amount, amount, granted_at, expires, note),
    )
    conn.commit()
    conn.close()
    suffix = f" (expires {expires})" if expires else ""
    print(f"  {_GREEN}✓{_RESET} Credit grant recorded for {agent}: ${amount:.2f}{suffix}")


def _fix_devlog_fork(conn, member_id: str, aliases: list) -> None:
    """Merges non-canonical alias devlog .md files into the canonical one and
    backfills devlog_entries.member_id for every row under any of the aliases.

    Canonical alias = the alias equal to member_id (the seed always registers
    member_id itself as one of its own aliases - see Task 1's seed insert).
    Non-canonical files are archived (not deleted from history) under
    project-docs/devlogs/archive/.
    """
    import datetime

    from synlynk import _docs_dir

    devlogs_dir = os.path.join(_docs_dir(), "devlogs")
    canonical_alias = member_id if member_id in aliases else sorted(aliases)[0]
    canonical_path = os.path.join(devlogs_dir, f"{canonical_alias}.md")
    today = datetime.date.today().isoformat()

    for alias in sorted(aliases):
        if alias == canonical_alias:
            continue
        alias_path = os.path.join(devlogs_dir, f"{alias}.md")
        if not os.path.exists(alias_path):
            continue
        with open(alias_path) as f:
            content = f.read()

        archive_dir = os.path.join(devlogs_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        archive_path = os.path.join(archive_dir, f"{alias}-merged-{today}.md")
        with open(archive_path, "w") as f:
            f.write(content)

        with open(canonical_path, "a") as f:
            f.write(f"\n<!-- migrated from project-docs/devlogs/{alias}.md on {today} -->\n")
            f.write(content)

        os.remove(alias_path)

    placeholders = ",".join("?" * len(aliases))
    conn.execute(
        f"UPDATE devlog_entries SET member_id = ? WHERE author IN ({placeholders})",
        (member_id, *aliases),
    )
    conn.commit()


def cmd_audit_docs(json_output: bool = False, fix: bool = False) -> list:
    """Reports (and optionally fixes) devlog author-identity drift.

    Cross-references distinct devlog_entries.author values and
    project-docs/devlogs/*.md filenames against the members/member_aliases
    registry (see Task 1). Two finding kinds:
      - "fork": two or more registered aliases resolve to the same member_id
        (e.g. nikhil + nikhilsoman both -> nikhilsoman).
      - "unregistered": an author/filename has no member_alias row at all
        (e.g. agy - a harness identity, never auto-fixed).

    --fix only merges "fork" findings; "unregistered" findings are report-only
    by design (auto-registering an unknown identity is a policy decision, not
    a mechanical fix).
    """
    import glob

    from synlynk import _docs_dir, _get_db

    conn = _get_db()
    # A backfilled member_id marks historical rows as reconciled while the
    # original author remains intact for provenance.  Only rows without that
    # identity linkage still represent active drift; otherwise a successful
    # --fix would continue to report the same fork forever.
    db_authors = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT author FROM devlog_entries WHERE member_id IS NULL"
        )
    }
    aliases = dict(conn.execute("SELECT alias, member_id FROM member_aliases").fetchall())

    file_authors = set()
    for path in glob.glob(os.path.join(_docs_dir(), "devlogs", "*.md")):
        file_authors.add(os.path.splitext(os.path.basename(path))[0])

    all_authors = db_authors | file_authors

    by_member: dict = {}
    unregistered = []
    for author in sorted(all_authors):
        member_id = aliases.get(author)
        if member_id is None:
            unregistered.append(author)
        else:
            by_member.setdefault(member_id, set()).add(author)

    findings = []
    for member_id, alias_set in by_member.items():
        if len(alias_set) > 1:
            findings.append({
                "kind": "fork",
                "member_id": member_id,
                "aliases": sorted(alias_set),
            })
    for author in unregistered:
        findings.append({"kind": "unregistered", "alias": author})

    if fix:
        for finding in findings:
            if finding["kind"] == "fork":
                _fix_devlog_fork(conn, finding["member_id"], finding["aliases"])

    conn.close()

    if json_output:
        print(json.dumps(findings, indent=2))
    else:
        if not findings:
            print("  ✓ No devlog identity drift found.")
        for finding in findings:
            if finding["kind"] == "fork":
                print(f"  FORK: aliases {finding['aliases']} all resolve to member_id={finding['member_id']!r}")
            else:
                print(f"  UNREGISTERED: {finding['alias']!r} has no member_aliases entry (not auto-fixable)")

    return findings

def cmd_pr_check() -> None:
    """Hard-blocks merge if any capability_ratings row has model_version='unknown'.

    Exit code 1 if blocked. Exit code 0 if clean.
    """
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.pr_multiplier import (
        _apply_review_cycle_multiplier,
        _current_pr_number,
        _is_github_remote,
    )
    from synlynk.sentinel import _extract_pr_review_cycles

    detect_hand_edit = globals().get("_detect_hand_edit")
    if callable(detect_hand_edit):
        for fname in ("todo.md", "roadmap.md", "memory.md", "costs.md"):
            warning = detect_hand_edit(fname)
            if warning is not None:
                print(warning)

    conn = _get_db()
    if _is_github_remote():
        pr_number = _current_pr_number()
        if pr_number is not None:
            changes_requested_count = _extract_pr_review_cycles() or 0
            _apply_review_cycle_multiplier(conn, pr_number, changes_requested_count)

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
    conn2 = _get_db()
    unlinked_story_ids = conn2.execute(
        "SELECT DISTINCT cr.story_id FROM capability_ratings cr "
        "LEFT JOIN stories s ON s.story_id = cr.story_id "
        "WHERE s.goal_id IS NULL "
        "AND cr.story_id NOT IN ("
        "  SELECT story_id FROM goal_contributions WHERE link_status='linked'"
        ")"
    ).fetchall()
    conn2.close()
    if unlinked_story_ids:
        print("\n  ⚠ [PR CHECK] Stories with no linked GOVERNS goal (soft-warn, not blocking):")
        for (story_id,) in unlinked_story_ids:
            print(f"    {story_id}")
        print("  Link with: synlynk goal link <story-id> --goal <goal-id>\n")
    devlog_findings = cmd_audit_docs(json_output=False)
    if devlog_findings:
        fork_count = sum(1 for f in devlog_findings if f["kind"] == "fork")
        unreg_count = sum(1 for f in devlog_findings if f["kind"] == "unregistered")
        print(
            f"\n  ⚠ [PR CHECK] devlog identity drift found: {fork_count} fork(s), "
            f"{unreg_count} unregistered (soft-warn, not blocking)"
        )
        print("  Fix with: synlynk audit-docs --fix\n")
    print(f"  {_GREEN}✓{_RESET} PR check passed — all model versions attested.")

def cmd_score_attest(story_id: str, model_version: str) -> None:
    """Retroactively sets model_version on all 'unknown' rows for a story.

    Also recalculates split_model — if model_at_dispatch differs from the attested
    completion model, the row is a split-model run and must be excluded from scoring.
    """
    from synlynk import _GREEN, _RESET, _get_db
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
