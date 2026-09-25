"""Cold-start detection and entry flows for `synlynk start`.

Detects whether the current directory is a brand-new project, an existing
one, or genuinely ambiguous, then routes to the appropriate flow. See
docs/superpowers/specs/2026-08-09-cold-start-design.md for the full design.
"""
import json
import os
import subprocess
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

_MANIFEST_FILES = (
    "package.json", "pyproject.toml", "setup.py", "requirements.txt",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Gemfile",
)
_README_FILES = ("README.md", "README.rst", "README.txt", "README")


@contextmanager
def _working_directory(path: str):
    """Temporarily run cwd-relative project operations from ``path``."""
    original = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


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


def _run_new_project_flow(answers: dict, repo_root: str = ".") -> None:
    """Bootstraps a brand-new project: config + docs via init(), then seeds the
    captured intent as the first roadmap arc. No workspace-canon.md -- round 1-2
    of the cold-start design explicitly excludes canon generation for new projects
    (nothing to document yet).
    """
    from synlynk import init
    from synlynk.db import cmd_roadmap_add

    repo_path = os.path.abspath(repo_root)
    with _working_directory(repo_path):
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


def run_ftue_journey(repo_root: str = ".", interactive: bool = True, dry_run: bool = False) -> dict:
    """Run end-to-end 5-stage FTUE onboarding journey:
    1. Surface detection & rule binding
    2. 3D static discovery & semantic overlay
    3. Context confirmation (chips validator)
    4. Gap scanning & GOVERNS goal generation
    5. First-win isolated worktree SOP task dispatch
    """
    from synlynk.surface import detect_developer_surfaces, bind_surface_rules
    from synlynk.discovery import scan_workspace_static
    from synlynk.discovery_semantic import enrich_with_semantic_overlay
    from synlynk.context_validator import validate_context
    from synlynk.gap_scanner import scan_workspace_gaps, generate_governs_goal
    from synlynk.first_win import dispatch_first_win_task

    # Stage 1: Surfaces
    surfaces = detect_developer_surfaces(repo_root)
    rule_bindings = bind_surface_rules(repo_root, surfaces)

    # Stage 2: Discovery
    discovery = scan_workspace_static(repo_root)
    discovery = enrich_with_semantic_overlay(discovery, repo_root)

    # Stage 3: Validate context
    confirmed_context = validate_context(discovery, interactive=interactive)

    # Stage 4: Gap Scanner & Goal Generation
    gaps = scan_workspace_gaps(confirmed_context, repo_root)
    governs_goal = generate_governs_goal(gaps[0]) if gaps else None

    # Stage 5: First-Win Task Dispatch
    first_win = None
    if governs_goal and not dry_run:
        first_win = dispatch_first_win_task(governs_goal, repo_root)
    elif governs_goal:
        first_win = {
            "status": "planned",
            "branch": "feat/first-win-verification",
            "goal": governs_goal,
            "worktree_isolated": True,
        }

    return {
        "success": True,
        "surfaces": surfaces,
        "rule_bindings": rule_bindings,
        "discovery": confirmed_context,
        "gaps": gaps,
        "governs_goal": governs_goal,
        "first_win_task": first_win,
        "recommendations": get_onboarding_recommendations(),
    }


def get_onboarding_recommendations() -> list[dict]:
    """Return onboarding tool recommendations with preflight availability status.

    Checks availability of registered ecosystem tools (e.g. Graphify AST Knowledge Graph)
    and marks uninstalled tools as recommended for 1-click installation during FTUE onboarding.
    """
    from synlynk.tool_installer import RECOMMENDED_TOOLS, is_tool_available

    recommendations = []
    for tool_name, meta in RECOMMENDED_TOOLS.items():
        installed = is_tool_available(tool_name)
        if tool_name == "graphify":
            label = "Graphify AST Knowledge Graph (Recommended: ~20x token savings)"
        else:
            binary = meta.get("binary", tool_name)
            desc = meta.get("description", "")
            label = f"{binary} CLI ({desc})" if desc else f"{binary} CLI"

        recommendations.append({
            "name": tool_name,
            "label": label,
            "description": meta.get("description", ""),
            "installed": installed,
            "recommended": not installed,
            "package": meta.get("package", tool_name),
            "binary": meta.get("binary", tool_name),
            "license": meta.get("license", ""),
        })
    return recommendations


