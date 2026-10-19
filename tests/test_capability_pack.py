"""Tests for capability pack export functionality."""

import json
import sqlite3
import pytest
from synlynk.capability_pack import export_capability_pack, generate_pack_metadata

def test_export_capability_pack_structure(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE capability_ratings (
            harness TEXT,
            model TEXT,
            discipline TEXT,
            quality REAL,
            quality_verified INTEGER,
            review_cycles REAL,
            cost_usd REAL,
            task_count INTEGER,
            PRIMARY KEY (harness, model, discipline)
        )
    """)
    cur.execute("""
        CREATE TABLE harness_models (
            harness TEXT,
            model TEXT,
            active INTEGER,
            PRIMARY KEY (harness, model)
        )
    """)
    cur.execute("INSERT INTO harness_models VALUES ('codex', 'gpt-5.6-terra', 1)")
    cur.execute("INSERT INTO harness_models VALUES ('grok', 'grok-4.6', 1)")
    cur.execute("INSERT INTO harness_models VALUES ('agy', 'gemini-3.8-flash', 1)")
    
    cur.execute("INSERT INTO capability_ratings VALUES ('codex', 'gpt-5.6-terra', 'PROG', 9.04, 1, 1.1, 0.52, 410)")
    cur.execute("INSERT INTO capability_ratings VALUES ('grok', 'grok-4.6', 'PROG', 8.55, 1, 1.2, 0.48, 176)")
    cur.execute("INSERT INTO capability_ratings VALUES ('agy', 'gemini-3.8-flash', 'PROG', 7.58, 1, 1.6, 0.08, 89)")
    conn.commit()

    pack = export_capability_pack(conn)
    assert pack["schema_version"] == "1.0.0"
    assert "matrix" in pack
    assert "PROG" in pack["matrix"]
    prog_ratings = pack["matrix"]["PROG"]
    assert len(prog_ratings) == 3
    assert prog_ratings[0]["harness"] == "codex"
    assert prog_ratings[0]["quality_score"] == 9.04
    assert prog_ratings[0]["sample_size"] == 410
    assert prog_ratings[0]["cost_per_verified_fix_usd"] == 0.52
    assert prog_ratings[0]["unmeasured"] is False

    assert "disciplines" in pack
    assert "PROG" in pack["disciplines"]
    assert pack["disciplines"]["PROG"]["name"] == "Software Development"

    assert "snapshot_metadata" in pack
    assert pack["snapshot_metadata"]["sha256"] is not None
    assert pack["snapshot_metadata"]["total_tasks"] == 675


def test_export_capability_pack_marks_unmeasured(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE capability_ratings (
            harness TEXT,
            model TEXT,
            discipline TEXT,
            quality REAL,
            quality_verified INTEGER,
            review_cycles REAL,
            cost_usd REAL,
            task_count INTEGER,
            PRIMARY KEY (harness, model, discipline)
        )
    """)
    cur.execute("""
        CREATE TABLE harness_models (
            harness TEXT,
            model TEXT,
            active INTEGER,
            PRIMARY KEY (harness, model)
        )
    """)
    cur.execute("INSERT INTO harness_models VALUES ('codex', 'gpt-5.6-terra', 1)")
    cur.execute("INSERT INTO capability_ratings VALUES ('codex', 'gpt-5.6-terra', 'DBDS', 8.0, 1, 1.0, 0.30, 3)")
    conn.commit()

    pack = export_capability_pack(conn, min_sample=5)
    dbds_ratings = pack["matrix"]["DBDS"]
    assert len(dbds_ratings) == 1
    assert dbds_ratings[0]["unmeasured"] is True


def test_generate_pack_metadata():
    meta = generate_pack_metadata(b'{"test": 123}')
    assert "snapshot_id" in meta
    assert "timestamp" in meta
    assert "sha256" in meta
    assert len(meta["sha256"]) == 64
