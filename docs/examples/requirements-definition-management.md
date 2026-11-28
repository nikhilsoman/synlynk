# Requirements Definition and Management: `make_slug`

This small example shows how a function can have explicit requirements, acceptance
tests, and a traceability table that keeps the requirements connected to the code.

## Defined requirements

| ID | Requirement | Acceptance test |
| --- | --- | --- |
| REQ-001 | Trim leading and trailing whitespace, convert text to lowercase, and replace runs of whitespace with one hyphen. | `test_make_slug_manages_defined_normalization_requirements` |
| REQ-002 | Reject input that contains no non-whitespace characters with a clear `ValueError`. | `test_make_slug_rejects_an_empty_requirement_input` |

## Implementation

```python
def make_slug(text: str) -> str:
    normalized = "-".join(text.strip().lower().split())
    if not normalized:
        raise ValueError("text must contain at least one non-whitespace character")
    return normalized
```

The requirements are managed by keeping each requirement mapped to an executable
acceptance test. A change is complete only when the relevant tests pass:

```bash
pytest -q tests/test_examples.py
```
