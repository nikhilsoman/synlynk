"""Charter frontmatter schema: parsing, validation, and rendering.

Zero-dependency (no PyYAML) — the project has no third-party dependencies,
so this hand-rolls just enough of YAML's flat-mapping/list syntax to cover
what a charter's frontmatter actually uses. It is not a general YAML parser.

See docs/superpowers/specs/2026-08-27-charter-content-structure-design.md.
"""
from __future__ import annotations

import json
import os
from typing import Optional

KNOWN_ROLES = (
    "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot", "maintainer",
    "secops", "infra-devops", "wingman",
)
VALID_ARCHETYPES = (
    "orchestrator", "strategist", "director", "creator", "inspector", "custodian", "chief-of-staff",
)
VALID_AUTONOMY_LEVELS = ("L1_ADVISORY", "L2_GATED", "L3_AUTONOMOUS")
VALID_DURABILITY = ("durable", "session-only", "dispatch-only")
REQUIRED_SECTIONS = ("Instructions", "Authority & Escalation", "Workflow Ownership")
REQUIRED_FRONTMATTER_KEYS = (
    "schema_version", "role", "description", "durability", "tools", "credentials",
)

_SFIA_CACHE: Optional[dict] = None


def get_sfia_taxonomy() -> dict:
    """Load and return the bundled SFIA skill taxonomy."""
    global _SFIA_CACHE
    if _SFIA_CACHE is None:
        path = os.path.join(os.path.dirname(__file__), "sfia_taxonomy.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                _SFIA_CACHE = json.load(f)
        else:
            _SFIA_CACHE = {"skills": {}}
    return _SFIA_CACHE


def get_sfia_skill(code: str) -> Optional[dict]:
    """Retrieve metadata for a specific SFIA skill code."""
    tax = get_sfia_taxonomy()
    return tax.get("skills", {}).get(code.upper())


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
    body_text = "\n" + "\n".join(lines[end_idx + 1:])
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
            if not non_blank:
                data[key] = [] if key in (
                    "tools", "credentials", "skills", "sops", "autonomous_authorities",
                    "escalation_triggers", "wake_cycle_sop", "verification_contracts",
                    "boundaries", "evidence_contracts"
                ) else ""
            elif all(bl.strip().startswith("- ") for bl in non_blank):
                data[key] = [bl.strip()[2:].strip() for bl in non_blank]
            elif non_blank and all(":" in bl and not bl.strip().startswith("- ") and bl.partition(":")[2].strip() != "" for bl in non_blank):
                dict_val = {}
                for bl in non_blank:
                    k, _, v = bl.strip().partition(":")
                    v_clean = v.strip()
                    if len(v_clean) >= 2 and v_clean[0] in ('"', "'") and v_clean[-1] == v_clean[0]:
                        v_clean = v_clean[1:-1]
                    dict_val[k.strip()] = v_clean
                data[key] = dict_val
            else:
                data[key] = "\n".join(block_lines)
            i = j
        elif rest == "[]":
            data[key] = []
            i += 1
        elif rest == "{}":
            data[key] = {}
            i += 1
        elif rest.startswith("{") and rest.endswith("}"):
            try:
                data[key] = json.loads(rest)
            except Exception:
                data[key] = {}
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

    if "primary_archetype" in data and data["primary_archetype"] not in VALID_ARCHETYPES:
        errors.append(
            f"unknown primary_archetype {data['primary_archetype']!r}; "
            f"must be one of {', '.join(VALID_ARCHETYPES)}"
        )

    if "secondary_hat" in data and data["secondary_hat"] and data["secondary_hat"] not in VALID_ARCHETYPES:
        errors.append(
            f"unknown secondary_hat {data['secondary_hat']!r}; "
            f"must be one of {', '.join(VALID_ARCHETYPES)}"
        )

    if "autonomy_level" in data and data["autonomy_level"] not in VALID_AUTONOMY_LEVELS:
        errors.append(
            f"invalid autonomy_level {data['autonomy_level']!r}; "
            f"must be one of {', '.join(VALID_AUTONOMY_LEVELS)}"
        )

    if "domain_autonomy_caps" in data and data["domain_autonomy_caps"] not in VALID_AUTONOMY_LEVELS:
        errors.append(
            f"invalid domain_autonomy_caps {data['domain_autonomy_caps']!r}; "
            f"must be one of {', '.join(VALID_AUTONOMY_LEVELS)}"
        )

    for list_key in (
        "tools", "credentials", "autonomous_authorities", "escalation_triggers",
        "skills", "sops", "wake_cycle_sop", "verification_contracts",
        "boundaries", "evidence_contracts"
    ):
        if list_key in data and not isinstance(data[list_key], list):
            errors.append(f"{list_key!r} must be a list (use '[]' for empty)")

    if "boundaries" in data and isinstance(data["boundaries"], list):
        for b in data["boundaries"]:
            if not isinstance(b, str) or not b.strip():
                errors.append("boundaries items must be non-empty strings")

    if "sfia_mapping" in data:
        mapping = data["sfia_mapping"]
        if isinstance(mapping, str):
            parsed_map = {}
            for line in mapping.splitlines():
                stripped = line.strip()
                if ":" in stripped:
                    k, _, v = stripped.partition(":")
                    parsed_map[k.strip()] = v.strip().strip('"\'')
            if parsed_map:
                data["sfia_mapping"] = parsed_map
                mapping = parsed_map

        if not isinstance(mapping, dict):
            errors.append("sfia_mapping must be a mapping/dict")
        else:
            if data.get("primary_archetype") == "chief-of-staff":
                if "composite_skills" in mapping and not isinstance(mapping["composite_skills"], list):
                    errors.append("chief-of-staff sfia_mapping.composite_skills must be a list")
            elif "sfia_code" in mapping:
                code = mapping.get("sfia_code")
                if not isinstance(code, str) or not code.strip():
                    errors.append("sfia_mapping.sfia_code must be a non-empty string")
                if "sfia_level" in mapping:
                    try:
                        lvl = int(mapping["sfia_level"])
                        if not (1 <= lvl <= 7):
                            errors.append(f"sfia_mapping.sfia_level must be between 1 and 7, got {lvl}")
                    except (ValueError, TypeError):
                        errors.append("sfia_mapping.sfia_level must be an integer between 1 and 7")

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
