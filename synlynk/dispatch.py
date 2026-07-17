"""synlynk dispatch: preflight gates, agent dispatch, exec wrapper."""

import json
import os
import re
from dataclasses import asdict
import select
import signal
import subprocess
import sys
import threading
import time
from typing import Optional, Tuple

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.sentinel import _read_sentinel_alerts, _write_sentinel_alert


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _dispatch_flags_for_agent(agent: str) -> list:
    """Return the executable dispatch flags for an agent baseline."""
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    baselines = baselines_map.get(agent, {})
    dispatch_flags = baselines.get("dispatch_flags", [])
    flags = []
    if isinstance(dispatch_flags, dict):
        for flag in dispatch_flags.get("required_flags", []) or []:
            if flag not in flags:
                flags.append(flag)
    else:
        flags = list(dispatch_flags or [])
    if agent == "local":
        from synlynk.local_agent import _local_dispatch_model_flags

        flags = flags + _local_dispatch_model_flags()
    return flags


def _context_mode_hint(context_mode: str, task: str) -> Optional[str]:
    if context_mode != "full":
        return None
    has_code_fence = "```" in task
    has_exact_commit = re.search(r"commit\s+-m|commit message", task, re.IGNORECASE) is not None
    if has_code_fence and has_exact_commit:
        return (
            "[context-mode hint] Task text looks fully self-contained "
            "(includes code + an exact commit message) — full project context "
            "may not be needed. Consider --context-mode task or none to reduce "
            "implementer token usage."
        )
    return None


def _load_harness_overrides(agent: str) -> dict:
    """Read per-project harness overrides from .agents/<agent>.json."""
    empty = {"dispatch_flags": {}, "env": {}, "network_deps": []}
    path = os.path.join(".agents", f"{agent}.json")
    if not os.path.exists(path):
        return empty
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("harness_overrides") or empty
    except (json.JSONDecodeError, OSError):
        sys.stderr.write(f"Warning: corrupt {path}, ignoring harness overrides\n")
        return empty


def _local_concurrency_exceeded(conn, max_concurrent: int = 1) -> bool:
    """True if the 'local' agent already has max_concurrent running jobs."""
    row = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE status='running' AND agent='local'"
    ).fetchone()
    running = row[0] if row else 0
    return running >= max_concurrent


def _resolve_dispatch_permissions(
    agent: str,
    role_list: list = None,
    grants: list = None,
    revokes: list = None,
) -> list:
    """Compute effective permissions from role defaults, grants, and revokes."""
    from synlynk._constants import _ROLE_PERMISSION_DEFAULTS

    del agent
    effective = set()
    for role in role_list or []:
        effective.update(_ROLE_PERMISSION_DEFAULTS.get(role, []))
    effective.update(grants or [])
    effective.difference_update(revokes or [])
    return sorted(effective)


def _permissions_to_flags(agent: str, permissions: list) -> list:
    """Translate permission strings into agent-specific CLI flags."""
    from synlynk._constants import _PERMISSION_TO_TOOL_MAP

    if agent == "agy":
        return []
    if agent == "claude":
        tools = []
        for perm in permissions or []:
            tools.extend(_PERMISSION_TO_TOOL_MAP.get(perm, []))
        tools = sorted(set(tools))
        if not tools:
            return []
        return ["--allowedTools", ",".join(tools)]
    if agent == "codex":
        has_write = any((perm or "").startswith("write:") for perm in (permissions or []))
        if not has_write:
            return ["--approval-policy", "untrusted"]
        return []
    return []


