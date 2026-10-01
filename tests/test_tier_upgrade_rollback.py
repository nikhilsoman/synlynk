from unittest.mock import patch


def test_detect_install_type_uv(tmp_path):
    from synlynk.upgrade import _detect_install_type

    with patch("shutil.which", return_value=str(tmp_path / "bin" / "synlynk")):
        with patch.dict("os.environ", {"UV_TOOL_DIR": str(tmp_path)}, clear=True):
            assert _detect_install_type() == "uv"


def test_detect_install_type_manifest(tmp_path):
    from synlynk.upgrade import _detect_install_type

    manifest_file = tmp_path / "install.json"
    manifest_file.write_text('{"method": "standalone_venv", "version": "0.23.0"}')
    with patch("synlynk.install_manifest.DEFAULT_MANIFEST_PATH", manifest_file):
        assert _detect_install_type() == "standalone_venv"


def test_rollback_leg2_standalone_venv(tmp_path, monkeypatch):
    from synlynk import rollback

    monkeypatch.chdir(tmp_path)
    rolled_back = []
    monkeypatch.setattr(
        "synlynk.standalone_venv.rollback_standalone_release",
        lambda: rolled_back.append(True),
    )
    monkeypatch.setattr(rollback, "_archive_manifest", lambda manifest: None)

    rollback.restore_leg2(
        {
            "op_id": "standalone-rollback",
            "install_type": "standalone_venv",
            "previous_version": "0.23.0",
        }
    )

    assert rolled_back == [True]
