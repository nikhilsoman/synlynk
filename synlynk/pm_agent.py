"""PM competitive-intelligence sweep: config loading, prompt composition,
and the headless-Claude invocation wrapper for `synlynk pm sweep`.

See docs/superpowers/specs/2026-08-24-pm-competitive-intelligence-sweep-design.md.
"""
import json
import subprocess

import yaml

from synlynk.team import HARNESS_CAPABILITY_BASELINES

CONFIG_PATH = "docs/strategy/competitive-config.yaml"
DOC_PATH = "docs/strategy/competitive-landscape.md"


def _load_config(config_path: str = CONFIG_PATH) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def _resolve_decide_panel(decide_panel_config: str) -> list:
    if decide_panel_config == "auto":
        return sorted(HARNESS_CAPABILITY_BASELINES.keys())
    return [name.strip() for name in decide_panel_config.split(",") if name.strip()]


def _compose_prompt(config: dict) -> str:
    panel = _resolve_decide_panel(config["decide_panel"])
    segment_lines = []
    for segment in config["segments"]:
        competitors = ", ".join(segment["competitors"]) or "(none known yet)"
        segment_lines.append(f"- {segment['name']}: {competitors}")
    segments_block = "\n".join(segment_lines)
    research_labels = ",".join(config["research_issue_labels"])
    proposal_labels = ",".join(config["proposal_issue_labels"])

    return (
        "You are running synlynk's weekly PM competitive-intelligence sweep.\n\n"
        "User segments and known competitors:\n"
        f"{segments_block}\n\n"
        "For each segment:\n"
        "1. Research the web for products/companies serving this segment that "
        "you don't already know about, and re-check known competitors for "
        "capability or positioning changes.\n"
        f"2. Update {DOC_PATH} in place: refresh existing rows, add new "
        "segments/competitors as new sections (never remove existing entries), "
        "bump the 'Last swept' date.\n"
        "3. For each genuine capability or marketing gap candidate you find, "
        f"open a GitHub research issue (`gh issue create --label {research_labels}`) "
        "describing what the competitor does, why it's a gap, and linking to the "
        f"relevant row in {DOC_PATH}.\n"
        "4. For each research candidate, run: "
        '`synlynk decide "<candidate>: should synlynk build this? Answer from '
        "your own harness-maintainer POV — implementation cost, maintenance "
        f'burden, fit with your role\'s workflow." --panel {",".join(panel)} --record`\n'
        "5. Judge fit against synlynk's stated vision and goals using the decide "
        "round's opinions plus your own research. For candidates you judge a "
        "strong fit, open a second issue titled `[Proposal] <candidate>` "
        f"(`gh issue create --label {proposal_labels}`), summarizing the research "
        "ticket, the decide-round opinions, and why it's a strong fit.\n\n"
        "Do not open a proposal issue for every research candidate — only ones "
        "with a strong fit. When finished, print a one-line JSON summary to "
        "stdout: "
        '{"research_tickets": <int>, "proposals": <int>, "segments_updated": <int>}.'
    )
