# synlynk Memory

## Project Overview
- **Name:** synlynk
- **Description:** <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80"> </p>
- **Languages:** Python
- **Directories:** agents, bin, docs, examples, project-docs, scripts, synlynk, synlynk.egg-info, test_archive, test_context_output, tests, website, worktrees

- **Vizor Multi-Workspace Hub & Clean Entrypoint Routing (#1758):** Root index `http://localhost:8721/` now renders a responsive Synlynk design system multi-workspace dashboard with status badges, view chips, and real-time JavaScript search filtering. Paths `/w/<slug>/overview.html` and root slug routes cleanly alias to `/<slug>/index.html`. [@agy, @nikhilsoman]
- **Vizor Daemon Shared HEAD Routing (#1760):** `WorkspaceRoutingHandler` routes `GET` and `HEAD` requests through a unified `_route_path()` handler, ensuring automated health checkers, proxies, and curl `-I` receive valid `200 OK` responses. [@agy, @nikhilsoman]
- **Unconfigured Workspace DB_PATH Fallback Guard (#1759):** `_resolve_db_path()` in `synlynk/__init__.py` falls back to `str(state_db_path(slug))` when imported outside an initialized synlynk project, preventing `StateRegistryError` during launchd service startups from non-repo directories. [@agy, @nikhilsoman]
- **Vizor Daemon Concurrency Mutex Lock (#1750):** `workspace_render_context()` in `synlynk/vizor_daemon.py` is protected by `_RENDER_LOCK = threading.Lock()` around the `os.chdir` and global `VIZ_CACHE_DIR`/`_get_db` monkeypatching window, preventing data races across concurrent polling threads. [@agy, @nikhilsoman]
- **Sandboxed Worktree State Migration Resilience (#1733):** `migrate_state_db_if_needed`, `ensure_product_dirs`, and `synlynk/__init__._resolve_db_path` catch `PermissionError` and `OSError` defensively, ensuring CLI commands (such as `synlynk watch status`) can safely run in restricted or read-only sandboxes without crashing during module import. [@agy, @nikhilsoman]
- **Concurrent SQLite Schema Migration Safety:** Wrapped `ALTER TABLE stories ADD COLUMN` in `synlynk/db.py` in `try...except sqlite3.OperationalError: pass` to eliminate race conditions when multi-threaded processes concurrently initialize schema on fresh databases. [@agy, @nikhilsoman]
- **Codex Dispatch Model Auto-Probing (#1748):** When dispatching to Codex without an explicit `--model` override, `synlynk/dispatch.py` and `synlynk/models.py` auto-probe `~/.codex/config.toml` for the local configured model (`gpt-5.6-luna`), ensuring ChatGPT-account setups work seamlessly. [@agy, @nikhilsoman]
- **Git Worktree Product Identity Slug Resolution (#1742):** `identity_slug_from_config()` in `synlynk/product_store.py` invokes `git rev-parse --path-format=absolute --git-common-dir` and evaluates relative paths defensively against `repo`, preventing git worktrees from creating isolated stray product entries in `registry.json`. [@agy, @nikhilsoman]
- **Registry Self-Healing Repo Path (#1743):** `ensure_registered_product()` in `synlynk/state_registry.py` self-heals and persists `repo_path` on existing entries so the cross-workspace Vizor background daemon has valid repo paths for all registered workspaces. [@agy, @nikhilsoman]
- **Vizor Daemon Liveness and Exit Code Inspection (#1749):** `install()` and `uninstall()` in `synlynk/vizor_daemon.py` check `subprocess.run().returncode` and `stderr` to fail closed with structured diagnostics on launchd/systemctl errors. [@agy, @nikhilsoman]

## Architecture
- All harnesses maintain strict tripartite separation between Role (`--role`), Execution Sandbox Backend (`--harness`), and Model Tiering (`--model-tier`).
- Canonical product databases in `~/.synlynk/workspaces/<slug>/state.db` are the single source of truth across all worktrees.
