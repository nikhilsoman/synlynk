"""Unit tests for Greenfield Dilemma Engine and DECIDE panel (v0.28.5)."""
from __future__ import annotations

import pytest
from synlynk.greenfield.dilemma_engine import isolate_dilemma, format_decide_box


def test_dilemma_matching_for_cli_archetype():
    """Verify CLI intent matches SQLite WAL vs Flat dotfiles dilemma."""
    dilemma = isolate_dilemma("Build an audio digest command-line tool with RSS feeds")
    assert dilemma["category"] == "cli"
    assert "SQLite WAL" in dilemma["topic"]
    assert "Option A" in dilemma["recommended"]
    assert "claude" in dilemma["panel_arguments"]
    assert "codex" in dilemma["panel_arguments"]
    assert "agy" in dilemma["panel_arguments"]
    assert "grok" in dilemma["panel_arguments"]


def test_dilemma_matching_for_backend_archetype():
    """Verify backend intent matches Task Queue architecture dilemma."""
    dilemma = isolate_dilemma("Build a fast web service API with background worker queues")
    assert dilemma["category"] == "backend"
    assert "Task Queue Architecture" in dilemma["topic"]


def test_dilemma_matching_for_general_fallback():
    """Verify unknown intent defaults to general architecture dilemma."""
    dilemma = isolate_dilemma("Something completely unconventional and unique")
    assert dilemma["category"] == "general"
    assert "Extensibility Architecture" in dilemma["topic"]


def test_format_decide_box():
    """Verify DECIDE panel formatting includes all harness positions and consensus."""
    dilemma = isolate_dilemma("Build a command line tool")
    box = format_decide_box(dilemma)
    assert "synlynk decide: Deliberating Architectural Dilemma" in box
    assert "Claude - Architect" in box
    assert "Codex - Dev" in box
    assert "Agy - QA" in box
    assert "Grok - Infra" in box
    assert "PANEL CONSENSUS:" in box
