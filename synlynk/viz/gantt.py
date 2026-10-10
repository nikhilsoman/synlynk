"""Release timeline (Gantt) canvas."""
import html
import json
from synlynk.viz.chrome import _live_js
_GANTT_STYLE = """
/* ══════════════════════════════════════════════
   THEME TOKENS
══════════════════════════════════════════════ */
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
}

* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'SF Mono','JetBrains Mono',monospace; background:var(--bg); color:var(--text); font-size:13px; transition:background .2s,color .2s; padding:20px 24px 48px; }

.content { width:100%; max-width:100%; }
.ws-header { display:flex;align-items:center;gap:12px;margin-bottom:16px; }
.ws-title { font-size:17px;font-weight:700;color:var(--text); }
.ws-sub { font-size:12px;color:var(--text3);margin-top:2px; }
.ws-chip { background:var(--accent-bg);color:var(--accent);border:1px solid var(--accent-dim);border-radius:12px;font-size:11px;padding:3px 10px; }
.toolbar { display:flex;align-items:center;gap:8px;margin-bottom:12px; }
.lbl { font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.8px; }
.chip { padding:3px 9px;border-radius:10px;font-size:11px;border:1px solid var(--border);color:var(--text2);cursor:pointer;background:transparent;font-family:inherit; }
.chip.on { background:var(--accent-bg);border-color:var(--accent);color:var(--accent); }
.sp { flex:1; }
.zbtn { padding:4px 9px;border-radius:5px;font-size:11px;background:var(--bg3);border:1px solid var(--border);color:var(--text2);cursor:pointer;font-family:inherit; }

/* ══ AGENT AVATARS ══════════════════════════════ */
.aa { width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:9px;font-weight:800;flex-shrink:0;border:1.5px solid;cursor:default;position:relative; }
.aa.sm { width:16px;height:16px;font-size:7px;border-width:1px; }
.aa.lg { width:24px;height:24px;font-size:10px; }
.aa-claude{background:var(--ag-claude-bg);border-color:var(--ag-claude-bd);color:var(--ag-claude-tx);}
.aa-agy   {background:var(--ag-agy-bg);   border-color:var(--ag-agy-bd);   color:var(--ag-agy-tx);   }
.aa-codex {background:var(--ag-codex-bg); border-color:var(--ag-codex-bd); color:var(--ag-codex-tx); font-size:8px;}
.aa-grok  {background:var(--ag-grok-bg);  border-color:var(--ag-grok-bd);  color:var(--ag-grok-tx);  }
.aa-stack { display:flex;align-items:center;gap:3px; }
.aa[title]:hover::after { content:attr(title);position:absolute;bottom:26px;left:50%;transform:translateX(-50%);background:var(--bg3);color:var(--text);padding:3px 7px;border-radius:4px;font-size:10px;white-space:nowrap;border:1px solid var(--border);z-index:200;pointer-events:none; }

/* ══ SVG PENCIL NOTE ICON ═══════════════════════ */
.pencil-wrap {
  opacity:0; position:absolute; top:5px; right:6px;
  cursor:pointer; z-index:20; transition:opacity .15s;
  width:18px; height:18px; display:flex; align-items:center; justify-content:center;
}
.editable:hover .pencil-wrap { opacity:1; }
.pencil-wrap.note-info   { opacity:1; }
.pencil-wrap.note-action { opacity:1; }
.pencil-wrap.note-urgent { opacity:1; }
.pencil-wrap.note-done   { opacity:1; }
.pencil-wrap svg { width:16px;height:16px;transition:transform .15s; }
.pencil-wrap:hover svg { transform:scale(1.15); }
.pencil-wrap.note-none   svg { color:#9ca3af; }
.pencil-wrap.note-info   svg { color:#3b82f6; }
.pencil-wrap.note-action svg { color:#f59e0b; }
.pencil-wrap.note-urgent svg { color:#ef4444; }
.pencil-wrap.note-done   svg { color:#22c55e; }

.note-chip { display:inline-flex;align-items:center;gap:3px;border-radius:4px;font-size:10px;padding:2px 6px;cursor:pointer;margin-left:6px;border:1px solid; }
.note-chip.nc-info   { background:#eff6ff;border-color:#93c5fd;color:#1d4ed8; }
.note-chip.nc-action { background:#fefce8;border-color:#fcd34d;color:#92400e; }
.note-chip.nc-urgent { background:#fef2f2;border-color:#fca5a5;color:#dc2626; }
[data-theme="dark"] .note-chip.nc-info   { background:#0d1a3a;border-color:#4285f4;color:#60a5fa; }
[data-theme="dark"] .note-chip.nc-action { background:#2d2500;border-color:#f59e0b;color:#fbbf24; }
[data-theme="dark"] .note-chip.nc-urgent { background:#3a1a1a;border-color:#f85149;color:#f85149; }

.pencil-icon { display:block; }

/* ══ NOTE MODAL ══════════════════════════════════ */
.ov { display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:999; }
.ov.open { display:block; }
.note-modal { display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:18px;width:400px;z-index:1000;box-shadow:var(--shadow); }
.note-modal.open { display:block; }
.nm-title { font-size:12px;color:var(--text2);margin-bottom:10px; }
.note-modal textarea { width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:inherit;font-size:12px;padding:8px 10px;resize:none;outline:none;height:80px; }
.note-modal textarea:focus { border-color:var(--accent); }
.ac-row { display:flex;align-items:center;gap:7px;margin-top:10px; }
.ac-lbl { font-size:11px;color:var(--text3); }
.ac { padding:3px 9px;border-radius:10px;font-size:11px;border:1px solid var(--border);color:var(--text2);cursor:pointer;background:transparent;font-family:inherit; }
.ac:hover { border-color:var(--accent);color:var(--accent); }
.ac.on { border-color:#f0883e;color:#f0883e;background:#fff7ed; }
[data-theme="dark"] .ac.on { background:#2d1a00; }
.nm-footer { display:flex;justify-content:flex-end;gap:8px;margin-top:12px; }
.btn { padding:6px 14px;border-radius:5px;cursor:pointer;font-family:inherit;font-size:12px;border:1px solid; }
.btn-cancel { background:transparent;border-color:var(--border);color:var(--text2); }
.btn-save { background:var(--accent-bg);border-color:var(--accent);color:var(--accent); }

/* ══ GANTT ═══════════════════════════════════════ */
.gw { overflow-x:auto; }
.gantt { min-width:960px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;overflow:hidden; }

.gh { display:grid;grid-template-columns:260px repeat(10,1fr);border-bottom:1px solid var(--border);background:var(--bg3); }
.ghl { padding:7px 14px;font-size:11px;color:var(--text3);border-right:1px solid var(--border);text-transform:uppercase;letter-spacing:.5px; }
.gwk { padding:7px 4px;font-size:10px;color:var(--text3);text-align:center;border-right:1px solid var(--border2); }
.gwk.now { color:var(--accent);font-weight:700; }

/* Dream row */
.drow { display:grid;grid-template-columns:260px 1fr;border-bottom:1px solid var(--border);background:var(--bg2);transition:background .15s; }
.drow:hover { background:var(--bg3); }
.drow.exp { background:var(--bg3); }
.dlbl { padding:9px 14px;border-right:1px solid var(--border);display:flex;flex-direction:column;justify-content:center;gap:5px;position:relative;cursor:pointer;min-height:52px; }
.dtop { display:flex;align-items:center;gap:7px; }
.darr { font-size:11px;color:var(--text3);transition:transform .25s; }
.exp .darr { transform:rotate(90deg);color:var(--accent); }
.dname { font-size:12px;color:var(--text);font-weight:600; }
.dbot { display:flex;align-items:center;gap:8px; }
.dcost { font-size:10px; }
.dcost.ok { color:#16a34a; }
.dcost.over { color:#dc2626; }
.dcost.na { color:var(--text3); }
.dbars { position:relative;height:52px;display:flex;align-items:center; }

/* Stage bars — OVERVIEW */
.sb {
  position:absolute; height:28px; border-radius:5px;
  display:flex;align-items:center;padding:0 8px;
  font-size:10px;font-weight:600;gap:5px;
  cursor:pointer;transition:filter .15s,box-shadow .2s;border:1px solid;white-space:nowrap;
}
.sb:hover { filter:brightness(.92); box-shadow: 0 2px 8px rgba(0,0,0,.12); }
[data-theme="dark"] .sb:hover { filter:brightness(1.2); }
.sb.dim { opacity:.3;cursor:default; }
.sb.dim:hover { filter:none;box-shadow:none; }
.sb.sel { box-shadow:0 0 0 2px var(--accent), 0 2px 8px rgba(0,0,0,.12); }

.sb-dream {background:var(--s-dream-bg);border-color:var(--s-dream-bd);color:var(--s-dream-tx);}
.sb-plan  {background:var(--s-plan-bg); border-color:var(--s-plan-bd); color:var(--s-plan-tx); }
.sb-work  {background:var(--s-work-bg); border-color:var(--s-work-bd); color:var(--s-work-tx); }
.sb-ship  {background:var(--s-ship-bg); border-color:var(--s-ship-bd); color:var(--s-ship-tx); }
.sb-maint {background:var(--s-maint-bg);border-color:var(--s-maint-bd);color:var(--s-maint-tx);}
.sb-engage{background:var(--s-engage-bg);border-color:var(--s-engage-bd);color:var(--s-engage-tx);}

.sb.live { background-size:200% 100%;animation:sh 2s infinite; }
.sb-plan.live { background:linear-gradient(90deg,var(--s-plan-bg),#bfdbfe,var(--s-plan-bg));background-size:200% 100%; }
.sb-work.live { background:linear-gradient(90deg,var(--s-work-bg),#bbf7d0,var(--s-work-bg));background-size:200% 100%; }
[data-theme="dark"] .sb-plan.live { background:linear-gradient(90deg,#1e3a5a,#2e5a8a,#1e3a5a);background-size:200% 100%; }
[data-theme="dark"] .sb-work.live { background:linear-gradient(90deg,#1a4a2e,#2a6a3e,#1a4a2e);background-size:200% 100%; }
@keyframes sh { 0%{background-position:200% 0}100%{background-position:-200% 0} }

.bar-agents .aa { width:13px;height:13px;font-size:7px;border-width:1px; }
.today-ln { position:absolute;top:0;bottom:0;width:2px;background:var(--accent);opacity:.5;pointer-events:none;z-index:5; }
.today-ln::before { content:'today';position:absolute;top:2px;left:4px;font-size:9px;color:var(--accent);white-space:nowrap; }

/* ══ DRILL-DOWN SECTION ══════════════════════════ */
.drill {
  max-height:0; overflow:hidden;
  border-left:3px solid var(--accent);
  background:var(--bg);
  transition:max-height .35s cubic-bezier(.4,0,.2,1);
  border-bottom:0px solid var(--border);
}
.drill.open {
  max-height:600px;
  border-bottom:1px solid var(--border);
}

.drill-header {
  display:flex;align-items:center;gap:10px;
  padding:8px 14px;border-bottom:1px solid var(--border2);
  background:var(--bg2);
}
.stage-pill { padding:3px 10px;border-radius:10px;font-size:11px;font-weight:700;border:1px solid; }
.drill-ttl { font-size:12px;color:var(--text2); }
.drill-close { margin-left:auto;color:var(--text3);cursor:pointer;font-size:14px;padding:0 4px; }
.drill-close:hover { color:var(--text); }

/* Zoomed timeline header */
.zoom-grid { display:grid;border-bottom:1px solid var(--border2);background:var(--bg3); }
.zoom-lbl { padding:6px 14px;font-size:11px;color:var(--text3);border-right:1px solid var(--border2);font-style:italic; }
.zoom-col { padding:6px 4px;font-size:10px;color:var(--accent);text-align:center;border-right:1px solid var(--border2);font-weight:700; }

/* Task rows in zoomed view */
.trow { display:grid;border-bottom:1px solid var(--border2);background:var(--bg);min-height:48px;transition:background .15s; }
.trow:last-child { border-bottom:none; }
.trow:hover { background:var(--bg3); }

.tlbl {
  padding:7px 14px;border-right:1px solid var(--border2);
  display:flex;align-items:center;gap:8px;position:relative;
  overflow:hidden;
}
.tname { font-size:12px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;text-align:right; }

/* Zoomed task bar */
.tbars { position:relative;display:flex;align-items:center; }
.tb {
  position:absolute; border-radius:5px;
  display:flex;align-items:center;padding:0 8px;
  font-size:10px;font-weight:600;border:1px solid;
  transition:filter .15s,box-shadow .15s;
  overflow:hidden; white-space:nowrap; height:30px;
}
.tb:hover { filter:brightness(.95);box-shadow:0 2px 8px rgba(0,0,0,.1); }
[data-theme="dark"] .tb:hover { filter:brightness(1.15); }
.tb-name { flex:1;overflow:hidden;text-overflow:ellipsis; }
.tb-right { display:flex;align-items:center;gap:5px;margin-left:auto;flex-shrink:0;padding-left:6px; }
.tb-cost { font-size:10px;opacity:.8; }

/* Task status variants */
.tb-done   { background:var(--bg3);border-color:var(--border);color:var(--text3); }
.tb-active { background:var(--s-work-bg);border-color:var(--s-work-bd);color:var(--s-work-tx);animation:sh 2s infinite; }
.tb-active { background:linear-gradient(90deg,var(--s-work-bg),#bbf7d0,var(--s-work-bg));background-size:200% 100%; }
[data-theme="dark"] .tb-active { background:linear-gradient(90deg,#1a4a2e,#2a6a3e,#1a4a2e);background-size:200% 100%; }
.tb-queued { background:var(--bg3);border-color:var(--border);color:var(--text3);opacity:.55; }
.tb-blocked{ background:#fef2f2;border-color:#fca5a5;color:#dc2626; }

/* Status dot */
.st-dot { width:7px;height:7px;border-radius:50%;flex-shrink:0; }
.st-dot.done    { background:#16a34a; }
.st-dot.active  { background:var(--s-work-tx);animation:pulse 1.5s infinite; }
.st-dot.queued  { background:var(--text3); }
.st-dot.blocked { background:#dc2626; }
@keyframes pulse { 0%,100%{opacity:1}50%{opacity:.3} }

/* ══ LEGEND + SUMMARY ════════════════════════════ */
.legend { display:flex;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap; }
.li { display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text3); }
.ld { width:10px;height:10px;border-radius:3px;border:1px solid; }
.lsep { color:var(--border); }
.al-row { display:flex;align-items:center;gap:14px;margin-top:8px; }
.ali { display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3); }

/* Note icon state legend */
.ni-legend { display:flex;align-items:center;gap:12px;margin-top:8px; }
.nil { display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text3); }

.srow { display:flex;gap:10px;margin-top:18px; }
.sc { flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:11px 13px;position:relative; }
.sc .sl { font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px; }
.sc .sv { font-size:20px;font-weight:700;color:var(--text);margin:4px 0 2px; }
.sc .ss { font-size:11px;color:var(--text3); }
.sc.teal .sv { color:var(--accent); }
.sc.blue .sv { color:#1d4ed8; }[data-theme="dark"] .sc.blue .sv { color:#60a5fa; }
.sc.org  .sv { color:#c2410c; }[data-theme="dark"] .sc.org  .sv { color:#fb923c; }
.sc.purp .sv { color:#6d28d9; }[data-theme="dark"] .sc.purp .sv { color:#a78bfa; }
.wow { display:inline-block;margin-top:4px;background:var(--s-work-bg);color:var(--s-work-tx);border:1px solid var(--s-work-bd);border-radius:10px;font-size:10px;padding:2px 8px; }

/* Goals Panel Styles */
.goals-panel {
  max-height: 0;
  overflow: hidden;
  border-left: 3px solid var(--accent);
  background: var(--bg);
  transition: max-height .35s cubic-bezier(.4,0,.2,1);
  border-bottom: 0px solid var(--border);
  margin-top: 15px;
  border-radius: 4px;
}
.goals-panel.open {
  max-height: 600px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  background: var(--bg2);
}
.goals-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border2);
  background: var(--bg3);
}
.goals-ttl {
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
}
.goals-close {
  margin-left: auto;
  color: var(--text3);
  cursor: pointer;
  font-size: 12px;
}
.goals-close:hover {
  color: var(--text);
}
.goals-body {
  padding: 8px 0;
}
.goal-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border2);
  gap: 12px;
}
.goal-item:last-child {
  border-bottom: none;
}
.goal-content {
  flex: 1;
}
.goal-outcome {
  font-weight: bold;
  color: var(--text);
  font-size: 13px;
}
.goal-criterion {
  font-size: 11px;
  color: var(--text2);
  margin-top: 2px;
}
.goal-deadline {
  font-size: 11px;
  color: var(--text3);
  margin-left: 10px;
  white-space: nowrap;
}
.goal-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  background: var(--bg3);
  color: var(--text2);
  border: 1px solid var(--border);
}
.goal-badge.active {
  background: var(--accent-bg);
  color: var(--accent);
  border-color: var(--accent-dim);
}
.empty-state {
  padding: 18px 14px;
  color: var(--text3);
  font-size: 12px;
  text-align: center;
}
.empty-state code {
  background: var(--bg3);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: inherit;
}
/* ══ SECTION DIVIDERS & COLLAPSIBLE CONTROLS ══════════════ */
.section-divider { margin: 16px 0 10px; }
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: var(--bg3); border: 1px solid var(--border);
  border-radius: 6px; cursor: pointer; user-select: none; transition: background .15s;
}
.section-header:hover { background: var(--border2); }
.section-title { display: flex; align-items: center; gap: 10px; font-size: 12px; font-weight: 700; color: var(--text); }
.section-chevron { font-size: 10px; color: var(--text3); transition: transform .2s; }
.section-header.collapsed .section-chevron { transform: rotate(-90deg); }
.section-badge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; text-transform: uppercase; }
.active-badge { background: rgba(13,158,135,0.15); color: #0d9e87; border: 1px solid rgba(13,158,135,0.3); }
.planned-badge { background: rgba(59,130,246,0.12); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
.completed-badge { background: rgba(100,116,139,0.15); color: var(--text3); border: 1px solid var(--border); }
.section-count { font-size: 11px; color: var(--text3); font-weight: normal; }
.section-hint { font-size: 11px; color: var(--text3); }
.section-content { transition: max-height .3s ease; }
.section-content.collapsed { display: none; }
.goal-pill { background: rgba(99,102,241,0.12); color: #6366f1; border: 1px solid rgba(99,102,241,0.3); font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; display: inline-flex; align-items: center; gap: 3px; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pivot-controls { display: flex; align-items: center; background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 2px; }
.pivot-btn { padding: 4px 12px; border-radius: 4px; font-size: 11px; font-family: inherit; border: none; background: transparent; color: var(--text2); cursor: pointer; transition: all .15s; }
.pivot-btn.active { background: var(--accent); color: #fff; font-weight: 700; }
"""

