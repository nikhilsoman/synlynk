from synlynk.examples import greet


def test_greet_returns_a_friendly_message():
    assert greet("Ada") == "Hello, Ada!"


def _general_scenario_active_items(items):
    """Return items with a truthy active flag — stand-in general scenario for QA calibration."""
    return [item for item in items if item.get("active")]


def test_write_3_test_cases_for_a_general_scenario_happy_path():
    items = [
        {"id": 1, "active": True},
        {"id": 2, "active": False},
        {"id": 3, "active": True},
    ]
    assert _general_scenario_active_items(items) == [
        {"id": 1, "active": True},
        {"id": 3, "active": True},
    ]


def test_write_3_test_cases_for_a_general_scenario_empty_input():
    assert _general_scenario_active_items([]) == []


def test_write_3_test_cases_for_a_general_scenario_missing_active_key():
    assert _general_scenario_active_items([{"id": 1}, {"id": 2, "active": False}]) == []
