"""Small render helpers shared by the effort canvas."""
import html
import json
def _viz_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _fmt_usd(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def _fmt_pct(value: float) -> str:
    try:
        return f"{float(value):.0f}%"
    except Exception:
        return "0%"


def _svg_text(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _stage_color(key: str) -> str:
    stage = (key or "").strip().lower()
    return {
        "goal": "#7b8cff",
        "open": "#60a5fa",
        "visualize": "#f39c6b",
        "execute": "#1a9e5c",
        "release": "#0d9e87",
        "notify": "#fbbf24",
        "sustain": "#888888",
    }.get(stage, "#0d9e87")

