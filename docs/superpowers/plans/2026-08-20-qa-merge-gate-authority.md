# qa Delegated Merge-Gate Authority (Block-Only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give qa's CI/CD-health charter (§3.2 of the agent-roles-charters spec) a real enforcement mechanism — a `qa_gate_mode="block-only"` gate that can block a PR merge on red CI or an unresolved sentinel alert, surfaced through `synlynk pr check` and backstopped by a GitHub branch-protection required check. Architect keeps sole merge authority.

**Architecture:** A new `synlynk/qa_gate.py` module computes a single fail-closed verdict from two signals — CI matrix status (reusing the existing `_extract_verified_by_ci` helper in `synlynk/sentinel.py`) and open Support-Engineer-filed sentinel issues (queried live via `gh issue list`, not a local `sentinel.md` file — see Task 1's note on why). `cmd_pr_check()` in `synlynk/db.py` calls it and blocks (exit 1) on red. A new thin CLI subcommand `synlynk pr gate-status` exposes just the verdict for a dedicated CI job (`.github/workflows/qa-gate.yml`), which becomes the context name a GitHub branch-protection required check points at.

**Tech Stack:** Python 3.8+ stdlib, `subprocess` + `gh` CLI (existing pattern throughout the codebase), pytest, GitHub Actions, GitHub REST API via `gh api`.

**Stacking:** Each PR branches off the previous PR's branch (not off `main`), so review/merge order is fixed and each PR is reviewable independently once its parent has landed. Branch names:

```
docs/qa-merge-gate-authority-design (already merged as spec, PR #1079)
  └─ feat/qa-gate-verdict-module        (Task 1 — PR A)
       └─ feat/qa-gate-pr-check-integration  (Task 2 — PR B)
            └─ feat/qa-gate-ci-workflow       (Task 3 — PR C)
                 └─ chore/qa-gate-branch-protection  (Task 4 — PR D)
```

---

## Task 1: Gate verdict module (`synlynk/qa_gate.py`)

**PR:** A — `feat/qa-gate-verdict-module`, branched from `main` (spec already merged into `main` via PR #1079).
**Dispatch target:** Codex (qa role's test/refactor lane — pure-Python logic + tests, no infra).

**Design note (grounds this in the actual repo, corrects a spec-level ambiguity):** The spec (§3) says the gate should check "no unresolved sentinel alert... per the Support Engineer's existing telemetry monitoring." The obvious-looking source, `.synlynk/sentinel.md`, is **gitignored** (`.gitignore` line 2: `.synlynk/*` with no `!.synlynk/sentinel.md` exception) and is regenerated fresh inside each Support Engineer CI run (`.github/workflows/support-engineer.yml`), which never commits it back. A PR's own CI checkout will never have a populated `sentinel.md` — reading that file from a `qa pr gate-status` CI job would silently always report "no alerts," defeating the gate. The actual durable, cross-context signal is what Support Engineer does with a finding once it has one: `_file_gh_issue()` in `synlynk/support_engineer.py` (line 487) files it as a GitHub issue with `--label "bug,support-engineer"` and title `[support] {finding['type']}: {finding['summary'][:80]}`. Querying open GitHub issues is available identically whether `synlynk pr check` runs on a developer's machine or inside a fresh GitHub Actions checkout (same `gh` CLI, same auth), so that's the signal this task uses instead.

**Files:**
- Create: `synlynk/qa_gate.py`
- Test: `tests/test_qa_gate.py`

- [ ] **Step 1: Write the failing tests for `_qa_gate_ci_status`**

```python
# tests/test_qa_gate.py
from unittest.mock import patch

from synlynk.qa_gate import (
    _qa_gate_ci_status,
    _qa_gate_sentinel_health,
    qa_gate_verdict,
)


def test_qa_gate_ci_status_green_when_ci_passes():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=True):
        assert _qa_gate_ci_status() is True


def test_qa_gate_ci_status_red_when_ci_fails():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=False):
        assert _qa_gate_ci_status() is False


def test_qa_gate_ci_status_none_when_undeterminable():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=None):
        assert _qa_gate_ci_status() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -v`
Expected: `ModuleNotFoundError: No module named 'synlynk.qa_gate'` (all 3 fail)

- [ ] **Step 3: Write `_qa_gate_ci_status`**

```python
# synlynk/qa_gate.py
"""qa delegated merge-gate authority (block-only mode).

Computes a fail-closed gate verdict from two signals: CI matrix status and
open Support-Engineer-filed sentinel-alert issues. See
docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md.
"""

import json
import subprocess
from typing import Optional

from synlynk.sentinel import _extract_verified_by_ci


def _qa_gate_ci_status(worktree_path=None, worktree_branch=None) -> Optional[bool]:
    """True/False/None (undeterminable) CI matrix status for the active branch."""
    return _extract_verified_by_ci(
        worktree_path=worktree_path, worktree_branch=worktree_branch
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -v`
Expected: the 3 `_qa_gate_ci_status` tests PASS; the sentinel/verdict tests still fail (not written yet)

- [ ] **Step 5: Commit**

```bash
git add synlynk/qa_gate.py tests/test_qa_gate.py
git commit -m "feat: qa gate CI-status signal (reuses _extract_verified_by_ci)"
```

- [ ] **Step 6: Write the failing tests for `_qa_gate_sentinel_health`**

```python
# tests/test_qa_gate.py (append)

_SENTINEL_ISSUES_HIGH = json.dumps([
    {"title": "[support] sentinel_alerts: ⚠ FLATLINE: 3 consecutive exec failures", "number": 501},
])
_SENTINEL_ISSUES_MEDIUM_ONLY = json.dumps([
    {"title": "[support] sentinel_alerts: ⚠ slow response time observed", "number": 502},
])
_SENTINEL_ISSUES_NONE = json.dumps([])
_SENTINEL_ISSUES_UNRELATED = json.dumps([
    {"title": "[support] telemetry_anomaly: high failure rate", "number": 503},
])


def _mock_gh_issue_list(stdout, returncode=0):
    result = type("Result", (), {"returncode": returncode, "stdout": stdout, "stderr": ""})()
    return result


def test_qa_gate_sentinel_health_red_on_high_severity_open_issue():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_HIGH)):
        assert _qa_gate_sentinel_health("owner", "repo") is False


def test_qa_gate_sentinel_health_green_on_medium_only():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_MEDIUM_ONLY)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_green_on_no_open_issues():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_NONE)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_ignores_unrelated_support_issues():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_UNRELATED)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_none_when_gh_errors():
    with patch("subprocess.run", return_value=_mock_gh_issue_list("", returncode=1)):
        assert _qa_gate_sentinel_health("owner", "repo") is None


def test_qa_gate_sentinel_health_none_on_malformed_json():
    with patch("subprocess.run", return_value=_mock_gh_issue_list("not json")):
        assert _qa_gate_sentinel_health("owner", "repo") is None
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -v`
Expected: the 6 new tests FAIL with `ImportError` / `AttributeError` (`_qa_gate_sentinel_health` not defined)

- [ ] **Step 8: Write `_qa_gate_sentinel_health`**

```python
# synlynk/qa_gate.py (append)

_HIGH_SEVERITY_MARKERS = ("FLATLINE", "QUOTA_EXHAUSTED", "CRITICAL")


def _qa_gate_sentinel_health(owner: str, repo: str) -> Optional[bool]:
    """True (healthy) / False (unhealthy) / None (undeterminable).

    Queries open GitHub issues Support Engineer files for sentinel alerts
    (synlynk/support_engineer.py:_file_gh_issue, title prefix
    "[support] sentinel_alerts:") rather than reading .synlynk/sentinel.md,
    which is gitignored and never persists across CI runs.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", f"{owner}/{repo}",
                "--label", "support-engineer",
                "--state", "open",
                "--json", "title,number",
                "--limit", "100",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if result.returncode != 0:
        return None

    try:
        issues = json.loads((result.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(issues, list):
        return None

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        title = str(issue.get("title") or "")
        if "sentinel_alerts" not in title:
            continue
        upper = title.upper()
        if any(marker in upper for marker in _HIGH_SEVERITY_MARKERS):
            return False
    return True
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -v`
Expected: all 9 tests so far PASS

- [ ] **Step 10: Commit**

```bash
git add synlynk/qa_gate.py tests/test_qa_gate.py
git commit -m "feat: qa gate sentinel-health signal (queries open support-engineer issues)"
```

- [ ] **Step 11: Write the failing tests for `qa_gate_verdict` (the fail-closed combiner)**

```python
# tests/test_qa_gate.py (append)

def test_qa_gate_verdict_green_when_both_signals_healthy():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "green"
    assert verdict["ci_status"] is True
    assert verdict["sentinel_status"] is True


def test_qa_gate_verdict_red_when_ci_fails():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=False), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "CI" in verdict["reason"]


def test_qa_gate_verdict_red_when_sentinel_unhealthy():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=False):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "sentinel" in verdict["reason"].lower()


def test_qa_gate_verdict_fails_closed_when_ci_status_undeterminable():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=None), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "undeterminable" in verdict["reason"].lower()


def test_qa_gate_verdict_fails_closed_when_sentinel_status_undeterminable():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=None):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "undeterminable" in verdict["reason"].lower()
```

- [ ] **Step 12: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -v`
Expected: the 5 new tests FAIL (`qa_gate_verdict` not defined)

- [ ] **Step 13: Write `qa_gate_verdict`**

```python
# synlynk/qa_gate.py (append)

def qa_gate_verdict(owner: str, repo: str, worktree_path=None, worktree_branch=None) -> dict:
    """Combines CI status + sentinel health into one fail-closed verdict.

    Returns {"verdict": "green"|"red", "ci_status": bool|None,
             "sentinel_status": bool|None, "reason": str}.
    Any undeterminable signal (None) is treated as red, not skipped —
    see docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md §3.
    """
    ci_status = _qa_gate_ci_status(worktree_path=worktree_path, worktree_branch=worktree_branch)
    sentinel_status = _qa_gate_sentinel_health(owner, repo)

    if ci_status is None:
        reason = "CI status undeterminable — failing closed"
    elif sentinel_status is None:
        reason = "sentinel health undeterminable — failing closed"
    elif ci_status is False:
        reason = "CI matrix is red"
    elif sentinel_status is False:
        reason = "unresolved high-severity sentinel alert open"
    else:
        reason = "CI green, no unresolved sentinel alert"

    verdict = "green" if (ci_status is True and sentinel_status is True) else "red"
    return {
        "verdict": verdict,
        "ci_status": ci_status,
        "sentinel_status": sentinel_status,
        "reason": reason,
    }
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -v`
Expected: all 14 tests PASS

- [ ] **Step 15: Commit**

```bash
git add synlynk/qa_gate.py tests/test_qa_gate.py
git commit -m "feat: qa_gate_verdict — fail-closed combiner for CI + sentinel signals"
```

## Task 1b: `qa_gate_mode` config field

**Same PR (A) — continues on `feat/qa-gate-verdict-module`.**

**Files:**
- Modify: `synlynk/__init__.py:1624-1682` (`load_config`)
- Test: `tests/test_qa_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_qa_gate.py (append)
import synlynk


def test_load_config_defaults_qa_gate_mode_to_block_only(project_dir):
    config = synlynk.load_config()
    assert config["qa_gate_mode"] == "block-only"


def test_load_config_preserves_explicit_qa_gate_mode(project_dir):
    import json
    config_path = project_dir / ".synlynk" / "config.json"
    existing = json.loads(config_path.read_text()) if config_path.exists() else {}
    existing["qa_gate_mode"] = "block-only"
    config_path.write_text(json.dumps(existing))
    config = synlynk.load_config()
    assert config["qa_gate_mode"] == "block-only"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -k qa_gate_mode -v`
Expected: `KeyError: 'qa_gate_mode'` on both

- [ ] **Step 3: Add the default field**

In `synlynk/__init__.py`, inside `load_config()`'s `defaults` dict (line 1627), add one line after `"story_classification": {"method": "heuristic"},` (line 1655):

```python
        "story_classification": {"method": "heuristic"},
        "qa_gate_mode": "block-only",
```

No merge-loop changes needed — `qa_gate_mode` is a flat scalar key, and the existing `for key, val in defaults.items(): if key not in config: config[key] = val` loop (lines 1663-1665) already handles it, the same way `"dispatch_mode"` and other flat keys are handled.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -k qa_gate_mode -v`
Expected: both PASS

- [ ] **Step 5: Run the full qa_gate test file**

Run: `pytest tests/test_qa_gate.py -v`
Expected: all 16 tests PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_qa_gate.py
git commit -m "feat: add qa_gate_mode config field, default block-only"
```

- [ ] **Step 7: Push and open PR A**

```bash
git push -u origin feat/qa-gate-verdict-module
gh pr create --base main --title "feat: qa gate verdict module (block-only mode)" --body "$(cat <<'EOF'
## Summary
- New synlynk/qa_gate.py: qa_gate_verdict() combines CI matrix status (reuses
  synlynk.sentinel._extract_verified_by_ci) and sentinel health (queries open
  GitHub issues Support Engineer files, not .synlynk/sentinel.md — that file
  is gitignored and never persists into a PR's CI checkout)
- Fail-closed: any undeterminable signal is treated as red
- New qa_gate_mode config field, default "block-only" (spec section 5 — other
  modes not implemented, out of scope per spec section 8)

Part of the stacked PR sequence implementing
docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md (PR #1079).
This PR only adds the verdict-computation module; nothing calls it yet
(Task 2, next PR in the stack, wires it into synlynk pr check).

## Test plan
- [ ] pytest tests/test_qa_gate.py -v — all pass
- [ ] Full suite: pytest tests/ -q
EOF
)"
```

---

## Task 2: Wire the verdict into `synlynk pr check`

**PR:** B — `feat/qa-gate-pr-check-integration`, branched from PR A's branch (`feat/qa-gate-verdict-module`), **not** from `main`.
**Dispatch target:** Codex (same file family as Task 1, qa's test/refactor lane).

**Files:**
- Modify: `synlynk/db.py:2982-3043` (`cmd_pr_check`)
- Test: `tests/test_pr_check.py`

- [ ] **Step 1: Create the stacked branch**

```bash
git checkout feat/qa-gate-verdict-module
git checkout -b feat/qa-gate-pr-check-integration
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_pr_check.py (append)
import pytest
from unittest.mock import patch


def test_pr_check_blocks_on_red_qa_gate(project_dir):
    from synlynk.db import cmd_pr_check
    red_verdict = {
        "verdict": "red", "ci_status": False, "sentinel_status": True,
        "reason": "CI matrix is red",
    }
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=True), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value=red_verdict), \
         patch("synlynk.pr_multiplier._current_pr_number", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_check()
    assert exc_info.value.code == 1


def test_pr_check_passes_on_green_qa_gate(project_dir, capsys):
    from synlynk.db import cmd_pr_check
    green_verdict = {
        "verdict": "green", "ci_status": True, "sentinel_status": True,
        "reason": "CI green, no unresolved sentinel alert",
    }
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=True), \
         patch("synlynk.db.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.db.qa_gate_verdict", return_value=green_verdict), \
         patch("synlynk.pr_multiplier._current_pr_number", return_value=None):
        cmd_pr_check()
    captured = capsys.readouterr()
    assert "qa gate" in captured.out.lower()


def test_pr_check_skips_qa_gate_off_github_remote(project_dir, capsys):
    from synlynk.db import cmd_pr_check
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()
    captured = capsys.readouterr()
    assert "qa gate" not in captured.out.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pr_check.py -v`
Expected: `test_pr_check_blocks_on_red_qa_gate` and `test_pr_check_passes_on_green_qa_gate` FAIL — no `SystemExit` raised / no "qa gate" text printed. `test_pr_check_skips_qa_gate_off_github_remote` PASSES already (nothing new runs off-GitHub yet) — that's expected, it documents current behavior before the change.

- [ ] **Step 4: Wire the gate into `cmd_pr_check`**

In `synlynk/db.py`, add the import near the existing local imports inside `cmd_pr_check` (line 2987-2993):

```python
def cmd_pr_check() -> None:
    """Hard-blocks merge if any capability_ratings row has model_version='unknown'
    or if qa's block-only merge gate is red (CI matrix or sentinel health).

    Exit code 1 if blocked. Exit code 0 if clean.
    """
    from synlynk import _GREEN, _RESET, _get_db, detect_remote_owner_repo
    from synlynk.pr_multiplier import (
        _apply_review_cycle_multiplier,
        _current_pr_number,
        _is_github_remote,
    )
    from synlynk.sentinel import _extract_pr_review_cycles
    from synlynk.qa_gate import qa_gate_verdict
```

Then insert the gate check right after the existing `_is_github_remote()` block (after line 3007, before `rows = conn.execute(...)` at line 3009):

```python
    conn = _get_db()
    if _is_github_remote():
        pr_number = _current_pr_number()
        if pr_number is not None:
            changes_requested_count = _extract_pr_review_cycles() or 0
            _apply_review_cycle_multiplier(conn, pr_number, changes_requested_count)

        owner, repo = detect_remote_owner_repo()
        if owner and repo:
            gate = qa_gate_verdict(owner, repo)
            if gate["verdict"] == "red":
                conn.close()
                print(f"\n  🚫 [PR CHECK BLOCKED] qa gate is red: {gate['reason']}")
                print("  This is qa's block-only merge gate (CI matrix + sentinel health).")
                print("  See docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md\n")
                raise SystemExit(1)
            print(f"  {_GREEN}✓{_RESET} qa gate green — {gate['reason']}")
```

Note: `conn` is reused later in the function (the `capability_ratings` query at line 3009), so only `conn.close()` early in the red-gate branch, not in the green path — the existing `conn` stays open for the rest of the function exactly as before.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pr_check.py -v`
Expected: all 3 new tests PASS, plus the 3 pre-existing tests in this file still PASS (they patch `_is_github_remote` to `False`, so they never touch the new code path)

- [ ] **Step 6: Run the full pr_check + capability_scoring + db test files (existing coverage for this function)**

Run: `pytest tests/test_pr_check.py tests/test_capability_scoring.py tests/test_db.py -v`
Expected: all PASS — `test_pr_check_blocks_on_unknown_model` and `test_pr_check_passes_when_all_models_known` in `test_capability_scoring.py` (lines 636, 654) don't patch `qa_gate_verdict`, so verify they still pass; if they fail because `_is_github_remote` isn't patched to `False` in those tests, that's a pre-existing gap this task didn't introduce — read those two tests first and only touch them if they break under `_is_github_remote() == True` with no `detect_remote_owner_repo` mock (patch `synlynk.db.detect_remote_owner_repo` to return `(None, None)` in that case to keep them exercising only the unknown-model check, unchanged from before)

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py tests/test_pr_check.py
git commit -m "feat: wire qa_gate_verdict into synlynk pr check (block-only)"
```

- [ ] **Step 8: Push and open PR B**

```bash
git push -u origin feat/qa-gate-pr-check-integration
gh pr create --base feat/qa-gate-verdict-module --title "feat: wire qa gate verdict into synlynk pr check" --body "$(cat <<'EOF'
## Summary
- synlynk pr check now calls qa_gate_verdict() when on a GitHub remote and
  blocks (exit 1) if the gate is red — printed reason names the failing
  signal (CI matrix vs sentinel health vs undeterminable/fail-closed)
- Green gate prints a one-line confirmation alongside the existing
  unattested-model-version check output

Stacked on #<PR-A-number> (qa gate verdict module) — this PR is the "authoring
surface" half of spec section 4's two-layer enforcement; Task 3 (next PR)
adds the CI-job half.

## Test plan
- [ ] pytest tests/test_pr_check.py tests/test_capability_scoring.py tests/test_db.py -v
- [ ] Full suite: pytest tests/ -q
EOF
)"
```

---

## Task 3: `synlynk pr gate-status` CLI subcommand + CI workflow job

**PR:** C — `feat/qa-gate-ci-workflow`, branched from PR B's branch (`feat/qa-gate-pr-check-integration`).
**Dispatch target:** Grok (qa's infra/CI-CD lane).

**Why a separate subcommand instead of reusing `synlynk pr check` as the required-check job:** `synlynk pr check` also runs the unattested-model-version check and the devlog-fork soft-warn (`cmd_audit_docs`), both of which need local DB state (`capability_ratings`, devlog files) that a bare `actions/checkout` in a fresh CI runner won't have populated the way a developer's machine does. Branch protection needs a check that's meaningful to run from a clean checkout on every PR. A dedicated subcommand keeps the required check scoped to exactly the two gate signals (§3-4 of the spec), decoupled from the rest of `pr check`'s local-state-dependent behavior.

**Files:**
- Modify: `synlynk/cli.py:881-883` (`pr` subparser)
- Modify: `synlynk/cli.py:1381-1383` (`pr` command dispatch)
- Create: `synlynk/qa_gate.py` (add `cmd_pr_gate_status`)
- Create: `.github/workflows/qa-gate.yml`
- Test: `tests/test_qa_gate.py`

- [ ] **Step 1: Create the stacked branch**

```bash
git checkout feat/qa-gate-pr-check-integration
git checkout -b feat/qa-gate-ci-workflow
```

- [ ] **Step 2: Write the failing test for the new command function**

```python
# tests/test_qa_gate.py (append)

def test_cmd_pr_gate_status_exits_zero_on_green(capsys):
    from synlynk.qa_gate import cmd_pr_gate_status
    green_verdict = {
        "verdict": "green", "ci_status": True, "sentinel_status": True,
        "reason": "CI green, no unresolved sentinel alert",
    }
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.qa_gate.qa_gate_verdict", return_value=green_verdict):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "green" in captured.out.lower()


def test_cmd_pr_gate_status_exits_one_on_red(capsys):
    from synlynk.qa_gate import cmd_pr_gate_status
    red_verdict = {
        "verdict": "red", "ci_status": False, "sentinel_status": True,
        "reason": "CI matrix is red",
    }
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.qa_gate.qa_gate_verdict", return_value=red_verdict):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "red" in captured.out.lower()


def test_cmd_pr_gate_status_exits_one_when_remote_undetectable(capsys):
    from synlynk.qa_gate import cmd_pr_gate_status
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=(None, None)):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 1
```

- [ ] **Step 3: Add `import pytest` at the top of the test file if not already present**

Check `tests/test_qa_gate.py`'s existing imports (Task 1, Step 1) — add `import pytest` alongside `from unittest.mock import patch` if it isn't already there.

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -k gate_status -v`
Expected: `ImportError: cannot import name 'cmd_pr_gate_status'`

