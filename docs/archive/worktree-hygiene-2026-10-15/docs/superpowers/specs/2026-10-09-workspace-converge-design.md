# Workspace Convergence (`synlynk workspace converge`) — Design

**Issue:** gh:#2154 — "Adopted repos have no non-destructive pathway onto the latest synlynk release"

## Problem

A repo that has already been through `synlynk init` has no automated, non-destructive way
to converge onto a newer synlynk release's contract (config schema, instruction fences,
ledger shape, repo binding). `synlynk upgrade` only reinstalls the binary and compares
versions against the latest *GitHub Release*, which silently diverges from reality once a
tag is cut without a matching Release object (observed live: tag `v0.25.0` exists on `main`,
latest Release is still `v0.22.0`). `synlynk migrate` is a one-shot legacy importer gated by
a sentinel file — it cannot be re-run as a forward path. The result: adopted repos silently
drift (instruction fences stamped `0.20.0`, missing config keys defaulted only in memory,
stray per-worktree ledgers) while `doctor` reports healthy, because nothing checks workspace
*generation*, only artifact *presence*.

Full fixture evidence and the 12-point gap analysis live in the gh:#2154 issue body
(`Dialify/cc-videoreframing`, product identity `vdowrx`, observed 2026-10-09). This design
does not repeat that evidence — it resolves the gaps into a shippable design.

## Decisions

**1. "Latest" = latest git tag reachable from `main`, not the latest GitHub Release.**
Closes the tag-without-Release blind spot directly and drops `upgrade`'s dependency on the
`gh api` call for version comparison (works offline/without `gh` auth). `synlynk upgrade`'s
version check changes to this source; its scope otherwise stays binary-reinstall-only.

**2. Single workspace-contract version stamp**, not per-artifact freshness tracking.
`.synlynk/config.json` gains `workspace_contract_version: "<tag>"` — the generation this
workspace last fully converged to. `doctor`'s `version_current` check and the new `converge`
command both read/write this one field. Drift is reported as "N releases behind," not as a
scatter of independently-stale artifacts.

**3. New dedicated command: `synlynk workspace converge`.**
`upgrade` (binary reinstall) and `migrate` (one-shot legacy import) keep their current,
narrow contracts untouched — other code and docs already depend on those scopes being what
they are. `converge` is the new, purpose-built command for adopted-repo → current-contract
convergence.

**4. Dry-run by default; `--apply` to write.**
Every invocation without `--apply` only prints the plan. Matches the issue's own caution
("please do not run a destructive migrate or ledger sync against it as part of analysis")
and the standing git-safety posture (confirm before anything hard to reverse).

## Scope boundaries

In scope for `converge`:
- Persisting config keys currently defaulted only in memory (e.g. `harness_billing`).
- Refreshing instruction fences, restricted to managed regions only, via the existing
  `instructions diff`/`instructions update` machinery (no change to that command's contract).
- Quarantining stray ledgers — repo-root `.synlynk/state.db`, any nested-worktree
  `state.db` — to `.synlynk/quarantine/<timestamp>/`. **Never** merges or syncs a repo
  ledger into the product ledger at `~/.synlynk/workspaces/<slug>/state.db`; that merge
  decision requires a human diff and is explicitly out of scope for automation.
- Reporting (not resolving) the dual-`todo.md` conflict — one file is `checkpoint`-projected,
  one may hold operator edits; `converge` can't safely decide which wins.
- Bumping `workspace_contract_version` to the latest tag, on a branch, never on `main`.

Reported as explicit follow-ups, not automated by `converge`:
- GitHub App repo-install binding (`workspace add-repo` already does the local-JSON half;
  the GitHub UI half stays manual).
- Story↔GitHub-issue linking (`repo_id`/`gh_issue`/`source_ref` on existing stories) — this
  needs its own linker design (candidate: `synlynk backlog ingest`), not an improvised
  piece of `converge`.
- Expired role tokens, `agents` redundancy, gh-shim `PATH` — machine-global or
  daemon-lifecycle state, out of a single repo-scoped command's blast radius.

Explicitly deferred, not part of this spec:
- Auto-running `converge` on a schedule. That's gh:#2066's territory, and #2066 needs this
  same tag-based "latest" fix (decision 1) before any auto-run is safe to turn on.
- The GitHub-issue linker design mentioned above.

## Command behavior

```
$ synlynk workspace converge              # dry-run (default)
$ synlynk workspace converge --apply      # writes, on a branch
```

**Dry-run output** — the plan, nothing written:
- Config keys missing/defaulted-only-in-memory, with proposed values.
- Instruction-fence diff preview (managed regions only), file by file.
- Stray ledgers found (path, size, last-modified) that would be quarantined.
- `workspace_contract_version`: current → target.
- The todo.md conflict, reported with both files' line counts/paths.
- The "reported, not automated" follow-up list (role tokens, repo binding, etc.), generated
  from current `doctor`/`doctor --readiness` state so it's never out of sync with what
  doctor already knows.

**`--apply` behavior:**
1. Creates a branch (`chore/converge-workspace-<tag>`) off the current HEAD — refuses to run
   if the working tree is dirty with *unrelated* changes (uncommitted changes that `converge`
   itself would touch, e.g. an in-progress `config.json` edit, are preserved and carried onto
   the branch rather than blocking).
2. Persists the missing config keys.
3. Runs the fence refresh (reuses existing `instructions update` logic, so no duplicate
   diff/fence code path).
4. Moves stray ledgers into `.synlynk/quarantine/<timestamp>/` with a manifest noting
   original path and why it was flagged.
5. Bumps `workspace_contract_version`.
6. Never commits to `main`; never touches prose outside managed fence regions; never writes
   to or reads from the product ledger for merge purposes.
7. Exits printing the same follow-up list as dry-run, now scoped to "still needs your
   attention" after the automated steps.

**Exit criteria / interaction with `doctor`:** `doctor`'s `version_current` check must move
to the same tag-based source as decision 1 — otherwise `converge` could succeed while
`doctor` still reports the workspace as stale by comparing against the wrong "latest."
This is a small, coupled fix to `doctor`'s existing check, not a new check.

## Testing

- Unit tests for the new tag-based version source (replacing the Release-based one in
  `upgrade.py` and `doctor.py`'s `version_current` check) — cover: tag exists past latest
  Release, no tags past latest Release, no Releases exist at all.
- Unit tests for `workspace_contract_version` read/write and drift reporting.
- Integration test for `converge --apply` against a fixture repo seeded with: a missing
  config key, a stale fence, a stray repo-root `state.db`, and a nested-worktree `state.db`
  — assert branch created (not on `main`), config key persisted, fence diff restricted to
  managed regions, both ledgers quarantined (not merged into any product ledger fixture),
  `workspace_contract_version` bumped, and the follow-up list contains the items the
  fixture didn't let it automate.
- Negative test: dirty working tree with unrelated changes is preserved, not discarded, when
  `--apply` creates its branch.
- Negative test: dry-run (no `--apply`) makes zero filesystem writes.

## Open question for the implementation plan

None — the design is scoped and decided. The implementation plan should sequence: (a) the
tag-based version-source fix shared by `upgrade`/`doctor` first, since `converge`'s exit
criteria depends on it, then (b) the new `converge` command itself.
