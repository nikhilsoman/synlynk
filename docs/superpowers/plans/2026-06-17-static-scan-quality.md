# Static Scan Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a language-agnostic source scanner that injects a `## Source Architecture` section (top-15 prioritized files + symbols) into every `synlynk exec` context, persisted in SQLite and cached in `.synlynk/scan-meta.json`.

**Architecture:** Three layers — a symbol-extraction regex engine per language, a file-scoring/skeleton builder (top-15 by git activity + entry-point bonus − depth penalty), and a passive cache keyed on `git rev-parse HEAD` that runs inside `generate_context()`. A `synlynk scan --deep` command does a full tree walk, populates `state.db:source_symbols`, and materialises `project-docs/source-map.md`. All logic stays in `bin/synlynk.py` — zero new pip dependencies.

**Tech Stack:** Python 3 stdlib only (`re`, `os`, `subprocess`, `json`, `sqlite3`, `time`). `re` is already imported at module level.

---

## Worktree

Create branch `feat/v0.7.0-static-scan-quality` from `main` before starting:
```bash
cd ~/dev/synlynk
git checkout main && git pull
git worktree add .worktrees/feat+v0.7.0-static-scan-quality -b feat/v0.7.0-static-scan-quality
cd .worktrees/feat+v0.7.0-static-scan-quality
```

All tasks execute in `.worktrees/feat+v0.7.0-static-scan-quality/`.

---

## File Map

| File | Action | Sections changed |
|---|---|---|
| `bin/synlynk.py` | Modify | `_SCAN_SKIP_DIRS` (extend), `_DB_SCHEMA` (add table), `generate_context()` (inject section), `main()` (add `scan` subparser) |
| `bin/synlynk.py` | Add new constants | `_SOURCE_EXTENSIONS`, `_SOURCE_ENTRY_POINTS`, `_SYMBOL_PATTERNS` after `_SCAN_SKIP_DIRS` |
| `bin/synlynk.py` | Add new functions | `_extract_symbols`, `_git_head_sha`, `_load_scan_meta`, `_save_scan_meta`, `_score_source_files`, `_scan_source_skeleton`, `_scan_full_repo`, `_check_scan_cache`, `_format_source_architecture`, `cmd_scan` |
| `tests/test_static_scan.py` | Create | All new tests |

---

## Task 1: Symbol extraction engine

**Files:**
- Modify: `bin/synlynk.py` — add constants after `_SCAN_SKIP_DIRS` (around line 1352), add `_extract_symbols()` function
- Create: `tests/test_static_scan.py`

- [ ] **Step 1: Create test file with failing symbol-extraction tests**

```python
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
    lines = [f"def func_{i}():\n    pass\n" for i in range(200)]
    # Put 5 defs before line 300 cutoff and 5 after
    content = "\n".join(f"x = {i}" for i in range(295)) + "\n"
    content += "def visible():\n    pass\n"
    # This ensures we have a def at line 296, within 300
    f = tmp_path / "big.py"
    f.write_text(content)
    syms = synlynk._extract_symbols(str(f))
    # Should include visible() since it's within 300 lines
    names = {s["symbol"] for s in syms}
    assert "visible" in names


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_static_scan.py -v 2>&1 | head -30
```
Expected: `AttributeError: module 'synlynk' has no attribute '_extract_symbols'`

- [ ] **Step 3: Add `_SOURCE_EXTENSIONS`, `_SOURCE_ENTRY_POINTS`, `_SYMBOL_PATTERNS` constants to `bin/synlynk.py`**

Find the `_SCAN_SKIP_DIRS` block (around line 1352) and add the following immediately after it:

