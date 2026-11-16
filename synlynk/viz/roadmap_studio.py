"""Roadmap Studio: drag/drop Vizor front-end over tpm_sweep's release_proposal tickets.

First Vizor view with real client-side JS (confirmed acceptable in the design
spec — Vizor's zero-JS convention is a convention, not a hard constraint).
See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
"""
from synlynk.viz.chrome import _live_js


def generate_roadmap_studio_html(port: int) -> str:
    """Render the Roadmap Studio shell; ticket/backlog data comes from GET api/roadmap_studio."""
    live = _live_js(port)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — Roadmap Studio</title>
<style>
:root{--bg:#f6f8fa;--panel:#fff;--panel-2:#f1f5f9;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4;--warn:#dc2626;--shadow:0 2px 8px rgba(31,35,40,0.06);--provisional:#d97706;--hold-bg:#fef3c7;--hold-border:#d97706;--hold-ink:#92400e;--drop-bg:#fee2e2;--drop-border:#dc2626;--drop-ink:#991b1b}
@media (prefers-color-scheme: dark){
  :root{--bg:#0d1117;--panel:#161b22;--panel-2:#21262d;--ink:#f0f6fc;--muted:#8b949e;--line:#30363d;--accent:#3de0c0;--accent-bg:#0d2137;--warn:#f87171;--shadow:0 2px 12px rgba(0,0,0,0.4);--provisional:#fbbf24;--hold-bg:#3a2e0f;--hold-border:#d97706;--hold-ink:#fbbf24;--drop-bg:#3a1414;--drop-border:#dc2626;--drop-ink:#f87171}
}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1600px;margin:0 auto;padding:28px 24px 70px}
.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px}
h1{font-size:30px;margin:6px 0 4px;font-weight:700}
.subtitle{color:var(--muted);margin:0 0 20px;font-size:13px}
.board{display:flex;gap:14px;align-items:start;overflow-x:auto;padding-bottom:16px}
.column{background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:10px;min-width:260px;min-height:280px;display:flex;flex-direction:column}
.column.dragover{border-color:var(--accent)}
.column-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.column h2{font-size:13px;margin:0;font-weight:700}
.cap-warn{color:var(--warn);font-size:10px;font-weight:700}
.column-actions{display:flex;gap:6px;margin-bottom:10px}
.btn{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer;font-family:inherit;font-weight:600}
.btn:hover{border-color:var(--accent)}
.btn-approve{border:none;background:var(--accent);color:#fff;font-weight:700}
.btn-approve:hover{opacity:.85}
.btn-hold{border:1px solid var(--hold-border);background:var(--hold-bg);color:var(--hold-ink)}
.btn-drop{border:1px solid var(--drop-border);background:var(--drop-bg);color:var(--drop-ink);font-size:10px;padding:2px 6px}
.btn-pin{border:1px solid var(--accent);background:var(--accent-bg);color:var(--accent);font-size:10px;padding:2px 6px}
.pin-select{font-size:10px;padding:2px;border-radius:4px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.provisional-banner{background:var(--accent-bg);border:1px solid var(--accent);border-radius:8px;padding:8px 12px;font-size:12px;color:var(--ink);margin-bottom:16px}
.column.provisional{border-left:3px solid var(--provisional)}
.column-theme{color:var(--muted);font-size:11px;font-weight:400;margin:2px 0 0}
.card-actions{margin-top:6px}
.revise-box{width:100%;font-size:11px;margin-top:6px;padding:4px;border-radius:4px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:8px;box-shadow:var(--shadow);cursor:grab}
.card h3{font-size:12px;margin:0 0 4px}
.card .meta{color:var(--muted);font-size:10px}
.backlog{margin-top:10px;background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:10px}
.backlog.dragover{border-color:var(--accent)}
.backlog h2{font-size:13px;margin:0 0 10px}
.empty{color:var(--muted);padding:16px 8px;font-size:11px;text-align:center;font-style:italic}
</style></head><body><main>
<div class="eyebrow">Vizor / Roadmap Studio</div>
<h1>Roadmap Studio</h1>
<p class="subtitle">Drag, approve, hold, revise, drop, and pin stories against open release proposals. Writes go straight to the product <code>state.db</code> via the same paths as the GitHub-comment grammar.</p>
<div class="provisional-banner">Nothing below is final. A release only ships once you Approve it.</div>
<div id="board" class="board"></div>
<div class="backlog" id="backlog-pane">
  <h2>Backlog</h2>
  <div id="backlog-list"></div>
</div>
</main>""" + live + """<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let studioData={tickets:[],backlog:[]};

function cardHtml(story,ticketId,openTickets){
  let action='';
  if(ticketId!=null){
    action=`<button class="btn btn-drop" onclick="dropStory('${esc(story.story_id)}')">Drop</button>`;
  }else if((openTickets||[]).length){
    const pinId=`pin-${esc(story.story_id)}`;
    const options=openTickets.map(t=>`<option value="${t.id}">${esc(t.release_version)}</option>`).join('');
    action=`<select class="pin-select" id="${pinId}">${options}</select> <button class="btn btn-pin" onclick="pinStory(Number(document.getElementById('${pinId}').value),'${esc(story.story_id)}')">Pin</button>`;
  }
  return `<article class="card" draggable="true" data-story-id="${esc(story.story_id)}" data-ticket-id="${ticketId??''}">
    <h3>${esc(story.title||story.story_id)}</h3>
    <div class="meta">${esc(story.story_id)} &middot; ${esc(story.role||'')}</div>
    <div class="card-actions">${action}</div>
  </article>`;
}

function draw(){
  const openTickets=(studioData.tickets||[]).filter(t=>t.status==='open'||t.status==='held');
  document.getElementById('board').innerHTML=studioData.tickets.map(t=>{
    const overCap=(t.stories||[]).length>5;
    const statusLabel=t.status==='held'?'ON HOLD — still a proposal':'PROPOSAL — awaiting /approve';
    const themeLine=t.theme?`<div class="column-theme">${esc(t.theme)}</div>`:'';
    return `<section class="column provisional" data-ticket-id="${t.id}">
      <div class="column-header">
        <div>
          <h2>${esc(t.release_version)} &middot; ${statusLabel}</h2>
          ${themeLine}
        </div>
        ${overCap?`<span class="cap-warn">${t.stories.length} of 5 suggested</span>`:''}
      </div>
      <div class="column-actions">
        <button class="btn btn-approve" onclick="approveTicket(${t.id})">Approve</button>
        <button class="btn btn-hold" onclick="holdTicket(${t.id})">Hold</button>
      </div>
      <div class="column-actions">
        <input class="revise-box" placeholder="Revise instructions..." id="revise-${t.id}" onkeydown="if(event.key==='Enter')reviseTicket(${t.id},this.value)">
        <button class="btn" onclick="reviseTicket(${t.id},document.getElementById('revise-${t.id}').value)">Submit</button>
      </div>
      <div class="cards" data-ticket-id="${t.id}">${(t.stories||[]).map(s=>cardHtml(s,t.id,openTickets)).join('')||'<div class="empty">No stories</div>'}</div>
    </section>`;
  }).join('')||'<div class="empty">No open proposals</div>';

  document.getElementById('backlog-list').innerHTML=(studioData.backlog||[]).map(s=>cardHtml(s,null,openTickets)).join('')||'<div class="empty">Backlog empty</div>';

  wireDragAndDrop();
}

function wireDragAndDrop(){
  document.querySelectorAll('.card').forEach(card=>{
    card.addEventListener('dragstart',e=>{
      e.dataTransfer.setData('story_id',card.dataset.storyId);
      e.dataTransfer.setData('from_ticket_id',card.dataset.ticketId||'');
    });
  });
  document.querySelectorAll('.column .cards').forEach(zone=>{
    zone.addEventListener('dragover',e=>{e.preventDefault();zone.closest('.column').classList.add('dragover')});
    zone.addEventListener('dragleave',()=>zone.closest('.column').classList.remove('dragover'));
    zone.addEventListener('drop',e=>{
      e.preventDefault();
      zone.closest('.column').classList.remove('dragover');
      const storyId=e.dataTransfer.getData('story_id');
      const fromTicket=e.dataTransfer.getData('from_ticket_id');
      const toTicket=Number(zone.dataset.ticketId);
      if(!fromTicket){pinStory(toTicket,storyId);}
      else{
        const ids=[...zone.querySelectorAll('.card')].map(c=>c.dataset.storyId);
        ids.push(storyId);
        reorderStories(toTicket,ids);
      }
    });
  });
  const backlogZone=document.getElementById('backlog-pane');
  backlogZone.addEventListener('dragover',e=>{e.preventDefault();backlogZone.classList.add('dragover')});
  backlogZone.addEventListener('dragleave',()=>backlogZone.classList.remove('dragover'));
  backlogZone.addEventListener('drop',e=>{
    e.preventDefault();
    backlogZone.classList.remove('dragover');
    const storyId=e.dataTransfer.getData('story_id');
    const fromTicket=e.dataTransfer.getData('from_ticket_id');
    if(fromTicket)dropStory(storyId);
  });
}

async function load(){
  const r=await fetch('api/roadmap_studio');
  if(!r.ok){document.getElementById('board').textContent='Roadmap Studio unavailable';return}
  studioData=await r.json();
  draw();
}
async function post(path,body){
  const r=await fetch(path,{method:'POST',headers:window.vizorAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify(body)});
  if(!r.ok){alert('Request failed');return}
  await load();
}
function approveTicket(id){post('api/roadmap_studio/approve',{ticket_id:id})}
function holdTicket(id){post('api/roadmap_studio/hold',{ticket_id:id})}
function reviseTicket(id,instructions){post('api/roadmap_studio/revise',{ticket_id:id,instructions})}
function dropStory(storyId){post('api/roadmap_studio/drop',{story_id:storyId})}
function reorderStories(ticketId,orderedStoryIds){post('api/roadmap_studio/reorder',{ticket_id:ticketId,ordered_story_ids:orderedStoryIds})}
function pinStory(ticketId,storyId){post('api/roadmap_studio/pin',{ticket_id:ticketId,story_id:storyId})}
load();
</script></body></html>"""
