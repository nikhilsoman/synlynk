"""End-to-End integration tests for Synaptic AI Capability Index & Preflight."""

import json
from pathlib import Path
from synlynk.capability_pack import export_capability_pack
from synlynk.preflight import evaluate_preflight

def test_e2e_export_and_evaluate_flow(tmp_path):
    import sqlite3
    db_path = tmp_path / "e2e_state.db"
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
    cur.execute("INSERT INTO capability_ratings VALUES ('codex', 'gpt-5.6-terra', 'PROG', 9.2, 1, 1.0, 0.40, 25)")
    conn.commit()

    # 1. Export pack
    pack = export_capability_pack(conn)
    pack_file = tmp_path / "pack.json"
    pack_file.write_text(json.dumps(pack))

    # 2. Evaluate preflight using exported pack
    result = evaluate_preflight(
        prompt="Design and implement a thread-safe connection cache",
        pack=pack,
        preferences={"optimize_for": "quality"}
    )

    assert result["task_classification"]["sfia_code"] == "PROG"
    assert result["task_classification"]["complexity"] in {"medium", "complex"}
    assert result["recommendations"]["primary"]["harness"] == "codex"
    assert result["recommendations"]["primary"]["quality_score"] == 9.2
    assert result["cta"]["install_cmd"] == "brew install synlynk"
