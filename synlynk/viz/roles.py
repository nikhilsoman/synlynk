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
        authorities = agent.get("autonomous_authorities") or []
        authority_html = "".join(
            f'<span class="authority {"enforced" if (a.get("enforced") if isinstance(a, dict) else False) else "guidance"}">'
            f'{html.escape(a.get("name", "") if isinstance(a, dict) else str(a))} '
            f'<small>{"Enforced" if (a.get("enforced") if isinstance(a, dict) else False) else "Guidance"}</small></span>'
            for a in authorities
        )
        cards.append(f"""
        <article class="role-card">
          <div class="card-top"><span class="role-tag">@{html.escape(role)}</span>
            <span class="durability">{badge}</span></div>
          <h2>{html.escape(role.replace('-', ' ').title())}</h2>
          <div class="meta"><span>Target Harnesses</span><strong>{html.escape(', '.join(map(str, harnesses)))}</strong></div>
          <p class="excerpt">{html.escape(str(agent.get('charter_excerpt') or 'No charter excerpt available.'))}</p>
          <details class="edit-charter">
            <summary>Edit Charter</summary>
            <form class="charter-edit-form" data-agent-id="{html.escape(str(agent.get('agent_id') or ''))}"
                  data-revision="{int(agent.get('charter_revision') or 0)}"
                  onsubmit="return window.__submitCharterEdit(event)">
              <label>Mandate (Instructions section)
                <textarea name="mandate" rows="4">{html.escape(str(agent.get('charter_excerpt') or ''))}</textarea>
              </label>
              <label>Attach existing capability
                <select name="capability_id">
                  <option value="">— none —</option>
                  {"".join(f'<option value="{html.escape(c.get("capability_id",""))}">{html.escape(c.get("capability_id",""))} ({html.escape(c.get("source",""))})</option>' for c in (data.get("capability_registry") or []))}
                </select>
              </label>
              <button type="submit" class="primary">Save revision</button>
              <span class="save-status" aria-live="polite"></span>
            </form>
          </details>
          <div class="authorities">{authority_html}</div>
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
.edit-charter{{margin-top:12px}}.edit-charter summary{{cursor:pointer;color:var(--accent);font-weight:700}}
.charter-edit-form{{display:grid;gap:8px;margin-top:10px}}.charter-edit-form textarea{{border:1px solid var(--line);border-radius:7px;padding:8px;font:inherit}}
.save-status{{font-size:11px;color:var(--muted)}}
.authorities{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}.authority{{font-size:11px;border-radius:99px;padding:4px 8px;background:var(--accent-bg);color:#087462}}
.authority.guidance{{background:#f1f0ea;color:#8a7a3a}}.authority small{{font-weight:700;margin-left:3px}}
.wizard .steps{{list-style:none;display:flex;gap:10px;padding:0;margin:0 0 16px;font-size:12px;color:#7fa8a3}}
.wizard .steps li.active{{color:#3de0c0;font-weight:700}}
.wizard [data-panel]{{display:grid;gap:10px}}.wizard pre{{background:#0c2225;padding:10px;border-radius:7px;color:#9ef5df}}
.wizard-status{{font-size:11px;color:#b7d4ce}}
</style></head><body><main>
<div class="eyebrow">Vizor / Living Workspace</div><h1>Workspace Agent Roles</h1>
<p class="subtitle">Living Charters for <strong>{workspace_name}</strong> — durable identities with visible ownership.</p>
<section class="summary"><div><strong>Workspace Persona &amp; Goals</strong><span>{len(agents)} active role(s) · governed by living charters</span></div><div class="goals"><strong>Active goals</strong><span>{goal_summary}</span></div></section>
<section><div class="section-head"><h2>Living Charters</h2><span>{len(agents)} active</span></div><div class="grid">{cards_html}</div></section>
<section class="drawer" id="provision"><h2>Onboard Workspace Role</h2>
<div class="wizard" id="ftue-wizard">
  <ol class="steps">
    <li data-step="1" class="active">1. Function family</li>
    <li data-step="2">2. Fields</li>
    <li data-step="3">3. Escalation scope</li>
    <li data-step="4">4. Identity</li>
    <li data-step="5">5. Review</li>
  </ol>
  <form id="ftue-form" onsubmit="return window.__submitFtue(event)">
    <div data-panel="1">
      <label>Function family
        <select name="role">
          <option value="dev">dev — delivery</option>
          <option value="qa">qa — quality/trust</option>
          <option value="secops">secops — quality/trust</option>
          <option value="maintainer">maintainer — platform</option>
          <option value="infra-devops">infra-devops — platform</option>
          <option value="designer">designer — experience</option>
          <option value="marketing">marketing — experience</option>
        </select>
      </label>
      <button type="button" onclick="window.__ftueNext(1)">Next</button>
    </div>
    <div data-panel="2" hidden>
      <label>Mandate (free text)<textarea name="mandate" rows="3"></textarea></label>
      <label>Durability
        <select name="durability"><option value="durable">durable</option><option value="dispatch-only">dispatch-only</option><option value="session-only">session-only</option></select>
      </label>
      <button type="button" onclick="window.__ftueNext(2)">Next</button>
    </div>
    <div data-panel="3" hidden>
      <p>Escalation triggers and veto scope are refined after activation, in the
         BAU charter editor above — this step confirms you understand the role
         activates with its taxonomy default scope (spec §2).</p>
      <button type="button" onclick="window.__ftueNext(3)">Next</button>
    </div>
    <div data-panel="4" hidden>
      <p>After activation, provision this role's GitHub App identity from a
         terminal (requires a browser for GitHub's manifest flow — cannot run
         inside Vizor):</p>
      <pre id="ftue-identity-cmd">synlynk identity init --role &lt;role&gt;</pre>
      <button type="button" onclick="window.__ftueNext(4)">Next</button>
    </div>
    <div data-panel="5" hidden>
      <p>Review your selections, then activate.</p>
      <button type="submit" class="primary">Activate role</button>
    </div>
  </form>
  <p class="wizard-status" aria-live="polite"></p>
</div>
</section>
</main>
<script>
window.__ftueNext = function(fromStep) {{
  document.querySelector('[data-panel="' + fromStep + '"]').hidden = true;
  document.querySelector('[data-panel="' + (fromStep + 1) + '"]').hidden = false;
  document.querySelectorAll(".steps li").forEach(li => li.classList.remove("active"));
  document.querySelector('[data-step="' + (fromStep + 1) + '"]').classList.add("active");
  if (fromStep + 1 === 4) {{
    const role = document.querySelector('[name="role"]').value;
    document.getElementById("ftue-identity-cmd").textContent = "synlynk identity init --role " + role;
  }}
}};
window.__submitFtue = function(ev) {{
  ev.preventDefault();
  const form = ev.target;
  const status = document.querySelector(".wizard-status");
  const body = {{
    role: form.role.value,
    durability: form.durability.value,
    mandate: form.mandate.value,
  }};
  status.textContent = "activating...";
  fetch("/roles/create", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body),
  }}).then(r => r.json()).then(result => {{
    status.textContent = result.ok
      ? "activated as " + result.agent_id + " — reload to see it in Living Charters"
      : "error: " + result.error;
  }}).catch(() => {{ status.textContent = "network error"; }});
  return false;
}};
window.__submitCharterEdit = function(ev) {{
  ev.preventDefault();
  const form = ev.target;
  const status = form.querySelector(".save-status");
  const body = {{
    agent_id: form.dataset.agentId,
    parent_revision: parseInt(form.dataset.revision, 10),
    mandate: form.mandate.value,
  }};
  status.textContent = "saving...";
  fetch("/roles/charter/update", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body),
  }}).then(r => r.json()).then(result => {{
    if (result.ok) {{
      status.textContent = "saved (rev " + result.revision + ") — reload to see it live";
      form.dataset.revision = result.revision;
    }} else {{
      status.textContent = "error: " + result.error;
    }}
  }}).catch(() => {{ status.textContent = "network error"; }});
  return false;
}};
</script>
{live}</body></html>"""

