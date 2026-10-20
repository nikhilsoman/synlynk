# [LIVE-29] Autonomous daemon deep scan walks worktrees/ directory causing 100% CPU lockup and swap thrashing

**Declared:** 2026-10-20  
**Severity:** Sev1 — critical resource exhaustion, system instability  
**Tracking:** [#2477](https://github.com/nikhilsoman/synlynk/issues/2477), related headless crash [#2463](https://github.com/nikhilsoman/synlynk/issues/2463)  

## Summary

The `synlynk daemon` background process repeatedly pegged CPU at 100% (observed on PIDs 77496, 53210, 57483) and triggered severe memory and swap pressure, driving host system unresponsiveness and contributing to macOS watchdog timeout kernel panics.

Investigation confirmed that the autonomous daemon's periodic 60-second self-healing cycle runs a deep workspace scan (`run_workspace_scan(deep=True)`). Five parallel AST parsing stages walked the repository directory tree using `os.walk`. The traversal `skip_names` set included standard directories (`.git`, `node_modules`, `venv`, etc.) but omitted `worktrees`, `.worktrees`, and `.synlynk`. Because the repository maintains 50+ active agent and task git worktrees containing **264,367 Python files** (compared to only 684 files in the repository root — a 386x inflation), 5 parallel threads repeatedly walked and AST-parsed over a quarter-million files every minute.

In addition, a related failure mode (LIVE-28, #2463) in `compile_html_to_pdf` caused Chrome to abort (`TransformProcessType` SIGABRT) during background headless PDF generation due to legacy `--headless` flags and lack of an isolated `--user-data-dir`.

## Timeline and Containment

- **2026-10-19 / 2026-10-20**: Developer machines experienced severe sluggishness, pegged CPU fans, and a Darwin kernel panic (`watchdog timeout: no checkins from watchdogd in 94 seconds`).
- **Inspection**: Process table showed `python -m synlynk daemon run` consuming 100% CPU continuously across restarts (managed by `com.synlynk.daemon` launchd agent).
- **Sampling**: Stack traces confirmed threads blocked in AST parsing (`_scan_stage_source`, `_scan_stage_complexity`, `_scan_stage_tests`, `_scan_stage_arch`) inside `worktrees/job-*/synlynk/*.py`.
- **Containment**: Daemon was killed, orphaned GPG/scdaemon helpers pruned, and issue #2477 was declared with Sev1 / P0 priority.

## Root Cause Analysis

### 1. Incomplete Directory Exclusion in Scan Stages
In `synlynk/scan.py` (lines 634, 719, 784, 917, 1035), the scan stages defined:
```python
skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}
```
`"worktrees"`, `".worktrees"`, and `".synlynk"` were completely absent from this set, despite `_SCAN_SKIP_DIRS` elsewhere in `synlynk/scan.py` (line 1502) having already recognized them as non-production metadata directories.

### 2. Failure to Prune `os.walk` Subdirectories
The scan loops implemented filtering as:
```python
for dirpath, _, filenames in os.walk(root):
    if _should_skip(dirpath):
        continue
```
In Python's `os.walk(root)`, ignoring the second yield element (`dirnames`) means `os.walk` continues to recurse into all nested subdirectories. Even if `_should_skip(dirpath)` returns `True`, `os.walk` still traverses all 264,367 paths, executing filesystem stat operations and path splitting millions of times.

### 3. Rapid Autonomous Tick Rate
In `synlynk/daemon.py` (`_autonomous_tick`), `cmd_heal()` is invoked on a 60-second cycle. Because walking and AST-parsing 264,000 files took longer than 60 seconds under disk/CPU contention, the previous scan never rested before the next tick fired, keeping all CPU cores permanently saturated and generating enormous temporary object allocations in Python memory.

### 4. Headless Chrome WindowServer Collision (LIVE-28)
In `synlynk/release_marketing.py`, `compile_html_to_pdf` invoked Google Chrome using legacy `--headless` without `--headless=new`, `--no-sandbox`, or `--user-data-dir`. When launched in background or daemonized contexts without an active Aqua WindowServer connection, Chrome aborted with SIGABRT in `HIServices!TransformProcessType`.

## Impact

- Permanent 100% CPU pegging by the daemon process.
- 386x amplification of scanned files (264,367 vs 684).
- Memory churn leading to swap thrashing and watchdog daemon starvation.
- Intermittent SIGABRT crashes when marketing docs PDF generation was triggered.

## Corrective Actions

1. **Explicit Exclusion**: Added `"worktrees"`, `".worktrees"`, and `".synlynk"` to `skip_names` across all 5 scan stages (`_scan_stage_source`, `_scan_stage_complexity`, `_scan_stage_tests`, `_scan_stage_arch`, `_scan_stage_stack`) and `_count_files` in `synlynk/scan.py`.
2. **In-Place Pruning**: Modified `os.walk` loops to prune `dirnames[:] = [d for d in dirnames if d not in skip_names]`, completely halting recursion into worktree and cache subtrees at the top level.
3. **Exported Skip Set**: Centralized and exported `_SCAN_SKIP_NAMES` in `synlynk/scan.py`.
4. **Headless Chrome Modernization**: Updated `compile_html_to_pdf` in `synlynk/release_marketing.py` to use `--headless=new`, `--no-sandbox`, `--disable-gpu`, and an isolated `tempfile.TemporaryDirectory()` for `--user-data-dir`.
5. **Regression Verification**: Added unit tests in `tests/test_scan.py` and `tests/test_release_marketing.py` verifying directory skipping and command flags.

## Prevention Invariants

- **Invariant 1**: Every `os.walk` over a repository root must prune `dirnames[:]` in-place using `_SCAN_SKIP_NAMES` or `_SCAN_SKIP_DIRS`.
- **Invariant 2**: Git worktrees must never be treated as source files of the parent project repository.
- **Invariant 3**: Headless browser invocations must always specify `--headless=new` and an ephemeral isolated user profile directory.
