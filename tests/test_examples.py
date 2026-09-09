from synlynk.examples import active_items, greet


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
