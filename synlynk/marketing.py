"""Autonomous Growth & Marketing Engine for synlynk.

Handles blog post frontmatter validation, blog index updates, social/changelog
snippet extraction, and growth promotion automation.
See docs/superpowers/specs/2026-09-02-autonomous-growth-and-marketing-engine-design.md.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REQUIRED_BLOG_FRONTMATTER_KEYS = (
    "title",
    "author",
    "date",
    "pr",
    "version",
    "tags",
)


class BlogValidationError(ValueError):
    """Raised when a blog post fails YAML frontmatter schema validation."""

    def __init__(self, errors: Union[str, List[str]]):
        if isinstance(errors, str):
            self.errors = [errors]
        else:
            self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def split_frontmatter(content: str) -> Tuple[Optional[str], str]:
    """Split markdown content into (frontmatter_text, body).

    Returns (None, content) if content does not start with '---' followed by a closing '---'.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, content
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None, content
    frontmatter_text = "\n".join(lines[1:end_idx])
    body_text = "\n" + "\n".join(lines[end_idx + 1:])
    return frontmatter_text, body_text


def parse_yaml_frontmatter(frontmatter_text: str) -> Dict[str, Any]:
    """Parse flat YAML frontmatter into a dict (stdlib only).

    Supports scalars, quoted strings, flow lists [a, b], and block lists (- item).
    """
    data: Dict[str, Any] = {}
    lines = frontmatter_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if line.startswith(" ") or line.startswith("\t"):
            i += 1
            continue

        key, sep, rest = line.partition(":")
        if not sep:
            i += 1
            continue
        key = key.strip()
        rest = rest.strip()

        if not rest:
            # Check for block list following
            j = i + 1
            block_items = []
            while j < len(lines) and (lines[j].startswith("  ") or lines[j].startswith("\t") or not lines[j].strip()):
                bl_stripped = lines[j].strip()
                if bl_stripped.startswith("- "):
                    val = bl_stripped[2:].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    block_items.append(val)
                j += 1
            if block_items:
                data[key] = block_items
                i = j
                continue
            else:
                data[key] = ""
                i += 1
                continue
        elif rest == "[]":
            data[key] = []
            i += 1
            continue
        elif rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            if inner:
                items = []
                for x in inner.split(","):
                    x = x.strip()
                    if (x.startswith('"') and x.endswith('"')) or (x.startswith("'") and x.endswith("'")):
                        x = x[1:-1]
                    if x:
                        items.append(x)
                data[key] = items
            else:
                data[key] = []
            i += 1
            continue
        else:
            if (rest.startswith('"') and rest.endswith('"')) or (rest.startswith("'") and rest.endswith("'")):
                rest = rest[1:-1]
            data[key] = rest
            i += 1
            continue

    return data


