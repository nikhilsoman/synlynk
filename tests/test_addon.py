import pytest
from synlynk.addon import list_available_addons, install_addon_bundle


def test_list_addons_contains_core_bundles():
    addons = list_available_addons()
    assert "bundle:quality" in addons
    assert "bundle:security" in addons
    assert "bundle:observability" in addons


def test_install_unknown_addon_fails():
    with pytest.raises(ValueError, match="Unknown add-on bundle"):
        install_addon_bundle("bundle:nonexistent")