def _spawn_with_pty_fallback(cmd, env, cwd):
    """Try pipe mode first; fall back to PTY if stdout hangs (POSIX only)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, cwd=cwd)
    try:
        out, _ = proc.communicate(timeout=5)
        if out:
            return proc, out
    except subprocess.TimeoutExpired:
        proc.kill()
    if sys.platform != "win32":
        import pty

        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                cwd=cwd,
                close_fds=True,
            )
            os.close(slave_fd)
            out_chunks = []
            while True:
                r, _, _ = select.select([master_fd], [], [], 5)
                if not r:
                    proc.kill()
                    break
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    out_chunks.append(data)
                except OSError:
                    break
            proc.wait(timeout=5)
            return proc, b"".join(out_chunks)
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
    return None, b""


def _is_interactive(cmd_args: list) -> bool:
    """Returns True if the command needs a real TTY (no stdout capture)."""
    non_interactive = ["--no-tty", "--output-format json", "--print", "--non-interactive", "-p "]
    cmd_str = " ".join(cmd_args)
    return not any(flag in cmd_str for flag in non_interactive)


def _inject_grok_rules(cmd_args: list) -> list:
    """Adds Grok rules flags when invoking grok and the rule files exist."""
    if not cmd_args or cmd_args[0] != "grok":
        return list(cmd_args)

    injected = [cmd_args[0]]
    if os.path.exists("GROK.md"):
        injected.extend(["--rules", "GROK.md"])
    if "-p" in cmd_args and os.path.exists(os.path.join(".synlynk", "context.md")):
        injected.extend(["--rules", os.path.join(".synlynk", "context.md")])
    injected.extend(cmd_args[1:])
    return injected


def _tee_process(process, buffer: list, meta: Optional[dict] = None) -> None:
    """Reads process stdout line-by-line, writes to terminal and appends to buffer."""
    for line in iter(process.stdout.readline, b""):
        if meta is not None:
            meta["output_bytes"] = meta.get("output_bytes", 0) + len(line)
            if not meta.get("first_output_at") and line.strip():
                meta["first_output_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        buffer.append(line.decode("utf-8", errors="replace"))
    process.stdout.close()


def _check_pre_exec_gate(force: bool = False) -> bool:
    """Checks for active sentinel alerts. Returns False to abort if CRITICAL and not forced."""
    warns = _read_sentinel_alerts(severity="WARN")
    criticals = _read_sentinel_alerts(severity="CRITICAL")
    for w in warns:
        print(f"  ⚠ {w}")
    if criticals:
        for c in criticals:
            print(f"  🚨 {c}")
        if not force:
            print("  Exec blocked by CRITICAL sentinel alert. "
                  "Fix the issue or re-run with --force to bypass.")
            return False
    return True


def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)

    stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60
    if stale_minutes < timeout:
        return False

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
    git_state = (
        inspect_worktree_git_state(
            job.get("worktree_path"),
            job.get("worktree_branch"),
            job.get("started_at"),
        )
        if inspect_worktree_git_state
        else None
    )
    if git_state and git_state.get("has_activity"):
        worktree_path = job.get("worktree_path")
        commit_count = git_state.get("commits_ahead", 0)
        dirty = git_state.get("dirty", False)
        parts = []
        if commit_count:
            parts.append(f"{commit_count} commit(s)")
        if dirty:
            parts.append("uncommitted changes")
        details = " and ".join(parts) if parts else "git activity"
        print(
            f"  Stall check extended for job {job.get('id')}: git activity detected in "
            f"{worktree_path} ({details})."
        )
        return False
    if git_state and git_state.get("remote_has_activity"):
        remote_ref = git_state.get("remote_ref")
        remote_commit_count = git_state.get("remote_commit_count", 0)
        print(
            f"  Stall check extended for job {job.get('id')}: remote activity detected on "
            f"{remote_ref} ({remote_commit_count} commit(s) since {job.get('started_at')})."
        )
        return False

    pid = job.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    job["status"] = "failed"
    job["exit_code"] = -1
    job["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
    write_alert(
        "CRITICAL", "STALL_NO_OUTPUT",
        f"Job {job.get('id')} on agent '{agent}' stalled with zero output after {timeout}min. Process killed.",
        sentinel_path,
    )
    write_alert(
        "WARN", "HANDOFF_PENDING",
        f"Job {job.get('id')} on agent '{agent}' is awaiting handoff to another agent.",
        sentinel_path,
    )
    return True


def _resolve_worktree_base_commit(worktree_path: Optional[str]) -> Optional[dict]:
    """Find the merge-base used to compare a worktree against mainline refs."""
    if not worktree_path or not os.path.isdir(worktree_path):
        return None

    for ref in ("main", "master", "origin/main", "origin/master"):
        try:
            base_result = subprocess.run(
                ["git", "-C", worktree_path, "merge-base", "HEAD", ref],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            continue

        base_commit = (base_result.stdout or "").strip()
        if base_result.returncode != 0 or not base_commit:
            continue

        return {"base_commit": base_commit, "base_ref": ref}

    return None


def _worktree_files_touched(worktree_path: Optional[str]) -> list:
    """Return sorted file paths changed in a worktree since the resolved merge-base."""
    if not worktree_path or not os.path.isdir(worktree_path):
        return []

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
    git_state = inspect_worktree_git_state(worktree_path) if inspect_worktree_git_state else None
    base_commit = (git_state or {}).get("base_commit") or (
        _resolve_worktree_base_commit(worktree_path) or {}
    ).get("base_commit")
    if not base_commit:
        return []

    touched = set()

    try:
        diff_result = subprocess.run(
            ["git", "-C", worktree_path, "diff", "--name-only", base_commit, "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        diff_result = None

    if diff_result and diff_result.returncode == 0:
        for path in (diff_result.stdout or "").splitlines():
            path = path.strip()
            if path:
                touched.add(path)

    try:
        status_result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--short", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        status_result = None

    if status_result and status_result.returncode == 0:
        for line in (status_result.stdout or "").splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if not path:
                continue
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            touched.add(path)

    return sorted(touched)


def _job_summary_path(job_id: str) -> str:
    return os.path.join(".synlynk/logs", f"{job_id}.summary")


def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        exit_code: Optional[int], duration_s: Optional[float],
                        in_tokens: int, out_tokens: int, cost_usd: float,
                        files_touched: Optional[list] = None,
                        worktree_path: Optional[str] = None,
                        worktree_branch: Optional[str] = None,
                        status_label: Optional[str] = None,
                        note: Optional[str] = None) -> str:
    """Formats the structured completion summary for a finished job."""
    files_touched = sorted(set(files_touched or []))
    story_label = story_id or "-"
    exit_code = -1 if exit_code is None else exit_code
    status_label = status_label or ("OK (exit 0)" if exit_code == 0 else f"FAILED (exit {exit_code})")
    duration_label = f"{duration_s:.1f}s" if duration_s is not None else "?s"
    worktree_line = ""
    note_line = f"note:     {note}\n" if note else ""
    if worktree_path:
        branch_note = f" (branch: {worktree_branch})" if worktree_branch else ""
        worktree_line = f"worktree: {worktree_path}{branch_note}\n"
    files_line = f"files:    {len(files_touched)} touched\n"
    if files_touched:
        visible_files = files_touched[:20]
        rendered_files = "".join(f"          {path}\n" for path in visible_files)
        more_count = len(files_touched) - len(visible_files)
        if more_count > 0:
            rendered_files += f"          +{more_count} more\n"
        files_line += rendered_files
    return (
        f"-- job {job_id} complete ---------\n"
        f"agent:    {agent}   story: {story_label}\n"
        f"status:   {status_label}\n"
        f"{note_line}"
        f"duration: {duration_label}\n"
        f"tokens:   in {in_tokens:,}  out {out_tokens:,}  (~${cost_usd:.2f})\n"
        f"{worktree_line}"
        f"{files_line}"
        f"---------------------------------\n"
    )


def _write_job_summary(job_id: str, agent: str, story_id: Optional[str],
                       exit_code: Optional[int], duration_s: Optional[float],
                       in_tokens: int, out_tokens: int, cost_usd: float,
                       files_touched: Optional[list],
                       worktree_path: Optional[str] = None,
                       worktree_branch: Optional[str] = None,
                       status_label: Optional[str] = None,
                       note: Optional[str] = None) -> str:
    """Writes a structured completion summary for a job and returns the text."""
    os.makedirs(".synlynk/logs", exist_ok=True)
    summary = _format_job_summary(
        job_id, agent, story_id, exit_code, duration_s, in_tokens, out_tokens,
        cost_usd, files_touched, worktree_path=worktree_path, worktree_branch=worktree_branch,
        status_label=status_label, note=note
    )
    with open(_job_summary_path(job_id), "w") as f:
        f.write(summary)
    return summary


def _format_prompt_for_agent(agent: str, context_text: str, story_id: str,
                              task: str, file_section: str, verify_section: str,
                              cwd_hint: Optional[str] = None) -> str:
    """Returns a prompt formatted for the agent's preferred input style."""
    story_ref = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""
    if agent == "codex":
        sentences = [s.strip() for s in re.split(r"[.!?]", task) if s.strip()]
        criteria = "\n".join(f"- {s}" for s in sentences) if sentences else f"- {task}"
        return (
            f"## Task Criteria\n{criteria}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"## Context\n{context_text}"
            f"{story_ref}\n"
        )
    if agent == "agy":
        working_dir = cwd_hint or os.getcwd()
        return (
            f"## Working Directory\n{working_dir}\n"
            f"All file edits MUST be in this directory.\n\n"
            f"Task: {task}\n"
            f"{story_ref}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"Context summary:\n{context_text}"
        )
    return (
        f"{context_text}"
        f"{story_ref}"
        f"{file_section}"
        f"\n\n## Your Task\n{task}"
        f"{verify_section}\n"
    )


