# Cold-Start Phase 2: workspace-canon.md Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real `workspace-canon.md` baseline generation (Documentation Index + 3-claim
receipt, with skeleton stubs for everything else) to `synlynk start`'s existing-project flow.

**Architecture:** New module `synlynk/canon.py` holds all canon-building logic, isolated from
`synlynk/coldstart.py`. `coldstart.py`'s `_run_existing_project_flow()` gets one new call —
`canon.run_canon_baseline(root, scan)` — inserted between the scan summary print and the intent
question. `run_canon_baseline()` is the single entry point: it decides first-run (offer consent,
generate, write) vs. re-run (check staleness, print banner) based solely on whether
`workspace-canon.md` already exists on disk.

**Tech Stack:** Python 3 stdlib only (`os`, `re`, `time`, `subprocess`) — matches the rest of the
repo; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-09-cold-start-phase2-canon-baseline-design.md`

---

## Task 1: Documentation Index builder

**Files:**
- Create: `synlynk/canon.py`
- Test: `tests/test_canon.py`

- [ ] **Step 1: Write the failing test**

```python
import os

from synlynk.canon import _build_documentation_index


def test_documentation_index_lists_files_from_both_dirs(tmp_path):
    os.makedirs(tmp_path / "project-docs")
    (tmp_path / "project-docs" / "roadmap.md").write_text("# roadmap")
    os.makedirs(tmp_path / "docs" / "superpowers" / "specs")
    (tmp_path / "docs" / "superpowers" / "specs" / "x-design.md").write_text("# x")

    result = _build_documentation_index(str(tmp_path))

    assert "project-docs/roadmap.md" in result
    assert os.path.join("docs", "superpowers", "specs", "x-design.md") in result


def test_documentation_index_handles_missing_dirs(tmp_path):
    result = _build_documentation_index(str(tmp_path))
    assert "No project-docs/ or docs/ markdown files found" in result


def test_documentation_index_ignores_non_markdown_files(tmp_path):
    os.makedirs(tmp_path / "docs")
    (tmp_path / "docs" / "notes.txt").write_text("not markdown")
    result = _build_documentation_index(str(tmp_path))
    assert "notes.txt" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_canon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.canon'`

- [ ] **Step 3: Create `synlynk/canon.py` with the module header and the index builder**

```python
"""Baseline workspace-canon.md generation for cold-start Phase 2.

Generates a Documentation Index and a 3-claim receipt from shallow-scan
data; every other section the parent spec describes ships as a skeleton
stub. See docs/superpowers/specs/2026-08-09-cold-start-phase2-canon-baseline-design.md.
"""
import os
import re
import subprocess
import time
from typing import Optional

_CANON_FILENAME = "workspace-canon.md"

_DOC_INDEX_DIRS = ("project-docs", "docs")

_SKELETON_SECTIONS = (
    "Retrospective Roadmap",
    "Current State (active code only)",
    "Functional View",
    "Data View",
    "Infra View",
    "Ops View",
    "UX View",
)

_SKELETON_NOTE = (
    "_Not yet assessed — see "
    "docs/superpowers/specs/2026-08-09-cold-start-design.md for the full canon vision._"
)

_PROVENANCE_RE = re.compile(
    r"<!--\s*canon:section=baseline\s+sha=(?P<sha>[0-9a-f]+|unknown)\s+"
    r"assessed_at=(?P<assessed_at>\S+)\s*-->"
)


def _build_documentation_index(root: str) -> str:
    """Walks project-docs/ and docs/ recursively for .md files, grouped by directory."""
    lines = ["## Documentation Index", ""]
    found_any = False
    for top in _DOC_INDEX_DIRS:
        top_path = os.path.join(root, top)
        if not os.path.isdir(top_path):
            continue
        files = []
        for dirpath, _dirnames, filenames in os.walk(top_path):
            for fn in filenames:
                if fn.endswith(".md"):
                    rel = os.path.relpath(os.path.join(dirpath, fn), root)
                    files.append(rel)
        if not files:
            continue
        found_any = True
        lines.append(f"### {top}/")
        for rel in sorted(files):
            lines.append(f"- `{rel}`")
        lines.append("")
    if not found_any:
        lines.append("_No project-docs/ or docs/ markdown files found._")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_canon.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/canon.py tests/test_canon.py
git commit -m "feat: add canon.py Documentation Index builder"
```

