"""Tests for seeding the local agent's starter capability envelope.
capability_scores is a VIEW over capability_ratings — seeding means inserting
synthetic calibration stories + capability_ratings rows for a narrow starter
whitelist (docs/testing discipline, execute stage, small estimated_tokens)."""
import sqlite3
import tempfile
import threading
import unittest

from synlynk.local_agent_seed import seed_local_capability_envelope, STARTER_WHITELIST


def _fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY, engg_domain TEXT, org_domain TEXT,
            industry TEXT, phase TEXT, estimated_tokens INTEGER, goal_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE capability_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, agent TEXT,
            model_version TEXT DEFAULT 'unknown', split_model INTEGER DEFAULT 0,
            engg_domain TEXT, discipline TEXT, org_domain TEXT, role TEXT,
            stage TEXT, industry TEXT, phase TEXT, signal_source TEXT DEFAULT 'auto',
            quality REAL, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


class TestSeedLocalCapabilityEnvelope(unittest.TestCase):
    def test_seeds_one_row_per_starter_coordinate(self):
        conn = _fresh_db()
        seed_local_capability_envelope(conn)
        rows = conn.execute(
            "SELECT discipline, stage, quality FROM capability_ratings WHERE agent='local'"
        ).fetchall()
        self.assertEqual(len(rows), len(STARTER_WHITELIST))

    def test_seeded_stories_are_tagged_calibration(self):
        conn = _fresh_db()
        seed_local_capability_envelope(conn)
        story_ids = [r[0] for r in conn.execute(
            "SELECT story_id FROM stories WHERE story_id LIKE 'local-seed-%'"
        ).fetchall()]
        self.assertEqual(len(story_ids), len(STARTER_WHITELIST))

    def test_is_idempotent(self):
        conn = _fresh_db()
        seed_local_capability_envelope(conn)
        seed_local_capability_envelope(conn)
        rows = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent='local'"
        ).fetchone()[0]
        self.assertEqual(rows, len(STARTER_WHITELIST))

    def test_concurrent_first_use_is_atomic_and_idempotent(self):
        with tempfile.NamedTemporaryFile() as db_file:
            setup = _fresh_db()
            destination = sqlite3.connect(db_file.name)
            setup.backup(destination)
            destination.close()
            setup.close()
            barrier = threading.Barrier(2)
            errors = []

            def seed_once():
                conn = sqlite3.connect(db_file.name, timeout=5)
                try:
                    barrier.wait()
                    seed_local_capability_envelope(conn)
                except Exception as exc:  # surfaced by the assertion below
                    errors.append(exc)
                finally:
                    conn.close()

            threads = [threading.Thread(target=seed_once) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            conn = sqlite3.connect(db_file.name)
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM capability_ratings WHERE agent='local'"
                ).fetchone()[0],
                len(STARTER_WHITELIST),
            )
            conn.close()


if __name__ == "__main__":
    unittest.main()
