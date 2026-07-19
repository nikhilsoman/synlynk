#!/usr/bin/env python3
"""Backfill api_equivalent_usd for historical cost_entries rows.

This is intentionally narrow:
- only rows with cost_source='estimated_manual'
- only rows with input_tokens/output_tokens/model present
- only rows where api_equivalent_usd is currently NULL
- payment_mode and actual_usd are left untouched
- cost_source='legacy_unknown' rows are never touched
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import synlynk  # noqa: E402


_BACKFILL_SQL = """
SELECT
    id,
    agent,
    model,
    input_tokens,
    output_tokens,
    COALESCE(cache_read_tokens, 0) AS cache_read_tokens
FROM cost_entries
WHERE cost_source = 'estimated_manual'
  AND input_tokens IS NOT NULL
  AND output_tokens IS NOT NULL
  AND model IS NOT NULL
  AND api_equivalent_usd IS NULL
ORDER BY id
"""


def _compute_api_equivalent_usd(agent, model, input_tokens, output_tokens, cache_read_tokens):
    rates = synlynk._model_rate_for_version(model, agent=agent)
    return (
        (input_tokens / 1000 * rates["input"]) +
        (output_tokens / 1000 * rates["output"]) +
        (cache_read_tokens / 1000 * rates["cache_read"])
    )


def backfill_api_equivalent_usd(db_path: str, dry_run: bool = False) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
        if "api_equivalent_usd" not in columns:
            raise RuntimeError("cost_entries.api_equivalent_usd column is missing")

        rows = conn.execute(_BACKFILL_SQL).fetchall()
        updated = 0
        for row in rows:
            api_equivalent_usd = _compute_api_equivalent_usd(
                row["agent"],
                row["model"],
                row["input_tokens"],
                row["output_tokens"],
                row["cache_read_tokens"] or 0,
            )
            if not dry_run:
                conn.execute(
                    "UPDATE cost_entries SET api_equivalent_usd=? WHERE id=?",
                    (api_equivalent_usd, row["id"]),
                )
            updated += 1

        if not dry_run:
            conn.commit()
        return updated
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill api_equivalent_usd for eligible historical cost_entries rows"
    )
    parser.add_argument("--dry-run", action="store_true", help="Report the rows that would be updated")
    args = parser.parse_args(argv)

    db_path = synlynk._resolve_db_path()
    if not os.path.exists(db_path):
        print(f"ERROR: state.db not found at {db_path}", file=sys.stderr)
        return 1

    mode = "dry run" if args.dry_run else "write"
    print(f"synlynk cost backfill")
    print(f"  DB: {db_path}")
    print(f"  Mode: {mode}")

    updated = backfill_api_equivalent_usd(db_path, dry_run=args.dry_run)
    if args.dry_run:
        print(f"  Would update {updated} rows")
    else:
        print(f"  Updated {updated} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
