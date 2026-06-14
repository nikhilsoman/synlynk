# Hybrid Workgroup Bootstrap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add intelligent `synlynk init` wizard with semantic repo discovery, agent discovery with Magic Moment 1 ("You have Claude + Gemini + Codex"), and shell-native background dispatch with Magic Moment 2 (`synlynk dispatch` runs agents in parallel from the shell).

**Architecture:** All new code goes into `bin/synlynk.py` (single-file, zero pip-dep constraint). The init wizard replaces the current plain `print`-based `init()` with a progressive ANSI-colored terminal flow — no curses required at v0.4.0. Background dispatch uses `subprocess.Popen` with `start_new_session=True` and stdout captured to `.synlynk/logs/<job_id>.log`; job state is tracked in `.synlynk/jobs.json` with PID reconciliation on every startup.

**Tech Stack:** Python 3 stdlib only — `subprocess`, `os`, `json`, `shutil`, `hashlib`, `datetime`. Tests: `pytest` with `tmp_path` fixture. All existing 140 tests must stay green.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `bin/synlynk.py` | Modify | All new functions; refactor `init()`; extend `main()` |
| `tests/test_synlynk.py` | Modify | Unit tests for every new function |
| `tests/test_e2e.py` | Modify | CLI-level E2E tests for new subcommands |
| `install.sh` | Modify | Bump VERSION to 0.4.0 |

---

## Task 1: Version bump, constants, and capability baselines

**Files:**
- Modify: `bin/synlynk.py:11` (VERSION)
- Modify: `install.sh`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_synlynk.py` after the existing imports:

```python
def test_version_is_040():
    import bin.synlynk as sl
    assert sl.VERSION == "0.4.0"

def test_agent_capability_baselines_exist():
    import bin.synlynk as sl
    assert "claude" in sl.AGENT_CAPABILITY_BASELINES
    assert "gemini" in sl.AGENT_CAPABILITY_BASELINES
    assert "codex" in sl.AGENT_CAPABILITY_BASELINES
    for name, caps in sl.AGENT_CAPABILITY_BASELINES.items():
        assert "roles" in caps
        assert "cli" in caps
        assert "non_interactive_flags" in caps

def test_jobs_file_constant():
    import bin.synlynk as sl
    assert sl.JOBS_FILE == ".synlynk/jobs.json"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_synlynk.py::test_version_is_040 tests/test_synlynk.py::test_agent_capability_baselines_exist tests/test_synlynk.py::test_jobs_file_constant -v
```

Expected: 3 FAILED

- [ ] **Step 3: Implement — VERSION, constants, baselines**

In `bin/synlynk.py`, change line 11 and add constants after the imports block:

```python
VERSION = "0.4.0"

JOBS_FILE = ".synlynk/jobs.json"
LOGS_DIR = ".synlynk/logs"
PROMPTS_DIR = ".synlynk/prompts"

