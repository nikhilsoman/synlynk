"""Tests for tokentrail modularity, adapters, and chunk deduplication."""

import ast
import json
import os
import tempfile
import pytest
from tokentrail.models import TokenUsage
from tokentrail.adapters.claude import ClaudeCodeAdapter
from tokentrail.adapters.agy import AgyAdapter
from tokentrail.adapters.codex import CodexAdapter
from tokentrail.adapters.gateway import GatewayAdapter
from tokentrail.extractor import extract_ledger


def test_modularity_zero_synlynk_imports():
    """Verify that packages/tokentrail/src contains ZERO imports of synlynk."""
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyfile:
                    tree = ast.parse(pyfile.read(), filename=fpath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert not alias.name.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {alias.name}"
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                assert not node.module.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {node.module}"


def test_claude_adapter_chunk_collapse():
    """Verify that multiple streaming progress chunks for the same message.id collapse to terminal usage."""
    adapter = ClaudeCodeAdapter()
    with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False) as tf:
        # Emit 3 events for msg-1 (intermediate progress chunks) and 1 event for msg-2
        chunk1 = {"type": "message", "message": {"id": "msg-1", "model": "claude-3-5-sonnet", "usage": {"input_tokens": 100, "output_tokens": 10}}}
        chunk2 = {"type": "message", "message": {"id": "msg-1", "model": "claude-3-5-sonnet", "usage": {"input_tokens": 100, "output_tokens": 50}}}
        chunk3 = {"type": "message", "message": {"id": "msg-1", "model": "claude-3-5-sonnet", "usage": {"input_tokens": 100, "output_tokens": 120, "cache_creation_input_tokens": 30}}}
        turn2 = {"type": "message", "message": {"id": "msg-2", "model": "claude-3-5-sonnet", "usage": {"input_tokens": 150, "output_tokens": 80}}}
        
        for item in [chunk1, chunk2, chunk3, turn2]:
            tf.write(json.dumps(item) + "\n")
        tf_name = tf.name

    try:
        ledger = adapter.parse(tf_name)
        assert len(ledger.turns) == 2
        
        total = ledger.total_usage
        # msg-1 collapsed usage: in=100, out=120, cache_w=30
        # msg-2 usage: in=150, out=80
        # total in = 250, total out = 200, cache_w = 30
        assert total.input_tokens == 250
        assert total.output_tokens == 200
        assert total.cache_write_tokens == 30
    finally:
        os.remove(tf_name)


def test_agy_adapter_parsing():
    """Verify Agy transcript step extraction."""
    adapter = AgyAdapter()
    with tempfile.NamedTemporaryFile("w+", suffix="transcript.jsonl", delete=False) as tf:
        step1 = {"step_index": 1, "model": "gemini-2.5-pro", "usage": {"prompt_tokens": 500, "completion_tokens": 100}}
        step2 = {"step_index": 2, "model": "gemini-2.5-pro", "usage": {"prompt_tokens": 600, "completion_tokens": 150}}
        for item in [step1, step2]:
            tf.write(json.dumps(item) + "\n")
        tf_name = tf.name

    try:
        ledger = adapter.parse(tf_name)
        assert len(ledger.turns) == 2
        total = ledger.total_usage
        assert total.input_tokens == 1100
        assert total.output_tokens == 250
    finally:
        os.remove(tf_name)


def test_codex_adapter_parsing():
    """Verify Codex transcript turn extraction."""
    adapter = CodexAdapter()
    with tempfile.NamedTemporaryFile("w+", suffix="codex-session.jsonl", delete=False) as tf:
        turn1 = {"turn_id": "t-1", "model": "o3-mini", "usage": {"prompt_tokens": 300, "completion_tokens": 70, "cached_tokens": 50}}
        turn2 = {"turn_id": "t-2", "model": "o3-mini", "usage": {"prompt_tokens": 400, "completion_tokens": 90}}
        for item in [turn1, turn2]:
            tf.write(json.dumps(item) + "\n")
        tf_name = tf.name

    try:
        ledger = adapter.parse(tf_name)
        assert len(ledger.turns) == 2
        total = ledger.total_usage
        assert total.input_tokens == 700
        assert total.output_tokens == 160
        assert total.cache_read_tokens == 50
    finally:
        os.remove(tf_name)


def test_gateway_adapter():
    """Verify Gateway completion payload extraction."""
    resp = {
        "id": "chatcmpl-123",
        "model": "deepseek-chat",
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 80,
            "prompt_tokens_details": {"cached_tokens": 100}
        }
    }
    ledger = GatewayAdapter.parse_response_dict(resp)
    assert len(ledger.turns) == 1
    turn = ledger.turns[0]
    assert turn.usage.input_tokens == 200
    assert turn.usage.output_tokens == 80
    assert turn.usage.cache_read_tokens == 100
