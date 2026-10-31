"""Grouped Vizor sentinel HUD. PR1 covers grouping, Overview, and GET/SSE."""
from synlynk.viz.constants import SENTINEL_ACKS_PATH
from synlynk.viz.data import group_workspace_sentinel_alerts


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
