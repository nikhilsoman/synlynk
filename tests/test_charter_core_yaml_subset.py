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
