import json
import sqlite3

import pytest

from synlynk.state_registry import (
    StateRegistryError,
    canonical_path,
    ensure_registered_product,
    identity_metadata,
)


def test_registry_registration_is_idempotent_and_path_bound(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    canonical = tmp_path / "workspace" / "state.db"

    first = ensure_registered_product("demo", canonical, "product-demo")
    second = ensure_registered_product("demo", canonical, "different-id")

    assert first == second
    assert second["product_id"] == "product-demo"
    assert canonical_path("demo", tmp_path / "wrong.db") == canonical.resolve()

    with pytest.raises(StateRegistryError, match="canonical path mismatch"):
        ensure_registered_product("demo", tmp_path / "other" / "state.db")


def test_existing_corrupt_registry_fails_closed(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    registry.write_text("not json", encoding="utf-8")
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))

    with pytest.raises(StateRegistryError, match="unreadable"):
        canonical_path("demo", tmp_path / "state.db")


def test_missing_registry_entry_can_be_explicitly_recovered(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    existing = tmp_path / "state.db"
    existing.write_text("state")
    registry.write_text(json.dumps({"version": 1, "products": {}}))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))

    assert canonical_path("demo", existing, allow_unregistered_existing=True) == existing.resolve()


def test_identity_metadata_rejects_copied_or_relocated_canonical(tmp_path):
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    conn = sqlite3.connect(first)
    try:
        identity_metadata(conn, product_id="product-demo", mode="canonical", path=first)
        conn.commit()
        with pytest.raises(StateRegistryError, match="identity mismatch"):
            identity_metadata(conn, product_id="product-demo", mode="canonical", path=second)
    finally:
        conn.close()


def test_registry_file_is_atomic_json(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    ensure_registered_product("demo", tmp_path / "state.db", "product-demo")
    payload = json.loads(registry.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["products"]["demo"]["mode"] == "canonical"


def test_ensure_registered_product_persists_repo_path(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    db_path = tmp_path / "workspaces" / "acme" / "state.db"
    repo_path = tmp_path / "repos" / "acme"
    repo_path.mkdir(parents=True)

    entry = ensure_registered_product(
        "acme", db_path, product_id="pid-1", repo_path=repo_path
    )

    assert entry["repo_path"] == str(repo_path.resolve())
    payload = json.loads(registry.read_text())
    assert payload["products"]["acme"]["repo_path"] == str(repo_path.resolve())


def test_ensure_registered_product_repo_path_optional(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    db_path = tmp_path / "workspaces" / "acme" / "state.db"

    entry = ensure_registered_product("acme", db_path, product_id="pid-1")

    assert "repo_path" not in entry


def test_ensure_registered_product_backfills_repo_path_on_existing_entry(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    db_path = tmp_path / "workspaces" / "acme" / "state.db"
    repo_path = tmp_path / "repos" / "acme"
    repo_path.mkdir(parents=True)

    # First register without repo_path
    initial = ensure_registered_product("acme", db_path, product_id="pid-1")
    assert "repo_path" not in initial

    # Re-registering with repo_path backfills and persists it
    updated = ensure_registered_product("acme", db_path, product_id="pid-1", repo_path=repo_path)
    assert updated["repo_path"] == str(repo_path.resolve())

    payload = json.loads(registry.read_text())
    assert payload["products"]["acme"]["repo_path"] == str(repo_path.resolve())


def test_typed_open_requires_explicit_noncanonical_modes(tmp_path):
    from synlynk import open_state_db

    with pytest.raises(ValueError, match="requires explicit_path"):
        open_state_db(mode="backup")
    with pytest.raises(RuntimeError, match="read-only by default"):
        open_state_db(mode="degraded", explicit_path=str(tmp_path / "state.db"))

    conn = open_state_db(mode="test", explicit_path=str(tmp_path / "test.db"))
    try:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()
