# Safe Fleet Parity Migration Engine & In-Browser Role Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Worktree-Isolated Shadow Parity Engine (`synlynk heal --parity`) and the `synlynk viz` In-Browser 6-Role Provisioning Wizard, then execute safe parity remediation across `cc-videoreframing`, `playblazer-ng`, and `hitchcock`.

**Architecture:** A stack-aware declarative migration module (`synlynk/parity.py`) executes non-destructive directive AST parsing and policy synthesis in a temporary background worktree (`.worktrees/synlynk-parity-check`), while `synlynk viz` exposes a local GitHub App manifest flow (`/onboarding/roles`) to configure and self-test all 6 canonical workspace roles (`pm`, `tpm`, `qa`, `dev`, `architect`, `marketing`).

**Tech Stack:** Python 3.10+, SQLite (WAL mode), Git worktrees, GitHub App Manifest API, HTML5/CSS, Server-Sent Events (SSE).

**Spec:** `docs/superpowers/specs/2026-09-12-safe-fleet-parity-migration-engine-design.md`

## Global Constraints
- Sacred User Directives: Code and text outside explicit `<!-- synlynk:start -->` and `<!-- synlynk:harness -->` tags must NEVER be altered or deleted.
- Non-Python Safe: Auto-detect Node/Go/Rust/Python; never inject Python-specific branch protection rules into non-Python repositories.
- Worktree-First Isolation: Parity remediation operations must occur in `.worktrees/synlynk-parity-check`; working directory must never be left dirty on abort or failure.
- Recursive Gitignore: Enforce `**/.synlynk/*` with whitelist exceptions (`!**/.synlynk/policy.json`, etc.).
- 100% Test Passing: All new features must include focused unit tests; zero regression across existing 2,800+ test suite.

---

### Task 1: Stack Detection & Directive AST/Fence Parser

**Files:**
- Create: `synlynk/parity.py`
- Test: `tests/test_parity.py`

**Interfaces:**
- Produces:
  - `detect_project_stack(repo_path: str) -> Dict[str, Any]`: Returns language (`node`, `go`, `python`, `mixed`), test command, and default role mapping.
  - `parse_directive_fences(content: str) -> Tuple[str, Optional[str], Optional[str]]`: Returns `(user_header, synlynk_start_block, synlynk_harness_block)`.
  - `inject_sop_fences(content: str, tool: str, version: str, sops: Dict[str, str]) -> str`: Non-destructively replaces or appends SOP blocks while preserving user headers.

- [ ] **Step 1: Write failing tests for stack detection and fence parsing**
```python
# tests/test_parity.py
import pytest
from synlynk.parity import detect_project_stack, parse_directive_fences, inject_sop_fences

def test_detect_project_stack_node(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "my-app", "scripts": {"test": "vitest"}}')
    stack = detect_project_stack(str(tmp_path))
    assert stack["language"] == "node"
    assert "vitest" in stack["test_cmd"] or "npm test" in stack["test_cmd"]

def test_parse_directive_fences_preserves_user_content():
    sample = """# My Project
Custom guidelines and domain rules.

<!-- synlynk:start version="0.18.0" tool="claude" -->
# Old synlynk block
<!-- synlynk:end -->

<!-- synlynk:harness v0.150.1 -->
# Old harness
"""
    user_header, start_block, harness_block = parse_directive_fences(sample)
    assert "# My Project" in user_header
    assert "Custom guidelines and domain rules." in user_header
    assert "<!-- synlynk:start" not in user_header
```

- [ ] **Step 2: Run tests to confirm failure**
```bash
python3 -m pytest tests/test_parity.py -v
```

- [ ] **Step 3: Implement stack detection and fence parsing in `synlynk/parity.py`**
Implement `detect_project_stack`, `parse_directive_fences`, and `inject_sop_fences` with regex-based non-destructive tokenization.

- [ ] **Step 4: Verify tests pass**
```bash
python3 -m pytest tests/test_parity.py -v
```

- [ ] **Step 5: Commit changes**
```bash
git add synlynk/parity.py tests/test_parity.py
git commit -m "feat(parity): implement stack detection and directive fence parser

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 2: Worktree-Isolated Shadow Parity Engine & CLI `heal --parity`

**Files:**
- Modify: `synlynk/parity.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Test: `tests/test_parity.py`

**Interfaces:**
- Produces:
  - `run_parity_remediation(repo_path: str, dry_run: bool = False, branch: Optional[str] = None) -> Dict[str, Any]`: Creates worktree, applies fences, generates policy, runs test suite, commits, and returns PR diff.
  - `cmd_heal_parity(args)`: CLI handler for `synlynk heal --parity`.

- [ ] **Step 1: Write failing tests for worktree-isolated parity remediation**
```python
# tests/test_parity.py
def test_run_parity_remediation_dry_run(tmp_path):
    # Setup mock git repository with un-fenced CLAUDE.md
    ...
    res = run_parity_remediation(str(tmp_path), dry_run=True)
    assert res["status"] == "DRY_RUN"
    assert "CLAUDE.md" in res["files_to_touch"]
```

- [ ] **Step 2: Run tests to confirm failure**
```bash
python3 -m pytest tests/test_parity.py -k "test_run_parity_remediation" -v
```

- [ ] **Step 3: Implement worktree orchestration and `heal --parity` command**
Implement git worktree creation, `.synlynk/policy.json` generation with detected test commands, recursive `.gitignore` rule injection, and CLI binding in `synlynk/cli.py` and `synlynk/taxonomy.py`.

