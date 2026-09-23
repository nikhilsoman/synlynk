# Vizor Cross-Workspace Daemon

**Status:** Approved
**Date:** 2026-09-23
**Scope:** Prerequisite sub-project for the broader Vizor UX/IA overhaul (see "Related work"). Replaces Vizor's per-repo, CWD-scoped server with a single persistent, OS-supervised background daemon serving every registered workspace.

## Background

Vizor today (`synlynk/viz.py`) is single-workspace-per-process: `generate_viz_data()` builds `data["workspace"]` from `_workspace_name()`, which reads `.synlynk/config.json` relative to `os.getcwd()`. Every `synlynk viz` invocation only ever knows about the one repo it was launched from. The sidenav's "Workspaces" section is static mockup HTML, not data-driven — there is no existing mechanism for one running Vizor process to enumerate or serve any workspace other than its own.

This surfaced while investigating the approved nav/IA restructure spec (`2026-09-22-vizor-nav-ia-restructure-design.md`), whose Tier-2 workspace accordion assumes clicking into a different workspace navigates you there — an assumption with no supporting server architecture today.

Rather than build a badge-only compromise for that one feature, the decision was made to fix the underlying architecture: Vizor is meant to be a durable, persistent dashboard — a comprehensive view across a developer's workspaces, replacing IDE/CLI-centric workflows — not a single-repo tool tied to whatever directory it happened to be launched from. This is also a direct prerequisite for hosted Team/Enterprise Vizor, which will need the same cross-workspace serving model.

`~/.synlynk/registry.json` (`synlynk/state_registry.py`) already provides full cross-workspace enumeration (`product_id`, `slug`, `canonical_path`, `mode`, `state` per registered product) — no new registry is needed. `open_state_db(mode="backup", read_only=True, explicit_path=...)` already provides a sanctioned way for one process to safely read a different workspace's `state.db` without triggering the canonical-identity check `mode="canonical"` enforces. Both are reused as-is.

The existing `synlynk watch` daemon (`synlynk/daemon.py`, `WatchDaemon`/`SynlynkDaemon`) is also repo-scoped — its pidfile/state paths resolve via `git rev-parse --git-common-dir`, anchored to whichever repo launched it. Extending it would mean untangling shared per-repo watch infrastructure from a machine-level service, so this daemon is built as a separate, standalone process instead.

## Goals

- One persistent background process serves every registered workspace's Vizor views, not one process per repo.
- The daemon survives reboots and starts without the user remembering to launch anything — installed via the OS's own service manager.
- Existing view-rendering code (`generate_*_html()` functions in `viz.py`) is reused as-is, parameterized by workspace instead of implicit CWD.
- `synlynk viz` becomes a thin "open the browser" convenience once the daemon exists.
- New workspaces registered after the daemon starts are picked up automatically, no restart required.

## Non-goals

- Team/Enterprise account-scope functionality itself — this spec only makes the serving architecture capable of supporting it later.
- Any change to `state.db` schema, the registry format, or `open_state_db()` — all reused unmodified.
- The nav/IA restructure's UI work (accordion, breadcrumbs, overview canvas) — that spec resumes once this daemon's routing exists, but its content is out of scope here.
- Extending or modifying `synlynk/daemon.py`'s `WatchDaemon` — this daemon is intentionally separate (see Background).
- Windows service-manager support — macOS (launchd) and Linux (systemd `--user`) only, matching today's supported dev environments.

## Approach

Three shapes were considered for how the daemon executes per-workspace refresh work:

1. **In-process daemon (chosen).** One long-lived process imports `synlynk.viz`'s `generate_viz_data()`/`generate_*_html()` functions directly and calls them per workspace each poll cycle, with a per-workspace `try/except` for isolation. Minimal moving parts, reuses nearly all existing `viz.py` code unmodified.
2. **Subprocess-per-workspace.** The daemon shells out to a `synlynk viz --render-only --workspace <slug>` subprocess per workspace per cycle. Gains process-level crash isolation, but adds subprocess spawn overhead scaling with workspace count × poll interval, and requires a new CLI render-only mode that doesn't exist today.
3. **Hybrid.** In-process by default, escalating a repeatedly-failing workspace to subprocess isolation (circuit breaker). More resilient, more complexity — deferred until in-process actually proves fragile in practice.

Approach 1 was selected: it is the direct extension of the daemon's already-scoped design, keeps one simple code path, and per-workspace `try/except` inside the poll loop provides adequate isolation without the cost of process boundaries.

## Design

### 1. Process & lifecycle

- New module `synlynk/vizor_daemon.py` — standalone, does not extend `synlynk/daemon.py`'s `WatchDaemon`/`SynlynkDaemon`.
- Machine-level home: `~/.synlynk/vizor-daemon/` containing `pidfile`, `port`, `daemon.log` — not repo-anchored, unlike other state paths in this codebase today.
- **OS service registration:**
  - macOS: a launchd `LaunchAgent` plist written to `~/Library/LaunchAgents/com.synlynk.vizor-daemon.plist`, loaded via `launchctl load`.
  - Linux: a systemd `--user` unit written to `~/.config/systemd/user/synlynk-vizor-daemon.service`, enabled via `systemctl --user enable --now`.
  - Both configured to restart on crash and start at login — the OS supervises the process; synlynk does not reimplement a watchdog.
