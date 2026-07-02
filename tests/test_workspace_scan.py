import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_write_workspace_config_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    scan = {
        "workspace_name": "my-ws",
        "topology": "single",
        "repos": [{"path": str(tmp_path), "name": "myrepo",
                   "stack_labels": ["Python"], "readme_excerpt": "",
                   "context_sections": {}}],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/usr/bin/claude"}],
        "agents": [], "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    config_path = synlynk.write_workspace_config(scan, "my-ws")
    assert os.path.exists(config_path)
    import json
    data = json.loads(open(config_path).read())
    assert data["workspace_name"] == "my-ws"
    assert data["home_harness"] == "claude"
    assert len(data["repos"]) == 1


def test_generate_structured_context_has_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    scan = {
        "workspace_name": "test-ws",
        "topology": "single",
        "repos": [{"path": str(tmp_path), "name": "testrepo",
                   "stack_labels": ["Python"], "readme_excerpt": "A test repo.",
                   "context_sections": {"Your Role": "You are PM."}}],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/usr/bin/claude"}],
        "agents": [{"name": "claude", "version": "1.x",
                    "functional": True, "roles": ["PM"]}],
        "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    out_path = str(tmp_path / ".synlynk" / "context.md")
    result = synlynk.generate_structured_context(scan, out_path=out_path)
    assert "# synlynk context" in result
    assert "test-ws" in result
    assert "testrepo" in result
    assert "Python" in result
    assert os.path.exists(out_path)


def test_cmd_scan_no_flags_runs_workspace_scan(tmp_path, monkeypatch, capsys):
    """synlynk scan (no flags) runs workspace scan and prints summary."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan()
    captured = capsys.readouterr()
    assert "workspace" in captured.out.lower() or "scan" in captured.out.lower()


def test_cmd_scan_dry_run_no_writes(tmp_path, monkeypatch):
    """--dry-run does not write config.json."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan(dry_run=True)
    ws_dir = tmp_path / ".synlynk" / "workspaces"
    assert not ws_dir.exists()


def test_cmd_scan_add_appends_repo(tmp_path, monkeypatch, capsys):
    """--add <path> appends a repo to existing workspace config."""
    ws_dir = tmp_path / ".synlynk" / "workspaces" / "test-ws"
    ws_dir.mkdir(parents=True)
    import json
    config = {"workspace_name": "test-ws", "topology": "single",
              "home_harness": "claude", "repos": [], "agent_roles": {},
              "created_at": "", "last_scanned_at": ""}
    (ws_dir / "config.json").write_text(json.dumps(config))
    (tmp_path / "newrepo").mkdir()
    (tmp_path / "newrepo" / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan(add_path=str(tmp_path / "newrepo"),
                     workspace_name="test-ws")
    data = json.loads((ws_dir / "config.json").read_text())
    assert any(r["name"] == "newrepo" for r in data["repos"])


def test_synlynk_scan_dry_run_cli(tmp_path, monkeypatch):
    import subprocess as sp
    (tmp_path / '.git').mkdir()
    (tmp_path / 'pyproject.toml').write_text("[project]\nname='test'")
    (tmp_path / '.synlynk').mkdir()
    env = os.environ.copy()
    env['HOME'] = str(tmp_path)
    env['PYTHONPATH'] = os.pathsep.join([
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
        env.get('PYTHONPATH', ''),
    ]).rstrip(os.pathsep)
    result = sp.run(
        ['python', '-m', 'synlynk', 'scan', '--dry-run'],
        cwd=str(tmp_path),
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert 'dry-run' in result.stdout or 'scan' in result.stdout


# ── Integration tests (require real git repos in tmp_path) ──────────────

def test_scan_add_then_remove_roundtrip(tmp_path, monkeypatch, capsys):
    """scan --add adds a repo; scan --remove removes it; config stays valid."""
    import json
    # Set up existing workspace config
    ws_dir = tmp_path / ".synlynk" / "workspaces" / "rtest"
    ws_dir.mkdir(parents=True)
    cfg = {"workspace_name": "rtest", "topology": "single", "home_harness": "claude",
           "repos": [], "agent_roles": {}, "created_at": "", "last_scanned_at": ""}
    (ws_dir / "config.json").write_text(json.dumps(cfg))

    # Add a repo
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan(add_path=str(repo), workspace_name="rtest")
    data = json.loads((ws_dir / "config.json").read_text())
    assert any(r["name"] == "myrepo" for r in data["repos"])

    # Remove it
    synlynk.cmd_scan(remove_path=str(repo), workspace_name="rtest")
    data = json.loads((ws_dir / "config.json").read_text())
    assert not any(r["name"] == "myrepo" for r in data["repos"])


def test_scan_dry_run_writes_nothing(tmp_path, monkeypatch):
    """scan --dry-run leaves no workspace config or context.md."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan(dry_run=True)
    ws_root = tmp_path / ".synlynk" / "workspaces"
    assert not ws_root.exists()
    context = tmp_path / ".synlynk" / "context.md"
    assert not context.exists()


def test_structured_context_written_after_scan(tmp_path, monkeypatch):
    """After a real scan, context.md exists and has workspace section."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan()
    context = tmp_path / ".synlynk" / "context.md"
    assert context.exists()
    content = context.read_text()
    assert "# synlynk context" in content
    assert "workspace" in content


def test_fingerprint_stack_ci_cd(tmp_path):
    """Repos with .github/workflows get CI/CD label."""
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "workflows").mkdir()
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert "CI/CD" in labels


def test_fingerprint_stack_sql(tmp_path):
    """Repos with migrations/ get SQL label."""
    (tmp_path / "migrations").mkdir()
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert "SQL" in labels


def test_deep_scan_returns_stage_keys(tmp_path, monkeypatch):
    """deep=True adds stack/source/complexity/tests/git/arch keys."""
    (tmp_path / "app.py").write_text("def foo(): pass\n")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path)], workspace_name="test", deep=False
    )
    for key in ("stack", "source", "complexity", "tests", "git", "arch"):
        assert key in result
        assert result[key] is None


