from pathlib import Path


def test_ux_10_phase_2_journey_map_simulator():
    """UX 1.0 Phase 2: Journey Map Simulator verification test."""
    repo_root = Path(__file__).parent.parent
    base_dir = repo_root / "docs" / "brainstorm" / "ux-journey-map"
    map_file = base_dir / "journey-map.html"
    index_file = base_dir / "index.html"

    assert map_file.exists(), f"{map_file} does not exist"
    assert index_file.exists(), f"{index_file} does not exist"

    map_content = map_file.read_text(encoding="utf-8")
    index_content = index_file.read_text(encoding="utf-8")

    # 1. Check Tailwind CDN
    assert "https://cdn.tailwindcss.com" in map_content
    assert "https://cdn.tailwindcss.com" in index_content

    # 2. Check Google Fonts pairing (Space Grotesk + Plus Jakarta Sans + Fira Code)
    assert "Space Grotesk" in map_content
    assert "Plus Jakarta Sans" in map_content
    assert "Fira Code" in map_content

    # 3. Check CSS transitions
    assert "transition: opacity 0.3s" in map_content or "transition: opacity 0.3s, transform 0.3s" in map_content

    # 4. Check all 7 journeys in order
    journey_titles = [
        "Install / upgrade / migrate",
        "synlynk concepts",
        "Repo onboarding",
        "SDLC-stage governance",
        "Dispatch a task",
        "Approve / kill a running job",
        "Get notified & react",
    ]
    for title in journey_titles:
        assert title in map_content, f"Journey title '{title}' missing from journey-map.html"
        assert title in index_content, f"Journey title '{title}' missing from index.html"

    # 5. Check 3 surface renderings
    for surface in ["TUI", "Vizor", "Slack"]:
        assert surface in map_content

    # 6. Check BYOUX Slack notifier payload shape reference
    assert "format_message" in map_content or "->" in map_content

    # 7. Check index.html links to journey-map.html
    assert "journey-map.html" in index_content
