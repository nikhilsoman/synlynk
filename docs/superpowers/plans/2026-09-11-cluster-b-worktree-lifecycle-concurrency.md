# Cluster B: Worktree Lifecycle & Rebase Concurrency — Implementation Plan

- **Spec:** `docs/superpowers/specs/2026-09-11-cluster-b-worktree-lifecycle-concurrency-design.md`
- **Branch:** `feat/agy/v0.20.0-cluster-b-worktrees`
- **Goal:** `goal-1d104154`, `goal-bf5af39f`, `goal-8f64eff5`
- **Milestone:** v0.20.0 Cluster B

---

## User Review Checkpoint
> [!IMPORTANT]
> This plan implements:
> 1. Adaptive Scope-Bounded Sparse Worktrees using `git sparse-checkout --cone` for `.synlynk/`, `project-docs/`, and task-scoped paths, reducing disk footprint by >70% and slashing creation latency.
> 2. Sibling Branch Auto-Pruning via `git cherry` patch-equivalence detection to clean up stacked branches upon PR squash-merges.
> 3. Multi-Task Lineage Tracking (`superseded_by`) in SQLite `jobs` and `stories` tables.
> 4. Deterministic Build Timestamp Freezing (`SOURCE_DATE_EPOCH`) injected into dispatch workers.

---

### Task 1: Adaptive Scope-Bounded Sparse Worktrees (`synlynk/worktree_sparse.py` & `synlynk/dispatch.py`)

**Files:**
- Create: `synlynk/worktree_sparse.py`
- Modify: `synlynk/dispatch.py`
- Create: `tests/test_worktree_sparse.py`

**Interfaces:**
- Produces: `create_sparse_cone_worktree(worktree_path, branch, base_sha, cone_dirs=None) -> bool`
- Produces: `ensure_path_in_sparse_cone(worktree_path, target_path) -> bool`
- Consumes: `git worktree add --no-checkout`, `git config extensions.worktreeConfig true`, `git sparse-checkout init --cone`

- [ ] **Step 1: Write the failing tests (`tests/test_worktree_sparse.py`)**
  - `test_create_sparse_cone_worktree_includes_mandatory_dirs()`
  - `test_ensure_path_in_sparse_cone_expands_set()`
  - `test_worktree_mode_fallback_on_unsupported_git()`
- [ ] **Step 2: Run tests to verify they fail**
  - Run: `pytest tests/test_worktree_sparse.py`
- [ ] **Step 3: Implement `synlynk/worktree_sparse.py`**
  - Implement cone initialization, mandatory directories (`.synlynk`, `project-docs`), and dynamic expansion.
- [ ] **Step 4: Wire into `synlynk/dispatch.py`**
  - In `_create_job_worktree`, inspect `config.get("worktree", {}).get("mode", "sparse")`.
  - When `"sparse"`, execute sparse cone checkout and fallback to full checkout if unsupported.
- [ ] **Step 5: Run tests to verify they pass**
  - Run: `pytest tests/test_worktree_sparse.py`
- [ ] **Step 6: Commit**
  - `git commit -m "feat(worktree): implement scope-bounded sparse worktree engine"`

---

### Task 2: Sibling Branch Auto-Pruning Engine (`synlynk/worktree_prune.py`)

**Files:**
- Create: `synlynk/worktree_prune.py`
- Modify: `synlynk/cli.py` & `synlynk/__init__.py`
- Create: `tests/test_worktree_prune.py`

**Interfaces:**
- Produces: `find_patch_equivalent_sibling_branches(root, target_branch="main") -> List[str]`
- Produces: `prune_sibling_branches(root, target_branch="main", dry_run=False) -> List[str]`
- Integrates with: `synlynk worktree clean`

- [ ] **Step 1: Write the failing tests (`tests/test_worktree_prune.py`)**
  - `test_detects_patch_equivalent_squashed_branches()`
  - `test_preserves_unmerged_or_dirty_branches()`
- [ ] **Step 2: Run tests to verify they fail**
  - Run: `pytest tests/test_worktree_prune.py`
