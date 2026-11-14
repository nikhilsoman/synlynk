"""Constitution Citation & Drift Gate.

Inspects instruction files (CLAUDE.md, GEMINI.md, AI_INSTRUCTIONS.md, etc.) and
role charters for constitutional law citations per
docs/superpowers/specs/2026-11-13-synlynk-constitution-charter-governance-design.md.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Set
from synlynk.constitution import CONSTITUTION_LAWS, validate_citation_tag


_CITATION_SCAN_FILES = [
    "CLAUDE.md",
    "GEMINI.md",
    "AI_INSTRUCTIONS.md",
    "AGENTS.md",
]

_CITATION_EXTRACTOR = re.compile(r"<!--\s*constitution:\s*([a-zA-Z0-9_\-]+)\s*-->")


def scan_file_for_citations(file_path: str) -> Set[str]:
    """Scan a single file for valid constitution citation IDs."""
    if not os.path.isfile(file_path):
        return set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return set()

    found = set()
    for match in _CITATION_EXTRACTOR.finditer(content):
        law_id = match.group(1).lower()
        if law_id in CONSTITUTION_LAWS:
            found.add(law_id)
    return found


def check_constitution_gate(
    repo_path: str,
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate constitutional citation coverage across governed instructions.
    
    Returns:
        Dict with keys:
          - passed: bool
          - mode: "observe" | "enforce"
          - warnings: List[str]
          - errors: List[str]
          - cited_laws: List[str]
          - orphaned_laws: List[str]
    """
    auth_cfg = policy.get("constitution_authority", {})
    mode = auth_cfg.get("require_citation_mode", "observe").lower()
    if mode not in ("observe", "enforce"):
        mode = "observe"

    all_law_ids = set(CONSTITUTION_LAWS.keys())
    aggregated_citations: Set[str] = set()
    uncited_files: List[str] = []

    for fname in _CITATION_SCAN_FILES:
        fpath = os.path.join(repo_path, fname)
        if os.path.exists(fpath):
            citations = scan_file_for_citations(fpath)
            if citations:
                aggregated_citations.update(citations)
            else:
                uncited_files.append(fname)

    # Check for orphaned laws (laws never cited anywhere)
    orphaned_laws = sorted(list(all_law_ids - aggregated_citations))

    warnings: List[str] = []
    errors: List[str] = []

    if uncited_files:
        msg = f"Instruction file(s) missing constitutional citations: {', '.join(uncited_files)}"
        if mode == "enforce":
            errors.append(msg)
        else:
            warnings.append(f"[OBSERVE MODE] {msg}")

    if orphaned_laws:
        msg = f"Constitutional laws orphaned (not cited in any instruction file): {', '.join(orphaned_laws)}"
        if mode == "enforce":
            errors.append(msg)
        else:
            warnings.append(f"[OBSERVE MODE] {msg}")

    passed = (len(errors) == 0)

    return {
        "passed": passed,
        "mode": mode,
        "warnings": warnings,
        "errors": errors,
        "cited_laws": sorted(list(aggregated_citations)),
        "orphaned_laws": orphaned_laws,
    }
