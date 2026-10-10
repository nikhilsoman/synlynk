"""Harness efficiency canvas."""
import html
import json
from typing import Tuple
from synlynk.viz.chrome import _live_js
def generate_efficiency_html(data: dict, port: int) -> str:
    import html
    import json
    import math

    def get_capability_level(cycle_cap: dict, agent: str, cycle: str) -> str:
        c_key = cycle.lower()
        a_key = agent.lower()
        if c_key in cycle_cap and isinstance(cycle_cap[c_key], dict):
            sub = cycle_cap[c_key]
            if a_key in sub:
                return sub[a_key]
            for k, v in sub.items():
                if k.lower() == a_key:
                    return v
        if a_key in cycle_cap and isinstance(cycle_cap[a_key], dict):
            sub = cycle_cap[a_key]
            if c_key in sub:
                return sub[c_key]
            for k, v in sub.items():
                if k.lower() == c_key:
                    return v
        return "none"

    def _money(value) -> str:
        try:
            return f"${float(value):.2f}"
        except Exception:
            return "$0.00"

    def _rate(value) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0

    def _avatar(name: str) -> Tuple[str, str]:
        key = (name or "").strip().lower()
        if key.startswith("claude"):
            return "C", "claude"
        if key.startswith("agy"):
            return "A", "agy"
        if key.startswith("codex"):
            return "Co", "codex"
        if key.startswith("grok"):
            return "G", "grok"
        if not name:
            return "?", "unknown"
        return (name.strip()[:2] if len(name.strip()) > 1 else name.strip()[0]).upper(), "unknown"

    def _dot_class(rate: float, alert_count: int) -> str:
        if rate >= 0.9 and alert_count == 0:
            return "dot-good"
        if 0.7 <= rate < 0.9 or alert_count == 1:
            return "dot-warn"
        return "dot-bad"

    def _bar_class(rate: float) -> str:
        if rate >= 0.9:
            return "bar-good"
        if rate >= 0.7:
            return "bar-warn"
        return "bar-bad"

    def _pattern_class(pattern: str) -> str:
        mapping = {
            "FLATLINE": "pattern-flatline",
            "SUCCESS_LOOP": "pattern-success-loop",
            "COST_SPIKE": "pattern-cost-spike",
            "QUOTA_EXHAUSTED": "pattern-quota-exhausted",
        }
        return mapping.get((pattern or "").upper(), "pattern-unknown")

    agents = data.get("agents") or {}
    telemetry = data.get("telemetry") or {}
    sentinel_alerts = telemetry.get("sentinel_alerts") or []
    recent_runs = telemetry.get("recent") or []
    json_data = json.dumps(data, ensure_ascii=False)

    try:
        from synlynk.status import TIER1_CAPACITY
    except ImportError:
        TIER1_CAPACITY = {
            "claude": {"ctx_window_tokens": 200_000, "read_budget_tokens": 750_000, "write_budget_tokens": 32_000, "tool_budget_count": 200},
            "agy": {"ctx_window_tokens": 1_000_000, "read_budget_tokens": 900_000, "write_budget_tokens": 65_000, "tool_budget_count": 500},
            "codex": {"ctx_window_tokens": 128_000, "read_budget_tokens": 110_000, "write_budget_tokens": 16_000, "tool_budget_count": 128},
            "grok": {"ctx_window_tokens": 131_000, "read_budget_tokens": 115_000, "write_budget_tokens": 16_000, "tool_budget_count": 100},
        }

    eco = data.get("ecosystem", {})
    is_placeholder = not bool(eco)

    if is_placeholder:
        efficiency = 1.0
        fleet_attached = 0
        fleet_total = 0
        dispatch_mode = "—"
        agents_data = {}
        cycle_cap = {
            "goal": {"claude": "full", "agy": "partial", "codex": "none", "grok": "none"},
            "open": {"claude": "full", "agy": "none", "codex": "none", "grok": "none"},
            "visualize": {"claude": "full", "agy": "partial", "codex": "full", "grok": "partial"},
            "execute": {"claude": "full", "agy": "partial", "codex": "partial", "grok": "none"},
            "release": {"claude": "full", "agy": "partial", "codex": "partial", "grok": "partial"},
            "notify": {"claude": "full", "agy": "partial", "codex": "none", "grok": "partial"},
            "sustain": {"claude": "full", "agy": "partial", "codex": "partial", "grok": "partial"},
        }
        capacity = TIER1_CAPACITY
        sentinels_active = 0
    else:
        efficiency = eco.get("headless_efficiency", 1.0)
        fleet = eco.get("fleet", {})
        fleet_attached = fleet.get("attached", 0)
        fleet_total = fleet.get("total", 0)
        dispatch_mode = fleet.get("dispatch_mode", "—")
        agents_data = eco.get("agents", {})
        cycle_cap = eco.get("cycle_capability", {})
        capacity = eco.get("capacity", {}) or TIER1_CAPACITY
        sentinels_active = eco.get("sentinels_active", 0)

    style_content = """
    :root {
      --bg:#f6f8fa; --bg2:#ffffff; --bg3:#eaeef2;
      --border:#d1d5db; --border2:#e8ebee;
      --text:#1f2328; --text2:#57606a; --text3:#8b949e;
      --accent:#0d9e87; --accent-bg:#e6f7f4; --accent-dim:#c0ede6;
      --shadow:0 2px 12px rgba(0,0,0,.10);

      --ag-claude-bg:#e6f7f4; --ag-claude-bd:#0d9e87; --ag-claude-tx:#0d9e87;
      --ag-agy-bg:#e8f0fe; --ag-agy-bd:#4285f4; --ag-agy-tx:#1a56c7;
      --ag-codex-bg:#e6f4f0; --ag-codex-bd:#10a37f; --ag-codex-tx:#0b7a60;
      --ag-grok-bg:#f0f0f0; --ag-grok-bd:#666; --ag-grok-tx:#333;
      --ag-muse-bg:#fdf2f8; --ag-muse-bd:#db2777; --ag-muse-tx:#9d174d;
      --ok:#16a34a; --warn:#d97706; --bad:#dc2626;
    }
    [data-theme="dark"] {
      --bg:#0d1117; --bg2:#161b22; --bg3:#0d1117;
      --border:#30363d; --border2:#30363d;
      --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
      --accent:#58a6ff; --accent-bg:#0d2137; --accent-dim:#0a3050;
      --shadow:0 2px 20px rgba(0,0,0,.5);

      --ag-claude-bg:#0d2a2a; --ag-claude-bd:#3de0c0; --ag-claude-tx:#3de0c0;
      --ag-agy-bg:#0d1a3a; --ag-agy-bd:#4285f4; --ag-agy-tx:#4285f4;
      --ag-codex-bg:#0a1f18; --ag-codex-bd:#10a37f; --ag-codex-tx:#10a37f;
      --ag-grok-bg:#1a1a1a; --ag-grok-bd:#e0e0e0; --ag-grok-tx:#e0e0e0;
      --ag-muse-bg:#2e081d; --ag-muse-bd:#f472b6; --ag-muse-tx:#f472b6;
      --ok:#3fb950; --warn:#f0883e; --bad:#f85149;
    }
    * { box-sizing:border-box; margin:0; padding:0; }
    body {
      font-family:'SF Mono','JetBrains Mono',monospace;
      background: radial-gradient(circle at top, rgba(13,158,135,.10), transparent 36%), var(--bg);
      color:var(--text);
      font-size:13px;
      transition:background .2s,color .2s;
      min-height:100vh;
      padding:20px;
    }
    .page {
      max-width:1280px;
      margin:0 auto;
      display:flex;
      flex-direction:column;
      gap:18px;
    }
    .hero {
      display:flex;
      align-items:end;
      justify-content:space-between;
      gap:16px;
    }
    .title {
      font-size:20px;
      font-weight:800;
      letter-spacing:-0.02em;
    }
    .subtitle {
      margin-top:4px;
      color:var(--text2);
      font-size:12px;
      line-height:1.4;
    }
    .meta-chip {
      align-self:flex-start;
      padding:5px 10px;
      border-radius:999px;
      border:1px solid var(--border);
      background:var(--bg2);
      color:var(--text2);
      font-size:11px;
      white-space:nowrap;
    }
    .section {
      background:var(--bg2);
      border:1px solid var(--border);
      border-radius:16px;
      box-shadow:var(--shadow);
      overflow:hidden;
    }
    .section-head {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      padding:14px 16px;
      border-bottom:1px solid var(--border2);
      background:linear-gradient(180deg, rgba(13,158,135,.06), transparent);
    }
    .section-title {
      font-size:13px;
      font-weight:800;
      letter-spacing:.02em;
      text-transform:uppercase;
      color:var(--text);
    }
    .section-note {
      color:var(--text3);
      font-size:11px;
    }
    .cards-grid {
      display:grid;
      grid-template-columns:repeat(2, minmax(0, 1fr));
      gap:14px;
      padding:16px;
    }
    .cards-grid.single {
      grid-template-columns:1fr;
    }
    .agent-card {
      position:relative;
      background:linear-gradient(180deg, rgba(255,255,255,.75), rgba(255,255,255,0));
      border:1px solid var(--border2);
      border-radius:14px;
      padding:16px 16px 14px;
      min-height:168px;
      overflow:hidden;
    }
    [data-theme="dark"] .agent-card {
      background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,0));
    }
    .agent-card::before {
      content:'';
      position:absolute;
      inset:0;
      border-radius:14px;
      pointer-events:none;
      background:linear-gradient(135deg, rgba(13,158,135,.08), transparent 42%);
      opacity:.7;
    }
    .traffic-dot {
      position:absolute;
      top:14px;
      right:14px;
      width:12px;
      height:12px;
      border-radius:50%;
      border:2px solid var(--bg2);
      box-shadow:0 0 0 1px rgba(0,0,0,.06);
      z-index:1;
    }
    .dot-good { background:var(--ok); }
    .dot-warn { background:var(--warn); }
    .dot-bad { background:var(--bad); }
    .agent-head {
      display:flex;
      align-items:center;
      gap:12px;
      position:relative;
      z-index:1;
      margin-bottom:12px;
      padding-right:20px;
    }
    .avatar-badge {
      width:34px;
      height:34px;
      border-radius:50%;
      display:flex;
      align-items:center;
      justify-content:center;
      font-weight:800;
      font-size:11px;
      letter-spacing:.02em;
      color:#fff;
      flex-shrink:0;
    }
    .agent-claude { background:linear-gradient(135deg, var(--ag-claude-bd), var(--ag-claude-tx)); }
    .agent-agy { background:linear-gradient(135deg, var(--ag-agy-bd), var(--ag-agy-tx)); }
    .agent-codex { background:linear-gradient(135deg, var(--ag-codex-bd), var(--ag-codex-tx)); }
    .agent-grok { background:linear-gradient(135deg, var(--ag-grok-bd), var(--ag-grok-tx)); }
    .agent-muse { background:linear-gradient(135deg, var(--ag-muse-bd), var(--ag-muse-tx)); }
    .agent-unknown { background:linear-gradient(135deg, var(--accent), #0b7a60); }
    .agent-name {
      font-size:15px;
      font-weight:800;
      color:var(--text);
      line-height:1.2;
    }
    .agent-metrics {
      display:flex;
      flex-direction:column;
      gap:10px;
      position:relative;
      z-index:1;
    }
    .agent-counts {
      color:var(--text2);
      font-size:12px;
    }
    .agent-spend {
      font-size:12px;
      color:var(--text);
      font-weight:700;
    }
    .alert-count {
      color:var(--bad);
      font-size:12px;
      font-weight:700;
    }
    .rate-wrap {
      margin-top:2px;
    }
    .rate-label-row {
      display:flex;
      align-items:center;
      justify-content:space-between;
      margin-bottom:6px;
      font-size:11px;
      color:var(--text2);
    }
    .rate-track {
      width:100%;
      height:10px;
      background:var(--bg3);
      border:1px solid var(--border);
      border-radius:999px;
      overflow:hidden;
    }
    .rate-fill {
      height:100%;
      border-radius:999px;
    }
    .bar-good { background:linear-gradient(90deg, #22c55e, #16a34a); }
    .bar-warn { background:linear-gradient(90deg, #f59e0b, #d97706); }
    .bar-bad { background:linear-gradient(90deg, #ef4444, #dc2626); }
    .timeline-list {
      display:flex;
      flex-direction:column;
      gap:10px;
      padding:14px 16px 16px;
      max-height:280px;
      overflow:auto;
    }
    .timeline-row {
      display:grid;
      grid-template-columns:160px minmax(0, 1fr) auto;
      gap:10px;
      align-items:center;
      padding:10px 12px;
      border:1px solid var(--border2);
      border-radius:12px;
      background:var(--bg);
    }
    .timeline-ts {
      color:var(--text2);
      font-size:11px;
      white-space:nowrap;
    }
    .badge {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      padding:4px 8px;
      border-radius:999px;
      font-size:10px;
      font-weight:800;
      letter-spacing:.02em;
      white-space:nowrap;
    }
    .pattern-flatline { background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; }
    .pattern-success-loop { background:#ffedd5; color:#c2410c; border:1px solid #fed7aa; }
    .pattern-cost-spike { background:#fef3c7; color:#a16207; border:1px solid #fde68a; }
    .pattern-quota-exhausted { background:#e5e7eb; color:#4b5563; border:1px solid #d1d5db; }
    .pattern-unknown { background:var(--bg3); color:var(--text2); border:1px solid var(--border); }
    [data-theme="dark"] .pattern-flatline { background:#2a1212; color:#fca5a5; border-color:#4c1d1d; }
    [data-theme="dark"] .pattern-success-loop { background:#2a1b12; color:#fdba74; border-color:#4a2a16; }
    [data-theme="dark"] .pattern-cost-spike { background:#2a2412; color:#fde68a; border-color:#4a4016; }
    [data-theme="dark"] .pattern-quota-exhausted { background:#1f2937; color:#d1d5db; border-color:#374151; }
    .resolved-badge {
      background:rgba(22,163,74,.12);
      color:var(--ok);
      border:1px solid rgba(22,163,74,.22);
    }
    .timeline-row .resolved-badge {
      justify-self:end;
    }
    .runs-table-wrap {
      padding:0 16px 16px;
    }
    table.runs-table {
      width:100%;
      border-collapse:separate;
      border-spacing:0;
      overflow:hidden;
      border:1px solid var(--border2);
      border-radius:12px;
      background:var(--bg);
    }
    .runs-table th,
    .runs-table td {
      padding:11px 12px;
      border-bottom:1px solid var(--border2);
      text-align:left;
      font-size:12px;
      vertical-align:middle;
    }
    .runs-table th {
      color:var(--text2);
      font-size:10px;
      text-transform:uppercase;
      letter-spacing:.08em;
      background:var(--bg3);
    }
    .runs-table tr:last-child td {
      border-bottom:none;
    }
    .run-agent {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .run-duration,
    .run-cost {
      white-space:nowrap;
      font-variant-numeric:tabular-nums;
    }
    .exit-ok {
      color:var(--ok);
      font-weight:800;
      white-space:nowrap;
    }
    .exit-bad {
      color:var(--bad);
      font-weight:800;
      white-space:nowrap;
    }
    .empty-state {
      min-height:60vh;
      display:flex;
      align-items:center;
      justify-content:center;
      text-align:center;
      padding:24px;
      font-size:14px;
      font-weight:700;
      color:var(--text2);
    }
    .empty-state span {
      display:inline-block;
      max-width:560px;
      line-height:1.6;
      border:1px solid var(--border);
      background:var(--bg2);
      border-radius:16px;
      padding:18px 20px;
      box-shadow:var(--shadow);
    }
    @media (max-width: 900px) {
      .cards-grid,
      .cards-grid.single {
        grid-template-columns:1fr;
      }
      .timeline-row {
        grid-template-columns:1fr;
      }
      .timeline-row .resolved-badge {
        justify-self:start;
      }
      .runs-table-wrap {
        overflow:auto;
      }
      .runs-table {
        min-width:680px;
      }
    }
    .number-font {
      font-family: system-ui, monospace;
    }
    .label-font {
      font-family: sans-serif;
    }
    .eco-top-row {
      display: flex;
      flex-wrap: wrap;
      gap: 18px;
      margin-bottom: 18px;
    }
    .eco-banner-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      flex: 1;
      min-width: 280px;
      box-shadow: var(--shadow);
      position: relative;
    }
    .efficiency-num {
      font-size: 48px;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
      margin-bottom: 8px;
    }
    .efficiency-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .efficiency-sub {
      font-size: 11px;
      color: var(--text2);
      margin-top: 4px;
    }
    .fleet-header-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      flex: 1;
      min-width: 280px;
      box-shadow: var(--shadow);
    }
    .fleet-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 16px;
    }
    .fleet-status-row {
      display: flex;
      gap: 12px;
    }
    .fleet-pill {
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid var(--border);
      background: var(--bg3);
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .dispatch-mode-pill {
      color: var(--accent);
      border-color: var(--accent);
    }
    .attached-badge {
      color: var(--ok);
      border-color: var(--ok);
    }
    .eco-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-bottom: 18px;
    }
    .cap-table, .matrix-table {
      width: 100%;
      border-collapse: collapse;
    }
    .cap-table th, .cap-table td,
    .matrix-table th, .matrix-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border2);
      vertical-align: middle;
    }
    .cap-table th, .matrix-table th {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text2);
      font-weight: 700;
      background: var(--bg3);
      padding: 8px 12px;
    }
    .cap-table td, .matrix-table td {
      background: var(--bg2);
    }
    .cap-agent-name, .matrix-agent-name {
      font-size: 13px;
      font-weight: 700;
      color: var(--text);
    }
    .cap-cell {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .cap-num {
      font-size: 12px;
      font-weight: 700;
      color: var(--text);
    }
    .cap-bar-track {
      width: 100%;
      height: 4px;
      background: var(--bg3);
      border-radius: 2px;
      overflow: hidden;
      border: 1px solid var(--border);
    }
    .cap-bar-fill {
      height: 100%;
      background: var(--accent);
      border-radius: 2px;
      transition: width 0.3s ease;
    }
    .matrix-table th, .matrix-table td {
      text-align: center;
    }
    .matrix-table th:first-child, .matrix-table td:first-child {
      text-align: left;
    }
    .matrix-circle-container {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .skeleton-text {
      color: var(--text3) !important;
    }
    .skeleton-fill {
      background: var(--border) !important;
      opacity: 0.5;
    }
    .skeleton-pulse::after {
      content: "";
      position: absolute;
      top: 0; right: 0; bottom: 0; left: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
      animation: skeleton-pulse-anim 1.5s infinite;
      pointer-events: none;
    }
    @keyframes skeleton-pulse-anim {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    .rwt-section { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
    .rwt-row { display: flex; align-items: center; gap: 6px; }
    .rwt-label { font-size: 10px; font-weight: 700; color: var(--text3); width: 10px; }
    .rwt-track { flex: 1; height: 5px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
    .rwt-fill { height: 100%; background: var(--accent); border-radius: 3px; }
    .rwt-fill.rwt-write { background: var(--ag-agy-bd); }
    .rwt-fill.rwt-tool { background: var(--ag-codex-bd); }
    .rwt-val { font-size: 10px; color: var(--text3); width: 36px; text-align: right; }
    .cycle-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .cycle-table th, .cycle-table td { padding: 7px 12px; border-bottom: 1px solid var(--border2); text-align: center; }
    .cycle-table th { font-weight: 700; color: var(--text2); background: var(--bg3); }
    .cycle-table td:first-child { text-align: left; }
    .cap-full { background: rgba(22,163,74,.12); color: var(--ok); font-weight: 600; border-radius: 4px; padding: 1px 6px; }
    .cap-partial { background: rgba(217,119,6,.12); color: var(--warn); border-radius: 4px; padding: 1px 6px; }
    .cap-none { color: var(--text3); }
    """

    cycles_list = ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]
    cards_html = []
    for name, stats in agents.items():
        rate = _rate(stats.get("success_rate"))
        alerts = int(stats.get("alert_count") or 0)
        initials, avatar_class = _avatar(name)
        dot_class = _dot_class(rate, alerts)
        bar_class = _bar_class(rate)
        alert_html = f'<div class="alert-count">{alerts} sentinel alerts</div>' if alerts > 0 else ""

        # Get capacity data safely
        clean_name = (name or "").strip().lower()
        agent_cap = capacity.get(clean_name) or capacity.get(name) or TIER1_CAPACITY.get(clean_name) or {}
        baseline_cap = TIER1_CAPACITY.get(clean_name) or {}
        if not baseline_cap:
            baseline_cap = {"read_budget_tokens": 1, "write_budget_tokens": 1, "tool_budget_count": 1}

        read_budget = agent_cap.get("read_budget_tokens", 0)
        write_budget = agent_cap.get("write_budget_tokens", 0)
        tool_budget = agent_cap.get("tool_budget_count", 0)

        base_read = baseline_cap.get("read_budget_tokens", 1) or 1
        base_write = baseline_cap.get("write_budget_tokens", 1) or 1
        base_tool = baseline_cap.get("tool_budget_count", 1) or 1

        if is_placeholder:
            read_pct = 100.0
            write_pct = 100.0
            tool_pct = 100.0
            read_budget_k = base_read // 1000
            write_budget_k = base_write // 1000
            tool_budget = base_tool
        else:
            read_pct = (read_budget / base_read) * 100 if base_read else 0.0
            write_pct = (write_budget / base_write) * 100 if base_write else 0.0
            tool_pct = (tool_budget / base_tool) * 100 if base_tool else 0.0
            read_budget_k = read_budget // 1000
            write_budget_k = write_budget // 1000

        rwt_html = f"""
            <div class="rwt-section">
              <div class="rwt-row">
                <span class="rwt-label">R</span>
                <div class="rwt-track"><div class="rwt-fill" style="width:{read_pct:.0f}%"></div></div>
                <span class="rwt-val">{read_budget_k}k</span>
              </div>
              <div class="rwt-row">
                <span class="rwt-label">W</span>
                <div class="rwt-track"><div class="rwt-fill rwt-write" style="width:{write_pct:.0f}%"></div></div>
                <span class="rwt-val">{write_budget_k}k</span>
              </div>
              <div class="rwt-row">
                <span class="rwt-label">T</span>
                <div class="rwt-track"><div class="rwt-fill rwt-tool" style="width:{tool_pct:.0f}%"></div></div>
                <span class="rwt-val">{tool_budget}</span>
              </div>
            </div>
        """.strip()

        # Radar heptagon SVG
        angles = [270, 321.4, 12.9, 64.3, 115.7, 167.1, 218.6]
        cycles_order = cycles_list

        outer_points = []
        for deg in angles:
            rad = math.radians(deg)
            x = 40 + 32 * math.cos(rad)
            y = 40 + 32 * math.sin(rad)
            outer_points.append(f"{x:.1f},{y:.1f}")
        outer_points_str = " ".join(outer_points)

        score_points = []
        for i, cycle in enumerate(cycles_order):
            support = get_capability_level(cycle_cap, clean_name, cycle)
            if support == "full":
                score = 1.0
            elif support == "partial":
                score = 0.5
            else:
                score = 0.0
            deg = angles[i]
            rad = math.radians(deg)
            r = 32 * score
            x = 40 + r * math.cos(rad)
            y = 40 + r * math.sin(rad)
            score_points.append((x, y))
        score_points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in score_points)

        axis_lines_html = []
        for i in range(len(cycles_list)):
            rad = math.radians(angles[i])
            x_outer = 40 + 32 * math.cos(rad)
            y_outer = 40 + 32 * math.sin(rad)
            axis_lines_html.append(
                f'<line x1="40" y1="40" x2="{x_outer:.1f}" y2="{y_outer:.1f}" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="2,2" />'
            )
        axis_lines_str = "\n".join(axis_lines_html)

        dots_html = []
        for x, y in score_points:
            dots_html.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="var(--ag-{avatar_class}-bd, var(--accent))" />')
        dots_str = "\n".join(dots_html)

        radar_svg_html = f"""
            <div class="radar-container" style="display: flex; justify-content: center; margin-top: 10px;">
              <svg width="80" height="80" viewBox="0 0 80 80" style="overflow: visible;">
                <polygon points="{outer_points_str}" fill="none" stroke="var(--border)" stroke-width="1" />
                {axis_lines_str}
                <polygon points="{score_points_str}" fill="var(--ag-{avatar_class}-bd, var(--accent))" fill-opacity="0.4" stroke="var(--ag-{avatar_class}-bd, var(--accent))" stroke-width="1.5" />
                {dots_str}
              </svg>
            </div>
        """.strip()

        cards_html.append(
            f"""
        <div class="agent-card">
          <span class="traffic-dot {dot_class}"></span>
          <div class="agent-head">
            <div class="avatar-badge agent-{avatar_class}">{html.escape(initials)}</div>
            <div class="agent-name">{html.escape(str(name))}</div>
          </div>
          <div class="agent-metrics">
            <div class="agent-counts">{int(stats.get("tasks_done") or 0)} done · {int(stats.get("tasks_active") or 0)} active</div>
            <div class="agent-spend">Total spend: {_money(stats.get("total_usd"))}</div>
            {alert_html}
            <div class="rate-wrap">
              <div class="rate-label-row">
                <span>Success rate</span>
                <span>{rate * 100:.0f}%</span>
              </div>
              <div class="rate-track">
                <div class="rate-fill {bar_class}" style="width:{rate * 100:.0f}%"></div>
              </div>
            </div>
            {rwt_html}
            {radar_svg_html}
          </div>
        </div>
            """.rstrip()
        )

    if not cards_html:
        cards_html.append(
            '<div style="grid-column: 1 / -1; text-align: center; color: var(--text3); padding: 32px 16px;" class="label-font">'
            'No agent telemetry recorded yet. Run synlynk exec or synlynk launch to populate.</div>'
        )

    sorted_alerts = sorted(
        [alert for alert in sentinel_alerts if isinstance(alert, dict)],
        key=lambda alert: str(alert.get("ts") or ""),
        reverse=True,
    )
    timeline_html = []
    for alert in sorted_alerts:
        pattern = str(alert.get("pattern") or "")
        resolved = bool(alert.get("resolved"))
        resolved_html = '<span class="badge resolved-badge">[RESOLVED] ✓</span>' if resolved else ""
        timeline_html.append(
            f"""
        <div class="timeline-row">
          <div class="timeline-ts">{html.escape(str(alert.get("ts") or ""))}</div>
          <span class="badge {_pattern_class(pattern)}">{html.escape(pattern or "UNKNOWN")}</span>
          {resolved_html}
        </div>
            """.rstrip()
        )
    if not timeline_html:
        timeline_html.append(
            """
        <div class="timeline-row">
          <div class="timeline-ts">No sentinel alerts</div>
          <span class="badge pattern-unknown">-</span>
          <span class="badge resolved-badge" style="visibility:hidden;">[RESOLVED] ✓</span>
        </div>
            """.rstrip()
        )

    recent_runs = telemetry.get("recent") or []
    recent_rows = list((recent_runs or [])[-10:])[::-1]
    runs_html = []
    for row in recent_rows:
        agent_name = str(row.get("agent") or "")
        initials, avatar_class = _avatar(agent_name)
        exit_code = int(row.get("exit_code") or 0)
        duration = float(row.get("duration_s") or 0.0)
        runs_html.append(
            f"""
        <tr>
          <td>{html.escape(str(row.get("ts") or ""))}</td>
          <td>
            <div class="run-agent">
              <span class="avatar-badge agent-{avatar_class}">{html.escape(initials)}</span>
              <span>{html.escape(agent_name or "unknown")}</span>
            </div>
          </td>
          <td class="run-duration">{duration:.0f}s</td>
          <td class="run-cost">{_money(row.get("cost_usd"))}</td>
          <td class="{ 'exit-ok' if exit_code == 0 else 'exit-bad' }">{'✓' if exit_code == 0 else '✗'} {exit_code}</td>
        </tr>
            """.rstrip()
        )
    if not runs_html:
        runs_html.append(
            """
        <tr>
          <td colspan="5" style="color:var(--text2);">No recent runs</td>
        </tr>
            """.rstrip()
        )

    # 1. Headless efficiency banner HTML
    efficiency_val = efficiency
    if is_placeholder:
        eff_banner_html = f"""
      <div class="eco-banner-card skeleton-pulse">
        <div class="efficiency-num number-font skeleton-text">—x</div>
        <div class="efficiency-title label-font">headless efficiency</div>
        <div class="efficiency-sub label-font">vs. interactive baseline (no probe run yet)</div>
      </div>
        """
    else:
        eff_banner_html = f"""
      <div class="eco-banner-card">
        <div class="efficiency-num number-font">{efficiency_val:.1f}x</div>
        <div class="efficiency-title label-font">headless efficiency</div>
        <div class="efficiency-sub label-font">vs. interactive baseline</div>
      </div>
        """

    # 2. Fleet header HTML
    if is_placeholder:
        fleet_html = f"""
      <div class="fleet-header-card skeleton-pulse">
        <div class="fleet-title label-font">Fleet Status</div>
        <div class="fleet-status-row">
          <span class="fleet-pill label-font skeleton-text" style="border-color: var(--border); color: var(--text3);">Mode: —</span>
          <span class="fleet-pill label-font skeleton-text" style="border-color: var(--border); color: var(--text3);">— attached</span>
        </div>
      </div>
        """
    else:
        fleet_html = f"""
      <div class="fleet-header-card">
        <div class="fleet-title label-font">Fleet Status</div>
        <div class="fleet-status-row">
          <span class="fleet-pill dispatch-mode-pill label-font">Mode: <span class="number-font">{html.escape(str(dispatch_mode))}</span></span>
          <span class="fleet-pill attached-badge label-font"><span class="number-font">{int(fleet_attached)}/{int(fleet_total)}</span> attached</span>
        </div>
      </div>
        """

    eco_top_html = f"""
    <div class="eco-top-row">
      {eff_banner_html}
      {fleet_html}
    </div>
    """

    # 3. Capacity table HTML
    agents_list = ["claude", "agy", "codex", "grok"]
    
    def _to_k(tokens) -> str:
        try:
            return f"{int(tokens) // 1000}K"
        except Exception:
            return "0K"

    max_r = max((capacity.get(a, {}).get("read_budget_tokens", 0) for a in agents_list), default=1)
    max_w = max((capacity.get(a, {}).get("write_budget_tokens", 0) for a in agents_list), default=1)
    max_t = max((capacity.get(a, {}).get("tool_budget_count", 0) for a in agents_list), default=1)
    max_ctx = max((capacity.get(a, {}).get("ctx_window_tokens", 0) for a in agents_list), default=1)

    capacity_rows = []
    for agent in agents_list:
        cap = capacity.get(agent, {})
        r_val = cap.get("read_budget_tokens", 0)
        w_val = cap.get("write_budget_tokens", 0)
        t_val = cap.get("tool_budget_count", 0)
        ctx_val = cap.get("ctx_window_tokens", 0)

        r_pct = (r_val / max_r) * 100 if max_r else 0
        w_pct = (w_val / max_w) * 100 if max_w else 0
        t_pct = (t_val / max_t) * 100 if max_t else 0
        ctx_pct = (ctx_val / max_ctx) * 100 if max_ctx else 0

        if is_placeholder:
            r_str, w_str, t_str, ctx_str = "—", "—", "—", "—"
            r_pct, w_pct, t_pct, ctx_pct = 0, 0, 0, 0
            text_cls = "skeleton-text"
            fill_cls = "skeleton-fill"
        else:
            r_str = _to_k(r_val)
            w_str = _to_k(w_val)
            t_str = str(t_val)
            ctx_str = _to_k(ctx_val)
            text_cls = ""
            fill_cls = ""

        capacity_rows.append(f"""
        <tr>
          <td class="cap-agent-name label-font">{html.escape(agent)}</td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{r_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {r_pct:.1f}%"></div>
              </div>
            </div>
          </td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{w_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {w_pct:.1f}%"></div>
              </div>
            </div>
          </td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{t_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {t_pct:.1f}%"></div>
              </div>
            </div>
          </td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{ctx_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {ctx_pct:.1f}%"></div>
              </div>
            </div>
          </td>
        </tr>
        """)

    capacity_table_html = f"""
    <section class="section">
      <div class="section-head">
        <div class="section-title label-font">Capacity Table</div>
        <div class="section-note label-font">Relative to max value in each column.</div>
      </div>
      <div style="padding: 16px; overflow-x: auto;">
        <table class="cap-table">
          <thead>
            <tr>
              <th class="label-font">Agent</th>
              <th class="label-font">R (Read)</th>
              <th class="label-font">W (Write)</th>
              <th class="label-font">T (Tools)</th>
              <th class="label-font">CTX (Context)</th>
            </tr>
          </thead>
          <tbody>
            {''.join(capacity_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """

    # 4. Cycle matrix HTML
    def _matrix_svg(support: str) -> str:
        s = (support or "").strip().lower()
        if s == "full":
            return (
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<circle cx="8" cy="8" r="7" fill="#3fb950" stroke="#3fb950" stroke-width="2"/>'
                '</svg>'
            )
        elif s == "partial":
            return (
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<circle cx="8" cy="8" r="7" stroke="#f0883e" stroke-width="2"/>'
                '<path d="M8 1a7 7 0 0 1 0 14V1z" fill="#f0883e"/>'
                '</svg>'
            )
        else:
            return (
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<circle cx="8" cy="8" r="7" stroke="#30363d" stroke-width="2"/>'
                '</svg>'
            )

    matrix_rows = []
    for agent in agents_list:
        tds = []
        for cycle in cycles_list:
            support = get_capability_level(cycle_cap, agent, cycle)
            tds.append(f"""
          <td>
            <div class="matrix-circle-container">
              {_matrix_svg(support)}
            </div>
          </td>
            """)
        matrix_rows.append(f"""
        <tr>
          <td class="matrix-agent-name label-font">{html.escape(agent)}</td>
          {''.join(tds)}
        </tr>
        """)

    matrix_table_html = f"""
    <section class="section">
      <div class="section-head">
        <div class="section-title label-font">Cycle Capability Matrix</div>
        <div class="section-note label-font">Support mapping across GOVERNS cycles.</div>
      </div>
      <div style="padding: 16px; overflow-x: auto;">
        <table class="matrix-table">
          <thead>
            <tr>
              <th class="label-font">Agent</th>
              <th class="label-font">Goal</th>
              <th class="label-font">Open</th>
              <th class="label-font">Visualize</th>
              <th class="label-font">Execute</th>
              <th class="label-font">Release</th>
              <th class="label-font">Notify</th>
              <th class="label-font">Sustain</th>
            </tr>
          </thead>
          <tbody>
            {''.join(matrix_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """

    eco_grid_html = f"""
    <div class="eco-grid">
      {capacity_table_html}
      {matrix_table_html}
    </div>
    """

    # 5. Cycle capability matrix section
    matrix_rows_new = []
    cycle_emojis = {
        "goal": "🎯 Goal",
        "open": "📂 Open",
        "visualize": "🧭 Visualize",
        "execute": "⚙️ Execute",
        "release": "🚀 Release",
        "notify": "✉️ Notify",
        "sustain": "🔧 Sustain",
    }
    matrix_agents = ["claude", "agy", "codex", "grok"]
    for cycle in cycles_list:
        row_tds = [f"<td>{cycle_emojis.get(cycle, cycle)}</td>"]
        for agent in matrix_agents:
            support = get_capability_level(cycle_cap, agent, cycle)
            support_lower = support.lower()
            row_tds.append(f'<td><span class="cap-{support_lower}">{support_lower}</span></td>')
        matrix_rows_new.append(f"<tr>{''.join(row_tds)}</tr>")
    new_matrix_table_html = f"""
    <section class="section">
      <div class="section-head">
        <div class="section-title">Cycle Capability Matrix</div>
        <div class="section-note">full / partial / none per agent per 7-stage GOVERNS cycle.</div>
      </div>
      <table class="cycle-table">
        <thead><tr><th>Cycle</th><th>Claude</th><th>Agy</th><th>Codex</th><th>Grok</th></tr></thead>
        <tbody>
          {"".join(matrix_rows_new)}
        </tbody>
      </table>
    </section>
    """

    grid_class = "cards-grid single" if len(agents) == 1 else "cards-grid"
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Efficiency Report Card</title>
<script>window.VIZOR_DATA = {json_data};</script>
<script>
  (function() {{
    const theme = localStorage.getItem('vizor-theme') || 'system';
    let actualTheme = theme;
    if (theme === 'system') {{
      actualTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }}
    document.documentElement.setAttribute('data-theme', actualTheme);
  }})();