- [ ] **Step 5: Write `cmd_pr_gate_status`**

```python
# synlynk/qa_gate.py (append)

from synlynk import detect_remote_owner_repo


def cmd_pr_gate_status() -> None:
    """Thin CLI entry point for the qa block-only gate, scoped for CI.

    Unlike `synlynk pr check`, this only computes qa_gate_verdict() — no
    local DB state, no devlog audit. This is what the qa-gate GitHub Actions
    job runs, and its exit code is what a branch-protection required check
    on that job name enforces.
    """
    owner, repo = detect_remote_owner_repo()
    if not owner or not repo:
        print("  🚫 [qa gate] could not determine GitHub owner/repo — failing closed")
        raise SystemExit(1)

    verdict = qa_gate_verdict(owner, repo)
    if verdict["verdict"] == "red":
        print(f"  🚫 [qa gate] RED — {verdict['reason']}")
        raise SystemExit(1)
    print(f"  ✓ [qa gate] GREEN — {verdict['reason']}")
    raise SystemExit(0)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -k gate_status -v`
Expected: all 3 PASS

- [ ] **Step 7: Wire the CLI subcommand**

In `synlynk/cli.py`, modify the `pr` subparser (line 881-883):

```python
    pr_parser = subparsers.add_parser("pr", help="PR workflow commands")
    pr_sub = pr_parser.add_subparsers(dest="pr_action")
    pr_sub.add_parser("check", help="Block PR if model versions are unattested")
    pr_sub.add_parser("gate-status", help="qa block-only merge gate (CI matrix + sentinel health)")
```

