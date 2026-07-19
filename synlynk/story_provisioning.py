"""Story provisioning helpers for dispatch story_id resolution."""

import json
import re
import subprocess
import sys
import time

_ISSUE_NUMBER_RE = re.compile(r"#(\d+)")

_DISCIPLINE_KEYWORDS = {
    "frontend": ("frontend", "css", "html", "ui ", "react"),
    "backend": ("backend", "api", "server", "database", "db_path", "sqlite"),
    "data": ("data pipeline", "etl", "dataset"),
    "ml": ("model training", "ml ", "machine learning"),
    "testing": ("test", "pytest", "selftest", "flaky"),
    "security": ("security", "auth", "vulnerability", "cve"),
    "devops": ("ci ", "deploy", "pipeline", "docker", "infra"),
    "docs": ("docs", "documentation", "readme", "blog post"),
    "architecture": ("architecture", "redesign", "refactor"),
}

_ORG_DOMAIN_LABEL_MAP = {
    "documentation": "content",
}


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _detect_issue_number(task_text: str, issue=None):
    """Resolve an issue number from an explicit flag or task text."""
    if issue is not None:
        return int(issue)
    match = _ISSUE_NUMBER_RE.search(task_text or "")
    if match:
        return int(match.group(1))
    return None


def _classify_heuristic(issue_number, task_text: str) -> dict:
    """Classify a story using GitHub issue metadata or task text keywords."""
    title = None
    haystack = (task_text or "").lower()
    labels = []

    if issue_number is not None:
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_number), "--json", "title,body,labels"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                issue_data = json.loads(result.stdout)
                title = issue_data.get("title")
                labels = [str(lbl.get("name", "")).lower() for lbl in issue_data.get("labels", [])]
                haystack = f"{title or ''} {issue_data.get('body') or ''} {task_text or ''}".lower()
        except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

    if title is None:
        title = (task_text or "").strip()[:200] or f"Ad-hoc dispatch {int(time.time())}"

    discipline = None
    for candidate, keywords in _DISCIPLINE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords) or candidate in labels:
            discipline = candidate
            break

    if discipline is None and "bug" in labels:
        discipline = "backend"

    org_domain = None
    for label in labels:
        if label in _ORG_DOMAIN_LABEL_MAP:
            org_domain = _ORG_DOMAIN_LABEL_MAP[label]
            break

    return {
        "title": title,
        "discipline": discipline,
        "org_domain": org_domain,
        "role": None,
        "stage": None,
    }


def classify_story(issue_number, task_text: str, method: str = "heuristic") -> dict:
    """Dispatch to the configured story classification method."""
    if method == "heuristic":
        return _classify_heuristic(issue_number, task_text)
    if method == "llm":
        raise NotImplementedError("story classification method 'llm' is not yet implemented")
    if method == "pm_manual":
        raise NotImplementedError("story classification method 'pm_manual' is not yet implemented")
    raise ValueError(f"Unknown story_classification method: {method!r}")


def resolve_or_create_story_id(task_text: str, issue=None) -> str:
    """Return an existing or newly-created story_id for a dispatch."""
    issue_number = _detect_issue_number(task_text, issue=issue)
    if issue_number is not None:
        story_id = f"story-issue-{issue_number}"
    else:
        story_id = f"story-adhoc-{int(time.time())}"

    get_db = _pkg("_get_db")
    if get_db is None:
        raise RuntimeError("synlynk._get_db is unavailable")
    conn = get_db()
    try:
        exists = conn.execute(
            "SELECT 1 FROM stories WHERE story_id=?",
            (story_id,),
        ).fetchone()
    finally:
        conn.close()
    if exists:
        return story_id

    load_config = _pkg("load_config")
    config = load_config() if load_config else {}
    method = (config.get("story_classification") or {}).get("method", "heuristic")
    classification = classify_story(issue_number, task_text, method=method)

    cmd_story_create = _pkg("cmd_story_create")
    if cmd_story_create is None:
        raise RuntimeError("synlynk.cmd_story_create is unavailable")
    cmd_story_create(
        classification["title"],
        discipline=classification["discipline"],
        org_domain=classification["org_domain"],
        role=classification["role"],
        stage=classification["stage"],
        story_id=story_id,
    )
    return story_id
