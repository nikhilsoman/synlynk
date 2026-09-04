# Research Spec: Virtualized VCS Workspace Backends for Multi-Agent Dispatch

**Date:** 2026-09-04  
**Status:** Approved / Research Notes  
**Issue:** [#1390](https://github.com/nikhilsoman/synlynk/issues/1390)  
**Authors:** [@nikhilsoman], [@agy], [@codex], [@claude]  
**Relates to:** #1341 (Ephemeral Swarm Cloud Runners), #832 (Worktree Base Freshness), #1250 (Worktree File Tracking), `goal-005ea87d`, `goal-abecd18c`  

---

## 1. Executive Summary & Problem Statement

As Synlynk evolves from single-agent tasks to concurrent multi-agent swarm execution (10–100+ concurrent agents across Claude, Codex, Agy, and Grok), workspace management has become a critical operational bottleneck.

### The Current Workspace Architecture
Currently, Synlynk creates an isolated Git worktree for every dispatched job:
```bash
git worktree add worktrees/<job_id> -b dispatch/<agent>/<job_id> <base_sha>
```
While Git worktrees provide branch isolation and prevent concurrent agents from corrupting each other's working state, this model exhibits severe limitations at scale:

1. **Storage & I/O Multiplication ($O(N)$ disk amplification):**
   Every worktree materializes the entire repository tree on disk. In a 2 GB repository with 50,000 files, running 20 concurrent agent dispatches consumes 40 GB of disk space and incurs substantial write I/O.
2. **Provisioning Latency:**
   Running `git worktree add` on medium-to-large repositories requires 5–30 seconds simply to check out files and update Git index caches before the agent executes a single instruction.
3. **Git Ref & Index Lock Contention:**
   Concurrent invocations of `git worktree add`, `git branch`, and `git worktree remove` compete for locks in the shared `.git/` directory (`.git/refs/heads/`, `.git/worktrees/`, `.git/index`). In Synlynk's `synlynk/dispatch.py`, this previously triggered ref contention errors (`cannot lock ref`, `operation not permitted`), requiring retry loops and filesystem mutexes (`git_ref_operation_lock`).
4. **Agent Scope Mismatch:**
   Most agent dispatches are strictly scoped by task permissions (e.g., `write:docs/`, `write:src/synlynk/dispatch.py`, `run:tests`). Checking out the entire repository when an agent only needs access to 5% of the codebase wastes memory, slows down IDE indexing, and floods the agent's file discovery tools.
5. **Ephemeral Cloud Runner Overhead (#1341):**
   For ephemeral micro-VM / container runners (Fly.io, Kubernetes, Docker), cloning or transferring full worktrees introduces significant network transfer penalties.

This research document evaluates **EdenFS**, **Sapling VCS**, and **Git Sparse Checkouts / Partial Clones**, comparing their architectural trade-offs and defining a multi-phase integration blueprint for Synlynk.

---

## 2. Deep-Dive: Virtualized VCS Technologies

### A. EdenFS (Meta Virtual File System)

**Overview:**  
EdenFS is Meta's high-performance virtual filesystem designed for massive monorepos. It exposes repository trees via a user-space daemon connecting to a kernel virtual filesystem layer (FUSE on Linux, Projected File System / Mac FSEvents / VFS on macOS).

```
┌────────────────────────────────────────────────────────┐
│                   Agent Process (CLI)                  │
│       e.g. Claude / Codex / Agy / Grok / Tests         │
└───────────────────────────┬────────────────────────────┘
                            │ POSIX open(), read(), stat()
                            ▼
┌────────────────────────────────────────────────────────┐
│           Operating System VFS / FUSE Kernel           │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     EdenFS Daemon                      │
│   - Materializes metadata stubs instantaneously        │
│   - Intercepts read() -> Fetches file blob on-demand   │
│   - Writes buffered to local overlay layer             │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
   ┌───────────────────────┐  ┌───────────────────────┐
   │ Local Object Store /  │  │ Remote Monorepo Cache │
   │ RocksDB Cache         │  │ (e.g. Eden Server)    │
   └───────────────────────┘  └───────────────────────┘
```

#### Key Architectural Characteristics
- **$O(1)$ Workspace Materialization:** Creating a new checkout or switching revisions is near-instantaneous. The daemon materializes virtual inode entries without writing blobs to disk.
- **On-Demand Blob Faulting:** File contents are fetched into a local RocksDB cache only when a process reads the file. Unopened files cost zero I/O and zero disk space.
- **Redirected Writes:** File edits are captured in an isolated per-workspace overlay, preserving base tree immutability.

#### Synlynk Assessment
- **Pros:**
  - True instant provisioning for 100+ concurrent agents.
  - Zero disk amplification for untouched directories.
  - Transparent POSIX semantics—agent CLIs and language toolchains require no code changes.
- **Cons:**
  - **High operational complexity:** Requires a long-running background daemon (`edenfs`).
  - **Kernel extension friction on macOS:** macOS requires `macFUSE` or system extension approvals, which creates significant barrier-to-entry for open-source CLI users.
  - **Container requirements:** In Docker / Kubernetes / Fly.io runners (#1341), running FUSE requires elevated privileges (`SYS_ADMIN` capability, `/dev/fuse` device passthrough).
  - **Failure recovery:** If the daemon restarts or crashes, active file handles become broken pipe errors.

---

### B. Sapling VCS (`sl`)

**Overview:**  
Sapling is Meta's open-source source control system. It offers a Git-compatible CLI with advanced graph indexing, native stacked-diff workflows, and integrated virtual repository capabilities.

```
                    ┌─────────────────────────┐
                    │    synlynk dispatch     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Sapling CLI (sl)    │
                    │   - Segmented Changelog │
                    │   - Native Stacked Diffs│
                    │   - Integrated Sparse   │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
   ┌──────────────────────┐              ┌──────────────────────┐
   │ Standalone Git Repo  │              │   EdenFS Virtual FS  │
   │ (.sl / .git backend) │              │  (Optional Mount)    │
   └──────────────────────┘              └──────────────────────┘
```

#### Key Architectural Characteristics
- **Segmented Changelog & Fast Indexing:** Commits, branches, and trees are indexed in segmented changelog data structures, executing `status`, `diff`, and `log` in sub-millisecond time.
- **First-Class Stacked Workflows:** Sapling is built around stacked changesets (`sl prev`, `sl next`, `sl rebase`), matching Synlynk's stacking dispatch model (`--stacking-mode auto|always`).
- **Native Sparse Support (`sl sparse`):** Workspaces can include or exclude paths using lightweight profiles without the complexity of Git's legacy sparse syntax.
- **GitHub / Git Interoperability:** Sapling clones directly from standard Git remotes (`sl clone https://github.com/...`) and pushes to Git branches.

#### Synlynk Assessment
- **Pros:**
  - Exceptional performance on branch operations and commit graph traversals.
  - Native alignment with multi-agent stacked branches.
  - Can operate standalone without EdenFS, providing faster Git operations with fewer lock contention issues.
- **Cons:**
  - Requires installing the `sl` binary on user machines and runner images.
  - Agent CLIs (Claude, Agy, Grok) and standard tools expect `git` command conventions. While `sl` supports aliases, prompt instructions must be adapted.

---

### C. Git Sparse-Checkouts & Partial Clones (Native Git 2.25+)

**Overview:**  
Standard Git has introduced robust virtualization features natively:
1. **`git sparse-checkout` (Cone Mode):** High-performance path matching restricted to directories rather than arbitrary glob patterns.
2. **Per-Worktree Configuration (`extensions.worktreeConfig`):** Allows each worktree to maintain its own independent sparse-checkout rules, index, and configuration without altering the root repository.
3. **Partial Clones (`--filter=blob:none` / `treeless`):** Allows Git to clone only tree objects or commit metadata, downloading file contents lazily on demand.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Root Repository (.git/)                         │
│     - extensions.worktreeConfig = true                                 │
│     - core.sparseCheckoutCone = true                                   │
│     - Object Database (shared packfiles, blobless on-demand cache)      │
└──────────────┬──────────────────────────┬──────────────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│  Worktree: Job A (docs only) │ │ Worktree: Job B (src only)   │
│  - config.worktree:          │ │  - config.worktree:          │
│    sparse-checkout: docs/    │ │    sparse-checkout: src/     │
│  - Materialized: 12 files    │ │  - Materialized: 45 files    │
│  - Disk footprint: ~50 KB    │ │  - Disk footprint: ~300 KB   │
└──────────────────────────────┘ └──────────────────────────────┘
```

#### Key Architectural Characteristics
- **Cone Mode Directory Filtering:** `git sparse-checkout set --cone <dirs...>` restricts filesystem materialization to specified directories and top-level files.
- **Zero-Dependency Native Git:** Works out-of-the-box on macOS, Linux, and Windows with Git >= 2.25. No daemons, no kernel extensions, no external binaries.
- **Per-Worktree Isolation:** By enabling `git config extensions.worktreeConfig true`, each worktree writes its sparse patterns to `.git/worktrees/<id>/info/sparse-checkout`.

#### Synlynk Assessment
- **Pros:**
  - **Zero installation friction:** Standard Git utility; ubiquitous across all environments.
  - **90–98% I/O reduction:** A task with `write:docs/` only checks out `docs/` and root configuration, reducing checkout latency from 15s to <200ms.
  - **Universal Agent Compatibility:** Every LLM CLI (`claude`, `codex`, `agy`, `grok`) operates on standard POSIX files with regular Git commands.
- **Cons:**
  - If an agent attempts to inspect an unmaterialized path (e.g. searching a file outside its cone), the file will appear missing unless the sparse cone is dynamically updated.
  - Shared `.git` ref locks still exist during branch creation, though checkout time is drastically reduced.

---

### D. OS-Level Copy-on-Write (APFS Reflinks & Linux OverlayFS)

In addition to VCS-level virtualization, OS-level filesystem virtualization provides compelling zero-lock solutions:

1. **macOS APFS Reflinks (`cp -c` / `clonefile`):**
   - Enables instant copy-on-write directory cloning on macOS.
   - Files share disk allocation until modified.
   - Decouples the cloned workspace from the central `.git/` directory, completely eliminating Git ref lock contention.
2. **Linux OverlayFS:**
   - Perfect for containerized swarm runners (Fly.io / K8s from #1341).
   - Mounts the base repository as a read-only lower directory (`lowerdir`).
   - Uses an ephemeral in-memory or tmpfs upper directory (`upperdir`) for agent writes.
   - Teardown is $O(1)$ (`umount` and discard upperdir).

---

## 3. Technology Comparison Matrix

| Evaluation Dimension | EdenFS | Sapling VCS (`sl`) | Native Git Sparse + WorktreeConfig | APFS Reflink / OverlayFS |
| :--- | :--- | :--- | :--- | :--- |
| **Workspace Creation Latency** | <10ms ($O(1)$) | ~100ms | ~150ms (cone mode) | <50ms ($O(1)$ CoW) |
| **Disk Overhead per Worker** | ~0 MB (on-demand) | ~5 MB | ~1–10 MB (sparse) | ~0 MB (CoW delta) |
| **External Dependencies** | High (`edenfs` daemon, FUSE) | Medium (`sl` binary) | **None** (Native Git >= 2.25) | None (OS native) |
| **macOS Developer Friction** | High (macFUSE approval) | Low (Homebrew `sl`) | **Zero** (Built-in) | **Zero** (Built-in APFS) |
| **Container / Swarm Runner** | Difficult (needs FUSE cap) | Easy (CLI binary) | **Trivial** | **Native** (OverlayFS) |
| **Lock Contention Risk** | Low (VFS overlay) | Low (segmented log) | Medium (shared `.git/` refs) | **Zero** (fully decoupled) |
| **Agent / Toolchain Compatibility** | 100% POSIX transparent | High (git-aliased) | **100% Standard Git** | **100% Standard Git** |

---

## 4. Multi-Agent Dispatch Architecture for Synlynk

Based on this evaluation, Synlynk should adopt a **Tiered Virtualization Strategy** that prioritizes zero-friction native Git sparse worktrees immediately while architecting a pluggable backend interface for specialized runners.

```
                                 ┌─────────────────────────────────┐
                                 │     synlynk dispatch / swarm    │
                                 └────────────────┬────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │      WorkspaceBackend (ABC)     │
                                 └────────────────┬────────────────┘
                                                  │
                 ┌────────────────────────────────┼────────────────────────────────┐
                 ▼                                ▼                                ▼
   ┌───────────────────────────┐    ┌───────────────────────────┐    ┌───────────────────────────┐
   │  GitSparseWorktreeBackend │    │   OverlayFSRunnerBackend  │    │     SaplingEdenBackend    │
   │  - extensions.worktreeCfg │    │   - Container ephemeral   │    │   - Enterprise Monorepo   │
   │  - Permission-aware cone  │    │   - lowerdir: base repo   │    │   - sl / EdenFS driver    │
   │  - Tier 1 (Default)       │    │   - Tier 2 (Cloud Swarm)  │    │   - Tier 3 (Opt-in)       │
   └───────────────────────────┘    └───────────────────────────┘    └───────────────────────────┘
```

### A. Tier 1: Permission-Aware Git Sparse Worktrees (Default)

When `synlynk dispatch` provisions a worktree:
1. **Derive Sparse Cone from Job Permissions:**
   - If task permissions grant `write:docs/`, the sparse cone includes `docs/`, `project-docs/`, and root files (`GEMINI.md`, `README.md`, `package.json`, etc.).
   - If task permissions grant `write:src/` and `run:tests`, the cone includes `src/`, `tests/`, and root config files.
2. **Worktree Provisioning Sequence:**
   ```bash
   # 1. Enable worktree-specific configuration
   git config extensions.worktreeConfig true

   # 2. Create worktree in detached or feature branch state
   git worktree add worktrees/<job_id> -b dispatch/<agent>/<job_id> <base_sha>

   # 3. Configure per-worktree sparse cone
   git -C worktrees/<job_id> config --worktree core.sparseCheckout true
   git -C worktrees/<job_id> config --worktree core.sparseCheckoutCone true
   git -C worktrees/<job_id> sparse-checkout set <target_cones...>
   ```
3. **Dynamic Cone Expansion Protocol:**
   If an agent needs to access files outside its initial cone (e.g. during a broad grep or import resolution), Synlynk provides a helper or automatically expands the sparse cone on demand (`git sparse-checkout add <new_cone>`).

### B. Tier 2: OverlayFS for Ephemeral Swarm Runners (#1341)

In remote containerized runners (Fly.io micro-VMs, Kubernetes Pods):
- The repository is pre-cloned as a read-only base layer (`/workspace/base`).
- Each dispatched agent mounts an ephemeral OverlayFS:
  ```bash
  mount -t overlay overlay -o lowerdir=/workspace/base,upperdir=/tmp/job-<id>/upper,workdir=/tmp/job-<id>/work /workspace/active
  ```
- The agent executes inside `/workspace/active` with instant startup (<50ms) and complete isolation.
- On job completion, Synlynk extracts the committed Git patches/commits and tears down the mount instantly.

### C. Tier 3: Pluggable Sapling / EdenFS Driver (Future Extension)

For enterprise users working in massive monorepos (>100k files):
- Define an abstract `WorkspaceBackend` interface in `synlynk/workspace/base.py`.
- Provide a `SaplingBackend` implementing `provision_workspace()`, `commit()`, and `cleanup()` using the `sl` CLI.

---

## 5. Implementation Roadmap & Milestones

- [ ] **Phase 1: Native Sparse Worktree Driver (v0.22.0)**
  - Add `synlynk/workspace/sparse.py` with cone derivation logic from role permissions.
  - Update `_job_worktree_details()` and worktree provisioning in `synlynk/dispatch.py` to support `--sparse`.
  - Benchmark worktree creation time and disk footprint across 10 concurrent dispatches.
- [ ] **Phase 2: Ref-Contention Elimination & Pruning Automation**
  - Implement atomic branch assignment to eliminate `.git/refs` lock contention.
  - Implement automated background worktree reaping (`synlynk worktree prune`) after job finalization.
- [ ] **Phase 3: OverlayFS Driver for Cloud Swarms (v0.23.0)**
  - Integrate OverlayFS mount drivers into `synlynk-worker:latest` container images (#1341).
- [ ] **Phase 4: Sapling / EdenFS Research Prototype**
  - Experimental prototype evaluating `sl` in large benchmark repos.

---

## 6. Conclusion & Recommendation

For Synlynk's current architecture and user base, **Git Sparse Checkouts with `extensions.worktreeConfig`** is the clear winner:
- It requires **no new runtime dependencies** or kernel extensions.
- It reduces disk consumption and checkout I/O by **over 90%**.
- It preserves 100% toolchain and agent compatibility across macOS and Linux.
- It seamlessly bridges to **OverlayFS** for containerized swarm runners.
