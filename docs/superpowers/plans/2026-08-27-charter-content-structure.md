# Charter Content & Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce a minimal YAML-frontmatter + three-required-section schema on all agent charters, retire the dead `.synlynk/agents/<id>.yaml` projection, and migrate the 7 live charters to the new schema (revision 3), restoring `pm`'s lost competitive-intelligence content in the process.

**Architecture:** A new dependency-free leaf module `synlynk/charter_schema.py` owns frontmatter parsing/validation/rendering (no PyYAML available — hand-rolled parser). `synlynk/agent_store.py`'s `propose_charter_revision` calls `charter_schema.validate_charter()` before writing; its projection-writing functions (`regenerate_agent_projection` and helpers) are deleted outright. `synlynk/agent_cli.py`'s `SEED_CHARTERS` is rewritten to the new schema and its `init`/`edit` handlers drop the projection call and surface `CharterValidationError`. A new `agent sync-routing` CLI subcommand regenerates a charter's `dispatch_routing` frontmatter block from `.synlynk/policy.json` via the existing `synlynk/policy.py:load_policy()`. Finally, the 7 live on-machine charters are migrated to revision 3 by hand-authoring schema-compliant content per role.

**Tech Stack:** Python 3 (zero third-party dependencies — no PyYAML), pytest, existing `synlynk/agent_store.py` content-hash versioning.

---

## File Structure

- **Create:** `synlynk/charter_schema.py` — frontmatter split/parse/validate/render, `CharterValidationError`, `KNOWN_ROLES`/`VALID_DURABILITY`/`REQUIRED_SECTIONS`/`REQUIRED_FRONTMATTER_KEYS` constants.
- **Create:** `tests/test_charter_schema.py` — unit tests for the above.
- **Modify:** `synlynk/agent_store.py` — wire `charter_schema.validate_charter()` into `propose_charter_revision`; delete `regenerate_agent_projection`, `_dump_flat_yaml`, `_read_existing_projection_overrides`, `_agent_role`; add `sync_dispatch_routing()`.
- **Modify:** `tests/test_agent_store.py` — replace non-schema-compliant charter literals with a `_valid_charter()` test helper; delete the 4 projection-only tests; trim `test_full_flow_canonical_content_lives_only_in_workspace_store`; add tests for `sync_dispatch_routing`.
- **Modify:** `synlynk/agent_cli.py` — rewrite `SEED_CHARTERS` (8 roles, new schema); source `ROLES` from `charter_schema.KNOWN_ROLES`; `cmd_agent_init`/`cmd_agent_edit` drop the projection call and catch `CharterValidationError`; add `cmd_agent_sync_routing`.
- **Modify:** `tests/test_agent_cli.py` — delete the 2 projection-only tests; update edit tests' charter content to schema-valid strings; add a test for `cmd_agent_sync_routing`.
- **Modify:** `synlynk/cli.py` — wire `agent sync-routing <id_or_alias>` subcommand (parser + dispatch block).
- **Modify:** `tests/test_cli.py` (or wherever `agent` subcommand parsing is tested — verified below) — add parser-level test for `sync-routing` if such tests exist for other `agent` actions.
- **Modify:** `CHANGELOG.md` — `[Unreleased]` entry.
- **No file creation for migration** — the 7 live charters are migrated via `synlynk agent edit <role> --charter <file>` CLI invocations (operational task, not a source file change), documented as explicit commands in Task 9.

---

## Task 1: `charter_schema.py` — constants, frontmatter split/parse, `CharterValidationError`

**Files:**
- Create: `synlynk/charter_schema.py`
- Test: `tests/test_charter_schema.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_charter_schema.py`:

```python
import pytest

from synlynk import charter_schema


def _valid_charter(role="dev", extra_frontmatter="", extra_body=""):
    return (
        "---\n"
        "schema_version: 1\n"
        f"role: {role}\n"
        'description: "Implementation — writes the code."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        f"{extra_frontmatter}"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "Do the work.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Escalates to human_authority_role.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns the Implement stage.\n"
        f"{extra_body}"
    )


def test_split_frontmatter_returns_frontmatter_and_body():
    content = "---\nrole: dev\n---\n\n## Instructions\n\nbody text\n"
    frontmatter_text, body = charter_schema.split_frontmatter(content)
    assert frontmatter_text == "role: dev"
    assert body == "\n\n## Instructions\n\nbody text\n"


def test_split_frontmatter_missing_returns_none():
    content = "## Instructions\n\nno frontmatter here\n"
    frontmatter_text, body = charter_schema.split_frontmatter(content)
    assert frontmatter_text is None
    assert body == content


def test_split_frontmatter_unclosed_returns_none():
    content = "---\nrole: dev\n\n## Instructions\n\nbody\n"
    frontmatter_text, body = charter_schema.split_frontmatter(content)
    assert frontmatter_text is None
    assert body == content


def test_parse_frontmatter_scalars_and_quoted_strings():
    data = charter_schema.parse_frontmatter(
        'schema_version: 1\nrole: dev\ndescription: "Implementation — writes the code."\n'
    )
    assert data == {
        "schema_version": "1",
        "role": "dev",
        "description": "Implementation — writes the code.",
    }


def test_parse_frontmatter_empty_flow_list():
    data = charter_schema.parse_frontmatter("tools: []\n")
    assert data == {"tools": []}


def test_parse_frontmatter_flow_list_with_items():
    data = charter_schema.parse_frontmatter("tools: [bash, editor]\n")
    assert data == {"tools": ["bash", "editor"]}


def test_parse_frontmatter_block_list():
    data = charter_schema.parse_frontmatter("credentials:\n  - github_token\n  - npm_token\n")
    assert data == {"credentials": ["github_token", "npm_token"]}


def test_validate_charter_accepts_well_formed_content():
    data = charter_schema.validate_charter(_valid_charter())
    assert data["role"] == "dev"
    assert data["durability"] == "dispatch-only"


def test_validate_charter_rejects_missing_frontmatter():
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter("## Instructions\n\nno frontmatter\n")
    assert "frontmatter" in str(exc_info.value)


def test_validate_charter_rejects_missing_required_keys():
    content = (
        "---\n"
        "role: dev\n"
        "---\n"
        "\n"
        "## Instructions\n\nx\n\n## Authority & Escalation\n\nx\n\n## Workflow Ownership\n\nx\n"
    )
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(content)
    message = str(exc_info.value)
    assert "schema_version" in message
    assert "description" in message
    assert "durability" in message
    assert "tools" in message
    assert "credentials" in message


def test_validate_charter_rejects_unknown_role():
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(_valid_charter(role="not-a-role"))
    assert "not-a-role" in str(exc_info.value)


def test_validate_charter_rejects_invalid_durability():
    content = _valid_charter().replace("durability: dispatch-only", "durability: whenever")
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(content)
    assert "whenever" in str(exc_info.value)


def test_validate_charter_rejects_missing_section():
    content = _valid_charter().replace(
        "## Workflow Ownership\n\nOwns the Implement stage.\n", ""
    )
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(content)
    assert "Workflow Ownership" in str(exc_info.value)


def test_validate_charter_rejects_empty_section():
    content = _valid_charter().replace(
        "## Instructions\n\nDo the work.\n", "## Instructions\n\n"
    )
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(content)
    assert "Instructions" in str(exc_info.value)


def test_validate_charter_reports_all_missing_sections_at_once():
    content = (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "x"\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n\nsomething\n"
    )
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(content)
    message = str(exc_info.value)
    assert "Authority & Escalation" in message
    assert "Workflow Ownership" in message


def test_validate_charter_dispatch_routing_presence_does_not_affect_validity():
    with_routing = _valid_charter(
        extra_frontmatter="dispatch_routing:\n  implement:\n    harness: codex\n    fallback: [grok]\n"
    )
    data = charter_schema.validate_charter(with_routing)
    assert data["role"] == "dev"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_charter_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.charter_schema'`

