"""Vizor onboarding pages and GitHub App manifest conversion."""
import html
import json
import os
from pathlib import Path
def get_role_manifest_payload(
    role: str,
    repo_name: str = "workspace",
    port: int = 27472,
    org: str = "",
    project_slug: str = "",
    owner: str = "",
) -> dict:
    """Generate GitHub App Manifest payload for a specific workspace role."""
    role = role.lower()
    permissions = {
        "metadata": "read",
        "contents": "write",
        "pull_requests": "write",
        "issues": "write",
    }
    if role in ("qa", "dev", "infra"):
        permissions["checks"] = "write"
        permissions["statuses"] = "write"

    slug = project_slug or repo_name
    owner_str = (owner or org or "").lower().strip()

    role_abbr = {
        "architect": "arch",
        "marketing": "mktg",
    }.get(role, role)

    prefix = "syn"

    if owner_str:
        # Format: syn-{owner}-{slug}-{role}
        # Fixed: prefix (3) + 3 hyphens + role_abbr = 6 + len(role_abbr)
        avail = 34 - len(prefix) - len(role_abbr) - 3
        if len(owner_str) + len(slug) > avail:
            capped_owner = owner_str[:10].rstrip("-")
            avail_slug = max(1, avail - len(capped_owner))
            clean_slug = slug[:avail_slug].rstrip("-")
            app_name = f"{prefix}-{capped_owner}-{clean_slug}-{role_abbr}"
        else:
            app_name = f"{prefix}-{owner_str}-{slug}-{role_abbr}"
    else:
        # Format: syn-{slug}-{role}
        avail_slug = 34 - len(prefix) - len(role_abbr) - 2
        clean_slug = slug[:avail_slug].rstrip("-")
        app_name = f"{prefix}-{clean_slug}-{role_abbr}"

    if len(app_name) > 34:
        app_name = app_name[:34].rstrip("-")

    return {
        "name": app_name,
        "url": "https://synlynk.com",
        "hook_attributes": {
            "url": f"https://synlynk.com/github-apps/{slug}/{role}/webhook",
            "active": False,
        },
        "redirect_url": (
            f"http://localhost:{port}/auth/callback?role={role}&state={slug}"
            if project_slug else f"http://localhost:{port}/auth/callback?role={role}"
        ),
        "public": False,
        "default_permissions": permissions,
        "default_events": [],
    }


