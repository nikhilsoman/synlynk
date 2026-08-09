"""Baseline workspace-canon.md generation for cold-start Phase 2.

Generates a Documentation Index and a 3-claim receipt from shallow-scan
data; every other section the parent spec describes ships as a skeleton
stub. See docs/superpowers/specs/2026-08-09-cold-start-phase2-canon-baseline-design.md.
"""
import os
import re
import subprocess
import time
from typing import Optional

_CANON_FILENAME = "workspace-canon.md"

_DOC_INDEX_DIRS = ("project-docs", "docs")

_SKELETON_SECTIONS = (
    "Retrospective Roadmap",
    "Current State (active code only)",
    "Functional View",
    "Data View",
    "Infra View",
    "Ops View",
    "UX View",
)

_SKELETON_NOTE = (
    "_Not yet assessed — see "
    "docs/superpowers/specs/2026-08-09-cold-start-design.md for the full canon vision._"
)

_PROVENANCE_RE = re.compile(
    r"<!--\s*canon:section=baseline\s+sha=(?P<sha>[0-9a-f]+|unknown)\s+"
    r"assessed_at=(?P<assessed_at>\S+)\s*-->"
)


def _build_documentation_index(root: str) -> str:
    """Walks project-docs/ and docs/ recursively for .md files, grouped by directory."""
    lines = ["## Documentation Index", ""]
    found_any = False
    for top in _DOC_INDEX_DIRS:
        top_path = os.path.join(root, top)
        if not os.path.isdir(top_path):
            continue
        files = []
        for dirpath, _dirnames, filenames in os.walk(top_path):
            for fn in filenames:
                if fn.endswith(".md"):
                    rel = os.path.relpath(os.path.join(dirpath, fn), root)
                    files.append(rel)
        if not files:
            continue
        found_any = True
        lines.append(f"### {top}/")
        for rel in sorted(files):
            lines.append(f"- `{rel}`")
        lines.append("")
    if not found_any:
        lines.append("_No project-docs/ or docs/ markdown files found._")
        lines.append("")
    return "\n".join(lines)


def _build_claim_receipt(scan: dict) -> list:
    """Up to 3 claims sourced directly from shallow-scan data. A claim is
    skipped outright — never fabricated — if its backing field is missing."""
    claims = []
    repos = scan.get("repos") or []
    repo = repos[0] if repos else None

    if repo and repo.get("stack_labels"):
        stack = ", ".join(repo["stack_labels"])
        claims.append({
            "claim": f"Detected stack: {stack}",
            "confidence": "found",
            "verify": f"ls {repo.get('path', '.')}",
        })

    if repo and repo.get("path"):
        claims.append({
            "claim": f"This is a git repository at {repo['path']}",
            "confidence": "found",
            "verify": f"git -C {repo['path']} rev-parse --show-toplevel",
        })

    harnesses = scan.get("harnesses") or []
    if harnesses:
        names = ", ".join(h["name"] for h in harnesses)
        first = harnesses[0]["name"]
        claims.append({
            "claim": f"Harness available on PATH: {names}",
            "confidence": "found",
            "verify": f"which {first}",
        })

    return claims[:3]


def _render_canon(root: str, scan: dict, head_sha: Optional[str] = None) -> str:
    sha = head_sha or "unknown"
    assessed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    provenance = f"<!-- canon:section=baseline sha={sha} assessed_at={assessed_at} -->"

    claims = _build_claim_receipt(scan)

    lines = [
        "# Workspace Canon",
        "",
        provenance,
        "",
        _build_documentation_index(root),
        "## 3-Claim Receipt",
        "",
    ]
    if claims:
        for i, c in enumerate(claims, start=1):
            lines.append(f"{i}. **{c['claim']}** ({c['confidence']})")
            lines.append(f"   Verify: `{c['verify']}`")
    else:
        lines.append("_No claims could be derived from the current scan data._")
    lines.append("")

    for section in _SKELETON_SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
        lines.append(_SKELETON_NOTE)
        lines.append("")

    return "\n".join(lines)


def _write_canon(root: str, content: str) -> str:
    path = os.path.join(root, _CANON_FILENAME)
    with open(path, "w") as fh:
        fh.write(content)
    return path


def _head_sha(root: str) -> Optional[str]:
    """Full HEAD SHA for `root`, or None if not a git repo / no commits.

    Uses `git -C <root>` rather than relying on process cwd, since `root`
    may differ from the caller's current working directory.
    """
    try:
        result = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha if len(sha) == 40 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _parse_canon_provenance(root: str) -> Optional[dict]:
    path = os.path.join(root, _CANON_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            content = fh.read()
    except OSError:
        return None
    match = _PROVENANCE_RE.search(content)
    if not match:
        return None
    return {"sha": match.group("sha"), "assessed_at": match.group("assessed_at")}


def _check_canon_staleness(root: str) -> list:
    """Returns ["baseline"] if the stamped baseline section is stale, else [].

    A missing/malformed provenance comment counts as stale. A stamped
    sha of "unknown" (no git repo at generation time) is never reported
    stale — there is nothing to compare it against.
    """
    provenance = _parse_canon_provenance(root)
    if provenance is None:
        return ["baseline"]
    if provenance["sha"] == "unknown":
        return []
    current_sha = _head_sha(root)
    if current_sha is None or current_sha == provenance["sha"]:
        return []
    return ["baseline"]
