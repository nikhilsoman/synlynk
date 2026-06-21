---
title: "Post v0.9.0 — The Gap Between Shipping and Working"
date: 2026-06-22
series: "Building the OS for Multi-Agent Development"
post: 20
pr: "hotfix — 3 commits to main"
merged: 2026-06-22
---

## The Broader Goal at the End of PR #53

PR #53 shipped v0.9.0 — the kernel hardening release. The package split moved ~4700 lines from `bin/synlynk.py` into a proper `synlynk/` package. Scoped dispatch context, per-agent prompt framing, Ed25519 signing, anti-gaming quality caps, and the package structure were all locked in. The stated next goal was v0.9.1: `synlynk relay join` onboarding and the community-first relay model.

We had 365 passing tests. We felt good about the state of the code.

## The Strategic Shift: Dogfooding Reveals Production Gaps

The morning after shipping v0.9.0, we ran `synlynk init` in `rxcc` — a separate, mature repo. Two things broke immediately.

This is not a v0.9.1 feature post. It's a gap post. The gaps mattered enough to fix before moving forward because they revealed something important: **synlynk had only ever been used inside its own repo**. The moment it was used in the wild, the seams showed.

Neither gap was theoretical. Both were reproducible in under 30 seconds. Both would have confused every agent that ran `synlynk init` in any non-synlynk repo.

---

## What Broke and Why

### Gap 1: `ModuleNotFoundError: No module named 'synlynk'`

The install script (`install.sh`) copies `bin/synlynk.py` to `~/.synlynk/bin/synlynk`. Before the v0.9.0 package split, that file contained the entire application — self-contained, zero dependencies. After the split, `bin/synlynk.py` became a 5-line shim:

```python
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from synlynk import main
if __name__ == "__main__":
    main()
```

The `sys.path.insert` line resolves to `parent(parent(__file__))`. In the dev repo that's `~/dev/synlynk/` — which contains the `synlynk/` package. But when installed to `~/.synlynk/bin/synlynk`, the same path arithmetic resolves to `~/.synlynk/` — which has no `synlynk` package. The shim was never updated for its new deployment context.

**The fix:**
- `install.sh` now copies the `synlynk/` package to `~/.synlynk/lib/synlynk/` alongside the shim
- For curl installs (no local repo), downloads `synlynk/__init__.py` directly
- Patches the installed shim's sys.path line from the dev-repo-relative path to `os.path.expanduser("~/.synlynk/lib")`
- The installed `~/.synlynk/bin/synlynk` was also patched immediately so existing installs worked without reinstalling

### Gap 2: `synlynk init` Was Blind to Existing Docs

`rxcc` already had `roadmap.md`, `todo.md`, and a `rxcc_memory.md` at the repo root — hundreds of entries of real project history. Running `synlynk init` created a fresh `project-docs/` directory with blank skeleton files generated from git commit topics.

AGY (running in rxcc) saw two sets of project docs: the real ones at root, and the blank ones in `project-docs/`. It correctly diagnosed the conflict and proposed symlinks to reconcile them. The user declined the destructive command and asked why.

The answer was that `synlynk init` had only ever been run on the synlynk repo itself, where `project-docs/` didn't exist yet. It had no detection logic for pre-existing project documentation in any other location.

This was the more important gap. An OS for multi-agent development that corrupts context on first run in any mature repo is not ready for use beyond its own development.

---

## What Was Shipped

### Fix 1: Configurable `project_docs_dir`

All ~35 hardcoded `"project-docs/"` strings in `synlynk/__init__.py` were replaced with calls to a new `_docs_dir()` helper:

```python
def _docs_dir() -> str:
    config_file = ".synlynk/config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                return json.load(f).get("project_docs_dir", "project-docs")
        except (json.JSONDecodeError, IOError):
            pass
    return "project-docs"
```

