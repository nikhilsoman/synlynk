import os
import textwrap

from synlynk.pm_agent import _compose_prompt, _load_config, _resolve_decide_panel
from synlynk.team import HARNESS_CAPABILITY_BASELINES


def test_load_config_reads_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.yaml", "w") as f:
        f.write(textwrap.dedent("""\
            segments:
              - name: "solo indie devs"
                competitors: ["Superpowers", "GStack"]
            decide_panel: auto
            research_issue_labels: ["competitive-research", "architect"]
            proposal_issue_labels: ["feature-proposal", "needs-user-review"]
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