And the dispatch (line 1381-1383):

```python
    elif args.command == "pr":
        if args.pr_action == "check":
            cmd_pr_check()
        elif args.pr_action == "gate-status":
            from synlynk.qa_gate import cmd_pr_gate_status
            cmd_pr_gate_status()
```

- [ ] **Step 8: Write a CLI-level test**

```python
# tests/test_qa_gate.py (append)

def test_cli_pr_gate_status_invokes_cmd(monkeypatch):
    import sys
    from synlynk import cli

    called = {}

    def fake_cmd():
        called["ran"] = True
        raise SystemExit(0)

    monkeypatch.setattr("synlynk.qa_gate.cmd_pr_gate_status", fake_cmd)
    monkeypatch.setattr(sys, "argv", ["synlynk", "pr", "gate-status"])
    with pytest.raises(SystemExit):
        cli.main()
    assert called.get("ran") is True
```

Run: `pytest tests/test_qa_gate.py -k cli_pr_gate_status -v` first to confirm it fails (patches the wrong import path before the wiring lands — expected to fail with `called` never set, since `cli.py`'s dispatch does a local `from synlynk.qa_gate import cmd_pr_gate_status` — monkeypatch the module attribute, not a `cli`-local name), then re-run after Step 7's wiring is in place.

Expected after Step 7: PASS.

- [ ] **Step 9: Create the CI workflow**

```yaml
# .github/workflows/qa-gate.yml
name: qa-gate

on:
  pull_request:
    branches: [main]

jobs:
  qa-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Run qa block-only merge gate
        run: python3 bin/synlynk.py pr gate-status
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Note: `GH_TOKEN` is required because `qa_gate_verdict` shells out to the `gh` CLI (both `_extract_verified_by_ci`'s `gh pr checks`/`gh run list` calls and `_qa_gate_sentinel_health`'s `gh issue list` call) — `gh` reads `GH_TOKEN` from the environment when not interactively logged in, which is the standard pattern GitHub Actions runners use (the built-in `GITHUB_TOKEN` secret has `issues: read` and `checks: read` by default on public repos; no new permissions/secrets need provisioning).

- [ ] **Step 10: Run the full test file**

Run: `pytest tests/test_qa_gate.py -v`
Expected: all tests (16 from Task 1 + this task's new ones) PASS

- [ ] **Step 11: Commit**

```bash
git add synlynk/qa_gate.py synlynk/cli.py tests/test_qa_gate.py .github/workflows/qa-gate.yml
git commit -m "feat: synlynk pr gate-status CLI command + qa-gate CI workflow job"
```

- [ ] **Step 12: Push and open PR C**

```bash
git push -u origin feat/qa-gate-ci-workflow
gh pr create --base feat/qa-gate-pr-check-integration --title "feat: qa-gate CI workflow job (branch-protection backstop, half 2 of 2)" --body "$(cat <<'EOF'
## Summary
- New `synlynk pr gate-status` CLI subcommand — thin wrapper around
  qa_gate_verdict(), scoped for a clean CI checkout (no local DB/devlog
  state dependency, unlike the rest of `synlynk pr check`)
- New .github/workflows/qa-gate.yml — runs on every PR into main, job name
  `qa-gate`, exits non-zero on a red gate

This is the "backstop" half of spec section 4's two-layer enforcement (PR B,
stacked below this one, is the "authoring surface" half via `synlynk pr
check`). The job produced here — context name `qa-gate` — is what Task 4
(next PR) points a branch-protection required check at. This PR does NOT
touch branch protection itself; the job exists and is visible on PRs, but
nothing requires it to pass yet.

