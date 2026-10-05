"""Activity stream canvas."""
import html
from synlynk.viz.chrome import _live_js
def generate_activity_stream_html(data: dict, port: int) -> str:
    """Generate the cross-workspace Activity Stream canvas (activity.html)."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # Collect and normalize events
    events = []

    # 1. From actions / events.jsonl
    for act in data.get("actions") or []:
        if not isinstance(act, dict):
            continue
        action_name = str(act.get("action") or act.get("event") or "event")
        ts = str(act.get("ts") or act.get("timestamp") or "")
        actor = str(act.get("user") or act.get("actor") or act.get("agent") or "system")
        summary = str(act.get("summary") or act.get("message") or act.get("description") or f"Action {action_name} executed by {actor}")
        ev_type = "story" if "story" in action_name else ("goal" if "goal" in action_name else ("pr" if "pr" in action_name else "job"))
        events.append({
            "workspace": workspace_name,
            "type": ev_type,
            "ts": ts,
            "title": f"Action <b>{action_name}</b> by @{actor}",
            "summary": summary,
            "links": [("Board", "board.html"), ("Gantt", "gantt.html")],
        })

    # 2. From jobs
    for j in data.get("jobs") or []:
        if not isinstance(j, dict):
            continue
        jid = j.get("job_id") or j.get("id") or "job"
        agent = j.get("agent") or j.get("harness") or "agent"
        task_desc = j.get("task_description") or j.get("task") or j.get("branch") or jid
        st = str(j.get("status") or "completed").lower()
        pr_url = j.get("pr_url") or j.get("pr") or ""
        ts = str(j.get("created_at") or j.get("updated_at") or "")
        links = [("Observatory", "observatory.html")]
        if pr_url:
            links.append(("GitHub PR", pr_url))
        events.append({
            "workspace": workspace_name,
            "type": "job",
            "ts": ts,
            "title": f"Dispatch <b>{jid}</b> on agent <b>{agent}</b> ({st})",
            "summary": task_desc,
            "links": links,
        })

    # 3. From goals
    for g in data.get("goals") or []:
        if not isinstance(g, dict):
            continue
        gid = g.get("id") or "goal"
        outcome = g.get("outcome") or g.get("name") or gid
        crit = g.get("criterion") or ""
        events.append({
            "workspace": workspace_name,
            "type": "goal",
            "ts": "",
            "title": f"Goal <b>{gid}</b> updated",
            "summary": f"{outcome} — {crit}" if crit else outcome,
            "links": [("Gantt", "gantt.html")],
        })

    # 4. From dreams / stories
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                tid = task.get("id") or "task"
                tname = task.get("name") or tid
                tstatus = task.get("status") or "active"
                agent = task.get("agent") or "agent"
                events.append({
                    "workspace": workspace_name,
                    "type": "story",
                    "ts": "",
                    "title": f"Story <b>{tid}</b> ({tstatus})",
                    "summary": f"{tname} — assigned to {agent}",
                    "links": [("Board", "board.html"), ("Gantt", "gantt.html")],
                })

    # If events is empty, add placeholder
    if not events:
        events.append({
            "workspace": workspace_name,
            "type": "goal",
            "ts": updated_at,
            "title": f"Workspace <b>{workspace_name}</b> initialized",
            "summary": "Vizor multi-workspace monitoring active. Autonomous events will stream here in real time.",
            "links": [("Overview", "overview.html"), ("Board", "board.html")],
        })

    workspaces = sorted(list({e["workspace"] for e in events if e.get("workspace")}))
    event_types = ["goal", "story", "epic", "pr", "job"]

    cards_html = []
    for idx, e in enumerate(events):
        ws = e.get("workspace") or workspace_name
        ev_type = e.get("type") or "story"
        title = e.get("title") or ""
        summary = e.get("summary") or ""
        ts = e.get("ts") or ""
        links = e.get("links") or []
        rendered_links = []
        for label, href in links:
            target_attr = ' target="_blank"' if href.startswith("http") else ""
            rendered_links.append(
                f'<a href="{html.escape(href)}"{target_attr} class="event-link">🔗 {html.escape(label)}</a>'
            )
        links_html = "".join(rendered_links)

        cards_html.append(f"""
        <div class="activity-card" data-workspace="{html.escape(ws)}" data-type="{html.escape(ev_type)}" style="{'display: flex;' if idx < 15 else 'display: none;'}">
          <div class="card-top">
            <div class="card-tags">
              <span class="tag-ws">{html.escape(ws)}</span>
              <span class="tag-type tag-{html.escape(ev_type)}">· {html.escape(ev_type)}</span>
            </div>
            {f'<div class="card-time">{html.escape(ts)}</div>' if ts else ''}
          </div>
          <div class="card-title">{title}</div>
          <div class="card-summary">{html.escape(summary)}</div>
          <div class="card-links">{links_html}</div>
        </div>
        """)

    stream_html = "\n".join(cards_html)

    style = """
    :root {
      --bg: #0d0f14; --bg2: #13171f; --bg3: #1a202c;
      --border: #1e2430; --border2: #2d3748;
      --text: #f3f4f6; --text2: #9ca3af; --text3: #6b7280;
      --accent: #0d9e87; --accent-bg: rgba(13,158,135,0.15); --accent-dim: #14b8a6;
      --font-mono: 'SF Mono', 'JetBrains Mono', monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-theme="light"] {
      --bg: #f8fafc; --bg2: #ffffff; --bg3: #f1f5f9;
      --border: #e2e8f0; --border2: #cbd5e1;
      --text: #0f172a; --text2: #475569; --text3: #94a3b8;
      --accent: #0d9e87; --accent-bg: #e6f7f4; --accent-dim: #0b7a60;
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
    .stream-container { max-width: 900px; margin: 0 auto; }
    .stream-header {
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .stream-title { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    .stream-sub { font-size: 13px; color: var(--text2); margin-top: 2px; }

    /* Filters Bar */
    .filters-bar {
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 24px;
    }
    .filter-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .filter-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text3); width: 80px; }
    .filter-chip {
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text2);
      font-size: 11px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 6px;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s ease;
    }
    .filter-chip:hover { border-color: var(--accent); color: var(--text); }
    .filter-chip.active { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }

    /* Activity Cards */
    .stream-feed { display: flex; flex-direction: column; gap: 12px; }
    .activity-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transition: border-color 0.15s ease;
    }
    .activity-card:hover { border-color: var(--accent); }
    .card-top { display: flex; justify-content: space-between; align-items: center; }
    .card-tags { display: flex; align-items: center; gap: 6px; font-size: 12px; }
    .tag-ws { font-weight: 700; color: var(--accent); }
    .tag-type { color: var(--text3); text-transform: lowercase; }
    .card-time { font-size: 11px; color: var(--text3); font-family: var(--font-mono); }
    .card-title { font-size: 13px; color: var(--text); }
    .card-summary { font-size: 12px; color: var(--text2); line-height: 1.4; }
    .card-links { display: flex; align-items: center; gap: 12px; margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--border); }
    .event-link { font-size: 11px; color: var(--accent); font-weight: 500; }
    .event-link:hover { text-decoration: underline; }

    .load-more-btn {
      width: 100%;
      padding: 12px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text2);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      margin-top: 20px;
      transition: all 0.15s ease;
    }
    .load-more-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--bg3); }
    """

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <title>synlynk Vizor — Activity Stream</title>
  <style>{style}</style>
</head>
<body>
  <div class="stream-container">
    <div class="stream-header">
      <h1 class="stream-title">Activity Stream</h1>
      <div class="stream-sub">Real-time cross-workspace events, dispatches, and governance updates</div>
    </div>

    <div class="filters-bar">
      <div class="filter-group">
        <span class="filter-label">Workspace:</span>
        <button class="filter-chip active" data-filter-group="ws" data-filter="all" onclick="toggleFilter(this)">All</button>
        {"".join(f'<button class="filter-chip" data-filter-group="ws" data-filter="{html.escape(w)}" onclick="toggleFilter(this)">{html.escape(w)}</button>' for w in workspaces)}
      </div>
      <div class="filter-group">
        <span class="filter-label">Type:</span>
        <button class="filter-chip active" data-filter-group="type" data-filter="all" onclick="toggleFilter(this)">All Types</button>
        {"".join(f'<button class="filter-chip" data-filter-group="type" data-filter="{html.escape(t)}" onclick="toggleFilter(this)">{html.escape(t.capitalize())}</button>' for t in event_types)}
      </div>
    </div>

    <div class="stream-feed" id="stream-feed">
      {stream_html}
    </div>

    <button type="button" class="load-more-btn" id="load-more" onclick="loadMore()">Load More Activity</button>
  </div>

  <script>
    let visibleCount = 15;
    let selectedWs = 'all';
    let selectedType = 'all';

    function toggleFilter(btn) {{
      const group = btn.dataset.filterGroup;
      const val = btn.dataset.filter;
      document.querySelectorAll(`.filter-chip[data-filter-group="${{group}}"]`).forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (group === 'ws') selectedWs = val;
      if (group === 'type') selectedType = val;
      applyFilters();
    }}

    function applyFilters() {{
      const cards = document.querySelectorAll('.activity-card');
      let shown = 0;
      cards.forEach(card => {{
        const cardWs = card.dataset.workspace;
        const cardType = card.dataset.type;
        const wsMatch = selectedWs === 'all' || cardWs === selectedWs;
        const typeMatch = selectedType === 'all' || cardType === selectedType;
        if (wsMatch && typeMatch && shown < visibleCount) {{
          card.style.display = 'flex';
          shown++;
        }} else {{
          card.style.display = 'none';
        }}
      }});
      const loadBtn = document.getElementById('load-more');
      if (loadBtn) {{
        loadBtn.style.display = (shown >= cards.length || shown === 0) ? 'none' : 'block';
      }}
    }}

    function loadMore() {{
      visibleCount += 15;
      applyFilters();
    }}
  </script>
  {_live_js(port)}
</body>
</html>"""