def generate_gantt_html(data: dict, port: int) -> str:
    data_json = json.dumps(data)

    script_content = """
const PORT = __PORT__;
const NOTE_STATE_CLASS = { none:'note-none', info:'note-info', action:'note-action', urgent:'note-urgent', done:'note-done' };
const STAGE_CLASS = {
  goal:'goal',
  open:'open',
  visualize:'visualize',
  execute:'execute',
  release:'release',
  notify:'notify',
  sustain:'sustain',
};
const STAGE_ICON = {
  goal:'◆ Goal',
  open:'○ Open',
  visualize:'◌ Visualize',
  execute:'⚙ Execute',
  release:'▲ Release',
  notify:'✉ Notify',
  sustain:'↺ Sustain',
};
const STAGE_STYLE = {
  goal:'background:#dbeafe;border-color:#93c5fd;color:#1d4ed8',
  open:'background:#ede9fe;border-color:#c4b5fd;color:#6d28d9',
  visualize:'background:#e6f7f4;border-color:#c0ede6;color:#0d9e87',
  execute:'background:#dcfce7;border-color:#86efac;color:#15803d',
  release:'background:#fef3c7;border-color:#fde68a;color:#d97706',
  notify:'background:#ffe4e6;border-color:#fda4af;color:#be123c',
  sustain:'background:#f3f4f6;border-color:#d1d5db;color:#6b7280',
};
const releases = Array.isArray(window.VIZOR_DATA && (window.VIZOR_DATA.releases || window.VIZOR_DATA.dreams)) ? (window.VIZOR_DATA.releases || window.VIZOR_DATA.dreams) : [];
const dreams = releases; // Backwards compatibility alias
const goals = Array.isArray(window.VIZOR_DATA && window.VIZOR_DATA.goals) ? window.VIZOR_DATA.goals : [];
const specVerifications = Array.isArray(window.VIZOR_DATA && window.VIZOR_DATA.spec_verifications) ? window.VIZOR_DATA.spec_verifications : [];
const currentWorkspaceProductId = window.VIZOR_DATA && window.VIZOR_DATA.product_id ? String(window.VIZOR_DATA.product_id) : null;
const VERDICT_BADGE = {
  fulfilled: 'background:#dcfce7;border-color:#86efac;color:#15803d',
  partial: 'background:#fef3c7;border-color:#fde68a;color:#d97706',
  diverged: 'background:#ffe4e6;border-color:#fda4af;color:#be123c',
};
const notes = (window.VIZOR_DATA && window.VIZOR_DATA.notes && typeof window.VIZOR_DATA.notes === 'object') ? window.VIZOR_DATA.notes : {};
let openDrills = {};
let currentNoteTarget = null;
let currentPivot = safeStorageGet('vizor-gantt-pivot', 'release');
let sectionStates = {
  active: safeStorageGet('vizor-gantt-sec-active', 'open') === 'open',
  planned: safeStorageGet('vizor-gantt-sec-planned', 'open') === 'open',
  completed: safeStorageGet('vizor-gantt-sec-completed', 'collapsed') === 'open',
};

function escapeHtml(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function safeStorageGet(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value;
  } catch (err) {
    return fallback;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (err) {}
}

function applyGovernanceRelayEvent(event) {
  const eventType = event && (event.event_type || event.type);
  const eventProductId = event && (event.product_id || event.payload?.product_id);
  if (!event || !['goal_realigned', 'governs_stage_advanced'].includes(eventType)) return;
  if (currentWorkspaceProductId && String(eventProductId || '') !== currentWorkspaceProductId) return;
  // Relay events are advisory. Re-rendering the already scoped snapshot keeps
  // the HUD consistent without allowing a foreign workspace to patch it.
  if (eventType === 'goal_realigned') renderTimeline();
}

if (typeof EventSource !== 'undefined') {
  try {
    const relay = new EventSource('/events');
    relay.onmessage = (message) => {
      try { applyGovernanceRelayEvent(JSON.parse(message.data)); } catch (err) {}
    };
  } catch (err) {}
}

function setTheme(t) {
  const resolved = t === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : t;
  document.documentElement.setAttribute('data-theme', resolved);
  document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('btn-' + t)?.classList.add('active');
  safeStorageSet('vizor-theme', t);
}

function toggleSection(secKey) {
  sectionStates[secKey] = !sectionStates[secKey];
  safeStorageSet('vizor-gantt-sec-' + secKey, sectionStates[secKey] ? 'open' : 'collapsed');
  const header = document.getElementById('sec-hdr-' + secKey);
  const content = document.getElementById('sec-cnt-' + secKey);
  if (header && content) {
    if (sectionStates[secKey]) {
      header.classList.remove('collapsed');
      content.classList.remove('collapsed');
      const hint = header.querySelector('.section-hint');
      if (hint) hint.textContent = 'Click to collapse';
    } else {
      header.classList.add('collapsed');
      content.classList.add('collapsed');
      const hint = header.querySelector('.section-hint');
      if (hint) hint.textContent = 'Click to expand';
    }
  }
}

function setPivot(pivot) {
  currentPivot = pivot;
  safeStorageSet('vizor-gantt-pivot', pivot);
  document.getElementById('pivot-release-btn')?.classList.toggle('active', pivot === 'release');
  document.getElementById('pivot-goal-btn')?.classList.toggle('active', pivot === 'goal');
  renderTimeline();
}

function classForStage(stageKey) {
  const key = String(stageKey || '').trim().toLowerCase();
  return STAGE_CLASS[key] || 'open';
}

function iconForStage(stageKey) {
  const key = String(stageKey || '').trim().toLowerCase();
  return STAGE_ICON[key] || (stageKey ? escapeHtml(stageKey) : '○ Open');
}

function noteStateClass(state) {
  return NOTE_STATE_CLASS[state || 'none'] || NOTE_STATE_CLASS.none;
}

function noteData(targetId) {
  return notes[targetId] || (window.VIZOR_DATA && window.VIZOR_DATA.notes && window.VIZOR_DATA.notes[targetId]) || null;
}

function setNoteButtons(tags) {
  const wanted = new Set((tags || []).map(t => String(t).trim().toLowerCase()));
  document.querySelectorAll('.ac').forEach(btn => {
    const tag = String(btn.getAttribute('data-tag') || '').trim().toLowerCase();
    btn.classList.toggle('on', wanted.has(tag));
  });
}

function noteTagsFromButtons() {
  return Array.from(document.querySelectorAll('.ac.on')).map(btn => btn.getAttribute('data-tag') || btn.textContent.trim()).filter(Boolean);
}

function updateNoteIcon(targetId, state) {
  const el = document.querySelector('[data-note-target="' + CSS.escape(targetId) + '"]');
  if (!el) return;
  Object.values(NOTE_STATE_CLASS).forEach(cls => el.classList.remove(cls));
  el.classList.add(noteStateClass(state));
}

function openNote(targetId, targetLabel) {
  currentNoteTarget = targetId;
  const existing = noteData(targetId);
  document.getElementById('nt').innerHTML = 'Note on <strong>' + escapeHtml(targetLabel || targetId) + '</strong>';
  document.getElementById('ntxt').value = existing && typeof existing.text === 'string' ? existing.text : '';
  setNoteButtons(existing && Array.isArray(existing.tags) ? existing.tags : []);
  document.getElementById('nm').classList.add('open');
  document.getElementById('ov').classList.add('open');
  document.getElementById('ntxt').focus();
}

function openNoteFromEl(el) {
  openNote(el.getAttribute('data-note-target'), el.getAttribute('data-note-label'));
}

function closeNote() {
  document.getElementById('nm').classList.remove('open');
  document.getElementById('ov').classList.remove('open');
  currentNoteTarget = null;
}

async function saveNote() {
  if (!currentNoteTarget) return;
  const text = document.getElementById('ntxt').value || '';
  const tags = noteTagsFromButtons();
  const existing = noteData(currentNoteTarget);
  const derivedState = existing && existing.state ? existing.state : ((text || tags.length) ? 'info' : null);
  const response = await fetch('/note', {
    method: 'POST',
    headers: window.vizorAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ id: currentNoteTarget, text, tags, state: derivedState }),
  });
  if (!response.ok) throw new Error('note save failed');
  notes[currentNoteTarget] = { text, tags, state: derivedState };
  if (window.VIZOR_DATA && window.VIZOR_DATA.notes) {
    window.VIZOR_DATA.notes[currentNoteTarget] = notes[currentNoteTarget];
  }
  updateNoteIcon(currentNoteTarget, derivedState);
  closeNote();
}

function renderTask(task, releaseId, stageKey, index, total) {
  const status = String(task.status || 'queued').trim().toLowerCase();
  const tbClass = status === 'done' ? 'tb-done' : status === 'active' ? 'tb-active' : status === 'blocked' ? 'tb-blocked' : 'tb-queued';
  const dotClass = status === 'done' ? 'done' : status === 'active' ? 'active' : status === 'blocked' ? 'blocked' : 'queued';
  const note = task.note || null;
  const noteClass = noteStateClass(note && note.state);
  const leftPct = total > 0 ? ((index / total) * 100).toFixed(1) : '0.0';
  const widthPct = total > 0 ? ((0.85 / total) * 100).toFixed(1) : '100.0';
  const agent = String(task.agent || '').trim().toLowerCase();
  const agentClass = agent === 'agy' ? 'aa-agy' : agent === 'codex' ? 'aa-codex' : agent === 'grok' ? 'aa-grok' : 'aa-claude';
  const agentLabel = agent === 'codex' ? 'Co' : agent === 'grok' ? 'G' : agent === 'claude' ? 'C' : 'A';
  return `
    <div class="trow editable" style="grid-template-columns:260px repeat(${total || 1}, 1fr)" title="ID: ${escapeHtml(task.id)}">
      <div class="tlbl">
        <div class="aa ${agentClass}" title="${escapeHtml(task.agent || 'agent')}">${agentLabel}</div>
        <div class="tname">${escapeHtml(task.name || 'Task')}</div>
        <div class="pencil-wrap ${noteClass}" data-note-target="${escapeHtml(task.id)}" data-note-label="${escapeHtml(task.name || task.id)}" onclick="openNoteFromEl(this);event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div>
      </div>
      <div class="tbars" style="grid-column:2/span ${total || 1}">
        <div class="tb ${tbClass}" style="left:${leftPct}%;width:${widthPct}%">
          <div class="st-dot ${dotClass}"></div>
          <span class="tb-name">${escapeHtml(task.name || 'Task')}</span>
          <div class="tb-right">
            <div class="aa sm ${agentClass}" title="${escapeHtml(task.agent || 'agent')}">${agentLabel}</div>
            <span class="tb-cost">${escapeHtml(status)}${note && note.text ? ' · note' : ''}</span>
          </div>
        </div>
      </div>
    </div>`;
}

function renderDrill(releaseId, stageKey) {
  const rel = releases.find(d => d.id === releaseId);
  const stage = rel && Array.isArray(rel.stages) ? rel.stages.find(s => s.key === stageKey) : null;
  const dr = document.getElementById('drill-' + releaseId);
  if (!dr) return;
  if (!stage) {
    dr.innerHTML = `<div style="padding:12px 14px;font-size:11px;color:var(--text3)">No tasks defined. <span style="color:var(--accent);cursor:pointer">📝 Add note</span></div>`;
    return;
  }

  const tasks = Array.isArray(stage.tasks) ? stage.tasks : [];
  const total = Math.max(tasks.length, 1);
  const gridCols = `260px repeat(${total}, 1fr)`;
  const headerCols = tasks.map((task, idx) => `<div class="zoom-col">${escapeHtml(task.name || ('Task ' + (idx + 1)))}</div>`).join('');
  const taskRows = tasks.map((task, idx) => renderTask(task, releaseId, stageKey, idx, total)).join('');
  const pillKey = classForStage(stageKey);
  const lastLabel = tasks.length > 1 ? tasks[tasks.length - 1].name : '';
  dr.innerHTML = `
    <div class="drill-header">
      <div class="stage-pill" style="${STAGE_STYLE[pillKey] || STAGE_STYLE.plan}">${escapeHtml(iconForStage(stageKey))} stage</div>
      <div class="drill-ttl">${escapeHtml(releaseId.toUpperCase())} — ${tasks.length} task${tasks.length !== 1 ? 's' : ''} · zoomed to stage window</div>
      <div class="drill-close" onclick="closeDrill('${escapeHtml(releaseId)}')">✕ collapse</div>
    </div>
    <div class="zoom-grid" style="grid-template-columns:${gridCols}">
      <div class="zoom-lbl">↳ zoomed: ${escapeHtml(stage.key || stageKey)}${lastLabel ? ' → ' + escapeHtml(lastLabel) : ''}</div>
      ${headerCols}
    </div>
    ${taskRows}`;
}

function zoomStage(releaseId, stageKey, barEl) {
  const dr = document.getElementById('drill-' + releaseId);
  const drow = document.getElementById('drow-' + releaseId);
  if (!dr || !drow) return;
  if (openDrills[releaseId] === stageKey) {
    closeDrill(releaseId);
    return;
  }
  if (openDrills[releaseId]) {
    const prevBar = document.getElementById('sb-' + releaseId + '-' + openDrills[releaseId]);
    if (prevBar) prevBar.classList.remove('sel');
  }
  renderDrill(releaseId, stageKey);
  dr.classList.add('open');
  drow.classList.add('exp');
  if (barEl) barEl.classList.add('sel');
  openDrills[releaseId] = stageKey;
}

function closeDrill(releaseId) {
  const dr = document.getElementById('drill-' + releaseId);
  const drow = document.getElementById('drow-' + releaseId);
  dr?.classList.remove('open');
  drow?.classList.remove('exp');
  if (openDrills[releaseId]) {
    const prevBar = document.getElementById('sb-' + releaseId + '-' + openDrills[releaseId]);
    if (prevBar) prevBar.classList.remove('sel');
  }
  delete openDrills[releaseId];
}

function toggleDrill(releaseId) {
  if (openDrills[releaseId]) {
    closeDrill(releaseId);
    return;
  }
  const rel = releases.find(d => d.id === releaseId);
  if (!rel || !Array.isArray(rel.stages) || !rel.stages.length) return;
  const activeStage = rel.stages.find(s => String(s.status || '').toLowerCase() === 'active') || rel.stages[0];
  const barEl = document.getElementById('sb-' + releaseId + '-' + activeStage.key);
  zoomStage(releaseId, activeStage.key, barEl);
}

function renderRelease(release) {
  const stages = Array.isArray(release.stages) ? release.stages : [];
  const note = release.note || noteData(release.id);
  const noteClass = noteStateClass(note && note.state);
  const taskCount = stages.reduce((sum, stage) => sum + (Array.isArray(stage.tasks) ? stage.tasks.length : 0), 0);
  const status = String(release.status || 'planned').trim().toLowerCase();
  const statusClass = (status === 'done' || status === 'shipped') ? 'ok' : (status === 'blocked' ? 'over' : 'na');
  const stageAgents = stages[0] && Array.isArray(stages[0].agents) ? stages[0].agents : [];
  const agentsHtml = stageAgents.slice(0, 4).map(agent => {
    const a = String(agent || '').trim().toLowerCase();
    const agentClass = a === 'agy' ? 'aa-agy' : a === 'codex' ? 'aa-codex' : a === 'grok' ? 'aa-grok' : 'aa-claude';
    const agentLabel = a === 'codex' ? 'Co' : a === 'grok' ? 'G' : a === 'claude' ? 'C' : 'A';
    return `<div class="aa ${agentClass}" title="${escapeHtml(agent)}">${agentLabel}</div>`;
  }).join('');
  const barHtml = stages.map(stage => {
    const cls = classForStage(stage.key);
    const live = String(stage.status || '').toLowerCase() === 'active' ? 'live' : 'dim';
    const left = Number(stage.start_frac || 0) * 100;
    const width = Number(stage.width_frac || 0) * 100;
    const agentHtml = Array.isArray(stage.agents) && stage.agents.length ? `<div class="bar-agents">${stage.agents.map(agent => {
      const a = String(agent || '').trim().toLowerCase();
      const agentClass = a === 'agy' ? 'aa-agy' : a === 'codex' ? 'aa-codex' : a === 'grok' ? 'aa-grok' : 'aa-claude';
      const agentLabel = a === 'codex' ? 'Co' : a === 'grok' ? 'G' : a === 'claude' ? 'C' : 'A';
      return `<div class="aa ${agentClass}">${agentLabel}</div>`;
    }).join('')}</div>` : '';
    return `<div class="sb sb-${cls} ${live}" id="sb-${release.id}-${stage.key}" style="left:${left}%;width:${width}%" onclick="zoomStage('${escapeHtml(release.id)}','${escapeHtml(stage.key)}',this)">${escapeHtml(iconForStage(stage.key))}${agentHtml}</div>`;
  }).join('');

  const goalBadge = release.goal_id ? `<span class="goal-pill" title="Goal: ${escapeHtml(release.goal_outcome || release.goal_id)}">🎯 ${escapeHtml(release.goal_id)}</span>` : '';
  const targetDateHtml = release.target_date ? `<span style="font-size:10px;color:var(--text3);margin-left:4px;">📅 ${escapeHtml(release.target_date)}</span>` : '';

  return `
      <div class="drow" id="drow-${release.id}">
        <div class="dlbl editable" onclick="toggleDrill('${escapeHtml(release.id)}')">
          <div class="dtop"><span class="darr">▶</span><div class="dname">${escapeHtml(release.id)} · ${escapeHtml(release.name || release.id)}</div>
            ${goalBadge}
            <span class="note-chip nc-${noteClass.replace('note-', '') === 'none' ? 'info' : noteClass.replace('note-', '')}" style="display:${noteClass === 'note-none' ? 'none' : 'inline-flex'}" onclick="openNote('${escapeHtml(release.id)}','${escapeHtml(release.name || release.id)}');event.stopPropagation()">✎ note</span>
          </div>
          <div class="dbot"><div class="aa-stack">${agentsHtml}</div><span class="dcost ${statusClass}">${escapeHtml(release.status || 'planned')}${taskCount ? ' · ' + taskCount + ' tasks' : ''}</span>${targetDateHtml}</div>
          <div class="pencil-wrap ${noteClass}" data-note-target="${escapeHtml(release.id)}" data-note-label="${escapeHtml(release.name || release.id)}" onclick="openNoteFromEl(this);event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div>
        </div>
        <div class="dbars">
          <div class="today-ln" style="left:19%"></div>
          ${barHtml}
        </div>
      </div>
      <div class="drill" id="drill-${release.id}"></div>`;
}

// Backwards compatibility alias
const renderDream = renderRelease;

function renderGoal(goal) {
  const deadlineHtml = goal.deadline ? `<span class="goal-deadline">📅 ${escapeHtml(goal.deadline)}</span>` : '';
  const status = String(goal.status || 'active').trim().toLowerCase();
  const badgeClass = status === 'active' ? 'active' : '';
  return `
    <div class="goal-item">
      <div class="goal-content">
        <div class="goal-outcome">${escapeHtml(goal.outcome)}</div>
        <div class="goal-criterion">${escapeHtml(goal.criterion)}</div>
      </div>
      ${deadlineHtml}
      <div class="goal-badge ${badgeClass}">${escapeHtml(status)}</div>
    </div>`;
}

function toggleGoalsPanel() {
  const panel = document.getElementById('goals-panel');
  if (!panel) return;
  panel.classList.toggle('open');
}

function renderGoals() {
  const goalCount = document.getElementById('goal-count');
  const goalSub = document.getElementById('goal-sub');
  const goalsBody = document.getElementById('goals-body');

  const activeCount = goals.filter(g => String(g.status || '').toLowerCase() === 'active').length;
  const totalCount = goals.length;

  if (goalCount) goalCount.textContent = String(activeCount);
  if (goalSub) goalSub.textContent = activeCount + ' active / of ' + totalCount + ' goals';

  if (!goalsBody) return;

  if (!goals.length) {
    goalsBody.innerHTML = `
      <div class="empty-state">
        <p class="empty-state-desc" style="padding: 12px 14px; font-size: 11px; color: var(--text3); margin: 0;">
          No active goals yet. Add a goal using: <code>synlynk goal create --outcome "..." --criterion "..."</code>
        </p>
      </div>`;
    return;
  }

  goalsBody.innerHTML = goals.map(renderGoal).join('');
}

function renderVerifiedEntry(entry) {
  const verdict = String(entry.verdict || 'unknown').trim().toLowerCase();
  const badgeStyle = VERDICT_BADGE[verdict] || 'background:#f3f4f6;border-color:#d1d5db;color:#6b7280';
  return `
    <div class="goal-item">
      <div class="goal-content">
        <div class="goal-outcome">PR #${escapeHtml(entry.pr_number ?? '—')} · ${escapeHtml(entry.spec_path || 'Unknown spec')}</div>
        <div class="goal-criterion">${escapeHtml(entry.rationale || 'No rationale provided')}</div>
      </div>
      <div class="goal-badge" style="${badgeStyle}">${escapeHtml(verdict)}</div>
    </div>`;
}

function toggleVerifiedPanel() {
  const panel = document.getElementById('spec-verifications-panel');
  if (!panel) return;
  panel.classList.toggle('open');
}

function renderVerified() {
  const count = document.getElementById('spec-verified-count');
  const sub = document.getElementById('spec-verified-sub');
  const body = document.getElementById('spec-verifications-body');
  if (count) count.textContent = String(specVerifications.length);
  if (sub) sub.textContent = specVerifications.length + ' verified PR' + (specVerifications.length === 1 ? '' : 's');
  if (!body) return;
  body.innerHTML = specVerifications.length
    ? specVerifications.map(renderVerifiedEntry).join('')
    : '<div class="empty-state"><p class="empty-state-desc" style="padding: 12px 14px; font-size: 11px; color: var(--text3); margin: 0;">No verified PRs yet.</p></div>';
}

function renderByRelease() {
  const body = document.getElementById('gantt-body');
  if (!body) return;
  if (!releases.length) {
    body.innerHTML = "<p class='empty-state'>No Releases found in state db</p>";
    return;
  }
  const activeList = [];
  const plannedList = [];
  const completedList = [];

  releases.forEach(r => {
    const s = String(r.status || '').trim().toLowerCase();
    if (s === 'shipped' || s === 'done' || s === 'completed' || s === 'resolved') {
      completedList.push(r);
    } else if (s === 'active' || s === 'in_progress') {
      activeList.push(r);
    } else {
      plannedList.push(r);
    }
  });

  const activeOpen = sectionStates.active;
  const plannedOpen = sectionStates.planned;
  const completedOpen = sectionStates.completed;

  let html = '';

  if (activeList.length > 0) {
    html += `
      <div class="section-divider">
        <div class="section-header ${activeOpen ? '' : 'collapsed'}" id="sec-hdr-active" onclick="toggleSection('active')">
          <div class="section-title">
            <span class="section-chevron">▼</span>
            <span class="section-badge active-badge">● Active</span>
            <span>In-Progress Releases & Milestones</span>
            <span class="section-count">(${activeList.length})</span>
          </div>
          <div class="section-hint">${activeOpen ? 'Click to collapse' : 'Click to expand'}</div>
        </div>
        <div class="section-content ${activeOpen ? '' : 'collapsed'}" id="sec-cnt-active">
          ${activeList.map(renderRelease).join('')}
        </div>
      </div>`;
  }

  if (plannedList.length > 0) {
    html += `
      <div class="section-divider">
        <div class="section-header ${plannedOpen ? '' : 'collapsed'}" id="sec-hdr-planned" onclick="toggleSection('planned')">
          <div class="section-title">
            <span class="section-chevron">▼</span>
            <span class="section-badge planned-badge">○ Planned</span>
            <span>Upcoming Releases & Arcs</span>
            <span class="section-count">(${plannedList.length})</span>
          </div>
          <div class="section-hint">${plannedOpen ? 'Click to collapse' : 'Click to expand'}</div>
        </div>
        <div class="section-content ${plannedOpen ? '' : 'collapsed'}" id="sec-cnt-planned">
          ${plannedList.map(renderRelease).join('')}
        </div>
      </div>`;
  }

  if (completedList.length > 0) {
    html += `
      <div class="section-divider">
        <div class="section-header ${completedOpen ? '' : 'collapsed'}" id="sec-hdr-completed" onclick="toggleSection('completed')">
          <div class="section-title">
            <span class="section-chevron">▼</span>
            <span class="section-badge completed-badge">✓ Shipped</span>
            <span>Completed Historical Releases</span>
            <span class="section-count">(${completedList.length})</span>
          </div>
          <div class="section-hint">${completedOpen ? 'Click to collapse' : 'Click to expand'}</div>
        </div>
        <div class="section-content ${completedOpen ? '' : 'collapsed'}" id="sec-cnt-completed">
          ${completedList.map(renderRelease).join('')}
        </div>
      </div>`;
  }

  body.innerHTML = html || "<p class='empty-state'>No Releases found in state db</p>";
}

function renderByGoal() {
  const body = document.getElementById('gantt-body');
  if (!body) return;
  if (!goals.length) {
    body.innerHTML = "<p class='empty-state'>No active goals defined. Create one via <code>synlynk goal create</code></p>";
    return;
  }
  let html = '';
  goals.forEach(goal => {
    const linkedReleases = releases.filter(r => r.goal_id === goal.id || (r.goal_outcome && r.goal_outcome === goal.outcome));
    const deadlineHtml = goal.deadline ? `<span style="font-size:11px;color:var(--text3);margin-left:8px;">📅 ${escapeHtml(goal.deadline)}</span>` : '';
    html += `
      <div class="section-divider">
        <div class="section-header">
          <div class="section-title">
            <span class="section-badge active-badge">🎯 Goal</span>
            <span>${escapeHtml(goal.outcome)}</span>
            <span class="section-count">(${linkedReleases.length} linked release${linkedReleases.length !== 1 ? 's' : ''})</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            ${deadlineHtml}
            <span class="goal-badge active">${escapeHtml(goal.status || 'active')}</span>
          </div>
        </div>
        <div class="section-content">
          ${linkedReleases.length ? linkedReleases.map(renderRelease).join('') : `<div style="padding:10px 14px;font-size:11px;color:var(--text3);font-style:italic;">No releases linked to this goal yet.</div>`}
        </div>
      </div>`;
  });
  const unmappedReleases = releases.filter(r => !r.goal_id && !r.goal_outcome);
  if (unmappedReleases.length) {
    html += `
      <div class="section-divider unmapped-goal-lane">
        <div class="section-header">
          <div class="section-title">
            <span class="section-badge">⚪ Unmapped</span>
            <span>Stories awaiting goal association</span>
            <span class="section-count">(${unmappedReleases.length})</span>
          </div>
        </div>
        <div class="section-content">${unmappedReleases.map(renderRelease).join('')}</div>
      </div>`;
  }
  body.innerHTML = html;
}

function renderTimeline() {
  const wsSub = document.getElementById('ws-sub');
  const releaseCount = document.getElementById('dream-count');
  const releaseSub = document.getElementById('dream-sub');
  const statusWorkspaces = document.getElementById('status-workspaces');

  if (!releases.length) {
    const body = document.getElementById('gantt-body');
    if (body) body.innerHTML = "<p class='empty-state'>No Releases found in state db</p>";
    if (wsSub) wsSub.textContent = '0 Releases · no stage data';
    if (releaseCount) releaseCount.textContent = '0';
    if (releaseSub) releaseSub.textContent = '0 stages';
    if (statusWorkspaces) statusWorkspaces.textContent = '0 releases';
    renderGoals();
    renderVerified();
    return;
  }

  const releaseCountValue = releases.length;
  const stageCountValue = releases.reduce((sum, rel) => sum + (Array.isArray(rel.stages) ? rel.stages.length : 0), 0);
  const activeReleases = releases.filter(rel => {
    const s = String(rel.status || '').toLowerCase();
    return s === 'active' || s === 'in_progress';
  }).length;

  if (currentPivot === 'goal') {
    renderByGoal();
  } else {
    renderByRelease();
  }

  if (wsSub) wsSub.textContent = releaseCountValue + ' Releases · click any stage bar to zoom in';
  if (releaseCount) releaseCount.textContent = String(releaseCountValue);
  if (releaseSub) releaseSub.textContent = stageCountValue + ' stages · ' + activeReleases + ' active';
  if (statusWorkspaces) statusWorkspaces.textContent = releaseCountValue + ' releases';
  renderGoals();
  renderVerified();

  const firstRel = releases[0];
  const firstStage = firstRel && Array.isArray(firstRel.stages) ? (firstRel.stages.find(s => String(s.status || '').toLowerCase() === 'active') || firstRel.stages[0]) : null;
  if (firstRel && firstStage) {
    const barEl = document.getElementById('sb-' + firstRel.id + '-' + firstStage.key);
    if (barEl) zoomStage(firstRel.id, firstStage.key, barEl);
  }
}

// Backwards compatibility
function renderDreams() {
  renderTimeline();
}

setTheme(safeStorageGet('vizor-theme', 'light'));
renderTimeline();
""".replace("__PORT__", str(port))

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Gantt Timeline</title>
<script>window.VIZOR_DATA = {data_json};</script>
<style>
{_GANTT_STYLE}
</style>
</head>
<body>

