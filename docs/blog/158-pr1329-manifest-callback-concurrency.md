---
title: "Issue #906 — The GitHub App Manifest Callback Server Could Drop a Code"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 158
pr: "#1329"
merged: status open
---

## The Broader Goal at the End of the Previous PR

Role provisioning (`synlynk team join` / role bootstrap) walks an operator
through GitHub's App Manifest flow: open a pre-filled form, submit it,
GitHub redirects to a loopback server on `127.0.0.1` with a one-time code,
and synlynk exchanges that code for App credentials. That loopback server
needs to be correct exactly once per operator per role — a dropped code
means re-running the whole manifest flow by hand.

## What This PR Shipped

`synlynk/team.py::_run_manifest_callback_server` used a `threading.Event`
plus a plain list to capture the single expected OAuth code:

```python
if code and not code_ready.is_set():
    captured.append(code)
    code_ready.set()
```

If a second `/callback` request arrived — a duplicated browser tab, GitHub
retrying the redirect, a re-submitted manifest form — before
`wait_for_code()` drained the first one, its code was silently discarded by
construction: the guard only ever keeps the first code, and the
check-then-set itself isn't atomic across request threads.

The fix swaps the `Event`/list pair for a `queue.Queue()` — every valid code
is unconditionally `put()`, so puts never drop data no matter how many
requests land before the queue is drained — and swaps the plain
`http.server.HTTPServer` for `ThreadingHTTPServer`, so concurrent callback
requests get their own handler thread instead of serializing behind one
accept loop. `wait_for_code()` becomes a `queue.get(timeout=...)`, keeping
the external contract (`port, wait_for_code, shutdown`) unchanged.

Added `tests/test_agent_cli.py::test_manifest_auth_prevent_dropped_oauth_codes_in_manifest_callback_server`,
which fires two concurrent `/callback` requests with distinct codes from two
threads (synchronized with a `threading.Barrier`) against the real loopback
server, and asserts both get a 200 response and both codes are retrievable
via two successive `wait_for_code()` calls.

Design spec: `docs/superpowers/specs/2026-09-02-manifest-callback-concurrency-design.md`.
Plan: `docs/superpowers/plans/2026-09-02-manifest-callback-concurrency.md`.

## What This Achieved on the Path to Autonomy

Role provisioning is a one-shot, human-in-the-loop flow that every new
teammate or role goes through exactly once — a silent drop there is
maximally confusing because there is no earlier signal that anything went
wrong. Removing the drop makes that onboarding step reliable under the kind
of double-click/double-tab behavior real operators actually exhibit.

## Strategic Note: The Goal at the End of This PR

Loopback callback servers used anywhere else in synlynk's auth flows should
default to a queue-backed capture + `ThreadingHTTPServer`, not
Event/list-based single-shot capture, as the standard pattern.
