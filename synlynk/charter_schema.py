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
