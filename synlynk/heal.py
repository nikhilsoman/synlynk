"""Closed-loop autonomous remediation orchestration."""
from __future__ import annotations

import json
import subprocess


def _diagnostics(scan: dict) -> list[dict]:
    """Normalize scanner findings into backlog work items."""
    findings = scan.get("findings") or scan.get("diagnostics") or scan.get("gaps") or []
    if isinstance(findings, dict):
        findings = findings.get("items", [])
    result = []
    for finding in findings:
        if isinstance(finding, str):
            result.append({"title": finding, "body": finding, "source_type": "scan"})
        elif isinstance(finding, dict) and (finding.get("title") or finding.get("name")):
            item = dict(finding)
            item.setdefault("title", item.get("name"))
            item.setdefault("body", item.get("description", item["title"]))
            result.append(item)
    return result


def _verify_story(story: dict) -> dict:
    command = story.get("verification_command") or "pytest -q"
    try:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        return {"story_id": story.get("story_id"), "passed": completed.returncode == 0,
                "command": command, "output": (completed.stdout + completed.stderr)[-4000:]}
    except OSError as exc:
        return {"story_id": story.get("story_id"), "passed": False, "command": command, "output": str(exc)}


def _auto_merge(stories: list[dict], verdicts: list[dict]) -> list[str]:
    if not stories or not verdicts or not all(v.get("passed") for v in verdicts):
        return []
    merged = []
    for story in stories:
        pr = story.get("pr_number") or story.get("pull_request")
        if not pr:
            continue
        result = subprocess.run(["gh", "pr", "merge", str(pr), "--squash", "--delete-branch"],
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            merged.append(str(pr))
    return merged


def cmd_heal(args=None, *, batch_size=None, auto_merge=None) -> dict:
    """Run scan -> backlog triage -> swarm dispatch -> QA -> merge."""
    from synlynk.scan import run_workspace_scan
    from synlynk.backlog import stage_discovered_work, triage_backlog, auto_promote_backlog
    from synlynk.tpm_sweep import run_sweep_pass
    from synlynk import _get_db

    batch_size = batch_size if batch_size is not None else getattr(args, "batch_size", 1)
    auto_merge = auto_merge if auto_merge is not None else getattr(args, "auto_merge", False)
    scan = run_workspace_scan(deep=True)
    findings = _diagnostics(scan)
    staged = []
    conn = _get_db()
    try:
        for finding in findings[:max(0, batch_size)]:
            staged.append(stage_discovered_work(
                finding["title"], finding.get("body", ""), role=finding.get("role", "dev"),
                stage=finding.get("stage", "sustain"), source_type="scan",
                source_ref=finding.get("source_ref", "scan"), db_conn=conn,
            ))
        triaged = triage_backlog(auto_promote=True, db_conn=conn)
        promoted = auto_promote_backlog(db_conn=conn)
    finally:
        conn.close()
    dispatch = run_sweep_pass()
    stories = promoted or triaged
    verdicts = [_verify_story(story) for story in stories]
    merged = _auto_merge(stories, verdicts) if auto_merge else []
    result = {"scanned": len(findings), "staged": staged, "triaged": triaged,
              "promoted": promoted, "dispatch": dispatch, "qa": verdicts, "merged": merged}
    print(json.dumps(result, indent=2, default=str))
    return result
