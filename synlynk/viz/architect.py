"""Architect map (knowledge-graph) canvas."""
import html
import json
import os
from typing import Dict
from synlynk.viz.chrome import _live_js
_ARCHITECT_MAP_JS = """
let amZoomScale = 1.0;
let amPanX = 0, amPanY = 0;

function amApplyTransform() {
  const vp = document.getElementById('am-canvas-viewport');
  if (vp) {
    vp.setAttribute('transform', 'translate(' + amPanX + ',' + amPanY + ') scale(' + amZoomScale + ')');
  }
  const details = document.querySelectorAll('.am-cluster-detail');
  details.forEach(d => {
    d.style.display = amZoomScale < 0.65 ? 'none' : 'block';
  });
}

function amZoomIn() {
  amZoomScale = Math.min(amZoomScale * 1.25, 3.0);
  amApplyTransform();
}

function amZoomOut() {
  amZoomScale = Math.max(amZoomScale / 1.25, 0.4);
  amApplyTransform();
}

function amZoomReset() {
  amZoomScale = 1.0;
  amPanX = 0;
  amPanY = 0;
  amApplyTransform();
}

function layoutGraph(nodes, edges) {
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
        if (e.from !== a.id && e.to !== a.id) return;
        const otherId = e.from === a.id ? e.to : e.from;
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

function renderGraph() {
  const svg = document.getElementById('am-svg');
  if (!svg) return;
  const nodes = window.ARCHITECT_NODES || [];
  const edges = window.ARCHITECT_EDGES || [];
  const edgeTypes = window.ARCHITECT_EDGE_TYPES || {};
  const isMultiRepo = nodes.length > 1;
  const pos = layoutGraph(nodes, edges);
  let markup = '<g id="am-canvas-viewport" transform="translate(' + amPanX + ',' + amPanY + ') scale(' + amZoomScale + ')">';

  edges.forEach(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    const color = (edgeTypes[e.type] || {}).color || '#0d9e87';
    const edgeLabel = (edgeTypes[e.type] || {}).label || e.type || 'api-bridge';
    if (isMultiRepo) {
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      markup += '<g class="am-bridge-group">' +
        '<line class="am-edge am-bridge-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + color + '" stroke-width="2.5" stroke-dasharray="6,4"></line>' +
        '<rect x="' + (mx - 40) + '" y="' + (my - 10) + '" width="80" height="20" rx="4" fill="#ffffff" stroke="' + color + '" stroke-width="1"></rect>' +
        '<text class="am-bridge-label" x="' + mx + '" y="' + (my + 4) + '" text-anchor="middle" font-size="10" fill="' + color + '" font-weight="600">' + edgeLabel + '</text>' +
        '</g>';
    } else {
      markup += '<line class="am-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + color + '"></line>';
    }
  });

  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const label = String(n.label || n.id || '');
    if (isMultiRepo) {
      const w = 220, h = 120;
      const stack = (n.stack_labels || []).join(', ');
      markup += '<g class="am-cluster am-cluster-repo am-repo-box" data-repo="' + n.id + '" transform="translate(' + (p.x - w / 2) + ',' + (p.y - h / 2) + ')" onclick="openDrawer(\\'' + n.id + '\\')">' +
        '<rect class="am-cluster-bg" width="' + w + '" height="' + h + '" rx="10"></rect>' +
        '<rect class="am-cluster-header" width="' + w + '" height="32" rx="10"></rect>' +
        '<rect y="22" width="' + w + '" height="10" class="am-cluster-header"></rect>' +
        '<text class="am-cluster-title" x="12" y="21">📦 ' + label + '</text>' +
        '<text class="am-cluster-detail" x="12" y="55">Stack: ' + (stack || 'general') + '</text>' +
        '<text class="am-cluster-detail" x="12" y="75">Active stories: ' + (n.active_dream_count || 0) + '</text>' +
        '<g class="am-node" transform="translate(12, 86)">' +
        '<rect width="' + (w - 24) + '" height="24" rx="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1"></rect>' +
        '<text x="' + ((w - 24) / 2) + '" y="16" text-anchor="middle" font-size="10" fill="#334155">Inspect Repo →</text>' +
        '</g>' +
        '</g>';
    } else {
      const w = Math.max(90, label.length * 7 + 20);
      markup += '<g class="am-node" transform="translate(' + (p.x - w / 2) + ',' + (p.y - 18) + ')" onclick="openDrawer(\\'' + n.id + '\\')">' +
        '<rect width="' + w + '" height="36" rx="8"></rect>' +
        '<text x="' + (w / 2) + '" y="22" text-anchor="middle">' + label + '</text>' +
        '</g>';
    }
  });

  markup += '</g>';
  svg.innerHTML = markup;
  amApplyTransform();
}

function setArchitectView(view) {
  document.querySelectorAll('.am-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  const kv = document.getElementById('am-knowledge-view');
  if (kv) kv.classList.toggle('active', view === 'knowledge');
  const gv = document.getElementById('am-graph-view');
  if (gv) gv.classList.toggle('active', view === 'graph');
  const tv = document.getElementById('am-tree-view');
  if (tv) tv.classList.toggle('active', view === 'tree');
  if (view === 'tree' && !window._treeRendered) {
    renderTree();
    window._treeRendered = true;
  }
  fetch('/architect-map/view-pref', {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({ view: view }),
  }).catch(() => {});
}

let currentDrawerNode = null;

function openDrawer(nodeId) {
  const node = (window.ARCHITECT_NODES || []).find(n => n.id === nodeId);
  if (!node) return;
  currentDrawerNode = node;
  document.getElementById('am-drawer-title').textContent = node.label;
  const stack = (node.stack_labels || []).join(', ') || 'unlabeled';
  document.getElementById('am-drawer-body').innerHTML =
    '<div>Path: <code>' + node.path + '</code></div>' +
    '<div>Stack: ' + stack + '</div>' +
    '<div>Active dreams: ' + (node.active_dream_count || 0) + '</div>';
  const githubLink = document.getElementById('am-drawer-github');
  if (node.github_url) {
    githubLink.href = node.github_url;
    githubLink.style.display = 'block';
  } else {
    githubLink.style.display = 'none';
  }
  document.getElementById('am-drawer').classList.add('open');
  document.getElementById('am-ov').classList.add('open');
}

function closeDrawer() {
  document.getElementById('am-drawer').classList.remove('open');
  document.getElementById('am-ov').classList.remove('open');
  currentDrawerNode = null;
}

async function drawerDispatch() {
  if (!currentDrawerNode) return;
  const task = prompt('Task to dispatch in ' + currentDrawerNode.label + ':');
  if (!task) return;
  await fetch('/dispatch', {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_path: currentDrawerNode.path, task: task }),
  });
  closeDrawer();
}

function drawerJumpGantt() {
  if (!currentDrawerNode) return;
  window.top.postMessage({ type: 'vizor-navigate', view: 'gantt', repo: currentDrawerNode.id }, '*');
}

function renderTreeNode(node) {
  let html = '';
  const dirNames = Object.keys(node.dirs || {}).sort();
  dirNames.forEach(name => {
    html += '<details class="am-tree-dir" open><summary>📁 ' + name + '</summary>' + renderTreeNode(node.dirs[name]) + '</details>';
  });
  (node.files || []).slice().sort((a, b) => a.name.localeCompare(b.name)).forEach(f => {
    html += '<div class="am-tree-file">📄 ' + f.name + ' <span style="color:#94a3b8">(' + f.symbol_count + ')</span></div>';
  });
  return html;
}

function renderTree() {
  const root = document.getElementById('am-tree-root');
  if (!root) return;
  const tree = window.ARCHITECT_FILE_TREE || { dirs: {}, files: [] };
  root.innerHTML = renderTreeNode(tree) || '<div class="am-tree-file">No scan data yet — run <code>synlynk scan --deep</code>.</div>';
}

function filterKgSearch(query) {
  const q = (query || '').toLowerCase().trim();
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'search', query: q }, '*');
    } catch (_) {}
  }
}

function toggleAmKgDropdown(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('am-kg-dropdown-menu');
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
  const frame = document.getElementById('am-graphify-frame');
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
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-community', community: comm, enabled: isChecked }, '*');
    } catch (_) {}
  }
}

function updateAmKgSelectedCount() {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  const checked = document.querySelectorAll('.am-community-checkbox:checked');
  const countEl = document.getElementById('am-kg-selected-count');
  if (countEl) {
    if (checked.length === checkboxes.length) {
      countEl.textContent = 'All (' + checkboxes.length + ')';
    } else {
      countEl.textContent = checked.length + ' / ' + checkboxes.length;
    }
  }
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
    const chip = document.getElementById('am-kg-status-chip') || document.querySelector('.am-kg-chip');
    if (chip && e.data.visibleCount !== undefined) {
      chip.textContent = e.data.visibleCount + ' of ' + e.data.totalCount + ' Clusters Visible (Level ' + e.data.level + ': ≥' + e.data.minDegree + ' conns)';
    }
  }
});

try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) applyTheme(savedTheme);
} catch (_) {}

const svgEl = document.getElementById('am-svg');
if (svgEl) {
  let isDragging = false;
  let startX = 0, startY = 0;
  svgEl.addEventListener('wheel', function(e) {
    e.preventDefault();
    if (e.deltaY < 0) {
      amZoomScale = Math.min(amZoomScale * 1.1, 3.0);
    } else {
      amZoomScale = Math.max(amZoomScale / 1.1, 0.4);
    }
    amApplyTransform();
  }, { passive: false });
  svgEl.addEventListener('mousedown', function(e) {
    if (e.target.closest('.am-node') || e.target.closest('.am-cluster')) return;
    isDragging = true;
    startX = e.clientX - amPanX;
    startY = e.clientY - amPanY;
  });
  window.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    amPanX = e.clientX - startX;
    amPanY = e.clientY - startY;
    amApplyTransform();
  });
  window.addEventListener('mouseup', function() {
    isDragging = false;
  });
}

function triggerAmKgRefresh(btn) {
  if (!btn) btn = document.getElementById('am-kg-refresh-btn');
  const chip = document.getElementById('am-kg-status-chip') || document.querySelector('.am-kg-chip');
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
    const iframe = document.getElementById('am-graphify-frame') || document.querySelector('iframe');
    const hud = document.getElementById('am-empty-hud');
    if (iframe) {
      if (iframe.dataset && iframe.dataset.src) iframe.src = iframe.dataset.src;
      else iframe.src = iframe.src;
      iframe.style.display = 'block';
    }
    if (hud) hud.style.display = 'none';
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
  const frame = document.getElementById('am-graphify-frame');
  if (!frame || !frame.contentWindow) return;
  const container = document.getElementById('am-kg-kind-filters');
  if (!container) return;
  const checked = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
  frame.contentWindow.postMessage({ type: 'filter-kind-l0', kinds: checked }, '*');
}

function resetInspectMode() {
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    frame.contentWindow.postMessage({ type: 'reset-inspect' }, '*');
  }
}

window.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeKgSourceDrawer();
    closeDrawer();
    resetInspectMode();
  }
});

window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.type === 'open-source-drawer') {
    openKgSourceDrawer(e.data.file, e.data.start_line, e.data.end_line);
  }
});

renderGraph();
"""

