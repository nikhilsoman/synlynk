"""Tests for FTUE onboarding wizard and Graphify tool recommendations."""

import json
from synlynk.coldstart import get_onboarding_recommendations


def test_onboarding_recommends_graphify_when_missing(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)
    recs = get_onboarding_recommendations()
    tools = [r["name"] for r in recs]
    assert "graphify" in tools
    assert recs[tools.index("graphify")]["recommended"] is True
    assert recs[tools.index("graphify")]["installed"] is False
    assert "20x token savings" in recs[tools.index("graphify")]["label"]


def test_onboarding_graphify_when_already_installed(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)
    recs = get_onboarding_recommendations()
    tools = [r["name"] for r in recs]
    assert "graphify" in tools
    assert recs[tools.index("graphify")]["installed"] is True
    assert recs[tools.index("graphify")]["recommended"] is False


def test_generate_onboarding_html_renders_graphify_checkbox(monkeypatch):
    from synlynk.viz import generate_onboarding_html

    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)
    html = generate_onboarding_html()
    assert "Graphify AST Knowledge Graph" in html
    assert "Recommended: ~20x token savings" in html
    assert "1-Click Install" in html
    assert "/tools/install" in html


def test_generate_onboarding_html_when_graphify_installed(monkeypatch):
    from synlynk.viz import generate_onboarding_html

    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)
    html = generate_onboarding_html()
    assert "Graphify AST Knowledge Graph" in html
    assert "Installed" in html


def test_run_ftue_journey_includes_recommendations(tmp_path):
    from synlynk.coldstart import run_ftue_journey

    (tmp_path / "main.py").write_text("print('test')\n")
    res = run_ftue_journey(str(tmp_path), interactive=False, dry_run=True)
    assert "recommendations" in res
    assert isinstance(res["recommendations"], list)
    tools = [r["name"] for r in res["recommendations"]]
    assert "graphify" in tools


def test_viz_tool_install_request_json(monkeypatch):
    import io
    from synlynk.viz import VizorHandler

    called = {}

    def fake_install(tool_name):
        called["tool"] = tool_name
        return True

    monkeypatch.setattr("synlynk.tool_installer.install_tool", fake_install)

    handler = VizorHandler.__new__(VizorHandler)
    handler.path = "/api/tools/install"
    handler.requestline = "POST /api/tools/install HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler._headers_buffer = []
    handler.headers = {"Content-Type": "application/json"}
    handler.wfile = io.BytesIO()

    monkeypatch.setattr(handler, "_read_json_body", lambda: {"tool": "graphify"})
    monkeypatch.setattr(handler, "_authorize_write", lambda: True)

    handler.do_POST()

    assert called.get("tool") == "graphify"
    raw_output = handler.wfile.getvalue().decode("utf-8")
    json_part = raw_output.split("\r\n\r\n", 1)[1]
    response_data = json.loads(json_part)
    assert response_data.get("ok") is True
    assert response_data.get("tool") == "graphify"


def test_viz_tool_install_request_form(monkeypatch):
    import io
    from synlynk.viz import VizorHandler

    called = {}

    def fake_install(tool_name):
        called["tool"] = tool_name
        return True

    monkeypatch.setattr("synlynk.tool_installer.install_tool", fake_install)

    handler = VizorHandler.__new__(VizorHandler)
    handler.path = "/tools/install"
    body = b"tool=graphify"
    handler.headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(body)),
    }
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()

    redirect_headers = {}

    def fake_send_response(code):
        redirect_headers["status"] = code

    def fake_send_header(key, val):
        redirect_headers[key] = val

    def fake_end_headers():
        pass

    monkeypatch.setattr(handler, "send_response", fake_send_response)
    monkeypatch.setattr(handler, "send_header", fake_send_header)
    monkeypatch.setattr(handler, "end_headers", fake_end_headers)
    monkeypatch.setattr(handler, "_authorize_write", lambda: True)

    handler.do_POST()

    assert called.get("tool") == "graphify"
    assert redirect_headers.get("status") == 302
    assert "/onboarding?installed=graphify&status=success" in redirect_headers.get("Location", "")
