# Minimal Requirements Definition and Management Example

This example shows how a small function can have clear, testable requirements and how each requirement stays connected to its implementation and verification.

## Change record

| Version | Change | Reason |
| --- | --- | --- |
| 1.0 | Initial requirements for `clamp_score` | Define expected behavior before implementation |

## Function

`clamp_score(value)` accepts a numeric score and returns it within the inclusive range 0 to 100.

## Requirements

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| R-1 | Values below 0 return 0. | `clamp_score(-3) == 0` |
| R-2 | Values above 100 return 100. | `clamp_score(120) == 100` |
| R-3 | Values from 0 through 100 are returned unchanged. | `clamp_score(0) == 0`, `clamp_score(42) == 42`, and `clamp_score(100) == 100` |
| R-4 | Non-numeric inputs are rejected with `TypeError`. | `clamp_score("42")` raises `TypeError` |

## Implementation

```python
def clamp_score(value: int | float) -> int | float:
    """Return a numeric score bounded by 0 and 100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be a number")
    return max(0, min(value, 100))
```

## Verification and traceability

```python
import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-3, 0), (0, 0), (42, 42), (100, 100), (120, 100)],
)
def test_clamp_score_bounds_and_preserves_in_range_values(value, expected):
    assert clamp_score(value) == expected


def test_clamp_score_rejects_text():
    with pytest.raises(TypeError):
        clamp_score("42")
```

| Requirement | Implementation | Verification |
| --- | --- | --- |
| R-1 | `max(0, ...)` | `test_clamp_score_bounds_and_preserves_in_range_values` (`-3`) |
| R-2 | `min(..., 100)` | `test_clamp_score_bounds_and_preserves_in_range_values` (`120`) |
| R-3 | `max` / `min` bounds | Same test (`0`, `42`, `100`) |
| R-4 | Type check at function entry | `test_clamp_score_rejects_text` |

When behavior changes, update the requirement and acceptance check first, then implementation and verification. Keep the ID stable when the intent is unchanged; add a new ID when introducing a distinct behavior. This keeps each requirement auditable through its test.
