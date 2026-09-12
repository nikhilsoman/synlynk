"""synlynk parity: Stack-aware declarative adoption parity and non-destructive migration engine."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

START_FENCE_REGEX = re.compile(
    r"<!-- synlynk:start(?:\s+version=\"[^\"]*\")?(?:\s+tool=\"[^\"]*\")?\s*-->.*?<!-- synlynk:end -->",
    re.DOTALL,
)

HARNESS_FENCE_REGEX = re.compile(
    r"<!-- synlynk:harness(?:\s+v\S+)?(?:\s+verified:\S+)?\s*-->.*?<!-- /synlynk:harness -->",
    re.DOTALL,
)


def detect_project_stack(repo_path: str) -> Dict[str, Any]:
    """Inspects a repository and returns its primary language, package manager, and test runner."""
    path = Path(repo_path)
    detected_languages: List[str] = []
    test_cmd = "pytest"
    package_manager = "pip"

    has_package_json = (path / "package.json").exists()
    has_go_mod = (path / "go.mod").exists()
    has_pyproject = (path / "pyproject.toml").exists() or (path / "setup.py").exists() or (path / "requirements.txt").exists()
    has_cargo = (path / "Cargo.toml").exists()

    if has_package_json:
        detected_languages.append("node")
    if has_go_mod:
        detected_languages.append("go")
    if has_pyproject:
        detected_languages.append("python")
    if has_cargo:
        detected_languages.append("rust")

    if not detected_languages:
        detected_languages.append("python")

    # Stack-specific inspection
    if "node" in detected_languages:
        # Detect package manager
        if (path / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
        elif (path / "yarn.lock").exists():
            package_manager = "yarn"
        elif (path / "bun.lockb").exists():
            package_manager = "bun"
        else:
            package_manager = "npm"

        # Inspect package.json for test script
        try:
            pkg_data = json.loads((path / "package.json").read_text(encoding="utf-8"))
            scripts = pkg_data.get("scripts", {})
            raw_test = scripts.get("test", "")
            if "vitest" in raw_test:
                test_cmd = "npx vitest run"
            elif "jest" in raw_test:
                test_cmd = "npx jest"
            elif raw_test:
                test_cmd = f"{package_manager} test"
            else:
                test_cmd = "npm test"
        except Exception:
            test_cmd = "npm test"

    elif "go" in detected_languages:
        package_manager = "go"
        test_cmd = "go test ./..."

    elif "rust" in detected_languages:
        package_manager = "cargo"
        test_cmd = "cargo test"

    elif "python" in detected_languages:
        package_manager = "pip"
        test_cmd = "pytest"

    primary_lang = detected_languages[0] if len(detected_languages) == 1 else "mixed"

    return {
        "language": primary_lang,
        "languages": detected_languages,
        "package_manager": package_manager,
        "test_cmd": test_cmd,
    }


def parse_directive_fences(content: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Splits an instruction file into user-authored content and synlynk fences.

    Returns: (user_content, start_block, harness_block)
    """
    if not content:
        return ("", None, None)

    start_match = START_FENCE_REGEX.search(content)
    start_block = start_match.group(0) if start_match else None

    harness_match = HARNESS_FENCE_REGEX.search(content)
    harness_block = harness_match.group(0) if harness_match else None

    # Remove fences from user content
    stripped = content
    if start_block:
        stripped = stripped.replace(start_block, "")
    if harness_block:
        stripped = stripped.replace(harness_block, "")

    # Clean up double blank lines
    lines = stripped.splitlines()
    cleaned_lines = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        cleaned_lines.append(line)
        prev_blank = is_blank

    user_content = "\n".join(cleaned_lines).strip()
    if user_content:
        user_content += "\n"

    return (user_content, start_block, harness_block)


def inject_sop_fences(
    content: str,
    tool: str,
    version: str,
    start_body: str,
    harness_body: str,
) -> str:
    """Non-destructively replaces or injects SOP fences while preserving user content."""
    user_content, _, _ = parse_directive_fences(content)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    start_fence = (
        f'<!-- synlynk:start version="{version}" tool="{tool}" -->\n'
        f"{start_body.strip()}\n"
        f"<!-- synlynk:end -->"
    )

    harness_fence = (
        f"<!-- synlynk:harness v{version} verified:{ts} -->\n"
        f"# Harness Instructions (synlynk-managed — do not edit)\n\n"
        f"{harness_body.strip()}\n"
        f"<!-- /synlynk:harness -->"
    )

    if user_content:
        return f"{user_content.rstrip()}\n\n{start_fence}\n\n{harness_fence}\n"
    else:
        return f"{start_fence}\n\n{harness_fence}\n"


