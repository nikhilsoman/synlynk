---
title: "PR TBD — Local HTTP Auth for the Daemon and Vizor"
date: 2026-09-04
series: "Building the OS for Multi-Agent Development"
post: 174
pr: "TBD"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

The previous post closed a presentation gap on the book: brand skin without brand skeleton. The longer-arc goalpost around that work was still operational reliability — sandboxing, credential masking, and making local agent surfaces safe enough to leave running. The daemon HTTP server on `127.0.0.1:27471` and Vizor on `127.0.0.1:8721` were still the unauthenticated local APIs they had been since v0.9.3 / BS-21: fine while "localhost means me," not fine once any other process or browser tab on the same machine can `POST /dispatch`.

PR #1417 (gh:#349) then landed the daemon's exclusive start-lock and orphan-reap path, taking series slot 173. This post is the HTTP-auth half of that same daemon-hardening pair.

## Strategic Shifts in This PR

gh:#355 made the CSRF path concrete. Binding to loopback stops the remote internet; it does not stop a sibling browser tab. CORS `Access-Control-Allow-Origin: *` on Vizor made the write even worse: a malicious page could both fire a billed dispatch and *read* the response. Cookies would have been the wrong fix — browsers auto-attach them on cross-site form POSTs, which is exactly the CSRF gadget. The shift is: treat these servers as a local dashboard, not a public API. Shared-secret header plus same-origin checks; no cookie.

This PR does **not** attempt gh:#348's log-redaction gap. Job-detail still returns the last 100 lines of raw stdout/stderr; auth now means that leak is limited to holders of `~/.synlynk/daemon.token`, not to every local HTTP client. Redaction remains a separate fix.

A parallel task (gh:#349) also touches `synlynk/daemon.py`'s HTTP handler for lifecycle reasons. Auth changes here are confined to an authorize-and-return guard at the top of `do_GET`/`do_POST` plus token creation at `_run_loop` start, so the two diffs should merge without fighting over job-queue or dispatch-body logic.

## What This PR Shipped

- New `synlynk/local_http_auth.py`. Token file is `~/.synlynk/daemon.token`, created on first daemon or Vizor start, mode `0600`, same permission pattern as `.synlynk/github_apps/<role>.token.json`. Clients send `X-Synlynk-Token` (never a cookie). `secrets.compare_digest` for the comparison.
- Same-origin/Referer defense in depth: if `Origin` or `Referer` is present, the host must be `localhost` / `127.0.0.1` / `::1`. CLI callers with neither header still work as long as the token is correct. Cross-site `fetch()` or form POST from `https://evil.example` is 403 even with a stolen-looking header.
- Daemon: every GET and POST (`/dispatch`, `/checkpoint`, `/jobs`, `/jobs/<id>` including `log_tail`, `/stories`, `/capability`, `/sentinel`, `/context`, `/status`) requires the token. Missing or wrong token is 401 and does not enqueue a job.
- Vizor: every write route (`/dispatch`, `/note`, `/approve`, `/kill`, `/architect-map/view-pref`) requires the token. Wildcard CORS is gone — no `Access-Control-Allow-Origin` at all, same-origin default. Inline dashboard JS now uses relative URLs (`fetch('/dispatch', …)`) and `window.vizorAuthHeaders()`, with the token injected into generated HTML so the legitimate page can send the custom header. Static HTML GET stays ungated so the dashboard can load; the token in the page is unreadable cross-origin without CORS.
- Tests cover missing token, wrong token, foreign Origin, `0600` file mode, Vizor write routes, and the existing daemon-HTTP / Vizor suites updated so they authenticate by default.

Follow-up not in this PR: Host-header / DNS-rebinding checks. Loopback bind already limits remote reachability; Host validation would be extra depth, not the live exploit path.

## Brainstorm Visuals Used

None — this was a security fix against a filed issue, not a design-phase visual.

## What This Achieved on the Path to Autonomy

An always-on daemon that can enqueue billed work from HTTP is only safe to leave running if "any tab on this machine" is not an implicit operator. Header-based local auth is the minimum bar for the sandboxing goal: credential-shaped secrets stay in a user-owned `0600` file, and CSRF from a random webpage can no longer spend the budget.

## Strategic Note: The Goal at the End of This PR

Local HTTP is authenticated. The next goalpost on this surface is gh:#348 (redact secrets out of job log tails) and, if we ever bind beyond loopback or add a Host check, treating DNS rebinding as a real control rather than a note. gh:#349's daemon lifecycle work should land beside this, not through it.