_CONTEXT_WARN_BYTES = 81920


def _warn_context_size(context_text: str) -> None:
    size = len(context_text.encode("utf-8"))
    if size > _CONTEXT_WARN_BYTES:
        print(f"  ⚠ context: full ({size // 1024}KB) — exceeds soft limit "
              f"({_CONTEXT_WARN_BYTES // 1024}KB)")
        print("    Use --context-mode task to reduce size")


def _job_worktree_details(job_id: str, agent: str) -> Tuple[str, str]:
    """Returns the per-job worktree path and branch name."""
    worktree_path = os.path.join("worktrees", job_id)
    worktree_branch = f"dispatch/{agent}/{job_id}"
    return worktree_path, worktree_branch


def _create_job_worktree(job_id: str, agent: str) -> str:
    """Create the isolated git worktree for a dispatched job."""
    worktree_path, worktree_branch = _job_worktree_details(job_id, agent)
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", worktree_path, "-b", worktree_branch],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.getcwd(),
    )
    if result.returncode != 0:
        details = "\n".join(
            part for part in [result.stdout.strip(), result.stderr.strip()] if part
        )
        raise RuntimeError(
            f"Failed to create worktree for job {job_id} at {worktree_path} "
            f"on branch {worktree_branch}."
            + (f"\n{details}" if details else "")
        )
    return worktree_path


