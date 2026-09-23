# synlynk Memory

## Project Overview
- **Name:** synlynk
- **Description:** <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80"> </p>
- **Languages:** Python
- **Directories:** agents, bin, docs, examples, project-docs, scripts, synlynk, synlynk.egg-info, test_archive, test_context_output, tests, website, worktrees

## Decisions
- **Codex Dispatch Model Auto-Probing (#1748):** When dispatching to Codex without an explicit `--model` override, `synlynk/dispatch.py` and `synlynk/models.py` auto-probe `~/.codex/config.toml` for the local configured model (`gpt-5.6-luna`), ensuring ChatGPT-account setups work seamlessly. [@agy, @nikhilsoman]
- **Git Worktree Product Identity Slug Resolution (#1742):** `identity_slug_from_config()` in `synlynk/product_store.py` invokes `git rev-parse --path-format=absolute --git-common-dir` and evaluates relative paths defensively against `repo`, preventing git worktrees from creating isolated stray product entries in `registry.json`. [@agy, @nikhilsoman]
- **Registry Self-Healing Repo Path (#1743):** `ensure_registered_product()` in `synlynk/state_registry.py` self-heals and persists `repo_path` on existing entries so the cross-workspace Vizor background daemon has valid repo paths for all registered workspaces. [@agy, @nikhilsoman]
- **Vizor Daemon Liveness and Exit Code Inspection (#1749):** `install()` and `uninstall()` in `synlynk/vizor_daemon.py` check `subprocess.run().returncode` and `stderr` to fail closed with structured diagnostics on launchd/systemctl errors. [@agy, @nikhilsoman]

## Architecture
- All harnesses maintain strict tripartite separation between Role (`--role`), Execution Sandbox Backend (`--harness`), and Model Tiering (`--model-tier`).
- Canonical product databases in `~/.synlynk/workspaces/<slug>/state.db` are the single source of truth across all worktrees.
