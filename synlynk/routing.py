"""Live capability-based routing for agent="auto" dispatches.

Ranks eligible harnesses (the primary + fallback list already configured in
policy.json's overrides.dev_authority.task_allocation[task_type]) using
capability_ratings/cost_entries once a harness has >=SAMPLE_SIZE_FLOOR
samples for the task type; round-robins across the eligible set below that
floor instead of defaulting to one hardcoded harness.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md
Section 2.
"""
import logging
import sqlite3
import json
from statistics import median
from typing import Optional

SAMPLE_SIZE_FLOOR = 5
EXPLORATION_SPEND_CAP_USD = 10.0
SCORE_COST_DIVISOR = {
    "implement": 50.0,
    "test": 50.0,
    "review": 30.0,
    "refactor": 50.0,
    "cli-plumbing": 50.0,
}
_DEFAULT_SCORE_COST_DIVISOR = 50.0
SUB_FLOOR_GUARDED_TASK_TYPES = frozenset({"deploy", "infra", "architecture-review"})


def sub_floor_exploration_mode(policy_path: str = ".synlynk/policy.json") -> str:
    """Return the blast-radius guard mode, defaulting closed to ``observe``.

    The mode follows the existing policy gate convention: invalid, missing, or
    malformed policy values are non-blocking until an operator explicitly
    opts into enforcement.
    """
    try:
        with open(policy_path, encoding="utf-8") as handle:
            policy = json.load(handle)
        mode = (policy.get("overrides") or {}).get("sub_floor_exploration_mode")
        return mode if mode in ("observe", "enforce") else "observe"
    except (OSError, TypeError, ValueError):
        return "observe"


MIN_VERDICTS_FOR_SUCCESS_RATIO = 3
SCORE_WEIGHTS = {
    "success_deficit": 2.0,
    "rework": 1.0,
    "cost_time": 1.0,
}

logger = logging.getLogger(__name__)


def _sample_count(conn: sqlite3.Connection, harness: str, task_type: str) -> int:
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)").fetchall()
    }
    source_filter = (
        " AND (signal_source IS NULL OR signal_source != 'baseline_seed')"
        if "signal_source" in columns
        else ""
    )
    row = conn.execute(
        "SELECT COUNT(*) FROM capability_ratings "
        "WHERE agent=? AND discipline=?" + source_filter,
        (harness, task_type),
    ).fetchone()
    return int(row[0]) if row else 0