```python
_SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".sh": "shell",
}

_SOURCE_ENTRY_POINTS = {
    "main.py", "app.py", "server.py", "index.js", "index.ts", "main.go",
    "lib.rs", "main.rs", "app.rb", "manage.py", "wsgi.py", "asgi.py", "__init__.py",
}

_SYMBOL_PATTERNS = {
    "python": [
        (re.compile(r"^async def (\w+)"), "async_function"),
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^([A-Z_]{2,})\s*="), "constant"),
    ],
    "javascript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "typescript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export interface (\w+)"), "interface"),
        (re.compile(r"^export type (\w+)"), "type"),
        (re.compile(r"^export enum (\w+)"), "enum"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "go": [
        (re.compile(r"^func (?:\(\w+ \*?\w+\) )?(\w+)"), "function"),
        (re.compile(r"^type (\w+) struct"), "struct"),
        (re.compile(r"^type (\w+) interface"), "interface"),
    ],
    "rust": [
        (re.compile(r"^pub fn (\w+)"), "function"),
        (re.compile(r"^pub struct (\w+)"), "struct"),
        (re.compile(r"^pub trait (\w+)"), "trait"),
        (re.compile(r"^pub enum (\w+)"), "enum"),
        (re.compile(r"^pub type (\w+)"), "type"),
    ],
    "ruby": [
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^module (\w+)"), "module"),
    ],
    "java": [
        (re.compile(r"(?:public|protected) (?:class|interface|enum) (\w+)"), "class"),
        (re.compile(r"(?:public|protected) \w+ (\w+)\s*\("), "function"),
    ],
    "kotlin": [
        (re.compile(r"^fun (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^object (\w+)"), "class"),
        (re.compile(r"^interface (\w+)"), "interface"),
    ],
    "shell": [
        (re.compile(r"^(\w+)\(\)"), "function"),
    ],
}
```

- [ ] **Step 4: Add `_extract_symbols()` function to `bin/synlynk.py`**

Add immediately after the `_SYMBOL_PATTERNS` constant:

```python
def _extract_symbols(file_path: str) -> list:
    """Returns [{"symbol": str, "symbol_type": str, "line": int}] from file_path.

    Reads at most 300 lines. Returns [] for unknown extensions or unreadable files.
    """
    ext = os.path.splitext(file_path)[1].lower()
    lang = _SOURCE_EXTENSIONS.get(ext)
    if not lang:
        return []
    patterns = _SYMBOL_PATTERNS.get(lang, [])
    if not patterns:
        return []
    results = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, 1):
                if lineno > 300:
                    break
                for pattern, sym_type in patterns:
                    m = pattern.match(line)
                    if m:
                        results.append({
                            "symbol": m.group(1),
                            "symbol_type": sym_type,
                            "line": lineno,
                        })
                        break
    except (OSError, IOError):
        pass
    return results
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "extract"
```
Expected: all 9 `test_extract_*` tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: symbol extraction engine for static scan quality"
```

---

## Task 2: Git HEAD SHA + cache I/O

**Files:**
- Modify: `bin/synlynk.py` — add `_git_head_sha()`, `_load_scan_meta()`, `_save_scan_meta()` after `_extract_symbols()`
- Modify: `tests/test_static_scan.py` — add cache I/O tests

- [ ] **Step 1: Add cache I/O tests to `tests/test_static_scan.py`**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "head_sha or scan_meta" 2>&1 | head -20
```
Expected: `AttributeError: module 'synlynk' has no attribute '_git_head_sha'`

- [ ] **Step 3: Add the three functions to `bin/synlynk.py` after `_extract_symbols()`**

```python
def _git_head_sha() -> Optional[str]:
    """Returns the full SHA of HEAD, or None if not in a git repo or no commits."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha if len(sha) == 40 else None
    except FileNotFoundError:
        pass
    return None


def _load_scan_meta() -> Optional[dict]:
    """Reads .synlynk/scan-meta.json. Returns None if absent or malformed."""
    path = os.path.join(".synlynk", "scan-meta.json")
    if not os.path.exists(path):
        return None
    try:
        return json.loads(open(path).read())
    except (ValueError, OSError):
        return None


def _save_scan_meta(head_sha: str, skeleton: list, deep: Optional[dict] = None) -> None:
    """Writes skeleton + metadata to .synlynk/scan-meta.json."""
    os.makedirs(".synlynk", exist_ok=True)
    meta = {
        "schema_version": 1,
        "head_sha": head_sha,
        "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_count": len(skeleton),
        "skeleton": skeleton,
    }
    if deep is not None:
        meta["deep"] = deep
    elif _load_scan_meta() and _load_scan_meta().get("deep"):
        meta["deep"] = _load_scan_meta()["deep"]
    with open(os.path.join(".synlynk", "scan-meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "head_sha or scan_meta"
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: git HEAD SHA resolver and scan-meta.json cache I/O"
```

