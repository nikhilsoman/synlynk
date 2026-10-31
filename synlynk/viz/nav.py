"""Workspace-relative Vizor navigation. No site-root /tube.html. No /timeline.html."""

from __future__ import annotations

# view_id -> (filename, chrome category, chrome label)
VIEW_CATALOG = {
    "overview": ("overview.html", "", "Overview"),
    "board": ("board.html", "STATUS", "Board"),
    "gantt": ("gantt.html", "STATUS", "Gantt"),
    "activity": ("activity.html", "Personal", "Activity Stream"),
    "tube": ("tube.html", "TOPOLOGIES", "Architect Map"),
    "infra": ("infra.html", "TOPOLOGIES", "Infra View"),
    "product": ("product.html", "PROJECTIONS", "Product View"),
    "logical": ("logical.html", "PROJECTIONS", "Logical View"),
    "world": ("world.html", "PROJECTIONS", "World View"),
    "effort": ("effort.html", "TELEMETRY", "Effort & Cost"),
    "efficiency": ("efficiency.html", "TELEMETRY", "Efficiency"),
    "observatory": ("observatory.html", "TELEMETRY", "Observatory"),
    "roles": ("roles.html", "TELEMETRY", "Agent Roles"),
    "graphify": ("graphify.html", "TOPOLOGIES", "Graphify"),
}

_ALIASES = {"timeline": "gantt"}

_SWITCHER = (
    ("tube", "Architect Map"),
    ("logical", "Logical Engine"),
    ("product", "Product Journeys"),
    ("infra", "Infra Topology"),
    ("world", "Ecosystem Radar"),
    ("board", "Board"),
    ("gantt", "Timeline"),
)


def workspace_view_href(view_id: str) -> tuple[str, str]:
    canonical = _ALIASES.get(view_id, view_id)
    if canonical not in VIEW_CATALOG:
        raise KeyError(view_id)
    filename, _cat, _label = VIEW_CATALOG[canonical]
    return filename, canonical


def switcher_html(active: str) -> str:
    parts = ['<nav class="view-nav">']
    for view_id, label in _SWITCHER:
        href, canonical = workspace_view_href(view_id)
        cls = "nav-btn active" if canonical == active else "nav-btn"
        cat = VIEW_CATALOG[canonical][1]
        chrome_label = VIEW_CATALOG[canonical][2]
        parts.append(
            f'<a href="{href}" class="{cls}" data-viz-view="{canonical}" '
            f'data-viz-cat="{cat}" data-viz-label="{chrome_label}">{label}</a>'
        )
    parts.append("</nav>")
    return "\n".join(parts)


def iframe_nav_script() -> str:
    return """<script>
(function () {
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-viz-view]');
    if (!a) return;
    var viewId = a.getAttribute('data-viz-view');
    var href = a.getAttribute('href');
    var cat = a.getAttribute('data-viz-cat') || '';
    var label = a.getAttribute('data-viz-label') || '';
    if (window.parent && window.parent !== window && typeof window.parent.setView === 'function') {
      e.preventDefault();
      window.parent.setView(viewId, href, cat, label);
      return;
    }
    e.preventDefault();
    window.location.href = 'index.html?view=' + encodeURIComponent(viewId);
  }, true);
})();
</script>"""
