"""synlynk team: onboarding (join), team digest, consensus (decide), identity keys."""

import hashlib
import json
import os
import subprocess
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from synlynk._constants import AGENT_CAPABILITY_BASELINES


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def get_username() -> str:
    """Resolves current user's GitHub login via gh CLI, falling back to git config."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True
        )
        login = result.stdout.strip()
        if login and result.returncode == 0:
            return login
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True
        )
        name = result.stdout.strip()
        return name.lower().replace(" ", "") if name else "unknown"
    except Exception:
        return "unknown"


def get_mode() -> str:
    """Returns 'single' or 'team' from <docs_dir>/.synlynk_config.json."""
    config_path = os.path.join(_pkg("_docs_dir")(), ".synlynk_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f).get("mode", "single")
        except (json.JSONDecodeError, IOError):
            pass
    return "single"


def _ensure_identity_key() -> str:
    key_dir = os.path.expanduser("~/.synlynk")
    key_path = os.path.join(key_dir, "identity.key")
    if not os.path.exists(key_path):
        os.makedirs(key_dir, exist_ok=True)
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", key_path, "-C", "synlynk-identity"],
                capture_output=True
            )
        except (FileNotFoundError, OSError):
            pass
    return key_path


def _role_slug(role: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    return slug or "role"


def _role_app_dir() -> Path:
    return Path(".synlynk") / "github_apps"


def _role_app_paths(role: str) -> tuple[Path, Path, Path]:
    slug = _role_slug(role)
    app_dir = _role_app_dir()
    return app_dir, app_dir / f"{slug}.json", app_dir / f"{slug}.pem"


def _build_app_manifest_url(project, role: str) -> str:
    project_slug = _role_slug(project) if project else _role_slug(os.path.basename(os.getcwd()))
    role_slug = _role_slug(role)
    manifest = {
        "name": f"synlynk-{project_slug}-{role_slug}",
        "url": "https://synlynk.com",
        "hook_attributes": {
            "url": f"https://synlynk.com/github-apps/{project_slug}/{role_slug}/webhook",
        },
        "redirect_url": f"https://synlynk.com/github-apps/{project_slug}/{role_slug}/callback",
        "public": False,
        "default_events": [],
        "default_permissions": {
            "metadata": "read",
            "contents": "read",
            "issues": "write",
            "pull_requests": "write",
        },
    }
    query = urlencode({"manifest": json.dumps(manifest, separators=(",", ":"))})
    return f"https://github.com/settings/apps/new?{query}"


def _github_auth_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _extract_manifest_code(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme and parsed.query:
        code = parse_qs(parsed.query).get("code", [""])[0]
        if code:
            return code.strip()
    if "code=" in value:
        parsed_qs = parse_qs(value.split("?", 1)[-1])
        code = parsed_qs.get("code", [""])[0]
        if code:
            return code.strip()
    return value


def _exchange_manifest_code(code: str) -> dict:
    token = _github_auth_token()
    url = f"https://api.github.com/app-manifests/{code}/conversions"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=b"", method="POST", headers=headers)
    with urlopen(request) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _write_role_app_config(role: str, conversion: dict) -> dict:
    app_dir, json_path, pem_path = _role_app_paths(role)
    app_dir.mkdir(parents=True, exist_ok=True)

    pem = (
        conversion.get("pem")
        or conversion.get("private_key")
        or conversion.get("private_key_pem")
        or ""
    )
    pem_path.write_text(pem)
    try:
        os.chmod(pem_path, 0o600)
    except OSError:
        pass

    config = {
        "role": role,
        "app_id": conversion.get("id"),
        "client_id": conversion.get("client_id"),
        "app_slug": conversion.get("slug") or conversion.get("name") or _role_slug(role),
        "installation_id": conversion.get("installation_id"),
        "private_key_path": str(pem_path),
    }
    json_path.write_text(json.dumps(config, indent=2) + "\n")
    try:
        os.chmod(json_path, 0o600)
    except OSError:
        pass
    return config


def _confirm_installation(app_slug: str, json_path: Path) -> dict:
    from synlynk.github_app_auth import _sign_jwt

    with open(json_path) as f:
        config = json.load(f)

    app_id = config["app_id"]
    private_key_path = config["private_key_path"]
    jwt = _sign_jwt(app_id, private_key_path)

    request = Request(
        "https://api.github.com/app/installations",
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {jwt}",
        },
    )
    with urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))

    installations = payload if isinstance(payload, list) else payload.get("installations", [])
    installation = None
    for item in installations:
        if not isinstance(item, dict):
            continue
        if item.get("app_slug") == app_slug or item.get("slug") == app_slug or item.get("name") == app_slug:
            installation = item
            break
    if installation is None and installations:
        first = installations[0]
        if isinstance(first, dict):
            installation = first
    if installation is None or "id" not in installation:
        raise RuntimeError(f"no installation found for {app_slug}")

    config["installation_id"] = installation["id"]
    with open(json_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    return installation


def _sign_capability_rating(data: dict) -> str:
    import json as _json
    import tempfile as _tmp

    key_path = _ensure_identity_key()
    if not os.path.exists(key_path):
        return ""
    canonical = _json.dumps(data, sort_keys=True).encode()
    msg_file = None
    sig_file = None
    try:
        with _tmp.NamedTemporaryFile(mode="wb", suffix=".rating", delete=False) as f:
            f.write(canonical)
            msg_file = f.name
        sig_file = msg_file + ".sig"
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", key_path, "-n", "synlynk-rating", msg_file],
            capture_output=True
        )
        if os.path.exists(sig_file):
            with open(sig_file) as fh:
                return fh.read().strip()
    except Exception:
        pass
    finally:
        if msg_file:
            try:
                os.unlink(msg_file)
            except Exception:
                pass
        if sig_file and os.path.exists(sig_file):
            try:
                os.unlink(sig_file)
            except Exception:
                pass
    return ""


def _run_agent_sync(agent: str, prompt: str, timeout: int = 120) -> str:
    """Run an agent synchronously and return its stdout. Returns '' on any failure."""
    import tempfile as _tmp

    baselines = AGENT_CAPABILITY_BASELINES
    if agent not in baselines:
        print(f"  ⚠ Unknown agent '{agent}' — skipping")
        return ""

    agent_cfg = baselines[agent]
    cli = agent_cfg["cli"]
    flags = agent_cfg["non_interactive_flags"]
    prompt_via_arg = agent_cfg.get("prompt_via_arg", False)
    prompt_flag = agent_cfg.get("prompt_flag")

    prompt_file = None
    try:
        with _tmp.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as pf:
            pf.write(prompt)
            prompt_file = pf.name

        if prompt_via_arg:
            if prompt_flag:
                cmd = [cli] + flags + [prompt_flag, prompt]
            else:
                cmd = [cli] + flags + [prompt]
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout
            )
        else:
            with open(prompt_file) as stdin_file:
                result = subprocess.run(
                    [cli] + flags,
                    stdin=stdin_file, capture_output=True,
                    text=True, timeout=timeout
                )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"  ⚠ Agent '{agent}' failed: {e}")
        return ""
    finally:
        if prompt_file:
            try:
                os.unlink(prompt_file)
            except Exception:
                pass


def _write_decision_record(
    decision_id: str, topic: str, date: str, panel: list,
    inputs: dict, synthesis: str, decision_text: str,
    decisions_dir: str, slug: str
) -> None:
    """Write MD + JSON sidecar for a Decision record. Signs JSON with local identity key."""
    base = os.path.join(decisions_dir, f"{date}-{slug}")

    record = {
        "decision_id": decision_id,
        "topic": topic,
        "date": date,
        "panel": panel,
        "status": "approved",
        "inputs": inputs,
        "synthesis": synthesis,
        "decision": decision_text,
    }

    sig = _pkg("_sign_capability_rating")(record)
    if sig:
        record["signature"] = sig
    else:
        print("  ⚠ No identity key — decision written unsigned. "
              "Run `synlynk identity init` first.")

    with open(f"{base}.json", "w") as f:
        json.dump(record, f, indent=2)

    panel_inputs_md = ""
    for member, text in inputs.items():
        panel_inputs_md += f"\n### {member}\n{text}\n"

    md_content = (
        f"---\n"
        f"decision_id: {decision_id}\n"
        f"topic: \"{topic}\"\n"
        f"date: {date}\n"
        f"panel: [{', '.join(panel)}]\n"
        f"status: approved\n"
        f"---\n\n"
        f"## Topic\n{topic}\n\n"
        f"## Panel Inputs\n{panel_inputs_md}\n"
        f"## Synthesis\n{synthesis}\n\n"
        f"## Decision\n{decision_text}\n\n"
        f"> Signatures: see {date}-{slug}.json\n"
    )
    with open(f"{base}.md", "w") as f:
        f.write(md_content)


def cmd_decide(topic: str, panel: list, record: bool = False) -> None:
    """Convene a multi-agent panel on topic and optionally record the Decision."""
    print(f"\n  {_CYAN}▶{_RESET} Convening panel on: {topic}")
    print(f"  Panel: {', '.join(panel)}\n")

    panel_prompt = (
        f"You are part of a decision panel. Topic: \"{topic}\"\n\n"
        f"Provide your analysis and recommendation in 200-400 words. "
        f"State your position clearly in the final paragraph."
    )

    inputs = {}
    for member in panel:
        print(f"  {_CYAN}▶{_RESET} Querying {member}...")
        output = _pkg("_run_agent_sync")(member, panel_prompt)
        if output:
            inputs[member] = output
            print(f"  {_GREEN}✓{_RESET} {member} responded ({len(output.split())} words)")
        else:
            print(f"  ⚠ {member} returned no output — skipping")

    if not inputs:
        print("Error: all panel members failed — cannot produce a decision")
        sys.exit(1)

    synthesis_parts = [
        f"The following are inputs from a decision panel on: \"{topic}\"\n"
    ]
    for member, text in inputs.items():
        synthesis_parts.append(f"### {member}\n{text}\n")
    synthesis_parts.append(
        "Synthesize these into a single decision. In the final paragraph, "
        "state the decision clearly starting with \"Decision:\"."
    )
    synthesis_prompt = "\n".join(synthesis_parts)

    print(f"\n  {_CYAN}▶{_RESET} Synthesizing...")
    synthesis = _pkg("_run_agent_sync")(panel[0], synthesis_prompt)
    if not synthesis:
        synthesis = "Synthesis unavailable — see individual panel inputs above."

    decision_text = ""
    for line in synthesis.split("\n"):
        if line.strip().lower().startswith("decision:"):
            decision_text = line.strip()
            break
    if not decision_text:
        lines = [l.strip() for l in synthesis.split("\n") if l.strip()]
        decision_text = lines[-1] if lines else synthesis

    sep = "─" * 50
    print(f"\n{sep}\nSYNTHESIS\n\n{synthesis}\n{sep}\n")

    if not record:
        print("  (Use --record to save this as a Decision record)")
        return

    _pkg("_check_upstream_divergence")()

    decision_id = "dec-" + hashlib.md5(
        f"{topic}{time.time()}".encode()
    ).hexdigest()[:8]

    today = time.strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40].strip('-')

    decisions_dir = os.path.join(_pkg("_docs_dir")(), "decisions")
    os.makedirs(decisions_dir, exist_ok=True)

    _write_decision_record(
        decision_id, topic, today, panel,
        inputs, synthesis, decision_text, decisions_dir, slug
    )

    print(f"  {_GREEN}✓{_RESET} Decision recorded: {decisions_dir}/{today}-{slug}.md")


def _build_team_digest() -> dict:
    """Reads devlogs + SQLite to build a team status digest.
    SQLite section silently skipped if state.db absent."""
    members = []
    devlogs_dir = os.path.join(_pkg("_docs_dir")(), "devlogs")
    if os.path.exists(devlogs_dir):
        for fname in sorted(os.listdir(devlogs_dir)):
            if fname.endswith(".md") and fname != "README.md":
                fpath = os.path.join(devlogs_dir, fname)
                user = fname[:-3]
                last_active = _pkg("_get_last_devlog_date")(fpath) or "unknown"
                shipped = 0
                try:
                    with open(fpath) as fh:
                        for line in fh:
                            if re.match(r'^## \d{4}-\d{2}-\d{2}', line):
                                shipped += 1
                except IOError:
                    pass
                members.append({
                    "user": user,
                    "last_active": last_active,
                    "stories_shipped": shipped,
                })

    in_progress = []
    recently_completed = []

    try:
        conn = _pkg("_get_db")()
        stories = conn.execute(
            "SELECT story_id, title, estimated_tokens FROM stories ORDER BY created_at DESC LIMIT 20"
        ).fetchall()

        telemetry = []
        tel_path = ".synlynk/telemetry.json"
        if os.path.exists(tel_path):
            try:
                with open(tel_path) as f:
                    telemetry = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        def _actual_tokens_for_story(sid):
            total = sum(
                e.get("in_tokens", 0) + e.get("out_tokens", 0)
                for e in telemetry
                if e.get("story_id") == sid
            )
            return total if total > 0 else None

        for story_id, title, est_tokens in stories:
            actual = _actual_tokens_for_story(story_id)
            has_rating = conn.execute(
                "SELECT id FROM capability_ratings WHERE story_id=? AND correct=1 LIMIT 1",
                (story_id,)
            ).fetchone()
            entry = {
                "story_id": story_id,
                "title": title,
                "estimated_tokens": est_tokens,
                "actual_tokens": actual,
            }
            if has_rating:
                recently_completed.append(entry)
            else:
                in_progress.append(entry)
        conn.close()
    except Exception:
        pass

    top_todo = None
    todo_path = os.path.join(_pkg("_docs_dir")(), "todo.md")
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[\s*\]', line):
                    top_todo = re.sub(r'\s*-\s*\[\s*\]\s*', '', line).strip()
                    top_todo = re.sub(r'<!--.*?-->', '', top_todo).strip()
                    break

    return {
        "members": members,
        "in_progress": in_progress[:5],
        "recently_completed": recently_completed[:3],
        "top_todo": top_todo,
    }


def cmd_join() -> None:
    """Onboards the current user to an existing synlynk project."""
    docs_dir = _pkg("_docs_dir")()
    if not os.path.exists(docs_dir):
        print("Error: project not initialized — run 'synlynk init' first")
        sys.exit(1)

    username = _pkg("get_username")()
    if not username:
        print("Error: git config user.name not set — run: git config user.name 'Your Name'")
        sys.exit(1)

    print(f"  {_GREEN}▶{_RESET} Joining project as @{username}...")

    arch_context = ""
    try:
        _pkg("cmd_scan")(no_tui=True)
        ctx_path = ".synlynk/context.md"
        if os.path.exists(ctx_path):
            arch_context = open(ctx_path).read()[:2000]
    except Exception:
        pass

    git_summary = ""
    try:
        git_summary = subprocess.check_output(
            ["git", "log", "--oneline", "-20"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except subprocess.CalledProcessError:
        pass

    _pkg("_generate_ai_context_files")(arch_context, git_summary)
    print(f"  {_GREEN}✓{_RESET} Updated CLAUDE.md, GEMINI.md, AGENTS.md")

    _pkg("_seed_devlog")(username)
    print(f"  {_GREEN}✓{_RESET} Seeded devlog at {docs_dir}/devlogs/{username}.md")

    config_path = os.path.join(docs_dir, ".synlynk_config.json")
    try:
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
        cfg["mode"] = "team"
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

    print(f"  {_GREEN}✓{_RESET} Joined project as @{username}\n")

    digest = _build_team_digest()

    n = len(digest["members"])
    print(f"TEAM ({n} member{'s' if n != 1 else ''})")
    for m in digest["members"]:
        flag = ("· joined now"
                if m["user"] == username and m["stories_shipped"] <= 1
                else f"· {m['stories_shipped']} entries")
        print(f"  @{m['user']:<12} · last active {m['last_active']}  {flag}")

    if digest["in_progress"]:
        print("\nIN PROGRESS")
        for s in digest["in_progress"]:
            est = (f"~{s['estimated_tokens']:,} tokens est"
                   if s["estimated_tokens"] else "no budget set")
            print(f"  {s['story_id']}  {(s['title'] or '')[:40]}   {est}")

    if digest["top_todo"]:
        print(f"\nRECOMMENDED FIRST TASK\n  → {digest['top_todo']}")
    print()


def cmd_team_status() -> None:
    """Prints a full team digest: members, stories, budget, top todo."""
    project_name = os.path.basename(os.path.abspath("."))
    mode = _pkg("get_mode")()
    print(f"\nTEAM STATUS · {project_name} · {mode} mode\n")

    digest = _build_team_digest()

    print(f"MEMBERS ({len(digest['members'])})")
    for m in digest["members"]:
        last = m["last_active"]
        if last == time.strftime("%Y-%m-%d"):
            last = "today"
        print(f"  @{m['user']:<12} · last active {last:<14} · {m['stories_shipped']} entries")

    if digest["in_progress"]:
        print("\nIN-PROGRESS STORIES")
        for s in digest["in_progress"]:
            est = (f"~{s['estimated_tokens']:,} est"
                   if s["estimated_tokens"] else "no budget set")
            act = (f"· {s['actual_tokens']:,} actual so far"
                   if s["actual_tokens"] else "")
            print(f"  {s['story_id']}  {(s['title'] or '')[:40]}   {est} {act}")
    else:
        print("\nIN-PROGRESS STORIES\n  No in-progress stories")

    if digest["recently_completed"]:
        print("\nRECENTLY COMPLETED (last 7 days)")
        for s in digest["recently_completed"]:
            est = s["estimated_tokens"]
            act = s["actual_tokens"]
            if est and act:
                delta_pct = round((act - est) / est * 100)
                sign = "+" if delta_pct >= 0 else ""
                delta_str = f"{est:,} est · {act:,} actual ({sign}{delta_pct}%)"
            elif act:
                delta_str = f"{act:,} actual"
            else:
                delta_str = "no data"
            print(f"  {s['story_id']:<14} {(s['title'] or '')[:38]:<40} {delta_str}")

    if digest["top_todo"]:
        print(f"\nTOP TODO\n  → {digest['top_todo']}")
    print()


def cmd_identity_init() -> None:
    key_path = _ensure_identity_key()
    pub_path = key_path + ".pub"
    print(f"  identity key: {key_path}")
    if os.path.exists(pub_path):
        with open(pub_path) as fh:
            pub = fh.read().strip()
        print(f"  Public key: {pub}")
    else:
        print("  (public key file not found)")


def cmd_identity_init_role(role: str, project=None) -> None:
    app_dir, json_path, pem_path = _role_app_paths(role)
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
        if existing.get("installation_id") and existing.get("private_key_path") and os.path.exists(existing["private_key_path"]):
            print(f"  role '{role}' already provisioned at {json_path}")
            return

    manifest_url = _build_app_manifest_url(project, role)
    print(f"  Open this GitHub App manifest URL for '{role}':")
    print(f"  {manifest_url}")
    code = _extract_manifest_code(input("Paste the manifest callback URL or code: "))
    if not code:
        raise RuntimeError("no manifest code provided")

    conversion = _exchange_manifest_code(code)
    conversion.setdefault("slug", conversion.get("name", _role_slug(role)))
    conversion["private_key_path"] = str(pem_path)
    config = _write_role_app_config(role, conversion)
    _confirm_installation(config["app_slug"], json_path)
    print(f"  role '{role}' provisioned at {json_path}")

    from synlynk.identity_roles import load_declared_roles, write_declared_roles

    declared = load_declared_roles()
    if role not in declared:
        write_declared_roles(declared + [role])
        print(f"  ✓ added '{role}' to .synlynk/roles.yaml")


def cmd_identity_list() -> None:
    """List every declared role's GitHub App identity provisioning status."""
    from synlynk.identity_roles import load_declared_roles

    roles = load_declared_roles()
    print(f"\n  {'role':<14}  {'app_slug':<24}  status")
    print(f"  {'─' * 14}  {'─' * 24}  {'─' * 20}")
    for role in roles:
        json_path = os.path.join(".synlynk", "github_apps", f"{role}.json")
        if not os.path.exists(json_path):
            print(f"  {role:<14}  {'—':<24}  not provisioned")
            continue
        with open(json_path) as fh:
            config = json.load(fh)
        slug = config.get("app_slug", "—")
        status = "provisioned" if config.get("installation_id") else "pending installation"
        print(f"  {role:<14}  {slug:<24}  {status}")
    print()
