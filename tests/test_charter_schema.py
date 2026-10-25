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


def test_parse_frontmatter_nested_flat_dict():
    text = (
        "behavioral_weights:\n"
        "  verbosity: concise\n"
        "  risk_tolerance: conservative\n"
    )
    data = charter_schema.parse_frontmatter(text)
    assert data == {
        "behavioral_weights": {
            "verbosity": "concise",
            "risk_tolerance": "conservative",
        }
    }


def test_validate_charter_accepts_maintainer_role():
    content = _valid_charter(role="maintainer")
    data = charter_schema.validate_charter(content)
    assert data["role"] == "maintainer"


def test_validate_charter_accepts_v2_schema_with_expanded_keys():
    extra = (
        "mandate: \"Maintain workspace hygiene and triage sentinel faults.\"\n"
        "autonomous_authorities:\n"
        "  - triage_sentinel_alerts\n"
        "  - probe_scratch_worktree\n"
        "escalation_triggers:\n"
        "  - recurring_sev1_fault\n"
        "skills:\n"
        "  - systematic-debugging\n"
        "sops:\n"
        "  - wake_cycle: read sentinel -> deduplicate -> probe\n"
        "verification_contracts:\n"
        "  - mandatory_reproduction_test\n"
    )
    content = _valid_charter(role="maintainer", extra_frontmatter=extra)
    data = charter_schema.validate_charter(content)
    assert data["role"] == "maintainer"
    assert data["mandate"] == "Maintain workspace hygiene and triage sentinel faults."
    assert data["autonomous_authorities"] == ["triage_sentinel_alerts", "probe_scratch_worktree"]
    assert data["escalation_triggers"] == ["recurring_sev1_fault"]
    assert data["skills"] == ["systematic-debugging"]
    assert data["verification_contracts"] == ["mandatory_reproduction_test"]


def test_validate_charter_rejects_invalid_list_fields():
    extra = "autonomous_authorities: not-a-list\n"
    content = _valid_charter(role="maintainer", extra_frontmatter=extra)
    with pytest.raises(charter_schema.CharterValidationError) as exc_info:
        charter_schema.validate_charter(content)
    assert "autonomous_authorities" in str(exc_info.value)

