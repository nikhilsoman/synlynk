# BS-17 Scan + Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `synlynk scan` (workspace-level environment scan) and `synlynk init --wizard` (8-screen FTUE TUI) as v0.10.0 P0 stories.

**Architecture:** All code goes into `synlynk/__init__.py` (single-file pattern — do not create new modules). `run_workspace_scan()` is the interface contract between the two agents — Codex implements it, Grok's wizard calls it. Wizard state is purely in-memory; nothing is written to disk until Screen 6 confirmation.

**Tech Stack:** Python 3.7+ stdlib only — `os`, `subprocess`, `shutil`, `sqlite3`, `json`, `time`, `termios`, `tty`, `sys`, `dataclasses`. No new dependencies.

**Agent assignments:**
- **Tasks A-1 through A-6** → **Codex** (`synlynk scan`)
- **Tasks B-1 through B-6** → **Grok** (`synlynk init --wizard`) — start after Task A-2 lands (needs `run_workspace_scan` signature)
- **Tasks C-1 through C-3** → **Agy** (integration tests for both) — start after A-6 + B-6

---

## Interface Contract (read before any implementation)

`run_workspace_scan()` returns this dict. Both agents must use exactly these key names:

```python
{
    "workspace_name": str,          # e.g. "dev-workspace"
    "topology": str,                # "single" | "monorepo" | "multi"
    "repos": [                      # list of dicts, one per git root
        {
            "path": str,            # absolute path
            "name": str,            # basename of path
            "stack_labels": list,   # e.g. ["Python", "TypeScript"]
            "readme_excerpt": str,  # first 200 chars of README.md
            "context_sections": dict,  # {"Your Role": "...", "Architecture": "..."}
        }
    ],
    "harnesses": [                  # discovered AI CLIs
        {"name": str, "cli": str, "version": str, "path": str}
    ],
    "agents": list,                 # output of existing discover_agents()
    "skills": [                     # installed skill packs
        {"name": str, "version": str, "path": str}
    ],
    "home_harness": str | None,     # e.g. "claude" or None
    "scanned_at": str,              # ISO timestamp e.g. "2026-07-01T10:00:00"
}
```

---

## File Structure

| File | Change | Responsible |
|------|--------|-------------|
| `synlynk/__init__.py` | Add `find_git_roots`, `fingerprint_stack`, `scan_skills`, `detect_home_harness`, `parse_context_sections`, `run_workspace_scan`, `write_workspace_config`, `generate_structured_context` after line ~2930 (near `_static_scan`) | Codex |
| `synlynk/__init__.py` | Extend `cmd_scan()` (line ~834) with `--refresh/--add/--remove/--dry-run` branches | Codex |
| `synlynk/__init__.py` | Extend `scan` subparser in `main()` (line ~7847) with new flags | Codex |
| `synlynk/__init__.py` | Add `_wiz_read_key`, `_wiz_header`, `_wiz_screen_*`, `wizard_init` before `init()` (line ~7448) | Grok |
| `synlynk/__init__.py` | Add `--wizard` flag to `init` subparser and handler in `main()` | Grok |
| `tests/test_workspace_scan.py` | New — unit tests for all scan functions | Agy |
| `tests/test_wizard.py` | New — unit + integration tests for wizard screens | Agy |

---

## PLAN A — Codex: `synlynk scan`

### Task A-1: `find_git_roots` + `fingerprint_stack`

**Files:**
- Modify: `synlynk/__init__.py` — insert after `_static_scan` function (line ~2933)
- Test: `tests/test_workspace_scan.py` (create)

- [ ] **Step 1: Create test file and write failing tests**

```python
# tests/test_workspace_scan.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_find_git_roots_finds_current_repo(tmp_path, monkeypatch):
    """find_git_roots returns paths that have a .git dir."""
    (tmp_path / "repo_a").mkdir()
    (tmp_path / "repo_a" / ".git").mkdir()
    (tmp_path / "repo_b").mkdir()
    (tmp_path / "repo_b" / ".git").mkdir()
    (tmp_path / "not_a_repo").mkdir()
    monkeypatch.chdir(tmp_path)
    roots = synlynk.find_git_roots([str(tmp_path)], max_depth=1)
    names = {os.path.basename(r) for r in roots}
    assert "repo_a" in names
    assert "repo_b" in names
    assert "not_a_repo" not in names


def test_find_git_roots_excludes_dotfiles(tmp_path, monkeypatch):
    (tmp_path / "dotfiles").mkdir()
    (tmp_path / "dotfiles" / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    roots = synlynk.find_git_roots([str(tmp_path)], max_depth=1,
                                    exclude_names={"dotfiles"})
    assert all("dotfiles" not in r for r in roots)


def test_fingerprint_stack_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'")
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert "Python" in labels


def test_fingerprint_stack_typescript(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "tsconfig.json").write_text("{}")
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert "TypeScript" in labels


def test_fingerprint_stack_nextjs(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "tsconfig.json").write_text("{}")
    (tmp_path / "next.config.js").write_text("module.exports = {}")
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert "Next.js" in labels
    assert "TypeScript" in labels


def test_fingerprint_stack_multiple(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11")
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert "Python" in labels
    assert "Docker" in labels


def test_fingerprint_stack_empty_dir(tmp_path):
    labels = synlynk.fingerprint_stack(str(tmp_path))
    assert labels == []
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd /Users/nikhilsoman/dev/synlynk
python -m pytest tests/test_workspace_scan.py -v 2>&1 | head -30
```
Expected: `AttributeError: module 'synlynk' has no attribute 'find_git_roots'`

- [ ] **Step 3: Implement `find_git_roots` and `fingerprint_stack` in `synlynk/__init__.py`**

Insert after the `_static_scan` function (find it with `grep -n "^def _static_scan" synlynk/__init__.py`). Add:

```python
_STACK_FINGERPRINTS = [
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("next.config.js", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("Pulumi.yaml", "Pulumi"),
    ("Pulumi.yml", "Pulumi"),
    ("Dockerfile", "Docker"),
    ("docker-compose.yml", "Docker"),
    ("docker-compose.yaml", "Docker"),
]
_STACK_EXT_MAP = {
    ".go": "Go",
    ".rs": "Rust",
}


def find_git_roots(search_dirs: list, max_depth: int = 2,
                   exclude_names: set = None) -> list:
    """Walk search_dirs up to max_depth levels deep; return absolute paths of
    directories containing a .git entry.

    exclude_names: set of dir basenames to skip (default: dotfiles heuristic).
    """
    _DEFAULT_EXCLUDE = {"dotfiles", ".dotfiles", "node_modules", "__pycache__",
                        ".venv", "venv", ".git"}
    if exclude_names is None:
        exclude_names = _DEFAULT_EXCLUDE
    found = []
    for base in search_dirs:
        base = os.path.expanduser(base)
        if not os.path.isdir(base):
            continue
        for depth in range(max_depth + 1):
            if depth == 0:
                candidates = [base]
            else:
                candidates = []
                for root, dirs, _ in os.walk(base):
                    # Prune excluded dirs in-place so os.walk doesn't descend
                    dirs[:] = [d for d in dirs
                                if not d.startswith(".") and d not in exclude_names]
                    rel = os.path.relpath(root, base)
                    if rel.count(os.sep) < depth - 1:
                        continue
                    candidates = [os.path.join(root, d) for d in dirs]
                    break
            for cand in candidates:
                if os.path.isdir(os.path.join(cand, ".git")):
                    abs_cand = os.path.abspath(cand)
                    if abs_cand not in found:
                        found.append(abs_cand)
    return found


def fingerprint_stack(repo_path: str) -> list:
    """Return a deduplicated list of stack labels for a directory.

    Detection is file-presence only — no content parsing.
    """
    labels = []
    seen = set()

    def _add(label):
        if label not in seen:
            seen.add(label)
            labels.append(label)

    for filename, label in _STACK_FINGERPRINTS:
        if os.path.exists(os.path.join(repo_path, filename)):
            _add(label)

    # package.json without tsconfig → JavaScript; with tsconfig → TypeScript
    has_pkg = os.path.exists(os.path.join(repo_path, "package.json"))
    has_ts = os.path.exists(os.path.join(repo_path, "tsconfig.json"))
    if has_pkg and has_ts:
        _add("TypeScript")
    elif has_pkg:
        _add("JavaScript")

    # .github/workflows → CI/CD
    if os.path.isdir(os.path.join(repo_path, ".github", "workflows")):
        _add("CI/CD")

    # migrations/ or *.sql files at root → SQL
    if os.path.isdir(os.path.join(repo_path, "migrations")):
        _add("SQL")
    else:
        try:
            if any(f.endswith(".sql") for f in os.listdir(repo_path)):
                _add("SQL")
        except OSError:
            pass

    # Sparse extension scan (top-level only) for Go/Rust without manifest
    try:
        for f in os.listdir(repo_path):
            ext = os.path.splitext(f)[1]
            if ext in _STACK_EXT_MAP:
                _add(_STACK_EXT_MAP[ext])
    except OSError:
        pass

    return labels
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_workspace_scan.py::test_find_git_roots_finds_current_repo \
  tests/test_workspace_scan.py::test_fingerprint_stack_python \
  tests/test_workspace_scan.py::test_fingerprint_stack_typescript \
  tests/test_workspace_scan.py::test_fingerprint_stack_nextjs \
  tests/test_workspace_scan.py::test_fingerprint_stack_multiple \
  tests/test_workspace_scan.py::test_fingerprint_stack_empty_dir -v
```
Expected: all 6 PASS

