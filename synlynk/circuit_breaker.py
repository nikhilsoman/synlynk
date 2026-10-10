"""In-flight active token & cost circuit breaker engine (Invariant 2).

Enforces real-time protection against runaway agent worker loops:
Tripped <=> Tokens(Job) >= T_max or Cost(Job) >= C_max
"""

from __future__ import annotations

import os
import signal
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED
from synlynk.sentinel import (
    _write_sentinel_alert,
    log_telemetry_event,
    process_identity_check,
)

DEFAULT_MAX_JOB_TOKENS = 5_000_000
DEFAULT_MAX_JOB_COST_USD = 15.00
DEFAULT_ZERO_FILE_TOKEN_THRESHOLD = 500_000

DEFAULT_TIER_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "fast": {"max_job_tokens": 500_000, "max_job_cost_usd": 2.00},
    "pro": {"max_job_tokens": 3_000_000, "max_job_cost_usd": 10.00},
    "reasoning": {"max_job_tokens": 5_000_000, "max_job_cost_usd": 15.00},
}


@dataclass
class CircuitBreakerResult:
    tripped: bool
    reason: Optional[str] = None
    in_tokens: int = 0
    out_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    process_killed: bool = False
    kill_method: Optional[str] = None


def _resolve_circuit_breaker_limits(
    job: dict,
    config: Optional[dict] = None,
) -> Tuple[int, float, int]:
    """Resolve max_tokens, max_cost, and zero_file_threshold from config and tier overrides."""
    cb_config = {}
    if config and isinstance(config, dict):
        cb_config = config.get("circuit_breaker", {})
        if not isinstance(cb_config, dict):
            cb_config = {}

    max_tokens = int(cb_config.get("max_job_tokens", DEFAULT_MAX_JOB_TOKENS))
    max_cost = float(cb_config.get("max_job_cost_usd", DEFAULT_MAX_JOB_COST_USD))
    zero_file_threshold = int(
        cb_config.get("zero_file_token_threshold", DEFAULT_ZERO_FILE_TOKEN_THRESHOLD)
    )

    tier_overrides = cb_config.get("tier_overrides", DEFAULT_TIER_OVERRIDES)
    job_tier = str(job.get("model_tier") or job.get("tier") or "").strip().lower()

    if job_tier and isinstance(tier_overrides, dict) and job_tier in tier_overrides:
        tier_cfg = tier_overrides[job_tier]
        if isinstance(tier_cfg, dict):
            if "max_job_tokens" in tier_cfg:
                max_tokens = int(tier_cfg["max_job_tokens"])
            if "max_job_cost_usd" in tier_cfg:
                max_cost = float(tier_cfg["max_job_cost_usd"])
            if "zero_file_token_threshold" in tier_cfg:
                zero_file_threshold = int(tier_cfg["zero_file_token_threshold"])

    return max_tokens, max_cost, zero_file_threshold


def _kill_process_tree(
    pid: Optional[int],
    expected_identity: Optional[dict] = None,
    process=None,
    skip_identity_check: bool = False,
    grace_period_seconds: float = 0.5,
) -> Tuple[bool, str]:
    """Safely terminate runaway process tree with SIGTERM escalated to SIGKILL."""
    if process is not None:
        try:
            process.terminate()
            time.sleep(min(0.2, grace_period_seconds))
            if getattr(process, "poll", lambda: None)() is None:
                process.kill()
            return True, "SIGTERM+SIGKILL"
        except Exception:
            pass

    if not pid:
        return False, "no_pid"

    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False, "invalid_pid"

    if not skip_identity_check:
        check = process_identity_check(pid, expected_identity)
        if check != "safe to kill":
            return False, f"PID recycled, skipped kill ({check})"

    try:
        # Step 1: Send SIGTERM
        os.kill(pid, signal.SIGTERM)
        time.sleep(grace_period_seconds)
        
        # Step 2: If still alive, escalate to SIGKILL
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
            return True, "SIGKILL"
        except (ProcessLookupError, OSError):
            return True, "SIGTERM"
    except (ProcessLookupError, OSError):
        return True, "SIGTERM"
    except Exception as exc:
        return False, f"kill_failed: {exc}"


