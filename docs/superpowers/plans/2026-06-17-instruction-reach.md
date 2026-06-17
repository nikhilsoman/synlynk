# Instruction Reach Implementation Plan — v0.4.1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend synlynk's instruction generation to Cursor, Copilot, and Windsurf using tool-native formats with section markers, detect drift in synlynk-authored sections at runtime, and add `synlynk instructions status/diff/update/ack` commands.

**Architecture:** All changes are in `bin/synlynk.py`. A new `_write_instruction_file()` helper handles create/append/replace-section logic for every instruction target. A SHA manifest at `.synlynk/instructions.json` tracks what synlynk wrote. `_check_instruction_drift()` is hooked into `exec_command()` to fire `INSTRUCTION_DRIFT` sentinel events automatically.

**Tech stack:** Python 3 stdlib only (`hashlib`, `re`, `json`, `os`). No new dependencies.

---

### Task 1: AGY cleanup — remove Gemini CLI, fix GEMINI.md template

Gemini CLI is EOL. Remove it from agent discovery and clean the stale transition note from the GEMINI.md template.

**Files:**
- Modify: `bin/synlynk.py` — `AGENT_CAPABILITY_BASELINES`, `AGENT_DISCOVERY_DEFAULTS`, `_build_templates()`
- Create: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write the two failing tests**

```python
# tests/test_instruction_reach.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))


def test_agy_baseline_replaces_gemini():
    from synlynk import AGENT_CAPABILITY_BASELINES
    assert "gemini" not in AGENT_CAPABILITY_BASELINES
    assert "agy" in AGENT_CAPABILITY_BASELINES


def test_gemini_md_template_has_no_transition_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _build_templates
    templates = _build_templates()
    assert "2026-06-18" not in templates["GEMINI.md"]
    assert "agy-2.x" in templates["GEMINI.md"]
    assert "gemini-2.x" not in templates["GEMINI.md"]
```

- [ ] **Step 2: Run to confirm both fail**

```bash
pytest tests/test_instruction_reach.py::test_agy_baseline_replaces_gemini \
       tests/test_instruction_reach.py::test_gemini_md_template_has_no_transition_note -v
```
Expected: 2 FAILED

- [ ] **Step 3: Remove `gemini` from `AGENT_CAPABILITY_BASELINES` and `AGENT_DISCOVERY_DEFAULTS`**

In `bin/synlynk.py`, find `AGENT_CAPABILITY_BASELINES` (line ~283). Delete the `"gemini"` block entirely:

```python
# DELETE this entire block:
    "gemini": {
        "cli": "gemini",
        ...
    },
```

Find `AGENT_DISCOVERY_DEFAULTS` (line ~312). Delete:
```python
# DELETE this line:
    "gemini": os.path.expanduser("~/.gemini"),
```

- [ ] **Step 4: Fix the GEMINI.md template in `_build_templates()`**

Find `_gemini_md` (line ~1451). Replace the opening block:

```python
    _gemini_md = (
        "# synlynk AGY (AntiGravity) Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** agy-2.x\n"
        "- **Commit trailer:** `Co-Authored-By: AGY <noreply@antigravity.dev>`\n"
        "- **Branch prefix:** `feat/agy/` or `fix/agy/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/agy/<description>` — new functionality\n"
        "- `fix/agy/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol
    )
```

- [ ] **Step 5: Run tests — both should pass**

```bash
pytest tests/test_instruction_reach.py::test_agy_baseline_replaces_gemini \
       tests/test_instruction_reach.py::test_gemini_md_template_has_no_transition_note -v
```
Expected: 2 PASSED

- [ ] **Step 6: Run full suite to confirm no regressions**

```bash
pytest tests/ -q
```
Expected: all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: remove gemini CLI (EOL), update GEMINI.md to AGY-only — v0.4.1"
```

---

### Task 2: Section marker helpers — `_extract_synlynk_section()` + `_compute_section_sha()`

These two helpers underpin every other task. `_extract_synlynk_section` pulls the synlynk block out of a file's content; `_compute_section_sha` hashes it for the manifest.

**Files:**
- Modify: `bin/synlynk.py` — add two functions after `_infer_industry()`
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_extract_synlynk_section_html_markers():
    from synlynk import _extract_synlynk_section
    content = 'Before\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nmy block\n<!-- synlynk:end -->\nAfter'
    assert _extract_synlynk_section(content, "html") == "\nmy block\n"


def test_extract_synlynk_section_hash_markers():
    from synlynk import _extract_synlynk_section
    content = "Before\n# synlynk:start version=\"0.4.1\"\nmy block\n# synlynk:end\nAfter"
    assert _extract_synlynk_section(content, "hash") == "my block"


def test_extract_synlynk_section_none_marker_returns_whole():
    from synlynk import _extract_synlynk_section
    content = "entire file content"
    assert _extract_synlynk_section(content, "none") == content


