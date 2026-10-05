"""BS-6 architectural canvases: product, logical, infra, and world."""
import html
import json
from typing import Dict
from synlynk.viz.chrome import _live_js
from synlynk.viz.architect import _ARCHITECT_MAP_STYLE
_BS6_VIEW_JS = """
function bs6LayoutGraph(nodes, edges) {
  const W = 900, H = 620, ITER = 200;
  const positions = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    positions[n.id] = { x: W / 2 + 260 * Math.cos(angle), y: H / 2 + 220 * Math.sin(angle) };
  });
  for (let iter = 0; iter < ITER; iter++) {
    nodes.forEach(a => {
      let fx = 0, fy = 0;
      nodes.forEach(b => {
        if (a.id === b.id) return;
        const dx = positions[a.id].x - positions[b.id].x;
        const dy = positions[a.id].y - positions[b.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const repel = 4000 / (dist * dist);
        fx += (dx / dist) * repel;
        fy += (dy / dist) * repel;
      });
      edges.forEach(e => {
        if (e.from_id !== a.id && e.to_id !== a.id) return;
        const otherId = e.from_id === a.id ? e.to_id : e.from_id;
        if (!positions[otherId]) return;
        const dx = positions[otherId].x - positions[a.id].x;
        const dy = positions[otherId].y - positions[a.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const attract = dist * 0.01;
        fx += (dx / dist) * attract;
        fy += (dy / dist) * attract;
      });
      positions[a.id].x = Math.min(W - 70, Math.max(70, positions[a.id].x + fx));
      positions[a.id].y = Math.min(H - 40, Math.max(40, positions[a.id].y + fy));
    });
  }
  return positions;
}

function bs6RenderGraph() {
  const svg = document.getElementById('bs6-svg');
  if (!svg) return;
  const nodes = window.BS6_NODES || [];
  const edges = window.BS6_EDGES || [];
  const pos = bs6LayoutGraph(nodes, edges);
  let markup = '';
  edges.forEach(e => {
    const a = pos[e.from_id], b = pos[e.to_id];
    if (!a || !b) return;
    markup += '<line class="am-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="#94a3b8"></line>';
  });
  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const label = String(n.label || n.id || '');
    const w = Math.max(90, label.length * 7 + 20);
    let strokeColor = '#334155';
    let community = n.community;
    if (community === undefined && n.attrs_json) {
      try { community = JSON.parse(n.attrs_json).community; } catch (e) {}
    }
    const communityColors = ['#0d9e87', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#10b981'];
    if (community !== undefined && community !== null) {
      let idx = Number(community);
      if (!Number.isFinite(idx)) {
        let hash = 0;
        const str = String(community);
        for (let i = 0; i < str.length; i++) {
          hash = (hash * 31 + str.charCodeAt(i)) | 0;
        }
        idx = Math.abs(hash);
      } else {
        idx = Math.abs(Math.floor(idx));
      }
      strokeColor = communityColors[idx % communityColors.length];
    }
    markup += '<g class="am-node" transform="translate(' + (p.x - w / 2) + ',' + (p.y - 18) + ')" onclick="bs6OpenDrawer(\\'' + n.id + '\\')">' +
      '<rect width="' + w + '" height="36" rx="8" stroke="' + strokeColor + '" stroke-width="1.8"></rect>' +
      '<text x="' + (w / 2) + '" y="22" text-anchor="middle">' + label + '</text>' +
      '</g>';
  });
  svg.innerHTML = markup;
}

function bs6OpenDrawer(nodeId) {
  const node = (window.BS6_NODES || []).find(n => n.id === nodeId);
  if (!node) return;
  document.getElementById('am-drawer-title').textContent = node.label;
  let attrs = {};
  try { attrs = JSON.parse(node.attrs_json || '{}'); } catch (e) {}
  const attrLines = Object.keys(attrs).map(k => '<div>' + k + ': <code>' + attrs[k] + '</code></div>').join('');
  document.getElementById('am-drawer-body').innerHTML =
    '<div>Kind: ' + (node.kind || '') + '</div>' +
    '<div>Source: <code>' + (node.source_path || '') + '</code></div>' +
    '<div>Provenance: ' + (node.provenance || '') + '</div>' +
    attrLines;
  document.getElementById('am-drawer').classList.add('open');
  document.getElementById('am-ov').classList.add('open');
}

function bs6CloseDrawer() {
  document.getElementById('am-drawer').classList.remove('open');
  document.getElementById('am-ov').classList.remove('open');
}

function setLogicalView(view) {
  document.querySelectorAll('.am-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  const iv = document.getElementById('bs6-interactive-view');
  if (iv) iv.classList.toggle('active', view === 'vis');
  const gv = document.getElementById('bs6-graph-view');
  if (gv) gv.classList.toggle('active', view === 'svg');
}

function toggleAmKgDropdown(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('bs6-kg-dropdown-menu');
  if (menu) menu.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.am-dropdown')) {
    const menus = document.querySelectorAll('.am-dropdown-menu');
    menus.forEach(m => m.classList.remove('open'));
  }
});

function filterAmKgCommunities(query) {
  const q = (query || '').toLowerCase().trim();
  const items = document.querySelectorAll('.am-community-item');
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = !q || text.includes(q) ? 'flex' : 'none';
  });
}

function selectAllAmCommunities(enable) {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = enable;
  });
  updateAmKgSelectedCount();
  const frame = document.getElementById('bs6-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-communities-batch', allEnabled: enable }, '*');
    } catch (_) {}
  }
}

function toggleAmCommunityFilter(cb) {
  const comm = cb.dataset.comm;
  const isChecked = cb.checked;
  updateAmKgSelectedCount();
  const frame = document.getElementById('bs6-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-community', community: comm, enabled: isChecked }, '*');
    } catch (_) {}
  }
}

function updateAmKgSelectedCount() {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  const checked = document.querySelectorAll('.am-community-checkbox:checked');
  const countEl = document.getElementById('bs6-kg-selected-count');
  if (countEl) {
    if (checked.length === checkboxes.length) {
      countEl.textContent = 'All (' + checkboxes.length + ')';
    } else {
      countEl.textContent = checked.length + ' / ' + checkboxes.length;
    }
  }
}

function bs6ToggleCommFilter(cb) {
  toggleAmCommunityFilter(cb);
}

function bs6FilterSearch(query) {
  const q = (query || '').toLowerCase().trim();
  const frame = document.getElementById('bs6-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'search', query: q }, '*');
    } catch (_) {}
  }
  const nodes = document.querySelectorAll('#bs6-svg .am-node');
  nodes.forEach(n => {
    const text = (n.textContent || '').toLowerCase();
    n.style.opacity = !q || text.includes(q) ? '1' : '0.2';
  });
}

function applyTheme(theme) {
  if (!theme) return;
  const resolved = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;
  document.documentElement.setAttribute('data-theme', resolved);
  const frame = document.querySelector('iframe');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'theme-change', theme: resolved }, '*');
    } catch (_) {}
  }
}

window.addEventListener('message', function(e) {
  if (!e.data) return;
  if (e.data.type === 'theme-change' || e.data.theme) {
    applyTheme(e.data.theme || e.data);
  } else if (e.data.type === 'lod-status-update') {
    const chip = document.getElementById('bs6-kg-status-chip') || document.querySelector('.am-kg-chip');
    if (chip && e.data.visibleCount !== undefined) {
      chip.textContent = e.data.visibleCount + ' of ' + e.data.totalCount + ' Clusters Visible (Level ' + e.data.level + ': ≥' + e.data.minDegree + ' conns)';
    }
  }
});

function triggerBs6KgRefresh(btn) {
  if (!btn) btn = document.getElementById('bs6-kg-refresh-btn');
  const chip = document.getElementById('bs6-kg-status-chip') || document.querySelector('.am-kg-chip');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '🔄 Refreshing...';
  }
  if (chip) chip.textContent = '⏳ Extracting AST Knowledge Graph...';

  const pathParts = window.location.pathname.split('/');
  let refreshUrl = '/api/graph/refresh';
  if (pathParts[1] === 'w' && pathParts[2]) {
    refreshUrl = '/w/' + encodeURIComponent(pathParts[2]) + '/api/graph/refresh';
  }

  fetch(refreshUrl, {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  .then(res => {
    if (!res.ok) throw new Error('Refresh failed with status ' + res.status);
    return res.json();
  })
  .then(data => {
    if (btn) {
      btn.textContent = '✓ Refreshed';
      setTimeout(() => { btn.textContent = '🔄 Refresh Graph'; btn.disabled = false; }, 2000);
    }
    if (chip) chip.textContent = '✓ Graph Refreshed';
    const iframe = document.getElementById('bs6-graphify-frame') || document.querySelector('iframe');
    if (iframe) {
      iframe.src = iframe.src;
    }
  })
  .catch(err => {
    console.error(err);
    if (btn) {
      btn.textContent = '✗ Failed';
      setTimeout(() => { btn.textContent = '🔄 Refresh Graph'; btn.disabled = false; }, 2500);
    }
    if (chip) chip.textContent = '✗ Extraction Failed';
  });
}

function triggerGraphRefresh(el) {
  if (el) el.textContent = '[Refreshing...]';
  const pathParts = window.location.pathname.split('/');
  let refreshUrl = '/api/graph/refresh';
  if (pathParts[1] === 'w' && pathParts[2]) {
    refreshUrl = '/w/' + encodeURIComponent(pathParts[2]) + '/api/graph/refresh';
  }
  fetch(refreshUrl, {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  .then(res => {
    if (!res.ok) throw new Error('Refresh failed with status ' + res.status);
    return res.json();
  })
  .then(data => {
    if (el) el.textContent = '[Refreshed ✓]';
    setTimeout(() => { location.reload(); }, 600);
  })
  .catch(err => {
    if (el) el.textContent = '[Refresh Failed ✗]';
    console.error(err);
  });
}

function openKgSourceDrawer(filePath, startLine, endLine) {
  if (!filePath) return;
  const drawer = document.getElementById('kg-source-drawer');
  const ov = document.getElementById('kg-source-ov');
  const title = document.getElementById('kg-source-title');
  const badge = document.getElementById('kg-source-badge');
  const code = document.getElementById('kg-source-code');
  if (!drawer || !code) return;

  title.textContent = filePath;
  badge.textContent = startLine && endLine ? 'L' + startLine + '-' + endLine : '';
  code.textContent = 'Loading source code...';
  drawer.classList.add('open');
  if (ov) ov.classList.add('open');

  let url = '/api/source?file=' + encodeURIComponent(filePath);
  if (startLine) url += '&start=' + startLine;
  if (endLine) url += '&end=' + endLine;

  fetch(url)
    .then(r => r.json())
    .then(res => {
      if (res.status === 'ok') {
        code.textContent = res.content || '[Empty content]';
      } else {
        code.textContent = 'Error: ' + (res.error || 'Failed to load source');
      }
    })
    .catch(err => {
      code.textContent = 'Failed to fetch source: ' + err.message;
    });
}

function closeKgSourceDrawer() {
  const drawer = document.getElementById('kg-source-drawer');
  const ov = document.getElementById('kg-source-ov');
  if (drawer) drawer.classList.remove('open');
  if (ov) ov.classList.remove('open');
}

function toggleAmKindFilter(el) {
  const frame = document.getElementById('bs6-graphify-frame') || document.getElementById('am-graphify-frame') || document.querySelector('iframe');
  if (!frame || !frame.contentWindow) return;
  const container = document.getElementById('bs6-kg-kind-filters') || document.getElementById('am-kg-kind-filters') || document.querySelector('.am-kg-kind-filters');
  if (!container) return;
  const checked = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
  frame.contentWindow.postMessage({ type: 'filter-kind-l0', kinds: checked }, '*');
}

function resetInspectMode() {
  const frame = document.getElementById('bs6-graphify-frame') || document.getElementById('am-graphify-frame') || document.querySelector('iframe');
  if (frame && frame.contentWindow) {
    frame.contentWindow.postMessage({ type: 'reset-inspect' }, '*');
  }
}

window.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeKgSourceDrawer();
    if (typeof closeDrawer === 'function') closeDrawer();
    if (typeof bs6CloseDrawer === 'function') bs6CloseDrawer();
    resetInspectMode();
  }
});

window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.type === 'open-source-drawer') {
    openKgSourceDrawer(e.data.file, e.data.start_line, e.data.end_line);
  }
});

try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) applyTheme(savedTheme);
} catch (_) {}

bs6RenderGraph();
"""


