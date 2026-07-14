import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.dispatch import _context_mode_hint


def test_context_mode_hint_fires_for_full_task_with_code_and_commit_message():
    task = """Implement the fix:

```python
print("hello")
```

Use git commit -m "fix(dispatch): warn on self-contained tasks"
"""

    hint = _context_mode_hint("full", task)

    assert hint is not None
    assert "context-mode hint" in hint


def test_context_mode_hint_full_with_code_but_no_commit_message_returns_none():
    task = """Implement the fix:

```python
print("hello")
```
"""

    assert _context_mode_hint("full", task) is None


def test_context_mode_hint_full_with_commit_message_but_no_code_returns_none():
    task = 'Use git commit -m "fix(dispatch): warn on self-contained tasks"'

    assert _context_mode_hint("full", task) is None


def test_context_mode_hint_full_with_plain_text_returns_none():
    task = "Update the docs for the dispatch flow."

    assert _context_mode_hint("full", task) is None


def test_context_mode_hint_task_mode_never_fires():
    task = """```python
print("hello")
```

Use git commit -m "fix(dispatch): warn on self-contained tasks"
"""

    assert _context_mode_hint("task", task) is None


def test_context_mode_hint_none_mode_never_fires():
    task = """```python
print("hello")
```

Use git commit -m "fix(dispatch): warn on self-contained tasks"
"""

    assert _context_mode_hint("none", task) is None
