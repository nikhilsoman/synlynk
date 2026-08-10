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
    """Bootstraps a brand-new project: config + docs via init(), then seeds the
    captured intent as the first roadmap arc. No workspace-canon.md -- round 1-2
    of the cold-start design explicitly excludes canon generation for new projects
    (nothing to document yet).
    """
    from synlynk import init
    from synlynk.db import cmd_roadmap_add

    mode = "team" if answers["team_mode"].startswith("team") else "solo"
    init(mode=mode, quiet=True)

    version = "v0.1.0"
    cmd_roadmap_add(
        version=version,
        title=answers["goal"],
        status="planned",
        notes=f"Deliverable shape: {answers['deliverable_shape']}."
        + (f" Preferred implementer: {answers['preferred_implementer']}."
           if answers["preferred_implementer"] else ""),
    )

    print(f"\nSetup complete. Next: run `synlynk dispatch {answers['preferred_implementer'] or '<agent>'} "
          f"--task \"{answers['goal']}\"` to start building against {version}.")


def _run_existing_project_flow(root: str = ".") -> None:
    """Baseline warm-start for an existing repo: env-probe + shallow scan summary
    + workspace-canon.md baseline (Documentation Index + 3-claim receipt, see
    cold-start Phase 2) + one question, routed into a seeded story.
    """
    import synlynk.scan as scan_mod
    from synlynk import canon
    from synlynk.db import cmd_story_create

    scan = scan_mod.run_workspace_scan(roots=[root], deep=False)

    repo = scan["repos"][0] if scan["repos"] else {
        "name": os.path.basename(os.path.abspath(root)),
        "stack_labels": [],
    }
    functional_agents = [a for a in scan.get("agents", []) if a.get("functional")]

    print(f"\nFound: {repo['name']}  ·  stack: {', '.join(repo['stack_labels']) or 'unknown'}  "
          f"·  topology: {scan.get('topology', 'single')}")
    if functional_agents:
        print(f"Harnesses ready: {', '.join(a['name'] for a in functional_agents)}")
    else:
        checked = ", ".join(a["name"] for a in scan.get("agents", [])) or "none found on PATH"
        print(f"No working harnesses detected (checked: {checked})  "
              "You can still browse the scan output; install/auth a harness to dispatch work.")

    canon.run_canon_baseline(root, scan)

    intent = input("\nWhat are you trying to do right now? ").strip()
    if intent:
        story_id = cmd_story_create(title=intent)
        print(f"\nNext: run `synlynk dispatch <agent> --task \"{intent}\"` "
              f"to work on {story_id}, or `synlynk story list` to see it queued.")
    else:
        print("\nNo task captured -- run `synlynk start` again anytime, "
              "or `synlynk scan --deep` for a fuller picture.")


def cmd_start() -> None:
    """Entry point for `synlynk start` -- see spec's "synlynk start EXACT FLOW"."""
    config_exists = os.path.exists(".synlynk/config.json")
    dir_exists = os.path.isdir(".synlynk")
    already_initialized = config_exists or dir_exists
    if already_initialized:
        what_exists = ".synlynk/config.json" if config_exists else ".synlynk/"
        answer = input(
            f"{what_exists} already exists -- refresh cold-start detection "
            "and re-run the relevant flow? [y/N] "
        ).strip().lower()
        if answer != "y":
            print("Left project unchanged.")
            return

    mode = _resolve_cold_start_mode(".")
    if mode == "new":
        answers = _prompt_new_project_questions()
        _run_new_project_flow(answers)
    else:
        _run_existing_project_flow(".")
