import subprocess
import sys


def test_generated_reference_doc_matches_taxonomy(tmp_path):
    from scripts.generate_command_docs import render_reference_doc

    with open("docs/reference/commands.md") as f:
        committed = f.read()
    assert render_reference_doc() == committed, (
        "docs/reference/commands.md is stale — run "
        "`python3 scripts/generate_command_docs.py` and commit the result"
    )


def test_generated_readme_section_matches_taxonomy():
    from scripts.generate_command_docs import render_readme_section

    with open("README.md") as f:
        readme = f.read()
    assert render_readme_section() in readme, (
        "README.md's command section is stale — run "
        "`python3 scripts/generate_command_docs.py` and commit the result"
    )