---

## Task 2: 3-claim receipt builder

**Files:**
- Modify: `synlynk/canon.py`
- Test: `tests/test_canon.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_canon.py`:

```python
from synlynk.canon import _build_claim_receipt


def test_claim_receipt_full_scan_yields_three_claims():
    scan = {
        "repos": [{"path": "/tmp/x", "stack_labels": ["python"]}],
        "harnesses": [{"name": "claude"}],
    }
    claims = _build_claim_receipt(scan)
    assert len(claims) == 3
    assert all(c["confidence"] == "found" for c in claims)
    assert "python" in claims[0]["claim"]
    assert "/tmp/x" in claims[1]["claim"]
    assert "claude" in claims[2]["claim"]


def test_claim_receipt_skips_missing_fields():
    scan = {"repos": [], "harnesses": []}
    claims = _build_claim_receipt(scan)
    assert claims == []


def test_claim_receipt_partial_scan_yields_partial_claims():
    scan = {"repos": [{"path": "/tmp/x", "stack_labels": []}], "harnesses": []}
    claims = _build_claim_receipt(scan)
    assert len(claims) == 1
    assert "/tmp/x" in claims[0]["claim"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_canon.py -v`
Expected: FAIL with `ImportError: cannot import name '_build_claim_receipt'`

- [ ] **Step 3: Add the claim receipt builder to `synlynk/canon.py`**

Append after `_build_documentation_index`:

```python
def _build_claim_receipt(scan: dict) -> list:
    """Up to 3 claims sourced directly from shallow-scan data. A claim is
    skipped outright — never fabricated — if its backing field is missing."""
    claims = []
    repos = scan.get("repos") or []
    repo = repos[0] if repos else None

    if repo and repo.get("stack_labels"):
        stack = ", ".join(repo["stack_labels"])
        claims.append({
            "claim": f"Detected stack: {stack}",
            "confidence": "found",
            "verify": f"ls {repo.get('path', '.')}",
        })

    if repo and repo.get("path"):
        claims.append({
            "claim": f"This is a git repository at {repo['path']}",
            "confidence": "found",
            "verify": f"git -C {repo['path']} rev-parse --show-toplevel",
        })

    harnesses = scan.get("harnesses") or []
    if harnesses:
        names = ", ".join(h["name"] for h in harnesses)
        first = harnesses[0]["name"]
        claims.append({
            "claim": f"Harness available on PATH: {names}",
            "confidence": "found",
            "verify": f"which {first}",
        })

    return claims[:3]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_canon.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/canon.py tests/test_canon.py
git commit -m "feat: add canon.py 3-claim receipt builder"
```

---

## Task 3: Canon renderer + writer

**Files:**
- Modify: `synlynk/canon.py`
- Test: `tests/test_canon.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_canon.py`:

```python
from synlynk.canon import _render_canon, _write_canon, _CANON_FILENAME


def test_render_canon_includes_provenance_and_both_real_sections(tmp_path):
    scan = {"repos": [{"path": str(tmp_path), "stack_labels": ["python"]}], "harnesses": []}
    content = _render_canon(str(tmp_path), scan, head_sha="a" * 40)
    assert f"canon:section=baseline sha={'a' * 40}" in content
    assert "## Documentation Index" in content
    assert "## 3-Claim Receipt" in content
    assert "Detected stack: python" in content


def test_render_canon_includes_skeleton_sections_without_provenance(tmp_path):
    scan = {"repos": [], "harnesses": []}
    content = _render_canon(str(tmp_path), scan, head_sha="a" * 40)
    assert "## Current State (active code only)" in content
    assert "Not yet assessed" in content
    # Only one provenance comment total — skeleton sections carry none.
    assert content.count("<!-- canon:section=") == 1


def test_render_canon_defaults_to_unknown_sha_when_none(tmp_path):
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=None)
    assert "sha=unknown" in content


def test_write_canon_writes_file(tmp_path):
    path = _write_canon(str(tmp_path), "hello")
    assert os.path.exists(path)
    assert os.path.basename(path) == _CANON_FILENAME
    assert open(path).read() == "hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_canon.py -v`
