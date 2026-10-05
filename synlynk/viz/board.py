"""GOVERNS board and boardroom canvases."""
import html
from synlynk.viz.chrome import _live_js
def generate_boardroom_html(workspace_slug: str, autonomy_mode: str = "supervised") -> str:
    """Render the executive glassmorphic Sovereign Boardroom HUD for a workspace.

    Distinct from generate_board_html() above (the GOVERNS Kanban board of
    stories) — this is the Ed25519 proposal-ledger/Autonomy Dial governance
    surface at /w/<slug>/board, backed by synlynk/board_governance.py.
    """
    mode = str(autonomy_mode or "supervised").lower()
    slug_html = html.escape(workspace_slug or "")

    def dial_class(candidate: str) -> str:
        return "dial-btn active" if mode == candidate else "dial-btn"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sovereign Boardroom — {slug_html}</title>
  <style>
    :root{{color-scheme:dark}}
    *{{box-sizing:border-box}}
    body {{ background: radial-gradient(circle at top, #141b2d, #05070d 70%); color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 32px; min-height: 100vh; }}
    .board-header {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 20px; margin-bottom: 28px; }}
    .eyebrow {{ color: #a5b4fc; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; font-size: 11px; margin: 0 0 4px; }}
    h1 {{ margin: 0; font-size: 26px; font-weight: 700; }}
    .subtitle {{ margin: 6px 0 0; color: #94a3b8; font-size: 13px; }}
    .chair-badge {{ background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 6px 14px; border-radius: 9999px; font-weight: 600; font-size: 13px; box-shadow: 0 4px 18px rgba(99,102,241,0.35); }}
    .dial-container {{ display: flex; gap: 6px; background: rgba(255,255,255,0.06); backdrop-filter: blur(12px); padding: 4px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); }}
    .dial-btn {{ border: none; padding: 8px 16px; border-radius: 7px; cursor: pointer; color: #94a3b8; background: transparent; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .dial-btn.active {{ background: #3b82f6; color: white; box-shadow: 0 2px 10px rgba(59,130,246,0.5); }}
    .panel-row {{ display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
    .proposals-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .prop-card {{ background: rgba(30, 41, 59, 0.55); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 20px; }}
    .prop-card h3 {{ margin-top: 0; }}
    .empty-state {{ color: #94a3b8; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="board-header">
    <div>
      <p class="eyebrow">Sovereign Boardroom</p>
      <h1>Sovereign Boardroom HUD</h1>
      <p class="subtitle">Workspace: <strong>{slug_html}</strong> &middot; Genesis Chair: <strong>Nikhil Soman</strong></p>
    </div>
    <div class="panel-row">
      <span class="eyebrow" style="margin:0;">Autonomy Dial</span>
      <div class="dial-container" id="autonomy-dial" data-mode="{mode}">
        <button class="{dial_class('manual')}" data-mode="manual">Manual</button>
        <button class="{dial_class('supervised')}" data-mode="supervised">Supervised</button>
        <button class="{dial_class('autonomous')}" data-mode="autonomous">Autonomous</button>
      </div>
      <div class="chair-badge">Genesis Seat Active &mdash; Nikhil Soman</div>
    </div>
  </div>
  <div class="proposals-grid" id="proposals-container">
    <div class="prop-card empty-state">Loading proposals&hellip;</div>
  </div>
  <script>
    async function loadProposals() {{
      const container = document.getElementById('proposals-container');
      try {{
        const r = await fetch('api/board/proposals');
        if (!r.ok) {{ container.innerHTML = '<div class="prop-card empty-state">Boardroom proposals unavailable.</div>'; return; }}
        const data = await r.json();
        const proposals = data.proposals || [];
        if (!proposals.length) {{
          container.innerHTML = '<div class="prop-card empty-state">No pending proposals require board signature.</div>';
          return;
        }}
        container.innerHTML = proposals.map(p => `<div class="prop-card">
          <h3>${{p.title}}</h3>
          <p class="empty-state">${{p.gate}} &middot; ${{p.status}}</p>
          <p>${{p.description || ''}}</p>
        </div>`).join('');
      }} catch (err) {{
        container.innerHTML = '<div class="prop-card empty-state">Boardroom proposals unavailable.</div>';
      }}
    }}
    loadProposals();
  </script>
</body>
</html>"""


def generate_board_html(port: int) -> str:
    """Render the local product board shell; cards come from product state.db."""
    live = _live_js(port)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — GOVERNS Board</title>
<style>
:root{--bg:#f6f8fa;--panel:#fff;--panel-2:#f1f5f9;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4;--shadow:0 2px 8px rgba(31,35,40,0.06)}
@media (prefers-color-scheme: dark){
  :root{--bg:#0d1117;--panel:#161b22;--panel-2:#21262d;--ink:#f0f6fc;--muted:#8b949e;--line:#30363d;--accent:#3de0c0;--accent-bg:#0d2137;--shadow:0 2px 12px rgba(0,0,0,0.4)}
}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1600px;margin:0 auto;padding:28px 24px 70px}
.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px}
h1{font-size:30px;margin:6px 0 4px;font-weight:700}
.subtitle{color:var(--muted);margin:0 0 20px;font-size:13px}
.filters{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin-bottom:20px;box-shadow:var(--shadow)}
select{border:1px solid var(--line);border-radius:6px;padding:6px 10px;background:var(--panel);color:var(--ink);font-size:12px;outline:none}
select:focus{border-color:var(--accent)}
.board{display:grid;grid-template-columns:repeat(7,minmax(200px,1fr));gap:12px;align-items:start;overflow-x:auto;padding-bottom:16px}
.column{background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:10px;min-height:280px;display:flex;flex-direction:column}
.column-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.column h2{font-size:12px;margin:0;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--ink)}
.column-count{font-size:10px;font-weight:700;padding:2px 6px;border-radius:999px;background:var(--panel);border:1px solid var(--line);color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;margin-bottom:10px;box-shadow:var(--shadow);transition:transform .15s,border-color .15s}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;gap:6px}
.status-pill{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;border:1px solid;text-transform:uppercase;letter-spacing:.03em}
.story-id{font-family:monospace;font-size:10px;color:var(--muted)}
.card h3{font-size:12px;margin:0 0 8px;line-height:1.4;font-weight:600;color:var(--ink)}
.meta{color:var(--muted);font-size:11px;margin:3px 0}
.goal-meta{color:var(--accent);font-weight:500}
.links{display:flex;gap:8px;font-size:11px;margin-top:6px}
.links a{color:var(--accent);text-decoration:none;font-weight:500}
.links a:hover{text-decoration:underline}
.card-actions{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:6px}
.status-btns{display:flex;gap:4px;flex-wrap:wrap}
.st-btn{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:3px 6px;font-size:10px;cursor:pointer;font-family:inherit;font-weight:600;transition:all .15s}
.st-btn:hover{filter:brightness(.92);border-color:currentColor}
.stage-select{width:100%;font-size:10px;padding:3px 6px;border-radius:4px;border:1px solid var(--line);background:var(--bg)}
.pulse-dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;animation:pdot 1.5s infinite}
@keyframes pdot{0%,100%{opacity:1}50%{opacity:.3}}
.empty{color:var(--muted);padding:24px 8px;font-size:11px;text-align:center;font-style:italic}
@media(max-width:1200px){.board{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}}
</style></head><body><main>
<div class="eyebrow">Vizor / Product graph</div>
<h1>GOVERNS Board</h1>
<p class="subtitle">Claimed work across every repository in this product mapped across the 7 GOVERNS lifecycle stages. Changes write to the product <code>state.db</code>.</p>
<div class="filters">
  <select id="repo"><option value="">All repositories</option></select>
  <select id="type"><option value="">All types</option></select>
  <select id="goal"><option value="">All goals</option></select>
  <select id="status"><option value="">All statuses</option><option value="open">Open</option><option value="ready">Ready</option><option value="in_progress">In Progress</option><option value="blocked">Blocked</option><option value="done">Done</option></select>
  <span id="identity" class="meta" style="margin-left:auto;font-weight:600;"></span>
</div>
<div id="board" class="board"></div>
</main>""" + live + """<script>
const stages=['goal','open','visualize','execute','release','notify','sustain'];
const stageIcons={goal:'◆ Goal',open:'○ Open',visualize:'◌ Visualize',execute:'⚙ Execute',release:'▲ Release',notify:'✉ Notify',sustain:'↺ Sustain'};
const statusColors={
  open:{bg:'rgba(100,116,139,0.12)',border:'#cbd5e1',color:'#64748b',label:'Open'},
  ready:{bg:'rgba(37,99,235,0.12)',border:'rgba(37,99,235,0.35)',color:'#2563eb',label:'Ready'},
  in_progress:{bg:'rgba(13,158,135,0.15)',border:'rgba(13,158,135,0.4)',color:'#0d9e87',label:'In Progress'},
  blocked:{bg:'rgba(220,38,38,0.12)',border:'rgba(220,38,38,0.35)',color:'#dc2626',label:'Blocked'},
  done:{bg:'rgba(22,163,74,0.12)',border:'rgba(22,163,74,0.35)',color:'#16a34a',label:'Done'}
};
let boardData={};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function options(id, values){const el=document.getElementById(id); values.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;el.appendChild(o);});}
function link(pointer){return pointer&&pointer.url?`<a href="${esc(pointer.url)}" target="_blank" rel="noopener">${esc(pointer.tracker)} #${esc(pointer.id)}</a>`:'';}
function draw(){
  const repo=document.getElementById('repo').value,type=document.getElementById('type').value,goal=document.getElementById('goal').value,status=document.getElementById('status').value;
  const cards=(boardData.cards||[]).filter(c=>(!repo||c.repo_id===repo)&&(!type||c.type_id===type)&&(!goal||c.goal_id===goal)&&(!status||c.status===status));
  document.getElementById('board').innerHTML=stages.map(st=>{
    const stageCards=cards.filter(c=>(c.governs_stage||c.stage||'open')===st);
    return `<section class="column" data-stage="${st}">
      <div class="column-header"><h2>${stageIcons[st]||st}</h2><span class="column-count">${stageCards.length}</span></div>
      ${stageCards.map(c=>{
        const sc=statusColors[c.status]||statusColors.open;
        const pulseHtml=c.status==='in_progress'?'<span class="pulse-dot"></span> ':'';
        return `<article class="card" id="card-${esc(c.story_id)}">
          <div class="card-top">
            <span class="status-pill" style="background:${sc.bg};border-color:${sc.border};color:${sc.color};">${pulseHtml}${esc(sc.label)}</span>
            <span class="story-id">${esc(c.story_id)}</span>
          </div>
          <h3>${esc(c.title)}</h3>
          <div class="meta">${esc(c.repo_name||c.repo_id||'unassigned')} · ${esc(c.type_id||'untyped')}</div>
          ${c.goal_id?`<div class="meta goal-meta">🎯 ${esc(c.goal_id)}</div>`:`<div class="meta goal-meta unmapped-goal">⚪ Unmapped</div>`}
          <div class="links">${link(c.tracker)}${c.pr_url?`<a href="${esc(c.pr_url)}" target="_blank" rel="noopener">PR</a>`:''}</div>
          <div class="card-actions">
            <div class="status-btns">
              ${['ready','in_progress','done','blocked'].filter(s=>s!==c.status).map(s=>{
                const btnSc=statusColors[s]||statusColors.open;
                return `<button class="st-btn" data-id="${esc(c.story_id)}" data-status="${s}" style="color:${btnSc.color};">${esc(btnSc.label)}</button>`;
              }).join(' ')}
            </div>
            <select class="stage-select" data-id="${esc(c.story_id)}" onchange="updateStage('${esc(c.story_id)}',this.value)">
              ${stages.map(s=>`<option value="${s}" ${(c.governs_stage===s||(!c.governs_stage&&s==='open'))?'selected':''}>Move: ${stageIcons[s]}</option>`).join('')}
            </select>
          </div>
        </article>`;
      }).join('')||'<div class="empty">No cards</div>'}
    </section>`;
  }).join('');
  document.querySelectorAll('button[data-status]').forEach(b=>b.onclick=()=>updateStatus(b.dataset.id,b.dataset.status));
}
async function load(){
  const q=new URLSearchParams();
  ['repo','type','goal'].forEach(k=>{const v=document.getElementById(k).value;if(v)q.set(k+'_id',v)});
  const r=await fetch('api/board?'+q.toString());
  if(!r.ok){document.getElementById('board').textContent='Board unavailable';return}
  boardData=await r.json();
  document.getElementById('identity').textContent='Product: '+(boardData.identity_slug||'unknown');
  draw();
}
async function updateStatus(id,status){
  const r=await fetch('api/board/status',{method:'POST',headers:window.vizorAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify({story_id:id,status})});
  if(!r.ok){alert('Status update failed');return}
  await load();
}
async function updateStage(id,stage){
  const r=await fetch('api/board/stage',{method:'POST',headers:window.vizorAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify({story_id:id,stage})});
  if(!r.ok){alert('Stage update failed');return}
  await load();
}
['repo','type','goal','status'].forEach(id=>document.getElementById(id).onchange=()=>id==='status'?draw():load());
fetch('api/board').then(r=>r.json()).then(d=>{
  boardData=d;
  options('repo',d.filters.repos||[]);
  options('type',d.filters.types||[]);
  options('goal',d.filters.goals||[]);
  document.getElementById('identity').textContent='Product: '+(d.identity_slug||'unknown');
  draw();
});
</script></body></html>"""

