"""Regenerates docs/reference/commands.md and README.md's command table
from synlynk.taxonomy.COMMAND_TAXONOMY. Run after any taxonomy change:

    python3 scripts/generate_command_docs.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from synlynk.taxonomy import COMMAND_TAXONOMY, entries_for_tier

TIER_LABELS = {
    0: "Tier 0 — First-Time Setup",
    1: "Tier 1 — Goal",
    2: "Tier 2 — Execute",
    3: "Tier 3 — Team / Enterprise",
    "latent": "Latent — Autopilot & Hooks Only",
}

README_START = "<!-- commands:start -->"
README_END = "<!-- commands:end -->"


def render_reference_doc() -> str:
    lines = ["# Command Reference", "",
             "Generated from `synlynk/taxonomy.py`. Do not edit by hand — run "
             "`python3 scripts/generate_command_docs.py`.", ""]
    gateway = [e for e in COMMAND_TAXONOMY if e["orientation_gateway"]]
    lines.append("## Orientation gateway (always available)")
    lines.append("")
    for e in gateway:
        lines.append(f"- `{e['command']}` — {e['governs_stage']}")
    lines.append("")
    for tier in (0, 1, 2, 3, "latent"):
        entries = [e for e in entries_for_tier(tier) if not e["orientation_gateway"]]
        if not entries:
            continue
        lines.append(f"## {TIER_LABELS[tier]}")
        lines.append("")
        for e in entries:
            prom = f" ({e['prominence']})" if e["prominence"] else ""
            lines.append(f"- `{e['command']}`{prom} — {e['governs_stage']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_readme_section() -> str:
    lines = [README_START, ""]
    lines.append("**Start here:**")
    lines.append("")
    for e in COMMAND_TAXONOMY:
        if e["maturity_tier"] == 0 and (e["prominence"] == "primary" or e["orientation_gateway"]):
            lines.append(f"- `synlynk {e['command']}`")
    lines.append("")
    lines.append("Full command reference: [docs/reference/commands.md](docs/reference/commands.md)")
    lines.append("")
    lines.append(README_END)
    return "\n".join(lines)


def main():
    Path("docs/reference").mkdir(parents=True, exist_ok=True)
    Path("docs/reference/commands.md").write_text(render_reference_doc())

    readme_path = Path("README.md")
    readme = readme_path.read_text()
    section = render_readme_section()
    pattern = re.compile(
        re.escape(README_START) + r".*?" + re.escape(README_END), re.DOTALL
    )
    if pattern.search(readme):
        readme = pattern.sub(section, readme)
    else:
        raise RuntimeError(
            f"README.md is missing {README_START}/{README_END} markers — "
            "add them once around the command section, then re-run this script"
        )
    readme_path.write_text(readme)
    print("Regenerated docs/reference/commands.md and README.md command section.")


if __name__ == "__main__":
    main()
