"""User-journey canvas."""
import json
from synlynk.viz.chrome import _live_js
def generate_journeys_html(data: dict, port: int) -> str:
    data_json = json.dumps(data)
    live_js_block = _live_js(port)
    html_template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — User Journeys</title>
<style>
/* ══════════════════════════════════════════════
   THEME TOKENS
   ══════════════════════════════════════════════ */
:root {
  --bg:        #f6f8fa;  --bg2: #ffffff; --bg3: #eaeef2;
  --border:    #d1d5db;  --border2: #e8ebee;
  --text:      #1f2328;  --text2: #57606a; --text3: #8b949e;
  --accent:    #0d9e87;  --accent-bg: #e6f7f4; --accent-dim: #c0ede6;
  --shadow:    0 2px 12px rgba(0,0,0,.10);

  /* Stage colors: design/blue, plan/purple, build/teal, ship/green, sustain/amber */
  --s-design-bg:  #dbeafe; --s-design-bd:  #93c5fd; --s-design-tx:  #1d4ed8;
  --s-plan-bg:    #ede9fe; --s-plan-bd:    #c4b5fd; --s-plan-tx:    #6d28d9;
  --s-build-bg:   #e6f7f4; --s-build-bd:   #c0ede6; --s-build-tx:   #0d9e87;
  --s-ship-bg:    #dcfce7; --s-ship-bd:    #86efac; --s-ship-tx:    #15803d;
  --s-sustain-bg: #fef3c7; --s-sustain-bd: #fde68a; --s-sustain-tx: #d97706;

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

  --s-design-bg:  #1e3a5a; --s-design-bd:  #3a6090; --s-design-tx:  #60a5fa;
  --s-plan-bg:    #2d1f5e; --s-plan-bd:    #4a3f80; --s-plan-tx:    #a78bfa;
  --s-build-bg:   #0d2a2a; --s-build-bd:   #1f4d45; --s-build-tx:   #3de0c0;
  --s-ship-bg:    #1a4a2e; --s-ship-bd:    #2a7040; --s-ship-tx:    #4ade80;
  --s-sustain-bg: #451a03; --s-sustain-bd: #78350f; --s-sustain-tx: #fbbf24;

  --ag-claude-bg:#0d2a2a;--ag-claude-bd:#3de0c0;--ag-claude-tx:#3de0c0;
  --ag-agy-bg:  #0d1a3a;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #4285f4;
  --ag-codex-bg:#0a1f18;--ag-codex-bd:#10a37f;--ag-codex-tx:#10a37f;
  --ag-grok-bg: #1a1a1a;--ag-grok-bd: #e0e0e0;--ag-grok-tx: #e0e0e0;
  --ag-muse-bg: #2e081d;--ag-muse-bd: #f472b6;--ag-muse-tx: #f472b6;
}

* { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background:var(--bg);
  color:var(--text);
  font-size:13px;
  transition:background .2s,color .2s;
  overflow:hidden;
}

/* Split Pane Layout */
.split-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
.left-panel {
  width: 280px;
  min-width: 200px;
  max-width: 500px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}
.resizer {
  width: 5px;
  background: transparent;
  cursor: col-resize;
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  transition: background 0.15s;
}
.resizer:hover, .resizer.dragging {
  background: var(--accent);
}
.right-panel {
  flex: 1;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Left Panel Header & Rows */
.panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  font-weight: 750;
  color: var(--text);
  background: var(--bg2);
}
.journey-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.journey-row {
  padding: 12px 16px;
  cursor: pointer;
  color: var(--text2);
  font-weight: 500;
  border-bottom: 1px solid var(--border2);
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.journey-row:hover {
  background: var(--bg3);
  color: var(--text);
}
.journey-row.active {
  background: var(--accent-bg);
  color: var(--accent);
  border-left: 3px solid var(--accent);
  padding-left: 13px;
}
.journey-steps-count {
  font-size: 10px;
  background: var(--bg3);
  color: var(--text3);
  padding: 2px 6px;
  border-radius: 8px;
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
}
.journey-row.active .journey-steps-count {
  background: var(--accent-dim);
  color: var(--accent);
}

/* FTUE Notice Banner */
.ftue-notice {
  background: var(--accent-bg);
  border-bottom: 1px solid var(--accent-dim);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  z-index: 5;
  animation: slideDown 0.3s ease;
}
@keyframes slideDown {
  from { transform: translateY(-100%); }
  to { transform: translateY(0); }
}
.notice-text {
  color: var(--accent);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}
.close-notice-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  opacity: 0.7;
  transition: opacity 0.15s;
}
.close-notice-btn:hover {
  opacity: 1;
}