def test_extract_synlynk_section_returns_none_when_absent():
    from synlynk import _extract_synlynk_section
    assert _extract_synlynk_section("no markers here", "html") is None


def test_compute_section_sha_is_deterministic():
    from synlynk import _compute_section_sha
    assert _compute_section_sha("hello") == _compute_section_sha("hello")
    assert _compute_section_sha("hello") != _compute_section_sha("world")
    assert len(_compute_section_sha("hello")) == 16
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "extract_synlynk_section or compute_section_sha" -v
```
Expected: 5 FAILED

- [ ] **Step 3: Add the two functions to `bin/synlynk.py`**

Add after `_infer_industry()` (around line 822):

```python
def _extract_synlynk_section(content: str, marker_style: str = "html") -> Optional[str]:
    """Return the text inside synlynk markers, or the whole content for marker_style='none'."""
    if marker_style == "none":
        return content
    if marker_style == "html":
        m = re.search(
            r'<!-- synlynk:start[^>]* -->(.*?)<!-- synlynk:end -->',
            content, re.DOTALL
        )
    else:  # hash
        m = re.search(
            r'# synlynk:start[^\n]*\n(.*?)\n# synlynk:end',
            content, re.DOTALL
        )
    return m.group(1) if m else None


def _compute_section_sha(content: str) -> str:
    """Return first 16 hex chars of SHA-256 of content string."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "extract_synlynk_section or compute_section_sha" -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: _extract_synlynk_section + _compute_section_sha helpers"
```

---

### Task 3: `_write_instruction_file()` — core append/replace helper

Handles all three write modes: create (new file), append (existing file, no markers), replace-section (existing file with markers).

**Files:**
- Modify: `bin/synlynk.py` — add after `_compute_section_sha()`
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_write_instruction_file_creates_new_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _write_instruction_file
    result = _write_instruction_file("CLAUDE.md", "claude", "synlynk content", "html")
    assert result is True
    text = open("CLAUDE.md").read()
    assert "<!-- synlynk:start" in text
    assert "synlynk content" in text
    assert "<!-- synlynk:end -->" in text


def test_write_instruction_file_appends_to_existing_no_markers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    open("CLAUDE.md", "w").write("# User content\nsome existing rules\n")
    from synlynk import _write_instruction_file
    _write_instruction_file("CLAUDE.md", "claude", "synlynk block", "html")
    text = open("CLAUDE.md").read()
    assert "# User content" in text          # preserved
    assert "synlynk block" in text           # appended
    assert text.index("# User content") < text.index("synlynk block")  # user content first


def test_write_instruction_file_replaces_existing_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = '# User\n<!-- synlynk:start version="0.4.0" tool="claude" -->\nold content\n<!-- synlynk:end -->\n# After'
    open("CLAUDE.md", "w").write(existing)
    from synlynk import _write_instruction_file
    _write_instruction_file("CLAUDE.md", "claude", "new content", "html")
    text = open("CLAUDE.md").read()
    assert "old content" not in text
    assert "new content" in text
    assert "# User" in text       # user content above preserved
    assert "# After" in text      # user content below preserved


def test_write_instruction_file_hash_markers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _write_instruction_file
    _write_instruction_file(".windsurfrules", "windsurf", "line one\nline two", "hash")
    text = open(".windsurfrules").read()
    assert "# synlynk:start" in text
    assert "line one" in text
    assert "# synlynk:end" in text


def test_write_instruction_file_none_marker_owns_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".cursor/rules", exist_ok=True)
    from synlynk import _write_instruction_file
    _write_instruction_file(".cursor/rules/synlynk.mdc", "cursor", "---\nalwaysApply: true\n---\ncontent", "none")
    text = open(".cursor/rules/synlynk.mdc").read()
    assert "alwaysApply: true" in text
    assert "<!-- synlynk" not in text  # no markers for "none" style


def test_write_instruction_file_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _write_instruction_file
    _write_instruction_file(".github/copilot-instructions.md", "copilot", "synlynk rules", "html")
    assert os.path.exists(".github/copilot-instructions.md")
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "write_instruction_file" -v
```
Expected: 6 FAILED

- [ ] **Step 3: Add `_write_instruction_file()` to `bin/synlynk.py`**

Add after `_compute_section_sha()`:

```python
def _write_instruction_file(path: str, tool: str, content: str,
                             marker_style: str = "html") -> bool:
    """Write or update the synlynk block in an instruction file.

    marker_style='none': synlynk owns the whole file (overwrites).
    marker_style='html': <!-- synlynk:start --> markers.
    marker_style='hash': # synlynk:start markers.

    Behaviour:
    1. File absent            → create with markers
    2. File present, no marks → append block at end
    3. File present, has marks → replace section between markers
    Returns True always (caller decides whether to proceed).
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    if marker_style == "none":
        with open(path, "w") as f:
            f.write(content)
        return True

    start = f'<!-- synlynk:start version="{VERSION}" tool="{tool}" -->'
    end = "<!-- synlynk:end -->"
    start_pattern = "<!-- synlynk:start"
    if marker_style == "hash":
        start = f'# synlynk:start version="{VERSION}"'
        end = "# synlynk:end"
        start_pattern = "# synlynk:start"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(f"{start}\n{content}\n{end}\n")
        return True

    with open(path) as f:
        existing = f.read()

    if start_pattern in existing:
        # Replace section between markers
        if marker_style == "html":
            pattern = r'<!-- synlynk:start[^>]* -->.*?<!-- synlynk:end -->'
        else:
            pattern = r'# synlynk:start[^\n]*\n.*?\n# synlynk:end'
        replacement = f"{start}\n{content}\n{end}"
        new_content = re.sub(pattern, replacement, existing, flags=re.DOTALL)
        with open(path, "w") as f:
            f.write(new_content)
        return True

    # Append block
    with open(path, "a") as f:
        f.write(f"\n{start}\n{content}\n{end}\n")
    return True
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "write_instruction_file" -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: _write_instruction_file — create/append/replace-section helper"
```

---

### Task 4: New tool templates — Cursor MDC, Copilot, Windsurf

Add `_build_cursor_mdc()`, `_build_copilot_instructions()`, `_build_windsurf_rules()` template functions, each returning the tool-native content string (without markers — `_write_instruction_file` adds those).

**Files:**
- Modify: `bin/synlynk.py` — add three functions near `_build_templates()`
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_build_cursor_mdc_has_frontmatter():
    from synlynk import _build_cursor_mdc
    content = _build_cursor_mdc()
    assert "alwaysApply: true" in content
    assert "---" in content
    assert "Session Start" in content
    assert "Git Worktree" in content


def test_build_copilot_instructions_no_frontmatter():
    from synlynk import _build_copilot_instructions
    content = _build_copilot_instructions()
    assert "---" not in content.splitlines()[0]  # no frontmatter on first line
    assert "Session Start" in content
    assert "synlynk checkpoint" in content


def test_build_windsurf_rules_is_terse():
    from synlynk import _build_windsurf_rules
    content = _build_windsurf_rules()
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) <= 8        # terse — no headers, bullet-style directives
    assert "context.md" in content
    assert "worktree" in content.lower() or "main" in content
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "build_cursor or build_copilot or build_windsurf" -v
```
Expected: 3 FAILED

