"""Generate a task_allocation routing proposal from capability data.

Read-only: never writes to .synlynk/policy.json or state.db. See
docs/superpowers/specs/2026-10-11-synlynk-capability-report-design.md (gh:#1993).
"""
from __future__ import annotations

from collections import defaultdict
import json
import statistics

DISCIPLINE_TO_TASK_TYPE = {
    "testing": "test",
    "backend": "implement",
    "frontend": "implement",
    "cli": "cli-plumbing",
    "devops": "infra",
    "architecture": "review",
    "docs": None,
    "security": None,
    "ml": None,
    "PROG": None,
}


def _column_exists(conn, table: str, column: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def _fetch_rows(conn):
    """Return rows and whether capability_ratings has quality_verified."""
    has_quality_verified = _column_exists(
        conn, "capability_ratings", "quality_verified"
    )
    qv_select = "cr.quality_verified" if has_quality_verified else "NULL"
    query = (
        "SELECT cr.story_id, cr.agent, cr.discipline, cr.pr_review_cycles, "
        f"{qv_select}, ce.total_cost_usd, ce.pr_number, ce.job_id "
        "FROM capability_ratings cr JOIN cost_entries ce ON cr.story_id = ce.story_id"
    )
    rows = conn.execute(query).fetchall()
    return [tuple(row) for row in rows], has_quality_verified


def _dedupe_cost_rows(rows):
    """Keep one cost contribution per story and PR, or story and job."""
    seen = set()
    deduped = []
    for row in rows:
        story_id, _harness, _discipline, _cycles, _qv, _cost, pr_number, job_id = row
        key = (
            (story_id, "pr", pr_number)
            if pr_number is not None
            else (story_id, "job", job_id)
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def build_buckets(conn):
    """Return ``(buckets, skipped_no_mapping)`` grouped by harness and task type."""
    rows, _has_quality_verified = _fetch_rows(conn)
    rows = _dedupe_cost_rows(rows)
    buckets = defaultdict(lambda: {"cycles": [], "costs": [], "story_ids": set()})
    skipped_no_mapping = 0
    for story_id, harness, discipline, cycles, _qv, cost, _pr_number, _job_id in rows:
        task_type = DISCIPLINE_TO_TASK_TYPE.get(discipline)
        if task_type is None:
            skipped_no_mapping += 1
            continue
        bucket = buckets[(harness, task_type)]
        if cycles is not None:
            bucket["cycles"].append(cycles)
        if cost is not None:
            bucket["costs"].append(cost)
        bucket["story_ids"].add(story_id)
    return dict(buckets), skipped_no_mapping


def summarize_buckets(buckets: dict, min_sample_size: int) -> dict:
    """Return sample counts, gate status, and metric medians per bucket."""
    summary = {}
    for key, data in buckets.items():
        n = len(data["story_ids"])
        summary[key] = {
            "n": n,
            "measured": n >= min_sample_size,
            "median_pr_review_cycles": (
                statistics.median(data["cycles"]) if data["cycles"] else None
            ),
            "median_total_cost_usd": (
                statistics.median(data["costs"]) if data["costs"] else None
            ),
        }
    return summary


def propose_diff(summary: dict, current_task_allocation: dict, min_sample_size: int) -> list:
    """Return harness swaps where a measured candidate beats both metrics."""
    by_task_type = defaultdict(dict)
    for (harness, task_type), entry in summary.items():
        by_task_type[task_type][harness] = entry

    proposals = []
    for task_type, current in current_task_allocation.items():
        current_harness = current.get("harness")
        candidates = by_task_type.get(task_type, {})
        current_entry = candidates.get(current_harness)
        if current_entry is None or not current_entry["measured"]:
            continue
        for harness, entry in candidates.items():
            if harness == current_harness or not entry["measured"]:
                continue
            cycles_ok = (
                entry["median_pr_review_cycles"] is not None
                and current_entry["median_pr_review_cycles"] is not None
                and entry["median_pr_review_cycles"]
                < current_entry["median_pr_review_cycles"]
            )
            cost_ok = (
                entry["median_total_cost_usd"] is not None
                and current_entry["median_total_cost_usd"] is not None
                and entry["median_total_cost_usd"] < current_entry["median_total_cost_usd"]
            )
            if cycles_ok and cost_ok:
                proposals.append(
                    {
                        "task_type": task_type,
                        "current_harness": current_harness,
                        "current": current_entry,
                        "proposed_harness": harness,
                        "proposed": entry,
                    }
                )
    return proposals


def format_text_report(proposals: list, summary: dict, skipped_no_mapping: int) -> str:
    lines = []
    if not proposals:
        lines.append(
            "No routing changes proposed (no harness clears min_sample_size "
            "with a strictly better median on both metrics)."
        )
    for proposal in proposals:
        current, proposed = proposal["current"], proposal["proposed"]
        lines.append(
            f"{proposal['task_type']}: {proposal['current_harness']} "
            f"(current, n={current['n']}, "
            f"cycles={current['median_pr_review_cycles']}, "
            f"cost=${current['median_total_cost_usd']:.2f}) -> "
            f"{proposal['proposed_harness']} (n={proposed['n']}, "
            f"cycles={proposed['median_pr_review_cycles']}, "
            f"cost=${proposed['median_total_cost_usd']:.2f})"
        )
    lines.append(f"\n{skipped_no_mapping} rows skipped (discipline has no task_type mapping).")
    return "\n".join(lines)


def _load_policy(path: str = ".synlynk/policy.json") -> dict:
    with open(path) as policy_file:
        return json.load(policy_file)


def cmd_capability_report(as_json: bool = False) -> None:
    """Print a read-only task allocation proposal from the canonical state DB."""
    from synlynk import _get_db

    policy = _load_policy()
    min_sample_size = policy["capability_policy"]["min_sample_size"]
    current_task_allocation = policy["overrides"]["dev_authority"]["task_allocation"]

    conn = _get_db(read_only=True)
    try:
        buckets, skipped_no_mapping = build_buckets(conn)
    finally:
        conn.close()

    summary = summarize_buckets(buckets, min_sample_size)
    proposals = propose_diff(summary, current_task_allocation, min_sample_size)

    if as_json:
        print(
            json.dumps(
                {"proposals": proposals, "skipped_no_mapping": skipped_no_mapping},
                indent=2,
                default=str,
            )
        )
    else:
        print(format_text_report(proposals, summary, skipped_no_mapping))
