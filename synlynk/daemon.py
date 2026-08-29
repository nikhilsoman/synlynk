"""synlynk daemon: background watch daemon, HTTP context server, SSE relay broker."""

import glob
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time

from synlynk.context import generate_context
from synlynk.jobs import _dispatch_ready_jobs, _reconcile_daemon_jobs
from synlynk.sentinel import _write_sentinel_alert, log_telemetry_event
from synlynk.team import get_username
from synlynk import github_app_auth


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _repo_common_dir() -> str:
    """Return the repository root shared by all worktrees.

    Git's common directory is ``<repo>/.git`` for a normal repository and is
    shared by linked worktrees.  Bare repositories report the repository
    directory itself, so only strip the final component when it is actually
    named ``.git``.  Commands outside a Git repository retain the historical
    current-working-directory behavior.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            check=True,
            capture_output=True,
            text=True,
        )
        common_dir = result.stdout.strip()
        if not common_dir:
            raise ValueError("git returned an empty common directory")
        common_dir = os.path.abspath(common_dir)
        if os.path.basename(common_dir) == ".git":
            return os.path.dirname(common_dir)
        return common_dir
    except Exception:
        # Broad by design: this must never crash daemon construction, whether
        # from a missing git binary, a non-repo cwd, or a test harness that
        # monkeypatches subprocess.Popen process-wide (subprocess.run() uses
        # Popen internally, so unrelated tests' fakes can surface here too).
        return os.getcwd()


def _daemon_state_path(*parts: str) -> str:
    return os.path.join(_repo_common_dir(), ".synlynk", *parts)


class WatchDaemon:
    """Polls project-docs/ and regenerates context.md on change.

    Subclass and override on_change() for the v1.3.0 LCP JSON-RPC daemon.
    """

    def __init__(self):
        self.pidfile = _daemon_state_path("watch.pid")
        self.logfile = _daemon_state_path("watch.log")
        self.settle_seconds = 3
        self.token_refresh_interval_seconds = 50 * 60

    def start(self) -> None:
        if self._is_running():
            print("  synlynk watch is already running.")
            return
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        if not hasattr(os, "fork"):
            print("  ⚠ watch daemon requires Unix (macOS/Linux). Not supported on Windows.")
            return
        pid = os.fork()
        if pid > 0:
            print("  ● synlynk watch started.")
            return
        os.setsid()
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        # Daemon process: redirect stdio to log
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.logfile, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        with open(self.pidfile, "w") as f:
            f.write(str(os.getpid()))
        _pkg("set_state")("watching")
        self._run_loop()

    def stop(self) -> None:
        if not os.path.exists(self.pidfile):
            print("  synlynk watch is not running.")
            _pkg("set_state")("stopped")
            return
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)  # SIGTERM
            os.remove(self.pidfile)
            _pkg("set_state")("stopped")
            print("  ✓ synlynk watch stopped.")
        except (ProcessLookupError, ValueError):
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            _pkg("set_state")("stopped")
            print("  synlynk watch was not running (cleaned stale pidfile).")
        except OSError as e:
            print(f"  Error stopping watch daemon: {e}")

    def status(self) -> None:
        if self._is_running():
            with open(self.pidfile) as f:
                pid = f.read().strip()
            print(f"  ● synlynk watch running (PID {pid})")
            if os.path.exists(self.logfile):
                with open(self.logfile) as f:
                    lines = f.readlines()
                if lines:
                    print(f"    Last log: {lines[-1].strip()}")
        else:
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            print("  ○ synlynk watch stopped")

    def _health(self) -> str:
        """Returns 'running', 'stopped', or 'zombie' (pidfile exists but process dead)."""
        if not os.path.exists(self.pidfile):
            return "stopped"
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return "running"
        except (ProcessLookupError, ValueError, OSError):
            return "zombie"

    def _is_running(self) -> bool:
        return self._health() == "running"

    def _get_mtimes(self, directory: str) -> dict:
        mtimes = {}
        if not os.path.exists(directory):
            return mtimes
        for root, _, files in os.walk(directory):
            for fname in files:
                if fname.endswith((".md", ".json")):
                    path = os.path.join(root, fname)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except OSError:
                        pass
        return mtimes

    def on_change(self, filepath: str) -> None:
        """Called when a project-docs file changes. Override in v1.3.0 LCP daemon."""
        _pkg("generate_context")()
        _pkg("log_telemetry_event")({
            "type": "watch_trigger",
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "user": _pkg("get_username")(),
            "changed_file": filepath,
        })

    def _refresh_github_tokens(self) -> None:
        """Mint fresh tokens for every provisioned role's GitHub App.

        Best-effort per role: one role's failure (revoked App, bad
        installation_id) must not stop the others or crash the daemon loop.
        """
        apps_dir = _daemon_state_path("github_apps")
        if not os.path.isdir(apps_dir):
            return
        for json_path in sorted(glob.glob(os.path.join(apps_dir, "*.json"))):
            if json_path.endswith(".token.json"):
                continue
            role = os.path.basename(json_path)[:-len(".json")]
            try:
                with open(json_path) as fh:
                    app_config = json.load(fh)
                if not app_config.get("installation_id"):
                    continue
                github_app_auth.refresh_installation_token(role, app_config)
            except Exception as exc:
                print(
                    f"  ⚠ could not refresh GitHub App token for role '{role}': {exc}",
                    file=sys.stderr,
                )

    def _run_loop(self) -> None:
        config = _pkg("load_config")()
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        # Refresh after daemonization so daemon start never performs signing or
        # network I/O in the foreground process.  This also keeps the refresh
        # in the same post-fork execution path as periodic refreshes.
        self._refresh_github_tokens()
        last_token_refresh = time.time()
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                _pkg("set_state")("active")
                self.on_change(changed[0])
                _pkg("set_state")("watching")
                last_mtimes = self._get_mtimes("project-docs")
            if time.time() - last_token_refresh >= self.token_refresh_interval_seconds:
                self._refresh_github_tokens()
                last_token_refresh = time.time()

def _make_daemon_handler(daemon_instance):
    """Returns a BaseHTTPRequestHandler class with daemon_instance bound via closure."""
    import http.server as _http_server
    import json as _json
    import urllib.parse as _urlparse

    class DaemonHTTPHandler(_http_server.BaseHTTPRequestHandler):
        _daemon = daemon_instance

        def log_message(self, fmt, *args):
            pass  # silence access log

        def _send_json(self, code: int, data) -> None:
            body = _json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, code: int, text: str) -> None:
            body = text.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _parse_path(self):
            parsed = _urlparse.urlparse(self.path)
            return parsed.path, dict(_urlparse.parse_qsl(parsed.query))

        def do_GET(self):
            path, params = self._parse_path()
            try:
                if path == "/context":
                    self._handle_context()
                elif path == "/status":
                    self._handle_status()
                elif path == "/jobs":
                    self._handle_jobs(params)
                elif path.startswith("/jobs/"):
                    self._handle_job_detail(path[6:])
                elif path == "/stories":
                    self._handle_stories()
                elif path.startswith("/stories/"):
                    self._handle_story_detail(path[9:])
                elif path == "/capability":
                    self._handle_capability()
                elif path == "/sentinel":
                    self._handle_sentinel()
                else:
                    self._send_json(404, {"error": "not found"})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        def do_POST(self):
            path, _ = self._parse_path()
            try:
                if path == "/dispatch":
                    self._handle_dispatch()
                elif path == "/checkpoint":
                    self._handle_checkpoint()
                else:
                    self._send_json(404, {"error": "not found"})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        def _handle_context(self):
            context_path = ".synlynk/context.md"
            content = ""
            if os.path.exists(context_path):
                with open(context_path) as f:
                    content = f.read()
            accept = self.headers.get("Accept", "")
            if "text/plain" in accept:
                self._send_text(200, content)
            else:
                self._send_json(200, {"content": content})

        def _handle_status(self):
            uptime = int(time.time() - getattr(self._daemon, "_start_time", time.time()))
            conn = _pkg("_get_db")()
            try:
                counts = {}
                for status in ("queued", "running", "done", "failed", "permission_denied"):
                    counts[status] = conn.execute(
                        "SELECT COUNT(*) FROM daemon_jobs WHERE status=?", (status,)
                    ).fetchone()[0]
            finally:
                conn.close()
            self._send_json(200, {
                "running": True,
                "uptime_s": uptime,
                "pid": os.getpid(),
                "jobs": counts,
            })

        def _handle_jobs(self, params):
            conn = _pkg("_get_db")()
            try:
                status_filter = params.get("status")
                if status_filter:
                    rows = conn.execute(
                        "SELECT job_id, agent, task, story_id, status, priority, "
                        "depends_on, pid, enqueued_at, started_at, completed_at, exit_code "
                        "FROM daemon_jobs WHERE status=? ORDER BY enqueued_at DESC",
                        (status_filter,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT job_id, agent, task, story_id, status, priority, "
                        "depends_on, pid, enqueued_at, started_at, completed_at, exit_code "
                        "FROM daemon_jobs ORDER BY enqueued_at DESC"
                    ).fetchall()
            finally:
                conn.close()
            cols = ["job_id", "agent", "task", "story_id", "status", "priority",
                    "depends_on", "pid", "enqueued_at", "started_at", "completed_at", "exit_code"]
            self._send_json(200, [dict(zip(cols, r)) for r in rows])

        def _handle_job_detail(self, job_id):
            conn = _pkg("_get_db")()
            try:
                row = conn.execute(
                    "SELECT job_id, agent, task, story_id, status, priority, depends_on, "
                    "pid, enqueued_at, started_at, completed_at, exit_code, log_path "
                    "FROM daemon_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            finally:
                conn.close()
            if not row:
                self._send_json(404, {"error": f"job {job_id!r} not found"})
                return
            cols = ["job_id", "agent", "task", "story_id", "status", "priority",
                    "depends_on", "pid", "enqueued_at", "started_at", "completed_at",
                    "exit_code", "log_path"]
            data = dict(zip(cols, row))
            log_tail = []
            if data.get("log_path") and os.path.exists(data["log_path"]):
                with open(data["log_path"]) as f:
                    log_tail = f.readlines()[-100:]
            data["log_tail"] = "".join(log_tail)
            self._send_json(200, data)

        def _handle_dispatch(self):
            import hashlib as _hashlib
            import json as _json
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            try:
                payload = _json.loads(body)
            except Exception:
                self._send_json(400, {"error": "invalid JSON body"})
                return
            agent = payload.get("agent")
            task = payload.get("task")
            if not agent or not task:
                self._send_json(400, {"error": "agent and task are required"})
                return
            job_id = "djob-" + _hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            conn = _pkg("_get_db")()
            try:
                # Daemon enqueue runs without an interactive operator.
                dispatch_context = "headless"
                conn.execute(
                    "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                    "priority, depends_on, enqueued_at, dispatch_context) VALUES (?,?,?,?,?,?,?,?,?)",
                    (job_id, agent, task, payload.get("story_id"),
                     "queued", payload.get("priority", 5),
                     _json.dumps(payload.get("depends_on", [])),
                     time.strftime("%Y-%m-%dT%H:%M:%S"), dispatch_context)
                )
                conn.commit()
            finally:
                conn.close()
            self._send_json(200, {"job_id": job_id})

        def _handle_stories(self):
            conn = _pkg("_get_db")()
            try:
                rows = conn.execute(
                    "SELECT story_id, title, engg_domain, org_domain, industry, phase, "
                    "estimated_tokens, actual_tokens, created_at "
                    "FROM stories ORDER BY created_at DESC"
                ).fetchall()
            finally:
                conn.close()
            cols = ["story_id", "title", "engg_domain", "org_domain", "industry",
                    "phase", "estimated_tokens", "actual_tokens", "created_at"]
            self._send_json(200, [dict(zip(cols, r)) for r in rows])

        def _handle_story_detail(self, story_id):
            conn = _pkg("_get_db")()
            try:
                row = conn.execute(
                    "SELECT story_id, title, engg_domain, org_domain, industry, phase, "
                    "estimated_tokens, actual_tokens, created_at "
                    "FROM stories WHERE story_id=?", (story_id,)
                ).fetchone()
            finally:
                conn.close()
            if not row:
                self._send_json(404, {"error": f"story {story_id!r} not found"})
                return
            cols = ["story_id", "title", "engg_domain", "org_domain", "industry",
                    "phase", "estimated_tokens", "actual_tokens", "created_at"]
            self._send_json(200, dict(zip(cols, row)))

        def _handle_capability(self):
            conn = _pkg("_get_db")()
            try:
                rows = conn.execute(
                    "SELECT agent, engg_domain, AVG(quality), COUNT(*) "
                    "FROM capability_ratings GROUP BY agent, engg_domain"
                ).fetchall()
            finally:
                conn.close()
            result = [
                {"agent": r[0], "domain": r[1], "avg_quality": r[2], "count": r[3]}
                for r in rows
            ]
            self._send_json(200, result)

        def _handle_sentinel(self):
            sentinel_file = ".synlynk/sentinel.md"
            alerts = []
            if os.path.exists(sentinel_file):
                with open(sentinel_file) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("- ["):
                            alerts.append(line)
            self._send_json(200, alerts)

        def _handle_checkpoint(self):
            with daemon_instance._context_lock:
                _pkg("generate_context")()
            self._send_json(200, {"regenerated": True})

    return DaemonHTTPHandler

def _daemon_install_service(daemon_instance) -> None:
    import textwrap as _textwrap

    synlynk_path = shutil.which("synlynk") or sys.argv[0]
    home = os.path.expanduser("~")

    try:
        if sys.platform == "darwin":
            launchagents_dir = os.path.join(home, "Library", "LaunchAgents")
            os.makedirs(launchagents_dir, exist_ok=True)
            log_dir = os.path.join(home, ".synlynk")
            os.makedirs(log_dir, exist_ok=True)
            plist_path = os.path.join(launchagents_dir, "com.synlynk.daemon.plist")
            log_path = os.path.join(log_dir, "launchd.log")
            plist = _textwrap.dedent(f"""\
                <?xml version="1.0" encoding="UTF-8"?>
                <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                <plist version="1.0">
                  <dict>
                    <key>Label</key>
                    <string>com.synlynk.daemon</string>
                    <key>ProgramArguments</key>
                    <array>
                      <string>{synlynk_path}</string>
                      <string>daemon</string>
                      <string>start</string>
                    </array>
                    <key>RunAtLoad</key>
                    <true/>
                    <key>KeepAlive</key>
                    <dict>
                      <key>SuccessfulExit</key>
                      <false/>
                    </dict>
                    <key>StandardOutPath</key>
                    <string>{log_path}</string>
                    <key>StandardErrorPath</key>
                    <string>{log_path}</string>
                  </dict>
                </plist>
            """)
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist)
            subprocess.run(["launchctl", "load", "-w", plist_path], check=False)
            print(f"  ✓ installed launchd service: {plist_path}")
            return

        if shutil.which("systemctl"):
            unit_dir = os.path.join(home, ".config", "systemd", "user")
            os.makedirs(unit_dir, exist_ok=True)
            synlynk_dir = os.path.join(home, ".synlynk")
            os.makedirs(synlynk_dir, exist_ok=True)
            unit_path = os.path.join(unit_dir, "synlynk-daemon.service")
            unit = _textwrap.dedent(f"""\
                [Unit]
                Description=Synlynk daemon
                After=default.target

                [Service]
                Type=forking
                ExecStart={synlynk_path} daemon start
                PIDFile=%h/.synlynk/daemon.pid
                Restart=on-failure

                [Install]
                WantedBy=default.target
            """)
            with open(unit_path, "w", encoding="utf-8") as f:
                f.write(unit)
            subprocess.run(["systemctl", "--user", "enable", "--now", "synlynk-daemon"], check=False)
            print(f"  ✓ installed systemd user service: {unit_path}")
            return

        synlynk_dir = os.path.join(home, ".synlynk")
        os.makedirs(synlynk_dir, exist_ok=True)
        entry = f"@reboot {synlynk_path} daemon start"
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = result.stdout if result.returncode == 0 else ""
        if entry not in current:
            new_crontab = current.rstrip("\n")
            if new_crontab:
                new_crontab += "\n"
            new_crontab += entry + "\n"
            subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=False)
        print("  ✓ installed @reboot crontab entry")
    except FileNotFoundError:
        print("  not installed")

def _daemon_uninstall_service() -> None:
    home = os.path.expanduser("~")

    try:
        if sys.platform == "darwin":
            plist_path = os.path.join(home, "Library", "LaunchAgents", "com.synlynk.daemon.plist")
            subprocess.run(["launchctl", "unload", plist_path], check=False)
            os.remove(plist_path)
            print(f"  ✓ uninstalled launchd service: {plist_path}")
            return

        if shutil.which("systemctl"):
            unit_path = os.path.join(home, ".config", "systemd", "user", "synlynk-daemon.service")
            subprocess.run(["systemctl", "--user", "disable", "--now", "synlynk-daemon"], check=False)
            os.remove(unit_path)
            print(f"  ✓ uninstalled systemd user service: {unit_path}")
            return

        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = result.stdout if result.returncode == 0 else ""
        filtered = "\n".join(
            line for line in current.splitlines()
            if not (line.strip().startswith("@reboot ") and line.strip().endswith(" daemon start"))
        )
        if filtered:
            filtered += "\n"
        subprocess.run(["crontab", "-"], input=filtered, text=True, check=False)
        print("  ✓ uninstalled @reboot crontab entry")
    except FileNotFoundError:
        print("  not installed")

def _make_relay_handler(subscribers: list, sub_lock) -> type:
    """Returns an HTTP handler class for the stateless relay broker."""
    import http.server as _http
    import json as _json
    import queue as _queue_mod

    class RelayHandler(_http.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # suppress access logs

        def do_GET(self):
            if self.path == "/health":
                self._send_json({"ok": True})
            elif self.path == "/events":
                self._stream_sse()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/publish":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    event = _json.loads(body)
                except ValueError:
                    self.send_error(400, "invalid JSON")
                    return
                data = f"data: {_json.dumps(event)}\n\n"
                with sub_lock:
                    dead = []
                    for q in subscribers:
                        try:
                            q.put_nowait(data)
                        except _queue_mod.Full:
                            pass  # slow subscriber — skip event, keep alive
                        except Exception:
                            dead.append(q)
                    for d in dead:
                        subscribers.remove(d)
                    fans = len(subscribers)
                self._send_json({"ok": True, "fans": fans})
            else:
                self.send_error(404)

        def _send_json(self, obj):
            body = _json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream_sse(self):
            import queue as _q
            q = _q.Queue(maxsize=256)
            with sub_lock:
                subscribers.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                while True:
                    try:
                        data = q.get(timeout=30)
                        self.wfile.write(data.encode())
                        self.wfile.flush()
                    except _q.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with sub_lock:
                    try:
                        subscribers.remove(q)
                    except ValueError:
                        pass

    return RelayHandler

class SynlynkRelay:
    """Stateless HTTP relay broker for synlynk node events."""

    RELAY_PORT = 27472

    def __init__(self, port: int = None):
        import threading as _threading
        self.port = port or self.RELAY_PORT
        self._subscribers: list = []
        self._sub_lock = _threading.Lock()
        self._server = None

    def start(self) -> None:
        """Starts the relay HTTP server in a background thread."""
        import http.server as _http
        import threading as _threading

        handler = _make_relay_handler(self._subscribers, self._sub_lock)
        self._server = _http.HTTPServer(("", self.port), handler)
        t = _threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        print(f"  {_pkg('_GREEN')}✓{_pkg('_RESET')} Relay started on port {self.port}")
        print(f"  {_pkg('_DIM')}Subscribe: GET http://localhost:{self.port}/events{_pkg('_RESET')}")
        print(f"  {_pkg('_DIM')}Publish:   POST http://localhost:{self.port}/publish{_pkg('_RESET')}")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            self._server.shutdown()
            print("\n  Relay stopped.")

    def is_alive(self, relay_url: str = None) -> bool:
        """Checks if the relay at relay_url (or localhost) is responding."""
        import urllib.request as _req

        url = relay_url or f"http://localhost:{self.port}/health"
        try:
            _req.urlopen(url, timeout=1)
            return True
        except Exception:
            return False

class SynlynkDaemon(WatchDaemon):
    """Always-running daemon: mtime polling + HTTP API + persistent job queue.

    Subclasses WatchDaemon (double-fork, pidfile, mtime loop) and adds:
    - HTTP server thread on localhost:27471
    - _reconcile_daemon_jobs() + _dispatch_ready_jobs() on each poll tick
    """

    HTTP_PORT = 27471

    def __init__(self):
        import threading as _threading
        super().__init__()
        self.pidfile = _daemon_state_path("daemon.pid")
        self.logfile = _daemon_state_path("daemon.log")
        self._start_time = time.time()
        self._context_lock = _threading.Lock()

    def start(self) -> None:
        if self._is_running():
            print("  synlynk daemon is already running.")
            return
        watch_pid = _daemon_state_path("watch.pid")
        if os.path.exists(watch_pid):
            print("  ⚠ synlynk watch is also running — both will poll project-docs/.")
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        if not hasattr(os, "fork"):
            print("  ⚠ daemon requires Unix (macOS/Linux). Not supported on Windows.")
            return
        pid = os.fork()
        if pid > 0:
            print("  ● synlynk daemon started.")
            return
        os.setsid()
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.logfile, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        with open(self.pidfile, "w") as f:
            f.write(str(os.getpid()))
        start_time = time.time()
        self._start_time = start_time
        start_file = self.pidfile.replace(".pid", ".start")
        with open(start_file, "w") as f:
            f.write(str(start_time))
        self._run_loop()

    def stop(self) -> None:
        if not os.path.exists(self.pidfile):
            print("  ✦ daemon not running")
            return
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)
            os.remove(self.pidfile)
            start_file = self.pidfile.replace(".pid", ".start")
            if os.path.exists(start_file):
                os.remove(start_file)
            print("  ✓ synlynk daemon stopped.")
        except (ProcessLookupError, ValueError):
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            start_file = self.pidfile.replace(".pid", ".start")
            if os.path.exists(start_file):
                os.remove(start_file)
            print("  ✦ daemon not running (cleaned stale pidfile).")
        except OSError as e:
            print(f"  Error stopping daemon: {e}")

    def status(self) -> None:
        if not self._is_running():
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            print("  ✦ synlynk daemon not running")
            return
        with open(self.pidfile) as f:
            pid = int(f.read().strip())
        start_file = self.pidfile.replace(".pid", ".start")
        try:
            with open(start_file) as f:
                start_time = float(f.read().strip())
        except (OSError, ValueError):
            start_time = time.time()
        uptime_s = int(time.time() - start_time)
        h, rem = divmod(uptime_s, 3600)
        m = rem // 60
        uptime_str = f"{h}h {m}m" if h else f"{m}m"
        conn = _pkg("_get_db")()
        try:
            counts = {s: conn.execute(
                "SELECT COUNT(*) FROM daemon_jobs WHERE status=?", (s,)
            ).fetchone()[0] for s in ("queued", "running", "done", "failed", "permission_denied")}
        finally:
            conn.close()
        print(f"  ✦ synlynk daemon running  (pid {pid}, up {uptime_str})")
        print(f"    jobs: {counts['queued']} queued · {counts['running']} running "
              f"· {counts['done']} done · {counts['failed']} failed · {counts['permission_denied']} permission_denied")
        print(f"    http: http://localhost:{self.HTTP_PORT}")

    def _run_loop(self) -> None:
        import threading as _threading
        import http.server as _http_server
        import traceback as _traceback

        class _ReuseAddrHTTPServer(_http_server.HTTPServer):
            allow_reuse_address = True

        handler_class = _make_daemon_handler(self)
        http_server = _ReuseAddrHTTPServer(("127.0.0.1", self.HTTP_PORT), handler_class)
        t = _threading.Thread(target=http_server.serve_forever, daemon=True)
        t.start()

        config = _pkg("load_config")()
        max_parallel = config.get("max_parallel", 4)
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        # Defer the initial refresh until the detached daemon has completed
        # its post-fork setup.  The caller of daemon start must not wait for
        # openssl signing or a GitHub API request.
        self._refresh_github_tokens()
        last_token_refresh = time.time()
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                try:
                    with self._context_lock:
                        self.on_change(changed[0])
                except Exception:
                    _traceback.print_exc()
                last_mtimes = self._get_mtimes("project-docs")
            try:
                _reconcile_daemon_jobs()
                _dispatch_ready_jobs(max_parallel=max_parallel)
            except Exception:
                _traceback.print_exc()
            if time.time() - last_token_refresh >= self.token_refresh_interval_seconds:
                self._refresh_github_tokens()
                last_token_refresh = time.time()

def cmd_relay_start(port: int = None) -> None:
    """Starts the relay broker in the foreground (Ctrl-C to stop)."""
    relay = SynlynkRelay(port=port)
    relay.start()

def cmd_relay_broadcast(kind: str, body: str, relay_url: str = None) -> None:
    """Publishes a broadcast event to the relay."""
    import json as _json
    import socket as _socket
    import urllib.request as _req

    url = relay_url or f"http://localhost:{SynlynkRelay.RELAY_PORT}/publish"
    event = _pkg("_build_relay_event")("broadcast", {
        "kind": kind,
        "body": body,
        "from": f"cli@{_socket.gethostname()}",
    })
    data = _json.dumps(event).encode()
    req = _req.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with _req.urlopen(req, timeout=5) as resp:
            result = _json.loads(resp.read())
        fans = result.get("fans", 0)
        print(f"  {_pkg('_GREEN')}✓{_pkg('_RESET')} broadcast sent ({kind}) → {fans} subscriber(s)")
    except Exception as e:
        print(f"  {_pkg('_YELLOW')}⚠{_pkg('_RESET')} relay not reachable: {e}")
        print(f"  Start relay: synlynk relay start")

def check_daemon_health() -> None:
    """Writes CRITICAL alert if watch daemon pidfile exists but process is dead."""
    daemon = WatchDaemon()
    if daemon._health() == "zombie":
        _write_sentinel_alert(
            "CRITICAL", "ZOMBIE_DAEMON",
            "Watch daemon pidfile exists but process is dead. "
            "Run: synlynk watch stop && synlynk watch start"
        )
        print("  🚨 [ZOMBIE_DAEMON] Watch daemon is dead — "
              "run: synlynk watch stop && synlynk watch start")

def check_stall() -> None:
    """Writes WARN alert if .synlynk/state has been 'active' longer than exec_timeout_minutes."""
    state_file = ".synlynk/state"
    if not os.path.exists(state_file):
        return
    try:
        with open(state_file) as f:
            state = f.read().strip()
        if state != "active":
            return
        age_minutes = (time.time() - os.path.getmtime(state_file)) / 60
        timeout = _pkg("load_config")().get("exec_timeout_minutes", 30)
        if age_minutes > timeout:
            _write_sentinel_alert(
                "WARN", "STALL",
                f"Exec has been running for {age_minutes:.0f} min "
                f"(threshold: {timeout} min). May be stalled."
            )
            print(f"  ⚠ [STALL] Exec has been active for {age_minutes:.0f} min — "
                  f"consider checking or restarting.")
    except (IOError, OSError):
        pass
