"""Live capability-based routing for automatic dispatches."""

from statistics import median


SAMPLE_SIZE_FLOOR = 5
_SCORE_COST_DIVISOR = {
    "implement": 50.0,
    "test": 50.0,
    "review": 30.0,
    "refactor": 50.0,
    "cli-plumbing": 50.0,
}


class LiveQueryRouter:
    """Select a harness from an already-eligible task allocation."""

    def select(self, eligible_harnesses, task_type, db_conn):
        if not eligible_harnesses:
            raise ValueError("eligible_harnesses must be non-empty")
        if len(eligible_harnesses) == 1:
            return eligible_harnesses[0]

        samples = {
            harness: self._sample_count(db_conn, harness, task_type)
            for harness in eligible_harnesses
        }
        below_floor = [
            harness for harness in eligible_harnesses
            if samples[harness] < SAMPLE_SIZE_FLOOR
        ]
        if below_floor:
            return self._round_robin(db_conn, task_type, below_floor)

        scored = [
            (self._score(db_conn, harness, task_type), -samples[harness], harness)
            for harness in eligible_harnesses
        ]
        return min(scored)[2]

    def _sample_count(self, conn, harness, task_type):
        row = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
            (harness, task_type),
        ).fetchone()
        return row[0] if row else 0

    def _score(self, conn, harness, task_type):
        cycles = [
            row[0] for row in conn.execute(
                "SELECT pr_review_cycles FROM capability_ratings "
                "WHERE agent=? AND discipline=? AND pr_review_cycles IS NOT NULL",
                (harness, task_type),
            )
        ]
        costs = [
            row[0] for row in conn.execute(
                "SELECT total_cost_usd FROM cost_entries "
                "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
                (harness, task_type),
            )
        ]
        divisor = _SCORE_COST_DIVISOR.get(task_type, 50.0)
        return (median(cycles) if cycles else 0.0) + (median(costs) if costs else 0.0) / divisor

    def _round_robin(self, conn, task_type, eligible_harnesses):
        row = conn.execute(
            "SELECT cursor FROM routing_rotation_state WHERE task_type=?",
            (task_type,),
        ).fetchone()
        cursor = row[0] if row else 0
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