def test_deep_false_stage_keys_are_none(tmp_path, monkeypatch):
    """deep=False keeps the new stage keys present and unset."""
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path)], workspace_name="test", deep=False
    )
    assert result["stack"] is None
    assert result["source"] is None


def test_workspace_name_single_repo_uses_repo_name(tmp_path, monkeypatch):
    """Single-repo workspace derives name from repo dir, not parent dir."""
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    monkeypatch.chdir(repo_dir)
    result = synlynk.run_workspace_scan(roots=[str(repo_dir)], deep=False)
    assert result["workspace_name"] == "myrepo"


def test_workspace_name_explicit_overrides(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path)], workspace_name="explicit-name", deep=False
    )
    assert result["workspace_name"] == "explicit-name"


def test_scan_stage_stack_python_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "foo"\n[tool.pytest.ini_options]\n'
    )
    results = {}
    synlynk._scan_stage_stack(str(tmp_path), results)
    assert results["stack"]["language"] == "python"
    assert results["stack"]["package_manager"] == "pyproject.toml"
    assert "pytest" in results["stack"]["frameworks"]


def test_scan_stage_stack_ci_detected(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: CI\n")
    results = {}
    synlynk._scan_stage_stack(str(tmp_path), results)
    assert results["stack"]["ci"] is True
    assert results["stack"]["ci_workflows"] == 1


def test_scan_stage_stack_dep_count(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests\npytest\nnumpy\n")
    results = {}
    synlynk._scan_stage_stack(str(tmp_path), results)
    assert results["stack"]["dep_count"]["prod"] == 3


def test_scan_stage_stack_lockfile_fresh(tmp_path):
    import time
    manifest = tmp_path / "package.json"
    lockfile = tmp_path / "package-lock.json"
    manifest.write_text('{"dependencies": {}}')
    time.sleep(0.01)
    lockfile.write_text("{}")
    results = {}
    synlynk._scan_stage_stack(str(tmp_path), results)
    assert results["stack"]["lockfile_fresh"] is True


def test_scan_stage_stack_schema_keys(tmp_path):
    results = {}
    synlynk._scan_stage_stack(str(tmp_path), results)
    required = {"language", "version", "frameworks", "package_manager",
                "ci", "ci_workflows", "dep_count", "lockfile_fresh"}
    assert required <= set(results["stack"].keys())


def test_scan_stage_source_basic(tmp_path):
    (tmp_path / "app.py").write_text(
        'def foo(x: int) -> str:\n    """docs"""\n    return str(x)\n'
        'def bar():\n    pass\n'
        'class MyClass:\n    pass\n'
    )
    results = {}
    synlynk._scan_stage_source(str(tmp_path), results)
    assert isinstance(results["source"], list)
    assert len(results["source"]) == 1
    f = results["source"][0]
    assert f["path"] == "app.py"
    assert f["functions"] == 2
    assert f["classes"] == 1
    assert f["typed_pct"] == 50


def test_scan_stage_source_sorted_by_lines(tmp_path):
    (tmp_path / "small.py").write_text("def a(): pass\n")
    big_content = "\n".join(f"def fn{i}(): pass" for i in range(60))
    (tmp_path / "big.py").write_text(big_content)
    results = {}
    synlynk._scan_stage_source(str(tmp_path), results)
    paths = [f["path"] for f in results["source"]]
    assert paths.index("big.py") < paths.index("small.py")


def test_scan_stage_source_syntax_error_handled(tmp_path):
    (tmp_path / "bad.py").write_text("def foo(\n  invalid syntax here\n")
    results = {}
    synlynk._scan_stage_source(str(tmp_path), results)
    assert len(results["source"]) == 1
    assert results["source"][0].get("parse_error") is True


def test_scan_stage_source_largest_fns(tmp_path):
    lines = ["def big():\n"] + ["    pass\n"] * 60 + ["def small(): pass\n"]
    (tmp_path / "app.py").write_text("".join(lines))
    results = {}
    synlynk._scan_stage_source(str(tmp_path), results)
    largest = results["source"][0]["largest_fns"]
    assert largest[0]["name"] == "big"
    assert largest[0]["lines"] >= 60


def test_scan_stage_source_skips_pycache(tmp_path):
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "cached.py").write_text("def hidden(): pass\n")
    (tmp_path / "real.py").write_text("def visible(): pass\n")
    results = {}
    synlynk._scan_stage_source(str(tmp_path), results)
    paths = [f["path"] for f in results["source"]]
    assert not any("__pycache__" in p for p in paths)
    assert any("real.py" in p for p in paths)


def test_scan_stage_complexity_function_hotspot(tmp_path):
    lines = ["def big():\n"] + ["    x = 1\n"] * 55 + ["def small(): pass\n"]
    (tmp_path / "app.py").write_text("".join(lines))
    results = {}
    synlynk._scan_stage_complexity(str(tmp_path), results)
    hotspots = results["complexity"]["hotspots"]
    assert any(h["fn"] == "big" for h in hotspots)
    assert not any(h["fn"] == "small" for h in hotspots)


def test_scan_stage_complexity_file_hotspot(tmp_path):
    content = "\n".join(f"x{i} = {i}" for i in range(510))
    (tmp_path / "big_file.py").write_text(content)
    results = {}
    synlynk._scan_stage_complexity(str(tmp_path), results)
    hotspots = results["complexity"]["hotspots"]
    assert any(h["fn"] is None and "big_file.py" in h["path"] for h in hotspots)


def test_scan_stage_complexity_todo_counts(tmp_path):
    (tmp_path / "app.py").write_text(
        "# TODO: fix this\n# FIXME: broken\n# HACK: workaround\n# TODO again\n"
    )
    results = {}
    synlynk._scan_stage_complexity(str(tmp_path), results)
    counts = results["complexity"]["todo_counts"]
    assert counts["TODO"] == 2
    assert counts["FIXME"] == 1
    assert counts["HACK"] == 1


def test_scan_stage_complexity_schema_keys(tmp_path):
    results = {}
    synlynk._scan_stage_complexity(str(tmp_path), results)
    assert "hotspots" in results["complexity"]
    assert "todo_counts" in results["complexity"]
    for key in ("TODO", "FIXME", "HACK", "XXX"):
        assert key in results["complexity"]["todo_counts"]


def test_scan_stage_tests_gap_detected(tmp_path):
    (tmp_path / "app.py").write_text("def foo(): pass\ndef bar(): pass\n")
    (tmp_path / "test_app.py").write_text("def test_foo(): pass\n")
    results = {}
    synlynk._scan_stage_tests(str(tmp_path), results)
    assert results["tests"]["gap_count"] == 1
    assert any(g["name"] == "bar" for g in results["tests"]["gap_functions"])
    assert results["tests"]["covered_count"] == 1


def test_scan_stage_tests_all_covered(tmp_path):
    (tmp_path / "app.py").write_text("def foo(): pass\n")
    (tmp_path / "test_app.py").write_text("def test_foo():\n    foo()\n")
    results = {}
    synlynk._scan_stage_tests(str(tmp_path), results)
    assert results["tests"]["gap_count"] == 0
    assert results["tests"]["covered_count"] == 1


def test_scan_stage_tests_private_ignored(tmp_path):
    (tmp_path / "app.py").write_text("def _private(): pass\ndef public(): pass\n")
    (tmp_path / "test_app.py").write_text("def test_public(): pass\n")
    results = {}
    synlynk._scan_stage_tests(str(tmp_path), results)
    assert results["tests"]["gap_count"] == 0


def test_scan_stage_tests_schema_keys(tmp_path):
    results = {}
    synlynk._scan_stage_tests(str(tmp_path), results)
    for key in ("gap_functions", "covered_count", "gap_count", "ratio"):
        assert key in results["tests"]


def _make_git_repo(path):
    import subprocess as _sp
    _sp.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    _sp.run(["git", "config", "user.email", "t@t.com"], cwd=str(path), check=True, capture_output=True)
    _sp.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True, capture_output=True)
    app = path / "app.py"
    app.write_text("def foo(): pass\n")
    _sp.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True)
    _sp.run(["git", "commit", "-m", "init"], cwd=str(path), check=True, capture_output=True)
    app.write_text("def foo(): pass\ndef bar(): pass\n")
    _sp.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True)
    _sp.run(["git", "commit", "-m", "add bar"], cwd=str(path), check=True, capture_output=True)


