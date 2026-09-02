# Claude Devlog

## 2026-09-02 — Manifest Callback Server Concurrency Fix (#906)

- Root-caused the drop to `synlynk/team.py::_run_manifest_callback_server`'s
  `threading.Event` + list capture: the check-then-set guard only ever kept
  the first `/callback` request's OAuth code, silently discarding any second
  concurrent one.
- Fixed by switching to `queue.Queue()` (unconditional `put`, never drops)
  and `http.server.ThreadingHTTPServer` (concurrent requests dispatched to
  independent handler threads instead of serializing behind one accept
  loop). `wait_for_code()`/`shutdown()` external contract unchanged.
- Added design spec `docs/superpowers/specs/2026-09-02-manifest-callback-concurrency-design.md`
  and plan `docs/superpowers/plans/2026-09-02-manifest-callback-concurrency.md`.
- Added `tests/test_agent_cli.py::test_manifest_auth_prevent_dropped_oauth_codes_in_manifest_callback_server`,
  firing two concurrent callback requests with distinct codes and asserting
  both are retrievable.
- Added blog post 158 and indexed it in `docs/blog/README.md`.
- Targeted test passed: `pytest tests/test_agent_cli.py -k 'auth_prevent_dropped_oauth_codes_in_mani' -v`.
[@claude]