Expected: FAIL with `ImportError: cannot import name '_render_canon'`

- [ ] **Step 3: Add the renderer and writer to `synlynk/canon.py`**

Append:

```python
def _render_canon(root: str, scan: dict, head_sha: Optional[str] = None) -> str:
    sha = head_sha or "unknown"
    assessed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    provenance = f"<!-- canon:section=baseline sha={sha} assessed_at={assessed_at} -->"

    claims = _build_claim_receipt(scan)

    lines = [
        "# Workspace Canon",
        "",
        provenance,
        "",
        _build_documentation_index(root),
        "## 3-Claim Receipt",
        "",
    ]
    if claims:
        for i, c in enumerate(claims, start=1):
            lines.append(f"{i}. **{c['claim']}** ({c['confidence']})")
            lines.append(f"   Verify: `{c['verify']}`")
    else:
        lines.append("_No claims could be derived from the current scan data._")
    lines.append("")

    for section in _SKELETON_SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
        lines.append(_SKELETON_NOTE)
        lines.append("")

    return "\n".join(lines)


def _write_canon(root: str, content: str) -> str:
    path = os.path.join(root, _CANON_FILENAME)
    with open(path, "w") as fh:
        fh.write(content)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_canon.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/canon.py tests/test_canon.py
git commit -m "feat: add canon.py renderer and writer"
```

---

## Task 4: Provenance parser + staleness checker

**Files:**
- Modify: `synlynk/canon.py`
- Test: `tests/test_canon.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_canon.py`:

```python
import subprocess

from synlynk.canon import _parse_canon_provenance, _check_canon_staleness


def _git_init_simple(root):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
    (root / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, capture_output=True, check=True)


def _current_sha(root):
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def test_parse_canon_provenance_round_trips(tmp_path):
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha="b" * 40)
    _write_canon(str(tmp_path), content)
    provenance = _parse_canon_provenance(str(tmp_path))
    assert provenance["sha"] == "b" * 40


def test_parse_canon_provenance_missing_file_returns_none(tmp_path):
    assert _parse_canon_provenance(str(tmp_path)) is None


def test_parse_canon_provenance_malformed_comment_returns_none(tmp_path):
    (tmp_path / _CANON_FILENAME).write_text("# Workspace Canon\nno provenance comment here\n")
    assert _parse_canon_provenance(str(tmp_path)) is None


def test_check_canon_staleness_same_sha_not_stale(tmp_path):
    _git_init_simple(tmp_path)
    sha = _current_sha(tmp_path)
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=sha)
    _write_canon(str(tmp_path), content)
    assert _check_canon_staleness(str(tmp_path)) == []


def test_check_canon_staleness_different_sha_is_stale(tmp_path):
    _git_init_simple(tmp_path)
    old_sha = _current_sha(tmp_path)
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=old_sha)
    _write_canon(str(tmp_path), content)
    (tmp_path / "new.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, capture_output=True, check=True)
    assert _check_canon_staleness(str(tmp_path)) == ["baseline"]


def test_check_canon_staleness_unknown_sha_never_stale(tmp_path):
    _git_init_simple(tmp_path)
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=None)
    _write_canon(str(tmp_path), content)
    assert _check_canon_staleness(str(tmp_path)) == []


def test_check_canon_staleness_missing_canon_is_stale(tmp_path):
    assert _check_canon_staleness(str(tmp_path)) == ["baseline"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_canon.py -v`
