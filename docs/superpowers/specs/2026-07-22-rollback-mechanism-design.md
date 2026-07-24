# Rollback Mechanism for init / migrate / upgrade — Design Spec

**Status:** Approved by user (2026-07-22)
**Context:** Follows PR #450 (fixed `selftest --live` isolation bugs #448/#449) and PR #452 (issue #451, live selftest coverage for `init`/`migrate`/`upgrade`). Prompted by the question "are we 100% certain synlynk init/migrate/upgrade cannot damage a repo or dev environment?" — answer was no: `upgrade` had zero live-test coverage, and `migrate`'s failure paths were not provably atomic. This spec closes that gap by giving every mutating operation an undo path, independent of the test-coverage work in #451.

## Problem

`synlynk init`, `synlynk migrate`, and `synlynk upgrade` all mutate real state — files in the user's repo, the git index, `.synlynk/` internals, and (for `upgrade`) the global package install location. None of them can currently be undone if something goes wrong mid-operation or the user simply doesn't like the result. Concretely:

- `migrate` performs `_migrate_import()`, a `shutil.copytree` backup, `git rm --cached`, a `.gitignore` edit, a sentinel write, and finally its own `git commit` — but only the first step (`_migrate_import`) is guarded; a failure in any later step leaves a half-migrated repo with no recovery path today.
- `init --force` can overwrite skeleton docs and instruction files with no backup.
- `init`'s four "extended" targets (`.cursor/rules/synlynk.mdc`, `.github/copilot-instructions.md`, `.windsurfrules`, `AI_INSTRUCTIONS.md`) use `marker_style="none"` and **always overwrite unconditionally**, regardless of `--force` — the highest-risk write site in `init`.
- `upgrade` never touches the git repo at all — it reinstalls the pipx venv (`pipx install ...@v<tag> --force` / `pipx upgrade`) or re-runs a curl-piped install script that rewrites `~/.synlynk/bin` and `~/.synlynk/lib`. A network failure mid-upgrade, or a bad release, currently leaves no way back to the previous working version.

## Approach

Two independent, cooperating mechanisms, as approved:

- **Approach A — Checkpoint + Restore**: record enough state before a mutating operation to fully undo it, either automatically on failure or on request via `synlynk rollback`.
- **Approach C — Dry-run** (already exists for `migrate`, extended to `init` and `upgrade`): a pre-flight preview so most unwanted changes are caught before they happen.

**Trigger model (confirmed with user):** both automatic (on any uncaught exception inside the wrapped operation) and manual (`synlynk rollback --last` after a successful-but-unwanted run).

**Time horizon (confirmed with user):** same session only. This scope is why Approach A leans on git itself as the ledger for repo-scoped changes rather than building a standalone transaction-journal (a "B" approach — full WAL-style logging of every write — was considered and rejected as disproportionate to a same-session-only requirement).

Because `init`/`migrate` and `upgrade` mutate fundamentally different things — a git repo vs. a global install location outside any repo — Approach A splits into two legs that share one CLI surface but have distinct restore logic.

### Leg 1 — Repo Checkpoint (covers `init`, `migrate`)

Before the operation runs:

1. If the working tree is dirty, auto-stash: `git stash push -u -m "synlynk-rollback-<op-id>"`.
2. Record the current `HEAD` SHA. **For `migrate` specifically, this must be recorded before `cmd_migrate()` runs at all** — `migrate`'s own final step is a `git commit`, so the checkpoint SHA has to be the state *before* that commit, not after. `git reset --hard <checkpoint-sha>` on rollback then correctly undoes migrate's commit, its `git rm --cached` index change, and its `.gitignore` edit in one step, since they're all part of that single commit.
3. Copy every *untracked* file/dir the operation is about to touch into `.synlynk/rollback/<op-id>/backup/`, preserving relative paths:
   - `init`: `.synlynk/config.json` (if pre-existing), `.git/hooks/pre-commit` (not git-tracked — hooks are never versioned), any manifest file `init` writes.
   - `migrate`: `.synlynk/state.db` (pre-import snapshot), `.synlynk/project-docs/` (if a prior backup already exists there — `cmd_migrate` does `shutil.rmtree` + `shutil.copytree`, a destructive overwrite of any earlier backup), `.synlynk/.synlynk_migrated` (absence itself is meaningful — its presence after rollback would be wrong).
4. Write `.synlynk/rollback/last.json`: `{op_id, op_type: "init"|"migrate", timestamp, checkpoint_sha, stash_ref, backup_dir}`.

On success: the manifest is left in place (so `synlynk rollback --last` still works later in the session). On an uncaught exception raised anywhere inside the wrapped operation: restore is triggered automatically using the same manifest, before the exception propagates to the user.

**Restore procedure** (used by both automatic and manual rollback):
1. `git reset --hard <checkpoint_sha>`.
2. If `stash_ref` is set, `git stash pop <stash_ref>` (or `apply` + `drop` if `pop` conflicts — surface the conflict rather than silently dropping user changes).
3. Recursively copy `backup_dir` back over its original relative paths, overwriting whatever the failed/unwanted operation left behind.
4. Move the manifest to `.synlynk/rollback/archive/<op-id>.json` so it can't be applied twice.

### Leg 2 — Install Snapshot (covers `upgrade`)

