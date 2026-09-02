# Implementation Plan: Review Dispatch Read-Only Scope (#937)

1. Extend dispatch permission resolution with an opt-in read-only filter that
   strips all `write:*` grants after merging defaults and overrides.
2. Apply the filter to review task types and make Codex review jobs use a
   read-only sandbox, including when GitHub network access is enabled.
3. Add regression tests in `tests/test_dispatch.py` for explicit write grants
   and review Codex command construction.
4. Record the design and result in the blog index, memory, and Codex devlog.
5. Run the requested focused test and the full `pytest tests/` suite.