Expected: FAIL with `ImportError: cannot import name '_parse_canon_provenance'`

- [ ] **Step 3: Add the parser, a `-C`-scoped HEAD SHA helper, and the staleness checker to `synlynk/canon.py`**

Append:

```python
def _head_sha(root: str) -> Optional[str]:
    """Full HEAD SHA for `root`, or None if not a git repo / no commits.

    Uses `git -C <root>` rather than relying on process cwd, since `root`
    may differ from the caller's current working directory.
    """
    try:
        result = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha if len(sha) == 40 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _parse_canon_provenance(root: str) -> Optional[dict]:
    path = os.path.join(root, _CANON_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            content = fh.read()
    except OSError:
        return None
    match = _PROVENANCE_RE.search(content)
    if not match:
        return None
    return {"sha": match.group("sha"), "assessed_at": match.group("assessed_at")}


def _check_canon_staleness(root: str) -> list:
    """Returns ["baseline"] if the stamped baseline section is stale, else [].

    A missing/malformed provenance comment counts as stale. A stamped
    sha of "unknown" (no git repo at generation time) is never reported
    stale — there is nothing to compare it against.
    """
    provenance = _parse_canon_provenance(root)
    if provenance is None:
        return ["baseline"]
    if provenance["sha"] == "unknown":
        return []
    current_sha = _head_sha(root)
    if current_sha is None or current_sha == provenance["sha"]:
        return []
    return ["baseline"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_canon.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/canon.py tests/test_canon.py
git commit -m "feat: add canon.py provenance parser and staleness checker"
```

---

## Task 5: Deep-scan consent + orchestration entry point

**Files:**
- Modify: `synlynk/canon.py`
- Test: `tests/test_canon.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_canon.py`:

```python
from unittest.mock import patch

from synlynk.canon import _offer_deep_scan_consent, run_canon_baseline


def test_offer_deep_scan_consent_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert _offer_deep_scan_consent() is True


def test_offer_deep_scan_consent_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert _offer_deep_scan_consent() is False


def test_run_canon_baseline_first_run_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    scan = {"repos": [{"path": str(tmp_path), "stack_labels": []}], "harnesses": []}
    with patch("synlynk.scan.cmd_scan") as mock_deep_scan:
        run_canon_baseline(str(tmp_path), scan)
        mock_deep_scan.assert_not_called()
    assert os.path.exists(tmp_path / _CANON_FILENAME)


def test_run_canon_baseline_first_run_accepts_deep_scan_consent(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    scan = {"repos": [], "harnesses": []}
    with patch("synlynk.scan.cmd_scan") as mock_deep_scan:
        run_canon_baseline(str(tmp_path), scan)
        mock_deep_scan.assert_called_once_with(deep=True)


def test_run_canon_baseline_rerun_skips_consent_prompt(tmp_path, monkeypatch):
    def _fail_input(prompt):
        raise AssertionError("should not prompt on rerun")
    scan = {"repos": [], "harnesses": []}
    _write_canon(str(tmp_path), _render_canon(str(tmp_path), scan, head_sha=None))
    monkeypatch.setattr("builtins.input", _fail_input)
    run_canon_baseline(str(tmp_path), scan)  # must not raise


def test_run_canon_baseline_rerun_prints_staleness_banner(tmp_path, monkeypatch, capsys):
    _git_init_simple(tmp_path)
    old_sha = _current_sha(tmp_path)
    scan = {"repos": [], "harnesses": []}
    _write_canon(str(tmp_path), _render_canon(str(tmp_path), scan, head_sha=old_sha))
    (tmp_path / "new.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, capture_output=True, check=True)

    def _fail_input(prompt):
        raise AssertionError("should not prompt on rerun")
    monkeypatch.setattr("builtins.input", _fail_input)

    run_canon_baseline(str(tmp_path), scan)

    captured = capsys.readouterr()
    assert "may be stale" in captured.out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_canon.py -v`
