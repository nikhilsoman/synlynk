"""Fleet discovery and asymmetric multi-harness routing for Greenfield (v0.28.5)."""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List

_CORE_FLEET = [
    {
        "harness": "claude",
        "provider": "Anthropic",
        "default_role": "PM / System Architect",
        "primary_domain": "Strategic requirements, nuance in tradeoffs, system architecture",
    },
    {
        "harness": "codex",
        "provider": "OpenAI",
        "default_role": "Dev / Refactoring",
        "primary_domain": "Surgical code generation, strict typing contracts, test implementations",
    },
    {
        "harness": "agy",
        "provider": "Google/Gemini",
        "default_role": "QA / High-Context Docs",
        "primary_domain": "Large-context documentation, cross-file verification, compliance auditing",
    },
    {
        "harness": "grok",
        "provider": "xAI",
        "default_role": "Fast Canvas / Infra",
        "primary_domain": "Ecosystem intelligence, infrastructure scripting, high-throughput execution",
    },
    {
        "harness": "local",
        "provider": "oMLX / Llama",
        "default_role": "Zero-Cost Local Worker",
        "primary_domain": "High-volume, low-risk local tasks, private offline execution",
    },
]


def probe_fleet() -> Dict[str, Any]:
    """Probe the developer environment for installed AI agent harnesses."""
    discovered: List[Dict[str, Any]] = []

    for item in _CORE_FLEET:
        name = item["harness"]
        # Check CLI binary or simulated env override
        bin_found = bool(shutil.which(name)) or os.environ.get(f"SYNLYNK_HARNESS_{name.upper()}_AVAILABLE") == "1"
        # agy might be invoked via python -m or antigravity
        if name == "agy" and not bin_found:
            bin_found = bool(shutil.which("antigravity")) or bool(shutil.which("gemini"))
        if name == "local" and not bin_found:
            bin_found = bool(shutil.which("mlx_lm")) or bool(shutil.which("ollama"))
            if not bin_found:
                try:
                    from synlynk.models import probe_local_runtimes

                    bin_found = bool(probe_local_runtimes(timeout=0.5))
                except Exception:
                    pass

        discovered.append({
            **item,
            "available": bin_found,
            "status": "Found ✓" if bin_found else "Not detected (optional)",
        })

    return {
        "harnesses": discovered,
        "available_count": sum(1 for h in discovered if h["available"]),
        "advantages": [
            "Domain Specialization: Claude (PM/Arch) vs Codex (Dev) vs Agy (QA/Docs) vs Grok (Infra).",
            "True Non-Author Governance: Dev (implementer) and QA (reviewer) execute on separate harnesses to eliminate self-confirmation bias.",
            "Dynamic Capability & Cost Routing: High-volume lint/docs route to cost-optimal Gemini/Local; complex architecture routes to frontier Claude/Codex.",
        ],
    }


def format_fleet_banner(probe_results: Dict[str, Any]) -> str:
    """Format the Stage 0 terminal banner introducing fleet capabilities."""
    lines = [
        "┌─────────────────────────────────────────────────────────────────────────────┐",
        "│ ⚡ Synlynk Fleet Discovery: Probing your development environment...          │",
        "│                                                                             │",
    ]
    for h in probe_results["harnesses"]:
        name_str = f"{h['harness'].capitalize()} CLI".ljust(12)
        prov_str = f"[{h['provider']}]".ljust(15)
        role_str = f"(Role: {h['default_role']})"
        status_symbol = "──► Found ✓ " if h["available"] else "──► Optional"
        lines.append(f"│   • {name_str} {prov_str} {status_symbol} {role_str}".ljust(78) + "│")

    lines.extend([
        "│                                                                             │",
        "│ Core Operating Invariant: Non-author review enforced across all pull reqs.  │",
        "└─────────────────────────────────────────────────────────────────────────────┘",
    ])
    return "\n".join(lines)