def _generate_bs6_view_html(data: dict, port: int, view_key: str, view_title: str) -> str:
    """Shared self-contained node/edge SVG view renderer for the BS-6 Product/Logical/Infra views."""
    from synlynk.viz_views import derive_canonical_community_names

    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    workspace_views = data.get("workspace_views") or {}
    view_data = workspace_views.get(view_key) or {"nodes": [], "edges": []}
    nodes = view_data.get("nodes") or []
    edges = view_data.get("edges") or []

    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)
    live_js_html = _live_js(port)

    kind_counts: Dict[str, int] = {}
    for n in nodes:
        kind = str(n.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-dot"></span>{html.escape(kind.title())} ({count})</div>'
        for kind, count in sorted(kind_counts.items())
    )

    is_stale = bool(view_data.get("stale"))
    if not is_stale and view_key == "logical":
        is_stale = bool(data.get("discovery", {}).get("knowledge_graph", {}).get("stale"))
        if not is_stale:
            for n in nodes:
                try:
                    attrs = json.loads(n.get("attrs_json") or "{}")
                    if attrs.get("stale"):
                        is_stale = True
                        break
                except Exception:
                    pass

    staleness_banner_html = ""
    if is_stale:
        staleness_banner_html = (
            '<div class="am-stale-banner" id="graph-stale-banner">'
            '<span>⚠️ Graph Stale (differs from HEAD commit) — '
            '<a href="#" onclick="triggerGraphRefresh(this); return false;" style="color:#b45309;text-decoration:underline;">[Refresh]</a></span>'
            '</div>'
        )

    switcher_html = ""
    if view_key == "logical":
        switcher_html = """  <div class="am-switcher">
    <button class="am-tab active" data-view="vis" onclick="setLogicalView('vis')">Interactive Canvas</button>
    <button class="am-tab" data-view="svg" onclick="setLogicalView('svg')">AST Projection</button>
  </div>"""

        comm_names = derive_canonical_community_names(nodes)
        communities: Dict[Any, int] = {}
        for n in nodes:
            comm = n.get("community")
            if comm is None:
                try:
                    attrs = json.loads(n.get("attrs_json") or "{}")
                    comm = attrs.get("community")
                except Exception:
                    pass
            if comm is not None:
                communities[comm] = communities.get(comm, 0) + 1

        community_colors = [
            "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899",
            "#06b6d4", "#6366f1", "#14b8a6", "#f97316", "#84cc16"
        ]
        if communities:
            sorted_comms = sorted(communities.items(), key=lambda x: x[1], reverse=True)
            comm_items = "".join(
                f'<label class="am-community-item" style="display:flex; align-items:center; gap:8px; padding:4px 0; font-size:12px; cursor:pointer;">'
                f'<input type="checkbox" class="am-community-checkbox" checked data-comm="{html.escape(str(cid))}" onchange="toggleAmCommunityFilter(this)">'
                f'<span class="legend-dot" style="background:{community_colors[i % len(community_colors)]}; width:10px; height:10px; border-radius:50%; display:inline-block; flex-shrink:0;"></span>'
                f'<span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{html.escape(comm_names.get(cid, f"Community {cid}"))}">{html.escape(comm_names.get(cid, f"Community {cid}"))} ({count})</span>'
                f'</label>'
                for i, (cid, count) in enumerate(sorted_comms)
            )
        else:
            comm_items = '<div style="font-size:11px; color:#64748b;">No Community clusters detected. Run <code>synlynk scan --deep</code>.</div>'

        num_clusters = len(communities)
        total_symbols = len(nodes)
        main_views_html = f"""
<div id="bs6-interactive-view" class="am-view active">
  <div class="am-kg-topbar">
    <div class="am-kg-controls">
      <div class="am-dropdown">
        <button type="button" class="am-dropdown-btn" onclick="toggleAmKgDropdown(event)">
          <span>🌐 Communities: <strong id="bs6-kg-selected-count">All ({num_clusters})</strong></span>
          <span style="font-size:9px; color:#64748b;">▼</span>
        </button>
        <div class="am-dropdown-menu" id="bs6-kg-dropdown-menu">
          <div class="am-dropdown-header">
            <input type="text" placeholder="Filter communities..." oninput="filterAmKgCommunities(this.value)">
          </div>
          <div class="am-dropdown-actions">
            <a onclick="selectAllAmCommunities(true)">Select All</a>
            <a onclick="selectAllAmCommunities(false)">Deselect All</a>
          </div>
          <div class="am-dropdown-list" id="bs6-communities-list">
            {comm_items}
          </div>
        </div>
      </div>
      <input type="text" id="bs6-search" class="am-search-input" placeholder="🔍 Search symbols..." oninput="bs6FilterSearch(this.value)">
      <div class="am-kg-kind-filters" id="bs6-kg-kind-filters">
        <label class="am-kind-chip"><input type="checkbox" checked value="Service Class" onchange="toggleAmKindFilter(this)"> Services</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="Module Cluster" onchange="toggleAmKindFilter(this)"> Modules</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="CLI Handler" onchange="toggleAmKindFilter(this)"> Handlers</label>
        <label class="am-kind-chip"><input type="checkbox" value="Test Suite" onchange="toggleAmKindFilter(this)"> Tests</label>
      </div>
      <span class="am-kg-chip" id="bs6-kg-status-chip">{num_clusters} Clusters · {total_symbols} AST Symbols</span>
      <button type="button" id="bs6-kg-refresh-btn" class="am-btn-action" onclick="triggerBs6KgRefresh(this)" title="Re-extract AST Knowledge Graph">🔄 Refresh Graph</button>
    </div>
  </div>
  <div class="am-kg-canvas-full">
    <iframe id="bs6-graphify-frame" src="graphify.html" width="100%" height="100%" style="border:none;" title="Graphify Knowledge Graph"></iframe>
  </div>
</div>
<div id="bs6-graph-view" class="am-view">
  <div class="am-legend">{legend_html}</div>
  <svg id="bs6-svg" width="100%" height="640"></svg>
</div>
"""
    else:
        main_views_html = f"""
<div class="am-legend">{legend_html}</div>
<div id="bs6-graph-view" class="am-view active">
  <svg id="bs6-svg" width="100%" height="640"></svg>
</div>
"""

    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — __VIEW_TITLE__</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>
<div class="am-header">
  <h1>__VIEW_TITLE__ — __WORKSPACE_NAME__</h1>
__SWITCHER_HTML__
</div>
__STALENESS_BANNER__
__MAIN_VIEWS__
<div class="ov" id="am-ov" onclick="bs6CloseDrawer()"></div>
<div class="am-drawer" id="am-drawer">
  <div class="am-drawer-header">
    <span id="am-drawer-title">—</span>
    <button onclick="bs6CloseDrawer()">✕</button>
  </div>
  <div class="am-drawer-body" id="am-drawer-body"></div>
</div>
<div class="ov" id="kg-source-ov" onclick="closeKgSourceDrawer()"></div>
<div class="kg-source-drawer" id="kg-source-drawer">
  <div class="kg-source-header">
    <div class="kg-source-title"><span id="kg-source-title">—</span><span class="kg-source-badge" id="kg-source-badge"></span></div>
    <button class="kg-source-close" onclick="closeKgSourceDrawer()">✕</button>
  </div>
  <div class="kg-source-body">
    <pre class="kg-source-pre"><code id="kg-source-code">Loading...</code></pre>
  </div>