def ensure_recursive_gitignore(repo_path: str) -> bool:
    """Ensures .gitignore contains recursive **/.synlynk/* rules with whitelist exceptions."""
    gi_path = Path(repo_path) / ".gitignore"
    existing_content = gi_path.read_text(encoding="utf-8") if gi_path.exists() else ""

    if "**/.synlynk/*" in existing_content:
        return False

    rules = (
        "\n# synlynk state & secret stores\n"
        "**/.synlynk/*\n"
        "!**/.synlynk/config.json\n"
        "!**/.synlynk/policy.json\n"
        "!**/.synlynk/roles.yaml\n"
        "!**/.synlynk/instructions.json\n"
        "!**/.synlynk/model_rates.json\n"
    )

    # Remove root-only .synlynk/* or .synlynk/ if present
    cleaned = re.sub(r"(?m)^\.synlynk/(\*\s*)?$", "", existing_content).strip()
    new_content = cleaned + ("\n" if cleaned else "") + rules

    gi_path.write_text(new_content, encoding="utf-8")
    return True


def generate_stack_policy(repo_id: str, stack_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a standard 2-tier policy dictionary customized for the detected stack."""
    lang = stack_info.get("language", "python")

    # Base task allocation
    if lang == "node":
        task_alloc = {
            "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
            "test": {"harness": "codex", "fallback": ["grok", "agy"]},
            "css": {"harness": "agy", "fallback": []},
            "templates": {"harness": "agy", "fallback": []},
            "content": {"harness": "agy", "fallback": []},
            "subpages": {"harness": "agy", "fallback": []},
            "canvas": {"harness": "grok", "fallback": []},
            "js": {"harness": "grok", "fallback": []},
            "infra": {"harness": "grok", "fallback": []},
            "refactor": {"harness": "codex", "fallback": []},
            "cli-plumbing": {"harness": "codex", "fallback": []},
            "review": {"harness": "codex", "fallback": ["claude", "agy"]},
            "gh_write": {"harness": "codex", "fallback": ["claude", "agy"]},
            "pm": {"harness": "claude", "fallback": []},
            "brainstorm": {"harness": "claude", "fallback": []},
            "architecture-review": {"harness": "claude", "fallback": []},
        }
    elif lang == "go":
        task_alloc = {
            "implement": {"harness": "codex", "fallback": ["grok"]},
            "test": {"harness": "codex", "fallback": ["grok"]},
            "refactor": {"harness": "codex", "fallback": []},
            "cli-plumbing": {"harness": "codex", "fallback": []},
            "review": {"harness": "codex", "fallback": ["claude"]},
            "gh_write": {"harness": "codex", "fallback": ["claude"]},
            "pm": {"harness": "claude", "fallback": []},
            "brainstorm": {"harness": "claude", "fallback": []},
            "architecture-review": {"harness": "claude", "fallback": []},
            "infra": {"harness": "grok", "fallback": ["codex"]},
            "canvas": {"harness": "grok", "fallback": []},
            "templates": {"harness": "agy", "fallback": []},
            "content": {"harness": "agy", "fallback": []},
        }
    else:
        task_alloc = {
            "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
            "test": {"harness": "codex", "fallback": ["grok", "agy"]},
            "css": {"harness": "agy", "fallback": []},
            "templates": {"harness": "agy", "fallback": []},
            "content": {"harness": "agy", "fallback": []},
            "subpages": {"harness": "agy", "fallback": []},
            "canvas": {"harness": "grok", "fallback": []},
            "js": {"harness": "grok", "fallback": []},
            "infra": {"harness": "grok", "fallback": []},
            "refactor": {"harness": "codex", "fallback": []},
            "cli-plumbing": {"harness": "codex", "fallback": []},
            "review": {"harness": "codex", "fallback": ["claude", "agy"]},
            "gh_write": {"harness": "codex", "fallback": ["claude", "agy"]},
            "pm": {"harness": "claude", "fallback": []},
            "brainstorm": {"harness": "claude", "fallback": []},
            "architecture-review": {"harness": "claude", "fallback": []},
        }

    return {
        "schema_version": 1,
        "repo_id": repo_id,
        "overrides": {
            "dev_authority": {
                "task_allocation": task_alloc,
            },
            "merge_authority": {
                "can_merge": ["qa"],
                "require_non_authoring_review": True,
                "review_fallback": "same_identity_comment_checklist",
            },
            "release_authority": {
                "can_cut_release": ["pm"],
                "requires_human_approval": True,
            },
        },
    }


def run_parity_remediation(
    repo_path: str,
    dry_run: bool = False,
    branch: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs adoption parity remediation in a worktree-isolated shadow environment."""
    import shutil
    import subprocess
    from synlynk._constants import VERSION
    from synlynk.instructions import _build_templates
    from synlynk.probe import SOP_BLOCKS

    path = Path(repo_path).resolve()
    repo_name = path.name
    stack = detect_project_stack(str(path))

    directive_map = {
        "CLAUDE.md": "claude",
        "GEMINI.md": "agy",
        "AGENTS.md": "codex",
        "GROK.md": "grok",
    }

    files_to_touch = list(directive_map.keys()) + [
        ".synlynk/config.json",
        ".synlynk/policy.json",
        ".synlynk/roles.yaml",
        ".agents/claude.json",
        ".agents/agy.json",
        ".agents/codex.json",
        ".agents/grok.json",
        ".synlynk/model_rates.json",
        ".gitignore",
    ]

    gaps = []
    for doc in directive_map:
        if not (path / doc).exists():
            gaps.append(f"Missing directive file: {doc}")
        else:
            txt = (path / doc).read_text(encoding="utf-8")
            if "synlynk:harness" not in txt:
                gaps.append(f"Missing modern synlynk:harness SOP fence: {doc}")

    if not (path / ".synlynk" / "policy.json").exists():
        gaps.append("Missing .synlynk/policy.json")
    if not (path / ".synlynk" / "roles.yaml").exists():
        gaps.append("Missing .synlynk/roles.yaml")

    if dry_run:
        return {
            "status": "DRY_RUN",
            "repo_path": str(path),
            "stack": stack,
            "files_to_touch": files_to_touch,
            "gaps_identified": gaps,
            "worktree": None,
        }

    # Setup isolated worktree
    branch_name = branch or "feat/agy/synlynk-adoption-parity"
    wt_dir = path / ".worktrees" / "synlynk-parity-check"

    if wt_dir.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt_dir)], cwd=str(path), capture_output=True)
        if wt_dir.exists():
            shutil.rmtree(str(wt_dir), ignore_errors=True)

    wt_dir.parent.mkdir(parents=True, exist_ok=True)

    chk = subprocess.run(["git", "rev-parse", "--verify", branch_name], cwd=str(path), capture_output=True)
    if chk.returncode == 0:
        subprocess.run(["git", "worktree", "add", str(wt_dir), branch_name], cwd=str(path), check=True, capture_output=True)
    else:
        subprocess.run(["git", "worktree", "add", "-b", branch_name, str(wt_dir)], cwd=str(path), check=True, capture_output=True)

    # In-worktree remediation
    templates = _build_templates(repo=repo_name)
    sop_body = "\n\n".join(SOP_BLOCKS)

    for doc_name, tool_name in directive_map.items():
        doc_path = wt_dir / doc_name
        existing_content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
        template_content = templates.get(doc_name, "")

        updated = inject_sop_fences(
            content=existing_content,
            tool=tool_name,
            version=VERSION,
            start_body=template_content,
            harness_body=sop_body,
        )
        doc_path.write_text(updated, encoding="utf-8")

    # .synlynk directory
    synlynk_dir = wt_dir / ".synlynk"
    synlynk_dir.mkdir(parents=True, exist_ok=True)

    # config.json
    cfg_path = synlynk_dir / "config.json"
    cfg_data = {}
    if cfg_path.exists():
        try:
            cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg_data = {}
    cfg_data.setdefault("schema_version", 1)
    cfg_data["workgroup_agents"] = ["claude", "codex", "agy", "grok"]
    cfg_data.setdefault("agent_slots", {"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"})
    cfg_path.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")

    # policy.json
    policy_path = synlynk_dir / "policy.json"
    if not policy_path.exists():
        pol_data = generate_stack_policy(repo_name, stack)
        policy_path.write_text(json.dumps(pol_data, indent=2), encoding="utf-8")

    # roles.yaml
    roles_path = synlynk_dir / "roles.yaml"
    if not roles_path.exists():
        roles_content = (
            "schema_version: 1\n"
            "roles:\n"
            "  pm:\n"
            "    harness: claude\n"
            "    description: \"Program management, roadmap, issue triage.\"\n"
            "  architect:\n"
            "    harness: claude\n"
            "    description: \"System architecture, specifications, technical decisions.\"\n"
            "  qa:\n"
            "    harness: claude\n"
            "    description: \"PR review, test validation, merge gating.\"\n"
            "  dev:\n"
            "    harness: codex\n"
            "    description: \"Code implementation, testing, refactoring.\"\n"
            "  marketing:\n"
            "    harness: agy\n"
            "    description: \"Release communications, documentation, community updates.\"\n"
            "  tpm:\n"
            "    harness: claude\n"
            "    description: \"Technical program management, milestone execution.\"\n"
        )
        roles_path.write_text(roles_content, encoding="utf-8")

    # .agents profiles
    agents_dir = wt_dir / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for agent_name in ("claude", "agy", "codex", "grok"):
        agent_file = agents_dir / f"{agent_name}.json"
        if not agent_file.exists():
            agent_file.write_text(
                json.dumps({"harness": agent_name, "created_at": datetime.now(timezone.utc).isoformat()}, indent=2),
                encoding="utf-8",
            )

    # model_rates.json
    rates_path = synlynk_dir / "model_rates.json"
    if not rates_path.exists():
        rates_path.write_text(json.dumps({"version": 1, "rates": {}}, indent=2), encoding="utf-8")

    # .gitignore recursive hardening
    ensure_recursive_gitignore(str(wt_dir))

    # Commit inside worktree
    subprocess.run(["git", "add", "."], cwd=str(wt_dir), check=True, capture_output=True)
    status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=str(wt_dir), capture_output=True, text=True)
    if status_proc.stdout.strip():
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                (
                    "feat(synlynk): adopt modern synlynk adoption parity\n\n"
                    "- Fenced SOP directives for claude, agy, codex, grok\n"
                    "- Configured stack-aware policy.json and roles.yaml\n"
                    "- Hardened recursive .gitignore rules\n\n"
                    "Co-Authored-By: AGY <noreply@antigravity.dev>"
                ),
            ],
            cwd=str(wt_dir),
            check=True,
            capture_output=True,
        )

    return {
        "status": "SUCCESS",
        "repo_path": str(path),
        "worktree": str(wt_dir),
        "branch": branch_name,
        "files_touched": files_to_touch,
        "gaps_resolved": gaps,
    }


