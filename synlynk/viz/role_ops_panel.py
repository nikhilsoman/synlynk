"""Generic per-role autonomous-action operations panel (spec §5.4,
docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md).

Keyed by role_slug + the MaintainerActionRegistry's registered actions for
that role, so any future role adopting the same wake-cycle pattern gets this
UI for free, on both Agent Studio (full panel) and the Overview page
(condensed widget via render_condensed_widget_html below).

Renders form controls directly from each action's `filter_schema` (list of
FieldSpec-shaped dicts from synlynk/maintainer_registry.py), per Task 4's own
commitment that this panel is the `filter_schema` consumer. Also surfaces two
pieces of validate-or-fallback state introduced by this plan's own revisions:
a "using built-in defaults" banner (DECIDE panel defect #5, from
load_taxonomy()'s schema_valid/validation_error) and a "why this grouping"
provenance detail per pending proposal (DECIDE panel defect #3, from
select_proposal_target()'s tier_provenance).
"""
import html as html_mod

_FIELD_INPUT_TYPES = {
    "str": "text",
    "int": "number",
    "bool": "checkbox",
    "list[str]": "text",
}


def _field_control_html(field_spec: dict, current_value) -> str:
    """One form control for a FieldSpec-shaped dict, pre-filled with current_value."""
    name = html_mod.escape(str(field_spec.get("name", "")))
    label = html_mod.escape(str(field_spec.get("label", field_spec.get("name", ""))))
    field_type = field_spec.get("type", "str")
    input_type = _FIELD_INPUT_TYPES.get(field_type, "text")

    if field_type == "bool":
        checked = "checked" if current_value else ""
        control = f'<input type="checkbox" name="{name}" {checked}>'
    elif field_type == "list[str]":
        value = ",".join(str(v) for v in (current_value or []))
        control = f'<input type="text" name="{name}" value="{html_mod.escape(value)}" placeholder="comma-separated">'
    else:
        value = html_mod.escape(str(current_value if current_value is not None else ""))
        control = f'<input type="{input_type}" name="{name}" value="{value}">'

    return f'<label class="ops-field"><span class="ops-field-label">{label}</span>{control}</label>'


def _proposal_provenance_html(proposal: dict) -> str:
    provenance = proposal.get("tier_provenance") or []
    title = html_mod.escape(str(proposal.get("title", proposal.get("proposal_id", ""))))
    provenance_html = ", ".join(html_mod.escape(str(t)) for t in provenance) or "no evidence tiers recorded"
    return (
        f'<div class="ops-proposal" data-proposal-id="{html_mod.escape(str(proposal.get("proposal_id", "")))}">'
        f'<span class="ops-proposal-title">{title}</span>'
        f'<span class="ops-proposal-provenance" title="why this grouping">why this grouping: {provenance_html}</span>'
        f'</div>'
    )


def _action_card_html(action: dict) -> str:
    name = html_mod.escape(str(action.get("name", "")))
    enabled = bool(action.get("enabled"))
    mode = html_mod.escape(str(action.get("mode", "dry_run")))
    last_run = html_mod.escape(str(action.get("last_run") or "never"))
    pending_proposals = action.get("pending_proposals") or []
    pending = len(pending_proposals)
    toggle_label = "On" if enabled else "Off"
    low_signal_html = (
        '<span class="ops-low-signal" title="This workspace has little source-code coverage for the code graph to carry signal">low signal</span>'
        if action.get("low_signal") else ""
    )
    config = action.get("config") or {}
    fields_html = "".join(
        _field_control_html(field_spec, config.get(field_spec.get("name")))
        for field_spec in (action.get("filter_schema") or [])
    )
    proposals_html = "".join(_proposal_provenance_html(p) for p in pending_proposals)
    return f"""
      <div class="ops-action-card" data-action="{name}">
        <div class="ops-action-header">
          <span class="ops-action-name">{name}</span>
          <span class="ops-action-toggle ops-toggle-{'on' if enabled else 'off'}">{toggle_label}</span>
          <span class="ops-action-mode">{mode}</span>
          {low_signal_html}
        </div>
        <div class="ops-action-meta">
          <span class="ops-last-run">Last run: {last_run}</span>
          <span class="ops-pending-count">{pending} pending proposal{'s' if pending != 1 else ''}</span>
        </div>
        <div class="ops-action-fields">
          {fields_html}
        </div>
        <div class="ops-action-proposals">
          {proposals_html}
        </div>
      </div>"""


def _taxonomy_banner_html(taxonomy_status: dict) -> str:
    """'using built-in defaults' banner when load_taxonomy()'s config
    validation failed (DECIDE panel defect #5) -- taxonomy_status is the
    dict returned by maintainer_taxonomy.load_taxonomy(), i.e. it has
    schema_valid/validation_error keys."""
    if not taxonomy_status or taxonomy_status.get("schema_valid", True):
        return ""
    error = html_mod.escape(str(taxonomy_status.get("validation_error") or "unknown validation error"))
    return (
        '<div class="ops-banner ops-banner-warning">'
        f'Using built-in defaults &mdash; config failed validation: {error}'
        '</div>'
    )


def generate_role_ops_panel_html(role_slug: str, data: dict) -> str:
    """Full operations panel for role_slug, consumed by viz/roles.py's
    Agent Studio card. Renders one card per registered action in data["actions"],
    plus a defaults banner if data["taxonomy_status"] reports a validation failure."""
    role_slug_html = html_mod.escape(str(role_slug))
    actions = data.get("actions") or []
    cards_html = "".join(_action_card_html(a) for a in actions)
    banner_html = _taxonomy_banner_html(data.get("taxonomy_status") or {})
    return f"""
    <details class="edit-charter ops-panel" data-role="{role_slug_html}">
      <summary>Operations</summary>
      <div class="ops-panel-body">
        {banner_html}
        {cards_html}
      </div>
    </details>"""


def generate_condensed_widget_html(role_slug: str, data: dict) -> str:
    """Condensed Overview-page widget: badges per action + pending-proposal
    count + last-wake-cycle timestamp, linking out to the full panel."""
    role_slug_html = html_mod.escape(str(role_slug))
    actions = data.get("actions") or []
    total_pending = sum(len(a.get("pending_proposals") or []) for a in actions)
    last_wake = max(
        (a.get("last_run") for a in actions if a.get("last_run")),
        default="never",
    )
    badges_html = "".join(
        f'<span class="ops-badge ops-badge-{html_mod.escape(str(a.get("mode", "off")))}">{html_mod.escape(str(a.get("name", "")))}: '
        f'{"Dry-run" if a.get("mode") == "dry_run" else ("Promoted" if a.get("enabled") else "Off")}</span>'
        for a in actions
    )
    return f"""
      <div class="section-card ops-widget" data-role="{role_slug_html}">
        <div class="section-header">
          <div class="section-title">{role_slug_html.capitalize()} Operations</div>
          <a href="roles.html" class="section-link">View in Agent Studio →</a>
        </div>
        <div class="ops-widget-badges">{badges_html}</div>
        <div class="ops-widget-meta">
          <span>{total_pending} pending proposal{'s' if total_pending != 1 else ''}</span>
          <span>Last wake cycle: {html_mod.escape(str(last_wake))}</span>
        </div>
      </div>"""
