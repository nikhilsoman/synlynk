"""Industry and domain fleet templates for Synlynk onboarding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


FLEET_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "saas_web": {
        "name": "SaaS / Web App",
        "description": "Full-stack web application with QA, PM, and UX design agents",
        "roles": {
            "pm": {"harness": "claude", "tasks": ["specs", "milestones"]},
            "dev": {"harness": "codex", "tasks": ["frontend", "backend", "tests"]},
            "qa": {"harness": "codex", "tasks": ["reviews", "verification"]},
            "ux": {"harness": "agy", "tasks": ["canvas", "css", "templates"]},
        },
    },
    "fintech": {
        "name": "Fintech / Payments",
        "description": "Ledger consistency, compliance audit, and automated testbeds",
        "roles": {
            "pm": {"harness": "claude", "tasks": ["specs", "architecture"]},
            "ledger_dev": {"harness": "codex", "tasks": ["backend", "sql", "transactions"]},
            "compliance": {"harness": "claude", "tasks": ["security", "audit"]},
            "qa": {"harness": "codex", "tasks": ["fuzzing", "reviews"]},
        },
    },
    "healthcare": {
        "name": "Healthcare / MedTech",
        "description": "HIPAA compliance, strict provenance, and clinical data safety",
        "roles": {
            "pm": {"harness": "claude", "tasks": ["specs", "clinical_review"]},
            "dev": {"harness": "codex", "tasks": ["backend", "api"]},
            "auditor": {"harness": "claude", "tasks": ["hipaa", "audit_log"]},
            "qa": {"harness": "codex", "tasks": ["validation", "reviews"]},
        },
    },
    "deeptech_ai": {
        "name": "DeepTech / AI Infra",
        "description": "Model benchmarking, pipeline orchestration, and distributed infra",
        "roles": {
            "ml_eng": {"harness": "codex", "tasks": ["pipelines", "models"]},
            "infra": {"harness": "grok", "tasks": ["cuda", "distributed", "benchmarks"]},
            "qa": {"harness": "claude", "tasks": ["evals", "verification"]},
        },
    },
    "devops": {
        "name": "DevOps / Platform",
        "description": "Kubernetes, CI/CD pipelines, and SRE sentinels",
        "roles": {
            "cloud_arch": {"harness": "claude", "tasks": ["terraform", "architecture"]},
            "devops": {"harness": "grok", "tasks": ["k8s", "actions", "docker"]},
            "qa": {"harness": "codex", "tasks": ["security_scan", "reviews"]},
        },
    },
}


def list_fleet_templates() -> List[str]:
    """Return the names of the fleet templates available for onboarding."""

    return list(FLEET_TEMPLATES)


def apply_fleet_template(repo_dir: str, template_name: str) -> Dict[str, Any]:
    """Merge a named fleet template into ``repo_dir``'s Synlynk config."""

    template = FLEET_TEMPLATES.get(template_name)
    if template is None:
        raise ValueError(f"Unknown template: {template_name}")

    synlynk_dir = Path(repo_dir) / ".synlynk"
    synlynk_dir.mkdir(parents=True, exist_ok=True)
    config_path = synlynk_dir / "config.json"
    config: Dict[str, Any] = {}
    if config_path.is_file():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = loaded
        except (OSError, json.JSONDecodeError):
            config = {}

    config["fleet_template"] = template_name
    config["roles"] = template["roles"]
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "applied",
        "template": template_name,
        "roles": list(template["roles"]),
    }
