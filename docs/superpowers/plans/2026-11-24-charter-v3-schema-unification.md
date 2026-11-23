# Charter v3.0 Schema Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the extraction-ready Charter v3.0 core (JSON Schema contract, zero-dependency strict-YAML parser, structural + constitution-binding validators, a `synlynk charter migrate` command) and wire it into `synlynk/charters.py::load_charter()` as a dual-read path, so the 9 non-v3 charters can be mechanically migrated and validated without breaking any live consumer.

**Architecture:** A new `synlynk/charter_core/` package holds the schema, the strict-YAML-subset parser/serializer, and the structural validator — all with **zero synlynk imports**, per the standalone-extraction-readiness constraint from the approved spec and decision records. A separate `synlynk/charter_constitution_adapter.py` holds the synlynk-specific semantic checks (resolving `constitution_binding` against `synlynk/constitution.py`'s real `CONSTITUTION_LAWS`/`DeliveryTier`, and `identity.app_ref` against `.synlynk/github_apps/<role>/`). `synlynk/charter_migrate.py` lifts existing v1 (`DEFAULT_ROLE_CHARTERS` / `.synlynk/charters/*.json`) and v2.0 SFIA (`tpm.json`, `wingman.json`) charters into the v3 shape. `synlynk/charters.py::load_charter()` gains a dual-read branch: when a charter file's `schema_version` starts with `"3"`, it is parsed via `charter_core` + validated via the constitution adapter instead of the legacy JSON path.

**Tech Stack:** Python 3 stdlib only (no PyYAML, no `jsonschema` package — matches the repo's existing zero-dependency policy already followed by `charter_schema.py`).

---

## Scope Check

The approved spec (`docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md`) and the three follow-up decision records cover several independent subsystems. This plan delivers **only the extraction-ready core + migration tooling + the `charters.py` loader dual-read path** — the minimum slice that produces working, testable software on its own (you can migrate a charter, validate it, and load it).

**Explicitly deferred to separate follow-on plans** (each its own spec-review-plan-build cycle):

1. **Vizor Agent Studio editor regeneration from the JSON Schema** — no live editor UI source was found under `synlynk/` in this repo (grep for charter-related HTML/JS under `synlynk/` returned empty); locating and migrating it is a separate, UI-side effort, consistent with the decision record's "effort goes into making synlynk run Charter v3 on itself" sequencing before any editor/product work.
2. **Deleting `harness_bindings` from `DEFAULT_ROLE_CHARTERS` and retiring the legacy Markdown+frontmatter validator in `charter_schema.py`** — both are called out in the spec as happening only *after* the dual-read window closes. This plan opens that window; it does not close it.
3. **Wiring `charter_injection.py::resolve_role_charter()`** (the second, independent live-consumption path, which reads `agent_store` Markdown+frontmatter, not `.synlynk/charters/*.json`) to understand v3 YAML charters. That path has a different storage backend (`agent_store` revisioned files vs. flat `.synlynk/charters/` JSON) and deserves its own design decision about where v3-authored agent_store charters live.
4. **Flipping `constitution_gate.py` from observe-mode to enforce-mode** — explicitly out of scope per all three decision records; this plan only gives the validator something concrete to check structurally.

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/charter_core/__init__.py` | Public API: re-exports `parse_yaml`, `dump_yaml`, `validate_structure`, `CHARTER_V3_REQUIRED_BLOCKS`. Zero synlynk imports. |
| `synlynk/charter_core/yaml_subset.py` | Strict-subset YAML parser (`parse_yaml`) and serializer (`dump_yaml`) supporting scalars, nested mappings, lists of scalars, and lists of mappings — the shapes `charter_schema.py`'s hand-rolled flat parser cannot round-trip. Zero synlynk imports. |
| `synlynk/charter_core/schema.py` | `CHARTER_V3_REQUIRED_BLOCKS`, enum constants (`VALID_OPERATIONS`, `VALID_TRANSPORTS`, `VALID_AUTONOMY_LEVELS`), and `validate_structure(data: dict, known_roles: list) -> list[str]` — pure structural validation, no constitution/identity resolution. Zero synlynk imports. |
| `synlynk/charter_constitution_adapter.py` | `validate_constitution_binding(data: dict) -> list[str]` and `validate_identity(data: dict, repo_path: str) -> list[str]` — synlynk-specific semantic checks against `synlynk/constitution.py` and `.synlynk/github_apps/`. |
| `synlynk/charter_migrate.py` | `migrate_v1_to_v3(role, v1_data) -> dict`, `migrate_v2_to_v3(role, v2_data) -> dict`, `cmd_charter_migrate(role=None, apply=False, charters_dir=None) -> dict`. |
| `synlynk/charters.py` | Modify: extend `AgentCharter` with optional v3 fields; modify `load_charter()` to dual-read v3 YAML files. |
| `synlynk/cli.py` | Modify: add `charter migrate` subcommand (new `charter` parser, distinct from the existing `charters adapt` parser). |
| `tests/test_charter_core_yaml_subset.py` | Parser/serializer round-trip tests. |
| `tests/test_charter_core_schema.py` | Structural validator tests. |
| `tests/test_charter_constitution_adapter.py` | Constitution/identity semantic validator tests. |
| `tests/test_charter_migrate.py` | v1→v3 and v2→v3 migration + round-trip tests, CLI command test. |
| `tests/test_charters_v3_loader.py` | `load_charter()` dual-read test for a v3 fixture file. |

---

## Task 1: `charter_core` package skeleton with zero-import guard

**Files:**
- Create: `synlynk/charter_core/__init__.py`
- Test: `tests/test_charter_core_yaml_subset.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charter_core_yaml_subset.py
import ast
import pathlib


def test_charter_core_has_zero_synlynk_imports():
    """charter_core must be extraction-ready: no synlynk package imports anywhere in it."""
    pkg_dir = pathlib.Path(__file__).resolve().parents[1] / "synlynk" / "charter_core"
    offending = []
    for py_file in pkg_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "synlynk" or alias.name.startswith("synlynk."):
                        offending.append((py_file.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module == "synlynk" or node.module.startswith("synlynk.")):
                    offending.append((py_file.name, node.module))
    assert offending == [], f"synlynk imports found in charter_core: {offending}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_core_yaml_subset.py::test_charter_core_has_zero_synlynk_imports -v`
Expected: FAIL with `FileNotFoundError` or no `.py` files found (pkg_dir doesn't exist yet, so `glob` returns nothing and the test passes vacuously — to make it meaningfully fail first, assert the directory exists too)

Update the test to also assert the directory exists, so it fails for the right reason:

```python
def test_charter_core_has_zero_synlynk_imports():
    pkg_dir = pathlib.Path(__file__).resolve().parents[1] / "synlynk" / "charter_core"
    assert pkg_dir.is_dir(), f"{pkg_dir} does not exist yet"
    ...
```

Run again: FAIL with `AssertionError: ... does not exist yet`

- [ ] **Step 3: Create the package**

```python
# synlynk/charter_core/__init__.py
"""Extraction-ready Charter v3.0 core: schema, strict-YAML parsing, structural validation.

Zero synlynk-package imports by design (standalone-extraction-readiness constraint,
docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md).
"""
from synlynk.charter_core.yaml_subset import parse_yaml, dump_yaml  # noqa: F401 (re-export)
from synlynk.charter_core.schema import (  # noqa: F401 (re-export)
    CHARTER_V3_REQUIRED_BLOCKS,
    VALID_OPERATIONS,
    VALID_TRANSPORTS,
    VALID_AUTONOMY_LEVELS,
    validate_structure,
)
```

Note: the `__init__.py`'s own imports reference `synlynk.charter_core.*`, which the zero-import test must not flag — the test only flags imports of the top-level `synlynk` package from *within* `charter_core`'s own files, and `synlynk.charter_core.yaml_subset` starts with `synlynk.charter_core`, not a bare `synlynk.<other-module>`. Tighten the test's exclusion so self-package imports are allowed:

```python
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("synlynk.") and not node.module.startswith("synlynk.charter_core"):
                    offending.append((py_file.name, node.module))
```

(Also apply the same `synlynk.charter_core` exclusion to the plain `ast.Import` branch's `alias.name` check above.)

This step creates `__init__.py` only; `yaml_subset.py` and `schema.py` don't exist yet, so leave `__init__.py`'s body commented out for now and uncomment in Tasks 2 and 4:

```python
# synlynk/charter_core/__init__.py
"""Extraction-ready Charter v3.0 core: schema, strict-YAML parsing, structural validation.

Zero synlynk-package imports by design (standalone-extraction-readiness constraint,
docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md).
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_core_yaml_subset.py::test_charter_core_has_zero_synlynk_imports -v`
Expected: PASS (empty directory glob matches nothing, directory now exists)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_core/__init__.py tests/test_charter_core_yaml_subset.py
git commit -m "feat: charter_core package skeleton with zero-synlynk-import guard test

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Strict-YAML-subset parser — scalars and flat mappings

**Files:**
- Create: `synlynk/charter_core/yaml_subset.py`
- Modify: `tests/test_charter_core_yaml_subset.py`

- [ ] **Step 1: Write the failing test**

```python
def test_parse_yaml_flat_mapping():
    from synlynk.charter_core.yaml_subset import parse_yaml

    text = """\
role: pm
mandate: Own portfolio goal alignment.
durability: durable
"""
    assert parse_yaml(text) == {
        "role": "pm",
        "mandate": "Own portfolio goal alignment.",
        "durability": "durable",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_core_yaml_subset.py::test_parse_yaml_flat_mapping -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.charter_core.yaml_subset'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/charter_core/yaml_subset.py
"""Strict-subset YAML parser/serializer for Charter v3.0 authoring.

Supports: scalars, nested mappings, lists of scalars, lists of mappings.
Does NOT support: anchors, tags, multi-document streams, flow-style collections
other than empty `{}`/`[]`, or implicit type coercion beyond int/float/bool/null/str.
This is intentionally narrower than full YAML 1.2 — it is the documented, strict
authoring subset for Charter v3, not a general-purpose YAML library.
"""
from __future__ import annotations

_NULL_TOKENS = {"null", "~", ""}
_TRUE_TOKENS = {"true", "True", "TRUE"}
_FALSE_TOKENS = {"false", "False", "FALSE"}


def _coerce_scalar(raw: str):
    raw = raw.strip()
    if raw in _NULL_TOKENS:
        return None
    if raw in _TRUE_TOKENS:
        return True
    if raw in _FALSE_TOKENS:
        return False
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    try:
        if raw.lstrip("-").isdigit():
            return int(raw)
        return float(raw)
    except ValueError:
        return raw


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_comment(line: str) -> str:
    # No quoting-aware comment stripping needed for the strict subset: '#'
    # inside a quoted scalar is not supported by Charter v3 authoring content.
    idx = line.find(" #")
    return line if idx == -1 else line[:idx]


def parse_yaml(text: str) -> dict:
    """Parse the strict Charter v3 YAML subset into a plain dict/list/scalar tree."""
    raw_lines = text.splitlines()
    lines = []
    for raw in raw_lines:
        line = _strip_comment(raw).rstrip()
        if line.strip() == "" or line.strip().startswith("#"):
            continue
        lines.append(line)
    value, _ = _parse_block(lines, 0, 0)
    return value


def _parse_block(lines: list, start: int, indent: int):
    """Parse a block (mapping or list) starting at lines[start], all at `indent`."""
    if start >= len(lines):
        return {}, start
    first_indent = _indent_of(lines[start])
    if first_indent < indent:
        return {}, start
    stripped = lines[start][first_indent:]
    if stripped.startswith("- "):
        return _parse_list(lines, start, first_indent)
    return _parse_mapping(lines, start, first_indent)


def _parse_mapping(lines: list, start: int, indent: int):
    result = {}
    i = start
    while i < len(lines):
        line = lines[i]
        cur_indent = _indent_of(line)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"unexpected indent at line {i}: {line!r}")
        content = line[cur_indent:]
        if content.startswith("- "):
            raise ValueError(f"expected mapping key, found list item at line {i}: {line!r}")
        if ":" not in content:
            raise ValueError(f"expected 'key: value' at line {i}: {line!r}")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            # Nested block (mapping or list) follows at greater indent.
            nested, next_i = _parse_block(lines, i + 1, indent + 1)
            result[key] = nested
            i = next_i
        else:
            result[key] = _coerce_scalar(rest)
            i += 1
    return result, i


def _parse_list(lines: list, start: int, indent: int):
    result = []
    i = start
    while i < len(lines):
        line = lines[i]
        cur_indent = _indent_of(line)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"unexpected indent at line {i}: {line!r}")
        content = line[cur_indent:]
        if not content.startswith("- "):
            break
        item_text = content[2:]
        if ":" in item_text and not item_text.strip().startswith(("'", '"')):
            # Inline first key of a mapping list-item: "- key: value"
            # followed by sibling keys indented to align under the item body.
            item_indent = indent + 2
            synthetic_first_line = " " * item_indent + item_text
            rest_lines = lines[i + 1 : i + 1 + _count_following(lines, i + 1, item_indent)]
            sub_lines = [synthetic_first_line] + rest_lines
            consumed = len(rest_lines)
            mapping, _ = _parse_mapping(sub_lines, 0, item_indent)
            result.append(mapping)
            i += 1 + consumed
        else:
            result.append(_coerce_scalar(item_text))
            i += 1
    return result, i


def _count_following(lines: list, start: int, indent: int) -> int:
    count = 0
    for j in range(start, len(lines)):
        if _indent_of(lines[j]) < indent:
            break
        count += 1
    return count


def dump_yaml(data, _indent: int = 0) -> str:
    """Serialize a plain dict/list/scalar tree back to the strict Charter v3 YAML subset."""
    lines = []
    _dump_into(data, _indent, lines)
    return "\n".join(lines) + "\n"


def _dump_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or text.strip() != text or text in _NULL_TOKENS | _TRUE_TOKENS | _FALSE_TOKENS:
        return f'"{text}"'
    return text


def _dump_into(data, indent: int, lines: list) -> None:
    pad = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                _dump_into(value, indent + 2, lines)
            elif isinstance(value, dict):
                lines.append(f"{pad}{key}: {{}}")
            elif isinstance(value, list):
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {_dump_scalar(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item:
                first_key = next(iter(item))
                first_val = item[first_key]
                if isinstance(first_val, (dict, list)):
                    lines.append(f"{pad}- {first_key}:")
                    _dump_into(first_val, indent + 4, lines)
                else:
                    lines.append(f"{pad}- {first_key}: {_dump_scalar(first_val)}")
                rest = dict(list(item.items())[1:])
                _dump_into(rest, indent + 2, lines)
            else:
                lines.append(f"{pad}- {_dump_scalar(item)}")
    else:
        lines.append(f"{pad}{_dump_scalar(data)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_core_yaml_subset.py::test_parse_yaml_flat_mapping -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_core/yaml_subset.py tests/test_charter_core_yaml_subset.py
git commit -m "feat: strict-YAML-subset parser for flat mappings (charter_core)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Strict-YAML-subset parser — nested mappings and lists of mappings

**Files:**
- Modify: `tests/test_charter_core_yaml_subset.py`

- [ ] **Step 1: Write the failing test**

```python
def test_parse_yaml_nested_mapping_and_list_of_mappings():
    from synlynk.charter_core.yaml_subset import parse_yaml

    text = """\
coordination:
  handoffs:
    - to_role: dev
      operation: delegate
      transport: dispatch_job
    - to_role: qa
      operation: request
      transport: gh_pr_comment
      ack: true
"""
    parsed = parse_yaml(text)
    assert parsed == {
        "coordination": {
            "handoffs": [
                {"to_role": "dev", "operation": "delegate", "transport": "dispatch_job"},
                {"to_role": "qa", "operation": "request", "transport": "gh_pr_comment", "ack": True},
            ]
        }
    }


def test_dump_yaml_round_trips_nested_structure():
    from synlynk.charter_core.yaml_subset import parse_yaml, dump_yaml

    original = {
        "coordination": {
            "handoffs": [
                {"to_role": "dev", "operation": "delegate", "transport": "dispatch_job"},
            ]
        }
    }
    dumped = dump_yaml(original)
    assert parse_yaml(dumped) == original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_core_yaml_subset.py -k nested_mapping -v`
Expected: FAIL (the list-of-mappings branch in `_parse_list` from Task 2 has an off-by-indent bug for this exact two-level-nested case — `item_indent = indent + 2` assumes handoffs' list items align two spaces past `handoffs:`'s own indent, which the fixture above matches, so this specific test should actually PASS already if Task 2's code is correct. If it fails, the bug is almost certainly in `_count_following`'s indent comparison picking up the next `- ` sibling as a nested key.)

Run it for real and read the actual failure before assuming — if it fails, fix `_parse_list`'s mapping-item branch so that a line starting a **new** `- ` at the same `item_indent` is never swept into `rest_lines` for the previous item. Replace `_count_following` with a version that also stops at a sibling list marker:

```python
def _count_following(lines: list, start: int, indent: int) -> int:
    count = 0
    for j in range(start, len(lines)):
        line_indent = _indent_of(lines[j])
        if line_indent < indent:
            break
        if line_indent == indent and lines[j][line_indent:].startswith("- "):
            break
        count += 1
    return count
```

- [ ] **Step 3: Verify / apply the fix above in `synlynk/charter_core/yaml_subset.py`**

(Already written inline in Step 2 — apply it to the `_count_following` function.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_core_yaml_subset.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_core/yaml_subset.py tests/test_charter_core_yaml_subset.py
git commit -m "fix: charter_core yaml_subset list-of-mappings sibling-item boundary

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Charter v3 structural schema + validator

**Files:**
- Create: `synlynk/charter_core/schema.py`
- Modify: `synlynk/charter_core/__init__.py`
- Test: `tests/test_charter_core_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charter_core_schema.py
def test_validate_structure_rejects_missing_core_block():
    from synlynk.charter_core.schema import validate_structure

    errors = validate_structure({"schema_version": "3.0.0"}, known_roles=["pm", "dev"])
    assert any("core" in e for e in errors)


def test_validate_structure_accepts_minimal_valid_charter():
    from synlynk.charter_core.schema import validate_structure

    data = {
        "schema_version": "3.0.0",
        "core": {
            "charter_id": "pm",
            "mandate": "Own portfolio goal alignment.",
            "authorities": ["sweep_goals"],
            "escalation": ["budget_exceeded"],
            "sop": ["1. Sweep goals."],
        },
        "governance": {"tools": [], "credentials": [], "evidence_contracts": []},
        "identity": {"app_ref": "github-app:pm"},
        "coordination": {"handoffs": []},
        "constitution_binding": {
            "tier_acknowledgements": ["injected", "cited"],
            "law_refs": [],
            "evidence_ref": "state_db:capability_ratings",
        },
        "requirements": {"task_types": ["pm"]},
        "extensions": {},
        "migration_provenance": {"source_schema": "v1", "migrated_at": "2026-11-24T00:00:00Z"},
    }
    errors = validate_structure(data, known_roles=["pm", "dev"])
    assert errors == []


def test_validate_structure_rejects_handoff_to_unknown_role():
    from synlynk.charter_core.schema import validate_structure

    data = {
        "schema_version": "3.0.0",
        "core": {"charter_id": "pm", "mandate": "x", "authorities": [], "escalation": [], "sop": ["x"]},
        "governance": {"tools": [], "credentials": [], "evidence_contracts": []},
        "identity": {"app_ref": "github-app:pm"},
        "coordination": {"handoffs": [{"to_role": "ghost", "operation": "delegate", "transport": "dispatch_job"}]},
        "constitution_binding": {"tier_acknowledgements": ["injected"], "law_refs": [], "evidence_ref": "x"},
        "requirements": {"task_types": ["pm"]},
        "extensions": {},
        "migration_provenance": {"source_schema": "v1", "migrated_at": "2026-11-24T00:00:00Z"},
    }
    errors = validate_structure(data, known_roles=["pm", "dev"])
    assert any("ghost" in e for e in errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_core_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.charter_core.schema'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/charter_core/schema.py
"""Charter v3.0 structural schema — pure shape/enum validation, no semantic resolution.

Semantic checks that need synlynk-specific data (constitution.py's real law/tier
enums, .synlynk/github_apps/ identity records) live in
synlynk/charter_constitution_adapter.py, not here, per the standalone-extraction
constraint: this module must stay resolvable with zero synlynk imports.
"""
from __future__ import annotations

CHARTER_V3_REQUIRED_BLOCKS = (
    "schema_version",
    "core",
    "governance",
    "identity",
    "coordination",
    "constitution_binding",
    "requirements",
    "extensions",
    "migration_provenance",
)

CHARTER_V3_REQUIRED_CORE_KEYS = ("charter_id", "mandate", "authorities", "escalation", "sop")
CHARTER_V3_REQUIRED_GOVERNANCE_KEYS = ("tools", "credentials", "evidence_contracts")
CHARTER_V3_REQUIRED_CONSTITUTION_KEYS = ("tier_acknowledgements", "law_refs", "evidence_ref")

VALID_OPERATIONS = ("delegate", "request", "notify", "escalate")
VALID_TRANSPORTS = ("dispatch_job", "gh_pr_comment", "gh_issue", "state_db_table", "queue")
VALID_AUTONOMY_LEVELS = ("none", "supervised", "scoped", "full")


def validate_structure(data: dict, known_roles: list) -> list:
    """Return a list of human-readable error strings; empty list means structurally valid."""
    errors = []

    for block in CHARTER_V3_REQUIRED_BLOCKS:
        if block not in data:
            errors.append(f"missing required top-level block: 'core' chain -> '{block}'")

    core = data.get("core", {})
    if isinstance(core, dict):
        for key in CHARTER_V3_REQUIRED_CORE_KEYS:
            if key not in core:
                errors.append(f"core: missing required key '{key}'")
    elif "core" in data:
        errors.append("core: expected a mapping")

    governance = data.get("governance", {})
    if isinstance(governance, dict):
        for key in CHARTER_V3_REQUIRED_GOVERNANCE_KEYS:
            if key not in governance:
                errors.append(f"governance: missing required key '{key}'")

    identity = data.get("identity", {})
    if isinstance(identity, dict):
        if "app_ref" not in identity:
            errors.append("identity: missing required key 'app_ref'")
        elif not isinstance(identity["app_ref"], str) or ":" not in identity["app_ref"]:
            errors.append("identity.app_ref: must be a typed URI string, e.g. 'github-app:<role>'")

    coordination = data.get("coordination", {})
    if isinstance(coordination, dict):
        handoffs = coordination.get("handoffs", [])
        if not isinstance(handoffs, list):
            errors.append("coordination.handoffs: expected a list")
        else:
            for i, edge in enumerate(handoffs):
                if not isinstance(edge, dict):
                    errors.append(f"coordination.handoffs[{i}]: expected a mapping")
                    continue
                to_role = edge.get("to_role")
                if to_role not in known_roles:
                    errors.append(f"coordination.handoffs[{i}]: to_role '{to_role}' is not a known role")
                operation = edge.get("operation")
                if operation not in VALID_OPERATIONS:
                    errors.append(
                        f"coordination.handoffs[{i}]: operation '{operation}' not in {VALID_OPERATIONS}"
                    )
                transport = edge.get("transport")
                if transport not in VALID_TRANSPORTS:
                    errors.append(
                        f"coordination.handoffs[{i}]: transport '{transport}' not in {VALID_TRANSPORTS}"
                    )

    constitution_binding = data.get("constitution_binding", {})
    if isinstance(constitution_binding, dict):
        for key in CHARTER_V3_REQUIRED_CONSTITUTION_KEYS:
            if key not in constitution_binding:
                errors.append(f"constitution_binding: missing required key '{key}'")

    requirements = data.get("requirements", {})
    if isinstance(requirements, dict):
        if "task_types" not in requirements:
            errors.append("requirements: missing required key 'task_types'")

    return errors
```

- [ ] **Step 4: Wire `__init__.py` re-exports (from Task 1's commented-out body)**

```python
# synlynk/charter_core/__init__.py
"""Extraction-ready Charter v3.0 core: schema, strict-YAML parsing, structural validation.

Zero synlynk-package imports by design (standalone-extraction-readiness constraint,
docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md).
"""
from synlynk.charter_core.yaml_subset import parse_yaml, dump_yaml  # noqa: F401
from synlynk.charter_core.schema import (  # noqa: F401
    CHARTER_V3_REQUIRED_BLOCKS,
    VALID_OPERATIONS,
    VALID_TRANSPORTS,
    VALID_AUTONOMY_LEVELS,
    validate_structure,
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_charter_core_schema.py -v`
Expected: PASS (all 3 tests)

Also re-run the zero-import guard test, since `__init__.py` now imports `synlynk.charter_core.schema`:

Run: `pytest tests/test_charter_core_yaml_subset.py::test_charter_core_has_zero_synlynk_imports -v`
Expected: PASS (the exclusion for `synlynk.charter_core.*` added in Task 1 Step 3 covers this)

- [ ] **Step 6: Commit**

```bash
git add synlynk/charter_core/schema.py synlynk/charter_core/__init__.py tests/test_charter_core_schema.py
git commit -m "feat: Charter v3.0 structural schema validator (charter_core.schema)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Constitution + identity semantic adapter

**Files:**
- Create: `synlynk/charter_constitution_adapter.py`
- Test: `tests/test_charter_constitution_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charter_constitution_adapter.py
def test_validate_constitution_binding_rejects_unknown_tier():
    from synlynk.charter_constitution_adapter import validate_constitution_binding

    data = {
        "constitution_binding": {
            "tier_acknowledgements": ["t0-fake"],
            "law_refs": [],
            "evidence_ref": "state_db:capability_ratings",
        }
    }
    errors = validate_constitution_binding(data)
    assert any("t0-fake" in e for e in errors)


def test_validate_constitution_binding_accepts_real_tiers_and_law_refs():
    from synlynk.charter_constitution_adapter import validate_constitution_binding

    data = {
        "constitution_binding": {
            "tier_acknowledgements": ["injected", "cited"],
            "law_refs": [
                {"law_id": "law-0", "applies_to": "sop_step:1", "evidence_ref": "state_db:row:1"},
                {"law_id": "law-3", "applies_to": "sop_step:2", "evidence_ref": "state_db:row:2"},
            ],
            "evidence_ref": "state_db:capability_ratings",
        }
    }
    errors = validate_constitution_binding(data)
    assert errors == []


def test_validate_constitution_binding_rejects_unknown_law_id():
    from synlynk.charter_constitution_adapter import validate_constitution_binding

    data = {
        "constitution_binding": {
            "tier_acknowledgements": ["injected"],
            "law_refs": [{"law_id": "law-99", "applies_to": "sop_step:1", "evidence_ref": "x"}],
            "evidence_ref": "x",
        }
    }
    errors = validate_constitution_binding(data)
    assert any("law-99" in e for e in errors)


def test_validate_identity_requires_github_app_dir(tmp_path):
    from synlynk.charter_constitution_adapter import validate_identity

    repo = tmp_path
    (repo / ".synlynk" / "github_apps" / "pm").mkdir(parents=True)
    ok = validate_identity({"identity": {"app_ref": "github-app:pm"}}, repo_path=str(repo))
    assert ok == []

    missing = validate_identity({"identity": {"app_ref": "github-app:ghost"}}, repo_path=str(repo))
    assert any("ghost" in e for e in missing)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_constitution_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.charter_constitution_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/charter_constitution_adapter.py
"""Synlynk-specific semantic validation for Charter v3.0's constitution_binding and
identity blocks. This is deliberately NOT in synlynk/charter_core/ — it reads real
data from synlynk/constitution.py and .synlynk/github_apps/, which charter_core must
never import (standalone-extraction-readiness constraint)."""
from __future__ import annotations

import os

from synlynk.constitution import CONSTITUTION_LAWS, DeliveryTier

_VALID_TIERS = {tier.value for tier in DeliveryTier}


def validate_constitution_binding(data: dict) -> list:
    errors = []
    binding = data.get("constitution_binding", {})
    if not isinstance(binding, dict):
        return ["constitution_binding: expected a mapping"]

    for tier in binding.get("tier_acknowledgements", []):
        if tier not in _VALID_TIERS:
            errors.append(f"constitution_binding.tier_acknowledgements: '{tier}' is not a real DeliveryTier value {sorted(_VALID_TIERS)}")

    for i, ref in enumerate(binding.get("law_refs", [])):
        if not isinstance(ref, dict):
            errors.append(f"constitution_binding.law_refs[{i}]: expected a mapping")
            continue
        law_id = ref.get("law_id")
        if law_id not in CONSTITUTION_LAWS:
            errors.append(f"constitution_binding.law_refs[{i}]: law_id '{law_id}' is not a known law in constitution.CONSTITUTION_LAWS")
        if not ref.get("evidence_ref"):
            errors.append(f"constitution_binding.law_refs[{i}]: missing evidence_ref")

    if not binding.get("evidence_ref"):
        errors.append("constitution_binding: missing top-level evidence_ref")

    return errors


def validate_identity(data: dict, repo_path: str) -> list:
    identity = data.get("identity", {})
    app_ref = identity.get("app_ref", "")
    if not app_ref.startswith("github-app:"):
        return [f"identity.app_ref: '{app_ref}' is not a github-app: typed ref"]
    role = app_ref.split(":", 1)[1]
    app_dir = os.path.join(repo_path, ".synlynk", "github_apps", role)
    if not os.path.isdir(app_dir):
        return [f"identity.app_ref: no GitHub App record found for role '{role}' at {app_dir}"]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_constitution_adapter.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_constitution_adapter.py tests/test_charter_constitution_adapter.py
git commit -m "feat: constitution_binding + identity semantic validator for Charter v3.0

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: Migrate a v1 charter (`DEFAULT_ROLE_CHARTERS["pm"]`) to v3

**Files:**
- Create: `synlynk/charter_migrate.py`
- Test: `tests/test_charter_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charter_migrate.py
def test_migrate_v1_to_v3_preserves_pm_content_and_adds_reserved_blocks():
    from synlynk.charter_migrate import migrate_v1_to_v3
    from synlynk.charters import DEFAULT_ROLE_CHARTERS

    pm_v1 = DEFAULT_ROLE_CHARTERS["pm"]
    v3 = migrate_v1_to_v3("pm", pm_v1)

    assert v3["schema_version"].startswith("3.")
    assert v3["core"]["charter_id"] == "pm"
    assert v3["core"]["mandate"] == pm_v1["mandate"]
    assert v3["core"]["authorities"] == pm_v1["autonomous_authorities"]
    assert v3["core"]["escalation"] == pm_v1["escalation_triggers"]
    assert v3["core"]["sop"] == pm_v1["wake_cycle_sop"]
    # Reserved blocks exist even though v1 had no data for them.
    assert v3["governance"] == {"tools": [], "credentials": [], "evidence_contracts": []}
    assert v3["identity"] == {"app_ref": "github-app:pm"}
    assert v3["coordination"] == {"handoffs": []}
    assert v3["constitution_binding"]["tier_acknowledgements"] == []
    assert v3["requirements"]["task_types"] == []
    assert v3["extensions"] == {}
    assert v3["migration_provenance"]["source_schema"] == "v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_migrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.charter_migrate'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/charter_migrate.py
"""Deterministic migration of legacy v1/v2.0 charters into the Charter v3.0 shape.

Per the migration strategy in docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md:
- v1 charters (DEFAULT_ROLE_CHARTERS / .synlynk/charters/<role>.json without schema_version)
  get empty-but-valid reserved blocks added.
- v2.0 SFIA charters (schema_version: "2.0", tpm.json/wingman.json) carry their existing
  sfia_mapping/boundaries/governance-shaped fields forward unchanged.
No v1/v2 content is dropped; round-trip tests in this file's test module assert that.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def migrate_v1_to_v3(role: str, v1_data: dict) -> dict:
    return {
        "schema_version": "3.0.0",
        "core": {
            "charter_id": role,
            "mandate": v1_data.get("mandate", ""),
            "authorities": list(v1_data.get("autonomous_authorities", [])),
            "escalation": list(v1_data.get("escalation_triggers", [])),
            "sop": list(v1_data.get("wake_cycle_sop", [])),
        },
        "governance": {
            "tools": list(v1_data.get("tools", [])),
            "credentials": list(v1_data.get("credentials", [])),
            "evidence_contracts": list(v1_data.get("verification_contracts", [])),
        },
        "identity": {"app_ref": f"github-app:{role}"},
        "coordination": {"handoffs": []},
        "constitution_binding": {
            "tier_acknowledgements": [],
            "law_refs": [],
            "evidence_ref": "",
        },
        "requirements": {"task_types": []},
        "extensions": {},
        "migration_provenance": {
            "source_schema": "v1",
            "migrated_at": _now_iso(),
            "source_fields_dropped": [],
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_migrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_migrate.py tests/test_charter_migrate.py
git commit -m "feat: migrate_v1_to_v3 charter migration function

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Migrate a v2.0 SFIA charter (`tpm.json`) to v3

**Files:**
- Modify: `synlynk/charter_migrate.py`
- Modify: `tests/test_charter_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_v2_to_v3_preserves_sfia_and_governance_fields():
    from synlynk.charter_migrate import migrate_v2_to_v3

    tpm_v2 = {
        "schema_version": "2.0",
        "role": "tpm",
        "mandate": "Own technical program sequencing.",
        "sfia_mapping": {"sfia_code": "PROG", "sfia_level": 5},
        "boundaries": ["no_direct_prod_deploy"],
        "coordination_pattern": "orchestrator",
        "tools": [{"id": "gh_write", "scope": "pr", "mode": "allow"}],
        "credentials": [{"secret_ref": "env:GH_TOKEN"}],
        "evidence_contracts": ["capability_ratings_row"],
    }
    v3 = migrate_v2_to_v3("tpm", tpm_v2)

    assert v3["core"]["charter_id"] == "tpm"
    assert v3["core"]["mandate"] == tpm_v2["mandate"]
    assert v3["sfia_mapping"] == tpm_v2["sfia_mapping"]
    assert v3["boundaries"] == tpm_v2["boundaries"]
    assert v3["governance"]["tools"] == tpm_v2["tools"]
    assert v3["governance"]["credentials"] == tpm_v2["credentials"]
    assert v3["governance"]["evidence_contracts"] == tpm_v2["evidence_contracts"]
    assert v3["coordination"]["handoffs"] == []
    assert v3["migration_provenance"]["source_schema"] == "v2.0"
    # coordination_pattern's old string value is preserved, not discarded, under extensions.
    assert v3["extensions"]["legacy_v2"]["coordination_pattern"] == "orchestrator"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_migrate.py::test_migrate_v2_to_v3_preserves_sfia_and_governance_fields -v`
Expected: FAIL with `ImportError: cannot import name 'migrate_v2_to_v3'`

- [ ] **Step 3: Write minimal implementation**

Add to `synlynk/charter_migrate.py`:

```python
def migrate_v2_to_v3(role: str, v2_data: dict) -> dict:
    return {
        "schema_version": "3.0.0",
        "core": {
            "charter_id": role,
            "mandate": v2_data.get("mandate", ""),
            "authorities": list(v2_data.get("autonomous_authorities", [])),
            "escalation": list(v2_data.get("escalation_triggers", [])),
            "sop": list(v2_data.get("wake_cycle_sop", [])),
        },
        "sfia_mapping": v2_data.get("sfia_mapping"),
        "boundaries": list(v2_data.get("boundaries", [])),
        "governance": {
            "tools": list(v2_data.get("tools", [])),
            "credentials": list(v2_data.get("credentials", [])),
            "evidence_contracts": list(v2_data.get("evidence_contracts", [])),
        },
        "identity": {"app_ref": f"github-app:{role}"},
        "coordination": {"handoffs": []},
        "constitution_binding": {
            "tier_acknowledgements": [],
            "law_refs": [],
            "evidence_ref": "",
        },
        "requirements": {"task_types": []},
        "extensions": {
            "legacy_v2": {"coordination_pattern": v2_data.get("coordination_pattern")},
        },
        "migration_provenance": {
            "source_schema": "v2.0",
            "migrated_at": _now_iso(),
            "source_fields_dropped": [],
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_migrate.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_migrate.py tests/test_charter_migrate.py
git commit -m "feat: migrate_v2_to_v3 charter migration function

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Migration round-trip test across all 9 non-v3 roles

**Files:**
- Modify: `tests/test_charter_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_v1_to_v3_round_trips_every_default_role_charter():
    from synlynk.charter_core.schema import validate_structure
    from synlynk.charter_migrate import migrate_v1_to_v3
    from synlynk.charters import DEFAULT_ROLE_CHARTERS

    known_roles = list(DEFAULT_ROLE_CHARTERS.keys())
    for role, v1_data in DEFAULT_ROLE_CHARTERS.items():
        v3 = migrate_v1_to_v3(role, v1_data)
        errors = validate_structure(v3, known_roles=known_roles)
        assert errors == [], f"role {role} failed structural validation: {errors}"
        # No v1 mandate/authority/escalation/sop content was silently dropped.
        assert v3["core"]["mandate"] == v1_data.get("mandate", "")
        assert v3["core"]["authorities"] == list(v1_data.get("autonomous_authorities", []))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_migrate.py::test_migrate_v1_to_v3_round_trips_every_default_role_charter -v`
Expected: Likely PASS already, since Tasks 4 and 6 built exactly for this. If it FAILS, the failure will point at a specific role/field — this is the expected place to discover a `DEFAULT_ROLE_CHARTERS` entry whose shape doesn't match the `pm` fixture used to design Task 6 (e.g. a role missing `wake_cycle_sop`). Read the assertion error for the exact role and field.

- [ ] **Step 3: Fix any discovered edge case**

If a role is missing a key `migrate_v1_to_v3` assumes exists (e.g. no `wake_cycle_sop` list), the `.get(key, [])` / `.get(key, "")` defaults already in Task 6's implementation handle absence safely — no code change should be needed. If the test fails for a different reason (e.g. a role's `mandate` is `None` instead of a missing key), add a coercion in `migrate_v1_to_v3`:

```python
            "mandate": v1_data.get("mandate") or "",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_migrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_migrate.py tests/test_charter_migrate.py
git commit -m "test: round-trip migration + structural validation for all default-role charters

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: `cmd_charter_migrate` — dry-run and `--apply` write-back

**Files:**
- Modify: `synlynk/charter_migrate.py`
- Modify: `tests/test_charter_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_charter_migrate_dry_run_writes_nothing(tmp_path):
    from synlynk.charter_migrate import cmd_charter_migrate

    charters_dir = tmp_path / ".synlynk" / "charters"
    charters_dir.mkdir(parents=True)

    result = cmd_charter_migrate(role="pm", apply=False, charters_dir=str(charters_dir))

    assert result["role"] == "pm"
    assert result["applied"] is False
    assert "core" in result["migrated"]
    assert not (charters_dir / "pm.v3.yaml").exists()


def test_cmd_charter_migrate_apply_writes_v3_yaml_file(tmp_path):
    from synlynk.charter_migrate import cmd_charter_migrate
    from synlynk.charter_core.yaml_subset import parse_yaml

    charters_dir = tmp_path / ".synlynk" / "charters"
    charters_dir.mkdir(parents=True)

    result = cmd_charter_migrate(role="pm", apply=True, charters_dir=str(charters_dir))

    assert result["applied"] is True
    out_file = charters_dir / "pm.v3.yaml"
    assert out_file.exists()
    written = parse_yaml(out_file.read_text())
    assert written["core"]["charter_id"] == "pm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_migrate.py -k cmd_charter_migrate -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_charter_migrate'`

- [ ] **Step 3: Write minimal implementation**

Add to `synlynk/charter_migrate.py`:

```python
import os

from synlynk.charter_core.yaml_subset import dump_yaml
from synlynk.charters import DEFAULT_ROLE_CHARTERS


def cmd_charter_migrate(role: str, apply: bool = False, charters_dir: str = None) -> dict:
    """Migrate one role's v1 charter to v3. Returns a result dict; writes a file only if apply=True."""
    if role not in DEFAULT_ROLE_CHARTERS:
        raise ValueError(f"unknown role for migration: {role!r}")

    v1_data = DEFAULT_ROLE_CHARTERS[role]
    migrated = migrate_v1_to_v3(role, v1_data)

    if apply:
        if not charters_dir:
            raise ValueError("charters_dir is required when apply=True")
        os.makedirs(charters_dir, exist_ok=True)
        out_path = os.path.join(charters_dir, f"{role}.v3.yaml")
        with open(out_path, "w") as f:
            f.write(dump_yaml(migrated))

    return {"role": role, "applied": apply, "migrated": migrated}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_migrate.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_migrate.py tests/test_charter_migrate.py
git commit -m "feat: cmd_charter_migrate dry-run/apply entry point

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Wire `synlynk charter migrate` into the CLI

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_charter_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_charter_migrate_dry_run_subprocess(tmp_path, monkeypatch):
    import subprocess
    import sys

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk" / "charters").mkdir(parents=True)

    cli_path = __import__("synlynk.cli", fromlist=["__file__"]).__file__
    proc = subprocess.run(
        [sys.executable, cli_path, "charter", "migrate", "--role", "pm"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "pm" in proc.stdout
    assert not (tmp_path / ".synlynk" / "charters" / "pm.v3.yaml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_migrate.py::test_cli_charter_migrate_dry_run_subprocess -v`
Expected: FAIL — `argparse` exits non-zero with `invalid choice: 'charter'` (only the existing `charters` subcommand with its `adapt` action exists today; `charter` singular is new)

- [ ] **Step 3: Write minimal implementation**

In `synlynk/cli.py`, near the existing `charters_parser` block (around line 1792), add a sibling `charter` parser:

```python
    charter_parser = subparsers.add_parser("charter", help="Migrate/validate individual role charters (Charter v3.0)")
    charter_sub = charter_parser.add_subparsers(dest="charter_action")
    charter_migrate_parser = charter_sub.add_parser("migrate", help="Migrate a v1/v2.0 charter to Charter v3.0")
    charter_migrate_parser.add_argument("--role", required=True, help="Role to migrate (e.g. pm, dev)")
    charter_migrate_parser.add_argument("--apply", action="store_true", help="Write the migrated v3 YAML file (default: dry-run)")
```

Also add `"charter"` to the top-level command list near line 333 (`"logs", "shell", ..., "charters", "cost",` → add `"charter",` alongside `"charters"`).

In the dispatch section near line 3298 (`elif args.command == "charters":`), add a sibling branch:

```python
    elif args.command == "charter":
        if getattr(args, "charter_action", None) == "migrate":
            from synlynk.charter_migrate import cmd_charter_migrate
            result = cmd_charter_migrate(
                role=args.role, apply=args.apply, charters_dir=os.path.join(os.getcwd(), ".synlynk", "charters")
            )
            print(f"role={result['role']} applied={result['applied']}")
            if not result["applied"]:
                print("(dry-run — pass --apply to write the v3 YAML file)")
        else:
            parser.parse_args(["charter", "--help"])
```

(Confirm `os` is already imported at module scope in `cli.py` — it is, used throughout the file for path handling.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_migrate.py::test_cli_charter_migrate_dry_run_subprocess -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_charter_migrate.py
git commit -m "feat: wire 'synlynk charter migrate' CLI subcommand

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: `charters.py::load_charter()` dual-read for v3 YAML files

**Files:**
- Modify: `synlynk/charters.py:16-34` (the `AgentCharter` dataclass)
- Modify: `synlynk/charters.py` (`load_charter()` function)
- Test: `tests/test_charters_v3_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charters_v3_loader.py
def test_load_charter_reads_v3_yaml_file(tmp_path, monkeypatch):
    from synlynk.charter_core.yaml_subset import dump_yaml
    from synlynk.charter_migrate import migrate_v1_to_v3
    from synlynk.charters import DEFAULT_ROLE_CHARTERS, load_charter

    charters_dir = tmp_path / ".synlynk" / "charters"
    charters_dir.mkdir(parents=True)
    v3 = migrate_v1_to_v3("pm", DEFAULT_ROLE_CHARTERS["pm"])
    (charters_dir / "pm.yaml").write_text(dump_yaml(v3))

    monkeypatch.chdir(tmp_path)
    charter = load_charter("pm")

    assert charter.role == "pm"
    assert charter.mandate == DEFAULT_ROLE_CHARTERS["pm"]["mandate"]
    assert charter.schema_version == "3.0.0"
    assert charter.identity == {"app_ref": "github-app:pm"}
    assert charter.coordination == {"handoffs": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charters_v3_loader.py -v`
Expected: FAIL — `load_charter("pm")` currently only looks for `pm.json` (not `.yaml`) and `AgentCharter` has no `schema_version`/`identity`/`coordination` fields, so this raises `AttributeError`

- [ ] **Step 3: Write minimal implementation**

In `synlynk/charters.py`, extend the dataclass (around line 16-34):

```python
@dataclass
class AgentCharter:
    role: str
    harness_bindings: List[str]
    mandate: str
    autonomous_authorities: List[str]
    escalation_triggers: List[str]
    behavioral_weights: Dict[str, str]
    durability: Optional[str] = None
    wake_cycle_sop: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    sops: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    credentials: List[str] = field(default_factory=list)
    verification_contracts: List[str] = field(default_factory=list)
    description: Optional[str] = None
    primary_archetype: Optional[str] = None
    sfia_mapping: Optional[dict] = None
    boundaries: List[str] = field(default_factory=list)
    evidence_contracts: List[str] = field(default_factory=list)
    schema_version: Optional[str] = None
    identity: Optional[dict] = None
    coordination: Optional[dict] = None
    constitution_binding: Optional[dict] = None
    requirements: Optional[dict] = None
```

Find `load_charter()`'s existing JSON-file-lookup branch (it resolves `_charters_dir()` then looks for `<role>.json`) and add a v3 YAML check **before** that lookup:

```python
def load_charter(role: str) -> AgentCharter:
    charters_dir = _charters_dir()
    v3_path = os.path.join(charters_dir, f"{role}.yaml")
    if os.path.isfile(v3_path):
        with open(v3_path) as f:
            data = parse_yaml(f.read())
        core = data.get("core", {})
        return AgentCharter(
            role=core.get("charter_id", role),
            harness_bindings=[],
            mandate=core.get("mandate", ""),
            autonomous_authorities=list(core.get("authorities", [])),
            escalation_triggers=list(core.get("escalation", [])),
            behavioral_weights={},
            wake_cycle_sop=list(core.get("sop", [])),
            tools=list(data.get("governance", {}).get("tools", [])),
            credentials=list(data.get("governance", {}).get("credentials", [])),
            verification_contracts=list(data.get("governance", {}).get("evidence_contracts", [])),
            sfia_mapping=data.get("sfia_mapping"),
            boundaries=list(data.get("boundaries", [])),
            schema_version=data.get("schema_version"),
            identity=data.get("identity"),
            coordination=data.get("coordination"),
            constitution_binding=data.get("constitution_binding"),
            requirements=data.get("requirements"),
        )
    # ... existing v1/v2.0 JSON-file / DEFAULT_ROLE_CHARTERS / agent_store-override logic unchanged below ...
```

Add the import at the top of `synlynk/charters.py`:

```python
from synlynk.charter_core.yaml_subset import parse_yaml
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charters_v3_loader.py -v`
Expected: PASS

Then run the full existing charter test suite to confirm no regression to the legacy v1/v2.0 path:

Run: `pytest tests/test_charters.py tests/test_wingman_charter.py tests/test_autonomous_role_charters.py -v`
Expected: PASS (all previously-passing tests still pass — the v3 branch only activates when a `<role>.yaml` file exists, which none of the legacy fixtures create)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charters.py tests/test_charters_v3_loader.py
git commit -m "feat: dual-read Charter v3.0 YAML files in charters.py::load_charter()

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage.** Checked against `docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md` and the three decision records:
- Canonical form (JSON Schema contract + JSON data model + strict-YAML authoring) — Tasks 2-4.
- `governance{tools,credentials,evidence_contracts}` reserved block — Task 4 (schema), Tasks 6-7 (migration).
- `identity.app_ref`, `coordination.handoffs[]` (typed-edge list with `to_role`/`operation`/`transport`/`ack`), required structural `constitution_binding` (`tier_acknowledgements`/`law_refs`/`evidence_ref`) resolved against the real `constitution.py` enums — Tasks 4-5.
- `requirements` block replacing hardcoded `harness_bindings` (deletion itself deferred, per Scope Check item 2, but the new field now exists and is populated by migration) — Tasks 4, 6-7.
- `extensions` namespaced escape hatch, `migration_provenance` — Tasks 4, 6-7.
- Deterministic `synlynk charter migrate`, round-trip test asserting no v1 content loss — Tasks 6-10.
- Loader dual-read for a bounded window — Task 11.
- Vizor editor regen, `harness_bindings` deletion, `charter_injection.py` wiring, `constitution_gate.py` enforce-flip — explicitly deferred in Scope Check, matching the decision records' own milestone-gated sequencing.

**2. Placeholder scan.** No TBD/TODO markers; every step has complete, runnable code; no "similar to Task N" references — Task 7 and 9 each repeat the full code they need rather than pointing back.

**3. Type consistency.** `parse_yaml`/`dump_yaml` signatures match across Tasks 2, 3, 9, 11. `validate_structure(data, known_roles)` signature matches across Tasks 4, 8. `migrate_v1_to_v3(role, v1_data)` / `migrate_v2_to_v3(role, v2_data)` signatures match across Tasks 6, 7, 8, 9. `AgentCharter`'s new fields (`schema_version`, `identity`, `coordination`, `constitution_binding`, `requirements`) are named identically in the dataclass (Task 11) and the test assertions (Task 11's test).

---

**Plan complete and saved to `docs/superpowers/plans/2026-11-24-charter-v3-schema-unification.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
