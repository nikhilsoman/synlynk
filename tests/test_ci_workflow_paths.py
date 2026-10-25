"""CI workflow path scoping and PR matrix contract for gh:#2529.

The classifier is the production rule in ``synlynk.ci_paths``. The workflow
YAML is parsed (Ruby YAML, which GitHub-hosted runners provide) so the
matrix and required jobs cannot drift away from that rule.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from synlynk.ci_paths import is_bookkeeping_only

WORKFLOW = Path(".github/workflows/test.yml")


def test_bookkeeping_classification():
    assert is_bookkeeping_only(["project-docs/devlogs/agy.md", "docs/blog/01.md"])
    assert is_bookkeeping_only(
        [
            "docs/brainstorm/session/notes.html",
            "CHANGELOG.md",
            ".gitattributes",
            ".gitignore",
            "roadmap.md",
            "todo.md",
            ".synlynk/config.json",
        ]
    )
    assert not is_bookkeeping_only(["docs/superpowers/specs/new-spec.md"])
    assert not is_bookkeeping_only(["docs/superpowers/plans/new-plan.md"])
    assert not is_bookkeeping_only(["synlynk/cli.py", "project-docs/todo.md"])
    assert not is_bookkeeping_only(["README.md"])
    assert not is_bookkeeping_only(["tests/README.md"])
    assert not is_bookkeeping_only([".github/workflows/test.yml"])
    assert not is_bookkeeping_only([])


def _load_workflow():
    """Parse the workflow with a real YAML loader. ``on`` is a YAML 1.1 bool."""
    proc = subprocess.run(
        [
            "ruby",
            "-ryaml",
            "-rjson",
            "-e",
            "puts JSON.generate(YAML.load_file(ARGV[0]))",
            str(WORKFLOW),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    doc = json.loads(proc.stdout)
    trigger = doc.get("on") or doc.get("true")
    assert isinstance(trigger, dict), "workflow trigger block did not parse"
    return doc, trigger


def test_workflow_yaml_parses_and_scopes_the_pr_matrix():
    text = WORKFLOW.read_text(encoding="utf-8")
    doc, trigger = _load_workflow()

    assert trigger["push"]["branches"] == ["main", "unstable"]
    assert "v*" in trigger["push"]["tags"]
    assert trigger["pull_request"]["branches"] == ["main", "unstable"]
    assert "workflow_dispatch" in trigger
    # A trigger-level paths-ignore skips qa-gate and leaves required checks
    # stuck on Expected (gh:#2505). Exemption is in-job instead.
    assert "paths-ignore" not in trigger.get("pull_request", {})
    assert "paths" not in trigger.get("pull_request", {})

    jobs = doc["jobs"]
    assert "qa-gate" in jobs
    assert "release-docs" in jobs
    assert "pull_request" in jobs["qa-gate"]["if"]
    assert "workflow_dispatch" in jobs["qa-gate"]["if"]
    assert "pull_request" in jobs["release-docs"]["if"]
    assert "workflow_dispatch" in jobs["release-docs"]["if"]
    assert "refs/tags/v" in jobs["release-docs"]["if"]

    test_job = jobs["test"]
    matrix = test_job["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest", "macos-latest"]
    assert matrix["python-version"] == ["3.10", "3.12"]
    # Only pull_request narrows the matrix. Push (main, unstable, version
    # tags) and workflow_dispatch keep every leg.
    assert "pull_request" in test_job["if"]
    assert "ubuntu-latest" in test_job["if"]
    assert "3.12" in test_job["if"]
    assert "format('test ({0})', matrix.python-version)" in text
    assert "is_bookkeeping_only" in text
    assert "bookkeeping_only" in text
    assert "grep -qvE '^(docs/|project-docs/|.*\\.md$)'" not in text
