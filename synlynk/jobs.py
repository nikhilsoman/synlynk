"""synlynk jobs: job store, reconciliation (CLI-dispatch and daemon paths), fleet routing."""

import json
import os
import re
import subprocess
import sys
import time
from typing import Optional

from synlynk.sentinel import _write_sentinel_alert
from synlynk._constants import AGENT_CAPABILITY_BASELINES


_BOLD = "[1m"
_GREEN = "[32m"
_YELLOW = "[33m"
_DIM = "[2m"
_RESET = "[0m"


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _load_jobs() -> list:
    """Reads .synlynk/jobs.json; returns [] if missing or corrupt."""
    jobs_file = _pkg("JOBS_FILE")
    if not os.path.exists(jobs_file):
        return []
    try:
        with open(jobs_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def _save_jobs(jobs: list) -> None:
    """Writes jobs list to .synlynk/jobs.json."""
    jobs_file = _pkg("JOBS_FILE")
    os.makedirs(os.path.dirname(jobs_file), exist_ok=True)
    with open(jobs_file, "w") as f:
        json.dump(jobs, f, indent=2)

def _inspect_worktree_git_state(
    worktree_path: Optional[str],
    worktree_branch: Optional[str] = None,
    started_at: Optional[str] = None,
) -> Optional[dict]:
    """Returns git evidence for a worktree, or None when it is unavailable."""
    if not worktree_path or not os.path.isdir(worktree_path):
        return None

    try:
        status_result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--short"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    dirty = bool((status_result.stdout or "").strip())
    commits_ahead = 0
    base_ref = None
    base_info = _pkg("_resolve_worktree_base_commit")(worktree_path)
    base_commit = (base_info or {}).get("base_commit")
    base_ref = (base_info or {}).get("base_ref")
    if base_commit:
        try:
            ahead_result = subprocess.run(
                ["git", "-C", worktree_path, "rev-list", "--count", f"{base_commit}..HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            ahead_result = None

        if ahead_result and ahead_result.returncode == 0:
            try:
                commits_ahead = int((ahead_result.stdout or "0").strip() or "0")
            except ValueError:
                commits_ahead = 0

    remote_branch_has_activity = False
    remote_branch_ref = None
    remote_branch_commit_count = 0
    remote_branch_files_touched = []
    if not dirty and commits_ahead == 0:
        remote_state = _inspect_origin_branch_activity(worktree_path, worktree_branch, started_at)
        if remote_state:
            remote_branch_has_activity = remote_state["remote_has_activity"]
            remote_branch_ref = remote_state["remote_ref"]
            remote_branch_commit_count = remote_state["remote_commit_count"]
            remote_branch_files_touched = remote_state["remote_files_touched"]

    return {
        "worktree_path": worktree_path,
        "dirty": dirty,
        "commits_ahead": commits_ahead,
        "base_ref": base_ref,
        "base_commit": base_commit,
        "has_activity": dirty or commits_ahead > 0,
        "remote_ref": remote_branch_ref,
        "remote_commit_count": remote_branch_commit_count,
        "remote_files_touched": remote_branch_files_touched,
        "remote_has_activity": remote_branch_has_activity,
    }


def _inspect_origin_branch_activity(
    worktree_path: Optional[str],
    worktree_branch: Optional[str],
    started_at: Optional[str],
) -> Optional[dict]:
    """Returns commit/file evidence for origin/<branch> activity since started_at."""
    if not worktree_path or not os.path.isdir(worktree_path) or not worktree_branch or not started_at:
        return None

    remote_ref = f"origin/{worktree_branch}"

    try:
        commit_result = subprocess.run(
            ["git", "-C", worktree_path, "log", "--since", started_at, "--format=%H", remote_ref],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    if commit_result.returncode != 0:
        return None

    commits = [line.strip() for line in (commit_result.stdout or "").splitlines() if line.strip()]
    files_touched = []
    if commits:
        try:
            files_result = subprocess.run(
                [
                    "git",
                    "-C",
                    worktree_path,
                    "log",
                    "--since",
                    started_at,
                    "--name-only",
                    "--pretty=format:",
                    remote_ref,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            files_result = None

        if files_result and files_result.returncode == 0:
            seen = set()
            for path in (files_result.stdout or "").splitlines():
                path = path.strip()
                if not path or path in seen:
                    continue
                seen.add(path)
                files_touched.append(path)

    return {
        "remote_ref": remote_ref,
        "remote_commit_count": len(commits),
        "remote_files_touched": sorted(files_touched),
        "remote_has_activity": bool(commits),
    }

def _count_dispatch_rework(story_id: str) -> int:
    """Counts completed jobs for this story_id — each represents one dispatch cycle."""
    if not story_id:
        return 0
    jobs = _load_jobs()
    return sum(1 for j in jobs
               if j.get("story_id") == story_id and j.get("status") == "completed")

def _extract_micro_rework(log_text: str) -> int:
    """Counts sub-task retry signals in agent log output."""
    patterns = [r"retrying step", r"retry attempt", r"re-trying", r"attempt \d+"]
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, log_text, re.IGNORECASE))
    return count

def _count_tool_calls(log_text: str) -> int:
    """Counts coarse tool-call markers in captured agent output."""
    patterns = ("Tool:", "Running tool", "function_call", "tool_use")
    return sum(log_text.count(pattern) for pattern in patterns)

def _write_capability_rating(job: dict, log_text: str) -> None:
    """Writes a capability_ratings row for a completed job."""
    story_id = job.get("story_id", "")
    if not story_id:
        return

    conn = _pkg("_get_db")()
    exists = conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone()
    if not exists:
        conn.close()
        return

    agent = job.get("agent", "unknown")
    if agent not in AGENT_CAPABILITY_BASELINES:
        conn.close()
        known_agents = ", ".join(sorted(AGENT_CAPABILITY_BASELINES))
        raise ValueError(
            f"Refusing capability rating write for unregistered agent {agent!r}. "
            f"Known agents: {known_agents}"
        )
    # Tier 1 only — synlynk-meta header, no config fallback (agent=None prevents Tier 3 contamination)
    tier1_completion = _pkg("extract_model_version")(log_text, agent=None)
    model_at_dispatch = job.get("model_at_dispatch", "unknown")
    # Tier 3: config default — used only as last resort label, never for split_model detection
    tier3_config = _pkg("extract_model_version")("", agent=agent)

    # Resolve hierarchy: Tier 1 > Tier 2 (live dispatch probe) > Tier 3 (config default)
    if tier1_completion != "unknown":
        model_at_completion = tier1_completion
        model_version = tier1_completion
    elif model_at_dispatch != "unknown":
        model_at_completion = model_at_dispatch
        model_version = model_at_dispatch
    else:
        model_at_completion = tier3_config
        model_version = tier3_config

    # Only flag split_model when BOTH Tier 1 and Tier 2 are concretely known and differ
    split_model = 1 if (
        tier1_completion != "unknown"
        and model_at_dispatch != "unknown"
        and tier1_completion != model_at_dispatch
    ) else 0

    signals = _pkg("_extract_auto_signals")(
        log_text,
        started_at=job.get("started_at"),
        ended_at=job.get("ended_at"),
        exit_code=job.get("exit_code"),
        worktree_path=job.get("worktree_path"),
        worktree_branch=job.get("worktree_branch"),
    )
    engg_domain = _pkg("_infer_engg_domain")(log_text)
    dispatch_rework = job.get("dispatch_rework", 0)
    micro_rework = job.get("micro_rework", 0)

    story_row = conn.execute(
        "SELECT engg_domain, discipline, org_domain, role, stage, industry, phase, stack_tags "
        "FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    if not story_row:
        conn.close()
        return
    story_engg_domain, story_discipline, org_domain, role, stage, industry, phase, stack_tags = story_row
    from synlynk.db import _normalize_capability_tags
    story_discipline, org_domain, role, stage = _normalize_capability_tags(
        story_engg_domain,
        org_domain,
        discipline=story_discipline,
        role=role,
        stage=stage,
    )
    engg_domain = story_discipline or engg_domain

    weighted_sum, total_weight = 0.0, 0.0
    if signals["test_pass_rate"] is not None:
        weighted_sum += signals["test_pass_rate"] * 10 * 0.30
        total_weight += 0.30
    if signals["build_success"] is not None:
        weighted_sum += (10.0 if signals["build_success"] else 0.0) * 0.25
        total_weight += 0.25
    if signals.get("pr_review_cycles") is not None:
        pr_review_score = max(0.0, 10.0 - min(float(signals["pr_review_cycles"]) * 2.0, 10.0))
        weighted_sum += pr_review_score * 0.15
        total_weight += 0.15
    if signals.get("verified_by_ci") is not None:
        weighted_sum += (10.0 if signals["verified_by_ci"] else 0.0) * 0.15
        total_weight += 0.15
    rework_penalty = min(dispatch_rework * 2.0, 10.0)
    weighted_sum += max(0.0, 10.0 - rework_penalty) * 0.15
    total_weight += 0.15
    quality_auto = (weighted_sum / total_weight) if total_weight else 5.0

    # Anti-gaming: cap quality_auto at 5.0 when < 3 tests ran with perfect pass rate.
    test_count = signals.get("test_count")
    if (signals["test_pass_rate"] == 1.0
            and test_count is not None
            and test_count < 3):
        quality_auto = min(quality_auto, 5.0)

    # Check for verifier meta block — upgrades signal_source from 'auto' to 'verifier'
    verifier_meta = _pkg("extract_verifier_meta")(log_text)
    if verifier_meta:
        signal_source = "verifier"
        quality = (quality_auto * 0.15) + (verifier_meta["quality"] * 0.85)
        verifier_model = verifier_meta.get("verifier_model")
        verifier_agent_val = agent
        correct = 0 if verifier_meta.get("correct") is False else 1
    else:
        signal_source = "auto"
        quality = quality_auto
        verifier_model = None
        verifier_agent_val = None
        # Auto: infer correctness from build success (default 1 if unknown)
        correct = 1 if signals.get("build_success") is not False else 0

    sig_payload = {
        "story_id": story_id, "agent": agent, "model_version": model_version,
        "quality": quality, "quality_auto": quality_auto,
        "signal_source": signal_source, "engg_domain": engg_domain,
    }
    ed25519_sig = _pkg("_sign_capability_rating")(sig_payload)

    conn.execute(
        """INSERT INTO capability_ratings
           (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
            engg_domain, discipline, org_domain, role, stage, stack_tags, industry, phase,
            signal_source, quality, quality_auto,
            verifier_agent, verifier_model,
            test_pass_rate, build_success,
            dispatch_rework, micro_rework, pr_review_cycles,
            duration_vs_estimate, verified_by_ci, correct, ed25519_sig)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
         engg_domain, story_discipline, org_domain, role, stage, stack_tags, industry, phase,
         signal_source, quality, quality_auto,
         verifier_agent_val, verifier_model,
         signals["test_pass_rate"], signals["build_success"],
         dispatch_rework, micro_rework, signals.get("pr_review_cycles"),
         None, signals.get("verified_by_ci"), correct, ed25519_sig)
    )
    conn.commit()
    conn.close()

def _capability_candidates_for_story(conn, engg, org, industry, phase) -> list:
    """Return [(agent, weighted_score, model_version), ...] best-first.

    Falls back through progressively wider coordinates (same as legacy
    _best_agent_for_story single-row lookup).
    """
    queries = [
        ("engg_domain=? AND org_domain=? AND industry=? AND phase=?",
         (engg, org, industry, phase)),
        ("engg_domain=? AND org_domain=? AND phase=?",
         (engg, org, phase)),
        ("engg_domain=? AND phase=?",
         (engg, phase)),
    ]
    for where, params in queries:
        rows = conn.execute(
            f"SELECT agent, weighted_score, model_version FROM capability_scores "
            f"WHERE {where} ORDER BY weighted_score DESC",
            params,
        ).fetchall()
        if rows:
            # Deduplicate by agent, keep highest score (first due to ORDER BY).
            seen = set()
            out = []
            for agent, score, model in rows:
                if agent in seen:
                    continue
                seen.add(agent)
                out.append((agent, float(score or 0.0), model or "unknown"))
            return out
    return []

def _best_agent_for_story(story_id: str) -> Optional[str]:
    """3-stage routing: capability score → quota headroom → cost.

    Stage 1 (capability, #139): rank agents by weighted capability score for
    the story's coordinate, falling back through wider coordinates.
    Stage 2 (quota, #141): filter agents with insufficient headroom. Real gate.
    Degraded-mode: when quota can't be read this cycle, keep the agent eligible
    (do not hard-block) but prefer agents with known headroom.
    Stage 3 (cost, #140): among remaining, if top scores are within
    _pkg("_CAPABILITY_COST_TIE_GAP"), pick the cheaper model; else highest capability.

    Returns None on cold start (no capability data).
    """
    if not story_id:
        return None
    conn = _pkg("_get_db")()
    try:
        story = conn.execute(
            "SELECT engg_domain, org_domain, industry, phase, estimated_tokens "
            "FROM stories WHERE story_id=?",
            (story_id,),
        ).fetchone()
        if not story:
            return None

        engg, org, industry, phase, estimated_tokens = story
        candidates = _capability_candidates_for_story(
            conn, engg, org, industry, phase
        )
        if not candidates:
            return None

        # Stage 2 — quota headroom gate
        gated = []  # (agent, score, model, quota_status)
        for agent, score, model in candidates:
            qstatus = _pkg("_quota_status_for_agent")(
                conn, agent, estimated_tokens=estimated_tokens
            )
            if qstatus["status"] == "exhausted":
                continue  # real gate: drop
            gated.append((agent, score, model, qstatus))

        if not gated:
            # Every capability-eligible agent is quota-exhausted.
            return None

        # Prefer known-headroom (non-degraded) over unknown when both present.
        known = [g for g in gated if not g[3].get("degraded")]
        pool = known if known else gated

        # Stage 3 — cost among capability-near ties
        top_score = pool[0][1]
        near = [g for g in pool if (top_score - g[1]) <= _pkg("_CAPABILITY_COST_TIE_GAP")]
        if len(near) == 1:
            return near[0][0]

        best = min(
            near,
            key=lambda g: (
                _pkg("_estimate_story_cost_usd")(g[2], estimated_tokens),
                -g[1],  # higher capability as secondary
                g[0],   # stable tie-break
            ),
        )
        return best[0]
    finally:
        conn.close()

def _reconcile_jobs() -> None:
    """Probes PIDs of running jobs; marks unreachable ones as failed or completed.

    Called on every synlynk invocation before any command runs.
    Prevents stale jobs surviving reboots or external kills.
    """
    jobs = _load_jobs()
    changed = False
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    config = _pkg("load_config")()
    sentinel_path = ".synlynk/sentinel.md"
    for job in jobs:
        if job.get("status") not in ("running",):
            continue
        if _pkg("_check_job_stall")(job, config, sentinel_path):
            ended_at = job.get("ended_at") or now
            started_at = job.get("started_at")
            duration_s = None
            try:
                duration_s = max(0.0, time.mktime(time.strptime(ended_at, "%Y-%m-%dT%H:%M:%S")) -
                                 time.mktime(time.strptime(started_at, "%Y-%m-%dT%H:%M:%S")))
            except Exception:
                duration_s = None
            log_file = job.get("log_file")
            log_text = ""
            if log_file and os.path.exists(log_file):
                try:
                    with open(log_file) as f:
                        log_text = f.read()
                except Exception:
                    log_text = ""
            in_tokens, out_tokens = _pkg("extract_tokens")(log_text)
            cost_usd = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
            summary = _pkg("_write_job_summary")(
                job.get("id", ""),
                job.get("agent", ""),
                job.get("story_id"),
                job.get("exit_code"),
                duration_s,
                in_tokens,
                out_tokens,
                cost_usd,
                _pkg("_worktree_files_touched")(job.get("worktree_path")),
                job.get("worktree_path"),
                job.get("worktree_branch"),
            )
            print(summary, end="")
            changed = True
            continue
        pid = job.get("pid")
        if pid is None:
            continue
        try:
            os.kill(pid, 0)  # signal 0: check existence only, no actual signal
        except ProcessLookupError:
            # PID is dead. Check if wrapper wrote an exit code.
            log_file = job.get("log_file")
            exit_code = None
            ambiguous_exit = False
            git_state = None
            if log_file:
                exit_file = log_file + ".exit"
                if os.path.exists(exit_file):
                    try:
                        with open(exit_file) as f:
                            exit_code = int(f.read().strip())
                        os.remove(exit_file)
                    except Exception:
                        pass
                elif job.get("worktree_path"):
                    git_state = _pkg("_inspect_worktree_git_state")(
                        job.get("worktree_path"),
                        job.get("worktree_branch"),
                        job.get("started_at"),
                    )
                    if git_state and git_state.get("has_activity"):
                        ambiguous_exit = True
                    # If the assigned worktree stayed clean but origin/<branch> advanced,
                    # the job likely ran in a borrowed worktree and still succeeded.
                    elif git_state and git_state.get("remote_has_activity"):
                        job["status"] = "completed"
                        job["exit_code"] = 0

            if exit_code == 0:
                job["status"] = "completed"
                job["exit_code"] = 0
            elif job.get("status") == "completed":
                pass
            elif ambiguous_exit:
                job["status"] = "failed_unverified"
                job["exit_code"] = None
            else:
                job["status"] = "failed"
                job["exit_code"] = exit_code if exit_code is not None else -1
            job["ended_at"] = now
            changed = True

            if log_file and os.path.exists(log_file):
                with open(log_file) as f:
                    log_text = f.read()
                if job.get("status") != "completed":
                    log_text_lower = log_text.lower()
                    for phrase in _pkg("HARNESS_TIMEOUT_PATTERNS"):
                        if phrase in log_text_lower:
                            _write_sentinel_alert(
                                "CRITICAL",
                                "HARNESS_INTERNAL_TIMEOUT",
                                f"Job {job.get('id')} on agent '{job.get('agent')}' died from an internal "
                                f"harness timeout (matched \"{phrase}\"), not a task failure. Consider retrying.",
                                sentinel_path,
                            )
                            break
                job["micro_rework"] = _extract_micro_rework(log_text)
                try:
                    _pkg("_write_capability_rating")(job, log_text)
                except ValueError as exc:
                    print(
                        f"  ⚠ capability rating skipped for job {job.get('id', '')}: {exc}"
                    )
            else:
                log_text = ""

            in_tokens, out_tokens = _pkg("extract_tokens")(log_text)
            cost_usd = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
            duration_s = None
            try:
                duration_s = max(0.0, time.mktime(time.strptime(job.get("ended_at"), "%Y-%m-%dT%H:%M:%S")) -
                                 time.mktime(time.strptime(job.get("started_at"), "%Y-%m-%dT%H:%M:%S")))
            except Exception:
                duration_s = None
            summary_note = None
            summary_status = None
            summary_files_touched = _pkg("_worktree_files_touched")(job.get("worktree_path"))
            if git_state and git_state.get("remote_has_activity") and not git_state.get("has_activity"):
                summary_files_touched = git_state.get("remote_files_touched", [])
                remote_ref = git_state.get("remote_ref")
                remote_commit_count = git_state.get("remote_commit_count", 0)
                summary_note = (
                    f"borrowed worktree detected; attributed from {remote_ref} "
                    f"with {remote_commit_count} commit(s) since {job.get('started_at')}"
                )
            elif ambiguous_exit and git_state:
                commit_count = git_state.get("commits_ahead", 0)
                dirty = git_state.get("dirty", False)
                parts = []
                if commit_count:
                    parts.append(f"{commit_count} commit(s)")
                if dirty:
                    parts.append("uncommitted changes")
                details = " and ".join(parts) if parts else "git activity"
                summary_note = (
                    f"job exited ambiguously but the worktree contains {details} "
                    f"— inspect before discarding (worktree: {job.get('worktree_path')})"
                )
                summary_status = "FAILED_UNVERIFIED (exit unknown)"
            summary = _pkg("_write_job_summary")(
                job.get("id", ""),
                job.get("agent", ""),
                job.get("story_id"),
                job.get("exit_code"),
                duration_s,
                in_tokens,
                out_tokens,
                cost_usd,
                summary_files_touched,
                job.get("worktree_path"),
                job.get("worktree_branch"),
                status_label=summary_status,
                note=summary_note,
            )
            print(summary, end="")

        except PermissionError:
            # Process exists but is owned by another user — keep status as running.
            pass
    if changed:
        _save_jobs(jobs)

def _reconcile_daemon_jobs() -> None:
    """Reaps finished daemon_jobs; updates status/exit_code/completed_at in state.db."""
    conn = _pkg("_get_db")()
    rows = conn.execute(
        "SELECT job_id, agent, story_id, pid, started_at, completed_at, log_path "
        "FROM daemon_jobs WHERE status='running'"
    ).fetchall()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        for job_id, agent, story_id, pid, started_at, completed_at, log_path in rows:
            if pid is None:
                continue
            exited = False
            raw_exit_status = None
            try:
                wpid, wstatus = os.waitpid(pid, os.WNOHANG)
                if wpid != 0:
                    exited = True
                    raw_exit_status = wstatus
            except ChildProcessError:
                # Process was adopted by init (daemon restart) — fall back to kill(0)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    exited = True

            if exited:
                exit_code = -1
                if raw_exit_status is not None:
                    if os.WIFEXITED(raw_exit_status):
                        exit_code = os.WEXITSTATUS(raw_exit_status)
                    elif os.WIFSIGNALED(raw_exit_status):
                        exit_code = -os.WTERMSIG(raw_exit_status)
                elif log_path:
                    exit_file = log_path + ".exit"
                    if os.path.exists(exit_file):
                        try:
                            with open(exit_file) as f:
                                exit_code = int(f.read().strip())
                            os.remove(exit_file)
                        except Exception:
                            pass
                status = "done" if exit_code == 0 else "failed"
                conn.execute(
                    "UPDATE daemon_jobs SET status=?, exit_code=?, completed_at=? "
                    "WHERE job_id=?",
                    (status, exit_code, now, job_id)
                )
                duration_s = None
                try:
                    end_ts = time.mktime(time.strptime(now, "%Y-%m-%dT%H:%M:%S"))
                    start_ts = time.mktime(time.strptime(started_at, "%Y-%m-%dT%H:%M:%S"))
                    duration_s = max(0.0, end_ts - start_ts)
                except Exception:
                    duration_s = None
                log_text = ""
                if log_path and os.path.exists(log_path):
                    try:
                        with open(log_path) as f:
                            log_text = f.read()
                    except Exception:
                        log_text = ""
                in_tokens, out_tokens = _pkg("extract_tokens")(log_text)
                cost_usd = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
                _pkg("_write_job_summary")(
                    job_id, agent, story_id, exit_code, duration_s, in_tokens,
                    out_tokens, cost_usd, []
                )
        conn.commit()
    finally:
        conn.close()

def _dispatch_ready_jobs(max_parallel: int = 4) -> int:
    """Launches queued daemon_jobs up to max_parallel concurrently. Returns count launched."""
    import json as _json
    import shlex as _shlex
    conn = _pkg("_get_db")()
    try:
        running_count = conn.execute(
            "SELECT COUNT(*) FROM daemon_jobs WHERE status='running'"
        ).fetchone()[0]
        if running_count >= max_parallel:
            return 0

        slots = max_parallel - running_count
        candidates = conn.execute(
            "SELECT job_id, agent, task, story_id, depends_on, log_path "
            "FROM daemon_jobs WHERE status='queued' "
            "ORDER BY priority ASC, enqueued_at ASC"
        ).fetchall()

        launched = 0
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for job_id, agent, task, story_id, depends_on_json, log_path in candidates:
            if launched >= slots:
                break
            deps = _json.loads(depends_on_json or "[]")
            if deps:
                placeholders = ",".join("?" * len(deps))
                dep_rows = conn.execute(
                    f"SELECT job_id, status FROM daemon_jobs WHERE job_id IN ({placeholders})",
                    deps
                ).fetchall()
                dep_statuses = {r[0]: r[1] for r in dep_rows}
                if any(dep_statuses.get(d) == "failed" for d in deps):
                    conn.execute(
                        "UPDATE daemon_jobs SET status='failed', completed_at=? WHERE job_id=?",
                        (now, job_id)
                    )
                    conn.commit()
                    continue
                done_ids = {jid for jid, st in dep_statuses.items() if st == "done"}
                if done_ids != set(deps):
                    continue

            if not log_path:
                os.makedirs(_pkg("LOGS_DIR"), exist_ok=True)
                log_path = os.path.join(_pkg("LOGS_DIR"), f"{job_id}.log")

            baselines = AGENT_CAPABILITY_BASELINES.get(agent, {})
            cli = baselines.get("cli", agent)
            flags = baselines.get("non_interactive_flags", [])
            prompt_via_arg = baselines.get("prompt_via_arg", False)
            prompt_flag = baselines.get("prompt_flag")
            prompt_file = os.path.join(_pkg("PROMPTS_DIR"), f"{job_id}.md")
            os.makedirs(_pkg("PROMPTS_DIR"), exist_ok=True)
            context_text = ""
            context_path = ".synlynk/context.md"
            if os.path.exists(context_path):
                with open(context_path) as f:
                    context_text = f.read()
            prompt = _pkg("_format_prompt_for_agent")(
                agent, context_text, story_id or "", task, "", ""
            )
            with open(prompt_file, "w") as pf:
                pf.write(prompt)

            if prompt_via_arg and prompt_flag:
                cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
            else:
                cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
            if prompt_via_arg:
                shell_cmd = (
                    f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
                    f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_path)} 2>&1; "
                    f"echo $? > {_shlex.quote(log_path)}.exit"
                )
            else:
                shell_cmd = (
                    f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_path)} 2>&1; "
                    f"echo $? > {_shlex.quote(log_path)}.exit"
                )

            proc = subprocess.Popen(
                ["sh", "-c", shell_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            conn.execute(
                "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, log_path=? "
                "WHERE job_id=?",
                (proc.pid, now, log_path, job_id)
            )
            conn.commit()
            launched += 1

        return launched
    finally:
        conn.close()

def cmd_jobs(all_jobs: bool = False, watch: bool = False, summary: Optional[str] = None,
             stalled: bool = False) -> None:
    """Prints jobs from daemon_jobs in state.db; --all includes done/failed; --watch refreshes."""
    import time as _time

    if summary:
        summary_path = _pkg("_job_summary_path")(summary)
        if not os.path.exists(summary_path):
            print(f"No summary for {summary} -- job may still be running or predates this feature")
            return
        with open(summary_path) as f:
            print(f.read(), end="")
        return

    if stalled:
        sentinel_path = os.path.join(".synlynk", "sentinel.md")
        sentinel_text = ""
        if os.path.exists(sentinel_path):
            with open(sentinel_path) as f:
                sentinel_text = f.read()
        pending_ids = _pkg("_stalled_job_ids_from_sentinel")(sentinel_text)
        if not pending_ids:
            print("No stalled jobs awaiting handoff.")
            return

        conn = _pkg("_get_db")()
        print(f"\n  {_BOLD}Stalled jobs — awaiting handoff{_RESET}\n")
        print(f"  {'JOB ID':14}  {'AGENT':8}  {'AGE':8}  {'TASK':36}  RECOMMENDED")
        print("  " + "─" * 90)
        try:
            for job_id in sorted(pending_ids):
                row = conn.execute(
                    "SELECT agent, task, started_at FROM daemon_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if not row:
                    continue
                agent, task_text, started_at = row
                age = "?"
                try:
                    if started_at:
                        started_ts = _time.mktime(_time.strptime(started_at, "%Y-%m-%dT%H:%M:%S"))
                        age_s = int(_time.time() - started_ts)
                        age = f"{age_s // 60}m{age_s % 60:02d}s" if age_s >= 60 else f"{age_s}s"
                except Exception:
                    age = "?"
                recommended = _pkg("_recommend_handoff_agent")(task_text or "", agent, conn)
                print(f"  {job_id:14}  {agent:8}  {age:8}  {(task_text or '')[:36]:36}  → {recommended}")
        finally:
            conn.close()
        print(f"\n  Run: synlynk jobs handoff <job_id> [--to <agent>]\n")
        return

    def _parse_age(enqueued_at: str) -> str:
        try:
            enq = _time.mktime(_time.strptime(enqueued_at, "%Y-%m-%dT%H:%M:%S"))
            age_s = int(_time.time() - enq)
            if age_s < 60:
                return f"{age_s}s"
            if age_s < 3600:
                return f"{age_s // 60}m{age_s % 60:02d}s"
            return f"{age_s // 3600}h{(age_s % 3600) // 60}m"
        except Exception:
            return "?"

    def _render_legacy_jobs() -> None:
        _pkg("_reconcile_jobs")()
        jobs = _load_jobs()
        if not jobs:
            print("No jobs found. Use `synlynk dispatch <agent> --task <task>` to start one.")
            return
        visible = jobs if all_jobs else [j for j in jobs if j["status"] == "running"]
        if not visible:
            completed = len([j for j in jobs if j["status"] in ("completed", "failed", "failed_unverified")])
            print(f"No running jobs. ({completed} completed/failed — use `synlynk jobs --all` to see)")
            return
        header = f"{'ID':12}  {'AGENT':10}  {'STATUS':10}  {'STORY':6}  TASK"
        print(f"{_BOLD}{header}{_RESET}")
        print("─" * 70)
        for j in visible:
            sid = (j.get("story_id") or "—")[:6]
            task = (j.get("task") or "")[:40]
            status = j["status"]
            color = _GREEN if status == "running" else (_DIM if status == "completed" else _YELLOW)
            print(f"{j['id']:12}  {j['agent']:10}  {color}{status:10}{_RESET}  {sid:6}  {task}")

    def _render() -> None:
        _pkg("_reconcile_daemon_jobs")()
        conn = _pkg("_get_db")()
        rows = conn.execute(
            "SELECT job_id, agent, story_id, status, enqueued_at, exit_code "
            "FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 50"
        ).fetchall()
        conn.close()

        if not rows:
            _render_legacy_jobs()
            return

        if all_jobs:
            visible = rows
        else:
            visible = [r for r in rows if r[3] in ("queued", "running")]
            if not visible:
                done = sum(1 for r in rows if r[3] in ("done", "failed"))
                print(f"  No active jobs. ({done} completed — use synlynk jobs --all)")
                return

        header = f"{'ID':14}  {'AGENT':8}  {'STORY':12}  {'STATUS':10}  {'AGE':8}  {'EXIT':4}"
        print(f"{_BOLD}{header}{_RESET}")
        print("  " + "─" * 64)
        for job_id, agent, story_id, status, enqueued_at, exit_code in visible:
            sid = (story_id or "—")[:12]
            age = _parse_age(enqueued_at)
            color = _GREEN if status == "running" else (_DIM if status in ("done", "failed") else _YELLOW)
            exit_str = str(exit_code) if exit_code is not None else "—"
            print(
                f"  {job_id:14}  {agent:8}  {sid:12}  "
                f"{color}{status:10}{_RESET}  {age:8}  {exit_str:4}"
            )

    if watch:
        try:
            while True:
                print("\033[H\033[J", end="")
                try:
                    _render()
                except Exception as e:
                    print(f"  render error: {e}")
                print(f"\n  {_DIM}Refreshing every 2s... Ctrl-C to exit{_RESET}")
                _time.sleep(2)
        except KeyboardInterrupt:
            pass
    else:
        _render()

def cmd_jobs_handoff(job_id: str, to_agent: str = None) -> None:
    """Transfer a stalled job to another agent, preserving context."""
    from synlynk.dispatch import dispatch_agent as _dispatch

    conn = _pkg("_get_db")()
    try:
        row = conn.execute(
            "SELECT agent, task, story_id, handoff_count, previous_agents FROM daemon_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if not row:
            print(f"  ✗ Job {job_id} not found.")
            return

        orig_agent, task_text, story_id, handoff_count, previous_agents_json = row
        previous = json.loads(previous_agents_json) if previous_agents_json else []
        if not to_agent:
            to_agent = _pkg("_recommend_handoff_agent")(task_text or "", orig_agent, conn)

        ctx_path = os.path.join(".synlynk", "contexts", f"{job_id}.md")
        context_text = ""
        if os.path.exists(ctx_path):
            with open(ctx_path) as f:
                context_text = f.read()
        handoff_note = (
            "\n## Handoff Note\n"
            f"- Previous agent: {orig_agent}\n"
            "- Reason: HANDOFF_PENDING (stall/quota/flatline)\n"
            f"- Handoff #{int(handoff_count or 0) + 1}\n"
        )
        if context_text:
            with open(ctx_path, "a") as f:
                if "## Handoff Note" not in context_text:
                    f.write(handoff_note)
            with open(ctx_path) as f:
                context_text = f.read()
        else:
            os.makedirs(os.path.dirname(ctx_path), exist_ok=True)
            with open(ctx_path, "w") as f:
                f.write(handoff_note.lstrip("\n"))
            context_text = handoff_note.lstrip("\n")

        previous.append(orig_agent)
        conn.execute(
            "UPDATE daemon_jobs SET handoff_count=?, previous_agents=? WHERE job_id=?",
            (int(handoff_count or 0) + 1, json.dumps(previous), job_id),
        )
        conn.commit()
    finally:
        conn.close()

    sentinel_path = os.path.join(".synlynk", "sentinel.md")
    if os.path.exists(sentinel_path):
        with open(sentinel_path) as f:
            lines = f.readlines()
        with open(sentinel_path, "w") as f:
            for line in lines:
                if job_id in line and "HANDOFF_PENDING" in line:
                    continue
                f.write(line)

    handoff_task = task_text
    if context_text:
        handoff_task = f"{task_text}\n\n{context_text}"
    print(f"  ✓ Handing off {job_id} from {orig_agent} → {to_agent}")
    result = _dispatch(
        to_agent,
        task=handoff_task,
        story_id=story_id or None,
        context_mode="none",
        skip_preflight=False,
    )

    new_context_file = result.get("context_file")
    if not new_context_file:
        new_context_file = os.path.join(".synlynk", "contexts", f"{result.get('id', '')}.md")
    if new_context_file:
        os.makedirs(os.path.dirname(new_context_file), exist_ok=True)
        with open(new_context_file, "w") as f:
            f.write(handoff_task)

    print(f"  ✓ New job: {result.get('id', '?')}")
