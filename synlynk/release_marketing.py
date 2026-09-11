"""Marketing Release Ceremony Engine for Synlynk named releases.

Synchronizes:
1. README.md (via synlynk.release_readme)
2. Canonical Synlynk Docs bundles (HTML headers, covers, dates, and mirrored PDFs)
3. Website metadata (website/src/_data/release.json) and static compilation verification
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from synlynk.release_readme import (
    collect_pytest_test_count,
    sync_readme_for_release,
)

CANONICAL_DOC_HTML_NAMES = (
    "synlynk-quickstart-guide.html",
    "synlynk-official-reference.html",
    "synlynk-command-reference.html",
)


@dataclass
class ReleaseCeremonyResult:
    ok: bool
    version: str
    readme_updated: bool = False
    docs_updated: List[str] = field(default_factory=list)
    website_updated: bool = False
    website_build_ok: bool = False
    dry_run: bool = False
    errors: List[str] = field(default_factory=list)


def sync_docs_bundles(
    root: str,
    version: str,
    date_str: Optional[str] = None,
    dry_run: bool = False,
) -> List[str]:
    """Updates version and release dates in canonical documentation HTML files."""
    docs_dir = os.path.join(root, "docs")
    if not os.path.isdir(docs_dir):
        return []

    ver_clean = version.lstrip("v")
    date_clean = date_str or datetime.date.today().isoformat()
    updated: List[str] = []

    for fname in sorted(os.listdir(docs_dir)):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(docs_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # 1. <title>... — vX.Y.Z</title>
        new_content = re.sub(
            r"(<title>[^<]*?v)\d+\.\d+\.\d+([^<]*?</title>)",
            rf"\g<1>{ver_clean}\g<2>",
            new_content,
        )

        # 2. Last updated: vX.Y.Z (YYYY-MM-DD)
        new_content = re.sub(
            r"Last updated:\s*v\d+\.\d+\.\d+\s*\([^)]*\)",
            f"Last updated: v{ver_clean} ({date_clean})",
            new_content,
        )

        # 3. <div class="cover-version">vX.Y.Z ...
        new_content = re.sub(
            r'(class=["\']cover-version["\']>v)\d+\.\d+\.\d+',
            rf"\g<1>{ver_clean}",
            new_content,
        )

        # 4. <div class='pill'>vX.Y.Z</div>
        new_content = re.sub(
            r'(class=["\']pill["\']>v)\d+\.\d+\.\d+',
            rf"\g<1>{ver_clean}",
            new_content,
        )

        # 5. Version X.Y.Z — Released YYYY-MM-DD
        new_content = re.sub(
            r"Version\s+\d+\.\d+\.\d+(\s*—\s*Released\s+[0-9-]+)?",
            f"Version {ver_clean} — Released {date_clean}",
            new_content,
        )

        # 6. SYNL... · vX.Y.Z · synlynk.com in footer
        new_content = re.sub(
            r"([·•]\s*)v\d+\.\d+\.\d+(\s*[·•]\s*synlynk\.com)",
            rf"\g<1>v{ver_clean}\g<2>",
            new_content,
        )

        if new_content != content:
            updated.append(fname)
            if not dry_run:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(new_content)

    return updated


def mirror_docs_pdfs_to_website(
    root: str,
    dry_run: bool = False,
) -> List[str]:
    """Copies all PDF files from docs/ to website/src/assets/docs/."""
    docs_dir = os.path.join(root, "docs")
    dest_dir = os.path.join(root, "website", "src", "assets", "docs")

    if not os.path.isdir(docs_dir):
        return []

    copied: List[str] = []
    for fname in sorted(os.listdir(docs_dir)):
        if fname.endswith(".pdf"):
            src_path = os.path.join(docs_dir, fname)
            dst_path = os.path.join(dest_dir, fname)
            copied.append(fname)
            if not dry_run:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(src_path, dst_path)

    return copied


def update_website_metadata(
    root: str,
    version: str,
    date_str: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """Writes release metadata to website/src/_data/release.json."""
    data_dir = os.path.join(root, "website", "src", "_data")
    meta_file = os.path.join(data_dir, "release.json")

    ver_clean = version.lstrip("v")
    date_clean = date_str or datetime.date.today().isoformat()

    metadata = {
        "version": ver_clean,
        "release_date": date_clean,
        "released_at": date_clean,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if not dry_run:
        os.makedirs(data_dir, exist_ok=True)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
            f.write("\n")

    return True


def verify_website_build(root: str) -> Tuple[bool, str]:
    """Runs Eleventy build inside website/ to verify templates compile cleanly."""
    website_dir = os.path.join(root, "website")
    pkg_json = os.path.join(website_dir, "package.json")
    if not os.path.isfile(pkg_json):
        return True, "No website/package.json found; skipping build."

    try:
        proc = subprocess.run(
            ["npm", "run", "build"],
            cwd=website_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            return True, "Website build succeeded."
        err = (proc.stderr or proc.stdout or "").strip()
        return False, f"npm run build failed (exit {proc.returncode}): {err[:400]}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not run website build: {exc}"


def execute_release_ceremony(
    root: str,
    version: str,
    collected_count: Optional[int] = None,
    hero_summary: Optional[str] = None,
    dry_run: bool = False,
    skip_build: bool = False,
) -> ReleaseCeremonyResult:
    """Executes the complete Marketing Release Ceremony."""
    root = os.path.abspath(os.path.normpath(root))
    ver_clean = version.lstrip("v")
    errors: List[str] = []

    # 1. README.md sync
    readme_path = os.path.join(root, "README.md")
    readme_updated = False
    if os.path.isfile(readme_path):
        if collected_count is None:
            collected_count = collect_pytest_test_count(root)

        if dry_run:
            readme_updated = True
        else:
            try:
                readme_updated = sync_readme_for_release(
                    root=root,
                    version=ver_clean,
                    collected_count=collected_count,
                    hero_summary=hero_summary,
                )
            except Exception as exc:
                errors.append(f"README sync failed: {exc}")
                readme_updated = False

    # 2. Canonical docs HTML update
    docs_updated: List[str] = []
    try:
        docs_updated = sync_docs_bundles(root=root, version=ver_clean, dry_run=dry_run)
    except Exception as exc:
        errors.append(f"Docs bundles sync failed: {exc}")

    # 3. Mirror PDF assets to website
    try:
        mirror_docs_pdfs_to_website(root=root, dry_run=dry_run)
    except Exception as exc:
        errors.append(f"PDF mirroring failed: {exc}")

    # 4. Website metadata update
    website_updated = False
    try:
        website_updated = update_website_metadata(root=root, version=ver_clean, dry_run=dry_run)
    except Exception as exc:
        errors.append(f"Website metadata update failed: {exc}")

    # 5. Website static build verification
    website_build_ok = True
    if not dry_run and not skip_build:
        build_ok, build_msg = verify_website_build(root=root)
        website_build_ok = build_ok
        if not build_ok:
            errors.append(build_msg)

    return ReleaseCeremonyResult(
        ok=(len(errors) == 0),
        version=ver_clean,
        readme_updated=readme_updated,
        docs_updated=docs_updated,
        website_updated=website_updated,
        website_build_ok=website_build_ok,
        dry_run=dry_run,
        errors=errors,
    )
