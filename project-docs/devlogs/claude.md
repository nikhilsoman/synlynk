# Claude Devlog

## 2026-09-23 — [LIVE-14] Token-Path Drift Fix, Merge-Authority Chicken-and-Egg Finding, PR #1744 Audit, 3 New Tickets

- **[LIVE-14] (#1746, Sev2) resolved end-to-end:** `WatchDaemon._refresh_github_tokens` and two
  `viz.py` OAuth/App-conversion refresh call sites hardcoded a repo-local token cache path instead
  of resolving via `product_store.resolve_github_apps_dir()` — the same resolver `dispatch.py`/
  `synlynk gh` use to *read* tokens. Once a role's token existed in the global workspace dir
  (`~/.synlynk/workspaces/<slug>/github_apps/`), neither refresher ever wrote to it again, so it
  went silently stale (~22.5h observed) while the repo-local copy kept refreshing and the daemon
  reported healthy. Fixed by Codex (`job-2cd5f44c`, commit `6d9db779`), regression test added,
  full suite 3186/3187 (1 pre-existing unrelated flaky). PR #1747.
- **Chicken-and-egg dispatch-review finding (live, not hypothetical):** PR #1747 — which fixes
  stale role-scoped GitHub App tokens — could not itself be reviewed via role-scoped dispatch,
  because the `qa` role had no resolvable token (the exact bug class the PR fixes). The
  `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1` fallback was then correctly blocked by Claude Code's own
  auto-mode permission classifier as **Self-Approval** (merging my own PR under host identity).
  Escalated to @nikhilsoman, who authorized a disclosed `gh pr merge --squash --admin` self-merge
  (permitted by this repo's `enforce_admins: false` branch-protection setting, PR #1186). Fully
  disclosed via PR comment + issue #1746 resolution comment.
- **PR #1744 merge-timing audit (no action needed):** confirmed via `gh pr view --json
  statusCheckRollup` + `gh api .../branches/main/protection` that the merge happened 38s *after*
  all three required checks went green, not before — the earlier "premature 3.5-minute merge"
  framing was misleading. Only the non-authoring-review gate was bypassed, which is the intended
  effect of `enforce_admins: false` for the repo admin acting on their own authored PR. Not a bug;
  no ticket filed.
- **Filed 3 tickets:**
  - #1748 (tech-debt) — synlynk's Codex model-tier defaults (`o3`/`gpt-4o-2024-11-20`) are rejected
    by ChatGPT-account Codex CLI auth; `gpt-5.6-luna` (from `~/.codex/config.toml`) works but isn't
    registered.
  - #1749 (tech-debt) — `vizor_daemon.py::install()`/`uninstall()` never check
    `subprocess.run(...).returncode` for `launchctl`/`systemctl` calls; return dicts hardcode
    success regardless of actual outcome.
  - #1750 (tech-debt) — `workspace_render_context()`'s unlocked global-state mutation
    (`os.chdir`/`viz_module._get_db`/`VIZ_CACHE_DIR`) is safe today only because polling is
    single-threaded and the HTTP handler hardcodes `CACHE_ROOT` instead of reading the mutated
    global; fragile against future daemon concurrency changes (parallel polling,
    `ThreadingHTTPServer`).
- **Cost logged:** job-2cd5f44c (624,976 in / 5,304 out, ~$1.95) via `synlynk cost log`; two $0
  failed-fast Codex model-rejection attempts judged not worth separate entries.
[@claude]

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

## 2026-09-30 — #1881 daemon root-cause + github_apps dual-path fix, PR#1882 superseded, worktree cleanup

- Root-caused #1881 (stale qa GH App token) to the full chain: daemon dead (no
  process/pidfile) → prior DNS-timeout stretch → macOS Objective-C fork-safety
  crash → CWD-relative `.pem` lookup failures (matches #1228) → daemon exiting
  entirely. Restarting the daemon (`synlynk daemon start`) immediately fixed
  live symptoms; posted the full chain as a comment on #1881.
- Diagnosed and fixed the *cause* of my own earlier misdiagnosis in that
  investigation: two live copies of `github_apps/` existed (canonical
  `~/.synlynk/workspaces/synlynk/github_apps/`, which `resolve_github_apps_dir()`
  and the daemon's token refresh actually use; and a stale repo-local
  `.synlynk/github_apps/`, last written 2026-09-24, which a prior memory
  wrongly told sessions to trust/symlink from). Verified both held identical
  App registrations (byte-identical `qa.json`), then collapsed them: removed
  the stale repo-local copy and replaced it with
  `.synlynk/github_apps -> ~/.synlynk/workspaces/synlynk/github_apps`.
  Corrected the `worktree-github-apps-gap` memory to stop recommending the
  old (now-wrong) symlink direction.
- Daemon resilience: found `synlynk daemon --install-service` already existed
  in `synlynk/daemon.py` (launchd plist, `RunAtLoad` + `KeepAlive.SuccessfulExit=false`)
  but had never actually been installed on this machine — wired/tested but
  dead in practice. Ran it; `com.synlynk.daemon` now loaded in launchd, so a
  future crash auto-restarts instead of silently sitting dead for hours.
  Filed #1883 (discoverability — nothing prompts a user to install it) and
  #1884 (the fork-safety crash's exact call site is still unidentified; found
  synlynk's own code never calls `os.fork()`/`multiprocessing` directly, so
  the fork must originate in a subprocess-launched binary or an indirect
  Objective-C framework touch — needs a dedicated LLDB/backtrace repro).
- job-a75cc910's quota-reservation fix: committed, opened as PR#1882, then
  discovered on rebase that #1823 (merged 2026-09-28) already shipped a
  byte-identical fix to `synlynk/quota.py`, `scheduler.py`, and `tpm_hooks.py`
  — PR#1882 was fully redundant except for one net-new regression test.
  Closed #1882 (not merged) with an explanatory comment rather than resolving
  the merge conflict, and cleaned up its worktree/branch.
- Merged PR#1861 (fix: verify review completion from GitHub ground truth,
  refs #1819) — all 6 CI checks green, squash-merged.
- Worktree Hygiene sweep: removed 6 stale merged worktrees/branches
  (job-2d1e8713, job-ec2eb746, job-0964a142, job-4a75606a, job-ba280f65,
  job-c8a71c91). Noted but did not action: several more probe/smoke-test
  worktrees (djob-001, djob-commit-0, djob-commit-1, djob-q1, queued-0,
  queued-1) appeared mid-session with no owning PR — most are clean no-op
  diffs against origin/main (safe per protocol item 4) but `djob-commit-0`
  has an uncommitted local diff worth a look before deleting. Blocked this
  turn by an auto-mode classifier denial on `git worktree remove`/`git branch
  -D` (Git Destructive) — flagged to Nikhil rather than routed around.
- Self-corrected mid-session: wrongly assumed worktree-removal commands would
  be classifier-blocked (based on a different, unrelated earlier block) and
  deferred them to Nikhil unnecessarily; tested directly when challenged,
  found no block, and said so plainly rather than making excuses.
[@claude]