`upgrade()` in `synlynk/upgrade.py` never touches the git repo, so Leg 1 does not apply to it at all. Before upgrading:

1. Record the current `VERSION` string and the detected install type (`pipx` / `pip` / `script` / `unknown`, via the existing `_detect_install_type()`) into the same `.synlynk/rollback/last.json` manifest, using `op_type: "upgrade"`.
2. For `install_type == "pipx"`: no file snapshot needed — pipx always builds a fresh venv on install, so rollback is simply re-running the same install path pinned to the old version: `pipx install git+https://github.com/nikhilsoman/synlynk@v<old_version> --force`.
3. For `install_type == "script"`: the curl-piped installer has no built-in version pinning today, so **also** copy `~/.synlynk/bin` and `~/.synlynk/lib` aside into `.synlynk/rollback/<op-id>/backup/` before running the installer. Rollback restores those directories directly by copying them back — this is the one case where Leg 2 needs a literal file backup rather than a reinstall-by-tag.
4. For `install_type in ("pip", "unknown")`: `upgrade()` already refuses/warns for these paths today (per `_warn_stale_script_install()` and friends) — no new rollback logic needed beyond recording the manifest for consistency; these paths don't perform the mutating reinstall this spec is concerned with.

**Restore procedure:**
1. `pipx`: re-run `pipx install git+...@v<old_version> --force`.
2. `script`: copy `~/.synlynk/bin` and `~/.synlynk/lib` back from the backup.
3. Archive the manifest (same as Leg 1, step 4).

### Shared CLI surface

`synlynk rollback [--last | <op-id>]`:
- Reads `.synlynk/rollback/last.json` (or a specific archived op-id under `.synlynk/rollback/archive/` if given explicitly).
- Dispatches to Leg 1 or Leg 2 restore logic based on the manifest's `op_type`.
- `synlynk rollback --clear` discards the current checkpoint without restoring anything — for when a user reviews an `init --force` or a `migrate` result and decides to keep it.

A single context manager, `_rollback_checkpoint(op_type)`, wraps the bodies of `init()`, `cmd_migrate()`, and `_run_upgrade()`, performing the pre-op snapshot on entry and the automatic-restore-on-exception behavior via `__exit__`.

### Error handling within the rollback mechanism itself

- If `git reset --hard` fails during restore (e.g. the checkpoint SHA no longer exists because of a concurrent force-push), abort the restore cleanly, print the exact manual recovery information (SHA, stash ref, backup dir path), and **do not delete the backup directory** — leave all evidence in place for manual recovery rather than silently losing it.
- The manifest is archived (not deleted) immediately after any successful rollback, preventing a second, stale rollback from reapplying on top of an already-restored state.
- Retention: only the single most recent checkpoint per `op_type` is kept live in `.synlynk/rollback/last.json` at a time — starting a new `init`/`migrate`/`upgrade` overwrites the previous checkpoint of the same type. This matches the "same session only" time horizon; nothing here promises rollback across sessions or across multiple prior operations.

### Approach C — Dry-run extension

`migrate --dry-run` already exists (prints what would happen, writes nothing). Extend the same pattern:

- `init --dry-run`: print every file that would be created or overwritten, explicitly calling out the four always-overwrite extended targets (`.cursor/rules/synlynk.mdc`, `.github/copilot-instructions.md`, `.windsurfrules`, `AI_INSTRUCTIONS.md`) so a user with pre-existing content in those files is warned before running for real.
- `upgrade --dry-run`: print detected install type, current version, target version, and which restore path (`pipx` reinstall vs. `script` file-backup) would be used if a rollback were later needed — no subprocess/network calls.

Dry-run is a complement to rollback, not a substitute — it doesn't help once an operation is already running or has already failed. Its value is catching intent mismatches (e.g., "I didn't realize `--force` would touch that file") before any mutation happens at all.

## Testing

This mechanism should be exercised by the same live-selftest scenarios introduced in #451/PR #452 (`_scenario_init_existing_files`, `_scenario_migrate`, `_scenario_upgrade`), extended with a failure-injection variant of each:

1. Run the scenario to completion normally (already covered by #451).
2. Run the scenario again, injecting a failure partway through the operation (e.g. patch `git rm --cached` to raise inside `_scenario_migrate`, patch the mocked `subprocess.run` to raise inside `_scenario_upgrade`), and assert that:
   - the automatic rollback fires,
   - the scratch workspace ends up byte-identical to its pre-operation state (same technique already used to catch #448),
   - the manifest is archived, not left live, after the auto-rollback.
3. A separate test for `synlynk rollback --last` on the happy path: run an operation to success, invoke `rollback --last`, assert the workspace matches the pre-operation snapshot exactly.
4. A separate test for `synlynk rollback --clear`: run an operation to success, invoke `--clear`, assert the manifest is gone but the operation's changes remain.

## Explicitly out of scope

- Rollback across sessions or after `.synlynk/rollback/` has been cleared/archived — the approved time horizon is same-session only.
- A general-purpose transaction journal for arbitrary future synlynk commands (rejected as Approach B; the mutation surface here is limited to three specific commands, and git already gives Leg 1 a reliable ledger).
- Automatic remediation of `pip`/`unknown` install types in `upgrade` — these are already refused/warned elsewhere in `upgrade()` and are not part of the mutating-reinstall path this spec covers.
