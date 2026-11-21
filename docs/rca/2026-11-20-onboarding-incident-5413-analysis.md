# Onboarding incident #5413 — analysis and repair advisory

**Date:** 2026-11-20
**Case file:** gh:#5413
**Product defect already tracked:** gh:#5363 (LIVE-33). Its RCA is `docs/rca/2026-11-18-LIVE-33-onboarding-unpublished-workspace.md` (merged in gh:#5364).
**Adopter:** jitendra.agrawal, Mac host `JS00006`, home `/Users/jitendra.agrawal`
**Builds:** wizard first run on a pre-v0.38.1 install (checkout was v0.32.0 / `13189d5a`). Later runs on v0.38.1 (`d1ead4e6`) after `synlynk upgrade`. Current main at filing is v0.38.3 (`28a05d19`).

## What he was trying to do

1. Create a workspace named `roku`.
2. Create a second workspace, `hotstar-android`, containing a small set of Android repositories (the TV client, player, livingroom, and any shared UI kit).
3. Produce a written Hotstar Android TV client context from that set.
4. Use that document to start a Roku port of the Android TV app.

The wizard never offered that sequence. It offered one architecture-review dispatch, titled from the current directory, and wrote files after the dispatch failed.

## Session timeline

### 1. First wizard launch, before the upgrade

He confirmed the built-in architecture review: Claude, Visualize, full context, ~2h, 80K read / 8K write / 12 tool calls. The prompt is `arch-review` in `synlynk/launch_templates.py`. The subject was `jitendra.agrawal`, not a product name.

The screen then showed, in order:

- Capability gate degraded (`gh-actions` artifacts, no `--requires`). Non-blocking.
- `GOVERNS linkage missing — dispatch proceeding`. On that build `require_linked_goal_mode` was still a warning. The launch screen calls `dispatch_agent` with `story_id=None`.
- Worktree base `origin/main` at `6c169e292b8d0cf822558d9a316589e6c3bf14b1`.
- `▶ [unknown] claude dispatched` and `Log: synlynk logs --job unknown`. `dispatch_agent` returns `job["id"]`. That launch path read `job["job_id"]`. gh:#5303 fixes the launch screen. `synlynk/launch.py` `dispatch_first_win_remediation` still reads only `job_id`.
- Because the tree was dirty, commit-on-complete then ran: tar `.synlynk/backups/init-1794483517.tar.gz`, stash `synlynk-init-safety-backup-1794483517`, a 50,919-character `.synlynk/context.md`, workspace config, and role fences in `CLAUDE.md` and `AGENTS.md`.

The job's worktree was already cut. It did not contain the context, the role text, or the stashed files. He opened `.synlynk/project-docs/memory.md` in the main checkout. That is the path the template names, and it is inside the job worktree, not the file he had open.

### 2. Upgrade to v0.38.1

The Synlynk checkout `~/synlynk` fast-forwarded 75 commits from `13189d5a` (v0.32.0) to `d1ead4e6` (v0.38.1). The global install went from 0.31.0 to 0.38.1 via `./install.sh`.

`synlynk doctor` reported schema, flags, verbs, and SOPs green. It also reported that the `local`, `openrouter`, and `muse` CLIs are not installed, and that `127.0.0.1:8000` is unreachable. That is the default oMLX/vLLM port. This Mac cannot see a model server on the DGX Spark.

The upgrade stashed local edits inside the synlynk-managed blocks of `AGENTS.md` and `CLAUDE.md` as `pre-upgrade: local synlynk harness block edits (vwizard)`. The upgrade message says those edits are regenerable.

### 3. Repo picker

`_wiz_screen_workspace_name_pick` lists every git root the scan found and selects all of them except dotfiles. His list ran past item 78 (Hotstar services, plus `New project 2`, `sentinels-temp`, `wiki-2`).

The footer says number-to-toggle. `_wiz_read_key` returns one character, and the handler does `int(key)`. Items 10 and above cannot be toggled. The header text still says space-to-toggle. Space does not toggle.

