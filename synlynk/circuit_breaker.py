"""In-flight active token & cost circuit breaker engine (Invariant 2).

Enforces real-time protection against runaway agent worker loops:
Tripped <=> Tokens(Job) >= T_max or Cost(Job) >= C_max
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED
from synlynk.process_lifecycle import capture_termination_domain, terminate_job_domain
from synlynk.sentinel import (
    _write_sentinel_alert,
    log_telemetry_event,
    process_identity_check,
)

DEFAULT_MAX_JOB_TOKENS = 5_000_000
DEFAULT_MAX_JOB_COST_USD = 15.00
DEFAULT_ZERO_FILE_TOKEN_THRESHOLD = 500_000
DEFAULT_MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50MB

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
) -> Tuple[int, float, int, int]:
    """Resolve max_tokens, max_cost, zero_file_threshold, and max_log_size_bytes
    from config and tier overrides."""
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
    max_log_size_bytes = int(
        cb_config.get("max_log_size_bytes", DEFAULT_MAX_LOG_SIZE_BYTES)
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
            if "max_log_size_bytes" in tier_cfg:
                max_log_size_bytes = int(tier_cfg["max_log_size_bytes"])

    return max_tokens, max_cost, zero_file_threshold, max_log_size_bytes


def _kill_process_tree(
    pid: Optional[int],
    expected_identity: Optional[dict] = None,
    process=None,
    skip_identity_check: bool = False,
    grace_period_seconds: float = 0.5,
    termination_domain: Optional[dict] = None,
) -> Tuple[bool, str]:
    """Compatibility adapter around verified termination-domain cleanup."""
    domain = termination_domain
    if domain is None and process is not None:
        domain = capture_termination_domain(process)
    if domain is None:
        if not pid:
            return False, "no_pid"
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return False, "invalid_pid"
        identity_verified = skip_identity_check or (
            process_identity_check(pid, expected_identity) == "safe to kill"
        )
        domain = {
            "version": 1,
            "kind": "legacy_process",
            "leader_pid": pid,
            "leader_identity": expected_identity,
            "identity_verified": identity_verified,
        }
    result = terminate_job_domain(domain, grace_seconds=grace_period_seconds)
    return (
        result.process_state == "stopped_verified",
        f"{result.process_state}:{result.method}:{result.reason_code}",
    )


def _worktree_branch_is_stable(worktree_path: Optional[str], expected_branch: Optional[str]) -> bool:
    """Return whether a zero-file observation is safe to act on.

    Detached HEAD is an in-progress checkout state. A named branch mismatch
    is deferred only while its HEAD reflog entry is recent; an old feature
    branch checkout must not permanently disable the circuit breaker.
    """
    if not worktree_path or not expected_branch:
        return True
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, check=False,
        )
    except Exception:
        return True
    if result.returncode == 0 and (result.stdout or "").strip() == expected_branch:
        return True
    try:
        reflog = subprocess.run(
            ["git", "-C", worktree_path, "reflog", "-1", "--format=%ct", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        if reflog.returncode != 0:
            return True
        changed_at = float((reflog.stdout or "").strip())
    except (ValueError, OSError, TypeError):
        return True
    return time.time() - changed_at > 60


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
    # as a million-token prompt for cost/token ceilings, but runaway loop
    # detection (zero-file threshold) tracks cumulative raw tokens to prevent
    # prompt-cache blindspot loops (gh:#1937).
    from synlynk.costs import extract_tokens, split_billed_tokens
    from synlynk.jobs import _job_cost_usd
    from synlynk.dispatch import _worktree_files_touched

    agent = job.get("agent", "")
    token_counts = extract_tokens(log_text, agent=agent)
    raw_in, out_tokens = token_counts
    cache_read_tokens = int(getattr(token_counts, "cache_read_tokens", 0) or 0)
    in_tokens, _cache = split_billed_tokens(agent, raw_in, cache_read_tokens)
    total_tokens = in_tokens + out_tokens
    raw_total_tokens = raw_in + out_tokens

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
    max_tokens, max_cost, zero_file_threshold, max_log_size_bytes = _resolve_circuit_breaker_limits(job, config)

    # 5. Check triggers
    log_size_bytes = 0
    if log_file and os.path.exists(log_file):
        try:
            log_size_bytes = os.path.getsize(log_file)
        except OSError:
            log_size_bytes = 0

    reason = None
    if cost_usd >= max_cost:
        reason = f"Cost limit breached: ${cost_usd:.2f} >= ${max_cost:.2f}"
    elif total_tokens >= max_tokens:
        reason = f"Token limit breached: {total_tokens:,} >= {max_tokens:,} tokens"
    elif log_size_bytes >= max_log_size_bytes:
        reason = (
            f"Log size runaway: {log_size_bytes:,} bytes >= {max_log_size_bytes:,} bytes "
            f"(extracted tokens: {total_tokens:,} — likely mid-turn token-extraction blind spot)"
        )
    elif total_tokens >= zero_file_threshold or raw_total_tokens >= zero_file_threshold:
        files_touched_list = _worktree_files_touched(worktree_path) if worktree_path else []
        files_touched = len(files_touched_list)
        if files_touched == 0 and _worktree_branch_is_stable(
            worktree_path, job.get("worktree_branch")
        ):
            reason = f"Zero-file runaway: {raw_total_tokens:,} tokens with 0 files touched (limit: {zero_file_threshold:,})"

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
        termination_domain=job.get("termination_domain"),
    )

    cleanup_unverified = kill_method.startswith("cleanup_unverified:")
    job["process_state"] = "stopped_verified" if killed else "cleanup_unverified"
    job.setdefault("lifecycle_evidence", []).extend([
        {"kind": "cleanup", "process_state": "stop_requested"},
        {
            "kind": "cleanup",
            "process_state": job["process_state"],
            "reason_code": kill_method,
        },
    ])

    if not killed and not cleanup_unverified:
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
        f"Job {job.get('id')} on agent '{job.get('agent')}' tripped the in-flight "
        f"circuit breaker ({reason}); process cleanup "
        f"{'verified' if killed else 'remains unverified'}.",
        sentinel_file,
    )
    if not killed:
        _write_sentinel_alert(
            "CRITICAL",
            "CLEANUP_UNVERIFIED",
            f"Job {job.get('id')} circuit-breaker cleanup remains unverified "
            f"({kill_method}); operator follow-up is required.",
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
