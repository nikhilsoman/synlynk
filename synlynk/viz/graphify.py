"""Graphify HTML enrichment for the architect canvas."""
import json
import re
def _enrich_graphify_html(html_str: str, graph_data: dict) -> str:
    """Enrich Graphify HTML graph with canonical community metadata, LOD zoom degree filtering, and rich sidebar."""
    if not html_str:
        return html_str

    from synlynk.viz_views import derive_canonical_community_metadata
    nodes = graph_data.get("nodes") or []
    meta_map = derive_canonical_community_metadata(nodes)

    m = re.search(r'const RAW_NODES = (\[.*?\]);', html_str, re.DOTALL)
    if m:
        try:
            raw_nodes = json.loads(m.group(1))
            for rn in raw_nodes:
                cid = rn.get("community")
                if cid in meta_map:
                    c_info = meta_map[cid]
                    cname = c_info.get("name") or rn.get("label")
                    rn["label"] = cname
                    rn["community_name"] = cname
                    rn["source_file"] = c_info.get("source_file") or rn.get("source_file") or ""
                    rn["file_type"] = c_info.get("kind") or "Module Cluster"
                    rn["_source_file"] = rn["source_file"]
                    rn["_file_type"] = rn["file_type"]
                    rn["_community_name"] = cname
                    rn["desc"] = c_info.get("desc") or ""
                    rn["_desc"] = rn["desc"]
                    rn["symbols"] = c_info.get("symbols") or []
                    rn["_symbols"] = rn["symbols"]
                    rn["title"] = f"{cname}\n{rn['desc']}\n{rn['file_type']} · {rn.get('degree', 0)} connections"
            new_nodes_json = json.dumps(raw_nodes)
            html_str = html_str[:m.start(1)] + new_nodes_json + html_str[m.end(1):]
        except Exception:
            pass

    lod_styles = """
<style>
  #graph-wrap { flex: 1; position: relative; min-width: 0; min-height: 0; }
  #graph-wrap #graph { position: absolute; inset: 0; flex: none; }
  .vis-map-zoom-bar {
    position: absolute;
    top: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: rgba(26, 26, 46, 0.88);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 8px;
    padding: 6px;
    z-index: 1000;
    box-shadow: 0 4px 16px rgba(0,0,0,0.35);
    user-select: none;
    pointer-events: auto;
  }
  .vis-zoom-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #fff;
    font-size: 15px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .vis-zoom-btn:hover {
    background: rgba(255, 255, 255, 0.22);
    border-color: rgba(255, 255, 255, 0.35);
  }
  .vis-zoom-stepper {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin: 4px 0;
    width: 100%;
  }
  .vis-zoom-step {
    font-size: 10px;
    font-weight: 600;
    padding: 3px 6px;
    text-align: center;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.05);
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .vis-zoom-step:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
  }
  .vis-zoom-step.active {
    background: #0d9e87;
    color: #ffffff;
    font-weight: bold;
    box-shadow: 0 0 8px rgba(13, 158, 135, 0.6);
  }
  .vis-zoom-badge {
    font-size: 9px;
    color: #cbd5e1;
    text-align: center;
    margin-top: 2px;
    white-space: nowrap;
    font-family: inherit;
  }
  .info-type-pill {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    background: rgba(13, 158, 135, 0.25);
    color: #2dd4bf;
    margin-bottom: 8px;
  }
  .info-desc-box {
    font-size: 12px;
    line-height: 1.5;
    color: #cbd5e1;
    margin-bottom: 12px;
    padding: 8px;
    background: rgba(0, 0, 0, 0.25);
    border-left: 3px solid #0d9e87;
    border-radius: 3px;
  }
  .info-section-title {
    margin-top: 12px;
    margin-bottom: 6px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
    font-weight: 600;
  }
  .info-symbol-tag {
    display: inline-block;
    font-size: 11px;
    padding: 2px 6px;
    margin: 2px 4px 2px 0;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    font-family: monospace;
    color: #e2e8f0;
  }
</style>
"""
    if "</head>" in html_str and ".vis-map-zoom-bar" not in html_str:
        html_str = html_str.replace("</head>", lod_styles + "</head>", 1)

    zoom_bar_html = """
<div class="vis-map-zoom-bar" id="vis-zoom-bar">
  <button type="button" class="vis-zoom-btn" onclick="zoomInStep()" title="Zoom In">+</button>
  <div class="vis-zoom-stepper">
    <div class="vis-zoom-step" data-level="3" onclick="setLODLevel(3)" title="Level 3: Micro (All symbols)">L3</div>
    <div class="vis-zoom-step" data-level="2" onclick="setLODLevel(2)" title="Level 2: Detailed (≥1 conns)">L2</div>
    <div class="vis-zoom-step" data-level="1" onclick="setLODLevel(1)" title="Level 1: Subsystem (≥2 conns)">L1</div>
    <div class="vis-zoom-step active" data-level="0" onclick="setLODLevel(0)" title="Level 0: Macro (≥3 conns)">L0</div>
  </div>
  <button type="button" class="vis-zoom-btn" onclick="zoomOutStep()" title="Zoom Out">−</button>
  <button type="button" class="vis-zoom-btn" onclick="resetFitLOD()" title="Reset / Fit Overview" style="font-size:12px;">⊙</button>
  <div class="vis-zoom-badge" id="vis-zoom-badge">L0 (≥3)</div>
</div>
"""
    if '<div id="graph"></div>' in html_str and 'id="vis-zoom-bar"' not in html_str:
        html_str = html_str.replace(
            '<div id="graph"></div>',
            '<div id="graph-wrap">' + zoom_bar_html + '<div id="graph"></div></div>',
            1,
        )

    lod_and_info_script = """
// Dynamic Percentile-based LOD Threshold Calculation
function computeDynamicLODThresholds() {
  if (typeof RAW_NODES === 'undefined' || !RAW_NODES.length) return [8, 4, 2, 0];
  const codeNodes = RAW_NODES.filter(n => (n.file_type || n._file_type) !== 'Test Suite');
  const degs = (codeNodes.length ? codeNodes : RAW_NODES).map(n => n.degree || n._degree || 0).sort((a, b) => b - a);
  if (!degs.length) return [8, 4, 2, 0];

  // L0: Top 10% or highest 10-12 nodes for clean macro architecture
  const l0Idx = Math.min(degs.length - 1, Math.max(8, Math.floor(degs.length * 0.10)));
  const l0 = Math.max(degs[l0Idx] || 6, 5);
  // L1: Top 30% for subsystem boundaries
  const l1Idx = Math.min(degs.length - 1, Math.floor(degs.length * 0.30));
  const l1 = Math.max(degs[l1Idx] || 3, 3);
  // L2: Top 65% for component modules
  const l2Idx = Math.min(degs.length - 1, Math.floor(degs.length * 0.65));
  const l2 = Math.max(degs[l2Idx] || 1, 1);
  const l3 = 0;

  return [l0, l1, l2, l3];
}

const LOD_THRESHOLDS = computeDynamicLODThresholds();
const LOD_SCALE_TIERS = [
  { minScale: 0.0, maxScale: 0.45, level: 0, label: 'L0 (Macro Core: ≥' + LOD_THRESHOLDS[0] + ')', minDegree: LOD_THRESHOLDS[0], targetScale: 0.35 },
  { minScale: 0.45, maxScale: 0.85, level: 1, label: 'L1 (Subsystems: ≥' + LOD_THRESHOLDS[1] + ')', minDegree: LOD_THRESHOLDS[1], targetScale: 0.60 },
  { minScale: 0.85, maxScale: 1.40, level: 2, label: 'L2 (Components: ≥' + LOD_THRESHOLDS[2] + ')', minDegree: LOD_THRESHOLDS[2], targetScale: 1.05 },
  { minScale: 1.40, maxScale: 99.0, level: 3, label: 'L3 (All Symbols)', minDegree: 0, targetScale: 1.60 }
];

let currentLODLevel = 0; // 0: Macro, 1: Subsystem, 2: Component, 3: Micro
let activeInspectedNodeId = null;
let inspectedEgoSet = new Set();
let activeKindFilters = null;
let currentSearchQuery = '';

function updateLODControlUI(level, visibleCount, totalCount) {
  document.querySelectorAll('.vis-zoom-step').forEach(el => {
    const elLvl = parseInt(el.dataset.level, 10);
    if (elLvl === level) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });
  const badge = document.getElementById('vis-zoom-badge');
  if (badge && LOD_SCALE_TIERS[level]) {
    badge.textContent = LOD_SCALE_TIERS[level].label;
  }
}

function growEgoNetwork(nodeId) {
  if (!nodeId || typeof network === 'undefined') return;
  inspectedEgoSet.add(String(nodeId));
  try {
    const neighbors = network.getConnectedNodes(nodeId) || [];
    neighbors.forEach(nid => inspectedEgoSet.add(String(nid)));
  } catch (_) {}
  activeInspectedNodeId = nodeId;
  showInfo(nodeId);
  applyLODAndFilter();
}

function inspectSourceCode(filePath, startLine, endLine) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({
      type: 'open-source-drawer',
      file: filePath,
      start_line: startLine,
      end_line: endLine
    }, '*');
  }
}

function applyLODAndFilter() {
  if (typeof RAW_NODES === 'undefined' || typeof nodesDS === 'undefined') return;
  const minDegree = LOD_THRESHOLDS[currentLODLevel] !== undefined ? LOD_THRESHOLDS[currentLODLevel] : 3;
  const updates = [];
  const q = (currentSearchQuery || '').toLowerCase().trim();

  let visibleCount = 0;
  RAW_NODES.forEach(n => {
    const cKey = String(n.community);
    const isCommEnabled = typeof hiddenCommunities !== 'undefined' ? !hiddenCommunities.has(n.community) && !hiddenCommunities.has(cKey) : true;
    const k = n.file_type || n._file_type || 'Module Cluster';
    const isKindAllowed = (!activeKindFilters || activeKindFilters.size === 0 || activeKindFilters.has(k));
    const deg = n.degree || n._degree || 0;
    const meetsDegree = deg >= minDegree;
    const isInspected = inspectedEgoSet.size > 0 ? inspectedEgoSet.has(String(n.id)) : false;

    const visible = isCommEnabled && isKindAllowed && (meetsDegree || isInspected);
    if (visible) visibleCount++;

    let opacity = 1.0;
    if (q) {
      const match = (n.label || '').toLowerCase().includes(q) || (n.title || '').toLowerCase().includes(q) || (n.source_file || '').toLowerCase().includes(q);
      opacity = match ? 1.0 : 0.15;
    }
    updates.push({ id: n.id, hidden: !visible, opacity: opacity });
  });

  nodesDS.update(updates);
  updateLODControlUI(currentLODLevel, visibleCount, RAW_NODES.length);

  if (window.parent && window.parent !== window) {
    try {
      window.parent.postMessage({
        type: 'lod-status-update',
        level: currentLODLevel,
        minDegree: minDegree,
        visibleCount: visibleCount,
        totalCount: RAW_NODES.length
      }, '*');
    } catch (_) {}
  }
}

function setLODLevel(level, animate = true) {
  currentLODLevel = Math.max(0, Math.min(3, level));
  if (typeof network !== 'undefined' && LOD_SCALE_TIERS[currentLODLevel]) {
    const targetScale = LOD_SCALE_TIERS[currentLODLevel].targetScale;
    if (animate) {
      network.moveTo({ scale: targetScale, animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
    }
  }
  applyLODAndFilter();
}

function zoomInStep() {
  if (typeof network !== 'undefined') {
    const curScale = network.getScale();
    const newScale = Math.min(curScale * 1.35, 3.5);
    network.moveTo({ scale: newScale, animation: { duration: 250 } });
  }
}

function zoomOutStep() {
  if (typeof network !== 'undefined') {
    const curScale = network.getScale();
    const newScale = Math.max(curScale / 1.35, 0.15);
    network.moveTo({ scale: newScale, animation: { duration: 250 } });
  }
}

function resetFitLOD() {
  currentLODLevel = 0;
  if (typeof network !== 'undefined') {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
  }
  applyLODAndFilter();
}

function showInfo(nodeId) {
  if (typeof nodesDS === 'undefined') return;
  const n = nodesDS.get(nodeId);
  if (!n) return;
  activeInspectedNodeId = nodeId;

  let neighborItems = '';
  let neighborIds = [];
  if (typeof network !== 'undefined') {
    try {
      neighborIds = network.getConnectedNodes(nodeId) || [];
      neighborItems = neighborIds.map(nid => {
        const nb = nodesDS.get(nid);
        const color = nb && nb.color ? (nb.color.background || '#555') : '#555';
        const label = nb ? nb.label : nid;
        return `<span class="neighbor-link" style="border-left-color:${color}; cursor:pointer;" onclick="growEgoNetwork('${nid}')" title="Click to grow ego network around ${label}">${label}</span>`;
      }).join('');
    } catch (_) {}
  }

  const rawSymbols = n.symbols || n._symbols || [];
  const symbolsHtml = rawSymbols.map(s => {
    const symName = typeof s === 'string' ? s : (s.label || s.name || '');
    return `<span class="info-symbol-tag">${symName}</span>`;
  }).join('');

  const typeLabel = n.file_type || n._file_type || 'Module Cluster';
  const descText = n.desc || n._desc || 'Component cluster with cross-module AST connections.';
  const sourceFile = n.source_file || n._source_file || '-';
  const degCount = n.degree !== undefined ? n.degree : (n._degree !== undefined ? n._degree : 0);
  const inspectBtn = (sourceFile && sourceFile !== '-')
    ? `<a href="#" style="color:#38bdf8; margin-left:8px; font-size:11px; text-decoration:underline;" onclick="inspectSourceCode('${sourceFile}', ${n.start_line || 1}, ${n.end_line || 50}); return false;">[Inspect Source]</a>`
    : '';

  const infoEl = document.getElementById('info-content');
  if (infoEl) {
    infoEl.innerHTML = `
      <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:4px; word-break:break-word;">${n.label}</div>
      <div class="info-type-pill">${typeLabel}</div>
      
      <div class="info-desc-box">
        ${descText}
      </div>

      <div class="field" style="font-size:12px; margin-bottom:4px;"><b>Source:</b> <code style="color:#38bdf8;">${sourceFile}</code>${inspectBtn}</div>
      <div class="field" style="font-size:12px; margin-bottom:4px;"><b>Community:</b> ${n.community !== undefined ? n.community : '-'}</div>
      <div class="field" style="font-size:12px; margin-bottom:8px;"><b>Connectivity:</b> <span style="font-weight:600; color:#2dd4bf;">${degCount}</span> edges</div>

      ${symbolsHtml ? `<div class="info-section-title">Contained Symbols (${rawSymbols.length})</div><div style="margin-bottom:10px;">${symbolsHtml}</div>` : ''}

      ${neighborIds.length ? `<div class="info-section-title">Connected Neighbors (${neighborIds.length})</div><div id="neighbors-list" style="max-height:160px; overflow-y:auto;">${neighborItems}</div>` : ''}
    `;
  }
}

if (typeof network !== 'undefined') {
  network.on('zoom', function(params) {
    const scale = params.scale;
    let newLevel = 0;
    for (const tier of LOD_SCALE_TIERS) {
      if (scale >= tier.minScale && scale < tier.maxScale) {
        newLevel = tier.level;
        break;
      }
    }
    if (newLevel !== currentLODLevel) {
      currentLODLevel = newLevel;
      applyLODAndFilter();
    }
  });

  network.on('selectNode', function(params) {
    if (params.nodes && params.nodes.length > 0) {
      const selId = params.nodes[0];
      if (inspectedEgoSet.size > 0 && inspectedEgoSet.has(String(selId))) {
        growEgoNetwork(selId);
      } else {
        inspectedEgoSet.clear();
        growEgoNetwork(selId);
      }
    }
  });

  network.on('deselectNode', function() {
    activeInspectedNodeId = null;
    inspectedEgoSet.clear();
    applyLODAndFilter();
  });

  network.once('afterDrawing', function() {
    applyLODAndFilter();
  });
}

// Global Message Listener for Parent Vizor Windows
window.addEventListener('message', function(e) {
  if (!e.data) return;
  if (e.data.type === 'set-lod') {
    if (e.data.level !== undefined) setLODLevel(e.data.level);
  } else if (e.data.type === 'filter-community') {
    const comm = e.data.community;
    const enabled = e.data.enabled;
    if (typeof hiddenCommunities !== 'undefined') {
      if (enabled) {
        hiddenCommunities.delete(comm);
        hiddenCommunities.delete(parseInt(comm, 10));
      } else {
        hiddenCommunities.add(comm);
        hiddenCommunities.add(parseInt(comm, 10));
      }
    }
    applyLODAndFilter();
  } else if (e.data.type === 'filter-communities-batch') {
    const enabledMap = e.data.enabledMap || {};
    const allEnabled = e.data.allEnabled;
    if (typeof hiddenCommunities !== 'undefined' && typeof LEGEND !== 'undefined') {
      LEGEND.forEach(c => {
        let isEnabled = true;
        if (allEnabled !== undefined) {
          isEnabled = allEnabled;
        } else if (enabledMap[String(c.cid)] !== undefined) {
          isEnabled = enabledMap[String(c.cid)];
        }
        if (isEnabled) {
          hiddenCommunities.delete(c.cid);
          hiddenCommunities.delete(String(c.cid));
        } else {
          hiddenCommunities.add(c.cid);
          hiddenCommunities.add(String(c.cid));
        }
      });
    }
    applyLODAndFilter();
  } else if (e.data.type === 'filter-kind-l0') {
    activeKindFilters = Array.isArray(e.data.kinds) ? new Set(e.data.kinds) : null;
    applyLODAndFilter();
  } else if (e.data.type === 'grow-ego-network') {
    growEgoNetwork(e.data.nodeId);
  } else if (e.data.type === 'reset-inspect') {
    activeInspectedNodeId = null;
    inspectedEgoSet.clear();
    applyLODAndFilter();
  } else if (e.data.type === 'search') {
    currentSearchQuery = e.data.query || '';
    applyLODAndFilter();
  } else if (e.data.type === 'theme-change') {
    const theme = e.data.theme;
    if (theme === 'dark') {
      document.body.style.background = '#0d0f14';
      document.body.style.color = '#c9d1d9';
    } else {
      document.body.style.background = '#ffffff';
      document.body.style.color = '#1f2328';
    }
  }
});
"""

    if "</script>" in html_str and "LOD_THRESHOLDS" not in html_str:
        last_script = html_str.rfind("</script>")
        html_str = html_str[:last_script] + lod_and_info_script + html_str[last_script:]

    return html_str

