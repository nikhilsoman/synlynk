"""``synlynk report``: collect, preview (mandatory), and file."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

from synlynk.report_bundle import PUBLIC_NOTICE, collect_bundle, render_body
from synlynk.report_scan import find_secrets

REPO = "nikhilsoman/synlynk"
URL_BODY_CAP = 6000
_input = input


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
    if not local_dir.is_dir():
        raise OSError(f"Report directory does not exist: {local_dir}")
    path = local_dir / f"synlynk-report-{__import__('secrets').token_hex(6)}.md"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(body)
    return str(path)


def _write_local_with_fallback(body: str, local_dir: Path) -> str | None:
    try:
        return _write_local(body, local_dir)
    except OSError:
        try:
            return _write_local(body, Path(tempfile.gettempdir()))
        except OSError:
            return None


def _fallback_url(title: str, body: str) -> str:
    base = f"https://github.com/{REPO}/issues/new?"
    fixed = {"title": title, "labels": "bug,early-adopter"}
    low, high = 0, len(body)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = base + urllib.parse.urlencode({**fixed, "body": body[:middle]})
        if len(candidate) <= URL_BODY_CAP:
            low = middle
        else:
            high = middle - 1
    return base + urllib.parse.urlencode({**fixed, "body": body[:low]})


def confirm_and_file(
    body: str,
    title: str,
    answer=input,
    interactive: bool | None = None,
    local_dir: Path = Path(".synlynk"),
) -> str | None:
    """Return the issue URL/local path, or ``None`` if nothing was filed."""
    interactive = (
        sys.stdin.isatty() and sys.stdout.isatty()
        if interactive is None
        else interactive
    )
    hits = find_secrets(body)
    if hits:
        print(
            f"\nREFUSING TO FILE: {len(hits)} secret-like pattern(s) found. "
            "Remove them and retry."
        )
        return None
    print(PUBLIC_NOTICE, "\n")
    print(body)
    if not interactive:
        path = _write_local_with_fallback(body, local_dir)
        if path is None:
            print("\nNon-interactive: could not save the report.")
            return None
        print(
            f"\nNon-interactive: saved to {path}. "
            "File it from a terminal with `synlynk report`."
        )
        return path
    if answer("\nFile this public issue? [y/N] ").strip().lower() != "y":
        print("Nothing was filed.")
        return None
    try:
        url = _gh_issue_create(title, body)
        print(f"Filed: {url}")
        return url
    except Exception:
        path = _write_local_with_fallback(body, local_dir)
        url = _fallback_url(title, body)
        saved = f"\nFull report saved to {path}" if path else ""
        print(f"gh unavailable. Open: {url}{saved}")
        return url


def cmd_report(args=None) -> int:
    from synlynk import flight_recorder

    if args is not None and getattr(args, "clear_flight", False):
        flight_recorder.clear(os.getcwd())
        print("Flight recorder buffer cleared.")
        return 0

    description = ""
    fingerprint_inputs = None
    if args is not None and getattr(args, "last", False):
        record = flight_recorder.last_failed(os.getcwd())
        if record is None:
            print("No failed command recorded in this project.")
            return 1
        command = str(record.get("command", ""))
        exit_code = int(record.get("exit_code", 1))
        first_error = str(record.get("error", ""))
        description = f"`synlynk {command}` exited {exit_code}: {first_error}"
        fingerprint_inputs = {
            "command": command,
            "exit_code": exit_code,
            "first_error": first_error,
        }

    withheld = []
    visible_terminal = sys.stdin.isatty() and sys.stdout.isatty()
    if visible_terminal and fingerprint_inputs is None:
        description = _input("What went wrong? (one line, optional): ").strip()
    bundle = collect_bundle(**fingerprint_inputs) if fingerprint_inputs else collect_bundle()
    remote = bundle.pop("remote", None)
    if remote not in (None, "none"):
        withheld.append("remote")
        if visible_terminal:
            include_remote = _input(
                "Include the repository identity in the public report? [y/N] "
            ).strip().lower()
            if include_remote == "y":
                bundle["remote"] = remote
                withheld.remove("remote")
    body = render_body(bundle, description, withheld=withheld)
    result = confirm_and_file(
        body, title=f"[report] {description or 'bug report'}"[:100]
    )
    return 0 if result is not None else 1