# Known baseline capabilities per agent CLI.
# Roles: "architect" (design/docs), "builder" (implement), "verifier" (test/review)
AGENT_CAPABILITY_BASELINES = {
    "claude": {
        "cli": "claude",
        "non_interactive_flags": ["--print"],
        "roles": ["architect", "builder"],
        "strengths": ["long context", "reasoning", "code review", "planning"],
    },
    "gemini": {
        "cli": "gemini",
        "non_interactive_flags": ["--quiet"],
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented", "fast"],
    },
    "codex": {
        "cli": "codex",
        "non_interactive_flags": [],
        "roles": ["builder"],
        "strengths": ["code completion", "inline edits", "fast iteration"],
    },
    "agy": {
        "cli": "agy",
        "non_interactive_flags": ["--quiet"],
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
}

# Default paths scanned for agent CLI config directories.
# Overridable in .synlynk/config.json under "agent_discovery_paths".
AGENT_DISCOVERY_DEFAULTS = {
    "claude": os.path.expanduser("~/.claude"),
    "gemini": os.path.expanduser("~/.gemini"),
    "codex": os.path.expanduser("~/.codex"),
    "agy": os.path.expanduser("~/.agy"),
}

# ANSI helpers used by the wizard.
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"
```

- [ ] **Step 4: Bump install.sh**

In `install.sh`, change the VERSION line (search for `VERSION=` or `0.3.1`):

```bash
VERSION="0.4.0"
```

- [ ] **Step 5: Run tests**

```
pytest tests/test_synlynk.py::test_version_is_040 tests/test_synlynk.py::test_agent_capability_baselines_exist tests/test_synlynk.py::test_jobs_file_constant -v
```

Expected: 3 PASSED

- [ ] **Step 6: Full suite must stay green**

```
pytest tests/ -v --tb=short
```

Expected: all 140 existing tests pass, 3 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add bin/synlynk.py install.sh tests/test_synlynk.py
git commit -m "feat: v0.4.0 — version bump, AGENT_CAPABILITY_BASELINES, job store constants"
```

---

## Task 2: Job store — load, save, reconcile

**Files:**
- Modify: `bin/synlynk.py` (add 3 functions after `load_config`)
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_load_jobs_returns_empty_list_when_no_file(project_dir):
    import bin.synlynk as sl
    jobs = sl._load_jobs()
    assert jobs == []

def test_save_and_load_jobs_roundtrip(project_dir):
    import bin.synlynk as sl
    job = {"id": "job-001", "agent": "claude", "pid": 99999, "status": "running",
            "started_at": "2026-06-14T10:00:00", "ended_at": None, "exit_code": None,
            "story_id": "14", "task": "do thing", "log_file": ".synlynk/logs/job-001.log",
            "prompt_file": ".synlynk/prompts/job-001.md"}
    sl._save_jobs([job])
    loaded = sl._load_jobs()
    assert loaded == [job]

def test_reconcile_marks_dead_pid_as_failed(project_dir):
    import bin.synlynk as sl
    # PID 1 always exists; PID 9999999 never exists
    jobs = [
        {"id": "job-alive", "pid": 1, "status": "running", "ended_at": None, "exit_code": None},
        {"id": "job-dead", "pid": 9999999, "status": "running", "ended_at": None, "exit_code": None},
    ]
    sl._save_jobs(jobs)
    sl._reconcile_jobs()
    result = sl._load_jobs()
    alive = next(j for j in result if j["id"] == "job-alive")
    dead = next(j for j in result if j["id"] == "job-dead")
    assert alive["status"] == "running"
    assert dead["status"] == "failed"
    assert dead["ended_at"] is not None

def test_reconcile_skips_finished_jobs(project_dir):
    import bin.synlynk as sl
    jobs = [{"id": "job-done", "pid": 9999999, "status": "completed",
              "ended_at": "2026-06-14T09:00:00", "exit_code": 0}]
    sl._save_jobs(jobs)
    sl._reconcile_jobs()
    result = sl._load_jobs()
    assert result[0]["status"] == "completed"  # unchanged
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_synlynk.py::test_load_jobs_returns_empty_list_when_no_file tests/test_synlynk.py::test_save_and_load_jobs_roundtrip tests/test_synlynk.py::test_reconcile_marks_dead_pid_as_failed tests/test_synlynk.py::test_reconcile_skips_finished_jobs -v
```

Expected: 4 FAILED

- [ ] **Step 3: Implement**

Add after `load_config()` in `bin/synlynk.py`:

```python
def _load_jobs() -> list:
    """Reads .synlynk/jobs.json; returns [] if missing or corrupt."""
    if not os.path.exists(JOBS_FILE):
        return []
    try:
        with open(JOBS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_jobs(jobs: list) -> None:
    """Writes jobs list to .synlynk/jobs.json."""
    os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


def _reconcile_jobs() -> None:
    """Probes PIDs of running jobs; marks unreachable ones as failed.

    Called on every synlynk invocation before any command runs.
    Prevents stale jobs surviving reboots or external kills.
    """
    jobs = _load_jobs()
    changed = False
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for job in jobs:
        if job.get("status") not in ("running",):
            continue
        pid = job.get("pid")
        if pid is None:
            continue
        try:
            os.kill(pid, 0)  # signal 0: check existence only, no actual signal
        except (ProcessLookupError, PermissionError):
            job["status"] = "failed"
            job["ended_at"] = now
            changed = True
    if changed:
        _save_jobs(jobs)
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py::test_load_jobs_returns_empty_list_when_no_file tests/test_synlynk.py::test_save_and_load_jobs_roundtrip tests/test_synlynk.py::test_reconcile_marks_dead_pid_as_failed tests/test_synlynk.py::test_reconcile_skips_finished_jobs -v
```

Expected: 4 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: job store — _load_jobs, _save_jobs, _reconcile_jobs with PID probe"
```

---

## Task 3: Agent discovery

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_check_agent_functional_returns_version_for_present_tool(monkeypatch):
    import bin.synlynk as sl
    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            stdout = "claude 2.1.175\n"
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    result = sl._check_agent_functional("claude")
    assert result == "claude 2.1.175"

def test_check_agent_functional_returns_none_for_missing_tool(monkeypatch):
    import bin.synlynk as sl
    def fake_run(cmd, **kw):
        raise FileNotFoundError
    monkeypatch.setattr("subprocess.run", fake_run)
    result = sl._check_agent_functional("notacli")
    assert result is None

def test_check_agent_functional_returns_none_for_nonzero_exit(monkeypatch):
    import bin.synlynk as sl
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    result = sl._check_agent_functional("claude")
    assert result is None

def test_discover_agents_returns_functional_agents(monkeypatch, tmp_path):
    import bin.synlynk as sl
    # Simulate claude config dir exists, others don't
    (tmp_path / ".claude").mkdir()
    versions = {"claude": "claude 2.1.0"}
    def fake_check(cli):
        return versions.get(cli)
    monkeypatch.setattr(sl, "_check_agent_functional", fake_check)
    monkeypatch.setattr(sl, "AGENT_DISCOVERY_DEFAULTS", {
        "claude": str(tmp_path / ".claude"),
        "gemini": str(tmp_path / ".gemini"),
    })
    agents = sl.discover_agents()
    names = [a["name"] for a in agents]
    assert "claude" in names
    functional = [a for a in agents if a["functional"]]
    assert all(a["name"] == "claude" for a in functional)

def test_discover_agents_uses_config_override(monkeypatch, tmp_path, project_dir):
    import bin.synlynk as sl
    import json as _json
    custom_path = str(tmp_path / "custom_claude")
    os.makedirs(custom_path)
    config = {"agent_discovery_paths": {"claude": custom_path}}
    with open(".synlynk/config.json", "w") as f:
        _json.dump(config, f)
    monkeypatch.setattr(sl, "_check_agent_functional", lambda cli: "claude 2.0")
    agents = sl.discover_agents()
    claude_agent = next((a for a in agents if a["name"] == "claude"), None)
    assert claude_agent is not None
    assert claude_agent["discovery_path"] == custom_path
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "agent_functional or discover_agents" -v
```

Expected: 5 FAILED

- [ ] **Step 3: Implement**

Add after `_reconcile_jobs()` in `bin/synlynk.py`:

```python
def _check_agent_functional(cli: str) -> Optional[str]:
    """Runs `<cli> --version` to confirm CLI is installed and executable.

    Returns version string (stdout stripped) on success, None otherwise.
    """
    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def discover_agents(config: dict = None) -> list:
    """Scans for installed agent CLIs and checks each is functional.

    Returns list of dicts: {name, cli, version, functional, capabilities,
    roles, discovery_path}.
    Agents not found on disk are omitted. Agents found but failing --version
    are included with functional=False.
    """
    if config is None:
        config = load_config()

    # Allow per-project overrides of discovery paths.
    discovery_paths = {**AGENT_DISCOVERY_DEFAULTS}
    discovery_paths.update(config.get("agent_discovery_paths", {}))

    found = []
    for name, defaults in AGENT_CAPABILITY_BASELINES.items():
        path = discovery_paths.get(name)
        if path and not os.path.exists(path):
            continue  # config dir not present — skip entirely
        cli = defaults["cli"]
        version = _check_agent_functional(cli)
        found.append({
            "name": name,
            "cli": cli,
            "version": version,
            "functional": version is not None,
            "roles": defaults["roles"],
            "capabilities": defaults["strengths"],
            "non_interactive_flags": defaults["non_interactive_flags"],
            "discovery_path": path or "",
        })
    return found
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "agent_functional or discover_agents" -v
```

Expected: 5 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: agent discovery — _check_agent_functional, discover_agents with configurable paths"
```

---

## Task 4: Static semantic scan

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_static_scan_extracts_project_name(tmp_path, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# my-cool-project\nA great tool.\n")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    result = sl._static_scan(str(tmp_path))
    assert result["project_name"] == "my-cool-project"

def test_static_scan_counts_commits(tmp_path, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: first"], cwd=tmp_path, capture_output=True)
    result = sl._static_scan(str(tmp_path))
    assert result["commit_count"] == 1

def test_static_scan_detects_structured_commits(tmp_path, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    for msg in ["feat: add thing", "fix: broken thing", "chore: cleanup"]:
        (tmp_path / f"{msg[:4]}.txt").write_text(msg)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=tmp_path, capture_output=True)
    result = sl._static_scan(str(tmp_path))
    assert result["has_structured_commits"] is True

def test_static_scan_no_git_repo(tmp_path, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.chdir(tmp_path)
    result = sl._static_scan(str(tmp_path))
    assert result["commit_count"] == 0
    assert result["project_name"] == tmp_path.name
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "static_scan" -v
```

Expected: 4 FAILED

- [ ] **Step 3: Implement**

Add after `discover_agents()` in `bin/synlynk.py`:

```python
def _static_scan(root: str = ".") -> dict:
    """Scans repo for project context: git log, README, file tree.

    Best-effort: repos without structured commits produce a lower-quality result.
    Returns dict with keys: project_name, description, commit_count,
    has_structured_commits, recent_topics, top_dirs, languages, readme_summary.
    """
    result = {
        "project_name": os.path.basename(os.path.abspath(root)),
        "description": "",
        "commit_count": 0,
        "has_structured_commits": False,
        "recent_topics": [],
        "top_dirs": [],
        "languages": [],
        "readme_summary": "",
    }

    # README extraction — project name from H1, summary from first paragraph.
    for readme in ("README.md", "README.rst", "README.txt", "README"):
        readme_path = os.path.join(root, readme)
        if os.path.exists(readme_path):
            try:
                text = open(readme_path).read(2000)
                lines = text.splitlines()
                for line in lines:
                    if line.startswith("# "):
                        result["project_name"] = line[2:].strip()
                        break
                # First non-heading, non-empty paragraph as description.
                para_lines = []
                in_para = False
                for line in lines[1:]:
                    if line.startswith("#"):
                        if in_para:
                            break
                        continue
                    if line.strip():
                        para_lines.append(line.strip())
                        in_para = True
                    elif in_para:
                        break
                result["description"] = " ".join(para_lines)[:300]
                result["readme_summary"] = text[:500]
            except IOError:
                pass
            break

    # Git log — commit count, structured commit detection, recent topics.
    try:
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-50", "--no-merges"],
            capture_output=True, text=True, cwd=root
        )
        if log_result.returncode == 0:
            messages = [l.split(" ", 1)[1] for l in log_result.stdout.strip().splitlines()
                        if " " in l]
            result["commit_count"] = int(subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, cwd=root
            ).stdout.strip() or "0")
            cc_prefixes = ("feat:", "fix:", "chore:", "docs:", "test:", "refactor:", "perf:")
            structured = sum(1 for m in messages if any(m.startswith(p) for p in cc_prefixes))
            result["has_structured_commits"] = structured >= max(1, len(messages) // 2)
            result["recent_topics"] = messages[:10]
    except (FileNotFoundError, ValueError):
        pass

    # File tree — top-level directories and language hints.
    try:
        entries = os.listdir(root)
        result["top_dirs"] = sorted([
            e for e in entries
            if os.path.isdir(os.path.join(root, e))
            and not e.startswith(".") and e not in ("node_modules", "__pycache__", "venv")
        ])
        lang_map = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
                    ".js": "JavaScript", ".go": "Go", ".rs": "Rust", ".rb": "Ruby"}
        langs = set()
        for e in entries:
            ext = os.path.splitext(e)[1]
            if ext in lang_map:
                langs.add(lang_map[ext])
        result["languages"] = sorted(langs)
    except OSError:
        pass

    return result
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "static_scan" -v
```

Expected: 4 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: _static_scan — git log, README, file tree semantic analysis"
```

---

## Task 5: Informed skeleton writer

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_write_informed_skeleton_creates_docs(project_dir):
    import bin.synlynk as sl
    import shutil
    # Remove existing project-docs to test creation path
    shutil.rmtree("project-docs")
    os.makedirs("project-docs/devlogs")
    scan = {
        "project_name": "testproject", "description": "A test tool.",
        "commit_count": 12, "has_structured_commits": True,
        "recent_topics": ["feat: add login", "fix: auth bug"],
        "top_dirs": ["src", "tests"], "languages": ["Python"],
        "readme_summary": "# testproject\nA test tool.",
    }
    written = sl._write_informed_skeleton(scan, skip_existing=False)
    assert "project-docs/roadmap.md" in written
    assert "project-docs/memory.md" in written
    assert "project-docs/todo.md" in written

def test_write_informed_skeleton_injects_project_name(project_dir):
    import bin.synlynk as sl
    import shutil
    shutil.rmtree("project-docs")
    os.makedirs("project-docs/devlogs")
    scan = {
        "project_name": "myapp", "description": "My application.",
        "commit_count": 5, "has_structured_commits": False,
        "recent_topics": ["initial commit"],
        "top_dirs": ["src"], "languages": ["Go"], "readme_summary": "",
    }
    sl._write_informed_skeleton(scan, skip_existing=False)
    roadmap = open("project-docs/roadmap.md").read()
    assert "myapp" in roadmap

def test_write_informed_skeleton_skips_existing_by_default(project_dir):
    import bin.synlynk as sl
    original = open("project-docs/roadmap.md").read()
    scan = {"project_name": "x", "description": "", "commit_count": 0,
            "has_structured_commits": False, "recent_topics": [],
            "top_dirs": [], "languages": [], "readme_summary": ""}
    sl._write_informed_skeleton(scan, skip_existing=True)
    assert open("project-docs/roadmap.md").read() == original
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "informed_skeleton" -v
```

Expected: 3 FAILED

- [ ] **Step 3: Implement**

Add after `_static_scan()` in `bin/synlynk.py`:

```python
def _write_informed_skeleton(scan: dict, skip_existing: bool = True) -> list:
    """Writes project-docs skeleton informed by static scan results.

    Returns list of file paths written. Skips files that already exist
    when skip_existing=True. The wizard surfaces a caveat for repos
    without structured commits.
    """
    name = scan.get("project_name", "this project")
    desc = scan.get("description") or f"A project named {name}."
    topics = scan.get("recent_topics", [])
    langs = ", ".join(scan.get("languages", [])) or "unknown"
    commit_count = scan.get("commit_count", 0)
    caveat = (
        "\n> ⚠ Skeleton generated from git history — results vary by commit style. "
        "Review before proceeding.\n"
        if not scan.get("has_structured_commits") else ""
    )

    recent_work = "\n".join(f"- {t}" for t in topics[:5]) or "- (no commits found)"

    roadmap_content = f"""\
# {name} Roadmap
{caveat}
**Positioning:** [Describe what {name} is building toward]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
| v0.1.0 | Initial release | ✅ Shipped | — |
| v0.2.0 | [Next milestone] | 🔜 Next | — |

## Recent work (from git history — {commit_count} commits, {langs})
{recent_work}
"""

    memory_content = f"""\
# {name} Memory

## Project Overview
- **Name:** {name}
- **Description:** {desc}
- **Languages:** {langs}
- **Directories:** {", ".join(scan.get("top_dirs", [])) or "—"}

## Decisions
[Document key decisions here with [@username] attribution in team mode]

## Architecture
[Document key architectural decisions here]
"""

    todo_content = f"""\
# {name} — Todo

## Active Tasks
- [ ] Review and refine the generated roadmap.md <!-- id: 1 -->
- [ ] Review and update memory.md with actual decisions <!-- id: 2 -->
- [ ] Define first milestone in roadmap <!-- id: 3 -->

## Completed
"""

    files = {
        "project-docs/roadmap.md": roadmap_content,
        "project-docs/memory.md": memory_content,
        "project-docs/todo.md": todo_content,
    }

    written = []
    for path, content in files.items():
        if skip_existing and os.path.exists(path):
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        written.append(path)
    return written
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "informed_skeleton" -v
```

Expected: 3 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: _write_informed_skeleton — scan-informed project-docs first draft"
```

---

## Task 6: LLM enrichment (opt-in)

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_llm_enrich_calls_agent_noninteractively(project_dir, monkeypatch):
    import bin.synlynk as sl
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = "# Updated Roadmap\n\nThis is enriched content.\n"
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    scan = {"project_name": "testproject", "description": "A test.",
            "commit_count": 5, "recent_topics": ["feat: add x"], "languages": ["Python"],
            "readme_summary": "# testproject\nA test.", "top_dirs": ["src"],
            "has_structured_commits": True}
    result = sl._llm_enrich("claude", scan)
    assert result is True
    assert any("claude" in str(c) for c in calls)

def test_llm_enrich_returns_false_on_agent_failure(project_dir, monkeypatch):
    import bin.synlynk as sl
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    scan = {"project_name": "x", "description": "", "commit_count": 0,
            "recent_topics": [], "languages": [], "readme_summary": "",
            "top_dirs": [], "has_structured_commits": False}
    result = sl._llm_enrich("claude", scan)
    assert result is False
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "llm_enrich" -v
```

Expected: 2 FAILED

- [ ] **Step 3: Implement**

Add after `_write_informed_skeleton()` in `bin/synlynk.py`:

```python
def _llm_enrich(agent_cli: str, scan: dict) -> bool:
    """Calls the configured agent non-interactively to enrich project-docs.

    Passes the static scan result + current doc drafts as context.
    Writes enriched roadmap.md if the agent responds successfully.
    Returns True on success, False on failure.
    Cost is logged to telemetry as an 'llm_enrich' event.
    """
    name = scan.get("project_name", "this project")
    topics = "\n".join(f"- {t}" for t in scan.get("recent_topics", []))
    langs = ", ".join(scan.get("languages", [])) or "unknown"
    readme = scan.get("readme_summary", "")[:400]

    prompt = f"""\
You are helping initialise a synlynk project context for a software project.

Project: {name}
Description: {scan.get('description', '')}
Languages: {langs}
Commit count: {scan.get('commit_count', 0)}
Recent commit messages:
{topics}

README excerpt:
{readme}

Based on this, write a concise `roadmap.md` for this project in this exact format:

# {name} Roadmap

**Positioning:** [one sentence describing the product goal]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
[3-5 plausible milestone rows based on the commit history]

Keep it short. Infer from the evidence. Do not invent features not supported by the commits.
"""

    # Write prompt to a temp file to avoid shell escaping issues.
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    prompt_file = os.path.join(PROMPTS_DIR, "llm-enrich.md")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    baselines = AGENT_CAPABILITY_BASELINES.get(agent_cli, {})
    flags = baselines.get("non_interactive_flags", ["--print"])
    cmd = [agent_cli] + flags

    try:
        with open(prompt_file) as pf:
            result = subprocess.run(cmd, stdin=pf, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not result.stdout.strip():
            return False
        enriched = result.stdout.strip()
        with open("project-docs/roadmap.md", "w") as f:
            f.write(enriched + "\n")
        log_telemetry_event({"type": "llm_enrich", "agent": agent_cli,
                             "project": name, "success": True})
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "llm_enrich" -v
```

Expected: 2 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: _llm_enrich — opt-in non-interactive agent enrichment of project-docs"
```

---

## Task 7: Init wizard

**Files:**
- Modify: `bin/synlynk.py` — refactor `init()` to call new `_init_wizard()` flow

- [ ] **Step 1: Write failing tests**

```python
def test_init_wizard_creates_synlynk_dir(tmp_path, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    monkeypatch.setattr("builtins.input", lambda _: "")  # accept all defaults
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(sl, "_llm_enrich", lambda *a, **kw: False)
    sl.init()
    assert os.path.exists(".synlynk")
    assert os.path.exists(".synlynk/config.json")

def test_init_wizard_writes_project_docs(tmp_path, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(sl, "_llm_enrich", lambda *a, **kw: False)
    sl.init()
    assert os.path.exists("project-docs/roadmap.md")
    assert os.path.exists("project-docs/memory.md")
    assert os.path.exists("project-docs/todo.md")

def test_init_wizard_skips_existing_synlynk_without_force(project_dir, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    original_roadmap = open("project-docs/roadmap.md").read()
    sl.init(force=False)
    assert open("project-docs/roadmap.md").read() == original_roadmap

def test_init_writes_workgroup_nudge_to_config(tmp_path, monkeypatch):
    import bin.synlynk as sl
    import json as _json
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    # Simulate user providing email at the cloud nudge step
    inputs = iter(["nikhil@example.com"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(sl, "_llm_enrich", lambda *a, **kw: False)
    sl.init()
    config = _json.loads(open(".synlynk/config.json").read())
    assert config.get("workgroup_invite_email") == "nikhil@example.com"
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "init_wizard" -v
```

Expected: 4 FAILED

- [ ] **Step 3: Implement**

Replace the body of the existing `init()` function in `bin/synlynk.py` (keep the signature identical — `main()` still calls `init()`):

```python
def init(force: bool = False, agents: list = None,
         org: str = None, repo: str = None, project_id: str = None,
         mode: str = "solo") -> None:
    """Progressive wizard: semantic scan → agent discovery → doc bootstrap → nudge."""

    def _print_step(n: int, label: str) -> None:
        print(f"\n{_BOLD}{_CYAN}Step {n}/{_TOTAL_STEPS} — {label}{_RESET}")

    _TOTAL_STEPS = 6

    # ── Step 1: Detect existing state ──────────────────────────────────────
    _print_step(1, "Scanning repository")
    synlynk_exists = os.path.exists(".synlynk")
    if synlynk_exists and not force:
        print(f"  {_YELLOW}⚠ .synlynk/ already exists.{_RESET} "
              "Use --force to reinitialise.\n  Updating agent files only.")

    scan = _static_scan(".")
    print(f"  Project : {_BOLD}{scan['project_name']}{_RESET}")
    print(f"  Commits : {scan['commit_count']}")
    print(f"  Languages: {', '.join(scan['languages']) or 'unknown'}")
    if scan["recent_topics"]:
        print(f"  Recent  : {scan['recent_topics'][0]}")
    if not scan["has_structured_commits"] and scan["commit_count"] > 0:
        print(f"  {_DIM}⚠ Commit messages don't follow a structured convention — "
              "skeleton quality may be lower. Review generated docs before proceeding.{_RESET}")

    # ── Step 2: Agent discovery ─────────────────────────────────────────────
    _print_step(2, "Discovering agents")
    discovered = discover_agents()
    functional = [a for a in discovered if a["functional"]]
    non_functional = [a for a in discovered if not a["functional"]]

    if functional:
        print(f"\n  {_BOLD}{_GREEN}✨ Your Hybrid Workgroup is ready:{_RESET}")
        for ag in functional:
            roles = ", ".join(ag["roles"])
            print(f"    {_GREEN}✓ {ag['name']:10}{_RESET} {ag['version']}  "
                  f"roles: {roles}")
    else:
        print(f"  {_YELLOW}No agents detected. Install Claude, Gemini, or Codex to form your Hybrid Workgroup.{_RESET}")

    if non_functional:
        print(f"\n  {_DIM}Found but not configured (run --version failed):{_RESET}")
        for ag in non_functional:
            print(f"    {_DIM}✗ {ag['name']} — check API key / install{_RESET}")

    # ── Step 3: Create directories + write skeleton ─────────────────────────
    _print_step(3, "Bootstrapping project-docs")
    for d in ["project-docs", "project-docs/devlogs", ".synlynk",
              LOGS_DIR, PROMPTS_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

    written = _write_informed_skeleton(scan, skip_existing=not force)
    if written:
        for p in written:
            print(f"  {_GREEN}✓{_RESET} Created {p}")
    else:
        print(f"  {_DIM}All project-docs already exist — skipped (use --force to overwrite){_RESET}")

    # Write agent instruction files.
    agent_set = set(agents) if agents is not None else {a["name"] for a in functional} or {"claude", "agy", "codex"}
    templates = _build_templates(org=org, repo=repo, project_id=project_id)
    _agent_guards = {"CLAUDE.md": "claude", "GEMINI.md": "agy", "AGENTS.md": "codex"}
    for filename, content in templates.items():
        required = _agent_guards.get(filename)
        if required and required not in agent_set:
            continue
        if filename in ("GEMINI.md", "CLAUDE.md", "AI_INSTRUCTIONS.md", "AGENTS.md", ".cursorrules"):
            file_path = filename
        elif filename == "config.json":
            file_path = os.path.join(".synlynk", filename)
        else:
            file_path = os.path.join("project-docs", filename)
        if os.path.exists(file_path) and not force:
            continue
        with open(file_path, "w") as f:
            f.write(content)

    # ── Step 4: LLM enrichment offer ────────────────────────────────────────
    _print_step(4, "LLM enrichment (optional)")
    if functional:
        enricher = functional[0]
        print(f"  I found {scan['commit_count']} commits and {len(scan['recent_topics'])} "
              f"recent topics.\n  Want me to ask {enricher['name']} to synthesise a roadmap "
              f"from this? (costs tokens)")
        answer = input("  [y/N] ").strip().lower()
        if answer == "y":
            print(f"  {_DIM}Calling {enricher['cli']} --print...{_RESET}", end=" ", flush=True)
            ok = _llm_enrich(enricher["cli"], scan)
            print(f"{_GREEN}done{_RESET}" if ok else f"{_YELLOW}failed — keeping skeleton{_RESET}")
    else:
        print(f"  {_DIM}No functional agent available — skipping enrichment{_RESET}")

    # ── Step 5: Cloud directory nudge ────────────────────────────────────────
    _print_step(5, "Team & cloud setup (optional)")
    print("  Add a collaborator or share this workspace with your team.")
    print("  Leave blank to skip.")
    email = input("  Email or synlynk ID: ").strip()

    # ── Step 6: Finalise config ──────────────────────────────────────────────
    _print_step(6, "Finalising")
    synlynk_config_path = os.path.join("project-docs", ".synlynk_config.json")
    if not os.path.exists(synlynk_config_path) or force:
        config_data = {"mode": mode, "version": VERSION,
                       "init_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(synlynk_config_path, "w") as f:
            json.dump(config_data, f, indent=2)

    _update_config({
        "workgroup_agents": [a["name"] for a in functional],
        "workgroup_invite_email": email or None,
    })

    set_state("stopped")

    print(f"\n{_BOLD}{_GREEN}✓ synlynk initialised — your Hybrid Workgroup is ready.{_RESET}")
    if functional:
        agent_names = " + ".join(a["name"] for a in functional)
        print(f"\n  {_BOLD}✨ Magic Moment 2 — dispatch agents now:{_RESET}")
        print(f"    {_CYAN}synlynk dispatch {functional[0]['name']} --task \"your task\"{_RESET}")
        if len(functional) >= 3:
            print(f"    {_CYAN}synlynk run --trio --task \"your task\"{_RESET}  "
                  f"← runs {agent_names} in parallel")
    print(f"\n  Next: {_DIM}synlynk status  ·  synlynk jobs  ·  synlynk dispatch --help{_RESET}\n")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "init_wizard" -v
```

Expected: 4 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: init wizard — semantic scan, agent discovery magic moment, LLM enrichment, cloud nudge"
```

---

## Task 8: Background dispatch

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_dispatch_agent_creates_job_entry(project_dir, monkeypatch):
    import bin.synlynk as sl
    launched = []
    class FakeProc:
        pid = 12345
    def fake_popen(cmd, **kw):
        launched.append(cmd)
        return FakeProc()
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    job = sl.dispatch_agent("claude", "implement auth fix", story_id="14")
    assert job["agent"] == "claude"
    assert job["pid"] == 12345
    assert job["status"] == "running"
    assert job["task"] == "implement auth fix"
    assert job["story_id"] == "14"
    jobs = sl._load_jobs()
    assert any(j["id"] == job["id"] for j in jobs)

def test_dispatch_agent_writes_prompt_file(project_dir, monkeypatch):
    import bin.synlynk as sl
    class FakeProc:
        pid = 99
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    job = sl.dispatch_agent("gemini", "write tests")
    assert os.path.exists(job["prompt_file"])
    content = open(job["prompt_file"]).read()
    assert "write tests" in content

def test_dispatch_agent_unknown_agent_raises(project_dir):
    import bin.synlynk as sl, pytest as _pytest
    with _pytest.raises(ValueError, match="Unknown agent"):
        sl.dispatch_agent("unknownbot", "do thing")

def test_dispatch_agent_appends_to_existing_jobs(project_dir, monkeypatch):
    import bin.synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    sl.dispatch_agent("claude", "task one")
    sl.dispatch_agent("claude", "task two")
    assert len(sl._load_jobs()) == 2
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "dispatch_agent" -v
```

Expected: 4 FAILED

- [ ] **Step 3: Implement**

Add after `_llm_enrich()` in `bin/synlynk.py`:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None) -> dict:
    """Dispatches an agent to run a task in the background.

    Uses non-interactive agent mode (no PTY). Stdout captured to
    .synlynk/logs/<job_id>.log. Returns the job dict.
    Raises ValueError for unknown agent names.
    """
    if agent not in AGENT_CAPABILITY_BASELINES:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")

    baselines = AGENT_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]

    # Unique job ID based on timestamp + agent.
    import hashlib as _hashlib
    job_id = "job-" + _hashlib.md5(
        f"{agent}{task}{time.time()}".encode()
    ).hexdigest()[:8]

    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    log_file = os.path.join(LOGS_DIR, f"{job_id}.log")
    prompt_file = os.path.join(PROMPTS_DIR, f"{job_id}.md")

    # Build prompt: context snapshot + task description.
    generate_context(scope="full")
    context_path = ".synlynk/context.md"
    context_text = ""
    if os.path.exists(context_path):
        context_text = open(context_path).read()

    story_line = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""
    prompt = f"{context_text}{story_line}\n\n## Your Task\n{task}\n"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    # Launch agent non-interactively, detached from terminal.
    cmd = [cli] + flags
    with open(log_file, "w") as log_out, open(prompt_file) as prompt_in:
        proc = subprocess.Popen(
            cmd,
            stdin=prompt_in,
            stdout=log_out,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # detach — survives terminal close
        )

    job = {
        "id": job_id,
        "agent": agent,
        "story_id": story_id or "",
        "task": task,
        "pid": proc.pid,
        "log_file": log_file,
        "prompt_file": prompt_file,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ended_at": None,
        "status": "running",
        "exit_code": None,
    }

    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)

    log_telemetry_event({"type": "dispatch", "agent": agent,
                         "story_id": story_id, "job_id": job_id})
    return job
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "dispatch_agent" -v
```

Expected: 4 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: dispatch_agent — background non-interactive agent dispatch with PID tracking"
```

---

## Task 9: `synlynk jobs`

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cmd_jobs_prints_running_jobs(project_dir, monkeypatch, capsys):
    import bin.synlynk as sl
    jobs = [
        {"id": "job-aaa", "agent": "claude", "story_id": "14", "task": "do thing",
         "pid": 99, "status": "running", "started_at": "2026-06-14T10:00:00",
         "ended_at": None, "exit_code": None, "log_file": ".synlynk/logs/job-aaa.log"},
    ]
    sl._save_jobs(jobs)
    sl.cmd_jobs()
    out = capsys.readouterr().out
    assert "job-aaa" in out
    assert "claude" in out
    assert "running" in out

def test_cmd_jobs_empty_output_when_no_jobs(project_dir, capsys):
    import bin.synlynk as sl
    sl.cmd_jobs()
    out = capsys.readouterr().out
    assert "No jobs" in out or out.strip() == "" or "no jobs" in out.lower()
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "cmd_jobs" -v
```

Expected: 2 FAILED

- [ ] **Step 3: Implement**

Add after `dispatch_agent()` in `bin/synlynk.py`:

```python
def cmd_jobs(all_jobs: bool = False) -> None:
    """Prints active (and optionally completed) jobs."""
    _reconcile_jobs()
    jobs = _load_jobs()
    if not jobs:
        print("No jobs found. Use `synlynk dispatch <agent> --task <task>` to start one.")
        return
    visible = jobs if all_jobs else [j for j in jobs if j["status"] == "running"]
    if not visible:
        completed = len([j for j in jobs if j["status"] in ("completed", "failed")])
        print(f"No running jobs. ({completed} completed/failed — use `synlynk jobs --all` to see)")
        return
    header = f"{'ID':12}  {'AGENT':10}  {'STATUS':10}  {'STORY':6}  TASK"
    print(f"{_BOLD}{header}{_RESET}")
    print("─" * 70)
    for j in visible:
        sid = (j.get("story_id") or "—")[:6]
        task = (j.get("task") or "")[:40]
        status = j["status"]
        color = _GREEN if status == "running" else (_DIM if status == "completed" else _YELLOW)
        print(f"{j['id']:12}  {j['agent']:10}  {color}{status:10}{_RESET}  {sid:6}  {task}")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "cmd_jobs" -v
```

Expected: 2 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: cmd_jobs — synlynk jobs with PID reconciliation and status table"
```

---

## Task 10: `synlynk logs`

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cmd_logs_prints_log_content(project_dir, capsys):
    import bin.synlynk as sl
    os.makedirs(".synlynk/logs", exist_ok=True)
    job = {"id": "job-bbb", "agent": "claude", "status": "running",
            "log_file": ".synlynk/logs/job-bbb.log", "pid": 1,
            "story_id": "", "task": "t", "started_at": "2026-06-14T10:00:00",
            "ended_at": None, "exit_code": None, "prompt_file": ""}
    sl._save_jobs([job])
    open(".synlynk/logs/job-bbb.log", "w").write("Agent output line 1\nAgent output line 2\n")
    sl.cmd_logs("job-bbb")
    out = capsys.readouterr().out
    assert "Agent output line 1" in out

def test_cmd_logs_error_for_missing_job(project_dir, capsys):
    import bin.synlynk as sl
    sl.cmd_logs("job-missing")
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "no job" in out.lower()
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "cmd_logs" -v
```

Expected: 2 FAILED

- [ ] **Step 3: Implement**

Add after `cmd_jobs()` in `bin/synlynk.py`:

```python
def cmd_logs(job_id: str, tail: int = 50) -> None:
    """Prints the captured stdout of a dispatched job."""
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        print(f"No job found with id '{job_id}'. Run `synlynk jobs` to list jobs.")
        return
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        print(f"Log file not found for job {job_id}.")
        return
    print(f"{_BOLD}── logs: {job_id} ({job['agent']}) ─────────────────────────{_RESET}")
    with open(log_file) as f:
        lines = f.readlines()
    for line in lines[-tail:]:
        print(line, end="")
    if len(lines) > tail:
        print(f"\n{_DIM}(showing last {tail} of {len(lines)} lines){_RESET}")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "cmd_logs" -v
```

Expected: 2 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: cmd_logs — tail captured agent stdout by job id"
```

---

## Task 11: `synlynk shell`

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cmd_shell_spawns_subshell(project_dir, monkeypatch):
    import bin.synlynk as sl
    spawned = []
    def fake_run(cmd, **kw):
        spawned.append((cmd, kw))
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl.cmd_shell(story_id="14")
    assert any(isinstance(c, list) and any("sh" in str(x) for x in c)
               for c, _ in spawned)

def test_cmd_shell_injects_synlynk_env(project_dir, monkeypatch):
    import bin.synlynk as sl
    captured_env = {}
    def fake_run(cmd, **kw):
        captured_env.update(kw.get("env", {}))
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl.cmd_shell(story_id="42")
    assert captured_env.get("SYNLYNK_STORY_ID") == "42"
    assert "SYNLYNK_PROJECT_DIR" in captured_env
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "cmd_shell" -v
```

Expected: 2 FAILED

- [ ] **Step 3: Implement**

Add after `cmd_logs()` in `bin/synlynk.py`:

```python
def cmd_shell(story_id: str = None) -> None:
    """Spawns an interactive subshell with synlynk context env vars injected.

    The shell runs in the current directory (worktree-per-story lands in v0.5.0).
    On exit the calling process resumes normally.
    """
    shell = os.environ.get("SHELL", "/bin/bash")
    env = {**os.environ,
           "SYNLYNK_PROJECT_DIR": os.path.abspath("."),
           "SYNLYNK_STORY_ID": story_id or "",
           "SYNLYNK_CONTEXT": os.path.abspath(".synlynk/context.md")}
    label = f"story #{story_id}" if story_id else "synlynk"
    print(f"{_BOLD}Entering synlynk shell ({label}).{_RESET} "
          f"Type {_CYAN}exit{_RESET} to return.")
    subprocess.run([shell], env=env)
    print(f"{_DIM}Returned from synlynk shell.{_RESET}")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "cmd_shell" -v
```

Expected: 2 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: cmd_shell — context-injected subshell for story handoff"
```

---

## Task 12: `synlynk launch`

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cmd_launch_starts_agent_interactively(project_dir, monkeypatch):
    import bin.synlynk as sl
    launched = []
    def fake_run(cmd, **kw):
        launched.append(cmd)
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl.cmd_launch("claude", story_id="14")
    assert any("claude" in str(c) for c in launched)

def test_cmd_launch_unknown_agent_prints_error(project_dir, capsys):
    import bin.synlynk as sl
    sl.cmd_launch("unknownbot", story_id="1")
    out = capsys.readouterr().out
    assert "unknown" in out.lower() or "not found" in out.lower()

def test_cmd_launch_generates_agent_context(project_dir, monkeypatch):
    import bin.synlynk as sl
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: type("R", (), {"returncode": 0})())
    sl.cmd_launch("claude", story_id="5")
    assert os.path.exists(".synlynk/context-claude.md")
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "cmd_launch" -v
```

Expected: 3 FAILED

- [ ] **Step 3: Implement**

Add after `cmd_shell()` in `bin/synlynk.py`:

```python
def cmd_launch(agent: str, story_id: str = None) -> None:
    """Launches an agent CLI interactively in the current directory.

    Pre-generates .synlynk/context-<agent>.md and starts the CLI so the
    agent reads it as initial context. Stdout/stderr are not captured —
    this is an interactive session. Telemetry is logged on exit.
    """
    if agent not in AGENT_CAPABILITY_BASELINES:
        print(f"Unknown agent '{agent}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")
        return

    cli = AGENT_CAPABILITY_BASELINES[agent]["cli"]

    # Generate agent-scoped context snapshot.
    generate_context(scope="full")
    src = ".synlynk/context.md"
    dest = f".synlynk/context-{agent}.md"
    if os.path.exists(src):
        import shutil as _shutil
        _shutil.copy(src, dest)

    label = f"story #{story_id}" if story_id else "interactive session"
    print(f"{_BOLD}Launching {agent} — {label}.{_RESET}")
    print(f"  Context: {_CYAN}{dest}{_RESET}")
    print(f"  Exit the agent to return to synlynk.\n")

    start = time.time()
    result = subprocess.run([cli])
    duration = time.time() - start

    log_telemetry_event({"type": "launch", "agent": agent,
                         "story_id": story_id, "exit_code": result.returncode,
                         "duration_s": round(duration, 1)})
    update_costs(cli, 0, 0, duration)
    print(f"\n{_DIM}Returned from {agent}. Duration: {duration:.0f}s{_RESET}")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "cmd_launch" -v
