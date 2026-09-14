import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.discovery_semantic import enrich_with_semantic_overlay


def test_enrich_with_semantic_overlay_timeout_graceful_fallback():
    static_data = {
        "domain": {"industry": "Generic Software"},
        "physical": {"languages": ["Python"]},
    }
    result = enrich_with_semantic_overlay(static_data, timeout_s=0.01)
    assert result["domain"]["industry"] == "Generic Software"
    assert result["provenance"]["semantic_enriched"] is False
