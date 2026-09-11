"""Guard the Milestone v0.20.0 architectural design spec against silent section loss."""
from pathlib import Path


SPEC_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-09-11-v0.20.0-visual-workspace-autonomous-onboarding-design.md"
)

REQUIRED_HEADINGS = (
    "## 1. Executive Summary & Architectural Motivation",
    "## 2. Workspace Agent Creation & Charter Formation Flow",
    "## 3. Cluster A: Visual Workspace Views, Role Setup Wizard & Marketing Release Ceremony",
    "## 4. Cluster B: Worktree Lifecycle & Rebase Concurrency",
    "## 5. Cluster C: Fleet Diagnostic Truth & Concurrency Resilience",
    "## 6. Cluster D: Next-Gen Harness Onboarding — Meta Muse Integration",
    "## 7. Implementation Sequence, Testing Strategy & Acceptance Criteria",
)

REQUIRED_PHRASES = (
    "Cluster A: Visual Workspace Views",
    "Cluster B: Worktree Lifecycle & Rebase Concurrency",
    "Cluster C: Fleet Diagnostic Truth & Concurrency Resilience",
    "Cluster D: Next-Gen Harness Onboarding",
    "Meta Muse",
    "sparse-checkout",
    "4-Point Readiness Matrix",
    "synlynk doctor --readiness",
    "synlynk viz",
    "SFIA 9",
    "PRAGMA busy_timeout = 30000",
    "Marketing Workspace Agent & Release Ceremony Lifecycle",
    "GitHub README Maintenance",
    "Synlynk Docs Bundles",
    "Quick Start Guide",
    "Official Reference / Manual",
    "Command Reference",
)


def test_v0_20_0_spec_exists():
    assert SPEC_PATH.is_file(), f"missing design spec at {SPEC_PATH}"


def test_v0_20_0_spec_covers_required_sections():
    text = SPEC_PATH.read_text(encoding="utf-8")
    missing_headings = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    missing_phrases = [phrase for phrase in REQUIRED_PHRASES if phrase not in text]
    assert not missing_headings, f"spec missing headings: {missing_headings}"
    assert not missing_phrases, f"spec missing locked phrases: {missing_phrases}"
    assert "TBD" not in text
    assert "TODO" not in text