def _preflight_dispatch(agent_name: str, dispatch_flags: list, db_conn=None, _task_hint: str = "") -> dict:
    import socket as _socket

    baseline = {}
    if db_conn:
        try:
            row = db_conn.execute(
                "SELECT active_flags, active_contract FROM harness_records WHERE agent_name=?",
                (agent_name,),
            ).fetchone()
        except Exception:
            row = None
        if row:
            try:
                baseline["dispatch_flags"] = json.loads(row[0]) if row[0] else {}
                baseline["headless_contract"] = json.loads(row[1]) if row[1] else {}
                baseline["network_deps"] = baseline["headless_contract"].get("network_deps", {})
            except Exception:
                baseline = {}
    if not baseline:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})

    if db_conn:
        try:
            _row = db_conn.execute(
                "SELECT installed_version, last_probe_at FROM harness_records WHERE agent_name=?",
                (agent_name,),
            ).fetchone()
        except Exception:
            _row = None
        if _row:
            _recorded_version, _last_probe_at = _row
            _is_stale = True
            if _last_probe_at:
                try:
                    _probe_ts = time.mktime(time.strptime(_last_probe_at, "%Y-%m-%dT%H:%M:%SZ"))
                    _is_stale = (time.time() - _probe_ts) > 3600
                except ValueError:
                    _is_stale = True
            if _is_stale:
                try:
                    _ver_result = subprocess.run(
                        [agent_name, "--version"], capture_output=True, text=True, timeout=3
                    )
                    _live_version = _ver_result.stdout.strip().split()[-1] if _ver_result.stdout.strip() else "unknown"
                    if _live_version != _recorded_version:
                        write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
                        write_alert(
                            "WARNING",
                            "HARNESS_VERSION_DRIFT",
                            f"Agent '{agent_name}' version changed: {_recorded_version} -> {_live_version}. Run synlynk probe to update.",
                        )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

    flags_spec = baseline.get("dispatch_flags", {})
    invalid_flags = set(flags_spec.get("invalid_flags", [])) if isinstance(flags_spec, dict) else set()
    for flag in dispatch_flags or []:
        f = flag.split("=", 1)[0]
        if f in invalid_flags:
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Flag {f!r} is invalid for agent '{agent_name}' (LIVE-1 class error)",
            }

    if isinstance(flags_spec, dict):
        valid_flags = list(flags_spec.get("valid_flags", []))
        required_flags = list(flags_spec.get("required_flags", []))
    else:
        valid_flags, required_flags = [], []
    if valid_flags or required_flags:
        from synlynk.probe import _run_tc2

        tc2 = _run_tc2(agent_name, flags_spec)
        if not tc2.get("passed", True):
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": (
                    f"TC-2 flag check failed for {agent_name}: {tc2.get('failed_flags', [])}. "
                    f"Run synlynk probe {agent_name} to update."
                ),
            }

    required = baseline.get("network_deps", {}).get("required_endpoints", [])
    for endpoint in required:
        host, _, port_str = endpoint.rpartition(":")
        if not host:
            host = endpoint
        port = int(port_str) if port_str.isdigit() else 443
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            sock.close()
        except (OSError, ConnectionRefusedError, _socket.timeout):
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Required endpoint {endpoint!r} unreachable for agent '{agent_name}'",
            }

    if db_conn and _task_hint:
        try:
            from synlynk.status import TIER1_CAPACITY, estimate_dispatch_tokens

            ctx_path = os.path.join(".synlynk", "context.md")
            context_md = ""
            if os.path.exists(ctx_path):
                with open(ctx_path) as f:
                    context_md = f.read()

            est = estimate_dispatch_tokens(_task_hint, context_md, agent_name)
            cap_row = None
            try:
                cap_row = db_conn.execute(
                    "SELECT read_budget_tokens, write_budget_tokens, tool_budget_count "
                    "FROM harness_status WHERE agent_name=?",
                    (agent_name,),
                ).fetchone()
            except Exception:
                cap_row = None

            if cap_row and any(v is not None for v in cap_row):
                read_budget, write_budget, tool_budget = cap_row
            else:
                tier1 = TIER1_CAPACITY.get(agent_name, {})
                read_budget = tier1.get("read_budget_tokens", 999_999)
                write_budget = tier1.get("write_budget_tokens", 32_000)
                tool_budget = tier1.get("tool_budget_count", 200)

            if est["input"] >= (read_budget or 0):
                return {
                    "passed": False,
                    "sentinel": "CAPACITY_EXCEEDED_INPUT",
                    "reason": (
                        f"task needs ~{est['input']:,} input tokens; "
                        f"{agent_name} budget is {(read_budget or 0):,}."
                    ),
                }

            if est["output"] >= (write_budget or 0):
                return {
                    "passed": False,
                    "sentinel": "CAPACITY_EXCEEDED_OUTPUT",
                    "reason": (
                        f"task needs ~{est['output']:,} output tokens; "
                        f"{agent_name} write budget is {(write_budget or 0):,}."
                    ),
                }

            if tool_budget and est["tools"] > tool_budget * 0.7:
                write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
                write_alert(
                    "WARNING",
                    "TOOL_PRESSURE",
                    f"{agent_name} tool budget ~{tool_budget}; estimated usage {est['tools']}",
                )
        except Exception:
            pass

    return {"passed": True, "sentinel": None, "reason": None}


