"""synlynk context: context.md generation from state.db and flat-file sources."""

import json
import os
import re
import sys
import time
from typing import Optional

from synlynk.team import get_mode, get_username


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _get_last_devlog_date(filepath: str) -> Optional[str]:
    """Returns the most recent ## YYYY-MM-DD heading from a devlog file."""
    if not os.path.exists(filepath):
        return None
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    last_date = None
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                last_date = m.group(1)
    return last_date

def _write_recent_devlog_entries(out, filepath: str, cutoff: float) -> None:
    """Writes devlog ## sections newer than cutoff timestamp to out."""
    import calendar
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    current_lines = []
    in_section = False
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if in_section and current_lines:
                    out.writelines(current_lines)
                try:
                    ts = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d"))
                    in_section = ts >= cutoff
                except ValueError:
                    in_section = False
                current_lines = [line]
            elif in_section:
                current_lines.append(line)
    if in_section and current_lines:
        out.writelines(current_lines)

def _write_last_devlog_section(out, filepath: str) -> None:
    """Writes only the last ## section from a devlog file."""
    if not os.path.exists(filepath):
        return
    pattern = re.compile(r'^## \d{4}-\d{2}-\d{2}')
    sections = []
    current = []
    with open(filepath) as f:
        for line in f:
            if pattern.match(line) and current:
                sections.append(current)
                current = [line]
            else:
                current.append(line)
    if current:
        sections.append(current)
    if sections:
        out.writelines(sections[-1])

def _generate_task_context(story_id: str, out_path: str = None) -> str:
    """Writes minimal scoped context for a single story dispatch. Returns context string.

    out_path: write to this path instead of the global .synlynk/context.md.
    Used by dispatch_agent to isolate per-job context and avoid concurrent overwrites.
    """
    import io as _io
    buf = _io.StringIO()

    conn = _pkg("_get_db")()
    row = conn.execute(
        "SELECT title, engg_domain, org_domain, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    conn.close()

    buf.write("# synlynk Context Snapshot (task-scoped)\n\n")
    buf.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    if row:
        buf.write("## Story\n")
        buf.write(f"**ID:** {story_id}  \n")
        buf.write(f"**Title:** {row[0] or ''}  \n")
        buf.write(
            f"**Domain:** {row[1] or 'unknown'} · "
            f"{row[2] or 'unknown'} · {row[3] or 'build'}  \n\n---\n\n"
        )

    # Active tasks only (not deferred, not done)
    todo_path = os.path.join("project-docs", "todo.md")
    if os.path.exists(todo_path):
        active = [l for l in open(todo_path) if "- [ ]" in l]
        if active:
            buf.write("## Active Tasks\n")
            buf.writelines(active)
            buf.write("\n---\n\n")

    # Source architecture (relevant files only, up to 20 entries)
    source_skeleton = _pkg("_check_scan_cache")()
    if source_skeleton:
        engg = row[1] if row and row[1] != "unknown" else None
        if engg:
            relevant = [
                f for f in source_skeleton
                if engg in f.get("file", "")
                or engg in " ".join(f.get("symbols", []))
            ]
            if not relevant:
                relevant = source_skeleton
        else:
            relevant = source_skeleton
        meta = _pkg("_load_scan_meta")()
        current_sha = _pkg("_git_head_sha")() or ""
        cache_hit = bool(meta and meta.get("head_sha") == current_sha)
        arch = _pkg("_format_source_architecture")(relevant[:20], current_sha, cache_hit, len(relevant))
        if arch:
            buf.write(arch)

    context_text = buf.getvalue()

    context_file = out_path if out_path else ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)
    with open(context_file, "w") as out:
        out.write(context_text)

    print(f"  ✓ Task-scoped context saved to {context_file}")
    return context_text

