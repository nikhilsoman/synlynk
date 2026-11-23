#!/usr/bin/env python3
"""Offline-unsafe follow-up to migration 38 (gh:#5443 item 3).

Run manually, once, after migration 38 has been applied in production:

    python3 scripts/verify_github_sync_map_arc_uid_migration.py --owner <owner> --repo <repo>

For every github_sync_map row of entity_type='roadmap_arc', fetches the live
GitHub milestone and compares its title against the local arc's expected
title (roadmap_arcs.title). Prints a mismatch report; does not write
anything. This is deliberately not part of migration 38 itself -- the
migration must stay pure-SQL and runnable offline/in CI.
"""
import argparse
import sys

from synlynk import _get_db
from synlynk.gh_sync import _gh_api_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--role", default="pm")
    args = parser.parse_args()

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT gm.entity_id, gm.github_number, ra.title "
            "FROM github_sync_map gm "
            "JOIN roadmap_arcs ra ON ra.arc_uid = gm.entity_id "
            "WHERE gm.entity_type = 'roadmap_arc'"
        ).fetchall()
    finally:
        conn.close()

    mismatches = []
    for arc_uid, github_number, expected_title in rows:
        live = _gh_api_json(
            [f"repos/{args.owner}/{args.repo}/milestones/{github_number}", "--method", "GET"],
            role=args.role,
        )
        live_title = live.get("title") if live else None
        if live_title != expected_title:
            mismatches.append((arc_uid, github_number, expected_title, live_title))

    if not mismatches:
        print(f"  ✓ all {len(rows)} github_sync_map rows match their live milestone title")
        return 0

    print(f"  ⚠ {len(mismatches)} of {len(rows)} github_sync_map rows mismatch:")
    for arc_uid, github_number, expected_title, live_title in mismatches:
        print(f"    arc_uid={arc_uid} github_number={github_number} expected={expected_title!r} live={live_title!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
