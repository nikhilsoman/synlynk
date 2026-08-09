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


def _resolve_cold_start_mode(root: str = ".") -> str:
    """Runs detection; prompts a single one-line confirm only if ambiguous.

    Returns "new" or "existing" (never "ambiguous" -- the prompt collapses it).
    Empty/unrecognized answers default to "existing" (the safer assumption --
    treating an existing project as new would risk overwriting content).
    """
    detected = _detect_cold_start_mode(root)
    if detected["mode"] != "ambiguous":
        return detected["mode"]

    answer = input(
        f"Looks like an existing project ({detected['reason']}) -- "
        "is that right, or are we starting fresh [existing/new] "
    ).strip().lower()
    if answer in ("new", "n"):
        return "new"
    return "existing"


def _prompt_new_project_questions() -> dict:
    """Exactly 4 questions per spec: goal, deliverable shape, solo/team, implementer."""
    goal = input("In one sentence, what are you trying to build? ").strip()
    deliverable_shape = input(
        "What shape is the deliverable (CLI, web app, library, etc.)? "
    ).strip()
    team_mode = input("Solo or team [solo] ").strip().lower() or "solo"
    preferred_implementer = input(
        "Preferred implementer, if you already know (claude/agy/codex/grok, or blank): "
    ).strip().lower() or None
    return {
        "goal": goal,
        "deliverable_shape": deliverable_shape,
        "team_mode": team_mode,
        "preferred_implementer": preferred_implementer,
    }


def _run_new_project_flow(answers: dict) -> None:
    """Bootstrap a new project and seed its captured intent as its first roadmap arc."""
    import builtins
    import shutil

    from synlynk import init
    from synlynk.db import cmd_roadmap_add

    mode = "team" if answers["team_mode"].startswith("team") else "solo"
    # The existing initializer has optional follow-up prompts. A new-project
    # flow has already collected its complete four-question intent, so leave
    # those optional answers blank while reusing the initializer unchanged.
    original_input = builtins.input
    builtins.input = lambda prompt: ""
    try:
        init(mode=mode)
    finally:
        builtins.input = original_input

    # This checkout's initializer stores the canonical config under
    # `.synlynk/config.json`; retain the task's legacy `synlynk/config.json`
    # path as a compatibility copy for new-project consumers.
    config_path = os.path.join(".synlynk", "config.json")
    legacy_config_path = os.path.join("synlynk", "config.json")
    if os.path.exists(config_path):
        os.makedirs(os.path.dirname(legacy_config_path), exist_ok=True)
        shutil.copyfile(config_path, legacy_config_path)

    version = "v0.1.0"
    cmd_roadmap_add(
        version=version,
        title=answers["goal"],
        status="planned",
        notes=(
            f"Deliverable shape: {answers['deliverable_shape']}."
            + (
                f" Preferred implementer: {answers['preferred_implementer']}."
                if answers["preferred_implementer"]
                else ""
            )
        ),
    )

    print(
        f"\nSetup complete. Next: run `synlynk dispatch "
        f"{answers['preferred_implementer'] or '<agent>'} --task \"{answers['goal']}\"` "
        f"to start building against {version}."
    )