---

## Task 3: File scoring and skeleton builder

**Files:**
- Modify: `bin/synlynk.py` — extend `_SCAN_SKIP_DIRS`, add `_score_source_files()`, `_scan_source_skeleton()`
- Modify: `tests/test_static_scan.py` — add skeleton tests

- [ ] **Step 1: Add skeleton tests to `tests/test_static_scan.py`**

```python
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
    # main.py is an entry point (+3) so it should appear before src/utils.py
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "skeleton" 2>&1 | head -20
```
Expected: `AttributeError: module 'synlynk' has no attribute '_scan_source_skeleton'`

- [ ] **Step 3: Extend `_SCAN_SKIP_DIRS` in `bin/synlynk.py`**

Find the existing `_SCAN_SKIP_DIRS` definition (the set starting with `".git", "node_modules"`) and replace it:

```python
_SCAN_SKIP_DIRS = {
    ".git", "node_modules", ".synlynk", "project-docs",
    "__pycache__", ".venv", "venv", "env", ".next", "dist", "build",
    "vendor", ".worktrees", "coverage", ".nyc_output", "target", "out", "tmp",
}
```

- [ ] **Step 4: Add `_score_source_files()` and `_scan_source_skeleton()` to `bin/synlynk.py`**

Add after `_save_scan_meta()`:

```python
def _score_source_files(root: str = ".") -> list:
    """Returns [(score, rel_path), ...] for all source files, sorted score descending.

    Scoring: +3 if filename is a known entry point, +1 per appearance in last-50
    git commits, -1 per directory level beyond 2.
    """
    # Collect git activity: count file appearances in last 50 commits
    git_counts: dict = {}
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "-50"],
            capture_output=True, text=True, cwd=root,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    git_counts[line] = git_counts.get(line, 0) + 1
    except FileNotFoundError:
        pass

    scored = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SOURCE_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            # Depth = number of directory separators
            depth = rel_path.count(os.sep)
            # Entry point bonus: filename match OR cmd/main.go path
            entry_bonus = 3 if (fname in _SOURCE_ENTRY_POINTS or rel_path in ("cmd/main.go",)) else 0
            git_score = git_counts.get(rel_path, 0)
            depth_penalty = max(0, depth - 2)
            score = entry_bonus + git_score - depth_penalty
            scored.append((score, rel_path))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored


def _scan_source_skeleton(root: str = ".") -> list:
    """Top-15 prioritised files with up to 8 symbols each.

    Returns list of {"file": str, "language": str, "symbols": [str]} where
    symbols are display strings ("name()" for functions, "name" for others).
    """
    scored = _score_source_files(root)
    top = scored[:15]
    skeleton = []
    for _score, rel_path in top:
        ext = os.path.splitext(rel_path)[1].lower()
        lang = _SOURCE_EXTENSIONS.get(ext, "generic")
        abs_path = os.path.join(root, rel_path)
        raw_syms = _extract_symbols(abs_path)[:8]
        display_syms = []
        for s in raw_syms:
            name = s["symbol"]
            if s["symbol_type"] in ("function", "async_function"):
                display_syms.append(f"{name}()")
            else:
                display_syms.append(name)
        skeleton.append({"file": rel_path, "language": lang, "symbols": display_syms})
    return skeleton
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "skeleton or score"
```
Expected: all skeleton tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: file scoring and top-15 skeleton builder"
```

---

## Task 4: `source_symbols` DB table migration

**Files:**
- Modify: `bin/synlynk.py` — append `source_symbols` DDL to `_DB_SCHEMA`
- Modify: `tests/test_static_scan.py` — add migration test

- [ ] **Step 1: Add migration test**

```python
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
```

Note: `isolated_db` is autouse in `conftest.py` so these tests automatically use an isolated DB at `tmp_path / "state.db"`.

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "source_symbols" 2>&1 | head -20
```
Expected: assertion fails — table does not exist yet.

- [ ] **Step 3: Append `source_symbols` DDL to `_DB_SCHEMA` in `bin/synlynk.py`**

Find the `_DB_SCHEMA = """` string (around line 45). Add before the closing `"""`:

