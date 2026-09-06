# Workspace agent identity routing — design

**Date:** 2026-09-06
**Status:** Draft (needs Nikhil sign-off; no implementation until approved)
**Issue:** #1436
**Author:** Grok (assessment). No code in this PR.

## 1. What this ticket asked

1. All dispatches (and PM/TPM GitHub writes) go through pm/tpm (or the role that owns the action) App handles.
2. qa can approve without the shared human identity.
3. `nikhilsoman` is for Nikhil only — never autonomous platform operation.
4. Review roles and charters against Apps and `policy.json`.

No implementation until this spec is signed off (Brainstorm-First).

## 2. Live evidence (2026-09-06 session)

These are GitHub facts, not `synlynk jobs` board labels.

| Event | Author | Actor | Result |
|---|---|---|---|
| PR #1447, #1449, #1450 `gh pr create` | `nikhilsoman` | Interactive Grok session host `gh` | PRs opened as the human |
| QA `gh pr review --approve` on those PRs | `synlynk-synlynk-qa[bot]` | `synlynk dispatch --role qa --requires-gh-write` | **APPROVE succeeded** |
| Squash-merge of those PRs | mergedBy `app/synlynk-synlynk-qa` | same qa dispatch | **merge succeeded without `--admin`** when CLEAN |
| `gh run rerun --failed` from qa job | qa App | `job-de005f86` | **failed**: `Resource not accessible by integration` (`actions:read` only) |
| `gh issue close 1435` | `nikhilsoman` | Interactive Grok session host `gh` | housekeeping close as the human |

`gh auth status` with the cached qa installation token: logged in as `synlynk-synlynk-qa[bot]` (`GH_TOKEN`). Host shell remains `nikhilsoman`.

**#423 is stale for App-vs-human.** GitHub’s self-approve block did **not** fire when `synlynk-synlynk-qa[bot]` approved a PR authored by `nikhilsoman`. The comment-checklist fallback is still required only when the reviewer and the author are the same GitHub identity (two dispatches both falling through to `nikhilsoman`, or a bot approving its own bot-authored PR).

**Not tested:** qa `--approve` on a PR whose author is `synlynk-synlynk-pm[bot]` or `synlynk-synlynk-dev[bot]`. That is the remaining empirical cell.

## 3. Dispatch routing audit

