from synlynk.examples import greet


def test_greet_returns_a_friendly_message():
    assert greet("Ada") == "Hello, Ada!"