<div class="ov" id="ov" onclick="closeNote()"></div>
<div class="note-modal" id="nm">
  <div class="nm-title" id="nt">Note on <strong>—</strong></div>
  <textarea placeholder="Add a note or instruction for next Vizor run…" id="ntxt"></textarea>
  <div class="ac-row">
    <span class="ac-lbl">Action:</span>
    <button class="ac" data-tag="Redo stage" onclick="this.classList.toggle('on')">↺ Redo stage</button>
    <button class="ac" data-tag="Reassign agent" onclick="this.classList.toggle('on')">⇄ Reassign agent</button>
    <button class="ac" data-tag="Defer" onclick="this.classList.toggle('on')">⏸ Defer</button>
  </div>
  <div class="nm-footer">
    <button class="btn btn-cancel" onclick="closeNote()">Cancel</button>
    <button class="btn btn-save" onclick="saveNote()">Save note</button>
  </div>
</div>

<svg style="display:none"><symbol id="pencil-svg" viewBox="0 0 16 16">
  <polygon points="2,14 3.5,10 12,1.5 14.5,4 6,12.5" fill="currentColor" opacity=".85"/>
  <polygon points="2,14 3.5,10 5.5,12" fill="currentColor"/>
  <rect x="12.2" y="0.5" width="2.5" height="3" rx=".5" fill="currentColor" opacity=".6"/>
  <line x1="4.5" y1="11" x2="12.5" y2="3" stroke="white" stroke-width=".7" opacity=".3"/>
