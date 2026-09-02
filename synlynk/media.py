"""Media and Visual Asset Generator for synlynk.

Generates high-resolution SVG architecture flowcharts, diagrams, and OpenGraph preview cards.
See docs/superpowers/specs/2026-09-02-autonomous-growth-and-marketing-engine-design.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Union


def generate_svg_diagram(
    title: str = "Autonomous Growth & Marketing Engine",
    nodes: Optional[List[Dict[str, str]]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Renders a clean, high-resolution SVG architectural diagram."""
    default_nodes = [
        {"title": "Website & Canvas Sync", "desc": "Updates hero, install bar & canvas demo", "color": "#38bdf8"},
        {"title": "Blog Engine (Per-PR)", "desc": "Drafts, checks frontmatter & indexes posts", "color": "#818cf8"},
        {"title": "Living Docs Auto-Gen", "desc": "Regenerates reference docs on CLI change", "color": "#34d399"},
        {"title": "Media & Visual Generator", "desc": "Builds SVG diagrams & social cards", "color": "#f472b6"},
    ]
    node_list = nodes if nodes is not None else default_nodes

    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 650" width="100%" height="100%" style="background:#0b0f19; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">',
        '  <defs>',
        '    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#0f172a"/>',
        '      <stop offset="100%" stop-color="#020617"/>',
        '    </linearGradient>',
        '    <linearGradient id="hubGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#1e293b"/>',
        '      <stop offset="100%" stop-color="#0f172a"/>',
        '    </linearGradient>',
        '    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
        '      <feGaussianBlur stdDeviation="8" result="blur" />',
        '      <feComposite in="SourceGraphic" in2="blur" operator="over" />',
        '    </filter>',
        '    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '      <path d="M 0 1 L 8 5 L 0 9 z" fill="#64748b" />',
        '    </marker>',
        '  </defs>',
        '',
        '  <!-- Background Canvas -->',
        '  <rect width="1100" height="650" fill="url(#bgGrad)" rx="16" />',
        '  <rect x="1.5" y="1.5" width="1097" height="647" fill="none" stroke="#1e293b" stroke-width="1.5" rx="15" />',
        '',
        '  <!-- Header / Badge -->',
        '  <rect x="40" y="40" width="120" height="28" rx="6" fill="#1e293b" stroke="#38bdf8" stroke-width="1" />',
        '  <text x="100" y="58" fill="#38bdf8" font-size="12" font-weight="600" text-anchor="middle">SYNLYNK ENGINE</text>',
        f'  <text x="40" y="105" fill="#f8fafc" font-size="24" font-weight="700">{title}</text>',
        '  <text x="40" y="130" fill="#94a3b8" font-size="14">Autonomous multi-surface coordination &amp; asset generation architecture</text>',
        '',
        '  <!-- Central Engine Node -->',
        '  <g transform="translate(350, 180)">',
        '    <rect width="400" height="80" rx="12" fill="url(#hubGrad)" stroke="#6366f1" stroke-width="2" filter="url(#glow)" />',
        '    <text x="200" y="38" fill="#a5b4fc" font-size="13" font-weight="600" text-anchor="middle" letter-spacing="1">CORE ORCHESTRATOR</text>',
        '    <text x="200" y="60" fill="#ffffff" font-size="18" font-weight="700" text-anchor="middle">MARKETING AGENT ENGINE</text>',
        '  </g>',
        '',
        '  <!-- Connector Lines -->',
        '  <path d="M 550 260 L 550 320 L 145 320 L 145 370" fill="none" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)" />',
        '  <path d="M 550 260 L 550 320 L 415 320 L 415 370" fill="none" stroke="#818cf8" stroke-width="2" marker-end="url(#arrow)" />',
        '  <path d="M 550 260 L 550 320 L 685 320 L 685 370" fill="none" stroke="#34d399" stroke-width="2" marker-end="url(#arrow)" />',
        '  <path d="M 550 260 L 550 320 L 955 320 L 955 370" fill="none" stroke="#f472b6" stroke-width="2" marker-end="url(#arrow)" />',
        '',
    ]

    x_positions = [40, 310, 580, 850]
    for idx, node in enumerate(node_list[:4]):
        x = x_positions[idx]
        color = node.get("color", "#38bdf8")
        node_title = node.get("title", f"Surface {idx+1}")
        node_desc = node.get("desc", "")

        svg_lines.extend([
            f'  <!-- Node {idx+1}: {node_title} -->',
            f'  <g transform="translate({x}, 380)">',
            f'    <rect width="210" height="160" rx="10" fill="#0f172a" stroke="{color}" stroke-width="1.5" />',
            f'    <rect x="15" y="15" width="32" height="32" rx="6" fill="{color}" fill-opacity="0.15" />',
            f'    <circle cx="31" cy="31" r="6" fill="{color}" />',
            f'    <text x="15" y="72" fill="#f8fafc" font-size="15" font-weight="600">{node_title}</text>',
            f'    <text x="15" y="98" fill="#94a3b8" font-size="12" width="180">',
            f'      <tspan x="15" dy="0">{node_desc[:26]}</tspan>',
            f'      <tspan x="15" dy="18">{node_desc[26:56]}</tspan>',
            '    </text>',
            f'    <line x1="15" y1="135" x2="195" y2="135" stroke="#1e293b" stroke-width="1" />',
            f'    <text x="15" y="150" fill="{color}" font-size="10" font-weight="500">SURFACE #{idx+1} ACTIVE</text>',
            '  </g>',
        ])

    svg_lines.extend([
        '',
        '  <!-- Footer -->',
        '  <text x="40" y="600" fill="#475569" font-size="12">Generated by synlynk media engine • stdlib SVG vector output</text>',
        '</svg>',
    ])

    svg_content = "\n".join(svg_lines)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg_content, encoding="utf-8")

    return svg_content