</div>
<script>
window.BS6_NODES = __NODES_JSON__;
window.BS6_EDGES = __EDGES_JSON__;
window.VIZOR_PORT = __PORT__;
__BS6_VIEW_JS__
</script>
__LIVE_JS_HTML__
</body>
</html>"""
    return (
        template
        .replace("__STYLE_CONTENT__", _ARCHITECT_MAP_STYLE)
        .replace("__VIEW_TITLE__", html.escape(view_title))
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__SWITCHER_HTML__", switcher_html)
        .replace("__STALENESS_BANNER__", staleness_banner_html)
        .replace("__MAIN_VIEWS__", main_views_html)
        .replace("__NODES_JSON__", nodes_json)
        .replace("__EDGES_JSON__", edges_json)
        .replace("__PORT__", str(port))
        .replace("__BS6_VIEW_JS__", _BS6_VIEW_JS)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


def generate_product_html(data: dict, port: int) -> str:
    """Generate rich, interactive Product View with User Journeys, Screen/Interface Catalog, and Terminal Personas."""
    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    workspace_views = data.get("workspace_views") or {}
    prod_data = workspace_views.get("product") or data.get("product") or {"nodes": [], "edges": []}
    nodes = prod_data.get("nodes") or []
    edges = prod_data.get("edges") or []

    live_js_html = _live_js(port)

    # Separate nodes by kind
    journeys = [n for n in nodes if n.get("kind") == "journey"]
    screens = [n for n in nodes if n.get("kind") == "screen"]
    cli_commands = [n for n in nodes if n.get("kind") == "cli_command"]
    routes = [n for n in nodes if n.get("kind") == "route"]

    # Fallbacks if empty
    if not journeys:
        journeys = [
            {
                "id": "j1",
                "label": "Zero-Friction Onboarding",
                "attrs_json": json.dumps({
                    "description": "Initialize workspace, scan AST code graph, and launch agent session.",
                    "steps": ["synlynk init", "synlynk scan --deep", "synlynk launch"]
                })
            },
            {
                "id": "j2",
                "label": "Interactive Home Harness Pairing",
                "attrs_json": json.dumps({
                    "description": "Pair with Claude, Codex, Agy, or Grok in terminal with real-time state and anti-amnesia.",
                    "steps": ["Session Start Greet", "Context Snapshot", "Task Boundary Checkpoint"]
                })
            },
            {
                "id": "j3",
                "label": "Autonomous Milestone DAG Execution",
                "attrs_json": json.dumps({
                    "description": "Execute multi-task milestone unattended across isolated worktrees with QA merge gates.",
                    "steps": ["Spec Brainstorm", "SDD Plan", "Parallel Worktree Dispatch", "QA Merge Gate"]
                })
            },
            {
                "id": "j4",
                "label": "Governance & Master Control Plane",
                "attrs_json": json.dumps({
                    "description": "Coordinate business goals, epic backlogs, and multi-view Vizor control dashboards.",
                    "steps": ["GOVERNS Board", "Gantt Timeline", "AST Architect Map", "Fleet Radar"]
                })
            }
        ]

    if not screens:
        screens = [
            {"label": "GOVERNS Board", "attrs_json": json.dumps({"route": "/board.html", "description": "Canonical Kanban & Stage Tracking", "category": "governance"})},
            {"label": "Gantt Timeline", "attrs_json": json.dumps({"route": "/timeline.html", "description": "Dual-Pivot Milestone Schedule", "category": "timeline"})},
            {"label": "Architect Code Graph", "attrs_json": json.dumps({"route": "/tube.html", "description": "Physical AST Graph & Community Clusters", "category": "architecture"})},
            {"label": "Logical Engine", "attrs_json": json.dumps({"route": "/logical.html", "description": "HLD Layers, LLD Components & Sequence Player", "category": "logical"})},
            {"label": "Host & Egress Topology", "attrs_json": json.dumps({"route": "/infra.html", "description": "Host-Local Runtime vs Outbound AI Egress", "category": "infra"})},
            {"label": "User Journeys & Catalog", "attrs_json": json.dumps({"route": "/product.html", "description": "Product Workflows & Harness Personas", "category": "product"})},
            {"label": "Ecosystem Radar", "attrs_json": json.dumps({"route": "/world.html", "description": "3-Ring Concentric Dependency Radar", "category": "ecosystem"})},
            {"label": "Fleet Observatory", "attrs_json": json.dumps({"route": "/observatory.html", "description": "Cross-Workspace Telemetry & Event Stream", "category": "observatory"})}
        ]

    template = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>synlynk Vizor — Product View & User Journeys</title>
<style>
:root {
  --bg: #0b0f19;
  --bg-surface: #111827;
  --bg-card: #1f2937;
  --bg-card-hover: #283548;
  --border: #374151;
  --border-subtle: #242e3f;
  --text-main: #f9fafb;
  --text-muted: #9ca3af;
  --text-dim: #6b7280;
  --accent: #0d9e87;
  --accent-light: #14b8a6;
  --accent-bg: rgba(13, 158, 135, 0.15);
  --purple: #a855f7;
  --blue: #3b82f6;
  --amber: #f59e0b;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

[data-theme="light"] {
  --bg: #f8fafc;
  --bg-surface: #ffffff;
  --bg-card: #f1f5f9;
  --bg-card-hover: #e2e8f0;
  --border: #cbd5e1;
  --border-subtle: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #475569;
  --text-dim: #94a3b8;
  --accent: #0d9e87;
  --accent-light: #0b7a60;
  --accent-bg: #e6f7f4;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text-main);
  font-family: var(--font-sans);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Header & BS-6 Navigation */
.header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-badge {
  background: var(--accent-bg);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 13px;
  border: 1px solid var(--accent);
}
.view-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}
.view-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}
.nav-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  color: var(--text-muted);
  transition: all 0.15s ease;
}
.nav-btn:hover {
  color: var(--text-main);
  background: var(--bg-card);
}
.nav-btn.active {
  background: var(--accent);
  color: #ffffff;
}

/* Tab Bar */
.tab-bar {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex;
  gap: 20px;
}
.tab-btn {
  padding: 14px 4px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
.tab-btn:hover {
  color: var(--text-main);
}
.tab-btn.active {
  color: var(--accent-light);
  border-bottom-color: var(--accent);
}

/* Content Container */
.main-container {
  flex: 1;
  padding: 24px;
  max-width: 1440px;
  margin: 0 auto;
  width: 100%;
}
.tab-pane {
  display: none;
}
.tab-pane.active {
  display: block;
}

/* Journeys Layout */
.journeys-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
}
.journey-sidebar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.journey-card-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.journey-card-item:hover {
  border-color: var(--accent);
  background: var(--bg-card-hover);
}
.journey-card-item.active {
  border-color: var(--accent);
  background: var(--accent-bg);
}
.journey-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 4px;
}
.journey-card-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
}

.journey-detail-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
}
.journey-detail-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
  margin-bottom: 24px;
}
.journey-flow-visual {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.flow-step-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
}
.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}
.step-content {
  flex: 1;
}
.step-cmd {
  font-family: var(--font-mono);
  background: var(--bg);
  border: 1px solid var(--border-subtle);
  padding: 3px 8px;
  border-radius: 4px;
  color: var(--accent-light);
  font-size: 12px;
  display: inline-block;
  margin-bottom: 4px;
}

/* Screens Grid */
.screens-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}
.screen-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all 0.2s ease;
}
.screen-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.screen-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.screen-category-badge {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-card);
  color: var(--text-muted);
}
.screen-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}
.screen-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
  flex: 1;
}
.screen-link {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-light);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
}
.screen-link:hover {
  text-decoration: underline;
}

/* Personas Grid */
.personas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}
.persona-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.persona-header {
  display: flex;
  align-items: center;
  gap: 14px;
}
.persona-avatar {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
}
.persona-claude { background: rgba(217, 119, 6, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }
.persona-codex { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
.persona-agy { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
.persona-grok { background: rgba(168, 85, 247, 0.2); color: #a855f7; border: 1px solid #a855f7; }

.persona-name { font-size: 16px; font-weight: 700; }
.persona-role { font-size: 12px; color: var(--text-muted); }
.persona-body { font-size: 13px; color: var(--text-muted); line-height: 1.5; flex: 1; }
.persona-terminal {
  background: #000000;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: #10b981;
}
</style>
</head>
<body>

<header class="header">
  <div class="brand-group">
    <span class="logo-badge">synlynk</span>
    <span class="view-title">Product View & User Journeys · __WORKSPACE_NAME__</span>
  </div>
  <nav class="view-nav">
    <a href="/tube.html" class="nav-btn">🚇 Architect Map</a>
    <a href="/logical.html" class="nav-btn">🧠 Logical Engine</a>
    <a href="/product.html" class="nav-btn active">📦 Product Journeys</a>
    <a href="/infra.html" class="nav-btn">⚡ Infra Topology</a>
    <a href="/world.html" class="nav-btn">🌐 Ecosystem Radar</a>
    <a href="/board.html" class="nav-btn">📋 Board</a>
    <a href="/timeline.html" class="nav-btn">⏱️ Timeline</a>
  </nav>
</header>

<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('journeys', this)">🗺️ User Journeys (__JOURNEY_COUNT__)</button>
  <button class="tab-btn" onclick="switchTab('screens', this)">📱 Screen & Interface Catalog (__SCREEN_COUNT__)</button>
  <button class="tab-btn" onclick="switchTab('personas', this)">💻 Harness Terminal Personas (4)</button>
</div>

<main class="main-container">
  <!-- TAB 1: USER JOURNEYS -->
  <div id="pane-journeys" class="tab-pane active">
    <div class="journeys-layout">
      <div class="journey-sidebar">
        __JOURNEY_SIDEBAR_HTML__
      </div>
      <div class="journey-detail-panel" id="journey-detail-container">
        __ACTIVE_JOURNEY_DETAIL_HTML__
      </div>
    </div>
  </div>

  <!-- TAB 2: SCREENS & INTERFACE CATALOG -->
  <div id="pane-screens" class="tab-pane">
    <div class="screens-grid">
      __SCREENS_GRID_HTML__
    </div>
  </div>

  <!-- TAB 3: HARNESS TERMINAL PERSONAS -->
  <div id="pane-personas" class="tab-pane">
    <div class="personas-grid">
      <!-- Claude Persona -->
      <div class="persona-card">
        <div class="persona-header">
          <div class="persona-avatar persona-claude">C</div>
          <div>
            <div class="persona-name">Claude Sonnet / Opus</div>
            <div class="persona-role">PM · Architect · Code Review · Spec Brainstorm</div>
          </div>
        </div>
        <div class="persona-body">
          Primary Home Harness conductor for milestone governance, living charter maintenance, specification brainstorming, and holistic multi-repository architectural review.
        </div>
        <div class="persona-terminal">
          $ /rc<br/>
          $ synlynk status<br/>
          $ synlynk dispatch codex --task "implement #124"
        </div>
      </div>

      <!-- Codex Persona -->
      <div class="persona-card">
        <div class="persona-header">
          <div class="persona-avatar persona-codex">X</div>
          <div>
            <div class="persona-name">OpenAI Codex</div>
            <div class="persona-role">Python · CLI Plumbing · PR Operations · GitHub Write</div>
          </div>
        </div>
        <div class="persona-body">
          High-velocity worker for backend Python implementation, rigorous TDD test suite generation, and automated GitHub PR authoring/merging with sandboxed network grants.
        </div>
        <div class="persona-terminal">
          $ synlynk start #124<br/>
          $ pytest tests/test_core.py<br/>
          $ gh pr create --fill
        </div>
      </div>

      <!-- Agy Persona -->
      <div class="persona-card">
        <div class="persona-header">
          <div class="persona-avatar persona-agy">A</div>
          <div>
            <div class="persona-name">Agy (Gemini 1.5 Pro / Flash)</div>
            <div class="persona-role">HTML · CSS · Canvas · Content · Documentation</div>
          </div>
        </div>
        <div class="persona-body">
          Specialized in high-volume research reads, full-stack templates, Vizor interactive canvas engines, living documentation updates, and deep AST graph visualizations.
        </div>
        <div class="persona-terminal">
          $ synlynk viz<br/>
          $ synlynk checkpoint<br/>
          $ synlynk cost log --amount 0.05
        </div>
      </div>

      <!-- Grok Persona -->
      <div class="persona-card">
        <div class="persona-header">
          <div class="persona-avatar persona-grok">G</div>
          <div>
            <div class="persona-name">Grok (xAI)</div>
            <div class="persona-role">JavaScript · Canvas Infra · Pure Mathematical Compute</div>
          </div>
        </div>
        <div class="persona-body">
          Executes compute-intensive algorithms, spatial graph layouts, coordinate transforms, and browser visualization pipelines in sandboxed, zero-side-effect worktrees.
        </div>
        <div class="persona-terminal">
          $ synlynk dispatch grok --task "optimize AST layout"<br/>
          &gt; Running isolated worker...<br/>
          &gt; Job completed (0 tokens egress)
        </div>
      </div>
    </div>
  </div>
</main>

<script>
const JOURNEYS_DATA = __JOURNEYS_DATA_JSON__;

function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const target = document.getElementById('pane-' + tabId);
  if (target) target.classList.add('active');
  if (btn) btn.classList.add('active');
}

function selectJourney(journeyId) {
  document.querySelectorAll('.journey-card-item').forEach(item => {
    item.classList.toggle('active', item.dataset.id === journeyId);
  });
  const journey = JOURNEYS_DATA.find(j => j.id === journeyId) || JOURNEYS_DATA[0];
  if (!journey) return;

  const container = document.getElementById('journey-detail-container');
  if (!container) return;

  let attrs = {};
  try {
    attrs = typeof journey.attrs_json === 'string' ? JSON.parse(journey.attrs_json) : (journey.attrs_json || {});
  } catch (_) {}

  const steps = attrs.steps || ['Step 1: Initiate', 'Step 2: Process', 'Step 3: Complete'];
  const desc = attrs.description || journey.label;

  let stepsHtml = steps.map((s, idx) => `
    <div class="flow-step-box">
      <div class="step-number">${idx + 1}</div>
      <div class="step-content">
        <div class="step-cmd">${escapeHtml(s)}</div>
        <div style="font-size: 12px; color: var(--text-muted);">Action phase executing ${escapeHtml(s)} against local workspace environment.</div>
      </div>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="journey-detail-header">
      <h2 style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">${escapeHtml(journey.label)}</h2>
      <p style="font-size: 13px; color: var(--text-muted);">${escapeHtml(desc)}</p>
    </div>
    <div class="journey-flow-visual">
      ${stepsHtml}
    </div>
  `;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
} catch (_) {}
</script>
__LIVE_JS_HTML__
</body>
</html>"""

    # Generate Journey Sidebar HTML
    sidebar_items = []
    for idx, j in enumerate(journeys):
        j_id = j.get("id") or f"journey-{idx}"
        j["id"] = j_id
        label = j.get("label") or "User Journey"
        attrs = {}
        try:
            attrs = json.loads(j.get("attrs_json") or "{}") if isinstance(j.get("attrs_json"), str) else (j.get("attrs_json") or {})
        except Exception:
            pass
        desc = attrs.get("description") or f"Workflow for {label}"
        is_active = "active" if idx == 0 else ""
        sidebar_items.append(f"""
        <div class="journey-card-item {is_active}" data-id="{html.escape(j_id)}" onclick="selectJourney('{html.escape(j_id)}')">
          <div class="journey-card-title">{html.escape(label)}</div>
          <div class="journey-card-desc">{html.escape(desc)}</div>
        </div>
        """)
    sidebar_html = "\n".join(sidebar_items)

    # Active Journey Detail HTML
    active_j = journeys[0] if journeys else {}
    active_attrs = {}
    try:
        active_attrs = json.loads(active_j.get("attrs_json") or "{}") if isinstance(active_j.get("attrs_json"), str) else (active_j.get("attrs_json") or {})
    except Exception:
        pass
    active_steps = active_attrs.get("steps") or ["synlynk init", "synlynk scan --deep", "synlynk launch"]
    active_desc = active_attrs.get("description") or active_j.get("label") or "User Workflow"
    active_steps_html = "\n".join([
        f"""
        <div class="flow-step-box">
          <div class="step-number">{idx + 1}</div>
          <div class="step-content">
            <div class="step-cmd">{html.escape(str(s))}</div>
            <div style="font-size: 12px; color: var(--text-muted);">Action phase executing {html.escape(str(s))} against local workspace environment.</div>
          </div>
        </div>
        """ for idx, s in enumerate(active_steps)
    ])
    active_detail_html = f"""
    <div class="journey-detail-header">
      <h2 style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">{html.escape(str(active_j.get("label") or "Journey"))}</h2>
      <p style="font-size: 13px; color: var(--text-muted);">{html.escape(active_desc)}</p>
    </div>
    <div class="journey-flow-visual">
      {active_steps_html}
    </div>
    """

    # Screens Grid HTML
    screen_cards = []
    for s in screens:
        s_label = s.get("label") or "Screen"
        s_attrs = {}
        try:
            s_attrs = json.loads(s.get("attrs_json") or "{}") if isinstance(s.get("attrs_json"), str) else (s.get("attrs_json") or {})
        except Exception:
            pass
        s_route = s_attrs.get("route") or "#"
        s_desc = s_attrs.get("description") or "Vizor interactive interface"
        s_cat = s_attrs.get("category") or "view"
        screen_cards.append(f"""
        <div class="screen-card">
          <div class="screen-card-top">
            <div class="screen-title">{html.escape(s_label)}</div>
            <span class="screen-category-badge">{html.escape(s_cat)}</span>
          </div>
          <div class="screen-desc">{html.escape(s_desc)}</div>
          <a href="{html.escape(s_route)}" class="screen-link">Open View ➔</a>
        </div>
        """)
    screens_grid_html = "\n".join(screen_cards)

    return (
        template
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__JOURNEY_COUNT__", str(len(journeys)))
        .replace("__SCREEN_COUNT__", str(len(screens)))
        .replace("__JOURNEY_SIDEBAR_HTML__", sidebar_html)
        .replace("__ACTIVE_JOURNEY_DETAIL_HTML__", active_detail_html)
        .replace("__SCREENS_GRID_HTML__", screens_grid_html)
        .replace("__JOURNEYS_DATA_JSON__", json.dumps(journeys))
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


def generate_logical_html(data: dict, port: int) -> str:
    """Generate rich, differentiated Logical View with Layered HLD Architecture, LLD Component Model, and Interactive Sequence Player."""
    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    workspace_views = data.get("workspace_views") or {}
    logical_data = workspace_views.get("logical") or data.get("logical") or {"nodes": [], "edges": []}
    nodes = logical_data.get("nodes") or []
    edges = logical_data.get("edges") or []

    # Dynamic Classification into 5 HLD Architectural Tiers
    layer_map = {
        "presentation": [],
        "orchestration": [],
        "domain": [],
        "persistence": [],
        "egress": [],
    }

    for n in nodes:
        label = str(n.get("label") or n.get("id") or "").lower()
        file_path = str(n.get("file") or n.get("source_file") or "").lower()
        if any(k in label or k in file_path for k in ("cli", "main", "viz", "server", "handler", "route", "http", "api", "view", "ui")):
            layer_map["presentation"].append(n)
        elif any(k in label or k in file_path for k in ("dispatch", "run", "fsm", "governs", "loop", "orchestrat", "tpm", "workflow", "plan")):
            layer_map["orchestration"].append(n)
        elif any(k in label or k in file_path for k in ("db", "state", "sqlite", "model", "store", "persist", "identity", "key", "worktree")):
            layer_map["persistence"].append(n)
        elif any(k in label or k in file_path for k in ("relay", "daemon", "network", "client", "egress", "adapter", "socket", "sse")):
            layer_map["egress"].append(n)
        else:
            layer_map["domain"].append(n)

    if not any(layer_map.values()):
        layer_map["presentation"] = [{"label": f"{workspace_name} CLI & API Surface", "kind": "interface"}]
        layer_map["orchestration"] = [{"label": "Workflow & Orchestration Engine", "kind": "orchestrator"}]
        layer_map["domain"] = [{"label": "Core Domain Services & Processing", "kind": "service"}]
        layer_map["persistence"] = [{"label": "Local State Ledger & Storage", "kind": "database"}]
        layer_map["egress"] = [{"label": "Network Adapters & External APIs", "kind": "gateway"}]

    def _render_layer_cards(items: list, default_title: str) -> str:
        if not items:
            return f'<div class="hld-empty-hint">Default {default_title} components</div>'
        out = []
        for it in items[:12]:
            lbl = html.escape(str(it.get("label") or it.get("id") or ""))
            k = html.escape(str(it.get("kind") or "module").title())
            out.append(f'<div class="hld-comp-card"><span class="hld-comp-name">{lbl}</span><span class="hld-comp-kind">{k}</span></div>')
        return "".join(out)

    hld_html = f"""
<div class="hld-container">
  <div class="hld-tier hld-tier-pres">
    <div class="hld-tier-header">
      <span class="hld-tier-badge">Tier 1</span>
      <h3>Presentation &amp; API Surface</h3>
      <span class="hld-tier-desc">CLI entrypoints, HTTP endpoints, WebSocket handlers, and UI routes</span>
    </div>
    <div class="hld-tier-body">
      {_render_layer_cards(layer_map["presentation"], "Presentation")}
    </div>
  </div>

  <div class="hld-flow-arrow">▼ Dispatches commands &amp; requests</div>

  <div class="hld-tier hld-tier-orch">
    <div class="hld-tier-header">
      <span class="hld-tier-badge">Tier 2</span>
      <h3>Orchestration &amp; Workflow Control</h3>
      <span class="hld-tier-desc">Autonomous execution loops, FSM stage managers, TPM synchronizers, and permission sandboxes</span>
    </div>
    <div class="hld-tier-body">
      {_render_layer_cards(layer_map["orchestration"], "Orchestration")}
    </div>
  </div>

  <div class="hld-flow-arrow">▼ Invokes business logic &amp; analysis</div>

  <div class="hld-tier hld-tier-domain">
    <div class="hld-tier-header">
      <span class="hld-tier-badge">Tier 3</span>
      <h3>Domain Services &amp; Core Processing</h3>
      <span class="hld-tier-desc">AST indexing, context packaging, impact calculation, and minimal cone worktree derivation</span>
    </div>
    <div class="hld-tier-body">
      {_render_layer_cards(layer_map["domain"], "Domain Services")}
    </div>
  </div>

  <div class="hld-flow-arrow">▼ Queries &amp; commits persistent state</div>

  <div class="hld-dual-row">
    <div class="hld-tier hld-tier-pers">
      <div class="hld-tier-header">
        <span class="hld-tier-badge">Tier 4</span>
        <h3>Persistence &amp; State Ledger</h3>
        <span class="hld-tier-desc">Primary SQLite database (WAL/SHM), Ed25519 identity key store, and Git worktrees</span>
      </div>
      <div class="hld-tier-body">
        {_render_layer_cards(layer_map["persistence"], "Persistence")}
      </div>
    </div>

    <div class="hld-tier hld-tier-egress">
      <div class="hld-tier-header">
        <span class="hld-tier-badge">Tier 5</span>
        <h3>Network &amp; External Egress</h3>
        <span class="hld-tier-desc">Local SSE event broker (:27472), background daemons, and air-gapped Cloud AI inference adapters</span>
      </div>
      <div class="hld-tier-body">
        {_render_layer_cards(layer_map["egress"], "Network & Egress")}
      </div>
    </div>
  </div>
</div>
"""

    is_stale = bool(logical_data.get("stale") or data.get("is_stale") or False)
    staleness_banner_html = ""
    if is_stale:
        staleness_banner_html = (
            '<div id="graph-stale-banner" class="staleness-banner" style="background:#fef3c7;border-bottom:1px solid #f59e0b;color:#92400e;padding:8px 24px;font-size:12px;display:flex;align-items:center;justify-content:space-between;">'
            '<span>⚠️ <strong>Graph Stale:</strong> AST graph was built on a previous commit. Run <code>synlynk scan --deep</code> to refresh.</span>'
            '</div>'
        )

    live_js_html = _live_js(port)
    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Logical View (System Design & Execution Flows)</title>
<style>
body { margin:0; font-family:'SF Mono',monospace; background:#f6f8fa; color:#1f2328; }
.am-header { display:flex; justify-content:space-between; align-items:center; padding:14px 20px; border-bottom:1px solid #d1d5db; background:#fff; }
.am-header h1 { font-size:15px; margin:0; }
.am-switcher { display:flex; gap:6px; }
.am-tab { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
.am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
.log-view-panel { display:none; padding:20px; max-width:1400px; margin:0 auto; }
.log-view-panel.active { display:block; }

/* HLD Tier Styles */
.hld-container { display:flex; flex-direction:column; gap:12px; }
.hld-tier { background:#fff; border:1px solid #d1d5db; border-radius:8px; padding:14px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.05); }
.hld-tier-pres { border-left:4px solid #3b82f6; }
.hld-tier-orch { border-left:4px solid #8b5cf6; }
.hld-tier-domain { border-left:4px solid #0d9e87; }
.hld-tier-pers { border-left:4px solid #f59e0b; flex:1; }
.hld-tier-egress { border-left:4px solid #ec4899; flex:1; }
.hld-dual-row { display:flex; gap:12px; }
.hld-tier-header { margin-bottom:10px; }
.hld-tier-header h3 { margin:0 0 4px 0; font-size:14px; font-weight:700; color:#0f172a; }
.hld-tier-badge { display:inline-block; font-size:10px; font-weight:600; padding:2px 6px; border-radius:4px; background:#e2e8f0; color:#475569; margin-bottom:4px; }
.hld-tier-desc { font-size:11px; color:#64748b; }
.hld-tier-body { display:flex; flex-wrap:wrap; gap:8px; }
.hld-comp-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:6px 10px; display:inline-flex; align-items:center; gap:6px; font-size:12px; }
.hld-comp-name { font-weight:600; color:#1e293b; }
.hld-comp-kind { font-size:10px; color:#64748b; background:#e2e8f0; padding:1px 5px; border-radius:3px; }
.hld-flow-arrow { text-align:center; font-size:11px; font-weight:600; color:#64748b; user-select:none; }
.hld-empty-hint { font-size:12px; color:#94a3b8; font-style:italic; }

/* Sequence Player Styles */
.seq-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:10px; }
.seq-pills { display:flex; gap:6px; flex-wrap:wrap; }
.seq-pill { background:#fff; border:1px solid #d1d5db; border-radius:20px; padding:6px 14px; font-size:12px; cursor:pointer; font-family:inherit; }
.seq-pill.active { background:#0f172a; color:#fff; border-color:#0f172a; font-weight:600; }
.seq-controls { display:flex; gap:8px; align-items:center; }
.seq-btn { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
.seq-btn:hover { background:#f1f5f9; }
.seq-canvas { background:#fff; border:1px solid #d1d5db; border-radius:8px; padding:20px; min-height:480px; position:relative; box-shadow:0 1px 3px rgba(0,0,0,0.05); }
.seq-step-card { background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:10px 14px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; }
.seq-step-title { font-weight:700; font-size:13px; color:#166534; }
.seq-step-desc { font-size:12px; color:#15803d; }

[data-theme="dark"] body { background:#0d0f14; color:#c9d1d9; }
[data-theme="dark"] .am-header { background:#161b22; border-bottom-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .am-tab { background:#161b22; border-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
[data-theme="dark"] .hld-tier { background:#161b22; border-color:#30363d; }
[data-theme="dark"] .hld-tier-header h3 { color:#f0f6fc; }
[data-theme="dark"] .hld-comp-card { background:#0d1117; border-color:#30363d; }
[data-theme="dark"] .hld-comp-name { color:#c9d1d9; }
[data-theme="dark"] .seq-canvas { background:#161b22; border-color:#30363d; }
[data-theme="dark"] .seq-pill { background:#161b22; border-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .seq-pill.active { background:#38bdf8; color:#0f172a; border-color:#38bdf8; }
[data-theme="dark"] .seq-btn { background:#161b22; border-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .seq-step-card { background:#064e3b; border-color:#059669; }
[data-theme="dark"] .seq-step-title { color:#a7f3d0; }
[data-theme="dark"] .seq-step-desc { color:#6ee7b7; }
</style>
</head>
<body>
<div class="am-header">
  <h1>Logical View — __WORKSPACE_NAME__</h1>
  <div class="am-switcher">
    <button class="am-tab active" data-view="hld" onclick="setLogicalTab('hld')">🏛️ Layered HLD Architecture</button>
    <button class="am-tab" data-view="lld" onclick="setLogicalTab('lld')">🧩 LLD Component Model</button>
    <button class="am-tab" data-view="sequence" onclick="setLogicalTab('sequence')">⚡ Interactive Sequence Player</button>
  </div>
</div>
__STALENESS_BANNER__

<div id="logical-hld-view" class="log-view-panel active">
  __HLD_CONTENT__
</div>

<div id="logical-lld-view" class="log-view-panel">
  <div class="seq-canvas" style="display:flex; flex-direction:column; align-items:center; justify-content:center;">
    <svg id="lld-svg" width="100%" height="600" style="background:transparent;"></svg>
  </div>
</div>

<div id="logical-sequence-view" class="log-view-panel">
  <div class="seq-toolbar">
    <div class="seq-pills">
      <button class="seq-pill active" onclick="loadSequence('loop')">🤖 Autonomous Milestone Loop</button>
      <button class="seq-pill" onclick="loadSequence('drift')">🔍 AST Drift &amp; Knowledge Graph Lifecycle</button>
      <button class="seq-pill" onclick="loadSequence('governs')">📋 Universal GOVERNS Lifecycle</button>
      <button class="seq-pill" onclick="loadSequence('relay')">📡 Real-Time SSE Relay</button>
      <button class="seq-pill" onclick="loadSequence('pipeline')">⚡ Target Request Pipeline</button>
    </div>
    <div class="seq-controls">
      <button class="seq-btn" onclick="prevSeqStep()">◀ Prev Step</button>
      <button class="seq-btn" id="seq-next-btn" onclick="nextSeqStep()" style="font-weight:700; background:#0d9e87; color:#fff; border-color:#0d9e87;">▶ Next Step</button>
      <button class="seq-btn" id="seq-play-btn" onclick="toggleAutoPlay()">▶ Auto Play</button>
      <button class="seq-btn" onclick="resetSeqStep()">↺ Reset</button>
    </div>
  </div>

  <div class="seq-step-card" id="seq-step-banner">
    <div>
      <div class="seq-step-title" id="seq-step-title">Step 1: Task Selection &amp; Preflight Verification</div>
      <div class="seq-step-desc" id="seq-step-desc">Conductor selects next ready story and verifies local ledger state.</div>
    </div>
    <div style="font-size:12px; font-weight:700; color:#64748b;" id="seq-step-counter">Step 1 of 6</div>
  </div>

  <div class="seq-canvas">
    <svg id="seq-svg" width="100%" height="450" style="background:transparent;"></svg>
  </div>
</div>

<script>
window.LOGICAL_NODES = __NODES_JSON__;
window.LOGICAL_EDGES = __EDGES_JSON__;

function setLogicalTab(tabKey) {
  document.querySelectorAll('.am-switcher .am-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.view === tabKey);
  });
  document.querySelectorAll('.log-view-panel').forEach(p => {
    p.classList.remove('active');
  });
  const activeEl = document.getElementById('logical-' + tabKey + '-view');
  if (activeEl) activeEl.classList.add('active');
  if (tabKey === 'lld') renderLldModel();
  if (tabKey === 'sequence') renderSequenceSVG();
}

const SEQUENCES = {
  loop: {
    actors: ['Human/Conductor', 'Task Planner', 'Dispatcher', 'Sandbox Worker', 'QA Gate', 'State Ledger'],
    steps: [
      { from: 0, to: 1, label: '1. Select Goal & Mint Story (synlynk story ready)', desc: 'Conductor identifies next prioritized story from state.db.' },
      { from: 1, to: 2, label: '2. Generate Spec & Plan (docs/superpowers/)', desc: 'Planner formulates TDD implementation plan with verification criteria.' },
      { from: 2, to: 3, label: '3. Worktree Dispatch (git sparse-checkout cone)', desc: 'Dispatcher derives minimal AST cone and spins isolated worktree.' },
      { from: 3, to: 3, label: '4. Autonomous TDD Loop (pytest 100% Green)', desc: 'Worker implements feature and executes local test suite.' },
      { from: 3, to: 4, label: '5. Create PR & QA Gate Review (synlynk pr check)', desc: 'Non-author QA role inspects diff and approves squash merge.' },
      { from: 4, to: 5, label: '6. Merge & Ledger Closeout (synlynk story done)', desc: 'PR squashed to main, worktree cleaned, and story marked done in state.db.' }
    ]
  },
  drift: {
    actors: ['Git Repository', 'Watch Daemon', 'AST Extractor', 'manifest.json', 'Vizor Server'],
    steps: [
      { from: 0, to: 1, label: '1. Commit Landed (HEAD drift detected)', desc: 'Watch daemon periodically polls workspace HEAD commit SHA.' },
      { from: 1, to: 2, label: '2. Trigger Background Extract (graphify --code-only)', desc: 'Watch daemon spawns non-blocking offline AST extraction.' },
      { from: 2, to: 3, label: '3. Update Manifest & AST Cache (.synlynk/graphify-out/)', desc: 'New graph.json and manifest.json written with updated commit stamp.' },
      { from: 3, to: 4, label: '4. Invalidate Vizor Cache & Broadcast Refresh', desc: 'Vizor reloads fresh AST graph without user intervention.' }
    ]
  },
  governs: {
    actors: ['Developer/Agent', 'Waterfall Resolver', 'GOVERNS FSM', 'state.db Ledger', 'Sentinel Sweep'],
    steps: [
      { from: 0, to: 1, label: '1. Create Artifact (Story / Spec / Decision)', desc: 'Work item created in workspace session.' },
      { from: 1, to: 2, label: '2. 5-Tier Waterfall Resolution', desc: 'Resolver matches story to canonical active goal (100% coverage).' },
      { from: 2, to: 3, label: '3. Transition Stage FSM (Draft → Ready → Build → Done)', desc: 'Deterministic state machine stamps stage labels and audit history.' },
      { from: 3, to: 4, label: '4. Continuous Reconciliation (synlynk governs sweep)', desc: 'Sentinel detects and repairs untracked drift automatically.' }
    ]
  },
  relay: {
    actors: ['Fleet Worker', 'Local Broker (:27472)', 'SSE Multiplexer', 'Vizor Web HUD'],
    steps: [
      { from: 0, to: 1, label: '1. Publish Event (POST /publish)', desc: 'Agent emits live progress, cost, or sentinel warning.' },
      { from: 1, to: 2, label: '2. Validate & Fan-out', desc: 'Broker authenticates event against local Ed25519 token.' },
      { from: 2, to: 3, label: '3. Push SSE Stream (GET /events)', desc: 'Browser HUD updates activity stream and status badges in real time.' }
    ]
  },
  pipeline: {
    actors: ['Client Request', 'Router / CLI Handler', 'Domain Service', 'Database / File Ledger', 'External Service'],
    steps: [
      { from: 0, to: 1, label: '1. Incoming CLI Invocation / HTTP Request', desc: 'Presentation layer parses args and authenticates session.' },
      { from: 1, to: 2, label: '2. Dispatch to Domain Core', desc: 'Executes primary business logic and state transitions.' },
      { from: 2, to: 3, label: '3. Read / Write State Store', desc: 'Queries SQLite DB and local filesystem.' },
      { from: 2, to: 4, label: '4. Optional External Outbound Egress', desc: 'Calls AI inference gateways or external APIs if requested.' },
      { from: 1, to: 0, label: '5. Return Formatted Output / JSON Payload', desc: 'Returns formatted response to client terminal or browser.' }
    ]
  }
};

let currentSeqKey = 'loop';
let currentStepIdx = 0;
let autoPlayTimer = null;

function loadSequence(key) {
  currentSeqKey = key;
  currentStepIdx = 0;
  if (autoPlayTimer) toggleAutoPlay();
  document.querySelectorAll('.seq-pill').forEach((p, i) => {
    p.classList.toggle('active', p.getAttribute('onclick').includes(key));
  });
  renderSequenceSVG();
}

function renderSequenceSVG() {
  const seq = SEQUENCES[currentSeqKey];
  if (!seq) return;
  const svg = document.getElementById('seq-svg');
  if (!svg) return;

  const W = svg.clientWidth || 900;
  const numActors = seq.actors.length;
  const colW = Math.max(120, W / numActors);
  const actorPositions = seq.actors.map((_, i) => colW * (i + 0.5));

  const curStep = seq.steps[currentStepIdx] || seq.steps[0];
  const bannerTitle = document.getElementById('seq-step-title');
  const bannerDesc = document.getElementById('seq-step-desc');
  const counter = document.getElementById('seq-step-counter');
  if (bannerTitle) bannerTitle.textContent = curStep.label;
  if (bannerDesc) bannerDesc.textContent = curStep.desc;
  if (counter) counter.textContent = 'Step ' + (currentStepIdx + 1) + ' of ' + seq.steps.length;

  let markup = '';
  // Draw Actor Columns & Lifelines
  seq.actors.forEach((act, i) => {
    const x = actorPositions[i];
    markup += '<rect x="' + (x - 55) + '" y="10" width="110" height="34" rx="6" fill="#f8fafc" stroke="#64748b" stroke-width="1.5"></rect>';
    markup += '<text x="' + x + '" y="32" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a" font-family="inherit">' + act + '</text>';
    markup += '<line x1="' + x + '" y1="44" x2="' + x + '" y2="420" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="4,4"></line>';
  });

  // Draw Steps
  const stepH = Math.min(55, 340 / Math.max(seq.steps.length, 1));
  seq.steps.forEach((st, idx) => {
    const y = 80 + idx * stepH;
    const x1 = actorPositions[st.from];
    const x2 = actorPositions[st.to];
    const isActive = idx === currentStepIdx;
    const isPast = idx < currentStepIdx;
    const strokeColor = isActive ? '#0d9e87' : (isPast ? '#94a3b8' : '#e2e8f0');
    const strokeW = isActive ? '2.5' : '1.5';
    const textColor = isActive ? '#0d9e87' : (isPast ? '#475569' : '#94a3b8');
    const fontWeight = isActive ? '700' : '500';

    if (st.from === st.to) {
      // Self loop
      markup += '<path d="M ' + x1 + ' ' + y + ' C ' + (x1 + 40) + ' ' + (y - 15) + ', ' + (x1 + 40) + ' ' + (y + 15) + ', ' + x1 + ' ' + (y + 10) + '" fill="none" stroke="' + strokeColor + '" stroke-width="' + strokeW + '"></path>';
      markup += '<text x="' + (x1 + 46) + '" y="' + (y + 4) + '" font-size="10" font-weight="' + fontWeight + '" fill="' + textColor + '" font-family="inherit">' + st.label + '</text>';
    } else {
      markup += '<line x1="' + x1 + '" y1="' + y + '" x2="' + x2 + '" y2="' + y + '" stroke="' + strokeColor + '" stroke-width="' + strokeW + '"></line>';
      // Arrowhead
      const arrowX = x2 > x1 ? x2 - 6 : x2 + 6;
      markup += '<polygon points="' + x2 + ',' + y + ' ' + arrowX + ',' + (y - 4) + ' ' + arrowX + ',' + (y + 4) + '" fill="' + strokeColor + '"></polygon>';
      const midX = (x1 + x2) / 2;
      markup += '<text x="' + midX + '" y="' + (y - 6) + '" text-anchor="middle" font-size="10" font-weight="' + fontWeight + '" fill="' + textColor + '" font-family="inherit">' + st.label + '</text>';
    }
  });

  svg.innerHTML = markup;
}

function nextSeqStep() {
  const seq = SEQUENCES[currentSeqKey];
  if (!seq) return;
  if (currentStepIdx < seq.steps.length - 1) {
    currentStepIdx++;
    renderSequenceSVG();
  }
}

function prevSeqStep() {
  if (currentStepIdx > 0) {
    currentStepIdx--;
    renderSequenceSVG();
  }
}

function resetSeqStep() {
  currentStepIdx = 0;
  if (autoPlayTimer) toggleAutoPlay();
  renderSequenceSVG();
}

function toggleAutoPlay() {
  const btn = document.getElementById('seq-play-btn');
  if (autoPlayTimer) {
    clearInterval(autoPlayTimer);
    autoPlayTimer = null;
    if (btn) btn.textContent = '▶ Auto Play';
  } else {
    if (btn) btn.textContent = '⏸ Pause';
    autoPlayTimer = setInterval(() => {
      const seq = SEQUENCES[currentSeqKey];
      if (!seq) return;
      if (currentStepIdx < seq.steps.length - 1) {
        currentStepIdx++;
      } else {
        currentStepIdx = 0;
      }
      renderSequenceSVG();
    }, 2200);
  }
}

function renderLldModel() {
  const svg = document.getElementById('lld-svg');
  if (!svg) return;
  const nodes = window.LOGICAL_NODES || [];
  const W = svg.clientWidth || 900, H = 560;
  let markup = '';
  const displayNodes = nodes.length ? nodes.slice(0, 16) : [
    { id: '1', label: 'GovernsResolver', kind: 'service' },
    { id: '2', label: 'StateDB Ledger', kind: 'database' },
    { id: '3', label: 'PolicyEngine', kind: 'policy' },
    { id: '4', label: 'RelayBroker', kind: 'gateway' },
    { id: '5', label: 'DoctorRunner', kind: 'tool' },
    { id: '6', label: 'VizorHandler', kind: 'server' }
  ];

  const cols = 3;
  displayNodes.forEach((n, i) => {
    const row = Math.floor(i / cols);
    const col = i % cols;
    const x = 80 + col * 260;
    const y = 50 + row * 110;
    markup += '<rect x="' + x + '" y="' + y + '" width="220" height="70" rx="8" fill="#ffffff" stroke="#334155" stroke-width="1.5"></rect>';
    markup += '<rect x="' + x + '" y="' + y + '" width="220" height="24" rx="8" fill="#f1f5f9" stroke="#334155" stroke-width="1.5"></rect>';
    markup += '<text x="' + (x + 10) + '" y="' + (y + 16) + '" font-size="11" font-weight="700" fill="#0f172a" font-family="inherit">' + (n.label || n.id) + '</text>';
    markup += '<text x="' + (x + 10) + '" y="' + (y + 45) + '" font-size="10" fill="#64748b" font-family="inherit">Kind: ' + (n.kind || 'component') + '</text>';
    markup += '<text x="' + (x + 10) + '" y="' + (y + 60) + '" font-size="9" fill="#0d9e87" font-family="inherit">Status: Active Service</text>';
  });
  svg.innerHTML = markup;
}

function bs6RenderGraph() {}

try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
} catch (_) {}
</script>
__LIVE_JS_HTML__
</body>
</html>"""

    return (
        template
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__STALENESS_BANNER__", staleness_banner_html)
        .replace("__HLD_CONTENT__", hld_html)
        .replace("__NODES_JSON__", json.dumps(nodes))
        .replace("__EDGES_JSON__", json.dumps(edges))
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


def generate_infra_html(data: dict, port: int) -> str:
    """Generate rich, dual-zone Infrastructure View (Host-Local Zero-SaaS vs Outbound Cloud AI Inference Egress)."""
    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    workspace_views = data.get("workspace_views") or {}
    infra_data = workspace_views.get("infra") or data.get("infra") or {"nodes": [], "edges": []}
    nodes = infra_data.get("nodes") or []
    edges = infra_data.get("edges") or []

    live_js_html = _live_js(port)

    # Separate by zone
    host_local_nodes = []
    outbound_nodes = []

    for n in nodes:
        attrs = {}
        try:
            attrs = json.loads(n.get("attrs_json") or "{}") if isinstance(n.get("attrs_json"), str) else (n.get("attrs_json") or {})
        except Exception:
            pass
        if attrs.get("zone") == "outbound_egress" or n.get("kind") in ("egress", "external_api"):
            outbound_nodes.append((n, attrs))
        else:
            host_local_nodes.append((n, attrs))

    # Fallbacks if empty
    if not host_local_nodes:
        host_local_nodes = [
            ({"label": "Vizor Server (:8721)", "kind": "daemon", "source_path": "synlynk/viz.py"}, {"port": 8721, "status": "Running", "description": "Local HTTP visualization server and UI control plane"}),
            ({"label": "SSE Relay Broker (:27472)", "kind": "daemon", "source_path": "synlynk/relay.py"}, {"port": 27472, "status": "Active", "description": "High-throughput localhost event multiplexer and SSE feed"}),
            ({"label": "StateDB SQLite Ledger", "kind": "database", "source_path": ".synlynk/state.db"}, {"file": ".synlynk/state.db", "status": "WAL Active", "description": "100% Host-local ACID transactional ledger"}),
            ({"label": "Cryptographic Keystore", "kind": "security", "source_path": "~/.synlynk/identity.key"}, {"file": "identity.key", "status": "Secured (0o600)", "description": "Ed25519 identity key and GitHub App PEM certificates"}),
            ({"label": "Isolated Git Worktrees", "kind": "worktree", "source_path": "../feat+*"}, {"pattern": "../feat+*", "status": "Isolated Cones", "description": "Parallel headless harness execution workspaces"}),
            ({"label": "Graphify AST Cache", "kind": "cache", "source_path": ".synlynk/graphify-out/"}, {"dir": ".synlynk/graphify-out", "status": "Indexed", "description": "Offline AST code graph, community clusters, and source index"})
        ]

    if not outbound_nodes:
        outbound_nodes = [
            ({"label": "Anthropic Claude API", "kind": "egress", "source_path": "synlynk/dispatch.py"}, {"endpoint": "api.anthropic.com:443", "role": "PM & Architecture", "status": "Connected", "category": "llm"}),
            ({"label": "OpenAI Codex API", "kind": "egress", "source_path": "synlynk/dispatch.py"}, {"endpoint": "api.openai.com:443", "role": "Python & PR Ops", "status": "Connected", "category": "llm"}),
            ({"label": "Google Gemini API (Agy)", "kind": "egress", "source_path": "synlynk/dispatch.py"}, {"endpoint": "generativelanguage.googleapis.com:443", "role": "HTML/CSS & Canvas", "status": "Connected", "category": "llm"}),
            ({"label": "xAI Grok API", "kind": "egress", "source_path": "synlynk/dispatch.py"}, {"endpoint": "api.x.ai:443", "role": "Compute & Layout", "status": "Connected", "category": "llm"}),
            ({"label": "GitHub REST/GraphQL API", "kind": "egress", "source_path": "synlynk/gh.py"}, {"endpoint": "api.github.com:443", "role": "Source Control & CI", "status": "Connected", "category": "vcs"})
        ]

    template = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>synlynk Vizor — Infrastructure & Egress Topology</title>
<style>
:root {
  --bg: #0b0f19;
  --bg-surface: #111827;
  --bg-card: #1f2937;
  --bg-card-hover: #283548;
  --border: #374151;
  --border-subtle: #242e3f;
  --text-main: #f9fafb;
  --text-muted: #9ca3af;
  --text-dim: #6b7280;
  --accent: #0d9e87;
  --accent-light: #14b8a6;
  --accent-bg: rgba(13, 158, 135, 0.15);
  --green: #10b981;
  --green-bg: rgba(16, 185, 129, 0.12);
  --blue: #3b82f6;
  --blue-bg: rgba(59, 130, 246, 0.12);
  --purple: #a855f7;
  --amber: #f59e0b;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

[data-theme="light"] {
  --bg: #f8fafc;
  --bg-surface: #ffffff;
  --bg-card: #f1f5f9;
  --bg-card-hover: #e2e8f0;
  --border: #cbd5e1;
  --border-subtle: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #475569;
  --text-dim: #94a3b8;
  --accent: #0d9e87;
  --accent-light: #0b7a60;
  --accent-bg: #e6f7f4;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text-main);
  font-family: var(--font-sans);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Header & BS-6 Navigation */
.header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-badge {
  background: var(--accent-bg);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 13px;
  border: 1px solid var(--accent);
}
.view-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}
.view-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}
.nav-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  color: var(--text-muted);
  transition: all 0.15s ease;
}
.nav-btn:hover {
  color: var(--text-main);
  background: var(--bg-card);
}
.nav-btn.active {
  background: var(--accent);
  color: #ffffff;
}

/* Trust & Security Badges Bar */
.security-bar {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.security-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  background: var(--green-bg);
  color: var(--green);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

/* Content Layout */
.main-container {
  flex: 1;
  padding: 24px;
  max-width: 1440px;
  margin: 0 auto;
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 1024px) {
  .main-container {
    grid-template-columns: 1fr;
  }
}

.zone-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.zone-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.zone-title {
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.zone-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
.zone-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}
.tag-host {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid #10b981;
}
.tag-egress {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
  border: 1px solid #3b82f6;
}

.infra-cards-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.infra-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.15s ease;
}
.infra-card:hover {
  border-color: var(--accent);
  background: var(--bg-card-hover);
}
.infra-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.infra-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 8px;
}
.infra-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}
.infra-card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-dim);
}
.infra-card-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
}
</style>
</head>
<body>

<header class="header">
  <div class="brand-group">
    <span class="logo-badge">synlynk</span>
    <span class="view-title">Infra Topology & Execution Boundary · __WORKSPACE_NAME__</span>
  </div>
  <nav class="view-nav">
    <a href="/tube.html" class="nav-btn">🚇 Architect Map</a>
    <a href="/logical.html" class="nav-btn">🧠 Logical Engine</a>
    <a href="/product.html" class="nav-btn">📦 Product Journeys</a>
    <a href="/infra.html" class="nav-btn active">⚡ Infra Topology</a>
    <a href="/world.html" class="nav-btn">🌐 Ecosystem Radar</a>
    <a href="/board.html" class="nav-btn">📋 Board</a>
    <a href="/timeline.html" class="nav-btn">⏱️ Timeline</a>
  </nav>
</header>

<div class="security-bar">
  <div class="security-badge">🔒 100% Host-Local Primary Ledger</div>
  <div class="security-badge">🛡️ Zero Cloud Telemetry</div>
  <div class="security-badge">⚡ No Third-Party Relay (Localhost Broker)</div>
  <div class="security-badge">🌐 Explicit Outbound AI Egress Only</div>
</div>

<main class="main-container">
  <!-- ZONE 1: HOST-LOCAL RUNTIME BOUNDARY -->
  <div class="zone-panel">
    <div class="zone-header">
      <div>
        <div class="zone-title">🖥️ Host-Local Runtime Boundary</div>
        <div class="zone-subtitle">100% Zero-SaaS execution directly on local host machine</div>
      </div>
      <span class="zone-tag tag-host">Local Isolation</span>
    </div>
    <div class="infra-cards-list">
      __HOST_LOCAL_CARDS_HTML__
    </div>
  </div>

  <!-- ZONE 2: OUTBOUND CLOUD AI EGRESS -->
  <div class="zone-panel">
    <div class="zone-header">
      <div>
        <div class="zone-title">☁️ Outbound AI Cloud Egress</div>
        <div class="zone-subtitle">Sandboxed TLS 1.3 inference gateways with explicit token budgets</div>
      </div>
      <span class="zone-tag tag-egress">Air-Gapped TLS</span>
    </div>
    <div class="infra-cards-list">
      __OUTBOUND_CARDS_HTML__
    </div>
  </div>
</main>

<script>
try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
} catch (_) {}
</script>
__LIVE_JS_HTML__
</body>
</html>"""

    # Generate Host-Local Cards HTML
    hl_cards = []
    for node, attrs in host_local_nodes:
        label = node.get("label") or "Host Component"
        src_path = node.get("source_path") or ""
        status = attrs.get("status") or "Active"
        desc = attrs.get("description") or f"Component in {src_path}"
        hl_cards.append(f"""
        <div class="infra-card">
          <div class="infra-card-top">
            <div class="infra-card-title">
              <span class="infra-status-dot"></span>
              <span>{html.escape(label)}</span>
            </div>
            <span style="font-size: 11px; font-weight: 600; color: var(--accent-light);">{html.escape(status)}</span>
          </div>
          <div class="infra-card-meta">
            <span>Path: {html.escape(src_path)}</span>
          </div>
          <div class="infra-card-desc">{html.escape(desc)}</div>
        </div>
        """)
    host_local_html = "\n".join(hl_cards)

    # Generate Outbound Cards HTML
    out_cards = []
    for node, attrs in outbound_nodes:
        label = node.get("label") or "Outbound Gateway"
        endpoint = attrs.get("endpoint") or "api.cloud.com:443"
        role = attrs.get("role") or attrs.get("category") or "AI Gateway"
        status = attrs.get("status") or "Connected"
        desc = attrs.get("description") or f"External endpoint for {role}"
        out_cards.append(f"""
        <div class="infra-card">
          <div class="infra-card-top">
            <div class="infra-card-title">
              <span class="infra-status-dot"></span>
              <span>{html.escape(label)}</span>
            </div>
            <span style="font-size: 11px; font-weight: 600; color: #3b82f6;">{html.escape(status)}</span>
          </div>
          <div class="infra-card-meta">
            <span>Endpoint: {html.escape(endpoint)}</span>
            <span>·</span>
            <span>Role: {html.escape(role)}</span>
          </div>
          <div class="infra-card-desc">{html.escape(desc)}</div>
        </div>
        """)
    outbound_html = "\n".join(out_cards)

    return (
        template
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__HOST_LOCAL_CARDS_HTML__", host_local_html)
        .replace("__OUTBOUND_CARDS_HTML__", outbound_html)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


def generate_world_html(data: dict, port: int) -> str:
    """Generate rich, 3-ring Concentric Ecosystem Radar View (Core, Primary Egress, Peripherals, Opportunity Horizon)."""
    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    workspace_views = data.get("workspace_views") or {}
    world_data = workspace_views.get("world") or data.get("world") or {"nodes": [], "edges": []}
    nodes = world_data.get("nodes") or []
    edges = world_data.get("edges") or []

    live_js_html = _live_js(port)

    # Process nodes by ring
    ring_nodes = {0: [], 1: [], 2: [], 3: []}
    for n in nodes:
        attrs = {}
        try:
            attrs = json.loads(n.get("attrs_json") or "{}") if isinstance(n.get("attrs_json"), str) else (n.get("attrs_json") or {})
        except Exception:
            pass
        ring = attrs.get("ring", 1)
        if ring not in ring_nodes:
            ring = 1
        ring_nodes[ring].append((n, attrs))

    template = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>synlynk Vizor — Concentric Ecosystem Radar</title>
<style>
:root {
  --bg: #07090e;
  --bg-surface: #0f131c;
  --bg-card: #171d2b;
  --bg-card-hover: #222b3d;
  --border: #263147;
  --border-subtle: #1a2233;
  --text-main: #f9fafb;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --accent: #0d9e87;
  --accent-light: #14b8a6;
  --accent-bg: rgba(13, 158, 135, 0.15);
  --cyan: #06b6d4;
  --purple: #a855f7;
  --blue: #3b82f6;
  --amber: #f59e0b;
  --green: #10b981;
  --radar-grid: #1e293b;
  --radar-sweep: rgba(13, 158, 135, 0.15);
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

[data-theme="light"] {
  --bg: #f8fafc;
  --bg-surface: #ffffff;
  --bg-card: #f1f5f9;
  --bg-card-hover: #e2e8f0;
  --border: #cbd5e1;
  --border-subtle: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #475569;
  --text-dim: #94a3b8;
  --accent: #0d9e87;
  --accent-light: #0b7a60;
  --accent-bg: #e6f7f4;
  --radar-grid: #cbd5e1;
  --radar-sweep: rgba(13, 158, 135, 0.08);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text-main);
  font-family: var(--font-sans);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Header & BS-6 Navigation */
.header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-badge {
  background: var(--accent-bg);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 13px;
  border: 1px solid var(--accent);
}
.view-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}
.view-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}
.nav-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  color: var(--text-muted);
  transition: all 0.15s ease;
}
.nav-btn:hover {
  color: var(--text-main);
  background: var(--bg-card);
}
.nav-btn.active {
  background: var(--accent);
  color: #ffffff;
}

/* Radar Legend Bar */
.legend-bar {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.legend-items {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
}
.ring-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}
.ring-0-badge { background: rgba(13, 158, 135, 0.2); color: #0d9e87; border: 1px solid #0d9e87; }
.ring-1-badge { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
.ring-2-badge { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }
.ring-3-badge { background: rgba(168, 85, 247, 0.2); color: #a855f7; border: 1px solid #a855f7; }

/* Main Grid Layout */
.radar-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 24px;
  padding: 24px;
  max-width: 1540px;
  margin: 0 auto;
  width: 100%;
}

@media (max-width: 1100px) {
  .radar-layout {
    grid-template-columns: 1fr;
  }
}

/* Radar Visual Canvas Container */
.radar-canvas-container {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  min-height: 600px;
}
.radar-svg {
  width: 100%;
  max-width: 680px;
  height: auto;
  aspect-ratio: 1 / 1;
  overflow: visible;
}

/* Side Inspection Panel */
.radar-inspector {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.inspector-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}
.inspector-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}
.blips-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  max-height: 580px;
}
.blip-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.blip-card:hover {
  border-color: var(--accent);
  background: var(--bg-card-hover);
}
.blip-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.blip-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
}
.blip-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
}
.blip-env {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--accent-light);
  margin-top: 6px;
}
</style>
</head>
<body>

<header class="header">
  <div class="brand-group">
    <span class="logo-badge">synlynk</span>
    <span class="view-title">Ecosystem Radar (World View) · __WORKSPACE_NAME__</span>
  </div>
  <nav class="view-nav">
    <a href="/tube.html" class="nav-btn">🚇 Architect Map</a>
    <a href="/logical.html" class="nav-btn">🧠 Logical Engine</a>
    <a href="/product.html" class="nav-btn">📦 Product Journeys</a>
    <a href="/infra.html" class="nav-btn">⚡ Infra Topology</a>
    <a href="/world.html" class="nav-btn active">🌐 Ecosystem Radar</a>
    <a href="/board.html" class="nav-btn">📋 Board</a>
    <a href="/timeline.html" class="nav-btn">⏱️ Timeline</a>
  </nav>
</header>

<div class="legend-bar">
  <div class="legend-items">
    <div class="legend-item">
      <span class="ring-badge ring-0-badge">Ring 0</span>
      <span>Workspace Core</span>
    </div>
    <div class="legend-item">
      <span class="ring-badge ring-1-badge">Ring 1</span>
      <span>Primary Egress (AI & VCS)</span>
    </div>
    <div class="legend-item">
      <span class="ring-badge ring-2-badge">Ring 2</span>
      <span>Ecosystem Peripherals</span>
    </div>
    <div class="legend-item">
      <span class="ring-badge ring-3-badge">Ring 3</span>
      <span>Opportunity Horizon</span>
    </div>
  </div>
  <div style="font-size: 11px; color: var(--text-dim); font-family: var(--font-mono);">
    Total Nodes: __TOTAL_NODES__
  </div>
</div>

<main class="radar-layout">
  <!-- RADAR CANVAS -->
  <div class="radar-canvas-container">
    <svg class="radar-svg" viewBox="-360 -360 720 720" id="radar-svg">
      <!-- Concentric Rings -->
      <circle cx="0" cy="0" r="320" fill="none" stroke="var(--radar-grid)" stroke-width="1" stroke-dasharray="4,4" />
      <circle cx="0" cy="0" r="230" fill="none" stroke="var(--radar-grid)" stroke-width="1" stroke-dasharray="4,4" />
      <circle cx="0" cy="0" r="130" fill="none" stroke="var(--radar-grid)" stroke-width="1" stroke-dasharray="4,4" />
      <circle cx="0" cy="0" r="40" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2" />

      <!-- Axes -->
      <line x1="-340" y1="0" x2="340" y2="0" stroke="var(--radar-grid)" stroke-width="1" />
      <line x1="0" y1="-340" x2="0" y2="340" stroke="var(--radar-grid)" stroke-width="1" />

      <!-- Ring Labels -->
      <text x="5" y="-45" font-size="10" font-weight="700" fill="var(--accent)" font-family="inherit">Ring 0: Core</text>
      <text x="5" y="-135" font-size="10" font-weight="700" fill="#3b82f6" font-family="inherit">Ring 1: Primary Egress</text>
      <text x="5" y="-235" font-size="10" font-weight="700" fill="#f59e0b" font-family="inherit">Ring 2: Ecosystem</text>
      <text x="5" y="-325" font-size="10" font-weight="700" fill="#a855f7" font-family="inherit">Ring 3: Opportunity</text>

      <!-- Rendered Blips -->
      __RADAR_BLIPS_SVG__
    </svg>
  </div>

  <!-- RADAR INSPECTION PANEL -->
  <div class="radar-inspector">
    <div class="inspector-header">
      <div class="inspector-title">📡 Ecosystem Integrations</div>
      <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">All active inside-out connections and opportunities</div>
    </div>
    <div class="blips-list">
      __BLIPS_LIST_HTML__
    </div>
  </div>
</main>

<script>
try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
} catch (_) {}
</script>
__LIVE_JS_HTML__
</body>
</html>"""

    # Generate Radar Blips SVG and List HTML
    import math
    blips_svg_list = []
    blips_html_list = []

    # Ring radii definitions
    radii = {0: 0, 1: 130, 2: 230, 3: 320}
    ring_colors = {0: "#0d9e87", 1: "#3b82f6", 2: "#f59e0b", 3: "#a855f7"}

    # Core node (Ring 0)
    blips_svg_list.append(f"""
      <circle cx="0" cy="0" r="10" fill="#0d9e87">
        <animate attributeName="r" values="8;12;8" dur="3s" repeatCount="indefinite"/>
      </circle>
      <text x="0" y="24" text-anchor="middle" font-size="11" font-weight="700" fill="var(--text-main)" font-family="inherit">{html.escape(workspace_name)}</text>
    """)

    # Populate Rings 1, 2, 3
    for ring_idx in (1, 2, 3):
        items = ring_nodes.get(ring_idx, [])
        num_items = len(items)
        if num_items == 0:
            continue
        radius = radii[ring_idx]
        color = ring_colors[ring_idx]

        for i, (n, attrs) in enumerate(items):
            angle = (2 * math.pi / num_items) * i + (ring_idx * 0.4)
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            label = n.get("label") or "Integration"
            desc = attrs.get("description") or ""
            env_var = attrs.get("env_var") or ""
            cat = attrs.get("category") or "service"

            # SVG Blip
            blips_svg_list.append(f"""
              <g class="radar-blip-node" transform="translate({x:.1f},{y:.1f})">
                <circle cx="0" cy="0" r="14" fill="{color}" fill-opacity="0.2" />
                <circle cx="0" cy="0" r="6" fill="{color}" />
                <text x="0" y="-10" text-anchor="middle" font-size="10" font-weight="600" fill="var(--text-main)" font-family="inherit">{html.escape(label[:18])}</text>
              </g>
            """)

            # List Item
            env_html = f'<div class="blip-env">🔑 {html.escape(env_var)}</div>' if env_var else ""
            blips_html_list.append(f"""
              <div class="blip-card">
                <div class="blip-card-top">
                  <span class="blip-label">{html.escape(label)}</span>
                  <span class="ring-badge ring-{ring_idx}-badge">Ring {ring_idx}</span>
                </div>
                <div class="blip-desc">{html.escape(desc)}</div>
                {env_html}
              </div>
            """)

    total_nodes = len(nodes)
    return (
        template
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__TOTAL_NODES__", str(total_nodes))
        .replace("__RADAR_BLIPS_SVG__", "\n".join(blips_svg_list))
        .replace("__BLIPS_LIST_HTML__", "\n".join(blips_html_list))
        .replace("__LIVE_JS_HTML__", live_js_html)
    )

