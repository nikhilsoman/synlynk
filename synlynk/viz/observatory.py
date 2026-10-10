"""Job observatory canvas."""
import html
import json
from synlynk.observatory import write_observatory_snapshot
def generate_observatory_html(snapshot: dict) -> str:
    snapshot = snapshot or {}
    write_observatory_snapshot(snapshot)

    def _money(value) -> str:
        try:
            return f"${float(value or 0.0):.2f}"
        except Exception:
            return "—"

    def _tokens(input_tokens, output_tokens) -> str:
        try:
            total = int(input_tokens or 0) + int(output_tokens or 0)
        except Exception:
            return "—"
        return f"{total/1000:.1f}k" if total >= 1000 else str(total)

    def _age(seconds) -> str:
        try:
            seconds = int(seconds or 0)
        except Exception:
            return "—"
        minutes, secs = divmod(max(0, seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        if minutes:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"

    def _render_job(job: dict) -> str:
        stage = html.escape(str(job.get("stage") or job.get("status") or "unknown"))
        repo = html.escape(str(job.get("repo") or "unknown"))
        job_id = html.escape(str(job.get("id") or "—"))
        short_id = job_id[-8:] if len(job_id) > 8 else job_id
        agent = html.escape(str(job.get("agent") or "—"))
        return f"""
          <div class="obs-job" data-stage="{stage}" data-repo="{repo}">
            <div class="obs-job-id">{short_id}</div>
            <div class="obs-job-agent">{agent}</div>
            <div class="obs-job-stage">{stage}</div>
            <div class="obs-job-age">{html.escape(_age(job.get("runtime_seconds")))}</div>
            <div class="obs-job-cost">{html.escape(_money(job.get("cost_usd")))}</div>
            <div class="obs-job-tokens">{html.escape(_tokens(job.get("input_tokens"), job.get("output_tokens")))}</div>
          </div>
        """.strip()

    def _render_repo(repo: dict) -> str:
        repo_name = html.escape(str(repo.get("repo") or "unknown"))
        rollups = repo.get("rollups") or {}
        jobs = repo.get("jobs") or []
        job_cards = "\n".join(_render_job(job) for job in jobs)
        if not job_cards:
            job_cards = '<div class="obs-empty">No jobs</div>'
        return f"""
        <section class="obs-repo">
          <header class="obs-repo-header">
            <div>
              <div class="obs-repo-title">{repo_name}</div>
              <div class="obs-repo-meta">{len(jobs)} jobs · {_money(rollups.get("total_cost"))} · {rollups.get("active_count", 0)} active</div>
            </div>
          </header>
          <div class="obs-job-grid">
            <div class="obs-job-head">
              <span>job</span><span>agent</span><span>stage</span><span>age</span><span>cost</span><span>tokens</span>
            </div>
            {job_cards}
          </div>
        </section>
        """.strip()

    def _worktree_model(value) -> tuple:
        if isinstance(value, list):
            items = value
            counts = {"active": 0, "safe": 0, "needs_review": 0, "dirty_orphan": 0}
            for item in items:
                status = str(item.get("status") or item.get("verdict") or "active").lower()
                if status in ("needs-review", "needs_review"):
                    counts["needs_review"] += 1
                elif status == "safe":
                    counts["safe"] += 1
                elif status in ("dirty-artifact", "dirty", "orphan"):
                    counts["dirty_orphan"] += 1
                else:
                    counts["active"] += 1
            return items, counts
        value = value if isinstance(value, dict) else {}
        return value.get("items") or [], {
            "active": int(value.get("active", 0) or 0),
            "safe": int(value.get("safe", 0) or 0),
            "needs_review": int(value.get("needs_review", 0) or 0),
            "dirty_orphan": int(value.get("dirty_orphan", 0) or 0),
        }

    def _worktree_status(item: dict) -> str:
        status = str(item.get("status") or item.get("verdict") or "active").lower()
        if status in ("needs-review", "needs_review"):
            return "needs-review"
        if status == "safe":
            return "safe"
        if status in ("dirty-artifact", "dirty", "orphan"):
            return "dirty-artifact"
        return "active"

    worktree_items, worktree_counts = _worktree_model(snapshot.get("worktrees"))
    worktree_rows = []
    for item in worktree_items:
        status = _worktree_status(item)
        label = {"active": "ACTIVE", "safe": "SAFE", "needs-review": "NEEDS-REVIEW", "dirty-artifact": "DIRTY-ARTIFACT"}[status]
        p_path = html.escape(str(item.get("path") or ""))
        prune_btn = f' <button class="wt-prune" data-path="{p_path}">Prune</button>' if status == "safe" else ""
        worktree_rows.append(
            f'<tr><td><code>{html.escape(str(item.get("branch") or "—"))}</code></td>'
            f'<td class="wt-path">{html.escape(str(item.get("path") or "—"))}</td>'
            f'<td><span class="wt-pill wt-{status}">{label}</span></td>'
            f'<td>{html.escape(str(item.get("reason") or "—"))}</td>'
            f'<td><button class="wt-inspect" data-path="{p_path}">Inspect</button>'
            f'{prune_btn}</td></tr>'
        )
    worktree_html = f'''<!-- Worktree Lifecycle & Fleet Health -->
    <section class="wt-panel" id="worktree-lifecycle">
      <header class="wt-header"><div><div class="wt-kicker">Fleet health</div><h2>Worktree Lifecycle &amp; Fleet Health</h2></div>
        <button class="wt-clean" id="wt-clean">Clean Safe Worktrees</button></header>
      <div class="wt-metrics">
        <div class="wt-metric"><span>Active Working</span><strong>{worktree_counts["active"]}</strong></div>
        <div class="wt-metric wt-safe"><span>Safe to Prune</span><strong>{worktree_counts["safe"]}</strong></div>
        <div class="wt-metric wt-review"><span>Needs Review</span><strong>{worktree_counts["needs_review"]}</strong></div>
        <div class="wt-metric wt-dirty"><span>Dirty / Orphan</span><strong>{worktree_counts["dirty_orphan"]}</strong></div>
      </div>
      <div class="wt-table-wrap"><table class="wt-table"><thead><tr><th>Branch</th><th>Path</th><th>Status</th><th>Reason</th><th></th></tr></thead>
        <tbody>{''.join(worktree_rows) or '<tr><td colspan="5" class="obs-empty">No auxiliary worktrees found.</td></tr>'}</tbody></table></div>
      <div class="wt-result" id="wt-result" aria-live="polite"></div>
    </section>'''

    repos = snapshot.get("repos") or []
    rollups = snapshot.get("rollups") or {}
    repo_cards = "\n".join(_render_repo(repo) for repo in repos)
    if not repo_cards:
        repo_cards = '<div class="obs-empty-state">No live jobs in this workspace.</div>'

    snapshot_json = json.dumps(snapshot).replace("</", "<\\/")
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Observatory</title>
<style>
:root {{
  --bg: #0b1020;
  --panel: rgba(12, 18, 35, 0.82);
  --panel-2: rgba(18, 24, 45, 0.9);
  --line: rgba(255,255,255,0.08);
  --text: #e7edf8;
  --muted: #9aa7bd;
  --accent: #47d7b1;
  --accent-2: #7aa8ff;
  --shadow: 0 24px 80px rgba(0,0,0,.45);
  --running: #47d7b1;
  --queued: #7aa8ff;
  --failed: #ff7a90;
  --done: #9ca3af;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; min-height: 100%; background: radial-gradient(circle at top, #18213d 0%, var(--bg) 44%, #05070f 100%); color: var(--text); font-family: "SF Mono", "JetBrains Mono", monospace; }}
body {{ padding: 24px; }}
.obs-shell {{ max-width: 1400px; margin: 0 auto; }}
.obs-hero {{
  display: flex; justify-content: space-between; align-items: flex-end; gap: 18px;
  margin-bottom: 18px; padding: 18px 20px; border: 1px solid var(--line);
  border-radius: 18px; background: linear-gradient(180deg, rgba(25,34,61,.95), rgba(12,18,35,.88));
  box-shadow: var(--shadow);
}}
.obs-title {{ font-size: 24px; font-weight: 800; letter-spacing: -0.03em; }}
.obs-subtitle {{ margin-top: 6px; color: var(--muted); font-size: 13px; }}
.obs-stats {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }}
.obs-stat {{
  min-width: 120px; padding: 10px 12px; border-radius: 14px;
  background: rgba(255,255,255,0.04); border: 1px solid var(--line);
}}
.obs-stat-label {{ display: block; font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .12em; }}
.obs-stat-value {{ display: block; margin-top: 6px; font-size: 18px; font-weight: 700; }}
.obs-grid {{ display: grid; gap: 16px; }}
.obs-repo {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 18px;
  overflow: hidden; box-shadow: var(--shadow);
}}
.obs-repo-header {{
  display: flex; justify-content: space-between; gap: 12px; align-items: center;
  padding: 16px 18px; background: var(--panel-2); border-bottom: 1px solid var(--line);
}}
.obs-repo-title {{ font-size: 18px; font-weight: 700; }}
.obs-repo-meta {{ margin-top: 4px; color: var(--muted); font-size: 12px; }}
.obs-job-grid {{ padding: 14px 18px 18px; }}
.obs-job-head, .obs-job {{
  display: grid; grid-template-columns: 1.2fr 1fr 1fr .9fr .9fr .9fr; gap: 10px;
  align-items: center;
}}
.obs-job-head {{
  padding: 0 6px 10px; color: var(--muted); font-size: 10px;
  text-transform: uppercase; letter-spacing: .14em;
}}
.obs-job {{
  padding: 10px 6px; border-top: 1px solid rgba(255,255,255,0.05);
  font-size: 13px;
}}
.obs-job:first-of-type {{ border-top: none; }}
.obs-job-id {{ color: var(--accent); font-weight: 700; }}
.obs-job-stage {{
  display: inline-flex; justify-self: start; padding: 4px 9px; border-radius: 999px;
  background: rgba(255,255,255,0.06); color: var(--text); font-size: 11px;
}}
.obs-job[data-stage="running"] .obs-job-stage {{ background: rgba(71, 215, 177, 0.16); color: var(--running); }}
.obs-job[data-stage="queued"] .obs-job-stage {{ background: rgba(122, 168, 255, 0.16); color: var(--queued); }}
.obs-job[data-stage="failed"] .obs-job-stage {{ background: rgba(255, 122, 144, 0.16); color: var(--failed); }}
.obs-job[data-stage="done"] .obs-job-stage {{ background: rgba(156, 163, 175, 0.16); color: var(--done); }}
.obs-job-age, .obs-job-cost, .obs-job-tokens {{ color: var(--muted); }}
.obs-empty-state, .obs-empty {{ padding: 18px 4px; color: var(--muted); }}
.wt-panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; overflow: hidden; box-shadow: var(--shadow); }}
.wt-header {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding:18px; background:var(--panel-2); border-bottom:1px solid var(--line); }}
.wt-header h2 {{ margin:4px 0 0; font-size:18px; }} .wt-kicker {{ color:var(--accent); font-size:10px; text-transform:uppercase; letter-spacing:.14em; }}
.wt-clean, .wt-inspect {{ cursor:pointer; border:1px solid rgba(71,215,177,.35); border-radius:8px; padding:8px 11px; background:rgba(71,215,177,.14); color:var(--accent); font:inherit; font-size:11px; font-weight:700; }}
.wt-metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; padding:16px 18px; }} .wt-metric {{ padding:13px; border:1px solid var(--line); border-radius:12px; background:rgba(255,255,255,.035); }}
.wt-metric span {{ display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.1em; }} .wt-metric strong {{ display:block; margin-top:7px; font-size:24px; }}
.wt-safe strong, .wt-pill.wt-safe {{ color:var(--accent); }} .wt-review strong, .wt-pill.wt-needs-review {{ color:#ffd166; }} .wt-dirty strong, .wt-pill.wt-dirty-artifact {{ color:#ff7a90; }}
.wt-table-wrap {{ overflow:auto; padding:0 18px 14px; }} .wt-table {{ width:100%; border-collapse:collapse; font-size:12px; }} .wt-table th {{ color:var(--muted); font-size:10px; text-align:left; text-transform:uppercase; letter-spacing:.1em; }} .wt-table th, .wt-table td {{ padding:11px 8px; border-top:1px solid rgba(255,255,255,.05); white-space:nowrap; }} .wt-path {{ color:var(--muted); max-width:300px; overflow:hidden; text-overflow:ellipsis; }}
.wt-pill {{ display:inline-flex; padding:4px 8px; border-radius:999px; background:rgba(255,255,255,.07); font-size:10px; font-weight:700; letter-spacing:.04em; }} .wt-result {{ padding:0 18px 14px; color:var(--muted); font-size:12px; }}
@media (max-width: 960px) {{
  body {{ padding: 16px; }}
  .obs-hero {{ flex-direction: column; align-items: flex-start; }}
  .obs-stats {{ justify-content: flex-start; }}
  .obs-job-head, .obs-job {{ grid-template-columns: 1fr 1fr; }}
  .obs-job-head span:nth-child(n+3), .obs-job > *:nth-child(n+3) {{ display: none; }}
  .wt-metrics {{ grid-template-columns:repeat(2,1fr); }} .wt-header {{ align-items:flex-start; flex-direction:column; }}
}}
</style>
</head>
<body>
<div class="obs-shell">
  <header class="obs-hero">
    <div>
      <div class="obs-title">Observatory</div>
      <div class="obs-subtitle">Live job board, refreshed every 10 seconds from <code>observatory-snapshot.json</code>.</div>
    </div>
    <div class="obs-stats" id="obs-stats">
      <div class="obs-stat"><span class="obs-stat-label">Total Cost</span><span class="obs-stat-value">{_money(rollups.get("total_cost"))}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Active</span><span class="obs-stat-value">{rollups.get("active_count", 0)}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Requests</span><span class="obs-stat-value">{rollups.get("total_requests", 0)}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Tokens</span><span class="obs-stat-value">{rollups.get("total_tokens", 0)}</span></div>
    </div>
  </header>
  <div class="obs-grid" id="obs-grid">
    {worktree_html}
    {repo_cards}
  </div>
</div>
<script>
(function() {{
  const snapshotEl = document.getElementById('obs-grid');
  const statsEl = document.getElementById('obs-stats');
  const initialSnapshot = {snapshot_json};

  function esc(value) {{
    return String(value ?? '').replace(/[&<>"]/g, (c) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
  }}

  function money(value) {{
    const n = Number(value || 0);
    return `$${{n.toFixed(2)}}`;
  }}

  function tokens(inputTokens, outputTokens) {{
    const total = Number(inputTokens || 0) + Number(outputTokens || 0);
    return total >= 1000 ? `${{(total / 1000).toFixed(1)}}k` : String(total);
  }}

  function age(seconds) {{
    seconds = Number(seconds || 0);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours) return `${{hours}}h ${{String(mins).padStart(2, '0')}}m`;
    if (minutes) return `${{minutes}}m ${{String(secs).padStart(2, '0')}}s`;
    return `${{secs}}s`;
  }}

  function renderJob(job) {{
    const stage = esc(job.stage || job.status || 'unknown');
    const repo = esc(job.repo || 'unknown');
    const jobId = esc(job.id || '—');
    const shortId = jobId.length > 8 ? jobId.slice(-8) : jobId;
    return `
      <div class="obs-job" data-stage="${{stage}}" data-repo="${{repo}}">
        <div class="obs-job-id">${{shortId}}</div>
        <div class="obs-job-agent">${{esc(job.agent || '—')}}</div>
        <div class="obs-job-stage">${{stage}}</div>
        <div class="obs-job-age">${{age(job.runtime_seconds)}}</div>
        <div class="obs-job-cost">${{money(job.cost_usd)}}</div>
        <div class="obs-job-tokens">${{tokens(job.input_tokens, job.output_tokens)}}</div>
      </div>`;
  }}

  function renderRepo(repo) {{
    const jobs = repo.jobs || [];
    const rollups = repo.rollups || {{}};
    return `
      <section class="obs-repo">
        <header class="obs-repo-header">
          <div>
            <div class="obs-repo-title">${{esc(repo.repo || 'unknown')}}</div>
            <div class="obs-repo-meta">${{jobs.length}} jobs · ${{money(rollups.total_cost)}} · ${{rollups.active_count || 0}} active</div>
          </div>
        </header>
        <div class="obs-job-grid">
          <div class="obs-job-head">
            <span>job</span><span>agent</span><span>stage</span><span>age</span><span>cost</span><span>tokens</span>
          </div>
          ${{jobs.length ? jobs.map(renderJob).join('') : '<div class="obs-empty">No jobs</div>'}}
        </div>
      </section>`;
  }}

  function renderStats(snapshot) {{
    const rollups = snapshot.rollups || {{}};
    statsEl.innerHTML = `
      <div class="obs-stat"><span class="obs-stat-label">Total Cost</span><span class="obs-stat-value">${{money(rollups.total_cost)}}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Active</span><span class="obs-stat-value">${{rollups.active_count || 0}}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Requests</span><span class="obs-stat-value">${{rollups.total_requests || 0}}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Tokens</span><span class="obs-stat-value">${{rollups.total_tokens || 0}}</span></div>
    `;
  }}

  function render(snapshot) {{
    const repos = snapshot.repos || [];
    // Keep the lifecycle panel stable while refreshing the job board.
    const lifecycle = document.getElementById('worktree-lifecycle');
    snapshotEl.innerHTML = (lifecycle ? lifecycle.outerHTML : '') + (repos.length ? repos.map(renderRepo).join('') : '<div class="obs-empty-state">No live jobs in this workspace.</div>');
    renderStats(snapshot);
    const clean = document.getElementById('wt-clean');
    const result = document.getElementById('wt-result');
    if (clean && !clean.dataset.bound) {{
      clean.dataset.bound = '1';
      clean.addEventListener('click', async () => {{
        result.textContent = 'Cleaning safe worktrees…';
        try {{ const response = await fetch('/worktrees/clean', {{ method: 'POST', headers: Object.assign({{'Content-Type':'application/json'}}, window.vizorAuthHeaders ? window.vizorAuthHeaders() : {{}}), body: JSON.stringify({{apply:true}}) }}); const out = await response.json(); result.textContent = out.ok ? `Cleaned ${{out.cleaned_count}} safe worktree(s).` : (out.error || 'Cleanup failed.'); if (out.ok) setTimeout(refresh, 500); }} catch (err) {{ result.textContent = 'Cleanup failed: ' + err.message; }}
      }});
    }}
  }}

  async function refresh() {{
    try {{
      const response = await fetch('observatory-snapshot.json?_=' + Date.now(), {{ cache: 'no-store' }});
      if (!response.ok) return;
      render(await response.json());
    }} catch (err) {{}}
  }}

  window.__OBSERVATORY_SNAPSHOT__ = initialSnapshot;
  render(initialSnapshot);
  setInterval(refresh, 10000);
  refresh();
}})();
</script>
</body>
</html>"""
    return html_out