- [ ] **Step 3: Implement `charter_schema.py`**

Create `synlynk/charter_schema.py`:

```python
"""Charter frontmatter schema: parsing, validation, and rendering.

Zero-dependency (no PyYAML) — the project has no third-party dependencies,
so this hand-rolls just enough of YAML's flat-mapping/list syntax to cover
what a charter's frontmatter actually uses. It is not a general YAML parser.

See docs/superpowers/specs/2026-08-27-charter-content-structure-design.md.
"""
from __future__ import annotations

KNOWN_ROLES = (
    "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot",
)
VALID_DURABILITY = ("durable", "session-only", "dispatch-only")
REQUIRED_SECTIONS = ("Instructions", "Authority & Escalation", "Workflow Ownership")
REQUIRED_FRONTMATTER_KEYS = (
    "schema_version", "role", "description", "durability", "tools", "credentials",
)


class CharterValidationError(Exception):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def split_frontmatter(content: str):
    """Split `content` into (frontmatter_text, body).

    Returns (None, content) if content does not start with a `---` line
    followed by a closing `---` line.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, content
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None, content
    frontmatter_text = "\n".join(lines[1:end_idx])
    body_text = "\n".join(lines[end_idx + 1:])
    return frontmatter_text, body_text


def parse_frontmatter(frontmatter_text: str) -> dict:
    """Parse a flat YAML-like frontmatter block into a dict.

    Supports: scalars, quoted strings, `[]` and `[a, b]` flow lists,
    and `- item` block lists. Does not support nested mappings as values
    (dispatch_routing's nested block is treated as opaque text elsewhere,
    never round-tripped through this parser).
    """
    data = {}
    lines = frontmatter_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith(" "):
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            j = i + 1
            block_lines = []
            while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
                block_lines.append(lines[j])
                j += 1
            non_blank = [bl for bl in block_lines if bl.strip()]
            if non_blank and all(bl.strip().startswith("- ") for bl in non_blank):
                data[key] = [bl.strip()[2:].strip() for bl in non_blank]
            else:
                data[key] = "\n".join(block_lines)
            i = j
        elif rest == "[]":
            data[key] = []
            i += 1
        elif rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            data[key] = [x.strip() for x in inner.split(",")] if inner else []
            i += 1
        else:
            if len(rest) >= 2 and rest[0] == '"' and rest[-1] == '"':
                rest = rest[1:-1]
            data[key] = rest
            i += 1
    return data


def validate_charter(content: str, known_roles=KNOWN_ROLES) -> dict:
    """Validate charter `content` against the required schema.

    Returns the parsed frontmatter dict on success. Raises
    CharterValidationError (listing every problem found, not just the
    first) on failure.
    """
    frontmatter_text, body = split_frontmatter(content)
    if frontmatter_text is None:
        raise CharterValidationError([
            "missing YAML frontmatter block (content must start with '---' "
            "and the frontmatter must close with a second '---' line)"
        ])
    data = parse_frontmatter(frontmatter_text)
    errors = []

    missing_keys = [k for k in REQUIRED_FRONTMATTER_KEYS if k not in data]
    if missing_keys:
        errors.append(f"missing required frontmatter key(s): {', '.join(missing_keys)}")

    if "role" in data and data["role"] not in known_roles:
        errors.append(f"unknown role {data['role']!r}; must be one of {', '.join(known_roles)}")

    if "durability" in data and data["durability"] not in VALID_DURABILITY:
        errors.append(
            f"invalid durability {data['durability']!r}; "
            f"must be one of {', '.join(VALID_DURABILITY)}"
        )

    for list_key in ("tools", "credentials"):
        if list_key in data and not isinstance(data[list_key], list):
            errors.append(f"{list_key!r} must be a list (use '[]' for empty)")

    missing_sections = []
    for section in REQUIRED_SECTIONS:
        header = f"## {section}"
        if header not in body:
            missing_sections.append(section)
            continue
        after = body.split(header, 1)[1]
        next_header_idx = after.find("\n## ")
        section_body = after[:next_header_idx] if next_header_idx != -1 else after
        if not section_body.strip():
            missing_sections.append(section)
    if missing_sections:
        errors.append(f"missing or empty required section(s): {', '.join(missing_sections)}")

    if errors:
        raise CharterValidationError(errors)
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_charter_schema.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_schema.py tests/test_charter_schema.py
git commit -m "feat: add charter_schema module for charter frontmatter validation"
```

---

## Task 2: `charter_schema.py` — `dispatch_routing` rendering and frontmatter-block editing

**Files:**
- Modify: `synlynk/charter_schema.py`
- Test: `tests/test_charter_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_charter_schema.py`:

```python
def test_render_dispatch_routing_block_nested_dict():
    block = charter_schema.render_dispatch_routing_block({
        "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
        "css": {"harness": "agy", "fallback": []},
    })
    assert block == (
        "dispatch_routing:\n"
        "  implement:\n"
        "    harness: codex\n"
        "    fallback: [grok, agy]\n"
        "  css:\n"
        "    harness: agy\n"
        "    fallback: []\n"
    )


def test_set_frontmatter_block_appends_when_key_absent():
    content = _valid_charter()
    updated = charter_schema.set_frontmatter_block(
        content, "dispatch_routing", "dispatch_routing:\n  implement:\n    harness: codex\n"
    )
    frontmatter_text, body = charter_schema.split_frontmatter(updated)
    assert "dispatch_routing:\n  implement:\n    harness: codex" in frontmatter_text
    assert body == charter_schema.split_frontmatter(content)[1]


def test_set_frontmatter_block_replaces_existing_key():
    content = _valid_charter(
        extra_frontmatter="dispatch_routing:\n  implement:\n    harness: grok\n"
    )
    updated = charter_schema.set_frontmatter_block(
        content, "dispatch_routing", "dispatch_routing:\n  implement:\n    harness: codex\n"
    )
    frontmatter_text, _ = charter_schema.split_frontmatter(updated)
    assert "harness: codex" in frontmatter_text
    assert "harness: grok" not in frontmatter_text
    assert frontmatter_text.count("dispatch_routing:") == 1


def test_set_frontmatter_block_preserves_other_keys():
    content = _valid_charter()
    updated = charter_schema.set_frontmatter_block(
        content, "dispatch_routing", "dispatch_routing:\n  implement:\n    harness: codex\n"
    )
    data = charter_schema.validate_charter(updated)
    assert data["role"] == "dev"
    assert data["durability"] == "dispatch-only"


def test_set_frontmatter_block_raises_without_frontmatter():
    with pytest.raises(charter_schema.CharterValidationError):
        charter_schema.set_frontmatter_block("no frontmatter here", "dispatch_routing", "x: y\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_charter_schema.py -v -k "render_dispatch_routing or set_frontmatter_block"`
Expected: FAIL with `AttributeError: module 'synlynk.charter_schema' has no attribute 'render_dispatch_routing_block'`

- [ ] **Step 3: Implement the rendering/editing functions**

Append to `synlynk/charter_schema.py`:

