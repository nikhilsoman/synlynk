"""Per-workspace Overview canvas."""
import html
from synlynk.viz.chrome import _live_js
def generate_overview_html(data: dict, port: int) -> str:
    """Generate the per-workspace Overview canvas (overview.html)."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # 1. Active sentinel alerts
    sentinel_alerts = [
        a for a in data.get("telemetry", {}).get("sentinel_alerts", [])
        if not a.get("resolved")
    ]
    alerts_html = ""
    if sentinel_alerts:
        alert_rows = []
        for a in sentinel_alerts[:6]:
            sev = str(a.get("severity") or "WARNING").upper()
            sev_class = "sev-crit" if sev in ("CRITICAL", "CRIT") else "sev-warn"
            pattern = a.get("pattern")
            raw_msg = a.get("message") or "Sentinel alert active"
            msg = f"{pattern}: {raw_msg}" if pattern and not raw_msg.startswith(str(pattern)) else raw_msg
            ts = a.get("ts") or ""
            alert_rows.append(
                f'<div class="alert-item {sev_class}">'
                f'<span class="alert-pill">{html.escape(sev)}</span>'
                f'<span class="alert-msg">{html.escape(msg)}</span>'
                f'<span class="alert-ts">{html.escape(ts)}</span>'
                f'</div>'
            )
        alerts_html = f"""
        <div class="alerts-banner">
          <div class="alerts-header">
            <span class="alerts-icon">⚠️</span>
            <span class="alerts-title">Active Sentinel Alerts ({len(sentinel_alerts)})</span>
          </div>
          <div class="alerts-list">
            {"".join(alert_rows)}
          </div>
        </div>
        """

    # 2. Stat Cards Data
    goals = data.get("goals") or []
    active_goals_count = len([g for g in goals if g.get("status") == "active" or not g.get("status")])

    open_stories_count = 0
    total_stories_count = 0
    done_stories_count = 0
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                total_stories_count += 1
                st = str(task.get("status") or "").lower()
                if st in ("done", "completed", "resolved", "merged"):
                    done_stories_count += 1
                elif st in ("active", "ready", "open", "in_progress", "todo", "in progress"):
                    open_stories_count += 1
    if open_stories_count == 0 and total_stories_count == 0:
        repos = workspace.get("repos") or []
        if repos and isinstance(repos[0], dict):
            open_stories_count = int(repos[0].get("active_dream_count") or 0)

    jobs = data.get("jobs") or []
    running_jobs_count = len([j for j in jobs if str(j.get("status") or "").lower() in ("running", "active", "dispatched")])

    costs = data.get("costs") or {}
    total_burn = float(costs.get("total_usd") or 0.0)

    # 3. Goal Progress Rollup
    goal_cards = []
    if goals:
        for g in goals[:6]:
            gid = g.get("id") or "goal"
            outcome = g.get("outcome") or g.get("name") or gid
            criterion = g.get("criterion") or ""
            pct = int((done_stories_count / total_stories_count) * 100) if total_stories_count > 0 else 0
            crit_html = f'<div class="goal-criterion">{html.escape(criterion)}</div>' if criterion else ''
            goal_cards.append(f"""
            <div class="goal-item">
              <div class="goal-top">
                <span class="goal-badge">{html.escape(gid)}</span>
                <span class="goal-outcome">{html.escape(outcome)}</span>
                <span class="goal-pct">{pct}%</span>
              </div>
              {crit_html}
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: {pct}%;"></div>
              </div>
            </div>
            """)
    else:
        goal_cards.append("""
        <div class="empty-hint">
          No active goals in state.db. Run <code>synlynk goal create</code> to define an outcome.
        </div>
        """)
    goals_html = "\n".join(goal_cards)

    # 4. Recent / Active Jobs Feed
    job_rows = []
    if jobs:
        for j in jobs[:6]:
            jid = j.get("job_id") or j.get("id") or "job"
            agent = j.get("agent") or j.get("harness") or "agent"
            task_desc = j.get("task_description") or j.get("task") or j.get("branch") or jid
            st = str(j.get("status") or "completed").lower()
            pr_url = j.get("pr_url") or j.get("pr") or ""

            if st in ("running", "active"):
                st_badge = '<span class="status-chip running">● running</span>'
            elif st in ("circuit_breaker_tripped", "circuit_breaker"):
                st_badge = '<span class="status-chip circuit-breaker">⚡ BREAKER</span>'
            elif "pr" in st or pr_url:
                st_badge = '<span class="status-chip pr-open">✓ PR open</span>'
            elif st in ("completed_without_changes", "failed_noop_denied"):
                st_badge = '<span class="status-chip noop">⚠ NOOP</span>'
            elif st in ("failed", "error", "failed_verification", "failed_unverified", "permission_denied", "scope_violation"):
                st_badge = '<span class="status-chip failed">✕ failed</span>'
            else:
                st_badge = '<span class="status-chip done">✓ completed</span>'

            pr_link_html = f'<a href="{html.escape(pr_url)}" target="_blank" class="job-link">PR ↗</a>' if pr_url else ""

            job_rows.append(f"""
            <div class="job-row">
              <span class="job-id">{html.escape(jid)}</span>
              <span class="agent-chip agent-{html.escape(agent.lower())}">{html.escape(agent)}</span>
              <span class="job-desc" title="{html.escape(task_desc)}">{html.escape(task_desc)}</span>
              {st_badge}
              {pr_link_html}
            </div>
            """)
    else:
        job_rows.append("""
        <div class="empty-hint">
          No recent jobs dispatched. Dispatches from <code>synlynk dispatch</code> will appear here.
        </div>
        """)
    jobs_html = "\n".join(job_rows)

    style = """
    :root {
      --bg: #0d0f14; --bg2: #13171f; --bg3: #1a202c;
      --border: #1e2430; --border2: #2d3748;
      --text: #f3f4f6; --text2: #9ca3af; --text3: #6b7280;
      --accent: #0d9e87; --accent-bg: rgba(13,158,135,0.15); --accent-dim: #14b8a6;
      --shadow: 0 4px 16px rgba(0,0,0,0.25);
      --font-mono: 'SF Mono', 'JetBrains Mono', monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-theme="light"] {
      --bg: #f8fafc; --bg2: #ffffff; --bg3: #f1f5f9;
      --border: #e2e8f0; --border2: #cbd5e1;
      --text: #0f172a; --text2: #475569; --text3: #94a3b8;
      --accent: #0d9e87; --accent-bg: #e6f7f4; --accent-dim: #0b7a60;
      --shadow: 0 2px 10px rgba(0,0,0,0.06);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      padding: 24px 32px 48px;
      line-height: 1.5;
      font-size: 13px;
    }
    a { color: inherit; text-decoration: none; }
    .overview-container { max-width: 1200px; margin: 0 auto; }
    .overview-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .overview-title { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    .overview-sub { font-size: 13px; color: var(--text2); margin-top: 2px; }
    .overview-meta { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--text3); }
    .status-pill {
      background: var(--accent-bg);
      color: var(--accent-dim);
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
    }

    /* Sentinel Banner */
    .alerts-banner {
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 24px;
    }
    .alerts-header { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #f59e0b; margin-bottom: 8px; }
    .alerts-list { display: flex; flex-direction: column; gap: 6px; }
    .alert-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      padding: 4px 8px;
      border-radius: 4px;
      background: var(--bg2);
    }
    .alert-item.sev-crit { border-left: 3px solid #ef4444; }
    .alert-item.sev-warn { border-left: 3px solid #f59e0b; }
    .alert-pill { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; background: rgba(0,0,0,0.2); }
    .alert-msg { flex: 1; word-break: break-word; }
    .alert-ts { color: var(--text3); font-size: 11px; font-family: var(--font-mono); }

    /* Stat Cards Row */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px 20px;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .stat-card:hover { border-color: var(--accent); transform: translateY(-1px); }
    .stat-label { font-size: 12px; color: var(--text2); font-weight: 500; }
    .stat-value { font-size: 26px; font-weight: 700; margin: 4px 0 2px; color: var(--text); }
    .text-accent { color: var(--accent-dim); }
    .stat-foot { font-size: 11px; color: var(--text3); }

    /* Section Cards */
    .sections-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }
    @media (max-width: 900px) {
      .sections-grid { grid-template-columns: 1fr; }
    }
    .section-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }
    .section-title { font-size: 15px; font-weight: 600; }
    .section-link { font-size: 12px; color: var(--accent); font-weight: 500; }
    .section-link:hover { text-decoration: underline; }

    /* Goals Rollup */
    .goals-list { display: flex; flex-direction: column; gap: 12px; }
    .goal-item {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
    }
    .goal-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
    .goal-badge {
      font-size: 11px;
      font-family: var(--font-mono);
      background: var(--bg3);
      color: var(--accent);
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 600;
    }
    .goal-outcome { font-weight: 600; font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .goal-pct { font-size: 12px; font-weight: 700; color: var(--accent-dim); }
    .goal-criterion { font-size: 12px; color: var(--text2); margin-bottom: 8px; line-height: 1.35; }
    .progress-bar-bg { height: 6px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s ease; }

    /* Jobs Feed */
    .jobs-list { display: flex; flex-direction: column; gap: 8px; }
    .job-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      padding: 8px 12px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    .job-id { font-family: var(--font-mono); font-size: 11px; color: var(--text3); }
    .agent-chip {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
      background: var(--bg3);
      color: var(--text2);
    }
    .agent-codex { background: rgba(16,163,127,0.15); color: #10a37f; }
    .agent-agy { background: rgba(66,133,244,0.15); color: #4285f4; }
    .agent-claude { background: rgba(13,158,135,0.15); color: #0d9e87; }
    .agent-grok { background: rgba(255,255,255,0.1); color: var(--text); }
    .job-desc { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
    .status-chip { font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
    .status-chip.running { background: rgba(13,158,135,0.15); color: var(--accent-dim); }
    .status-chip.pr-open { background: rgba(59,130,246,0.15); color: #60a5fa; }
    .status-chip.done { background: rgba(34,197,94,0.15); color: #22c55e; }
    .status-chip.failed { background: rgba(239,68,68,0.15); color: #ef4444; }
    .status-chip.noop { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .status-chip.circuit-breaker { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
    .job-link { font-size: 11px; color: var(--accent); font-weight: 600; }
    .job-link:hover { text-decoration: underline; }

    /* Category Shortcuts Grid */
    .shortcuts-section { margin-top: 12px; }
    .shortcuts-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; }
    .shortcuts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }
    .cat-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      display: flex;
      flex-direction: column;
    }
    .cat-card-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--accent);
      margin-bottom: 12px;
    }
    .cat-card-links { display: flex; flex-direction: column; gap: 8px; }
    .cat-link {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 6px;
      background: var(--bg);
      border: 1px solid var(--border);
      font-size: 12px;
      color: var(--text);
      transition: all 0.15s ease;
    }
    .cat-link:hover {
      border-color: var(--accent);
      color: var(--accent);
      transform: translateX(2px);
    }
    .link-icon { font-size: 13px; width: 16px; text-align: center; }

    .empty-hint {
      text-align: center;
      padding: 24px 16px;
      color: var(--text3);
      font-size: 12px;
      background: var(--bg);
      border-radius: 6px;
      border: 1px dashed var(--border);
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <title>{html.escape(workspace_name)} — Workspace Overview</title>
  <style>{style}</style>
</head>
<body>
  <div class="overview-container">
    <div class="overview-header">
      <div>
        <h1 class="overview-title">{html.escape(workspace_name)}</h1>
        <div class="overview-sub">Workspace Overview & Operational Health</div>
      </div>
      <div class="overview-meta">
        <span class="status-pill">● Active</span>
        <span class="meta-time">Updated {html.escape(updated_at)}</span>
      </div>
    </div>

    {alerts_html}

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Active Goals</div>
        <div class="stat-value">{active_goals_count}</div>
        <div class="stat-foot">Sovereign GOVERNS goals</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Open Stories</div>
        <div class="stat-value">{open_stories_count}</div>
        <div class="stat-foot">Ready & in-flight tasks</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Jobs Running</div>
        <div class="stat-value text-accent">{running_jobs_count}</div>
        <div class="stat-foot">Autonomous dispatches</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Burn (7d)</div>
        <div class="stat-value">${total_burn:.2f}</div>
        <div class="stat-foot">Fleet AI spend</div>
      </div>
    </div>

    <div class="sections-grid">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Goal Progress Rollup</div>
          <a href="gantt.html" class="section-link">View in Gantt →</a>
        </div>
        <div class="goals-list">
          {goals_html}
        </div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Recent / Active Dispatches</div>
          <a href="observatory.html" class="section-link">Observatory →</a>
        </div>
        <div class="jobs-list">
          {jobs_html}
        </div>
      </div>
    </div>

    <div class="shortcuts-section">
      <div class="shortcuts-title">Jump to a View</div>
      <div class="shortcuts-grid">
        <div class="cat-card">
          <div class="cat-card-header">STATUS</div>
          <div class="cat-card-links">
            <a href="board.html" class="cat-link"><span class="link-icon">▦</span> Board</a>
            <a href="gantt.html" class="cat-link"><span class="link-icon">📅</span> Gantt</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">TOPOLOGIES</div>
          <div class="cat-card-links">
            <a href="tube.html" class="cat-link"><span class="link-icon">🚇</span> Architect Map</a>
            <a href="infra.html" class="cat-link"><span class="link-icon">⚙️</span> Infra View</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">PROJECTIONS</div>
          <div class="cat-card-links">
            <a href="product.html" class="cat-link"><span class="link-icon">🗺</span> Product View</a>
            <a href="logical.html" class="cat-link"><span class="link-icon">🧩</span> Logical View</a>
            <a href="world.html" class="cat-link"><span class="link-icon">🌐</span> World View</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">TELEMETRY</div>
          <div class="cat-card-links">
            <a href="effort.html" class="cat-link"><span class="link-icon">💰</span> Effort & Cost</a>
            <a href="efficiency.html" class="cat-link"><span class="link-icon">📊</span> Efficiency</a>
            <a href="observatory.html" class="cat-link"><span class="link-icon">◉</span> Observatory</a>
            <a href="roles.html" class="cat-link"><span class="link-icon">🤖</span> Agent Roles</a>
          </div>
        </div>
      </div>
    </div>
  </div>
  {_live_js(port)}
</body>
</html>"""

