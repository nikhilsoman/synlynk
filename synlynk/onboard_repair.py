"""Conservative local repair for the known #5413 onboarding artifacts."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
from typing import Iterable


_INSTRUCTION_FILES = ("CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md")


@dataclass(frozen=True)
class RepairAction:
    """A single safe-to-report remediation finding."""

    kind: str
    path: Path
    detail: str


@dataclass
class RepairReport:
    """Findings and changes made by :func:`repair_onboarding`."""

    actions: list[RepairAction] = field(default_factory=list)
    applied: list[RepairAction] = field(default_factory=list)


def _is_synlynk_source_checkout(repo_root: Path) -> bool:
    """Return whether ``repo_root`` is a Synlynk source checkout."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        return 'name = "synlynk"' in pyproject.read_text(encoding="utf-8")
    except OSError:
        return False


def _git_show_head(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:{path.name}"], cwd=path.parent, text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def _strip_managed_sections(content: str) -> str:
    """Remove Synlynk HTML fences so user-owned text can be compared safely."""
    start = "<!-- synlynk:start"
    end = "<!-- /synlynk:end -->"
    remaining = content
    while start in remaining:
        before, _, tail = remaining.partition(start)
        _, marker, after = tail.partition(end)
        if not marker:
            return content
        remaining = before + after
    return remaining


def _has_managed_fence_only_diff(path: Path) -> bool:
    """Check that HEAD differs only by complete Synlynk-managed fence blocks."""
    head = _git_show_head(path)
    if head is None:
        return False
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return current != head and _strip_managed_sections(current) == _strip_managed_sections(head)


def _restore_from_head(path: Path) -> None:
    subprocess.run(
        ["git", "checkout", "HEAD", "--", path.name], cwd=path.parent,
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _is_git_repo(path: Path) -> bool:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=path,
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        return False


def _workspace_invalid_repos(workspaces_dir: Path, source_checkout: Path) -> Iterable[RepairAction]:
    if not workspaces_dir.is_dir():
        return ()
    actions: list[RepairAction] = []
    for config_path in sorted(workspaces_dir.glob("*/config.json")):
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        repos = payload.get("repos", []) if isinstance(payload, dict) else []
        for raw_path in repos if isinstance(repos, list) else []:
            raw_path = raw_path.get("path") if isinstance(raw_path, dict) else raw_path
            if not isinstance(raw_path, str):
                actions.append(RepairAction(
                    "workspace-invalid-repo", config_path,
                    "workspace includes an invalid repository entry; left unchanged",
                ))
                continue
            candidate = Path(raw_path).expanduser()
            if candidate.resolve() == source_checkout.resolve():
                detail = "workspace includes the Synlynk source checkout; left unchanged"
            elif not _is_git_repo(candidate):
                detail = "workspace includes a path that is not a git repository; left unchanged"
            else:
                continue
            actions.append(RepairAction("workspace-invalid-repo", config_path, detail))
    return actions


def repair_onboarding(repo_root: Path | str = ".", home: Path | str | None = None, apply: bool = False) -> RepairReport:
    """Inspect and optionally repair only #5413's known local artifacts.

    Stashes and workspace configurations are always reported-only because their
    intent cannot be recovered safely.  Applying a repair is limited to a
    fence-only instruction-file restoration and the orphaned home context made
    by running onboarding outside a git repository.
    """
    root = Path(repo_root).resolve()
    home_path = Path.home() if home is None else Path(home).expanduser().resolve()
    report = RepairReport()

    if _is_synlynk_source_checkout(root):
        for name in _INSTRUCTION_FILES:
            instruction = root / name
            if instruction.is_file() and _has_managed_fence_only_diff(instruction):
                action = RepairAction("restore-managed-fence", instruction, "restore fence-only change from HEAD")
                report.actions.append(action)
                if apply:
                    _restore_from_head(instruction)
                    report.applied.append(action)

    orphan_context = home_path / ".synlynk" / "context.md"
    if orphan_context.is_file() and not _is_git_repo(root):
        action = RepairAction("remove-orphan-context", orphan_context, "remove context created outside a git repository")
        report.actions.append(action)
        if apply:
            orphan_context.unlink()
            report.applied.append(action)

    report.actions.extend(_workspace_invalid_repos(home_path / ".synlynk" / "workspaces", root))
    return report


def cmd_onboard_repair(dry_run: bool = True) -> int:
    """Run the user-facing repair command and print a concise receipt."""
    report = repair_onboarding(apply=not dry_run)
    mode = "dry run" if dry_run else "applied"
    print(f"onboard repair ({mode})")
    if not report.actions:
        print("  No known #5413 onboarding artifacts found.")
        return 0
    for action in report.actions:
        status = "applied" if action in report.applied else "found"
        print(f"  {status}: {action.path} — {action.detail}")
    if dry_run:
        print("  Re-run with --apply to perform only the listed safe repairs.")
    return 0