```

Expected: 3 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: cmd_launch — interactive agent CLI launcher with context pre-load"
```

---

## Task 13: `synlynk run --trio`

**Files:**
- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cmd_run_trio_dispatches_three_agents(project_dir, monkeypatch):
    import bin.synlynk as sl
    dispatched = []
    def fake_dispatch(agent, task, story_id=None):
        dispatched.append(agent)
        return {"id": f"job-{agent}", "agent": agent, "pid": 1, "status": "running",
                "task": task, "story_id": story_id, "log_file": "", "prompt_file": "",
                "started_at": "2026-06-14T10:00:00", "ended_at": None, "exit_code": None}
    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch)
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [
        {"name": "claude", "functional": True, "roles": ["architect", "builder"],
         "cli": "claude", "version": "2", "capabilities": [], "non_interactive_flags": ["--print"],
         "discovery_path": ""},
        {"name": "gemini", "functional": True, "roles": ["builder", "verifier"],
         "cli": "gemini", "version": "1", "capabilities": [], "non_interactive_flags": [],
         "discovery_path": ""},
        {"name": "codex", "functional": True, "roles": ["builder"],
         "cli": "codex", "version": "1", "capabilities": [], "non_interactive_flags": [],
         "discovery_path": ""},
    ])
    sl.cmd_run_trio("implement the auth feature")
    assert len(dispatched) == 3
    assert "claude" in dispatched

