"""Unit tests for Synlynk Editions classification engine and gating primitives."""

import pytest

from synlynk.editions import (
    CAPABILITIES,
    DEFAULT_HOSTED_BY_EDITION,
    EDITION_ORDER,
    Capability,
    check_edition,
    check_hosted,
)


def test_edition_order_hierarchy():
    """EDITION_ORDER must define ordinal progression: personal < team < enterprise."""
    assert EDITION_ORDER == ("personal", "team", "enterprise")


def test_registry_structural_invariants():
    """Verify registry shape integrity across all registered capabilities."""
    assert len(CAPABILITIES) > 0

    for name, cap in CAPABILITIES.items():
        assert isinstance(cap, Capability)
        assert cap.name == name
        assert cap.category in ("core", "opt_in", "hosted")

        if cap.category == "hosted":
            assert cap.hosted_key is not None, f"Hosted capability '{name}' must specify hosted_key"
            assert isinstance(cap.hosted_key, str) and len(cap.hosted_key) > 0
        else:
            assert cap.min_edition is None, f"Non-hosted capability '{name}' must have min_edition=None"
            assert cap.hosted_key is None, f"Non-hosted capability '{name}' must have hosted_key=None"


def test_check_edition_core_and_opt_in():
    """Core and Opt-in capabilities are never blocked by configured edition."""
    # Test across all possible editions (including empty/default)
    configs = [{}, {"edition": "personal"}, {"edition": "team"}, {"edition": "enterprise"}]

    for cfg in configs:
        ok_core, msg_core = check_edition(cfg, "capability_tracking")
        assert ok_core is True
        assert msg_core == ""

        ok_opt, msg_opt = check_edition(cfg, "github_app_auth")
        assert ok_opt is True
        assert msg_opt == ""


def test_check_edition_ordinal_comparison():
    """Check edition gates when capability specifies min_edition."""
    # Test a hypothetical capability with min_edition='team'
    test_cap = Capability(name="test_team_feature", category="core", min_edition="team")
    # Temporarily patch test_cap into CAPABILITIES
    CAPABILITIES["test_team_feature"] = test_cap
    try:
        # Default/Personal should be denied
        ok, msg = check_edition({}, "test_team_feature")
        assert ok is False
        assert "requires edition 'team' or higher" in msg

        ok, msg = check_edition({"edition": "personal"}, "test_team_feature")
        assert ok is False
        assert "requires edition 'team' or higher" in msg

        # Team and Enterprise should be allowed
        ok, msg = check_edition({"edition": "team"}, "test_team_feature")
        assert ok is True
        assert msg == ""

        ok, msg = check_edition({"edition": "enterprise"}, "test_team_feature")
        assert ok is True
        assert msg == ""
    finally:
        del CAPABILITIES["test_team_feature"]


def test_check_edition_unknown_capability_raises_key_error():
    """Unknown capability name must raise KeyError to fail closed."""
    with pytest.raises(KeyError, match="Unknown capability 'non_existent_cap'"):
        check_edition({"edition": "enterprise"}, "non_existent_cap")


def test_check_hosted_membership():
    """Hosted capabilities verify membership of hosted_key in config['hosted']."""
    # 'hosted_relay' has hosted_key='hosted_relay'
    assert check_hosted({}, "hosted_relay") == (False, "Hosted capability 'hosted_relay' is not enabled in config['hosted']")

    cfg_without = {"hosted": ["other_service"]}
    assert check_hosted(cfg_without, "hosted_relay") == (False, "Hosted capability 'hosted_relay' is not enabled in config['hosted']")

    cfg_with = {"hosted": ["hosted_relay", "other_service"]}
    assert check_hosted(cfg_with, "hosted_relay") == (True, "")


def test_check_hosted_non_hosted_category_raises_value_error():
    """Calling check_hosted on a core or opt-in capability is a programming error."""
    with pytest.raises(ValueError, match="is not a 'hosted' capability"):
        check_hosted({"hosted": ["capability_tracking"]}, "capability_tracking")


def test_check_hosted_unknown_capability_raises_key_error():
    """Unknown capability name in check_hosted must raise KeyError."""
    with pytest.raises(KeyError, match="Unknown capability 'unknown_hosted_feature'"):
        check_hosted({"hosted": []}, "unknown_hosted_feature")


def test_default_hosted_by_edition():
    """Verify default hosted key mappings for presets."""
    assert DEFAULT_HOSTED_BY_EDITION["personal"] == []
    assert "hosted_relay" in DEFAULT_HOSTED_BY_EDITION["team"]
    assert "hosted_relay" in DEFAULT_HOSTED_BY_EDITION["enterprise"]
    assert "sso" in DEFAULT_HOSTED_BY_EDITION["enterprise"]
    assert "audit_retention" in DEFAULT_HOSTED_BY_EDITION["enterprise"]
