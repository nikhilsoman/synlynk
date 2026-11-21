# RCA: onboarding incident #5413 — the wizard cannot carry a multi-repo product intent

**Date:** 2026-11-20
**Severity:** Sev2 for the adopter session. No fleet-wide data loss. His uncommitted work was stashed, and a later run wrote role fences into the Synlynk source checkout.
**Status:** Causes confirmed on v0.38.3 (`28a05d19`). Prevention and the repair SOP below are proposed. They are not scheduled.
**Case file:** gh:#5413
**Analysis and the commands he should run:** `docs/rca/2026-11-20-onboarding-incident-5413-analysis.md`
**Already filed and still open:** gh:#5363, RCA `docs/rca/2026-11-18-LIVE-33-onboarding-unpublished-workspace.md` (gh:#5364). That RCA covers publish-after-dispatch, sovereign-runner discovery, and multi-identity quota. This document covers the rest of the same human session and does not restate those three designs except where this session proved them again.

## Summary

Jitendra upgraded Synlynk, named a workspace `roku`, and was trying to assemble a small Hotstar Android set so he could write a client context and start a Roku port. The first-run wizard dispatched an architecture review of whatever directory he happened to be in. After v0.38.1 that dispatch cannot succeed: from `~` it cannot resolve a git root, and from a real repo it fails the GOVERNS enforce gate because the wizard passes no story. Both failures still publish workspace files. One of them published into the Synlynk source checkout.

The workspace name, the repo list, and the job are three different objects. He set the first, the scan overwrote the meaning of the second, and the job never started.

## Causes

### 1. Launch throws away the workspace the wizard just built

`wizard_init` keeps `{workspace_name, repos, topology, home_harness}` in memory through screen 6. `_wiz_screen_launch` then calls `cmd_launch_ftue()`, which calls `run_workspace_scan()` with no arguments. The template variable `workspace` becomes the parent directory of the first git root (`dev` from `~`, `jitendra.agrawal` from `~/synlynk`). The name `roku` is written only later, by `write_workspace_config(workspace, ws_name)`, and only the config file sees it.

The architecture-review template also hardcodes `agent: claude` and tells the agent to append `.synlynk/project-docs/memory.md`. That is not the Android context document he needed, and on an unmigrated repo it is not where Synlynk keeps memory.

### 2. Failure is not the end of the wizard

`cmd_launch_ftue` catches every exception from `dispatch_agent`, prints `Dispatch failed`, and returns. `wizard_init` treats that return as success and runs `guard_dirty_worktree`, `write_workspace_config`, `generate_structured_context`, and the role-fence upsert. There is no published-generation marker. A reader cannot tell a failed attempt from a finished workspace.

`guard_dirty_worktree` runs `git stash` when `git status --porcelain` is non-empty. On the first session that hid his uncommitted files after the worktree had already been cut from `origin/main`. On the later sessions the dispatch failed first, and the stash and the writes still ran.

### 3. Enforce mode shipped without a first-run story

`require_linked_goal_mode` defaults to `enforce`. `_dispatch_capability_preflight` rejects a task hint with no story, issue, or PR. The wizard's only call is `dispatch_agent(..., story_id=None)`. v0.32 printed the #1990 warning and continued. v0.38.1's upgrade notes describe the enforcement gate as a delivered feature. The button the wizard still draws cannot pass that gate.

Creating a story is not enough on its own. `synlynk governs start` needs a roadmap version and a phase title, or an explicit unplaced goal with a reason. An unplaced goal still fails dispatch when the phase check is in enforce. The first-run path has neither a roadmap nor a story, and it does not create them.

### 4. The picker and the scan describe the neighborhood, not the product

`run_workspace_scan` with no roots searches `~/dev`, `~/projects`, and the current directory, depth 2. More than one root becomes topology `multi`, and every repo except dotfiles starts selected.

The picker reads one key. `int("5")` toggles item 5. `int("1")` then `int("2")` toggles items 1 and 2, not item 12. A path that does not contain `.git` hits `if extra and os.path.isdir(...)` and falls through with no message.

`synlynk scan --refresh` writes that same discovered set into the workspace config. `synlynk scan --add` is the precise tool, and the wizard does not use it. `--add` also requires a config file that already exists, so the first repo has to be seeded by hand or by a scan that over-collects.

### 5. The current directory is not checked

Two cwd checks are missing.

- `~` is not a git checkout. Dispatch fails closed, which is correct. The wizard continues and writes `~/.synlynk/context.md` plus a global workspace config, which is not correct.
- `~/synlynk` is a git checkout of the tool he just upgraded. Nothing compares `git rev-parse --show-toplevel` with the Synlynk install or with a clone whose `pyproject` / package name is synlynk. Role fences landed in the product repo. The next upgrade will stash them again, which is what the v0.38.1 upgrade already did once.

### 6. A workspace config is not a job scope

`write_workspace_config` stores paths, names, and stack labels under `~/.synlynk/workspaces/<name>/config.json`. Dispatch creates a worktree of the current repo (`_create_job_worktree`). The Android player repo is not in that worktree because it is listed in a JSON file. Doctor's note that `127.0.0.1:8000` is down is also not an input to the task picker, so the picker still offers Claude on a machine whose only interesting models are on another host.

#5363 already records that onboarding does not inventory a sovereign runner and does not federate a second identity. This session confirmed the user-visible half: doctor printed the closed port, and the wizard did not change the task.

### 7. There is no source-to-target handoff

His intent is a source set (`hotstar-android`), a context document, and a target repo (`roku`). The product has no object for that. The closest command is the architecture review, which writes a section into a generated memory file inside one worktree. Copying `docs/hotstar-android-client-context.md` into the Roku repo is the handoff that actually survives a worktree. The wizard cannot express it.

