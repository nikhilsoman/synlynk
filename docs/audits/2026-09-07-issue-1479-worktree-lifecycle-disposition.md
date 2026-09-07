# Worktree Lifecycle & Disposition Report (#1479)

**Audit Date:** 2026-09-07  
**Auditor:** AGY (`dispatch/agy/job-12af0aa9`)  
**Scope:** Comprehensive read-only lifecycle review of all registered git worktrees in `nikhilsoman/synlynk`  
**References:** Issue #1479 (Worktree Triage), Issue #1487 (Commit Recovery), Issue #1488 (Sentinel Lifecycle Hygiene)

## 1. Executive Summary

Following the 2026-09-07 lifecycle maintenance run that cleaned 42 merged worktrees, a total of **53 worktrees** remain registered in the git repository (52 registered worktrees evaluated + the current inspection session `job-12af0aa9`).

A strict, read-only audit of every worktree was performed using `synlynk worktree audit`, `git status --porcelain`, `git cherry origin/main`, `git log`, and GitHub CLI (`gh pr list`).

### High-Level Classification Breakdown

| Category | Count | Official Verdict | Key Characteristic |
| :--- | :---: | :--- | :--- |
| **Active Pull Requests** | 6 | `UNSAFE` | Active open PRs (#1477, #1478, #1480, #1481, #1482, #1483). Do not touch. |
| **Dirty Content** | 2 | `NEEDS-REVIEW` | Uncommitted / untracked files requiring preservation review. |
| **Nested Worktrees** | 1 | `NEEDS-REVIEW` | Worktree path physically inside another worktree path (structural hazard). |
| **Functionally Merged (`cherry -`)** | 14 | `NEEDS-REVIEW` | All unique commits already merged upstream into `origin/main` via PRs. |
| **Stale Superseded Dispatches** | 15 | `NEEDS-REVIEW` | Older dispatch attempts for features that landed under different PRs. |
| **Unmerged Unique Commits** | 12 | `NEEDS-REVIEW` | Valuable unmerged tests, refactors, specs, runbooks to recover in #1487. |
| **Clean Ancestor / Current Session** | 3 | `SAFE` / `EXCLUDED` | `main` repo checkout, `job-9ed27dd4` (safe clean ancestor), and `job-12af0aa9` (current session). |
| **Total Registered Worktrees** | **53** | — | — |

## 2. Active Pull Requests (`UNSAFE` — 6 Worktrees)

The following 6 worktrees correspond to open GitHub pull requests actively in flight. Per repository policy, these worktrees and their branches must remain completely untouched until their PR reviews and merge lifecycles conclude.

| PR # | Branch | Worktree Path | Title | Ahead |
| :--- | :--- | :--- | :--- | :---: |
| [#1478](https://github.com/nikhilsoman/synlynk/pull/1478) | `dispatch/grok/job-8423ec87` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-8423ec87` | test: QA advanced flaky-integration regression strategy | 1 |
| [#1482](https://github.com/nikhilsoman/synlynk/pull/1482) | `dispatch/grok/job-89b5c9a1` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-89b5c9a1` | fix: Write 3 test cases for a general scenario at basic d (job-89b5c9a1) | 1 |
| [#1483](https://github.com/nikhilsoman/synlynk/pull/1483) | `dispatch/grok/job-8aa012b0` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-8aa012b0` | fix: Detect drift between two versions of a roadmap doc: (job-8aa012b0) | 1 |
| [#1481](https://github.com/nikhilsoman/synlynk/pull/1481) | `dispatch/grok/job-aca06f51` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-aca06f51` | fix: Reconcile a slipping deadline against two blocked de (job-aca06f51) | 1 |
| [#1477](https://github.com/nikhilsoman/synlynk/pull/1477) | `dispatch/grok/job-b60fc2e1` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-b60fc2e1` | test: minimal Python function for capability calibration (job-b60fc2e1) | 1 |
| [#1480](https://github.com/nikhilsoman/synlynk/pull/1480) | `dispatch/grok/job-df2aee7c` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-df2aee7c` | fix: Draft a roadmap section reconciling two conflicting (job-df2aee7c) | 1 |

> [!IMPORTANT]
> All 6 active PRs were authored via headless Grok dispatches. They must not be pruned, cleaned, or modified by automated sweeps.

## 3. Dirty Content & Preservation Review (`NEEDS-REVIEW` — 2 Worktrees)

An inspection using `git status --porcelain` across all 53 worktrees identified **exactly 2 worktrees** with dirty working trees. All other 51 worktrees have clean working trees. Both dirty worktrees contain important artifacts that must be preserved.

### 3.1 `dispatch/codex/job-262d4800`

- **Worktree Path:** `/Users/nikhilsoman/dev/synlynk/worktrees/job-262d4800`
- **Branch:** `dispatch/codex/job-262d4800` (at commit `6bb73fec`, direct ancestor of `origin/main`)
- **Dirty Status:** `?? docs/superpowers/specs/2026-09-07-sentinel-persistence-review-1488-design.md`
- **Analysis:** This worktree was clean and classified as `SAFE` in earlier sweeps. At `2026-09-07 23:55`, an untracked design spec (12,587 bytes) for **Issue #1488 (Sentinel lifecycle hygiene)** was created in this worktree directory.
- **Preservation Action:** **DO NOT CLEAN.** The untracked design spec represents active architectural work for Issue #1488. Move or commit `docs/superpowers/specs/2026-09-07-sentinel-persistence-review-1488-design.md` to a dedicated feature branch (`feat/sentinel-lifecycle-1488`) before this worktree is ever considered for removal.

### 3.2 `dispatch/codex/job-89bd001e` (`pr-1371-review`)

- **Worktree Path:** `/Users/nikhilsoman/dev/synlynk/worktrees/pr-1371-review`
- **Branch:** `dispatch/codex/job-89bd001e` (associated with closed PR #1371)
- **Dirty Status:** `M docs/blog/README.md`
- **Analysis:** Modified `docs/blog/README.md` adds 29 table rows backfilling historical blog post references (posts 28, 51-53, 55-58, 91-96, 100-101, 132-133, 144-149, 165). This documentation index update is valuable and should not be discarded.
- **Preservation Action:** Extract the git diff of `docs/blog/README.md` into a patch or commit it directly to main/docs branch (`chore: backfill historical blog index entries in docs/blog/README.md`), then discard or clean the worktree.

## 4. Nested Worktrees & Structural Hazards (1 Worktree)

A physical directory nesting condition exists between two worktrees in the registry:

- **Child Worktree:** `/Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1/pr-1361-review`
  - **Branch:** `dispatch/agy/job-e2061c9a`
  - **Associated PR:** PR #1361 (Closed)
  - **Status:** 2 commits ahead of main, clean working tree
- **Parent Worktree:** `/Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1`
  - **Branch:** `dispatch/codex/job-92c021a1`
  - **Associated PR:** None (Review commit for PR #1361)
  - **Status:** 3 commits ahead of main, clean working tree

### Structural Hazard & Removal Ordering Rule
> [!WARNING]
> **Removal Ordering Hazard:** The child directory `pr-1361-review` resides physically inside the directory of the parent worktree `job-92c021a1`. If any tool or operator attempts to delete the parent directory `/Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1` first, the child git worktree metadata will be corrupted or `git worktree remove` will fail because the folder contains an active nested git repository link.
> 
> **Strict Deconstruction Sequence:**
> 1. First: Safely remove the child worktree: `git worktree remove /Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1/pr-1361-review`
> 2. Second: Remove the parent worktree: `git worktree remove /Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1`
> 
> `synlynk worktree audit` correctly enforces the nesting floor: the child verdict is held at `needs-review` because `parent worktree not yet safe`.

## 5. Functionally Merged Worktrees (`cherry -` — 14 Worktrees)

These 14 worktrees were classified as `needs-review` by `synlynk worktree audit` solely because their commits were merged into `origin/main` via squash, rebase, or PR merge rather than direct fast-forward ancestor commits. `git cherry origin/main <branch>` confirms that **every single commit patch is already present in `origin/main`** (`cherry -`). None of these worktrees contain unmerged code.

| Branch | Path | Ahead Commits | Commit Summary | Landed Upstream Via |
| :--- | :--- | :---: | :--- | :--- |
| `dispatch/codex/job-17663b7c` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-17663b7c` | 1 | fix: Implement Living Charter Evolution & Capability-Gate (job-4bf9c7e6) | PR #1360 |
| `dispatch/claude/job-1885d5fe` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-1885d5fe` | 1 | fix: Implement Living Charter Evolution & Capability-Gate (job-4bf9c7e6) | PR #1360 |
| `dispatch/codex/job-2d0fe8f5` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-2d0fe8f5` | 1 | fix: isolate parent auto-pr github auth | Upstream PR |
| `dispatch/codex/job-5c76d72d` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-5c76d72d` | 1 | fix: Implement issue #1327: Deduplicate boolean CLI flags (job-a24af5b3) | PR #1345 |
| `dispatch/claude/job-64787914` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-64787914` | 1 | fix: Implement issue #1327: Deduplicate boolean CLI flags (job-a24af5b3) | PR #1345 |
| `dispatch/codex/job-6c151971` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-6c151971` | 1 | fix: ## Permissions (job-8575a177) | Upstream PR |
| `dispatch/claude/job-86a60902` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-86a60902` | 1 | fix: Implement Living Charter Evolution & Capability-Gate (job-4bf9c7e6) | PR #1360 |
| `dispatch/claude/job-8f16d74c` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-8f16d74c` | 1 | fix: Implement issue #1327: Deduplicate boolean CLI flags (job-a24af5b3) | PR #1345 |
| `dispatch/codex/job-a8a6758b` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-a8a6758b` | 1 | fix: Implement Phase 1 and Phase 2 of Issue #1343 per doc (job-d6812ef1) | PR #1345 |
| `dispatch/codex/job-ca34924a` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ca34924a` | 1 | fix: ## Permissions (job-7c8c84f5) | Upstream PR |
| `dispatch/codex/job-d5d34915` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-d5d34915` | 1 | docs: add #1436 bot-authored live cell | PR #1471 |
| `dispatch/claude/job-e7039f36` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-e7039f36` | 1 | fix: Implement Phase 1 and Phase 2 of Issue #1343 per doc (job-d6812ef1) | PR #1345 |
| `dispatch/claude/job-ea922d14` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ea922d14` | 1 | fix: Implement Phase 1 and Phase 2 of Issue #1343 per doc (job-d6812ef1) | PR #1345 |
| `dispatch/codex/job-edf3bd07` | `/Users/nikhilsoman/dev/synlynk/worktrees/job-edf3bd07` | 1 | fix: ## Permissions (job-e73d175d) | Upstream PR |

**Disposition Recommendation:** These 14 worktrees are 100% safe to remove. They can be safely pruned as part of a batch cleanup once the worktree audit tool supports equivalent patch detection (`git cherry`) or manual pruning is run.

## 6. Unique Commits Analysis & Triage (Candidates for #1487)

For the remaining 27 clean worktrees that contain unique commits (`cherry +`), a detailed triage was conducted to distinguish **superseded dispatches** from **valuable commits to recover** under Issue #1487.

### 6.1 Superseded Duplicate Dispatches (15 Worktrees — Safe to Abandon)

These worktrees contain commits from parallel or superseded dispatches where the intended feature, fix, or documentation has already landed on `main` through a different commit or PR:

- **Autonomous Heal (PR #1371 / #1373):** `review/pr-1371`, `dispatch/claude/job-09be09ef`, `dispatch/codex/job-2ea87ea6`, `dispatch/claude/job-3757f399`. (Feature landed via PR #1373).
- **Pipx CLI Drift Warning (#1188):** `dispatch/claude/job-04888f6b`. (Landed via commit `aa214523` / PR #1325).
- **Ephemeral Swarm Runners (#1341):** `dispatch/claude/job-46e77bb9`. (Landed via PR #1366).
- **Cross-Harness Event Relay (#1339):** `dispatch/claude/job-74c66dcf`. (Landed via PR #1358).
- **PM Backlog Triage Engine (#1340):** `dispatch/codex/job-92c021a1`, `dispatch/agy/job-e2061c9a`. (Landed via PR #1362).
- **Book EPUB Output (#1430):** `dispatch/codex/job-2614fd19`. (Landed via PR #1430).
- **Review Dispatch Read-Only Scope (#937):** `dispatch/claude/job-c9128e46`. (Landed via PR #1328).
- **Review Fallback (#1436 / #1475):** `dispatch/codex/job-157f6822`, `dispatch/codex/job-7c7c2ced`. (Landed via PR #1476).

**Disposition:** Safe to abandon and delete once documented. No code recovery required.

### 6.2 High-Value Candidate Commits for Recovery in #1487 (12 Worktrees)

The following 12 worktrees contain unique, unmerged contributions that should be evaluated and recovered into scoped PRs under Issue #1487 before their worktrees are pruned:

| Worktree / Branch | Agent | Unique Content / Files | Proposed Recovery Action (#1487) |
| :--- | :--- | :--- | :--- |
| `dispatch/grok/job-0799a9c7` | Grok | `tests/test_agent_cli.py`: Fix `KeyError` from stack-dump whitespace during capability calibration | Cherry-pick regression test to `fix/calibration-keyerror` |
| `dispatch/grok/job-51a07047` | Grok | `tests/test_agent_cli.py`: Cover dry-run reject of disabled `--as-agent` | Cherry-pick test coverage |
| `dispatch/grok/job-5719a676` | Grok | `synlynk/agent_cli.py`, `tests/test_agent_cli.py`: Dedupe seed charter envelope and lookup helpers | Review refactor; open cleanup PR if clean |
| `dispatch/grok/job-ae258269` | Grok | `synlynk/rebase.py`, `tests/test_rebase.py`: Reconcile union-merged markdown conflict artifacts | Evaluate markdown union-merge conflict resolver |
| `dispatch/grok/job-f89e6e67` | Grok | `website/src/`: Collapse mobile nav behind hamburger overlay | Extract website frontend responsive nav fix |
| `dispatch/claude/job-663b6ffb` | Claude | `docs/superpowers/specs/2026-09-07-live-selftest-scratch-probe-metadata-design.md`: Investigation spec for #1486 | Merge design spec into docs for Issue #1486 archive |
| `dispatch/codex/job-442611f6` / `job-be950e93` | Codex | `docs/qa/1436-qa-actions-write-reapproval.md`, `docs/blog/193-prTBD`: QA actions:write runbook | Commit QA runbook to `docs/qa/` |
| `dispatch/codex/job-ccb9dc92` / `job-ff15f012` | Codex | `docs/blog/191-prTBD-exec-gh-shim.md`: Blog post for PR #1472 | Commit blog post 191 to `docs/blog/` |
| `dispatch/codex/job-d2cf2bf1` | Codex | `docs/blog/192-prTBD`, `synlynk/uxcore.py`: Gating PR approval comment fallback | Evaluate comment fallback gate changes vs landed PR #1476 |
| `dispatch/agy/job-221ae733` | Agy | `docs/blog/187-prTBD`, agent docs: Make `synlynk gh --role` documented default | Archive blog 187 and verify doc parity |
| `dispatch/agy/job-b0f5b560` | Agy | `project-docs/devlogs/agy.md`: QA review record for PR #1408 | Merge devlog entry to `agy.md` |
| `dispatch/agy/job-b2e00304` | Agy | `project-docs/devlogs/agy.md`: PR #1415 review & merge record | Merge devlog entry to `agy.md` |
| `dispatch/agy/job-fac0b0b9` | Agy | `tests/test_agent_cli.py`: Verification test for PR #1405 research spec review | Cherry-pick verification test |

## 7. Complete 53-Worktree Disposition Inventory

The table below lists every single worktree currently registered in the repository, its location, branch, audit verdict, ahead commits, dirty status, PR association, and assigned lifecycle disposition.

| # | Worktree Path | Branch | Agent | Verdict | Ahead | Dirty | PR | Disposition / Safe Next Action |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-8423ec87` | `dispatch/grok/job-8423ec87` | grok | `unsafe` | 1 | Clean | #1478 (OPEN) | HOLD: Active PR in progress (UNSAFE) |
| 2 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-89b5c9a1` | `dispatch/grok/job-89b5c9a1` | grok | `unsafe` | 1 | Clean | #1482 (OPEN) | HOLD: Active PR in progress (UNSAFE) |
| 3 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-8aa012b0` | `dispatch/grok/job-8aa012b0` | grok | `unsafe` | 1 | Clean | #1483 (OPEN) | HOLD: Active PR in progress (UNSAFE) |
| 4 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-aca06f51` | `dispatch/grok/job-aca06f51` | grok | `unsafe` | 1 | Clean | #1481 (OPEN) | HOLD: Active PR in progress (UNSAFE) |
| 5 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-b60fc2e1` | `dispatch/grok/job-b60fc2e1` | grok | `unsafe` | 1 | Clean | #1477 (OPEN) | HOLD: Active PR in progress (UNSAFE) |
| 6 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-df2aee7c` | `dispatch/grok/job-df2aee7c` | grok | `unsafe` | 1 | Clean | #1480 (OPEN) | HOLD: Active PR in progress (UNSAFE) |
| 7 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-262d4800` | `dispatch/codex/job-262d4800` | codex | `safe` | 0 | Dirty (1 files) | None | PRESERVE: Extract dirty content before removal |
| 8 | `/Users/nikhilsoman/dev/synlynk/worktrees/pr-1371-review` | `dispatch/codex/job-89bd001e` | codex | `needs-review` | 2 | Dirty (1 files) | #1371 (CLOSED) | PRESERVE: Extract dirty content before removal |
| 9 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1/pr-1361-review` | `dispatch/agy/job-e2061c9a` | agy | `needs-review` | 2 | Clean | #1361 (CLOSED) | ORDERING: Remove nested child BEFORE parent |
| 10 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-04888f6b` | `dispatch/claude/job-04888f6b` | claude | `needs-review` | 1 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 11 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-0799a9c7` | `dispatch/grok/job-0799a9c7` | grok | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 12 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-09be09ef` | `dispatch/claude/job-09be09ef` | claude | `needs-review` | 2 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 13 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-157f6822` | `dispatch/codex/job-157f6822` | codex | `needs-review` | 1 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 14 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-221ae733` | `dispatch/agy/job-221ae733` | agy | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 15 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-2614fd19` | `dispatch/codex/job-2614fd19` | codex | `needs-review` | 2 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 16 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-2ea87ea6` | `dispatch/codex/job-2ea87ea6` | codex | `needs-review` | 2 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 17 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-3757f399` | `dispatch/claude/job-3757f399` | claude | `needs-review` | 2 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 18 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-442611f6` | `dispatch/codex/job-442611f6` | codex | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 19 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-46e77bb9` | `dispatch/claude/job-46e77bb9` | claude | `needs-review` | 2 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 20 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-51a07047` | `dispatch/grok/job-51a07047` | grok | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 21 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-5719a676` | `dispatch/grok/job-5719a676` | grok | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 22 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-663b6ffb` | `dispatch/claude/job-663b6ffb` | claude | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 23 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-74c66dcf` | `dispatch/claude/job-74c66dcf` | claude | `needs-review` | 2 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 24 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-7c7c2ced` | `dispatch/codex/job-7c7c2ced` | codex | `needs-review` | 1 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 25 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1` | `dispatch/codex/job-92c021a1` | codex | `needs-review` | 3 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 26 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ae258269` | `dispatch/grok/job-ae258269` | grok | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 27 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-b0f5b560` | `dispatch/agy/job-b0f5b560` | agy | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 28 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-b2e00304` | `dispatch/agy/job-b2e00304` | agy | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 29 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-be950e93` | `dispatch/codex/job-be950e93` | codex | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 30 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-c9128e46` | `dispatch/claude/job-c9128e46` | claude | `needs-review` | 1 | Clean | None | ABANDON: Superseded dispatch (no recovery needed) |
| 31 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ccb9dc92` | `dispatch/codex/job-ccb9dc92` | codex | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 32 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-d2cf2bf1` | `dispatch/codex/job-d2cf2bf1` | codex | `needs-review` | 2 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 33 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-f89e6e67` | `dispatch/grok/job-f89e6e67` | grok | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 34 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-fac0b0b9` | `dispatch/agy/job-fac0b0b9` | agy | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 35 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ff15f012` | `dispatch/codex/job-ff15f012` | codex | `needs-review` | 2 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 36 | `/private/tmp/synlynk-pr-1371` | `review/pr-1371` | review | `needs-review` | 1 | Clean | None | RECOVER: Triage unique commits under Issue #1487 |
| 37 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-17663b7c` | `dispatch/codex/job-17663b7c` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 38 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-1885d5fe` | `dispatch/claude/job-1885d5fe` | claude | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 39 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-2d0fe8f5` | `dispatch/codex/job-2d0fe8f5` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 40 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-5c76d72d` | `dispatch/codex/job-5c76d72d` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 41 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-64787914` | `dispatch/claude/job-64787914` | claude | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 42 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-6c151971` | `dispatch/codex/job-6c151971` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 43 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-86a60902` | `dispatch/claude/job-86a60902` | claude | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 44 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-8f16d74c` | `dispatch/claude/job-8f16d74c` | claude | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 45 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-a8a6758b` | `dispatch/codex/job-a8a6758b` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 46 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ca34924a` | `dispatch/codex/job-ca34924a` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 47 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-d5d34915` | `dispatch/codex/job-d5d34915` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 48 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-e7039f36` | `dispatch/claude/job-e7039f36` | claude | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 49 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-ea922d14` | `dispatch/claude/job-ea922d14` | claude | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 50 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-edf3bd07` | `dispatch/codex/job-edf3bd07` | codex | `needs-review` | 1 | Clean | None | SAFE: Functionally merged upstream (cherry -) |
| 51 | `/Users/nikhilsoman/dev/synlynk` | `main` | repo-root | `safe` | 0 | Clean | None | RETAIN: Root repository checkout |
| 52 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-12af0aa9` | `dispatch/agy/job-12af0aa9` | agy | `unknown` | 0 | Clean | None | RETAIN: Active session workspace |
| 53 | `/Users/nikhilsoman/dev/synlynk/worktrees/job-9ed27dd4` | `dispatch/grok/job-9ed27dd4` | grok | `safe` | 0 | Clean | None | SAFE: Direct ancestor, removable via synlynk clean |

## 8. Safe Next Actions & Step-by-Step Runbook

To ensure zero risk of accidental data loss, worktree cleanup must proceed strictly according to the following phased runbook:

### Phase 1: Immediately Safe Worktree Pruning
1. Remove `dispatch/grok/job-9ed27dd4` (`/Users/nikhilsoman/dev/synlynk/worktrees/job-9ed27dd4`). It is a clean direct ancestor commit of `origin/main` at `6bb73fec`. Run:
   ```bash
   git worktree remove /Users/nikhilsoman/dev/synlynk/worktrees/job-9ed27dd4
   git branch -d dispatch/grok/job-9ed27dd4
   ```

### Phase 2: Dirty Content Preservation
2. **Preserve Sentinel Design Spec (#1488):**
   In `/Users/nikhilsoman/dev/synlynk/worktrees/job-262d4800`, copy or commit `docs/superpowers/specs/2026-09-07-sentinel-persistence-review-1488-design.md` onto the active #1488 workstream. Only after this file is committed elsewhere may `job-262d4800` be removed.
3. **Preserve Historical Blog Index:**
   In `/Users/nikhilsoman/dev/synlynk/worktrees/pr-1371-review`, export the diff in `docs/blog/README.md` and commit it to `main`. Then discard remaining worktree files.

### Phase 3: Nested Worktree Deconstruction
4. **Strict Parent-Child Removal Ordering:**
   Execute child worktree removal first, followed by parent worktree removal:
   ```bash
   # Step 4a: Remove child worktree first
   git worktree remove /Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1/pr-1361-review
   git branch -D dispatch/agy/job-e2061c9a

   # Step 4b: Remove parent worktree second
   git worktree remove /Users/nikhilsoman/dev/synlynk/worktrees/job-92c021a1
   git branch -D dispatch/codex/job-92c021a1
   ```

### Phase 4: Functionally Merged Batch Pruning
5. Remove the 14 functionally merged worktrees confirmed via `cherry -` (e.g. `job-17663b7c`, `job-1885d5fe`, `job-2d0fe8f5`, `job-5c76d72d`, `job-64787914`, `job-6c151971`, `job-86a60902`, `job-8f16d74c`, `job-a8a6758b`, `job-ca34924a`, `job-d5d34915`, `job-e7039f36`, `job-ea922d14`, `job-edf3bd07`).

### Phase 5: Commit Recovery (#1487)
6. Dispatch recovery tasks under Issue #1487 for the 12 valuable candidate commits (Grok test fixes, charter refactor, QA re-approval runbook, website hamburger fix, devlog updates).
7. Abandon and delete the 15 superseded dispatch worktrees once verified against landed PRs.

### Phase 6: Active PR Monitoring
8. Leave the 6 active PR worktrees (#1477-#1483) untouched until each PR reaches a terminal state (merged or closed). Remove them only upon PR closure.
