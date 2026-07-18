import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_naics_codes_have_label_and_parent():
    from synlynk.taxonomy_standards import NAICS_CODES

    assert len(NAICS_CODES) >= 15
    for code, entry in NAICS_CODES.items():
        assert isinstance(code, str)
        assert "label" in entry
        assert "parent" in entry  # may be None for top-level codes


def test_apqc_codes_have_label_and_parent():
    from synlynk.taxonomy_standards import APQC_CODES

    assert len(APQC_CODES) >= 15
    for code, entry in APQC_CODES.items():
        assert "label" in entry
        assert "parent" in entry


def test_sfia_codes_have_label_and_parent():
    from synlynk.taxonomy_standards import SFIA_CODES

    assert len(SFIA_CODES) >= 15
    for code, entry in SFIA_CODES.items():
        assert "label" in entry
        assert "parent" in entry
    # Calibration-relevant skills referenced elsewhere in this plan must exist
    assert "PROG" in SFIA_CODES
    assert "TEST" in SFIA_CODES
    assert "REQM" in SFIA_CODES


def test_taxonomy_label_looks_up_known_code():
    from synlynk.taxonomy_standards import _taxonomy_label

    assert _taxonomy_label("sfia", "PROG") != "PROG"  # returns human label, not raw code


def test_taxonomy_label_falls_back_to_raw_code_for_unknown():
    from synlynk.taxonomy_standards import _taxonomy_label

    assert _taxonomy_label("sfia", "NOT_A_REAL_CODE") == "NOT_A_REAL_CODE"


def test_taxonomy_label_rejects_unknown_axis():
    from synlynk.taxonomy_standards import _taxonomy_label
    import pytest

    with pytest.raises(ValueError):
        _taxonomy_label("not_an_axis", "PROG")


def test_taxonomy_axis_registry_contains_expected_tables():
    from synlynk.taxonomy_standards import _AXIS_TABLES

    assert set(_AXIS_TABLES) == {"naics", "apqc", "sfia"}