/* Right Panel Content Header & Flow */
.right-header {
  padding: 16px 24px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  min-height: 53px;
  display: flex;
  align-items: center;
}
.right-header-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.flow-viewport {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 40px 24px;
  display: flex;
  align-items: center;
  background: var(--bg);
}
.flow-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* Cards & Arrows */
.step-card {
  width: 200px;
  min-height: 120px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: var(--shadow);
  transition: transform 0.2s, box-shadow 0.2s;
  flex-shrink: 0;
}
.step-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0,0,0,.12);
}
[data-theme="dark"] .step-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,.4);
}
.step-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
}
.step-route {
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--text3);
  background: var(--bg3);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.step-desc {
  font-size: 11px;
  color: var(--text2);
  line-height: 1.4;
  flex: 1;
  word-break: break-word;
}
.step-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  flex-shrink: 0;
}

/* Stage Badge Pill Styles */
.stage-pill {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid;
  letter-spacing: 0.5px;
}
.st-design { background: var(--s-design-bg); border-color: var(--s-design-bd); color: var(--s-design-tx); }
.st-plan { background: var(--s-plan-bg); border-color: var(--s-plan-bd); color: var(--s-plan-tx); }
.st-build { background: var(--s-build-bg); border-color: var(--s-build-bd); color: var(--s-build-tx); }
.st-ship { background: var(--s-ship-bg); border-color: var(--s-ship-bd); color: var(--s-ship-tx); }
.st-sustain { background: var(--s-sustain-bg); border-color: var(--s-sustain-bd); color: var(--s-sustain-tx); }
.st-unknown { background: var(--bg3); border-color: var(--border); color: var(--text3); }

/* Agent Avatar Badges */
.aa {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 800;
  flex-shrink: 0;
  border: 1.5px solid;
  cursor: default;
}
.aa-claude { background: var(--ag-claude-bg); border-color: var(--ag-claude-bd); color: var(--ag-claude-tx); }
.aa-agy    { background: var(--ag-agy-bg);    border-color: var(--ag-agy-bd);    color: var(--ag-agy-tx);    }
.aa-codex  { background: var(--ag-codex-bg);  border-color: var(--ag-codex-bd);  color: var(--ag-codex-tx);  font-size: 8px; }
.aa-grok   { background: var(--ag-grok-bg);   border-color: var(--ag-grok-bd);   color: var(--ag-grok-tx);   }
.aa-muse   { background: var(--ag-muse-bg);   border-color: var(--ag-muse-bd);   color: var(--ag-muse-tx);   }
.aa-unknown { background: var(--bg3); border-color: var(--border); color: var(--text3); }

.flow-arrow {
  font-size: 20px;
  color: var(--text3);
  user-select: none;
  font-weight: bold;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
}

/* Empty State Styles */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px;
  text-align: center;
  color: var(--text2);
  background: var(--bg);
}
.empty-state-icon {
  font-size: 40px;
  margin-bottom: 16px;
  opacity: 0.6;
}
.empty-state-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text);
}
.empty-state-desc {
  font-size: 12px;
  max-width: 480px;
  line-height: 1.6;
  color: var(--text3);
  background: var(--bg2);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: 8px;
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  text-align: left;
}
</style>
</head>
<body>

<header style="height:44px;padding:0 20px;display:flex;align-items:center;gap:20px;background:var(--bg2);border-bottom:1px solid var(--border);flex-shrink:0;font-size:13px;font-family:inherit">
  <span style="font-weight:700;color:var(--text)">🗺 User Journeys</span>
  <span style="color:var(--text3)">Screen-by-screen flows from docs/journeys/</span>
</header>
<div id="app-container" style="height: calc(100vh - 44px); width: 100vw; display: flex; flex-direction: column;"></div>

<script>
window.VIZOR_DATA = {{data_json}};
</script>
<script>
function setTheme(t) {
  const resolved = t === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : t;
  document.documentElement.setAttribute('data-theme', resolved);
}
setTheme(localStorage.getItem('vizor-theme') || 'system');
window.addEventListener('storage', (e) => {
  if (e.key === 'vizor-theme') {
    setTheme(e.newValue);
  }
});

let selectedJourneyId = null;

function getAgentDetails(name) {
  const n = (name || '').trim().toLowerCase();
  if (n.startsWith('claude')) return { cls: 'aa-claude', lbl: 'C' };
  if (n.startsWith('agy')) return { cls: 'aa-agy', lbl: 'A' };
  if (n.startsWith('codex')) return { cls: 'aa-codex', lbl: 'Cx' };
  if (n.startsWith('grok')) return { cls: 'aa-grok', lbl: 'G' };
  if (!n) return null;
  return { cls: 'aa-unknown', lbl: n.charAt(0).toUpperCase() };
}