- **Install triggers:**
  - New `synlynk viz install` command — writes and loads/enables the service unit, starts the daemon immediately.
  - `./install.sh` (fresh installs) calls `synlynk viz install` automatically as part of setup.
  - `synlynk upgrade` (existing installs) calls the same install step if not already registered — idempotent, one-time per machine.
  - `synlynk viz uninstall` — unloads/disables the unit and stops the process, for users who want it off.
  - `synlynk viz status` — reports whether the service is registered/running, its port, and pidfile state.

### 2. Refresh loop

- Fixed polling interval, default 15 seconds, overridable via `SYNLYNK_VIZOR_POLL_INTERVAL`.
- Each cycle:
  1. Read `~/.synlynk/registry.json` via `state_registry.registry_path()` / the registry's existing read helpers.
  2. For each registered product, in its own `try/except` block (a failure here logs and continues — it must never halt the loop or affect other workspaces):
     - Resolve `canonical_path` for the slug.
     - `open_state_db(mode="backup", read_only=True, explicit_path=<that workspace's state.db>)`.
     - Call the existing `generate_viz_data()` and `generate_*_html()` functions, passing the resolved workspace path/slug instead of relying on implicit CWD (these functions' CWD-relative reads — e.g. `_workspace_name()`, `_load_action_history()` — become parameterized by the workspace path being processed).
     - Write output to `~/.synlynk/vizor-cache/<slug>/*.html`, replacing today's flat `.synlynk/viz-cache/` per-repo cache.
- A workspace registered after the daemon starts is picked up on its next natural poll cycle — no daemon restart required.

### 3. HTTP serving & URL scheme

- One port, default 8721 (`DEFAULT_PORT`, unchanged from today).
- Path-prefixed routing: `/w/<slug>/overview.html`, `/w/<slug>/board.html`, `/w/<slug>/gantt.html`, etc. `VizorHandler.do_GET` gains routing logic mapping `/w/<slug>/...` requests to `~/.synlynk/vizor-cache/<slug>/...` on disk (today's handler serves one flat directory as a `SimpleHTTPRequestHandler`; this is new routing logic, not just new cache entries).
- An unregistered/unknown slug in the URL path returns 404.
- `/` with no path redirects to `/w/<current-repo-slug>/overview.html` when the request can be associated with a recognizable workspace context (best-effort), otherwise to the Personal-tier Activity Stream root (introduced by the nav/IA spec once that resumes).
- `/onboarding`, `/onboarding/roles`, `/auth/callback` keep their existing top-level (non-workspace-scoped) routes.

### 4. OAuth callback workspace-carry

`/auth/callback` today has no way to know which workspace initiated the OAuth flow, since it assumed a single-workspace process. Fix: the initiating slug is encoded into the OAuth `state` parameter when a flow starts from `/w/<slug>/...`; `/auth/callback` decodes it on completion and redirects back to that workspace's page instead of an implicit single-workspace assumption.

### 5. CLI semantics

- `synlynk viz` — opens the OS browser to `http://localhost:<port>/w/<current-repo-slug>/overview.html`. No spawn logic, no foreground server. If the daemon isn't reachable (not installed, or crashed and not yet restarted by the OS), it prints a one-line message pointing at `synlynk viz install` / `synlynk doctor` rather than falling back to a temporary single-workspace server.
- `synlynk viz install` / `synlynk viz uninstall` / `synlynk viz status` — new lifecycle commands (section 1).
- The old single-workspace spawn-and-cache-write code path in `synlynk viz`'s current entry point is retired, not kept alongside as a second implementation.

### 6. Testing

- Extend `tests/test_viz.py` conventions: unit-test the poll loop against a fixture `registry.json` and temp `state.db` files (mocking `open_state_db` per existing test patterns) — assert per-slug cache files are written, and that one workspace raising an exception doesn't prevent others in the same cycle from refreshing.
- URL-routing tests: `/w/<slug>/...` maps to the correct cache directory; an unregistered slug returns 404.
- Existing `generate_*_html()` pure-function tests are unaffected — same function signatures and return values, just invoked with an explicit workspace path/slug argument instead of relying on `os.getcwd()`.
- Lifecycle command tests (`synlynk viz install/uninstall/status`) run against a temp `HOME` so they don't touch the real developer's launchd/systemd state.

## Related work

- Tracked under `goal-70317121`, the existing long-lived GOVERNS goal covering the full Vizor UX/IA overhaul — this daemon is a new sub-project under that same goal, not a new goal.
- Prerequisite for `2026-09-22-vizor-nav-ia-restructure-design.md`: that spec's Tier-2 workspace accordion routes to `/w/<slug>/overview.html` on this daemon once both land. The nav/IA spec's own implementation-planning work resumes after this daemon's spec/plan/build cycle completes.
- Direct architectural prerequisite for hosted Team/Enterprise Vizor (per `vizor-strategic-position` memory: Vizor is the only web HUD, local-first now, syncing to synlynk.com Team/Enterprise later via NATS) — this daemon's per-workspace serving model is the same shape that hosted mode will need, built correctly once rather than as a throwaway single-workspace stopgap.
