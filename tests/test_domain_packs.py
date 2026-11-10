"""Tests for versioned in-repo domain packs and suggested tool baselines."""
import pytest
from synlynk.domain_packs import (
    load_domain_pack,
    list_domain_packs,
    get_suggested_tool_baseline,
)


def test_list_domain_packs_includes_canonical_domains():
    domains = list_domain_packs()
    assert "software" in domains
    assert "hitchcock" in domains
    assert "rxcc" in domains


def test_load_domain_pack_loads_valid_structure():
    pack = load_domain_pack("hitchcock")
    assert pack["domain_id"] == "hitchcock"
    assert pack["industry"] == "Film & Creative Media Production"
    assert "lifecycle_stages" in pack
    assert "suggested_tools" in pack
    assert len(pack["lifecycle_stages"]) > 0


def test_get_suggested_tool_baseline_enforces_requires_confirmation():
    # Binding Amendment 2 (dec-4a53a2ee): All suggestions must require human confirmation
    suggestions = get_suggested_tool_baseline(
        domain_id="hitchcock",
        archetype_id="creator",
        sfia_codes=["MUDI", "ANIM"],
    )
    assert len(suggestions) > 0
    for s in suggestions:
        assert s["requires_confirmation"] is True
        assert s["confirmed"] is False
        assert "tool_id" in s
        assert "source" in s
        assert "scope_paths" in s


def test_rxcc_domain_pack_includes_autonomy_cap():
    # Binding Amendment 3 (dec-4a53a2ee): rxcc has mandatory ceiling <= L2_GATED
    pack = load_domain_pack("rxcc")
    assert pack.get("max_autonomy_level") == "L2_GATED"