function getStageClass(stage) {
  const s = (stage || '').trim().toLowerCase();
  if (s === 'design') return 'st-design';
  if (s === 'plan') return 'st-plan';
  if (s === 'build') return 'st-build';
  if (s === 'ship') return 'st-ship';
  if (s === 'sustain') return 'st-sustain';
  return 'st-unknown';
}

function dismissNotice() {
  const notice = document.getElementById('ftue-notice');
  if (notice) {
    notice.style.display = 'none';
  }
}

function selectJourney(id) {
  selectedJourneyId = id;
  
  // Highlight row
  document.querySelectorAll('.journey-row').forEach(row => {
    if (row.getAttribute('data-id') === id) {
      row.classList.add('active');
    } else {
      row.classList.remove('active');
    }
  });

  const journey = window.VIZOR_DATA.journeys.find(j => j.id === id);
  if (!journey) return;

  // Render header
  const header = document.getElementById('right-header-title');
  if (header) {
    header.textContent = journey.name;
  }

  // Render flow
  const viewport = document.getElementById('flow-viewport');
  if (!viewport) return;

  if (!journey.steps || journey.steps.length === 0) {
    viewport.innerHTML = '<div class="empty-state"><div class="empty-state-title">No steps defined for this journey</div></div>';
    return;
  }

  let html = '<div class="flow-row">';
  journey.steps.forEach((step, idx) => {
    const stageCls = getStageClass(step.stage);
    const stageLabel = step.stage || 'unknown';
    const agent = getAgentDetails(step.agent);
    
    let agentHtml = '';
    if (agent) {
      agentHtml = `<div class="aa ${agent.cls}" title="Agent: ${step.agent}">${agent.lbl}</div>`;
    }

    html += `
      <div class="step-card">
        <div class="step-name">${step.screen || 'Screen'}</div>
        <div class="step-route" title="${step.route || ''}">${step.route || '/'}</div>
        <div class="step-desc">${step.desc || ''}</div>
        <div class="step-footer">
          <div class="stage-pill ${stageCls}">${stageLabel}</div>
          ${agentHtml}
        </div>
      </div>
    `;

    if (idx < journey.steps.length - 1) {
      html += '<div class="flow-arrow">→</div>';
    }
  });
  html += '</div>';
  viewport.innerHTML = html;
}

function initApp() {
  const container = document.getElementById('app-container');
  const data = window.VIZOR_DATA;

  if (!data || !data.journeys || data.journeys.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🗺️</div>
        <div class="empty-state-title">User Journeys</div>
        <div class="empty-state-desc">No journeys found. Create docs/journeys/ with .md files, each starting with a # H1 title. Steps use ## Screen Name headings with route:, desc:, agent:, stage: key-value lines.</div>
      </div>
    `;
    return;
  }

  let leftRowsHtml = '';
  data.journeys.forEach(j => {
    const stepCount = j.steps ? j.steps.length : 0;
    leftRowsHtml += `
      <div class="journey-row" data-id="${j.id}" onclick="selectJourney('${j.id}')">
        <span>${j.name}</span>
        <span class="journey-steps-count">${stepCount} step${stepCount !== 1 ? 's' : ''}</span>
      </div>
    `;
  });

  const showFTUE = data.workspace && data.workspace.vizor_second_view === 'tube';
  const noticeStyle = showFTUE ? 'display: flex;' : 'display: none;';

  container.innerHTML = `
    <div class="split-container">
      <div class="left-panel" id="left-panel">
        <div class="panel-header">User Journeys</div>
        <div class="journey-list">${leftRowsHtml}</div>
      </div>
      <div class="resizer" id="resizer"></div>
      <div class="right-panel" id="right-panel">
        <div class="ftue-notice" id="ftue-notice" style="${noticeStyle}">
          <span class="notice-text">Your workspace is configured for the Architect Map as the primary structural view. User Journeys is available if your project has UX screens.</span>
          <button class="close-notice-btn" onclick="dismissNotice()">✕</button>
        </div>
        <div class="right-header">
          <div class="right-header-title" id="right-header-title">Select a Journey</div>
        </div>
        <div class="flow-viewport" id="flow-viewport"></div>
      </div>
    </div>
  `;

  const resizer = document.getElementById('resizer');
  const leftPanel = document.getElementById('left-panel');
  let isDragging = false;

  resizer.addEventListener('mousedown', (e) => {
    isDragging = true;
    resizer.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const newWidth = e.clientX;
    if (newWidth >= 200 && newWidth <= 500) {
      leftPanel.style.width = `${newWidth}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      resizer.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  });

  if (data.journeys.length > 0) {
    selectJourney(data.journeys[0].id);
  }
}

initApp();
</script>
{_live_js(port)}
</body>
</html>"""
    return html_template.replace("{{data_json}}", data_json).replace("{_live_js(port)}", live_js_block)

