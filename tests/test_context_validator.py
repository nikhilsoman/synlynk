import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.context_validator import validate_context_interactive, render_chips_summary


def test_validate_context_no_input_json_mode():
    data = {
        "domain": {"industry": "Healthcare AI"},
        "physical": {"languages": ["Python"], "frameworks": ["FastAPI"]},
    }
    validated = validate_context_interactive(data, no_input=True)
    assert validated == data


def test_render_chips_summary():
    data = {
        "domain": {"industry": "Healthcare AI"},
        "physical": {"languages": ["Python"], "frameworks": ["FastAPI"]},
    }
    summary = render_chips_summary(data)
    assert "[Domain: Healthcare AI]" in summary
    assert "[Language: Python]" in summary
    assert "[Framework: FastAPI]" in summary
