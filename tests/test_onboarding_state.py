import sqlite3
import pytest
from synlynk.db import _migrate_onboarding_sessions
from synlynk.onboarding_state import (
    STAGES,
    STAGE_S1_ORIENTATION,
    STAGE_S2_DEPENDENCIES,
    STAGE_S4_TOPOLOGY,
    get_or_create_session,
    advance_stage,
    confirm_topology,
    record_probe,
)


@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    _migrate_onboarding_sessions(conn)
    yield conn
    conn.close()


def test_get_or_create_session_resumable(mem_db):
    s1 = get_or_create_session(mem_db, "my-product")
    assert s1["product_id"] == "my-product"
    assert s1["current_stage"] == STAGE_S1_ORIENTATION

    # Advance stage
    s2 = advance_stage(mem_db, s1["session_id"], STAGE_S2_DEPENDENCIES)
    assert s2["current_stage"] == STAGE_S2_DEPENDENCIES

    # Re-calling get_or_create returns existing session at S2
    resumed = get_or_create_session(mem_db, "my-product")
    assert resumed["session_id"] == s1["session_id"]
    assert resumed["current_stage"] == STAGE_S2_DEPENDENCIES


def test_confirm_topology_persists(mem_db):
    session = get_or_create_session(mem_db, "my-product")
    candidate = {"archetype": "standalone", "workspaces": [{"slug": "my-product"}]}
    updated = confirm_topology(mem_db, session["session_id"], candidate)
    assert updated["topology_status"] == "confirmed"
    assert updated["topology_confirmed"]["archetype"] == "standalone"


def test_record_probe_persists(mem_db):
    session = get_or_create_session(mem_db, "my-product")
    res = record_probe(mem_db, session["session_id"], "harness", "claude", {"status": "ok", "version": "1.0"})
    assert "claude" in res["harness_probes"]
    assert res["harness_probes"]["claude"]["status"] == "ok"
