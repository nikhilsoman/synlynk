"""Live capability-based routing for agent="auto" dispatches.

Ranks eligible harnesses (the primary + fallback list already configured in
policy.json's overrides.dev_authority.task_allocation[task_type]) using
capability_ratings/cost_entries once a harness has >=SAMPLE_SIZE_FLOOR
samples for the task type; round-robins across the eligible set below that
floor instead of defaulting to one hardcoded harness.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md
Section 2.
"""
import sqlite3
from statistics import median
from typing import Optional

SAMPLE_SIZE_FLOOR = 5
SCORE_COST_DIVISOR = {
    "implement": 50.0,
    "test": 50.0,
    "review": 30.0,
    "refactor": 50.0,
    "cli-plumbing": 50.0,
}
_DEFAULT_SCORE_COST_DIVISOR = 50.0


class LiveQueryRouter:
    """Selects one harness from an eligible set for a task type."""

    def select(self, eligible_harnesses: list[str], task_type: str, db_conn: sqlite3.Connection) -> str:
        if not eligible_harnesses:
            raise ValueError("eligible_harnesses must be non-empty")
        if len(eligible_harnesses) == 1:
            return eligible_harnesses[0]

        samples = {h: self._sample_count(db_conn, h, task_type) for h in eligible_harnesses}
        below_floor = [h for h in eligible_harnesses if samples[h] < SAMPLE_SIZE_FLOOR]
        if below_floor:
            return self._round_robin(db_conn, task_type, below_floor)

        scored = [
            (self._score(db_conn, h, task_type), -samples[h], h)
            for h in eligible_harnesses
        ]
        scored.sort()  # lowest score first, then higher sample_count (more negative), then alphabetical
        return scored[0][2]

    def _sample_count(self, conn: sqlite3.Connection, harness: str, task_type: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
            (harness, task_type),
        ).fetchone()
        return row[0] if row else 0

    def _score(self, conn: sqlite3.Connection, harness: str, task_type: str) -> float:
        cycles = [
            row[0] for row in conn.execute(
                "SELECT pr_review_cycles FROM capability_ratings "
                "WHERE agent=? AND discipline=? AND pr_review_cycles IS NOT NULL",
                (harness, task_type),
            ).fetchall()
        ]
        costs = [
            row[0] for row in conn.execute(
                "SELECT total_cost_usd FROM cost_entries "
                "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
                (harness, task_type),
            ).fetchall()
        ]
        divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_SCORE_COST_DIVISOR)
        median_cycles = median(cycles) if cycles else 0.0
        median_cost = median(costs) if costs else 0.0
        return median_cycles + (median_cost / divisor)

    def _round_robin(self, conn: sqlite3.Connection, task_type: str, eligible_harnesses: list[str]) -> str:
        row = conn.execute(
            "SELECT cursor FROM routing_rotation_state WHERE task_type=?", (task_type,)
        ).fetchone()
        cursor = row[0] if row else 0
        picked = eligible_harnesses[cursor % len(eligible_harnesses)]
        conn.execute(
            "INSERT INTO routing_rotation_state (task_type, cursor, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(task_type) DO UPDATE SET cursor=excluded.cursor, updated_at=excluded.updated_at",
            (task_type, cursor + 1),
        )
        conn.commit()
        return picked
