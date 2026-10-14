"""Migration 21: enrich discovered harness models with catalog metadata."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='harness_models'"
    ).fetchone()
    if not exists:
        return

    info = conn.execute("PRAGMA table_info(harness_models)").fetchall()
    cols = {row[1] for row in info}
    pk = tuple(row[1] for row in sorted((r for r in info if r[5]), key=lambda r: r[5]))
    required = {
        "provider", "rate_input_per_mtok", "rate_output_per_mtok",
        "rate_cache_read_per_mtok", "rate_cache_write_per_mtok",
        "rate_tool_use_per_mtok", "rate_currency", "rate_source",
        "complexity_tier", "max_effort_level", "context_window_tokens",
        "max_output_tokens", "discovered_at",
    }
    if required <= cols and pk == ("harness_name", "model_id", "provider"):
        return

    # The previous schema keyed only by harness/model. Rebuild so provider is
    # part of the key, and use last_seen_at as the discovery timestamp.
    conn.execute("DROP TABLE IF EXISTS harness_models_catalog_new")
    conn.execute(
        """CREATE TABLE harness_models_catalog_new (
            harness_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            superseded_by TEXT,
            discovery_source TEXT NOT NULL DEFAULT 'curated',
            provider TEXT NOT NULL DEFAULT 'native',
            rate_input_per_mtok REAL,
            rate_output_per_mtok REAL,
            rate_cache_read_per_mtok REAL,
            rate_cache_write_per_mtok REAL,
            rate_tool_use_per_mtok REAL,
            rate_currency TEXT NOT NULL DEFAULT 'usd',
            rate_source TEXT,
            complexity_tier TEXT,
            max_effort_level TEXT,
            context_window_tokens INTEGER,
            max_output_tokens INTEGER,
            discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (harness_name, model_id, provider)
        )"""
    )
    old_columns = [
        "harness_name", "model_id", "first_seen_at", "last_seen_at", "status",
        "superseded_by", "discovery_source",
    ]
    select = [name if name in cols else ("'active'" if name == "status" else "NULL") for name in old_columns]
    expressions = {
        "provider": "COALESCE(provider, 'native')" if "provider" in cols else "'native'",
        "rate_currency": "COALESCE(rate_currency, 'usd')" if "rate_currency" in cols else "'usd'",
        "discovered_at": "COALESCE(discovered_at, last_seen_at)" if "discovered_at" in cols else "last_seen_at",
    }
    for name in ("rate_input_per_mtok", "rate_output_per_mtok", "rate_cache_read_per_mtok",
                 "rate_cache_write_per_mtok", "rate_tool_use_per_mtok", "rate_source",
                 "complexity_tier", "max_effort_level", "context_window_tokens", "max_output_tokens"):
        expressions[name] = name if name in cols else "NULL"
    names = old_columns + ["provider", "rate_input_per_mtok", "rate_output_per_mtok",
        "rate_cache_read_per_mtok", "rate_cache_write_per_mtok", "rate_tool_use_per_mtok",
        "rate_currency", "rate_source", "complexity_tier", "max_effort_level",
        "context_window_tokens", "max_output_tokens", "discovered_at"]
    values = select + [expressions[n] for n in names[len(old_columns):]]
    conn.execute(
        f"INSERT OR IGNORE INTO harness_models_catalog_new ({', '.join(names)}) "
        f"SELECT {', '.join(values)} FROM harness_models"
    )
    conn.execute("DROP TABLE harness_models")
    conn.execute("ALTER TABLE harness_models_catalog_new RENAME TO harness_models")


MIGRATION = Migration(version=21, name="harness_model_catalog", up=_up)
