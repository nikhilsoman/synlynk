# Devlog Identity Registry + `synlynk audit-docs` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the live `nikhil`/`nikhilsoman`/`agy` devlog author fork from growing, and give the project a `synlynk audit-docs` command that detects and (for the registered-human case) fixes it, backed by a new stable `member_id` identity registry.

**Architecture:** Add two small SQLite tables (`members`, `member_aliases`) to `synlynk/db.py`, seeded with the known `nikhil`/`nikhilsoman` → single canonical member fork. Add `member_id` as a nullable column on the existing `devlog_entries` table (provenance-preserving — `author` is never overwritten). Add a new `cmd_audit_docs()` in `synlynk/db.py` that cross-references `devlog_entries` rows and `project-docs/devlogs/*.md` filenames against the registry, reporting FORK (two aliases → one member) and UNREGISTERED (alias not in registry at all — e.g. `agy`) findings, in human and `--json` form. `--fix` merges markdown files and backfills `member_id` for FORK findings only; UNREGISTERED findings are never auto-fixed. Canonicalize `checkpoint()`'s devlog path resolution through the registry so the fork can't reopen. Wire a non-blocking soft-warn into `cmd_pr_check()`.

**Tech Stack:** Python 3 stdlib, sqlite3 (existing `_get_db()` connection helper, WAL mode, `_migrate_db()` migration pattern), argparse (`synlynk/cli.py`), pytest with the existing `project_dir` fixture (`tests/conftest.py`) and `SYNLYNK_STATE_DB_PATH` env-var override pattern.

**Note on line numbers:** every line number cited below (e.g. `db.py:549`, `__init__.py:2926`) was accurate at plan-writing time but is not a stable identifier — the codebase moves. Locate each anchor by function/table name first (`grep -n "def checkpoint"`, `grep -n "devlog_entries"`, etc.) and treat the cited line as a hint, not ground truth.

---

## Explicitly out of scope

Per the user's instruction, this plan covers only action items 1, 2 (report-mode + this one `--fix` category), and 7 from `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` §5. It does **not** cover: repo-wide `project-docs/` migration across the other 3 repos, `docs/superpowers/`-style skill injection, replacing the Blog Post Protocol, `synlynk instructions update`, moving `sentinel.md` into `state.db`, or any of §4's agent-artifact workspace store / `agent_id` registry / `gated` mutability tier. Those get separate follow-up plans.

---

### Task 1: `members` + `member_aliases` tables + `devlog_entries.member_id` column

**Files:**
- Modify: `synlynk/db.py:549-562` (the `devlog_entries` CREATE TABLE block and its migration guard right below it)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py`:

```python
def test_member_registry_tables_and_seed(project_dir):
    from synlynk import _get_db

    conn = _get_db()
    members = conn.execute("SELECT member_id, canonical_name FROM members").fetchall()
    assert ("nikhilsoman", "Nikhil Soman") in members

    aliases = dict(conn.execute("SELECT alias, member_id FROM member_aliases").fetchall())
    assert aliases["nikhil"] == "nikhilsoman"
    assert aliases["nikhilsoman"] == "nikhilsoman"
    conn.close()


