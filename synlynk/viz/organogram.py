"""Workspace Organogram & Workflow Designer canvas."""
from __future__ import annotations

import html
from typing import Any
from synlynk.viz.chrome import _live_js


def generate_organogram_html(data: dict[str, Any], port: int = 33333) -> str:
    """Render the offline-first Workspace Organogram & Workflow Designer."""
    workspace = data.get("workspace") or {}
    workspace_name = html.escape(str(workspace.get("name") or "workspace"))
    agents = data.get("agents") or data.get("workspace_agents") or []
    edges = data.get("workflow_edges") or []
    archetypes = data.get("archetypes") or []

    # Build node cards
    node_cards = []
    for agent in agents:
        agent_id = html.escape(str(agent.get("agent_id") or ""))
        role = html.escape(str(agent.get("role") or agent_id))
        archetype = html.escape(str(agent.get("primary_archetype") or agent.get("archetype_id") or "unassigned"))
        sec_hat = html.escape(str(agent.get("secondary_hat") or ""))
        autonomy = html.escape(str(agent.get("autonomy_level") or "L1_ADVISORY"))
        disciplines = agent.get("sfia_disciplines") or []
        if isinstance(disciplines, str):
            disciplines = [d.strip() for d in disciplines.strip("[]").replace('"', '').split(",") if d.strip()]
        disc_html = "".join(f'<span class="sfia-chip">{html.escape(d)}</span>' for d in disciplines)
        charter = html.escape(str(agent.get("charter_excerpt") or "No charter available."))

        sec_hat_badge = f'<span class="hat-badge">+{sec_hat}</span>' if sec_hat else ""

        node_cards.append(f"""
        <div class="organo-node" data-agent-id="{agent_id}">
          <div class="node-header">
            <span class="role-tag">@{role}</span>
            <span class="autonomy-badge {autonomy.lower()}">{autonomy}</span>
          </div>
          <div class="archetype-title">
            <span class="archetype-badge">{archetype}</span>
            {sec_hat_badge}
          </div>
          <div class="disciplines">{disc_html or '<span class="sfia-chip none">general</span>'}</div>
          <p class="excerpt">{charter}</p>
          <div class="node-footer">
            <button type="button" class="inspect-btn" onclick="inspectNode('{agent_id}')">Inspect &amp; Tools</button>
          </div>
        </div>
        """)

    nodes_html = "\n".join(node_cards) or '<div class="empty">No agents in organogram.</div>'

    # Build edge list
    edge_rows = []
    for edge in edges:
        s = html.escape(str(edge.get("source_agent_id", "")))
        t = html.escape(str(edge.get("target_agent_id", "")))
        etype = html.escape(str(edge.get("edge_type", "delegation")))
        edge_rows.append(f'<li><strong>@{s}</strong> &rarr; <span class="edge-type {etype}">{etype}</span> &rarr; <strong>@{t}</strong></li>')
    edges_html = "\n".join(edge_rows) or "<li>No workflow edges recorded yet.</li>"

    live = _live_js(port)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — Workspace Organogram</title>
<style>
:root {{
  --bg: #0f141c;
  --panel: #161d27;
  --ink: #e6edf3;
  --muted: #8b949e;
  --line: #30363d;
  --accent: #58a6ff;
  --accent-bg: #1f3552;
  --green: #3fb950;
  --amber: #d29922;
  --red: #f85149;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}}
main {{
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}}
.breadcrumbs {{
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}}
.breadcrumbs a {{ color: var(--accent); text-decoration: none; }}
h1 {{ font-size: 26px; margin: 0 0 6px; font-weight: 600; }}
.subtitle {{ color: var(--muted); margin: 0 0 20px; }}

.top-bar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
}}
.top-bar strong {{ color: var(--ink); }}

.layout-grid {{
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}}
.canvas-panel, .side-panel {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}}
h2 {{ font-size: 16px; margin: 0 0 14px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }}

