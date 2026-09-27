"""Tests for synlynk.governs_compressed: 5-stage compressed GOVERNS view projection."""

import pytest

from synlynk.governs_compressed import (
    COMPRESSED_STAGES,
    compress_governs_stage,
    get_compressed_stage_progress,
    format_compressed_governs_summary,
)


def test_compress_governs_stage_mappings():
    assert compress_governs_stage("dream") == "plan"
    assert compress_governs_stage("plan") == "plan"
    assert compress_governs_stage("work") == "build"
    assert compress_governs_stage("review") == "verify"
    assert compress_governs_stage("verify") == "verify"
    assert compress_governs_stage("ship") == "ship"
    assert compress_governs_stage("maint") == "sustain"
    assert compress_governs_stage("engag") == "sustain"
    # Case insensitivity
    assert compress_governs_stage("DREAM") == "plan"
    assert compress_governs_stage("Work") == "build"
    # Unknown fallback
    assert compress_governs_stage("unknown") == "plan"
    assert compress_governs_stage("") == "plan"


def test_get_compressed_stage_progress():
    items = [
        {"id": "spec-1", "stage": "dream"},
        {"id": "spec-2", "stage": "plan"},
        {"id": "story-1", "stage": "work"},
        {"id": "pr-1", "stage": "review"},
        {"id": "rel-1", "stage": "ship"},
        {"id": "maint-1", "stage": "maint"},
        {"id": "doc-1", "stage": "engag"},
    ]
    progress = get_compressed_stage_progress(items)
    assert len(progress["plan"]) == 2
    assert len(progress["build"]) == 1
    assert len(progress["verify"]) == 1
    assert len(progress["ship"]) == 1
    assert len(progress["sustain"]) == 2


def test_format_compressed_governs_summary():
    items = [
        {"id": "spec-1", "stage": "dream", "title": "Idea 1"},
        {"id": "story-1", "stage": "work", "title": "Build 1"},
    ]
    summary_compressed = format_compressed_governs_summary(items, full=False)
    assert "Plan" in summary_compressed
    assert "Build" in summary_compressed
    assert "Verify" in summary_compressed
    assert "Ship" in summary_compressed
    assert "Sustain" in summary_compressed

    summary_full = format_compressed_governs_summary(items, full=True)
    assert "Dream" in summary_full
    assert "Work" in summary_full
