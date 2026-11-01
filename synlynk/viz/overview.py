"""Per-workspace Overview canvas."""
import html
import json
from synlynk.viz import nav
from synlynk.viz.chrome import _live_js
def generate_overview_html(data: dict, port: int) -> str:
    """Generate the per-workspace Overview canvas (overview.html)."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # 1. Active sentinel alerts, grouped by pattern code.
    from synlynk.viz.data import group_workspace_sentinel_alerts

    sentinel_alerts = [
        a for a in data.get("telemetry", {}).get("sentinel_alerts", [])
        if not a.get("resolved")
    ]
    hud = group_workspace_sentinel_alerts(
        sentinel_alerts, data.get("sentinel_acks") or {}
    )
    alerts_html = ""

    def _sev_class(sev: str) -> str:
        return "sev-crit" if sev in ("CRITICAL", "CRIT") else "sev-warn"

    def _action_buttons(scope: str, code: str, index=None, section="active") -> str:
        index_attr = f' data-alert-index="{index}"' if index is not None else ""
        attrs = (
            f'data-sentinel-scope="{html.escape(scope)}" '
            f'data-sentinel-code="{html.escape(code)}" '
            f'data-sentinel-section="{html.escape(section)}"{index_attr}'
        )
        return (
            '<div class="sentinel-actions">'
            f'<button type="button" data-sentinel-action="inspect" {attrs}>Inspect</button>'
            f'<button type="button" data-sentinel-action="ignore" {attrs}>Ignore</button>'
            f'<button type="button" data-sentinel-action="issue" {attrs}>Raise issue</button>'
            f'<button type="button" data-sentinel-action="investigate" {attrs}>Investigate</button>'
            '</div>'
        )

    def _member_button(member: dict, index: int, code: str, section: str) -> str:
        sev = str(member.get("severity") or "WARNING").upper()
        pattern = member.get("pattern") or ""
        raw_msg = member.get("message") or "Sentinel alert active"
        msg = f"{pattern}: {raw_msg}" if pattern and not str(raw_msg).startswith(str(pattern)) else raw_msg
        ts = str(member.get("ts") or "")
        return (
            f'<div class="sentinel-member"><div class="alert-item {_sev_class(sev)}">'
            f'<span class="alert-pill">{html.escape(sev)}</span>'
            f'<span class="alert-msg">{html.escape(str(msg))}</span>'
            f'<span class="alert-ts">{html.escape(ts)}</span>'
            f'</div>{_action_buttons("occurrence", code, index, section)}</div>'
        )

    def _group_details(group: dict, start_index: int, section: str) -> tuple:
        code = str(group.get("code") or "")
        sev = str(group.get("severity") or "WARNING").upper()
        open_attr = "" if group.get("collapsed") else " open"
        buttons = []
        index = start_index
        for member in group.get("members") or []:
            buttons.append(_member_button(member, index, code, section))
            index += 1
        hidden = int(group.get("hidden_member_count") or 0)
        more = f'<div class="sentinel-more">{hidden} more</div>' if hidden else ""
        block = (
            f'<details class="sentinel-group" data-sentinel-group="{html.escape(code)}"{open_attr}>'
            f'<summary class="alert-item {_sev_class(sev)}">'
            f'<span class="alert-pill">{html.escape(sev)}</span>'
            f'<span class="sentinel-code">{html.escape(code)}</span>'
            f'<span class="sentinel-count">{int(group.get("count") or 0)}</span>'
            f'<span class="alert-ts">first seen {html.escape(str(group.get("first_seen") or ""))}</span>'
            f'<span class="alert-ts">last seen {html.escape(str(group.get("last_seen") or ""))}</span>'
            f'{_action_buttons("pattern", code, section=section)}'
            f'</summary>'
            f'<div class="sentinel-members">{"".join(buttons)}{more}</div>'
            f'</details>'
        )
        return block, index

    if hud["active_count"] or hud["acked_count"]:
        index = 0
        active_parts = []
        for group in hud["groups"]:
            block, index = _group_details(group, index, "active")
            active_parts.append(block)
        acked_parts = []
        for group in hud["acked"]:
            block, index = _group_details(group, index, "acked")
            acked_parts.append(block)
        alerts_html = f"""
        <div class="alerts-banner">
          <div class="alerts-header">
            <span class="alerts-icon">⚠️</span>
            <span class="alerts-title">Active Sentinel Alerts ({hud["active_count"]})</span>
          </div>
          <div class="alerts-list">
            {"".join(active_parts)}
            <details class="sentinel-acked">
              <summary>Acked ({hud["acked_count"]})</summary>
              {"".join(acked_parts)}
            </details>
          </div>
        </div>
        """

    # 2. Stat Cards Data
    goals = data.get("goals") or []
    active_goals_count = len([g for g in goals if g.get("status") == "active" or not g.get("status")])

    open_stories_count = 0
    total_stories_count = 0
    done_stories_count = 0
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                total_stories_count += 1
                st = str(task.get("status") or "").lower()
                if st in ("done", "completed", "resolved", "merged"):
                    done_stories_count += 1
                elif st in ("active", "ready", "open", "in_progress", "todo", "in progress"):
                    open_stories_count += 1
    if open_stories_count == 0 and total_stories_count == 0:
        repos = workspace.get("repos") or []
        if repos and isinstance(repos[0], dict):
            open_stories_count = int(repos[0].get("active_dream_count") or 0)

    jobs = data.get("jobs") or []
    running_jobs_count = len([j for j in jobs if str(j.get("status") or "").lower() in ("running", "active", "dispatched")])

    costs = data.get("costs") or {}
    total_burn = float(costs.get("total_usd") or 0.0)

    # 3. Goal Progress Rollup
    goal_cards = []
    if goals:
        for g in goals[:6]:
            gid = g.get("id") or "goal"
            outcome = g.get("outcome") or g.get("name") or gid
            criterion = g.get("criterion") or ""
            pct = int((done_stories_count / total_stories_count) * 100) if total_stories_count > 0 else 0
            crit_html = f'<div class="goal-criterion">{html.escape(criterion)}</div>' if criterion else ''
            goal_cards.append(f"""
            <div class="goal-item">
              <div class="goal-top">
                <span class="goal-badge">{html.escape(gid)}</span>
                <span class="goal-outcome">{html.escape(outcome)}</span>
                <span class="goal-pct">{pct}%</span>
              </div>
              {crit_html}
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: {pct}%;"></div>
              </div>
            </div>
            """)
    else:
        goal_cards.append("""
        <div class="empty-hint">
          No active goals in state.db. Run <code>synlynk goal create</code> to define an outcome.
        </div>
        """)
    goals_html = "\n".join(goal_cards)

    # 4. Recent / Active Jobs Feed
    job_rows = []
    if jobs:
        for j in jobs[:6]:
            jid = j.get("job_id") or j.get("id") or "job"
            agent = j.get("agent") or j.get("harness") or "agent"
            task_desc = j.get("task_description") or j.get("task") or j.get("branch") or jid
            st = str(j.get("status") or "completed").lower()
            pr_url = j.get("pr_url") or j.get("pr") or ""

            if st in ("running", "active"):
                st_badge = '<span class="status-chip running">● running</span>'
            elif st in ("circuit_breaker_tripped", "circuit_breaker"):
                st_badge = '<span class="status-chip circuit-breaker">⚡ BREAKER</span>'
            elif "pr" in st or pr_url:
                st_badge = '<span class="status-chip pr-open">✓ PR open</span>'
            elif st in ("completed_without_changes", "failed_noop_denied"):
                st_badge = '<span class="status-chip noop">⚠ NOOP</span>'
            elif st in ("failed", "error", "failed_verification", "failed_unverified", "permission_denied", "scope_violation"):
                st_badge = '<span class="status-chip failed">✕ failed</span>'
            else:
                st_badge = '<span class="status-chip done">✓ completed</span>'

            pr_link_html = f'<a href="{html.escape(pr_url)}" target="_blank" class="job-link">PR ↗</a>' if pr_url else ""

            job_rows.append(f"""
            <div class="job-row">
              <span class="job-id">{html.escape(jid)}</span>
              <span class="agent-chip agent-{html.escape(agent.lower())}">{html.escape(agent)}</span>
              <span class="job-desc" title="{html.escape(task_desc)}">{html.escape(task_desc)}</span>
              {st_badge}
              {pr_link_html}
            </div>
            """)
    else:
        job_rows.append("""
        <div class="empty-hint">
          No recent jobs dispatched. Dispatches from <code>synlynk dispatch</code> will appear here.
        </div>
        """)
    jobs_html = "\n".join(job_rows)

    style = """
    :root {
      --bg: #0d0f14; --bg2: #13171f; --bg3: #1a202c;
      --border: #1e2430; --border2: #2d3748;
      --text: #f3f4f6; --text2: #9ca3af; --text3: #6b7280;
      --accent: #0d9e87; --accent-bg: rgba(13,158,135,0.15); --accent-dim: #14b8a6;
      --shadow: 0 4px 16px rgba(0,0,0,0.25);
      --font-mono: 'SF Mono', 'JetBrains Mono', monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-theme="light"] {
      --bg: #f8fafc; --bg2: #ffffff; --bg3: #f1f5f9;
      --border: #e2e8f0; --border2: #cbd5e1;
      --text: #0f172a; --text2: #475569; --text3: #94a3b8;
      --accent: #0d9e87; --accent-bg: #e6f7f4; --accent-dim: #0b7a60;
      --shadow: 0 2px 10px rgba(0,0,0,0.06);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      padding: 24px 32px 48px;
      line-height: 1.5;
      font-size: 13px;
    }
    a { color: inherit; text-decoration: none; }
    .overview-container { max-width: 1200px; margin: 0 auto; }
    .overview-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .overview-title { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    .overview-sub { font-size: 13px; color: var(--text2); margin-top: 2px; }
    .overview-meta { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--text3); }
    .status-pill {
      background: var(--accent-bg);
      color: var(--accent-dim);
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
    }

    /* Sentinel Banner */
    .alerts-banner {
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 24px;
    }
    .alerts-header { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #f59e0b; margin-bottom: 8px; }
    .alerts-list { display: flex; flex-direction: column; gap: 6px; }
    .alert-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      padding: 4px 8px;
      border-radius: 4px;
      background: var(--bg2);
    }
    .alert-item.sev-crit { border-left: 3px solid #ef4444; }
    .alert-item.sev-warn { border-left: 3px solid #f59e0b; }
    .alert-pill { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; background: rgba(0,0,0,0.2); }
    .alert-msg { flex: 1; word-break: break-word; }
    .alert-ts { color: var(--text3); font-size: 11px; font-family: var(--font-mono); }
    button.alert-item { width: 100%; text-align: left; color: inherit; font: inherit; cursor: pointer; border: 0; }
    .sentinel-member { background: var(--bg2); border-radius: 4px; }
    .sentinel-actions { display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 8px 8px; }
    .sentinel-actions button { cursor: pointer; color: var(--text2); background: var(--bg3); border: 1px solid var(--border2); border-radius: 4px; padding: 3px 7px; font-size: 11px; }
    .sentinel-group, .sentinel-acked { margin-top: 6px; }
    .sentinel-group > summary, .sentinel-acked > summary { cursor: pointer; list-style: none; }
    .sentinel-members { display: flex; flex-direction: column; gap: 6px; margin: 6px 0 0 12px; }
    .sentinel-more { font-size: 11px; color: var(--text3); padding: 2px 8px; }
    .sentinel-panel {
      margin: 0 0 16px;
      padding: 12px 16px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    .sentinel-panel[hidden] { display: none; }

    /* Stat Cards Row */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px 20px;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .stat-card:hover { border-color: var(--accent); transform: translateY(-1px); }
    .stat-label { font-size: 12px; color: var(--text2); font-weight: 500; }
    .stat-value { font-size: 26px; font-weight: 700; margin: 4px 0 2px; color: var(--text); }
    .text-accent { color: var(--accent-dim); }
    .stat-foot { font-size: 11px; color: var(--text3); }

    /* Section Cards */
    .sections-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }
    @media (max-width: 900px) {
      .sections-grid { grid-template-columns: 1fr; }
    }
    .section-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }
    .section-title { font-size: 15px; font-weight: 600; }
    .section-link { font-size: 12px; color: var(--accent); font-weight: 500; }
    .section-link:hover { text-decoration: underline; }

    /* Goals Rollup */
    .goals-list { display: flex; flex-direction: column; gap: 12px; }
    .goal-item {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
    }
    .goal-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
    .goal-badge {
      font-size: 11px;
      font-family: var(--font-mono);
      background: var(--bg3);
      color: var(--accent);
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 600;
    }
    .goal-outcome { font-weight: 600; font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .goal-pct { font-size: 12px; font-weight: 700; color: var(--accent-dim); }
    .goal-criterion { font-size: 12px; color: var(--text2); margin-bottom: 8px; line-height: 1.35; }
    .progress-bar-bg { height: 6px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s ease; }

    /* Jobs Feed */
    .jobs-list { display: flex; flex-direction: column; gap: 8px; }
    .job-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      padding: 8px 12px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    .job-id { font-family: var(--font-mono); font-size: 11px; color: var(--text3); }
    .agent-chip {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
      background: var(--bg3);
      color: var(--text2);
    }
    .agent-codex { background: rgba(16,163,127,0.15); color: #10a37f; }
    .agent-agy { background: rgba(66,133,244,0.15); color: #4285f4; }
    .agent-claude { background: rgba(13,158,135,0.15); color: #0d9e87; }
    .agent-grok { background: rgba(255,255,255,0.1); color: var(--text); }
    .job-desc { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
    .status-chip { font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
    .status-chip.running { background: rgba(13,158,135,0.15); color: var(--accent-dim); }
    .status-chip.pr-open { background: rgba(59,130,246,0.15); color: #60a5fa; }
    .status-chip.done { background: rgba(34,197,94,0.15); color: #22c55e; }
    .status-chip.failed { background: rgba(239,68,68,0.15); color: #ef4444; }
    .status-chip.noop { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .status-chip.circuit-breaker { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
    .job-link { font-size: 11px; color: var(--accent); font-weight: 600; }
    .job-link:hover { text-decoration: underline; }

    /* Category Shortcuts Grid */
    .shortcuts-section { margin-top: 12px; }
    .shortcuts-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; }
    .shortcuts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }
    .cat-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      display: flex;
      flex-direction: column;
    }
    .cat-card-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--accent);
      margin-bottom: 12px;
    }
    .cat-card-links { display: flex; flex-direction: column; gap: 8px; }
    .cat-link {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 6px;
      background: var(--bg);
      border: 1px solid var(--border);
      font-size: 12px;
      color: var(--text);
      transition: all 0.15s ease;
    }
    .cat-link:hover {
      border-color: var(--accent);
      color: var(--accent);
      transform: translateX(2px);
    }
    .link-icon { font-size: 13px; width: 16px; text-align: center; }

    .empty-hint {
      text-align: center;
      padding: 24px 16px;
      color: var(--text3);
      font-size: 12px;
      background: var(--bg);
      border-radius: 6px;
      border: 1px dashed var(--border);
    }
    """

    snapshot = json.dumps(hud).replace("<", "\\u003c")
    inspection_html = """
        <div id="sentinel-panel" class="sentinel-panel" hidden>
          <div class="section-title">Sentinel inspection</div>
          <div id="sentinel-panel-body"></div>
        </div>
        <script type="application/json" id="sentinel-snapshot">""" + snapshot + """</script>
        <script>
        (function () {
          const snapshotNode = document.getElementById('sentinel-snapshot');
          function readHud() {
            try {
              const parsed = JSON.parse(snapshotNode ? snapshotNode.textContent : '{}');
              if (parsed && parsed.groups) return parsed;
            } catch (err) {}
            return {groups: [], acked: [], active_count: 0, acked_count: 0};
          }
          function memberAt(index) {
            const current = readHud();
            const all = [];
            (current.groups || []).concat(current.acked || []).forEach(function (group) {
              (group.members || []).forEach(function (member) { all.push(member); });
            });
            return all[index];
          }
          function renderPanel(alert) {
            const panel = document.getElementById('sentinel-panel');
            const body = document.getElementById('sentinel-panel-body');
            if (!panel || !body || !alert) return;
            body.textContent = '';
            [
              ['severity', alert.severity],
              ['code', alert.pattern],
              ['message', alert.message],
              ['first seen', alert.first_seen],
              ['last seen', alert.last_seen],
              ['occurrences', String(alert.occurrences == null ? '' : alert.occurrences)],
              ['active/resolved', alert.resolved ? 'resolved' : 'active'],
              ['raw', alert.raw_line]
            ].forEach(function (pair) {
              const row = document.createElement('div');
              row.textContent = pair[0] + ': ' + (pair[1] || '');
              body.appendChild(row);
            });
            panel.hidden = false;
          }
          function groupFor(code, section) {
            const current = readHud();
            const groups = section === 'acked' ? (current.acked || []) : (current.groups || []);
            return groups.find(function (group) {
              return String(group.code || '') === String(code || '');
            });
          }
          function identityFor(member, code) {
            const severity = String(member && member.severity || 'INFO').trim().toUpperCase();
            const identityCode = String(code || '').trim().toUpperCase() === 'UNPARSED' ? '' : String(code || '').trim().toUpperCase();
            return [severity === 'WARNING' ? 'WARN' : severity, identityCode, String(member && member.message || '').trim().replace(/\\s+/g, ' ')];
          }
          function briefFor(group, member) {
            const members = member ? [member] : (group.members || []).slice(0, 20);
            const jobIds = [];
            const agents = [];
            members.forEach(function (item) {
              const text = String(item.message || '') + ' ' + String(item.raw_line || '');
              (text.match(/\\bjob-[0-9a-f]+\\b/gi) || []).forEach(function (jobId) {
                if (!jobIds.includes(jobId) && jobIds.length < 20) jobIds.push(jobId);
              });
              const agentMatch = String(item.raw_line || '').match(/Agent ['"]([^'"]+)['"] version changed:/);
              if (agentMatch && !agents.includes(agentMatch[1]) && agents.length < 20) agents.push(agentMatch[1]);
            });
            return {
              slug: slug,
              code: group.code || '',
              severity: member ? (member.severity || group.severity || '') : (group.severity || ''),
              count: member ? 1 : (group.count || 0),
              first_seen: member ? (member.first_seen || member.ts || '') : (group.first_seen || ''),
              last_seen: member ? (member.last_seen || member.ts || '') : (group.last_seen || ''),
              sample_messages: members.map(function (item) { return item.message || ''; }).slice(0, 20),
              identities: members.map(function (item) { return identityFor(item, group.code); }).slice(0, 20),
              job_ids: jobIds,
              agents: agents
            };
          }
          const parts = location.pathname.split('/').filter(Boolean);
          const slug = parts[0] === 'w' ? parts[1] : '';
          async function postSentinel(route, payload) {
            const options = {
              method: 'POST',
              headers: window.vizorAuthHeaders({'Content-Type': 'application/json'}),
              body: JSON.stringify(payload)
            };
            const response = route === 'issue'
              ? await fetch('api/sentinel/issue', options)
              : await fetch('api/sentinel/ack', options);
            if (!response.ok) throw new Error('sentinel write failed');
            location.reload();
          }
          document.addEventListener('click', function (event) {
            const button = event.target.closest('[data-sentinel-action]');
            if (!button) return;
            event.preventDefault();
            const action = button.getAttribute('data-sentinel-action');
            const scope = button.getAttribute('data-sentinel-scope');
            const code = button.getAttribute('data-sentinel-code');
            const section = button.getAttribute('data-sentinel-section');
            const group = groupFor(code, section);
            const indexValue = button.getAttribute('data-alert-index');
            const member = indexValue === null ? null : memberAt(Number(indexValue));
            if (!group) return;
            if (action === 'inspect') {
              if (member) renderPanel(member);
              else renderPanel({severity: group.severity, pattern: group.code, message: (group.members || []).slice(0, 5).map(function (item) { return item.message || ''; }).join('; '), first_seen: group.first_seen, last_seen: group.last_seen, occurrences: group.count, resolved: false, raw_line: ''});
              return;
            }
            if (action === 'investigate') {
              navigator.clipboard.writeText(JSON.stringify(briefFor(group, member), null, 2));
              return;
            }
            const payload = {scope: scope, code: code};
            if (scope === 'occurrence' && member) payload.identity = identityFor(member, code);
            postSentinel(action === 'issue' ? 'issue' : 'ack', payload).catch(function () {});
          });
          const streamUrl = slug ? ('/w/' + slug + '/api/daemon/stream') : '/api/daemon/stream';
          if (typeof EventSource === 'undefined') return;
          try {
            const source = new EventSource(streamUrl);
            source.addEventListener('heartbeat', function (message) {
              const chip = document.getElementById('vizor-heartbeat');
              if (!chip) return;
              try {
                const beat = JSON.parse(message.data);
                chip.textContent = 'Vizor heartbeat: ' + (beat.status || 'unknown');
              } catch (err) {}
            });
            source.addEventListener('sentinel', function (message) {
              const list = document.querySelector('.alerts-list');
              let payload;
              try { payload = JSON.parse(message.data); } catch (err) { return; }
              const hud = payload.groups ? payload : {groups: [], acked: [], active_count: 0, acked_count: 0};
              if (snapshotNode) {
                snapshotNode.textContent = JSON.stringify(hud).replace(/</g, '\\\\u003c');
              }
              const title = document.querySelector('.alerts-title');
              if (title) title.textContent = 'Active Sentinel ' + 'Alerts (' + (hud.active_count || 0) + ')';
              if (!list) return;
              list.textContent = '';
              let alertIndex = 0;
              function appendMembers(parent, group, section) {
                (group.members || []).forEach(function (alert) {
                  const wrap = document.createElement('div');
                  wrap.className = 'sentinel-member';
                  const row = document.createElement('div');
                  const sev = String(alert.severity || 'WARNING').toUpperCase();
                  row.className = 'alert-item ' + ((sev === 'CRITICAL' || sev === 'CRIT') ? 'sev-crit' : 'sev-warn');
                  const currentIndex = alertIndex;
                  alertIndex += 1;
                  row.textContent = (alert.severity || '') + ' ' + (alert.pattern || '') + ' ' + (alert.message || '');
                  wrap.appendChild(row);
                  appendActions(wrap, 'occurrence', group.code || '', currentIndex, section);
                  parent.appendChild(wrap);
                });
              }
              function appendActions(parent, scope, code, index, section) {
                const actions = document.createElement('div');
                actions.className = 'sentinel-actions';
                [['inspect', 'Inspect'], ['ignore', 'Ignore'], ['issue', 'Raise issue'], ['investigate', 'Investigate']].forEach(function (pair) {
                  const button = document.createElement('button');
                  button.type = 'button';
                  button.textContent = pair[1];
                  button.setAttribute('data-sentinel-action', pair[0]);
                  button.setAttribute('data-sentinel-scope', scope);
                  button.setAttribute('data-sentinel-code', code);
                  button.setAttribute('data-sentinel-section', section);
                  if (index !== null && index !== undefined) button.setAttribute('data-alert-index', String(index));
                  actions.appendChild(button);
                  });
                parent.appendChild(actions);
              }
              (hud.groups || []).forEach(function (group) {
                const details = document.createElement('details');
                details.className = 'sentinel-group';
                details.setAttribute('data-sentinel-group', group.code || '');
                if (!group.collapsed) details.open = true;
                const summary = document.createElement('summary');
                summary.textContent = (group.severity || '') + ' ' + (group.code || '') + ' ' + String(group.count || 0);
                appendActions(summary, 'pattern', group.code || '', null, 'active');
                details.appendChild(summary);
                appendMembers(details, group, 'active');
                list.appendChild(details);
              });
              const acked = document.createElement('details');
              acked.className = 'sentinel-acked';
              const ackedSummary = document.createElement('summary');
              ackedSummary.textContent = 'Acked (' + (hud.acked_count || 0) + ')';
              acked.appendChild(ackedSummary);
              (hud.acked || []).forEach(function (group) {
                const details = document.createElement('details');
                details.className = 'sentinel-group';
                details.setAttribute('data-sentinel-group', group.code || '');
                if (!group.collapsed) details.open = true;
                const summary = document.createElement('summary');
                summary.textContent = (group.severity || '') + ' ' + (group.code || '');
                appendActions(summary, 'pattern', group.code || '', null, 'acked');
                details.appendChild(summary);
                appendMembers(details, group, 'acked');
                acked.appendChild(details);
              });
              list.appendChild(acked);
            });
            source.onerror = function () {};
          } catch (err) {}
        })();
        </script>
    """

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <title>{html.escape(workspace_name)} — Workspace Overview</title>
  <style>{style}</style>
</head>
<body>
  <div class="overview-container">
    <div class="overview-header">
      <div>
        <h1 class="overview-title">{html.escape(workspace_name)}</h1>
        <div class="overview-sub">Workspace Overview & Operational Health</div>
      </div>
      <div class="overview-meta">
        <span class="status-pill">● Active</span>
        <span id="vizor-heartbeat" class="status-pill">Vizor heartbeat: unknown</span>
        <span class="meta-time">Updated {html.escape(updated_at)}</span>
      </div>
    </div>

    {alerts_html}
    {inspection_html}

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Active Goals</div>
        <div class="stat-value">{active_goals_count}</div>
        <div class="stat-foot">Sovereign GOVERNS goals</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Open Stories</div>
        <div class="stat-value">{open_stories_count}</div>
        <div class="stat-foot">Ready & in-flight tasks</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Jobs Running</div>
        <div class="stat-value text-accent">{running_jobs_count}</div>
        <div class="stat-foot">Autonomous dispatches</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Burn (7d)</div>
        <div class="stat-value">${total_burn:.2f}</div>
        <div class="stat-foot">Fleet AI spend</div>
      </div>
    </div>

    <div class="sections-grid">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Goal Progress Rollup</div>
          <a href="gantt.html" class="section-link" data-viz-view="gantt" data-viz-cat="STATUS" data-viz-label="Gantt">View in Gantt →</a>
        </div>
        <div class="goals-list">
          {goals_html}
        </div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Recent / Active Dispatches</div>
          <a href="observatory.html" class="section-link" data-viz-view="observatory" data-viz-cat="TELEMETRY" data-viz-label="Observatory">Observatory →</a>
        </div>
        <div class="jobs-list">
          {jobs_html}
        </div>
      </div>
    </div>

    <div class="shortcuts-section">
      <div class="shortcuts-title">Jump to a View</div>
      <div class="shortcuts-grid">
        <div class="cat-card">
          <div class="cat-card-header">STATUS</div>
          <div class="cat-card-links">
            <a href="board.html" class="cat-link" data-viz-view="board" data-viz-cat="STATUS" data-viz-label="Board"><span class="link-icon">▦</span> Board</a>
            <a href="gantt.html" class="cat-link" data-viz-view="gantt" data-viz-cat="STATUS" data-viz-label="Gantt"><span class="link-icon">📅</span> Gantt</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">TOPOLOGIES</div>
          <div class="cat-card-links">
            <a href="tube.html" class="cat-link" data-viz-view="tube" data-viz-cat="TOPOLOGIES" data-viz-label="Architect Map"><span class="link-icon">🚇</span> Architect Map</a>
            <a href="infra.html" class="cat-link" data-viz-view="infra" data-viz-cat="TOPOLOGIES" data-viz-label="Infra View"><span class="link-icon">⚙️</span> Infra View</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">PROJECTIONS</div>
          <div class="cat-card-links">
            <a href="product.html" class="cat-link" data-viz-view="product" data-viz-cat="PROJECTIONS" data-viz-label="Product View"><span class="link-icon">🗺</span> Product View</a>
            <a href="logical.html" class="cat-link" data-viz-view="logical" data-viz-cat="PROJECTIONS" data-viz-label="Logical View"><span class="link-icon">🧩</span> Logical View</a>
            <a href="world.html" class="cat-link" data-viz-view="world" data-viz-cat="PROJECTIONS" data-viz-label="World View"><span class="link-icon">🌐</span> World View</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">TELEMETRY</div>
          <div class="cat-card-links">
            <a href="effort.html" class="cat-link" data-viz-view="effort" data-viz-cat="TELEMETRY" data-viz-label="Effort & Cost"><span class="link-icon">💰</span> Effort & Cost</a>
            <a href="efficiency.html" class="cat-link" data-viz-view="efficiency" data-viz-cat="TELEMETRY" data-viz-label="Efficiency"><span class="link-icon">📊</span> Efficiency</a>
            <a href="observatory.html" class="cat-link" data-viz-view="observatory" data-viz-cat="TELEMETRY" data-viz-label="Observatory"><span class="link-icon">◉</span> Observatory</a>
            <a href="roles.html" class="cat-link" data-viz-view="roles" data-viz-cat="TELEMETRY" data-viz-label="Agent Roles"><span class="link-icon">🤖</span> Agent Roles</a>
          </div>
        </div>
      </div>
    </div>
  </div>
  {_live_js(port)}
  {nav.iframe_nav_script()}
</body>
</html>"""