`a` reads one line and accepts it only when `<path>/.git` is a directory. `hotstar-android-player and hotstar-android-livingroom` is not a directory, and the code prints nothing. Each name on its own line resolved relative to the current directory and was added.

### 4. Dispatch from `~`

Shell prompt `JS00006:~`. The preview titled the task `dev (Docker, CI/CD, multi repo)`. `dev` is `os.path.basename` of the parent of the first discovered git root (`synlynk/scan.py`, multi-repo branch). The workspace name he typed does not enter `cmd_launch_ftue`. That function calls `run_workspace_scan()` again and renders the template from the new scan.

Dispatch raised:

`could not resolve git-common-dir; refusing to silently fall back to the current working directory`

`_project_root()` in `synlynk/__init__.py` does this on purpose (gh:#1831). `~` is not a git checkout. `SYNLYNK_ALLOW_CWD_FALLBACK=1` is the escape hatch that #1831 exists to keep people from using.

`cmd_launch_ftue` catches the exception, prints `Dispatch failed`, and returns. `wizard_init` then runs commit-on-complete anyway. That wrote `~/.synlynk/context.md` (57,431 characters) and `~/.synlynk/workspaces/roku/config.json`. So the name `roku` was stored, and the task he was shown was not about `roku`.

### 5. Dispatch from `~/synlynk`

Shell prompt `JS00006:synlynk`. This is the Synlynk source checkout he had just upgraded. Git resolution succeeds, so preflight runs. The task title is `jitendra.agrawal (Python, CI/CD, multi repo)`, the parent directory of that checkout.

Preflight then rejects:

`Dispatch rejected: task is not linked to a GOVERNS story, issue, or PR. Link with --story <id>, --issue <num>, or --pr <num>.`

`gate_mode("governs_authority", "require_linked_goal_mode")` defaults to `enforce` (`tests/test_policy_gates.py`). The upgrade notes called this the universal GOVERNS enforcement gate. The wizard was not given a story, a goal, or a way to create one. The capability-gate line printed above the rejection is still only a warning.

Commit-on-complete ran again: `.synlynk/context.md` (32,286 characters) inside the Synlynk checkout, role fences in that repo's `CLAUDE.md` and `AGENTS.md`, and `~/.synlynk/workspaces/roku/config.json` again.

## What is on disk now

| Location | What the session put there | Repair |
|---|---|---|
| `~/synlynk` `CLAUDE.md`, `AGENTS.md` | Wizard role fences, after the upgrade had stashed the previous fences | `git diff` those two files. If the diff is only the wizard blocks, `git checkout -- CLAUDE.md AGENTS.md` |
| `~/synlynk` stash | `pre-upgrade: local synlynk harness block edits (vwizard)` | `git stash show`. Drop only if the patch is those blocks |
| Other repo, if the first wizard ran there | stash `synlynk-init-safety-backup-1794483517` and tar `.synlynk/backups/init-1794483517.tar.gz` | Inspect with `git stash show` before pop |
| `~/.synlynk/context.md` | 57,431-character scan from the home-directory run | Delete. It is not a workspace |
| `~/.synlynk/workspaces/roku/config.json` | Repo list from whatever was selected when the wizard finally wrote | Replace in the Roku step below. Do not trust it |
| Job worktree from the first launch | Possible architecture-review output under `.synlynk/project-docs/memory.md` | Ignore. Wrong task, wrong base commit |

Do not delete `~/.synlynk` itself. The CLI install is `~/.local/bin/synlynk`. Do not set `SYNLYNK_ALLOW_CWD_FALLBACK=1`. Do not run the wizard inside `~/synlynk` again. On the task picker, `s` skips the dispatch.

## Repair steps

A workspace file under `~/.synlynk/workspaces/<name>/config.json` is a list of repos. `synlynk dispatch` runs in the git checkout you are standing in and creates a worktree of that checkout only. Sibling paths are visible to the agent only if the sandbox can read them. The reliable handoff into the Roku repo is a document copied into that repo.

### A. Clean the tool checkout

```bash
cd ~/synlynk
git diff -- CLAUDE.md AGENTS.md
git checkout -- CLAUDE.md AGENTS.md
git stash list
git stash show -p "stash^{/pre-upgrade: local synlynk harness block edits}"
git stash drop "stash^{/pre-upgrade: local synlynk harness block edits}"
```

Drop the stash only after the show confirms it is the role blocks. Leave every other stash. In any other repo where the wizard ran, `git stash list` and `synlynk jobs`. Pop `synlynk-init-safety-backup-1794483517` only after `git stash show`.

```bash
rm -f ~/.synlynk/context.md
```

### B. Register the Android client, and nothing else

Stand in the Android TV app. Not `~`, and not `~/synlynk`.

```bash
cd /absolute/path/to/hotstar-android-tv
synlynk init --yes
mkdir -p ~/.synlynk/workspaces/hotstar-android
```

Write `~/.synlynk/workspaces/hotstar-android/config.json`:

```json
{
  "workspace_name": "hotstar-android",
  "topology": "multi",
  "repos": []
}
```

Add one absolute path per command. `synlynk scan --add` rejects a path that is not a single git checkout, and it prints that rejection. Do not run `synlynk scan --refresh`. That walks `~/dev` and `~/projects` and would put the whole neighborhood back in the file.

```bash
synlynk scan --add /absolute/path/to/hotstar-android-tv --workspace hotstar-android
synlynk scan --add /absolute/path/to/hotstar-android-player --workspace hotstar-android
synlynk scan --add /absolute/path/to/hotstar-android-livingroom --workspace hotstar-android
synlynk scan --deep
```

`--deep` writes `project-docs/source-map.md` for the TV app repo only.

### C. Write the Android context with a linked story

v0.38.1 rejects an unlinked dispatch. Create the goal in the TV app repo, the same checkout you will dispatch from.

```bash
synlynk roadmap add --version v0.1.0 --title "Hotstar Android client context"
synlynk roadmap add --version v0.1.0 --phase-title "Client context"
synlynk governs start \
  --outcome "A written model of the Hotstar Android TV client that a Roku port can follow" \
  --criterion "docs/hotstar-android-client-context.md names modules, screens, playback, and the sibling repo that owns each part" \
  --version v0.1.0 \
  --phase-title "Client context"
synlynk story create --title "Write the Hotstar Android TV client context"
synlynk goal link story-XXXXXXXX --goal goal-YYYYYYYY
synlynk story ready story-XXXXXXXX
synlynk dispatch claude --story story-XXXXXXXX --context-mode full \
  "Read this repo and these sibling checkouts: /absolute/path/to/hotstar-android-player and /absolute/path/to/hotstar-android-livingroom. Write docs/hotstar-android-client-context.md in this repo. Cite files. Stop after the document."
```

Use the ids the commands print. Follow the job with `synlynk logs --job <id>`. Merge the branch that contains the document. If a sibling path is unreadable from the job, run the same request in that repo and paste the section into the TV app's document.

### D. Start the Roku repo from that document

```bash
mkdir -p ~/src/hotstar-roku/docs
cd ~/src/hotstar-roku
git init
cp /absolute/path/to/hotstar-android-tv/docs/hotstar-android-client-context.md docs/
synlynk init --yes
```

Replace `~/.synlynk/workspaces/roku/config.json` with an empty repo list (`"workspace_name": "roku"`, `"topology": "multi"`, `"repos": []`), then:

```bash
synlynk scan --add ~/src/hotstar-roku --workspace roku
synlynk scan --add /absolute/path/to/hotstar-android-tv --workspace roku
```

Repeat roadmap, `governs start`, story, link, and ready inside `~/src/hotstar-roku`. The outcome is a Roku SceneGraph app whose screens and playback follow `docs/hotstar-android-client-context.md`. Dispatch with `--story`. The context file is inside this repo, so the worktree contains it.

Claude is the harness for both dispatches. Leave the local harness unused until `synlynk doctor` shows `127.0.0.1:8000` open, or until `OPENAI_BASE_URL` / `SYNLYNK_LOCAL_AI_URL` points at a server this Mac can reach.