def test_cmd_run_trio_warns_with_fewer_than_three_agents(project_dir, monkeypatch, capsys):
    import bin.synlynk as sl
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [
        {"name": "claude", "functional": True, "roles": ["architect"],
         "cli": "claude", "version": "2", "capabilities": [], "non_interactive_flags": [],
         "discovery_path": ""},
    ])
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: {"id": "j", "pid": 1,
        "status": "running", "agent": "claude", "task": "", "story_id": "",
        "log_file": "", "prompt_file": "", "started_at": "", "ended_at": None, "exit_code": None})
    sl.cmd_run_trio("do thing")
    out = capsys.readouterr().out
    assert "1" in out or "agent" in out.lower()
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_synlynk.py -k "cmd_run_trio" -v
```

Expected: 2 FAILED

- [ ] **Step 3: Implement**

Add after `cmd_launch()` in `bin/synlynk.py`:

```python
def cmd_run_trio(task: str, story_id: str = None) -> None:
    """Dispatches all functional agents in parallel — one job per agent.

    This is a parallel convenience wrapper, NOT the sequential Trio pipeline.
    Each agent gets the same task description and full context. For the
    sequential Architect→Build→Verify pipeline, see the Trio Protocol spec.
    """
    agents = [a for a in discover_agents() if a["functional"]]
    if not agents:
        print("No functional agents found. Run `synlynk init` to set up your Hybrid Workgroup.")
        return
    if len(agents) < 3:
        print(f"  {_YELLOW}Only {len(agents)} agent(s) available "
              f"(trio needs 3). Dispatching what's configured.{_RESET}")

    print(f"{_BOLD}✨ Dispatching {len(agents)} agents in parallel{_RESET}")
    print(f"  Task: {task}\n")

    jobs = []
    for ag in agents:
        job = dispatch_agent(ag["name"], task, story_id=story_id)
        jobs.append(job)
        role = ag["roles"][0] if ag["roles"] else "worker"
        print(f"  {_GREEN}▶{_RESET} [{job['id']}] {ag['name']:10} → {role}  PID {job['pid']}")

    print(f"\n  {_DIM}All agents running in background.{_RESET}")
    print(f"  Monitor with: {_CYAN}synlynk jobs{_RESET}")
    print(f"  View output:  {_CYAN}synlynk logs <job-id>{_RESET}")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_synlynk.py -k "cmd_run_trio" -v
