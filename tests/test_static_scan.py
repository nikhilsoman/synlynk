# tests/test_static_scan.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import synlynk


# --- _extract_symbols ---

def test_extract_python_symbols(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(
        "import os\n"
        "MY_CONST = 1\n"
        "class Foo:\n"
        "    pass\n"
        "def bar():\n"
        "    pass\n"
        "async def baz():\n"
        "    pass\n"
    )
    syms = synlynk._extract_symbols(str(f))
    types = {s["symbol_type"] for s in syms}
    names = {s["symbol"] for s in syms}
    assert "constant" in types
    assert "class" in types
    assert "function" in types
    assert "async_function" in types
    assert "Foo" in names
    assert "bar" in names
    assert "baz" in names
    assert "MY_CONST" in names


def test_extract_typescript_symbols(tmp_path):
    f = tmp_path / "service.ts"
    f.write_text(
        "export class AuthService {}\n"
        "export function verifyToken(t: string) {}\n"
        "export interface TokenPayload {}\n"
        "export type UserId = string;\n"
        "export enum Role { Admin, User }\n"
        "export const DB_URL = '';\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    types = {s["symbol_type"] for s in syms}
    assert "AuthService" in names
    assert "verifyToken" in names
    assert "TokenPayload" in names
    assert "UserId" in names
    assert "Role" in names
    assert "DB_URL" in names
    assert "interface" in types
    assert "type" in types
    assert "enum" in types


def test_extract_go_symbols(tmp_path):
    f = tmp_path / "main.go"
    f.write_text(
        "package main\n"
        "func main() {}\n"
        "type Server struct{}\n"
        "type Handler interface{}\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    types = {s["symbol_type"] for s in syms}
    assert "main" in names
    assert "Server" in names
    assert "Handler" in names
    assert "function" in types
    assert "struct" in types
    assert "interface" in types


def test_extract_rust_symbols(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text(
        "pub fn connect() {}\n"
        "pub struct Config {}\n"
        "pub trait Adapter {}\n"
        "pub enum State { Active, Idle }\n"
        "pub type Result<T> = std::result::Result<T, Error>;\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "connect" in names
    assert "Config" in names
    assert "Adapter" in names
    assert "State" in names
    assert "Result" in names


def test_extract_shell_symbols(tmp_path):
    f = tmp_path / "deploy.sh"
    f.write_text(
        "#!/bin/bash\n"
        "setup_env() {\n"
        "  echo hi\n"
        "}\n"
        "run_deploy() {}\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "setup_env" in names
    assert "run_deploy" in names


def test_extract_generic_returns_empty(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("col1,col2\n1,2\n")
    syms = synlynk._extract_symbols(str(f))
    assert syms == []


def test_extract_max_300_lines(tmp_path):
    # Lines 1-298: filler assignments
    lines = [f"x_{i} = {i}" for i in range(298)]
    # Line 299: def within limit — must be found
    lines.append("def within_limit():")
    lines.append("    pass")
    # Line 301: def beyond limit — must NOT be found
    lines.append("def beyond_limit():")
    lines.append("    pass")
    f = tmp_path / "big.py"
    f.write_text("\n".join(lines) + "\n")
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "within_limit" in names
    assert "beyond_limit" not in names


def test_extract_shell_function_keyword(tmp_path):
    f = tmp_path / "build.sh"
    f.write_text(
        "#!/bin/bash\n"
        "function build_release() {\n"
        "  echo building\n"
        "}\n"
        "cleanup() {}\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "build_release" in names
    assert "cleanup" in names


def test_extract_missing_file_returns_empty():
    syms = synlynk._extract_symbols("/nonexistent/path/file.py")
    assert syms == []


def test_extract_line_numbers(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("class Alpha:\n    pass\ndef beta():\n    pass\n")
    syms = synlynk._extract_symbols(str(f))
    by_name = {s["symbol"]: s["line"] for s in syms}
    assert by_name["Alpha"] == 1
    assert by_name["beta"] == 3


# --- _git_head_sha ---

def test_git_head_sha_returns_string_or_none():
    sha = synlynk._git_head_sha()
    # In the synlynk repo with commits this should return a 40-char hex string
    assert sha is None or (isinstance(sha, str) and len(sha) == 40)


def test_git_head_sha_no_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sha = synlynk._git_head_sha()
    assert sha is None


# --- _load_scan_meta / _save_scan_meta ---

def test_scan_meta_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    skeleton = [{"file": "app.py", "language": "python", "symbols": ["main()"]}]
    synlynk._save_scan_meta("abc1234", skeleton)
    meta = synlynk._load_scan_meta()
    assert meta is not None
    assert meta["head_sha"] == "abc1234"
    assert meta["skeleton"] == skeleton
    assert meta["schema_version"] == 1
    assert "scanned_at" in meta


def test_load_scan_meta_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    assert synlynk._load_scan_meta() is None


def test_load_scan_meta_corrupt_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "scan-meta.json").write_text("not json{{")
    assert synlynk._load_scan_meta() is None


def test_save_scan_meta_creates_synlynk_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # .synlynk does NOT exist yet
    synlynk._save_scan_meta("deadbeef", [])
    assert (tmp_path / ".synlynk" / "scan-meta.json").exists()


def test_save_scan_meta_preserves_deep_on_resave(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    deep = {"total_files": 47, "total_symbols": 312, "scanned_at": "2026-06-17T21:00:00"}
    synlynk._save_scan_meta("sha1" + "0" * 36, [], deep=deep)
    # Re-save without deep — deep should be preserved from existing meta
    synlynk._save_scan_meta("sha2" + "0" * 36, [{"file": "app.py", "language": "python", "symbols": []}])
    meta = synlynk._load_scan_meta()
    assert meta["deep"] == deep


# --- _scan_source_skeleton ---

def _make_source_tree(root):
    """Helper: creates a minimal source tree for skeleton tests."""
    (root / "main.py").write_text("def main():\n    pass\n")
    src = root / "src"
    src.mkdir()
    (src / "utils.py").write_text("def helper():\n    pass\n")
    deep = root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "buried.py").write_text("def deep_func():\n    pass\n")
    (root / ".synlynk").mkdir(exist_ok=True)
    (root / "project-docs").mkdir(exist_ok=True)


def test_skeleton_returns_at_most_15_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create 20 .py files
    for i in range(20):
        (tmp_path / f"mod_{i}.py").write_text(f"def func_{i}():\n    pass\n")
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    assert len(skeleton) <= 15


def test_skeleton_entry_point_scored_higher(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_source_tree(tmp_path)
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    files = [e["file"] for e in skeleton]
    # main.py is an entry point (+3) so it should appear in skeleton
    assert any("main.py" in f for f in files)


def test_skeleton_skips_scan_skip_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("function x(){}")
    (tmp_path / "app.py").write_text("def main(): pass\n")
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    files = [e["file"] for e in skeleton]
    assert not any("node_modules" in f for f in files)


def test_skeleton_depth_penalty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Entry point at depth 0 vs same-name file deeply nested
    (tmp_path / "index.js").write_text("function main(){}")
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "index.js").write_text("function main(){}")
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    files = [e["file"] for e in skeleton]
    # Root index.js should appear before the deeply nested one
    root_idx = next((i for i, f in enumerate(files) if f == "index.js"), None)
    deep_idx = next((i for i, f in enumerate(files) if "a/b/c/d" in f), None)
    if root_idx is not None and deep_idx is not None:
        assert root_idx < deep_idx


def test_skeleton_symbols_capped_at_8(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lines = "\n".join(f"def func_{i}(): pass" for i in range(20))
    (tmp_path / "big.py").write_text(lines + "\n")
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    entry = next((e for e in skeleton if "big.py" in e["file"]), None)
    assert entry is not None
    assert len(entry["symbols"]) <= 8


def test_skeleton_language_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("def main(): pass\n")
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    entry = next((e for e in skeleton if "app.py" in e["file"]), None)
    assert entry is not None
    assert entry["language"] == "python"


def test_skeleton_empty_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skeleton = synlynk._scan_source_skeleton(str(tmp_path))
    assert skeleton == []


# --- source_symbols DB table ---

def test_source_symbols_table_created(isolated_db):
    conn = synlynk._get_db()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='source_symbols'"
    )
    assert cursor.fetchone() is not None


def test_source_symbols_schema(isolated_db):
    conn = synlynk._get_db()
    cursor = conn.execute("PRAGMA table_info(source_symbols)")
    cols = {row[1] for row in cursor.fetchall()}
    assert cols == {"id", "head_sha", "file", "language", "symbol", "symbol_type", "line", "scanned_at"}


# --- _scan_full_repo ---

def test_scan_full_repo_writes_source_map(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "app.py").write_text("def main():\n    pass\nclass App:\n    pass\n")
    (tmp_path / "utils.py").write_text("def helper():\n    pass\n")
    skeleton, total_files, total_syms = synlynk._scan_full_repo(str(tmp_path))
    source_map = tmp_path / "project-docs" / "source-map.md"
    assert source_map.exists()
    content = source_map.read_text()
    assert "# Source Map" in content
    assert "app.py" in content
    assert "main()" in content


def test_scan_full_repo_populates_db(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "app.py").write_text("def alpha():\n    pass\ndef beta():\n    pass\n")
    synlynk._scan_full_repo(str(tmp_path))
    conn = synlynk._get_db()
    rows = conn.execute("SELECT symbol FROM source_symbols").fetchall()
    names = {r[0] for r in rows}
    assert "alpha" in names
    assert "beta" in names


def test_scan_full_repo_returns_counts(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "app.py").write_text("def a():\n    pass\ndef b():\n    pass\n")
    skeleton, total_files, total_syms = synlynk._scan_full_repo(str(tmp_path))
    assert total_files >= 1
    assert total_syms >= 2


def test_scan_full_repo_clears_stale_db_rows(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "app.py").write_text("def func_a():\n    pass\n")
    # Insert a stale row with a different head_sha
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, scanned_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        ("old_sha", "old.py", "python", "stale_func", "function", "2026-01-01T00:00:00"),
    )
    conn.commit()
    synlynk._scan_full_repo(str(tmp_path))
    rows = conn.execute("SELECT symbol FROM source_symbols WHERE symbol='stale_func'").fetchall()
    assert rows == []


def test_scan_full_repo_source_map_format(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "svc.py").write_text("class Service:\n    pass\ndef connect():\n    pass\n")
    synlynk._scan_full_repo(str(tmp_path))
    content = (tmp_path / "project-docs" / "source-map.md").read_text()
    assert "HEAD:" in content
    assert "svc.py" in content
    assert "Service" in content
    assert "connect()" in content


# --- _check_scan_cache ---

def test_check_scan_cache_returns_cached_on_sha_match(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    skeleton_saved = [{"file": "app.py", "language": "python", "symbols": ["main()"]}]
    fake_sha = "a" * 40
    synlynk._save_scan_meta(fake_sha, skeleton_saved)
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    result = synlynk._check_scan_cache(str(tmp_path))
    assert result == skeleton_saved


def test_check_scan_cache_rescans_on_sha_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def fresh_func(): pass\n")
    stale = [{"file": "old.py", "language": "python", "symbols": ["stale()"]}]
    synlynk._save_scan_meta("old_sha_" + "0" * 32, stale)
    new_sha = "b" * 40
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: new_sha)
    result = synlynk._check_scan_cache(str(tmp_path))
    files = [e["file"] for e in result]
    assert any("app.py" in f for f in files)


def test_check_scan_cache_no_git_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: None)
    result = synlynk._check_scan_cache(str(tmp_path))
    assert result == []


def test_check_scan_cache_no_meta_triggers_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "svc.py").write_text("class Service: pass\n")
    fake_sha = "c" * 40
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    result = synlynk._check_scan_cache(str(tmp_path))
    assert any("svc.py" in e["file"] for e in result)
    meta = synlynk._load_scan_meta()
    assert meta is not None
    assert meta["head_sha"] == fake_sha


# --- context injection ---

def test_generate_context_includes_source_architecture(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "todo.md").write_text("# Todo\n")
    (tmp_path / "project-docs" / "roadmap.md").write_text("# Roadmap\n")
    (tmp_path / "project-docs" / "memory.md").write_text("# Memory\n")
    (tmp_path / "project-docs" / ".synlynk_config.json").write_text('{"mode":"single"}')
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    fake_sha = "d" * 40
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    synlynk.generate_context()
    ctx = (tmp_path / ".synlynk" / "context.md").read_text()
    assert "## Source Architecture" in ctx


def test_generate_context_omits_source_architecture_without_git(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "todo.md").write_text("# Todo\n")
    (tmp_path / "project-docs" / "roadmap.md").write_text("# Roadmap\n")
    (tmp_path / "project-docs" / "memory.md").write_text("# Memory\n")
    (tmp_path / "project-docs" / ".synlynk_config.json").write_text('{"mode":"single"}')
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: None)
    synlynk.generate_context()
    ctx = (tmp_path / ".synlynk" / "context.md").read_text()
    assert "## Source Architecture" not in ctx


def test_generate_context_source_architecture_before_roadmap(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "todo.md").write_text("# Todo\n- [ ] Task one\n")
    (tmp_path / "project-docs" / "roadmap.md").write_text(
        "# Roadmap\n| Priority | Feature | Description | Status | Target Release | Owner |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| P0 | X | Y | In Progress | v1.0 | Z |\n"
    )
    (tmp_path / "project-docs" / "memory.md").write_text("# Memory\n")
    (tmp_path / "project-docs" / ".synlynk_config.json").write_text('{"mode":"single"}')
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    fake_sha = "e" * 40
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    synlynk.generate_context()
    ctx = (tmp_path / ".synlynk" / "context.md").read_text()
    arch_pos = ctx.find("## Source Architecture")
    roadmap_pos = ctx.find("## Roadmap")
    assert arch_pos != -1
    assert roadmap_pos != -1
    assert arch_pos < roadmap_pos


def test_format_source_architecture_groups_by_dir():
    skeleton = [
        {"file": "src/auth/service.py", "language": "python", "symbols": ["AuthService", "login()"]},
        {"file": "src/auth/models.py", "language": "python", "symbols": ["User"]},
        {"file": "main.py", "language": "python", "symbols": ["main()"]},
    ]
    out = synlynk._format_source_architecture(skeleton, "abc1234", cache_hit=True, total_files=5)
    assert "### src/auth/" in out
    assert "### [root]/" in out
    assert "cache hit" in out
    # 2 more files (total_files=5, skeleton has 3)
    assert "2 more" in out


def test_format_source_architecture_empty_returns_empty():
    out = synlynk._format_source_architecture([], "abc1234", cache_hit=True)
    assert out == ""
