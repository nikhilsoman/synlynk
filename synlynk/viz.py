"""BS-21 Vizor: local browser dashboard generator and server."""
import http.server
import json
import os
import subprocess
import threading
import time
import webbrowser
from typing import Optional

VIZ_CACHE_DIR = ".synlynk/viz-cache"
VIZ_NOTES_PATH = ".synlynk/viz-notes.json"
VIZ_META_PATH = ".synlynk/viz-meta.json"
VIZ_TUBE_PATH = ".synlynk/vizor-tube.json"
DEFAULT_PORT = 8721


def generate_viz_data() -> dict:
    raise NotImplementedError  # Task 2


def generate_index_html(data: dict, port: int) -> str:
    return f"<html><body>index stub port={port}</body></html>"


def generate_gantt_html(data: dict, port: int) -> str:
    return f"<html><body>gantt stub</body></html>"


def generate_tube_html(data: dict, port: int) -> str:
    return f"<html><body>tube stub</body></html>"


def generate_journeys_html(data: dict, port: int) -> str:
    return f"<html><body>journeys stub</body></html>"


def generate_effort_html(data: dict, port: int) -> str:
    return f"<html><body>effort stub</body></html>"


def generate_efficiency_html(data: dict, port: int) -> str:
    return f"<html><body>efficiency stub</body></html>"


def _write_cache(data: dict, port: int) -> None:
    """Generate all views and write to viz-cache/."""
    os.makedirs(VIZ_CACHE_DIR, exist_ok=True)
    views = {
        "index.html": generate_index_html(data, port),
        "gantt.html": generate_gantt_html(data, port),
        "tube.html": generate_tube_html(data, port),
        "journeys.html": generate_journeys_html(data, port),
        "effort.html": generate_effort_html(data, port),
        "efficiency.html": generate_efficiency_html(data, port),
    }
    for filename, html in views.items():
        with open(os.path.join(VIZ_CACHE_DIR, filename), "w") as f:
            f.write(html)
    manifest = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": "0.1"}
    with open(os.path.join(VIZ_CACHE_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f)


class VizorHandler(http.server.SimpleHTTPRequestHandler):
    """Serves viz-cache/ and handles POST /note."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(VIZ_CACHE_DIR), **kwargs)

    def do_POST(self):
        if self.path != "/note":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            note = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        notes = {}
        if os.path.exists(VIZ_NOTES_PATH):
            with open(VIZ_NOTES_PATH) as f:
                try:
                    notes = json.load(f)
                except json.JSONDecodeError:
                    notes = {}
        element_id = note.get("id", "")
        if not element_id:
            self.send_error(400, "Missing id")
            return
        notes[element_id] = {
            "text": note.get("text", ""),
            "tags": note.get("tags", []),
            "state": note.get("state", "info"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(VIZ_NOTES_PATH, "w") as f:
            json.dump(notes, f, indent=2)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, format, *args):
        pass  # suppress request logs


def _server_is_running() -> bool:
    meta_path = VIZ_META_PATH
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return meta.get("serving", False)


def _start_server(port: int) -> None:
    server = http.server.HTTPServer(("127.0.0.1", port), VizorHandler)
    meta = {"port": port, "serving": True}
    with open(VIZ_META_PATH, "w") as f:
        json.dump(meta, f)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _stop_server() -> None:
    if os.path.exists(VIZ_META_PATH):
        with open(VIZ_META_PATH, "w") as f:
            json.dump({"serving": False}, f)
    print("Vizor: server stopped (next startup will start a fresh server).")


def _ftue_prompts(config: dict) -> dict:
    """Run first-use prompts; update and return config with vizor key."""
    vizor = config.get("vizor", {})
    if vizor.get("ftue_done"):
        return config
    print("\n✦ synlynk viz — first setup\n")
    has_ux = input("  Does this project have user-facing UX? (y/n) ").strip().lower() == "y"
    vizor["second_view"] = "journeys" if has_ux else "tube"
    notify = input("  Enable browser notifications? (y/n) ").strip().lower() == "y"
    vizor["notify_on_refresh"] = notify
    interval_raw = input("  Auto-refresh interval? (15 / 30 / off) [off] ").strip() or "off"
    vizor["refresh_interval_minutes"] = 0 if interval_raw == "off" else int(interval_raw)
    vizor["port"] = DEFAULT_PORT
    vizor["theme"] = "system"
    vizor["timeline_weeks"] = 10
    vizor["ftue_done"] = True
    config["vizor"] = vizor
    config_path = ".synlynk/config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("  ✓ Settings saved to .synlynk/config.json\n")
    return config


def cmd_viz(args) -> None:
    """Entry point for `synlynk viz` subcommand."""
    import synlynk  # local import to avoid circular at module load
    config_path = ".synlynk/config.json"
    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    port = getattr(args, "port", None) or config.get("vizor", {}).get("port", DEFAULT_PORT)

    if args.stop:
        _stop_server()
        return

    if args.open:
        webbrowser.open(f"http://localhost:{port}/index.html")
        return

    if not args.generate:
        config = _ftue_prompts(config)
        port = getattr(args, "port", None) or config.get("vizor", {}).get("port", DEFAULT_PORT)

    print("  Generating Vizor views…")
    try:
        data = generate_viz_data()
    except NotImplementedError:
        data = {
            "workspace": {
                "name": os.path.basename(os.getcwd()) or "workspace",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "notes": {},
            "tube_config": None,
        }
    except Exception as e:
        print(f"  ✗ Data extraction failed: {e}")
        return

    _write_cache(data, port)
    print(f"  ✓ Views written to {VIZ_CACHE_DIR}/")

    if args.generate:
        print("  (--generate only: server not started)")
        return

    if not _server_is_running() or args.serve:
        server = _start_server(port)
        print(f"  ✓ Serving at http://localhost:{port}/")

    if not args.serve:
        webbrowser.open(f"http://localhost:{port}/index.html")