def test_devlog_entries_has_member_id_column(project_dir):
    from synlynk import _get_db

    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devlog_entries)")}
    assert "member_id" in cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -k "member_registry or devlog_entries_has_member_id" -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: members`

- [ ] **Step 3: Add the schema + seed + column migration**

In `synlynk/db.py`, find the `devlog_entries` CREATE TABLE block (currently at line 549) and the `devlog_cols` migration guard right after it (line 561-562 area, which currently only checks for `session_id`). Replace that whole block with:

```python
        CREATE TABLE IF NOT EXISTS devlog_entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            author        TEXT NOT NULL,
            entry_date    TEXT NOT NULL,
            session_title TEXT,
            session_id    TEXT,
            body          TEXT NOT NULL,
            recorded_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_devlog_author ON devlog_entries(author);
        CREATE INDEX IF NOT EXISTS idx_devlog_date   ON devlog_entries(entry_date);
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
```

Leave the existing `session_id` ALTER TABLE branch below it untouched, but add a sibling branch right after it (same indentation level, same function) for the new column:

```python
    if "member_id" not in devlog_cols:
        conn.execute("ALTER TABLE devlog_entries ADD COLUMN member_id TEXT")

    conn.execute(
        "INSERT OR IGNORE INTO members (member_id, canonical_name) VALUES (?, ?)",
        ("nikhilsoman", "Nikhil Soman"),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO member_aliases (alias, member_id, alias_type) VALUES (?, ?, 'seed')",
        [("nikhil", "nikhilsoman"), ("nikhilsoman", "nikhilsoman")],
    )
```

Note: `devlog_cols` was read once before the `session_id` branch; since the `session_id` ALTER runs first inside the same connection/transaction, re-reading `PRAGMA table_info` is not required — `devlog_cols` was computed before either ALTER, so both branches must test membership in that same pre-ALTER set, which is already how the existing `session_id` check works. Confirm this is inside `_migrate_db(conn)` (the same function `devlog_entries` is created in), not a new function.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -k "member_registry or devlog_entries_has_member_id" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat(db): add member/member_aliases registry + devlog_entries.member_id column"
```

---

### Task 2: `cmd_audit_docs()` — report mode (human + `--json`)

**Files:**
- Modify: `synlynk/db.py` (add new function near `cmd_pr_check`, e.g. directly above it around line 2523)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
def test_audit_docs_report_detects_fork_and_unregistered(project_dir, capsys):
    from synlynk import _get_db
    from synlynk.db import cmd_audit_docs

    conn = _get_db()
    conn.executemany(
        "INSERT INTO devlog_entries (author, entry_date, body) VALUES (?, ?, ?)",
        [
            ("nikhil", "2026-05-16", "did a thing"),
            ("nikhilsoman", "2026-06-29", "did another thing"),
            ("agy", "2026-06-28", "harness wrote this"),
        ],
    )
    conn.commit()
    conn.close()

    findings = cmd_audit_docs(json_output=False)

    kinds = {f["kind"] for f in findings}
    assert "fork" in kinds
    assert "unregistered" in kinds

    fork = next(f for f in findings if f["kind"] == "fork")
    assert fork["member_id"] == "nikhilsoman"
    assert set(fork["aliases"]) == {"nikhil", "nikhilsoman"}

    unregistered = next(f for f in findings if f["kind"] == "unregistered")
    assert unregistered["alias"] == "agy"

    out = capsys.readouterr().out
    assert "FORK" in out
    assert "UNREGISTERED" in out


