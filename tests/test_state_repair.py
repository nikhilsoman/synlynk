import sqlite3

import pytest

from synlynk.state_repair import promote_state_db, quarantine_state_db, restore_state_db
from synlynk.state_registry import StateRegistryError


def _db(path, value="one"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE facts (value TEXT)")
    conn.execute("INSERT INTO facts VALUES (?)", (value,))
    conn.commit()
    conn.close()


def test_promotion_is_idempotent_and_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))
    source = tmp_path / "legacy.db"
    destination = tmp_path / "workspace" / "state.db"
    _db(source)

    first = promote_state_db(source, destination, slug="demo", product_id="product-demo")
    second = promote_state_db(source, destination, slug="demo", product_id="product-demo")
    assert first["disposition"] == "promoted"
    assert second["disposition"] == "already-complete"
    assert not (destination.parent / "state.db-wal").exists()

    _db(tmp_path / "different.db", "different")
    with pytest.raises(StateRegistryError, match="refusing to overwrite"):
        promote_state_db(tmp_path / "different.db", destination, slug="demo", product_id="product-demo")


def test_quarantine_defaults_to_plan_and_apply_moves_sidecars_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))
    legacy = tmp_path / "repo" / ".synlynk" / "state.db"
    legacy.parent.mkdir(parents=True)
    _db(legacy)
    plan = quarantine_state_db(legacy, slug="demo", quarantine_root=tmp_path / "q")
    assert plan["disposition"] == "planned"
    assert legacy.exists()

    applied = quarantine_state_db(legacy, slug="demo", quarantine_root=tmp_path / "q", apply=True)
    assert applied["disposition"] == "quarantined"
    assert not legacy.exists()
    assert all((tmp_path / "q").glob("*/manifest.json"))


def test_quarantine_rejects_registered_canonical(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))
    canonical = tmp_path / "canonical.db"
    _db(canonical)
    promote_state_db(canonical, canonical, slug="demo", product_id="product-demo")
    with pytest.raises(StateRegistryError, match="canonical DB"):
        quarantine_state_db(canonical, slug="demo", quarantine_root=tmp_path / "q", apply=True)


def test_restore_is_dry_run_by_default_and_assigns_new_lineage(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))
    source = tmp_path / "source.db"
    destination = tmp_path / "workspace" / "state.db"
    _db(source, "restored")
    destination.parent.mkdir()
    _db(destination, "broken")

    planned = restore_state_db(
        source, destination, slug="demo", product_id="product-demo", archive_root=tmp_path / "archive"
    )
    assert planned["disposition"] == "planned"
    assert destination.exists()

    restored = restore_state_db(
        source,
        destination,
        slug="demo",
        product_id="product-demo",
        archive_root=tmp_path / "archive",
        apply=True,
    )
    assert restored["disposition"] == "restored"
    assert restored["lineage_generation"] == 2
    conn = sqlite3.connect(destination)
    assert conn.execute("SELECT value FROM facts").fetchone()[0] == "restored"
    conn.close()
    assert list((tmp_path / "archive").rglob("state.db"))
