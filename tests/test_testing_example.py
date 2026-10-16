"""A minimal example of testing a small Python function with pytest."""


def add_tax(price: float, rate: float) -> float:
    """Return a price with tax applied."""
    return price * (1 + rate)


def test_add_tax():
    assert add_tax(10.0, 0.1) == 11.0