def check_fleet_parity(repo_path: str = ".") -> Dict[str, Any]:
    """Diagnostic check inspecting directive fences, config roster, and policy authority."""
    path = Path(repo_path).resolve()
    gaps = []

    directive_files = ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md"]
    for doc in directive_files:
        fpath = path / doc
        if not fpath.exists():
            gaps.append(f"{doc} missing")
        else:
            try:
                txt = fpath.read_text(encoding="utf-8")
                if "synlynk:harness" not in txt:
                    gaps.append(f"{doc} missing synlynk:harness fence")
            except Exception:
                gaps.append(f"{doc} unreadable")

    cfg_path = path / ".synlynk" / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            wg = cfg.get("workgroup_agents")
            if wg:
                missing_wg = [a for a in ("claude", "codex", "agy", "grok") if a not in wg]
                if missing_wg:
                    gaps.append(f"workgroup_agents missing: {', '.join(missing_wg)}")
            slots = cfg.get("agent_slots") or {}
            missing_slots = [a for a in ("claude", "codex", "agy", "grok") if a not in slots]
            if missing_slots:
                gaps.append(f"agent_slots missing: {', '.join(missing_slots)}")
        except Exception:
            gaps.append(".synlynk/config.json malformed")
    else:
        gaps.append(".synlynk/config.json missing")

    from synlynk.readiness import check_point_3_policy_authority
    pol_res = check_point_3_policy_authority(repo_path=str(path))
    if pol_res.get("status") != "PASS":
        gaps.append(f"policy: {pol_res.get('message', 'invalid')}")

    if gaps:
        return {
            "status": "WARN",
            "message": f"Fleet parity drift: {'; '.join(gaps[:3])}" + (f" (+{len(gaps)-3} more)" if len(gaps) > 3 else ""),
            "details": {"gaps": gaps},
            "remediation": "Run `synlynk heal --parity` to create a verified, worktree-isolated migration PR",
        }

    return {
        "status": "PASS",
        "message": "Directives fenced, workgroup roster complete, and policy authority active",
        "details": {"gaps": []},
        "remediation": "",
    }


