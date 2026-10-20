import json
import os
import pytest

from synlynk.release_marketing import (
    ReleaseCeremonyResult,
    sync_docs_bundles,
    mirror_docs_pdfs_to_website,
    update_website_metadata,
    execute_release_ceremony,
    compile_docs_pdfs,
    compile_book_epub,
    compile_html_to_pdf,
    find_chrome_binary,
    find_pandoc_binary,
)


def _setup_fixture_repo(tmp_path):
    root = str(tmp_path)
    # 1. README
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Synlynk\n\n"
        "![Version](https://img.shields.io/badge/version-0.18.0-blue)\n"
        "![Tests](https://img.shields.io/badge/tests-2000%20collected-green)\n\n2000 tests collected.\n\n"
        "**v0.18.0:** Initial release\n\n"
        "<!-- commands:start -->\nold commands\n<!-- commands:end -->\n"
    )
    # 2. Docs bundles
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    for name in ("synlynk-quickstart-guide.html", "synlynk-official-reference.html", "synlynk-command-reference.html"):
        (docs_dir / name).write_text(
            f"<html><head><title>{name}</title></head><body>"
            f"<div class='pill'>v0.18.0</div>"
            f"<p>Version 0.18.0 — Released 2026-08-30</p>"
            f"</body></html>"
        )
    for name in ("synlynk-quickstart-guide.pdf", "synlynk-official-reference.pdf", "synlynk-command-reference.pdf"):
        (docs_dir / name).write_bytes(b"%PDF-1.4 dummy binary content")

    # 3. Website structure
    web_data = tmp_path / "website" / "src" / "_data"
    web_data.mkdir(parents=True)
    web_assets_docs = tmp_path / "website" / "src" / "assets" / "docs"
    web_assets_docs.mkdir(parents=True)
    (tmp_path / "website" / "package.json").write_text('{"name": "test-website"}')
    return root


