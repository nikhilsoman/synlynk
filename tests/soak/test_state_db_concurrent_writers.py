import os
import shutil
import sqlite3
import tempfile
import threading
import time
import json
import pytest

pytestmark = pytest.mark.soak


@pytest.fixture
def isolated_db_path():
    tmpdir = tempfile.mkdtemp(prefix="synlynk-soak-")
    db_path = os.path.join(tmpdir, "state.db")
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _init_schema(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE cost_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "job_id TEXT, harness TEXT, total_cost_usd REAL)"
    )
    conn.execute(
        "CREATE TABLE capability_ratings (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "agent TEXT, story_id TEXT, quality REAL)"
    )
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, status TEXT, updated_at REAL)"
    )
    conn.commit()
    conn.close()
