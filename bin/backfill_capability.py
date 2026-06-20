#!/usr/bin/env python3
"""
Backfill capability ledger from merged GitHub PRs.

Usage:
    python3 bin/backfill_capability.py [--dry-run] [--repo OWNER/REPO]

Inserts one story + one capability_rating per merged PR into state.db.
Ratings start with quality=0.0 and model_version='unknown' — attest them with:
    synlynk story list
    synlynk score attest <story-id> --model <version>
    synlynk score add <story-id> <quality_0_to_10> --note "PR#N retrospective"
"""

import json
import os
import sqlite3
import subprocess
import sys
import hashlib
from datetime import datetime

# ---------------------------------------------------------------------------
# Reproduce DB_PATH logic from synlynk.py
# ---------------------------------------------------------------------------

def _get_git_root() -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        if r.returncode == 0:
            git_common = r.stdout.strip()
            return os.path.dirname(os.path.abspath(git_common))
    except Exception:
        pass
    return None

_GIT_ROOT = _get_git_root()
if _GIT_ROOT:
    _root_hash = hashlib.md5(_GIT_ROOT.encode()).hexdigest()[:8]
    DB_PATH = os.path.expanduser(f"~/.synlynk/projects/{_root_hash}/state.db")
else:
    DB_PATH = os.path.expanduser("~/.synlynk/state.db")

# ---------------------------------------------------------------------------
# Domain inference
# ---------------------------------------------------------------------------

_TITLE_PREFIX_DOMAIN = {
    "test:":  "test",
    "docs:":  "docs",
    "chore:": "docs",
}

_FILE_DOMAIN_RULES = [
    (lambda f: f.startswith("bin/"),             "cli"),
    (lambda f: f.startswith("tests/"),           "test"),
    (lambda f: f.startswith("site/"),            "web"),
    (lambda f: f.startswith("docs/") or f.startswith("project-docs/") or f == "README.md", "docs"),
]

def infer_engg_domain(title: str, files: list[str]) -> str:
    t = title.lower()
    for prefix, domain in _TITLE_PREFIX_DOMAIN.items():
        if t.startswith(prefix):
            return domain
    for path_fn, domain in _FILE_DOMAIN_RULES:
        if any(path_fn(f) for f in files):
            return domain
    return "unknown"

# Known model version by PR (attest these automatically where we're confident)
_KNOWN_MODELS: dict[int, str] = {
    49: "claude-sonnet-4-6",   # v0.7.0 — this session
}

def infer_phase(pr_number: int) -> str:
    if pr_number <= 3:
        return "bootstrap"
    if pr_number <= 29:
        return "build"
    return "scale"

def count_review_cycles(reviews: list) -> int:
    meaningful = [r for r in reviews if r.get("state") in
                  ("APPROVED", "CHANGES_REQUESTED", "COMMENTED")]
    return len(meaningful)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        print(f"  ERROR: state.db not found at {DB_PATH}")
        print("  Run: synlynk init  (in this repo) to create the database first.")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def story_exists(conn: sqlite3.Connection, story_id: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM stories WHERE story_id=?", (story_id,)
    ).fetchone())

def insert_story(conn: sqlite3.Connection, story_id: str, title: str,
                 engg_domain: str, phase: str, created_at: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO stories "
        "(story_id, title, engg_domain, org_domain, industry, phase, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, title, engg_domain, "product", "developer-tools", phase, created_at)
    )

def insert_rating(conn: sqlite3.Connection, story_id: str, engg_domain: str,
                  phase: str, model_version: str, pr_review_cycles: int,
                  note: str, ts: str) -> None:
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, test_pass_rate, build_success, pr_review_cycles, "
        " correct, note, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, "claude", model_version, engg_domain, "product",
         "developer-tools", phase, "backfill", 0.0, 1.0, 1,
         pr_review_cycles, 1, note, ts)
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fetch_prs(repo: str | None) -> list[dict]:
    cmd = ["gh", "pr", "list", "--state", "merged", "--limit", "100",
           "--json", "number,title,mergedAt,files,reviews,body"]
    if repo:
        cmd += ["--repo", repo]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERROR fetching PRs: {r.stderr.strip()}")
        sys.exit(1)
    return json.loads(r.stdout)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    repo = None
    for i, arg in enumerate(sys.argv):
        if arg == "--repo" and i + 1 < len(sys.argv):
            repo = sys.argv[i + 1]

    print("synlynk capability backfill")
    print(f"  DB: {DB_PATH}")
    if dry_run:
        print("  Mode: DRY RUN (no writes)")
    print()

    prs = fetch_prs(repo)
    print(f"  Found {len(prs)} merged PRs\n")

    conn = None if dry_run else get_db()

    rows = []
    for pr in prs:
        number = pr["number"]
        title  = pr["title"]
        files  = [f["path"] for f in (pr.get("files") or [])]
        reviews = pr.get("reviews") or []
        merged_at = pr.get("mergedAt", "")[:19].replace("T", " ")

        story_id   = f"story-pr{number}"
        engg       = infer_engg_domain(title, files)
        phase      = infer_phase(number)
        model_ver  = _KNOWN_MODELS.get(number, "unknown")
        cycles     = count_review_cycles(reviews)
        note       = f"Backfill: PR#{number} merged {merged_at[:10]}"

        rows.append({
            "pr": number, "story_id": story_id, "title": title[:60],
            "engg": engg, "phase": phase, "model": model_ver,
            "cycles": cycles, "ts": merged_at,
        })

        if not dry_run:
            skip = story_exists(conn, story_id)
            if not skip:
                insert_story(conn, story_id, title, engg, phase, merged_at)
                insert_rating(conn, story_id, engg, phase, model_ver, cycles, note, merged_at)

    # Print table
    print(f"  {'PR':<6} {'story_id':<18} {'engg':<6} {'phase':<10} {'model':<22} {'cyc':<4}  title")
    print("  " + "-" * 100)
    skipped = 0
    for r in rows:
        already = (not dry_run) and story_exists(conn, r["story_id"]) if not dry_run else False
        flag = " [skip]" if (not dry_run and already) else ""
        if flag:
            skipped += 1
        print(f"  #{r['pr']:<5} {r['story_id']:<18} {r['engg']:<6} {r['phase']:<10} "
              f"{r['model']:<22} {r['cycles']:<4}  {r['title']}{flag}")

    if not dry_run:
        conn.commit()
        conn.close()
        inserted = len(rows) - skipped
        print(f"\n  {inserted} stories inserted, {skipped} already existed.")
    else:
        print(f"\n  (Dry run — {len(rows)} rows would be inserted)")

    print("""
Next steps:
  1. Review stories:
       synlynk story list

  2. Attest model versions for known PRs:
       synlynk score attest story-pr49 --model claude-sonnet-4-6
       synlynk score attest story-pr47 --model claude-sonnet-4-5
       # etc.

  3. Add quality scores (0–10) for each story:
       synlynk score add story-pr49 9.0 --note "316 tests, clean review"
       synlynk score add story-pr42 8.0 --note "2 review cycles, shipped clean"
       # etc.

  4. Check the ledger:
       synlynk score list --engg cli
       synlynk score list --engg test
""")


if __name__ == "__main__":
    main()
