"""Extractors for discovered work signals across devlogs, jobs, and diagnostics.

See docs/superpowers/specs/2026-08-31-governs-backlog-automation-design.md.
"""
from __future__ import annotations

import re
from typing import Optional


def extract_from_devlog_content(text: str, author: str = "") -> list[dict]:
    """Extract action items from devlog markdown content.

    Looks for sections like:
    - ### Discovered / Follow-up Work
    - ### Follow-ups / Tech Debt
    - Bullet points matching <!-- discover: <title> [| stage: <stage>] [| role: <role>] -->
    - Lines starting with "- [ ] TODO:" or "- [ ] Followup:"
    """
    if not text:
        return []

    results = []
    lines = text.splitlines()
    in_followup_section = False

    for line in lines:
        stripped = line.strip()
        header_match = re.match(r"^#{2,4}\s+(.*)", stripped)
        if header_match:
            hdr = header_match.group(1).lower()
            if any(k in hdr for k in ["discovered", "follow-up", "followup", "tech debt", "next steps", "open items"]):
                in_followup_section = True
            else:
                in_followup_section = False
            continue

        explicit_marker = re.search(r"<!--\s*discover:\s*(.*?)\s*-->", stripped, re.IGNORECASE)
        if explicit_marker:
            payload = explicit_marker.group(1)
            parts = [p.strip() for p in payload.split("|")]
            title = parts[0]
            stage = "open"
            role = "dev"
            for p in parts[1:]:
                if p.lower().startswith("stage:"):
                    stage = p.split(":", 1)[1].strip()
                elif p.lower().startswith("role:"):
                    role = p.split(":", 1)[1].strip()
            results.append({
                "title": title,
                "description": f"Extracted from devlog by @{author}" if author else "Extracted from devlog.",
                "stage": stage,
                "role": role,
                "source_type": "devlog",
                "source_ref": f"devlog:{author}" if author else "devlog",
            })
            continue

        if in_followup_section:
            bullet_match = re.match(r"^[-*]\s+(?:\[\s*\]\s*)?(.*)", stripped)
            if bullet_match:
                item_text = bullet_match.group(1).strip()
                if item_text and not item_text.startswith("<!--") and len(item_text) > 5:
                    item_clean = re.sub(r"^TODO:\s*|^Followup:\s*|^Tech-Debt:\s*", "", item_text, flags=re.IGNORECASE)
                    results.append({
                        "title": item_clean,
                        "description": f"Discovered during session devlog by @{author}" if author else "Discovered in session devlog.",
                        "stage": "open",
                        "role": "dev",
                        "source_type": "devlog",
                        "source_ref": f"devlog:{author}" if author else "devlog",
                    })

    return results


def extract_from_job_summary(summary: str, job_id: str = "", touched_files: list = None) -> list[dict]:
    """Extract out-of-scope follow-ups or tech debt surfaced during job execution."""
    if not summary:
        return []

    results = []
    lines = summary.splitlines()
    files_list = list(touched_files) if touched_files else []
    files_note = f" (touched files: {', '.join(files_list)})" if files_list else ""

    # Infer default role / stage from touched files if applicable
    default_role = "qa" if files_list and all(f.startswith("tests/") for f in files_list) else "dev"
    default_stage = "sustain" if files_list and all(f.startswith("tests/") for f in files_list) else "open"

    for line in lines:
        stripped = line.strip()
        match = re.search(r"(?:^|\b)(?:FOLLOWUP|TECH-DEBT|DISCOVERED):\s*(.*)", stripped, re.IGNORECASE)
        if match:
            item_text = match.group(1).strip()
            if item_text:
                results.append({
                    "title": item_text,
                    "description": f"Surfaced in job {job_id} output{files_note}.",
                    "stage": default_stage,
                    "role": default_role,
                    "source_type": "job_output",
                    "source_ref": f"job:{job_id}" if job_id else "job",
                    "touched_files": files_list,
                })
    return results


def extract_from_doctor_failures(failures: list[dict]) -> list[dict]:
    """Convert unresolved doctor diagnostic failures into tracked tech debt items."""
    results = []
    for f in failures or []:
        name = f.get("name") or f.get("check") or "Doctor health check"
        reason = f.get("reason") or f.get("message") or ""
        title = f"Fix doctor check: {name}"
        desc = f"Doctor check {name} failed: {reason}"
        results.append({
            "title": title,
            "description": desc,
            "stage": "sustain",
            "role": "qa",
            "source_type": "doctor",
            "source_ref": f"doctor:{name}",
        })
    return results