def test_audit_docs_report_json_output(project_dir, capsys):
    import json
    from synlynk import _get_db
    from synlynk.db import cmd_audit_docs

    conn = _get_db()
    conn.execute(
        "INSERT INTO devlog_entries (author, entry_date, body) VALUES (?, ?, ?)",
        ("nikhil", "2026-05-16", "did a thing"),
    )
    conn.commit()
    conn.close()

    cmd_audit_docs(json_output=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert isinstance(payload, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -k "audit_docs" -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_audit_docs'`

- [ ] **Step 3: Implement `cmd_audit_docs()`**

Add to `synlynk/db.py`, directly above `def cmd_pr_check()`:

```python
def cmd_audit_docs(json_output: bool = False, fix: bool = False) -> list:
    """Reports (and optionally fixes) devlog author-identity drift.

    Cross-references distinct devlog_entries.author values and
    project-docs/devlogs/*.md filenames against the members/member_aliases
    registry (see Task 1). Two finding kinds:
      - "fork": two or more registered aliases resolve to the same member_id
        (e.g. nikhil + nikhilsoman both -> nikhilsoman).
      - "unregistered": an author/filename has no member_alias row at all
        (e.g. agy — a harness identity, never auto-fixed).

    --fix only merges "fork" findings; "unregistered" findings are report-only
    by design (auto-registering an unknown identity is a policy decision, not
    a mechanical fix).
    """
    import glob

    from synlynk import _docs_dir, _get_db

    conn = _get_db()
    db_authors = {row[0] for row in conn.execute("SELECT DISTINCT author FROM devlog_entries")}
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -k "audit_docs" -v`
Expected: `test_audit_docs_report_detects_fork_and_unregistered` PASSES; `test_audit_docs_report_json_output` still FAILS (json_output prints but nothing else broke) — confirm it passes too since `_fix_devlog_fork` isn't called in report mode. Both should PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat(db): add cmd_audit_docs report mode (fork + unregistered findings)"
```

---

### Task 3: `_fix_devlog_fork()` — merge markdown files + backfill `member_id`

**Files:**
- Modify: `synlynk/db.py` (add `_fix_devlog_fork` above `cmd_audit_docs`)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
def test_audit_docs_fix_merges_fork(project_dir):
    import os
    from synlynk import _get_db
    from synlynk.db import cmd_audit_docs

    devlogs_dir = os.path.join("project-docs", "devlogs")
    with open(os.path.join(devlogs_dir, "nikhil.md"), "w") as f:
        f.write("# nikhil devlog\n\n## 2026-05-16\n- did old thing\n")
    with open(os.path.join(devlogs_dir, "nikhilsoman.md"), "w") as f:
        f.write("# nikhilsoman devlog\n\n## 2026-06-29\n- did new thing\n")

    conn = _get_db()
    conn.executemany(
        "INSERT INTO devlog_entries (author, entry_date, body) VALUES (?, ?, ?)",
        [
            ("nikhil", "2026-05-16", "did old thing"),
            ("nikhilsoman", "2026-06-29", "did new thing"),
        ],
    )
    conn.commit()
    conn.close()

    findings = cmd_audit_docs(fix=True)
    assert any(f["kind"] == "fork" for f in findings)

    canonical_path = os.path.join(devlogs_dir, "nikhilsoman.md")
    assert os.path.exists(canonical_path)
    merged = open(canonical_path).read()
    assert "did old thing" in merged
    assert "did new thing" in merged
    assert "migrated from" in merged

    assert not os.path.exists(os.path.join(devlogs_dir, "nikhil.md"))
    archived = os.path.join(devlogs_dir, "archive")
    assert any("nikhil" in fn for fn in os.listdir(archived))

    conn = _get_db()
    member_ids = {
        row[0] for row in conn.execute("SELECT DISTINCT member_id FROM devlog_entries")
    }
    assert member_ids == {"nikhilsoman"}
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -k "audit_docs_fix_merges_fork" -v`
Expected: FAIL — canonical file not merged (no `_fix_devlog_fork` yet, so `--fix` is a no-op for files; `member_id` stays NULL)

- [ ] **Step 3: Implement `_fix_devlog_fork()`**

Add to `synlynk/db.py`, directly above `def cmd_audit_docs`:

```python
def _fix_devlog_fork(conn, member_id: str, aliases: list) -> None:
    """Merges non-canonical alias devlog .md files into the canonical one and
    backfills devlog_entries.member_id for every row under any of the aliases.

    Canonical alias = the alias equal to member_id (the seed always registers
    member_id itself as one of its own aliases — see Task 1's seed insert).
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -k "audit_docs_fix_merges_fork" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat(db): _fix_devlog_fork merges alias devlogs into canonical member file"
```

---

### Task 4: Canonicalize `checkpoint()`'s devlog path through the registry

**Files:**
- Modify: `synlynk/__init__.py:2926-2935` (`checkpoint()` — the `username`/`devlog_path` resolution at the top)
- Test: `tests/test_checkpoint_identity.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_checkpoint_identity.py`:

```python
def test_checkpoint_writes_to_canonical_member_path(project_dir, monkeypatch):
    import os

    from synlynk import _get_db, checkpoint

    monkeypatch.setattr("synlynk.get_username", lambda: "nikhil")

    with open("project-docs/todo.md", "a") as f:
        f.write("- [x] Ship the thing <!-- id: 99 -->\n")

    checkpoint()

    canonical_path = os.path.join("project-docs", "devlogs", "nikhilsoman.md")
    assert os.path.exists(canonical_path)
    assert "Ship the thing" in open(canonical_path).read()
    assert not os.path.exists(os.path.join("project-docs", "devlogs", "nikhil.md"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_checkpoint_identity.py -v`
Expected: FAIL — `project-docs/devlogs/nikhil.md` exists instead (checkpoint still uses the raw username)

- [ ] **Step 3: Add canonicalization**

In `synlynk/__init__.py`, inside `checkpoint()` (currently starting at line 2926), replace:

```python
    username = get_username()
    todo_path = "project-docs/todo.md"
    devlog_path = f"project-docs/devlogs/{username}.md"
```

with:

```python
    username = get_username()
    canonical_id = _resolve_member_id(username)
    todo_path = "project-docs/todo.md"
    devlog_path = f"project-docs/devlogs/{canonical_id}.md"
```

Add a small helper near `get_username`'s import site in `synlynk/__init__.py` (module scope, above `def checkpoint`):

```python
def _resolve_member_id(username: str) -> str:
    """Looks up username in the member_aliases registry; falls back to username
    itself when unregistered (matches audit-docs' "unregistered" finding — an
    unregistered identity is reported, never silently reassigned)."""
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT member_id FROM member_aliases WHERE alias = ?", (username,)
        ).fetchone()
        conn.close()
        return row[0] if row else username
    except Exception:
        return username
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_checkpoint_identity.py -v`
Expected: PASS

- [ ] **Step 5: Run full checkpoint test suite for regressions**

Run: `pytest tests/ -k checkpoint -v`
Expected: all PASS (existing checkpoint tests use usernames not in the seeded registry, e.g. generic test fixtures — those fall through the `except`/no-row branch to the unchanged raw-username path, so no behavior change for them)

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_checkpoint_identity.py
git commit -m "fix(checkpoint): resolve devlog path through member_id registry to prevent re-fork"
```

---

### Task 5: Wire `synlynk audit-docs` into `cli.py`

**Files:**
- Modify: `synlynk/cli.py` (subparser registration near `decide_parser`, import block, and command dispatch `elif` chain)
- Test: `tests/test_cli_parser.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_parser.py` (follow the existing file's pattern — check its imports first with `head -20 tests/test_cli_parser.py` if unsure of its helper style; use `build_parser()` or equivalent already used by other tests in that file):

```python
def test_audit_docs_parser_accepts_json_and_fix_flags():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["audit-docs", "--json", "--fix"])
    assert args.command == "audit-docs"
    assert args.json is True
    assert args.fix is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_parser.py -k audit_docs -v`
Expected: FAIL — `error: argument command: invalid choice: 'audit-docs'`

- [ ] **Step 3: Register the subparser**

In `synlynk/cli.py`, directly after the `decide_parser` block (currently ending around line 264, right before `goal_parser = subparsers.add_parser("goal", ...)`), add:

```python
    audit_docs_parser = subparsers.add_parser(
        "audit-docs", help="Detect (and optionally fix) devlog author-identity drift"
    )
    audit_docs_parser.add_argument(
        "--json", action="store_true", help="Emit findings as JSON"
    )
    audit_docs_parser.add_argument(
        "--fix", action="store_true",
        help="Merge fork findings into their canonical member devlog (unregistered findings are never auto-fixed)"
    )
```

Add `cmd_audit_docs` to both import blocks that already list `cmd_decide` (line 155 area and line 926 area) — insert alphabetically, i.e. right after `cmd_agent_run,` and before `cmd_decide,`:

```python
        cmd_agent_run,
        cmd_audit_docs,
        cmd_decide,
```

Add the dispatch branch. In `synlynk/cli.py`, directly after the existing `elif args.command == "decide":` block (currently lines 1316-1318), add:

```python
    elif args.command == "audit-docs":
        findings = cmd_audit_docs(json_output=args.json, fix=args.fix)
        if findings and not args.fix:
            sys.exit(1)
```

Check whether `cmd_audit_docs` is imported from `synlynk` (re-exported via `synlynk/__init__.py`, matching how `cmd_decide` is imported at line 155/926) or needs a direct `from synlynk.db import cmd_audit_docs` (matching how `goal` subcommands are imported inline at line 1319). Grep first:

```bash
grep -n "^    cmd_decide\|from synlynk.db import" synlynk/__init__.py | head -5
```

If `cmd_decide` is re-exported from `synlynk/__init__.py` (likely, since it's imported the same way `checkpoint` is at line 150), add the matching re-export line to `synlynk/__init__.py`'s import-from-db block so `cmd_audit_docs` is reachable the same way. If no such block exists and `cmd_decide` is actually imported directly from `synlynk.db` elsewhere, use `from synlynk.db import cmd_audit_docs` inline in the `elif` branch instead, matching the `goal` pattern at line 1319.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_parser.py -k audit_docs -v`
Expected: PASS

- [ ] **Step 5: Manual smoke test**

```bash
cd /tmp && rm -rf audit-docs-smoke && mkdir audit-docs-smoke && cd audit-docs-smoke
python3 -m synlynk init --non-interactive 2>/dev/null || python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py init
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py audit-docs
```
Expected: prints `✓ No devlog identity drift found.` and exits 0 (fresh project, empty registry usage).

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py synlynk/__init__.py tests/test_cli_parser.py
git commit -m "feat(cli): wire synlynk audit-docs subcommand (--json, --fix)"
```

---

### Task 6: Soft-warn from `synlynk pr check`

**Files:**
- Modify: `synlynk/db.py:2523-2574` (`cmd_pr_check()`)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
def test_pr_check_soft_warns_on_devlog_fork(project_dir, capsys, monkeypatch):
    from synlynk import _get_db
    from synlynk.db import cmd_pr_check

    monkeypatch.setattr("synlynk.pr_multiplier._is_github_remote", lambda: False)

    conn = _get_db()
    conn.executemany(
        "INSERT INTO devlog_entries (author, entry_date, body) VALUES (?, ?, ?)",
        [("nikhil", "2026-05-16", "x"), ("nikhilsoman", "2026-06-29", "y")],
    )
    conn.commit()
    conn.close()

    cmd_pr_check()
    out = capsys.readouterr().out
    assert "devlog identity drift" in out.lower()
    assert "synlynk audit-docs" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -k pr_check_soft_warns_on_devlog_fork -v`
Expected: FAIL — no mention of "devlog identity drift" in output

- [ ] **Step 3: Add the soft-warn**

In `synlynk/db.py`, inside `cmd_pr_check()`, directly before the final `print(f"  {_GREEN}✓{_RESET} PR check passed...")` line, add this block. `cmd_audit_docs` already prints its own per-finding report (FORK/UNREGISTERED lines from Task 2); this adds a `pr check`-specific summary line on top of that, matching the existing `goal_contributions` soft-warn style immediately above it in the same function (non-blocking, printed, no `SystemExit`):

```python
    devlog_findings = cmd_audit_docs(json_output=False)
    if devlog_findings:
        fork_count = sum(1 for f in devlog_findings if f["kind"] == "fork")
        unreg_count = sum(1 for f in devlog_findings if f["kind"] == "unregistered")
        print(
            f"\n  ⚠ [PR CHECK] devlog identity drift found: {fork_count} fork(s), "
            f"{unreg_count} unregistered (soft-warn, not blocking)"
        )
        print("  Fix with: synlynk audit-docs --fix\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -k pr_check_soft_warns_on_devlog_fork -v`
Expected: PASS

- [ ] **Step 5: Run the full `cmd_pr_check` test suite for regressions**

Run: `pytest tests/test_db.py -k pr_check -v`
Expected: all PASS — existing PR-check tests with no devlog_entries rows at all produce zero findings from `cmd_audit_docs`, so the new block is a no-op for them.

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat(pr-check): soft-warn on devlog identity drift, point at audit-docs --fix"
```

---

### Task 7: Run the full test suite

- [ ] **Step 1: Run everything**

Run: `pytest tests/ -v 2>&1 | tail -40`
Expected: all tests pass (current baseline before this plan: 1916 passed, 2 skipped — expect that plus this plan's ~9 new tests, so ~1925 passed, 2 skipped, 0 failed)

- [ ] **Step 2: If anything regressed, fix before proceeding**

Likely regression risk: any existing test that calls `checkpoint()` with `username` mocked/monkeypatched to `"nikhil"` or `"nikhilsoman"` and asserts on the raw `project-docs/devlogs/nikhil.md` path will now see `nikhilsoman.md` instead (Task 4's canonicalization). A known instance: `tests/test_synlynk.py:1296-1303` mocks `get_username()` to `"nikhil"` and asserts on `project-docs/devlogs/nikhil.md` directly — this must be updated to expect `nikhilsoman.md`. Search for all such matches before running (the existing tests build the path via `os.path.join`/f-strings, not a literal `"devlogs/nikhil"` substring, so grep for the filename fragment instead):

```bash
grep -rln '"nikhil\.md"\|devlogs.*nikhil\b\|nikhil.*devlogs' tests/
```

Read each match and confirm whether it's asserting on the raw per-alias devlog path (needs updating to `nikhilsoman.md`) or using a username that has no registry entry (e.g. some other test fixture username) — those are unaffected and should be left as-is. Update `tests/test_synlynk.py:1296-1303` specifically as part of this step.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "test: fix devlog path assertions after member_id canonicalization"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` §5 items 1, 2, 7 — note this plan implements only the devlog-identity slice of each item, not the item in full; the rest of each item is out of scope here per the "Explicitly out of scope" section above):
- Item 1 (doc-lifecycle manifest) → this plan implements only the `member_id` identity-registry piece (`members`/`member_aliases` tables, Task 1), not a general doc-lifecycle manifest schema. A full manifest (canonical identifier/path/backend/`create_via`/mutability/archive policy per Round 4's CRUD contract) is a separate follow-up plan.
- Item 2 (report-mode audit) → Task 2, scoped to the devlog author category only, not the other doc categories from the spec.
- Item 7 (revision-aware manifest writes + machine-readable audit wired into CI/pr check) → this plan implements the machine-readable audit (`--json`, Task 2) and `pr check` wiring (Task 6) for the devlog category, plus archive-not-delete provenance on fix (Task 3). It does **not** implement general revision-aware manifest writes (there is no manifest in this plan, per Item 1's note above) — devlog fixes are provenance-preserving via file archival and `member_id` backfill, which is a narrower mechanism than a manifest revision history.

**Placeholder scan:** none present — the rejected-example pattern previously used in Task 6 Step 3 was removed per review; the step now shows only the real implementation.

**Type consistency:** `cmd_audit_docs(json_output: bool = False, fix: bool = False) -> list` — signature used identically in Tasks 2, 3, 5, 6. `_fix_devlog_fork(conn, member_id: str, aliases: list) -> None` used identically in Tasks 2 and 3. `_resolve_member_id(username: str) -> str` used identically in Task 4's helper and call site.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-14-devlog-identity-registry.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