- [ ] **Step 4: Verify tests pass**
```bash
python3 -m pytest tests/test_parity.py -v
```

- [ ] **Step 5: Commit changes**
```bash
git add synlynk/parity.py synlynk/cli.py synlynk/taxonomy.py tests/test_parity.py
git commit -m "feat(parity): implement worktree-isolated shadow parity engine and CLI heal --parity

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 3: Doctor `_hc_fleet_parity` Diagnostic Check

**Files:**
- Modify: `synlynk/doctor.py`
- Test: `tests/test_parity.py`

**Interfaces:**
- Produces:
  - `check_fleet_parity(repo_path: str) -> Dict[str, Any]`: Checks whether directives have modern `<!-- synlynk:harness -->` fences, whether `policy.json` exists and passes Point 3 readiness, and whether `workgroup_agents` contains all 4 harnesses.

- [ ] **Step 1: Write failing test for `check_fleet_parity`**
```python
def test_check_fleet_parity_detects_drift(tmp_path):
    res = check_fleet_parity(str(tmp_path))
    assert res["status"] in ("WARN", "FAIL")
    assert "synlynk heal --parity" in res["remediation"]
```

- [ ] **Step 2: Implement check in `synlynk/doctor.py`**
Wire `check_fleet_parity` into `synlynk doctor` as `_hc_fleet_parity`.

- [ ] **Step 3: Verify tests pass**
```bash
python3 -m pytest tests/test_parity.py -k "test_check_fleet_parity" -v
```

- [ ] **Step 4: Commit changes**
```bash
git add synlynk/doctor.py tests/test_parity.py
git commit -m "feat(doctor): add fleet parity diagnostic check with heal --parity suggestion

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 4: `synlynk viz` In-Browser 6-Role Provisioning Wizard

**Files:**
- Modify: `synlynk/viz.py`
- Modify: `synlynk/viz_views.py`
- Create: `synlynk/templates/roles_onboarding.html` (or inline in `synlynk/viz.py`)
- Test: `tests/test_viz_onboarding.py`

**Interfaces:**
- Produces:
  - Route `/onboarding/roles`: Renders 6 role cards (`pm`, `tpm`, `qa`, `dev`, `architect`, `marketing`) with "Provision with GitHub" manifest form.
  - Route `/auth/callback`: Receives `code`, converts manifest via GitHub API, writes `.synlynk/github_apps/<role>/`, and registers roles in `roles.yaml` and `policy.json`.

- [ ] **Step 1: Write failing tests for viz onboarding endpoints**
```python
# tests/test_viz_onboarding.py
def test_roles_onboarding_route_renders():
    ...
```

- [ ] **Step 2: Implement manifest generator and callback conversion in `synlynk/viz.py`**
Implement GitHub App Manifest schema generation, loopback handler, credentials writer, and automatic token refresh.

- [ ] **Step 3: Verify tests pass**
```bash
python3 -m pytest tests/test_viz_onboarding.py -v
```

- [ ] **Step 4: Commit changes**
```bash
git add synlynk/viz.py tests/test_viz_onboarding.py
git commit -m "feat(viz): implement in-browser GitHub App role provisioning wizard

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 5: Live 4-Point Readiness Self-Test Integration

**Files:**
- Modify: `synlynk/viz.py`
- Modify: `synlynk/readiness.py`
- Test: `tests/test_viz_onboarding.py`

**Interfaces:**
- Produces:
  - Route `/api/readiness/live`: Streams 4-point readiness verification (`evaluate_readiness_matrix`) in real time.
  - CLI auto-launch helper: Prompts and opens `synlynk viz` in default browser if unprovisioned roles are detected during `synlynk init`, `synlynk join`, or `synlynk heal --parity`.

- [ ] **Step 1: Write failing test for live readiness endpoint**
```python
def test_live_readiness_api_returns_points():
    ...
```

- [ ] **Step 2: Implement endpoint and browser trigger helper**
Wired into `evaluate_readiness_matrix()`.

- [ ] **Step 3: Run full readiness and viz test suites**
```bash
python3 -m pytest tests/test_readiness_matrix.py tests/test_viz_onboarding.py -v
```

- [ ] **Step 4: Commit changes**
```bash
git add synlynk/viz.py synlynk/readiness.py tests/test_viz_onboarding.py
git commit -m "feat(viz): add live 4-point readiness self-test streaming and auto-launch helper

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 6: Execute Fleet Remediation Playbooks (`cc-videoreframing`, `playblazer-ng`, `hitchcock`)

**Repositories:**
- `/Users/nikhilsoman/dev/cc-videoreframing`
- `/Users/nikhilsoman/dev/playblazer-ng`
- `/Users/nikhilsoman/dev/hitchcock`

**Steps:**
- [ ] **Step 1: Remediate `cc-videoreframing`**
  - Run `synlynk heal --parity` in `/Users/nikhilsoman/dev/cc-videoreframing`.
  - Verify Python test suite passes.
  - Review and merge PR.
- [ ] **Step 2: Remediate `playblazer-ng`**
  - Run `synlynk heal --parity` in `/Users/nikhilsoman/dev/playblazer-ng`.
  - Verify Go test suite passes.
  - Review and merge PR.
- [ ] **Step 3: Remediate `hitchcock`**
  - Run `synlynk heal --parity` in `/Users/nikhilsoman/dev/hitchcock`.
  - Verify Electron/Node and Python tests pass.
  - Review and merge PR.
- [ ] **Step 4: Verify all 3 repositories report green across `synlynk doctor` and `synlynk doctor --readiness`**
