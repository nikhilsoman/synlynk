import json
import os
import re
import sqlite3
import subprocess
import time

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

def _migrate_db(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations. Adds tables/views if absent."""
    from synlynk import AGENT_CAPABILITY_BASELINES, _DB_SCHEMA, _DB_SCORES_VIEW, _seed_verb_map
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
    except sqlite3.OperationalError:
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
        except sqlite3.OperationalError:
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

def _migrate_import(docs_dir: str, dry_run: bool = False) -> None:
    """Parse flat files in docs_dir -> state.db. Prints import summary."""
    from synlynk import _get_db, _parse_costs_md, _parse_devlog_file, _parse_memory_md, _parse_roadmap_md, _parse_todo_metadata
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
    from synlynk import _docs_dir, _migrate_import, _synlynk_project_docs_dir
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

def _write_memory_md() -> None:
    """Regenerate .synlynk/project-docs/memory.md from memory_entries table."""
    from synlynk import _get_db, _synlynk_project_docs_dir
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
    if _is_migrated():
        _write_memory_md()
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
                      session_title: str = None) -> None:
    """Append a devlog entry to DB and write through to flat file if migrated."""
    from synlynk import _dr_sync, _get_db, _is_migrated
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
    from synlynk import _docs_dir, _get_db
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
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    conn.close()
    return imported

def cmd_story_create(title: str, engg_domain: str = "unknown",
                     org_domain: str = "unknown", phase: str = "build",
                     org_domain_tags: list = None,
                     estimated_tokens: int = None) -> str:
    """Creates a story record in state.db. Returns the generated story_id."""
    from synlynk import _GREEN, _RESET, _generate_todo_md, _get_db, load_config
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

def cmd_score_add(story_id: str, rating: float, note: str = None,
                  rework: bool = False) -> None:
    """Add a human quality rating for a story. Inserts a new 'human' row."""
    from synlynk import _GREEN, _RESET, _get_db
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
    from synlynk import _get_db
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
    from synlynk import _GREEN, _RESET, _get_db
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