```python
def _render_task_allocation(task_allocation: dict) -> str:
    lines = ["dispatch_routing:"]
    for task_type, entry in task_allocation.items():
        lines.append(f"  {task_type}:")
        lines.append(f"    harness: {entry['harness']}")
        fallback = entry.get("fallback", [])
        lines.append(f"    fallback: [{', '.join(fallback)}]")
    return "\n".join(lines) + "\n"


def render_dispatch_routing_block(task_allocation: dict) -> str:
    """Render a policy.json task_allocation table as a dispatch_routing frontmatter block."""
    return _render_task_allocation(task_allocation)


def set_frontmatter_block(content: str, key: str, block_text: str) -> str:
    """Replace (or append) a top-level frontmatter key's block in `content`.

    `block_text` must be the full rendered block including its own
    trailing newline, e.g. "dispatch_routing:\\n  implement:\\n    harness: codex\\n".
    """
    frontmatter_text, body = split_frontmatter(content)
    if frontmatter_text is None:
        raise CharterValidationError([f"cannot set {key!r}: no frontmatter block present"])

    lines = frontmatter_text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        line_key = line.split(":", 1)[0].strip()
        if line_key == key:
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                i += 1
            continue
        out.append(line)
        i += 1

    while out and not out[-1].strip():
        out.pop()

    out.append(block_text.rstrip("\n"))
    new_frontmatter = "\n".join(out)
    return f"---\n{new_frontmatter}\n---{body}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_charter_schema.py -v`
