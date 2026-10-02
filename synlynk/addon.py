from typing import Dict, List

ADDON_BUNDLES: Dict[str, Dict[str, str]] = {
    "bundle:quality": {
        "description": "Pre-vetted Ruff, ESLint, Biome, and Prettier configurations",
        "packages": "ruff prettier",
    },
    "bundle:security": {
        "description": "Gitleaks pre-commit hooks, Semgrep SAST scans, and Trivy audits",
        "packages": "gitleaks semgrep",
    },
    "bundle:observability": {
        "description": "Graphify AST knowledge graph and Mermaid rendering tools",
        "packages": "graphify mermaid-cli",
    },
}


def list_available_addons() -> List[str]:
    return sorted(list(ADDON_BUNDLES.keys()))


def install_addon_bundle(bundle_name: str) -> bool:
    if bundle_name not in ADDON_BUNDLES:
        raise ValueError(f"Unknown add-on bundle '{bundle_name}'. Available: {', '.join(list_available_addons())}")
    return True
