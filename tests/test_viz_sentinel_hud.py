"""Grouped Vizor sentinel HUD and workspace-scoped write paths."""
import json
import http.client
import subprocess
import threading
from http.server import HTTPServer

from synlynk.viz.constants import SENTINEL_ACKS_PATH
from synlynk.viz.data import (
    group_workspace_sentinel_alerts,
    investigate_brief,
    load_sentinel_acks,
    raise_sentinel_issue,
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


def _workspace_server(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".synlynk" / "sentinel.md").write_text(
        "- [CRITICAL] [2026-10-28 00:00:00 UTC] VIZOR_DAEMON_DOWN: "
        "vizor bind failed [occurrences: 2; first seen: 2026-10-27 00:00:00 UTC; "
        "last seen: 2026-10-28 00:00:00 UTC]\n",
        encoding="utf-8",
    )
    db = tmp_path / "state.db"
    db.write_bytes(b"")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "version": 1,
        "products": {"acme": {
            "product_id": "pid-acme",
            "slug": "acme",
            "canonical_path": str(db),
            "repo_path": str(repo),
            "mode": "canonical",
            "lineage_generation": 1,
            "state": "active",
        }},
    }))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    httpd = HTTPServer(
        ("127.0.0.1", 0), vizor_daemon.build_workspace_routing_handler()
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, repo


def _request(httpd, method, route, *, token=None, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Synlynk-Token"] = token
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=2)
    try:
        conn.request(method, route, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if raw.startswith(b"{") else raw
    finally:
        conn.close()


def test_post_ack_requires_auth_then_writes_workspace_sidecar(tmp_path, monkeypatch):
    from synlynk.local_http_auth import ensure_local_token

    httpd, repo = _workspace_server(tmp_path, monkeypatch)
    sidecar = repo / ".synlynk" / "sentinel-acks.json"
    try:
        denied, _ = _request(
            httpd, "POST", "/w/acme/api/sentinel/ack",
            payload={"scope": "pattern", "code": "VIZOR_DAEMON_DOWN"},
        )
        token = ensure_local_token()
        accepted, result = _request(
            httpd, "POST", "/w/acme/api/sentinel/ack", token=token,
            payload={"scope": "pattern", "code": "VIZOR_DAEMON_DOWN"},
        )
        fetched, hud = _request(httpd, "GET", "/w/acme/api/sentinel")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert denied in (401, 403)
    assert accepted == 200
    assert result == {"ok": True}
    assert fetched == 200
    assert hud["groups"] == []
    assert hud["acked"][0]["code"] == "VIZOR_DAEMON_DOWN"
    assert json.loads(sidecar.read_text())["slug"] == "acme"


def test_raise_sentinel_issue_uses_support_role_without_host_auth(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(
            argv, 0, stdout="https://github.com/nikhilsoman/synlynk/issues/1\n", stderr=""
        )

    monkeypatch.setenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", "1")
    monkeypatch.setattr(subprocess, "run", fake_run)
    group = group_workspace_sentinel_alerts([_alert("TOKEN_BLOAT", n=3)], {})["groups"][0]

    issue_url = raise_sentinel_issue("acme", group)

    argv, kwargs = calls[0]
    assert argv[:5] == ["synlynk", "gh", "--role", "support", "--"]
    assert argv[5] == "issue"
    assert argv[6] == "create"
    assert "[support] sentinel: TOKEN_BLOAT (3)" in argv
    assert "SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH" not in kwargs["env"]
    assert issue_url.endswith("/issues/1")


def test_post_issue_returns_502_without_ack_on_gh_failure(tmp_path, monkeypatch):
    from synlynk.local_http_auth import ensure_local_token
    import synlynk.viz.data as viz_data

    def fail_raise(slug, group):
        raise RuntimeError("gh failed")

    monkeypatch.setattr(viz_data, "raise_sentinel_issue", fail_raise)
    httpd, repo = _workspace_server(tmp_path, monkeypatch)
    try:
        status, result = _request(
            httpd, "POST", "/w/acme/api/sentinel/issue",
            token=ensure_local_token(),
            payload={"scope": "pattern", "code": "VIZOR_DAEMON_DOWN"},
        )
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 502
    assert result == {"ok": False, "error": "gh_failed"}
    assert not (repo / ".synlynk" / "sentinel-acks.json").exists()


def test_post_issue_success_records_url_on_pattern_ack(tmp_path, monkeypatch):
    from synlynk.local_http_auth import ensure_local_token
    import synlynk.viz.data as viz_data

    issue_url = "https://github.com/nikhilsoman/synlynk/issues/1"
    monkeypatch.setattr(viz_data, "raise_sentinel_issue", lambda slug, group: issue_url)
    httpd, repo = _workspace_server(tmp_path, monkeypatch)
    try:
        status, result = _request(
            httpd, "POST", "/w/acme/api/sentinel/issue",
            token=ensure_local_token(),
            payload={"scope": "pattern", "code": "VIZOR_DAEMON_DOWN"},
        )
    finally:
        httpd.shutdown()
        httpd.server_close()

    saved = json.loads((repo / ".synlynk" / "sentinel-acks.json").read_text())
    assert status == 200
    assert result == {"ok": True, "issue_url": issue_url}
    assert saved["acks"][0]["issue_url"] == issue_url


def test_investigate_brief_is_bounded_and_command_free():
    alerts = [
        _alert(
            "STALL_NO_OUTPUT",
            message=f"job-{index:08x} stalled",
        )
        for index in range(25)
    ]
    group = group_workspace_sentinel_alerts(alerts, {})["groups"][0]

    brief = investigate_brief("acme", group)

    assert brief["slug"] == "acme"
    assert brief["code"] == "STALL_NO_OUTPUT"
    assert len(brief["sample_messages"]) == 20
    assert len(brief["identities"]) == 20
    assert len(brief["job_ids"]) == 20
    assert set(brief) == {
        "slug", "code", "severity", "count", "first_seen", "last_seen",
        "sample_messages", "identities", "job_ids", "agents",
    }
    serialized = json.dumps(brief).lower()
    assert "shell" not in serialized
    assert "reproduce" not in serialized
    assert "$ " not in serialized


def test_overview_has_group_and_member_sentinel_actions_with_relative_fetches():
    from synlynk.viz.overview import generate_overview_html

    html = generate_overview_html({
        "workspace": {"name": "acme", "updated_at": "2026-10-31"},
        "telemetry": {"sentinel_alerts": [_alert("STALL_NO_OUTPUT", message="job a")]},
        "goals": [], "dreams": [], "jobs": [],
    }, 33333)

    for label in ("Inspect", "Ignore", "Raise issue", "Investigate"):
        assert html.count(f">{label}<") >= 2
    assert "fetch('api/sentinel/ack'" in html
    assert "fetch('api/sentinel/issue'" in html
    inline = html.split('id="sentinel-snapshot">', 1)[1]
    inline = inline.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "fetch('/" not in inline
    assert "navigator.clipboard.writeText" in html
    assert "reproduce" not in html.lower()
    assert "shell" not in inline.lower()


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
