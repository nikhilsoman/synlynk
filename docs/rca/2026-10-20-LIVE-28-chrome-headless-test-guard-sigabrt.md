# [LIVE-28] Test-time Google Chrome GUI invocation in sandboxed review agent triggers HIServices TransformProcessType abort (SIGABRT)

**Declared:** 2026-10-20  
**Severity:** Sev2 — live test isolation defect, test execution flakiness in sandboxed harnesses, host crash dump pollution  
**Tracking:** [#2463](https://github.com/nikhilsoman/synlynk/issues/2463)  

## Summary

During review runs of dispatched agent jobs (e.g. Codex job `job-d564fcc4` executing `pytest tests/test_release_marketing.py`), multiple instances of `/Applications/Google Chrome.app` were spawned simultaneously (PIDs 9847, 9849, 9851, 9853, 9855). Each spawned process terminated immediately with `SIGABRT` (`Abort trap: 6`) inside `HIServices!___RegisterApplication_block_invoke` via `TransformProcessType`.

The crash reports (`/Library/Logs/DiagnosticReports/Google Chrome_*.ips`) showed:
```
Triggered by Thread: 0, Dispatch Queue: com.apple.main-thread
Exception Type:    EXC_CRASH (SIGABRT)
Termination Reason: Namespace SIGNAL, Code 6, Abort trap: 6
Application Specific Information: abort() called

Thread 0 Crashed:: Dispatch queue: com.apple.main-thread
0   libsystem_kernel.dylib         0x198b91650 __pthread_kill + 8
1   libsystem_pthread.dylib        0x198bcd97c pthread_kill + 296
2   libsystem_c.dylib              0x198ad0458 abort + 148
3   HIServices                     0x1a01f4b80 ___RegisterApplication_block_invoke + 12752
4   libdispatch.dylib              0x198a265a0 _dispatch_client_callout + 16
5   libdispatch.dylib              0x198a0f624 _dispatch_once_callout + 32
6   HIServices                     0x1a01c5994 _RegisterApplication + 164
7   HIServices                     0x1a01cab70 TransformProcessType + 112
8   Google Chrome Framework        0x13b10136c ChromeMain + 137332652
9   Google Chrome Framework        0x13b100f0c ChromeMain + 137331532
10  Google Chrome Framework        0x132e08f4c ChromeMain + 908
11  Google Chrome                  0x1044b0810 main + 200
```

## Root Cause Analysis

### 1. `execute_release_ceremony` Ignored `skip_build` for PDF & EPUB Compilation
In `synlynk/release_marketing.py` (lines 407-425), `execute_release_ceremony()` accepts a `skip_build: bool = False` parameter intended to allow dry-run and lightweight verification workflows to bypass heavy asset builds:
```python
    # 3. PDF compilation
    pdfs_compiled: List[str] = []
    try:
        pdfs_compiled = compile_docs_pdfs(root=root, dry_run=dry_run)
    except Exception as exc:
        errors.append(f"PDF compilation failed: {exc}")

    # 4. EPUB compilation
    epub_compiled: Optional[str] = None
    try:
        epub_compiled = compile_book_epub(root=root, dry_run=dry_run)
    except Exception as exc:
        errors.append(f"EPUB compilation failed: {exc}")

    # 5. Mirror PDF and EPUB assets to website
    try:
        mirror_docs_pdfs_to_website(root=root, dry_run=dry_run)
    except Exception as exc:
        errors.append(f"PDF/EPUB mirroring failed: {exc}")
```
While Step 7 (`verify_website_build`) checked `if not dry_run and not skip_build:`, Steps 3, 4, and 5 completely ignored `skip_build`.

### 2. Live Unit Tests Executed Unmocked Host Chrome
In `tests/test_release_marketing.py`:
- `test_execute_release_ceremony_live` invoked `execute_release_ceremony(..., dry_run=False, skip_build=True)`.
- `test_cmd_marketing_ceremony_cli` invoked `cmd_marketing_ceremony(..., dry_run=False, skip_build=True)`.

Because `dry_run` was `False` and `skip_build` was ignored for Step 3, `compile_docs_pdfs` located the host's installed `/Applications/Google Chrome.app` via `find_chrome_binary()` and executed `compile_html_to_pdf()` for all 3 HTML documentation files in `docs/` and the book HTML in `docs/book/`.

### 3. macOS Sandboxed Review Harness WindowServer Constraint
On macOS, `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` is built as an AppKit GUI application bundle. Its startup path in `ChromeMain` unconditionally calls `HIServices!_RegisterApplication` and `TransformProcessType` to establish a connection with the macOS WindowServer.

When an autonomous review agent runs under an isolated seatbelt sandbox (e.g. Codex running with restricted seatbelt profiles or non-GUI dispatch worktrees), Mach port lookups to `com.apple.windowserver.active`, `com.apple.coreservices.launchservicesd`, and `MachPortRendezvousServer` are blocked by sandbox policy. When `_RegisterApplication` encounters this denial, HIServices calls `abort()`, generating SIGABRT and writing `.ips` crash logs to `/Library/Logs/DiagnosticReports/`.

## Impact

- Spurious Chrome crash logs (`Google Chrome_*.ips`) generated during automated test runs.
- Potential test flakiness and hangs in sandboxed CI or agent environments.
- Violation of unit test hermeticity (unit tests spawning real GUI applications on the host machine).

## Corrective Actions

1. **Honor `skip_build` Across All Compilation Steps:**
   Updated `execute_release_ceremony()` in `synlynk/release_marketing.py` so that Step 3 (`compile_docs_pdfs`), Step 4 (`compile_book_epub`), and Step 5 (`mirror_docs_pdfs_to_website`) are guarded by `if not skip_build:`.

2. **Hermetic Test-Time Guard in `compile_html_to_pdf`:**
   Added a fail-safe check in `compile_html_to_pdf()`:
   ```python
   if "PYTEST_CURRENT_TEST" in os.environ and not os.environ.get("SYNLYNK_ALLOW_LIVE_BROWSER"):
       if getattr(subprocess.run, "__module__", None) == "subprocess":
           return False
   ```
   If a test does not mock `subprocess.run`, `compile_html_to_pdf` safely rejects launching host GUI Chrome binaries without crashing.

3. **Regression Tests:**
   - Added `test_execute_release_ceremony_respects_skip_build` in `tests/test_release_marketing.py` verifying that when `skip_build=True`, `compile_docs_pdfs`, `compile_book_epub`, and `mirror_docs_pdfs_to_website` are never invoked.
   - Added `test_compile_html_to_pdf_unmocked_under_pytest_is_safely_blocked` verifying that unmocked invocations under pytest return `False` safely.
   - Verified that `test_execute_release_ceremony_live` expects empty `pdfs_compiled` and `epub_compiled` when `skip_build=True`.

## Prevention Invariants

- **Invariant 1**: Unit test suites must never launch host GUI browser processes directly. All browser invocations in unit tests must be mocked or use hermetic dry-run flags.
- **Invariant 2**: Any high-level ceremony or pipeline command accepting `skip_build=True` must bypass all compilation and asset-generation subroutines.
