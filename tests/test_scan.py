import os
import synlynk
import synlynk.scan as scan


def test_grok_agent_file_is_registered_and_detected(tmp_path):
    assert "GROK.md" in synlynk._AGENT_FILE_NAMES
    assert "GROK.md" in scan._AGENT_FILE_NAMES

    grok_file = tmp_path / "GROK.md"
    grok_file.write_text("# Grok instructions\n")

    result = scan._scan_repo_for_docs(str(tmp_path))

    assert result["agent_files"]["GROK.md"] == str(grok_file)


def test_scan_skip_names_includes_worktrees_and_synlynk():
    assert "worktrees" in scan._SCAN_SKIP_NAMES
    assert ".worktrees" in scan._SCAN_SKIP_NAMES
    assert ".synlynk" in scan._SCAN_SKIP_NAMES


def test_scan_stages_exclude_worktrees_and_synlynk(tmp_path):
    root = str(tmp_path)

    # 1. Root python file
    main_py = tmp_path / "main_app.py"
    main_py.write_text("def app_func():\n    # TODO: root todo\n    return 42\n")

    # 2. File in worktrees/ directory
    wt_dir = tmp_path / "worktrees" / "sub_branch"
    wt_dir.mkdir(parents=True)
    wt_py = wt_dir / "wt_app.py"
    wt_py.write_text("def wt_func():\n    # TODO: worktree todo\n    return 99\n")

    # 3. File in .synlynk/ directory
    synlynk_dir = tmp_path / ".synlynk" / "internal"
    synlynk_dir.mkdir(parents=True)
    synlynk_py = synlynk_dir / "internal_tool.py"
    synlynk_py.write_text("def tool_func():\n    # TODO: synlynk todo\n    return 100\n")

    # Test Stage 2: source scan
    results = {}
    scan._scan_stage_source(root, results)
    scanned_files = [f["path"] for f in results["source"]]
    assert "main_app.py" in scanned_files
    assert not any("worktrees" in f for f in scanned_files)
    assert not any(".synlynk" in f for f in scanned_files)

    # Test Stage 3: complexity scan
    results = {}
    scan._scan_stage_complexity(root, results)
    assert results["complexity"]["todo_counts"]["TODO"] == 1

    # Test Stage 4: test gaps scan
    results = {}
    scan._scan_stage_tests(root, results)
    gap_funcs = [g["name"] for g in results["tests"]["gap_functions"]]
    assert "app_func" in gap_funcs
    assert "wt_func" not in gap_funcs
    assert "tool_func" not in gap_funcs

    # Test Stage 6: arch scan
    results = {}
    scan._scan_stage_arch(root, results)
    entry_files = [ep["file"] for ep in results["arch"]["entry_points"]]
    assert not any("worktrees" in f for f in entry_files)
    assert not any(".synlynk" in f for f in entry_files)

