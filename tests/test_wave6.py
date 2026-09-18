import json

import pytest

from synlynk.wave6 import (
    GraphUnavailable,
    MembershipUnavailable,
    accept_membership,
    connector_dispatch_allowed,
    graph_read,
    hosted_vizor_placeholder,
)


def test_membership_requires_explicit_invite_and_writes_no_pem(tmp_path):
    with pytest.raises(MembershipUnavailable):
        accept_membership("", str(tmp_path / ".synlynk" / "membership.json"))

    path = tmp_path / ".synlynk" / "membership.json"
    receipt = accept_membership("opaque-invite", str(path))
    assert receipt["status"] == "pending"
    assert json.loads(path.read_text())["invite"] == "opaque-invite"
    assert not list(path.parent.glob("*.pem"))


def test_connector_dispatch_requires_explicit_grant(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config = tmp_path / ".synlynk" / "config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"identity_slug": "demo"}))
    from synlynk.connectors import add_connector
    add_connector(
        "demo", type_id="github", home_repo="synlynk", reach="home_repo",
        allowlist=["api.github.com"], protocol="oauth",
    )

    assert not connector_dispatch_allowed("github")
    assert connector_dispatch_allowed("github", ["connector"])
    assert connector_dispatch_allowed("dev")


def test_graph_read_fails_closed_without_minter():
    with pytest.raises(GraphUnavailable):
        graph_read()
    assert graph_read(lambda: {"nodes": []}) == {"nodes": []}


def test_hosted_vizor_is_named_placeholder():
    result = hosted_vizor_placeholder("My Product")
    assert result["status"] == "unavailable"
    assert result["url"] == "https://synlynk.com/my-product"
    assert "OAuth" in result["message"]
