import json
import os
import pytest
from synlynk.viz import (
    generate_overview_html,
    generate_activity_stream_html,
    generate_index_html,
    _write_cache,
    VIZ_CACHE_DIR,
)


@pytest.fixture
def sample_viz_data():
    return {
        "workspace": {
            "name": "synlynk",
            "updated_at": "2026-09-24T08:00:00Z",
            "repos": [{"name": "synlynk", "branch": "main", "active": True}],
        },
        "goals": [
            {
                "id": "goal-70317121",
                "outcome": "Vizor is a fully interactive, workspace-first web HUD",
                "criterion": "All views populated and interactive",
                "status": "active",
            }
        ],
        "dreams": [
            {
                "id": "epic-1",
                "name": "Vizor IA Restructure",
                "status": "active",
                "stages": [
                    {
                        "key": "work",
                        "status": "active",
                        "tasks": [
                            {"id": "story-1", "name": "Sidenav Accordion", "status": "active", "agent": "agy"},
                            {"id": "story-2", "name": "Overview Canvas", "status": "done", "agent": "agy"},
                        ],
                    }
                ],
            }
        ],
        "jobs": [
            {
                "job_id": "job-891306ab",
                "agent": "codex",
                "task_description": "Implement model routing",
                "status": "running",
                "pr_url": "https://github.com/nikhilsoman/synlynk/pull/1739",
            }
        ],
        "costs": {
            "total_usd": 18.40,
            "total_usd_estimated": 20.00,
            "by_agent": {"agy": 10.0, "codex": 8.40},
            "by_stage": {},
        },
        "telemetry": {
            "sentinel_alerts": [
                {
                    "severity": "WARNING",
                    "pattern": "TOKEN_BLOAT",
                    "message": "Job consumed 600k tokens with 0 files touched",
                    "ts": "2026-09-24 07:00",
                    "resolved": False,
                }
            ],
            "recent": [],
        },
        "actions": [
            {
                "action": "story_done",
                "user": "nikhilsoman",
                "summary": "Story Ph2 Social+Economy marked done",
                "ts": "2026-09-24 06:00",
            }
        ],
    }


def test_generate_overview_html(sample_viz_data):
    html = generate_overview_html(sample_viz_data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Workspace Overview" in html
    assert "synlynk" in html
    # Sentinel alerts banner
    assert "Active Sentinel Alerts" in html
    assert "TOKEN_BLOAT" in html
    # Stat cards
    assert "Active Goals" in html
    assert "Open Stories" in html
    assert "Jobs Running" in html
    assert "Burn (7d)" in html
    assert "$18.40" in html
    # Goals rollup
    assert "goal-70317121" in html
    assert "Vizor is a fully interactive" in html
    # Jobs feed
    assert "job-891306ab" in html
    assert "codex" in html
    assert "PR #1739" in html or "PR ↗" in html
    # Shortcuts grid
    assert "STATUS" in html
    assert "TOPOLOGIES" in html
    assert "PROJECTIONS" in html
    assert "TELEMETRY" in html
    assert 'href="board.html"' in html
    assert 'href="gantt.html"' in html
    assert 'href="tube.html"' in html
    assert 'href="product.html"' in html
    assert 'href="effort.html"' in html
    assert "checkManifest" in html


def test_generate_overview_html_clean_alerts(sample_viz_data):
    sample_viz_data["telemetry"]["sentinel_alerts"] = []
    html = generate_overview_html(sample_viz_data, 8721)
    assert "Active Sentinel Alerts" not in html


def test_generate_activity_stream_html(sample_viz_data):
    html = generate_activity_stream_html(sample_viz_data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Activity Stream" in html
    # Filter chips
    assert "Workspace:" in html
    assert "Type:" in html
    assert 'data-filter-group="ws"' in html
    assert 'data-filter-group="type"' in html
    # Stream events
    assert "story_done" in html or "Story" in html
    assert "job-891306ab" in html or "Dispatch" in html
    assert "goal-70317121" in html or "Goal" in html
    # Pagination
    assert "Load More Activity" in html
    assert "checkManifest" in html


def test_generate_index_html_two_tier_accordion_and_categories(sample_viz_data):
    html = generate_index_html(sample_viz_data, 8721)
    assert "<!DOCTYPE html>" in html
    # Two-tier accordion
    assert '<details name="tier1"' in html
    assert "PERSONAL" in html
    assert "TEAM" in html
    assert "ENTERPRISE" in html
    assert "Coming soon" in html
    # Active workspace and badge
    assert '<details name="workspace"' in html
    assert "synlynk" in html
    assert 'class="count-badge"' in html
    # Category Groupings
    assert "STATUS" in html
    assert "TOPOLOGIES" in html
    assert "PROJECTIONS" in html
    assert "TELEMETRY" in html
    # Category view links
    assert 'href="board.html"' in html
    assert 'href="gantt.html"' in html
    assert 'href="tube.html"' in html
    assert 'href="infra.html"' in html
    assert 'href="product.html"' in html
    assert 'href="logical.html"' in html
    assert 'href="world.html"' in html
    assert 'href="effort.html"' in html
    assert 'href="efficiency.html"' in html
    assert 'href="observatory.html"' in html
    assert 'href="roles.html"' in html
    # Breadcrumbs & Corner actions
    assert 'class="breadcrumbs"' in html
    assert 'Personal' in html
    assert 'corner-actions' in html
    # Default iframe loads overview.html
    assert '<iframe id="view-frame" src="overview.html"' in html


def test_write_cache_includes_overview_and_activity(tmp_path, monkeypatch, sample_viz_data):
    monkeypatch.chdir(tmp_path)
    _write_cache(sample_viz_data, port=8721)
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "index.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "overview.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "activity.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "board.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "gantt.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "tube.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "product.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "logical.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "world.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "infra.html"))
    assert os.path.exists(os.path.join(VIZ_CACHE_DIR, "manifest.json"))