```

Expected: 2 PASSED

- [ ] **Step 5: Full suite**

```
pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: cmd_run_trio — parallel dispatch convenience wrapper (not the Trio pipeline)"
```

---

## Task 14: Wire subcommands, startup reconciliation, E2E tests

**Files:**
- Modify: `bin/synlynk.py` (`main()`)
- Modify: `tests/test_e2e.py`

- [ ] **Step 1: Write failing E2E tests**

Add to `tests/test_e2e.py`:

```python
def test_dispatch_creates_job(cli):
    # dispatch requires a functional agent CLI — mock it via PATH
    import shutil, sys
    fake_bin = cli.project / ".fake_bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    fake_claude.write_text("#!/bin/sh\ncat > /dev/null\n")
    fake_claude.chmod(0o755)
    env = {**os.environ, "PATH": str(fake_bin) + ":" + os.environ["PATH"]}
    r = cli.run(["dispatch", "claude", "--task", "test task"], env=env)
    assert r.returncode == 0
    jobs_file = cli.project / ".synlynk" / "jobs.json"
    assert jobs_file.exists()
    import json as _json
    jobs = _json.loads(jobs_file.read_text())
    assert len(jobs) == 1
    assert jobs[0]["agent"] == "claude"

def test_jobs_shows_no_jobs_when_empty(cli):
    r = cli.run(["jobs"])
    assert r.returncode == 0
    assert "no jobs" in r.stdout.lower() or r.stdout.strip() == ""

