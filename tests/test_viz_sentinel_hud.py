"""Grouped Vizor sentinel HUD and workspace-scoped write paths."""
import json

from synlynk.viz.constants import SENTINEL_ACKS_PATH
from synlynk.viz.data import (
    group_workspace_sentinel_alerts,
    load_sentinel_acks,
    save_sentinel_ack,
)


def _alert(code, n=1, *, severity="WARNING", message="stall", last="2026-10-31 12:00:00 UTC", first=None):
    return {
        "severity": severity,
        "pattern": code,
        "message": message,
        "ts": last,
        "raw_line": f"- [{severity}] [{last}] {code}: {message}",
        "occurrences": n,
        "first_seen": first or last,
        "last_seen": last,
        "resolved": False,
    }


def test_sentinel_acks_path():
    assert SENTINEL_ACKS_PATH == ".synlynk/sentinel-acks.json"


def test_groups_by_code_and_collapse_default():
    alerts = (
        [_alert("STALL_NO_OUTPUT", message=f"job {i}") for i in range(20)]
        + [_alert("TOKEN_BLOAT", message=f"tok {i}") for i in range(10)]
        + [_alert("COST_INFLATION", message="a"), _alert("COST_INFLATION", message="b")]
    )
    hud = group_workspace_sentinel_alerts(alerts, {"version": 1, "acks": []})
    by_code = {g["code"]: g for g in hud["groups"]}
    assert set(by_code) == {"STALL_NO_OUTPUT", "TOKEN_BLOAT", "COST_INFLATION"}
    assert by_code["STALL_NO_OUTPUT"]["count"] == 20
    assert by_code["STALL_NO_OUTPUT"]["collapsed"] is True
    assert by_code["TOKEN_BLOAT"]["collapsed"] is True
    assert by_code["COST_INFLATION"]["collapsed"] is False
    assert hud["active_count"] == 32
    assert hud["acked"] == []
    assert hud["acked_count"] == 0


def test_worst_severity_and_member_cap():
    alerts = [_alert("X", severity="WARNING", message=f"m{i}") for i in range(55)]
    alerts[0]["severity"] = "CRITICAL"
    hud = group_workspace_sentinel_alerts(alerts, {"acks": []})
    group = hud["groups"][0]
    assert group["severity"] == "CRITICAL"
    assert group["count"] == 55
    assert len(group["members"]) == 50
    assert group["hidden_member_count"] == 5


def test_empty_code_is_unparsed():
    hud = group_workspace_sentinel_alerts([_alert("")], {"acks": []})
    assert hud["groups"][0]["code"] == "UNPARSED"


def test_resolved_alerts_are_dropped():
    alerts = [_alert("X"), {**_alert("Y"), "resolved": True}]
    hud = group_workspace_sentinel_alerts(alerts, {"acks": []})
    assert [g["code"] for g in hud["groups"]] == ["X"]


def test_load_missing_acks_is_empty(tmp_path):
    assert load_sentinel_acks(str(tmp_path / "missing.json"))["acks"] == []


def test_corrupt_acks_are_empty(tmp_path):
    path = tmp_path / "sentinel-acks.json"
    path.write_text("{not json")

    assert load_sentinel_acks(str(path))["acks"] == []


def test_occurrence_ack_hides_one_identity_without_touching_sentinel(tmp_path):
    from synlynk.sentinel import _alert_identity

    alerts = [
        _alert("STALL_NO_OUTPUT", message="job a"),
        _alert("STALL_NO_OUTPUT", message="job b"),
    ]
    acks_path = tmp_path / "acks.json"
    sentinel_path = tmp_path / "sentinel.md"
    sentinel_path.write_text("untouched\n")
    ident = list(_alert_identity({
        "severity": "WARNING",
        "code": "STALL_NO_OUTPUT",
        "message": "job a",
    }))

    save_sentinel_ack(str(acks_path), {
        "kind": "occurrence",
        "code": "STALL_NO_OUTPUT",
        "identity": ident,
        "acked_at": "2026-10-31T12:00:00Z",
        "last_seen_at_ack": "2026-10-31 12:00:00 UTC",
        "issue_url": None,
    }, slug="acme")
    hud = group_workspace_sentinel_alerts(
        alerts, load_sentinel_acks(str(acks_path))
    )

    assert hud["groups"][0]["count"] == 1
    assert hud["groups"][0]["members"][0]["message"] == "job b"
    assert sentinel_path.read_text() == "untouched\n"


def test_pattern_ack_moves_group_until_refire():
    alerts = [_alert("TOKEN_BLOAT", last="2026-10-31 12:00:00 UTC")]
    acks = {"acks": [{
        "kind": "pattern",
        "code": "TOKEN_BLOAT",
        "identity": None,
        "acked_at": "2026-10-31T12:00:00Z",
        "last_seen_at_ack": "2026-10-31 12:00:00 UTC",
        "issue_url": None,
    }]}

    hud = group_workspace_sentinel_alerts(alerts, acks)
    later = [_alert("TOKEN_BLOAT", last="2026-10-31 12:05:00 UTC")]
    refired = group_workspace_sentinel_alerts(later, acks)

    assert hud["groups"] == []
    assert hud["acked"][0]["code"] == "TOKEN_BLOAT"
    assert refired["groups"][0]["code"] == "TOKEN_BLOAT"
    assert refired["acked"] == []


def test_acks_are_isolated_per_sidecar_file(tmp_path):
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    save_sentinel_ack(str(a_path), {
        "kind": "pattern",
        "code": "X",
        "identity": None,
        "acked_at": "t",
        "last_seen_at_ack": "t",
        "issue_url": None,
    }, slug="one")

    assert load_sentinel_acks(str(b_path))["acks"] == []
    assert load_sentinel_acks(str(a_path))["slug"] == "one"
    assert json.loads(a_path.read_text())["slug"] == "one"


def test_overview_renders_groups_not_six_flat_rows():
    from synlynk.viz.overview import generate_overview_html

    alerts = []
    for i in range(20):
        alerts.append({
            "severity": "WARNING",
            "pattern": "STALL_NO_OUTPUT",
            "message": f"stall {i}",
            "ts": "2026-10-31",
            "resolved": False,
            "raw_line": f"stall {i}",
            "occurrences": 1,
            "first_seen": "2026-10-01",
            "last_seen": "2026-10-31",
        })
    alerts.append({
        "severity": "CRITICAL",
        "pattern": "VIZOR_DAEMON_DOWN",
        "message": "bind failed",
        "ts": "2026-10-31",
        "resolved": False,
        "raw_line": "raw sentinel line",
        "occurrences": 4,
        "first_seen": "2026-10-27 01:00:00 UTC",
        "last_seen": "2026-10-28 02:00:00 UTC",
    })
    html = generate_overview_html({
        "workspace": {"name": "acme", "updated_at": "2026-10-31"},
        "telemetry": {"sentinel_alerts": alerts},
        "goals": [], "dreams": [], "jobs": [],
    }, 33333)
    assert "Active Sentinel Alerts (24)" in html
    assert 'data-sentinel-group="STALL_NO_OUTPUT"' in html
    assert 'data-sentinel-group="VIZOR_DAEMON_DOWN"' in html
    assert "Acked (" in html
    snapshot = html.split('id="sentinel-snapshot">', 1)[1].split("</script>", 1)[0]
    assert '"groups"' in snapshot
    listener = html.split("addEventListener('sentinel'", 1)[1].split("source.onerror", 1)[0]
    assert "payload.alerts" not in listener or "payload.groups" in html
