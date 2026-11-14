"""Tests for _hc_editions_config in synlynk/doctor.py."""

from synlynk.doctor import HealthCheck, _hc_editions_config


def test_hc_editions_config_empty_or_defaults():
    """Empty config or absent keys evaluate to ok (defaults applied)."""
    res = _hc_editions_config({})
    assert isinstance(res, HealthCheck)
    assert res.name == "editions_config"
    assert res.status == "ok"


def test_hc_editions_config_valid_editions():
    """All valid editions in EDITION_ORDER evaluate to ok."""
    for ed in ("personal", "team", "enterprise"):
        res = _hc_editions_config({"edition": ed, "hosted": []})
        assert res.status == "ok"
        assert ed in res.message


def test_hc_editions_config_valid_hosted_keys():
    """Valid hosted keys evaluate to ok."""
    res = _hc_editions_config({"edition": "team", "hosted": ["hosted_relay"]})
    assert res.status == "ok"
    assert "1 hosted key(s)" in res.message


def test_hc_editions_config_unrecognized_edition():
    """Unrecognized edition emits a warn status."""
    res = _hc_editions_config({"edition": "pro"})
    assert res.status == "warn"
    assert "unrecognized edition 'pro'" in res.message
    assert "synlynk edition set" in res.fix


def test_hc_editions_config_unknown_hosted_key():
    """Unknown hosted key emits a warn status."""
    res = _hc_editions_config({"edition": "personal", "hosted": ["quantum_compiler"]})
    assert res.status == "warn"
    assert "unknown hosted capability key(s): quantum_compiler" in res.message


def test_hc_editions_config_hosted_not_a_list():
    """Hosted as non-list emits a warn status."""
    res = _hc_editions_config({"edition": "personal", "hosted": "hosted_relay"})
    assert res.status == "warn"
    assert "must be a list" in res.message