</script>
<style>{style_content}</style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <div class="title">Efficiency Report Card</div>
        <div class="subtitle">Per-agent throughput, spend, success rate, and sentinel health.</div>
      </div>
      <div class="meta-chip">{html.escape(str(data.get("workspace", {}).get("name", "workspace")))} · {len(agents)} agent{'' if len(agents) == 1 else 's'}</div>
    </div>

    {eco_top_html}

    {eco_grid_html}

    <section class="section">
      <div class="section-head">
        <div class="section-title">Agent Cards</div>
        <div class="section-note">Traffic-light status uses success rate and sentinel alert count.</div>
      </div>
      <div class="{grid_class}">
        {''.join(cards_html)}
      </div>
    </section>

    {new_matrix_table_html}

    <section class="section">
      <div class="section-head">
        <div class="section-title">Sentinel Timeline</div>
        <div class="section-note">Newest first.</div>
      </div>
      <div class="timeline-list">
        {''.join(timeline_html)}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div class="section-title">Recent Runs</div>
        <div class="section-note">Last 10 telemetry rows.</div>
      </div>
      <div class="runs-table-wrap">
        <table class="runs-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Agent</th>
              <th>Duration</th>
              <th>Cost</th>
              <th>Exit</th>
            </tr>
          </thead>
          <tbody>
            {''.join(runs_html)}
          </tbody>
        </table>
      </div>
    </section>
  </div>
  {_live_js(port)}
</body>
</html>"""
    return html_out