def _generate_context_from_db(out_path: str = None) -> str:
    """Build context.md from state.db (post-migration path)."""
    context_file = out_path if out_path else ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)
    username = get_username()
    mode = get_mode()
    conn = _pkg("_get_db")()
    top_story = conn.execute(
        "SELECT title FROM stories WHERE status='open' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    active_goal = conn.execute(
        "SELECT goal_id, outcome, criterion, deadline FROM goals "
        "WHERE status='active' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    recent_devlogs = conn.execute(
        "SELECT author, entry_date, session_title, body FROM devlog_entries "
        "ORDER BY entry_date DESC, id DESC LIMIT 5"
    ).fetchall()
    memory_sections = conn.execute(
        "SELECT section, body FROM memory_entries ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    with open(context_file, "w") as out:
        out.write("# synlynk Context Snapshot\n\n")
        out.write(
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"| User: @{username} | Mode: {mode}\n\n"
        )
        if active_goal:
            goal_id, outcome, criterion, deadline = active_goal
            deadline_s = deadline or "ongoing"
            out.write("## Active Goal\n")
            out.write(f"- [{goal_id}] {outcome}\n")
            out.write(f"  Success criterion: {criterion}  ·  Deadline: {deadline_s}\n\n---\n\n")
        if top_story:
            out.write("## Next Task\n")
            out.write(f"- {top_story[0]}\n\n---\n\n")
        if recent_devlogs:
            out.write("## Recent Activity\n")
            for author, entry_date, session_title, body in recent_devlogs:
                title_part = f" — {session_title}" if session_title else ""
                out.write(f"\n### @{author} · {entry_date}{title_part}\n")
                out.write(body[:500])
                if len(body) > 500:
                    out.write("\n...(truncated)")
                out.write("\n")
            out.write("\n---\n\n")
        if memory_sections:
            out.write("## Project Memory\n")
            for section, body in memory_sections:
                out.write(f"\n### {section}\n{body[:300]}\n")
    _append_vizor_notes(context_file)
    with open(context_file) as f:
        return f.read()

def _append_vizor_notes(context_file: str) -> None:
    viz_notes_path = ".synlynk/viz-notes.json"
    if os.path.exists(viz_notes_path):
        with open(viz_notes_path) as f:
            viz_notes = json.load(f)
        if not isinstance(viz_notes, dict):
            return
        action_notes = {
            k: v
            for k, v in viz_notes.items()
            if v.get("tags") or v.get("state") in ("action", "urgent")
        }
        if viz_notes:
            with open(context_file, "a") as f:
                f.write("\n\n## Vizor Notes\n")
                for element_id, note in viz_notes.items():
                    f.write(f"\n- [{element_id}] ({note.get('state','info')}): {note.get('text','')}")
                    if note.get("tags"):
                        f.write(f" [tags: {', '.join(note['tags'])}]")
        if action_notes:
            with open(context_file, "a") as f:
                f.write("\n\n## Pending actions from Vizor\n")
                for element_id, note in action_notes.items():
                    for tag in note.get("tags", []):
                        if tag == "redo":
                            f.write(f"\n- ↺ Redo: {element_id} — {note.get('text','')}")
                        elif tag == "reassign":
                            f.write(f"\n- ⇄ Reassign agent for: {element_id} — {note.get('text','')}")
                        elif tag == "defer":
                            f.write(f"\n- ⏸ Defer: {element_id} — {note.get('text','')}")

def generate_context(scope: str = "full", out_path: str = None) -> str:
    """Aggregates project-docs into .synlynk/context.md (active items only).

    Returns the context string. The file is still written for daemon HTTP
    endpoint and external tooling compatibility.

    out_path: when set, write to this path instead of .synlynk/context.md.
    Passed through to _generate_task_context for per-job isolation in dispatch.
    """
    if _pkg("_is_migrated")():
        return _generate_context_from_db(out_path=out_path)

    docs_dir = _pkg("_docs_dir")()
    context_file = out_path if out_path else ".synlynk/context.md"
    sentinel_file = ".synlynk/sentinel.md"

    if not os.path.exists(docs_dir):
        return ""

    if scope != "full":
        if scope.startswith("task:"):
            return _generate_task_context(scope[5:], out_path=out_path)
        print(f"  ⚠ scope='{scope}' not yet implemented, falling back to full context")
        scope = "full"

    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)

    username = get_username()
    mode = get_mode()

    with open(context_file, "w") as out:
        out.write("# synlynk Context Snapshot\n\n")
        out.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} | User: @{username} | Mode: {mode}\n\n")

        # Sentinel alerts at top (omit section if empty)
        if os.path.exists(sentinel_file):
            content = open(sentinel_file).read().strip()
            lines = [l for l in content.splitlines() if l.startswith("- [")]
            if lines:
                out.write("# Sentinel Alerts\n")
                out.write("\n".join(lines) + "\n\n---\n\n")

        # Active + deferred tasks; superseded/absorbed/done excluded
        todo_path = os.path.join(docs_dir, "todo.md")
        if os.path.exists(todo_path):
            active, deferred = [], []
            with open(todo_path) as f:
                for line in f:
                    if "- [ ]" in line:
                        active.append(line)
                    elif "- [-]" in line:
                        deferred.append(line)
            if active or deferred:
                out.write("## Active Tasks\n")
                out.writelines(active)
                if deferred:
                    out.write("\n### Deferred\n")
                    out.writelines(deferred)
                out.write("\n---\n\n")

        # Source architecture (passive cache — re-scans if HEAD changed)
        source_skeleton = _pkg("_check_scan_cache")()
        if source_skeleton:
            meta = _pkg("_load_scan_meta")()
            current_sha = _pkg("_git_head_sha")() or ""
            cache_hit = bool(meta and meta.get("head_sha") == current_sha)
            total_files = 0
            if meta and meta.get("deep"):
                total_files = meta["deep"].get("total_files", 0)
            arch_section = _pkg("_format_source_architecture")(
                source_skeleton, current_sha or "unknown", cache_hit, total_files
            )
            if arch_section:
                out.write(arch_section)

        # Roadmap: header rows + In Progress rows only
        roadmap_path = os.path.join(docs_dir, "roadmap.md")
        if os.path.exists(roadmap_path):
            out.write("## Roadmap (active)\n")
            with open(roadmap_path) as f:
                for line in f:
                    if (line.startswith("| Priority") or "| :---" in line or
                            "In Progress" in line):
                        out.write(line)
            out.write("\n---\n\n")

        # Memory (decisions) — full, it's already curated
        memory_path = os.path.join(docs_dir, "memory.md")
        if os.path.exists(memory_path):
            out.write("## Decisions\n")
            out.write(open(memory_path).read())
            out.write("\n---\n\n")

        # Recent devlog (last 7 days)
        cutoff = time.time() - (7 * 24 * 3600)
        devlog_path = os.path.join(docs_dir, "devlogs", f"{username}.md")
        if os.path.exists(devlog_path):
            out.write(f"## Recent Devlog (@{username})\n")
            _write_recent_devlog_entries(out, devlog_path, cutoff)
            out.write("\n---\n\n")

        # Teammates (team mode): last 1 entry per teammate devlog
        if mode == "team":
            devlogs_dir = os.path.join(docs_dir, "devlogs")
            if os.path.exists(devlogs_dir):
                for fname in sorted(os.listdir(devlogs_dir)):
                    if (fname.endswith(".md") and
                            fname not in (f"{username}.md", "README.md")):
                        out.write(f"## Teammate Activity (@{fname[:-3]})\n")
                        _write_last_devlog_section(out, os.path.join(devlogs_dir, fname))
                        out.write("\n---\n\n")

    print(f"  ✓ Context saved to {context_file}")
    try:
        size_kb = os.path.getsize(".synlynk/context.md") / 1024
        if size_kb > 64:
            print(f"  ⚠ Context is very large ({size_kb:.0f} KB) — strongly consider "
                  "archiving completed todos and old devlog entries to reduce token cost.")
        elif size_kb > 32:
            print(f"  ⚠ Context is large ({size_kb:.0f} KB) — consider archiving "
                  "completed todos and old devlog entries.")
    except OSError:
        pass
    _append_vizor_notes(context_file)
    try:
        return open(context_file).read()
    except OSError:
        return ""

