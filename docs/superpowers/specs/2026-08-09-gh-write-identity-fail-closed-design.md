# GH-write identity: fail-closed + host-auth isolation (Epic B0/B1)

**Date:** 2026-08-09  
**Status:** Implementing  
**Parent plan:** `docs/superpowers/plans/2026-08-09-job-truth-and-gh-write-epics.md` (Epic B)  
**Issues:** #569 (primary), #426, #517 (partial), #423 (context)  
**Prior design:** `2026-07-23-agent-github-identity-design.md` (App-per-role minting — kept)

## Problem

When `--requires-gh-write` is set and no role-scoped GitHub App token is available, dispatch **strips** `GH_TOKEN`/`GITHUB_TOKEN` and **warns** that writes "will fail." In practice `gh` still authenticates via the OS keyring / `~/.config/gh` using `HOME` (still allowlisted). Writes succeed under the shared personal identity — the #423 failure mode. See #569.

## Decision (B0/B1)

| Case | Behavior |
|------|----------|
| `--requires-gh-write` + mintable role App token | Inject `GH_TOKEN` (+ `GITHUB_TOKEN` mirror). Set `GH_CONFIG_DIR` to an isolated empty config dir so `gh` does not use the host keyring session. |
| `--requires-gh-write` + no token | **Hard-fail** dispatch before spawn (`RuntimeError`). Message points to `synlynk identity init --role <role>`. |
| Escape hatch | `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1` (or `true`/`yes`) allows proceed without App token, with a loud warning that host `gh` identity will be used. Default **off**. |
| No `--requires-gh-write` | Unchanged: no GH_TOKEN inject; allowlisted env only (no GH_TOKEN in base allowlist). |

## Non-goals (this PR)

- Completing full App Manifest provisioning UX (already partially shipped; operator still runs `identity init --role`).
- Codex sandbox network allowlist (#577) — separate.
- MCP review cancel flakes (#659/#714) — after identity is trustworthy.
- Changing capability routing table (still prefer Grok/Agy for GH-write by policy).

## Acceptance

- [ ] Dispatch with `--requires-gh-write` and no App JSON → raises; no agent process started.
- [ ] With fake/minted token → env has `GH_TOKEN` and `GH_CONFIG_DIR` under `~/.synlynk/gh-config/`.
- [ ] Escape hatch documented and tested.
- [ ] Existing inject/fallback token resolution tests still pass; strip-and-proceed test replaced by fail-closed.

## Follow-on (B2/B3)

- Codex: permanent no-GH-write route or sandbox fix.  
- MCP review reliability once bots are real actors on GitHub.
