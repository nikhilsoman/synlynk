import json

import pytest

from synlynk.connectors import (
    ConnectorInvalid,
    add_connector,
    connector_metadata_path,
    connector_secret_path,
)
from synlynk.types_registry import load_types, relabel_type, seed_canonical_types


def setup_product(tmp_path, monkeypatch, slug="hitchcock"):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": slug}))
    monkeypatch.chdir(repo)
    return slug


def test_pack_type_ids_are_distinct_from_kinds_and_relabel_does_not_remint(tmp_path, monkeypatch):
    slug = setup_product(tmp_path, monkeypatch)
    seed_canonical_types(slug, "studio")
    assert load_types(slug)["director"]["kind"] == "pm"
    before = load_types(slug)["director"].copy()
    relabel_type(slug, "director", "Showrunner")
    after = load_types(slug)["director"]
    assert after["label"] == "Showrunner"
    assert after["kind"] == before["kind"]
    assert after["canonical"] is True


def test_connector_requires_allowlist_and_known_protocol(tmp_path, monkeypatch):
    slug = setup_product(tmp_path, monkeypatch)
    with pytest.raises(ConnectorInvalid, match="allowlist"):
        add_connector(slug, type_id="figma", home_repo="synlynk", reach="home_repo", allowlist=[], protocol="oauth")
    with pytest.raises(ConnectorInvalid, match="unknown connector protocol"):
        add_connector(slug, type_id="figma", home_repo="synlynk", reach="home_repo", allowlist=["figma.com"], protocol="magic")


def test_connector_metadata_is_product_scoped_and_secret_is_not_returned(tmp_path, monkeypatch):
    slug = setup_product(tmp_path, monkeypatch)
    metadata = add_connector(
        slug, type_id="figma", home_repo="synlynk", reach="home_repo",
        allowlist=["api.figma.com"], protocol="gateway", secret="top-secret",
    )
    assert metadata["kind"] == "connector"
    assert "secret" not in metadata
    assert json.loads(connector_metadata_path(slug, "figma").read_text())["protocol"] == "gateway"
    assert connector_secret_path(slug, "figma").read_text() == "top-secret"
    assert connector_secret_path(slug, "figma").stat().st_mode & 0o777 == 0o600