`load_config()` defaults now include `"project_docs_dir": "project-docs"` so all existing repos are unaffected. A new `--docs-dir` flag on `synlynk init` writes the setting to `.synlynk/config.json` before any file creation happens:

```bash
synlynk init --docs-dir .   # keeps docs at repo root
```

All functions that previously read from a hardcoded path — `generate_context()`, `checkpoint()`, `parse_costs_md()`, `update_costs()`, `get_mode()`, `_deep_scan()` — now read from `_docs_dir()` at call time.

### Fix 2: `_find_existing_doc()` — Doc Migration on Init

`_write_informed_skeleton()` was rewritten to search for existing doc content before generating from git history. A new `_find_existing_doc(basename, target_dir, project_name)` helper runs the search:

```python
candidates = []
if target_dir not in (".", ""):
    candidates.append(basename)                         # root level
if target_dir != "project-docs":
    candidates.append(os.path.join("project-docs", basename))
# Project-prefixed variants: rxcc_memory.md, rxcc-memory.md
stem, ext = os.path.splitext(basename)
if slug:
    candidates += [f"{slug}_{stem}{ext}", f"{slug}-{stem}{ext}"]
```

First candidate with >200 bytes wins. The content is copied verbatim to the target path. The `init` output now tells you exactly what happened:

```
Step 3/6 — Bootstrapping ./
  ✓ ./roadmap.md  (migrated from project-docs/roadmap.md)
  ✓ ./memory.md   (migrated from project-docs/memory.md)
  ✓ ./todo.md     (migrated from project-docs/todo.md)
```

vs the fallback on a genuinely new repo:

```
  ✓ project-docs/roadmap.md  (generated from git history)
```

Blank skeletons from git history are now the last resort, not the default.

---

## Brainstorm Visuals Used

None for this post — these were hotfixes identified through direct usage, not a designed feature. The invisible-state spec (`docs/superpowers/specs/2026-06-21-invisible-state-design.md`) and its brainstorm visuals (`docs/brainstorm/invisible-state/`) are related in that both address how project docs are discovered, owned, and migrated — but they weren't consulted for these specific fixes.

---

## What This Achieved on the Path to Autonomy

**Agents can now init themselves correctly in any mature repo.**

Before these fixes, running `synlynk init` in a repo with existing docs produced a corrupted context: two sets of docs pointing at different states, with agents unable to know which was authoritative. The symlink workaround AGY proposed was reasonable but brittle — git doesn't track symlink targets, CI environments break them, and the underlying indexing problem remained.

After these fixes:
- The installed binary works regardless of where it's installed
- `synlynk init --docs-dir .` correctly defers to the repo's existing convention
- `synlynk init --force` on a mature repo reads existing docs and migrates them rather than overwriting with blank templates

This is foundational for the relay and workspace tiers in the invisible-state design. Before you can sync project state across teammates, the state needs to be correctly initialised on each machine. A broken init undermines every downstream feature.

**The meta-lesson:** synlynk was built and tested exclusively within its own repo until v0.9.0 shipped. The instant it ran in `rxcc`, two gaps appeared that 365 tests hadn't caught — because those tests ran in a controlled environment where `project-docs/` was always the expected location and the installed binary was never tested separately from the dev repo. Dogfooding in a real external project revealed what the test suite couldn't.

---

## Strategic Note: The Goal at the End of This Post

The install-time and init-time gaps are closed. synlynk can now be reliably initialised in any repo regardless of where its existing docs live.

The invisible-state spec (`docs/superpowers/specs/2026-06-21-invisible-state-design.md`) is written and awaiting user review. It addresses the deeper version of this problem: why should project docs be in git at all, and what does the path to local SQLite state + relay sync look like?

The immediate next goalpost remains v0.9.1 — but the init hardening work here is also a stepping stone to `synlynk migrate`, which the invisible-state spec describes as the one-time migration from `project-docs/` to `~/.synlynk/projects/<hash>/state.db`. The `_find_existing_doc()` logic written in this post will be reused there.
