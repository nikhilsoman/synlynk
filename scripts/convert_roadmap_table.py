#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def _strip_markdown_formatting(text: str) -> str:
    return re.sub(r"(\*\*|~~)", "", text).strip()


def _parse_roadmap_version_arc_table(content: str) -> list[dict]:
    rows: list[dict] = []
    in_version_arc = False

    for raw_line in content.splitlines():
        line = raw_line.strip()

        if line == "## Version Arc":
            in_version_arc = True
            continue
        if in_version_arc and line.startswith("## "):
            break
        if not in_version_arc or not line.startswith("|"):
            continue

        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        if cells[0].lower() == "version" or set(cells[0]) <= {":", "-", " "}:
            continue

        version = _strip_markdown_formatting(cells[0])
        title = _strip_markdown_formatting(cells[1])
        notes = cells[2]
        status_cell = cells[3]
        target_date = cells[4]

        if "✅" in status_cell:
            status = "shipped"
        elif "🚧" in status_cell:
            status = "in_progress"
        elif "📦" in status_cell or "📋" in status_cell:
            status = "planned"
        else:
            status = "planned"

        rows.append(
            {
                "version": version,
                "title": title,
                "status": status,
                "target_date": target_date,
                "notes": notes,
            }
        )

    return rows


def _read_roadmap(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    roadmap_path = Path.cwd() / "project-docs" / "roadmap.md"
    content = _read_roadmap(roadmap_path)
    rows = _parse_roadmap_version_arc_table(content)

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from synlynk.db import cmd_roadmap_add

    for row in rows:
        target_date = row["target_date"] if row["target_date"] != "—" else None
        cmd_roadmap_add(
            version=row["version"],
            title=row["title"],
            status=row["status"],
            target_date=target_date,
            notes=row["notes"],
        )
        print(f"inserted arc {row['version']}: {row['title']} [{row['status']}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
