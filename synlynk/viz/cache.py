"""Write rendered Vizor views into the cache directory."""
import html
import json
import os
import shutil
import time
from synlynk.viz.activity import generate_activity_stream_html
from synlynk.viz.architect import generate_architect_map_html
from synlynk.viz.board import generate_board_html
from synlynk.viz.efficiency import generate_efficiency_html
from synlynk.viz.effort import generate_effort_html
from synlynk.viz.gantt import generate_gantt_html
from synlynk.viz.home import generate_index_html
from synlynk.viz.canvases import generate_infra_html, generate_logical_html, generate_product_html, generate_world_html
from synlynk.viz.observatory import generate_observatory_html
from synlynk.viz.overview import generate_overview_html
from synlynk.viz.roles import generate_roles_html
from synlynk.viz.graphify import _enrich_graphify_html
def _pkg():
    """Package namespace tests and the Vizor daemon rebind."""
    import synlynk.viz as viz
    return viz

def _write_cache(data: dict, port: int) -> None:
    """Generate all views and write to viz-cache/."""
    os.makedirs(_pkg().VIZ_CACHE_DIR, exist_ok=True)
    views = {
        "index.html": generate_index_html(data, port),
        "overview.html": generate_overview_html(data, port),
        "activity.html": generate_activity_stream_html(data, port),
        "board.html": generate_board_html(port),
        "gantt.html": generate_gantt_html(data, port),
        "tube.html": generate_architect_map_html(data, port),
        "product.html": generate_product_html(data, port),
        "logical.html": generate_logical_html(data, port),
        "world.html": generate_world_html(data, port),
        "infra.html": generate_infra_html(data, port),

        "roles.html": generate_roles_html(data, port),
        "journeys.html": (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<meta http-equiv="refresh" content="0; url=product.html">'
            '<title>synlynk Vizor — Redirecting</title></head>'
            '<body>Redirecting to <a href="product.html">Product View</a>...'
            '<script>window.location.replace("product.html");</script>'
            "</body></html>"
        ),
        "effort.html": generate_effort_html(data, port),
        "efficiency.html": generate_efficiency_html(data, port),
        "observatory.html": generate_observatory_html(data.get("observatory") or {}),
    }
    for filename, html in views.items():
        with open(os.path.join(_pkg().VIZ_CACHE_DIR, filename), "w") as f:
            f.write(html)

    # Copy graphify.html to cache if present in workspace and enrich with canonical labels
    repo_root = os.getcwd()
    repos = data.get("workspace", {}).get("repos") or []
    if repos and isinstance(repos[0], dict) and repos[0].get("path"):
        repo_root = repos[0]["path"]

    graphify_src = os.path.join(repo_root, ".synlynk", "graphify-out", "graph.html")
    graphify_json_src = os.path.join(repo_root, ".synlynk", "graphify-out", "graph.json")
    if os.path.isfile(graphify_src):
        try:
            with open(graphify_src, "r", encoding="utf-8") as gf:
                html_str = gf.read()
            graph_data = {}
            if os.path.isfile(graphify_json_src):
                with open(graphify_json_src, "r", encoding="utf-8") as jf:
                    graph_data = json.load(jf)
            elif (data.get("workspace_views") or {}).get("logical"):
                graph_data = {"nodes": (data.get("workspace_views") or {}).get("logical", {}).get("nodes", [])}
            enriched_html = _enrich_graphify_html(html_str, graph_data)
            with open(os.path.join(_pkg().VIZ_CACHE_DIR, "graphify.html"), "w", encoding="utf-8") as out_f:
                out_f.write(enriched_html)
            with open(os.path.join(_pkg().VIZ_CACHE_DIR, "graph.html"), "w", encoding="utf-8") as out_f:
                out_f.write(enriched_html)
        except Exception:
            try:
                shutil.copyfile(graphify_src, os.path.join(_pkg().VIZ_CACHE_DIR, "graphify.html"))
                shutil.copyfile(graphify_src, os.path.join(_pkg().VIZ_CACHE_DIR, "graph.html"))
            except Exception:
                pass

    manifest = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": "0.1"}
    with open(os.path.join(_pkg().VIZ_CACHE_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f)