_ARCHITECT_MAP_STYLE = """
body { margin:0; font-family:'SF Mono',monospace; background:#f6f8fa; color:#1f2328; }
.am-header { display:flex; justify-content:space-between; align-items:center; padding:14px 20px; border-bottom:1px solid #d1d5db; }
.am-header h1 { font-size:15px; margin:0; }
.am-switcher { display:flex; gap:6px; }
.am-tab { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
.am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
.am-legend { display:flex; gap:14px; padding:8px 20px; font-size:11px; }
.legend-item { display:flex; align-items:center; gap:5px; }
.legend-dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
.am-view { display:none; padding:10px 20px; }
.am-view.active { display:block; }
.am-node { cursor:pointer; }
.am-node rect { fill:#fff; stroke:#334155; stroke-width:1.5; }
.am-node text { font-size:11px; font-family:inherit; }
.am-edge { stroke-width:2; fill:none; }
.ov { display:none; position:fixed; inset:0; background:rgba(0,0,0,.35); z-index:999; }
.ov.open { display:block; }
.am-drawer { position:fixed; top:0; right:-360px; width:340px; height:100%; background:#fff; box-shadow:-2px 0 12px rgba(0,0,0,.15); z-index:1000; transition:right .2s ease; padding:16px; box-sizing:border-box; }
.am-drawer.open { right:0; }
.am-drawer-header { display:flex; justify-content:space-between; align-items:center; font-size:13px; font-weight:bold; margin-bottom:12px; }
.am-drawer-header button { background:none; border:none; cursor:pointer; font-size:14px; }
.am-drawer-body { font-size:12px; line-height:1.6; margin-bottom:16px; }
.am-drawer-actions { display:flex; flex-direction:column; gap:8px; }
.btn { background:#0d9e87; color:#fff; border:none; border-radius:5px; padding:7px 10px; font-size:12px; cursor:pointer; text-align:center; text-decoration:none; font-family:inherit; }
.am-tree { font-size:12px; }
.am-tree-dir > summary { cursor:pointer; padding:2px 0; }
.am-tree-file { padding:2px 0 2px 18px; color:#475569; }
.am-stale-banner { background:#fffbeb; border:1px solid #f59e0b; color:#b45309; padding:8px 16px; margin:8px 20px; border-radius:6px; font-size:12px; font-weight:500; display:flex; align-items:center; gap:8px; }
.am-zoom-controls { position:absolute; top:20px; right:30px; display:flex; gap:6px; z-index:10; }
.am-zoom-btn { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 10px; font-size:12px; cursor:pointer; font-family:inherit; box-shadow:0 1px 3px rgba(0,0,0,0.1); }
.am-zoom-btn:hover { background:#f3f4f6; }
.am-cluster-repo { cursor:pointer; }
.am-cluster-bg { fill:#f8fafc; stroke:#64748b; stroke-width:1.5; }
.am-cluster-header { fill:#e2e8f0; }
.am-cluster-title { font-size:12px; font-weight:bold; fill:#0f172a; }
.am-cluster-detail { font-size:11px; fill:#475569; }
.am-bridge-edge { stroke-dasharray:6,4; }
.am-bridge-label { font-size:10px; font-weight:600; }
.am-kg-topbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; flex-wrap:wrap; }
.am-kg-controls { display:flex; align-items:center; gap:10px; flex:1; }
.am-dropdown { position:relative; display:inline-block; }
.am-dropdown-btn { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 12px; font-size:12px; font-family:inherit; cursor:pointer; display:flex; align-items:center; gap:6px; box-shadow:0 1px 2px rgba(0,0,0,0.05); }
.am-dropdown-btn:hover { background:#f3f4f6; }
.am-dropdown-menu { display:none; position:absolute; top:100%; left:0; margin-top:4px; width:340px; max-height:400px; background:#fff; border:1px solid #d1d5db; border-radius:8px; box-shadow:0 10px 25px rgba(0,0,0,0.15); z-index:100; flex-direction:column; box-sizing:border-box; }
.am-dropdown-menu.open { display:flex; }
.am-dropdown-header { padding:8px 10px; border-bottom:1px solid #e5e7eb; }
.am-dropdown-header input { width:100%; box-sizing:border-box; padding:5px 8px; font-size:12px; border:1px solid #d1d5db; border-radius:4px; outline:none; font-family:inherit; }
.am-dropdown-actions { display:flex; justify-content:space-between; padding:6px 10px; border-bottom:1px solid #e5e7eb; font-size:11px; }
.am-dropdown-actions a { color:#0d9e87; text-decoration:none; cursor:pointer; font-weight:500; }
.am-dropdown-actions a:hover { text-decoration:underline; }
.am-dropdown-list { overflow-y:auto; padding:6px 10px; max-height:280px; }
.am-community-item { user-select:none; }
.am-search-input { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 10px; font-size:12px; font-family:inherit; width:220px; outline:none; box-shadow:0 1px 2px rgba(0,0,0,0.05); }
.am-search-input:focus { border-color:#0d9e87; }
.am-kg-chip { font-size:11px; color:#64748b; background:#f1f5f9; padding:4px 8px; border-radius:6px; border:1px solid #e2e8f0; white-space:nowrap; }
.am-kg-canvas-full { width:100%; height:720px; border:1px solid #d1d5db; border-radius:8px; overflow:hidden; position:relative; background:#fff; }

[data-theme="dark"] body { background:#0d0f14; color:#c9d1d9; }
[data-theme="dark"] .am-header { border-bottom-color:#1e2430; }
[data-theme="dark"] .am-tab { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
[data-theme="dark"] .am-drawer { background:#0a0c10; color:#c9d1d9; box-shadow:-2px 0 20px rgba(0,0,0,.5); }
[data-theme="dark"] .am-node rect { fill:#13171f; stroke:#38bdf8; }
[data-theme="dark"] .am-node text { fill:#c9d1d9; }
[data-theme="dark"] .am-tree-file { color:#8b949e; }
[data-theme="dark"] .am-stale-banner { background:#451a03; border-color:#78350f; color:#fbbf24; }
[data-theme="dark"] .am-zoom-btn { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-zoom-btn:hover { background:#1e2430; }
[data-theme="dark"] .am-cluster-bg { fill:#13171f; stroke:#334155; }
[data-theme="dark"] .am-cluster-header { fill:#1e2430; }
[data-theme="dark"] .am-cluster-title { fill:#38bdf8; }
[data-theme="dark"] .am-cluster-detail { fill:#8b949e; }
.am-btn-action { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 12px; font-size:12px; font-family:inherit; cursor:pointer; display:inline-flex; align-items:center; gap:6px; box-shadow:0 1px 2px rgba(0,0,0,0.05); transition:all .15s ease; color:#1e293b; }
.am-btn-action:hover { background:#f1f5f9; border-color:#94a3b8; }
.am-btn-action:disabled { opacity:0.6; cursor:not-allowed; }
.kg-source-drawer { position:fixed; top:0; right:-520px; width:500px; height:100%; background:#fff; box-shadow:-4px 0 20px rgba(0,0,0,.2); z-index:1100; transition:right .25s ease-in-out; display:flex; flex-direction:column; box-sizing:border-box; }
.kg-source-drawer.open { right:0; }
.kg-source-header { padding:12px 16px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; background:#f8fafc; font-weight:600; font-size:13px; }
.kg-source-title { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:380px; }
.kg-source-badge { font-size:10px; background:#e2e8f0; color:#475569; padding:2px 6px; border-radius:4px; margin-left:6px; font-weight:normal; }
.kg-source-close { background:none; border:none; font-size:16px; cursor:pointer; color:#64748b; }
.kg-source-close:hover { color:#0f172a; }
.kg-source-body { flex:1; overflow:auto; padding:12px 16px; font-family:'SF Mono',monospace; font-size:12px; line-height:1.5; background:#ffffff; }
.kg-source-pre { margin:0; tab-size:4; white-space:pre; }
.am-kg-kind-filters { display:flex; align-items:center; gap:6px; }
.am-kind-chip { display:inline-flex; align-items:center; gap:4px; font-size:11px; padding:3px 8px; border-radius:12px; border:1px solid #d1d5db; background:#fff; cursor:pointer; user-select:none; }
.am-kind-chip:hover { background:#f1f5f9; }
.am-kind-chip input { margin:0; cursor:pointer; }
[data-theme="dark"] .kg-source-drawer { background:#0d1117; border-left:1px solid #30363d; color:#c9d1d9; box-shadow:-4px 0 20px rgba(0,0,0,.6); }
[data-theme="dark"] .kg-source-header { background:#161b22; border-bottom-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .kg-source-badge { background:#30363d; color:#8b949e; }
[data-theme="dark"] .kg-source-body { background:#0d1117; color:#c9d1d9; }
[data-theme="dark"] .am-kind-chip { background:#161b22; border-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .am-kind-chip:hover { background:#21262d; }
[data-theme="dark"] .am-dropdown-btn { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-dropdown-btn:hover { background:#1e2430; }
[data-theme="dark"] .am-dropdown-menu { background:#0a0c10; border-color:#1e2430; color:#c9d1d9; box-shadow:0 10px 25px rgba(0,0,0,0.5); }
[data-theme="dark"] .am-dropdown-header { border-bottom-color:#1e2430; }
[data-theme="dark"] .am-dropdown-header input { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-dropdown-actions { border-bottom-color:#1e2430; }
[data-theme="dark"] .am-search-input { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-kg-chip { background:#13171f; border-color:#1e2430; color:#8b949e; }
[data-theme="dark"] .am-btn-action { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-btn-action:hover { background:#1e2430; border-color:#334155; }
[data-theme="dark"] .am-kg-canvas-full { border-color:#1e2430; background:#0d0f14; }
.am-empty-hud { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:480px; background:radial-gradient(circle at center, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.8) 100%); border:1px solid rgba(255, 255, 255, 0.08); border-radius:12px; margin:16px; text-align:center; backdrop-filter:blur(12px); box-shadow:0 8px 32px 0 rgba(0, 0, 0, 0.37); }
.am-hud-card { max-width:520px; padding:32px 24px; }
.am-hud-badge { display:inline-block; padding:4px 10px; background:rgba(59, 130, 246, 0.15); color:#60a5fa; border:1px solid rgba(59, 130, 246, 0.3); border-radius:9999px; font-size:11px; font-weight:600; letter-spacing:0.05em; text-transform:uppercase; }
"""


