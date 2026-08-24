import os
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from synlynk.pm_agent import (
    _compose_prompt,
    _invoke_headless_claude,
    _load_config,
    _resolve_decide_panel,
    cmd_pm_sweep,
)
from synlynk.team import HARNESS_CAPABILITY_BASELINES


def test_load_config_reads_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.json", "w") as f:
        f.write(textwrap.dedent("""\
            {
              "segments": [{"name": "solo indie devs", "competitors": ["Superpowers", "GStack"]}],
              "decide_panel": "auto",
              "research_issue_labels": ["competitive-research", "architect"],
              "proposal_issue_labels": ["feature-proposal", "needs-user-review"]
            }
        """))
    config = _load_config()
    assert config["segments"][0]["name"] == "solo indie devs"
    assert config["segments"][0]["competitors"] == ["Superpowers", "GStack"]
    assert config["decide_panel"] == "auto"
    assert config["research_issue_labels"] == ["competitive-research", "architect"]


def test_resolve_decide_panel_auto_returns_all_known_harnesses():
    panel = _resolve_decide_panel("auto")
    assert panel == sorted(HARNESS_CAPABILITY_BASELINES.keys())


def test_resolve_decide_panel_explicit_list():
    panel = _resolve_decide_panel("claude,codex")
    assert panel == ["claude", "codex"]


def test_compose_prompt_includes_segments_competitors_panel_labels():
    config = {
        "segments": [
            {"name": "solo indie devs", "competitors": ["Superpowers", "GStack"]},
        ],
        "decide_panel": "claude,codex",
        "research_issue_labels": ["competitive-research", "architect"],
        "proposal_issue_labels": ["feature-proposal", "needs-user-review"],
    }
    prompt = _compose_prompt(config)
    assert "solo indie devs" in prompt
    assert "Superpowers" in prompt
    assert "GStack" in prompt
    assert "claude" in prompt and "codex" in prompt
    assert "competitive-research" in prompt
    assert "feature-proposal" in prompt
    assert "docs/strategy/competitive-landscape.md" in prompt
    assert "gh issue create" in prompt
    assert "--label competitive-research,architect" in prompt
    assert "--label feature-proposal,needs-user-review" in prompt
    assert "synlynk decide" in prompt
    assert "--panel claude,codex --record" in prompt
    assert "harness-maintainer POV" in prompt


def test_invoke_headless_claude_builds_expected_command():
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout='{"result": "ok"}', stderr=""
        )
        result = _invoke_headless_claude("do the sweep")
    args = mock_run.call_args[0][0]
    assert args[0] == "claude"
    assert "-p" in args
    assert "do the sweep" in args
    assert "--allowedTools" in args
    tools_idx = args.index("--allowedTools") + 1
    assert set(args[tools_idx].split(",")) == {"WebSearch", "WebFetch", "Bash"}
    assert "--output-format" in args
    assert "json" in args
    assert result["returncode"] == 0
    assert result["stdout"] == '{"result": "ok"}'


def test_invoke_headless_claude_nonzero_exit_reported():
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        result = _invoke_headless_claude("do the sweep")
    assert result["returncode"] == 1
    assert result["stderr"] == "boom"


def _write_seed_config():
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.json", "w") as f:
        f.write(textwrap.dedent("""\
            {
              "segments": [{"name": "solo indie devs", "competitors": ["Superpowers"]}],
              "decide_panel": "claude,codex",
              "research_issue_labels": ["competitive-research"],
              "proposal_issue_labels": ["feature-proposal"]
            }
        """))


def test_cmd_pm_sweep_dry_run_does_not_invoke_subprocess(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        summary = cmd_pm_sweep(dry_run=True)
    mock_run.assert_not_called()
    captured = capsys.readouterr()
    assert "solo indie devs" in captured.out
    assert summary is None


def test_cmd_pm_sweep_real_run_parses_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    fake_stdout = (
        '{"result": "'
        '{\\"research_tickets\\": 2, \\"proposals\\": 1, \\"segments_updated\\": 1}"}'
    )
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_stdout, stderr="")
        summary = cmd_pm_sweep(dry_run=False)
    assert summary["research_tickets"] == 2
    assert summary["proposals"] == 1
    captured = capsys.readouterr()
    assert "research_tickets" in captured.out


def test_cmd_pm_sweep_real_run_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="network error")
        with pytest.raises(SystemExit):
            cmd_pm_sweep(dry_run=False)


@pytest.mark.parametrize("stdout", ["not json", '{"result": "not json"}', '{"wrong": "key"}'])
def test_cmd_pm_sweep_malformed_output_exits_nonzero(tmp_path, monkeypatch, capsys, stdout):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        with pytest.raises(SystemExit) as exc_info:
            cmd_pm_sweep(dry_run=False)
    assert exc_info.value.code == 1
    assert "could not parse summary JSON" in capsys.readouterr().err
