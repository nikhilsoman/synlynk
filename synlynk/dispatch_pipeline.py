"""Explicit dispatch stages over a DispatchRequest and HarnessAdapter.

Stage order: resolve -> authorize -> prepare_worktree -> spawn -> observe ->
finalize. Harness-specific behavior remains behind the adapter protocol.
"""

import subprocess
from dataclasses import replace

from synlynk.harness_adapters.base import HarnessAdapter
from synlynk.harness_adapters.request import DispatchRequest


def resolve(request: DispatchRequest) -> DispatchRequest:
    """Resolve the requested harness using the existing dispatch router."""
    from synlynk.dispatch import resolve_dispatch_harness

    resolved_agent = resolve_dispatch_harness(
        request.agent,
        agent_id=request.agent_id,
        story_id=request.story_id,
        force_agent=request.force_agent,
        requires_gh_write=request.requires_gh_write,
        static_baseline=request.static_baseline,
        task_domain=request.task_domain,
        criticality=request.criticality,
        lambda_=request.lambda_,
        task=request.task,
        task_type=request.task_type,
        requires=request.requires,
        grants=request.grants,
        revokes=request.revokes,
    )
    return replace(request, agent=resolved_agent)


def authorize(request: DispatchRequest) -> None:
    """Enforce policy authority for task-typed dispatches."""
    if not request.task_type:
        return

    from synlynk.dispatch import check_authority

    try:
        authority = check_authority(
            f"task_dispatch:{request.task_type}",
            role=request.role or "dev",
            repo_path=".",
            enforce_role_compat=request.role is not None,
        )
    except ValueError:
        authority = None
    if authority is not None and not authority.allowed:
        raise RuntimeError(
            f"Dispatch refused: task_type {request.task_type!r} is not an authorized "
            f"task_type for role {request.role or 'dev'!r} per policy.json (see #423, #569)."
        )


def prepare_worktree(request: DispatchRequest) -> dict:
    """Create the isolated job worktree using the existing implementation."""
    from synlynk.dispatch import _create_job_worktree

    return _create_job_worktree(
        job_id=request.job_id,
        agent=request.agent,
        base=request.base,
        scoped_paths=request.scope_paths,
    )


def spawn(request: DispatchRequest, adapter: HarnessAdapter, env: dict, cwd: str) -> dict:
    """Build and execute a harness command, preserving its raw output."""
    proc = subprocess.Popen(
        adapter.build_cmd(request),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=cwd,
    )
    output, _ = proc.communicate()
    raw_output = (
        output.decode("utf-8", errors="replace")
        if isinstance(output, bytes)
        else (output or "")
    )
    return {"exit_code": proc.returncode, "raw_output": raw_output}


def observe(spawn_result: dict, adapter: HarnessAdapter) -> dict:
    """Parse output and classify any adapter-specific failure."""
    raw_output = spawn_result["raw_output"]
    event = adapter.parse_output(raw_output)
    failure = adapter.classify_failure(
        spawn_result["exit_code"], raw_output, raw_output
    )
    return {"event": event, "failure": failure,
            "lifecycle_events": getattr(event, "lifecycle_events", ()),
            "compatibility_evidence": getattr(event, "compatibility_evidence", None),
            **spawn_result}


def finalize(request: DispatchRequest, observed: dict) -> dict:
    """Write the complete job summary using the current summary contract."""
    from synlynk.dispatch import _write_job_summary

    _write_job_summary(
        job_id=request.job_id or "",
        agent=request.agent,
        story_id=request.story_id,
        exit_code=observed.get("exit_code"),
        duration_s=observed.get("duration_s"),
        in_tokens=observed.get("in_tokens", 0),
        out_tokens=observed.get("out_tokens", 0),
        cost_usd=observed.get("cost_usd", 0.0),
        files_touched=observed.get("files_touched"),
        worktree_path=observed.get("worktree_path"),
        worktree_branch=observed.get("worktree_branch"),
        status_label=observed.get("status_label"),
        note=observed.get("note"),
        base_branch=observed.get("base_branch"),
        base_sha=observed.get("base_sha"),
        suite_result=observed.get("suite_result"),
        task_sha256=observed.get("task_sha256"),
        task_preview=observed.get("task_preview"),
        log_text=observed.get("raw_output"),
    )
    return observed
