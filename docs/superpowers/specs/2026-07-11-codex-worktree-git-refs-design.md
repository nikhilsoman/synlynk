# Codex Worktree git-ref Write Blocking — Design

**Tracks:** [#161](https://github.com/nikhilsoman/synlynk/issues/161) — Codex worktree dispatch structurally blocked from git commit/push

## Problem

Every Codex job runs inside an isolated `git worktree add <path> -b dispatch/codex/<job_id>` (`_create_job_worktree`, `synlynk/dispatch.py:462`). Git worktrees share `.git/refs/heads/` with the main repo by design — there is no per-worktree ref store for branches.

Codex is dispatched with `-s workspace-write` (`AGENT_CAPABILITY_BASELINES["codex"]`, `synlynk/_constants.py:44-56`), which sandboxes the process's filesystem writes to its own workdir + `/tmp`. This was flagged as a structural blocker in a dispatch-reliability handoff from the rxcc project (`docs/handoffs/dispatch-reliability-rxcc-2026-07-11.md`, item 3): a dispatched Codex job correctly diagnosed and drafted a fix but could not commit or push it, surfacing:

```
fatal: cannot lock ref 'refs/heads/<branch>':
Unable to create '<repo>/.git/refs/heads/....lock': Operation not permitted
```

### Root cause, refined through direct reproduction

The handoff doc characterized this as blocking "any git checkout -b / commit / push... regardless of task content." Direct reproduction (using `codex exec -s workspace-write` against a scratch worktree in this repo) showed a narrower mechanism:

- A plain `git commit` on the worktree's **already-existing** dispatch branch (`dispatch/codex/<job_id>`, created by synlynk before Codex runs) **succeeds** under `-s workspace-write` with no extra flags — updating an existing ref file is permitted.
- `git checkout -b <new-branch>` — creating a **second, new** branch inside the worktree — **fails** with exactly the reported error. Creating a new ref path (a new lock file / new directory under `.git/refs/heads/`) is what the sandbox blocks; updating an existing one is not.

So the actual failure trigger is Codex creating an additional branch on top of the one synlynk already isolated it onto — not every git write, as originally assumed.

### Fix validated

`codex exec` supports `--add-dir <DIR>` — "Additional directories that should be writable alongside the primary workspace" (confirmed via `codex exec --help`, codex-cli 0.142.3). This is the same class of flag Agy already lists as a valid dispatch flag (`synlynk/_constants.py:68`), just not yet wired into automatic dispatch for any agent.

Reproduced fix: running the identical failing `git checkout -b <new-branch>` command with `--add-dir <main-repo-git-common-dir>` added succeeds cleanly. No change to Codex's sandbox mode, no bypass flag, no change to synlynk's worktree isolation strategy.

## Design

### What changes

In `dispatch_agent()` (`synlynk/dispatch.py`), add a Codex-specific block that appends `--add-dir <git-common-dir>` to the dispatch flags, mirroring the existing `if agent == "grok":` flag-mutation blocks already in that function (~line 705-709).

```python
if agent == "codex":
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, cwd=os.getcwd(), timeout=5,
        )
        if result.returncode == 0:
            git_common_dir = result.stdout.strip()
            flags = flags + ["--add-dir", git_common_dir]
    except Exception:
        pass
```

Placed after the existing grok-specific blocks, before `probe_model` is called (flags must be finalized before the command is built/logged).

### Why `--git-common-dir`, not `<cwd>/.git`

`.git` at repo root is usually a directory, but inside a worktree (including a nested dispatch — synlynk dispatched from within another worktree) it's a *file* containing `gitdir: <path>`. `git rev-parse --path-format=absolute --git-common-dir` always resolves to the actual shared ref store regardless of nesting, so the fix is correct even in worktree-of-worktree scenarios. Using `--path-format=absolute` (git ≥ 2.31) avoids manually resolving a possibly-relative `.git` result against `os.getcwd()`.

### Why Codex-only, inline (not a new baseline field)

No other dispatched agent (`claude`, `agy`, `grok`) runs under an OS-level directory-scoped sandbox the way Codex's `-s workspace-write` does — Claude uses `--dangerously-skip-permissions`, Agy and Grok aren't sandboxed by a `-s`-style flag at all. This is currently a one-instance problem. Adding a generic `AGENT_CAPABILITY_BASELINES` field (e.g. `needs_git_common_dir_writable`) for a single consumer is premature abstraction — an inline `if agent == "codex":` block matches the existing pattern for grok's flag quirks and is trivial to generalize later if a second agent needs it.

### Error handling

The `git rev-parse` call is wrapped in try/except — if it fails for any reason (e.g. `git` unavailable, unexpected timeout), the flag is simply not appended and dispatch proceeds without it, rather than blocking dispatch entirely. This is defense-in-depth: `_create_job_worktree` runs moments later and already requires a valid git repo, so a real problem here would surface loudly there anyway.

### What does NOT change

- Codex's sandbox mode stays `-s workspace-write` — no widening to `danger-full-access`, no `--dangerously-bypass-approvals-and-sandbox`.
- Worktree isolation strategy (`git worktree add`, not `git clone`) is unchanged — the full-clone alternative from the original issue is not needed given the refined root cause.
- No prompt/task-injection changes telling Codex to avoid creating branches — per user decision, `--add-dir` alone is the fix; Codex remains free to create additional branches if it chooses to, they'll just now succeed.

## Testing

Unit test in `tests/test_agy_dispatch_fix.py` (existing file for dispatch-mechanics tests):

- `test_dispatch_codex_adds_git_common_dir_as_writable`: mock `subprocess.run` (for the `git rev-parse` call) to return a fixed absolute path, mock `subprocess.Popen`/worktree creation as existing nearby tests do, call `dispatch_agent(agent="codex", ...)`, and assert the constructed command list contains `--add-dir` immediately followed by the mocked git-common-dir path.
- A second case asserting that when the `git rev-parse` call fails (mocked non-zero return code), dispatch still proceeds and the command list does **not** contain `--add-dir` (defense-in-depth path exercised).

No integration test against a real `codex` binary — the existing test suite mocks subprocess calls for dispatch tests; the live reproduction done during this design session (documented above) stands as the manual verification that the mechanism itself is sound.

## Out of scope

- Issue #162 (Agy heartbeat/timeout observability) — separate, unrelated fix.
- Issue #160 (dispatch --help missing grok) — separate, trivial fix.
- Any change to how synlynk decides which branch name to give a worktree, or to job cleanup/merge flow.
