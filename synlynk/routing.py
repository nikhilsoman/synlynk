"""Live capability-based routing for automatic dispatches."""

import sqlite3
from statistics import median


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
    """Select one eligible harness using live ratings or round-robin exploration."""

    def select(
        self,
        eligible_harnesses: list[str],
        task_type: str,
        db_conn: sqlite3.Connection,
    ) -> str:
        if not eligible_harnesses:
            raise ValueError("eligible_harnesses must be non-empty")
        if len(eligible_harnesses) == 1:
            return eligible_harnesses[0]

        samples = {
            harness: self._sample_count(db_conn, harness, task_type)
            for harness in eligible_harnesses
        }
        below_floor = [
            harness for harness in eligible_harnesses if samples[harness] < SAMPLE_SIZE_FLOOR
        ]
        if below_floor:
            return self._round_robin(db_conn, task_type, below_floor)

        scored = [
            (self._score(db_conn, harness, task_type), -samples[harness], harness)
            for harness in eligible_harnesses
        ]
        return min(scored)[2]

    def _sample_count(self, conn: sqlite3.Connection, harness: str, task_type: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
            (harness, task_type),
        ).fetchone()
        return int(row[0]) if row else 0

    def _score(self, conn: sqlite3.Connection, harness: str, task_type: str) -> float:
        cycles = [
            row[0]
            for row in conn.execute(
                "SELECT pr_review_cycles FROM capability_ratings "
                "WHERE agent=? AND discipline=? AND pr_review_cycles IS NOT NULL",
                (harness, task_type),
            )
        ]
        costs = [
            row[0]
            for row in conn.execute(
                "SELECT total_cost_usd FROM cost_entries "
                "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
                (harness, task_type),
            )
        ]
        divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_SCORE_COST_DIVISOR)
        return (median(cycles) if cycles else 0.0) + (
            (median(costs) if costs else 0.0) / divisor
        )

    def _round_robin(
        self,
        conn: sqlite3.Connection,
        task_type: str,
        eligible_harnesses: list[str],
    ) -> str:
        row = conn.execute(
            "SELECT cursor FROM routing_rotation_state WHERE task_type=?", (task_type,)
        ).fetchone()
        cursor = int(row[0]) if row else 0
        picked = eligible_harnesses[cursor % len(eligible_harnesses)]
        conn.execute(
            "INSERT INTO routing_rotation_state (task_type, cursor, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(task_type) DO UPDATE SET cursor=excluded.cursor, "
            "updated_at=excluded.updated_at",
            (task_type, cursor + 1),
        )
        conn.commit()
        return picked