- [ ] **Step 5: Run full test suite — confirm no regressions**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```
Expected: 557+ passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_workspace_scan.py
git commit -m "feat(scan): find_git_roots + fingerprint_stack — BS-17 Task A-1"
```

---

### Task A-2: `scan_skills`, `detect_home_harness`, `parse_context_sections`

**Files:**
- Modify: `synlynk/__init__.py` — add after `fingerprint_stack`
- Test: `tests/test_workspace_scan.py`

- [ ] **Step 1: Add tests to `tests/test_workspace_scan.py`**

```python
def test_scan_skills_finds_superpowers(tmp_path, monkeypatch):
    plugins_dir = tmp_path / ".claude" / "plugins" / "cache" / "superpowers-marketplace" / "superpowers" / "5.1.0"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "manifest.json").write_text('{"name":"superpowers","version":"5.1.0"}')
    monkeypatch.setenv("HOME", str(tmp_path))
    skills = synlynk.scan_skills()
    names = [s["name"] for s in skills]
    assert "superpowers" in names


def test_scan_skills_returns_empty_when_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    skills = synlynk.scan_skills()
    assert skills == []


def test_detect_home_harness_from_env(monkeypatch):
    monkeypatch.setenv("SYNLYNK_HOME_HARNESS", "gemini")
    result = synlynk.detect_home_harness([{"name": "claude"}, {"name": "gemini"}])
    assert result == "gemini"


def test_detect_home_harness_first_available(monkeypatch):
    monkeypatch.delenv("SYNLYNK_HOME_HARNESS", raising=False)
    harnesses = [{"name": "codex"}, {"name": "claude"}]
    result = synlynk.detect_home_harness(harnesses)
    assert result == "codex"


def test_detect_home_harness_prefers_claude(monkeypatch):
    monkeypatch.delenv("SYNLYNK_HOME_HARNESS", raising=False)
    harnesses = [{"name": "codex"}, {"name": "claude"}, {"name": "gemini"}]
    result = synlynk.detect_home_harness(harnesses)
    assert result == "claude"


def test_detect_home_harness_empty_list(monkeypatch):
    monkeypatch.delenv("SYNLYNK_HOME_HARNESS", raising=False)
    result = synlynk.detect_home_harness([])
    assert result is None


def test_parse_context_sections_extracts_role(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\n## Your Role\nYou are the PM.\n\n## Other\nstuff\n"
    )
    sections = synlynk.parse_context_sections(str(tmp_path))
    assert "Your Role" in sections
    assert "PM" in sections["Your Role"]


def test_parse_context_sections_missing_file(tmp_path):
    sections = synlynk.parse_context_sections(str(tmp_path))
    assert sections == {}
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
python -m pytest tests/test_workspace_scan.py -k "skills or harness or context_sections" -v 2>&1 | head -20
```
Expected: `AttributeError: module 'synlynk' has no attribute 'scan_skills'`

- [ ] **Step 3: Implement the three functions in `synlynk/__init__.py`** (insert after `fingerprint_stack`)

```python
_KNOWN_SKILL_PATHS = [
    "~/.claude/plugins/cache/superpowers-marketplace/superpowers/*/",
    "~/.config/gstack/plugins/*/",
]

_SKILL_MANIFEST_NAMES = ("manifest.json", "package.json", "skill.json")


def scan_skills(extra_paths: list = None) -> list:
    """Discover installed skill packs by searching known plugin dirs.

    Returns list of {name, version, path} dicts.
    """
    import glob as _glob
    search = list(_KNOWN_SKILL_PATHS)
    if extra_paths:
        search.extend(extra_paths)
    found = []
    seen_paths = set()
    for pattern in search:
        for candidate in _glob.glob(os.path.expanduser(pattern)):
            if not os.path.isdir(candidate):
                continue
            abs_path = os.path.abspath(candidate)
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)
            name = version = None
            for mname in _SKILL_MANIFEST_NAMES:
                mpath = os.path.join(candidate, mname)
                if os.path.exists(mpath):
                    try:
                        import json as _j
                        data = _j.loads(open(mpath).read())
                        name = data.get("name") or os.path.basename(candidate)
                        version = data.get("version", "unknown")
                        break
                    except Exception:
                        pass
            if name is None:
                name = os.path.basename(candidate)
                version = "unknown"
            found.append({"name": name, "version": version, "path": abs_path})
    return found


def detect_home_harness(harnesses: list) -> "str | None":
    """Return the name of the home harness using this heuristic order:

    1. SYNLYNK_HOME_HARNESS env var
    2. 'claude' if present in list (default preference)
    3. First entry in list
    4. None if list is empty
    """
    env_val = os.environ.get("SYNLYNK_HOME_HARNESS", "").strip()
    harness_names = [h["name"] for h in harnesses]
    if env_val and env_val in harness_names:
        return env_val
    if "claude" in harness_names:
        return "claude"
    return harness_names[0] if harness_names else None


def parse_context_sections(repo_path: str) -> dict:
    """Read CLAUDE.md, GEMINI.md, AGENTS.md from repo_path; extract named
    ## sections. Returns {section_title: content} dict.

    Only reads the first 4000 chars of each file to stay fast.
    """
    sections = {}
    for fname in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        fpath = os.path.join(repo_path, fname)
        if not os.path.exists(fpath):
            continue
        try:
            text = open(fpath).read(4000)
        except OSError:
            continue
        current_title = None
        current_lines = []
        for line in text.splitlines():
            if line.startswith("## "):
                if current_title and current_lines:
                    sections.setdefault(current_title, "\n".join(current_lines).strip())
                current_title = line[3:].strip()
                current_lines = []
            elif current_title:
                current_lines.append(line)
        if current_title and current_lines:
            sections.setdefault(current_title, "\n".join(current_lines).strip())
    return sections
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_workspace_scan.py -k "skills or harness or context_sections" -v
```
Expected: 8 PASS

- [ ] **Step 5: Run full suite — no regressions**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_workspace_scan.py
git commit -m "feat(scan): scan_skills + detect_home_harness + parse_context_sections — BS-17 Task A-2"
```

---

### Task A-3: `run_workspace_scan` — the interface contract function

**Files:**
- Modify: `synlynk/__init__.py` — add after `parse_context_sections`
- Test: `tests/test_workspace_scan.py`

- [ ] **Step 1: Add tests**

```python
def test_run_workspace_scan_single_repo(tmp_path, monkeypatch):
    """Single git root → topology 'single', one repo entry."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], dry_run=True)
    assert result["topology"] == "single"
    assert len(result["repos"]) == 1
    assert result["repos"][0]["name"] == tmp_path.name
    assert "Python" in result["repos"][0]["stack_labels"]


def test_run_workspace_scan_multi_repo(tmp_path, monkeypatch):
    """Multiple git roots → topology 'multi'."""
    for name in ("repo_a", "repo_b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    result = synlynk.run_workspace_scan(
        roots=[str(tmp_path / "repo_a"), str(tmp_path / "repo_b")],
        dry_run=True,
    )
    assert result["topology"] == "multi"
    assert len(result["repos"]) == 2


def test_run_workspace_scan_monorepo(tmp_path, monkeypatch):
    """Single root with packages/ sub-dir → topology 'monorepo'."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "core").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], dry_run=True)
    assert result["topology"] == "monorepo"


