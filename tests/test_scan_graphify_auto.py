import os
import subprocess
from unittest.mock import patch, MagicMock
from synlynk.scan import _run_graphify_extract


def test_run_graphify_extract_skips_subprocess_when_opted_out(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_SKIP_GRAPHIFY_EXTRACT", "1")

    with patch("synlynk.scan.is_tool_available") as mock_available, \
         patch("synlynk.scan.install_tool") as mock_install, \
         patch("subprocess.run") as mock_run:
        assert _run_graphify_extract(str(tmp_path)) is True

    mock_available.assert_not_called()
    mock_install.assert_not_called()
    mock_run.assert_not_called()


def test_run_graphify_extract_when_installed(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNLYNK_SKIP_GRAPHIFY_EXTRACT", raising=False)

    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        mock_run.assert_called_once_with(
            ["graphify", "extract", str(tmp_path), "--code-only", "--out", os.path.join(str(tmp_path), ".synlynk", "graphify-out")],
            capture_output=True,
            text=True,
            timeout=120,
        )


def test_run_graphify_extract_auto_installs_if_missing(tmp_path):
    with patch("synlynk.scan.is_tool_available", side_effect=[False, True]), \
         patch("synlynk.scan.install_tool", return_value=True) as mock_install, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        mock_install.assert_called_once_with("graphify")


def test_run_graphify_extract_install_fails(tmp_path):
    with patch("synlynk.scan.is_tool_available", return_value=False), \
         patch("synlynk.scan.install_tool", return_value=False) as mock_install:
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is False
        mock_install.assert_called_once_with("graphify")


def test_run_graphify_extract_subprocess_error(tmp_path):
    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is False


def test_classify_source_file_is_brownfield_with_zero_commits(tmp_path):
    from synlynk.scan import classify_workspace

    (tmp_path / "app.py").write_text("x = 1\n")
    assert classify_workspace(str(tmp_path)) == "brownfield"


def test_classify_init_templates_only_is_greenfield(tmp_path):
    from synlynk.scan import classify_workspace

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# demo\n")
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "todo.md").write_text("todo\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    # A commit is optional. Tracked init templates with no source stay greenfield.
    assert classify_workspace(str(tmp_path)) == "greenfield"


def test_write_greenfield_skeleton_has_no_symbols(tmp_path):
    import json
    from synlynk.scan import write_greenfield_skeleton

    write_greenfield_skeleton(str(tmp_path))
    graph = json.loads((tmp_path / ".synlynk" / "graphify-out" / "graph.json").read_text())
    manifest = json.loads((tmp_path / ".synlynk" / "graphify-out" / "manifest.json").read_text())
    pointer = json.loads((tmp_path / ".synlynk" / "graph.json").read_text())
    assert graph == {"nodes": [], "edges": [], "lifecycle": "greenfield"}
    assert manifest["lifecycle"] == "greenfield"
    assert manifest["built_at_commit"] == ""
    assert manifest["node_count"] == 0
    assert pointer["schema"] == 1
    assert pointer["graph"] == ".synlynk/graphify-out/graph.json"
    assert pointer["lifecycle"] == "greenfield"


def test_ensure_graph_for_head_noop_when_stamp_matches(tmp_path, monkeypatch):
    import json
    from synlynk.scan import ensure_graph_for_head

    (tmp_path / "app.py").write_text("x = 1\n")
    out = tmp_path / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text('{"nodes":[{"id":"a"}],"edges":[]}')
    (out / "manifest.json").write_text(json.dumps({
        "built_at_commit": "abc123",
        "lifecycle": "brownfield",
    }))
    monkeypatch.setattr("synlynk.discovery._get_head_commit", lambda root: "abc123")
    with patch("synlynk.scan._run_graphify_extract") as mock_extract:
        ensure_graph_for_head(str(tmp_path))
        mock_extract.assert_not_called()


def test_ensure_graph_for_head_extracts_brownfield_when_missing(tmp_path):
    from synlynk.scan import ensure_graph_for_head

    (tmp_path / "lib.ts").write_text("export const n = 1\n")
    with patch("synlynk.scan._run_graphify_extract", return_value=True) as mock_extract:
        ensure_graph_for_head(str(tmp_path))
        mock_extract.assert_called_once_with(str(tmp_path))


def test_ensure_graph_for_head_extracts_when_greenfield_stamp_on_source(tmp_path):
    import json
    from synlynk.scan import ensure_graph_for_head

    (tmp_path / "main.go").write_text("package main\n")
    out = tmp_path / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text('{"nodes":[],"edges":[],"lifecycle":"greenfield"}')
    (out / "manifest.json").write_text(json.dumps({
        "lifecycle": "greenfield",
        "built_at_commit": "",
        "node_count": 0,
    }))
    with patch("synlynk.scan._run_graphify_extract", return_value=True) as mock_extract:
        ensure_graph_for_head(str(tmp_path))
        mock_extract.assert_called_once_with(str(tmp_path))


def test_ensure_graph_for_head_writes_skeleton_for_greenfield(tmp_path):
    import json
    from synlynk.scan import ensure_graph_for_head

    with patch("synlynk.scan._run_graphify_extract") as mock_extract:
        ensure_graph_for_head(str(tmp_path))
        mock_extract.assert_not_called()
    graph = json.loads((tmp_path / ".synlynk" / "graphify-out" / "graph.json").read_text())
    assert graph["nodes"] == []
    assert graph["lifecycle"] == "greenfield"


def test_failed_extract_emits_graphify_sentinel(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNLYNK_SKIP_GRAPHIFY_EXTRACT", raising=False)
    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="extract blew up", stdout="")):
        ok = _run_graphify_extract(str(tmp_path))
    assert ok is False
    sentinel = (tmp_path / ".synlynk" / "sentinel.md").read_text()
    assert "GRAPHIFY_EXTRACT_FAILED" in sentinel
    assert "extract blew up" in sentinel


def test_cmd_scan_deep_greenfield_does_not_extract(tmp_path):
    from synlynk.scan import cmd_scan

    with patch("synlynk.scan._pkg") as mock_pkg, \
         patch("synlynk.scan._run_graphify_extract") as mock_extract, \
         patch("os.getcwd", return_value=str(tmp_path)):
        mock_pkg.side_effect = lambda name, default=None: (
            (lambda: ({}, 0, 0)) if name == "_scan_full_repo"
            else (lambda: None) if name == "_git_head_sha"
            else default
        )
        cmd_scan(deep=True)
        mock_extract.assert_not_called()
    graph = (tmp_path / ".synlynk" / "graphify-out" / "graph.json").read_text()
    assert '"lifecycle": "greenfield"' in graph or '"lifecycle":"greenfield"' in graph


def test_cmd_scan_no_flag_ensures_graph_when_not_dry_run(tmp_path, monkeypatch):
    from synlynk.scan import cmd_scan

    (tmp_path / "app.py").write_text("x = 1\n")
    monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    scan = {"workspace_name": "ws", "repos": [{"path": str(tmp_path)}]}

    def fake_pkg(name, default=None):
        if name == "run_workspace_scan":
            return lambda **kwargs: scan
        if name == "_card_summary":
            return lambda key, data: ("ok", "")
        if name == "_write_scan_fences":
            return lambda *args, **kwargs: []
        return default

    with patch("synlynk.scan._pkg", side_effect=fake_pkg), \
         patch("synlynk.scan.ensure_graph_for_head") as mock_ensure:
        cmd_scan(no_tui=True)
        mock_ensure.assert_called_once_with(str(tmp_path))

    with patch("synlynk.scan._pkg", side_effect=fake_pkg), \
         patch("synlynk.scan.ensure_graph_for_head") as mock_ensure:
        cmd_scan(dry_run=True)
        mock_ensure.assert_not_called()


def test_cmd_scan_deep_calls_run_graphify_extract(tmp_path):
    from synlynk.scan import cmd_scan

    (tmp_path / "app.py").write_text("x = 1\n")
    with patch("synlynk.scan._pkg") as mock_pkg, \
         patch("synlynk.scan._run_graphify_extract") as mock_extract, \
         patch("os.getcwd", return_value=str(tmp_path)):
        mock_pkg.side_effect = lambda name, default=None: (
            (lambda: ({}, 10, 20)) if name == "_scan_full_repo"
            else (lambda: "1234567890") if name == "_git_head_sha"
            else default
        )
        cmd_scan(deep=True)
        mock_extract.assert_called_once_with(str(tmp_path))


def test_execute_upgrade_calls_run_graphify_extract(tmp_path):
    import importlib
    upgrade_mod = importlib.import_module("synlynk.upgrade")

    with patch.object(upgrade_mod, "_run_graphify_extract") as mock_extract, \
         patch("synlynk.surface.detect_developer_surfaces", return_value=[]), \
         patch("synlynk.surface.bind_surface_rules"):
        res = upgrade_mod.execute_upgrade(str(tmp_path))
        assert res["status"] == "upgraded"
        mock_extract.assert_called_once_with(str(tmp_path))
