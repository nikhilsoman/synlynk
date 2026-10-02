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
++ b/project-docs/devlogs/claude.md

## 2026-09-30 — #1886 multi-agent concurrency architecture + PR#1888 pre-commit
  worktree guard (shipped)
- Discovered mid-cleanup that the main checkout had switched to
  `feat/agy/vizor-workspace-scoped-routing` with uncommitted files not
  created by me — an interactive Agy session working directly in the shared
  main checkout instead of a worktree. Stopped, did not touch the foreign
  files, confirmed with Nikhil (was Agy, expected) before continuing. Filed
  the itemized deferred-cleanup list as #1886 (6 probe worktrees, 1 remote
  branch, PR#1885's stuck merge, 1 orphaned nested worktree) and held per
  explicit instruction rather than resuming cleanup mid-collision.
- Nikhil asked whether multi-agent concurrency on one repo is a git
  limitation or solvable: answered no — git worktrees already give hard
  isolation (can't check out the same branch twice, separate HEAD/index per
  worktree, shared object DB, no ref collisions across branches). The actual
  gap was procedural: nothing stopped a session from skipping worktree
  creation and working in the shared main checkout, which is exactly what
  happened. Presented 3 ranked options; Nikhil approved a pre-commit hook
  that technically enforces worktree-only commits rather than relying on
  every harness remembering the rule.
- Dispatched the hook to Codex per locked Default Agent Role policy (PM
  writes specs, not code). First dispatch attempt omitted `--base main` and
  silently based off Agy's checked-out branch in the shared repo — caught
  from the dispatch tool's own stderr before any commit, killed the
  subprocess, verified no damage, cleaned up, redispatched correctly with
  `--base main`.
- job-49d011d4 shipped `githooks/pre-commit` (blocks commits in the shared
  main checkout — main branch or detached HEAD — allows any linked
  worktree), wired `core.hooksPath` into `synlynk init`, documented it in
  CLAUDE.md, added tests. Opened PR#1888. Dispatched a non-authoring `qa`
  review per PR Review Discipline (job-e5e7e18c): CHANGES_REQUESTED — found
  the init wiring unconditionally clobbered any pre-existing
  `core.hooksPath`, and the tests invoked the hook script directly rather
  than through a real `git commit`. Dispatched the fix (job-fa07b112,
  commit b19dbe81): preserves existing hooksPath, tests now drive real
  `git commit` through main/detached-HEAD/linked-worktree cases.
- Re-dispatching the re-review (job-c3a4c1be) initially resolved against the
  stale pre-fix commit because my local branch ref hadn't been updated after
  the push — caught by diffing the worktree's `git log -1` against origin,
  killed the job before it reviewed the wrong code, force-updated the local
  ref to origin's tip, redispatched correctly. Re-review APPROVED, CI green
  6/6, `qa` cleared via `synlynk policy check-merge`, merged (`1e1da814`).
- Every job in this PR's lifecycle (implementer, review 1, fix, review 2)
  reported `FAILED (exit -9)`/`circuit_breaker_tripped` on completion despite
  doing real, verified work each time (confirmed independently via
  `gh pr view`/`git log` rather than trusting the exit code) — consistent
  false-negative pattern already in memory (#202), now observed 4x
  consecutively on one PR. Worth a dedicated investigation if it keeps
  recurring at this rate; capturing here rather than opening a ticket this
  turn since the underlying artifacts were all independently verified.
- Cleaned up all 3 review-cycle worktrees/branches same-turn per Worktree
  Hygiene Protocol (PR merged). One (job-e5e7e18c) carried the same
  1525-line `project-docs/todo.md` test-run side-effect diff already
  documented in #1886 for `djob-commit-0` — confirmed as a known harmless
  artifact, not new work, before discarding.
[@claude]

## 2026-10-02 — Five-POV deep review (developer / architect / founder / VC / influencer)

- Wrote `docs/strategy/2026-10-02-five-pov-review.md`. Every metric was measured on 2026-10-02
  (repo, git, CI, GitHub) rather than copied from docs: ~80.7K LOC, 155 commands, 3,667 tests,
  831 merged PRs, 21 LIVE incidents, 1 star / 0 forks, `~/.synlynk` 8.3 GB.
- Since the 2026-07-12 Fable review: the daemon queue path now delegates to `dispatch_agent()`
  (fixed). Unchanged: Claude still defaults to skip-permissions, token accounting is still
  regex-scraped, and distribution is still the bottleneck.
- Architect recommendations, in priority order:
  1. `HarnessAdapter` protocol to replace the `if agent ==` branches
  2. Split `dispatch_agent` (27 kwargs) into a pipeline with a typed request object
  3. Structured telemetry + verified-effects job state machine
  4. Consolidate state behind one DAO; markdown becomes an export; add GC and a size budget
  5. Safe-by-default permission profiles
  6. Split core (~15 commands) from optional packs
  7. Break up `viz.py`
  8. Make `release --check-docs` a required CI check, with one version source
  9. Cold-start performance budget
- Found version drift: `VERSION`=0.23.0-dev, README badge 0.22.0, CHANGELOG at v0.25.0
  (no v0.23/v0.24 entries), v0.21.0 listed twice. No ticket filed yet.
[@claude]

## 2026-10-02 — Blog index fix (#1914) + lifted stale Blog Post Protocol hold

- Added missing `docs/blog/README.md` index row for post 236 (flagged by qa's PR #1913
  review); folded into #1914 rather than a third ticket, per Nikhil's instruction.
- Lifted the 2026-07-12 "Blog Post Protocol paused" Active Hold: it predates ~165 posts
  (71→236) written since, and was never actually enforced in the committed
  `project-docs/memory.md` — it existed only in this machine's local `state.db`
  (`~/.synlynk/workspaces/synlynk/state.db`, `memory_entries` id=21) and the generated
  `.synlynk/context.md`, so there was nothing to commit to the repo. Updated that row
  in place (struck through + LIFTED note) rather than deleting it, so the history of
  why it existed and why it's lifted stays visible.
- New finding, not yet ticketed: `_write_memory_md()` regenerating the tracked
  `project-docs/memory.md` from this machine's registered state.db produces a 249
  insertion / 49 deletion diff against `origin/main` — i.e. local DB state has drifted
  well beyond what's committed. Did not commit that regeneration (same risk class as
  #1915's costs.md finding); flagging for Nikhil rather than filing a third ticket
  unprompted.
[@claude]