| Path | Who runs `gh` | Token | Identity today |
|---|---|---|---|
| `synlynk dispatch --requires-gh-write --role qa` child | Codex/Claude/Agy in the job worktree | Role App installation token in `GH_TOKEN` + isolated `GH_CONFIG_DIR` (`dispatch.py` `_build_subprocess_env`) | Role bot (`synlynk-synlynk-qa[bot]`, etc.) |
| Same, token missing | refused unless `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH` | fail-closed (#569) | n/a |
| `synlynk dispatch` **parent** auto-finalize (`jobs.py` `_maybe_open_worktree_pr`) | Parent Python process after the child exits | **Host `gh` keyring** — not the child’s `GH_TOKEN` | `nikhilsoman` (source of auto-PR noise #1443/#1445/#1448 and of Grok/Claude-opened PRs if they go through this path) |
| Interactive harness session (`gh pr create`, `gh issue close`, `gh run rerun`) | The session shell | Host `gh auth` | `nikhilsoman` |
| `synlynk pr check` / `gh pr checks` | Session or child | whichever env that process has | lookup only |

`_resolve_dispatch_gh_token` / `_resolve_dispatch_gh_bot_login` only apply to the **dispatched child**. They do not wrap the parent finalize path or interactive PM/Grok/Claude shells.

## 4. App manifests vs installed capability

`synlynk/team.py` `_build_app_manifest_url` default permissions:

- All roles: `metadata:read`, `contents:write`, `issues:write`, `pull_requests:write`
- `merge_authority.can_merge` roles (policy: `qa` only): `administration:write`

No `actions` permission. That matches the live qa rerun failure. Manifest `administration:write` is create-time; re-approval after a manifest change was not re-verified via JWT this session (ticket item 3). It was also **unnecessary** for the CLEAN squash-merges above.

`.synlynk/github_apps/` has provisioned Apps + cached tokens for: `pm`, `qa`, `dev`, `architect`, `tpm`, `designer`, `marketing`, `synlynk-bot`.

## 5. Charter vs policy vs live

Source: `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`, `.synlynk/policy.json`, `.synlynk/roles.yaml`.

| Role | Charter (condensed) | `policy.json` | Live GH write |
|---|---|---|---|
| **pm** | Represents the human; Named Releases; durable triage. Does not silently commit the human. | `pm` / `brainstorm` → Claude | No pm-bot PRs this session; interactive `gh` is `nikhilsoman` |
| **tpm** | Turns plans into dispatched tickets; no technical approach | not in `can_merge` / `can_cut_release` | App exists; unused for writes here |
| **architect** | Spec/plan; charter patched to qa-only merge in this PR | `can_merge` is **qa only** | Charter text patched to match policy in this PR (#1436 leftover) |
| **dev** | Implementation | implement/test → Codex/Grok/Agy | Should author PRs as `synlynk-synlynk-dev[bot]` if auto-PR used the child token; today auto-PR/parent `gh` is `nikhilsoman` |
| **qa** | Tests, CI/CD, merge | `can_merge: ["qa"]`; review → Codex | Approve + squash-merge as qa bot: **proven**. Actions rerun: **not granted** |
| **designer** | UI/UX | css/templates → Agy | App unused here |
| **marketing** | Blog/docs/site | content → Agy | Blog posts in this arc were written by Grok in the authoring session (`nikhilsoman`) |
| **synlynk-bot** | Not a role; catch-all automation identity | token fallback in `_resolve_dispatch_gh_token` | Fallback if a role App is missing |

`policy.json` `review_fallback: comment_checklist` encodes #423. After §2, that fallback should be **conditional** (same GitHub login as author), not the default for qa App reviews.

## 6. Target end-state

1. **Autonomous GitHub writes never use `nikhilsoman`.** That login is reserved for Nikhil at the keyboard.
2. **Child dispatch already does (1)** for `--requires-gh-write` when the App token cache is fresh.
3. **Close the two remaining shared-identity holes:**
   - Parent `jobs.py` `_maybe_open_worktree_pr` / `git push` must use the job’s role App token (same injection as the child), not host `gh`.
   - Interactive PM/TPM/implement sessions that open or merge PRs must go through `synlynk exec` / a role-token wrapper (`--role pm|tpm|dev|qa`), not raw host `gh`.
4. **qa `--approve` is the default** when the reviewer login ≠ PR author login. Keep the comment-checklist only for same-identity collisions.
5. **qa Actions rerun** is a separate, optional grant (`actions: write`) if flake retrigger is in qa’s charter. Not required to merge CLEAN PRs.
6. **Architect merge-authority sentence** in the 2026-08-09 charter should be amended to match `can_merge: ["qa"]`, or policy should change — do not leave them disagreeing.
7. Remaining live test: open one PR as `synlynk-synlynk-dev[bot]` (or pm) and have qa `--approve` it.

## 7. Follow-up implementation (not this PR)

Do not start these until Nikhil signs this spec.

- **Hole A — parent auto-PR identity:** `jobs.py` finalize uses role `GH_TOKEN`. Closes nikhilsoman auto-PRs from merge/review jobs.
- **Hole B — interactive `gh`:** a `synlynk gh --role <role> -- …` (or `synlynk exec` env) so Grok/Claude sessions cannot `gh pr create` as the human by default.
- **Policy — review fallback:** `comment_checklist` only when author login equals reviewer login.
- **Charter patch:** architect merge sentence vs `can_merge` — **addressed in this PR (#1436 leftover)**: living charters aligned to qa-only merge.
- **Optional:** qa `actions: write` for `gh run rerun`.
- **Live cell:** one PR authored by a role bot, approved by qa bot.

## 8. What this PR does not do

No code. No policy.json change. No App re-provision. Sign-off is the gate.