- [ ] **Step 3: Add the three template functions to `bin/synlynk.py`**

Add after `_build_templates()` (after line ~1545):

```python
def _build_cursor_mdc() -> str:
    """Returns content for .cursor/rules/synlynk.mdc (Cursor MDC format, no markers)."""
    return """\
---
description: synlynk project protocol — session start, task tracking, git discipline
alwaysApply: true
---

# synlynk Protocol

## Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

## During Session
- Mark tasks `[x]` in `project-docs/todo.md` when complete — do not delete them
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a worktree for every feature or fix:
```
git worktree add .worktrees/<name> feat/<name>
git branch --show-current   # confirm before every commit
```

## At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
"""


def _build_copilot_instructions() -> str:
    """Returns content for .github/copilot-instructions.md synlynk block (plain markdown)."""
    return """\
## synlynk Session Protocol

### Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

### During Session
- Mark tasks `[x]` in `project-docs/todo.md` when complete — do not delete them
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary
- Never commit directly to `main`/`master` — create a worktree or branch first

### At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
"""


def _build_windsurf_rules() -> str:
    """Returns content for .windsurfrules synlynk block (terse directive format)."""
    return """\
Read .synlynk/context.md at session start.
Mark tasks [x] in project-docs/todo.md when complete.
Run `synlynk checkpoint` at task boundaries.
Never commit directly to main or master — use a worktree.
Append decisions to project-docs/memory.md with [@username].
Check .synlynk/sentinel.md for active alerts before starting work.
"""
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "build_cursor or build_copilot or build_windsurf" -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: tool-native templates — Cursor MDC, Copilot, Windsurf"
```

---

### Task 5: Manifest — `_write_instruction_manifest()` + `_load_instruction_manifest()`

Write and read `.synlynk/instructions.json`. SHA covers synlynk section content only.

**Files:**
- Modify: `bin/synlynk.py` — add two functions
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_write_instruction_manifest_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk import _write_instruction_manifest
    entries = {"CLAUDE.md": {"tool": "claude", "sha": "abc123"}}
    _write_instruction_manifest(entries)
    import json
    manifest = json.load(open(".synlynk/instructions.json"))
    assert manifest["schema_version"] == 1
    assert manifest["files"]["CLAUDE.md"]["sha"] == "abc123"
    assert manifest["files"]["CLAUDE.md"]["tool"] == "claude"
    assert "last_checked" in manifest["files"]["CLAUDE.md"]


