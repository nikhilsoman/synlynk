"""Historical Capability Backfill Engine and CLI Command for Synlynk.

Analyzes historical tasks, stories, and job receipts in state.db, converts legacy discipline
labels to the Open SFIA 8/9 taxonomy, enforces dynamic >= 1% attribution, synchronizes
the multi-model catalog window, and populates canonical capability ratings.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Any

from synlynk import _CYAN, _GREEN, _RED, _RESET, _YELLOW, _get_db
from synlynk.capability_window import (
    get_active_sfia_disciplines,
    sync_harness_models_window,
)
from synlynk.sfia import (
    classify_task_sfia,
    get_sfia_domain,
    get_sfia_name,
    is_valid_sfia_code,
)

LEGACY_TO_SFIA_FALLBACK = {
    "backend": "PROG",
    "cli": "PROG",
    "testing": "TEST",
    "test": "TEST",
    "architecture": "REQM",
    "docs": "COMM",
    "frontend": "VISU",
    "data": "DBDS",
    "security": "REQM",
    "devops": "PROG",
    "ml": "PROG",
    "DEPL": "PROG",
    "DTAN": "DBDS",
    "SCTY": "REQM",
}


def run_capability_backfill(
    conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    min_sample: int = 5,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Execute historical capability rating classification and model window backfill.

    Args:
        conn: SQLite database connection.
        dry_run: When True, computes changes without modifying tables.
        force: When True, re-classifies rows even if already assigned an SFIA code.
        min_sample: Minimum sample floor for reporting (default 5).
        lookback_days: Sliding window for active models (default 30).

    Returns:
        dict: Detailed execution report.
    """
    rows = conn.execute("""
        SELECT cr.id, cr.story_id, s.title, cr.discipline, cr.agent, cr.quality,
               cr.quality_verified, cr.pr_review_cycles, cr.model_at_completion
        FROM capability_ratings cr
        LEFT JOIN stories s ON cr.story_id = s.story_id
    """).fetchall()

    total_ratings = len(rows)
    updated_records: list[dict[str, Any]] = []
    evaluated_rows: list = []

    for r_id, story_id, title, old_disc, agent, quality, verified, cycles, model in rows:
        target_code = old_disc

        # If old_disc is already valid SFIA and force is not set, keep it
        if not force and is_valid_sfia_code(old_disc) and old_disc != "UNAN":
            target_code = old_disc
        else:
            classified_code, _, _ = classify_task_sfia(title or story_id or "")
            if classified_code != "UNAN":
                target_code = classified_code
            elif old_disc in LEGACY_TO_SFIA_FALLBACK:
                target_code = LEGACY_TO_SFIA_FALLBACK[old_disc]
            else:
                target_code = "UNAN"

        evaluated_rows.append((r_id, story_id, title, old_disc, agent, quality, verified, cycles, model, target_code))

        if target_code != old_disc:
            updated_records.append({
                "id": r_id,
                "story_id": story_id,
                "old_discipline": old_disc,
                "new_discipline": target_code,
                "agent": agent,
            })
            if not dry_run:
                conn.execute(
                    "UPDATE capability_ratings SET discipline = ? WHERE id = ?",
                    (target_code, r_id),
                )

    if not dry_run and updated_records:
        conn.commit()

    # Synchronize multi-model sliding window
    synced_models = sync_harness_models_window(conn, lookback_days=lookback_days)

    # Calculate active disciplines meeting >= 1% attribution
    active_disciplines = get_active_sfia_disciplines(conn, threshold=0.01)

    # Compute aggregate summary grouped by (agent, target_discipline)
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    for r_id, story_id, title, old_disc, agent, quality, verified, cycles, model, target_code in evaluated_rows:
        key = (agent, target_code)
        if key not in agg:
            agg[key] = {
                "count": 0,
                "verified_count": 0,
                "total_quality": 0.0,
                "total_cycles": 0,
            }
        agg[key]["count"] += 1
        if verified == 1 or (quality is not None and quality > 0):
            agg[key]["verified_count"] += 1
        agg[key]["total_quality"] += (quality or 0.0)
        agg[key]["total_cycles"] += (cycles or 0)

    summary: list[dict[str, Any]] = []
    for (ag, disc), stats in sorted(agg.items(), key=lambda item: (item[0][0], -item[1]["count"])):
        cnt = stats["count"]
        summary.append({
            "agent": ag,
            "discipline": disc,
            "discipline_name": get_sfia_name(disc),
            "task_count": cnt,
            "verified_count": stats["verified_count"],
            "avg_quality": round(stats["total_quality"] / cnt, 2) if cnt > 0 else 0.0,
            "avg_review_cycles": round(stats["total_cycles"] / cnt, 2) if cnt > 0 else 0.0,
            "sample_floor_met": cnt >= min_sample,
            "qualifies_attribution": disc in active_disciplines,
        })

    return {
        "dry_run": dry_run,
        "total_ratings_analyzed": total_ratings,
        "updated_count": len(updated_records),
        "active_disciplines": active_disciplines,
        "synced_models_count": len(synced_models),
        "summary": summary,
    }


def cmd_capability_backfill(
    dry_run: bool = False,
    force: bool = False,
    min_sample: int = 5,
    lookback_days: int = 30,
) -> int:
    """CLI handler for `synlynk capability backfill`."""
    conn = _get_db()
    try:
        report = run_capability_backfill(
            conn,
            dry_run=dry_run,
            force=force,
            min_sample=min_sample,
            lookback_days=lookback_days,
        )
    finally:
        conn.close()

    mode_label = f"{_YELLOW}[DRY-RUN]{_RESET}" if dry_run else f"{_GREEN}[COMMITTED]{_RESET}"
    print(f"\n{_CYAN}▶{_RESET} Synlynk Capability Backfill {mode_label}")
    print(f"  Analyzed ratings:  {report['total_ratings_analyzed']}")
    print(f"  Disciplines mapped: {report['updated_count']}")
    print(f"  Active SFIA (≥1%):  {', '.join(report['active_disciplines']) or 'None'}")
    print(f"  Models in window:  {report['synced_models_count']}\n")

    print("  " + "─" * 76)
    print(f"  {'Harness':<10} {'SFIA':<6} {'Name':<24} {'Tasks':>6} {'Ver%':>6} {'Score':>6} {'Status':>10}")
    print("  " + "─" * 76)

    for item in report["summary"]:
        status = f"{_GREEN}ACTIVE{_RESET}" if item["sample_floor_met"] and item["qualifies_attribution"] else f"{_YELLOW}UNMEAS{_RESET}"
        ver_pct = f"{round((item['verified_count'] / item['task_count']) * 100)}%" if item["task_count"] > 0 else "0%"
        print(
            f"  {item['agent']:<10} {item['discipline']:<6} {item['discipline_name'][:24]:<24} "
            f"{item['task_count']:>6} {ver_pct:>6} {item['avg_quality']:>6.2f} {status:>10}"
        )

    print("  " + "─" * 76 + "\n")
    return 0
