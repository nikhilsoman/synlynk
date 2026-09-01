# Wire Charter Content into Dispatch Context Implementation Plan

- **Spec**: `docs/superpowers/specs/2026-08-27-charter-authority-design.md`
- **Issue**: #1201
- **Goal**: Wire workspace agent charter rendering and resolution into `synlynk/charter_injection.py`, `synlynk/context.py`, and `synlynk/dispatch.py`.

## Plan Steps
1. Enhance `synlynk/charter_injection.py` to support explicit `role` resolution with fallback to `get_human_authority_role()`.
2. Update `_generate_task_context` and `_generate_context_from_db` in `synlynk/context.py` to inject `render_charter_section()`.
3. Update `dispatch_agent()` in `synlynk/dispatch.py` to resolve the agent role, pass it to context generation, and record `charter_role` and `charter_revision` in job metadata.
4. Add comprehensive unit tests in `tests/test_charter_injection_dispatch.py`.
5. Run full test suite and verify all tests pass.
6. Open PR and dispatch for review.
