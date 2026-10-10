"""Effort and cost canvas."""
from synlynk.viz.chrome import _live_js
from synlynk.viz.format import _fmt_pct, _fmt_usd, _stage_color, _svg_text, _viz_json
def generate_effort_html(data: dict, port: int) -> str:
    costs = data.get("costs") or {}
    dreams = list(data.get("dreams") or [])
    by_agent = dict(costs.get("by_agent") or {})
    by_stage = dict(costs.get("by_stage") or {})
    total_usd = float(costs.get("total_usd") or 0.0)
    total_usd_estimated = float(costs.get("total_usd_estimated") or 0.0)

    def _bucket_total(bucket) -> float:
        if isinstance(bucket, dict):
            return float(bucket.get("actual", 0.0)) + float(bucket.get("estimated", 0.0))
        return float(bucket or 0.0)

    def _bucket_estimated(bucket) -> float:
        if isinstance(bucket, dict):
            return float(bucket.get("estimated", 0.0))
        return 0.0

    data_json = _viz_json(data)

    if total_usd == 0:
        return f"""<!doctype html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Effort & Cost</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --bg-accent: linear-gradient(180deg, #ffffff 0%, #eef3fb 100%);
      --panel: rgba(255,255,255,0.92);
      --panel-border: rgba(15, 23, 42, 0.10);
      --text: #142033;
      --muted: #64748b;
      --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      --card: #ffffff;
      --card-border: rgba(15, 23, 42, 0.08);
      --teal: #0d9e87;
      --blue: #3b7dd8;
      --green: #1a9e5c;
      --gray: #888888;
      --red: #e05;
      --stage-goal: #7b8cff;
      --stage-open: #60a5fa;
      --stage-visualize: #f39c6b;
      --stage-execute: #1a9e5c;
      --stage-release: #0d9e87;
      --stage-notify: #fbbf24;
      --stage-sustain: #888888;
    }}
    [data-theme="dark"] {{
      color-scheme: dark;
      --bg: #0b1220;
      --bg-accent: linear-gradient(180deg, #111a2e 0%, #0b1220 100%);
      --panel: rgba(15, 23, 42, 0.92);
      --panel-border: rgba(148, 163, 184, 0.18);
      --text: #e5edf8;
      --muted: #94a3b8;
      --shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
      --card: rgba(15, 23, 42, 0.92);
      --card-border: rgba(148, 163, 184, 0.16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg-accent);
    }}
    .shell {{ display: grid; place-items: center; min-height: 100vh; padding: 32px; }}
    .empty {{
      width: min(860px, 100%);
      border: 1px solid var(--panel-border);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 36px;
    }}
    h1 {{ margin: 0 0 12px; font-size: 30px; letter-spacing: -0.03em; }}
    p {{ margin: 0; color: var(--muted); font-size: 16px; line-height: 1.6; }}
  </style>
</head>
<body>
  <script>window.VIZOR_DATA = {data_json}; function checkManifest() {{ return window.VIZOR_DATA; }}</script>
  <header style="height:44px;padding:0 20px;display:flex;align-items:center;gap:20px;background:#fff;border-bottom:1px solid rgba(15,23,42,.10);flex-shrink:0;font-size:13px;font-family:inherit">
    <span style="font-weight:700;color:#142033">💰 Effort & Cost</span>
    <span style="color:#64748b">Spend by goal, agent, and stage</span>
  </header>
  <main class="shell">
    <section class="empty">
      <h1>Effort & Cost</h1>
      <p>No cost data yet. Cost entries are recorded automatically on each synlynk exec run.</p>
    </section>
  </main>
  {_live_js(port)}
</body>
</html>"""

    dreams_sorted = sorted(dreams, key=lambda d: float(d.get("cost_total") or 0.0), reverse=True)
    max_dream_cost = max([float(d.get("cost_total") or 0.0) for d in dreams_sorted] + [0.0]) or 1.0
    dreams_in_flight = sum(1 for dream in dreams_sorted if (dream.get("status") or "") == "active")
    over_budget = sum(
        1
        for dream in dreams_sorted
        if dream.get("cost_est") is not None and float(dream.get("cost_total") or 0.0) > float(dream.get("cost_est") or 0.0)
    )
    top_agent = max(by_agent.items(), key=lambda item: _bucket_total(item[1]))[0] if by_agent else "—"

    def build_summary_cards() -> str:
        est_pct = (total_usd_estimated / total_usd * 100.0) if total_usd else 0.0
        cards = [
            ("Total Spend", _fmt_usd(total_usd)),
            ("ACTIVE GOALS", str(dreams_in_flight)),
            ("Over Budget", str(over_budget)),
            ("Top Agent", _svg_text(top_agent)),
            ("~Estimated", f"{_fmt_usd(total_usd_estimated)} ({_fmt_pct(est_pct)})"),
        ]
        return "".join(
            f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>'
            for label, value in cards
        )

    def render_bar_chart(rows, title, value_key, color_fn, label_fn, empty_text, max_value=None, estimated_key=None) -> str:
        rows = list(rows)
        max_value = max_value or max([float(row.get(value_key) or 0.0) for row in rows] + [0.0]) or 1.0
        chart_rows = []
        if rows:
            for row in rows:
                value = float(row.get(value_key) or 0.0)
                estimated_val = float(row.get(estimated_key) or 0.0) if estimated_key else 0.0
                actual_val = max(value - estimated_val, 0.0)
                bar_color = color_fn(row, value)
                label = label_fn(row, value)
                actual_width = (actual_val / max_value) * 100 if max_value else 0.0
                estimated_width = (estimated_val / max_value) * 100 if max_value else 0.0
                bar_html = (
                    f'<div class="effort-bar-fill" style="width:{actual_width:.2f}%;background:{bar_color};"></div>'
                )
                if estimated_val > 0:
                    bar_html += (
                        f'<div class="effort-bar-fill effort-bar-estimated" '
                        f'style="width:{estimated_width:.2f}%;background:{bar_color};"></div>'
                    )
                chart_rows.append(
                    f'<div class="effort-row">'
                    f'<div class="effort-label">{_svg_text(row.get("label") or row.get("name") or row.get("key") or "")}</div>'
                    f'<div class="effort-bar-track" aria-hidden="true">{bar_html}</div>'
                    f'<div class="effort-cost">{_svg_text(label)}</div>'
                    f'</div>'
                )
        else:
            chart_rows.append(f'<div class="effort-empty">{_svg_text(empty_text)}</div>')

        return f"""
        <section class="panel">
          <div class="panel-head">
            <h2>{_svg_text(title)}</h2>
          </div>
          <div class="effort-chart" aria-label="{_svg_text(title)}">{''.join(chart_rows)}</div>
        </section>
        """

    dream_rows = [
        {
            "label": dream.get("name") or dream.get("id") or "Unnamed goal",
            "name": dream.get("name") or dream.get("id") or "Unnamed goal",
            "value": float(dream.get("cost_total") or 0.0),
            "estimated": float(dream.get("cost_total_estimated") or 0.0),
            "cost_est": dream.get("cost_est"),
            "cost_total": float(dream.get("cost_total") or 0.0),
        }
        for dream in dreams_sorted
    ]

    agent_rows = []
    for agent, bucket in sorted(by_agent.items(), key=lambda item: _bucket_total(item[1]), reverse=True):
        total = _bucket_total(bucket)
        if total <= 0:
            continue
        agent_rows.append({
            "label": agent, "name": agent, "value": total, "spend": total,
            "estimated": _bucket_estimated(bucket),
        })

    stage_rows = []
    for stage, bucket in sorted(by_stage.items(), key=lambda item: _bucket_total(item[1]), reverse=True):
        total = _bucket_total(bucket)
        if total <= 0:
            continue
        stage_rows.append({
            "label": stage, "name": stage, "value": total, "spend": total,
            "estimated": _bucket_estimated(bucket),
        })

    def dream_color(row, value):
        est = row.get("cost_est")
        if est is not None and value > float(est or 0.0):
            return "#e05"
        return "#0d9e87"

    def dream_label(row, value):
        est = row.get("cost_est")
        prov_estimated = row.get("estimated") or 0.0
        base = _fmt_usd(value)
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        if est is None:
            return base
        return f"{base} / est {_fmt_usd(est)}"

    def agent_color(row, value):
        agent = (row.get("label") or "").strip().lower()
        return {
            "claude": "#0d9e87",
            "agy": "#3b7dd8",
            "codex": "#1a9e5c",
            "grok": "#888888",
        }.get(agent, "#0d9e87")

    def agent_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        base = f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
        prov_estimated = row.get("estimated") or 0.0
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        return base

    def stage_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        base = f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
        prov_estimated = row.get("estimated") or 0.0
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        return base

    def stage_color(row, value):
        return _stage_color(row.get("label") or row.get("name") or "")

    return f"""<!doctype html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Effort & Cost</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --bg-accent: linear-gradient(180deg, #ffffff 0%, #eef3fb 100%);
      --panel: rgba(255,255,255,0.92);
      --panel-border: rgba(15, 23, 42, 0.10);
      --text: #142033;
      --muted: #64748b;
      --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      --card: #ffffff;
      --card-border: rgba(15, 23, 42, 0.08);
      --teal: #0d9e87;
      --blue: #3b7dd8;
      --green: #1a9e5c;
      --gray: #888888;
      --red: #e05;
      --stage-goal: #7b8cff;
      --stage-open: #60a5fa;
      --stage-visualize: #f39c6b;
      --stage-execute: #1a9e5c;
      --stage-release: #0d9e87;
      --stage-notify: #fbbf24;
      --stage-sustain: #888888;
    }}
    [data-theme="dark"] {{
      color-scheme: dark;
      --bg: #0b1220;
      --bg-accent: linear-gradient(180deg, #111a2e 0%, #0b1220 100%);
      --panel: rgba(15, 23, 42, 0.92);
      --panel-border: rgba(148, 163, 184, 0.18);
      --text: #e5edf8;
      --muted: #94a3b8;
      --shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
      --card: rgba(15, 23, 42, 0.92);
      --card-border: rgba(148, 163, 184, 0.16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg-accent);
    }}
    .wrap {{
      width: min(1320px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 24px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 30px;
      letter-spacing: -0.04em;
    }}
    .subtle {{ color: var(--muted); margin-top: 6px; font-size: 14px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .stat, .panel {{
      border: 1px solid var(--card-border);
      background: var(--card);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .stat {{
      padding: 18px 18px 16px;
      min-height: 102px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .stat span {{ color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .stat strong {{ font-size: 28px; line-height: 1.1; letter-spacing: -0.04em; }}
    .panel {{
      padding: 18px 18px 8px;
      margin-top: 16px;
    }}
    .panel-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 8px;
    }}
    .panel h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.02em;
    }}
    .effort-chart {{ display: grid; gap: 12px; }}
    .effort-row {{
      display: grid;
      grid-template-columns: minmax(180px, 1.2fr) minmax(160px, 2fr) minmax(120px, .8fr);
      align-items: center;
      gap: 14px;
      min-width: 0;
    }}
    .effort-label, .effort-cost {{ min-width: 0; overflow-wrap: anywhere; }}
    .effort-label {{ color: var(--text); font-size: 12px; line-height: 1.35; }}
    .effort-cost {{ color: var(--muted); font-size: 12px; text-align: right; }}
    .effort-bar-track {{
      display: flex;
      min-width: 0;
      height: 18px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--bg);
    }}
    .effort-bar-fill {{ height: 100%; flex: 0 0 auto; min-width: 0; }}
    .effort-bar-estimated {{ opacity: .4; }}
    .effort-empty {{ color: var(--muted); font-size: 14px; padding: 12px 0; }}
    @media (max-width: 980px) {{
      .summary {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 700px) {{
      .wrap {{ width: min(100vw - 20px, 100%); }}
      .summary {{ grid-template-columns: 1fr; }}
      .hero {{ flex-direction: column; align-items: start; }}
      .effort-row {{ grid-template-columns: 1fr; gap: 6px; }}
      .effort-cost {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <script>window.VIZOR_DATA = {data_json}; function checkManifest() {{ return window.VIZOR_DATA; }}</script>
  <main class="wrap">
    <header class="hero">
      <div>
        <h1>Effort & Cost</h1>
        <div class="subtle">Workspace spend, goal overruns, and agent allocation at a glance. Faded segments indicate estimated (non-structural) cost.</div>
      </div>
    </header>
    <section class="summary">{build_summary_cards()}</section>
    {render_bar_chart(
        dream_rows,
        "By Goal / Milestone",
        "value",
        dream_color,
        dream_label,
        "No goals found",
        max_dream_cost,
        estimated_key="estimated",
    )}
    {render_bar_chart(
        agent_rows,
        "By Agent",
        "value",
        agent_color,
        agent_label,
        "No agent spend yet",
        estimated_key="estimated",
    )}
    {render_bar_chart(
        stage_rows,
        "By Stage",
        "value",
        stage_color,
        stage_label,
        "No stage spend yet",
        estimated_key="estimated",
    )}
  </main>
  {_live_js(port)}
</body>
</html>"""

