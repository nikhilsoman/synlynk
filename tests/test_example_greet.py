"""Tests for the minimal greet example (TDD RED step)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from example_greet import greet


def test_greet_returns_greeting():
    assert greet("Ada") == "Hello, Ada!"


def test_greet_strips_whitespace():
    assert greet("  Ada  ") == "Hello, Ada!"


def test_greet_rejects_blank_name():
    import pytest

    with pytest.raises(ValueError, match="name must not be blank"):
        greet("   ")