def _relevant_files_for_story(story_id: str) -> list:
    """Returns up to 10 source file paths relevant to the story's engg_domain."""
    if not story_id:
        return []
    conn = _pkg("_get_db")()
    row = conn.execute(
        "SELECT engg_domain FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    if not row or row[0] == "unknown":
        return []
    engg = row[0]
    # Try to load cached scan meta first (faster, avoids git operations)
    meta = _pkg("_load_scan_meta")()
    skeleton = meta.get("skeleton", []) if meta else None
    # If no cached meta, try to check scan cache (may re-scan if HEAD changed)
    if skeleton is None:
        try:
            skeleton = _pkg("_check_scan_cache")()
        except Exception:
            skeleton = []
    if not skeleton:
        return []
    relevant = []
    for entry in skeleton:
        path = entry.get("file", "")
        symbols_str = " ".join(entry.get("symbols") or [])
        if engg in path or engg in symbols_str:
            relevant.append(path)
    return relevant[:10]

def _verify_contract_for_story(story_id: str, task: str) -> str:
    """Returns a ## How to Verify section with a pytest invocation. Empty string if no tests/ dir."""
    if not os.path.exists("tests"):
        return ""

    conn = _pkg("_get_db")()
    row = conn.execute(
        "SELECT title FROM stories WHERE story_id=?", (story_id,)
    ).fetchone() if story_id else None
    conn.close()
    title = (row[0] if row else "") or task

    # Derive test pattern: lowercase, alphanumeric + underscores, max 40 chars
    pattern = re.sub(r"[^a-z0-9_]", "", title.lower().replace(" ", "_"))[:40]
    if not pattern:
        return ""

    # Find first test file
    test_file = None
    for root, _dirs, files in os.walk("tests"):
        for f in sorted(files):
            if f.startswith("test_") and f.endswith(".py"):
                test_file = os.path.join(root, f)
                break
        if test_file:
            break

    if not test_file:
        return ""

    cmd = f"pytest {test_file} -k '{pattern}' -v" if pattern else f"pytest {test_file} -v"
    return (
        "\n\n## How to Verify\n"
        f"Run: `{cmd}`\n"
        "Expected: all matched tests pass, no new failures.\n"
    )
