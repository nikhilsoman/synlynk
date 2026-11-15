import re
import pytest
from synlynk.viz.home import generate_index_html
from synlynk.viz.overview import generate_overview_html
from synlynk.viz.gantt import generate_gantt_html
from synlynk.viz.architect import generate_architect_map_html
from synlynk.viz.canvases import (
    generate_infra_html,
    generate_logical_html,
    generate_product_html,
    generate_world_html,
)
from synlynk.viz.journeys import generate_journeys_html
from synlynk.viz.effort import generate_effort_html
from synlynk.viz.efficiency import generate_efficiency_html
from synlynk.viz.observatory import generate_observatory_html
from synlynk.viz.roles import generate_roles_html
from synlynk.viz.board import generate_board_html
from synlynk.viz.onboarding import (
    generate_onboarding_html,
    generate_roles_onboarding_html,
)


def _assert_valid_html_structure(html: str, title_hint: str = ""):
    assert isinstance(html, str)
    assert len(html) > 100, f"HTML payload unexpectedly short: {len(html)}"
    assert "<html" in html.lower()
    assert "<body" in html.lower()
    if title_hint:
        assert title_hint.lower() in html.lower()


def test_vizor_html_generators_e2e():
    """Verify all 16 primary Vizor pages render non-empty valid HTML."""
    sample_data = {
        "repo_name": "synlynk-test",
        "timestamp": "2026-11-15T12:00:00Z",
        "summary": {"total_tasks": 10, "completed": 5},
        "stories": [],
        "goals": [],
        "members": [],
        "cost": {"total_spent_usd": 12.50},
        "repos": [],
    }
    port = 27472

    # 1. Home / Index
    home_html = generate_index_html(sample_data, port)
    _assert_valid_html_structure(home_html)

    # 2. Overview
    overview_html = generate_overview_html(sample_data, port)
    _assert_valid_html_structure(overview_html)

    # 3. Gantt
    gantt_html = generate_gantt_html(sample_data, port)
    _assert_valid_html_structure(gantt_html)

    # 4. Architect Map
    arch_html = generate_architect_map_html(sample_data, port)
    _assert_valid_html_structure(arch_html)

    # 5. Infrastructure Canvas
    infra_html = generate_infra_html(sample_data, port)
    _assert_valid_html_structure(infra_html)

    # 6. Logical Architecture Canvas
    logical_html = generate_logical_html(sample_data, port)
    _assert_valid_html_structure(logical_html)

    # 7. Product Map Canvas
    prod_html = generate_product_html(sample_data, port)
    _assert_valid_html_structure(prod_html)

    # 8. World Egress Radar
    world_html = generate_world_html(sample_data, port)
    _assert_valid_html_structure(world_html)

    # 9. Journeys
    journeys_html = generate_journeys_html(sample_data, port)
    _assert_valid_html_structure(journeys_html)

    # 10. Effort Matrix
    effort_html = generate_effort_html(sample_data, port)
    _assert_valid_html_structure(effort_html)

    # 11. Efficiency Matrix
    eff_html = generate_efficiency_html(sample_data, port)
    _assert_valid_html_structure(eff_html)

    # 12. Observatory Stream
    obs_html = generate_observatory_html(sample_data)
    _assert_valid_html_structure(obs_html)

    # 13. Roles Charter
    roles_html = generate_roles_html(sample_data, port)
    _assert_valid_html_structure(roles_html)

    # 14. Board
    board_html = generate_board_html(port)
    _assert_valid_html_structure(board_html)

    # 15. Onboarding Wizard
    onb_html = generate_onboarding_html(port=port)
    _assert_valid_html_structure(onb_html)

    # 16. Roles Onboarding
    roles_onb_html = generate_roles_onboarding_html(port=port)
    _assert_valid_html_structure(roles_onb_html)