def test_logs_error_for_missing_job(cli):
    r = cli.run(["logs", "--job", "job-missing"])
    assert r.returncode == 0  # exits cleanly
    assert "not found" in r.stdout.lower() or "no job" in r.stdout.lower()

def test_reconcile_runs_on_startup(cli):
    import json as _json
    # Inject a stale job with an impossible PID.
    jobs = [{"id": "job-stale", "agent": "claude", "pid": 9999999, "status": "running",
              "task": "stale", "story_id": "", "log_file": "", "prompt_file": "",
              "started_at": "2026-06-14T09:00:00", "ended_at": None, "exit_code": None}]
    (cli.project / ".synlynk" / "jobs.json").write_text(_json.dumps(jobs))
    # Any command should trigger reconciliation.
    r = cli.run(["jobs"])
    assert r.returncode == 0
    result = _json.loads((cli.project / ".synlynk" / "jobs.json").read_text())
    assert result[0]["status"] == "failed"
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_e2e.py::test_dispatch_creates_job tests/test_e2e.py::test_jobs_shows_no_jobs_when_empty tests/test_e2e.py::test_logs_error_for_missing_job tests/test_e2e.py::test_reconcile_runs_on_startup -v
```

Expected: 4 FAILED

- [ ] **Step 3: Wire new subcommands into `main()`**

In `bin/synlynk.py`, find `main()` and add the following:

After the existing `sentinel_parser` block and before `args = parser.parse_args()`, add:

```python
    dispatch_parser = subparsers.add_parser(
        "dispatch", help="Dispatch an agent to run a task in the background")
    dispatch_parser.add_argument("agent",
        help="Agent name: claude, gemini, codex, agy")
    dispatch_parser.add_argument("--task", required=True,
        help="Task description for the agent")
    dispatch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story/task ID for context labelling")

    jobs_parser = subparsers.add_parser("jobs", help="List dispatched background jobs")
    jobs_parser.add_argument("--all", action="store_true", dest="all_jobs",
        help="Include completed and failed jobs")

    logs_parser = subparsers.add_parser("logs", help="Tail the output log of a job")
    logs_parser.add_argument("--job", required=True, dest="job_id",
        help="Job ID (from `synlynk jobs`)")
    logs_parser.add_argument("--tail", type=int, default=50,
        help="Number of lines to show (default: 50)")

    shell_parser = subparsers.add_parser(
        "shell", help="Spawn a subshell with synlynk context injected")
    shell_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID to label the shell session")

    launch_parser = subparsers.add_parser(
        "launch", help="Launch an agent CLI interactively with pre-loaded context")
    launch_parser.add_argument("agent", help="Agent name: claude, gemini, codex, agy")
    launch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")

    run_parser = subparsers.add_parser(
        "run", help="Convenience wrappers for common dispatch patterns")
    run_sub = run_parser.add_subparsers(dest="run_action")
    trio_parser = run_sub.add_parser("--trio",
        help="Dispatch all functional agents in parallel (not the sequential Trio pipeline)")
    trio_parser.add_argument("--task", required=True,
        help="Task description sent to all agents")
    trio_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")