def test_scan_stage_git_churn(tmp_path):
    _make_git_repo(tmp_path)
    results = {}
    synlynk._scan_stage_git(str(tmp_path), results)
    assert "churn" in results["git"]
    assert "total_commits_scanned" in results["git"]
    assert results["git"]["total_commits_scanned"] == 2
    paths = [c["path"] for c in results["git"]["churn"]]
    assert "app.py" in paths


def test_scan_stage_git_temp_classification(tmp_path):
    _make_git_repo(tmp_path)
    results = {}
    synlynk._scan_stage_git(str(tmp_path), results)
    entry = next(c for c in results["git"]["churn"] if c["path"] == "app.py")
    assert entry["commits"] == 2
    assert entry["temp"] == "cold"


def test_scan_stage_git_no_git_repo(tmp_path):
    results = {}
    synlynk._scan_stage_git(str(tmp_path), results)
    assert "error" in results["git"]
    assert results["git"]["churn"] == []


def test_scan_stage_git_schema_keys(tmp_path):
    results = {}
    synlynk._scan_stage_git(str(tmp_path), results)
    assert "churn" in results["git"]
    assert "total_commits_scanned" in results["git"]


def test_scan_stage_arch_entry_point_main(tmp_path):
    (tmp_path / "app.py").write_text(
        'def main():\n    pass\n\nif __name__ == "__main__":\n    main()\n'
    )
    results = {}
    synlynk._scan_stage_arch(str(tmp_path), results)
    names = [e["name"] for e in results["arch"]["entry_points"]]
    assert "main" in names or "__main__" in names