def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None) -> dict:
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    if story_id and not force_agent:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                agent = best

    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")

    if agent == "local":
        get_db = _pkg("_get_db")
        conn = get_db() if get_db else None
        if conn is not None:
            try:
                local_config = json.load(open(os.path.join(".agents", "local.json")))
            except (OSError, json.JSONDecodeError):
                local_config = {}
            max_concurrent = local_config.get("max_concurrent", 1)
            if _local_concurrency_exceeded(conn, max_concurrent=max_concurrent):
                raise RuntimeError(
                    f"local agent at max concurrency ({max_concurrent}); "
                    "wait for the running job to finish"
                )

    baselines = baselines_map[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"] + _dispatch_flags_for_agent(agent)
    overrides = _load_harness_overrides(agent)
    for key, value in overrides.get("dispatch_flags", {}).items():
        flags = flags + [f"--{key}"] if value in (None, "") else flags + [f"--{key}", str(value)]
    load_config = _pkg("load_config")
    cfg = load_config() if load_config else {}
    role_list = (cfg.get("roles", {}) or {}).get(agent, [])
    permissions = _resolve_dispatch_permissions(agent, role_list=role_list, grants=grants, revokes=revokes)
    flags = flags + _permissions_to_flags(agent, permissions)
    if agent == "agy" and permissions:
        perm_lines = "\n".join(f"- {p}" for p in permissions)
        task = f"## Permissions\n{perm_lines}\n\n{task}"
    if not skip_preflight:
        preflight_fn = _pkg("_preflight_dispatch", _preflight_dispatch)
        _get_db_fn = _pkg("_get_db")
        _preflight_db = _get_db_fn() if _get_db_fn else None
        try:
            preflight = preflight_fn(agent_name=agent, dispatch_flags=flags, db_conn=_preflight_db, _task_hint=task)
        except TypeError:
            preflight = preflight_fn(agent_name=agent, dispatch_flags=flags, db_conn=_preflight_db)
        if isinstance(preflight, dict):
            if not preflight.get("passed", False):
                sentinel_path = os.path.join(".synlynk", "sentinel.md")
                write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
                write_alert("CRITICAL", preflight["sentinel"], preflight["reason"], sentinel_path)
                raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight['reason']}")
        elif preflight:
            sentinel_path = os.path.join(".synlynk", "sentinel.md")
            write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
            write_alert("CRITICAL", "HARNESS_PREFLIGHT_FAIL", str(preflight), sentinel_path)
            raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight}")

    load_profile = _pkg("_load_agent_profile")
    profile = load_profile(agent) if load_profile else {}
    dispatch_mode = (cfg or {}).get("dispatch_mode", "daily-grind") if load_config else "daily-grind"
    if agent == "grok" and profile.get("always_approve_unsupported"):
        flags = [flag for flag in flags if flag != "--always-approve"]
        flags = flags + ["--permission-mode", "bypassPermissions"]
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    if agent == "claude":
        flags = flags + ["--output-format", "stream-json", "--verbose"]
    if agent == "agy":
        flags = flags + ["--output-format", "json"]
    if agent == "codex":
        flags = flags + ["--json"]
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=5,
            )
            if result.returncode == 0:
                git_common_dir = result.stdout.strip()
                if git_common_dir:
                    flags = flags + ["--add-dir", git_common_dir]
        except Exception:
            pass

    probe_model = _pkg("_probe_model_version")
    model_at_dispatch = probe_model(agent, cli) if probe_model else "unknown"
    if context_mode is None:
        context_mode = profile.get("context_mode", "task")
    hint = _context_mode_hint(context_mode, task)
    if hint:
        print(f"    {hint}")

    import hashlib as _hashlib
    if not job_id:
        job_id = "job-" + _hashlib.md5(f"{agent}{task}{time.time()}".encode()).hexdigest()[:8]

    worktree_path, worktree_branch = _job_worktree_details(job_id, agent)
    worktree_path = _create_job_worktree(job_id, agent)
    worktree_synlynk_dir = os.path.join(worktree_path, ".synlynk")
    logs_dir = os.path.join(worktree_synlynk_dir, "logs")
    prompts_dir = os.path.join(worktree_synlynk_dir, "prompts")
    contexts_dir = os.path.join(worktree_synlynk_dir, "contexts")
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(contexts_dir, exist_ok=True)

    log_file = os.path.abspath(os.path.join(logs_dir, f"{job_id}.log"))
    prompt_file = os.path.abspath(os.path.join(prompts_dir, f"{job_id}.md"))
    context_file = os.path.abspath(os.path.join(contexts_dir, f"{job_id}.md"))

    context_text = ""
    if context_mode != "none":
        if context_mode == "task":
            scope = f"task:{story_id}" if story_id else "task"
        else:
            scope = "full"
        try:
            generate_context = _pkg("generate_context")
            context_text = generate_context(scope=scope, out_path=context_file) or ""
        except Exception:
            pass
    warn_context = _pkg("_warn_context_size", _warn_context_size)
    warn_context(context_text)

    context_max_bytes = profile.get("context_max_bytes")
    if context_max_bytes is not None:
        try:
            context_max_bytes = int(context_max_bytes)
        except (TypeError, ValueError):
            context_max_bytes = None
    if context_max_bytes is not None:
        encoded_context = context_text.encode("utf-8")
        if len(encoded_context) > context_max_bytes:
            context_text = encoded_context[:context_max_bytes].decode("utf-8", errors="ignore")
            print(f"  context truncated to {context_max_bytes}B (agent profile limit)")

    relevant_files = _pkg("_relevant_files_for_story")
    file_list = relevant_files(story_id) if (story_id and relevant_files) else []
    file_section = ""
    if file_list:
        file_section = "\n\n## Relevant Files\n" + "\n".join(f"- `{f}`" for f in file_list)

    verify_contract = _pkg("_verify_contract_for_story")
    verify_section = verify_contract(story_id, task) if (story_id and verify_contract) else ""

    format_prompt = _pkg("_format_prompt_for_agent", _format_prompt_for_agent)
    try:
        prompt = format_prompt(
            agent,
            context_text,
            story_id or "",
            task,
            file_section,
            verify_section,
            cwd_hint=worktree_path,
        )
    except TypeError:
        prompt = format_prompt(agent, context_text, story_id or "", task, file_section, verify_section)
    with open(prompt_file, "w") as f:
        f.write(prompt)

    fence_data = None
    load_config_fn = _pkg("load_config")
    fence_config = load_config_fn() if load_config_fn else {}
    from synlynk.fencing import FenceData, is_fenced_command
    from synlynk.status import estimate_dispatch_tokens
    if is_fenced_command("dispatch", fence_config):
        rate_fn = _pkg("_model_rate_for_version")
        if context_mode == "none":
            est = estimate_dispatch_tokens(prompt, context_text, agent)
            in_tok, out_tok = est["input"], est["output"]
            basis = "prompt_estimate"
        else:
            db_conn = _pkg("_get_db")
            conn = db_conn() if db_conn else None
            if conn is not None:
                if story_id:
                    row = conn.execute(
                        "SELECT estimated_tokens FROM stories WHERE story_id=?",
                        (story_id,),
                    ).fetchone()
                    if row and row[0]:
                        total_tokens = int(row[0])
                        half = total_tokens // 2
                        in_tok, out_tok, basis = half, total_tokens - half, "story_estimate"
                    else:
                        discipline = None
                        phase = None
                        row = conn.execute(
                            "SELECT discipline, phase FROM stories WHERE story_id=?",
                            (story_id,),
                        ).fetchone()
                        if row:
                            discipline, phase = row[0], row[1]
                        if discipline and phase:
                            rows = conn.execute(
                                """SELECT cost_entries.input_tokens, cost_entries.output_tokens
                                   FROM cost_entries
                                   JOIN stories ON cost_entries.story_id = stories.story_id
                                   WHERE stories.discipline = ?
                                     AND stories.phase = ?
                                     AND cost_entries.cost_source IN ('actual', 'estimated_token_rate')
                                   ORDER BY cost_entries.id DESC
                                   LIMIT ?""",
                                (discipline, phase, 20),
                            ).fetchall()
                            if len(rows) >= 3:
                                avg_in = sum((row[0] or 0) for row in rows) // len(rows)
                                avg_out = sum((row[1] or 0) for row in rows) // len(rows)
                                in_tok, out_tok, basis = avg_in, avg_out, "historical_avg"
                            else:
                                in_tok, out_tok, basis = 5000, 2000, "fixed_default"
                        else:
                            in_tok, out_tok, basis = 5000, 2000, "fixed_default"
                else:
                    in_tok, out_tok, basis = 5000, 2000, "fixed_default"
            else:
                in_tok, out_tok, basis = 5000, 2000, "fixed_default"
        rates = rate_fn(model_at_dispatch, agent=agent) if rate_fn else {"input": 0.003, "output": 0.015}
        cost_usd = (in_tok / 1000 * rates["input"]) + (out_tok / 1000 * rates["output"])
        fence_data = FenceData(
            command="dispatch",
            kind="estimate",
            in_tokens=in_tok,
            out_tokens=out_tok,
            cost_usd=cost_usd,
            basis=basis,
        )

    import shlex as _shlex
    prompt_file_flag = baselines.get("prompt_file_flag")
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")
    if prompt_file_flag:
        cmd_str = " ".join(
            _shlex.quote(c) for c in [cli] + flags + [prompt_file_flag, prompt_file]
        )
        shell_cmd = f"{cmd_str} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"
    elif prompt_via_arg:
        if prompt_flag:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
        else:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"

    contract = baselines.get("headless_contract", {})
    proc_env = os.environ.copy()
    proc_env.update(overrides.get("env", {}))
    for var in contract.get("env_vars_required", []):
        if "=" in var:
            k, v = var.split("=", 1)
            proc_env[k] = v

    proc = subprocess.Popen(
        ["sh", "-c", shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=worktree_path,
        env=proc_env,
    )

    job = {
        "id": job_id,
        "agent": agent,
        "story_id": story_id or "",
        "task": task,
        "cycle": cycle,
        "pid": proc.pid,
        "log_file": log_file,
        "prompt_file": prompt_file,
        "context_file": context_file if context_mode != "none" else "",
        "worktree_path": worktree_path,
        "worktree_branch": worktree_branch,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": dispatch_mode,
        "dispatch_rework": _pkg("_count_dispatch_rework")(story_id or "") if _pkg("_count_dispatch_rework") else 0,
        "micro_rework": 0,
        "retry_count": 0,
        "model_at_dispatch": model_at_dispatch,
        "fence": fence_data,
    }

    load_jobs = _pkg("_load_jobs")
    save_jobs = _pkg("_save_jobs")
    jobs = load_jobs() if load_jobs else []
    jobs.append(job)
    if save_jobs:
        jobs_to_save = []
        for saved_job in jobs:
            if hasattr(saved_job.get("fence"), "__dataclass_fields__"):
                saved_job = dict(saved_job)
                saved_job["fence"] = asdict(saved_job["fence"])
            jobs_to_save.append(saved_job)
        save_jobs(jobs_to_save)

    dconn = None
    get_db = _pkg("_get_db")
    try:
        dconn = get_db() if get_db else None
        if dconn is not None:
            existing = dconn.execute(
                "SELECT 1 FROM daemon_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                # Preserve priority/depends_on/enqueued_at from the queue row.
                dconn.execute(
                    "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, "
                    "log_path=?, agent=?, task=?, story_id=? WHERE job_id=?",
                    (
                        proc.pid,
                        job["started_at"],
                        log_file,
                        agent,
                        task,
                        story_id,
                        job_id,
                    ),
                )
            else:
                dconn.execute(
                    "INSERT OR REPLACE INTO daemon_jobs "
                    "(job_id, agent, task, story_id, status, priority, depends_on, pid, "
                    "enqueued_at, started_at, log_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        agent,
                        task,
                        story_id,
                        "running",
                        5,
                        "[]",
                        proc.pid,
                        job["started_at"],
                        job["started_at"],
                        log_file,
                    ),
                )
            dconn.commit()
    finally:
        if dconn is not None:
            try:
                dconn.close()
            except Exception:
                pass

    log_telemetry = _pkg("log_telemetry_event")
    if log_telemetry:
        log_telemetry({"type": "dispatch", "agent": agent, "story_id": story_id, "job_id": job_id})
    return job


def exec_command(cmd_args: list, force: bool = False) -> int:
    if not cmd_args:
        print("Error: No command provided to exec.")
        return 1

    generate_context = _pkg("generate_context")
    check_budgets = _pkg("check_budgets")
    set_state = _pkg("set_state")
    check_costs = _pkg("_check_costs_freshness", lambda: None)
    log_telemetry = _pkg("log_telemetry_event")
    check_sentinels = _pkg("check_sentinel_patterns")
    update_costs = _pkg("update_costs")
    extract_tokens = _pkg("extract_tokens")
    extract_model_version = _pkg("extract_model_version")
    model_rate_for_version = _pkg("_model_rate_for_version")
    get_username = _pkg("get_username")
    check_drift = _pkg("_check_instruction_drift", lambda: None)
    watch_daemon_cls = _pkg("WatchDaemon")

    if generate_context:
        generate_context()
    cmd_args = _inject_grok_rules(cmd_args)
    if check_budgets:
        check_budgets()

    check_gate = _pkg("_check_pre_exec_gate", _check_pre_exec_gate)
    run_housekeeping = _pkg("_run_daily_housekeeping", lambda: None)
    if run_housekeeping:
        run_housekeeping()
    if not check_gate(force=force):
        return 1

    if set_state:
        set_state("active")
    print(f"  Executing: {' '.join(cmd_args)}")
    start_time = time.time()
    exit_code = 0
    output_text = ""

    try:
        interactive = _is_interactive(cmd_args)
        if interactive:
            process = subprocess.Popen(cmd_args)
            process.wait()
            exit_code = process.returncode
        else:
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            buffer: list = []
            stream_meta = {"first_output_at": None, "output_bytes": 0}
            tee_thread = threading.Thread(target=_tee_process, args=(process, buffer, stream_meta))
            tee_thread.start()
            process.wait()
            tee_thread.join()
            exit_code = process.returncode
            output_text = "".join(buffer)
    except FileNotFoundError:
        exit_code = 127
        print(f"  Error: Command '{cmd_args[0]}' not found.")
    except Exception as e:
        exit_code = 1
        print(f"  Error: {e}")
    finally:
        duration = time.time() - start_time
        print(f"\n  ✓ Execution finished in {duration:.2f}s")

        if extract_tokens:
            token_counts = extract_tokens(output_text, agent=cmd_args[0])
            in_tokens, out_tokens = token_counts
            cache_read_tokens = getattr(token_counts, "cache_read_tokens", 0)
            basis = getattr(token_counts, "basis", "none")
        else:
            in_tokens, out_tokens, cache_read_tokens, basis = 0, 0, 0, "none"

        if not _is_interactive(cmd_args):
            model_version = extract_model_version(output_text, agent=cmd_args[0]) if extract_model_version else "unknown"
            if update_costs:
                cmd_label = " ".join(cmd_args)
                if exit_code != 0 and in_tokens == 0 and out_tokens == 0:
                    cmd_label = "[failed job] " + cmd_label
                update_costs(
                    cmd_label,
                    in_tokens,
                    out_tokens,
                    duration,
                    cache_read_tokens=cache_read_tokens,
                    model_version=model_version,
                    agent=cmd_args[0],
                    basis=basis,
                )
            if in_tokens > 0 or out_tokens > 0:
                rates = model_rate_for_version(model_version, agent=cmd_args[0]) if model_rate_for_version else {
                    "input": 0.003,
                    "output": 0.015,
                    "cache_read": 0.0000003,
                }
                est_cost = (
                    (in_tokens / 1000 * rates["input"]) +
                    (out_tokens / 1000 * rates["output"]) +
                    (cache_read_tokens / 1000 * rates["cache_read"])
                )
                print(f"  ⚡ Tokens: {in_tokens:,} in / {out_tokens:,} out  |  est. ${est_cost:.4f}")
            else:
                print(f"  ⚡ Token count unavailable — logged as estimated_tshirt fallback")
        else:
            print("  ⚡ Token count unavailable (interactive mode)")

        if check_costs:
            check_costs()
        if log_telemetry:
            tool_call_count = _pkg("_count_tool_calls", lambda _text: 0)(output_text)
            output_bytes = 0
            first_output_at = None
            output_velocity_bpm = None
            if not _is_interactive(cmd_args):
                output_bytes = len(output_text.encode("utf-8"))
                if output_text:
                    first_output_at = stream_meta.get("first_output_at") if "stream_meta" in locals() else None
                if duration > 0 and output_bytes > 0:
                    output_velocity_bpm = round(output_bytes / (duration / 60.0), 1)
            log_telemetry({
                "type": "exec",
                "schema_version": 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "_ts": time.time(),
                "user": get_username() if get_username else "unknown",
                "command": " ".join(cmd_args),
                "duration": round(duration, 2),
                "exit_code": exit_code,
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "first_output_at": first_output_at,
                "tool_call_count": tool_call_count,
                "rescue_agent": None,
                "output_velocity_bpm": output_velocity_bpm,
            })
            # #291: roll exec usage into agent_quotas so stage-2 headroom is live
            refresh_quotas = _pkg("_refresh_agent_quotas_from_telemetry") or _pkg(
                "refresh_agent_quotas_from_telemetry"
            )
            if refresh_quotas:
                try:
                    refresh_quotas()
                except Exception:
                    pass
        if check_sentinels:
            check_sentinels(output_text=output_text, exit_code=exit_code, cmd=" ".join(cmd_args))
        if check_drift:
            check_drift()
        if watch_daemon_cls is not None:
            daemon = watch_daemon_cls()
            if set_state:
                set_state("watching" if daemon._is_running() else "stopped")

    return exit_code