def test_load_instruction_manifest_returns_empty_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk import _load_instruction_manifest
    assert _load_instruction_manifest() == {}


def test_manifest_sha_covers_only_synlynk_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk import _extract_synlynk_section, _compute_section_sha
    content_with_user = '# User stuff\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n# More user'
    section = _extract_synlynk_section(content_with_user, "html")
    sha = _compute_section_sha(section)
    # Changing user content outside markers must not change the sha
    content_modified = '# CHANGED user stuff\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n# More user'
    section2 = _extract_synlynk_section(content_modified, "html")
    sha2 = _compute_section_sha(section2)
    assert sha == sha2
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "manifest" -v
```
Expected: 3 FAILED

- [ ] **Step 3: Add manifest functions to `bin/synlynk.py`**

Add after `_build_windsurf_rules()`:

```python
_INSTRUCTIONS_MANIFEST = ".synlynk/instructions.json"

_INSTRUCTION_TARGETS = [
    # (path, tool, marker_style, detection_fn)
    ("CLAUDE.md",                          "claude",    "html", lambda: True),
    ("GEMINI.md",                          "agy",       "html", lambda: True),
    ("AGENTS.md",                          "codex",     "html", lambda: True),
    (".cursor/rules/synlynk.mdc",          "cursor",    "none", lambda: os.path.isdir(".cursor")),
    (".github/copilot-instructions.md",    "copilot",   "html", lambda: os.path.isdir(".github")),
    (".windsurfrules",                     "windsurf",  "hash", lambda: True),
    ("AI_INSTRUCTIONS.md",                 "universal", "html", lambda: True),
]


