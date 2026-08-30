import json
import pytest
from synlynk.costs import _extract_agy_structured, extract_tokens


def test_extract_agy_structured_captures_cache_read_tokens():
    output = json.dumps({
        "conversation_id": "c3203df0",
        "status": "SUCCESS",
        "response": "parity achieved",
        "duration_seconds": 15.2,
        "num_turns": 2,
        "usage": {
            "input_tokens": 1024,
            "output_tokens": 512,
            "thinking_tokens": 128,
            "cache_read_tokens": 32533,
            "total_tokens": 34201,
        },
    })
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 1024
    assert result.output_tokens == 512 + 128
    assert result.cache_read_tokens == 32533
    assert result.basis == "structured_output"


def test_extract_tokens_captures_agy_cache_read_tokens():
    output = json.dumps({
        "conversation_id": "c3203df0",
        "status": "SUCCESS",
        "response": "parity achieved",
        "duration_seconds": 15.2,
        "num_turns": 2,
        "usage": {
            "input_tokens": 1024,
            "output_tokens": 512,
            "thinking_tokens": 128,
            "cache_read_tokens": 32533,
            "total_tokens": 34201,
        },
    })
    counts = extract_tokens(output, agent="agy")
    assert counts.input_tokens == 1024
    assert counts.output_tokens == 640
    assert counts.cache_read_tokens == 32533
    in_tok, out_tok = counts
    assert in_tok == 1024
    assert out_tok == 640

