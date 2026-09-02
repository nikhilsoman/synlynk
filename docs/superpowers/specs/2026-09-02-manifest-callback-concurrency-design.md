# Design: manifest callback loopback server concurrency (#906)

## Problem

`synlynk/team.py::_run_manifest_callback_server` starts a loopback HTTP
server that GitHub redirects to after a user completes the App Manifest
creation flow (`/callback?code=...`). The old implementation gated the
captured code behind a single `threading.Event`:

```python
code_ready = threading.Event()
captured = []
...
if code and not code_ready.is_set():
    captured.append(code)
    code_ready.set()
```

Two problems:

1. **Dropped second code.** If a second `/callback` request arrives (a
   duplicated browser tab, GitHub retrying the redirect, or the user
   re-submitting the manifest form) before `wait_for_code()` is ever called
   to clear the event, its code is silently discarded — the `is_set()`
   check-then-append is not atomic, and even when it is, the design only
   ever keeps one code by construction.
2. **Serialized handling.** `_run_manifest_callback_server` used a plain
   `http.server.HTTPServer`, which processes one request at a time from a
   single `serve_forever` loop. A second concurrent connection is not
   rejected, but it queues behind the first at the socket level rather than
   being handled independently.

## Fix

- Replace the `Event` + list pair with a `queue.Queue()`. Every valid code
  received by `do_GET` is unconditionally `put()` onto the queue — puts
  never drop data regardless of how many requests arrive before the queue is
  drained.
- Replace `HTTPServer` with `http.server.ThreadingHTTPServer` so concurrent
  callback requests are dispatched to independent handler threads instead of
  being serialized behind one accept loop.
- `wait_for_code()` becomes `queue.get(timeout=...)`, preserving the existing
  external contract (returns a code string, or `None` on timeout).

This is a minimal, behavior-preserving fix: the manifest flow only ever
consumes the first code in practice (`wait_for_code()` is called once), but
the second/Nth code — if one arrives — is now queued rather than lost, and
concurrent requests no longer contend on shared mutable state without a lock.

## Non-goals

- No change to `_extract_manifest_code`, `_exchange_manifest_code`, or the
  manifest form HTML generation.
- No change to the external return signature of
  `_run_manifest_callback_server` (`port, wait_for_code, shutdown`).
- Does not attempt to correlate which of N concurrent codes is "the real
  one" — GitHub's manifest flow issues one code per completed flow, so this
  is a robustness fix against duplicate/retried requests, not a
  multi-tenant callback router.

## Testing

Added `tests/test_agent_cli.py::test_manifest_auth_prevent_dropped_oauth_codes_in_manifest_callback_server`:
starts the real loopback server, fires two concurrent GET requests with
distinct codes from two threads via a `threading.Barrier`, and asserts both
requests get a 200 response and both codes are retrievable via two
successive `wait_for_code()` calls (order-independent, since either could
land first depending on thread scheduling).
