"""Small, conservative helpers for append-only markdown rebases."""

import os
import re
import subprocess
from typing import Optional


MARKDOWN_INDEX_PATHS = (
    "docs/blog/README.md",
    "project-docs/memory.md",
    "CHANGELOG.md",
)
_CONFLICT = re.compile(r"^<<<<<<< .*$", re.M)
_PR_NUMBER = re.compile(r"(?:PR|#)(\d+)", re.I)


def _merge_markdown_conflict(text: str) -> Optional[str]:
    """Resolve conflict blocks by preserving unique lines in stable order."""
    if not _CONFLICT.search(text):
        return None
    lines = text.splitlines(keepends=True)
    output = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<<"):
            output.append(lines[i]); i += 1; continue
        ours, theirs = [], []
        i += 1
        target = ours
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            if lines[i].startswith("======="):
                target = theirs
            else:
                target.append(lines[i])
            i += 1
        if i >= len(lines):
            return None
        combined = []
        for line in ours + theirs:
            if line not in combined:
                combined.append(line)
        if any("|" in line for line in combined):
            header = [line for line in combined if line.lstrip().startswith("|") and "---" in line]
            body = [line for line in combined if line not in header]
            body.sort(key=lambda line: int(_PR_NUMBER.search(line).group(1)) if _PR_NUMBER.search(line) else 10**9)
            combined = body[:1] + header + body[1:] if header else body
        output.extend(combined)
        i += 1
    return "".join(output)


def auto_rebase_markdown_conflicts(repo_path: str, branch: str, target_branch: str = "main") -> bool:
    """Merge target into *branch* when all conflicts are supported markdown appends."""
    def run(*args):
        return subprocess.run(["git", "-C", repo_path, *args], text=True,
                              capture_output=True, check=False)

    if run("fetch", "origin", target_branch).returncode != 0:
        return False
    merge = run("merge", "--no-edit", f"origin/{target_branch}")
    if merge.returncode == 0:
        return True
    status = run("status", "--porcelain").stdout.splitlines()
    conflicted = [line[3:] for line in status if line.startswith("UU ")]
    if not conflicted or any(path not in MARKDOWN_INDEX_PATHS for path in conflicted):
        run("merge", "--abort")
        return False
    for path in conflicted:
        full = os.path.join(repo_path, path)
        with open(full, encoding="utf-8") as handle:
            resolved = _merge_markdown_conflict(handle.read())
        if resolved is None:
            run("merge", "--abort"); return False
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(resolved)
    if run("add", "--", *conflicted).returncode != 0:
        run("merge", "--abort"); return False
    return run("commit", "-m", "merge: auto-rebase markdown index").returncode == 0
