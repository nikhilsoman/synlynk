# RCA: [LIVE-16] Vizor launchd daemon crash-loop

**Date:** 2026-09-26  
**Severity:** Sev1  
**Issue:** #1794

## Timeline

- 2026-09-25 15:00 — `com.synlynk.vizor-daemon.plist` written with Homebrew `python3.14 -m synlynk.vizor_daemon`, no PYTHONPATH.
- Editable pip install pointed at deleted worktree `~/dev/feat+kg-ux-improvements`.
- Launchd KeepAlive respawned on exit 1 with no throttle (3700+ runs).
- Session workaround: `PYTHONPATH=/Users/nikhilsoman/dev/synlynk python3 -m synlynk.vizor_daemon` served port 8721.
- 2026-09-26 — Operator observed empty Agent Roles; assumed it was the crash. Sentinel never fired.

## Root causes

1. **Import crash-loop.** Launchd cwd is `/`. `python -m synlynk.vizor_daemon` requires `synlynk` on sys.path. Plist had no PYTHONPATH. Editable install mapped the package to a **deleted** worktree, so import failed from `/` and `$HOME`.
2. **KeepAlive without ThrottleInterval** turned a one-line import failure into a tight respawn loop.
3. **Empty Agent Roles is independent.** `_load_workspace_agents()` reads `agent_store` `registry.json` under `~/.synlynk/workspaces/<workspace_id>/agents/`. That file is missing. Charter stubs live in repo `.synlynk/agents/*.yaml`. The HUD that showed 0 roles was the session daemon, not launchd.
4. **Token refresh is not in vizor_daemon.** `synlynk watch` (`daemon.py`) refreshes GitHub App tokens. Vizor daemon only renders HTML. Watch had DNS errors for role `tpm`.
5. **Sentinel only scans exec/dispatch stdout.** It does not watch launchd last-exit or `~/.synlynk/vizor-daemon/daemon.log`.

## Impact

Designed OS-supervised HUD was down. A session process masked the outage. Agent dispatch via GitHub Apps could still work. Token refresh depended on watch, not Vizor.

## Fix

- Plist/systemd: PYTHONPATH = live package root, WorkingDirectory = daemon home, ThrottleInterval/RestartSec = 30.
- `probe_health()` writes CRITICAL `VIZOR_DAEMON_CRASHLOOP` / `VIZOR_DAEMON_DOWN`; watch token-refresh tick calls it.

## Prevention

- Do not `pip install -e` from a disposable worktree.
- Doctor/watch must treat a registered-but-dead Vizor service as Sev1.
- Follow-up: project Agent Roles from charter yaml/registry so the HUD matches provisioned GitHub App roles.
