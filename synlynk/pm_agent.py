"""PM competitive-intelligence sweep: config loading, prompt composition,
and the headless-Claude invocation wrapper for `synlynk pm sweep`.

See docs/superpowers/specs/2026-08-24-pm-competitive-intelligence-sweep-design.md.
"""
import json
import subprocess
import sys

import os
import re
from datetime import datetime, timezone
from synlynk.team import HARNESS_CAPABILITY_BASELINES

CONFIG_PATH = "docs/strategy/competitive-config.json"
DOC_PATH = "docs/strategy/competitive-landscape.md"
RADAR_OUTPUT_PATH = ".synlynk/radar.json"
PM_RADAR_DOC_PATH = "docs/pm/opportunities-radar.md"


def extract_radar_opportunities(
    landscape_path: str = DOC_PATH,
    config_path: str = CONFIG_PATH,
) -> dict:
    """Extract Ring 3 (Ecosystem & Competitor Frontier) opportunities from competitive intelligence."""
    segments = []
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                cfg = json.load(f)
                segments = cfg.get("segments", [])
        except Exception:
            pass

    landscape_text = ""
    if os.path.exists(landscape_path):
        try:
            with open(landscape_path) as f:
                landscape_text = f.read()
        except Exception:
            pass

    opportunities = []
    opp_index = 1

    if landscape_text:
        rows = re.findall(r"^\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|", landscape_text, flags=re.MULTILINE)
        for r in rows:
            col1, col2, col3, col4, col5 = [c.strip() for c in r]
            if col1.lower() in ("capability", "positioning vector", "---", "") or "---" in col1:
                continue
            opp_id = f"opp-r3-{opp_index:03d}"
            opp_index += 1
            opportunities.append({
                "id": opp_id,
                "title": col1,
                "synlynk_stance": col2.replace("<br>", " "),
                "competitor_analysis": f"Superpowers: {col3.replace('<br>', ' ')} | GStack: {col4.replace('<br>', ' ')}",
                "gap_assessment": col5,
                "ring": 3,
                "ring_label": "Ring 3 (Ecosystem & Competitor Frontier)",
                "fit_score": 0.90 if "ahead" in col5.lower() else 0.75,
                "status": "monitored",
            })

    if not opportunities:
        opportunities = [
            {
                "id": "opp-r3-001",
                "title": "State & Memory Durable Ledger",
                "synlynk_stance": "Durable human/AI readable project-docs ledger with dynamic snapshots",
                "competitor_analysis": "Superpowers / GStack local checklist files",
                "gap_assessment": "Synlynk differentiated with state.db single source of truth",
                "ring": 3,
                "ring_label": "Ring 3 (Ecosystem & Competitor Frontier)",
                "fit_score": 0.95,
                "status": "active",
            },
            {
                "id": "opp-r3-002",
                "title": "Universal Model & Gateway Provider Aggregators",
                "synlynk_stance": "BYOK OpenRouter / LiteLLM / Fal.ai / Zapier gateways",
                "competitor_analysis": "Locked to single vendor shells",
                "gap_assessment": "Ecosystem frontier capability",
                "ring": 3,
                "ring_label": "Ring 3 (Ecosystem & Competitor Frontier)",
                "fit_score": 0.88,
                "status": "active",
            },
        ]

    radar_payload = {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ring": "Ring 3 (Ecosystem & Competitor Frontier)",
        "total_opportunities": len(opportunities),
        "opportunities": opportunities,
    }
    return radar_payload


def save_radar_opportunities(
    radar_payload: dict,
    json_path: str = RADAR_OUTPUT_PATH,
    doc_path: str = PM_RADAR_DOC_PATH,
) -> tuple[str, str]:
    """Save radar opportunities to JSON and markdown report."""
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(radar_payload, f, indent=2)

    os.makedirs(os.path.dirname(doc_path) or ".", exist_ok=True)
    md_lines = [
        "# PM Opportunities Radar — Ring 3 (Ecosystem & Competitor Frontier)",
        "",
        f"> **Generated at:** {radar_payload.get('generated_at')}  ",
        f"> **Total Monitored Opportunities:** {radar_payload.get('total_opportunities')}",
        "",
        "## Opportunity Matrix",
        "",
        "| ID | Opportunity / Capability | Synlynk Stance | Competitor Stance | Fit Score | Status |",
        "| :--- | :--- | :--- | :--- | :---: | :---: |",
    ]
    for opp in radar_payload.get("opportunities", []):
        md_lines.append(
            f"| `{opp.get('id')}` | **{opp.get('title')}** | {opp.get('synlynk_stance')} | {opp.get('competitor_analysis')} | {opp.get('fit_score', 0):.2f} | `{opp.get('status')}` |"
        )
    md_lines.extend([
        "",
        "## Radar Plot Distribution",
        "- **Ring 1 (Core Workspace):** Internal engines & CLI control plane.",
        "- **Ring 2 (Team Mesh & Gateways):** P2P relay, identity roles, and MCP tools.",
        "- **Ring 3 (Ecosystem & Competitor Frontier):** Active frontier capabilities plotted above.",
        "",
    ])
    doc_content = "\n".join(md_lines)
    with open(doc_path, "w") as f:
        f.write(doc_content)

    return json_path, doc_path


def _load_config(config_path: str = CONFIG_PATH) -> dict:
    with open(config_path) as f:
        return json.load(f)


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


def _invoke_headless_claude(prompt: str) -> dict:
    cmd = [
        "claude",
        "-p", prompt,
        "--allowedTools", "WebSearch,WebFetch,Bash",
        "--output-format", "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def cmd_pm_sweep(dry_run: bool = False, radar: bool = False):
    config = _load_config()
    prompt = _compose_prompt(config)

    try:
        radar_data = extract_radar_opportunities()
        save_radar_opportunities(radar_data)
    except Exception:
        pass

    if dry_run:
        print(prompt)
        return None

    result = _invoke_headless_claude(prompt)
    if result["returncode"] != 0:
        print(
            f"pm sweep failed (exit {result['returncode']}): {result['stderr']}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        outer = json.loads(result["stdout"])
        summary = json.loads(outer["result"])
    except (json.JSONDecodeError, KeyError, TypeError):
        print("pm sweep: could not parse summary JSON from output", file=sys.stderr)
        sys.exit(1)

    print(
        f"pm sweep: {summary.get('research_tickets', 0)} research_tickets, "
        f"{summary.get('proposals', 0)} proposals, "
        f"{summary.get('segments_updated', 0)} segments_updated"
    )
    return summary
