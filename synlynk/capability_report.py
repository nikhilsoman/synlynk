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
    "docs": "content",
    "security": "refactor",
    "ml": None,
    "PROG": "implement",
    "TEST": "test",
    "REQM": "brainstorm",
    "COMM": "content",
    "PROD": "pm",
    "DBDS": "infra",
    "VISU": "css",
}

MIN_REWORK_RATE_MARGIN_PP = 10.0


def _column_exists(conn, table: str, column: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def _fetch_rows(conn):
    """Return rows and whether capability_ratings has quality_verified.

    Filters out synthetic seed rows (local agent, quality=0.6, or seed story IDs).
    """
    has_quality_verified = _column_exists(
        conn, "capability_ratings", "quality_verified"
    )
    has_quality = _column_exists(conn, "capability_ratings", "quality")
    qv_select = "cr.quality_verified" if has_quality_verified else "NULL"
    quality_filter = " AND (cr.quality IS NULL OR cr.quality != 0.6)" if has_quality else ""
    query = (
        "SELECT cr.story_id, cr.agent, cr.discipline, cr.pr_review_cycles, "
        "cr.dispatch_rework, cr.micro_rework, "
        f"{qv_select}, ce.total_cost_usd, ce.pr_number, ce.job_id "
        "FROM capability_ratings cr JOIN cost_entries ce ON cr.story_id = ce.story_id "
        f"WHERE cr.agent != 'local' AND cr.story_id NOT LIKE 'seed-%' AND cr.story_id NOT LIKE 'local-seed-%'{quality_filter}"
    )
    rows = conn.execute(query).fetchall()
    return [tuple(row) for row in rows], has_quality_verified


def _dedupe_cost_rows(rows):
    """Keep one cost contribution per story and PR, or story and job."""
    seen = set()
    deduped = []
    for row in rows:
        (
            story_id,
            _harness,
            _discipline,
            _cycles,
            _dispatch_rework,
            _micro_rework,
            _qv,
            _cost,
            pr_number,
            job_id,
        ) = row
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
    buckets = defaultdict(
        lambda: {
            "cycles": [],
            "costs": [],
            "dispatch_rework": [],
            "micro_rework": [],
            "story_ids": set(),
        }
    )
    skipped_no_mapping = 0
    for (
        story_id,
        harness,
        discipline,
        cycles,
        dispatch_rework,
        micro_rework,
        _qv,
        cost,
        _pr_number,
        _job_id,
    ) in rows:
        task_type = DISCIPLINE_TO_TASK_TYPE.get(discipline)
        if task_type is None:
            skipped_no_mapping += 1
            continue
        bucket = buckets[(harness, task_type)]
        if cycles is not None:
            bucket["cycles"].append(cycles)
        if cost is not None:
            bucket["costs"].append(cost)
        if dispatch_rework is not None:
            bucket["dispatch_rework"].append(dispatch_rework)
        if micro_rework is not None:
            bucket["micro_rework"].append(micro_rework)
        bucket["story_ids"].add(story_id)
    return dict(buckets), skipped_no_mapping


def summarize_buckets(buckets: dict, min_sample_size: int) -> dict:
    """Return sample counts, gate status, and metric medians/rates per bucket."""
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
            "dispatch_rework_rate": (
                sum(1 for value in data["dispatch_rework"] if value > 0)
                / len(data["dispatch_rework"])
                * 100.0
                if data["dispatch_rework"]
                else None
            ),
            "micro_rework_rate": (
                sum(1 for value in data["micro_rework"] if value > 0)
                / len(data["micro_rework"])
                * 100.0
                if data["micro_rework"]
                else None
            ),
        }
    return summary


def propose_diff(summary: dict, current_task_allocation: dict, min_sample_size: int) -> list:
    """Return harness swaps where a measured candidate beats both metrics.

    Quality requires the candidate's dispatch rework rate to be at least
    ``MIN_REWORK_RATE_MARGIN_PP`` percentage points below the incumbent's.
    Review-cycle medians remain in summaries as historical report context.
    """
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
            rework_rate_ok = (
                entry["dispatch_rework_rate"] is not None
                and current_entry["dispatch_rework_rate"] is not None
                and (
                    current_entry["dispatch_rework_rate"]
                    - entry["dispatch_rework_rate"]
                )
                >= MIN_REWORK_RATE_MARGIN_PP
            )
            cost_ok = (
                entry["median_total_cost_usd"] is not None
                and current_entry["median_total_cost_usd"] is not None
                and entry["median_total_cost_usd"] < current_entry["median_total_cost_usd"]
            )
            if rework_rate_ok and cost_ok:
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


def apply_proposals(proposals: list, policy_path: str = ".synlynk/policy.json") -> bool:
    """Apply proposed task allocation routing changes to policy.json."""
    if not proposals:
        print("No routing changes to apply.")
        return False
    policy = _load_policy(policy_path)
    allocations = (
        policy.setdefault("overrides", {})
        .setdefault("dev_authority", {})
        .setdefault("task_allocation", {})
    )
    changes_made = False
    for p in proposals:
        task_type = p["task_type"]
        new_harness = p["proposed_harness"]
        old_harness = p["current_harness"]
        if task_type in allocations:
            allocations[task_type]["harness"] = new_harness
            fallbacks = allocations[task_type].setdefault("fallback", [])
            if old_harness not in fallbacks:
                fallbacks.insert(0, old_harness)
            if new_harness in fallbacks:
                fallbacks.remove(new_harness)
            changes_made = True
            print(f"Applied routing update for '{task_type}': {old_harness} -> {new_harness}")
        else:
            allocations[task_type] = {"harness": new_harness, "fallback": [old_harness]}
            changes_made = True
            print(f"Added routing for '{task_type}': {new_harness} (fallback: {old_harness})")
    if changes_made:
        with open(policy_path, "w") as f:
            json.dump(policy, f, indent=2)
            f.write("\n")
        print(f"Updated {policy_path} successfully.")
    return changes_made


def cmd_capability_report(
    as_json: bool = False,
    apply: bool = False,
    policy_path: str = ".synlynk/policy.json",
) -> None:
    """Print or apply a task allocation proposal from the canonical state DB."""
    from synlynk import _get_db

    policy = _load_policy(policy_path)
    min_sample_size = policy["capability_policy"]["min_sample_size"]
    current_task_allocation = policy["overrides"]["dev_authority"]["task_allocation"]

    conn = _get_db(read_only=True)
    try:
        buckets, skipped_no_mapping = build_buckets(conn)
    finally:
        conn.close()

    summary = summarize_buckets(buckets, min_sample_size)
    proposals = propose_diff(summary, current_task_allocation, min_sample_size)

    if apply:
        apply_proposals(proposals, policy_path=policy_path)
        return

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