def evaluate_job_circuit_breaker(
    job: dict,
    config: Optional[dict] = None,
    sentinel_path: Optional[str] = None,
    process=None,
    skip_identity_check_for_test: bool = False,
) -> CircuitBreakerResult:
    """Evaluate in-flight job logs and terminate worker if token/cost limits breached."""
    # 1. Check if circuit breaker is globally enabled
    if config and isinstance(config.get("circuit_breaker"), dict):
        if config["circuit_breaker"].get("enabled") is False:
            return CircuitBreakerResult(tripped=False)

    log_file = job.get("log_file")
    log_text = ""
    if log_file and os.path.exists(log_file):
        try:
            with open(log_file, "r", errors="replace") as f:
                log_text = f.read()
        except Exception:
            log_text = ""

    # 2. Extract in-flight token metrics.
    # Codex turn.completed input_tokens sums every tool-loop request, and
    # cached_input_tokens is already inside that sum. Limits compare the
    # uncached remainder so a ~50k prompt replayed from cache is not treated
    # as a million-token prompt.
    from synlynk.costs import extract_tokens, split_billed_tokens
    from synlynk.jobs import _job_cost_usd
    from synlynk.dispatch import _worktree_files_touched

    agent = job.get("agent", "")
    token_counts = extract_tokens(log_text, agent=agent)
    raw_in, out_tokens = token_counts
    cache_read_tokens = int(getattr(token_counts, "cache_read_tokens", 0) or 0)
    in_tokens, _cache = split_billed_tokens(agent, raw_in, cache_read_tokens)
    total_tokens = in_tokens + out_tokens

    model_version = job.get("model_version") or job.get("model_at_dispatch")
    cost_usd = _job_cost_usd(
        agent,
        raw_in,
        out_tokens,
        model_version,
        cache_read_tokens=cache_read_tokens,
    )

    worktree_path = job.get("worktree_path")
    files_touched = 0

    # 4. Resolve limits
    max_tokens, max_cost, zero_file_threshold = _resolve_circuit_breaker_limits(job, config)

    # 5. Check triggers
    reason = None
    if cost_usd >= max_cost:
        reason = f"Cost limit breached: ${cost_usd:.2f} >= ${max_cost:.2f}"
    elif total_tokens >= max_tokens:
        reason = f"Token limit breached: {total_tokens:,} >= {max_tokens:,} tokens"
    elif total_tokens >= zero_file_threshold:
        files_touched_list = _worktree_files_touched(worktree_path) if worktree_path else []
        files_touched = len(files_touched_list)
        if files_touched == 0:
            reason = f"Zero-file runaway: {total_tokens:,} tokens with 0 files touched (limit: {zero_file_threshold:,})"

    if not reason:
        return CircuitBreakerResult(
            tripped=False,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )

    # 6. Trip Circuit Breaker: Kill Process & Stamp Status
    killed, kill_method = _kill_process_tree(
        job.get("pid"),
        job.get("pid_identity"),
        process=process,
        skip_identity_check=skip_identity_check_for_test,
    )

    if not killed:
        log_telemetry_event({
            "type": "circuit_breaker_post_exit_warning",
            "job_id": job.get("id"),
            "agent": job.get("agent"),
            "tokens": total_tokens,
            "cost_usd": cost_usd,
            "reason": reason,
        })
        return CircuitBreakerResult(
            tripped=False,
            reason=reason,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            process_killed=False,
            kill_method=kill_method,
        )

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    job["status"] = STATUS_CIRCUIT_BREAKER_TRIPPED
    job["exit_code"] = -9
    job["ended_at"] = now_iso
    job["circuit_breaker_reason"] = reason
    job["in_tokens"] = in_tokens
    job["out_tokens"] = out_tokens
    job["cost_usd"] = cost_usd

    # 7. Write critical Sentinel Alert
    sentinel_file = sentinel_path or ".synlynk/sentinel.md"
    _write_sentinel_alert(
        "CRITICAL",
        "TOKEN_CIRCUIT_BREAKER_TRIPPED",
        f"Job {job.get('id')} on agent '{job.get('agent')}' terminated by in-flight circuit breaker ({reason}).",
        sentinel_file,
    )

    # 8. Structured Telemetry
    log_telemetry_event({
        "type": "circuit_breaker",
        "job_id": job.get("id"),
        "agent": job.get("agent"),
        "tokens": total_tokens,
        "cost_usd": cost_usd,
        "reason": reason,
        "kill_method": kill_method,
    })

    return CircuitBreakerResult(
        tripped=True,
        reason=reason,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        process_killed=killed,
        kill_method=kill_method,
    )