def _detect_brownfield_stack(root: str) -> dict:
    """Reverse-engineer languages, runtimes, and build systems from workspace files."""
    languages = []

    # Check Python
    if any(os.path.exists(os.path.join(root, f)) for f in ("pyproject.toml", "setup.py", "requirements.txt", "Pipfile")):
        languages.append("Python")

    # Check Node/JS/TS
    if os.path.exists(os.path.join(root, "package.json")):
        if os.path.exists(os.path.join(root, "tsconfig.json")):
            languages.append("TypeScript")
        else:
            languages.append("JavaScript")

    # Check Rust
    if os.path.exists(os.path.join(root, "Cargo.toml")):
        languages.append("Rust")

    # Check Go
    if os.path.exists(os.path.join(root, "go.mod")):
        languages.append("Go")

    # Check Java/Kotlin
    if os.path.exists(os.path.join(root, "pom.xml")) or os.path.exists(os.path.join(root, "build.gradle")):
        languages.append("Java/Kotlin")

    # Deduplicate
    languages = list(dict.fromkeys(languages))
    if not languages:
        languages = ["Generic/Polyglot"]

    return {
        "languages": languages,
        "primary": languages[0],
        "label": " + ".join(languages)
    }


def _detect_brownfield_tests(root: str, primary_lang: str) -> str:
    """Detect test runner and return recommended test command."""
    # Check Python
    if primary_lang in ("Python", "Generic/Polyglot"):
        if (os.path.exists(os.path.join(root, "pytest.ini")) or
            os.path.exists(os.path.join(root, "setup.cfg")) or
            os.path.exists(os.path.join(root, "tests")) or
            any(f.endswith(".py") and ("test" in f) for f in os.listdir(root) if os.path.isfile(os.path.join(root, f)))):
            return "pytest"
        return "python -m unittest discover"

    # Check JS/TS
    if primary_lang in ("JavaScript", "TypeScript"):
        pkg_json = os.path.join(root, "package.json")
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    if "test" in scripts:
                        return "npm test"
            except Exception:
                pass
        if any(os.path.exists(os.path.join(root, f)) for f in ("vitest.config.ts", "vitest.config.js")):
            return "npx vitest run"
        if any(os.path.exists(os.path.join(root, f)) for f in ("jest.config.ts", "jest.config.js")):
            return "npx jest"
        return "npm test"

    # Check Rust
    if primary_lang == "Rust":
        return "cargo test"

    # Check Go
    if primary_lang == "Go":
        return "go test ./..."

    # Check Java
    if primary_lang == "Java/Kotlin":
        if os.path.exists(os.path.join(root, "mvnw")) or os.path.exists(os.path.join(root, "pom.xml")):
            return "./mvnw test" if os.path.exists(os.path.join(root, "mvnw")) else "mvn test"
        return "./gradlew test" if os.path.exists(os.path.join(root, "gradlew")) else "gradle test"

    return "make test" if os.path.exists(os.path.join(root, "Makefile")) else "pytest"


def _detect_brownfield_linters(root: str, primary_lang: str) -> str:
    """Detect linter and return recommended lint command."""
    if primary_lang in ("Python", "Generic/Polyglot"):
        if os.path.exists(os.path.join(root, "ruff.toml")) or os.path.exists(os.path.join(root, ".ruff.toml")):
            return "ruff check ."
        pyproj = os.path.join(root, "pyproject.toml")
        if os.path.exists(pyproj):
            try:
                with open(pyproj, "r", encoding="utf-8") as f:
                    if "ruff" in f.read():
                        return "ruff check ."
            except Exception:
                pass
        if os.path.exists(os.path.join(root, ".flake8")):
            return "flake8 ."
        return "ruff check ."

    if primary_lang in ("JavaScript", "TypeScript"):
        if any(f.startswith(".eslintrc") or f.startswith("eslint.config") for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))):
            return "npx eslint ."
        if os.path.exists(os.path.join(root, "tsconfig.json")):
            return "npx tsc --noEmit"
        return "npx eslint ."

    if primary_lang == "Rust":
        return "cargo clippy"

    if primary_lang == "Go":
        return "golangci-lint run"

    return "make lint" if os.path.exists(os.path.join(root, "Makefile")) else "ruff check ."


def _detect_brownfield_build(root: str, primary_lang: str) -> str:
    """Detect build command."""
    if os.path.exists(os.path.join(root, "Makefile")):
        return "make build"
    if primary_lang in ("JavaScript", "TypeScript"):
        return "npm run build"
    if primary_lang == "Rust":
        return "cargo build"
    if primary_lang == "Go":
        return "go build ./..."
    if primary_lang == "Python":
        return "pip install -e ."
    return "make build"


