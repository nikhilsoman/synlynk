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