Stacked on #<PR-B-number>.

## Test plan
- [ ] pytest tests/test_qa_gate.py -v
- [ ] Full suite: pytest tests/ -q
- [ ] After merge: confirm the qa-gate job actually appears and runs on the
      next real PR (visible via `gh pr checks <N>`), before Task 4 makes it
      required
EOF
)"
```

---

## Task 4: Branch-protection required-check wiring

**PR:** D — `chore/qa-gate-branch-protection`, branched from PR C's branch (`feat/qa-gate-ci-workflow`).
**Dispatch target:** Grok drafts the script and documents the exact command (infra lane). **The actual branch-protection API call must NOT be executed autonomously** — modifying `main`'s branch-protection rules is a repo security-configuration change, which this project's own risk framework treats as hard-to-reverse and requiring explicit human confirmation before execution, the same category as CI/CD pipeline changes. Grok's job is to produce and test the script in dry-run form; running it for real is an architect/Claude action gated on Nikhil's go-ahead, done in a follow-up turn after this PR merges — not a step in this PR's own CI or dispatch.

**Files:**
- Create: `scripts/apply_qa_gate_branch_protection.sh`
- Modify: `docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md` (append an "Applied" note once run for real — this edit happens in the follow-up turn, not in this PR)

- [ ] **Step 1: Create the stacked branch**

```bash
git checkout feat/qa-gate-ci-workflow
git checkout -b chore/qa-gate-branch-protection
```

- [ ] **Step 2: Read current branch protection so the script only adds, never overwrites**

```bash
gh api repos/nikhilsoman/synlynk/branches/main/protection --jq '.required_status_checks.contexts' 2>&1
```

Expected output today: the existing required contexts, most likely including `test (3.8)`, `test (3.10)`, `test (3.12)` (the matrix jobs from `.github/workflows/test.yml`) if branch protection is already configured, or a 404 if no protection rule exists yet on `main`. Record whichever it is — the script in Step 3 must read this live, not hardcode an assumed prior state, since a hardcoded list would silently clobber any other required checks added between this plan being written and being run.

- [ ] **Step 3: Write the script**

```bash
#!/usr/bin/env bash
# scripts/apply_qa_gate_branch_protection.sh
#
# Adds "qa-gate" (the job from .github/workflows/qa-gate.yml) to main's
# required status checks, without touching any other existing protection
# settings. Read-modify-write: fetches current contexts live, appends
# "qa-gate" if not already present, PUTs the merged list back.
#
# This script does not run itself in CI or via dispatch — per
# docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md,
# applying it is an explicit, human-confirmed action.
set -euo pipefail

