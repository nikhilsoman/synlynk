from pathlib import Path
import pytest


def test_all_four_graphify_skills_exist_and_have_valid_frontmatter():
    skills_dir = Path(".synlynk/skills")
    required_skills = [
        "graphify-architecture-audit",
        "graphify-pr-impact",
        "graphify-symbol-navigator",
        "graphify-domain-sweep",
    ]
    for skill in required_skills:
        skill_file = skills_dir / skill / "SKILL.md"
        assert skill_file.is_file(), f"Missing skill file: {skill_file}"
        content = skill_file.read_text()
        assert content.startswith("---"), f"Skill {skill} missing YAML frontmatter"
        assert "name: " in content
        assert "description: " in content


@pytest.mark.parametrize(
    "skill_name,expected_role,expected_tools",
    [
        (
            "graphify-architecture-audit",
            "architect",
            ["god_nodes", "get_community", "find_cycles", "synlynk heal --cycles"],
        ),
        (
            "graphify-pr-impact",
            "verifier",
            ["get_pr_impact", "shortest_path", "synlynk pr check", "synlynk impact"],
        ),
        (
            "graphify-symbol-navigator",
            "builder",
            ["get_neighbors", "query_graph", "synlynk pack", "synlynk impact"],
        ),
        (
            "graphify-domain-sweep",
            "pm",
            ["query_graph", "--mode deep", "graphify extract", "synlynk pm sweep"],
        ),
    ],
)
def test_skill_roles_and_tools_documented(skill_name, expected_role, expected_tools):
    skill_file = Path(".synlynk/skills") / skill_name / "SKILL.md"
    content = skill_file.read_text()

    # Verify frontmatter name matches directory name
    lines = content.splitlines()
    assert lines[0] == "---"
    assert f"name: {skill_name}" in lines

    # Verify role attribution
    assert expected_role in content.lower()

    # Verify each expected tool or CLI command is referenced
    for tool in expected_tools:
        assert tool in content, f"Skill {skill_name} does not reference {tool}"
