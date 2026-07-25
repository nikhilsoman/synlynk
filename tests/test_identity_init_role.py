import json
from urllib.parse import parse_qs, urlparse

import synlynk as sl


def test_build_app_manifest_url_encodes_role_and_project():
    url = sl._build_app_manifest_url("alpha-project", "review")

    assert url.startswith("https://github.com/settings/apps/new?")
    manifest = json.loads(parse_qs(urlparse(url).query)["manifest"][0])
    assert manifest["name"] == "synlynk-alpha-project-review"
    assert "alpha-project" in manifest["hook_attributes"]["url"]
    assert "review" in manifest["redirect_url"]


def test_cmd_identity_init_role_noops_if_already_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    app_dir = tmp_path / ".synlynk" / "github_apps"
    app_dir.mkdir(parents=True)
    pem_path = app_dir / "review.pem"
    pem_path.write_text("PRIVATE KEY")

    json_path = app_dir / "review.json"
    json_path.write_text(
        json.dumps(
            {
                "role": "review",
                "app_id": 42,
                "client_id": "client-1",
                "app_slug": "synlynk-review",
                "installation_id": 99,
                "private_key_path": str(pem_path),
            },
            indent=2,
        )
        + "\n"
    )

    monkeypatch.setattr(sl, "_exchange_manifest_code", lambda code: (_ for _ in ()).throw(AssertionError("should not exchange")))
    monkeypatch.setattr(sl, "_confirm_installation", lambda app_slug, path: (_ for _ in ()).throw(AssertionError("should not confirm")))
    monkeypatch.setattr("builtins.input", lambda prompt="": (_ for _ in ()).throw(AssertionError("should not prompt")))

    sl.cmd_identity_init_role("review")

    assert json.loads(json_path.read_text())["installation_id"] == 99