```sql

CREATE TABLE IF NOT EXISTS source_symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    head_sha    TEXT NOT NULL,
    file        TEXT NOT NULL,
    language    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    line        INTEGER,
    scanned_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_symbols_head ON source_symbols(head_sha);
CREATE INDEX IF NOT EXISTS idx_source_symbols_file ON source_symbols(file);
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "source_symbols"
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: source_symbols DB table and indexes"
```

---

## Task 5: Deep scan (`_scan_full_repo`)

**Files:**
- Modify: `bin/synlynk.py` — add `_scan_full_repo()` after `_scan_source_skeleton()`
- Modify: `tests/test_static_scan.py` — add deep scan tests

- [ ] **Step 1: Add deep scan tests**

```python
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
    # First scan with fake sha
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, scanned_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        ("old_sha", "old.py", "python", "stale_func", "function", "2026-01-01"),
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
    # Should have HEAD sha line, file entry, symbol list
    assert "HEAD:" in content
    assert "svc.py" in content
    assert "Service" in content
    assert "connect()" in content
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "full_repo" 2>&1 | head -20
```
Expected: `AttributeError: module 'synlynk' has no attribute '_scan_full_repo'`

- [ ] **Step 3: Add `_scan_full_repo()` to `bin/synlynk.py` after `_scan_source_skeleton()`**

```python
def _scan_full_repo(root: str = ".") -> tuple:
    """Deep scan: extracts all symbols, writes DB + project-docs/source-map.md.

    Returns (skeleton, total_files, total_symbols).
    Clears rows for any SHA != current HEAD before inserting.
    """
    head_sha = _git_head_sha() or "unknown"
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    all_entries = []  # {"file": str, "language": str, "symbols": [raw_dict]}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SOURCE_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            lang = _SOURCE_EXTENSIONS[ext]
            raw_syms = _extract_symbols(abs_path)
            all_entries.append({"file": rel_path, "language": lang, "symbols": raw_syms})

    total_files = len(all_entries)
    total_syms = sum(len(e["symbols"]) for e in all_entries)

    # Write DB
    try:
        conn = _get_db()
        conn.execute("DELETE FROM source_symbols WHERE head_sha != ?", (head_sha,))
        rows = []
        for entry in all_entries:
            for sym in entry["symbols"]:
                rows.append((
                    head_sha, entry["file"], entry["language"],
                    sym["symbol"], sym["symbol_type"], sym.get("line"), now,
                ))
        conn.executemany(
            "INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, line, scanned_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception as e:
        print(f"  ⚠ source_symbols DB write failed: {e}")

    # Write project-docs/source-map.md
    source_map_path = os.path.join("project-docs", "source-map.md")
    try:
        os.makedirs("project-docs", exist_ok=True)
        sha_short = head_sha[:7] if head_sha != "unknown" else "unknown"
        lines = [
            "# Source Map",
            f"_Generated: {now} · HEAD: {sha_short} · {total_files} files_",
            "",
        ]
        # Group by directory
        groups: dict = {}
        for entry in sorted(all_entries, key=lambda e: e["file"]):
            dirname = os.path.dirname(entry["file"])
            groups.setdefault(dirname, []).append(entry)

        for dirname, entries in sorted(groups.items()):
            lang_counts: dict = {}
            for e in entries:
                lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
            lang_str = ", ".join(
                f"{lg} · {cnt}" for lg, cnt in sorted(lang_counts.items())
            )
            label = dirname if dirname else "[root]"
            lines.append(f"## {label}/  [{lang_str}]")
            for entry in entries:
                sym_count = len(entry["symbols"])
                lines.append(f"`{entry['file']}` · {sym_count} symbols")
                display_parts = []
                for s in entry["symbols"]:
                    name = s["symbol"]
                    disp = f"{name}()" if s["symbol_type"] in ("function", "async_function") else name
                    disp += f" [{s['symbol_type']}:{s.get('line', '?')}]"
                    display_parts.append(disp)
                if display_parts:
                    lines.append("  " + ", ".join(display_parts))
                lines.append("")

        with open(source_map_path, "w") as fh:
            fh.write("\n".join(lines))
    except OSError as e:
        print(f"  ⚠ source-map.md write failed: {e}")

    # Build and persist skeleton
    skeleton = _scan_source_skeleton(root)
    deep_meta = {"total_files": total_files, "total_symbols": total_syms, "scanned_at": now}
    _save_scan_meta(head_sha, skeleton, deep=deep_meta)

    return skeleton, total_files, total_syms
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "full_repo"
```
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: deep scan writes source_symbols DB and source-map.md"
```

---

## Task 6: Passive cache invalidation (`_check_scan_cache`)

**Files:**
- Modify: `bin/synlynk.py` — add `_check_scan_cache()` after `_scan_full_repo()`
- Modify: `tests/test_static_scan.py` — add cache tests

- [ ] **Step 1: Add cache tests**

```python
# --- _check_scan_cache ---