## Onboarding changes that prevent a repeat

These are the product changes. #5363 remains the ticket for the publish marker, runner discovery, and identity rows. The items below are the rest of this incident.

1. **Bind launch to the workspace in memory.** `cmd_launch_ftue` takes the `{workspace_name, repos}` the wizard already confirmed. It does not call `run_workspace_scan()` again. The template subject is that name.
2. **Stop the wizard when dispatch raises.** Commit-on-complete runs only after a publish step the user confirms, and only when dispatch did not raise. A failed dispatch leaves the previous config byte-for-byte unchanged.
3. **Do not stash the caller's tree.** Copy Synlynk-owned paths into the staging directory if a backup is required. `git stash` stays a command the user runs.
4. **Refuse a non-repo cwd, and refuse the tool's own checkout.** If `git rev-parse --show-toplevel` fails, the wizard stops before any write under `$HOME/.synlynk` other than a log line. If the toplevel is a Synlynk source checkout, the wizard says so and stops.
5. **Make the first task legal under enforce.** The launch screen creates a roadmap phase, a goal, and a story for the task it is about to run, and passes that story id. Until that exists, the dispatch key is disabled and the screen prints the GOVERNS reason. No warning-and-continue path remains on an enforce install.
6. **Picker: current repo only, then explicit adds.** Default selection is the repo he is standing in. An index is a line he submits, so 12 toggles item 12. A bad path prints `not a git repository`. `synlynk scan` without `--add` does not walk `~/dev` unless he passes `--discover`.
7. **A handoff command, not a smarter architecture review.** `synlynk context write` (name to be fixed in the spec) runs inside the source repo on a linked story and writes a path he names, default `docs/client-context.md`. `synlynk context apply --from <file> --workspace roku` copies that file into the target repo and opens a linked story whose prompt cites it. The target must already be its own git repo. The command refuses to run in the Synlynk source checkout.

Acceptance for this incident: repeating his two launches (cwd `~`, cwd = Synlynk clone, GOVERNS enforce, 78 nearby repos) writes no config, no context, and no role fence, and the task title on a legal run is `roku` or `hotstar-android`, whichever he confirmed.

## Repairing the next person automatically

GitHub cannot see his Mac. A workflow can diagnose the report and tell him the exact command. A local command is what changes his disk.

**Recommended: issue SOP plus `synlynk onboard repair`.**

The issue form for label `onboarding-incident` asks for four fields: what he was trying to build, the shell prompt (so the cwd is visible), `synlynk doctor`, and the last 40 lines of the wizard. Filing gh:#5413 by hand is the specimen. `help@` mail, if it exists, opens this form and does nothing else.

The fleet SOP, owned by the support/PM role and runnable as a headless dispatch with `--requires-gh-write` only for comments on the incident issue:

1. Read the issue. Do not clone his private repos and do not ask for his tokens.
2. Classify each symptom against the causes in this RCA. File a child bug for a new product gap. Comment the existing child when it is #5363 or one of the items above.
3. Reply with the `synlynk onboard repair` dry-run he should run, plus the manual steps the command cannot do (creating the target repo, copying the context file, the linked-story commands).

`synlynk onboard repair` defaults to dry-run. `--apply` is limited to signatures this incident actually produced:

- Role-fence hunks inside a Synlynk source checkout: restore those files from HEAD when the diff is confined to the managed fence.
- `$HOME/.synlynk/context.md` written while cwd was not a git repo: delete that file.
- A workspace config whose repo list contains the Synlynk source checkout or a non-repo path: print the offending paths. Do not delete the workspace. Rewriting the repo list requires him to pass `--repos` again.
- A stash named `pre-upgrade: local synlynk harness block edits (vwizard)` or `synlynk-init-safety-backup-*`: show the stat and stop. Dropping a stash is not `--apply`.

The command writes a receipt to the incident issue only when he passes `--issue <n>` and a role token is already available. It does not open a new issue by itself.

Two alternatives, and why they are weaker:

- **Playbook comments only.** This is the SOP above without the command. It repairs nothing until he types the commands. It is the right interim, and it is what the analysis doc already is.
- **A bot that edits his machine from the issue.** There is no channel to his Mac. Pretending a GitHub Action can drop his stash or rewrite `~/.synlynk` would mean shipping credentials into the issue. Rejected.

## help@synlynk.com

Yes, as a front door, after the issue form exists. Not as the system of record.

`help@synlynk.com` creates one GitHub issue with label `onboarding-incident` and the four fields above. The mail hook's only GitHub permission is to open that issue. It does not dispatch, it does not write repo files, and it does not copy attachment bodies that look like tokens into the issue. `security@synlynk.com` stays a different address so a credential report does not enter this queue.

Build the mailbox after the form and `synlynk onboard repair --dry-run` exist. Before that, help@ is a mailbox with no SOP. Until then, gh:#5413 is the template for what the mail should open.

## What is already fixed, and what is not

Fixed on the builds he can upgrade to: the launch screen prints `job["id"]` (gh:#5303), one Claude profile's `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `CLAUDE_CONFIG_DIR` pass through (gh:#5298), and `init` on a repo with no `.synlynk/config.json` skips job reconcile (gh:#5299).

Not fixed: publish-after-failure, launch ignoring the confirmed workspace, the picker, ambient scan, wizard-in-the-tool-checkout, GOVERNS enforce versus the first button, and source-to-target context handoff. #5363 covers the publish marker and the runner/identity discovery. This RCA's items 1 through 7 are the remainder. None of them are implemented by this document.