def generate_architect_map_html(data: dict, port: int) -> str:
    """Generate the Architect Map view shell."""
    import json
    from synlynk.viz_views import derive_canonical_community_names

    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = workspace.get("updated_at", "")
    repos = workspace.get("repos") or []
    workspace_map = data.get("workspace_map") or {"edges": [], "edge_types": {}}
    edges = workspace_map.get("edges", [])
    edge_types = workspace_map.get("edge_types", {})

    if not repos:
        repos = [{"path": os.getcwd(), "name": workspace_name, "stack_labels": [], "github_url": None}]

    has_graphify = data.get("has_graphify")
    if has_graphify is None:
        repo_root = repos[0].get("path", os.getcwd()) if repos and isinstance(repos[0], dict) else os.getcwd()
        has_graphify = os.path.isfile(os.path.join(repo_root, ".synlynk", "graphify-out", "graph.html")) or os.path.isfile(os.path.join(repo_root, ".synlynk", "graphify-out", "graph.json"))

    nodes_json = json.dumps([
        {
            "id": r["name"],
            "label": r["name"],
            "path": r.get("path", ""),
            "stack_labels": r.get("stack_labels", []),
            "github_url": r.get("github_url"),
            "active_dream_count": r.get("active_dream_count", 0),
        }
        for r in repos
    ])
    edges_json = json.dumps(edges)
    edge_types_json = json.dumps(edge_types)
    file_tree_json = json.dumps(data.get("file_tree") or {"name": ".", "dirs": {}, "files": []})

    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{html.escape(et.get("color", "#94a3b8"))}"></span>{html.escape(et.get("label", key))}</div>'
        for key, et in edge_types.items()
    )

    style_content = _ARCHITECT_MAP_STYLE
    json_data = json.dumps(data)
    live_js_html = _live_js(port)

    is_monorepo = len(repos) <= 1

    is_stale = bool(data.get("discovery", {}).get("knowledge_graph", {}).get("stale"))
    if not is_stale:
        is_stale = bool((data.get("workspace_views") or {}).get("logical", {}).get("stale"))

    staleness_banner_html = ""
    if is_stale:
        staleness_banner_html = (
            '<div class="am-stale-banner" id="graph-stale-banner">'
            '<span>⚠️ Graph Stale (differs from HEAD commit) — '
            '<a href="#" onclick="triggerGraphRefresh(this); return false;" style="color:#b45309;text-decoration:underline;">[Refresh Index]</a></span>'
            '</div>'
        )

    if is_monorepo:
        logical_nodes = (data.get("workspace_views") or {}).get("logical", {}).get("nodes") or []
        comm_names = derive_canonical_community_names(logical_nodes)

        communities: Dict[Any, int] = {}
        for n in logical_nodes:
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
            communities_html = "".join(
                f'<label class="am-community-item" style="display:flex; align-items:center; gap:8px; padding:4px 0; font-size:12px; cursor:pointer;">'
                f'<input type="checkbox" class="am-community-checkbox" checked data-comm="{html.escape(str(cid))}" onchange="toggleAmCommunityFilter(this)">'
                f'<span class="legend-dot" style="background:{community_colors[i % len(community_colors)]}; width:10px; height:10px; border-radius:50%; display:inline-block; flex-shrink:0;"></span>'
                f'<span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{html.escape(comm_names.get(cid, f"Community {cid}"))}">{html.escape(comm_names.get(cid, f"Community {cid}"))} ({count})</span>'
                f'</label>'
                for i, (cid, count) in enumerate(sorted_comms)
            )
        else:
            communities_html = '<div style="font-size:11px; color:#64748b;">No Community clusters detected. Run <code>synlynk scan --deep</code>.</div>'

        switcher_html = """    <button class="am-tab active" data-view="knowledge" onclick="setArchitectView('knowledge')">Knowledge Graph</button>
    <button class="am-tab" data-view="tree" onclick="setArchitectView('tree')">File Tree</button>"""

        total_symbols = len(logical_nodes)
        num_clusters = len(communities)

        if has_graphify:
            canvas_inner = '<iframe id="am-graphify-frame" src="graphify.html" width="100%" height="100%" style="border:none;" title="Graphify Knowledge Graph"></iframe>'
        else:
            canvas_inner = f"""<div class="am-empty-hud" id="am-empty-hud">
    <div class="am-hud-card">
      <div class="am-hud-badge">AWAITING AST INDEXING</div>
      <h2 style="margin: 16px 0 8px 0; font-size: 20px; font-weight: 600; color: #f1f5f9;">Physical AST Graph Not Yet Indexed</h2>
      <p style="color: #94a3b8; font-size: 13px; max-width: 480px; line-height: 1.5; margin: 0 auto 20px auto;">
        The physical AST symbols, call hierarchies, and community clusters have not yet been extracted for workspace <span style="color:#60a5fa; font-weight:600;">{html.escape(workspace_name)}</span>. Run the deep scanner to index symbols and topology.
      </p>
      <div style="display:flex; justify-content:center; align-items:center; gap:12px; margin-bottom:14px;">
        <button type="button" class="am-btn-action" style="padding: 8px 18px; background: #2563eb; color: #fff; border-radius: 6px; font-weight: 500; cursor: pointer; border: none;" onclick="triggerAmKgRefresh(this)">⚡ Run AST Code Scan</button>
      </div>
      <div style="font-size: 11px; color: #64748b;">
        or run in terminal: <code style="background: rgba(255,255,255,0.06); padding: 3px 8px; border-radius: 4px; color: #cbd5e1;">synlynk scan --deep</code>
      </div>
    </div>
  </div>
  <iframe id="am-graphify-frame" data-src="graphify.html" width="100%" height="100%" style="border:none; display:none;" title="Graphify Knowledge Graph"></iframe>"""

        views_html = f"""{staleness_banner_html}
<div id="am-knowledge-view" class="am-view active">
  <div class="am-kg-topbar">
    <div class="am-kg-controls">
      <div class="am-dropdown">
        <button type="button" class="am-dropdown-btn" onclick="toggleAmKgDropdown(event)">
          <span>🌐 Communities: <strong id="am-kg-selected-count">All ({num_clusters})</strong></span>
          <span style="font-size:9px; color:#64748b;">▼</span>
        </button>
        <div class="am-dropdown-menu" id="am-kg-dropdown-menu">
          <div class="am-dropdown-header">
            <input type="text" placeholder="Filter communities..." oninput="filterAmKgCommunities(this.value)">
          </div>
          <div class="am-dropdown-actions">
            <a onclick="selectAllAmCommunities(true)">Select All</a>
            <a onclick="selectAllAmCommunities(false)">Deselect All</a>
          </div>
          <div class="am-dropdown-list" id="am-communities-list">
            {communities_html}
          </div>
        </div>
      </div>
      <input type="text" id="am-kg-search" class="am-search-input" placeholder="🔍 Search symbols..." oninput="filterKgSearch(this.value)">
      <div class="am-kg-kind-filters" id="am-kg-kind-filters">
        <label class="am-kind-chip"><input type="checkbox" checked value="Service Class" onchange="toggleAmKindFilter(this)"> Services</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="Module Cluster" onchange="toggleAmKindFilter(this)"> Modules</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="CLI Handler" onchange="toggleAmKindFilter(this)"> Handlers</label>
        <label class="am-kind-chip"><input type="checkbox" value="Test Suite" onchange="toggleAmKindFilter(this)"> Tests</label>
      </div>
      <span class="am-kg-chip" id="am-kg-status-chip">{num_clusters} Clusters · {total_symbols} AST Symbols</span>
      <button type="button" id="am-kg-refresh-btn" class="am-btn-action" onclick="triggerAmKgRefresh(this)" title="Re-extract AST Knowledge Graph">🔄 Refresh Graph</button>
    </div>
  </div>
  <div class="am-kg-canvas-full">
    {canvas_inner}
  </div>
</div>
<div id="am-tree-view" class="am-view">
  <div id="am-tree-root" class="am-tree"></div>
</div>"""
    else:
        switcher_html = """    <button class="am-tab active" data-view="graph" onclick="setArchitectView('graph')">Clustered Canvas</button>
    <button class="am-tab" data-view="tree" onclick="setArchitectView('tree')">File Tree</button>"""

        views_html = f"""{staleness_banner_html}
<div class="am-legend">{legend_html}</div>
<div id="am-graph-view" class="am-view active" style="position:relative;">
  <div class="am-zoom-controls">
    <button type="button" class="am-zoom-btn" onclick="amZoomIn()" title="Zoom In">➕</button>
    <button type="button" class="am-zoom-btn" onclick="amZoomOut()" title="Zoom Out">➖</button>
    <button type="button" class="am-zoom-btn" onclick="amZoomReset()" title="Reset LOD Zoom">⊙ Reset</button>
  </div>
  <svg id="am-svg" width="100%" height="680" style="background:#fff; border-radius:8px; border:1px solid #d1d5db;"></svg>
</div>
<div id="am-tree-view" class="am-view">
  <div id="am-tree-root" class="am-tree"></div>
</div>"""

    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Architect Map</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>
