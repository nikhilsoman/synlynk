# Plan: CI Supported-Python Matrix

1. Inspect active required-check configuration and workflow references.
2. Edit `.github/workflows/test.yml` to use Python 3.10 and 3.12 only.
3. Run YAML/configuration checks and the smallest relevant local test selection.
4. Commit the workflow-only change with the required Codex trailer.
5. Push the feature branch and open a PR linked to #1494.
6. Obtain genuine QA review and compare CI timing against the recorded baseline.