def _load_instruction_manifest() -> dict:
    """Returns files dict from .synlynk/instructions.json, or {} if absent."""
    if not os.path.exists(_INSTRUCTIONS_MANIFEST):
        return {}
    try:
        return json.load(open(_INSTRUCTIONS_MANIFEST)).get("files", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def _write_instruction_manifest(entries: dict) -> None:
    """Write .synlynk/instructions.json with schema_version, synlynk_version, and file SHAs."""
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    existing = _load_instruction_manifest()
    existing.update({
        path: {
            "tool": info["tool"],
            "sha": info["sha"],
            "last_checked": ts,
        }
        for path, info in entries.items()
    })
    manifest = {
        "schema_version": 1,
        "generated_at": ts,
        "synlynk_version": VERSION,
        "files": existing,
    }
    with open(_INSTRUCTIONS_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "manifest" -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: instruction manifest — write/load .synlynk/instructions.json"
```

---

### Task 6: Refactor `init()` Step 3 to use `_write_instruction_file()` + write manifest

Replace the current raw template writes in `init()` with calls to `_write_instruction_file()`. Write the manifest after all files are processed.

**Files:**
- Modify: `bin/synlynk.py` — `init()` function, around lines 2593–2610
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_init_writes_cursor_rules_when_cursor_dir_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".cursor", exist_ok=True)
    os.makedirs(".synlynk/state", exist_ok=True)
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    assert os.path.exists(".cursor/rules/synlynk.mdc")
    content = open(".cursor/rules/synlynk.mdc").read()
    assert "alwaysApply: true" in content


def test_init_skips_cursor_when_no_cursor_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    assert not os.path.exists(".cursor/rules/synlynk.mdc")


def test_init_appends_to_existing_copilot_instructions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".github", exist_ok=True)
    os.makedirs(".synlynk/state", exist_ok=True)
    open(".github/copilot-instructions.md", "w").write("# Existing rules\nDo something.\n")
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    text = open(".github/copilot-instructions.md").read()
    assert "# Existing rules" in text           # preserved
    assert "synlynk" in text.lower()            # appended
    assert text.index("# Existing rules") < text.index("<!-- synlynk:start")


def test_manifest_written_after_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    assert os.path.exists(".synlynk/instructions.json")
    import json
    manifest = json.load(open(".synlynk/instructions.json"))
    assert manifest["schema_version"] == 1
    assert "AI_INSTRUCTIONS.md" in manifest["files"]
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "test_init_writes_cursor or test_init_skips or test_init_appends or test_manifest_written_after_init" -v
```
Expected: 4 FAILED

- [ ] **Step 3: Refactor `init()` Step 3 in `bin/synlynk.py`**

Replace the block from `# Write agent instruction files.` through the closing brace (around lines 2593–2610) with:

```python
    # Write agent instruction files using _write_instruction_file().
    # Core trio: only write if agent was discovered as functional.
    trio_content = {
        "CLAUDE.md":   (templates.get("CLAUDE.md", ""), "html"),
        "GEMINI.md":   (templates.get("GEMINI.md", ""), "html"),
        "AGENTS.md":   (templates.get("AGENTS.md", ""), "html"),
    }
    _agent_guards = {"CLAUDE.md": "claude", "GEMINI.md": "agy", "AGENTS.md": "codex"}
    for fname, (content, mstyle) in trio_content.items():
        required = _agent_guards[fname]
        if required not in agent_set:
            continue
        _write_instruction_file(fname, required, content, mstyle)

    # Extended targets: written based on environment detection.
    extended = [
        (".cursor/rules/synlynk.mdc",       "cursor",    "none", _build_cursor_mdc()),
        (".github/copilot-instructions.md",  "copilot",   "html", _build_copilot_instructions()),
        (".windsurfrules",                   "windsurf",  "hash", _build_windsurf_rules()),
        ("AI_INSTRUCTIONS.md",              "universal",  "html", templates.get("AI_INSTRUCTIONS.md", "")),
    ]
    ext_guards = {
        ".cursor/rules/synlynk.mdc":       lambda: os.path.isdir(".cursor"),
        ".github/copilot-instructions.md": lambda: os.path.isdir(".github"),
        ".windsurfrules":                  lambda: True,
        "AI_INSTRUCTIONS.md":             lambda: True,
    }
    for fpath, tool, mstyle, content in extended:
        if ext_guards[fpath]():
            _write_instruction_file(fpath, tool, content, mstyle)

    # Also remove legacy .cursorrules if it exists (replaced by .cursor/rules/synlynk.mdc)
    # Write manifest of all tracked files with their SHAs.
    manifest_entries = {}
    for fpath, tool, mstyle, _ in [
        ("CLAUDE.md",                        "claude",    "html", None),
        ("GEMINI.md",                        "agy",       "html", None),
        ("AGENTS.md",                        "codex",     "html", None),
        (".cursor/rules/synlynk.mdc",        "cursor",    "none", None),
        (".github/copilot-instructions.md",  "copilot",   "html", None),
        (".windsurfrules",                   "windsurf",  "hash", None),
        ("AI_INSTRUCTIONS.md",               "universal", "html", None),
    ]:
        if not os.path.exists(fpath):
            continue
        file_content = open(fpath).read()
        section = _extract_synlynk_section(file_content, mstyle)
        if section is not None:
            manifest_entries[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}
    if manifest_entries:
        _write_instruction_manifest(manifest_entries)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "test_init_writes_cursor or test_init_skips or test_init_appends or test_manifest_written_after_init" -v
```
Expected: 4 PASSED

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -q
```
Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: refactor init() to use _write_instruction_file for all 7 targets + manifest"
```

---

### Task 7: `_check_instruction_drift()` + hook into `exec_command()`

Detect when synlynk sections have been modified externally. Fire `INSTRUCTION_DRIFT` sentinel events.

**Files:**
- Modify: `bin/synlynk.py` — add function + call in `exec_command()`
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_check_instruction_drift_detects_section_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    # Write a file with a synlynk section
    content = '<!-- synlynk:start version="0.4.1" tool="claude" -->\noriginal\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    original_sha = __import__('synlynk', fromlist=['_compute_section_sha'])._compute_section_sha("\noriginal\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": original_sha, "last_checked": "2026-06-17T10:00:00"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    # Now modify the synlynk section externally
    open("CLAUDE.md", "w").write('<!-- synlynk:start version="0.4.1" tool="claude" -->\nmodified\n<!-- synlynk:end -->\n')
    from synlynk import _check_instruction_drift
    drifted = _check_instruction_drift()
    assert "CLAUDE.md" in drifted


def test_check_instruction_drift_ignores_user_content_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    content = '# User\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sha = __import__('synlynk', fromlist=['_compute_section_sha'])._compute_section_sha("\nblock\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17T10:00:00"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    # Change only user content — synlynk section unchanged
    open("CLAUDE.md", "w").write('# CHANGED USER\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n')
    from synlynk import _check_instruction_drift
    drifted = _check_instruction_drift()
    assert "CLAUDE.md" not in drifted


def test_check_instruction_drift_returns_empty_when_no_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _check_instruction_drift
    assert _check_instruction_drift() == []


def test_instruction_drift_sentinel_fires_once_per_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    content = '<!-- synlynk:start version="0.4.1" tool="claude" -->\noriginal\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sha = __import__('synlynk', fromlist=['_compute_section_sha'])._compute_section_sha("\noriginal\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17T10:00:00"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    open("CLAUDE.md", "w").write('<!-- synlynk:start version="0.4.1" tool="claude" -->\nmodified\n<!-- synlynk:end -->\n')
    from synlynk import _check_instruction_drift
    _check_instruction_drift()  # first call — fires sentinel, updates manifest sha
    # second call — sha in manifest now matches file; must not fire again
    drifted2 = _check_instruction_drift()
    assert "CLAUDE.md" not in drifted2
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "drift" -v
```
Expected: 4 FAILED

- [ ] **Step 3: Add `_check_instruction_drift()` to `bin/synlynk.py`**

Add after `_write_instruction_manifest()`:

```python
_MARKER_STYLE_FOR_TOOL = {
    "claude":    "html",
    "agy":       "html",
    "codex":     "html",
    "cursor":    "none",
    "copilot":   "html",
    "windsurf":  "hash",
    "universal": "html",
}


def _check_instruction_drift() -> list:
    """Check tracked instruction files for external modifications to the synlynk section.

    Fires INSTRUCTION_DRIFT sentinel entries for any drifted file.
    Updates last_checked in manifest after each check.
    Returns list of drifted file paths.
    """
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        return []

    drifted = []
    updated_entries = {}
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')

    for fpath, info in manifest_data.items():
        tool = info.get("tool", "unknown")
        recorded_sha = info.get("sha", "")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if not os.path.exists(fpath):
            updated_entries[fpath] = {**info, "last_checked": ts}
            continue

        file_content = open(fpath).read()
        section = _extract_synlynk_section(file_content, marker_style)
        if section is None:
            updated_entries[fpath] = {**info, "last_checked": ts}
            continue

        current_sha = _compute_section_sha(section)
        updated_entries[fpath] = {**info, "sha": current_sha, "last_checked": ts}

        if current_sha != recorded_sha:
            drifted.append(fpath)
            _write_sentinel_alert(
                "WARN", "INSTRUCTION_DRIFT",
                f"{fpath} (tool: {tool}) — synlynk section modified externally. "
                f"Run `synlynk instructions diff {fpath}` to review. "
                f"Run `synlynk instructions update {fpath}` to reset. "
                f"[ack: synlynk instructions ack {fpath}]"
            )

    _write_instruction_manifest(updated_entries)
    return drifted
```

- [ ] **Step 4: Hook into `exec_command()`**

In `exec_command()` find the `finally:` block. After `_check_costs_freshness()` (line ~2768), add:

```python
        _check_instruction_drift()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "drift" -v
```
Expected: 4 PASSED

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -q
```
Expected: all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: _check_instruction_drift + INSTRUCTION_DRIFT sentinel — v0.4.1"
```

---

### Task 8: `cmd_instructions_status()` — status table

**Files:**
- Modify: `bin/synlynk.py` — add function
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing test**

```python
def test_cmd_instructions_status_shows_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    content = '<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sha = __import__('synlynk', fromlist=['_compute_section_sha'])._compute_section_sha("\nblock\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    from synlynk import cmd_instructions_status
    cmd_instructions_status()
    out = capsys.readouterr().out
    assert "CLAUDE.md" in out
    assert "clean" in out


def test_cmd_instructions_status_shows_drifted(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    open("CLAUDE.md", "w").write('<!-- synlynk:start version="0.4.1" tool="claude" -->\ncurrent\n<!-- synlynk:end -->\n')
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": "stale_sha_000", "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    from synlynk import cmd_instructions_status
    cmd_instructions_status()
    out = capsys.readouterr().out
    assert "drifted" in out


def test_cmd_instructions_status_shows_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": "abc", "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    from synlynk import cmd_instructions_status
    cmd_instructions_status()
    out = capsys.readouterr().out
    assert "missing" in out
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "cmd_instructions_status" -v
```
Expected: 3 FAILED

- [ ] **Step 3: Add `cmd_instructions_status()` to `bin/synlynk.py`**

Add after `_check_instruction_drift()`:

```python
def cmd_instructions_status() -> None:
    """Print status table for all tracked instruction files."""
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        print("  No instruction manifest found. Run `synlynk init` first.")
        return

    col = {"file": 38, "tool": 10, "status": 16, "checked": 12}
    header = (f"{'File':<{col['file']}}{'Tool':<{col['tool']}}"
              f"{'Status':<{col['status']}}{'Last checked':<{col['checked']}}")
    print(f"\n{_BOLD}{header}{_RESET}")
    print("─" * (col["file"] + col["tool"] + col["status"] + col["checked"]))

    for fpath, info in sorted(manifest_data.items()):
        tool = info.get("tool", "?")
        recorded_sha = info.get("sha", "")
        checked = info.get("last_checked", "")[:10]
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if not os.path.exists(fpath):
            status = f"{_YELLOW}✗ missing{_RESET}"
        else:
            file_content = open(fpath).read()
            section = _extract_synlynk_section(file_content, marker_style)
            if section is None:
                status = f"{_YELLOW}? no markers{_RESET}"
            elif _compute_section_sha(section) != recorded_sha:
                status = f"{_YELLOW}⚠ drifted{_RESET}"
            else:
                has_user = bool(re.sub(
                    r'<!-- synlynk:start.*?<!-- synlynk:end -->', '', file_content, flags=re.DOTALL
                ).strip() if marker_style == "html" else re.sub(
                    r'# synlynk:start.*?# synlynk:end', '', file_content, flags=re.DOTALL
                ).strip())
                status = (f"{_DIM}+ user-content{_RESET}" if has_user
                          else f"{_GREEN}✓ clean{_RESET}")

        print(f"{fpath:<{col['file']}}{tool:<{col['tool']}}"
              f"{status:<{col['status'] + 10}}{checked}")
    print()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "cmd_instructions_status" -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: cmd_instructions_status — status table for tracked instruction files"
```

---

### Task 9: `cmd_instructions_diff()`, `cmd_instructions_update()`, `cmd_instructions_ack()`

**Files:**
- Modify: `bin/synlynk.py` — add three functions
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cmd_instructions_update_replaces_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    old = '# User\n<!-- synlynk:start version="0.4.0" tool="claude" -->\nold content\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(old)
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.0",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": "old_sha", "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    from synlynk import cmd_instructions_update
    cmd_instructions_update("CLAUDE.md", new_content="updated content")
    text = open("CLAUDE.md").read()
    assert "old content" not in text
    assert "updated content" in text
    assert "# User" in text  # user content preserved
    updated_manifest = json.load(open(".synlynk/instructions.json"))
    assert updated_manifest["files"]["CLAUDE.md"]["sha"] != "old_sha"


def test_cmd_instructions_ack_suppresses_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    # Seed sentinel.md with a drift event for CLAUDE.md
    open(".synlynk/sentinel.md", "w").write(
        "# Sentinel Alerts\n"
        "- [WARN] [2026-06-17 10:00] INSTRUCTION_DRIFT: CLAUDE.md (tool: claude) — synlynk section modified externally.\n"
    )
    from synlynk import cmd_instructions_ack
    cmd_instructions_ack("CLAUDE.md")
    alerts = open(".synlynk/sentinel.md").read()
    assert "CLAUDE.md" not in alerts


def test_cmd_instructions_diff_shows_user_content(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    content = '# User rules here\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nsynlynk block\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sha = __import__('synlynk', fromlist=['_compute_section_sha'])._compute_section_sha("\nsynlynk block\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    from synlynk import cmd_instructions_diff
    cmd_instructions_diff("CLAUDE.md")
    out = capsys.readouterr().out
    assert "User rules here" in out
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_instruction_reach.py -k "cmd_instructions_update or cmd_instructions_ack or cmd_instructions_diff" -v
```
Expected: 3 FAILED

- [ ] **Step 3: Add the three functions to `bin/synlynk.py`**

Add after `cmd_instructions_status()`:

```python
def cmd_instructions_diff(file_path: Optional[str] = None) -> None:
    """Show user/tool content outside the synlynk section for review."""
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        print("  No instruction manifest found. Run `synlynk init` first.")
        return

    targets = ([file_path] if file_path else list(manifest_data.keys()))
    for fpath in targets:
        if fpath not in manifest_data:
            print(f"  {fpath}: not tracked in manifest")
            continue
        if not os.path.exists(fpath):
            print(f"  {fpath}: {_RED}missing{_RESET}")
            continue
        info = manifest_data[fpath]
        tool = info.get("tool", "unknown")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")
        file_content = open(fpath).read()

        print(f"\n{_BOLD}── {fpath} (tool: {tool}) ──{_RESET}")

        # Show user content outside synlynk markers
        if marker_style == "html":
            user_content = re.sub(
                r'<!-- synlynk:start.*?<!-- synlynk:end -->', '', file_content, flags=re.DOTALL
            ).strip()
        elif marker_style == "hash":
            user_content = re.sub(
                r'# synlynk:start.*?# synlynk:end', '', file_content, flags=re.DOTALL
            ).strip()
        else:
            user_content = ""

        if user_content:
            print(f"{_DIM}User/tool content outside synlynk section:{_RESET}")
            print(user_content)
        else:
            print(f"{_DIM}No user content outside synlynk section.{_RESET}")


def cmd_instructions_update(file_path: Optional[str] = None,
                             new_content: Optional[str] = None) -> None:
    """Re-generate the synlynk section for file(s) and refresh manifest SHAs.

    file_path=None updates all tracked files.
    new_content is used only in tests — production callers pass None and content
    is rebuilt from the relevant template function.
    """
    manifest_data = _load_instruction_manifest()
    targets = ([file_path] if file_path else list(manifest_data.keys()))

    _tool_content_builders = {
        "cursor":    (_build_cursor_mdc,            "none"),
        "copilot":   (_build_copilot_instructions,  "html"),
        "windsurf":  (_build_windsurf_rules,        "hash"),
        "universal": (lambda: _build_templates().get("AI_INSTRUCTIONS.md", ""), "html"),
    }

    updated = {}
    for fpath in targets:
        if fpath not in manifest_data:
            print(f"  {fpath}: not tracked — skipping")
            continue
        info = manifest_data[fpath]
        tool = info.get("tool", "unknown")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if new_content is not None:
            content = new_content
        elif tool in _tool_content_builders:
            builder, _ = _tool_content_builders[tool]
            content = builder()
        else:
            templates = _build_templates()
            fname = os.path.basename(fpath)
            content = templates.get(fname, "")

        _write_instruction_file(fpath, tool, content, marker_style)

        if os.path.exists(fpath):
            section = _extract_synlynk_section(open(fpath).read(), marker_style)
            if section:
                updated[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}

        print(f"  {_GREEN}✓{_RESET} Updated {fpath}")

    if updated:
        _write_instruction_manifest(updated)


def cmd_instructions_ack(file_path: str) -> None:
    """Acknowledge an INSTRUCTION_DRIFT event for a specific file.

    Removes matching INSTRUCTION_DRIFT lines from sentinel.md so the alert
    is suppressed until the SHA changes again.
    """
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        return
    with open(sentinel_file) as f:
        lines = f.readlines()
    filtered = [
        l for l in lines
        if not (f"INSTRUCTION_DRIFT" in l and file_path in l)
    ]
    with open(sentinel_file, "w") as f:
        f.writelines(filtered)
    print(f"  {_GREEN}✓{_RESET} Acknowledged drift for {file_path}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_instruction_reach.py -k "cmd_instructions_update or cmd_instructions_ack or cmd_instructions_diff" -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: cmd_instructions_diff/update/ack — on-demand review and re-generation"
```

---

### Task 10: Wire `synlynk instructions` CLI subparser + run full suite

**Files:**
- Modify: `bin/synlynk.py` — subparser wiring in `main()`
- Test: `tests/test_instruction_reach.py`

- [ ] **Step 1: Write failing test**

```python
def test_instructions_status_subcommand_wired(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import json
    json.dump({"schema_version": 1, "generated_at": "...", "synlynk_version": "0.4.1", "files": {}},
              open(".synlynk/instructions.json", "w"))
    import subprocess
    result = subprocess.run(
        ["python3", "bin/synlynk.py", "instructions", "status"],
        capture_output=True, text=True, cwd=str(tmp_path.parent.parent
            if "synlynk" in str(tmp_path) else tmp_path)
    )
    # Just verify it doesn't crash with exit code 2 (argparse error)
    assert result.returncode != 2
```

- [ ] **Step 2: Run to confirm it fails**

```bash
pytest tests/test_instruction_reach.py::test_instructions_status_subcommand_wired -v
```
Expected: FAILED (returncode 2 — argparse unknown command)

- [ ] **Step 3: Add `instructions` subparser to `main()` in `bin/synlynk.py`**

After the `pr_sub` block (around line 2908), add:

```python
    instructions_parser = subparsers.add_parser(
        "instructions", help="Manage synlynk instruction files across AI tools"
    )
    instructions_sub = instructions_parser.add_subparsers(dest="instructions_action")
    instructions_sub.add_parser("status", help="Show status of all tracked instruction files")
    instr_diff_parser = instructions_sub.add_parser(
        "diff", help="Show user/tool content outside synlynk sections"
    )
    instr_diff_parser.add_argument("file", nargs="?", default=None,
                                   help="Specific file to diff (default: all)")
    instr_update_parser = instructions_sub.add_parser(
        "update", help="Re-generate synlynk sections and refresh manifest"
    )
    instr_update_parser.add_argument("file", nargs="?", default=None,
                                     help="Specific file to update (default: all)")
    instr_ack_parser = instructions_sub.add_parser(
        "ack", help="Acknowledge an INSTRUCTION_DRIFT sentinel event"
    )
    instr_ack_parser.add_argument("file", help="File to acknowledge drift for")
```

In the dispatch section (`if args.command == ...`), add after the `pr` block:

```python
    elif args.command == "instructions":
        action = getattr(args, "instructions_action", None)
        if action == "status" or action is None:
            cmd_instructions_status()
        elif action == "diff":
            cmd_instructions_diff(getattr(args, "file", None))
        elif action == "update":
            cmd_instructions_update(getattr(args, "file", None))
        elif action == "ack":
            cmd_instructions_ack(args.file)
        else:
            instructions_parser.print_help()
```

- [ ] **Step 4: Run the wiring test**

```bash
pytest tests/test_instruction_reach.py::test_instructions_status_subcommand_wired -v
```
Expected: PASSED

- [ ] **Step 5: Run the complete test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```
Expected: all tests pass, including the 13 new tests in `test_instruction_reach.py`

- [ ] **Step 6: Smoke-test the CLI manually**

```bash
cd /tmp && mkdir test-synlynk-v041 && cd test-synlynk-v041 && git init
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py init
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py instructions status
```
Expected: init runs without error, `instructions status` prints a table showing the tracked files.

- [ ] **Step 7: Final commit and tag**

```bash
cd /Users/nikhilsoman/dev/synlynk
git add bin/synlynk.py tests/test_instruction_reach.py
git commit -m "feat: wire synlynk instructions subparser — v0.4.1 complete"
```
