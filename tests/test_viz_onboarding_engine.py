import json
import sqlite3
from unittest.mock import MagicMock, patch
import pytest

from synlynk.viz import generate_onboarding_html, VizorHandler
from synlynk.onboarding_state import get_or_create_session, advance_stage, STAGE_S2_DEPENDENCIES, confirm_topology
from synlynk.db import _migrate_onboarding_sessions

def test_generate_onboarding_html_includes_10_stages():
    html = generate_onboarding_html(port=27472)
    assert "S1_Orientation" in html or "Orientation" in html
    assert "S2_Dependencies" in html or "Dependencies" in html
    assert "S4_TopologyConfirmation" in html or "Topology" in html
    assert "S10_BuildExperience" in html or "First-Win" in html

@patch('synlynk.open_state_db')
def test_onboarding_api_state(mock_open_db):
    conn = sqlite3.connect(":memory:")
    conn.execute("""
    CREATE TABLE onboarding_sessions (
        session_id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        current_stage TEXT NOT NULL,
        topology_status TEXT,
        topology_candidate TEXT,
        topology_confirmed TEXT,
        harness_probes TEXT,
        dependency_checks TEXT,
        first_win_meta TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        completed_at REAL
    )
    """)
    get_or_create_session(conn, "test-slug")
    mock_open_db.return_value = (conn, True)

    server = MagicMock()
    server.server_port = 27472
    handler = VizorHandler.__new__(VizorHandler)
    handler.server = server
    handler.require_auth = False
    handler.path = ""
    handler.requestline = ""
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)

    handler.path = "/w/test-slug/api/onboarding/state"
    handler.headers = {"Cookie": "synlynk_local_token=123"}
    handler.wfile = MagicMock()
    handler._authorize_write = MagicMock(return_value=True)

    handler.do_GET()

    
    args, _ = handler.wfile.write.call_args_list[-1]
    data = json.loads(args[0].decode('utf-8'))
    assert data["product_id"] == "test-slug"
    assert data["current_stage"] == "S1_Orientation"

@patch('synlynk.open_state_db')
def test_onboarding_api_confirm_topology(mock_open_db):
    conn = sqlite3.connect(":memory:")
    conn.execute("""
    CREATE TABLE onboarding_sessions (
        session_id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        current_stage TEXT NOT NULL,
        topology_status TEXT,
        topology_candidate TEXT,
        topology_confirmed TEXT,
        harness_probes TEXT,
        dependency_checks TEXT,
        first_win_meta TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        completed_at REAL
    )
    """)
    sess = get_or_create_session(conn, "test-slug")
    mock_open_db.return_value = (conn, True)

    server = MagicMock()
    server.server_port = 27472
    handler = VizorHandler.__new__(VizorHandler)
    handler.server = server
    handler.require_auth = False
    handler.path = ""
    handler.requestline = ""
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)

    handler.path = "/w/test-slug/api/onboarding/topology/confirm"
    handler.headers = {"Cookie": "synlynk_local_token=123"}
    handler.wfile = MagicMock()
    handler.rfile = MagicMock()
    handler.rfile.read.return_value = json.dumps({"test_topology": "value"}).encode("utf-8")
    handler.headers["Content-Length"] = str(len(handler.rfile.read.return_value))
    handler._authorize_write = MagicMock(return_value=True)

    handler.do_POST()

    
    args, _ = handler.wfile.write.call_args_list[-1]
    data = json.loads(args[0].decode('utf-8'))
    assert data["topology_status"] == "confirmed"
    assert data["topology_confirmed"] == {"test_topology": "value"}