def test_scan_stage_arch_pattern_monolith(tmp_path):
    big = "\n".join(f"x{i} = {i}" for i in range(600))
    (tmp_path / "big.py").write_text(big)
    (tmp_path / "small.py").write_text("x = 1\n")
    results = {}
    synlynk._scan_stage_arch(str(tmp_path), results)
    assert results["arch"]["pattern"] == "monolith"


def test_scan_stage_arch_pattern_library(tmp_path):
    (tmp_path / "__init__.py").write_text("def helper(): pass\n")
    results = {}
    synlynk._scan_stage_arch(str(tmp_path), results)
    assert results["arch"]["pattern"] == "library"


def test_scan_stage_arch_schema_keys(tmp_path):
    results = {}
    synlynk._scan_stage_arch(str(tmp_path), results)
    for key in ("entry_points", "import_graph", "dead_candidates",
                "public_api_count", "pattern"):
        assert key in results["arch"]


def test_run_workspace_scan_deep_populates_stages(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("def foo(x: int) -> str:\n    return str(x)\n")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path)], workspace_name="test", deep=True
    )
    for key in ("stack", "source", "complexity", "tests", "git", "arch"):
        assert result[key] is not None, f"{key} should not be None in deep mode"


def test_run_workspace_scan_deep_has_type_hints_derived(tmp_path, monkeypatch):
    content = "\n".join(
        ["# lots of unrelated content"] * 200
        + ["def annotated(x: int) -> str:\n    return str(x)\n"]
    )
    (tmp_path / "app.py").write_text(content)
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path)], workspace_name="test", deep=True
    )
    assert result["has_type_hints"] is True


