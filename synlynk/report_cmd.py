"""``synlynk report``: collect, preview (mandatory), and file."""
from __future__ import annotations

import subprocess
import sys
import urllib.parse
from pathlib import Path

from synlynk.report_bundle import PUBLIC_NOTICE, collect_bundle, render_body
from synlynk.report_scan import find_secrets

REPO = "nikhilsoman/synlynk"
URL_BODY_CAP = 6000


def _gh_issue_create(title: str, body: str) -> str:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            title,
            "--body",
            body,
            "--label",
            "bug",
            "--label",
            "early-adopter",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def _write_local(body: str, local_dir: Path) -> str:
    local_dir.mkdir(parents=True, exist_ok=True)
    path = local_dir / "synlynk-report.md"
    path.write_text(body)
    return str(path)


def confirm_and_file(
    body: str,
    title: str,
    answer=input,
    interactive: bool | None = None,
    local_dir: Path = Path(".synlynk"),
) -> str | None:
    """Return the issue URL/local path, or ``None`` if nothing was filed."""
    interactive = sys.stdin.isatty() if interactive is None else interactive
    print(PUBLIC_NOTICE, "\n")
    print(body)
    hits = find_secrets(body)
    if hits:
        print(
            f"\nREFUSING TO FILE: {len(hits)} secret-like pattern(s) found. "
            "Remove them and retry."
        )
        return None
    if not interactive:
        path = _write_local(body, local_dir)
        print(
            f"\nNon-interactive: saved to {path}. "
            "File it from a terminal with `synlynk report`."
        )
        return path
    if answer("\nFile this public issue? [y/N] ").strip().lower() != "y":
        print("Nothing was filed.")
        return None
    try:
        return _gh_issue_create(title, body)
    except Exception:
        path = _write_local(body, local_dir)
        url = f"https://github.com/{REPO}/issues/new?" + urllib.parse.urlencode(
            {
                "title": title,
                "labels": "bug,early-adopter",
                "body": body[:URL_BODY_CAP],
            }
        )
        print(f"gh unavailable. Open: {url}\nFull report saved to {path}")
        return url


def cmd_report(args=None) -> int:
    description = ""
    if sys.stdin.isatty():
        description = input("What went wrong? (one line, optional): ").strip()
    bundle = collect_bundle()
    body = render_body(bundle, description)
    result = confirm_and_file(
        body, title=f"[report] {description or 'bug report'}"[:100]
    )
    return 0 if result is not None else 1
