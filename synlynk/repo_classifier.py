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