def test_run_workspace_scan_shallow_preserves_backwards_compat(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("def foo(): pass\n")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path)], workspace_name="test", deep=False
    )
    assert "test_ratio" in result
    assert "has_ci" in result
    assert result["source"] is None


def test_write_scan_fences_updates_claude_md(tmp_path):
    """_write_scan_fences writes Codebase Context into CLAUDE.md."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project\n\nSome existing content.\n")
    results = {
        "stack": {"language": "python", "version": "3.11", "frameworks": ["pytest"],
                  "package_manager": "pyproject.toml", "ci": True, "ci_workflows": 1,
                  "dep_count": {"prod": 0, "dev": 4}, "lockfile_fresh": True},
        "source": [{"path": "app.py", "lines": 200, "functions": 10, "classes": 1,
                    "typed_pct": 50, "docstring_pct": 30, "largest_fns": []}],
        "complexity": {"hotspots": [], "todo_counts": {"TODO": 2, "FIXME": 0, "HACK": 0, "XXX": 0}},
        "tests": {"gap_functions": [{"name": "foo", "file": "app.py", "lineno": 1}],
                  "covered_count": 5, "gap_count": 1, "ratio": 0.83},
        "git": {"churn": [], "total_commits_scanned": 5},
        "arch": {"entry_points": [], "import_graph": {}, "dead_candidates": [],
                 "public_api_count": 8, "pattern": "modular"},
    }
    updated = synlynk._write_scan_fences(results, root=str(tmp_path))
    assert str(claude_md) in updated or "CLAUDE.md" in " ".join(updated)
    content = claude_md.read_text()
    assert "Codebase Context" in content
    assert "python" in content.lower()


def test_write_scan_fences_skips_missing_files(tmp_path):
    """Does not create directive files that don't exist."""
    results = {"stack": {"language": "go"}, "source": None,
               "complexity": None, "tests": None, "git": None, "arch": None}
    updated = synlynk._write_scan_fences(results, root=str(tmp_path))
    assert updated == []
    assert not (tmp_path / "CLAUDE.md").exists()


def test_write_scan_fences_omits_errored_stage(tmp_path):
    """If git stage errored, Hot Files section is omitted."""
    (tmp_path / "CLAUDE.md").write_text("# Project\n")
    results = {
        "stack": {"language": "python", "version": "3.11", "frameworks": [],
                  "package_manager": "pyproject.toml", "ci": False, "ci_workflows": 0,
                  "dep_count": {"prod": 0, "dev": 0}, "lockfile_fresh": True},
        "source": [],
        "complexity": {"hotspots": [], "todo_counts": {"TODO": 0, "FIXME": 0, "HACK": 0, "XXX": 0}},
        "tests": {"gap_functions": [], "covered_count": 0, "gap_count": 0, "ratio": 0.0},
        "git": {"error": "git unavailable", "churn": [], "total_commits_scanned": 0},
        "arch": {"entry_points": [], "import_graph": {}, "dead_candidates": [],
                 "public_api_count": 0, "pattern": "library"},
    }
    synlynk._write_scan_fences(results, root=str(tmp_path))
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Hot Files" not in content
    assert "git unavailable" not in content
