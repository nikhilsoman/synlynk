"""Minimal testing example: tests for the small `greet` function."""

from synlynk.example_greet import greet


def test_greet_names_person():
    assert greet("Ada") == "Hello, Ada!"


def test_greet_strips_whitespace():
    assert greet("  Ada  ") == "Hello, Ada!"


def test_greet_empty_name():
    assert greet("") == "Hello, stranger!"