```

After all the existing `elif args.command == ...` blocks in `main()`, add:

```python
    elif args.command == "dispatch":
        _reconcile_jobs()
        try:
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id)
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "jobs":
        cmd_jobs(all_jobs=getattr(args, "all_jobs", False))
    elif args.command == "logs":
        cmd_logs(args.job_id, tail=getattr(args, "tail", 50))
    elif args.command == "shell":
        cmd_shell(story_id=getattr(args, "story_id", None))
    elif args.command == "launch":
        cmd_launch(args.agent, story_id=getattr(args, "story_id", None))
    elif args.command == "run":
        action = getattr(args, "run_action", None)
        if action == "--trio":
            _reconcile_jobs()
            cmd_run_trio(args.task, story_id=getattr(args, "story_id", None))
        else:
            run_parser.print_help()
```

Also add `_reconcile_jobs()` as the very first call inside `main()`, before `parser = argparse.ArgumentParser(...)`:

```python
def main() -> None:
    _reconcile_jobs()   # ← ADD THIS LINE — probe PIDs on every invocation
    parser = argparse.ArgumentParser(
```

- [ ] **Step 4: Run E2E tests**

```
pytest tests/test_e2e.py::test_dispatch_creates_job tests/test_e2e.py::test_jobs_shows_no_jobs_when_empty tests/test_e2e.py::test_logs_error_for_missing_job tests/test_e2e.py::test_reconcile_runs_on_startup -v
```

Expected: 4 PASSED

- [ ] **Step 5: Full suite — all tests must pass**

```
pytest tests/ -v --tb=short
```

Expected: 140+ tests (all existing) + ~35 new tests — all green.

- [ ] **Step 6: Smoke test manually**

```bash
python3 bin/synlynk.py jobs
python3 bin/synlynk.py --version
python3 bin/synlynk.py dispatch --help
python3 bin/synlynk.py run --help
```

Expected: `synlynk 0.4.0`, help text for new commands, "No jobs found" for jobs.

- [ ] **Step 7: Commit**

```bash
git add bin/synlynk.py tests/test_e2e.py
git commit -m "feat: wire dispatch/jobs/logs/shell/launch/run subcommands; startup PID reconciliation"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task(s) |
|---|---|
| Intelligent init TUI wizard (progressive) | Task 7 |
| Two-pass semantic discovery | Tasks 4, 5, 6 |
| Agent/CLI discovery with functional check | Task 3 |
| Configurable discovery paths | Task 3 |
| Magic Moment 1 — "You have Hybrid Workgroup" | Task 7 (wizard step 2) |
| Magic Moment 2 — parallel dispatch from shell | Tasks 8, 13, 14 |
| Shell-native dispatch: `synlynk dispatch` | Tasks 8, 14 |
| Shell-native dispatch: `synlynk jobs` | Tasks 9, 14 |
| Shell-native dispatch: `synlynk logs` | Tasks 10, 14 |
| PID tracking in `.synlynk/jobs.json` | Task 2 |
| PID reconciliation on startup | Tasks 2, 14 |
| `synlynk shell --story <id>` | Tasks 11, 14 |
| `synlynk launch <agent> --story <id>` | Tasks 12, 14 |
| Cloud directory nudge in wizard | Task 7 (wizard step 5) |
| `synlynk run --trio` as parallel convenience | Tasks 13, 14 |
| Single-file / zero-pip-dep | All tasks (stdlib only) |
| Non-interactive agent modes only | Tasks 6, 8 (flags from AGENT_CAPABILITY_BASELINES) |
| Context injection per agent (context-<agent>.md) | Tasks 8, 12 |
| VERSION 0.4.0 | Task 1 |

All spec requirements covered. ✓

### Open questions resolved in this plan

- **Q1 Multi-repo init:** v0.4.0 scans local repo only. `_static_scan(root)` stays single-repo.
- **Q2 Capability registry:** Shipped as `AGENT_CAPABILITY_BASELINES` hardcoded dict in Task 1.
- **Q3 PTY wrapper:** Non-interactive only in v0.4.0. Interactive `launch` uses `subprocess.run` (no PTY management needed since it inherits the parent terminal). Full PTY wrapper deferred to v0.7.0.
- **Q4 Wizard depth:** Runs only when no `.synlynk/` exists, or with `--force`.
