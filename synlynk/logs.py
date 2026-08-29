"""Rendering and display helpers for dispatched job logs."""

import json
import os
import re


def _pkg(name):
    import synlynk
    return getattr(synlynk, name)


def _render_codex_log_line(line: str):
    stripped = line.strip()
    if not stripped:
        return line
    try:
        event = json.loads(stripped)
    except (ValueError, TypeError):
        return line
    if not isinstance(event, dict):
        return line
    if event.get("type") in {"thread.started", "turn.started", "item.started", "turn.completed"}:
        return None
    if event.get("type") == "item.completed":
        item = event.get("item", {})
        if not isinstance(item, dict):
            return line
        if item.get("type") == "agent_message":
            return f"{item.get('text', '')}\n\n"
        if item.get("type") == "command_execution":
            output = (item.get("aggregated_output") or "").rstrip("\n")
            return f"$ {item.get('command', '')}\n{output}\n\n"
    return line


def _render_claude_log_line(line: str):
    stripped = line.strip()
    if not stripped:
        return line
    try:
        event = json.loads(stripped)
    except (ValueError, TypeError):
        return line
    if not isinstance(event, dict):
        return line
    if event.get("type") in {"system", "rate_limit_event", "result", "user"}:
        return None
    if event.get("type") != "assistant":
        return line
    message = event.get("message", {})
    content = message.get("content", []) if isinstance(message, dict) else []
    if not isinstance(content, list):
        return None
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text", ""):
            parts.append(f"{block['text']}\n\n")
        elif block.get("type") == "tool_use":
            try:
                args = json.dumps(block.get("input", {}), separators=(",", ":"))
            except (TypeError, ValueError):
                args = str(block.get("input", {}))
            parts.append(f"$ {block.get('name', '')}({args})\n\n")
    return "".join(parts) if parts else None


def _redact_active_tokens(text: str) -> str:
    from synlynk.github_app_auth import _load_redaction_tokens
    for token in _load_redaction_tokens():
        text = text.replace(token, "***REDACTED***")
    return text


_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"), re.compile(r"gh[oprsu]_[A-Za-z0-9]{36}"),
    re.compile(r"ghs_[A-Za-z0-9._-]{20,}"), re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"), re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]


def _redact_secret_patterns(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def cmd_logs(job_id: str, tail: int = 50) -> None:
    jobs = _pkg("_load_jobs")()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        print(f"No job found with id '{job_id}'. Run `synlynk jobs` to list jobs.")
        return
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        print(f"Log file not found for job {job_id}.")
        return
    print(f"{_pkg('_BOLD')}── logs: {job_id} ({job['agent']}) ─────────────────────────{_pkg('_RESET')}")
    with open(log_file) as f:
        lines = f.readlines()
    renderer = {"codex": _render_codex_log_line, "claude": _render_claude_log_line}.get(job.get("agent"))
    for line in lines[-tail:]:
        rendered = renderer(line) if renderer else line
        if rendered is not None:
            print(_redact_secret_patterns(_redact_active_tokens(rendered)), end="")
    if len(lines) > tail:
        print(f"\n{_pkg('_DIM')}(showing last {tail} of {len(lines)} lines){_pkg('_RESET')}")
    summary_path = _pkg("_job_summary_path")(job_id)
    if os.path.exists(summary_path):
        print()
        with open(summary_path) as f:
            print(f.read(), end="")
