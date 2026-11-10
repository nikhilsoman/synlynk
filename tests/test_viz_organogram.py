"""Tests for Vizor Organogram view and API routes."""
import json
import pytest

from synlynk.viz.organogram import generate_organogram_html


def test_generate_organogram_html_renders_offline_first_svg():
    mock_data = {
        "workspace": {"name": "test-workspace", "slug": "synlynk"},
        "agents": [
            {
                "agent_id": "tpm",
                "role": "tpm",
                "primary_archetype": "orchestrator",
                "autonomy_level": "L2_GATED",
                "sfia_disciplines": ["PGMT", "PRMG"],
                "charter_excerpt": "Coordinates workflow waves",
            },
            {
                "agent_id": "dev",
                "role": "dev",
                "primary_archetype": "creator",
                "autonomy_level": "L1_ADVISORY",
                "sfia_disciplines": ["PROG"],
                "charter_excerpt": "Hands-on software development",
            },
        ],
        "workflow_edges": [
            {
                "edge_id": "e-1",
                "source_agent_id": "tpm",
                "target_agent_id": "dev",
                "edge_type": "delegation",
            }
        ],
        "archetypes": [
            {"archetype_id": "orchestrator", "name": "Orchestrator"},
            {"archetype_id": "creator", "name": "Creator"},
        ],
    }

    html_out = generate_organogram_html(mock_data, port=33333)

    assert "<!DOCTYPE html>" in html_out
    assert "synlynk Vizor — Workspace Organogram" in html_out
    assert "@tpm" in html_out
    assert "@dev" in html_out
    assert "orchestrator" in html_out.lower()
    assert "creator" in html_out.lower()
    assert "L2_GATED" in html_out
    assert "L1_ADVISORY" in html_out
    # Zero external CDN script tags (offline-first guarantee)
    assert "https://" not in html_out.lower() or "href" not in html_out.lower()
    assert "cdn." not in html_out.lower()
    assert "unpkg.com" not in html_out.lower()