def handle_github_app_conversion(code: str, role: str, repo_root: str = ".") -> dict:
    """Exchange GitHub App manifest conversion code and write credentials."""
    import urllib.request
    from pathlib import Path

    url = f"https://api.github.com/app-manifests/{code}/conversions"
    req = urllib.request.Request(url, method="POST", headers={"Accept": "application/vnd.github+json"})

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    app_id = data.get("id")
    pem = data.get("pem")

    root = Path(repo_root).resolve()
    role_dir = root / ".synlynk" / "github_apps" / role
    role_dir.mkdir(parents=True, exist_ok=True)

    app_json_path = role_dir / f"{role}.app.json"
    pem_path = role_dir / f"{role}.private-key.pem"

    app_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if pem:
        pem_path.write_text(pem, encoding="utf-8")
    os.chmod(str(app_json_path), 0o600)
    if pem_path.exists():
        os.chmod(str(pem_path), 0o600)

    # Also persist standard flat files expected by synlynk doctor and team.py
    apps_dir = root / ".synlynk" / "github_apps"
    legacy_json_path = apps_dir / f"{role}.json"
    legacy_pem_path = apps_dir / f"{role}.pem"
    if pem:
        legacy_pem_path.write_text(pem, encoding="utf-8")
        try:
            os.chmod(str(legacy_pem_path), 0o600)
        except OSError:
            pass

    flat_config = {
        "role": role,
        "app_id": app_id,
        "client_id": data.get("client_id"),
        "app_slug": data.get("slug") or data.get("name") or role,
        "installation_id": data.get("installation_id"),
        "private_key_path": str(legacy_pem_path if legacy_pem_path.exists() else pem_path),
    }
    legacy_json_path.write_text(json.dumps(flat_config, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(str(legacy_json_path), 0o600)
    except OSError:
        pass

    try:
        from synlynk.github_app_auth import refresh_installation_token
        from synlynk.product_store import resolve_github_apps_dir
        refresh_installation_token(role, apps_dir=str(resolve_github_apps_dir(str(root))))
    except Exception:
        pass

    return {"ok": True, "role": role, "app_id": app_id, "slug": data.get("slug")}


def generate_onboarding_html(data: dict = None, port: int = 27472) -> str:
    """Generate self-contained HTML for onboarding 3-view canvas and artifact tour."""
    import html as _html

    data = data or {}
    industry = _html.escape(data.get("domain", {}).get("industry", "Application Service"))

    try:
        from synlynk.coldstart import get_onboarding_recommendations
        recs = get_onboarding_recommendations()
    except Exception:
        recs = []

    recs_cards = []
    for rec in recs:
        name = _html.escape(str(rec.get("name", "")))
        label = _html.escape(str(rec.get("label", name)))
        desc = _html.escape(str(rec.get("description", "")))
        installed = rec.get("installed", False)
        if installed:
            recs_cards.append(f"""
    <div class="tool-item installed" style="background: #161b22; border: 1px solid #238636; border-radius: 8px; padding: 14px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <input type="checkbox" id="tool-{name}" checked disabled style="width: 18px; height: 18px; accent-color: #238636;" />
        <div>
          <label for="tool-{name}" style="font-weight: 600; color: #f0f3f6;">{label}</label>
          <div style="font-size: 13px; color: #8b949e; margin-top: 2px;">{desc}</div>
        </div>
      </div>
      <span class="badge" style="background: #238636; font-size: 12px; padding: 4px 8px; border-radius: 4px; color: #fff;">Installed</span>
    </div>""")
        else:
            recs_cards.append(f"""
    <div class="tool-item recommended" style="background: #161b22; border: 1px solid #388bfd; border-radius: 8px; padding: 14px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <input type="checkbox" id="tool-{name}" checked style="width: 18px; height: 18px; accent-color: #1f6feb;" />
        <div>
          <label for="tool-{name}" style="font-weight: 600; color: #f0f3f6; cursor: pointer;">{label}</label>
          <div style="font-size: 13px; color: #8b949e; margin-top: 2px;">{desc}</div>
        </div>
      </div>
      <form method="POST" action="/tools/install" style="margin: 0;">
        <input type="hidden" name="tool" value="{name}" />
        <button type="submit" class="btn-install" style="background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;">1-Click Install</button>
      </form>
    </div>""")

    tools_html = "".join(recs_cards) if recs_cards else "<p style='color: #8b949e;'>All recommended ecosystem tools are installed.</p>"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Synlynk Onboarding Canvas</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #0f1419; color: #f0f3f6; }}
    .header {{ padding: 20px; border-bottom: 1px solid #21262d; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; padding: 20px; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
    .badge {{ background: #1f6feb; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
    .tour {{ margin: 20px; padding: 16px; background: #0d1117; border: 1px solid #238636; border-radius: 8px; }}
    .recommendations {{ margin: 20px; padding: 16px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Synlynk Onboarding — {industry}</h1>
    <span class="badge">Local Offline Canvas</span>
  </div>
  <div class="grid">
    <div class="card"><h3>View 1: Physical File Tree</h3><p>Directories, frameworks, and component boundaries.</p></div>
    <div class="card"><h3>View 2: Logical Tubemap</h3><p>Data streams and entity lifecycles.</p></div>
    <div class="card"><h3>View 3: Application Screens</h3><p>Discovered routes and cloud topology.</p></div>
    <div class="card" id="S1_Orientation"><h3>S1_Orientation</h3><p>Welcome to Synlynk.</p></div>
    <div class="card" id="S2_Dependencies"><h3>S2_Dependencies</h3><p>Ecosystem Tools.</p></div>
    <div class="card" id="S3_HarnessBinding"><h3>S3_HarnessBinding</h3><p>Harness Binding.</p></div>
    <div class="card" id="S4_TopologyConfirmation"><h3>S4_TopologyConfirmation</h3><p>Topology.</p></div>
    <div class="card" id="S5_GovernsIntro"><h3>S5_GovernsIntro</h3><p>Governance.</p></div>
    <div class="card" id="S6_DispatchDecide"><h3>S6_DispatchDecide</h3><p>Dispatch Rules.</p></div>
    <div class="card" id="S7_AgentTeam"><h3>S7_AgentTeam</h3><p>Agent Team.</p></div>
    <div class="card" id="S8_FleetTemplates"><h3>S8_FleetTemplates</h3><p>Fleet Templates.</p></div>
    <div class="card" id="S9_FirstWinIntake"><h3>S9_FirstWinIntake</h3><p>First Win Intake.</p></div>
    <div class="card" id="S10_BuildExperience"><h3>S10_BuildExperience</h3><p>First-Win Loop.</p></div>
  </div>
  <div class="recommendations">
    <h2>Recommended Ecosystem Tools &amp; Substrates</h2>
    <p style="color: #8b949e; font-size: 14px; margin-bottom: 16px;">Synlynk is a neutral control plane that routes coding tasks across AI vendors and local models, then proves the result.</p>
    {tools_html}
  </div>
  <div class="tour">
    <h2>Behind the Curtain: The Coordination Substrate</h2>
    <ul>
      <li><strong>state.db:</strong> SQLite persistent ledger tracking goals, stories, and jobs.</li>
      <li><strong>.synlynk/context.md:</strong> Real-time situational awareness snapshot.</li>
      <li><strong>project-docs/:</strong> Living 4-doc governance (roadmap.md, todo.md, memory.md, devlogs/).</li>
      <li><strong>.worktrees/:</strong> Clean, isolated task execution sandboxes.</li>
    </ul>
  </div>
</body>
</html>"""



def generate_roles_onboarding_html(repo_root: str = ".", port: int = 27472) -> str:
    """Generate in-browser role provisioning wizard HTML."""
    from pathlib import Path
    import html as _html

    root = Path(repo_root).resolve()
    repo_name = root.name
    roles_dir = root / ".synlynk" / "github_apps"

    owner_type = "user"
    owner_login = ""
    project_slug = repo_name
    try:
        from synlynk.team import _resolve_repo_owner
        owner_type, owner_login = _resolve_repo_owner(cwd=str(root))
    except Exception:
        pass

    owner_slug = ""
    try:
        cfg_path = root / ".synlynk" / "config.json"
        if cfg_path.exists():
            cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if cfg_data.get("identity_slug"):
                project_slug = cfg_data["identity_slug"]
            elif cfg_data.get("repo"):
                project_slug = cfg_data["repo"]
            if cfg_data.get("owner_slug"):
                owner_slug = cfg_data["owner_slug"]
    except Exception:
        pass

    effective_owner = owner_slug or owner_login
    org_name = owner_login if owner_type == "org" else ""
    form_action = (
        f"https://github.com/organizations/{owner_login}/settings/apps/new"
        if owner_type == "org" and owner_login
        else "https://github.com/settings/apps/new"
    )

    roles_info = [
        ("pm", "Program Manager", "claude", "Roadmap, goal tracking, issue triage, and named release narratives."),
        ("tpm", "Technical Program Manager", "claude", "Milestone execution loop, cross-harness sweeps, and dependency tracking."),
        ("qa", "QA Engineer", "claude", "Autonomous PR review, test validation, and merge-gate authority."),
        ("dev", "Software Developer", "codex", "Core implementation, tests, bugfixes, refactoring, and PR creation."),
        ("architect", "Lead Architect", "claude", "System architecture, specifications, technical decisions, and charter governance."),
        ("marketing", "Marketing Engineer", "agy", "Release communications, documentation compilation, and build diary blogs."),
        ("infra", "DevOps & Infrastructure", "grok", "Pulumi IaC, AWS cloud resource management, and CI/CD pipelines."),
    ]

    cards_html = []
    for slug, title, default_harness, desc in roles_info:
        role_app = roles_dir / slug / f"{slug}.app.json"
        legacy_role_app = roles_dir / f"{slug}.json"
        is_configured = role_app.exists() or legacy_role_app.exists()

        conf = {}
        if legacy_role_app.exists():
            try:
                conf = json.loads(legacy_role_app.read_text(encoding="utf-8"))
            except Exception:
                pass
        elif role_app.exists():
            try:
                conf = json.loads(role_app.read_text(encoding="utf-8"))
            except Exception:
                pass

        installation_id = conf.get("installation_id")
        app_slug = conf.get("app_slug") or conf.get("slug") or slug

        if is_configured and installation_id:
            badge = '<span class="badge configured">✓ Installed & Active</span>'
            btn_html = '<button class="btn configured-btn" disabled>Active Role</button>'
            app_name_display = app_slug
        elif is_configured:
            badge = '<span class="badge configured" style="background:#f59e0b;color:#000;">Pending Installation</span>'
            btn_html = f'''<div style="display:flex;gap:8px;flex-direction:column;">
                <a href="https://github.com/apps/{app_slug}/installations/new" target="_blank" class="btn primary-btn" style="text-align:center;text-decoration:none;padding:8px 12px;">Install on GitHub ↗</a>
                <a href="/auth/sync?role={slug}" class="btn" style="text-align:center;text-decoration:none;padding:8px 12px;background:#283044;color:#f0f3f8;">Sync Installation ID</a>
            </div>'''
            app_name_display = app_slug
        else:
            badge = '<span class="badge unconfigured">Not Configured</span>'
            manifest = get_role_manifest_payload(
                slug,
                repo_name=repo_name,
                port=port,
                org=org_name,
                project_slug=project_slug,
                owner=effective_owner,
            )
            app_name_display = manifest.get("name", "")
            manifest_json = json.dumps(manifest)
            escaped = _html.escape(manifest_json, quote=True)
            btn_html = f'''<form action="{form_action}" method="POST" target="_blank">
                <input type="hidden" name="manifest" value="{escaped}">
                <button type="submit" class="btn primary-btn">Provision with GitHub</button>
            </form>'''

        cards_html.append(f'''
        <div class="role-card">
            <div class="card-header">
                <h3>{title} (<code>{slug}</code>)</h3>
                {badge}
            </div>
            <p class="role-desc">{desc}</p>
            <div class="role-meta">Default Harness: <strong>{default_harness}</strong> &bull; App: <code>{app_name_display}</code></div>
            <div class="card-actions">
                {btn_html}
            </div>
        </div>
        ''')

    cards_joined = "".join(cards_html)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>synlynk Vizor — Workspace Role Provisioning Wizard</title>
    <style>
        :root {{
            --bg-base: #0f1117;
            --bg-card: #181c27;
            --border: #283044;
            --text-main: #f0f3f8;
            --text-muted: #8b9bb4;
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --green: #10b981;
            --yellow: #f59e0b;
        }}
        body {{
            background: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 32px;
        }}
        header {{
            max-width: 1100px;
            margin: 0 auto 32px auto;
        }}
        h1 {{
            font-size: 28px;
            margin: 0 0 8px 0;
            color: #fff;
        }}
        p.subtitle {{
            color: var(--text-muted);
            margin: 0;
            font-size: 15px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            max-width: 1100px;
            margin: 0 auto 32px auto;
        }}
        .role-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .card-header h3 {{
            margin: 0;
            font-size: 18px;
        }}
        .badge {{
            font-size: 12px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        .badge.configured {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--green);
            border: 1px solid var(--green);
        }}
        .badge.unconfigured {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--yellow);
            border: 1px solid var(--yellow);
        }}
        .role-desc {{
            color: var(--text-muted);
            font-size: 14px;
            line-height: 1.5;
            margin: 0 0 16px 0;
        }}
        .role-meta {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }}
        .btn {{
            width: 100%;
            padding: 10px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            font-size: 14px;
            transition: all 0.2s ease;
        }}
        .primary-btn {{
            background: var(--accent);
            color: #fff;
        }}
        .primary-btn:hover {{
            background: var(--accent-hover);
        }}
        .configured-btn {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            cursor: default;
        }}
        .readiness-card {{
            max-width: 1100px;
            margin: 0 auto;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
        }}
        .readiness-card h2 {{
            margin-top: 0;
            font-size: 20px;
        }}
        .point-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        .point-row:last-child {{
            border-bottom: none;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Workspace Role Provisioning Wizard</h1>
        <p class="subtitle">1-Click GitHub App provisioning for autonomous fleet agents in <strong>{repo_name}</strong>.</p>
    </header>

    <div class="grid">
        {cards_joined}
    </div>

    <div class="readiness-card">
        <h2>Live 4-Point Fleet Readiness Matrix</h2>
        <div id="readiness-container">Loading live readiness points...</div>
    </div>

    <script>
        async function fetchReadiness() {{
            try {{
                const res = await fetch('/api/readiness/live');
                const data = await res.json();
                const container = document.getElementById('readiness-container');
                if (!data.points) return;
                let html = '';
                for (const p of data.points) {{
                    const color = p.status === 'PASS' ? '#10b981' : (p.status === 'WARN' ? '#f59e0b' : '#ef4444');
                    html += `<div class="point-row">
                        <span><strong>${{p.name}}</strong>: ${{p.message}}</span>
                        <span style="color: ${{color}}; font-weight: 600;">${{p.status}}</span>
                    </div>`;
                }}
                container.innerHTML = html;
            }} catch (err) {{
                console.error('Readiness poll error:', err);
            }}
        }}
        fetchReadiness();
        setInterval(fetchReadiness, 3000);
    </script>
</body>
</html>'''