REPO="nikhilsoman/synlynk"

echo "Current required status checks on main:"
CURRENT=$(gh api "repos/${REPO}/branches/main/protection/required_status_checks" \
  --jq '.contexts' 2>/dev/null || echo "[]")
echo "$CURRENT"

if echo "$CURRENT" | grep -q '"qa-gate"'; then
  echo "qa-gate is already a required check. Nothing to do."
  exit 0
fi

NEW_CONTEXTS=$(echo "$CURRENT" | python3 -c "
import json, sys
contexts = json.load(sys.stdin)
if 'qa-gate' not in contexts:
    contexts.append('qa-gate')
print(json.dumps(contexts))
")

echo "New required status checks (adding qa-gate):"
echo "$NEW_CONTEXTS"

read -p "Apply this to main's branch protection? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ]; then
  echo "Aborted — no changes made."
  exit 1
fi

gh api "repos/${REPO}/branches/main/protection/required_status_checks" \
  --method PATCH \
  --field strict=true \
  --field "contexts[]=qa-gate" \
  -f "contexts[]=$(echo "$NEW_CONTEXTS" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)))' | sed 's/,/ --field contexts[]=/g')"

echo "Applied. Verify with:"
echo "  gh api repos/${REPO}/branches/main/protection/required_status_checks --jq '.contexts'"
```

- [ ] **Step 4: Test the script against the live repo in read-only/dry-run form**

Run: `bash scripts/apply_qa_gate_branch_protection.sh` and answer `N` at the confirmation prompt. Verify:
- It prints the current required contexts without error (or `[]` / a 404-safe empty list if none configured)
- It correctly detects `qa-gate` is not yet present
- It computes and prints the new contexts list including `qa-gate`
- Answering `N` exits 1 without modifying anything — confirm via `gh api repos/nikhilsoman/synlynk/branches/main/protection/required_status_checks --jq '.contexts'` unchanged

This step is where a dispatched Grok job's work stops — it validates the script is correct and safe, but does not answer `y`.

- [ ] **Step 5: Make the script executable and commit**

```bash
chmod +x scripts/apply_qa_gate_branch_protection.sh
git add scripts/apply_qa_gate_branch_protection.sh
git commit -m "chore: script to add qa-gate to main's required status checks (not yet applied)"
```

- [ ] **Step 6: Push and open PR D**

```bash
git push -u origin chore/qa-gate-branch-protection
gh pr create --base feat/qa-gate-ci-workflow --title "chore: branch-protection script for qa-gate required check (not applied yet)" --body "$(cat <<'EOF'
## Summary
- Read-modify-write script that adds "qa-gate" (job from PR C /
  .github/workflows/qa-gate.yml) to main's required status checks, without
  clobbering any existing required contexts
- Script prompts for interactive confirmation before making any change and
  defaults to abort

## IMPORTANT — this PR does not change branch protection
Per the spec's own framing and this project's risk-handling conventions,
modifying main's branch-protection rules is a repo security-configuration
change requiring explicit human confirmation — it is not something a
dispatched job runs unattended. This PR only adds and validates the script
in dry-run form (confirmation prompt answered "N"). Running it for real
against main is a follow-up action for Nikhil/architect to explicitly
approve and execute after this PR merges, at which point the design spec
gets a short "Applied: <date>" note appended (out of scope for this PR's own
diff).

Stacked on #<PR-C-number>. This is the last PR in the qa-merge-gate-authority
stack — spec sections 3, 4, and 5's default value are now fully implemented
end to end once this merges (branch protection is applied as a manual
follow-up, not blocked by anything left to build).

## Test plan
- [ ] Script run manually, confirmation answered "N", no changes made,
      verified via `gh api .../branches/main/protection/required_status_checks`
- [ ] Full suite unaffected (no Python changes in this PR):
      pytest tests/ -q
EOF
)"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md`):
- §2 (block, don't merge) — Task 2 only blocks (`raise SystemExit(1)`), never calls any merge API. ✓
- §3 (gate verdict: CI matrix + sentinel health, fail-closed) — Task 1's `qa_gate_verdict`. ✓ (sentinel-health source corrected from the spec's implied `sentinel.md` to open GitHub issues, documented as a grounded implementation decision, not a scope change)
- §3 (scope: every PR, no exceptions) — the `qa-gate.yml` workflow triggers on all `pull_request` events into `main`, no author/path filtering. ✓
- §4 (two enforcement layers) — Task 2 (`synlynk pr check`) + Task 3 (`synlynk pr gate-status` + CI job). ✓
- §5 (`qa_gate_mode` config field, `"block-only"` default, other modes reserved not built) — Task 1b adds the field with only the one value; no `"merge-restricted-classes"` or `"non-authoring-equivalent"` logic anywhere in this plan. ✓
- §4 branch-protection backstop — Task 4, deliberately not auto-applied (see Task 4's dispatch-target note). ✓
- §7 (architect keeps sole merge authority) — no task grants any role a `gh pr merge` call. ✓
- §8 (out of scope: other two modes, broker-service question) — neither appears anywhere in this plan. ✓
- §9 (this plan itself) — satisfied by this document.

**Placeholder scan:** no `TBD`/`TODO`; the two `<PR-A-number>`/`<PR-B-number>`/`<PR-C-number>` placeholders in PR body templates (Tasks 2, 3, 4's `gh pr create` bodies) are intentional — the actual PR number only exists once the prior PR in the stack is opened, and must be filled in at dispatch time from the real `gh pr create` output of the previous task, not left as literal text in the merged PR description.

**Type/name consistency:** `qa_gate_verdict(owner, repo, worktree_path=None, worktree_branch=None)` (Task 1) is called identically in Task 2 (`qa_gate_verdict(owner, repo)`, positional-only owner/repo, both keyword args left at their defaults since `cmd_pr_check` doesn't operate on a specific worktree) and Task 3 (`qa_gate_verdict(owner, repo)`, same). The verdict dict's three keys (`verdict`, `ci_status`/`sentinel_status`, `reason`) are used with the same names in Tasks 2 and 3's assertions and print statements. `_qa_gate_ci_status`/`_qa_gate_sentinel_health` signatures match between their Task 1 definitions and Task 1's own combiner call in `qa_gate_verdict`.
