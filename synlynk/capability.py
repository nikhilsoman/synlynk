"""Empirical capability ledger and Bayesian capability scoring.

The ledger deliberately keeps observations separate from the older, story-scoped
``capability_ratings`` table.  It is safe to use this module with a bare SQLite
connection in tests; the table is created lazily as well as by the normal DB
migration.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS capability_ledger (
        model_id TEXT NOT NULL,
        harness TEXT NOT NULL,
        task_domain TEXT NOT NULL,
        alpha REAL NOT NULL DEFAULT 1.0,
        beta REAL NOT NULL DEFAULT 1.0,
        prior_alpha REAL NOT NULL DEFAULT 1.0,
        prior_beta REAL NOT NULL DEFAULT 1.0,
        recency_half_life REAL NOT NULL DEFAULT 30.0,
        token_productivity_ratio REAL,
        output_tokens_accepted INTEGER NOT NULL DEFAULT 0,
        total_tokens_spent INTEGER NOT NULL DEFAULT 0,
        p95_latency REAL,
        observations INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (model_id, harness, task_domain)
    )""")


def _as_success(outcome: Any) -> bool:
    if isinstance(outcome, str):
        return outcome.strip().lower() in {"1", "true", "success", "succeeded", "pass", "passed", "ok", "green"}
    return bool(outcome)


def _now(value: datetime | str | None) -> tuple[datetime, str]:
    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt, dt.isoformat()


def _connection(conn=None):
    if conn is not None:
        return conn, False
    from synlynk import _get_db
    return _get_db(), True


def update_capability_score(
    model_id: str,
    harness: str,
    task_domain: str,
    outcome: Any,
    *,
    conn: sqlite3.Connection | None = None,
    observed_at: datetime | str | None = None,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    recency_half_life: float = 30.0,
    output_tokens_accepted: int = 0,
    total_tokens_spent: int = 0,
    p95_latency: float | None = None,
) -> dict:
    """Record one verified outcome and return its posterior score.

    Old evidence is shrunk toward the configured Beta prior by ``2**(-age /
    recency_half_life)`` before the new observation is applied.  Thus model
    upgrades can change the score without deleting historical provenance.
    """
    if not model_id or not harness or not task_domain:
        raise ValueError("model_id, harness, and task_domain are required")
    if prior_alpha <= 0 or prior_beta <= 0 or recency_half_life <= 0:
        raise ValueError("Beta priors and recency_half_life must be positive")
    db, owned = _connection(conn)
    try:
        _ensure_table(db)
        dt, timestamp = _now(observed_at)
        row = db.execute(
            "SELECT * FROM capability_ledger WHERE model_id=? AND harness=? AND task_domain=?",
            (model_id, harness, task_domain),
        ).fetchone()
        if row:
            names = [d[0] for d in db.execute("SELECT * FROM capability_ledger LIMIT 0").description]
            old = dict(zip(names, row))
            previous = datetime.fromisoformat(old["updated_at"].replace("Z", "+00:00"))
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (dt - previous).total_seconds() / 86400)
            decay = math.pow(0.5, age_days / float(old["recency_half_life"] or recency_half_life))
            alpha = float(old["prior_alpha"]) + (float(old["alpha"]) - float(old["prior_alpha"])) * decay
            beta = float(old["prior_beta"]) + (float(old["beta"]) - float(old["prior_beta"])) * decay
            p_alpha, p_beta, half_life = old["prior_alpha"], old["prior_beta"], old["recency_half_life"]
            out_accepted = old["output_tokens_accepted"] + int(output_tokens_accepted or 0)
            spent = old["total_tokens_spent"] + int(total_tokens_spent or 0)
            observations = old["observations"] + 1
        else:
            alpha, beta = float(prior_alpha), float(prior_beta)
            p_alpha, p_beta, half_life = prior_alpha, prior_beta, recency_half_life
            out_accepted, spent, observations = int(output_tokens_accepted or 0), int(total_tokens_spent or 0), 1
        if _as_success(outcome):
            alpha += 1.0
        else:
            beta += 1.0
        ratio = (out_accepted / spent) if spent > 0 else None
        db.execute("""INSERT INTO capability_ledger
            (model_id,harness,task_domain,alpha,beta,prior_alpha,prior_beta,recency_half_life,
             token_productivity_ratio,output_tokens_accepted,total_tokens_spent,p95_latency,observations,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(model_id,harness,task_domain) DO UPDATE SET
              alpha=excluded.alpha,beta=excluded.beta,prior_alpha=excluded.prior_alpha,
              prior_beta=excluded.prior_beta,recency_half_life=excluded.recency_half_life,
              token_productivity_ratio=excluded.token_productivity_ratio,
              output_tokens_accepted=excluded.output_tokens_accepted,total_tokens_spent=excluded.total_tokens_spent,
              p95_latency=COALESCE(excluded.p95_latency, capability_ledger.p95_latency),
              observations=excluded.observations,updated_at=excluded.updated_at""",
            (model_id, harness, task_domain, alpha, beta, p_alpha, p_beta, half_life,
             ratio, out_accepted, spent, p95_latency, observations, timestamp),
        )
        db.commit()
        return {"model_id": model_id, "harness": harness, "task_domain": task_domain,
                "alpha": alpha, "beta": beta, "success_probability": alpha / (alpha + beta),
                "token_productivity_ratio": ratio, "observations": observations, "updated_at": timestamp}
    finally:
        if owned:
            db.close()


def capability_score(model_id: str, harness: str, task_domain: str, *, conn=None) -> dict | None:
    db, owned = _connection(conn)
    try:
        _ensure_table(db)
        row = db.execute("SELECT * FROM capability_ledger WHERE model_id=? AND harness=? AND task_domain=?",
                         (model_id, harness, task_domain)).fetchone()
        if not row:
            return None
        names = [d[0] for d in db.execute("SELECT * FROM capability_ledger LIMIT 0").description]
        result = dict(zip(names, row))
        result["success_probability"] = result["alpha"] / (result["alpha"] + result["beta"])
        return result
    finally:
        if owned:
            db.close()


def expected_value(success_probability: float, criticality: float, amortized_cost: float,
                   p95_latency: float, lambda_: float = 1.0) -> float:
    """Return the dispatch EV; invalid/non-positive denominators are ineligible."""
    denominator = float(amortized_cost) + float(lambda_) * float(p95_latency)
    if denominator <= 0:
        return 0.0
    return float(success_probability) * float(criticality) / denominator


def route_expected_value(candidates: Iterable, task_domain: str, criticality: float = 1.0,
                         *, conn=None, lambda_: float = 1.0, costs=None, latencies=None):
    """Choose the highest-EV candidate, returning a scored candidate dictionary."""
    db, owned = _connection(conn)
    try:
        _ensure_table(db)
        costs, latencies = costs or {}, latencies or {}
        scored = []
        for candidate in candidates:
            harness = candidate if isinstance(candidate, str) else candidate.get("harness") or candidate.get("agent")
            model_id = candidate if isinstance(candidate, str) else candidate.get("model_id", harness)
            row = capability_score(model_id, harness, task_domain, conn=db) or {"alpha": 1.0, "beta": 1.0, "success_probability": 0.5}
            cost = costs.get(model_id, costs.get(harness, 1.0))
            latency = latencies.get(model_id, latencies.get(harness, 1.0))
            item = {"harness": harness, "model_id": model_id, "success_probability": row["success_probability"],
                    "expected_value": expected_value(row["success_probability"], criticality, cost, latency, lambda_)}
            scored.append(item)
        return max(scored, key=lambda item: item["expected_value"]) if scored else None
    finally:
        if owned:
            db.close()
