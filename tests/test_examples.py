import pytest

from synlynk.examples import (
    CLAMP_REQUIREMENTS,
    active_items,
    clamp,
    define_requirements,
    greet,
    set_requirement_status,
    uncovered_requirement_ids,
)


def test_greet_returns_a_friendly_message():
    assert greet("Ada") == "Hello, Ada!"


def test_write_3_test_cases_for_a_general_scenario_happy_path():
    items = [
        {"id": 1, "active": True},
        {"id": 2, "active": False},
        {"id": 3, "active": True},
    ]
    assert active_items(items) == [
        {"id": 1, "active": True},
        {"id": 3, "active": True},
    ]


def test_write_3_test_cases_for_a_general_scenario_empty_input():
    assert active_items([]) == []


def test_write_3_test_cases_for_a_general_scenario_missing_active_key():
    assert active_items([{"id": 1}, {"id": 2, "active": False}]) == []


def test_active_items_handles_mixed_truthy_and_falsy_flag_values():
    items = [
        {"id": 1, "active": 1},
        {"id": 2, "active": 0},
        {"id": 3, "active": "yes"},
        {"id": 4, "active": ""},
        {"id": 5, "active": None},
    ]

    assert active_items(items) == [
        {"id": 1, "active": 1},
        {"id": 3, "active": "yes"},
    ]


def test_active_items_preserves_order_and_duplicate_ids_with_extra_metadata():
    """Filtering should not deduplicate or reshape otherwise valid records."""
    first = {"id": 7, "active": True, "label": "first"}
    second = {"id": 7, "active": True, "label": "second"}
    inactive = {"id": 8, "active": False, "label": "hidden"}

    result = active_items([first, inactive, second])

    assert result == [first, second]
    assert result[0] is first
    assert result[1] is second


def test_active_items_returns_a_single_active_item_unchanged():
    item = {"id": 42, "active": True}

    assert active_items([item]) == [item]


def test_active_items_returns_no_items_when_every_item_is_inactive():
    items = [
        {"id": 1, "active": False},
        {"id": 2, "active": None},
        {"id": 3, "active": 0},
    ]

    assert active_items(items) == []


def test_active_items_preserves_metadata_on_selected_items():
    item = {"id": 9, "active": True, "name": "visible", "tags": ["basic"]}

    result = active_items([item, {"id": 10, "active": False, "name": "hidden"}])

    assert result == [item]
    assert result[0]["name"] == "visible"
    assert result[0]["tags"] == ["basic"]


def test_active_items_returns_all_items_when_every_item_is_active():
    items = [{"id": 1, "active": True}, {"id": 2, "active": True}]

    assert active_items(items) == items


def test_active_items_returns_only_the_active_item_from_a_two_item_list():
    active = {"id": 1, "active": True}
    inactive = {"id": 2, "active": False}

    assert active_items([active, inactive]) == [active]


def test_active_items_keeps_the_input_order_of_active_items():
    items = [
        {"id": 3, "active": True},
        {"id": 1, "active": True},
        {"id": 2, "active": False},
    ]

    assert active_items(items) == [items[0], items[1]]


def test_greet_handles_a_name_with_spaces():
    assert greet("Ada Lovelace") == "Hello, Ada Lovelace!"


def test_greet_handles_an_empty_name():
    assert greet("") == "Hello, !"


def test_greet_preserves_punctuation_in_a_name():
    assert greet("O'Connor") == "Hello, O'Connor!"


def test_define_requirements_builds_an_open_catalog():
    catalog = define_requirements(CLAMP_REQUIREMENTS)

    assert list(catalog) == [
        "REQ-CLAMP-01",
        "REQ-CLAMP-02",
        "REQ-CLAMP-03",
        "REQ-CLAMP-04",
    ]
    assert catalog["REQ-CLAMP-01"].status == "open"
    assert "unchanged" in catalog["REQ-CLAMP-01"].statement


def test_define_requirements_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate requirement id"):
        define_requirements(
            [
                ("REQ-1", "first"),
                ("REQ-1", "again"),
            ]
        )


def test_set_requirement_status_marks_a_requirement_satisfied():
    catalog = define_requirements(CLAMP_REQUIREMENTS)
    updated = set_requirement_status(catalog, "REQ-CLAMP-01", "satisfied")

    assert updated["REQ-CLAMP-01"].status == "satisfied"
    assert catalog["REQ-CLAMP-01"].status == "open"


def test_set_requirement_status_rejects_unknown_id_and_status():
    catalog = define_requirements(CLAMP_REQUIREMENTS)

    with pytest.raises(KeyError):
        set_requirement_status(catalog, "REQ-MISSING", "satisfied")
    with pytest.raises(ValueError, match="unknown requirement status"):
        set_requirement_status(catalog, "REQ-CLAMP-01", "shipped")


def test_uncovered_requirement_ids_reports_open_untraced_requirements():
    catalog = define_requirements(CLAMP_REQUIREMENTS)
    catalog = set_requirement_status(catalog, "REQ-CLAMP-04", "deferred")

    missing = uncovered_requirement_ids(
        catalog,
        traced_ids=["REQ-CLAMP-01", "REQ-CLAMP-02"],
    )

    assert missing == ["REQ-CLAMP-03"]


def test_clamp_returns_value_inside_range():
    """REQ-CLAMP-01"""
    assert clamp(5, 0, 10) == 5
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10


def test_clamp_returns_lo_when_value_is_below_range():
    """REQ-CLAMP-02"""
    assert clamp(-3, 0, 10) == 0


def test_clamp_returns_hi_when_value_is_above_range():
    """REQ-CLAMP-03"""
    assert clamp(15, 0, 10) == 10


def test_clamp_raises_when_bounds_are_inverted():
    """REQ-CLAMP-04"""
    with pytest.raises(ValueError, match="lo must be <= hi"):
        clamp(1, 10, 0)


def test_clamp_requirements_are_fully_traced_by_this_suite():
    catalog = define_requirements(CLAMP_REQUIREMENTS)
    traced = [
        "REQ-CLAMP-01",
        "REQ-CLAMP-02",
        "REQ-CLAMP-03",
        "REQ-CLAMP-04",
    ]

    assert uncovered_requirement_ids(catalog, traced) == []
    for req_id in traced:
        catalog = set_requirement_status(catalog, req_id, "satisfied")
    assert all(req.status == "satisfied" for req in catalog.values())