Expected: FAIL with `ImportError: cannot import name '_offer_deep_scan_consent'`

- [ ] **Step 3: Add the consent prompt and orchestration entry point to `synlynk/canon.py`**

Append:

```python
def _offer_deep_scan_consent() -> bool:
    answer = input(
        "\nWant me to run a deeper scan now (source tree walk, symbols, git history)? "
        "This may take a bit longer. [y/N] "
    ).strip().lower()
    return answer == "y"


def run_canon_baseline(root: str, scan: dict) -> None:
    """Entry point called from cold-start's existing-project flow.

    First run (no workspace-canon.md yet): offers deep-scan consent once,
    then generates and writes the baseline. Re-run: skips the consent
    offer entirely and prints a staleness banner if the baseline section's
    stamped SHA no longer matches HEAD.
    """
    path = os.path.join(root, _CANON_FILENAME)
    if not os.path.exists(path):
        if _offer_deep_scan_consent():
            import synlynk.scan as scan_mod
            scan_mod.cmd_scan(deep=True)
        head_sha = _head_sha(root)
        content = _render_canon(root, scan, head_sha)
        _write_canon(root, content)
        print(f"\nWrote {_CANON_FILENAME} (baseline: documentation index + 3-claim receipt).")
        return

    stale_sections = _check_canon_staleness(root)
    if stale_sections:
        provenance = _parse_canon_provenance(root) or {}
        old_sha = (provenance.get("sha") or "unknown")[:7]
        current_sha = (_head_sha(root) or "unknown")[:7]
        print(f"\n⚠ {_CANON_FILENAME}'s baseline section may be stale "
              f"(generated at {old_sha}, HEAD is now {current_sha}).\n"
              "  Re-run not yet supported in Phase 2 — regenerate manually if needed.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_canon.py -v`