.nodes-container {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}}
.organo-node {{
  background: #1c2430;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  transition: border-color 0.15s ease;
}}
.organo-node:hover {{ border-color: var(--accent); }}
.node-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}}
.role-tag {{ font-weight: 600; color: var(--accent); font-size: 13px; }}
.autonomy-badge {{
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 12px;
  text-transform: uppercase;
}}
.autonomy-badge.l1_advisory {{ background: #21262d; color: var(--muted); }}
.autonomy-badge.l2_gated {{ background: #342a12; color: var(--amber); border: 1px solid #634d1b; }}
.autonomy-badge.l3_autonomous {{ background: #123220; color: var(--green); border: 1px solid #238636; }}

.archetype-title {{ margin-bottom: 8px; display: flex; gap: 6px; align-items: center; }}
.archetype-badge {{
  background: #1f3552;
  color: #79c0ff;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}}
.hat-badge {{
  background: #38274c;
  color: #d2a8ff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
}}
.disciplines {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }}
.sfia-chip {{
  background: #21262d;
  color: var(--muted);
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
}}
.sfia-chip.none {{ font-style: italic; }}
.excerpt {{
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
  margin: 0 0 10px;
  max-height: 48px;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.node-footer {{ text-align: right; }}
.inspect-btn {{
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--line);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}}
.inspect-btn:hover {{ background: var(--accent-bg); border-color: var(--accent); }}

.edge-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
.edge-list li {{ padding: 8px 0; border-bottom: 1px solid #21262d; }}
.edge-type {{
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 3px;
  font-weight: 600;
}}
.edge-type.delegation {{ background: #123220; color: var(--green); }}
.edge-type.review_gate {{ background: #342a12; color: var(--amber); }}
.edge-type.escalation {{ background: #3c1e1e; color: var(--red); }}

.drawer-preview {{
  background: #1c2430;
  border: 1px dashed var(--line);
  border-radius: 6px;
  padding: 12px;
  color: var(--muted);
  font-size: 12px;
}}
.empty {{ text-align: center; color: var(--muted); padding: 30px; }}
</style>
</head>
<body>
<main>
  <div class="breadcrumbs">
    <a href="/w/synlynk/overview.html">Personal</a> &rsaquo; 
    <a href="/w/synlynk/index.html">{workspace_name}</a> &rsaquo; 
    <span>TOPOLOGIES</span> &rsaquo; 
    <span>Organogram</span>
  </div>
  <h1>Workspace Organogram &amp; Workflow Topology</h1>
  <p class="subtitle">Autonomous Fleet Governance across Universal Archetypes &amp; Earned Autonomy Tiers</p>

  <div class="top-bar">
    <div><strong>Workspace:</strong> {workspace_name} &bull; <strong>Living Fleet:</strong> {len(agents)} Agent(s)</div>
    <div><strong>Universal Archetypes:</strong> {len(archetypes) or 6} &bull; <strong>Workflow Connections:</strong> {len(edges)}</div>
  </div>

  <div class="layout-grid">
    <div class="canvas-panel">
      <h2>Agent Organogram Graph</h2>
      <div class="nodes-container">
        {nodes_html}
      </div>
    </div>

    <div class="side-panel">
      <h2>Workflow Edges</h2>
      <ul class="edge-list">
        {edges_html}
      </ul>

      <h2 style="margin-top: 24px;">Inspection &amp; Confirmation Drawer</h2>
      <div id="inspectorDrawer" class="drawer-preview">
        Select an agent node above to inspect its charter, suggested tool baselines, and human write confirmations.
      </div>
    </div>
  </div>
</main>
<script>
function inspectNode(agentId) {{
  var drawer = document.getElementById('inspectorDrawer');
  if (drawer) {{
    drawer.innerHTML = '<strong>Inspecting @' + agentId + '</strong><br><br>' +
      '&bull; <em>Suggested Tools:</em> Requires explicit human confirmation before write grant.<br>' +
      '&bull; <em>Autonomy:</em> Promotion strictly gated by human confirmation.<br>' +
      '&bull; <em>Demotion:</em> Automatic tripwire by Sentinel upon failure.';
  }}
}}
</script>
{live}
</body>
</html>"""
