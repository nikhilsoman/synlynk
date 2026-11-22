"""Comment-only intake check for newly opened early-adopter issues."""

import json
import re
import subprocess
import sys
from pathlib import Path


_FP = re.compile(r"^fingerprint: [0-9a-f]{12}$", re.M)
COMMENT = (
    "Thanks for the report. It has no diagnostic bundle. Please run `synlynk report` "
    "(redacted and previewed before filing) and paste the result, or file a new issue with it."
)


def needs_bundle_comment(issue: dict) -> bool:
    return "early-adopter" in issue.get("labels", []) and not _FP.search(issue.get("body", ""))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        return 2

    event = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    labels = [
        label.get("name", "") if isinstance(label, dict) else str(label)
        for label in issue.get("labels", [])
    ]
    normalized_issue = {**issue, "labels": labels}
    if not needs_bundle_comment(normalized_issue):
        return 0

    number = issue.get("number")
    if number is None:
        return 2
    result = subprocess.run(
        ["gh", "issue", "comment", str(number), "--body", COMMENT],
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