- [ ] **Step 3: Implement `synlynk/worktree_prune.py`**
  - Use `git cherry` and `git merge-base` to detect patch equivalence.
  - Safely remove worktree registration and delete local/remote tracking branch.
- [ ] **Step 4: Wire into `cmd_worktree_clean()` in `synlynk/__init__.py`**
  - Add `--prune-siblings` flag or automatic invocation.
- [ ] **Step 5: Run tests to verify they pass**
  - Run: `pytest tests/test_worktree_prune.py`
- [ ] **Step 6: Commit**
  - `git commit -m "feat(worktree): add sibling branch auto-pruning engine"`

---

### Task 3: Multi-Task Lineage Tracking (`synlynk/lineage.py` & `state.db`)

**Files:**
- Create: `synlynk/lineage.py`
- Modify: `synlynk/state.py`
- Modify: `synlynk/jobs.py`
- Create: `tests/test_worktree_lineage.py`

**Interfaces:**
- Alters SQLite tables: `ALTER TABLE jobs ADD COLUMN superseded_by TEXT DEFAULT NULL;`
- Produces: `record_job_superseded(old_job_id: str, new_job_id: str, db_path: Optional[str] = None) -> bool`
- Produces: `get_job_lineage(job_id: str, db_path: Optional[str] = None) -> List[dict]`

- [ ] **Step 1: Write the failing tests (`tests/test_worktree_lineage.py`)**
  - `test_record_job_superseded_updates_schema_and_status()`
  - `test_superseded_jobs_excluded_from_zombies()`
- [ ] **Step 2: Run tests to verify they fail**
  - Run: `pytest tests/test_worktree_lineage.py`
- [ ] **Step 3: Implement schema migration and `synlynk/lineage.py`**
  - Add columns if missing in `state.py` initialization and migration routines.
  - Implement lineage recording and querying helpers.
- [ ] **Step 4: Update `synlynk/jobs.py`**
  - Mark superseded jobs in `synlynk jobs` list output with `superseded` status tag.
- [ ] **Step 5: Run tests to verify they pass**
  - Run: `pytest tests/test_worktree_lineage.py`
- [ ] **Step 6: Commit**
  - `git commit -m "feat(lineage): implement multi-task superseded_by lineage tracking"`

---

### Task 4: Deterministic Build Timestamp Freezing (`SOURCE_DATE_EPOCH`)

**Files:**
- Create: `tests/test_worktree_timestamp.py`
- Modify: `synlynk/dispatch.py`

**Interfaces:**
- Produces: `get_worktree_epoch(worktree_path: str) -> str`
- Injects: `os.environ["SOURCE_DATE_EPOCH"]` into agent dispatch execution subprocess.

- [ ] **Step 1: Write the failing test (`tests/test_worktree_timestamp.py`)**
  - `test_source_date_epoch_extracted_and_injected()`
- [ ] **Step 2: Run test to verify it fails**
  - Run: `pytest tests/test_worktree_timestamp.py`
- [ ] **Step 3: Implement timestamp resolution and environment injection in `synlynk/dispatch.py`**
- [ ] **Step 4: Run test to verify it passes**
  - Run: `pytest tests/test_worktree_timestamp.py`
- [ ] **Step 5: Commit**
  - `git commit -m "feat(worktree): inject SOURCE_DATE_EPOCH for deterministic builds"`

---

### Task 5: Full Verification, Documentation Sync, and PR Review

- [ ] **Step 1: Run full regression test suite**
  - Run: `pytest tests/test_worktree_sparse.py tests/test_worktree_prune.py tests/test_worktree_lineage.py tests/test_worktree_timestamp.py tests/test_release_marketing.py tests/test_viz*.py`
- [ ] **Step 2: Update 4-doc discipline (`roadmap.md`, `memory.md`, `costs.md`, `devlogs/agy.md`)**
- [ ] **Step 3: Open PR, dispatch QA review to Codex, and squash-merge into `main`**
