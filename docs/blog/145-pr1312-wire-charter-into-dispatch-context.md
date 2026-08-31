---
title: "PR #1312 — Wire Charter Content into Dispatch and Execution Context"
date: 2026-08-31
series: "Building the OS for Multi-Agent Development"
post: 145
pr: "#1312"
issue: "#1201"
status: open
---

# PR #1312 — Wire Charter Content into Dispatch and Execution Context

## The Broader Goal

In multi-agent software development, agents need authoritative, role-grounded directives that define their responsibilities, escalation rules, and durability. Per `docs/superpowers/specs/2026-08-27-charter-authority-design.md`, synlynk provisions durable agent records in `agent_store` with version-tracked Markdown charters.

Issue #1201 (Story `story-586b6237`) wires this charter authority directly into dispatch execution context so that every dispatched harness run receives its role-specific charter automatically as the first section in `.synlynk/contexts/<job-id>.md`.

## What Was Missing & Root Cause

Previously:
- `synlynk/charter_injection.py:render_charter_section` only resolved the default `human_authority_role` (falling back to `pm`), ignoring the specific role assigned to a dispatched task or story.
- `synlynk/context.py:generate_context` and `_generate_task_context` lacked a `role` parameter and could not inject role-specific charters for non-PM roles (`dev`, `qa`, `architect`, etc.).
- Dispatched jobs did not record `charter_role` or `charter_revision` in their job metadata dictionary, preventing downstream traceability of the exact charter revision under which an agent executed.

## What Shipped

1. **Role-Specific Charter Resolution (`synlynk/charter_injection.py`, `synlynk/__init__.py`):**
   - Added `resolve_role_charter(role=None, repo_path=None)` returning `(role, agent_id, revision, content)`.
   - Updated `render_charter_section(repo_path=None, role=None)` to resolve the explicit role when supplied, falling back to `get_human_authority_role()`.
   - Handled unadopted workspaces gracefully by returning `""` when zero agents are provisioned, while raising `CharterInjectionError` if a requested role cannot be found in an adopted workspace.

2. **Context Injection Pipeline (`synlynk/context.py`):**
   - Updated `generate_context()`, `_generate_context_from_db()`, and `_generate_task_context()` to accept `role: Optional[str] = None`.
   - Injected `render_charter_section(role=role)` at the header of generated task and full contexts.

3. **Dispatch Integration & Metadata Recording (`synlynk/dispatch.py`):**
   - Passed `role=resolved_agent_role` into `generate_context()`.
   - Recorded `charter_role` and `charter_revision` in the `job` dictionary for full telemetry and auditability.

4. **Comprehensive Test Suite (`tests/test_charter_injection_dispatch.py`):**
   - Added unit and integration tests covering empty workspaces, default PM resolution, explicit role resolution (`dev`, `qa`), missing role rejection, task context injection, and end-to-end dispatch context generation.