</symbol></svg>

<div class="content">
  <div class="ws-header">
    <div>
      <div class="ws-title">{html.escape(str(data.get("workspace", {}).get("name", "workspace")))}</div>
      <div class="ws-sub" id="ws-sub">Loading timeline…</div>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin-left:auto;">
      <div class="pivot-controls">
        <button id="pivot-release-btn" class="pivot-btn active" onclick="setPivot('release')">By Release</button>
        <button id="pivot-goal-btn" class="pivot-btn" onclick="setPivot('goal')">By Goal</button>
      </div>
      <div class="ws-chip">● live</div>
    </div>
  </div>
  <div class="toolbar">
    <span class="lbl">Filter:</span>
    <button class="chip on">All</button><button class="chip">In Progress</button><button class="chip">Ships soon</button>
    <div class="sp"></div>
    <button class="zbtn">← 4w</button>
    <button class="zbtn" style="border-color:var(--accent);color:var(--accent)">10w ✓</button>
    <button class="zbtn">26w →</button>
  </div>

  <div class="gw"><div class="gantt" id="gantt">
    <div class="gh" id="gantt-header">
      <div class="ghl">Release / Epic</div>
      <div class="gwk">Goal</div><div class="gwk">Open</div>
      <div class="gwk">Visualize</div><div class="gwk now">Execute ▾</div>
      <div class="gwk">Release</div><div class="gwk">Notify</div>
      <div class="gwk">Sustain</div><div class="gwk">QA Gate</div>
      <div class="gwk">Target</div><div class="gwk">Review</div>
    </div>
    <div id="gantt-body"></div>
  </div></div>

  <div class="legend">
    <div class="li"><div class="ld" style="background:#dbeafe;border-color:#93c5fd"></div>◆ Goal</div>
    <div class="li"><div class="ld" style="background:#ede9fe;border-color:#c4b5fd"></div>○ Open</div>
    <div class="li"><div class="ld" style="background:#e6f7f4;border-color:#c0ede6"></div>◌ Visualize</div>
    <div class="li"><div class="ld" style="background:#dcfce7;border-color:#86efac"></div>⚙ Execute</div>
    <div class="li"><div class="ld" style="background:#fef3c7;border-color:#fde68a"></div>▲ Release</div>
    <div class="li"><div class="ld" style="background:#ffe4e6;border-color:#fda4af"></div>✉ Notify</div>
    <div class="li"><div class="ld" style="background:#f3f4f6;border-color:#d1d5db"></div>↺ Sustain</div>
    <span class="lsep">|</span><div class="li" style="font-style:italic">~ animated = in progress</div>
  </div>
  <div class="ni-legend">
    <span class="lbl">Note icons:</span>
    <div class="nil"><svg width="14" height="14" style="color:#9ca3af"><use href="#pencil-svg"/></svg> no note</div>
    <div class="nil"><svg width="14" height="14" style="color:#3b82f6"><use href="#pencil-svg"/></svg> has note</div>
    <div class="nil"><svg width="14" height="14" style="color:#f59e0b"><use href="#pencil-svg"/></svg> action tagged</div>
    <div class="nil"><svg width="14" height="14" style="color:#ef4444"><use href="#pencil-svg"/></svg> urgent / overrun</div>
    <div class="nil"><svg width="14" height="14" style="color:#22c55e"><use href="#pencil-svg"/></svg> resolved</div>
  </div>
  <div class="al-row">
    <span class="lbl">Agents:</span>
    <div class="ali"><div class="aa aa-claude">C</div>Claude</div>
    <div class="ali"><div class="aa aa-agy">A</div>Agy</div>
    <div class="ali"><div class="aa aa-codex">Co</div>Codex</div>
    <div class="ali"><div class="aa aa-grok">G</div>Grok</div>
  </div>

  <div class="srow">
    <div class="sc teal editable"><div class="sl">Releases tracked</div><div class="sv" id="dream-count">0</div><div class="ss" id="dream-sub">0 stages</div><div class="wow">⚡ live</div><div class="pencil-wrap note-none" onclick="openNote('summary','Summary');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc blue editable"><div class="sl">Active agents</div><div class="sv">3</div><div class="aa-stack" style="margin-top:6px"><div class="aa aa-agy">A</div><div class="aa aa-codex">Co</div><div class="aa aa-grok">G</div></div><div class="pencil-wrap note-none" onclick="openNote('agents','Agents');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc org editable"><div class="sl">Total spend</div><div class="sv">$28.50</div><div class="ss">of ~$71 · 40% in</div><div class="pencil-wrap note-none" onclick="openNote('cost','Total spend');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc purp editable"><div class="sl">Next ship</div><div class="sv">Jul 24</div><div class="ss">Module Extraction → main</div><div class="pencil-wrap note-none" onclick="openNote('ship','Next ship');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc teal editable" onclick="toggleGoalsPanel()" style="cursor:pointer;"><div class="sl">Business Goals</div><div class="sv" id="goal-count">0</div><div class="ss" id="goal-sub">0 active</div><div class="pencil-wrap note-none" onclick="openNote('goals','Business Goals');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc teal editable" onclick="toggleVerifiedPanel()" style="cursor:pointer;"><div class="sl">Spec Verified</div><div class="sv" id="spec-verified-count">0</div><div class="ss" id="spec-verified-sub">0 verified PRs</div></div>
  </div>

  <div class="goals-panel" id="goals-panel">
    <div class="goals-header">
      <div class="goals-ttl">🎯 Business Goals</div>
      <div class="goals-close" onclick="toggleGoalsPanel()">✕ collapse</div>
    </div>
    <div class="goals-body" id="goals-body"></div>
  </div>
  <div class="goals-panel" id="spec-verifications-panel">
    <div class="goals-header">
      <div class="goals-ttl">✅ Spec Verified</div>
      <div class="goals-close" onclick="toggleVerifiedPanel()">✕ collapse</div>
    </div>
    <div class="goals-body" id="spec-verifications-body"></div>
  </div>
</div>

<script>
{script_content}
</script>
{_live_js(port)}
</body>
</html>"""

