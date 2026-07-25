import json
import stat

import synlynk as sl


def test_identity_role_parser_registers_init_role_and_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from synlynk.cli import build_parser

    parser = build_parser()

    init_args = parser.parse_args(["identity", "init", "--role", "review"])
    assert init_args.command == "identity"
    assert init_args.identity_action == "init"
    assert init_args.role == "review"

    list_args = parser.parse_args(["identity", "list"])
    assert list_args.command == "identity"
    assert list_args.identity_action == "list"


def test_build_app_manifest_url_includes_manifest_payload():
    url = sl._build_app_manifest_url("review")

    assert url.startswith("https://github.com/settings/apps/new?")
    assert "manifest=" in url
    assert "synlynk-review" in url


def test_confirm_installation_uses_signed_jwt(monkeypatch):
    captured = {}
    import synlynk.team as team

    monkeypatch.setattr("synlynk.github_app_auth._sign_jwt", lambda pem_path, app_id=None, lifetime_seconds=540: "signed.jwt")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"id": 7, "html_url": "https://github.com/apps/synlynk-review"}).encode("utf-8")

    def fake_urlopen(request):
        captured["authorization"] = request.headers.get("Authorization")
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr(team, "urlopen", fake_urlopen)

    result = sl._confirm_installation("review", {"app_id": 7, "pem_path": "/tmp/review.pem"})

    assert result["id"] == 7
    assert captured["url"] == "https://api.github.com/app"
    assert captured["authorization"] == "Bearer signed.jwt"


def test_cmd_identity_init_role_writes_role_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.team as team

    monkeypatch.setattr(team, "_build_app_manifest_url", lambda role: f"https://github.com/settings/apps/new?role={role}")
    monkeypatch.setattr("builtins.input", lambda prompt="": "https://example.com/redirect?code=abc123")
    monkeypatch.setattr(
        team,
        "_exchange_manifest_code",
        lambda code: {
            "id": 42,
            "name": "synlynk-review",
            "client_id": "client-1",
            "client_secret": "secret-1",
            "webhook_secret": "webhook-1",
            "pem": "PEM DATA",
            "html_url": "https://github.com/apps/synlynk-review",
        },
    )
    monkeypatch.setattr(team, "_confirm_installation", lambda role, app_config: {"id": app_config["app_id"]})

    sl.cmd_identity_init_role("review")

    app_dir = tmp_path / "synlynk" / "github_apps"
    json_path = app_dir / "review.json"
    pem_path = app_dir / "review.pem"

    assert json_path.exists()
    assert pem_path.exists()
    assert pem_path.read_text() == "PEM DATA"
    assert stat.S_IMODE(pem_path.stat().st_mode) == 0o600

    config = json.loads(json_path.read_text())
    assert config["role"] == "review"
    assert config["app_id"] == 42
    assert config["pem_path"] == "synlynk/github_apps/review.pem"