Expected: PASS (22 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_schema.py tests/test_charter_schema.py
git commit -m "feat: add dispatch_routing rendering and frontmatter-block editing to charter_schema"
```

---

## Task 3: Wire `validate_charter` into `agent_store.propose_charter_revision`

**Files:**
- Modify: `synlynk/agent_store.py`
- Modify: `tests/test_agent_store.py`

- [ ] **Step 1: Read the current `propose_charter_revision` to confirm the exact insertion point**

Run: `grep -n "def propose_charter_revision" -A 20 synlynk/agent_store.py`

Expected output shows a function that computes `content_hash`, checks `parent_revision` against the current on-disk revision (raising `RevisionConflictError` on mismatch), then calls `_write_versioned_file`. The validation call goes at the top of the function body, before any hash/conflict logic — an invalid charter should never even reach the conflict check.

- [ ] **Step 2: Add the validation call**

In `synlynk/agent_store.py`, add the import near the top (alongside the other `from synlynk import ...` / stdlib imports):

```python
from synlynk import charter_schema
```

Then, at the very start of `propose_charter_revision`'s body (before any existing logic), add:

```python
    charter_schema.validate_charter(content)
```

(`content` is the function's existing parameter name — confirm via the same grep from Step 1 before editing; do not rename it.)

- [ ] **Step 3: Add a test that invalid content is rejected**

`tests/test_agent_store.py` currently starts with just `import json` / `import os` (no `pytest` import — confirmed via `head -5 tests/test_agent_store.py`). Add `import pytest` as a third top-level import line before adding the new test.

Add to `tests/test_agent_store.py`, near the other `propose_charter_revision` tests:

```python
def test_propose_charter_revision_rejects_invalid_content(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store, charter_schema

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    with pytest.raises(charter_schema.CharterValidationError):
        agent_store.propose_charter_revision(
            "dev-primary", "not a valid charter", actor="human:nikhilsoman", parent_revision=0
        )
```

- [ ] **Step 4: Run test to verify it fails, then update existing non-compliant literals**

Run: `python3 -m pytest tests/test_agent_store.py -v -k "propose_charter_revision or charter_revisions_jsonl or full_flow_canonical"`

Expected: several existing tests now FAIL, because they write plain strings like `"# Charter v1"` which are no longer valid charter content. Fix them as follows.

At the top of `tests/test_agent_store.py`, add a module-level helper (after the existing imports, before the first test function):

```python
def _valid_charter(marker: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        f'description: "{marker}"\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        f"\n{marker} instructions body.\n"
        "\n"
        "## Authority & Escalation\n"
        "\nEscalates per policy.\n"
        "\n"
        "## Workflow Ownership\n"
        "\nOwns nothing in particular for this test.\n"
    )
```

Update `test_propose_charter_revision_writes_and_reads_back`:

```python
def test_propose_charter_revision_writes_and_reads_back(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    charter_v1 = _valid_charter("Charter v1")
    new_revision = agent_store.propose_charter_revision(
        "dev-primary", charter_v1, actor="human:nikhilsoman", parent_revision=0
    )
    assert new_revision == 1

    content, revision = agent_store.read_charter("dev-primary")
    assert content == charter_v1
    assert revision == 1
```

Update `test_propose_charter_revision_stale_parent_raises_conflict`:

```python
def test_propose_charter_revision_stale_parent_raises_conflict(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    try:
        agent_store.propose_charter_revision(
            "dev-primary", _valid_charter("Charter v2 stale"), actor="human:nikhilsoman", parent_revision=0
        )
        assert False, "expected agent_store.RevisionConflictError"
    except agent_store.RevisionConflictError:
        pass
```

Update `test_charter_revisions_jsonl_provenance_chain`:

```python
def test_charter_revisions_jsonl_provenance_chain(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store
    import json as _json

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Charter v2"), actor="agent:dev-primary", parent_revision=1
    )

    revisions_path = os.path.join(
        agent_store.agent_store_path("dev-primary"), "charter.revisions.jsonl"
    )
    lines = [_json.loads(line) for line in open(revisions_path) if line.strip()]
    assert len(lines) == 2
    assert lines[0]["revision"] == 1
    assert lines[0]["parent_hash"] is None
    assert lines[1]["revision"] == 2
    assert lines[1]["parent_hash"] == lines[0]["content_hash"]
    assert lines[1]["actor"] == "agent:dev-primary"
```

In `test_full_flow_canonical_content_lives_only_in_workspace_store`, replace the two `propose_charter_revision` calls and their content assertions:

```python
    rev1 = agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    assert rev1 == 1
    rev2 = agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v2 expanded scope"), actor="agent:dev-primary", parent_revision=1
    )
    assert rev2 == 2

    content, revision = agent_store.read_charter("dev-primary")
    assert content == _valid_charter("Dev charter v2 expanded scope")
    assert revision == 2
```

(Leave the rest of that test's body as-is for now — the `regenerate_agent_projection` lines inside it are removed in Task 4, not here.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agent_store.py -v -k "propose_charter_revision or charter_revisions_jsonl or full_flow_canonical"`
Expected: PASS for the charter-content-focused assertions in these tests (the `full_flow` test will still fail at the `regenerate_agent_projection` line until Task 4 — that's expected and addressed next task).

- [ ] **Step 6: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: enforce charter schema validation in propose_charter_revision"
```

---

## Task 4: Retire the `.synlynk/agents/<id>.yaml` projection mechanism

**Files:**
- Modify: `synlynk/agent_store.py`
- Modify: `tests/test_agent_store.py`

- [ ] **Step 1: Confirm the functions to delete**

Run: `grep -n "_dump_flat_yaml\|_read_existing_projection_overrides\|_agent_role\|regenerate_agent_projection" synlynk/agent_store.py`

Confirm all four names appear only as function definitions and internal call sites within `agent_store.py` (no other module imports them — already confirmed via prior grep across the whole repo during spec research; re-run `grep -rn "regenerate_agent_projection\|_dump_flat_yaml" --include="*.py" .` from the repo root to double check nothing outside `agent_store.py`/`agent_cli.py`/tests references them before deleting).

- [ ] **Step 2: Delete the functions from `agent_store.py`**

Remove the full definitions of `_dump_flat_yaml`, `_agent_role`, `_read_existing_projection_overrides`, and `regenerate_agent_projection` from `synlynk/agent_store.py`. Use the line ranges from the Step 1 grep output to locate and remove each function body in full (from its `def` line through its last indented line, plus any blank lines immediately preceding it that separate it from the prior function).

- [ ] **Step 3: Delete the 4 projection-only tests from `tests/test_agent_store.py`**

Remove these four test functions in full: `test_regenerate_agent_projection_writes_flat_yaml`, `test_regenerate_agent_projection_is_idempotent`, `test_regenerate_agent_projection_merges_overrides_across_calls`, `test_regenerate_agent_projection_path_is_gitignored`.

- [ ] **Step 4: Trim `test_full_flow_canonical_content_lives_only_in_workspace_store`**

Replace the function body (keep the parts through the `content`/`revision` assertions added in Task 3, drop everything projection-related) with:

```python
def test_full_flow_canonical_content_lives_only_in_workspace_store(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    workspace_id = agent_store.get_workspace_id()
    assert workspace_id

    agent_store.register_agent(
        "dev-primary",
        aliases=[
            {"kind": "role_slug", "value": "dev"},
            {"kind": "github_app_slug", "value": "synlynk-dev[bot]"},
        ],
    )
    assert agent_store.resolve_agent_id("dev") == "dev-primary"

    rev1 = agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    assert rev1 == 1
    rev2 = agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v2 expanded scope"), actor="agent:dev-primary", parent_revision=1
    )
    assert rev2 == 2

    content, revision = agent_store.read_charter("dev-primary")
    assert content == _valid_charter("Dev charter v2 expanded scope")
    assert revision == 2

    canonical_charter_path = os.path.join(
        agent_store.agent_store_path("dev-primary"), "charter.md"
    )
    assert str(fake_home) in canonical_charter_path
    with open(canonical_charter_path) as f:
        assert "Dev charter v2" in f.read()
```

- [ ] **Step 5: Check whether `conftest.py`'s `git_worktree_repo` fixture is still used**

Run: `grep -rn "git_worktree_repo" tests/`

If the only remaining usage was the now-deleted `test_regenerate_agent_projection_path_is_gitignored`, the fixture in `tests/conftest.py` becomes unused. Leave the fixture definition in place (it's a small, generically-useful fixture and removing it is out of scope for this plan — YAGNI cuts toward not touching unrelated fixture infrastructure); pytest does not warn on unused fixtures by default, so no test failure results either way.

- [ ] **Step 6: Run full agent_store test suite**

Run: `python3 -m pytest tests/test_agent_store.py -v`
Expected: PASS, all tests (projection tests gone, remaining tests pass).

- [ ] **Step 7: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "refactor: retire dead .synlynk/agents/<id>.yaml projection mechanism"
```

---

## Task 5: `agent_store.sync_dispatch_routing()`

**Files:**
- Modify: `synlynk/agent_store.py`
- Modify: `tests/test_agent_store.py`

This reuses `synlynk/policy.py:load_policy()` (two-tier workspace+repo merge already used elsewhere in the codebase for `check_authority`) rather than writing a second, parallel `.synlynk/policy.json` reader — avoids duplicating JSON-merge logic for the same file. `load_policy()`'s merged result exposes `<role>_authority` keys at the top level (e.g. `merged["dev_authority"]["task_allocation"]`); only `dev_authority` currently has a populated `task_allocation` table in `DEFAULT_WORKSPACE_POLICY`/`.synlynk/policy.json`, so every other role naturally no-ops.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_agent_store.py`:

```python
def test_sync_dispatch_routing_populates_block_for_dev(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v1"), actor="human:nikhilsoman", parent_revision=0
    )

    new_revision = agent_store.sync_dispatch_routing("dev-primary", "dev", actor="cli")
    assert new_revision == 2

    content, revision = agent_store.read_charter("dev-primary")
    assert revision == 2
    assert "dispatch_routing:" in content
    assert "harness: codex" in content


def test_sync_dispatch_routing_is_noop_for_role_without_task_allocation(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("qa-primary", aliases=[{"kind": "role_slug", "value": "qa"}])
    charter_v1 = _valid_charter("QA charter v1").replace("role: dev", "role: qa")
    agent_store.propose_charter_revision(
        "qa-primary", charter_v1, actor="human:nikhilsoman", parent_revision=0
    )

    unchanged_revision = agent_store.sync_dispatch_routing("qa-primary", "qa", actor="cli")
    assert unchanged_revision == 1

    content, revision = agent_store.read_charter("qa-primary")
    assert revision == 1
    assert "dispatch_routing" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_agent_store.py -v -k sync_dispatch_routing`
Expected: FAIL with `AttributeError: module 'synlynk.agent_store' has no attribute 'sync_dispatch_routing'`

- [ ] **Step 3: Implement `sync_dispatch_routing`**

Add to `synlynk/agent_store.py` (near `propose_charter_revision`/`read_charter`, since it composes both):

```python
def sync_dispatch_routing(agent_id: str, role: str, actor: str) -> int:
    """Regenerate an agent's charter `dispatch_routing` frontmatter block
    from .synlynk/policy.json's <role>_authority.task_allocation table.

    No-op (returns the current revision unchanged, no new revision written)
    if the role has no task_allocation entry in policy.json.
    """
    from synlynk import policy as policy_mod

    content, revision = read_charter(agent_id)
    merged_policy = policy_mod.load_policy(repo_path=os.getcwd())
    authority = merged_policy.get(f"{role}_authority", {})
    task_allocation = authority.get("task_allocation")
    if not task_allocation:
        return revision

    block = charter_schema.render_dispatch_routing_block(task_allocation)
    new_content = charter_schema.set_frontmatter_block(content, "dispatch_routing", block)
    return propose_charter_revision(agent_id, new_content, actor=actor, parent_revision=revision)
```

Confirm `os` is already imported at the top of `agent_store.py` (it is, per existing usage elsewhere in the file — `os.path.expanduser` etc.); no new import needed beyond the inline `from synlynk import policy as policy_mod` (kept inline to avoid a module-level circular import risk between `agent_store` and `policy`, matching the existing inline-import style already used elsewhere for `agent_cli`/`agent_store` cross-references — check via `grep -n "^from synlynk\|^import" synlynk/agent_store.py` for the file's existing import conventions before finalizing placement).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agent_store.py -v -k sync_dispatch_routing`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full agent_store suite to check for regressions**

Run: `python3 -m pytest tests/test_agent_store.py -v`
Expected: PASS, all tests.

- [ ] **Step 6: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: add sync_dispatch_routing to regenerate charter dispatch_routing from policy.json"
```

---

## Task 6: Rewrite `SEED_CHARTERS` and update `agent_cli.py` handlers

**Files:**
- Modify: `synlynk/agent_cli.py`
- Modify: `tests/test_agent_cli.py`

- [ ] **Step 1: Read current `test_agent_cli.py` tests that will be affected**

Run: `grep -n "def test_cmd_agent_init_writes_projection_with_empty_capability_grants\|def test_cmd_agent_edit_preserves_capability_grants_set_after_init\|def test_cmd_agent_init_creates_registry_entry_and_charter\|def test_pm_charter_includes_competitive_sweep_responsibility\|def test_cmd_agent_edit_updates_charter\|def test_cmd_agent_edit_stdin" tests/test_agent_cli.py`

This confirms line numbers before editing (they may have shifted since the pre-compaction research pass).

- [ ] **Step 2: Rewrite `SEED_CHARTERS` in `synlynk/agent_cli.py`**

Replace the `SEED_CHARTERS` dict and `ROLES = list(SEED_CHARTERS)` line with:

```python
from synlynk import charter_schema

SEED_CHARTERS = {
    "dev": (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "Implementation — writes the code."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "Implementation work: turn an approved plan or ticket into working, tested\n"
        "code. Dispatch-triggered only — no autonomous loop. Follow the plan's task\n"
        "breakdown; do not redesign architecture mid-implementation.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Decides implementation details (naming, file layout, test structure) within\n"
        "an approved plan unilaterally. Escalates to whoever holds\n"
        "`human_authority_role` before deviating from the plan's architecture or\n"
        "scope.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns the Implement stage of the end-to-end workflow.\n"
    ),
    "qa": (
        "---\n"
        "schema_version: 1\n"
        "role: qa\n"
        'description: "Quality assurance — tests and verifies work."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "Quality assurance: writes and runs tests, verifies implementation work\n"
        "against its plan/spec before merge, and holds merge authority per\n"
        "`.synlynk/policy.json`'s `merge_authority`.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Decides pass/fail on a PR unilaterally, including blocking a merge on\n"
        "missing test coverage. Escalates to whoever holds `human_authority_role`\n"
        "when a fix requires descoping or renegotiating the original plan.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns the CI/CD gate and Deploy stage of the end-to-end workflow.\n"
    ),
    "pm": (
        "---\n"
        "schema_version: 1\n"
        "role: pm\n"
        'description: "Program management — roadmap, brainstorming, issue triage."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "Program management: owns the roadmap, runs brainstorming sessions, and\n"
        "triages incoming issues. Runs a weekly competitive-intelligence sweep:\n"
        "tracks products serving synlynk's user segments, maintains a living\n"
        "capability/marketing-gap comparison doc, opens research tickets for\n"
        "candidate features, convenes harness-maintainer decide rounds, and\n"
        "escalates strong-fit candidates to the user as feature proposals.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Decides roadmap prioritization and issue triage unilaterally. Anything\n"
        "matching a major decision (spec approval, budget/release sign-off, charter\n"
        "changes) queues and blocks for whoever holds `human_authority_role` — pm\n"
        "never commits the human to something they haven't seen.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns Named Releases (final sign-off + narrative).\n"
    ),
    "architect": (
        "---\n"
        "schema_version: 1\n"
        "role: architect\n"
        'description: "System design — architecture and technical direction."\n'
        "durability: session-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "System design: writes and approves both the Spec and the Plan for\n"
        "non-trivial work, and does PR code review.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Session-only, human-in-the-loop by design. Holds merge authority alongside\n"
        "qa; non-authoring-reviewer discipline applies — architect never reviews its\n"
        "own dispatch. Escalates architectural tradeoffs with cost/scope\n"
        "implications to whoever holds `human_authority_role`.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns the Review and Merge stages of the end-to-end workflow.\n"
    ),
    "tpm": (
        "---\n"
        "schema_version: 1\n"
        "role: tpm\n"
        'description: "Technical program management — cross-cutting coordination, GOVERNS integration."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "Operations: turns architect's finished plan into tracked, dispatched\n"
        "tickets, does actual tasking/tracking, and reports status back to pm. Does\n"
        "not decide technical approach.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Decides ticket sequencing and dispatch scheduling unilaterally. Escalates\n"
        "to whoever holds `human_authority_role` when tracked work reveals a\n"
        "scope or architecture gap the plan didn't anticipate.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Runs a continuous tasking/tracking/reporting loop, consuming GOVERNS'\n"
        "existing lifecycle-enforcement event contract as its data source.\n"
    ),
    "designer": (
        "---\n"
        "schema_version: 1\n"
        "role: designer\n"
        'description: "Design — visual and interaction design."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "UI/UX: maintains end-user-facing interfaces, journeys, and look & feel.\n"
        "Dispatch-triggered only, routed to Agy (CSS/templates/content/subpages).\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Decides visual/interaction details within an approved design direction\n"
        "unilaterally. Escalates to whoever holds `human_authority_role` before a\n"
        "change that alters user-facing information architecture.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns the design pass within the Implement stage for user-facing surfaces.\n"
    ),
    "marketing": (
        "---\n"
        "schema_version: 1\n"
        "role: marketing\n"
        'description: "Marketing — external communication and positioning."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "All end-user-facing comms: docs, blogs, website, plus outbound digital\n"
        "marketing. Writes every PR's blog post — dev/architect hand off a short\n"
        "technical summary at merge time, marketing turns it into the actual post.\n"
        "Owns `docs/blog/README.md`'s series template and Named Release blog\n"
        "content. Dispatch-triggered only, routed to Agy (docs/templates/content).\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Decides post structure, tone, and framing unilaterally within the series\n"
        "template. Escalates to whoever holds `human_authority_role` before\n"
        "publishing anything that commits to a roadmap claim not yet approved.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns the Blog/Comms pass of the Named Release stage.\n"
    ),
    "synlynk-bot": (
        "---\n"
        "schema_version: 1\n"
        "role: synlynk-bot\n"
        'description: "Catch-all workspace automation identity."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        "\n"
        "Infra automation identity for workspace-level jobs with no natural owner\n"
        "among the seven org-chart roles (e.g. scheduled housekeeping, projection\n"
        "regeneration). Not a decision-making role.\n"
        "\n"
        "## Authority & Escalation\n"
        "\n"
        "Holds no unilateral decision authority. Any action beyond routine\n"
        "housekeeping escalates to whoever holds `human_authority_role`.\n"
        "\n"
        "## Workflow Ownership\n"
        "\n"
        "Owns no workflow stage; supports other roles' stages as infrastructure.\n"
    ),
}

ROLES = list(charter_schema.KNOWN_ROLES)
```

- [ ] **Step 3: Verify every `SEED_CHARTERS` entry passes validation**

Run:

```bash
python3 -c "
from synlynk import agent_cli
for role, content in agent_cli.SEED_CHARTERS.items():
    agent_cli.charter_schema.validate_charter(content)
    print(f'{role}: OK')
"
```

Expected: prints `OK` for all 8 roles, no exceptions.

- [ ] **Step 4: Update `cmd_agent_init` — drop the projection call**

In `synlynk/agent_cli.py`, replace the body of `cmd_agent_init` (the part after the duplicate-role check) with:

```python
    agent_id = str(uuid.uuid4())
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(
        agent_id, SEED_CHARTERS[role], actor="cli", parent_revision=0
    )
    print(f"Created agent {agent_id} (role: {role})")
    return agent_id
```

(Removes the `agent_store.regenerate_agent_projection(...)` call — `propose_charter_revision` already validates via Task 3's wiring, and `SEED_CHARTERS` content is now schema-compliant by construction, so no new error handling is needed here.)

- [ ] **Step 5: Update `cmd_agent_edit` — drop the projection call, catch `CharterValidationError`**

Replace the body of `cmd_agent_edit` with:

```python
def cmd_agent_edit(id_or_alias: str, charter_path: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    if charter_path == "-":
        new_content = sys.stdin.read()
    else:
        with open(charter_path) as f:
            new_content = f.read()

    _, parent_revision = agent_store.read_charter(agent_id)
    try:
        new_revision = agent_store.propose_charter_revision(
            agent_id, new_content, actor="cli", parent_revision=parent_revision
        )
    except agent_store.RevisionConflictError:
        print(
            "Charter was updated by someone else since you last viewed it. "
            f"Run `synlynk agent show {agent_id}` and retry.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except charter_schema.CharterValidationError as exc:
        print("Charter failed validation:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Updated charter for {agent_id} (revision {new_revision})")
```

- [ ] **Step 6: Add `cmd_agent_sync_routing`**

Add this new function to `synlynk/agent_cli.py`, after `cmd_agent_edit`:

```python
def cmd_agent_sync_routing(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    role = next(
        (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), ""
    )
    _, revision_before = agent_store.read_charter(agent_id)
    new_revision = agent_store.sync_dispatch_routing(agent_id, role, actor="cli")
    if new_revision == revision_before:
        print(f"No task_allocation entry for role '{role}' in policy.json — nothing to sync.")
    else:
        print(f"Synced dispatch_routing for {agent_id} (role: {role}, revision {new_revision})")
```

- [ ] **Step 7: Delete the 2 projection-only tests from `tests/test_agent_cli.py`**

Remove `test_cmd_agent_init_writes_projection_with_empty_capability_grants` and `test_cmd_agent_edit_preserves_capability_grants_set_after_init` in full.

- [ ] **Step 8: Update `test_cmd_agent_edit_updates_charter` and `test_cmd_agent_edit_stdin` to use schema-valid content**

Replace `test_cmd_agent_edit_updates_charter`:

```python
def test_cmd_agent_edit_updates_charter(project_dir, tmp_path, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    new_content = (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "Implementation — writes the code, reviews own PRs."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n\nUpdated instructions.\n\n"
        "## Authority & Escalation\n\nUpdated escalation.\n\n"
        "## Workflow Ownership\n\nUpdated ownership.\n"
    )
    charter_file = tmp_path / "new_charter.md"
    charter_file.write_text(new_content)

    agent_cli.cmd_agent_edit(agent_id, str(charter_file))

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert content == new_content
```

Replace `test_cmd_agent_edit_stdin`:

```python
def test_cmd_agent_edit_stdin(project_dir, monkeypatch, capsys):
    import io
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    new_content = (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "New charter from stdin."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n\nFrom stdin.\n\n"
        "## Authority & Escalation\n\nFrom stdin.\n\n"
        "## Workflow Ownership\n\nFrom stdin.\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(new_content))
    agent_cli.cmd_agent_edit(agent_id, "-")

    content, revision = agent_store.read_charter(agent_id)
    assert content == new_content
    assert revision == 2
```

- [ ] **Step 9: Add a test for `cmd_agent_edit`'s new validation-rejection path**

Add to `tests/test_agent_cli.py`:

```python
def test_cmd_agent_edit_rejects_invalid_charter_exits_1(project_dir, tmp_path, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    charter_file = tmp_path / "invalid.md"
    charter_file.write_text("not a valid charter, no frontmatter")

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_edit(agent_id, str(charter_file))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "failed validation" in captured.err
```

(Confirm `import pytest` is present at the top of `tests/test_agent_cli.py` — it already is, per the existing `test_cmd_agent_edit_stale_revision_exits_1` test's use of `pytest.raises`.)

- [ ] **Step 10: Add a test for `cmd_agent_sync_routing`**

Add to `tests/test_agent_cli.py`:

```python
def test_cmd_agent_sync_routing_populates_dispatch_routing_for_dev(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_sync_routing(agent_id)

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert "dispatch_routing:" in content
    captured = capsys.readouterr()
    assert "Synced dispatch_routing" in captured.out


def test_cmd_agent_sync_routing_reports_noop_for_role_without_task_allocation(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("qa")
    capsys.readouterr()

    agent_cli.cmd_agent_sync_routing(agent_id)

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 1
    captured = capsys.readouterr()
    assert "nothing to sync" in captured.out
```

- [ ] **Step 11: Run the full `test_agent_cli.py` suite**

Run: `python3 -m pytest tests/test_agent_cli.py -v`
Expected: PASS, all tests including `test_pm_charter_includes_competitive_sweep_responsibility` and `test_cmd_agent_init_creates_registry_entry_and_charter` (both pass unmodified against the new `SEED_CHARTERS["pm"]`/`SEED_CHARTERS["dev"]` content).

- [ ] **Step 12: Commit**

```bash
git add synlynk/agent_cli.py tests/test_agent_cli.py
git commit -m "feat: rewrite SEED_CHARTERS to new schema, add sync-routing command, drop projection writes"
```

---

## Task 7: Wire `agent sync-routing` into `cli.py`

**Files:**
- Modify: `synlynk/cli.py`

- [ ] **Step 1: Locate the `agent` subparser block**

The relevant block in `synlynk/cli.py` (confirmed at the time of writing this plan via `grep -n 'agent_parser = subparsers.add_parser\|agent_action\|_synlynk_skip_taxonomy' synlynk/cli.py` — re-run this grep before editing in case line numbers have shifted) reads:

```python
    agent_parser = subparsers.add_parser("agent", help="Manage workspace agents (roles/charters)")
    agent_parser._synlynk_skip_taxonomy = True
    agent_sub = agent_parser.add_subparsers(dest="agent_action")

    agent_init_parser = agent_sub.add_parser("init", help="Create a new workspace agent for a role")
    agent_init_parser.add_argument("role", choices=[
        "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot",
    ], help="Org-chart role for this agent")

    agent_sub.add_parser("list", help="List all registered workspace agents")

    agent_show_parser = agent_sub.add_parser("show", help="Show one agent's details and charter")
    agent_show_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")

    agent_edit_parser = agent_sub.add_parser("edit", help="Propose a new charter revision")
    agent_edit_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")
    agent_edit_parser.add_argument("--charter", required=True,
        help="Path to new charter content, or '-' to read from stdin")

    agent_disable_parser = agent_sub.add_parser("disable", help="Disable a workspace agent")
    agent_disable_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")
```

Note: `edit` takes `--charter` as a required flag (not a positional `charter_path`) — `agent_cli.cmd_agent_edit`'s parameter is still named `charter_path` internally, but the CLI surface passes it via `args.charter`. The subparser variable-naming convention is `agent_<action>_parser = agent_sub.add_parser(...)`.

- [ ] **Step 2: Add the `sync-routing` subparser**

Insert immediately after the `agent_edit_parser` block (before `agent_disable_parser`), matching the file's existing variable-naming convention:

```python
    agent_sync_routing_parser = agent_sub.add_parser(
        "sync-routing", help="Regenerate an agent's dispatch_routing frontmatter from policy.json"
    )
    agent_sync_routing_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")
```

- [ ] **Step 3: Add the dispatch-block wiring**

The relevant dispatch block in `synlynk/cli.py` (confirmed via `grep -n 'args.command == "agent"' -A 20 synlynk/cli.py` — re-run before editing) reads:

```python
    elif args.command == "agent":
        from synlynk import agent_cli
        if args.agent_action == "init":
            agent_cli.cmd_agent_init(args.role)
        elif args.agent_action == "list":
            agent_cli.cmd_agent_list()
        elif args.agent_action == "show":
            agent_cli.cmd_agent_show(args.id_or_alias)
        elif args.agent_action == "edit":
            agent_cli.cmd_agent_edit(args.id_or_alias, args.charter)
        elif args.agent_action == "disable":
            agent_cli.cmd_agent_disable(args.id_or_alias)
        else:
            help_parsers.get("agent", parser).print_help()
```

Insert a new branch immediately after the `edit` branch, before `disable`:

```python
        elif args.agent_action == "edit":
            agent_cli.cmd_agent_edit(args.id_or_alias, args.charter)
        elif args.agent_action == "sync-routing":
            agent_cli.cmd_agent_sync_routing(args.id_or_alias)
        elif args.agent_action == "disable":
            agent_cli.cmd_agent_disable(args.id_or_alias)
```

(i.e. only the new `elif args.agent_action == "sync-routing": agent_cli.cmd_agent_sync_routing(args.id_or_alias)` block is added — the surrounding `edit`/`disable` branches are shown for exact insertion-point context, not themselves modified.)

- [ ] **Step 4: Verify the taxonomy exemption still applies**

Run: `grep -n "_synlynk_skip_taxonomy" synlynk/cli.py`

Confirm the `agent_parser._synlynk_skip_taxonomy = True` line is set on the top-level `agent_parser` (not per sub-action), meaning the whole `agent` subcommand group — including the new `sync-routing` action — remains exempt from `test_taxonomy_matches_real_cli_surface`. No taxonomy file edit needed.

- [ ] **Step 5: Manually verify the CLI wiring end-to-end**

The project's entry point is `synlynk = "synlynk:main"` (`pyproject.toml`'s `[project.scripts]`), and `synlynk` is already on `PATH` via an editable install (confirmed via `which synlynk`). Run (from the worktree root, using a scratch `HOME` to avoid touching the real machine's workspace, and `cd`'d into the worktree so `.synlynk/policy.json` resolves to this repo's copy):

```bash
export TMPDIR_TEST=$(mktemp -d)
HOME="$TMPDIR_TEST" synlynk agent init dev
HOME="$TMPDIR_TEST" synlynk agent list
HOME="$TMPDIR_TEST" synlynk agent sync-routing dev
HOME="$TMPDIR_TEST" synlynk agent show dev
rm -rf "$TMPDIR_TEST"
```

Expected: `agent init dev` prints `Created agent <uuid> (role: dev)`; `agent sync-routing dev` prints `Synced dispatch_routing for <uuid> (role: dev, revision 2)`; `agent show dev` prints charter content containing a `dispatch_routing:` block with `harness: codex` under `implement`.

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `python3 -m pytest tests/ -v`
Expected: PASS, all tests (including the pre-existing `test_taxonomy_matches_real_cli_surface` test, unaffected since `agent` remains exempt).

- [ ] **Step 7: Commit**

```bash
git add synlynk/cli.py
git commit -m "feat: wire agent sync-routing CLI subcommand"
```

---

## Task 8: `CHANGELOG.md` entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add an `[Unreleased]` bullet cluster**

Run: `head -30 CHANGELOG.md` to confirm the exact current `[Unreleased]` section heading and the most recent bullet-cluster's formatting convention (bold sub-heading + indented bullets, per existing entries like "**Agent vs Harness Terminology — Phase 0**").

Add a new bullet cluster under the `[Unreleased]` heading (above or below existing clusters, matching whatever ordering convention — newest-on-top or newest-on-bottom — the existing file already uses):

```markdown
- **Charter Content & Structure Schema**
  - Charters now require YAML frontmatter (`schema_version`, `role`, `description`, `durability`, `tools`, `credentials`) plus three markdown sections (`## Instructions`, `## Authority & Escalation`, `## Workflow Ownership`), enforced via a new `synlynk/charter_schema.py` validator wired into `propose_charter_revision`.
  - Retired the dead `.synlynk/agents/<id>.yaml` projection file and `regenerate_agent_projection()` — its only field (`capability_grants`) was write-only, never read.
  - Added `synlynk agent sync-routing <id_or_alias>` to regenerate a charter's `dispatch_routing` frontmatter block from `.synlynk/policy.json`'s task-allocation table.
  - Migrated all 7 provisioned charters (dev, qa, architect, pm, tpm, designer, marketing) to schema revision 3; `pm`'s migration restores the competitive-intelligence-sweep / capability-gap-doc content that had been lost in an earlier revision.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG entry for charter content/structure schema"
```

---

## Task 9: Migrate the 7 live charters to revision 3

**Files:** none (operational CLI task against this machine's live `~/.synlynk/workspaces/<id>/agents/` store — no source file changes)

This task must run from a normal shell session on this machine (not a sandboxed test), since it writes to the real `~/.synlynk/workspaces/<workspace_id>/agents/<agent_id>/charter.md` store via the actual installed `synlynk` CLI, using each agent's real `agent_id`.

- [ ] **Step 1: Confirm current charter revisions before migrating**

Run: `synlynk agent list`

Expected: 7 rows (dev, qa, architect, pm, tpm, designer, marketing), all currently at charter revision 2 (confirm via `synlynk agent show <id>` for one role if the `list` output doesn't show revision directly).

- [ ] **Step 2: Write and apply the `dev` migration**

Create a temp file with this content (this restructures the rev-2 content captured during spec research into the three required sections — the `dispatch_routing` block is intentionally omitted here and added separately in Step 9 via `sync-routing`, per §4.4's "generated, never hand-authored" rule):

```bash
cat > /tmp/charter-dev.md << 'CHARTER_EOF'
---
schema_version: 1
role: dev
description: "Implementation — writes the code."
durability: dispatch-only
tools: []
credentials: []
---

## Instructions

Implementation — writes the code. Dispatch-triggered only, no autonomous
loop. Routed via capability-fit dispatch policy: Codex (refactor/CLI-plumbing),
Grok (canvas/JS/infra/complex data structures), or Agy (general
implementation) per task, with live holdback calibration continuously
testing whether that routing is still correct.

## Authority & Escalation

Decides implementation details within an approved plan unilaterally.
Escalates to whoever holds `human_authority_role` before deviating from
the plan's architecture or scope.

## Workflow Ownership

Owns the Implement stage of the end-to-end workflow.
CHARTER_EOF
synlynk agent edit dev --charter /tmp/charter-dev.md
```

Expected output: `Updated charter for <dev-agent-id> (revision 3)`

- [ ] **Step 3: Write and apply the `qa` migration**

```bash
cat > /tmp/charter-qa.md << 'CHARTER_EOF'
---
schema_version: 1
role: qa
description: "Quality assurance — tests and verifies work."
durability: durable
tools: []
credentials: []
---

## Instructions

Test coverage, overall quality & performance, CI/CD, IaC, and deployments.
The shipped Support Engineer (`synlynk/support_engineer.py`) is qa's
always-on presence.

## Authority & Escalation

Decides pass/fail on a PR unilaterally, including blocking a merge on
missing test coverage or pipeline failure. Holds merge authority per
`.synlynk/policy.json`'s `merge_authority`. Escalates to whoever holds
`human_authority_role` when a fix requires descoping or renegotiating the
original plan.

## Workflow Ownership

Owns the CI/CD gate and Deploy stage of the end-to-end workflow: pipeline
health and deploy mechanics.
CHARTER_EOF
synlynk agent edit qa --charter /tmp/charter-qa.md
```

Expected output: `Updated charter for <qa-agent-id> (revision 3)`

- [ ] **Step 4: Write and apply the `architect` migration**

```bash
cat > /tmp/charter-architect.md << 'CHARTER_EOF'
---
schema_version: 1
role: architect
description: "System design — architecture and technical direction."
durability: session-only
tools: []
credentials: []
---

## Instructions

Technical custodian of build quality, design, and performance — everything
technical. Owns the full technical design surface: writes/approves both
the Spec and the Plan. Does PR code review.

## Authority & Escalation

Session-only, human-in-the-loop by design. Holds merge authority alongside
qa; non-authoring-reviewer discipline applies — architect never reviews
its own dispatch. Escalates architectural tradeoffs with cost/scope
implications to whoever holds `human_authority_role`.

## Workflow Ownership

Owns the Review and Merge stages of the end-to-end workflow.
CHARTER_EOF
synlynk agent edit architect --charter /tmp/charter-architect.md
```

Expected output: `Updated charter for <architect-agent-id> (revision 3)`

- [ ] **Step 5: Write and apply the `pm` migration (restores lost SEED content)**

This is the one migration flagged in spec §4.6 as a correction, not just a reformat: it restores the "competitive-intelligence sweep" / "capability/marketing-gap comparison doc" / feature-proposal-escalation content from the original `SEED_CHARTERS["pm"]` text, merged alongside revision 2's additions (Named Release ownership, the "never commits the human to something they haven't seen" line) — neither version replaces the other.

```bash
cat > /tmp/charter-pm.md << 'CHARTER_EOF'
---
schema_version: 1
role: pm
description: "Program management — roadmap, brainstorming, issue triage."
durability: durable
tools: []
credentials: []
---

## Instructions

Represents the human user in everything built: brainstorming, issuing
work, major decisions based on other roles' reports, keeping course.
Runs a continuous triage loop — responds to inbound signals/reports,
re-prioritizes the backlog, dispatches tpm on already-approved work — to
prevent workspace dormancy when unattended.

Runs a weekly competitive-intelligence sweep: tracks products serving
synlynk's user segments, maintains a living capability/marketing-gap
comparison doc, opens research tickets for candidate features, convenes
harness-maintainer decide rounds, and escalates strong-fit candidates to
the user as feature proposals.

## Authority & Escalation

Durable, narrowly scoped. Anything matching a "major decision" (spec
approval, budget/release sign-off, charter changes) queues and blocks for
whoever holds `human_authority_role` — pm never commits the human to
something they haven't seen.

## Workflow Ownership

Owns Named Releases (final sign-off + narrative).
CHARTER_EOF
synlynk agent edit pm --charter /tmp/charter-pm.md
```

Expected output: `Updated charter for <pm-agent-id> (revision 3)`

- [ ] **Step 6: Write and apply the `tpm` migration**

```bash
cat > /tmp/charter-tpm.md << 'CHARTER_EOF'
---
schema_version: 1
role: tpm
description: "Technical program management — cross-cutting coordination, GOVERNS integration."
durability: durable
tools: []
credentials: []
---

## Instructions

Operations role: turns architect's finished plan into tracked, dispatched
tickets; does actual tasking/tracking; reports status back to pm. Does not
decide technical approach.

## Authority & Escalation

Decides ticket sequencing and dispatch scheduling unilaterally. Escalates
to whoever holds `human_authority_role` when tracked work reveals a scope
or architecture gap the plan didn't anticipate.

## Workflow Ownership

Runs a continuous tasking/tracking/reporting loop, consuming GOVERNS'
existing lifecycle-enforcement event contract as its data source rather
than building an independent tracking mechanism. Lightweight periodic
reconciliation is kept only as a correctness backstop, never the primary
source of truth.
CHARTER_EOF
synlynk agent edit tpm --charter /tmp/charter-tpm.md
```

Expected output: `Updated charter for <tpm-agent-id> (revision 3)`

- [ ] **Step 7: Write and apply the `designer` migration**

```bash
cat > /tmp/charter-designer.md << 'CHARTER_EOF'
---
schema_version: 1
role: designer
description: "Design — visual and interaction design."
durability: dispatch-only
tools: []
credentials: []
---

## Instructions

UI/UX specialist: maintains end-user-facing interfaces, journeys, and look
& feel. Dispatch-triggered only. Routed to Agy
(CSS/templates/content/subpages).

## Authority & Escalation

Decides visual/interaction details within an approved design direction
unilaterally. Escalates to whoever holds `human_authority_role` before a
change that alters user-facing information architecture.

## Workflow Ownership

Owns the design pass within the Implement stage for user-facing surfaces.
CHARTER_EOF
synlynk agent edit designer --charter /tmp/charter-designer.md
```

Expected output: `Updated charter for <designer-agent-id> (revision 3)`

- [ ] **Step 8: Write and apply the `marketing` migration**

```bash
cat > /tmp/charter-marketing.md << 'CHARTER_EOF'
---
schema_version: 1
role: marketing
description: "Marketing — external communication and positioning."
durability: dispatch-only
tools: []
credentials: []
---

## Instructions

All end-user-facing comms: docs, blogs, website, plus outbound digital
marketing. Writes every PR's blog post — dev/architect hand off a short
technical summary at merge time, marketing turns it into the actual post.
Owns `docs/blog/README.md`'s series template and Named Release blog
content. Dispatch-triggered only. Routed to Agy (docs/templates/content).

## Authority & Escalation

Decides post structure, tone, and framing unilaterally within the series
template. Escalates to whoever holds `human_authority_role` before
publishing anything that commits to a roadmap claim not yet approved.

## Workflow Ownership

Owns the Blog/Comms pass of the Named Release stage.
CHARTER_EOF
synlynk agent edit marketing --charter /tmp/charter-marketing.md
```

Expected output: `Updated charter for <marketing-agent-id> (revision 3)`

- [ ] **Step 9: Run `sync-routing` for `dev` to populate its `dispatch_routing` block**

```bash
synlynk agent sync-routing dev
```

Expected output: `Synced dispatch_routing for <dev-agent-id> (role: dev, revision 4)`

Verify:

```bash
synlynk agent show dev | grep -A 3 "dispatch_routing:"
```

Expected: shows the `implement`/`test`/`css`/etc. task-type entries with `harness:`/`fallback:` matching the live `.synlynk/policy.json`'s `overrides.dev_authority.task_allocation` table.

- [ ] **Step 10: Verify all 7 charters pass validation post-migration**

```bash
python3 -c "
from synlynk import agent_store, charter_schema
for role in ('dev', 'qa', 'architect', 'pm', 'tpm', 'designer', 'marketing'):
    agent_id = agent_store.resolve_agent_id(role)
    content, revision = agent_store.read_charter(agent_id)
    charter_schema.validate_charter(content)
    print(f'{role}: revision {revision} OK')
"
```

Expected: prints `OK` at revision 3 for qa/architect/pm/tpm/designer/marketing and revision 4 for dev, no exceptions.

- [ ] **Step 11: Clean up temp files**

```bash
rm -f /tmp/charter-dev.md /tmp/charter-qa.md /tmp/charter-architect.md /tmp/charter-pm.md /tmp/charter-tpm.md /tmp/charter-designer.md /tmp/charter-marketing.md
```

(No git commit for this task — it modifies only the per-machine `~/.synlynk/workspaces/` store, not repo-tracked files.)

---

## Task 10: Full regression pass and PR

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest tests/ -v`
Expected: PASS, 0 failures.

- [ ] **Step 2: Self-review this plan against the spec**

Confirm every spec section has a corresponding task:
- §4.1 (merge frontmatter into `charter.md`, retire projection) → Tasks 1, 4.
- §4.2 (frontmatter schema) → Task 1.
- §4.3 (three required body sections) → Task 1.
- §4.4 (`dispatch_routing` generated, never hand-authored) → Tasks 2, 5, 7, 9 Step 9.
- §4.5 (enforcement wired into `propose_charter_revision` / `agent_cli.py`) → Tasks 3, 6.
- §4.6 (migrate 7 charters, restore pm's lost content) → Task 9.
- §5 (error handling: parse errors, missing-keys-at-once, missing-sections-named, unknown-role) → Task 1's validator + Task 6 Step 5's CLI error surface.
- §6 (testing: validator unit tests, all-7-pass-validation regression guard, projection-no-longer-written test) → Task 1/2 tests, Task 9 Step 10, Task 4 Step 3 (projection tests deleted rather than inverted, since the function no longer exists to test against — confirmed as the correct approach since §7 states retiring the projection carries no runtime risk).

- [ ] **Step 3: Push the branch**

```bash
git push -u origin chore/charter-content-structure-spec
```

- [ ] **Step 4: Open a PR**

```bash
gh pr create --title "Charter content & structure schema" --body "$(cat <<'PR_EOF'
## Summary
- Adds enforced YAML frontmatter + three required markdown sections (`## Instructions`, `## Authority & Escalation`, `## Workflow Ownership`) to agent charters, validated via a new `synlynk/charter_schema.py`.
- Retires the dead `.synlynk/agents/<id>.yaml` projection file and its write-only `capability_grants` field.
- Adds `synlynk agent sync-routing` to regenerate a charter's `dispatch_routing` block from `.synlynk/policy.json`.
- Migrates all 7 live charters to schema revision 3 (revision 4 for `dev`, after `sync-routing`); restores `pm`'s lost competitive-intelligence-sweep content per spec §4.6.

## Test plan
- [x] `python3 -m pytest tests/ -v` — full suite passes
- [x] Manual CLI smoke test: `agent init`, `agent edit` (valid + invalid content), `agent sync-routing`, `agent show`
- [x] All 7 live charters re-validated post-migration

Spec: `docs/superpowers/specs/2026-08-27-charter-content-structure-design.md`
Plan: `docs/superpowers/plans/2026-08-27-charter-content-structure.md`
PR_EOF
)"
```