class LiveQueryRouter:
    """Selects one harness from an eligible set for a task type."""

    def __init__(self):
        self.last_selection = {
            "harness": None,
            "task_type": None,
            "sub_floor": False,
        }

    def select(self, eligible_harnesses: list[str], task_type: str, db_conn: sqlite3.Connection) -> str:
        if not eligible_harnesses:
            raise ValueError("eligible_harnesses must be non-empty")
        if len(eligible_harnesses) == 1:
            self.last_selection = {
                "harness": eligible_harnesses[0],
                "task_type": task_type,
                "sub_floor": False,
            }
            return eligible_harnesses[0]

        samples = {h: self._sample_count(db_conn, h, task_type) for h in eligible_harnesses}
        below_floor = [
            h for h in eligible_harnesses
            if not is_calibrated(h, task_type, db_conn)
        ]
        if below_floor:
            picked = self._round_robin(db_conn, task_type, below_floor)
            self.last_selection = {
                "harness": picked,
                "task_type": task_type,
                "sub_floor": True,
            }
            return picked

        scored = [
            (self._score(db_conn, h, task_type, eligible_harnesses), -samples[h], h)
            for h in eligible_harnesses
        ]
        scored.sort()  # lowest score first, then higher sample_count (more negative), then alphabetical
        picked = scored[0][2]
        self.last_selection = {
            "harness": picked,
            "task_type": task_type,
            "sub_floor": False,
        }
        return picked

    def _sample_count(self, conn: sqlite3.Connection, harness: str, task_type: str) -> int:
        return _sample_count(conn, harness, task_type)

    def _score(
        self,
        conn: sqlite3.Connection,
        harness: str,
        task_type: str,
        eligible_harnesses: Optional[list[str]] = None,
    ) -> float:
        """Return the normalized composite deficit score for one routing cell.

        Lower is better. Missing sub-statistics use the median observed in the
        other eligible harnesses, so sparse data is neutral rather than a
        reward. ``eligible_harnesses`` is optional for callers inspecting one
        harness in isolation; routing always supplies the full cell.
        """
        eligible = eligible_harnesses or [harness]
        components = self._score_components(conn, task_type, eligible)
        score = sum(
            SCORE_WEIGHTS[name] * values[harness]
            for name, values in components["normalized"].items()
        )
        logger.debug(
            "routing score cell=%s harness=%s score=%s components=%s",
            task_type, harness, score,
            {name: values[harness] for name, values in components["normalized"].items()},
        )
        return score

    def _score_components(
        self,
        conn: sqlite3.Connection,
        task_type: str,
        eligible_harnesses: list[str],
    ) -> dict:
        try:
            cols = {
                r[1] for r in conn.execute("PRAGMA table_info(capability_ratings)").fetchall()
            }
        except Exception:
            cols = set()

        def col_or_null(name: str) -> str:
            return name if name in cols else f"NULL AS {name}"

        query = (
            f"SELECT {col_or_null('pr_review_cycles')}, "
            f"{col_or_null('dispatch_rework')}, "
            f"{col_or_null('micro_rework')}, "
            f"{col_or_null('duration_vs_estimate')}, "
            f"{col_or_null('correct')} "
            f"FROM capability_ratings WHERE agent=? AND discipline=?"
        )
        ratings = {}
        for harness in eligible_harnesses:
            ratings[harness] = conn.execute(
                query,
                (harness, task_type),
            ).fetchall()

        def impute(values_by_harness: dict[str, list[float]], label: str) -> dict[str, float]:
            observed = {h: median(values) for h, values in values_by_harness.items() if values}
            if not observed:
                logger.debug("routing score degenerate cell=%s substat=%s", task_type, label)
                return {h: 0.0 for h in eligible_harnesses}
            result = {}
            for h in eligible_harnesses:
                if h in observed:
                    result[h] = observed[h]
                    continue
                substitute = median(observed.values())
                logger.debug(
                    "routing score imputed cell=%s harness=%s substat=%s value=%s",
                    task_type, h, label, substitute,
                )
                result[h] = substitute
            return result

        cycles = {
            h: [row[0] for row in rows if row[0] is not None]
            for h, rows in ratings.items()
        }
        rework = {
            h: [float((row[1] or 0) != 0 or (row[2] or 0) != 0) for row in rows
                if row[1] is not None or row[2] is not None]
            for h, rows in ratings.items()
        }
        durations = {
            h: [row[3] for row in rows if row[3] is not None]
            for h, rows in ratings.items()
        }
        costs = {
            h: [row[0] for row in conn.execute(
                "SELECT total_cost_usd FROM cost_entries_effective "
                "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
                (h, task_type),
            ).fetchall()]
            for h in eligible_harnesses
        }

        cycle_values = impute(cycles, "pr_review_cycles")
        rework_values = impute(rework, "rework")
        duration_values = impute(durations, "duration_vs_estimate")
        cost_values = impute(costs, "total_cost_usd")

        qualified_ratios = {}
        for h, rows in ratings.items():
            verdicts = [row[4] for row in rows if row[4] is not None]
            if len(verdicts) >= MIN_VERDICTS_FOR_SUCCESS_RATIO:
                qualified_ratios[h] = sum(v == 1 for v in verdicts) / len(verdicts)
        if qualified_ratios:
            success = {}
            for h in eligible_harnesses:
                if h in qualified_ratios:
                    success[h] = qualified_ratios[h]
                else:
                    success[h] = median(qualified_ratios.values())
                    logger.debug(
                        "routing score imputed cell=%s harness=%s substat=success_ratio value=%s",
                        task_type, h, success[h],
                    )
        else:
            logger.debug("routing score degenerate cell=%s substat=success_ratio", task_type)
            success = {h: 1.0 for h in eligible_harnesses}

        divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_SCORE_COST_DIVISOR)
        raw = {
            "success_deficit": {h: 1.0 - success[h] for h in eligible_harnesses},
            "rework": {h: cycle_values[h] + rework_values[h] for h in eligible_harnesses},
            "cost_time": {
                h: cost_values[h] / divisor + duration_values[h]
                for h in eligible_harnesses
            },
        }
        normalized = {
            name: self._normalize(values)
            for name, values in raw.items()
        }
        return {"raw": raw, "normalized": normalized, "success_ratio": success}

    @staticmethod
    def _normalize(values: dict[str, float]) -> dict[str, float]:
        low = min(values.values())
        high = max(values.values())
        if high == low:
            return {h: 0.0 for h in values}
        return {h: (value - low) / (high - low) for h, value in values.items()}

    def _round_robin(self, conn: sqlite3.Connection, task_type: str, eligible_harnesses: list[str]) -> str:
        eligible_harnesses = [
            harness for harness in eligible_harnesses
            if self._exploration_spend(conn, harness, task_type) < EXPLORATION_SPEND_CAP_USD
        ]
        if not eligible_harnesses:
            raise ValueError(
                f"exploration spend cap reached for every sub-floor harness in {task_type!r}"
            )
        row = conn.execute(
            "SELECT cursor FROM routing_rotation_state WHERE task_type=?", (task_type,)
        ).fetchone()
        cursor = row[0] if row else 0
        picked = eligible_harnesses[cursor % len(eligible_harnesses)]
        spend = self._exploration_spend(conn, picked, task_type)
        state_cols = {row[1] for row in conn.execute("PRAGMA table_info(routing_rotation_state)")}
        if "exploration_spend_usd" in state_cols:
            conn.execute(
                "INSERT INTO routing_rotation_state "
                "(task_type, cursor, exploration_spend_usd, updated_at) "
                "VALUES (?, ?, ?, datetime('now')) "
                "ON CONFLICT(task_type) DO UPDATE SET cursor=excluded.cursor, "
                "exploration_spend_usd=excluded.exploration_spend_usd, "
                "updated_at=excluded.updated_at",
                (task_type, cursor + 1, spend),
            )
        else:
            conn.execute(
                "INSERT INTO routing_rotation_state (task_type, cursor, updated_at) "
                "VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(task_type) DO UPDATE SET cursor=excluded.cursor, updated_at=excluded.updated_at",
                (task_type, cursor + 1),
            )
        conn.commit()
        return picked

    @staticmethod
    def _exploration_spend(conn: sqlite3.Connection, harness: str, task_type: str) -> float:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_entries_effective "
            "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
            (harness, task_type),
        ).fetchone()
        return float(row[0] or 0.0) if row else 0.0


def is_calibrated(harness: str, task_type: str, conn: sqlite3.Connection) -> bool:
    """Return whether a harness has enough measured samples for one task cell."""
    return _sample_count(conn, harness, task_type) >= SAMPLE_SIZE_FLOOR
