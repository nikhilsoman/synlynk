"""Read-only source slices served by the Vizor source API."""
import os
from pathlib import Path
from typing import Optional
def _get_source_slice(
    repo_root: str,
    file_rel_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> dict:
    """Safely fetch and slice source code lines from workspace with path traversal protection."""
    try:
        norm_root = os.path.abspath(repo_root)
        target_abs = os.path.abspath(os.path.join(norm_root, file_rel_path.lstrip("/")))

        # Path traversal guard
        if not (target_abs == norm_root or target_abs.startswith(norm_root + os.sep)):
            return {"status": "error", "error": "Path traversal rejected", "code": 403}

        if not os.path.isfile(target_abs):
            return {"status": "error", "error": f"File not found: {file_rel_path}", "code": 404}

        content = Path(target_abs).read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)

        s = max(1, start_line) if start_line is not None else 1
        e = min(total_lines, end_line) if end_line is not None else total_lines

        if s > total_lines or s > e:
            sliced = ""
        else:
            sliced = "\n".join(lines[s - 1:e])

        ext = os.path.splitext(file_rel_path)[1].lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".sh": "bash",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        lang = lang_map.get(ext, "text")

        return {
            "status": "ok",
            "file": file_rel_path,
            "start_line": s,
            "end_line": e,
            "total_lines": total_lines,
            "content": sliced,
            "language": lang,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "code": 500}

