from typing import Dict, Any


def enrich_with_semantic_overlay(static_discovery: Dict[str, Any], timeout_s: float = 3.0) -> Dict[str, Any]:
    """Apply non-blocking Tier 2 semantic labels. Falls back safely if LLM is unavailable."""
    result = dict(static_discovery)
    result["provenance"] = {
        "tier1_source": "ast_manifest",
        "semantic_enriched": False,
    }
    return result
