"""gh:#2547 Workstream E -- baseline-seeded capability_ratings rows
(signal_source='baseline_seed') must never count toward the n>=5 sample
threshold that gates routing decisions."""
import os


def test_routing_sample_count_excludes_baseline_seed_rows(monkeypatch, project_dir):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title) VALUES ('__baseline_seed__', 'seed')"
    )
    for _ in range(10):
        conn.execute(
            """INSERT INTO capability_ratings
               (story_id, agent, model_version, discipline, org_domain,
                industry, phase, signal_source, quality, correct)
               VALUES ('__baseline_seed__', 'muse', 'muse-1', 'backend',
                       'platform', 'unknown', 'build', 'baseline_seed', 9.0, 1)"""
        )
    conn.commit()

    from synlynk.capability_sweep import _measured_sample_count

    count = _measured_sample_count(conn, "muse")
    assert count == 0  # all 10 rows are baseline_seed, none are real measurements

    # Insert 5 real measurement rows with signal_source='auto'
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title) VALUES ('story-real-1', 'real story')"
    )
    for _ in range(5):
        conn.execute(
            """INSERT INTO capability_ratings
               (story_id, agent, model_version, discipline, org_domain,
                industry, phase, signal_source, quality, correct)
               VALUES ('story-real-1', 'muse', 'muse-1', 'backend',
                       'platform', 'unknown', 'build', 'auto', 8.5, 1)"""
        )
    conn.commit()

    count_after_real = _measured_sample_count(conn, "muse")
    conn.close()

    assert count_after_real == 5  # only the 5 real measurements are counted toward the threshold


def test_routing_sample_count_gates_threshold(monkeypatch, project_dir):
    """Confirm n>=5 threshold check returns False with only baseline seeds, True with real data."""
    import synlynk
    from synlynk.capability_sweep import _measured_sample_count

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title) VALUES ('__baseline_seed__', 'seed')"
    )
    # 20 baseline_seed rows
    for _ in range(20):
        conn.execute(
            """INSERT INTO capability_ratings
               (story_id, agent, model_version, discipline, org_domain,
                industry, phase, signal_source, quality, correct)
               VALUES ('__baseline_seed__', 'muse', 'muse-1', 'backend',
                       'platform', 'unknown', 'build', 'baseline_seed', 9.0, 1)"""
        )
    conn.commit()

    count = _measured_sample_count(conn, "muse")
    assert count < 5  # Gate closed despite 20 rows in table

    # Add 4 real measurements (still < 5)
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title) VALUES ('story-real-2', 'real story 2')"
    )
    for _ in range(4):
        conn.execute(
            """INSERT INTO capability_ratings
               (story_id, agent, model_version, discipline, org_domain,
                industry, phase, signal_source, quality, correct)
               VALUES ('story-real-2', 'muse', 'muse-1', 'backend',
                       'platform', 'unknown', 'build', 'auto', 9.0, 1)"""
        )
    conn.commit()
    assert _measured_sample_count(conn, "muse") == 4
    assert _measured_sample_count(conn, "muse") < 5

    # 5th real measurement unlocks the gate
    conn.execute(
        """INSERT INTO capability_ratings
           (story_id, agent, model_version, discipline, org_domain,
            industry, phase, signal_source, quality, correct)
           VALUES ('story-real-2', 'muse', 'muse-1', 'backend',
                   'platform', 'unknown', 'build', 'verifier', 9.2, 1)"""
    )
    conn.commit()
    assert _measured_sample_count(conn, "muse") == 5
    assert _measured_sample_count(conn, "muse") >= 5
    conn.close()