<div class="am-header">
  <h1>Architect Map — __WORKSPACE_NAME__</h1>
  <div class="am-switcher">
__SWITCHER_HTML__
  </div>
</div>
__VIEWS_HTML__
<div class="ov" id="am-ov" onclick="closeDrawer()"></div>
<div class="am-drawer" id="am-drawer">
  <div class="am-drawer-header">
    <span id="am-drawer-title">—</span>
    <button onclick="closeDrawer()">✕</button>
  </div>
  <div class="am-drawer-body" id="am-drawer-body"></div>
  <div class="am-drawer-actions">
    <button class="btn" onclick="drawerDispatch()">Dispatch to this repo</button>
    <button class="btn" onclick="drawerJumpGantt()">Jump to Gantt view</button>
    <a class="btn" id="am-drawer-github" href="#" target="_blank" rel="noopener">Open on GitHub</a>
  </div>
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
window.VIZOR_DATA = __JSON_DATA__;
window.ARCHITECT_NODES = __NODES_JSON__;
window.ARCHITECT_EDGES = __EDGES_JSON__;
window.ARCHITECT_EDGE_TYPES = __EDGE_TYPES_JSON__;
window.ARCHITECT_FILE_TREE = __FILE_TREE_JSON__;
window.VIZOR_PORT = __PORT__;
__ARCHITECT_MAP_JS__
</script>
__LIVE_JS_HTML__
</body>
</html>"""
    return (
        template
        .replace("__STYLE_CONTENT__", style_content)
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__SWITCHER_HTML__", switcher_html)
        .replace("__VIEWS_HTML__", views_html)
        .replace("__JSON_DATA__", json_data)
        .replace("__NODES_JSON__", nodes_json)
        .replace("__EDGES_JSON__", edges_json)
        .replace("__EDGE_TYPES_JSON__", edge_types_json)
        .replace("__FILE_TREE_JSON__", file_tree_json)
        .replace("__PORT__", str(port))
        .replace("__ARCHITECT_MAP_JS__", _ARCHITECT_MAP_JS)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )

