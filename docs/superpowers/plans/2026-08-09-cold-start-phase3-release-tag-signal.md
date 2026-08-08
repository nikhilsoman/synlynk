# Cold-Start Phase 3 Slice: Release-Tag Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Scope note:** This is a standalone, independently testable *slice* of Phase 3 (progressive `canon assess` sections), not the full Phase 3 plan. Phase 3's other sections (`canon assess` command itself, Retrospective Roadmap generator, Functional/Data/Infra/Ops/UX views) have not been planned yet — that brainstorming/planning is still pending and will consume this module as a dependency when it happens. This plan produces only the release-tag detection primitives, fully tested in isolation, with no fictitious integration points into commands that don't exist yet.
>
> **Role split reminder (this repo's CLAUDE.md):** the controller coordinating this plan (Claude) does not write implementation code directly. Each task below is written so its full text can be handed to `python3 -m synlynk dispatch <agy|grok|codex> --task "..." --force-agent --context-mode full`. Reviewer/spec-compliance stages stay with Claude.

**Goal:** Build a self-contained module that detects a repo's git tag/release pattern (semver, CalVer, monorepo per-package, or none), finds the latest release tag, and classifies HEAD as released-baseline vs. in-flight relative to it — the primitives the future Retrospective Roadmap and Current State (active code) sections need per the amended spec.

**Architecture:** One new focused module, `synlynk/release_signals.py`, with pure/subprocess-backed functions (no CLI wiring, no canon file writes — those land when Phase 3's `canon assess` command itself is planned). GitHub Releases cross-referencing is opportunistic and best-effort: any failure (no `gh`, not authenticated, network error) degrades to an empty result rather than raising, per the spec's "their absence is not an error."

**Tech Stack:** Python 3 stdlib only (`subprocess`, `json`, `re`, `datetime`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-09-cold-start-design.md` — this plan implements the "Release tags as a primary timeline source" paragraph under **Section: Retrospective Roadmap**, and the "When release tags exist, they sharpen this definition" paragraph under **Section: Current State (active code only)**. It does not implement canon file writing, the `canon assess` command, or any other Phase 3 section.

---

## File Structure

- **Create:** `synlynk/release_signals.py` — tag enumeration, pattern detection, latest-tag lookup, in-flight commit counting, release-status classification, opportunistic GitHub Releases fetch.
- **Create:** `tests/test_release_signals.py` — unit tests against real tmp git repos (tags) and mocked `gh` subprocess calls.

## Task 1: Tag enumeration with dates

**Files:**
- Create: `synlynk/release_signals.py`
- Test: `tests/test_release_signals.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_release_signals.py
import subprocess

import pytest

from synlynk.release_signals import _git_tags_with_dates


def _git_init(root):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)


def _commit(root, fname, content, msg):
    (root / fname).write_text(content)
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=root, capture_output=True, check=True)


def _tag(root, name, annotated=True):
    if annotated:
        subprocess.run(["git", "tag", "-a", name, "-m", name], cwd=root, capture_output=True, check=True)
    else:
        subprocess.run(["git", "tag", name], cwd=root, capture_output=True, check=True)


def test_git_tags_with_dates_empty_repo_returns_empty(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    assert _git_tags_with_dates(str(tmp_path)) == []


def test_git_tags_with_dates_returns_sorted_by_date(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _tag(tmp_path, "v0.2.0")

    tags = _git_tags_with_dates(str(tmp_path))
    assert [t["tag"] for t in tags] == ["v0.1.0", "v0.2.0"]
    assert all("date" in t and "sha" in t for t in tags)


def test_git_tags_with_dates_handles_lightweight_tags(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0", annotated=False)

    tags = _git_tags_with_dates(str(tmp_path))
    assert [t["tag"] for t in tags] == ["v0.1.0"]


def test_git_tags_with_dates_non_git_dir_returns_empty(tmp_path):
    assert _git_tags_with_dates(str(tmp_path)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_release_signals.py -k tags_with_dates -v`
Expected: `ModuleNotFoundError: No module named 'synlynk.release_signals'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/release_signals.py
"""Release-tag signal detection for cold-start canon sections.

Pure detection primitives — no canon writes, no CLI wiring. Consumed by
Phase 3's Retrospective Roadmap and Current State (active code) sections.
See docs/superpowers/specs/2026-08-09-cold-start-design.md.
"""
import json
import re
import subprocess

_TAG_FORMAT = "%(refname:short)\t%(creatordate:iso-strict)\t%(objectname)"


def _git_tags_with_dates(root: str = ".") -> list:
    """Returns [{"tag": str, "date": str (ISO 8601), "sha": str}, ...] sorted
    oldest-to-newest by creation date. Works for both annotated and
    lightweight tags. Returns [] if not a git repo or no tags exist."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--sort=creatordate",
             f"--format={_TAG_FORMAT}", "refs/tags"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []

    tags = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        tag, date, sha = parts
        tags.append({"tag": tag, "date": date, "sha": sha})
    return tags
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_release_signals.py -k tags_with_dates -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/release_signals.py tests/test_release_signals.py
git commit -m "feat: add git tag enumeration for release-signal detection"
```

## Task 2: Tag pattern detection

**Files:**
- Modify: `synlynk/release_signals.py`
- Test: `tests/test_release_signals.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_release_signals.py
from synlynk.release_signals import _detect_tag_pattern


def test_detect_pattern_semver():
    tags = [{"tag": "v0.1.0"}, {"tag": "v0.2.0"}, {"tag": "v1.0.0"}]
    assert _detect_tag_pattern(tags) == "semver"


def test_detect_pattern_semver_no_v_prefix():
    tags = [{"tag": "0.1.0"}, {"tag": "0.2.0"}]
    assert _detect_tag_pattern(tags) == "semver"


def test_detect_pattern_calver():
    tags = [{"tag": "2026.01.15"}, {"tag": "2026.03.02"}]
    assert _detect_tag_pattern(tags) == "calver"


def test_detect_pattern_monorepo():
    tags = [{"tag": "api@1.0.0"}, {"tag": "web@2.3.1"}, {"tag": "api@1.1.0"}]
    assert _detect_tag_pattern(tags) == "monorepo"


def test_detect_pattern_none_when_no_tags():
    assert _detect_tag_pattern([]) == "none"


def test_detect_pattern_mixed_when_inconsistent():
    tags = [{"tag": "v1.0.0"}, {"tag": "release-candidate-7"}, {"tag": "checkpoint"}]
    assert _detect_tag_pattern(tags) == "mixed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_release_signals.py -k detect_pattern -v`
Expected: `ImportError: cannot import name '_detect_tag_pattern'`

- [ ] **Step 3: Implement pattern detection**

Append to `synlynk/release_signals.py`:

```python
_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+")
_CALVER_RE = re.compile(r"^v?(19|20)\d{2}[.\-]\d{1,2}([.\-]\d{1,2})?$")
_MONOREPO_RE = re.compile(r"^[\w\-./]+@v?\d+\.\d+\.\d+")


def _classify_single_tag(tag: str) -> str:
    if _MONOREPO_RE.match(tag):
        return "monorepo"
    if _CALVER_RE.match(tag):
        return "calver"
    if _SEMVER_RE.match(tag):
        return "semver"
    return "other"


def _detect_tag_pattern(tags: list) -> str:
    """Returns "semver" | "calver" | "monorepo" | "none" | "mixed".

    "none" means no tags exist. "mixed" means tags exist but don't share a
    single recognizable pattern — still meaningful signal (an inconsistently
    tagged repo), never silently dropped."""
    if not tags:
        return "none"

    classifications = {_classify_single_tag(t["tag"]) for t in tags}
    if classifications == {"semver"}:
        return "semver"
    if classifications == {"calver"}:
        return "calver"
    if classifications == {"monorepo"}:
        return "monorepo"
    return "mixed"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_release_signals.py -k detect_pattern -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/release_signals.py tests/test_release_signals.py
git commit -m "feat: add release tag pattern classification (semver/calver/monorepo)"
```

## Task 3: Latest tag + in-flight commit count

**Files:**
- Modify: `synlynk/release_signals.py`
- Test: `tests/test_release_signals.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_release_signals.py
from synlynk.release_signals import _latest_tag, _commits_since


def test_latest_tag_returns_most_recent_by_date(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _tag(tmp_path, "v0.2.0")

    latest = _latest_tag(str(tmp_path))
    assert latest["tag"] == "v0.2.0"


def test_latest_tag_none_when_no_tags(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    assert _latest_tag(str(tmp_path)) is None


def test_commits_since_counts_commits_after_ref(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _commit(tmp_path, "c.txt", "c", "third")

    assert _commits_since(str(tmp_path), "v0.1.0") == 2


def test_commits_since_zero_when_tag_is_head(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")

    assert _commits_since(str(tmp_path), "v0.1.0") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_release_signals.py -k "latest_tag or commits_since" -v`
Expected: `ImportError`

- [ ] **Step 3: Implement**

Append to `synlynk/release_signals.py`:

```python
def _latest_tag(root: str = ".") -> dict:
    """Returns the most recently created tag dict, or None if no tags exist."""
    tags = _git_tags_with_dates(root)
    return tags[-1] if tags else None


def _commits_since(root: str, ref: str) -> int:
    """Returns the count of non-merge-excluding commits on HEAD since `ref`."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{ref}..HEAD"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return 0
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip() or "0")
    except ValueError:
        return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_release_signals.py -k "latest_tag or commits_since" -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/release_signals.py tests/test_release_signals.py
git commit -m "feat: add latest-tag lookup and in-flight commit counting"
```

## Task 4: Release status classification (released-baseline vs. in-flight)

**Files:**
- Modify: `synlynk/release_signals.py`
- Test: `tests/test_release_signals.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_release_signals.py
from synlynk.release_signals import _release_status


def test_release_status_no_tags(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")

    status = _release_status(str(tmp_path))
    assert status == {
        "pattern": "none",
        "latest_tag": None,
        "latest_tag_date": None,
        "in_flight_commit_count": None,
        "in_flight_summary": None,
    }


def test_release_status_with_in_flight_commits(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _commit(tmp_path, "c.txt", "c", "third")

    status = _release_status(str(tmp_path))
    assert status["pattern"] == "semver"
    assert status["latest_tag"] == "v0.1.0"
    assert status["in_flight_commit_count"] == 2
    assert status["in_flight_summary"] == "2 commits ahead of v0.1.0, not yet released"


def test_release_status_at_latest_tag_has_no_in_flight_summary(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")

    status = _release_status(str(tmp_path))
    assert status["in_flight_commit_count"] == 0
    assert status["in_flight_summary"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_release_signals.py -k release_status -v`
Expected: `ImportError`

- [ ] **Step 3: Implement**

Append to `synlynk/release_signals.py`:

```python
def _release_status(root: str = ".") -> dict:
    """Merges tag pattern + latest tag + in-flight count into one classification
    dict, per the spec's "released-baseline vs. in-flight" active-code labeling.

    Returns:
        {
            "pattern": "semver"|"calver"|"monorepo"|"mixed"|"none",
            "latest_tag": str or None,
            "latest_tag_date": str (ISO 8601) or None,
            "in_flight_commit_count": int or None (None only when no tags exist),
            "in_flight_summary": str or None (None when 0 in-flight commits or no tags),
        }
    """
    tags = _git_tags_with_dates(root)
    pattern = _detect_tag_pattern(tags)
    latest = tags[-1] if tags else None

    if latest is None:
        return {
            "pattern": pattern,
            "latest_tag": None,
            "latest_tag_date": None,
            "in_flight_commit_count": None,
            "in_flight_summary": None,
        }

    in_flight = _commits_since(root, latest["tag"])
    summary = (f"{in_flight} commits ahead of {latest['tag']}, not yet released"
               if in_flight > 0 else None)

    return {
        "pattern": pattern,
        "latest_tag": latest["tag"],
        "latest_tag_date": latest["date"],
        "in_flight_commit_count": in_flight,
        "in_flight_summary": summary,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_release_signals.py -k release_status -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/release_signals.py tests/test_release_signals.py
git commit -m "feat: add release-status classification for active-code labeling"
```

## Task 5: Opportunistic GitHub Releases cross-reference

**Files:**
- Modify: `synlynk/release_signals.py`
- Test: `tests/test_release_signals.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_release_signals.py
from unittest.mock import patch, MagicMock

from synlynk.release_signals import _fetch_github_releases


def test_fetch_github_releases_parses_json_output(tmp_path):
    fake_output = json.dumps([
        {"tagName": "v0.2.0", "name": "v0.2.0", "publishedAt": "2026-08-01T00:00:00Z"},
        {"tagName": "v0.1.0", "name": "v0.1.0", "publishedAt": "2026-07-01T00:00:00Z"},
    ])
    fake_result = MagicMock(returncode=0, stdout=fake_output)
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        releases = _fetch_github_releases(str(tmp_path))
    assert releases == [
        {"tag": "v0.2.0", "name": "v0.2.0", "published_at": "2026-08-01T00:00:00Z"},
        {"tag": "v0.1.0", "name": "v0.1.0", "published_at": "2026-07-01T00:00:00Z"},
    ]
    mock_run.assert_called_once()


def test_fetch_github_releases_returns_empty_when_gh_not_installed(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert _fetch_github_releases(str(tmp_path)) == []


def test_fetch_github_releases_returns_empty_on_nonzero_exit(tmp_path):
    fake_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=fake_result):
        assert _fetch_github_releases(str(tmp_path)) == []


def test_fetch_github_releases_returns_empty_on_malformed_json(tmp_path):
    fake_result = MagicMock(returncode=0, stdout="not json")
    with patch("subprocess.run", return_value=fake_result):
        assert _fetch_github_releases(str(tmp_path)) == []
```

Add `import json` to the top of `tests/test_release_signals.py` alongside the existing imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_release_signals.py -k fetch_github_releases -v`
Expected: `ImportError: cannot import name '_fetch_github_releases'`

- [ ] **Step 3: Implement**

Append to `synlynk/release_signals.py`:

```python
def _fetch_github_releases(root: str = ".") -> list:
    """Best-effort cross-reference of GitHub Releases via the `gh` CLI.

    Absence is not an error per spec: no `gh` installed, not authenticated,
    no remote, or any other failure all degrade to []. Tags remain the
    primary signal; this only enriches the timeline with release notes
    when available."""
    try:
        result = subprocess.run(
            ["gh", "release", "list", "--limit", "50",
             "--json", "tagName,name,publishedAt"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    return [
        {"tag": r.get("tagName"), "name": r.get("name"), "published_at": r.get("publishedAt")}
        for r in raw
        if isinstance(r, dict)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_release_signals.py -k fetch_github_releases -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/release_signals.py tests/test_release_signals.py
git commit -m "feat: add opportunistic GitHub Releases cross-reference"
```

## Task 6: Full module test run + self-review pass

**Files:** none new — verification only.

- [ ] **Step 1: Run the full new test file**

Run: `pytest tests/test_release_signals.py -v`
Expected: all 21 tests pass (4 + 6 + 4 + 3 + 4, per tasks 1-5).

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass, including the pre-existing Phase 1 `test_coldstart.py` suite — this module has no import-time coupling to `synlynk/coldstart.py`, so no interaction is expected.

- [ ] **Step 3: Manual smoke test against this repo**

```bash
cd /Users/nikhilsoman/dev/synlynk
python3 -c "
from synlynk.release_signals import _release_status, _fetch_github_releases
import json
print(json.dumps(_release_status('.'), indent=2))
print(json.dumps(_fetch_github_releases('.'), indent=2))
"
```
Confirm `_release_status` reports a real pattern/tag/in-flight-count against synlynk's own tag history, and `_fetch_github_releases` either returns real release data or `[]` without raising.

- [ ] **Step 4: Commit any fixes found during smoke testing**

If the manual smoke test surfaces issues (e.g. an unanticipated tag naming convention in this repo's own history), fix them in `synlynk/release_signals.py`, re-run `pytest -q`, and commit with a message describing the fix.

---

## Self-Review Notes (completed during plan authoring)

- **Spec coverage:** "Release tags as a primary timeline source" (pattern detection across semver/CalVer/monorepo/untagged, GitHub Releases cross-reference) → Tasks 1, 2, 5. "When release tags exist, they sharpen this definition" (released-baseline vs. in-flight labeling) → Tasks 3, 4. Wiring these primitives into the actual Retrospective Roadmap / Current State canon sections is explicitly out of scope — those commands don't exist yet and will consume this module when Phase 3's remaining plan is written.
- **Placeholder scan:** no TBD/TODO; every step has complete, runnable code.
- **Type consistency:** `_git_tags_with_dates` returns `[{"tag","date","sha"}, ...]` consistently consumed by `_detect_tag_pattern`, `_latest_tag`, and `_release_status` across Tasks 1-4; `_release_status`'s output dict shape is fixed in Task 4 and matches the smoke-test usage in Task 6.
- **Open item carried forward:** when Phase 3's full plan is written, it must decide where `_release_status()`'s output actually gets rendered in `workspace-canon.md` (which section header, what prose wraps `in_flight_summary`) — that's a canon-writing concern this slice deliberately does not touch.
