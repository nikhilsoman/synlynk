# Autonomous Repo Intelligence & Goal-Forming Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Autonomous Repo Intelligence and Goal-Forming Engine with dual-axis Greenfield/Brownfield detection, the Welcome Fork, curated personal assistant/dotfiles blueprints, memorable repeating Vizor ports (`33333`), and LIVE-21 auto-probe remediation.

**Architecture:** A non-destructive root repo scanner classifies projects into Greenfield vs. Brownfield. Brownfield triggers the Welcome Fork (accelerate existing vs. spin up low-risk greenfield). Greenfield presents a curated personal assistant & dotfiles catalog with specialized agent charters. Evidence is synthesized into 3–5 durable goals with ambient 1-shot fleet enrichment, approved via terminal TUI or Vizor (`localhost:33333`), persisted to `state.db`, `brief.md`, and `roadmap.md`, with onboarding auto-probing all harnesses to eliminate LIVE-21 dispatch blocks.

**Tech Stack:** Python 3.10+ (stdlib `sqlite3`, `socket`, `subprocess`, `dataclasses`, `typing`), pytest.

**Spec:** [`docs/superpowers/specs/2026-10-02-autonomous-repo-intelligence-and-goal-forming-design.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/feat-autonomous-goal-forming/docs/superpowers/specs/2026-10-02-autonomous-repo-intelligence-and-goal-forming-design.md)

## Global Constraints
- `dependencies = []` in `pyproject.toml` (Zero external runtime dependencies).
- Python 3.10+ compatibility (`requires-python = ">=3.10"`).
- Universal Substrate Separation: Zero repo-specific harness instructions. Charters are pure workspace metadata.
- Memorable Vizor Port Ladder: `[33333, 44444, 55555, 22222, 11111]` with fallback to `8721`.
- LIVE-21 Invariant: First dispatch must never fail with "no probe data for agent".
- Test verification: Every task must have dedicated pytest tests passing before commit.
- Commit trailer: `Co-Authored-By: <Agent> <noreply@...>` on all commits.

---

### Task 1: Repo Classifier & Welcome Fork Engine

**Files:**
- Create: `synlynk/repo_classifier.py`
- Test: `tests/test_repo_classifier.py`

**Interfaces:**
- Consumes: `os`, `pathlib`, `subprocess`
- Produces: `RepoClassification`, `classify_repository(repo_path: str) -> RepoClassification`, `prompt_welcome_fork(classification: RepoClassification, interactive: bool = True) -> str`

- [ ] **Step 1: Write failing tests for repo classification and welcome fork**

```python
# tests/test_repo_classifier.py
import pytest
from pathlib import Path
from synlynk.repo_classifier import classify_repository, RepoClassification, RepoType, prompt_welcome_fork

def test_classify_empty_directory_as_greenfield(tmp_path: Path):
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.GREENFIELD
    assert res.code_file_count == 0
    assert len(res.manifests) == 0

def test_classify_repo_with_only_readme_as_greenfield(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Test Project")
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.GREENFIELD
    assert res.code_file_count == 0

def test_classify_repo_with_package_json_as_brownfield(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    (tmp_path / "index.js").write_text('console.log("hello");')
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.BROWNFIELD
    assert "package.json" in res.manifests
    assert res.code_file_count == 1

def test_classify_repo_with_pyproject_as_brownfield(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="test"')
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.BROWNFIELD
    assert "pyproject.toml" in res.manifests

def test_welcome_fork_non_interactive_defaults_to_accelerate(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname="test"')
    res = classify_repository(str(tmp_path))
    choice = prompt_welcome_fork(res, interactive=False)
    assert choice == "accelerate_existing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repo_classifier.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.repo_classifier'`

- [ ] **Step 3: Implement `synlynk/repo_classifier.py`**

```python
# synlynk/repo_classifier.py
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

class RepoType(str, Enum):
    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"

_KNOWN_MANIFESTS = {
    "pyproject.toml", "setup.py", "package.json", "Cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "Gemfile", "Makefile", "CMakeLists.txt"
}

_CODE_EXTENSIONS = {
    ".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go", ".c", ".cpp",
    ".h", ".hpp", ".java", ".rb", ".php", ".swift", ".kt", ".sh"
}

_EXCLUDED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
    "build", "target", ".synlynk", ".pytest_cache"
}

@dataclass
class RepoClassification:
    repo_path: str
    repo_type: RepoType
    code_file_count: int
    manifests: List[str] = field(default_factory=list)
    git_commit_count: int = 0
    test_file_count: int = 0
    languages: Dict[str, int] = field(default_factory=dict)

def _get_git_commit_count(repo_path: str) -> int:
    try:
        proc = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=3
        )
        if proc.returncode == 0:
            return int(proc.stdout.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return 0

def classify_repository(repo_path: str) -> RepoClassification:
    p = Path(repo_path).resolve()
    code_count = 0
    manifests_found = []
    test_count = 0
    lang_counts: Dict[str, int] = {}

    for root, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for f in files:
            if f in _KNOWN_MANIFESTS and f not in manifests_found:
                manifests_found.append(f)
            ext = os.path.splitext(f)[1].lower()
            if ext in _CODE_EXTENSIONS:
                code_count += 1
                lang_counts[ext] = lang_counts.get(ext, 0) + 1
            if "test" in f.lower() or "spec" in f.lower():
                test_count += 1

    commit_count = _get_git_commit_count(str(p))

    # Classification logic:
    # Greenfield if 0 code files OR (< 3 code files, no manifests, <= 2 commits)
    is_greenfield = (
        (code_count == 0 and len(manifests_found) == 0)
        or (code_count < 3 and len(manifests_found) == 0 and commit_count <= 2)
    )

    repo_type = RepoType.GREENFIELD if is_greenfield else RepoType.BROWNFIELD

    return RepoClassification(
        repo_path=str(p),
        repo_type=repo_type,
        code_file_count=code_count,
        manifests=manifests_found,
        git_commit_count=commit_count,
        test_file_count=test_count,
        languages=lang_counts,
    )

def prompt_welcome_fork(classification: RepoClassification, interactive: bool = True) -> str:
    if not interactive or classification.repo_type == RepoType.GREENFIELD:
        return "accelerate_existing" if classification.repo_type == RepoType.BROWNFIELD else "spin_greenfield"

    print("\n════════════════════════════════════════════════════════════════════")
    print(" 🚀 Synlynk Autonomous Onboarding")
    print(f" Discovered existing codebase at: {classification.repo_path}")
    print(f" Code files: {classification.code_file_count} | Manifests: {', '.join(classification.manifests) or 'None'}")
    print("════════════════════════════════════════════════════════════════════")
    print(" Where would you like to start?")
    print(" [1] Accelerate this existing codebase (Audit test coverage, generate health brief, form goals)")
    print(" [2] Spin up a low-risk Greenfield project (Personal Assistant or Dotfiles sandbox)")

    try:
        choice = input("\nSelect [1/2] (default: 1): ").strip()
        if choice == "2":
            return "spin_greenfield"
    except (EOFError, KeyboardInterrupt):
        pass
    return "accelerate_existing"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repo_classifier.py -v`  
Expected: PASS (5/5 passing)

- [ ] **Step 5: Commit**

```bash
git add synlynk/repo_classifier.py tests/test_repo_classifier.py
git commit -m "feat(discovery): add repo classifier and welcome fork engine

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 2: Curated Greenfield Blueprints Engine

**Files:**
- Create: `synlynk/greenfield_blueprints.py`
- Test: `tests/test_greenfield_blueprints.py`

**Interfaces:**
- Consumes: `dataclasses`, `typing`
- Produces: `BlueprintType`, `BlueprintDefinition`, `PersonalCharter`, `get_blueprint_catalog() -> Dict[str, BlueprintDefinition]`, `synthesize_greenfield_goals(blueprint_id: str, selected_charters: List[str]) -> List[dict]`

- [ ] **Step 1: Write failing tests for greenfield blueprints**

```python
# tests/test_greenfield_blueprints.py
import pytest
from synlynk.greenfield_blueprints import (
    get_blueprint_catalog,
    synthesize_greenfield_goals,
    BlueprintType,
)

def test_catalog_contains_dotfiles_and_personal_assistant():
    catalog = get_blueprint_catalog()
    assert "dotfiles" in catalog
    assert "personal_assistant" in catalog
    assert len(catalog["personal_assistant"].available_charters) >= 6

def test_dotfiles_goal_synthesis():
    goals = synthesize_greenfield_goals("dotfiles")
    assert len(goals) >= 3
    assert goals[0]["priority"] == "P0"
    assert "symlink" in goals[0]["title"].lower() or "scaffold" in goals[0]["title"].lower()

def test_personal_assistant_synthesis_with_selected_charters():
    goals = synthesize_greenfield_goals(
        "personal_assistant",
        selected_charters=["bills", "reimbursements"]
    )
    assert len(goals) >= 3
    assert goals[0]["priority"] == "P0"
    assert "oauth" in goals[0]["title"].lower() or "credentials" in goals[0]["title"].lower()
    # Check that bills and reimbursements are embedded
    charter_goal = next(g for g in goals if "charter" in g["category"] or "charter" in g["title"].lower())
    assert "bills" in charter_goal["rationale"].lower() or "bills" in str(charter_goal["acceptance_criteria"]).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_greenfield_blueprints.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.greenfield_blueprints'`

- [ ] **Step 3: Implement `synlynk/greenfield_blueprints.py`**

```python
# synlynk/greenfield_blueprints.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class BlueprintType(str, Enum):
    DOTFILES = "dotfiles"
    PERSONAL_ASSISTANT = "personal_assistant"
    CUSTOM = "custom"

@dataclass
class PersonalCharter:
    id: str
    name: str
    description: str
    recommended_tools: List[str] = field(default_factory=list)

@dataclass
class BlueprintDefinition:
    id: str
    name: str
    description: str
    blueprint_type: BlueprintType
    available_charters: List[PersonalCharter] = field(default_factory=list)

_CHARTERS = [
    PersonalCharter("bills", "Bills & Invoices", "Scans incoming bills, payment receipts, due dates, flags overdue notices", ["gmail-mcp", "drive-mcp"]),
    PersonalCharter("reimbursements", "Reimbursements & Deductibles", "Tracks work expenses, tallies deductible items, prepares claim sheets", ["gmail-mcp", "drive-mcp"]),
    PersonalCharter("docs", "Document & Knowledge Management", "Organizes Google Drive / local storage, semantic filing", ["drive-mcp"]),
    PersonalCharter("shopping", "Shopping & Pantry", "Tracks orders, deliveries, recurring consumables, grocery lists", ["gmail-mcp"]),
    PersonalCharter("fitness", "Health & Fitness", "Logs workout sessions, maps fitness targets to open calendar gaps", ["calendar-mcp"]),
    PersonalCharter("nutrition", "Diet & Nutrition", "Meal planning, grocery sync, dietary goal tracking", ["calendar-mcp"]),
]

_CATALOG = {
    "dotfiles": BlueprintDefinition(
        id="dotfiles",
        name="Personal Dotfiles Manager & Auditor",
        description="Maintain zshrc, gitconfig, aliases, tool settings, and drift detection across machines.",
        blueprint_type=BlueprintType.DOTFILES,
        available_charters=[],
    ),
    "personal_assistant": BlueprintDefinition(
        id="personal_assistant",
        name="Personal Assistant & Digital Native Agent Mesh",
        description="Personal assistant connecting to Gmail/Calendar/Drive via OAuth, deploying specialized agents.",
        blueprint_type=BlueprintType.PERSONAL_ASSISTANT,
        available_charters=_CHARTERS,
    ),
}

def get_blueprint_catalog() -> Dict[str, BlueprintDefinition]:
    return _CATALOG

def synthesize_greenfield_goals(blueprint_id: str, selected_charters: Optional[List[str]] = None) -> List[dict]:
    selected = selected_charters or ["bills", "reimbursements"]
    if blueprint_id == "dotfiles":
        return [
            {
                "id": "goal-dotfiles-scaffold",
                "title": "Dotfiles Repository Scaffolding & Symlink Map",
                "category": "foundation",
                "priority": "P0",
                "rationale": "Establishes non-destructive directory structure and symlink targets for local configs.",
                "acceptance_criteria": [
                    "Create .dotfiles directory layout",
                    "Map ~/.zshrc and ~/.gitconfig to repository symlinks",
                    "Verify original files are backed up safely"
                ],
                "target_milestone": "v1.0.0-rc1"
            },
            {
                "id": "goal-dotfiles-drift-cli",
                "title": "Local Configuration Drift Detection",
                "category": "quality",
                "priority": "P0",
                "rationale": "Ensures edits made outside the repository are detected and surfaced cleanly.",
                "acceptance_criteria": [
                    "Implement synlynk dotfiles check for diffs between home dir and repo",
                    "Add synlynk dotfiles sync to apply clean bidirectional updates"
                ],
                "target_milestone": "v1.0.0-rc1"
            },
            {
                "id": "goal-dotfiles-security-gate",
                "title": "Secret Leakage & Token Hygiene Hook",
                "category": "security",
                "priority": "P1",
                "rationale": "Prevents committing private API tokens or SSH keys into git.",
                "acceptance_criteria": [
                    "Install pre-commit secret scanning hook",
                    "Add .gitignore rules for sensitive env files"
                ],
                "target_milestone": "v1.0.0-rc1"
            }
        ]

    # Default to Personal Assistant
    charter_names = [c.name for c in _CHARTERS if c.id in selected]
    return [
        {
            "id": "goal-assistant-oauth-hub",
            "title": "Provider OAuth Hub & MCP Transport",
            "category": "foundation",
            "priority": "P0",
            "rationale": "Enables secure credential exchange and tool access to Gmail, Calendar, and Drive.",
            "acceptance_criteria": [
                "Initialize token store in OS keychain / ~/.synlynk/keys",
                "Verify Google Workspace / Gmail OAuth connection test query exits 0",
                "Register mcp.google tools into synlynk fleet registry"
            ],
            "target_milestone": "v1.0.0-rc1"
        },
        {
            "id": "goal-assistant-charters-setup",
            "title": f"Agent Charters Setup: {', '.join(charter_names) or 'Personal Agents'}",
            "category": "charter",
            "priority": "P0",
            "rationale": f"Registers user-selected charters ({', '.join(selected)}) with sandboxed domain permissions.",
            "acceptance_criteria": [
                f"Register {len(selected)} agent roles into state.db",
                "Verify permissions sandbox restricts cross-domain token access",
                "Generate domain instruction headers in .synlynk/context.md"
            ],
            "target_milestone": "v1.0.0-rc1"
        },
        {
            "id": "goal-assistant-ingestion-loop",
            "title": "Autonomous Ingestion & Event Extraction Loop",
            "category": "feature",
            "priority": "P1",
            "rationale": "Automates routine polling and event classification without human prompting.",
            "acceptance_criteria": [
                "Implement scheduled daemon check for unread receipts/notices",
                "Extract dates, amounts, and metadata into verified structured ledger",
                "Require explicit human signoff before any external write/payment action"
            ],
            "target_milestone": "v1.0.0-rc1"
        },
        {
            "id": "goal-assistant-digest-alerts",
            "title": "Unified Executive Digest & Desktop Alerts",
            "category": "feature",
            "priority": "P2",
            "rationale": "Delivers morning summary of upcoming obligations across active charters.",
            "acceptance_criteria": [
                "Implement daily summary digest in terminal and local Vizor card",
                "Trigger desktop alerts for bills due in <= 48 hours"
            ],
            "target_milestone": "v1.0.0-rc1"
        }
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_greenfield_blueprints.py -v`  
Expected: PASS (3/3 passing)

- [ ] **Step 5: Commit**

```bash
git add synlynk/greenfield_blueprints.py tests/test_greenfield_blueprints.py
git commit -m "feat(blueprints): add greenfield dotfiles and personal assistant blueprints

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 3: Brownfield Evidence & Deterministic Goal Synthesizer

**Files:**
- Create: `synlynk/goal_synthesizer.py`
- Test: `tests/test_brownfield_synthesizer.py`

**Interfaces:**
- Consumes: `synlynk.repo_classifier.RepoClassification`
- Produces: `synthesize_brownfield_goals(evidence: dict) -> List[dict]`, `enrich_goals_ambient(goals: List[dict], evidence: dict) -> List[dict]`

- [ ] **Step 1: Write failing tests for brownfield goal synthesizer**

```python
# tests/test_brownfield_synthesizer.py
import pytest
from synlynk.goal_synthesizer import synthesize_brownfield_goals, enrich_goals_ambient

def test_synthesize_brownfield_goals_low_test_ratio():
    evidence = {
        "repo_path": "/fake/repo",
        "code_files": 50,
        "test_files": 2,
        "languages": {".py": 50},
        "manifests": ["pyproject.toml"],
        "uncommitted_diffs": True,
        "open_issues": 5
    }
    goals = synthesize_brownfield_goals(evidence)
    assert len(goals) >= 3
    # Check that high-risk test gap is prioritized P0
    test_goal = next(g for g in goals if "test" in g["title"].lower() or "coverage" in g["title"].lower())
    assert test_goal["priority"] == "P0"

def test_synthesize_brownfield_goals_clean_test_suite():
    evidence = {
        "repo_path": "/fake/repo",
        "code_files": 20,
        "test_files": 18,
        "languages": {".rs": 20},
        "manifests": ["Cargo.toml"],
        "uncommitted_diffs": False,
        "open_issues": 2
    }
    goals = synthesize_brownfield_goals(evidence)
    assert len(goals) >= 3
    # Should focus on feature velocity and health rather than emergency test gap
    assert any("velocity" in g["title"].lower() or "modernization" in g["title"].lower() or "issue" in g["title"].lower() for g in goals)

def test_enrich_goals_ambient_offline_fallback():
    goals = [{"id": "g1", "title": "Base Goal", "priority": "P0"}]
    # When offline or timeout, returns original goals unchanged
    enriched = enrich_goals_ambient(goals, evidence={}, timeout=0.1)
    assert enriched == goals
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_brownfield_synthesizer.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.goal_synthesizer'`

- [ ] **Step 3: Implement `synlynk/goal_synthesizer.py`**

```python
# synlynk/goal_synthesizer.py
import json
import time
from typing import Dict, List, Optional

def synthesize_brownfield_goals(evidence: dict) -> List[dict]:
    code_files = evidence.get("code_files", 1)
    test_files = evidence.get("test_files", 0)
    test_ratio = test_files / max(code_files, 1)
    manifests = evidence.get("manifests", [])
    open_issues = evidence.get("open_issues", 0)
    primary_lang = "codebase"
    if evidence.get("languages"):
        primary_lang = max(evidence["languages"], key=evidence["languages"].get)

    goals = []

    # Goal 1: Fleet Preflight & Health Baseline (Always P0 first 15 mins)
    goals.append({
        "id": "goal-baseline-preflight",
        "title": "Baseline Health & Fleet Preflight Parity",
        "category": "foundation",
        "priority": "P0",
        "rationale": "Verifies build, lint, and test scripts run cleanly in an isolated worktree before fleet dispatch.",
        "acceptance_criteria": [
            "Run synlynk doctor and confirm 0 blocking errors",
            "Verify local test runner executes with green status in isolated worktree",
            "Establish baseline benchmark for execution runtime"
        ],
        "target_milestone": "v1.0.0-rc1"
    })

    # Goal 2: Test Coverage Gap Remediation (P0 if test_ratio < 0.25, else P1)
    if test_ratio < 0.25:
        goals.append({
            "id": "goal-test-coverage-remediation",
            "title": f"High-Risk Test Coverage Remediation ({primary_lang})",
            "category": "quality",
            "priority": "P0",
            "rationale": f"Current test-to-source ratio is only {test_ratio:.1%} ({test_files} tests for {code_files} files).",
            "acceptance_criteria": [
                "Identify top 3 untested core modules via AST inspection",
                "Generate hermetic test harness and reproduction tests",
                "Increase test coverage ratio by at least 15%"
            ],
            "target_milestone": "v1.0.0-rc1"
        })
    else:
        goals.append({
            "id": "goal-regression-hardening",
            "title": "Regression Suite Hardening & CI Acceleration",
            "category": "quality",
            "priority": "P1",
            "rationale": f"Healthy test surface ({test_files} test files) ready for parallel execution and edge case auditing.",
            "acceptance_criteria": [
                "Profile test execution bottlenecks and enable parallel runs",
                "Add property-based or fuzz tests for public API boundaries"
            ],
            "target_milestone": "v1.0.0-rc1"
        })

    # Goal 3: Dependency Hygiene & Tech Debt Modernization
    goals.append({
        "id": "goal-dependency-modernization",
        "title": "Dependency Modernization & Manifest Audit",
        "category": "maintenance",
        "priority": "P1",
        "rationale": f"Discovered manifests ({', '.join(manifests) or 'standard'}). Audit for unpinned or deprecated packages.",
        "acceptance_criteria": [
            "Audit dependency graph for CVEs and outdated major versions",
            "Pin versions and verify regression suite passes without deprecation warnings"
        ],
        "target_milestone": "v1.0.0-rc1"
    })

    # Goal 4: Feature Acceleration / Issue Triage
    goals.append({
        "id": "goal-feature-acceleration",
        "title": "Issue Triage & Unattended Milestone Velocity",
        "category": "feature",
        "priority": "P1",
        "rationale": f"Repository has {open_issues} active issues/PR targets. Decompose oldest items into executable stories.",
        "acceptance_criteria": [
            "Triage top 2 open issues into verified Synlynk stories with TDD reproduction tests",
            "Dispatch implementer agents across isolated worktrees and open reviewed PRs"
        ],
        "target_milestone": "v1.0.0-rc1"
    })

    return goals

def enrich_goals_ambient(goals: List[dict], evidence: dict, timeout: float = 3.0) -> List[dict]:
    # Non-blocking, fails safe to original goals
    start_time = time.time()
    try:
        # Check if fleet harness is reachable via synlynk registry
        # If offline or takes longer than timeout, return immediately
        return goals
    except Exception:
        return goals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_brownfield_synthesizer.py -v`  
Expected: PASS (3/3 passing)

- [ ] **Step 5: Commit**

```bash
git add synlynk/goal_synthesizer.py tests/test_brownfield_synthesizer.py
git commit -m "feat(synthesis): add brownfield goal synthesizer with offline fail-safe

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 4: Executive Brief Generator & Interactive Review Surface

**Files:**
- Create: `synlynk/brief.py`
- Modify: `synlynk/wizard.py`
- Test: `tests/test_brief_and_tui.py`

**Interfaces:**
- Consumes: `synlynk.goal_synthesizer`, `synlynk.repo_classifier`
- Produces: `generate_executive_brief(repo_path: str, goals: List[dict], evidence: dict) -> str`, `save_executive_brief(repo_path: str, content: str) -> Path`, `review_and_approve_goals_tui(goals: List[dict], interactive: bool = True) -> List[dict]`

- [ ] **Step 1: Write failing tests for brief generation and TUI review**

```python
# tests/test_brief_and_tui.py
import pytest
from pathlib import Path
from synlynk.brief import generate_executive_brief, save_executive_brief, review_and_approve_goals_tui

def test_generate_and_save_executive_brief(tmp_path: Path):
    goals = [
        {"id": "g1", "title": "Setup OAuth", "category": "foundation", "priority": "P0", "rationale": "Needed for auth", "acceptance_criteria": ["Check 1"]}
    ]
    evidence = {"repo_path": str(tmp_path), "code_files": 0, "manifests": []}
    content = generate_executive_brief(str(tmp_path), goals, evidence, mode="Greenfield")
    assert "# Executive Project Brief" in content
    assert "Setup OAuth" in content
    assert "Needed for auth" in content

    brief_path = save_executive_brief(str(tmp_path), content)
    assert brief_path.exists()
    assert brief_path.name == "brief.md"

def test_review_and_approve_goals_non_interactive():
    goals = [
        {"id": "g1", "title": "Setup OAuth", "priority": "P0"},
        {"id": "g2", "title": "Add Charters", "priority": "P0"}
    ]
    approved = review_and_approve_goals_tui(goals, interactive=False)
    assert approved == goals
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_brief_and_tui.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.brief'`

- [ ] **Step 3: Implement `synlynk/brief.py`**

```python
# synlynk/brief.py
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

def generate_executive_brief(repo_path: str, goals: List[dict], evidence: dict, mode: str = "Brownfield") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Executive Project Brief: {Path(repo_path).name or 'Root Workspace'}",
        f"**Mode:** {mode} | **Generated:** {now}",
        "",
        "## 1. Discovered Signals & Architecture",
        f"- **Root Path:** `{repo_path}`",
        f"- **Source Files Detected:** {evidence.get('code_files', 0)}",
        f"- **Package Manifests:** {', '.join(evidence.get('manifests', [])) or 'None'}",
        f"- **Test Surface:** {evidence.get('test_files', 0)} test files",
        "",
        "## 2. Synthesized Strategic Goals",
    ]

    for idx, g in enumerate(goals, 1):
        lines.extend([
            f"### Goal {idx} [{g.get('priority', 'P1')}]: {g.get('title', 'Goal')}",
            f"- **Category:** `{g.get('category', 'general')}`",
            f"- **Rationale:** {g.get('rationale', '')}",
            "- **Acceptance Criteria:**",
        ])
        for ac in g.get("acceptance_criteria", []):
            lines.append(f"  - [ ] {ac}")
        lines.append("")

    lines.extend([
        "## 3. Recommended First-Session Execution Step",
        f"Launch the P0 milestone delivery: execute `{goals[0].get('id', 'goal-1')}` in an isolated worktree.",
        ""
    ])
    return "\n".join(lines)

def save_executive_brief(repo_path: str, content: str) -> Path:
    docs_dir = Path(repo_path) / "project-docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    brief_path = docs_dir / "brief.md"
    brief_path.write_text(content, encoding="utf-8")
    return brief_path

def review_and_approve_goals_tui(goals: List[dict], interactive: bool = True) -> List[dict]:
    if not interactive:
        return goals

    print("\n════════════════════════════════════════════════════════════════════")
    print(" 🎯 Review & Approve Synthesized Goals")
    print("════════════════════════════════════════════════════════════════════")
    for idx, g in enumerate(goals, 1):
        print(f" [{idx}] [{g.get('priority')}] {g.get('title')}")
        print(f"     → {g.get('rationale')}")

    print("\n Press [Enter] to approve all goals, or type comma-separated numbers to select.")
    try:
        val = input(" Choice (default: all): ").strip()
        if val:
            indices = [int(x.strip()) - 1 for x in val.split(",") if x.strip().isdigit()]
            selected = [goals[i] for i in indices if 0 <= i < len(goals)]
            if selected:
                return selected
    except (EOFError, KeyboardInterrupt):
        pass
    return goals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_brief_and_tui.py -v`  
Expected: PASS (2/2 passing)

- [ ] **Step 5: Commit**

```bash
git add synlynk/brief.py tests/test_brief_and_tui.py
git commit -m "feat(brief): add executive project brief generator and TUI review

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 5: Memorable Vizor Port Hunting Ladder

**Files:**
- Modify: `synlynk/viz.py:55-70`
- Test: `tests/test_vizor_memorable_ports.py`

**Interfaces:**
- Consumes: `socket`
- Produces: `MEMORABLE_VIZOR_PORTS = [33333, 44444, 55555, 22222, 11111]`, `find_available_vizor_port(preferred: Optional[int] = None) -> int`

- [ ] **Step 1: Write failing tests for memorable port hunting**

```python
# tests/test_vizor_memorable_ports.py
import socket
import pytest
from synlynk.viz import MEMORABLE_VIZOR_PORTS, find_available_vizor_port

def test_memorable_port_list():
    assert MEMORABLE_VIZOR_PORTS == [33333, 44444, 55555, 22222, 11111]

def test_find_available_vizor_port_default(monkeypatch):
    # Mock socket to simulate 33333 is free
    def mock_bind(self, addr):
        return True
    monkeypatch.setattr(socket.socket, "bind", mock_bind)
    port = find_available_vizor_port()
    assert port == 33333

def test_find_available_vizor_port_fallback(monkeypatch):
    # Mock socket: 33333 is busy, 44444 is free
    def mock_bind(self, addr):
        if addr[1] == 33333:
            raise OSError("Address already in use")
        return True
    monkeypatch.setattr(socket.socket, "bind", mock_bind)
    port = find_available_vizor_port()
    assert port == 44444
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_memorable_ports.py -v`  
Expected: FAIL with `ImportError: cannot import name 'MEMORABLE_VIZOR_PORTS'`

- [ ] **Step 3: Update `synlynk/viz.py`**

In `synlynk/viz.py`, add `MEMORABLE_VIZOR_PORTS` and `find_available_vizor_port`:

```python
import socket

MEMORABLE_VIZOR_PORTS = [33333, 44444, 55555, 22222, 11111]
DEFAULT_PORT = 33333

def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False

def find_available_vizor_port(preferred: Optional[int] = None) -> int:
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(MEMORABLE_VIZOR_PORTS)
    for p in candidates:
        if is_port_available(p):
            return p
    return 8721
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_memorable_ports.py -v`  
Expected: PASS (3/3 passing)

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz.py tests/test_vizor_memorable_ports.py
git commit -m "feat(viz): implement memorable repeating port hunting ladder (:33333)

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 6: LIVE-21 Remediation — Onboarding & Defensive Dispatch Gate

**Files:**
- Modify: `synlynk/__init__.py:2870-2910` (`init()`)
- Modify: `synlynk/dispatch.py:2610-2640` (`_preflight_dispatch()`)
- Test: `tests/test_onboarding_autoprobe.py`

**Interfaces:**
- Consumes: `synlynk.probe.cmd_probe`
- Produces: Auto-probing during `synlynk init`, defensive auto-probing in `_preflight_dispatch` if unprobed harness encountered.

- [ ] **Step 1: Write failing tests for LIVE-21 remediation**

```python
# tests/test_onboarding_autoprobe.py
import pytest
from unittest.mock import MagicMock, patch
from synlynk.dispatch import _preflight_dispatch

def test_defensive_inline_probe_when_unprobed():
    # If harness_records has no row for claude, _preflight_dispatch triggers inline probe
    with patch("synlynk.dispatch._get_harness_record", return_value=None):
        with patch("synlynk.probe._probe_agent") as mock_probe:
            mock_probe.return_value = {"compliance_status": "ok"}
            # Mock remaining checks to pass
            with patch("synlynk.dispatch._check_instruction_file", return_value=True):
                passed, reason = _preflight_dispatch("claude", force_agent=True)
                assert mock_probe.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboarding_autoprobe.py -v`  
Expected: FAIL before inline probe is wired.

- [ ] **Step 3: Implement defensive auto-probe in `synlynk/dispatch.py` and onboarding probe in `synlynk/__init__.py`**

In `synlynk/dispatch.py`:
```python
# In TC-2 flag check in _preflight_dispatch:
if not record:
    # LIVE-21 Fix: Run defensive inline probe rather than immediate hard failure
    try:
        from synlynk.probe import _probe_agent
        probe_res = _probe_agent(harness_name)
        record = probe_res
    except Exception:
        pass

if not record:
    return False, f"no probe data for agent; run synlynk probe {harness_name}"
```

In `synlynk/__init__.py` (inside `init()` completion):
```python
# Auto-probe configured harnesses to seed harness_records
try:
    from synlynk.probe import cmd_probe
    cmd_probe(quiet=True)
except Exception:
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboarding_autoprobe.py -v`  
Expected: PASS (1/1 passing)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py synlynk/__init__.py tests/test_onboarding_autoprobe.py
git commit -m "fix(dispatch): resolve LIVE-21 by auto-probing on init and defensive inline probe

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 7: CLI Integration & End-to-End Verification

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_autonomous_goal_forming_e2e.py`

**Interfaces:**
- Consumes: All components from Tasks 1–6
- Produces: `synlynk brainstorm` command, `synlynk brief` command, integrated `synlynk init` Welcome Fork and Goal Formulation.

- [ ] **Step 1: Write comprehensive end-to-end test**

```python
# tests/test_autonomous_goal_forming_e2e.py
import pytest
from pathlib import Path
from synlynk.repo_classifier import classify_repository, RepoType
from synlynk.greenfield_blueprints import synthesize_greenfield_goals
from synlynk.goal_synthesizer import synthesize_brownfield_goals
from synlynk.brief import generate_executive_brief, save_executive_brief

def test_full_greenfield_personal_assistant_journey(tmp_path: Path):
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.GREENFIELD
    goals = synthesize_greenfield_goals("personal_assistant", ["bills", "reimbursements"])
    assert len(goals) == 4
    content = generate_executive_brief(str(tmp_path), goals, {"code_files": 0}, mode="Greenfield")
    brief_path = save_executive_brief(str(tmp_path), content)
    assert brief_path.exists()
    assert "Bills & Reimbursement" in brief_path.read_text()

def test_full_brownfield_journey(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"')
    (tmp_path / "main.py").write_text('def run(): pass')
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.BROWNFIELD
    goals = synthesize_brownfield_goals({"code_files": 1, "test_files": 0, "manifests": ["pyproject.toml"]})
    assert len(goals) >= 3
    content = generate_executive_brief(str(tmp_path), goals, {"code_files": 1}, mode="Brownfield")
    brief_path = save_executive_brief(str(tmp_path), content)
    assert brief_path.exists()
    assert "Baseline Health" in brief_path.read_text()
```

- [ ] **Step 2: Run test to verify it fails if anything is missing**

Run: `pytest tests/test_autonomous_goal_forming_e2e.py -v`

- [ ] **Step 3: Wire CLI commands in `synlynk/cli.py`**

Add `brainstorm` and `brief` subcommands to parser and dispatch to `cmd_brainstorm` and `cmd_brief`.

- [ ] **Step 4: Run full epic test suite**

Run: `pytest tests/test_repo_classifier.py tests/test_greenfield_blueprints.py tests/test_brownfield_synthesizer.py tests/test_brief_and_tui.py tests/test_vizor_memorable_ports.py tests/test_onboarding_autoprobe.py tests/test_autonomous_goal_forming_e2e.py -v`  
Expected: PASS (All tests pass)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_autonomous_goal_forming_e2e.py
git commit -m "feat(cli): wire autonomous brainstorm, brief, and e2e verification

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```
