# Plan: manifest callback loopback server concurrency (#906)

Spec: `docs/superpowers/specs/2026-09-02-manifest-callback-concurrency-design.md`

## Tasks

1. `synlynk/team.py::_run_manifest_callback_server`
   - Swap `threading.Event` + list capture for `queue.Queue()`.
   - Swap `HTTPServer` for `ThreadingHTTPServer`.
   - Update `wait_for_code()` to `queue.get(timeout=...)` / `except queue.Empty: return None`.
   - Add a docstring explaining the prior drop bug and the fix.
2. Tests: add `tests/test_agent_cli.py::test_manifest_auth_prevent_dropped_oauth_codes_in_manifest_callback_server`
   covering two concurrent `/callback` requests, asserting neither code is
   lost.
3. Run `pytest tests/` in full to confirm no regressions in `test_team.py`
   or elsewhere that touches `_run_manifest_callback_server`.
4. Docs: this plan, the design spec, blog post, `docs/blog/README.md` index
   entry, `project-docs/memory.md`, `project-docs/devlogs/claude.md`.

## Verification

`pytest tests/test_agent_cli.py -k 'auth_prevent_dropped_oauth_codes_in_mani' -v`
