"""Curated blueprints for new repositories.

The blueprint catalog is intentionally data-oriented: it describes the
workspace to create without embedding repository-specific harness guidance.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class BlueprintType(str, Enum):
    DOTFILES = "dotfiles"
    PERSONAL_ASSISTANT = "personal_assistant"
    CUSTOM = "custom"


@dataclass
class PersonalCharter:
    id: str
    name: str
    description: str
    recommended_tools: List[str] = field(default_factory=list)


@dataclass
class BlueprintDefinition:
    id: str
    name: str
    description: str
    blueprint_type: BlueprintType
    available_charters: List[PersonalCharter] = field(default_factory=list)


_CHARTERS = [
    PersonalCharter(
        "bills",
        "Bills & Invoices",
        "Scans incoming bills, payment receipts, due dates, flags overdue notices",
        ["gmail-mcp", "drive-mcp"],
    ),
    PersonalCharter(
        "reimbursements",
        "Reimbursements & Deductibles",
        "Tracks work expenses, tallies deductible items, prepares claim sheets",
        ["gmail-mcp", "drive-mcp"],
    ),
    PersonalCharter(
        "docs",
        "Document & Knowledge Management",
        "Organizes Google Drive / local storage, semantic filing",
        ["drive-mcp"],
    ),
    PersonalCharter(
        "shopping",
        "Shopping & Pantry",
        "Tracks orders, deliveries, recurring consumables, grocery lists",
        ["gmail-mcp"],
    ),
    PersonalCharter(
        "fitness",
        "Health & Fitness",
        "Logs workout sessions, maps fitness targets to open calendar gaps",
        ["calendar-mcp"],
    ),
    PersonalCharter(
        "nutrition",
        "Diet & Nutrition",
        "Meal planning, grocery sync, dietary goal tracking",
        ["calendar-mcp"],
    ),
]

_CATALOG = {
    "dotfiles": BlueprintDefinition(
        id="dotfiles",
        name="Personal Dotfiles Manager & Auditor",
        description=(
            "Maintain zshrc, gitconfig, aliases, tool settings, and drift "
            "detection across machines."
        ),
        blueprint_type=BlueprintType.DOTFILES,
    ),
    "personal_assistant": BlueprintDefinition(
        id="personal_assistant",
        name="Personal Assistant & Digital Native Agent Mesh",
        description=(
            "Personal assistant connecting to Gmail/Calendar/Drive via OAuth, "
            "deploying specialized agents."
        ),
        blueprint_type=BlueprintType.PERSONAL_ASSISTANT,
        available_charters=_CHARTERS,
    ),
}


def get_blueprint_catalog() -> Dict[str, BlueprintDefinition]:
    """Return the available greenfield blueprints.

    A shallow copy protects the catalog's top-level mapping while retaining
    the dataclass values as the canonical metadata objects.
    """

    return dict(_CATALOG)


def synthesize_greenfield_goals(
    blueprint_id: str, selected_charters: Optional[List[str]] = None
) -> List[dict]:
    """Create deterministic goal records for a selected blueprint."""

    selected = selected_charters or ["bills", "reimbursements"]

    if blueprint_id == "dotfiles":
        return [
            {
                "id": "goal-dotfiles-scaffold",
                "title": "Dotfiles Repository Scaffolding & Symlink Map",
                "category": "foundation",
                "priority": "P0",
                "rationale": (
                    "Establishes non-destructive directory structure and symlink "
                    "targets for local configs."
                ),
                "acceptance_criteria": [
                    "Create .dotfiles directory layout",
                    "Map ~/.zshrc and ~/.gitconfig to repository symlinks",
                    "Verify original files are backed up safely",
                ],
                "target_milestone": "v1.0.0-rc1",
            },
            {
                "id": "goal-dotfiles-drift-cli",
                "title": "Local Configuration Drift Detection",
                "category": "quality",
                "priority": "P0",
                "rationale": (
                    "Ensures edits made outside the repository are detected and "
                    "surfaced cleanly."
                ),
                "acceptance_criteria": [
                    "Implement synlynk dotfiles check for diffs between home dir and repo",
                    "Add synlynk dotfiles sync to apply clean bidirectional updates",
                ],
                "target_milestone": "v1.0.0-rc1",
            },
            {
                "id": "goal-dotfiles-security-gate",
                "title": "Secret Leakage & Token Hygiene Hook",
                "category": "security",
                "priority": "P1",
                "rationale": "Prevents committing private API tokens or SSH keys into git.",
                "acceptance_criteria": [
                    "Install pre-commit secret scanning hook",
                    "Add .gitignore rules for sensitive env files",
                ],
                "target_milestone": "v1.0.0-rc1",
            },
        ]

    charter_names = [charter.name for charter in _CHARTERS if charter.id in selected]
    return [
        {
            "id": "goal-assistant-oauth-hub",
            "title": "Provider OAuth Hub & MCP Transport",
            "category": "foundation",
            "priority": "P0",
            "rationale": "Enables secure credential exchange and tool access to Gmail, Calendar, and Drive.",
            "acceptance_criteria": [
                "Initialize token store in OS keychain / ~/.synlynk/keys",
                "Verify Google Workspace / Gmail OAuth connection test query exits 0",
                "Register mcp.google tools into synlynk fleet registry",
            ],
            "target_milestone": "v1.0.0-rc1",
        },
        {
            "id": "goal-assistant-charters-setup",
            "title": f"Agent Charters Setup: {', '.join(charter_names) or 'Personal Agents'}",
            "category": "charter",
            "priority": "P0",
            "rationale": f"Registers user-selected charters ({', '.join(selected)}) with sandboxed domain permissions.",
            "acceptance_criteria": [
                f"Register {len(selected)} agent roles into state.db",
                "Verify permissions sandbox restricts cross-domain token access",
                "Generate domain instruction headers in .synlynk/context.md",
            ],
            "target_milestone": "v1.0.0-rc1",
        },
        {
            "id": "goal-assistant-ingestion-loop",
            "title": "Autonomous Ingestion & Event Extraction Loop",
            "category": "feature",
            "priority": "P1",
            "rationale": "Automates routine polling and event classification without human prompting.",
            "acceptance_criteria": [
                "Implement scheduled daemon check for unread receipts/notices",
                "Extract dates, amounts, and metadata into verified structured ledger",
                "Require explicit human signoff before any external write/payment action",
            ],
            "target_milestone": "v1.0.0-rc1",
        },
        {
            "id": "goal-assistant-digest-alerts",
            "title": "Unified Executive Digest & Desktop Alerts",
            "category": "feature",
            "priority": "P2",
            "rationale": "Delivers morning summary of upcoming obligations across active charters.",
            "acceptance_criteria": [
                "Implement daily summary digest in terminal and local Vizor card",
                "Trigger desktop alerts for bills due in <= 48 hours",
            ],
            "target_milestone": "v1.0.0-rc1",
        },
    ]