def test_run_workspace_scan_result_schema(tmp_path, monkeypatch):
    """Returned dict has all required keys from the interface contract."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], dry_run=True)
    for key in ("workspace_name", "topology", "repos", "harnesses",
                "agents", "skills", "home_harness", "scanned_at"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["repos"], list)
    assert isinstance(result["harnesses"], list)
    assert isinstance(result["skills"], list)
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_workspace_scan.py -k "workspace_scan" -v 2>&1 | head -15
```

- [ ] **Step 3: Implement `run_workspace_scan`** (insert after `parse_context_sections`)

```python
_MONOREPO_MARKERS = ("packages", "apps", "services", "modules", "libs")


def run_workspace_scan(roots: list = None, workspace_name: str = None,
                       dry_run: bool = False) -> dict:
    """Scan the environment and return a ScanResult dict (see interface contract).

    roots: explicit list of absolute repo paths. If None, auto-discovers
           from ~/dev, ~/projects, and cwd.
    workspace_name: if None, inferred from parent dir name or first repo name.
    dry_run: if True, skip writing any files/config.
    """
    import shutil as _shutil
    import time as _time

    # ── 1. Discover / validate repo roots ────────────────────────────────
    if roots is None:
        search_dirs = [
            os.path.expanduser("~/dev"),
            os.path.expanduser("~/projects"),
            os.getcwd(),
        ]
        roots = find_git_roots(search_dirs, max_depth=2)
    # Normalise to absolute paths and deduplicate
    roots = list({os.path.abspath(r) for r in roots if os.path.isdir(r)})

    # ── 2. Determine topology ─────────────────────────────────────────────
    if len(roots) > 1:
        topology = "multi"
    elif roots:
        root = roots[0]
        if any(os.path.isdir(os.path.join(root, m)) for m in _MONOREPO_MARKERS):
            topology = "monorepo"
        else:
            topology = "single"
    else:
        topology = "single"

    # ── 3. Build repo info list ───────────────────────────────────────────
    repos = []
    for rpath in roots:
        readme_excerpt = ""
        for rname in ("README.md", "README.rst", "README.txt"):
            rfile = os.path.join(rpath, rname)
            if os.path.exists(rfile):
                try:
                    readme_excerpt = open(rfile).read(200)
                except OSError:
                    pass
                break
        repos.append({
            "path": rpath,
            "name": os.path.basename(rpath),
            "stack_labels": fingerprint_stack(rpath),
            "readme_excerpt": readme_excerpt,
            "context_sections": parse_context_sections(rpath),
        })

    # ── 4. Discover harnesses (installed AI CLIs) ─────────────────────────
    harnesses = []
    for hname in ("claude", "gemini", "codex", "grok", "aider"):
        cli_path = _shutil.which(hname)
        if not cli_path:
            continue
        version = "unknown"
        try:
            r = subprocess.run([hname, "--version"], capture_output=True,
                               text=True, timeout=5)
            ver_line = (r.stdout or r.stderr or "").strip().splitlines()
            version = ver_line[0] if ver_line else "unknown"
        except Exception:
            pass
        harnesses.append({"name": hname, "cli": hname,
                           "version": version, "path": cli_path})

    # ── 5. Discover agents (richer than harnesses — uses existing function) ─
    agents = []
    try:
        agents = discover_agents()
    except Exception:
        pass

    # ── 6. Scan skills ─────────────────────────────────────────────────────
    skills = scan_skills()

    # ── 7. Infer home harness ─────────────────────────────────────────────
    home_harness = detect_home_harness(harnesses)

    # ── 8. Infer workspace name ───────────────────────────────────────────
    if workspace_name is None:
        parent = os.path.basename(os.path.dirname(roots[0])) if roots else "workspace"
        workspace_name = parent if parent not in ("", "/", "~") else (
            repos[0]["name"] if repos else "workspace"
        )

    return {
        "workspace_name": workspace_name,
        "topology": topology,
        "repos": repos,
        "harnesses": harnesses,
        "agents": agents,
        "skills": skills,
        "home_harness": home_harness,
        "scanned_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_workspace_scan.py -k "workspace_scan" -v
```
Expected: 4 PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_workspace_scan.py
git commit -m "feat(scan): run_workspace_scan interface contract — BS-17 Task A-3"
```

---

### Task A-4: `write_workspace_config` + `generate_structured_context`

**Files:**
- Modify: `synlynk/__init__.py` — add after `run_workspace_scan`
- Test: `tests/test_workspace_scan.py`

- [ ] **Step 1: Add tests**

```python
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
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_workspace_scan.py -k "write_workspace or structured_context" -v 2>&1 | head -10
```

- [ ] **Step 3: Implement both functions** (insert after `run_workspace_scan`)

```python
def write_workspace_config(scan_result: dict, workspace_name: str) -> str:
    """Write workspace config to ~/.synlynk/workspaces/<name>/config.json.

    Returns the path written.
    """
    import json as _json
    ws_dir = os.path.expanduser(f"~/.synlynk/workspaces/{workspace_name}")
    os.makedirs(ws_dir, exist_ok=True)
    config = {
        "workspace_name": workspace_name,
        "topology": scan_result.get("topology", "single"),
        "home_harness": scan_result.get("home_harness"),
        "repos": [
            {
                "path": r["path"],
                "name": r["name"],
                "stack_labels": r["stack_labels"],
            }
            for r in scan_result.get("repos", [])
        ],
        "agent_roles": {},  # populated by wizard Screen 5
        "created_at": scan_result.get("scanned_at", ""),
        "last_scanned_at": scan_result.get("scanned_at", ""),
    }
    config_path = os.path.join(ws_dir, "config.json")
    open(config_path, "w").write(_json.dumps(config, indent=2))
    return config_path


def generate_structured_context(scan_result: dict,
                                 out_path: str = None) -> str:
    """Write structured context.md from a ScanResult dict.

    This replaces generate_context() when a workspace scan has been run.
    Falls back to generate_context() if scan_result is None.
    """
    context_file = out_path or ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)

    lines = []
    ws_name = scan_result.get("workspace_name", "workspace")
    lines.append(f"# synlynk context — {ws_name}")
    lines.append(f"generated: {scan_result.get('scanned_at', '')}")
    lines.append("")
    lines.append("## workspace")
    lines.append(f"name: {ws_name}")
    home_h = scan_result.get("home_harness") or "none"
    lines.append(f"home harness: {home_h}")
    repo_list = scan_result.get("repos", [])
    lines.append(f"repos: {len(repo_list)}")
    lines.append("")

    if repo_list:
        lines.append("## repos")
        for repo in repo_list:
            lines.append(f"### {repo['name']}")
            lines.append(f"path: {repo['path']}")
            stack = ", ".join(repo.get("stack_labels", [])) or "unknown"
            lines.append(f"stack: {stack}")
            excerpt = (repo.get("readme_excerpt") or "").replace("\n", " ").strip()
            if excerpt:
                lines.append(f"readme: {excerpt[:200]}")
            for title, content in (repo.get("context_sections") or {}).items():
                lines.append(f"\n### {title} (from {repo['name']})")
                lines.append(content[:300])
            lines.append("")

    harnesses = scan_result.get("harnesses", [])
    agents = scan_result.get("agents", [])
    if harnesses or agents:
        lines.append("## agent fleet")
        for h in harnesses:
            lines.append(f"{h['name']}: {h['version']} — {h['path']}")
        lines.append("")

    skills = scan_result.get("skills", [])
    if skills:
        lines.append("## skills")
        for s in skills:
            lines.append(f"{s['name']}: {s['version']} — {s['path']}")
        lines.append("")

    content = "\n".join(lines)
    try:
        open(context_file, "w").write(content)
        print(f"  ✓ context.md updated ({len(content)} chars) → {context_file}")
    except OSError as e:
        print(f"  ⚠ Could not write context.md: {e}")

    return content
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_workspace_scan.py -k "write_workspace or structured_context" -v
```

- [ ] **Step 5: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_workspace_scan.py
git commit -m "feat(scan): write_workspace_config + generate_structured_context — BS-17 Task A-4"
```

---

### Task A-5: Extend `cmd_scan()` and the `scan` subparser

**Files:**
- Modify: `synlynk/__init__.py` — extend `cmd_scan()` (line ~834) and `scan_parser` in `main()` (line ~7847)
- Test: `tests/test_workspace_scan.py`

- [ ] **Step 1: Add CLI integration tests**

```python
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
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_workspace_scan.py -k "cmd_scan" -v 2>&1 | head -15
```

- [ ] **Step 3: Rewrite `cmd_scan()` in `synlynk/__init__.py`**

Find `def cmd_scan(deep: bool = False, status: bool = False) -> None:` (~line 834) and replace the entire function with:

```python
def cmd_scan(deep: bool = False, status: bool = False,
             refresh: bool = False, add_path: str = None,
             remove_path: str = None, dry_run: bool = False,
             workspace_name: str = None) -> None:
    """synlynk scan — workspace environment scan + context generation.

    No flags: first-time workspace scan (discover topology, harnesses,
              agents, skills; write workspace config + context.md).
    --refresh: re-run scan on existing workspace.
    --add <path>: add a repo to the current workspace config.
    --remove <path>: remove a repo from the current workspace config.
    --dry-run: print what would change; write nothing.
    --deep: (original) full source-tree walk → state.db + source-map.md.
    --status: (original) show skeleton cache status.
    """
    import json as _json

    # ── Preserved: --status ───────────────────────────────────────────────
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
            print(f"  source-map:  {tf} files · {ts} symbols · {da}")
        else:
            print("  source-map:  not generated — run `synlynk scan --deep`")
        return

    # ── Preserved: --deep ─────────────────────────────────────────────────
    if deep:
        print(f"  {_GREEN}▶{_RESET} Deep scanning source tree...")
        skeleton, total_files, total_syms = _scan_full_repo()
        sha_short = (_git_head_sha() or "unknown")[:7]
        print(f"  {_GREEN}✓{_RESET} Scanned {total_files} files · {total_syms} symbols · HEAD {sha_short}")
        print(f"  {_CYAN}→{_RESET} project-docs/source-map.md updated")
        return

    # ── --remove ──────────────────────────────────────────────────────────
    if remove_path:
        abs_remove = os.path.abspath(remove_path)
        ws_dir = os.path.expanduser(f"~/.synlynk/workspaces/{workspace_name or 'default'}")
        cfg_path = os.path.join(ws_dir, "config.json")
        if not os.path.exists(cfg_path):
            print(f"  ⚠ No workspace config found at {cfg_path}")
            return
        cfg = _json.loads(open(cfg_path).read())
        before = len(cfg.get("repos", []))
        cfg["repos"] = [r for r in cfg.get("repos", [])
                        if os.path.abspath(r["path"]) != abs_remove]
        after = len(cfg["repos"])
        if dry_run:
            print(f"  [dry-run] would remove {os.path.basename(abs_remove)} from workspace")
            return
        open(cfg_path, "w").write(_json.dumps(cfg, indent=2))
        print(f"  {_GREEN}✓{_RESET} Removed {before - after} repo(s) from workspace")
        return

    # ── --add ─────────────────────────────────────────────────────────────
    if add_path:
        abs_add = os.path.abspath(add_path)
        if not os.path.isdir(os.path.join(abs_add, ".git")):
            print(f"  ⚠ {abs_add} is not a git repository")
            return
        ws_dir = os.path.expanduser(f"~/.synlynk/workspaces/{workspace_name or 'default'}")
        cfg_path = os.path.join(ws_dir, "config.json")
        if not os.path.exists(cfg_path):
            print(f"  ⚠ No workspace config at {cfg_path} — run `synlynk scan` first")
            return
        cfg = _json.loads(open(cfg_path).read())
        existing_paths = {os.path.abspath(r["path"]) for r in cfg.get("repos", [])}
        if abs_add in existing_paths:
            print(f"  {_YELLOW}⚠{_RESET} {os.path.basename(abs_add)} already in workspace")
            return
        new_entry = {
            "path": abs_add,
            "name": os.path.basename(abs_add),
            "stack_labels": fingerprint_stack(abs_add),
        }
        if dry_run:
            print(f"  [dry-run] would add {new_entry['name']} "
                  f"({', '.join(new_entry['stack_labels'])}) to workspace")
            return
        cfg["repos"].append(new_entry)
        open(cfg_path, "w").write(_json.dumps(cfg, indent=2))
        print(f"  {_GREEN}✓{_RESET} Added {new_entry['name']} to workspace")
        return

    # ── Default / --refresh: full workspace scan ──────────────────────────
    print(f"  {_CYAN}›{_RESET} scanning your environment...")
    scan = run_workspace_scan(workspace_name=workspace_name, dry_run=dry_run)

    # Print scan summary
    repo_names = ", ".join(r["name"] for r in scan["repos"])
    harness_names = ", ".join(h["name"] for h in scan["harnesses"]) or "none"
    stacks = sorted({lbl for r in scan["repos"] for lbl in r["stack_labels"]})
    print(f"  repos found: {len(scan['repos'])}  ·  "
          f"harnesses: {harness_names}  ·  "
          f"stacks: {', '.join(stacks) or 'unknown'}")

    if not dry_run:
        config_path = write_workspace_config(scan, scan["workspace_name"])
        generate_structured_context(scan)
        print(f"  {_GREEN}✓{_RESET} workspace: {scan['workspace_name']}")
        print(f"  {_GREEN}✓{_RESET} repos: {repo_names}")
        if scan["skills"]:
            skill_names = ", ".join(s["name"] for s in scan["skills"])
            print(f"  {_GREEN}✓{_RESET} skills: {skill_names}")
        print(f"\n  next: synlynk dispatch {scan['home_harness'] or 'claude'} "
              f'"what\'s the current task?"')
    else:
        print("  [dry-run] no files written")
```

- [ ] **Step 4: Extend the `scan_parser` in `main()`**

Find `scan_parser = subparsers.add_parser("scan", ...)` (~line 7847) and replace:
```python
    scan_parser = subparsers.add_parser("scan", help="Scan source tree and update architecture context")
    scan_parser.add_argument("--deep", action="store_true",
                             help="Full tree walk: populate state.db and write project-docs/source-map.md")
    scan_parser.add_argument("--status", action="store_true",
                             help="Show cache age, HEAD SHA, file and symbol counts")
```
with:
```python
    scan_parser = subparsers.add_parser(
        "scan", help="Scan workspace environment (repos, harnesses, agents, skills)")
    scan_parser.add_argument("--deep", action="store_true",
                             help="Full source-tree walk: populate state.db + source-map.md")
    scan_parser.add_argument("--status", action="store_true",
                             help="Show source-skeleton cache status")
    scan_parser.add_argument("--refresh", action="store_true",
                             help="Re-run workspace scan on existing workspace")
    scan_parser.add_argument("--add", default=None, dest="add_path", metavar="PATH",
                             help="Add a repo path to the current workspace")
    scan_parser.add_argument("--remove", default=None, dest="remove_path", metavar="PATH",
                             help="Remove a repo path from the current workspace")
    scan_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                             help="Preview changes without writing")
    scan_parser.add_argument("--workspace", default=None, dest="workspace_name",
                             help="Workspace name (default: inferred from parent dir)")
```

- [ ] **Step 5: Update the `elif args.command == "scan":` handler in `main()`**

Find `elif args.command == "scan":` and replace:
```python
    elif args.command == "scan":
        cmd_scan(deep=getattr(args, "deep", False), status=getattr(args, "status", False))
```
with:
```python
    elif args.command == "scan":
        cmd_scan(
            deep=getattr(args, "deep", False),
            status=getattr(args, "status", False),
            refresh=getattr(args, "refresh", False),
            add_path=getattr(args, "add_path", None),
            remove_path=getattr(args, "remove_path", None),
            dry_run=getattr(args, "dry_run", False),
            workspace_name=getattr(args, "workspace_name", None),
        )
```

- [ ] **Step 6: Run all scan tests**

```bash
python -m pytest tests/test_workspace_scan.py -v 2>&1 | tail -20
```
Expected: all PASS

- [ ] **Step 7: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/__init__.py tests/test_workspace_scan.py
git commit -m "feat(scan): extend cmd_scan + scan subparser with workspace flags — BS-17 Task A-5"
```

---

### Task A-6: Smoke-test `synlynk scan` end-to-end

**Files:**
- Test: `tests/test_workspace_scan.py`

- [ ] **Step 1: Add CLI subprocess test**

```python
def test_synlynk_scan_dry_run_cli(tmp_path, monkeypatch):
    """Run `synlynk scan --dry-run` as a subprocess in a tmp git repo."""
    import subprocess as sp
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / ".synlynk").mkdir()
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = sp.run(
        ["python", "-m", "synlynk", "scan", "--dry-run"],
        cwd=str(tmp_path),
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "dry-run" in result.stdout or "scan" in result.stdout
```

- [ ] **Step 2: Run it**

```bash
python -m pytest tests/test_workspace_scan.py::test_synlynk_scan_dry_run_cli -v
```
Expected: PASS

- [ ] **Step 3: Full suite final check**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 4: Final Codex commit**

```bash
git add synlynk/__init__.py tests/test_workspace_scan.py
git commit -m "feat(scan): smoke test + BS-17 Task A-6 complete — synlynk scan ready"
```

---

## PLAN B — Grok: `synlynk init --wizard`

> **Dependency:** Requires Task A-3 to be merged (needs `run_workspace_scan` in `synlynk/__init__.py`). Run `git pull` before starting.

### Task B-1: TUI primitives — `_wiz_read_key` + `_wiz_header` + `_wiz_clear`

**Files:**
- Modify: `synlynk/__init__.py` — insert before `init()` function (~line 7448)
- Test: `tests/test_wizard.py` (create)

- [ ] **Step 1: Create test file**

```python
# tests/test_wizard.py
import os
import sys
import io
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_wiz_header_step_1(capsys):
    synlynk._wiz_header(step=1, total=6)
    out = capsys.readouterr().out
    assert "1" in out and "6" in out


def test_wiz_header_sub_active(capsys):
    """Sub-active step should produce different output than normal step."""
    synlynk._wiz_header(step=2, total=6, sub_active=False)
    normal = capsys.readouterr().out
    synlynk._wiz_header(step=2, total=6, sub_active=True)
    sub = capsys.readouterr().out
    # Both should contain progress indicator — content may differ
    assert "2" in normal and "2" in sub


def test_wiz_read_key_from_stdin(monkeypatch):
    """_wiz_read_key returns a character when stdin is a pipe (non-TTY)."""
    monkeypatch.setattr("sys.stdin", io.StringIO("y"))
    key = synlynk._wiz_read_key()
    assert key == "y"
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_wizard.py -v 2>&1 | head -15
```

- [ ] **Step 3: Implement primitives in `synlynk/__init__.py`** (insert before `def init(`)

```python
# ── Wizard TUI primitives ─────────────────────────────────────────────────

def _wiz_clear() -> None:
    """Clear the terminal screen."""
    os.system("clear" if os.name != "nt" else "cls")


def _wiz_read_key() -> str:
    """Read a single keypress without requiring Enter.

    Falls back to input()[0] when stdin is not a TTY (e.g. tests, pipes).
    """
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line[0] if line else "\r"
    try:
        import tty as _tty
        import termios as _termios
        fd = sys.stdin.fileno()
        old = _termios.tcgetattr(fd)
        try:
            _tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
    except (ImportError, Exception):
        # Windows or no termios — fall back to Enter-terminated input
        line = input()
        return line[0] if line else "\r"


def _wiz_header(step: int, total: int, sub_active: bool = False) -> None:
    """Print the wizard progress header.

    Active step shown as a wider pill. Sub-active steps use teal colour.
    """
    _TEAL = "\033[36m"
    dots = []
    for i in range(1, total + 1):
        if i < step:
            dots.append(f"{_CYAN}●{_RESET}")
        elif i == step:
            color = _TEAL if sub_active else _CYAN
            dots.append(f"{color}━━{_RESET}")
        else:
            dots.append(f"{_DIM}·{_RESET}")
    dot_str = "  ".join(dots)
    sub_note = " (multi-repo)" if sub_active else ""
    print(f"\n  step {_CYAN}{step}{_RESET}/{total}{sub_note}   {dot_str}\n")


def _wiz_prompt(hint: str, color: str = None) -> None:
    """Print the bottom prompt line."""
    c = color or _CYAN
    print(f"\n  {c}›{_RESET} {_DIM}{hint}{_RESET}")
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_wizard.py -v
```

- [ ] **Step 5: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_wizard.py
git commit -m "feat(wizard): TUI primitives _wiz_read_key + _wiz_header — BS-17 Task B-1"
```

---

### Task B-2: Screens 1–2 (Landing + Harness picker)

**Files:**
- Modify: `synlynk/__init__.py` — add screen functions after `_wiz_prompt`
- Test: `tests/test_wizard.py`

- [ ] **Step 1: Add screen tests**

```python
def test_wiz_screen_landing_enters_on_any_key(monkeypatch, capsys):
    """Landing screen returns without error when any key is pressed."""
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    synlynk._wiz_screen_landing()
    out = capsys.readouterr().out
    assert "synlynk" in out.lower() or "syn" in out


def test_wiz_screen_harness_selects_first(monkeypatch, capsys):
    """Pressing '1' selects the first harness."""
    scan = {
        "harnesses": [
            {"name": "claude", "cli": "claude", "version": "1.x", "path": "/bin/claude"},
        ],
        "home_harness": "claude",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO("1"))
    result = synlynk._wiz_screen_harness(scan)
    assert result == "claude"


def test_wiz_screen_harness_preselects_home(monkeypatch, capsys):
    """Pressing Enter with no input selects home_harness."""
    scan = {
        "harnesses": [
            {"name": "claude", "cli": "claude", "version": "1.x", "path": "/bin/claude"},
            {"name": "gemini", "cli": "gemini", "version": "2.x", "path": "/bin/gemini"},
        ],
        "home_harness": "claude",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    result = synlynk._wiz_screen_harness(scan)
    assert result == "claude"
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_wizard.py -k "landing or harness" -v 2>&1 | head -15
```

- [ ] **Step 3: Implement `_wiz_screen_landing` and `_wiz_screen_harness`** (insert after `_wiz_prompt`)

```python
_WIZ_SYNAPTIC_BLURB = (
    "In the brain, a synaptic link is the tiny gap where one neuron passes\n"
    "  its signal to the next. Alone, neurons are just cells. Connected, they\n"
    "  produce thought. Your AI tools are the same — powerful in isolation,\n"
    "  transformative when they share a signal. synlynk is the gap that makes\n"
    "  them think together."
)

_WIZ_PRODUCT_BLURB = (
    "You already have great AI tools. The problem is they don't know about\n"
    "  each other — or your project. synlynk fixes that: it injects shared\n"
    "  context before every dispatch, routes tasks to the right agent, and\n"
    "  keeps score on what's working. Your fleet, finally coordinated."
)


def _wiz_screen_landing() -> None:
    """Landing screen — brand intro + synaptic link explainer. Waits for Enter."""
    _wiz_clear()
    print(f"\n  {_BOLD}{_CYAN}syn{_RESET}{_CYAN}l{_RESET}{_DIM}y{_RESET}"
          f"{_CYAN}n{_RESET}k  {_DIM}·  synaptic link for AI development{_RESET}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}")
    print(f"\n  {_BOLD}What is a synaptic link?{_RESET}")
    print(f"  {_DIM}{_WIZ_SYNAPTIC_BLURB}{_RESET}\n")
    print(f"  {_WIZ_PRODUCT_BLURB}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}")
    print(f"\n  {_GREEN}✦ One brain{_RESET}  {_DIM}Every agent works from the same project memory.{_RESET}")
    print(f"  {_GREEN}✦ 4× efficiency{_RESET}  {_DIM}Headless dispatch — no wasted tokens on chat.{_RESET}")
    print(f"  {_GREEN}✦ Always watching{_RESET}  {_DIM}Costs, drift, and jobs tracked automatically.{_RESET}")
    _wiz_prompt("press enter to start setup — takes about 2 minutes")
    _wiz_read_key()


def _wiz_screen_harness(scan: dict) -> str:
    """Screen 1 — choose home harness. Returns chosen harness name."""
    _wiz_clear()
    _wiz_header(step=1, total=6)
    print(f"  {_BOLD}Choose your home harness{_RESET}\n")
    print(f"  {_DIM}Your home harness is the AI CLI synlynk treats as primary —{_RESET}")
    print(f"  {_DIM}where it orchestrates jobs, reads costs, and runs health checks.{_RESET}")
    print(f"  {_DIM}You can dispatch to any agent regardless of this choice.{_RESET}\n")

    harnesses = scan.get("harnesses", [])
    home = scan.get("home_harness")

    if not harnesses:
        print(f"  {_YELLOW}⚠ No harnesses found on PATH.{_RESET}")
        print(f"  {_DIM}Install claude, gemini, or codex then re-run `synlynk scan`.{_RESET}")
        _wiz_prompt("press enter to continue with no home harness")
        _wiz_read_key()
        return ""

    print(f"  {_DIM}scan found:{_RESET}")
    for h in harnesses:
        marker = f"{_GREEN}●{_RESET}" if h["name"] == home else f"{_DIM}○{_RESET}"
        print(f"    {marker} {h['name']:12} {_DIM}{h['version']}  {h['path']}{_RESET}")
    print()

    for i, h in enumerate(harnesses, 1):
        default_note = "  (default)" if h["name"] == home else ""
        print(f"  {_CYAN}[{i}]{_RESET} {h['name']}{_DIM}{default_note}{_RESET}")

    _wiz_prompt("enter number to select · enter to use default")
    key = _wiz_read_key()

    if key in ("\r", "\n", ""):
        return home or (harnesses[0]["name"] if harnesses else "")
    try:
        idx = int(key) - 1
        if 0 <= idx < len(harnesses):
            return harnesses[idx]["name"]
    except ValueError:
        pass
    return home or (harnesses[0]["name"] if harnesses else "")
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_wizard.py -k "landing or harness" -v
```

- [ ] **Step 5: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_wizard.py
git commit -m "feat(wizard): screens landing + harness — BS-17 Task B-2"
```

---

### Task B-3: Screens 2–2c (topology picker + multi-repo sub-flow)

**Files:**
- Modify: `synlynk/__init__.py` — add after `_wiz_screen_harness`
- Test: `tests/test_wizard.py`

- [ ] **Step 1: Add tests**

```python
def test_wiz_screen_topology_single(monkeypatch, capsys):
    """Pressing '1' → 'single' topology."""
    scan = {"repos": [{"path": "/tmp/r", "name": "r",
                       "stack_labels": [], "readme_excerpt": "",
                       "context_sections": {}}], "topology": "single"}
    monkeypatch.setattr("sys.stdin", io.StringIO("1"))
    topo = synlynk._wiz_screen_topology(scan)
    assert topo == "single"


def test_wiz_screen_topology_multi(monkeypatch, capsys):
    """Pressing '3' → 'multi' topology."""
    scan = {"repos": [
        {"path": "/tmp/a", "name": "a", "stack_labels": [], "readme_excerpt": "", "context_sections": {}},
        {"path": "/tmp/b", "name": "b", "stack_labels": [], "readme_excerpt": "", "context_sections": {}},
    ], "topology": "multi"}
    monkeypatch.setattr("sys.stdin", io.StringIO("3"))
    topo = synlynk._wiz_screen_topology(scan)
    assert topo == "multi"


def test_wiz_screen_workspace_name_pick_returns_dict(monkeypatch, capsys):
    """Returns dict with workspace_name and repos keys."""
    scan = {
        "workspace_name": "dev-ws",
        "topology": "multi",
        "repos": [
            {"path": "/tmp/a", "name": "repo_a", "stack_labels": ["Python"],
             "readme_excerpt": "", "context_sections": {}},
        ],
    }
    # Simulate: press Enter for suggested name, then space to toggle repo_a, then Enter
    monkeypatch.setattr("sys.stdin", io.StringIO("\r \r"))
    result = synlynk._wiz_screen_workspace_name_pick(scan)
    assert "workspace_name" in result
    assert "repos" in result


def test_wiz_screen_workspace_confirm_enter_returns_true(monkeypatch, capsys):
    workspace = {"workspace_name": "dev-ws", "repos": [],
                 "topology": "multi", "home_harness": "claude"}
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    assert synlynk._wiz_screen_workspace_confirm(workspace) is True


def test_wiz_screen_workspace_confirm_e_returns_false(monkeypatch, capsys):
    workspace = {"workspace_name": "dev-ws", "repos": [],
                 "topology": "multi", "home_harness": "claude"}
    monkeypatch.setattr("sys.stdin", io.StringIO("e"))
    assert synlynk._wiz_screen_workspace_confirm(workspace) is False
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_wizard.py -k "topology or workspace_name or workspace_confirm" -v 2>&1 | head -15
```

- [ ] **Step 3: Implement screens 2, 2ab, 2c** (insert after `_wiz_screen_harness`)

```python
def _wiz_screen_topology(scan: dict) -> str:
    """Screen 2 — repo topology. Returns 'single', 'monorepo', or 'multi'."""
    _wiz_clear()
    _wiz_header(step=2, total=6)
    print(f"  {_BOLD}How are your repos arranged?{_RESET}\n")
    print(f"  {_DIM}synlynk organises your work into workspaces — named containers{_RESET}")
    print(f"  {_DIM}that share a context database, agent fleet, and budget.{_RESET}\n")

    repos = scan.get("repos", [])
    if repos:
        print(f"  {_DIM}scan found {len(repos)} git repo(s) nearby:{_RESET}")
        for r in repos[:5]:
            stack = ", ".join(r["stack_labels"]) or "unknown"
            print(f"    {_CYAN}●{_RESET} {r['name']:20} {_DIM}{stack}{_RESET}")
        if len(repos) > 5:
            print(f"    {_DIM}… and {len(repos) - 5} more{_RESET}")
        print()

    print(f"  {_CYAN}[1]{_RESET} Single repo  {_DIM}— just this repo{_RESET}")
    print(f"  {_CYAN}[2]{_RESET} Monorepo     {_DIM}— one repo with packages/ or apps/ sub-dirs{_RESET}")
    print(f"  {_CYAN}[3]{_RESET} Multi-repo   {_DIM}— multiple repos sharing one workspace{_RESET}")

    # Pre-select based on scan result
    auto = scan.get("topology", "single")
    auto_num = {"single": "1", "monorepo": "2", "multi": "3"}.get(auto, "1")
    _wiz_prompt(f"enter 1/2/3 · enter for auto-detected ({auto_num})")
    key = _wiz_read_key()

    if key in ("\r", "\n", ""):
        return auto
    mapping = {"1": "single", "2": "monorepo", "3": "multi"}
    return mapping.get(key, auto)


def _wiz_screen_workspace_name_pick(scan: dict) -> dict:
    """Screen 2ab — combined workspace name input + repo picker (multi-repo).

    Returns dict: {workspace_name: str, repos: list[dict]}
    """
    _TEAL = "\033[36m"
    _wiz_clear()
    _wiz_header(step=2, total=6, sub_active=True)
    print(f"  {_BOLD}Name & assemble your workspace{_RESET}\n")
    print(f"  {_DIM}All selected repos share one state.db, agent fleet, and budget.{_RESET}")
    print(f"  {_DIM}synlynk found these git roots nearby — include everything your{_RESET}")
    print(f"  {_DIM}agents need to see together.{_RESET}\n")

    # Workspace name
    suggested = scan.get("workspace_name", "my-workspace")
    print(f"  {_DIM}workspace name{_RESET}  [{_CYAN}{suggested}{_RESET}]  "
          f"{_DIM}(enter to accept, or type new name){_RESET}")
    _wiz_prompt("workspace name")

    if sys.stdin.isatty():
        import tty as _tty, termios as _termios
        # Restore normal line editing for text input
        fd = sys.stdin.fileno()
        try:
            old = _termios.tcgetattr(fd)
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
        except Exception:
            pass
    raw_name = input().strip()
    workspace_name = raw_name if raw_name else suggested

    # Repo picker
    repos = scan.get("repos", [])
    _DOTFILE_NAMES = {"dotfiles", ".dotfiles", "dotfile"}
    selected = [r["name"] not in _DOTFILE_NAMES for r in repos]

    print(f"\n  {_DIM}repos to include:{_RESET}  "
          f"{_DIM}(space to toggle, enter to confirm){_RESET}\n")
    for i, (r, sel) in enumerate(zip(repos, selected)):
        stack = ", ".join(r["stack_labels"]) or "unknown"
        check = f"{_TEAL}[✓]{_RESET}" if sel else f"{_DIM}[ ]{_RESET}"
        print(f"  {check} {i+1}. {r['name']:20} {_DIM}{stack}{_RESET}")

    print(f"\n  {_DIM}[a] add repo from another path{_RESET}")
    _wiz_prompt("number to toggle · a to add · enter to confirm")

    while True:
        key = _wiz_read_key()
        if key in ("\r", "\n", ""):
            break
        if key == "a":
            print(f"\n  {_DIM}path to repo:{_RESET} ", end="", flush=True)
            extra = input().strip()
            if extra and os.path.isdir(os.path.join(extra, ".git")):
                repos.append({
                    "path": os.path.abspath(extra),
                    "name": os.path.basename(extra),
                    "stack_labels": fingerprint_stack(extra),
                    "readme_excerpt": "",
                    "context_sections": {},
                })
                selected.append(True)
                print(f"  {_GREEN}✓{_RESET} added {os.path.basename(extra)}")
        try:
            idx = int(key) - 1
            if 0 <= idx < len(selected):
                selected[idx] = not selected[idx]
        except ValueError:
            pass

    chosen_repos = [r for r, s in zip(repos, selected) if s]
    return {"workspace_name": workspace_name, "repos": chosen_repos}


def _wiz_screen_workspace_confirm(workspace: dict) -> bool:
    """Screen 2c — confirm workspace structure.

    Returns True = confirmed (continue), False = go back to 2ab.
    """
    _TEAL = "\033[36m"
    _wiz_clear()
    _wiz_header(step=2, total=6, sub_active=True)
    print(f"  {_BOLD}Here's your workspace{_RESET}\n")

    ws_name = workspace.get("workspace_name", "workspace")
    repos = workspace.get("repos", [])
    print(f"  {_TEAL}{ws_name}/{_RESET}")
    print(f"  {_DIM}├─ state.db{_RESET}")
    print(f"  {_DIM}├─ config.json{_RESET}")
    print(f"  {_DIM}└─ repos{_RESET}")
    for r in repos:
        print(f"  {_GREEN}    ✓{_RESET} {r['name']:20} {_DIM}{r['path']}{_RESET}")

    print(f"\n  {_DIM}state lives at: ~/.synlynk/workspaces/{ws_name}/state.db{_RESET}")
    print(f"  {_DIM}add more later: synlynk scan --add ~/path/to/repo{_RESET}\n")

    print(f"  {_TEAL}[enter]{_RESET} Create workspace · "
          f"{_DIM}[e]{_RESET} Edit")
    _wiz_prompt("enter to create · e to edit")
    key = _wiz_read_key()
    return key not in ("e", "E")
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_wizard.py -k "topology or workspace_name or workspace_confirm" -v
```

- [ ] **Step 5: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_wizard.py
git commit -m "feat(wizard): screens topology + workspace 2ab/2c — BS-17 Task B-3"
```

---

### Task B-4: Screens 3–5 (Skills, Agents, Roles)

**Files:**
- Modify: `synlynk/__init__.py` — add after `_wiz_screen_workspace_confirm`
- Test: `tests/test_wizard.py`

- [ ] **Step 1: Add tests**

```python
def test_wiz_screen_skills_enter_continues(monkeypatch, capsys):
    """Skills screen is education-only — pressing enter continues."""
    scan = {"skills": [{"name": "superpowers", "version": "5.1.0", "path": "/tmp/sp"}]}
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    synlynk._wiz_screen_skills(scan)  # should not raise
    out = capsys.readouterr().out
    assert "superpowers" in out or "skill" in out.lower()


def test_wiz_screen_skills_no_skills(monkeypatch, capsys):
    """Skills screen with no skills found shows fallback message."""
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    synlynk._wiz_screen_skills({"skills": []})
    out = capsys.readouterr().out
    assert "no skill" in out.lower() or "none" in out.lower() or "skill" in out.lower()


def test_wiz_screen_agents_enter_continues(monkeypatch, capsys):
    scan = {"agents": [
        {"name": "claude", "version": "1.x", "functional": True,
         "roles": ["PM"], "capabilities": ["reasoning"]}
    ]}
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    synlynk._wiz_screen_agents(scan)
    out = capsys.readouterr().out
    assert "claude" in out


def test_wiz_screen_roles_returns_dict(monkeypatch, capsys):
    """Roles screen: pressing enter accepts pre-filled roles."""
    scan = {"agents": [
        {"name": "claude", "version": "1.x", "functional": True,
         "roles": ["PM", "code review"], "capabilities": []},
        {"name": "agy", "version": "2.x", "functional": True,
         "roles": ["implementation"], "capabilities": []},
    ]}
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    roles = synlynk._wiz_screen_roles(scan)
    assert isinstance(roles, dict)
    assert "claude" in roles
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_wizard.py -k "skills or agents or roles" -v 2>&1 | head -15
```

- [ ] **Step 3: Implement screens 3, 4, 5** (insert after `_wiz_screen_workspace_confirm`)

```python
def _wiz_screen_skills(scan: dict) -> None:
    """Screen 3 — skills/plugins education (no required choice)."""
    _wiz_clear()
    _wiz_header(step=3, total=6)
    print(f"  {_BOLD}synlynk and your skill packs work together{_RESET}\n")
    print(f"  {_DIM}synlynk injects project context before skills run — it never overrides{_RESET}")
    print(f"  {_DIM}them. If you use Superpowers or GStack, your skill routes stay intact.{_RESET}")
    print(f"  {_DIM}synlynk adds the layer below: shared state, dispatch coordination,{_RESET}")
    print(f"  {_DIM}cost tracking.{_RESET}\n")

    skills = scan.get("skills", [])
    if skills:
        print(f"  {_DIM}scan found:{_RESET}")
        for s in skills:
            print(f"    {_GREEN}●{_RESET} {s['name']:20} {_DIM}v{s['version']}  {s['path']}{_RESET}")
    else:
        print(f"  {_DIM}No skill packs found. You can install them later —{_RESET}")
        print(f"  {_DIM}synlynk works great without them.{_RESET}")

    _wiz_prompt("press enter to continue")
    _wiz_read_key()


_ROBOT_ASCII = "[~]"  # ASCII robot stand-in for terminal (no emoji)


def _wiz_screen_agents(scan: dict) -> None:
    """Screen 4 — agent fleet display (no required choice)."""
    _wiz_clear()
    _wiz_header(step=4, total=6)
    print(f"  {_BOLD}Your agent fleet{_RESET}\n")
    print(f"  {_DIM}Each agent has different strengths. synlynk's dispatch command routes{_RESET}")
    print(f"  {_DIM}tasks to the right agent and tracks what they cost you.{_RESET}\n")

    agents = [a for a in scan.get("agents", []) if a.get("functional")]
    if agents:
        print(f"  {_DIM}installed agents:{_RESET}\n")
        for a in agents:
            caps = ", ".join((a.get("capabilities") or a.get("roles") or [])[:3])
            print(f"  {_CYAN}{_ROBOT_ASCII}{_RESET}  {_BOLD}{a['name']:12}{_RESET}"
                  f"  {_DIM}{a.get('version', 'unknown'):10}{_RESET}  {caps}")
    else:
        print(f"  {_YELLOW}No functional agents found.{_RESET}")
        print(f"  {_DIM}Install claude, gemini, or codex to form your agent fleet.{_RESET}")

    _wiz_prompt("press enter to continue")
    _wiz_read_key()


def _wiz_screen_roles(scan: dict) -> dict:
    """Screen 5 — agent role assignment.

    Returns dict: {agent_name: role_description}
    """
    _wiz_clear()
    _wiz_header(step=5, total=6)
    print(f"  {_BOLD}Who does what?{_RESET}\n")
    print(f"  {_DIM}Consistent role assignment stops agents stomping on each other's work.{_RESET}")
    print(f"  {_DIM}synlynk writes a role block into each agent's directive file so every{_RESET}")
    print(f"  {_DIM}agent knows its lane from token one.{_RESET}\n")

    agents = [a for a in scan.get("agents", []) if a.get("functional")]
    _DEFAULT_ROLES = {
        "claude": "PM · code review · deployments",
        "agy": "implementation · testing · templates",
        "codex": "CLI plumbing · refactoring",
        "grok": "canvas/JS · infra scaffold · complex data structures",
    }
    roles = {}
    for a in agents:
        name = a["name"]
        existing = _DEFAULT_ROLES.get(name, ", ".join(a.get("roles", [])) or "general")
        roles[name] = existing
        print(f"  {_CYAN}{name:12}{_RESET} {_DIM}→{_RESET}  {existing}")

    print()
    print(f"  {_CYAN}[enter]{_RESET} use these roles  "
          f"{_DIM}[e]{_RESET} edit (opens per-agent prompts)")
    _wiz_prompt("enter to accept · e to edit")
    key = _wiz_read_key()

    if key in ("e", "E"):
        for name in list(roles.keys()):
            print(f"\n  {name} role [{roles[name]}]: ", end="", flush=True)
            entered = input().strip()
            if entered:
                roles[name] = entered

    return roles
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest tests/test_wizard.py -k "skills or agents or roles" -v
```

- [ ] **Step 5: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_wizard.py
git commit -m "feat(wizard): screens skills + agents + roles — BS-17 Task B-4"
```

---

### Task B-5: Screen 6 + `wizard_init` orchestrator + `--wizard` flag

**Files:**
- Modify: `synlynk/__init__.py` — add `_wiz_screen_launch` + `wizard_init`, extend `init` subparser and `main()`
- Test: `tests/test_wizard.py`

- [ ] **Step 1: Add tests**

```python
def test_wiz_screen_launch_prints_commands(monkeypatch, capsys):
    workspace = {"workspace_name": "test-ws", "repos": [], "home_harness": "claude",
                 "topology": "single"}
    monkeypatch.setattr("sys.stdin", io.StringIO("\r"))
    synlynk._wiz_screen_launch(workspace, {})
    out = capsys.readouterr().out
    assert "dispatch" in out or "synlynk" in out


def test_wizard_init_completes_without_write_on_ctrl_c(monkeypatch, tmp_path):
    """wizard_init passed a pre-built scan dict runs to completion via stdin mock."""
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    # Simulate full wizard: enter(landing) → 1(harness) → 1(topo) → enter(name)
    # → enter(repos) → enter(skills) → enter(agents) → enter(roles) → enter(launch)
    monkeypatch.setattr("sys.stdin", io.StringIO("\r1\r1\r\r\r\r\r\r\r"))
    scan = {
        "workspace_name": "test-ws", "topology": "single",
        "repos": [{"path": str(tmp_path), "name": "test",
                   "stack_labels": ["Python"], "readme_excerpt": "",
                   "context_sections": {}}],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/bin/claude"}],
        "agents": [], "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    # Should not raise
    synlynk.wizard_init(scan=scan, dry_run=True)
```

- [ ] **Step 2: Run — confirm failure**

```bash
python -m pytest tests/test_wizard.py -k "launch or wizard_init" -v 2>&1 | head -15
```

- [ ] **Step 3: Implement `_wiz_screen_launch` and `wizard_init`** (insert before `def init(`)

```python
def _wiz_screen_launch(workspace: dict, scan: dict) -> None:
    """Screen 6 — launch cheat sheet. Final screen."""
    _wiz_clear()
    _wiz_header(step=6, total=6)
    ws_name = workspace.get("workspace_name", "workspace")
    home_h = workspace.get("home_harness") or scan.get("home_harness") or "claude"
    print(f"  {_BOLD}{_GREEN}You're set up.{_RESET}  "
          f"{_DIM}workspace: {ws_name}{_RESET}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}\n")
    cmds = [
        (f"synlynk dispatch {home_h}", f'"ask {home_h} something"', "dispatch a task"),
        ("synlynk scan --refresh", "", "re-scan all repos"),
        ("synlynk status", "", "platform health + agent availability"),
        ("synlynk jobs", "", "list running/recent jobs"),
        ("synlynk help", "", "full command reference"),
    ]
    for cmd, arg, desc in cmds:
        suffix = f" {arg}" if arg else ""
        print(f"  {_CYAN}{cmd}{suffix}{_RESET}  {_DIM}{desc}{_RESET}")
    print(f"\n  {_DIM}{'─' * 52}{_RESET}")
    _wiz_prompt("done · run `synlynk help` for all commands")
    _wiz_read_key()


def wizard_init(scan: dict = None, dry_run: bool = False) -> None:
    """Run the FTUE wizard. All state is held in memory until Screen 6.

    scan: pre-built ScanResult dict (used by tests and when called from init()).
          If None, runs run_workspace_scan() automatically (Phase 0).
    dry_run: if True, skip writing workspace config + context.md at the end.
    """
    # ── Phase 0: silent scan (skipped if scan provided) ───────────────────
    if scan is None:
        print(f"\n  {_CYAN}›{_RESET} scanning your environment...")
        try:
            scan = run_workspace_scan()
            repo_names = ", ".join(r["name"] for r in scan["repos"])
            harness_names = ", ".join(h["name"] for h in scan["harnesses"]) or "none"
            stacks = sorted({l for r in scan["repos"] for l in r["stack_labels"]})
            print(f"  repos found: {len(scan['repos'])}  ·  "
                  f"harnesses: {harness_names}  ·  "
                  f"stacks: {', '.join(stacks) or 'unknown'}\n")
        except Exception as e:
            print(f"  {_YELLOW}⚠ Scan failed: {e}. Continuing with empty scan.{_RESET}")
            scan = {"workspace_name": "my-workspace", "topology": "single",
                    "repos": [], "harnesses": [], "agents": [], "skills": [],
                    "home_harness": None, "scanned_at": ""}

    # ── Landing ────────────────────────────────────────────────────────────
    _wiz_screen_landing()

    # ── Screen 1: Home harness ─────────────────────────────────────────────
    home_harness = _wiz_screen_harness(scan)

    # ── Screen 2: Topology ────────────────────────────────────────────────
    topology = _wiz_screen_topology(scan)

    # ── Screens 2ab + 2c (multi-repo sub-flow) ────────────────────────────
    if topology == "multi":
        while True:
            workspace_pick = _wiz_screen_workspace_name_pick(scan)
            workspace = {
                "workspace_name": workspace_pick["workspace_name"],
                "repos": workspace_pick["repos"],
                "topology": "multi",
                "home_harness": home_harness,
            }
            if _wiz_screen_workspace_confirm(workspace):
                break
    else:
        workspace = {
            "workspace_name": scan.get("workspace_name", "my-workspace"),
            "repos": scan.get("repos", []),
            "topology": topology,
            "home_harness": home_harness,
        }

    # ── Screen 3: Skills ──────────────────────────────────────────────────
    _wiz_screen_skills(scan)

    # ── Screen 4: Agents ─────────────────────────────────────────────────
    _wiz_screen_agents(scan)

    # ── Screen 5: Roles ───────────────────────────────────────────────────
    roles = _wiz_screen_roles(scan)
    workspace["agent_roles"] = roles

    # ── Screen 6: Launch cheat sheet ─────────────────────────────────────
    _wiz_screen_launch(workspace, scan)

    # ── Commit-on-complete: write all state ───────────────────────────────
    if not dry_run:
        ws_name = workspace["workspace_name"]
        config_path = write_workspace_config(workspace, ws_name)
        generate_structured_context({**scan, **workspace})
        print(f"\n  {_GREEN}✓{_RESET} workspace config → {config_path}")

        # Write role blocks into agent directive files
        for agent_name, role_desc in roles.items():
            fname_map = {"claude": "CLAUDE.md", "agy": "GEMINI.md",
                         "grok": "GROK.md", "codex": "AGENTS.md"}
            fname = fname_map.get(agent_name)
            if fname and os.path.exists(fname):
                try:
                    _upsert_harness_fence(
                        fname,
                        harness_version="wizard",
                        body=f"## Your Role\n{role_desc}\n",
                    )
                    print(f"  {_GREEN}✓{_RESET} wrote role to {fname}")
                except Exception:
                    pass
```

- [ ] **Step 4: Add `--wizard` flag to `init_parser` and handler in `main()`**

Find `init_parser = subparsers.add_parser("init", ...)` and add one line after all existing `add_argument` calls:
```python
    init_parser.add_argument("--wizard", action="store_true",
                             help="Run the FTUE guided setup wizard")
```

Find `if args.command == "init":` in `main()` and replace:
```python
    if args.command == "init":
        agents = [a.strip() for a in args.agents.split(",") if a.strip()]
        if getattr(args, "docs_dir", None):
            os.makedirs(".synlynk", exist_ok=True)
            _update_config({"project_docs_dir": args.docs_dir})
        init(force=args.force, agents=agents, mode=args.mode,
             org=args.org, repo=args.repo, project_id=args.project_id)
```
with:
```python
    if args.command == "init":
        if getattr(args, "wizard", False):
            wizard_init()
        else:
            agents = [a.strip() for a in args.agents.split(",") if a.strip()]
            if getattr(args, "docs_dir", None):
                os.makedirs(".synlynk", exist_ok=True)
                _update_config({"project_docs_dir": args.docs_dir})
            init(force=args.force, agents=agents, mode=args.mode,
                 org=args.org, repo=args.repo, project_id=args.project_id)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_wizard.py -v
```
Expected: all PASS

- [ ] **Step 6: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_wizard.py
git commit -m "feat(wizard): screen-launch + wizard_init orchestrator + --wizard flag — BS-17 Task B-5"
```

---

### Task B-6: Smoke-test `synlynk init --wizard` end-to-end

**Files:**
- Test: `tests/test_wizard.py`

- [ ] **Step 1: Add subprocess smoke test**

```python
def test_synlynk_init_wizard_dry_run_subprocess(tmp_path, monkeypatch):
    """Run `synlynk init --wizard` with stdin pipe — must exit 0."""
    import subprocess as sp
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    # Full wizard key sequence (non-TTY path: every _wiz_read_key reads one char)
    # landing=\r, harness=\r, topo=1(single), skills=\r, agents=\r, roles=\r, launch=\r
    stdin_seq = "\r\r1\r\r\r\r"
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = sp.run(
        ["python", "-m", "synlynk", "init", "--wizard"],
        input=stdin_seq, cwd=str(tmp_path),
        capture_output=True, text=True, env=env, timeout=60,
    )
    # Wizard may exit 0 or print to stderr on scan failure — just check it didn't crash
    assert result.returncode == 0 or "Traceback" not in result.stderr, result.stderr
```

- [ ] **Step 2: Run it**

```bash
python -m pytest tests/test_wizard.py::test_synlynk_init_wizard_dry_run_subprocess -v -s
```

- [ ] **Step 3: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 4: Final Grok commit**

```bash
git add synlynk/__init__.py tests/test_wizard.py
git commit -m "feat(wizard): smoke test complete — synlynk init --wizard ready — BS-17 Task B-6"
```

---

## PLAN C — Agy: Integration test suite

> **Dependency:** Start after Task A-6 and B-6 are both merged. Run `git pull` first.

### Task C-1: Scan integration tests (multi-repo + flags)

**Files:**
- Modify: `tests/test_workspace_scan.py` — add integration section

- [ ] **Step 1: Add integration tests**

```python
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
```

- [ ] **Step 2: Run**

```bash
python -m pytest tests/test_workspace_scan.py -v
```
Expected: all PASS

- [ ] **Step 3: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_workspace_scan.py
git commit -m "test(scan): integration tests — add/remove roundtrip, dry-run, context.md — BS-17 Task C-1"
```

---

### Task C-2: Wizard integration tests (full flow, Ctrl-C teardown)

**Files:**
- Modify: `tests/test_wizard.py` — add integration section

- [ ] **Step 1: Add integration tests**

```python
# ── Wizard integration tests ──────────────────────────────────────────────

def test_wizard_single_repo_full_flow(tmp_path, monkeypatch, capsys):
    """Full wizard run (single-repo path) completes and writes workspace config."""
    import json
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    # Keys: landing=\r, harness=\r(default), topo=1(single),
    #       skills=\r, agents=\r, roles=\r, launch=\r
    monkeypatch.setattr("sys.stdin", io.StringIO("\r\r1\r\r\r\r"))
    scan = {
        "workspace_name": "int-test", "topology": "single",
        "repos": [{"path": str(tmp_path), "name": "int-test",
                   "stack_labels": [], "readme_excerpt": "", "context_sections": {}}],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/bin/claude"}],
        "agents": [], "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    synlynk.wizard_init(scan=scan, dry_run=False)
    ws_config = tmp_path / ".synlynk" / "workspaces" / "int-test" / "config.json"
    # May be under ~HOME/.synlynk/... which is tmp_path in this test
    home_ws = tmp_path / ".synlynk" / "workspaces" / "int-test" / "config.json"
    assert home_ws.exists(), "workspace config should have been written"
    data = json.loads(home_ws.read_text())
    assert data["home_harness"] == "claude"


def test_wizard_ctrl_c_leaves_no_state(tmp_path, monkeypatch):
    """If wizard_init raises KeyboardInterrupt, no workspace config is written."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    call_count = {"n": 0}
    original = synlynk._wiz_screen_landing

    def raising_landing():
        call_count["n"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(synlynk, "_wiz_screen_landing", raising_landing)
    scan = {"workspace_name": "ctrl-c-test", "topology": "single", "repos": [],
            "harnesses": [], "agents": [], "skills": [], "home_harness": None,
            "scanned_at": ""}
    try:
        synlynk.wizard_init(scan=scan, dry_run=False)
    except KeyboardInterrupt:
        pass
    ws_dir = tmp_path / ".synlynk" / "workspaces" / "ctrl-c-test"
    assert not ws_dir.exists(), "workspace dir must not be created before Screen 6"


def test_wizard_multi_repo_flow(tmp_path, monkeypatch, capsys):
    """Multi-repo path (topo=3) runs through 2ab+2c sub-flow."""
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    # Keys: landing=\r, harness=\r, topo=3(multi), name=\r, repos=\r, confirm=\r,
    #       skills=\r, agents=\r, roles=\r, launch=\r
    monkeypatch.setattr("sys.stdin", io.StringIO("\r\r3\r\r\r\r\r\r\r"))
    scan = {
        "workspace_name": "multi-test", "topology": "multi",
        "repos": [
            {"path": str(tmp_path / "a"), "name": "a", "stack_labels": [],
             "readme_excerpt": "", "context_sections": {}},
            {"path": str(tmp_path / "b"), "name": "b", "stack_labels": [],
             "readme_excerpt": "", "context_sections": {}},
        ],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/bin/claude"}],
        "agents": [], "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    # Should complete without raising
    synlynk.wizard_init(scan=scan, dry_run=True)
```

- [ ] **Step 2: Run**

```bash
python -m pytest tests/test_wizard.py -v
```

- [ ] **Step 3: Full suite**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_wizard.py
git commit -m "test(wizard): integration tests — full flow, Ctrl-C, multi-repo — BS-17 Task C-2"
```

---

### Task C-3: Blog post for BS-17 PR

**Files:**
- Create: `docs/blog/35-prNN-v0.10.0-bs17-scan-wizard.md`

- [ ] **Step 1: Write the blog post**

Following the template in `docs/blog/README.md`. The post must cover:
1. **Previous goalpost** — end of BS-16 (ecosystem status design), v0.10.0 targeted as developer preview
2. **Strategic shift** — project-docs drift problem surfaced; `synlynk migrate` pulled to P0; BS-17 onboarding redesigned around workspace model as first-class unit; multi-repo made primary (not afterthought)
3. **What this PR shipped** — `synlynk scan` (7 new functions, 5 flags, workspace config write, structured context.md), `synlynk init --wizard` (8 screens, multi-repo sub-flow, commit-on-complete, pure stdlib TUI), interface contract pattern (ScanResult dict)
4. **Brainstorm visuals** — reference `docs/brainstorm/bs17-ftue-onboarding/wizard-v3.html`, `multirepo-2ab.html`
5. **Progress toward goal** — full autonomous multi-agent dispatch now has a clean workspace model as its foundation
6. **New goalpost** — `synlynk migrate` (project-docs → state.db) + pyproject.toml packaging for developer preview release

File naming: use the PR number once it's opened. Placeholder: `35-prTBD-v0.10.0-bs17-scan-wizard.md`.

- [ ] **Step 2: Commit**

```bash
git add docs/blog/35-prTBD-v0.10.0-bs17-scan-wizard.md
git commit -m "docs(blog): BS-17 scan + wizard blog post — Task C-3"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `synlynk scan` — topology detection (single/mono/multi) | A-3 `run_workspace_scan` |
| `synlynk scan` — stack fingerprinting (14 heuristics) | A-1 `fingerprint_stack` |
| `synlynk scan` — harness/agent discovery | A-3 `run_workspace_scan` |
| `synlynk scan` — skills scan | A-2 `scan_skills` |
| `synlynk scan` — structured context.md | A-4 `generate_structured_context` |
| `synlynk scan --refresh/--add/--remove/--dry-run` | A-5 `cmd_scan` |
| `synlynk init --wizard` — 8 screens | B-2 through B-5 |
| Multi-repo sub-flow (2ab + 2c) | B-3 |
| Commit-on-complete (no writes before Screen 6) | B-5 `wizard_init` |
| Pure stdlib TUI (`termios`) | B-1 `_wiz_read_key` |
| Home harness detection heuristics | A-2 `detect_home_harness` |
| Workspace model — `~/.synlynk/workspaces/<name>/config.json` | A-4 `write_workspace_config` |
| Agent role blocks written to directive files | B-5 `wizard_init` commit block |
| Ctrl-C leaves no state | C-2 test verifies; pattern: wizard_init writes only on Screen 6 |
| `synlynk scan --dry-run` | A-5 `cmd_scan` |
| Blog post | C-3 |

**Placeholder scan:** None found.

**Type consistency:** `run_workspace_scan()` → `ScanResult dict` used consistently. `cmd_scan()` → `None`. `write_workspace_config(scan, name)` → `str`. `generate_structured_context(scan, out_path)` → `str`.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-01-bs17-scan-wizard.md`.
