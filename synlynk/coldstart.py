"""Cold-start detection and entry flows for `synlynk start`.

Detects whether the current directory is a brand-new project, an existing
one, or genuinely ambiguous, then routes to the appropriate flow. See
docs/superpowers/specs/2026-08-09-cold-start-design.md for the full design.
"""
import os
import subprocess

_MANIFEST_FILES = (
    "package.json", "pyproject.toml", "setup.py", "requirements.txt",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Gemfile",
)
_README_FILES = ("README.md", "README.rst", "README.txt", "README")


def _commit_count(root: str) -> int:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return 0
        return int(result.stdout.strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0


def _detect_cold_start_mode(root: str = ".") -> dict:
    """Returns {"mode": "new"|"existing"|"ambiguous", "reason": str, "signals": dict}.

    Heuristics (see spec "Detection: new vs. existing"):
    - No .git, no manifest/README, no visible files -> confident new.
    - .git present, 0 commits, no manifest/README -> confident new (fresh `git init`).
    - .git present, 0 commits, manifest/README present -> ambiguous (forked/cloned
      scaffold not yet committed).
    - .git present, commits > 0, manifest/README/other files present -> confident existing.
    - .git present, commits > 0, nothing recognizable -> ambiguous.
    - No .git, but manifest/README present -> ambiguous (project files without git yet).
    """
    has_git = os.path.isdir(os.path.join(root, ".git"))
    has_manifest = any(os.path.exists(os.path.join(root, f)) for f in _MANIFEST_FILES)
    has_readme = any(os.path.exists(os.path.join(root, f)) for f in _README_FILES)
    try:
        visible_files = [f for f in os.listdir(root) if not f.startswith(".")]
    except OSError:
        visible_files = []
    commit_count = _commit_count(root) if has_git else 0

    signals = {
        "has_git": has_git,
        "has_manifest": has_manifest,
        "has_readme": has_readme,
        "commit_count": commit_count,
        "visible_file_count": len(visible_files),
    }

    if not has_git:
        if has_manifest or has_readme:
            return {"mode": "ambiguous",
                    "reason": "project files present but no git repo yet",
                    "signals": signals}
        return {"mode": "new", "reason": "empty directory, no git", "signals": signals}

    if commit_count == 0:
        if has_manifest or has_readme:
            return {"mode": "ambiguous",
                    "reason": "git initialized but 0 commits, with existing content "
                              "(fork/clone scaffold?)",
                    "signals": signals}
        return {"mode": "new",
                "reason": "git initialized, 0 commits, no content",
                "signals": signals}

    if has_manifest or has_readme or visible_files:
        return {"mode": "existing",
                "reason": f"{commit_count} commit(s), project files present",
                "signals": signals}

    return {"mode": "ambiguous",
            "reason": f"{commit_count} commit(s) but no recognizable project files",
            "signals": signals}