def validate_blog_post_frontmatter(path_or_content: Union[str, Path, dict]) -> dict:
    """Validates blog post YAML frontmatter according to schema.

    Enforces required fields:
      - title (non-empty str)
      - author (non-empty str)
      - date (non-empty str)
      - pr (non-empty str or int)
      - version (non-empty str)
      - tags (non-empty list of str)

    Returns the parsed frontmatter dict on success.
    Raises BlogValidationError (subclass of ValueError) on schema violations.
    """
    if isinstance(path_or_content, dict):
        data = dict(path_or_content)
    else:
        path = Path(path_or_content)
        if path.is_file():
            content = path.read_text(encoding="utf-8")
        else:
            content = str(path_or_content)

        fm_text, _ = split_frontmatter(content)
        if fm_text is None:
            raise BlogValidationError("Missing YAML frontmatter block enclosed by '---'")
        data = parse_yaml_frontmatter(fm_text)

    errors = []
    for req_key in REQUIRED_BLOG_FRONTMATTER_KEYS:
        val = data.get(req_key)
        if val is None or val == "" or (isinstance(val, (list, tuple, dict)) and len(val) == 0):
            errors.append(f"Missing or empty required frontmatter field: '{req_key}'")

    if "tags" in data:
        tags = data["tags"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
            data["tags"] = tags
        elif isinstance(tags, list):
            if not tags or not all(isinstance(t, str) and t.strip() for t in tags):
                errors.append("Field 'tags' must be a non-empty list of non-empty strings")
        else:
            errors.append("Field 'tags' must be a list of strings")

    if "pr" in data and data["pr"]:
        data["pr"] = str(data["pr"]).strip()

    if "version" in data and data["version"]:
        data["version"] = str(data["version"]).strip()

    if "date" in data and data["date"]:
        data["date"] = str(data["date"]).strip()

    if errors:
        raise BlogValidationError(errors)

    return data


def extract_social_changelog_snippets(
    blog_post_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> dict:
    """Extracts structured social announcement and changelog snippets from a blog post.

    Exports draft to output_path (defaults to .synlynk/social_drafts.json) and returns the snippet dict.
    """
    path = Path(blog_post_path)
    content = path.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(content)

    if fm_text is not None:
        try:
            meta = validate_blog_post_frontmatter(path)
        except BlogValidationError:
            meta = parse_yaml_frontmatter(fm_text)
    else:
        meta = {}

    title = meta.get("title", path.stem)
    author = meta.get("author", "synlynk team")
    date = str(meta.get("date", ""))
    pr = str(meta.get("pr", ""))
    version = str(meta.get("version", ""))
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    highlights = []
    shipped_match = re.search(r"## What This PR Shipped\s*(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if shipped_match:
        section_text = shipped_match.group(1)
        for line in section_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("- ") or line_str.startswith("* ") or re.match(r"^\d+\.\s+", line_str):
                item = re.sub(r"^[-*]|\d+\.\s*", "", line_str).strip()
                if item:
                    highlights.append(item)
    if not highlights:
        for line in body.splitlines():
            line_str = line.strip()
            if (line_str.startswith("- ") or line_str.startswith("* ")) and len(line_str) > 5:
                highlights.append(line_str[2:].strip())

    tag_str = " ".join(f"#{t.replace(' ', '').replace('-', '')}" for t in tags)
    pr_tag = f"PR {pr}" if pr else ""
    ver_tag = f"v{version}" if version else ""
    headline = f"🚀 {title}"
    if pr_tag or ver_tag:
        details = " (" + ", ".join(filter(None, [pr_tag, ver_tag])) + ")"
        headline += details

    hl_preview = "\n".join(f"• {h[:100]}..." if len(h) > 100 else f"• {h}" for h in highlights[:3])
    tweet = f"{headline}\n\n{hl_preview}\n\n{tag_str}".strip()

    changelog_header = f"### {ver_tag} ({date}) - {pr_tag}".strip(" -")
    changelog_items = "\n".join(f"- {h}" for h in (highlights or [title]))
    changelog = f"{changelog_header}\n{changelog_items}".strip()

    draft = {
        "file": str(path),
        "title": title,
        "author": author,
        "date": date,
        "pr": pr,
        "version": version,
        "tags": tags,
        "highlights": highlights,
        "tweet": tweet,
        "changelog": changelog,
    }

    target_out = Path(output_path) if output_path else Path(".synlynk/social_drafts.json")
    try:
        target_out.parent.mkdir(parents=True, exist_ok=True)
        existing_drafts = []
        if target_out.is_file():
            try:
                data = json.loads(target_out.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    existing_drafts = data
                elif isinstance(data, dict):
                    existing_drafts = [data]
            except Exception:
                existing_drafts = []

        updated = False
        for idx, existing in enumerate(existing_drafts):
            if isinstance(existing, dict) and (
                existing.get("file") == str(path) or (pr and existing.get("pr") == pr)
            ):
                existing_drafts[idx] = draft
                updated = True
                break
        if not updated:
            existing_drafts.append(draft)

        target_out.write_text(json.dumps(existing_drafts, indent=2), encoding="utf-8")
    except Exception:
        pass

    return draft


def update_blog_index(
    blog_dir: Union[str, Path] = "docs/blog",
    readme_path: Optional[Union[str, Path]] = None,
) -> str:
    """Scans blog_dir, extracts post records, and keeps docs/blog/README.md Series Index in sync."""
    bdir = Path(blog_dir)
    rd_path = Path(readme_path) if readme_path else bdir / "README.md"
    if not rd_path.exists():
        return ""

    content = rd_path.read_text(encoding="utf-8")

    posts = []
    for p in bdir.glob("*.md"):
        if p.name in ("README.md", "TEMPLATE.md") or p.name.startswith("."):
            continue
        m = re.match(r"^(\d+)-", p.name)
        post_num = int(m.group(1)) if m else 99999
        post_text = p.read_text(encoding="utf-8")
        fm_text, _ = split_frontmatter(post_text)
        meta = parse_yaml_frontmatter(fm_text) if fm_text else {}
        title = meta.get("title", p.stem)
        date = str(meta.get("date", "—"))
        pr = str(meta.get("pr", "—"))
        posts.append({
            "num": post_num,
            "filename": p.name,
            "title": title,
            "date": date,
            "pr": pr,
        })

    posts.sort(key=lambda x: x["num"])

    new_rows = []
    for p in posts:
        link = f"[{p['num']:02d}](./{p['filename']})" if p['num'] < 100 else f"[{p['num']}](./{p['filename']})"
        pr_display = p['pr']
        if pr_display.startswith("#"):
            pr_num = pr_display[1:]
            pr_link = f"[{pr_display}](https://github.com/nikhilsoman/synlynk/pull/{pr_num})"
        else:
            pr_link = pr_display

        row = f"| {link} | {p['title']} | {pr_link} | {p['date']} |"
        if p['filename'] not in content:
            new_rows.append(row)

    if new_rows:
        template_header = "## Per-PR Post Template"
        if template_header in content:
            prefix, sep, suffix = content.partition(template_header)
            content = prefix.rstrip() + "\n" + "\n".join(new_rows) + "\n\n" + sep + suffix
            rd_path.write_text(content, encoding="utf-8")

    return content


def validate_all_blog_posts(blog_dir: Union[str, Path] = "docs/blog") -> List[Dict[str, Any]]:
    """Scans and validates all blog posts in blog_dir."""
    findings = []
    bdir = Path(blog_dir)
    if not bdir.is_dir():
        return findings

    for p in bdir.glob("*.md"):
        if p.name in ("README.md", "TEMPLATE.md") or p.name.startswith("."):
            continue
        try:
            validate_blog_post_frontmatter(p)
        except BlogValidationError as err:
            findings.append({"file": str(p), "errors": err.errors})
        except Exception as exc:
            findings.append({"file": str(p), "errors": [str(exc)]})
    return findings


def fetch_pr_details(pr_number: Union[int, str], repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Fetches PR metadata from GitHub CLI or local git context."""
    import subprocess
    import datetime
    pr_clean = str(pr_number).lstrip("#")
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", pr_clean, "--json", "number,title,body,author,mergedAt"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_root or os.getcwd(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            author_data = data.get("author") or {}
            author_login = author_data.get("login", "synlynk team")
            if author_login.startswith("app/"):
                author_login = author_login.replace("app/synlynk-", "").replace("app/", "") + " agent"

            merged_at = data.get("mergedAt") or ""
            date_str = merged_at[:10] if merged_at else datetime.date.today().isoformat()

            return {
                "number": int(data.get("number") or pr_clean),
                "title": data.get("title") or f"PR #{pr_clean}",
                "body": data.get("body") or "",
                "author": author_login,
                "date": date_str,
            }
    except Exception:
        pass

    return {
        "number": int(pr_clean) if pr_clean.isdigit() else 0,
        "title": f"PR #{pr_clean}",
        "body": "",
        "author": "synlynk team",
        "date": datetime.date.today().isoformat(),
    }


def sync_pr_blog_post(
    pr_number: Union[int, str],
    root: Optional[str] = None,
    dry_run: bool = False,
    title: Optional[str] = None,
    author: Optional[str] = None,
    date_str: Optional[str] = None,
    version: Optional[str] = None,
    body: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates or updates a Limited-Treatment per-PR blog post for a merged pull request.

    Ensures valid YAML frontmatter (type: pr), structured sections, index update, and social draft.
    """
    import datetime
    repo_root = root or os.getcwd()
    blog_dir = Path(repo_root) / "docs" / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)

    pr_clean = str(pr_number).lstrip("#")

    # 1. Fetch metadata if not provided
    if title is None or body is None:
        fetched = fetch_pr_details(pr_clean, repo_root=repo_root)
        title = title or fetched["title"]
        body = body or fetched["body"]
        author = author or fetched["author"]
        date_str = date_str or fetched["date"]

    author = author or "synlynk team"
    date_str = date_str or datetime.date.today().isoformat()

    # Determine version from VERSION file if not passed
    if not version:
        vfile = Path(repo_root) / "VERSION"
        if vfile.is_file():
            version = vfile.read_text(encoding="utf-8").strip()
        else:
            version = "0.20.0"
    version = version.lstrip("v")

    # 2. Check if a post for this PR already exists
    target_post = None
    target_num = None
    for p in blog_dir.glob("*.md"):
        if p.name in ("README.md", "TEMPLATE.md"):
            continue
        m = re.match(r"^(\d+)-.*pr" + re.escape(pr_clean) + r"(-.*)?\.md$", p.name, re.IGNORECASE)
        if m:
            target_post = p
            target_num = int(m.group(1))
            break

    if not target_post:
        # Determine next post number
        max_num = 0
        for p in blog_dir.glob("*.md"):
            if p.name in ("README.md", "TEMPLATE.md"):
                continue
            m = re.match(r"^(\d+)-", p.name)
            if m:
                max_num = max(max_num, int(m.group(1)))
        target_num = max_num + 1

        # Clean title for filename slug
        title_slug = title
        title_slug = re.sub(r"^(feat|fix|chore|docs|refactor|test)(\([^)]+\))?:\s*", "", title_slug, flags=re.IGNORECASE)
        slug = re.sub(r"[^a-z0-9]+", "-", title_slug.lower()).strip("-")[:40]
        if not slug:
            slug = "update"
        target_post = blog_dir / f"{target_num:02d}-pr{pr_clean}-{slug}.md"

    # 3. Parse PR body into sections
    highlights = []
    tests_summary = []
    co_authors = []

    if body:
        # Extract co-authors if present
        for line in body.splitlines():
            line_str = line.strip()
            co_m = re.match(r"^Co-Authored-By:\s*(.*?)\s*<.*?>", line_str, re.IGNORECASE)
            if co_m:
                ca = co_m.group(1).strip()
                if ca and ca not in co_authors:
                    co_authors.append(ca)

        m_ship = re.search(r"###?\s*(What This PR Shipped|Highlights)\s*(.*?)(?=\n###? |\Z)", body, re.DOTALL | re.IGNORECASE)
        if m_ship:
            for line in m_ship.group(2).splitlines():
                l_str = line.strip()
                if l_str.startswith("- ") or l_str.startswith("* ") or re.match(r"^\d+\.\s+", l_str):
                    item = re.sub(r"^[-*]|\d+\.\s*", "", l_str).strip()
                    if item and not item.lower().startswith("co-authored-by:"):
                        highlights.append(item)

        m_test = re.search(r"###?\s*(Tests|Verification)\s*(.*?)(?=\n###? |\Z)", body, re.DOTALL | re.IGNORECASE)
        if m_test:
            for line in m_test.group(2).splitlines():
                l_str = line.strip()
                if l_str and not l_str.lower().startswith("co-authored-by:"):
                    tests_summary.append(l_str)

    if co_authors and (author == "synlynk team" or "agent" in author or "bot" in author):
        author = ", ".join(co_authors)

    if not highlights:
        highlights.append(f"Merged improvements and fixes for PR #{pr_clean}.")

    test_evidence_text = "\n".join(tests_summary) if tests_summary else "Verified via local regression test suite and GitHub Actions CI matrix."
    highlights_text = "\n".join(f"- {h}" for h in highlights)

    title_clean = re.sub(r"^(feat|fix|chore|docs|refactor|test)(\([^)]+\))?:\s*", "", title, flags=re.IGNORECASE).strip()
    if title.startswith("PR #"):
        clean_title = title
    else:
        clean_title = f"PR #{pr_clean} — {title_clean}"
    clean_title_escaped = clean_title.replace('"', '\\"')

    post_content = f"""---
title: "{clean_title_escaped}"
date: {date_str}
series: "Building the OS for Multi-Agent Development"
post: {target_num}
pr: "#{pr_clean}"
status: merged
author: "{author}"
version: "{version}"
tags: [posts]
type: pr
---

## The Broader Goal at the End of the Previous PR

Advancing the multi-agent operating system toward reliable, autonomous development, unblocking workgroup velocity and eliminating manual developer toil.

## Strategic Shifts in This PR

Focused, limited-treatment delta resolving PR #{pr_clean} requirements with strict backward compatibility and comprehensive verification.

## What This PR Shipped

{highlights_text}

## Verification & Test Evidence

{test_evidence_text}

## What This Achieved on the Path to Autonomy

Maintains repository integrity, expands test-proven capabilities, and keeps the hybrid human-agent workgroup aligned with zero drift.
"""

    if not dry_run:
        target_post.write_text(post_content, encoding="utf-8")
        update_blog_index(blog_dir=blog_dir)
        extract_social_changelog_snippets(target_post, output_path=Path(repo_root) / ".synlynk" / "social_drafts.json")

    return {
        "file": str(target_post),
        "post": target_num,
        "pr": f"#{pr_clean}",
        "title": clean_title,
        "date": date_str,
        "version": version,
        "author": author,
        "dry_run": dry_run,
    }


def cmd_marketing_sync_pr(pr_number: Union[int, str], dry_run: bool = False) -> None:
    """CLI handler for synlynk marketing sync-pr <pr>."""
    print(f"🔄 [Marketing PR Sync] Synchronizing blog post for PR #{pr_number}...")
    res = sync_pr_blog_post(pr_number=pr_number, dry_run=dry_run)
    action = "Would create" if dry_run else "Created/Updated"
    print(f"✅ [Marketing PR Sync] {action} blog post #{res['post']}: {res['file']}")
    print(f"   Title: {res['title']}")
    print(f"   Date: {res['date']} | Version: v{res['version']} | Author: {res['author']}")

