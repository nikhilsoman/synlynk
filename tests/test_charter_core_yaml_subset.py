import ast
import pathlib


def test_charter_core_has_zero_synlynk_imports():
    """charter_core must be extraction-ready: no synlynk imports from outside its own package."""
    pkg_dir = pathlib.Path(__file__).resolve().parents[1] / "synlynk" / "charter_core"
    assert pkg_dir.is_dir(), f"{pkg_dir} does not exist yet"
    offending = []
    for py_file in pkg_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "synlynk" or (
                        alias.name.startswith("synlynk.")
                        and not alias.name.startswith("synlynk.charter_core")
                    ):
                        offending.append((py_file.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.module
                    and node.module.startswith("synlynk.")
                    and not node.module.startswith("synlynk.charter_core")
                ):
                    offending.append((py_file.name, node.module))
                elif node.module == "synlynk":
                    offending.append((py_file.name, node.module))
    assert offending == [], f"synlynk imports found in charter_core: {offending}"


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
