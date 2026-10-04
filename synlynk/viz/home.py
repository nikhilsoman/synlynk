"""Vizor index / home canvas."""
import html
import json
from synlynk.viz.chrome import _live_js
def generate_index_html(data: dict, port: int) -> str:
    """Generate the master Vizor shell with two-tier accordion and location breadcrumbs."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # Calculate open stories count for active workspace
    open_stories = 0
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                st = str(task.get("status") or "").lower()
                if st in ("active", "ready", "open", "in_progress", "todo", "in progress"):
                    open_stories += 1
    if open_stories == 0:
        repos = workspace.get("repos") or []
        if repos and isinstance(repos[0], dict):
            open_stories = int(repos[0].get("active_dream_count") or 0)

    # Registered workspaces for accordion
    try:
        from synlynk.state_registry import _read_unlocked, registry_path
        rpath = registry_path()
        reg_products = _read_unlocked(rpath).get("products", {}) if rpath.exists() else {}
        other_slugs = [s for s in sorted(reg_products.keys()) if s != workspace_name]
    except Exception:
        other_slugs = []

    other_ws_html = "".join(f"""
        <details name="workspace" class="ws-accordion">
          <summary class="ws-summary" onclick="window.location.href='/w/{html.escape(s)}/index.html';">
            <span class="ws-chevron">▸</span>
            <span class="ws-name">{html.escape(s)}</span>
          </summary>
        </details>
    """ for s in other_slugs)

    style_content = """
    :root {
      --bg:        #f6f8fa;  --bg2: #ffffff; --bg3: #eaeef2;
      --border:    #d1d5db;  --border2: #e8ebee;
      --text:      #1f2328;  --text2: #57606a; --text3: #8b949e;
      --accent:    #0d9e87;  --accent-bg: #e6f7f4; --accent-dim: #c0ede6;
      --shadow:    0 2px 12px rgba(0,0,0,.10);

      --s-dream-bg:#ede9fe; --s-dream-bd:#c4b5fd; --s-dream-tx:#6d28d9;
      --s-plan-bg: #dbeafe; --s-plan-bd: #93c5fd; --s-plan-tx: #1d4ed8;
      --s-work-bg: #dcfce7; --s-work-bd: #86efac; --s-work-tx: #15803d;
      --s-ship-bg: #ffedd5; --s-ship-bd: #fdba74; --s-ship-tx: #c2410c;
      --s-maint-bg:#e0e7ff; --s-maint-bd:#a5b4fc; --s-maint-tx:#4338ca;
      --s-engage-bg:#fce7f3;--s-engage-bd:#f9a8d4;--s-engage-tx:#be185d;

      --ag-claude-bg:#e6f7f4;--ag-claude-bd:#0d9e87;--ag-claude-tx:#0d9e87;
      --ag-agy-bg:  #e8f0fe;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #1a56c7;
      --ag-codex-bg:#e6f4f0;--ag-codex-bd:#10a37f;--ag-codex-tx:#0b7a60;
      --ag-grok-bg: #f0f0f0;--ag-grok-bd: #666;   --ag-grok-tx: #333;
      --ag-muse-bg: #fdf2f8;--ag-muse-bd: #db2777;--ag-muse-tx: #9d174d;
    }
    [data-theme="dark"] {
      --bg:#0d0f14; --bg2:#0a0c10; --bg3:#13171f;
      --border:#1e2430; --border2:#13171f;
      --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
      --accent:#3de0c0; --accent-bg:#0d2137; --accent-dim:#0a3050;
      --shadow: 0 2px 20px rgba(0,0,0,.5);

      --s-dream-bg:#2d1f5e;--s-dream-bd:#4a3f80;--s-dream-tx:#a78bfa;
      --s-plan-bg: #1e3a5a;--s-plan-bd: #3a6090;--s-plan-tx: #60a5fa;
      --s-work-bg: #1a4a2e;--s-work-bd: #2a7040;--s-work-tx: #4ade80;
      --s-ship-bg: #5a3a00;--s-ship-bd: #8a5a00;--s-ship-tx: #fb923c;
      --s-maint-bg:#1e2a4a;--s-maint-bd:#3a4a80;--s-maint-tx:#818cf8;
      --s-engage-bg:#3a1a3a;--s-engage-bd:#6a2a6a;--s-engage-tx:#f472b6;

      --ag-claude-bg:#0d2a2a;--ag-claude-bd:#3de0c0;--ag-claude-tx:#3de0c0;
      --ag-agy-bg:  #0d1a3a;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #4285f4;
      --ag-codex-bg:#0a1f18;--ag-codex-bd:#10a37f;--ag-codex-tx:#10a37f;
      --ag-grok-bg: #1a1a1a;--ag-grok-bd: #e0e0e0;--ag-grok-tx: #e0e0e0;
      --ag-muse-bg: #2e081d;--ag-muse-bd: #f472b6;--ag-muse-tx: #f472b6;
    }

    * { box-sizing:border-box; margin:0; padding:0; }
    html, body { height:100%; }
    body {
      display:flex;
      height:100vh;
      margin:0;
      overflow:hidden;
      font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 'SF Mono', monospace;
      background:var(--bg);
      color:var(--text);
      font-size:13px;
      transition:background .2s,color .2s;
    }
    a { color:inherit; text-decoration:none; }
    button { font:inherit; }

    .shell {
      display:flex;
      height:100vh;
      width:100%;
      overflow:hidden;
    }
    .sidenav {
      width:260px;
      min-width:260px;
      flex-shrink:0;
      background:var(--bg2);
      border-right:1px solid var(--border);
      display:flex;
      flex-direction:column;
      overflow:hidden;
    }
    .nav-header {
      padding:14px 16px;
      border-bottom:1px solid var(--border);
      display:flex;
      align-items:center;
      justify-content:space-between;
    }
    .nav-brand {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .logo-badge {
      background:var(--accent);
      color:#fff;
      font-weight:800;
      font-size:11px;
      padding:3px 6px;
      border-radius:4px;
      letter-spacing:.5px;
    }
    .brand-title {
      font-size:14px;
      font-weight:700;
      color:var(--text);
      letter-spacing:-.3px;
    }
    .nav-section {
      flex:1;
      overflow-y:auto;
      padding:8px 0;
    }

    /* Accordion Styles */
    .tier-accordion {
      margin-bottom:2px;
      border-bottom:1px solid var(--border2);
    }
    .tier-summary {
      display:flex;
      align-items:center;
      gap:8px;
      padding:10px 14px;
      font-weight:700;
      font-size:11px;
      letter-spacing:.8px;
      cursor:pointer;
      user-select:none;
    }
    .tier-summary::-webkit-details-marker { display:none; }
    .tier-personal > .tier-summary {
      background:rgba(13,158,135,0.12);
      color:var(--accent);
    }
    .tier-team > .tier-summary, .tier-enterprise > .tier-summary {
      background:rgba(59,130,246,0.10);
      color:#60a5fa;
    }
    .tier-chevron { font-size:10px; width:12px; }
    .stub-badge {
      margin-left:auto;
      font-size:9px;
      font-weight:500;
      opacity:.75;
      padding:1px 5px;
      border-radius:4px;
      background:rgba(255,255,255,0.08);
    }
    .stub-panel {
      padding:16px 14px;
      background:var(--bg3);
      color:var(--text2);
      text-align:center;
      font-size:11px;
      border-top:1px solid var(--border);
    }
    .stub-icon { font-size:18px; margin-bottom:4px; }
    .stub-sub { font-size:10px; color:var(--text3); margin-top:4px; }

    .tier-content {
      background:var(--bg2);
    }

    /* Workspace Accordion */
    .ws-accordion {
      border-bottom:1px solid var(--border);
    }
    .ws-summary {
      display:flex;
      align-items:center;
      gap:6px;
      padding:8px 14px;
      font-size:12px;
      font-weight:600;
      cursor:pointer;
      background:var(--bg3);
      color:var(--text);
    }
    .ws-summary::-webkit-details-marker { display:none; }
    .ws-chevron { font-size:9px; width:10px; color:var(--text3); }
    .ws-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .count-badge {
      font-size:10px;
      font-weight:700;
      background:var(--accent-bg);
      color:var(--accent);
      padding:1px 6px;
      border-radius:8px;
    }
    .ws-content {
      padding:4px 0 8px;
    }

    .nav-category-header {
      font-size:10px;
      font-weight:700;
      text-transform:uppercase;
      letter-spacing:.8px;
      color:var(--text3);
      padding:8px 16px 4px;
    }
    .nav-link {
      padding:6px 12px 6px 20px;
      display:flex;
      align-items:center;
      gap:8px;
      cursor:pointer;
      border-radius:5px;
      margin:1px 8px;
      color:var(--text2);
      font-size:12px;
      line-height:1.2;
      user-select:none;
    }
    .nav-link:hover { background:var(--bg3); color:var(--text); }
    .nav-link.active { background:var(--accent-bg); color:var(--accent); font-weight:600; }
    .nav-icon { width:16px; text-align:center; flex-shrink:0; font-size:12px; }
    .nav-label { white-space:nowrap; }

    .nav-footer {
      border-top:1px solid var(--border);
      padding:10px 14px;
      background:var(--bg2);
    }
    .theme-sw { display:flex; gap:4px; margin-bottom:8px; }
    .theme-btn {
      flex:1;
      padding:4px 0;
      border-radius:5px;
      font-size:10px;
      text-align:center;
      cursor:pointer;
      border:1px solid var(--border);
      color:var(--text3);
      background:transparent;
    }
    .theme-btn:hover { border-color:var(--accent); color:var(--accent); }
    .theme-btn.active { background:var(--accent-bg); border-color:var(--accent); color:var(--accent); font-weight:700; }

    .avatar-row {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .avatar {
      width:22px;
      height:22px;
      border-radius:50%;
      background:linear-gradient(135deg,var(--accent),#0b7a60);
      display:flex;
      align-items:center;
      justify-content:center;
      font-size:10px;
      font-weight:800;
      color:#fff;
      flex-shrink:0;
    }
    .avatar-name {
      font-size:11px;
      color:var(--text2);
      flex:1;
      min-width:0;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }

    /* Main Area */
    .main {
      flex:1;
      display:flex;
      flex-direction:column;
      overflow:hidden;
      min-width:0;
    }
    .main-topbar {
      background:var(--bg2);
      border-bottom:1px solid var(--border);
      padding:8px 20px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      min-height:42px;
    }
    .breadcrumbs {
      display:flex;
      align-items:center;
      gap:6px;
      font-size:12px;
      color:var(--text2);
    }
    .crumb-link { color:var(--text2); font-weight:500; }
    .crumb-link:hover { color:var(--accent); text-decoration:underline; }
    .crumb-sep { color:var(--text3); font-size:11px; }
    .crumb-cat { color:var(--text3); font-weight:600; text-transform:uppercase; font-size:11px; letter-spacing:.5px; }
    .crumb-current { color:var(--text); font-weight:600; }

    .corner-actions {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .corner-btn {
      background:transparent;
      border:1px solid var(--border);
      border-radius:6px;
      padding:4px 8px;
      cursor:pointer;
      color:var(--text2);
      display:flex;
      align-items:center;
      justify-content:center;
      transition:all 0.15s ease;
    }
    .corner-btn:hover { border-color:var(--accent); color:var(--accent); background:var(--bg3); }
    .corner-link {
      font-size:11px;
      font-weight:600;
      color:var(--accent);
      padding:4px 8px;
      border-radius:6px;
      background:var(--accent-bg);
      border:1px solid var(--accent);
    }
    .corner-link:hover { opacity:0.9; }

    iframe#view-frame {
      flex:1;
      border:none;
      width:100%;
      background:var(--bg);
    }
    .status-bar {
      background:var(--bg2);
      border-top:1px solid var(--border);
      padding:5px 20px;
      display:flex;
      align-items:center;
      gap:10px;
      font-size:11px;
      color:var(--text3);
      flex-shrink:0;
      min-height:28px;
    }
    .status-dot { color:var(--accent); }
    .status-workspace { color:var(--text2); font-weight:600; }
    .status-updated { margin-left:auto; }
    """

    meta_json = json.dumps({"port": port, "updated_at": updated_at})
    avatar_label = (workspace_name[:1] or "S").upper()

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Shell</title>
<script>window.VIZOR_META = {meta_json};</script>
<style>{style_content}</style>
</head>
<body>
<div class="shell">
  <aside class="sidenav">
    <div class="nav-header">
      <div class="nav-brand">
        <span class="logo-badge">VIZOR</span>
        <span class="brand-title">synlynk</span>
      </div>
    </div>
    <div class="nav-section">
      <!-- Tier 1: Personal -->
      <details name="tier1" class="tier-accordion tier-personal" open>
        <summary class="tier-summary">
          <span class="tier-chevron">▾</span>
          <span>PERSONAL</span>
        </summary>
        <div class="tier-content">
          <!-- Active Workspace -->
          <details name="workspace" class="ws-accordion" open>
            <summary class="ws-summary">
              <span class="ws-chevron">▾</span>
              <span class="ws-name">{html.escape(workspace_name)}</span>
              <span class="count-badge">{open_stories}</span>
            </summary>
            <div class="ws-content">
              <a class="nav-link active" href="overview.html" data-view="overview" data-cat="Overview" data-label="Overview">
                <span class="nav-icon">📊</span>
                <span class="nav-label">Overview</span>
              </a>

              <div class="nav-category-header">STATUS</div>
              <a class="nav-link" href="board.html" data-view="board" data-cat="STATUS" data-label="Board">
                <span class="nav-icon">▦</span>
                <span class="nav-label">Board</span>
              </a>
              <a class="nav-link" href="gantt.html" data-view="gantt" data-cat="STATUS" data-label="Gantt">
                <span class="nav-icon">📅</span>
                <span class="nav-label">Gantt</span>
              </a>

              <div class="nav-category-header">TOPOLOGIES</div>
              <a class="nav-link" href="tube.html" data-view="tube" data-cat="TOPOLOGIES" data-label="Architect Map">
                <span class="nav-icon">🚇</span>
                <span class="nav-label">Architect Map</span>
              </a>
              <a class="nav-link" href="infra.html" data-view="infra" data-cat="TOPOLOGIES" data-label="Infra View">
                <span class="nav-icon">⚙️</span>
                <span class="nav-label">Infra View</span>
              </a>

              <div class="nav-category-header">PROJECTIONS</div>
              <a class="nav-link" href="product.html" data-view="product" data-cat="PROJECTIONS" data-label="Product View">
                <span class="nav-icon">🗺</span>
                <span class="nav-label">Product View</span>
              </a>
              <a class="nav-link" href="logical.html" data-view="logical" data-cat="PROJECTIONS" data-label="Logical View">
                <span class="nav-icon">🧩</span>
                <span class="nav-label">Logical View</span>
              </a>
              <a class="nav-link" href="world.html" data-view="world" data-cat="PROJECTIONS" data-label="World View">
                <span class="nav-icon">🌐</span>
                <span class="nav-label">World View</span>
              </a>

              <div class="nav-category-header">TELEMETRY</div>
              <a class="nav-link" href="effort.html" data-view="effort" data-cat="TELEMETRY" data-label="Effort & Cost">
                <span class="nav-icon">💰</span>
                <span class="nav-label">Effort & Cost</span>
              </a>
              <a class="nav-link" href="efficiency.html" data-view="efficiency" data-cat="TELEMETRY" data-label="Efficiency">
                <span class="nav-icon">📊</span>
                <span class="nav-label">Efficiency</span>
              </a>
              <a class="nav-link" href="observatory.html" data-view="observatory" data-cat="TELEMETRY" data-label="Observatory">
                <span class="nav-icon">◉</span>
                <span class="nav-label">Observatory</span>
              </a>
              <a class="nav-link" href="roles.html" data-view="roles" data-cat="TELEMETRY" data-label="Agent Roles">
                <span class="nav-icon">🤖</span>
                <span class="nav-label">Agent Roles</span>
              </a>
            </div>
          </details>
          {other_ws_html}
        </div>
      </details>

      <!-- Tier 1: Team Stub -->
      <details name="tier1" class="tier-accordion tier-team">
        <summary class="tier-summary">
          <span class="tier-chevron">▸</span>
          <span>TEAM</span>
          <span class="stub-badge">Coming soon</span>
        </summary>
        <div class="stub-panel">
          <div class="stub-icon">🚧</div>
          <div>Team workspaces aren't set up yet.</div>
          <div class="stub-sub">Coming soon — invite teammates and share workspace views.</div>
        </div>
      </details>

      <!-- Tier 1: Enterprise Stub -->
      <details name="tier1" class="tier-accordion tier-enterprise">
        <summary class="tier-summary">
          <span class="tier-chevron">▸</span>
          <span>ENTERPRISE</span>
          <span class="stub-badge">Coming soon</span>
        </summary>
        <div class="stub-panel">
          <div class="stub-icon">🏢</div>
          <div>Enterprise workspaces coming soon.</div>
          <div class="stub-sub">Coming soon — SSO, audit logs, and fleet-wide policies.</div>
        </div>
      </details>
    </div>

    <div class="nav-footer">
      <div class="theme-sw">
        <button class="theme-btn" type="button" data-theme-mode="light">☀ Light</button>
        <button class="theme-btn" type="button" data-theme-mode="dark">☾ Dark</button>
        <button class="theme-btn active" type="button" data-theme-mode="system">⊙ System</button>
      </div>
      <div class="avatar-row">
        <div class="avatar">{html.escape(avatar_label)}</div>
        <div class="avatar-name">{html.escape(workspace_name)}</div>
      </div>
    </div>
  </aside>

  <main class="main">
    <header class="main-topbar">
      <nav class="breadcrumbs" id="breadcrumbs">
        <a class="crumb-link" href="activity.html" onclick="return setView('activity', 'activity.html', 'Personal', 'Activity Stream');">Personal</a>
        <span class="crumb-sep" id="crumb-sep-ws">›</span>
        <a class="crumb-link" href="overview.html" id="crumb-ws" onclick="return setView('overview', 'overview.html', '', 'Overview');">{html.escape(workspace_name)}</a>
        <span class="crumb-sep" id="crumb-sep-cat" style="display:none;">›</span>
        <span class="crumb-cat" id="crumb-cat" style="display:none;"></span>
        <span class="crumb-sep" id="crumb-sep-view" style="display:none;">›</span>
        <span class="crumb-current" id="crumb-view" style="display:none;"></span>
      </nav>
      <div class="corner-actions">
        <button class="corner-btn" type="button" title="Settings — GitHub & Harness Connections (Sub-project 2)" onclick="alert('Settings section coming in Sub-project 2 (GitHub OAuth, Provider connections, Backup/Restore)');">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </button>
        <button class="corner-btn" type="button" title="Guided Walkthrough (Sub-project 4)" onclick="alert('FTUE Guided Walkthrough coming in Sub-project 4');">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        </button>
        <a href="/" class="corner-link" title="Workspace Hub">Hub ↗</a>
      </div>
    </header>

    <iframe id="view-frame" src="overview.html" title="Synlynk Vizor view"></iframe>
    <div class="status-bar">
      <span class="status-dot">●</span>
      <span>local</span>
      <span>·</span>
      <span>offline-ready</span>
      <span>·</span>
      <span class="status-workspace">{html.escape(workspace_name)}</span>
      <span>·</span>
      <span class="status-updated">updated {html.escape(updated_at)}</span>
    </div>
  </main>
</div>

<script>
(function() {{
  const themeKey = 'vizor-theme';
  const themeButtons = Array.from(document.querySelectorAll('.theme-btn'));
  const viewFrame = document.getElementById('view-frame');
  const navLinks = Array.from(document.querySelectorAll('.nav-link'));

  function resolveTheme(theme) {{
    if (theme === 'system') {{
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }}
    return theme || 'light';
  }}

  function syncThemeButtons(theme) {{
    themeButtons.forEach((btn) => {{
      btn.classList.toggle('active', btn.dataset.themeMode === theme);
    }});
  }}

  function applyTheme(theme) {{
    const resolved = resolveTheme(theme);
    document.documentElement.setAttribute('data-theme', resolved);
    syncThemeButtons(theme);
  }}

  function setView(viewId, viewSrc, category, label) {{
    if (viewSrc && viewFrame) {{
      viewFrame.src = viewSrc;
    }}
    navLinks.forEach((link) => {{
      link.classList.toggle('active', link.dataset.view === viewId);
    }});

    const sepWs = document.getElementById('crumb-sep-ws');
    const wsEl = document.getElementById('crumb-ws');
    const sepCat = document.getElementById('crumb-sep-cat');
    const catEl = document.getElementById('crumb-cat');
    const sepView = document.getElementById('crumb-sep-view');
    const viewEl = document.getElementById('crumb-view');

    if (viewId === 'activity') {{
      if (sepWs) sepWs.style.display = 'none';
      if (wsEl) wsEl.style.display = 'none';
      if (sepCat) sepCat.style.display = 'inline';
      if (catEl) {{ catEl.style.display = 'inline'; catEl.textContent = 'ACTIVITY STREAM'; }}
      if (sepView) sepView.style.display = 'none';
      if (viewEl) viewEl.style.display = 'none';
    }} else if (viewId === 'overview') {{
      if (sepWs) sepWs.style.display = 'inline';
      if (wsEl) wsEl.style.display = 'inline';
      if (sepCat) sepCat.style.display = 'none';
      if (catEl) catEl.style.display = 'none';
      if (sepView) sepView.style.display = 'none';
      if (viewEl) viewEl.style.display = 'none';
    }} else {{
      if (sepWs) sepWs.style.display = 'inline';
      if (wsEl) wsEl.style.display = 'inline';
      if (sepCat) sepCat.style.display = 'inline';
      if (catEl) {{ catEl.style.display = 'inline'; catEl.textContent = category || ''; }}
      if (sepView) sepView.style.display = 'inline';
      if (viewEl) {{ viewEl.style.display = 'inline'; viewEl.textContent = label || ''; }}
    }}
    return false;
  }}

  window.setView = setView;

  const storedTheme = localStorage.getItem(themeKey) || 'system';
  applyTheme(storedTheme);

  themeButtons.forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const theme = btn.dataset.themeMode || 'system';
      localStorage.setItem(themeKey, theme);
      applyTheme(theme);
    }});
  }});

  window.addEventListener('storage', (e) => {{
    if (e.key === themeKey) {{
      applyTheme(e.newValue || 'system');
    }}
  }});

  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  if (prefersDark && typeof prefersDark.addEventListener === 'function') {{
    prefersDark.addEventListener('change', () => {{
      if ((localStorage.getItem(themeKey) || 'system') === 'system') {{
        applyTheme('system');
      }}
    }});
  }}

  navLinks.forEach((link) => {{
    link.addEventListener('click', (event) => {{
      event.preventDefault();
      const viewId = link.dataset.view || 'overview';
      const viewSrc = link.getAttribute('href') || 'overview.html';
      const category = link.dataset.cat || '';
      const label = link.dataset.label || '';
      setView(viewId, viewSrc, category, label);
    }});
  }});

  setView('overview', 'overview.html', '', 'Overview');
}})();
</script>
{_live_js(port)}
</body>
</html>"""

