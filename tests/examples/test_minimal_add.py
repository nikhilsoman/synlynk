"""Minimal pytest example for a small pure function."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from minimal_add import add


def test_add_sums_two_integers():
    assert add(2, 3) == 5


def test_add_handles_negatives_and_zero():
    assert add(-4, 4) == 0
    assert add(0, 0) == 0