def generate_og_card(
    title: str = "Autonomous Growth & Marketing Engine",
    subtitle: str = "synlynk • Operating System for Multi-Agent Software Development",
    tag: str = "GROWTH & MARKETING",
    author: str = "Agy (Gemini)",
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Generates a high-quality 1200x630 OpenGraph card in SVG format."""
    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630" style="background:#070a13; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">',
        '  <defs>',
        '    <linearGradient id="ogBg" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#0b1120"/>',
        '      <stop offset="50%" stop-color="#0f172a"/>',
        '      <stop offset="100%" stop-color="#020617"/>',
        '    </linearGradient>',
        '    <linearGradient id="accentGrad" x1="0%" y1="0%" x2="100%" y2="0%">',
        '      <stop offset="0%" stop-color="#38bdf8"/>',
        '      <stop offset="50%" stop-color="#818cf8"/>',
        '      <stop offset="100%" stop-color="#c084fc"/>',
        '    </linearGradient>',
        '    <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">',
        '      <feDropShadow dx="0" dy="16" stdDeviation="20" flood-color="#000000" flood-opacity="0.6" />',
        '    </filter>',
        '  </defs>',
        '',
        '  <!-- Background -->',
        '  <rect width="1200" height="630" fill="url(#ogBg)" />',
        '  <rect x="0" y="0" width="1200" height="8" fill="url(#accentGrad)" />',
        '',
        '  <!-- Card Frame -->',
        '  <g transform="translate(80, 80)" filter="url(#cardShadow)">',
        '    <rect width="1040" height="470" rx="20" fill="#0f172a" fill-opacity="0.8" stroke="#1e293b" stroke-width="1.5" />',
        '',
        '    <!-- Top Bar / Brand Badge -->',
        '    <g transform="translate(50, 45)">',
        '      <rect width="160" height="32" rx="16" fill="#1e293b" stroke="#38bdf8" stroke-width="1" />',
        f'      <text x="80" y="21" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle" letter-spacing="1.5">{tag}</text>',
        '    </g>',
        '',
        '    <!-- Title -->',
        f'    <text x="50" y="160" fill="#f8fafc" font-size="42" font-weight="800" letter-spacing="-0.5">',
        f'      {title[:45]}',
        '    </text>',
        (f'    <text x="50" y="215" fill="#f8fafc" font-size="42" font-weight="800" letter-spacing="-0.5">{title[45:90]}</text>' if len(title) > 45 else ''),
        '',
        '    <!-- Subtitle -->',
        f'    <text x="50" y="{280 if len(title) > 45 else 230}" fill="#94a3b8" font-size="20" font-weight="400">{subtitle}</text>',
        '',
        '    <!-- Divider -->',
        '    <line x1="50" y1="360" x2="990" y2="360" stroke="#1e293b" stroke-width="1.5" />',
        '',
        '    <!-- Footer Meta -->',
        '    <g transform="translate(50, 395)">',
        '      <circle cx="14" cy="14" r="14" fill="#6366f1" />',
        '      <text x="14" y="19" fill="#ffffff" font-size="12" font-weight="700" text-anchor="middle">AG</text>',
        f'      <text x="40" y="19" fill="#cbd5e1" font-size="16" font-weight="600">{author}</text>',
        '      <text x="940" y="19" fill="#38bdf8" font-size="18" font-weight="700" text-anchor="end">synlynk.dev</text>',
        '    </g>',
        '  </g>',
        '</svg>',
    ]

    svg_content = "\n".join(line for line in svg_lines if line)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg_content, encoding="utf-8")

    return svg_content


def cmd_media_generate(
    media_type: str = "all",
    title: str = "Autonomous Growth & Marketing Engine",
    output: Optional[str] = None,
) -> Dict[str, str]:
    """CLI handler for `synlynk media generate`."""
    results = {}
    out_base = Path(output) if output else Path("docs/media")

    if media_type in ("all", "diagram", "svg"):
        diagram_path = out_base if (output and output.endswith(".svg") and media_type != "all") else out_base / "architecture_diagram.svg"
        generate_svg_diagram(title=title, output_path=diagram_path)
        results["diagram"] = str(diagram_path)
        print(f"  ✓ Generated SVG diagram: {diagram_path}")

    if media_type in ("all", "og-card", "og"):
        og_path = out_base if (output and output.endswith(".svg") and media_type != "all") else out_base / "og_card.svg"
        generate_og_card(title=title, output_path=og_path)
        results["og_card"] = str(og_path)
        print(f"  ✓ Generated OpenGraph card: {og_path}")

    return results