Expected: PASS (23 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/canon.py tests/test_canon.py
git commit -m "feat: add canon.py deep-scan consent and run_canon_baseline entry point"
```

---

## Task 6: Wire into `synlynk/coldstart.py`

**Files:**
- Modify: `synlynk/coldstart.py:150-182` (`_run_existing_project_flow`)
- Modify: `tests/test_coldstart.py`

- [ ] **Step 1: Update `_run_existing_project_flow`'s docstring and insert the canon call**

In `synlynk/coldstart.py`, replace the whole `_run_existing_project_flow` function body:

```python
def _run_existing_project_flow(root: str = ".") -> None:
    """Baseline warm-start for an existing repo: env-probe + shallow scan summary
    + workspace-canon.md baseline (Documentation Index + 3-claim receipt, see
    cold-start Phase 2) + one question, routed into a seeded story.
    """
    import synlynk.scan as scan_mod
    from synlynk import canon
    from synlynk.db import cmd_story_create

    scan = scan_mod.run_workspace_scan(roots=[root], deep=False)

    repo = scan["repos"][0] if scan["repos"] else {
        "name": os.path.basename(os.path.abspath(root)),
        "stack_labels": [],
    }
    functional_agents = [a for a in scan.get("agents", []) if a.get("functional")]

    print(f"\nFound: {repo['name']}  ·  stack: {', '.join(repo['stack_labels']) or 'unknown'}  "
          f"·  topology: {scan.get('topology', 'single')}")
    if functional_agents:
        print(f"Harnesses ready: {', '.join(a['name'] for a in functional_agents)}")
    else:
        checked = ", ".join(a["name"] for a in scan.get("agents", [])) or "none found on PATH"
        print(f"No working harnesses detected (checked: {checked})  "
              "You can still browse the scan output; install/auth a harness to dispatch work.")

    canon.run_canon_baseline(root, scan)

    intent = input("\nWhat are you trying to do right now? ").strip()
    if intent:
        story_id = cmd_story_create(title=intent)
        print(f"\nNext: run `synlynk dispatch <agent> --task \"{intent}\"` "
              f"to work on {story_id}, or `synlynk story list` to see it queued.")
    else:
        print("\nNo task captured -- run `synlynk start` again anytime, "
              "or `synlynk scan --deep` for a fuller picture.")
```

- [ ] **Step 2: Run the existing coldstart test suite**

Run: `pytest tests/test_coldstart.py -v`
Expected: PASS — the two `_run_existing_project_flow` tests each supply a fixed `input()` answer
regardless of prompt text, which now gets consumed by the new deep-scan consent prompt first
(declining it, since the fixed answer isn't `"y"`) and then by the intent prompt, so their
assertions on printed output still hold. If any test unexpectedly fails here, read the failure
output before changing anything — do not blanket-adjust assertions.

- [ ] **Step 3: Add a coldstart-side test asserting the canon module is invoked**

Append to `tests/test_coldstart.py`:

```python
def test_run_existing_project_flow_invokes_canon_baseline(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fake_scan = {
        "repos": [{"name": "myrepo", "path": str(tmp_path), "stack_labels": ["python"],
                    "readme_excerpt": "", "context_sections": {}}],
        "harnesses": [{"name": "claude"}],
        "agents": [{"name": "claude", "functional": True}],
        "skills": [],
        "topology": "single",
        "workspace_name": "myrepo",
        "home_harness": "claude",
        "scanned_at": "",
    }
    answers = iter(["n", "fix the flaky CI job"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    with patch("synlynk.scan.run_workspace_scan", return_value=fake_scan):
        _run_existing_project_flow(str(tmp_path))

    assert os.path.exists(tmp_path / "workspace-canon.md")
    captured = capsys.readouterr()
    assert "workspace-canon.md" in captured.out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -v`
Expected: PASS (all prior tests + 1 new test)

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "feat: generate workspace-canon.md baseline in existing-project cold-start flow"
```

---

## Task 7: End-to-end integration test through `cmd_start()`

**Files:**
- Modify: `tests/test_coldstart.py`

- [ ] **Step 1: Write the integration test**

Append to `tests/test_coldstart.py`:

```python
def test_cmd_start_generates_canon_then_flags_staleness_on_rerun(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_init(tmp_path, commits=1, files={"README.md": "# repo\n"})
    fake_scan = {
        "repos": [{"name": tmp_path.name, "path": str(tmp_path), "stack_labels": [],
                    "readme_excerpt": "", "context_sections": {}}],
        "harnesses": [], "agents": [], "skills": [], "topology": "single",
        "workspace_name": tmp_path.name, "home_harness": None, "scanned_at": "",
    }

    with patch("synlynk.scan.run_workspace_scan", return_value=fake_scan):
        first_answers = iter(["n", "look at ci"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(first_answers))
        cmd_start()

    assert os.path.exists(tmp_path / "workspace-canon.md")
    first_output = capsys.readouterr().out
    assert "Wrote workspace-canon.md" in first_output

    (tmp_path / "new.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, capture_output=True, check=True)

    with patch("synlynk.scan.run_workspace_scan", return_value=fake_scan):
        second_answers = iter(["look again"])  # no consent prompt expected on rerun
        monkeypatch.setattr("builtins.input", lambda prompt: next(second_answers))
        cmd_start()

    second_output = capsys.readouterr().out
    assert "may be stale" in second_output.lower()
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `pytest tests/test_coldstart.py -v -k test_cmd_start_generates_canon_then_flags_staleness_on_rerun`
Expected: PASS

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass, 0 failures (matches the pre-Phase-2 baseline of 1817 passed, 2 skipped).

- [ ] **Step 4: Commit**

```bash
git add tests/test_coldstart.py
git commit -m "test: add end-to-end cmd_start canon generation and staleness integration test"
```

---

## Final Review

After all 7 tasks are complete and committed, dispatch a final code reviewer subagent (per
`superpowers:subagent-driven-development`) to review the entire diff against the spec at
`docs/superpowers/specs/2026-08-09-cold-start-phase2-canon-baseline-design.md`, then use
`superpowers:finishing-a-development-branch` to open the PR.