def _detect_git_churn(root: str) -> List[str]:
    """Analyze commit log to find top churned / hotspot files."""
    try:
        res = subprocess.run(
            ["git", "-C", os.path.abspath(root), "log", "--pretty=format:", "--name-only", "-n", "200"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode != 0:
            return []
        counts: Dict[str, int] = {}
        for line in res.stdout.splitlines():
            f = line.strip()
            if not f or f.startswith(".git"):
                continue
            if os.path.exists(os.path.join(root, f)):
                counts[f] = counts.get(f, 0) + 1
        sorted_files = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [f for f, count in sorted_files[:8]]
    except Exception:
        return []


def _detect_git_user(root: str) -> Tuple[str, str, List[str]]:
    """Detect active developer username and top repository contributors."""
    user_name = "developer"
    user_email = ""
    contributors = []
    try:
        res = subprocess.run(["git", "-C", os.path.abspath(root), "config", "user.name"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            user_name = res.stdout.strip()
    except Exception:
        user_name = os.environ.get("USER") or "developer"

    try:
        res = subprocess.run(["git", "-C", os.path.abspath(root), "config", "user.email"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            user_email = res.stdout.strip()
    except Exception:
        pass

    try:
        res = subprocess.run(["git", "-C", os.path.abspath(root), "shortlog", "-sn", "--all", "-n", "5"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                parts = line.strip().split("\t", 1)
                if len(parts) == 2 and parts[1].strip():
                    contributors.append(parts[1].strip())
    except Exception:
        pass
    if not contributors:
        contributors = [user_name]

    return user_name, user_email, contributors


def _bootstrap_4docs(
    root: str,
    stack: str,
    test_cmd: str,
    lint_cmd: str,
    build_cmd: str,
    hotspots: List[str],
    user_name: str,
    force: bool = False
) -> List[str]:
    """Generate or update the mandatory 4-doc structure in project-docs/."""
    docs_dir = os.path.join(root, "project-docs")
    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(os.path.join(docs_dir, "devlogs"), exist_ok=True)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    created = []

    # 1. roadmap.md
    roadmap_path = os.path.join(docs_dir, "roadmap.md")
    if not os.path.exists(roadmap_path) or force:
        roadmap_content = f"""# Project Roadmap

> **Repository Baseline:** Brownfield Ingestion ({today})  
> **Primary Author:** @{user_name}  ·  **Stack:** {stack}

---

## 🌊 Arc 1: Brownfield Baseline & Stabilization
**Governing Goal:** Establish automated test coverage and CI quality gates on legacy codebase.

### Phase 1: Test Verification & Hotspot Safety
- [ ] **Phase 1.1:** Automated test suite verification (`{test_cmd}`) against top churn files
- [ ] **Phase 1.2:** Code quality & linter alignment (`{lint_cmd}`)
- [ ] **Phase 1.3:** Build & package verification (`{build_cmd}`)
"""
        with open(roadmap_path, "w", encoding="utf-8") as f:
            f.write(roadmap_content)
        created.append("roadmap.md")

    # 2. memory.md
    memory_path = os.path.join(docs_dir, "memory.md")
    if not os.path.exists(memory_path) or force:
        hotspot_str = ", ".join(hotspots[:3]) if hotspots else "core workspace modules"
        memory_content = f"""# Project Memory & Architectural Decisions

## [{today} @{user_name}] Brownfield Stack & Test Ingestion
- **Stack Decision:** Reverse-engineered `{stack}` runtime architecture.
- **Verification Gate:** Standard test runner configured as `{test_cmd}`.
- **Linting Gate:** Code standard linter configured as `{lint_cmd}`.
- **Hotspot Prioritization:** Focusing test harness & regression safety on high-churn files: {hotspot_str}.
"""
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(memory_content)
        created.append("memory.md")

    # 3. todo.md
    todo_path = os.path.join(docs_dir, "todo.md")
    if not os.path.exists(todo_path) or force:
        todo_content = f"""# Tasks (TODO)

<!-- Auto-projected from state.db — updated via synlynk story -->

## Ready / In Progress
- [ ] **Story 1:** Run and verify automated test harness (`{test_cmd}`) against top churn files [@{user_name}]
- [ ] **Story 2:** Establish CI lint and type verification gate (`{lint_cmd}`) [@{user_name}]
- [ ] **Story 3:** Build & deployment verification (`{build_cmd}`) [@{user_name}]
"""
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write(todo_content)
        created.append("todo.md")

    # 4. costs.md
    costs_path = os.path.join(docs_dir, "costs.md")
    if not os.path.exists(costs_path) or force:
        costs_content = f"""# Project AI Costs & Token Ledger

| Date | Agent / Harness | Operation | Input Tokens | Output Tokens | Cost (USD) | Notes |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| {today} | `init --brownfield` | Workspace Ingestion | 0 | 0 | $0.000 | Initialized by @{user_name} |
"""
        with open(costs_path, "w", encoding="utf-8") as f:
            f.write(costs_content)
        created.append("costs.md")

    # 5. devlogs/<user>.md
    devlog_path = os.path.join(docs_dir, "devlogs", f"{user_name}.md")
    if not os.path.exists(devlog_path) or force:
        devlog_content = f"""# Devlog — @{user_name}

## {today}
- **Task:** Initialized brownfield project via `synlynk init --brownfield`
- **Discovered Stack:** {stack}
- **Discovered Test Command:** `{test_cmd}`
- **Discovered Lint Command:** `{lint_cmd}`
- **Discovered Hotspots:** {', '.join(hotspots) if hotspots else 'none'}
- **Next Task:** Run verification test suite against core hotspot modules
"""
        with open(devlog_path, "w", encoding="utf-8") as f:
            f.write(devlog_content)
        created.append(f"devlogs/{user_name}.md")

    return created


def run_brownfield_init(
    repo_root: str = ".",
    interactive: bool = True,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """Deep Brownfield Ingestion Engine for existing codebases.

    Reverse-engineers tech stack, test harnesses, linters, and git churn hotspots,
    presents 1-click confirmation chips, and bootstraps the mandatory 4-doc standard.
    """
    repo_path = os.path.abspath(repo_root)
    project_name = os.path.basename(repo_path) or "workspace"

    # 1. Reverse-engineer tech stack & commands
    stack_info = _detect_brownfield_stack(repo_path)
    test_cmd = _detect_brownfield_tests(repo_path, stack_info["primary"])
    lint_cmd = _detect_brownfield_linters(repo_path, stack_info["primary"])
    build_cmd = _detect_brownfield_build(repo_path, stack_info["primary"])
    hotspots = _detect_git_churn(repo_path)
    user_name, user_email, contributors = _detect_git_user(repo_path)

    # 2. 1-Click Confirmation Prompts / Chips
    chips = [
        f"[Stack: {stack_info['label']}]",
        f"[Tests: {test_cmd}]",
        f"[Linter: {lint_cmd}]",
        f"[Author: @{user_name}]",
    ]
    if hotspots:
        chips.append(f"[Hotspots: {', '.join(hotspots[:2])}]")

    print("\n✦ Deep Brownfield Repository Ingestion:")
    print("  " + "  ".join(chips))

    if interactive and not dry_run and os.isatty(0):
        print("\nOptions:")
        print("  [1] Confirm discovered settings & bootstrap 4-doc workspace standard (Default [Enter])")
        print("  [2] Skip initialization")
        choice = input("Select [1/2]: ").strip()
        if choice == "2":
            print("Aborted brownfield initialization.")
            return {"success": False, "aborted": True}

    if dry_run:
        print("\n[DRY RUN] Would bootstrap:")
        print(f"  • .synlynk/config.json with test='{test_cmd}', lint='{lint_cmd}', stack='{stack_info['label']}'")
        print(f"  • project-docs/roadmap.md, memory.md, todo.md, costs.md, devlogs/{user_name}.md")
        return {
            "success": True,
            "dry_run": True,
            "project_name": project_name,
            "stack": stack_info["label"],
            "test_command": test_cmd,
            "lint_command": lint_cmd,
            "build_command": build_cmd,
            "hotspots": hotspots,
            "primary_author": user_name,
            "contributors": contributors,
            "docs_created": ["roadmap.md", "memory.md", "todo.md", "costs.md", f"devlogs/{user_name}.md"],
        }

    # init() and the state helpers are cwd-relative, so keep all of the
    # initialization transaction inside the target repository. The context
    # manager also restores the caller's cwd if any step raises.
    from synlynk import init, _update_config
    with _working_directory(repo_path):
        # 3. Initialize synlynk base structure
        init(force=force, mode="solo", quiet=True)

        # 4. Save brownfield configs
        os.makedirs(os.path.join(repo_path, ".synlynk"), exist_ok=True)
        _update_config({
            "project_name": project_name,
            "stack": stack_info["label"],
            "test_command": test_cmd,
            "lint_command": lint_cmd,
            "build_command": build_cmd,
            "hotspots": hotspots,
            "primary_author": user_name,
            "brownfield": True,
            "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

        # 5. Bootstrap 4-doc structure
        created_docs = _bootstrap_4docs(
            repo_path, stack_info["label"], test_cmd, lint_cmd, build_cmd, hotspots, user_name, force=force
        )

        # 6. Seed state.db with initial brownfield goals & stories
        try:
            from synlynk.db import cmd_goal_create, cmd_story_create
            cmd_goal_create(
                outcome=f"Stabilize brownfield {stack_info['label']} codebase and establish verification gates",
                criterion=f"{test_cmd} passes cleanly with 0 regressions",
                role="pm"
            )
            cmd_story_create(title=f"Verify automated test harness ({test_cmd}) against top churn files")
            cmd_story_create(title=f"Establish CI lint and type verification gate ({lint_cmd})")
        except Exception:
            pass

    return {
        "success": True,
        "project_name": project_name,
        "stack": stack_info["label"],
        "test_command": test_cmd,
        "lint_command": lint_cmd,
        "build_command": build_cmd,
        "hotspots": hotspots,
        "primary_author": user_name,
        "contributors": contributors,
        "docs_created": created_docs,
    }
