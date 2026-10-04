"""Local Vizor HTTP server, request handler, and ``synlynk viz`` command."""
import html
import json
import os
import re
import sys
import threading
import time
import uuid
import http.server
from pathlib import Path
from synlynk.viz.constants import DEFAULT_PORT
from synlynk.viz.onboarding import generate_onboarding_html, generate_roles_onboarding_html, handle_github_app_conversion
from synlynk.viz.source import _get_source_slice
def _pkg():
    """Package namespace tests and the Vizor daemon rebind."""
    import synlynk.viz as viz
    return viz

class VizorHandler(http.server.SimpleHTTPRequestHandler):
    """Serves viz-cache/ and handles Vizor POST routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(_pkg().VIZ_CACHE_DIR), **kwargs)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body)

    def _drain_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length > 0:
            self.rfile.read(length)

    def _authorize_write(self) -> bool:
        from synlynk.local_http_auth import authorize_local_request

        ok, code, message = authorize_local_request(self.headers)
        if ok:
            return True
        self._drain_body()
        self.send_error(code, message)
        return False

    def _send_json_ok(self, payload: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/api/source", "/api/v1/source") or path.endswith("/api/source"):
            params = parse_qs(parsed.query)
            file_param = params.get("file", [""])[0]
            start_p = params.get("start", [None])[0]
            end_p = params.get("end", [None])[0]
            slug_p = params.get("slug", [None])[0]

            s_line = int(start_p) if start_p and start_p.isdigit() else None
            e_line = int(end_p) if end_p and end_p.isdigit() else None

            repo_root = "."
            if slug_p:
                try:
                    from synlynk.state_registry import get_registered_product
                    entry = get_registered_product(slug_p)
                    if entry and entry.get("repo_path"):
                        repo_root = entry["repo_path"]
                except Exception:
                    pass

            res = _get_source_slice(repo_root, file_param, s_line, e_line)
            status_code = 200 if res["status"] == "ok" else res.get("code", 400)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        if path in ("/graphify", "/graph"):
            self.send_response(302)
            self.send_header("Location", "/graphify.html")
            self.end_headers()
            return

        if path in ("/onboarding", "/onboarding/") or (path.startswith("/w/") and path.endswith("/onboarding")):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            port = getattr(self.server, "server_port", 27472)
            html = generate_onboarding_html(port=port)
            self.wfile.write(html.encode("utf-8"))
            return

        if path.startswith("/w/") and path.endswith("/api/onboarding/state"):
            slug = path.split("/")[2]
            try:
                from synlynk import open_state_db
                from synlynk.onboarding_state import get_or_create_session
                conn, _ = open_state_db()
                sess = get_or_create_session(conn, slug)
                self._send_json_ok(sess)
            except Exception as e:
                self.send_error(500, str(e))
            return

        if path in ("/onboarding/roles", "/onboarding/roles/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            port = getattr(self.server, "server_port", 27472)
            html = generate_roles_onboarding_html(port=port)
            self.wfile.write(html.encode("utf-8"))
            return

        if path == "/auth/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [""])[0]
            role = params.get("role", [""])[0] or "qa"
            state_slug = params.get("state", [""])[0]
            redirect_target = (
                f"/w/{state_slug}/onboarding/roles?success={role}"
                if state_slug else f"/onboarding/roles?success={role}"
            )
            if code:
                try:
                    handle_github_app_conversion(code=code, role=role)
                    self.send_response(302)
                    self.send_header("Location", redirect_target)
                    self.end_headers()
                    return
                except Exception as e:
                    self.send_error(500, f"GitHub App conversion error: {e}")
                    return
            self.send_error(400, "Missing code query param")
            return

        if path == "/auth/sync":
            params = parse_qs(parsed.query)
            role = params.get("role", [""])[0]
            if role:
                try:
                    from pathlib import Path
                    from synlynk.github_app_auth import _sign_jwt, refresh_installation_token
                    from synlynk.product_store import resolve_github_apps_dir
                    from urllib.request import Request, urlopen
                    root = Path(".").resolve()
                    apps_dir = resolve_github_apps_dir(str(root))
                    json_path = apps_dir / f"{role}.json"
                    app_json_path = apps_dir / role / f"{role}.app.json"
                    target_path = json_path if json_path.exists() else app_json_path
                    if target_path.exists():
                        conf = json.loads(target_path.read_text(encoding="utf-8"))
                        app_id = conf.get("app_id") or conf.get("id")
                        pem_path = conf.get("private_key_path")
                        if not pem_path or not os.path.exists(pem_path):
                            cand_pem = apps_dir / f"{role}.pem"
                            cand_pem2 = apps_dir / role / f"{role}.private-key.pem"
                            pem_path = str(cand_pem if cand_pem.exists() else cand_pem2)
                        if app_id and pem_path and os.path.exists(pem_path):
                            jwt = _sign_jwt(app_id, pem_path)
                            req = Request(
                                "https://api.github.com/app/installations",
                                headers={
                                    "Accept": "application/vnd.github+json",
                                    "Authorization": f"Bearer {jwt}",
                                    "X-GitHub-Api-Version": "2022-11-28",
                                    "User-Agent": "synlynk-viz",
                                }
                            )
                            with urlopen(req) as resp:
                                inst_payload = json.loads(resp.read().decode("utf-8"))
                            inst_list = inst_payload if isinstance(inst_payload, list) else inst_payload.get("installations", [])
                            if inst_list and isinstance(inst_list[0], dict) and "id" in inst_list[0]:
                                inst_id = inst_list[0]["id"]
                                conf["installation_id"] = inst_id
                                target_path.write_text(json.dumps(conf, indent=2) + "\n", encoding="utf-8")
                                if json_path.exists() and target_path != json_path:
                                    jconf = json.loads(json_path.read_text(encoding="utf-8"))
                                    jconf["installation_id"] = inst_id
                                    json_path.write_text(json.dumps(jconf, indent=2) + "\n", encoding="utf-8")
                                if app_json_path.exists() and target_path != app_json_path:
                                    aconf = json.loads(app_json_path.read_text(encoding="utf-8"))
                                    aconf["installation_id"] = inst_id
                                    app_json_path.write_text(json.dumps(aconf, indent=2) + "\n", encoding="utf-8")
                                try:
                                    refresh_installation_token(role, conf, apps_dir=str(apps_dir))
                                except Exception:
                                    pass
                except Exception:
                    pass
            self.send_response(302)
            self.send_header("Location", f"/onboarding/roles?synced={role}")
            self.end_headers()
            return

        if path == "/api/readiness/live":
            from synlynk.readiness import evaluate_readiness_matrix
            matrix = evaluate_readiness_matrix()
            self._send_json_ok(matrix)
            return

        if path == "/api/board":
            from synlynk.board import board_data
            filters = parse_qs(parsed.query)
            try:
                payload = board_data(
                    repo_id=(filters.get("repo_id") or [None])[0],
                    type_id=(filters.get("type_id") or [None])[0],
                    goal_id=(filters.get("goal_id") or [None])[0],
                )
            except FileNotFoundError:
                payload = {"identity_slug": "", "cards": [], "filters": {"repos": [], "types": [], "goals": []}}
            self._send_json_ok(payload)
            return

        super().do_GET()

    def do_OPTIONS(self):
        clean_path = self.path.split("?")[0]
        valid_paths = ("/note", "/dispatch", "/approve", "/kill", "/architect-map/view-pref", "/roles/create", "/worktrees/clean", "/tools/install", "/api/tools/install", "/api/board/status", "/api/board/stage", "/graph/refresh", "/api/graph/refresh", "/api/v1/graph/refresh")
        if clean_path not in valid_paths and not clean_path.endswith("/api/graph/refresh") and not clean_path.endswith("/api/tools/install"):
            self.send_error(404)
            return
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if not self._authorize_write():
            return
        clean_path = self.path.split("?")[0]
        if clean_path == "/note":
            self._handle_note_request()
        elif clean_path == "/dispatch":
            self._handle_dispatch_request()
        elif clean_path == "/approve":
            self._handle_approve_request()
        elif clean_path == "/kill":
            self._handle_kill_request()
        elif clean_path == "/architect-map/view-pref":
            self._handle_view_pref_request()
        elif clean_path == "/roles/create":
            self._handle_role_create_request()
        elif clean_path == "/worktrees/clean":
            self._handle_worktree_clean_request()
        elif clean_path in ("/tools/install", "/api/tools/install") or clean_path.endswith("/api/tools/install"):
            self._handle_tool_install_request()
        elif clean_path.startswith("/w/") and clean_path.endswith("/api/onboarding/step"):
            self._handle_onboarding_step(clean_path)
        elif clean_path.startswith("/w/") and clean_path.endswith("/api/onboarding/topology/confirm"):
            self._handle_onboarding_topology_confirm(clean_path)
        elif clean_path == "/api/board/status" or clean_path.endswith("/api/board/status"):
            self._handle_board_status_request()
        elif clean_path == "/api/board/stage" or clean_path.endswith("/api/board/stage"):
            self._handle_board_stage_request()
        elif clean_path in ("/graph/refresh", "/api/graph/refresh", "/api/v1/graph/refresh") or clean_path.endswith("/api/graph/refresh"):
            self._handle_graph_refresh_request()
        else:
            self.send_error(404)

    def _handle_onboarding_step(self, path):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
            target_stage = data.get("stage")
            payload = data.get("payload")
            slug = path.split("/")[2]
            from synlynk import open_state_db
            from synlynk.onboarding_state import get_or_create_session, advance_stage
            conn, _ = open_state_db()
            sess = get_or_create_session(conn, slug)
            new_sess = advance_stage(conn, sess["session_id"], target_stage, payload)
            self._send_json_ok(new_sess)
        except Exception as e:
            self.send_error(500, str(e))

    def _handle_onboarding_topology_confirm(self, path):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            confirmed_topology = json.loads(body.decode("utf-8"))
            slug = path.split("/")[2]
            from synlynk import open_state_db
            from synlynk.onboarding_state import get_or_create_session, confirm_topology
            conn, _ = open_state_db()
            sess = get_or_create_session(conn, slug)
            new_sess = confirm_topology(conn, sess["session_id"], confirmed_topology)
            self._send_json_ok(new_sess)
        except Exception as e:
            self.send_error(500, str(e))

    def _handle_graph_refresh_request(self):
        try:
            from synlynk.scan import _run_graphify_extract
            clean_path = self.path.split("?")[0]
            slug = None
            if clean_path.startswith("/w/"):
                parts = clean_path.strip("/").split("/")
                if len(parts) >= 2:
                    slug = parts[1]
            elif clean_path.startswith("/"):
                parts = clean_path.strip("/").split("/")
                if len(parts) >= 3 and parts[-2] == "api" and parts[-1] == "refresh":
                    slug = parts[0]

            repo_root = None
            if slug:
                try:
                    from synlynk.vizor_daemon import _registered_workspaces
                    workspaces = _registered_workspaces()
                    if slug in workspaces:
                        repo_root = workspaces[slug].get("repo_path")
                except Exception:
                    pass

            if not repo_root:
                repo_root = os.getcwd()

            success = _run_graphify_extract(repo_root)
            if not success:
                self.send_error(500, "Graph extraction failed or tool unavailable")
                return

            port = getattr(self.server, "server_port", 8721) if hasattr(self, "server") else 8721
            if slug:
                try:
                    from synlynk.vizor_daemon import refresh_workspace, _registered_workspaces
                    workspaces = _registered_workspaces()
                    if slug in workspaces:
                        db_path = workspaces[slug].get("canonical_path")
                        if db_path and os.path.isfile(db_path):
                            try:
                                import sqlite3
                                from synlynk.viz_views import build_workspace_views_snapshot
                                conn = sqlite3.connect(db_path)
                                build_workspace_views_snapshot(conn, repo_root)
                                conn.commit()
                                conn.close()
                            except Exception:
                                pass
                        refresh_workspace(slug, workspaces[slug], port)
                except Exception:
                    pass
            else:
                try:
                    views_conn = _pkg()._get_db()
                    try:
                        from synlynk.viz_views import build_workspace_views_snapshot
                        build_workspace_views_snapshot(views_conn, repo_root)
                        if hasattr(views_conn, "commit"):
                            views_conn.commit()
                    finally:
                        views_conn.close()
                except Exception:
                    pass
                try:
                    data = _pkg().generate_viz_data()
                    _pkg()._write_cache(data, port)
                except Exception:
                    pass

            self._send_json_ok({"status": "ok", "message": "Knowledge graph successfully extracted and refreshed", "workspace": slug or "default"})
        except Exception as exc:
            self.send_error(500, str(exc))

    def _handle_board_status_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.board import update_status
            result = update_status(payload.get("story_id"), payload.get("status"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_board_stage_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.board import update_stage
            result = update_stage(payload.get("story_id"), payload.get("stage"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_tool_install_request(self):
        from urllib.parse import parse_qs
        from synlynk.tool_installer import install_tool

        content_type = self.headers.get("Content-Type", "")
        tool_name = "graphify"
        if "application/json" in content_type:
            try:
                payload = self._read_json_body()
                tool_name = payload.get("tool", "graphify")
            except (json.JSONDecodeError, TypeError, ValueError):
                self.send_error(400, "Invalid JSON")
                return
        else:
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
                params = parse_qs(body)
                tool_name = params.get("tool", ["graphify"])[0]
            except Exception:
                tool_name = "graphify"

        try:
            ok = install_tool(tool_name)
        except Exception:
            ok = False

        if "application/json" in content_type:
            self._send_json_ok({"ok": ok, "tool": tool_name})
        else:
            self.send_response(302)
            status_param = "success" if ok else "failed"
            self.send_header("Location", f"/onboarding?installed={tool_name}&status={status_param}")
            self.end_headers()

    def _handle_worktree_clean(self, payload: dict) -> dict:
        """Run the guarded worktree cleaner and return a small UI-friendly result."""
        from synlynk.worktree import cmd_worktree_clean

        apply = bool(payload.get("apply")) and not bool(payload.get("dry_run"))
        output = cmd_worktree_clean(apply=apply, json_output=True)
        if isinstance(output, dict):
            details = output
            output = json.dumps(output)
        else:
            details = None
        try:
            details = details or json.loads(output)
        except (TypeError, json.JSONDecodeError):
            details = {}
        if apply:
            cleaned_count = len(details.get("results") or [])
        else:
            cleaned_count = int(details.get("would_remove", 0) or 0)
        return {
            "ok": True,
            "dry_run": not apply,
            "cleaned_count": cleaned_count,
            "output": output,
        }

    def _handle_worktree_clean_request(self):
        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, TypeError, ValueError):
            self.send_error(400, "Invalid JSON")
            return
        try:
            result = self._handle_worktree_clean(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_role_create(self, payload: dict) -> dict:
        """Provision a role identity and its first living charter."""
        from synlynk import agent_store, agent_cli, charter_schema

        role = str(payload.get("role") or "").strip().lower()
        durability = str(payload.get("durability") or "durable").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", role):
            return {"ok": False, "error": "role must be a lowercase slug"}
        if durability not in charter_schema.VALID_DURABILITY:
            return {"ok": False, "error": "invalid durability"}
        for entry in agent_store.list_agents():
            for alias in entry.get("aliases", []):
                if alias.get("kind") == "role_slug" and alias.get("value") == role:
                    return {"ok": True, "agent_id": entry.get("agent_id"), "existing": True}
        agent_id = f"{role}-{uuid.uuid4().hex[:10]}"
        seed = agent_cli.SEED_CHARTERS.get(role)
        if seed:
            charter = re.sub(r"^durability: .*?$", f"durability: {durability}", seed, count=1, flags=re.MULTILINE)
        else:
            charter = (
                "---\n"
                "schema_version: 1\n"
                "role: dev\n"
                f'description: "Workspace role {role}"\n'
                f"durability: {durability}\n"
                "tools: []\ncredentials: []\n"
                "---\n\n"
                "## Instructions\n\n"
                f"Act as the {role} workspace persona according to the approved task brief.\n\n"
                "## Authority & Escalation\n\n"
                "Operate within workspace policy and escalate decisions outside the brief.\n\n"
                "## Workflow Ownership\n\n"
                f"Own work assigned to the {role} role.\n"
            )
        agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
        agent_store.propose_charter_revision(agent_id, charter, actor="vizor", parent_revision=0)
        return {"ok": True, "agent_id": agent_id}

    def _handle_role_create_request(self):
        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, TypeError, ValueError):
            self.send_error(400, "Invalid JSON")
            return
        try:
            result = self._handle_role_create(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_note_request(self):
        try:
            note = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        notes = {}
        if os.path.exists(_pkg().VIZ_NOTES_PATH):
            with open(_pkg().VIZ_NOTES_PATH) as f:
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
        with open(_pkg().VIZ_NOTES_PATH, "w") as f:
            json.dump(notes, f, indent=2)
        self._send_json_ok({"ok": True})

    def _handle_dispatch(self, payload: dict) -> dict:
        from synlynk import uxcore

        agent = payload.get("agent", "codex")
        task = payload.get("task", "")
        result = uxcore.dispatch(agent=agent, task=task)
        return {"ok": result.ok, "message": result.message, "job_id": result.job_id}

    def _handle_dispatch_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        if not payload.get("task"):
            self.send_error(400, "Missing task")
            return
        try:
            result = self._handle_dispatch(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_approve(self, payload: dict) -> dict:
        from synlynk import uxcore

        approve_kwargs = {"pr_number": payload["pr_number"]}
        if payload.get("story_id"):
            approve_kwargs["story_id"] = payload["story_id"]
        result = uxcore.approve_pr(**approve_kwargs)
        return {"ok": result.ok, "message": result.message, "job_id": result.job_id}

    def _handle_approve_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        if not payload.get("pr_number"):
            self.send_error(400, "Missing pr_number")
            return
        try:
            result = self._handle_approve(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_kill(self, payload: dict) -> dict:
        from synlynk import uxcore

        result = uxcore.kill_job(job_id=payload["job_id"])
        return {"ok": result.ok, "message": result.message, "job_id": result.job_id}

    def _handle_kill_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        if not payload.get("job_id"):
            self.send_error(400, "Missing job_id")
            return
        try:
            result = self._handle_kill(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_view_pref(self, payload: dict) -> dict:
        view = payload.get("view", "graph")
        config = {}
        config_path = ".synlynk/config.json"
        if os.path.exists(config_path):
            with open(config_path) as f:
                try:
                    config = json.load(f)
                except json.JSONDecodeError:
                    config = {}
        config.setdefault("vizor", {})["architect_map_view"] = view
        os.makedirs(".synlynk", exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return {"ok": True}

    def _handle_view_pref_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        result = self._handle_view_pref(payload)
        self._send_json_ok(result)

    def log_message(self, format, *args):
        pass  # suppress request logs


def _server_is_running() -> bool:
    meta_path = _pkg().VIZ_META_PATH
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return meta.get("serving", False)


def _start_server(port: int) -> http.server.HTTPServer:
    from synlynk.local_http_auth import ensure_local_token

    ensure_local_token()
    server = http.server.HTTPServer(("127.0.0.1", port), VizorHandler)
    meta = {"port": port, "serving": True}
    with open(_pkg().VIZ_META_PATH, "w") as f:
        json.dump(meta, f)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _serve_until_stopped(server: http.server.HTTPServer) -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


def _stop_server() -> None:
    if os.path.exists(_pkg().VIZ_META_PATH):
        with open(_pkg().VIZ_META_PATH, "w") as f:
            json.dump({"serving": False}, f)
    print("Vizor: server stopped (next startup will start a fresh server).")


def _ftue_prompts(config: dict) -> dict:
    """Run first-use prompts; update and return config with vizor key."""
    vizor = config.get("vizor", {})
    if vizor.get("ftue_done"):
        return config
    print("\n✦ synlynk viz — first setup\n")
    if sys.stdin.isatty():
        has_ux = input("  Does this project have user-facing UX? (y/n) ").strip().lower() == "y"
        vizor["second_view"] = "journeys" if has_ux else "tube"
        notify = input("  Enable browser notifications? (y/n) ").strip().lower() == "y"
        vizor["notify_on_refresh"] = notify
        interval_raw = input("  Auto-refresh interval? (15 / 30 / off) [off] ").strip() or "off"
        vizor["refresh_interval_minutes"] = 0 if interval_raw == "off" else int(interval_raw)
    else:
        vizor["second_view"] = "tube"
        vizor["notify_on_refresh"] = False
        vizor["refresh_interval_minutes"] = 0
    vizor["port"] = DEFAULT_PORT
    vizor["theme"] = "system"
    vizor["timeline_weeks"] = 10
    vizor["ftue_done"] = True
    config["vizor"] = vizor
    config_path = ".synlynk/config.json"
    os.makedirs(".synlynk", exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("  ✓ Settings saved to .synlynk/config.json\n")
    return config


def _current_workspace_slug() -> str:
    from synlynk.product_store import identity_slug_from_config

    return identity_slug_from_config(".")


def cmd_viz(args) -> None:
    """Entry point for `synlynk viz` subcommand."""
    from synlynk import vizor_daemon

    if getattr(args, "hosted", False):
        from synlynk.product_store import identity_slug_from_config
        from synlynk.wave6 import hosted_vizor_placeholder
        print(json.dumps(hosted_vizor_placeholder(identity_slug_from_config(".")), indent=2))
        return

    if getattr(args, "install", False):
        result = vizor_daemon.install()
        if result.get("installed"):
            print(f"  ✓ Vizor daemon installed via {result['manager']} ({result['unit_path']})")
        else:
            print(f"  ✗ Install failed: {result.get('reason', 'unknown error')}")
        return

    if getattr(args, "uninstall", False):
        result = vizor_daemon.uninstall()
        if result.get("uninstalled"):
            print(f"  ✓ Vizor daemon uninstalled ({result['manager']})")
        else:
            print(f"  ✗ Uninstall failed: {result.get('reason', 'unknown error')}")
        return

    if getattr(args, "daemon_status", False):
        status = vizor_daemon.status()
        print(json.dumps(status, indent=2))
        return

    slug = _pkg()._current_workspace_slug()
    if not vizor_daemon.is_running():
        print("  ✗ Vizor daemon is not running.")
        print("  Run: synlynk viz --install")
        print("  Or check: synlynk viz --daemon-status")
        return

    port = vizor_daemon._read_port() or _pkg().DEFAULT_PORT
    url = f"http://localhost:{port}/w/{slug}/overview.html"
    _pkg().webbrowser.open(url)
    print(f"  ✓ Opened {url}")