def test_check_scan_cache_returns_cached_on_sha_match(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    skeleton_saved = [{"file": "app.py", "language": "python", "symbols": ["main()"]}]
    # Fake HEAD sha
    fake_sha = "a" * 40
    synlynk._save_scan_meta(fake_sha, skeleton_saved)
    # Monkeypatch _git_head_sha to return the same sha
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
    # Should have rescanned and returned fresh skeleton
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
    # Meta should now be written
    meta = synlynk._load_scan_meta()
    assert meta is not None
    assert meta["head_sha"] == fake_sha
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "cache" 2>&1 | head -20
```
Expected: `AttributeError: module 'synlynk' has no attribute '_check_scan_cache'`

- [ ] **Step 3: Add `_check_scan_cache()` to `bin/synlynk.py` after `_scan_full_repo()`**

```python
def _check_scan_cache(root: str = ".") -> list:
    """Returns skeleton from cache if HEAD unchanged, else re-scans.

    Returns [] if not in a git repo (no commits). On re-scan, writes updated
    scan-meta.json but does NOT write source-map.md or the DB — that's --deep only.
    """
    current_sha = _git_head_sha()
    if current_sha is None:
        return []
    meta = _load_scan_meta()
    if meta and meta.get("head_sha") == current_sha:
        return meta.get("skeleton", [])
    skeleton = _scan_source_skeleton(root)
    _save_scan_meta(current_sha, skeleton)
    return skeleton
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "cache"
```
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: passive scan cache invalidation on HEAD change"
```

---

## Task 7: Context injection (`generate_context` + `_format_source_architecture`)

**Files:**
- Modify: `bin/synlynk.py` — add `_format_source_architecture()`, modify `generate_context()`
- Modify: `tests/test_static_scan.py` — add context injection tests

- [ ] **Step 1: Add context injection tests**

```python
# --- context injection ---

def test_generate_context_includes_source_architecture(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    # Minimal project structure
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
    assert "2 more files" in out or "more file" in out


def test_format_source_architecture_empty_returns_empty():
    out = synlynk._format_source_architecture([], "abc1234", cache_hit=True)
    assert out == ""
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "context or format_source" 2>&1 | head -25
```
Expected: `AttributeError: module 'synlynk' has no attribute '_format_source_architecture'`

- [ ] **Step 3: Add `_format_source_architecture()` to `bin/synlynk.py` after `_check_scan_cache()`**

```python
def _format_source_architecture(skeleton: list, head_sha: str, cache_hit: bool,
                                 total_files: int = 0) -> str:
    """Formats the ## Source Architecture block for context.md."""
    if not skeleton:
        return ""
    status = "cache hit" if cache_hit else "refreshed"
    sha_short = head_sha[:7] if head_sha and head_sha != "unknown" else "unknown"
    lines = [
        "## Source Architecture",
        f"_Scanned: {time.strftime('%Y-%m-%d %H:%M')} · HEAD: {sha_short}"
        f" · {len(skeleton)} files · {status}_",
        "",
    ]
    # Group by directory
    groups: dict = {}
    for entry in skeleton:
        dirname = os.path.dirname(entry["file"])
        groups.setdefault(dirname, []).append(entry)

    for dirname in sorted(groups):
        entries = groups[dirname]
        lang_counts: dict = {}
        for e in entries:
            lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
        lang_str = ", ".join(
            f"{lg} · {cnt} {'file' if cnt == 1 else 'files'}"
            for lg, cnt in sorted(lang_counts.items())
        )
        label = dirname if dirname else "[root]"
        lines.append(f"### {label}/  [{lang_str}]")
        for entry in entries:
            syms = entry.get("symbols", [])
            if syms:
                lines.append(f"`{entry['file']}` — {', '.join(syms)}")
            else:
                lines.append(f"`{entry['file']}`")
        lines.append("")

    if total_files > len(skeleton):
        overflow = total_files - len(skeleton)
        noun = "file" if overflow == 1 else "files"
        lines.append(
            f"> {overflow} more {noun} in source-map.md"
            " — run `synlynk scan --deep` to refresh"
        )
    lines.append("---")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Modify `generate_context()` to inject `## Source Architecture`**

Find the `generate_context()` function. After the Active Tasks block (just after `out.write("\n---\n\n")` that closes tasks), and **before** the Roadmap block, add:

```python
        # Source architecture (passive cache — re-scans if HEAD changed)
        source_skeleton = _check_scan_cache()
        if source_skeleton:
            meta = _load_scan_meta()
            head_sha = meta.get("head_sha", "unknown") if meta else "unknown"
            # Determine cache_hit: True if HEAD matches what was already in meta
            current_sha = _git_head_sha() or ""
            cache_hit = bool(meta and meta.get("head_sha") == current_sha)
            total_files = 0
            if meta and meta.get("deep"):
                total_files = meta["deep"].get("total_files", 0)
            arch_section = _format_source_architecture(
                source_skeleton, head_sha, cache_hit, total_files
            )
            if arch_section:
                out.write(arch_section)
```

The existing Roadmap block (starting with `out.write("## Roadmap (active)\n")`) follows immediately after this insertion.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "context or format_source"
```
Expected: all 5 PASS.

- [ ] **Step 6: Run the full existing test suite to check for regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all pre-existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: inject ## Source Architecture into generate_context()"
```

---

## Task 8: `synlynk scan` CLI surface

**Files:**
- Modify: `bin/synlynk.py` — add `cmd_scan()`, extend `main()` with `scan` subparser
- Modify: `tests/test_static_scan.py` — add CLI tests

- [ ] **Step 1: Add CLI tests**

```python
# --- cmd_scan ---

def test_cmd_scan_status_output(tmp_path, monkeypatch, capsys, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    fake_sha = "f" * 40
    synlynk._save_scan_meta(fake_sha, [{"file": "app.py", "language": "python", "symbols": ["main()"]}])
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    synlynk.cmd_scan(status=True)
    out = capsys.readouterr().out
    assert "Skeleton" in out or "skeleton" in out
    assert "HEAD" in out or fake_sha[:7] in out


def test_cmd_scan_status_no_cache(tmp_path, monkeypatch, capsys, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: None)
    synlynk.cmd_scan(status=True)
    out = capsys.readouterr().out
    assert "no scan" in out.lower() or "not scanned" in out.lower() or "none" in out.lower()


def test_cmd_scan_deep_writes_source_map(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "app.py").write_text("def main(): pass\n")
    fake_sha = "a" * 40
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    synlynk.cmd_scan(deep=True)
    assert (tmp_path / "project-docs" / "source-map.md").exists()


def test_cmd_scan_force_refresh(tmp_path, monkeypatch, isolated_db):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "mod.py").write_text("class Widget: pass\n")
    fake_sha = "b" * 40
    monkeypatch.setattr(synlynk, "_git_head_sha", lambda: fake_sha)
    # Run scan (no --deep, no --status = force-refresh skeleton)
    synlynk.cmd_scan()
    meta = synlynk._load_scan_meta()
    assert meta is not None
    assert meta["head_sha"] == fake_sha
    files = [e["file"] for e in meta.get("skeleton", [])]
    assert any("mod.py" in f for f in files)
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_static_scan.py -v -k "cmd_scan" 2>&1 | head -20
```
Expected: `AttributeError: module 'synlynk' has no attribute 'cmd_scan'`

- [ ] **Step 3: Add `cmd_scan()` to `bin/synlynk.py`**

Add near the other `cmd_*` functions (e.g., after `cmd_pr_check`):

```python
def cmd_scan(deep: bool = False, status: bool = False) -> None:
    """synlynk scan [--deep] [--status]

    No flags: force-refresh skeleton (even if HEAD unchanged).
    --deep:   full tree walk → state.db + project-docs/source-map.md.
    --status: show cache age, HEAD SHA, file/symbol counts.
    """
    _GREEN = "\033[32m"
    _CYAN = "\033[36m"
    _RESET = "\033[0m"

    if status:
        meta = _load_scan_meta()
        if not meta:
            print("Source scan status: not scanned yet — run `synlynk scan` to populate")
            return
        sha_short = meta.get("head_sha", "unknown")[:7]
        file_count = meta.get("file_count", 0)
        scanned_at = meta.get("scanned_at", "unknown")
        print("Source scan status:")
        print(f"  Skeleton:    {file_count} files · cached · HEAD {sha_short} · {scanned_at}")
        deep_meta = meta.get("deep")
        if deep_meta:
            tf = deep_meta.get("total_files", "?")
            ts = deep_meta.get("total_symbols", "?")
            da = deep_meta.get("scanned_at", "unknown")
            print(f"  source-map:  {tf} files · {ts} symbols · project-docs/source-map.md · {da}")
        else:
            print("  source-map:  not yet generated — run `synlynk scan --deep`")
        print("  Next refresh: on next commit (HEAD change)")
        return

    if deep:
        print(f"  {_GREEN}▶{_RESET} Deep scanning source tree...")
        skeleton, total_files, total_syms = _scan_full_repo()
        sha_short = (_git_head_sha() or "unknown")[:7]
        print(f"  {_GREEN}✓{_RESET} Scanned {total_files} files · {total_syms} symbols · HEAD {sha_short}")
        print(f"  {_CYAN}→{_RESET} project-docs/source-map.md updated")
        return

    # Force-refresh skeleton (ignore HEAD comparison)
    head_sha = _git_head_sha()
    if head_sha is None:
        print("  ⚠ Not in a git repository — scan requires git")
        return
    skeleton = _scan_source_skeleton()
    _save_scan_meta(head_sha, skeleton)
    sha_short = head_sha[:7]
    print(f"  {_GREEN}✓{_RESET} Skeleton refreshed · {len(skeleton)} files · HEAD {sha_short}")
```

- [ ] **Step 4: Add `scan` subparser to `main()` in `bin/synlynk.py`**

Find the `subparsers.add_parser("upgrade", ...)` line. Add `scan` parser after it (or near the other simple subcommands):

```python
    scan_parser = subparsers.add_parser("scan", help="Scan source tree and update architecture context")
    scan_parser.add_argument("--deep", action="store_true",
                             help="Full tree walk: populate state.db and write project-docs/source-map.md")
    scan_parser.add_argument("--status", action="store_true",
                             help="Show cache age, HEAD SHA, file and symbol counts")
```

Find the `elif args.command == "upgrade":` dispatch block in `main()` and add after the corresponding `upgrade()` call block:

```python
    elif args.command == "scan":
        cmd_scan(deep=getattr(args, "deep", False), status=getattr(args, "status", False))
```

- [ ] **Step 5: Run CLI tests to verify they pass**

```bash
pytest tests/test_static_scan.py -v -k "cmd_scan"
```
Expected: all 4 PASS.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all tests pass.

- [ ] **Step 7: Manual smoke test**

```bash
cd ~/dev/synlynk
python3 .worktrees/feat+v0.7.0-static-scan-quality/bin/synlynk.py scan
python3 .worktrees/feat+v0.7.0-static-scan-quality/bin/synlynk.py scan --status
python3 .worktrees/feat+v0.7.0-static-scan-quality/bin/synlynk.py scan --deep
cat project-docs/source-map.md | head -30
```
Expected: skeleton output shows synlynk's own Python symbols; source-map.md generated.

- [ ] **Step 8: Commit**

```bash
git add bin/synlynk.py tests/test_static_scan.py
git commit -m "feat: synlynk scan [--deep] [--status] CLI surface"
```

---

## Task 9: VERSION bump, blog post, PR

**Files:**
- Modify: `bin/synlynk.py` — `VERSION = "0.7.0"`
- Create: `docs/blog/15-prN-v0.7.0-static-scan-quality.md`

- [ ] **Step 1: Bump VERSION**

In `bin/synlynk.py`, change:
```python
VERSION = "0.6.1"
```
to:
```python
VERSION = "0.7.0"
```

- [ ] **Step 2: Run full test suite after version bump**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: any `test_version_is_*` test now expects "0.7.0". Update if failing:

In `tests/test_synlynk.py`, find:
```python
def test_version_is_061():
    assert synlynk.VERSION == "0.6.1"
```
Change to:
```python
def test_version_is_070():
    assert synlynk.VERSION == "0.7.0"
```

Re-run:
```bash
pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: all pass.

- [ ] **Step 3: Write blog post**

Create `docs/blog/15-prN-v0.7.0-static-scan-quality.md` following the template in `docs/blog/README.md`. The post must cover: the dual-storage design decision (SQLite + source-map.md), the passive HEAD-keyed cache, the file scoring formula, language detection via regex, the context injection location (between tasks and roadmap), and what signal types A–D are and aren't implemented.

- [ ] **Step 4: Final commit and PR**

```bash
git add bin/synlynk.py tests/test_synlynk.py docs/blog/
git commit -m "feat: v0.7.0 static scan quality — source architecture in every exec context"
git push -u origin feat/v0.7.0-static-scan-quality
gh pr create \
  --title "feat: v0.7.0 Static Scan Quality — source architecture in every exec context" \
  --body "$(cat <<'EOF'
## Summary
- Language-agnostic symbol extractor (9 languages + generic fallback, 300-line read cap)
- Top-15 file skeleton scored by entry-point bonus + git activity − depth penalty
- Passive cache keyed on `git rev-parse HEAD` — auto-refreshes in `generate_context()`
- `## Source Architecture` section injected between tasks and roadmap in `context.md`
- `synlynk scan [--deep] [--status]` CLI; `--deep` populates `state.db:source_symbols` + `project-docs/source-map.md`
- Dual storage: SQLite (queryable, Tokq-sync-ready) + flat-file materialized export

## Test Plan
- [ ] `pytest tests/test_static_scan.py -v` — all new tests pass
- [ ] `pytest tests/ -v` — no regressions in existing suite
- [ ] `synlynk scan` in this repo shows synlynk's own Python symbols
- [ ] `synlynk exec claude` — context.md includes `## Source Architecture`
- [ ] `synlynk scan --status` shows HEAD SHA and age
- [ ] `synlynk scan --deep` writes project-docs/source-map.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Checklist

**Spec section coverage:**
- ✅ Goal: generate_context injection
- ✅ Scope: works on arbitrary repos, A/B/C/D signals documented
- ✅ Architecture: three new capabilities, two storage locations
- ✅ File Prioritization: +3 entry-point, +1 git activity, −1/level depth, top-15 cap, skip dirs extended
- ✅ Symbol Extraction: all 9 languages + generic, 300-line limit, 8-symbol skeleton cap
- ✅ SQLite Schema: source_symbols table with indexes
- ✅ scan-meta.json Schema: schema_version, head_sha, scanned_at, file_count, skeleton, deep
- ✅ Context Injection Format: grouped by dir, language, overflow line, cache status
- ✅ source-map.md Format: full symbol list, grouped by dir, no cap
- ✅ CLI Surface: `synlynk scan`, `--deep`, `--status`
- ✅ Passive Cache Invalidation: `_check_scan_cache` in `generate_context()`
- ✅ Error Handling: no git → skip; file read error → skip file; DB unavailable → skeleton only; empty repo → omit section
- ✅ Testing: all 8 spec test cases covered + extras

**Placeholder scan:** None found.

**Type consistency:**
- `_extract_symbols` returns `list[dict]` with keys `symbol`, `symbol_type`, `line` — used consistently in `_scan_full_repo` and `_scan_source_skeleton`
- `_scan_source_skeleton` returns `list[dict]` with keys `file`, `language`, `symbols: list[str]` — used in `_save_scan_meta`, `_check_scan_cache`, `_format_source_architecture`
- `_scan_full_repo` returns `(skeleton, total_files, total_syms)` — used in `cmd_scan(deep=True)`
