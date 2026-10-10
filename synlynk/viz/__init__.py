"""BS-21 Vizor: local browser dashboard generator and server.

Domain package split out of the former ``viz.py`` module. Public names stay
importable from ``synlynk.viz``. The ecosystem snapshot still comes from the
existing ``synlynk status --json`` seam inside ``synlynk.viz.data``.
"""

import webbrowser

from synlynk import _get_db, _query_repo_file_tree

_open_state_db = _get_db

from synlynk.viz.constants import (
    DEFAULT_PORT,
    MEMORABLE_VIZOR_PORTS,
    VIZ_CACHE_DIR,
    VIZ_META_PATH,
    VIZ_NOTES_PATH,
    VIZ_WORKSPACE_MAP_PATH,
    _KNOWN_AGENTS,
)
from synlynk.viz.chrome import _live_js
from synlynk.viz.ports import find_available_vizor_port, is_port_available
from synlynk.viz.banner import _compute_underused_feature_banner
from synlynk.viz.data import (
    _load_workspace_map,
    _load_workspace_repos,
    _repo_github_url,
    collect_data,
    generate_viz_data,
)
from synlynk.viz.overview import generate_overview_html
from synlynk.viz.activity import generate_activity_stream_html
from synlynk.viz.home import generate_index_html
from synlynk.viz.gantt import _GANTT_STYLE, generate_gantt_html
from synlynk.viz.architect import (
    _ARCHITECT_MAP_JS,
    _ARCHITECT_MAP_STYLE,
    generate_architect_map_html,
)
from synlynk.viz.canvases import (
    _BS6_VIEW_JS,
    _generate_bs6_view_html,
    generate_infra_html,
    generate_logical_html,
    generate_product_html,
    generate_world_html,
)
from synlynk.viz.journeys import generate_journeys_html
from synlynk.viz.format import _fmt_pct, _fmt_usd, _stage_color, _svg_text, _viz_json
from synlynk.viz.effort import generate_effort_html
from synlynk.viz.efficiency import generate_efficiency_html
from synlynk.viz.observatory import generate_observatory_html
from synlynk.viz.roles import generate_roles_html
from synlynk.viz.board import generate_board_html, generate_boardroom_html
from synlynk.viz.graphify import _enrich_graphify_html
from synlynk.viz.cache import _write_cache
from synlynk.viz.onboarding import (
    generate_onboarding_html,
    generate_roles_onboarding_html,
    get_role_manifest_payload,
    handle_github_app_conversion,
)
from synlynk.viz.source import _get_source_slice
from synlynk.viz.server import (
    VizorHandler,
    _current_workspace_slug,
    _ftue_prompts,
    _serve_until_stopped,
    _server_is_running,
    _start_server,
    _stop_server,
    cmd_viz,
)
from synlynk import vizor_daemon
