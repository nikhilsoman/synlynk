import json
import pytest
from pathlib import Path

from synlynk.marketing import (
    REQUIRED_BLOG_FRONTMATTER_KEYS,
    BlogValidationError,
    extract_social_changelog_snippets,
    parse_yaml_frontmatter,
    split_frontmatter,
    update_blog_index,
    validate_all_blog_posts,
    validate_blog_post_frontmatter,
)


def test_split_frontmatter():
    content = "---\ntitle: Test\nauthor: Agy\n---\n\n# Body Content\n"
    fm, body = split_frontmatter(content)
    assert fm == "title: Test\nauthor: Agy"
    assert "# Body Content" in body

    no_fm = "# Just body\n"
    fm, body = split_frontmatter(no_fm)
    assert fm is None
    assert body == no_fm


def test_parse_yaml_frontmatter():
    fm_text = """title: "PR #1347 — Growth Engine"
author: Agy (Gemini)
date: 2026-09-02
pr: "#1347"
version: 0.19.0
tags: [growth, marketing, living-docs]
extra_list:
  - item1
  - item2
"""
    data = parse_yaml_frontmatter(fm_text)
    assert data["title"] == "PR #1347 — Growth Engine"
    assert data["author"] == "Agy (Gemini)"
    assert data["date"] == "2026-09-02"
    assert data["pr"] == "#1347"
    assert data["version"] == "0.19.0"
    assert data["tags"] == ["growth", "marketing", "living-docs"]
    assert data["extra_list"] == ["item1", "item2"]


def test_validate_blog_post_frontmatter_valid(tmp_path):
    post_file = tmp_path / "164-pr1347-test.md"
    post_file.write_text("""---
title: "PR #1347 — Autonomous Growth Engine"
author: "Agy (Gemini)"
date: "2026-09-02"
pr: "#1347"
version: "0.19.0"
tags: ["growth", "marketing"]
---

## What This PR Shipped
- Added automated YAML validation.
- Added SVG media generator.
""", encoding="utf-8")

    meta = validate_blog_post_frontmatter(post_file)
    assert meta["title"] == "PR #1347 — Autonomous Growth Engine"
    assert meta["author"] == "Agy (Gemini)"
    assert meta["pr"] == "#1347"
    assert meta["version"] == "0.19.0"
    assert meta["tags"] == ["growth", "marketing"]


def test_validate_blog_post_frontmatter_missing_keys(tmp_path):
    post_file = tmp_path / "bad-post.md"
    post_file.write_text("""---
title: "Incomplete Post"
date: "2026-09-02"
---
Body text
""", encoding="utf-8")

    with pytest.raises(BlogValidationError) as excinfo:
        validate_blog_post_frontmatter(post_file)

    msg = str(excinfo.value)
    assert "author" in msg
    assert "pr" in msg
    assert "version" in msg
    assert "tags" in msg


def test_validate_blog_post_frontmatter_invalid_tags(tmp_path):
    post_file = tmp_path / "bad-tags.md"
    post_file.write_text("""---
title: "Bad Tags Post"
author: "Agy"
date: "2026-09-02"
pr: "#1347"
version: "0.19.0"
tags: []
---
Body text
""", encoding="utf-8")
    with pytest.raises(BlogValidationError):
        validate_blog_post_frontmatter(post_file)


def test_extract_social_changelog_snippets(tmp_path):
    post_file = tmp_path / "164-pr1347-autonomous-growth-engine.md"
    post_file.write_text("""---
title: "PR #1347 — Autonomous Growth & Marketing Engine"
author: "Agy (Gemini)"
date: "2026-09-02"
pr: "#1347"
version: "0.19.0"
tags: ["growth", "marketing"]
---

## What This PR Shipped
- Implemented YAML frontmatter validation for blog posts.
- Integrated automated command docs sync.
- Added SVG and OG card media generator.
""", encoding="utf-8")

    draft_out = tmp_path / ".synlynk" / "social_drafts.json"
    draft = extract_social_changelog_snippets(post_file, output_path=draft_out)

    assert draft["title"] == "PR #1347 — Autonomous Growth & Marketing Engine"
    assert draft["pr"] == "#1347"
    assert draft["version"] == "0.19.0"
    assert len(draft["highlights"]) == 3
    assert "#growth" in draft["tweet"]
    assert "### v0.19.0 (2026-09-02) - PR #1347" in draft["changelog"]

    assert draft_out.exists()
    saved = json.loads(draft_out.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["title"] == draft["title"]


def test_update_blog_index(tmp_path):
    blog_dir = tmp_path / "docs" / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    readme = blog_dir / "README.md"
    readme.write_text("""# Blog Series

## Series Index

| Post | Title | PR | Date |
|---|---|---|---|
| [01](./01-first-post.md) | First Post | [#1](https://github.com/nikhilsoman/synlynk/pull/1) | 2026-06-09 |

## Per-PR Post Template
""", encoding="utf-8")

    (blog_dir / "01-first-post.md").write_text("""---
title: First Post
author: Agy
date: 2026-06-09
pr: "#1"
version: 0.1.0
tags: [init]
---
Body
""", encoding="utf-8")

    (blog_dir / "164-pr1347-growth.md").write_text("""---
title: "PR #1347 — Autonomous Growth Engine"
author: "Agy (Gemini)"
date: "2026-09-02"
pr: "#1347"
version: "0.19.0"
tags: [growth]
---
Body
""", encoding="utf-8")

    updated_content = update_blog_index(blog_dir=blog_dir, readme_path=readme)
    assert "164-pr1347-growth.md" in updated_content
    assert "PR #1347 — Autonomous Growth Engine" in updated_content
