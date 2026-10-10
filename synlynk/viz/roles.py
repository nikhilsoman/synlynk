"""Workspace role canvas."""
import html
from synlynk.viz.chrome import _live_js
def generate_roles_html(data: dict, port: int) -> str:
    """Render the offline-first Workspace Agent Roles & Onboarding Studio."""
    workspace = data.get("workspace") or {}
    goals = data.get("goals") or []
    agents = [agent for agent in (data.get("workspace_agents") or []) if not agent.get("disabled")]
    cards = []
    for agent in agents:
        role = str(agent.get("role") or "unknown")
        durability = str(agent.get("durability") or "dispatch-only")
        badge = "Durable" if durability == "durable" else "Dispatch-only"
        harnesses = agent.get("target_harnesses") or ["Unassigned"]
        cards.append(f"""
        <article class="role-card">
          <div class="card-top"><span class="role-tag">@{html.escape(role)}</span>
            <span class="durability">{badge}</span></div>
          <h2>{html.escape(role.replace('-', ' ').title())}</h2>
          <div class="meta"><span>Target Harnesses</span><strong>{html.escape(', '.join(map(str, harnesses)))}</strong></div>
          <p class="excerpt">{html.escape(str(agent.get('charter_excerpt') or 'No charter excerpt available.'))}</p>
          <button class="edit" data-agent-id="{html.escape(str(agent.get('agent_id') or ''))}">Edit Charter</button>
        </article>""")
    cards_html = "\n".join(cards) or '<div class="empty">No active workspace roles yet. Provision the first one below.</div>'
    goal_summary = " · ".join(
        html.escape(str(goal.get("outcome") or goal.get("criterion") or ""))
        for goal in goals[:3] if isinstance(goal, dict)
    ) or "No active goals recorded"
    workspace_name = html.escape(str(workspace.get("name") or "workspace"))
    live = _live_js(port)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — Workspace Agent Roles</title>
<style>
:root{{--bg:#f6f8fa;--panel:#fff;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:34px 28px 70px}}.eyebrow{{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px}}
h1{{font-size:34px;margin:8px 0}}.subtitle{{color:var(--muted);margin:0 0 24px}}.summary{{display:flex;gap:18px;align-items:center;justify-content:space-between;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-bottom:30px}}
.summary strong{{display:block;font-size:16px;margin-bottom:5px}}.summary span{{color:var(--muted)}}.summary .goals{{max-width:56%;text-align:right}}.section-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}}h2{{margin:0 0 12px;font-size:19px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
.role-card,.empty{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 4px 15px #1f23280d}}.card-top{{display:flex;justify-content:space-between;align-items:center}}.role-tag{{color:var(--accent);font-weight:700}}.durability{{background:var(--accent-bg);border-radius:99px;color:#087462;padding:5px 9px;font-size:11px;font-weight:700}}.role-card h2{{margin-top:17px;text-transform:capitalize}}.meta{{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:11px}}.meta strong{{display:block;color:var(--ink);font-size:13px;margin-top:4px}}.excerpt{{color:var(--muted);line-height:1.5;min-height:64px}}button{{cursor:pointer;border:0;border-radius:8px;padding:9px 13px;font-weight:700}}.edit,.primary{{background:var(--accent);color:#fff}}.empty{{color:var(--muted);padding:28px;text-align:center}}
.drawer{{margin-top:34px;background:#102a2d;color:#eefcf8;border-radius:16px;padding:24px}}.drawer h2{{color:#fff}}.drawer p{{color:#b7d4ce}}.options{{display:flex;flex-wrap:wrap;gap:9px;margin:18px 0}}.option{{background:#1b4546;color:#d6f5ef;border:1px solid #2b6463}}.option.selected{{background:#3de0c0;color:#082b2a}}form{{display:grid;grid-template-columns:1fr 1fr auto;gap:10px;align-items:end}}label{{display:flex;flex-direction:column;gap:6px;color:#b7d4ce;font-size:11px}}input,select{{border:1px solid #47736f;background:#0c2225;color:#fff;border-radius:7px;padding:10px;font:inherit}}@media(max-width:700px){{.summary,form{{display:block}}.summary .goals{{max-width:none;text-align:left;margin-top:12px}}form>*{{margin-top:10px;width:100%}}}}
</style></head><body><main>
<div class="eyebrow">Vizor / Living Workspace</div><h1>Workspace Agent Roles</h1>
<p class="subtitle">Living Charters for <strong>{workspace_name}</strong> — durable identities with visible ownership.</p>
<section class="summary"><div><strong>Workspace Persona &amp; Goals</strong><span>{len(agents)} active role(s) · governed by living charters</span></div><div class="goals"><strong>Active goals</strong><span>{goal_summary}</span></div></section>
<section><div class="section-head"><h2>Living Charters</h2><span>{len(agents)} active</span></div><div class="grid">{cards_html}</div></section>
<section class="drawer" id="provision"><h2>Onboard Workspace Role</h2><p>Choose an archetype to provision a governed identity in one click.</p>
<div class="options">{''.join(f'<button type="button" class="option{" selected" if value == "fullstack-builder" else ""}" data-archetype="{value}">{label}</button>' for value, label in (("fullstack-builder", "Fullstack Builder"), ("qa-reviewer", "QA Reviewer"), ("architect", "Architect"), ("marketing", "Marketing"), ("custom", "Custom")))}</div>
<form id="role-form"><label>Role slug<input id="role" name="role" value="fullstack-builder" required></label><label>Durability<select id="durability" name="durability"><option value="durable">Durable</option><option value="dispatch-only">Dispatch-only</option><option value="session-only">Session-only</option></select></label><button class="primary" type="submit">Provision role</button></form><div id="role-result" aria-live="polite"></div></section>
</main>{live}<script>
const options=document.querySelectorAll('.option');options.forEach(b=>b.addEventListener('click',()=>{{options.forEach(x=>x.classList.remove('selected'));b.classList.add('selected');document.querySelector('#role').value=b.dataset.archetype;}}));
document.querySelector('#role-form').addEventListener('submit',async e=>{{e.preventDefault();const result=document.querySelector('#role-result');const payload={{role:document.querySelector('#role').value.trim(),durability:document.querySelector('#durability').value}};try{{const r=await fetch('/roles/create',{{method:'POST',headers:Object.assign({{'Content-Type':'application/json'}},window.vizorAuthHeaders?window.vizorAuthHeaders():{{}}),body:JSON.stringify(payload)}});const out=await r.json();result.textContent=out.ok?'Provisioned '+out.agent_id:(out.error||'Provisioning failed');if(out.ok)setTimeout(()=>location.reload(),500);}}catch(err){{result.textContent='Provisioning failed: '+err.message;}}}});
</script></body></html>"""