def test_sync_docs_bundles_updates_version_and_date(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    updated = sync_docs_bundles(root, version="0.20.0", date_str="2026-09-11")
    assert len(updated) == 3
    for fname in updated:
        content = open(os.path.join(root, "docs", fname)).read()
        assert "v0.20.0" in content
        assert "Version 0.20.0" in content
        assert "2026-09-11" in content
        assert "v0.18.0" not in content


def test_mirror_docs_pdfs_to_website(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    copied = mirror_docs_pdfs_to_website(root)
    assert len(copied) == 3
    dest_dir = os.path.join(root, "website", "src", "assets", "docs")
    for name in ("synlynk-quickstart-guide.pdf", "synlynk-official-reference.pdf", "synlynk-command-reference.pdf"):
        assert os.path.isfile(os.path.join(dest_dir, name))
        assert open(os.path.join(dest_dir, name), "rb").read() == b"%PDF-1.4 dummy binary content"


def test_update_website_metadata(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    ok = update_website_metadata(root, version="0.20.0", date_str="2026-09-11")
    assert ok is True
    meta_path = os.path.join(root, "website", "src", "_data", "release.json")
    assert os.path.isfile(meta_path)
    with open(meta_path) as f:
        meta = json.load(f)
    assert meta["version"] == "0.20.0"
    assert meta["release_date"] == "2026-09-11"


def test_execute_release_ceremony_dry_run(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    res = execute_release_ceremony(root, version="0.20.0", dry_run=True)
    assert isinstance(res, ReleaseCeremonyResult)
    assert res.ok is True
    assert res.version == "0.20.0"
    assert res.dry_run is True
    # Verify files were NOT altered in dry-run
    readme = open(os.path.join(root, "README.md")).read()
    assert "version-0.18.0" in readme


def test_execute_release_ceremony_live(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    res = execute_release_ceremony(
        root, version="0.20.0", collected_count=2750, hero_summary="Visual Workspace & Onboarding",
        dry_run=False, skip_build=True
    )
    assert res.ok is True
    assert res.readme_updated is True
    assert res.website_updated is True
    assert len(res.docs_updated) == 3
    assert res.pdfs_compiled == []
    assert res.epub_compiled is None
    readme = open(os.path.join(root, "README.md")).read()
    assert "version-0.20.0" in readme
    assert "2750%20collected" in readme
    assert "2750 tests collected" in readme


def test_cmd_marketing_ceremony_cli(tmp_path, monkeypatch):
    from synlynk import cmd_marketing_ceremony
    root = _setup_fixture_repo(tmp_path)
    (tmp_path / "VERSION").write_text("0.20.0\n")
    monkeypatch.chdir(tmp_path)
    # Dry run
    cmd_marketing_ceremony(version="0.20.0", dry_run=True, skip_build=True)
    # Live run
    cmd_marketing_ceremony(version="0.20.0", dry_run=False, skip_build=True)
    meta_path = os.path.join(root, "website", "src", "_data", "release.json")
    assert os.path.isfile(meta_path)
    with open(meta_path) as f:
        meta = json.load(f)
    assert meta["version"] == "0.20.0"


def test_cli_parser_marketing_ceremony():
    from synlynk.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["marketing", "ceremony", "--version", "0.20.0", "--dry-run", "--skip-build"])
    assert args.command == "marketing"
    assert args.marketing_action == "ceremony"
    assert args.version == "0.20.0"
    assert args.dry_run is True
    assert args.skip_build is True


def test_cmd_release_invokes_marketing_ceremony(tmp_path, monkeypatch):
    from synlynk import cmd_release
    root = _setup_fixture_repo(tmp_path)
    (tmp_path / "VERSION").write_text("0.18.0\n")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [v0.18.0]\n- Old\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *args, **kwargs: type("Auth", (), {"allowed": True})())

    waives = ["hero=test", "install=test", "links=test", "commands=test"]
    # Dry-run release should trigger dry-run marketing ceremony
    cmd_release(dry_run=True, version="0.19.0", role="dev", waive=waives)
    # Model the metadata committed with the proposed release before its
    # fail-closed validation. The validator deliberately does not let a
    # marketing dry-run create a new source-of-truth version.
    (tmp_path / "VERSION").write_text("0.19.0\n")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [v0.19.0]\n- Test release\n")
    readme = tmp_path / "README.md"
    readme.write_text(readme.read_text().replace("**v0.18.0:**", "**v0.19.0:**"))
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        "dynamic = [\"version\"]\n\n"
        "[tool.setuptools.dynamic]\n"
        "version = {file = [\"VERSION\"]}\n"
    )
    # Release check docs validates the committed metadata without writing it.
    cmd_release(check_docs=True, version="0.19.0", role="dev", waive=waives)


def test_compile_docs_pdfs_dry_run(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    compiled = compile_docs_pdfs(root, dry_run=True)
    assert len(compiled) == 3
    assert "synlynk-quickstart-guide.pdf" in compiled
    assert "synlynk-official-reference.pdf" in compiled
    assert "synlynk-command-reference.pdf" in compiled


def test_compile_book_epub_dry_run(tmp_path):
    root = _setup_fixture_repo(tmp_path)
    book_dir = tmp_path / "docs" / "book"
    book_dir.mkdir(parents=True)
    (book_dir / "the-supervised-machine-v0.5-DRAFT.html").write_text("<html><body>Book</body></html>")
    epub = compile_book_epub(root, dry_run=True)
    assert epub == "the-supervised-machine-v0.5-DRAFT.epub"


def test_find_binaries():
    # In this Mac environment, Chrome or Pandoc may be detected
    chrome = find_chrome_binary()
    assert chrome is None or os.path.exists(chrome)
    pandoc = find_pandoc_binary()
    assert pandoc is None or os.path.exists(pandoc)


def test_compile_html_to_pdf_headless_flags(monkeypatch, tmp_path):
    html_file = tmp_path / "test.html"
    html_file.write_text("<html><body>Test</body></html>")
    pdf_file = tmp_path / "test.pdf"

    captured_cmds = []

    def mock_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        # Create dummy pdf file so compile_html_to_pdf sees success
        pdf_file.write_bytes(b"%PDF-1.4 dummy content")
        class MockProc:
            returncode = 0
        return MockProc()

    monkeypatch.setattr("subprocess.run", mock_run)

    success = compile_html_to_pdf(
        str(html_file),
        str(pdf_file),
        chrome_bin="/usr/bin/fake-chrome",
    )
    assert success is True
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert cmd[0] == "/usr/bin/fake-chrome"
    assert "--headless=new" in cmd
    assert "--no-sandbox" in cmd
    assert "--disable-gpu" in cmd
    assert any(arg.startswith("--user-data-dir=") for arg in cmd)


def test_execute_release_ceremony_respects_skip_build(monkeypatch, tmp_path):
    import synlynk.release_marketing as rm
    root = _setup_fixture_repo(tmp_path)

    pdf_called = []
    epub_called = []
    mirror_called = []

    monkeypatch.setattr(rm, "compile_docs_pdfs", lambda **kw: pdf_called.append(kw) or ["mock.pdf"])
    monkeypatch.setattr(rm, "compile_book_epub", lambda **kw: epub_called.append(kw) or "mock.epub")
    monkeypatch.setattr(rm, "mirror_docs_pdfs_to_website", lambda **kw: mirror_called.append(kw))
    monkeypatch.setattr(rm, "verify_website_build", lambda **kw: (True, "Mock website build ok"))

    # When skip_build=True, none of these should be called
    res_skip = execute_release_ceremony(root, version="0.21.0", dry_run=False, skip_build=True)
    assert res_skip.ok is True
    assert len(pdf_called) == 0
    assert len(epub_called) == 0
    assert len(mirror_called) == 0
    assert res_skip.pdfs_compiled == []
    assert res_skip.epub_compiled is None

    # When skip_build=False, all build steps should be called
    res_build = execute_release_ceremony(root, version="0.21.0", dry_run=False, skip_build=False)
    assert res_build.ok is True
    assert len(pdf_called) == 1
    assert len(epub_called) == 1
    assert len(mirror_called) == 1
    assert res_build.pdfs_compiled == ["mock.pdf"]
    assert res_build.epub_compiled == "mock.epub"


def test_compile_html_to_pdf_unmocked_under_pytest_is_safely_blocked(tmp_path):
    html_file = tmp_path / "test.html"
    html_file.write_text("<html><body>Test</body></html>")
    pdf_file = tmp_path / "test.pdf"

    # Under pytest with unmocked subprocess.run, it must refuse to spawn real host Chrome
    success = compile_html_to_pdf(
        str(html_file),
        str(pdf_file),
        chrome_bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    assert success is False
    assert not pdf_file.exists()



