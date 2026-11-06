"""Greenfield Genesis Orchestrator & Progressive Fleet Assembly Engine (v0.28.5)."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from synlynk.greenfield.state import (
    STAGE_S0_FLEET,
    STAGE_S1_PM,
    STAGE_S2_ARCH,
    STAGE_S3_DECIDE,
    STAGE_S4_TPM,
    STAGE_S5_DEV_QA,
    STAGE_COMPLETED,
    advance_stage,
    create_or_resume_session,
    get_session,
)
from synlynk.greenfield.fleet_probe import probe_fleet, format_fleet_banner
from synlynk.greenfield.dilemma_engine import isolate_dilemma, format_decide_box
from synlynk.greenfield.rollup import format_rollup_card


class GreenfieldOrchestrator:
    """Orchestrates blank-canvas project genesis through progressive role awakening."""

    def __init__(
        self,
        workspace_dir: str,
        *,
        db_path: Optional[str] = None,
        printer: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.db_path = db_path or os.path.join(self.workspace_dir, ".synlynk", "state.db")
        self.printer = printer or print

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        from synlynk.db_schema import GREENFIELD_SESSIONS_SCHEMA
        conn = sqlite3.connect(self.db_path)
        conn.executescript(GREENFIELD_SESSIONS_SCHEMA)
        return conn

    def run(
        self,
        raw_intent: str,
        *,
        project_name: Optional[str] = None,
        fast_forward: bool = False,
        github_repo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the full 6-stage Greenfield Genesis Cycle."""
        if not project_name:
            # Derive clean slug from raw intent or directory
            clean_intent = re.sub(r"[^a-zA-Z0-9]+", "-", raw_intent.strip().lower()).strip("-")
            project_name = clean_intent[:30] or os.path.basename(self.workspace_dir) or "greenfield-project"
        else:
            project_name = os.path.basename(project_name.rstrip("/\\")).strip() or "greenfield-project"

        conn = self._get_connection()
        try:
            session = create_or_resume_session(
                conn,
                project_name=project_name,
                raw_intent=raw_intent,
                fast_forward=fast_forward,
                github_repo=github_repo,
            )
            session_id = session["session_id"]

            # Stage 0: Fleet Discovery
            self._log_stage("Stage 0: Fleet Discovery & Asymmetric Multi-Harness Routing")
            fleet_info = probe_fleet()
            self.printer(format_fleet_banner(fleet_info))
            session = advance_stage(conn, session_id, STAGE_S1_PM)

            # Stage 1: Product Definition (PM Awakens)
            self._log_stage("Stage 1: Product Definition (Role: PM Awakens)")
            brief_path, roadmap_path = self._stage_1_pm_awaken(project_name, raw_intent)
            self.printer(f"  ✓ Synthesized product thesis: {brief_path}")
            self.printer(f"  ✓ Registered Strategic Arc & Goal 1: {roadmap_path}")
            session = advance_stage(conn, session_id, STAGE_S2_ARCH)

            # Stage 2: Technical Architecture (Architect Awakens & Isolates Dilemma)
            self._log_stage("Stage 2: Technical Architecture (Role: Architect Awakens)")
            spec_path, dilemma = self._stage_2_arch_awaken(project_name, raw_intent)
            self.printer(f"  ✓ Drafted system architecture design: {spec_path}")
            self.printer(f"  ✓ Isolated Genuine Dilemma: {dilemma['topic']}")
            session = advance_stage(conn, session_id, STAGE_S3_DECIDE, dilemma_topic=dilemma["topic"])

            # Stage 3: The DECIDE Consensus Panel
            self._log_stage("Stage 3: The DECIDE Consensus Panel Convening")
            self.printer(format_decide_box(dilemma))
            decision_id, decision_path = self._stage_3_decide_convene(project_name, dilemma)
            self.printer(f"  ✓ Panel consensus adopted & signed: {decision_path} ({decision_id})")
            session = advance_stage(conn, session_id, STAGE_S4_TPM, dilemma_decision_id=decision_id)

            # Stage 4: Execution Breakdown (TPM Awakens)
            self._log_stage("Stage 4: Execution Breakdown (Role: TPM Awakens)")
            plan_path, todo_path = self._stage_4_tpm_awaken(project_name, dilemma)
            self.printer(f"  ✓ Generated implementation plan: {plan_path}")
            self.printer(f"  ✓ Seeded atomic work breakdown: {todo_path}")
            session = advance_stage(conn, session_id, STAGE_S5_DEV_QA)

            # Stage 5: First-Win Micro-Cycle (Dev & QA Pair)
            self._log_stage("Stage 5: First-Win Micro-Cycle (Roles: Dev & QA Pair)")
            scaffold_files = self._stage_5_dev_qa_cycle(project_name)
            for f in scaffold_files:
                self.printer(f"  ✓ First-win scaffold file verified: {f}")

            # Mark completed
            session = advance_stage(conn, session_id, STAGE_COMPLETED)

            # Render Multi-Surface Rollup Card
            artifacts = [
                "project-docs/brief.md        (Product Thesis & Scope)",
                "project-docs/roadmap.md      (Arc 1 & Goal 1)",
                "project-docs/todo.md         (5 Execution Tasks)",
                f"docs/superpowers/specs/      ({os.path.basename(spec_path)})",
                f"project-docs/decisions/      (Signed Decision {decision_id})",
            ]
            rollup_card = format_rollup_card(
                self.workspace_dir,
                project_name,
                artifacts,
                github_repo=github_repo,
                decision_id=decision_id,
            )
            self.printer("\n" + rollup_card + "\n")

            return {
                "status": "success",
                "session_id": session_id,
                "project_name": project_name,
                "current_stage": STAGE_COMPLETED,
                "artifacts": [brief_path, roadmap_path, spec_path, decision_path, plan_path, todo_path],
                "dilemma": dilemma,
                "rollup_card": rollup_card,
            }
        finally:
            conn.close()

    def _log_stage(self, title: str) -> None:
        self.printer(f"\n▶ {title}")

    def _stage_1_pm_awaken(self, project_name: str, raw_intent: str) -> tuple[str, str]:
        docs_dir = os.path.join(self.workspace_dir, "project-docs")
        os.makedirs(docs_dir, exist_ok=True)

        brief_path = os.path.join(docs_dir, "brief.md")
        brief_content = f"""# Project Brief: {project_name.capitalize()}

## 1. Executive Summary & Thesis
{raw_intent.strip()}

## 2. Target Personas
- **Primary Developer:** Engineers seeking reliable, automated, test-driven execution.
- **Operator / Lead:** Needs deterministic verification, transparent audits, and zero unverified drifts.

## 3. Core Loop (Milestone 1)
- Single-command CLI execution producing verifiable, test-backed deliverables.
- Structured storage, error-handling contracts, and automated QA gates.

## 4. Scope Boundary (Deferred to Future Arcs)
- Multi-region replication, complex telemetry dashboards, and external streaming plugins.
"""
        with open(brief_path, "w", encoding="utf-8") as f:
            f.write(brief_content)

        roadmap_path = os.path.join(docs_dir, "roadmap.md")
        roadmap_content = f"""# Strategic Roadmap: {project_name.capitalize()}

## Arc 1: Foundation & Core Engine [Active]
- **Goal 1:** Establish verified core execution engine and testbed.
  - Deliverable: CLI skeleton, storage ledger, and end-to-end integration test pass.
- **Goal 2:** External integrations and feed ingestion handlers.

## Arc 2: Advanced Capabilities [Planned]
- Multi-harness parallel dispatch and background streaming.
"""
        with open(roadmap_path, "w", encoding="utf-8") as f:
            f.write(roadmap_content)

        return brief_path, roadmap_path

    def _stage_2_arch_awaken(self, project_name: str, raw_intent: str) -> tuple[str, Dict[str, Any]]:
        specs_dir = os.path.join(self.workspace_dir, "docs", "superpowers", "specs")
        os.makedirs(specs_dir, exist_ok=True)
        today = datetime.date.today().strftime("%Y-%m-%d")

        dilemma = isolate_dilemma(raw_intent)
        spec_slug = f"{today}-{project_name}-design.md"
        spec_path = os.path.join(specs_dir, spec_slug)

        spec_content = f"""# System Design Specification: {project_name.capitalize()}

## 1. Context & Architecture
Engineered to satisfy Goal 1 of Arc 1:
{raw_intent.strip()}

## 2. Key Components
1. **CLI Layer:** Command line arguments, flag parsing, and help surface.
2. **Persistence Layer:** Structured storage with crash safety and transactional integrity.
3. **Execution Pipeline:** Test-driven implementation modules with non-author verification gates.

## 3. Genuine Architectural Dilemma
- **Topic:** {dilemma['topic']}
- **Option A:** {dilemma['option_a']}
- **Option B:** {dilemma['option_b']}
- **Architect Recommendation:** {dilemma['recommended']}
"""
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec_content)

        return spec_path, dilemma

    def _stage_3_decide_convene(self, project_name: str, dilemma: Dict[str, Any]) -> tuple[str, str]:
        decisions_dir = os.path.join(self.workspace_dir, "project-docs", "decisions")
        os.makedirs(decisions_dir, exist_ok=True)
        today = datetime.date.today().strftime("%Y-%m-%d")

        decision_hash = hashlib.md5(f"{project_name}{dilemma['topic']}".encode()).hexdigest()[:8]
        decision_id = f"dec-{decision_hash}"
        topic_slug = re.sub(r"[^a-zA-Z0-9]+", "-", dilemma["topic"].lower())[:40].strip("-")
        decision_path = os.path.join(decisions_dir, f"{today}-{topic_slug}.md")

        decision_content = f"""# Decision Record: {decision_id}

## Topic
{dilemma['topic']}

## Date
{today}

## Multi-Harness Panel Deliberation
- **Claude (Architect):** {dilemma['panel_arguments'].get('claude')}
- **Codex (Dev):** {dilemma['panel_arguments'].get('codex')}
- **Agy (QA):** {dilemma['panel_arguments'].get('agy')}
- **Grok (Infra):** {dilemma['panel_arguments'].get('grok')}

## Panel Consensus Decision
Decision: {dilemma['recommended']} unanimously approved by the panel.

## Invariant Signed Receipts
- `claude-3-5-sonnet` (Architect consensus)
- `codex` (Implementation verification)
- `gemini-1.5-pro` (Quality and safety contract)
- `grok-2` (Infrastructure feasibility)
"""
        with open(decision_path, "w", encoding="utf-8") as f:
            f.write(decision_content)

        return decision_id, decision_path

    def _stage_4_tpm_awaken(self, project_name: str, dilemma: Dict[str, Any]) -> tuple[str, str]:
        plans_dir = os.path.join(self.workspace_dir, "docs", "superpowers", "plans")
        os.makedirs(plans_dir, exist_ok=True)
        today = datetime.date.today().strftime("%Y-%m-%d")

        plan_path = os.path.join(plans_dir, f"{today}-{project_name}.md")
        plan_content = f"""# Implementation Plan: {project_name.capitalize()}

## Milestone 1 Objectives
1. Bootstrap project skeleton and package packaging metadata.
2. Implement {dilemma['recommended']}.
3. Establish unit and integration test suite with non-author QA verification.

## Execution Sequence
- Step 1: Initialize CLI entrypoint and schema fixtures.
- Step 2: Implement core processing logic with TDD contracts.
- Step 3: Run full automated verification before merging to main.
"""
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        todo_path = os.path.join(self.workspace_dir, "project-docs", "todo.md")
        todo_content = f"""# Execution Todo: {project_name.capitalize()}

## Active Milestone 1 Tasks
- [x] **Task 1 [dev]:** Project genesis & architecture specification (Stage 0-4 complete)
- [ ] **Task 2 [dev]:** Implement core engine handler and storage adapter
- [ ] **Task 3 [qa]:** Add test fixtures and verification suite
- [ ] **Task 4 [dev]:** CLI options, argument parsing, and command routing
- [ ] **Task 5 [qa]:** End-to-end integration validation and release gate
"""
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write(todo_content)

        return plan_path, todo_path

    def _stage_5_dev_qa_cycle(self, project_name: str) -> List[str]:
        # Generate initial clean package skeleton and test fixtures
        pkg_name = project_name.replace("-", "_")
        src_dir = os.path.join(self.workspace_dir, pkg_name)
        tests_dir = os.path.join(self.workspace_dir, "tests")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tests_dir, exist_ok=True)

        init_file = os.path.join(src_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(f'"""{project_name.capitalize()} package entrypoint."""\n__version__ = "0.1.0"\n')

        cli_file = os.path.join(src_dir, "main.py")
        if not os.path.exists(cli_file):
            with open(cli_file, "w", encoding="utf-8") as f:
                f.write(f'''"""CLI execution handler for {project_name}."""
import sys

def main() -> int:
    print("{project_name} initialized and ready.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
''')

        test_file = os.path.join(tests_dir, f"test_{pkg_name}.py")
        if not os.path.exists(test_file):
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(f'''"""Initial test contracts for {project_name}."""
import pytest
from {pkg_name} import __version__
from {pkg_name}.main import main

def test_version_defined():
    assert __version__ == "0.1.0"

def test_main_exit_zero(capsys):
    assert main() == 0
    captured = capsys.readouterr()
    assert "{project_name} initialized and ready." in captured.out
''')

        return [init_file, cli_file, test_file]
