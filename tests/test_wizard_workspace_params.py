"""Regression coverage for wizard workspace selection parameters."""

import io

import synlynk
from synlynk.cli import build_parser


def test_repo_picker_toggles_multi_digit_index_and_defaults_to_cwd(monkeypatch):
    """A line of ``10`` targets repo 10, while only cwd starts selected.

    This fails if the picker reverts to single-key reads or defaults every
    discovered repository to selected.
    """
    repos = [
        {
            "path": f"/work/repo-{index}",
            "name": f"repo-{index}",
            "stack_labels": [],
            "readme_excerpt": "",
            "context_sections": {},
        }
        for index in range(1, 13)
    ]
    scan = {"workspace_name": "workspace", "repos": repos}

    monkeypatch.setattr("sys.stdin", io.StringIO("\n10\n\n"))
    monkeypatch.setattr(synlynk.os, "getcwd", lambda: "/work/repo-1")

    result = synlynk._wiz_screen_workspace_name_pick(scan)

    assert [repo["name"] for repo in result["repos"]] == ["repo-1", "repo-10"]


def test_init_discover_flag_is_opt_in():
    """Ambient repository discovery is enabled only with ``init --discover``."""
    parser = build_parser()

    assert parser.parse_args(["init"]).discover is False
    assert parser.parse_args(["init", "--discover"]).discover is True


def test_wizard_scan_limits_repositories_to_cwd_unless_discover(monkeypatch, tmp_path):
    """The wizard must not ambient-scan unless the user asks it to."""
    scan_calls = []
    scan = {
        "workspace_name": "repo-1",
        "repos": [],
        "harnesses": [],
        "agents": [],
        "skills": [],
    }

    def run_workspace_scan(**kwargs):
        scan_calls.append(kwargs)
        return scan

    monkeypatch.setattr(synlynk, "run_workspace_scan", run_workspace_scan)
    monkeypatch.setattr(synlynk, "_wiz_screen_landing", lambda: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_harness", lambda _scan: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_topology", lambda _scan: "single")
    monkeypatch.setattr(synlynk, "_wiz_screen_skills", lambda _scan: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_agents", lambda _scan: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_roles", lambda _scan: {})
    monkeypatch.setattr(synlynk, "_wiz_screen_launch", lambda *args, **kwargs: None)
    monkeypatch.setattr(synlynk, "load_config", lambda: {})
    monkeypatch.chdir(tmp_path)

    synlynk.wizard_init(dry_run=True)
    synlynk.wizard_init(dry_run=True, discover=True)

    assert scan_calls == [
        {"roots": [str(tmp_path)], "deep": False},
        {"roots": None, "deep": False},
    ]
