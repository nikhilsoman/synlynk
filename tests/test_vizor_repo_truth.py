import json
import sqlite3
from pathlib import Path
import pytest
from synlynk.viz_views import (
    extract_infra_nodes,
    extract_product_nodes,
    extract_world_nodes,
)


@pytest.fixture
def mock_db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_extract_infra_nodes_arbitrary_repo_no_synlynk_leakage(tmp_path, mock_db):
    """An external repo must NEVER show synlynk's internal daemons, ports, or LLM egress."""
    repo = tmp_path / "rxcc_dummy"
    repo.mkdir()
    
    # Target repo has its own docker-compose and Dockerfile
    compose_file = repo / "docker-compose.yml"
    compose_file.write_text(
        """
version: '3.8'
services:
  web:
    build: .
    ports:
      - "3000:3000"
  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
"""
    )
    (repo / "Dockerfile").write_text("FROM node:20\nEXPOSE 3000\n")

    nodes, edges = extract_infra_nodes(mock_db, str(repo))

    labels = [n["label"] for n in nodes]
    source_paths = [n.get("source_path") or "" for n in nodes]
    all_text = " ".join(labels + source_paths + [n.get("attrs_json", "") for n in nodes])

    # Must NOT contain synlynk private daemons or egress
    assert "Vizor Server (:8721)" not in labels, "Synlynk Vizor server leaked into external repo!"
    assert "SSE Relay Broker (:27472)" not in labels, "Synlynk Relay leaked into external repo!"
    assert "StateDB SQLite Ledger" not in labels, "Synlynk StateDB leaked into external repo!"
    assert "Anthropic Claude API" not in labels, "Synlynk LLM egress leaked into external repo!"
    assert "synlynk/viz.py" not in all_text
    assert "synlynk/dispatch.py" not in all_text

    # Must discover the repo's actual declared services
    assert any("web" in l.lower() or "3000" in l for l in labels)
    assert any("postgres" in l.lower() or "5432" in l for l in labels)


def test_extract_product_nodes_discovers_brainstorm_prototypes(tmp_path, mock_db):
    """HTML prototypes in .superpowers/brainstorm/*/content/*.html must be discovered as screens."""
    repo = tmp_path / "app_with_mocks"
    repo.mkdir()
    
    mock_dir = repo / ".superpowers" / "brainstorm" / "39816-1782111579" / "content"
    mock_dir.mkdir(parents=True)
    (mock_dir / "01-landing.html").write_text("<!DOCTYPE html><html><head><title>Landing Page</title></head><body>Hero</body></html>")
    (mock_dir / "02-dashboard.html").write_text("<!DOCTYPE html><html><head><title>User Dashboard</title></head><body>Dashboard</body></html>")

    nodes, edges = extract_product_nodes(mock_db, str(repo))

    labels = [n["label"] for n in nodes]
    screens = [n for n in nodes if n.get("kind") == "screen" or "Mockup" in n.get("kind", "") or "Prototype" in n.get("kind", "")]

    # Should discover both prototypes
    assert any("Landing Page" in n["label"] or "01-landing" in n["label"] for n in screens)
    assert any("User Dashboard" in n["label"] or "02-dashboard" in n["label"] for n in screens)


def test_extract_product_nodes_discovers_monorepo_apps(tmp_path, mock_db):
    """A monorepo with apps/web and apps/api should discover those apps, not synlynk journeys."""
    repo = tmp_path / "monorepo_dummy"
    repo.mkdir()

    (repo / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n  - 'packages/*'\n")
    apps_dir = repo / "apps"
    web_app = apps_dir / "web"
    web_app.mkdir(parents=True)
    (web_app / "package.json").write_text(json.dumps({"name": "@myorg/web", "version": "1.0.0"}))

    api_app = apps_dir / "api"
    api_app.mkdir(parents=True)
    (api_app / "package.json").write_text(json.dumps({"name": "@myorg/api", "version": "1.0.0"}))

    nodes, edges = extract_product_nodes(mock_db, str(repo))

    labels = [n["label"] for n in nodes]
    all_text = " ".join(labels + [n.get("attrs_json", "") for n in nodes])

    # Must NOT have synlynk-specific canonical journeys
    assert "Zero-Friction Onboarding" not in labels, "Synlynk onboarding journey leaked into monorepo!"
    assert "synlynk/cli.py" not in all_text

    # Must discover the monorepo apps
    assert any("web" in l.lower() for l in labels)
    assert any("api" in l.lower() for l in labels)


def test_extract_world_nodes_no_synlynk_source_paths(tmp_path, mock_db):
    """World view must not reference synlynk source paths on external repos."""
    repo = tmp_path / "simple_service"
    repo.mkdir()
    (repo / ".env.example").write_text("STRIPE_API_KEY=sk_test_123\nAWS_S3_BUCKET=my-bucket\n")

    nodes, edges = extract_world_nodes(mock_db, str(repo))

    all_text = " ".join(n["label"] + " " + (n.get("source_path") or "") + " " + n.get("attrs_json", "") for n in nodes)
    assert "synlynk/gh.py" not in all_text
    assert "synlynk/dispatch.py" not in all_text
    assert "synlynk/media.py" not in all_text
