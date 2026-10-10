"""Concierge Agent: synthesizes structured feature proposals from user answers."""
from dataclasses import dataclass
from typing import Dict


@dataclass
class ConciergeResult:
    title: str
    body_markdown: str
    target: str  # local_spec or upstream_issue


def synthesize_github_issue(answers: Dict[str, str]) -> str:
    title = answers.get("title", "New Feature Proposal")
    problem = answers.get("problem", "")
    scope = answers.get("scope", "")
    criteria = answers.get("criteria", "")

    return f"""## Summary
{title}

### Problem Statement
{problem}

### Proposed Scope
{scope}

## Acceptance Criteria
{criteria}

---
*Synthesized via Synlynk Concierge Agent*
"""
