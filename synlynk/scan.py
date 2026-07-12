"""synlynk scan: language-agnostic repo scanner, stack fingerprinting, source architecture generation."""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Optional

from synlynk.wizard import _run_scan_tui

def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)

def cmd_scan(deep: bool = False, status: bool = False,
             refresh: bool = False, add_path: str = None,
             remove_path: str = None, dry_run: bool = False,
             workspace_name: str = None, no_tui: bool = False) -> None:
    """synlynk scan — workspace environment scan + context generation.

    No flags: first-time workspace scan (discover topology, harnesses,
              agents, skills; write workspace config + context.md).
    --refresh: re-run scan on existing workspace.
    --add <path>: add a repo to the current workspace config.
    --remove <path>: remove a repo from the current workspace config.
    --dry-run: print what would change; write nothing.
    --deep: (original) full source-tree walk → state.db + source-map.md.
    --status: (original) show skeleton cache status.
    --no-tui: skip the interactive stage-card TUI and print a text summary.
    """
    import json as _json

    # ── Preserved: --status ───────────────────────────────────────────────
    if status:
        meta = _pkg("_load_scan_meta")()
        if not meta:
            print("Source scan status: not scanned yet — run `synlynk scan` to populate")
            return
        sha_short = meta.get("head_sha", "unknown")[:7]
        file_count = meta.get("file_count", 0)
        scanned_at = meta.get("scanned_at", "unknown")
        print("Source scan status:")
        print(f"  Skeleton:    {file_count} files · cached · HEAD {sha_short} · {scanned_at}")
        deep_meta = meta.get("deep")
        if deep_meta:
            tf = deep_meta.get("total_files", "?")
            ts = deep_meta.get("total_symbols", "?")
            da = deep_meta.get("scanned_at", "unknown")
            print(f"  source-map:  {tf} files · {ts} symbols · {da}")
        else:
            print("  source-map:  not generated — run `synlynk scan --deep`")
        return

    # ── Preserved: --deep ─────────────────────────────────────────────────
    if deep:
        print(f"  {_GREEN}▶{_RESET} Deep scanning source tree...")
        skeleton, total_files, total_syms = _pkg("_scan_full_repo")()
        sha_short = (_pkg("_git_head_sha")() or "unknown")[:7]
        print(f"  {_GREEN}✓{_RESET} Scanned {total_files} files · {total_syms} symbols · HEAD {sha_short}")
        print(f"  {_CYAN}→{_RESET} project-docs/source-map.md updated")
        return

    # ── --remove ──────────────────────────────────────────────────────────
    if remove_path:
        abs_remove = os.path.abspath(remove_path)
        ws_dir = _pkg("_workspace_config_dir")(workspace_name or "default")
        cfg_path = os.path.join(ws_dir, "config.json")
        if not os.path.exists(cfg_path):
            print(f"  ⚠ No workspace config found at {cfg_path}")
            return
        cfg = _json.loads(open(cfg_path).read())
        before = len(cfg.get("repos", []))
        cfg["repos"] = [r for r in cfg.get("repos", [])
                        if os.path.abspath(r["path"]) != abs_remove]
        after = len(cfg["repos"])
        if dry_run:
            print(f"  [dry-run] would remove {os.path.basename(abs_remove)} from workspace")
            return
        open(cfg_path, "w").write(_json.dumps(cfg, indent=2))
        print(f"  {_GREEN}✓{_RESET} Removed {before - after} repo(s) from workspace")
        return

    # ── --add ─────────────────────────────────────────────────────────────
    if add_path:
        abs_add = os.path.abspath(add_path)
        if not os.path.isdir(os.path.join(abs_add, ".git")):
            print(f"  ⚠ {abs_add} is not a git repository")
            return
        ws_dir = _pkg("_workspace_config_dir")(workspace_name or "default")
        cfg_path = os.path.join(ws_dir, "config.json")
        if not os.path.exists(cfg_path):
            print(f"  ⚠ No workspace config at {cfg_path} — run `synlynk scan` first")
            return
        cfg = _json.loads(open(cfg_path).read())
        existing_paths = {os.path.abspath(r["path"]) for r in cfg.get("repos", [])}
        if abs_add in existing_paths:
            print(f"  {_YELLOW}⚠{_RESET} {os.path.basename(abs_add)} already in workspace")
            return
        new_entry = {
            "path": abs_add,
            "name": os.path.basename(abs_add),
            "stack_labels": _pkg("fingerprint_stack")(abs_add),
        }
        if dry_run:
            print(f"  [dry-run] would add {new_entry['name']} "
                  f"({', '.join(new_entry['stack_labels'])}) to workspace")
            return
        cfg["repos"].append(new_entry)
        open(cfg_path, "w").write(_json.dumps(cfg, indent=2))
        print(f"  {_GREEN}✓{_RESET} Added {new_entry['name']} to workspace")
        return

    # ── Compatibility: non-git working tree keeps legacy source scan ─────
    in_git_repo = os.path.isdir(os.path.join(os.getcwd(), ".git"))
    if not in_git_repo and not refresh and not no_tui and not dry_run:
        head_sha = _pkg("_git_head_sha")()
        if head_sha is None:
            print("  ⚠ Not in a git repository — scan requires git")
            return
        skeleton = _pkg("_scan_source_skeleton")()
        _pkg("_save_scan_meta")(head_sha, skeleton)
        sha_short = head_sha[:7]
        print(f"  {_GREEN}✓{_RESET} Skeleton refreshed · {len(skeleton)} files · HEAD {sha_short}")
        return

    # ── Preserved: --refresh keeps the legacy workspace scan summary path ──
    if refresh:
        print(f"  {_CYAN}›{_RESET} scanning your environment...")
        scan = _pkg("run_workspace_scan")(workspace_name=workspace_name, dry_run=dry_run, deep=False)

        repo_names = ", ".join(r["name"] for r in scan["repos"])
        harness_names = ", ".join(h["name"] for h in scan["harnesses"]) or "none"
        stacks = sorted({lbl for r in scan["repos"] for lbl in r["stack_labels"]})
        print(f"  repos found: {len(scan['repos'])}  ·  "
              f"harnesses: {harness_names}  ·  "
              f"stacks: {', '.join(stacks) or 'unknown'}")

        if not dry_run:
            config_path = _pkg("write_workspace_config")(scan, scan["workspace_name"])
            _pkg("generate_structured_context")(scan)
            print(f"  {_GREEN}✓{_RESET} workspace: {scan['workspace_name']}")
            print(f"  {_GREEN}✓{_RESET} repos: {repo_names}")
            if scan["skills"]:
                skill_names = ", ".join(s["name"] for s in scan["skills"])
                print(f"  {_GREEN}✓{_RESET} skills: {skill_names}")
            print(f"\n  next: synlynk dispatch {scan['home_harness'] or 'claude'} "
                  f'"what\'s the current task?"')
        else:
            print("  [dry-run] no files written")
        return

    # ── Default: deep workspace scan with optional TUI ───────────────────
    print(f"  {_CYAN}›{_RESET} scanning your environment...")
    primary_root = os.getcwd()
    workspace_label = workspace_name or os.path.basename(primary_root) or "workspace"

    if dry_run or no_tui or not sys.stdin.isatty() or not sys.stdout.isatty():
        scan = _pkg("run_workspace_scan")(workspace_name=workspace_name, dry_run=dry_run, deep=True)
        primary_root = scan["repos"][0]["path"] if scan.get("repos") else primary_root
        print(f"\n  {_BOLD}synlynk scan{_RESET}  workspace: {scan['workspace_name']}\n")
        card_summary = _pkg("_card_summary")
        for key, label in zip(STAGE_KEYS, _STAGE_LABELS):
            data = scan.get(key)
            if data is None:
                print(f"  {_DIM}{label}: skipped{_RESET}")
            elif isinstance(data, dict) and data.get("error"):
                print(f"  {_RED}✗ {label}: {data['error']}{_RESET}")
            else:
                line1, _ = card_summary(key, data)
                print(f"  {_GREEN}✓{_RESET} {label}: {line1}")
        if not dry_run:
            updated = _pkg("_write_scan_fences")(scan, root=primary_root)
            for path in updated:
                print(f"  {_GREEN}✓{_RESET} {os.path.basename(path)} updated")
        else:
            print("  [dry-run] no files written")
        return

    results_live = {key: None for key in STAGE_KEYS}
    results_live["workspace_name"] = workspace_label
    threads = []
    for stage_fn in (
        _pkg("_scan_stage_stack"),
        _pkg("_scan_stage_source"),
        _pkg("_scan_stage_complexity"),
        _pkg("_scan_stage_tests"),
        _pkg("_scan_stage_git"),
        _pkg("_scan_stage_arch"),
    ):
        thread = threading.Thread(target=stage_fn, args=(primary_root, results_live), daemon=True)
        thread.start()
        threads.append(thread)

    _run_scan_tui(results_live, threads, primary_root=primary_root)

_BOLD = "\033[1m"

_GREEN = "\033[32m"

_YELLOW = "\033[33m"

_CYAN = "\033[36m"

_DIM = "\033[2m"

_RESET = "\033[0m"

_RED = "\033[31m"

_MAGENTA = "\033[35m"

def _static_scan(root: str = ".") -> dict:
    """Scans repo for project context: git log, README, file tree.

    Best-effort: repos without structured commits produce a lower-quality result.
    Returns dict with keys: project_name, description, commit_count,
    has_structured_commits, recent_topics, top_dirs, languages, readme_summary.
    """
    result = {
        "project_name": os.path.basename(os.path.abspath(root)),
        "description": "",
        "commit_count": 0,
        "has_structured_commits": False,
        "recent_topics": [],
        "top_dirs": [],
        "languages": [],
        "readme_summary": "",
    }

    # README extraction — project name from H1, summary from first paragraph.
    for readme in ("README.md", "README.rst", "README.txt", "README"):
        readme_path = os.path.join(root, readme)
        if os.path.exists(readme_path):
            try:
                text = open(readme_path).read(2000)
                lines = text.splitlines()
                for line in lines:
                    if line.startswith("# "):
                        result["project_name"] = line[2:].strip()
                        break
                # First non-heading, non-empty paragraph as description.
                para_lines = []
                in_para = False
                for line in lines[1:]:
                    if line.startswith("#"):
                        if in_para:
                            break
                        continue
                    if line.strip():
                        para_lines.append(line.strip())
                        in_para = True
                    elif in_para:
                        break
                result["description"] = " ".join(para_lines)[:300]
                result["readme_summary"] = text[:500]
            except IOError:
                pass
            break

    # Git log — commit count, structured commit detection, recent topics.
    try:
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-50", "--no-merges"],
            capture_output=True, text=True, cwd=root
        )
        if log_result.returncode == 0:
            messages = [l.split(" ", 1)[1] for l in log_result.stdout.strip().splitlines()
                        if " " in l]
            result["commit_count"] = int(subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, cwd=root
            ).stdout.strip() or "0")
            cc_prefixes = ("feat:", "fix:", "chore:", "docs:", "test:", "refactor:", "perf:")
            structured = sum(1 for m in messages if any(m.startswith(p) for p in cc_prefixes))
            result["has_structured_commits"] = structured >= max(1, len(messages) // 2)
            result["recent_topics"] = messages[:10]
    except (FileNotFoundError, ValueError):
        pass

    # File tree — top-level directories and language hints.
    try:
        entries = os.listdir(root)
        result["top_dirs"] = sorted([
            e for e in entries
            if os.path.isdir(os.path.join(root, e))
            and not e.startswith(".") and e not in ("node_modules", "__pycache__", "venv")
        ])
        lang_map = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
                    ".js": "JavaScript", ".go": "Go", ".rs": "Rust", ".rb": "Ruby"}
        langs = set()
        for e in entries:
            ext = os.path.splitext(e)[1]
            if ext in lang_map:
                langs.add(lang_map[ext])
        result["languages"] = sorted(langs)
    except OSError:
        pass

    return result

_INDUSTRY_KEYWORDS = {
    "ott": ["ott", "over-the-top", "streaming service", "video platform"],
    "streaming": ["streaming", "live stream", "media delivery"],
    "fintech": ["fintech", "financial", "payment", "trading", "investment"],
    "banking": ["banking", "bank", "loan", "mortgage", "deposit"],
    "securities": ["securities", "stock", "equity", "portfolio", "brokerage"],
    "healthcare": ["healthcare", "medical", "patient", "clinical", "health"],
    "ecommerce": ["ecommerce", "e-commerce", "shop", "cart", "marketplace"],
    "edtech": ["edtech", "education", "learning", "course", "student"],
    "gaming": ["gaming", "game", "player", "leaderboard", "matchmaking"],
}

def _infer_industry(root: str = ".") -> str:
    """Infers industry vertical from README content. Returns 'unknown' if no match."""
    for fname in ("README.md", "README.rst", "README.txt"):
        path = os.path.join(root, fname)
        if os.path.exists(path):
            try:
                text = open(path).read().lower()
                for industry, keywords in _INDUSTRY_KEYWORDS.items():
                    if any(kw in text for kw in keywords):
                        return industry
            except Exception:
                pass
    return "unknown"

_STACK_FINGERPRINTS = [
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("next.config.js", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("Pulumi.yaml", "Pulumi"),
    ("Pulumi.yml", "Pulumi"),
    ("Dockerfile", "Docker"),
    ("docker-compose.yml", "Docker"),
    ("docker-compose.yaml", "Docker"),
]

_STACK_EXT_MAP = {
    ".go": "Go",
    ".rs": "Rust",
}

def find_git_roots(search_dirs: list, max_depth: int = 2, exclude_names: set = None) -> list:
    """Return absolute paths of directories containing a .git entry.

    Search is breadth-first from each search directory and stops at max_depth.
    """
    exclude_names = set(exclude_names or {"node_modules", "__pycache__", ".venv", "venv"})
    found = []
    seen = set()
    queue = []

    for base in search_dirs or []:
        if not base:
            continue
        abs_base = os.path.abspath(os.path.expanduser(base))
        if os.path.isdir(abs_base):
            queue.append((abs_base, 0))

    while queue:
        current, depth = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        name = os.path.basename(current)
        if depth > 0 and (name.startswith(".") or name in exclude_names):
            continue

        if os.path.isdir(os.path.join(current, ".git")):
            if current not in found:
                found.append(current)

        if depth >= max_depth:
            continue

        try:
            entries = sorted(os.listdir(current))
        except OSError:
            continue

        for entry in entries:
            if entry.startswith(".") or entry in exclude_names:
                continue
            child = os.path.join(current, entry)
            if os.path.isdir(child):
                queue.append((child, depth + 1))

    return found

def fingerprint_stack(repo_path: str) -> list:
    """Return a deduplicated list of stack labels for a repository path."""
    labels = []
    seen = set()

    def _add(label: str) -> None:
        if label not in seen:
            seen.add(label)
            labels.append(label)

    if not repo_path or not os.path.isdir(repo_path):
        return labels

    for filename, label in _STACK_FINGERPRINTS:
        if os.path.exists(os.path.join(repo_path, filename)):
            _add(label)

    has_pkg = os.path.exists(os.path.join(repo_path, "package.json"))
    has_ts = any(
        os.path.exists(os.path.join(repo_path, candidate))
        for candidate in ("tsconfig.json", "tsconfig.base.json", "tsconfig.app.json")
    )
    if has_pkg and has_ts:
        _add("TypeScript")
    elif has_pkg:
        _add("JavaScript")

    if os.path.isdir(os.path.join(repo_path, ".github", "workflows")):
        _add("CI/CD")

    if os.path.isdir(os.path.join(repo_path, "migrations")):
        _add("SQL")
    else:
        try:
            if any(fname.endswith(".sql") for fname in os.listdir(repo_path)):
                _add("SQL")
        except OSError:
            pass

    try:
        for entry in os.listdir(repo_path):
            ext = os.path.splitext(entry)[1]
            if ext in _STACK_EXT_MAP:
                _add(_STACK_EXT_MAP[ext])
    except OSError:
        pass

    return labels

_KNOWN_SKILL_PATTERNS = [
    "~/.claude/plugins/cache/superpowers-marketplace/superpowers/*/",
    "~/.config/gstack/plugins/*/",
]

_SKILL_MANIFEST_NAMES = ("manifest.json", "package.json", "skill.json")

def scan_skills(extra_paths: list = None) -> list:
    """Discover installed skill packs from known plugin cache paths."""
    import glob as _glob
    import json as _json

    patterns = list(_KNOWN_SKILL_PATTERNS)
    if extra_paths:
        patterns.extend(extra_paths)

    found = []
    seen_paths = set()
    for pattern in patterns:
        for candidate in _glob.glob(os.path.expanduser(pattern)):
            if not os.path.isdir(candidate):
                continue
            abs_path = os.path.abspath(candidate)
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)

            name = os.path.basename(candidate)
            version = "unknown"
            for manifest_name in _SKILL_MANIFEST_NAMES:
                manifest_path = os.path.join(candidate, manifest_name)
                if not os.path.exists(manifest_path):
                    continue
                try:
                    with open(manifest_path) as f:
                        data = _json.load(f)
                    name = data.get("name") or name
                    version = data.get("version") or version
                    break
                except (OSError, ValueError, TypeError):
                    continue

            found.append({"name": name, "version": version, "path": abs_path})

    found.sort(key=lambda item: (item["name"], item["path"]))
    return found

def detect_home_harness(harnesses: list) -> "str | None":
    """Choose the preferred harness using env override, then claude, then first."""
    env_name = os.environ.get("SYNLYNK_HOME_HARNESS", "").strip().lower()
    normalized = [(h.get("name", ""), h) for h in harnesses or []]
    if env_name:
        for name, _entry in normalized:
            if name.lower() == env_name:
                return name

    for name, _entry in normalized:
        if name.lower() == "claude":
            return name

    return normalized[0][0] if normalized else None

def parse_context_sections(repo_path: str) -> dict:
    """Extract ## sections from agent context files in a repository."""
    sections = {}
    for fname in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        path = os.path.join(repo_path, fname)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                text = f.read(4000)
        except OSError:
            continue

        current_title = None
        current_lines = []
        for line in text.splitlines():
            if line.startswith("## "):
                if current_title and current_lines:
                    sections.setdefault(current_title, "\n".join(current_lines).strip())
                current_title = line[3:].strip()
                current_lines = []
                continue
            if current_title is not None:
                current_lines.append(line)

        if current_title and current_lines:
            sections.setdefault(current_title, "\n".join(current_lines).strip())

    return sections

_MONOREPO_MARKERS = ("packages", "apps", "services", "modules", "libs")

def _scan_stage_source(root: str, results: dict) -> None:
    """Stage 2: AST-parse Python files and collect per-file source metrics."""
    import ast as _ast

    skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}

    def _should_skip(dirpath: str) -> bool:
        parts = set(dirpath.split(os.sep))
        return bool(parts & skip_names)

    file_results = []
    if not os.path.isdir(root):
        results["source"] = file_results
        return

    for dirpath, _, filenames in os.walk(root):
        if _should_skip(dirpath):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fn)
            rel_path = os.path.relpath(filepath, root)
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except OSError:
                continue

            lines = content.count("\n") + 1
            try:
                tree = _ast.parse(content, filename=filepath)
            except SyntaxError:
                file_results.append({
                    "path": rel_path,
                    "lines": lines,
                    "functions": 0,
                    "classes": 0,
                    "typed_pct": 0,
                    "docstring_pct": 0,
                    "largest_fns": [],
                    "parse_error": True,
                })
                continue

            functions = [
                node for node in _ast.walk(tree)
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef))
            ]
            classes = [node for node in _ast.walk(tree) if isinstance(node, _ast.ClassDef)]
            public_functions = [node for node in functions if not node.name.startswith("_")]
            typed_functions = [
                node for node in functions
                if getattr(node, "returns", None)
                or any(arg.annotation for arg in getattr(node.args, "args", []))
                or getattr(node.args, "vararg", None) and node.args.vararg.annotation
                or getattr(node.args, "kwarg", None) and node.args.kwarg.annotation
                or any(arg.annotation for arg in getattr(node.args, "kwonlyargs", []))
            ]
            typed_pct = int((len(typed_functions) * 100) / len(functions)) if functions else 0
            docstring_pct = int((sum(1 for node in public_functions if _ast.get_docstring(node)) * 100) / len(public_functions)) if public_functions else 0

            fn_sizes = []
            for node in functions:
                end_lineno = getattr(node, "end_lineno", node.lineno)
                fn_sizes.append({
                    "name": node.name,
                    "lines": max(1, end_lineno - node.lineno + 1),
                    "lineno": node.lineno,
                })
            fn_sizes.sort(key=lambda item: item["lines"], reverse=True)

            file_results.append({
                "path": rel_path,
                "lines": lines,
                "functions": len(functions),
                "classes": len(classes),
                "typed_pct": typed_pct,
                "docstring_pct": docstring_pct,
                "largest_fns": fn_sizes[:3],
            })

    file_results.sort(key=lambda item: item["lines"], reverse=True)
    results["source"] = file_results

def _scan_stage_complexity(root: str, results: dict) -> None:
    """Stage 3: detect function/file hotspots and count TODO-style markers."""
    import ast as _ast

    skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}

    def _should_skip(dirpath: str) -> bool:
        parts = set(dirpath.split(os.sep))
        return bool(parts & skip_names)

    hotspots = []
    todo_counts = {"TODO": 0, "FIXME": 0, "HACK": 0, "XXX": 0}
    if not os.path.isdir(root):
        results["complexity"] = {"hotspots": hotspots, "todo_counts": todo_counts}
        return

    marker_pattern = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")

    for dirpath, _, filenames in os.walk(root):
        if _should_skip(dirpath):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fn)
            rel_path = os.path.relpath(filepath, root)
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except OSError:
                continue

            for marker in marker_pattern.findall(content):
                todo_counts[marker] += 1

            lines = content.count("\n") + 1
            if lines > 500:
                hotspots.append({
                    "path": rel_path,
                    "fn": None,
                    "lines": lines,
                    "lineno": 1,
                })

            try:
                tree = _ast.parse(content, filename=filepath)
            except SyntaxError:
                continue

            for node in _ast.walk(tree):
                if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    continue
                end_lineno = getattr(node, "end_lineno", node.lineno)
                fn_lines = max(1, end_lineno - node.lineno + 1)
                if fn_lines > 50:
                    hotspots.append({
                        "path": rel_path,
                        "fn": node.name,
                        "lines": fn_lines,
                        "lineno": node.lineno,
                    })

    hotspots.sort(key=lambda item: item["lines"], reverse=True)
    results["complexity"] = {"hotspots": hotspots, "todo_counts": todo_counts}

def _scan_stage_tests(root: str, results: dict) -> None:
    """Stage 4: structural name matching for public-function test gaps."""
    import ast as _ast

    skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}

    def _should_skip(dirpath: str) -> bool:
        parts = set(dirpath.split(os.sep))
        return bool(parts & skip_names)

    source_functions = []
    covered_names = set()
    if not os.path.isdir(root):
        results["tests"] = {
            "gap_functions": [],
            "covered_count": 0,
            "gap_count": 0,
            "ratio": 0.0,
        }
        return

    for dirpath, _, filenames in os.walk(root):
        if _should_skip(dirpath):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fn)
            rel_path = os.path.relpath(filepath, root)
            is_test = fn.startswith("test_") or fn.endswith("_test.py")
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                tree = _ast.parse(content, filename=filepath)
            except (OSError, SyntaxError):
                continue

            if is_test:
                for node in _ast.walk(tree):
                    if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                        covered_names.add(node.name[5:])
                    elif isinstance(node, _ast.Call):
                        func = node.func
                        if isinstance(func, _ast.Name):
                            covered_names.add(func.id)
                        elif isinstance(func, _ast.Attribute):
                            covered_names.add(func.attr)
                continue

            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    source_functions.append({
                        "name": node.name,
                        "file": rel_path,
                        "lineno": node.lineno,
                    })

    covered = [item for item in source_functions if item["name"] in covered_names]
    gaps = [item for item in source_functions if item["name"] not in covered_names]
    total = len(source_functions)
    results["tests"] = {
        "gap_functions": gaps,
        "covered_count": len(covered),
        "gap_count": len(gaps),
        "ratio": (len(covered) / total) if total else 0.0,
    }

def _scan_stage_git(root: str, results: dict) -> None:
    """Stage 5: scan the last 30 commits and compute file churn."""
    import datetime as _dt

    error_result = {"error": "", "churn": [], "total_commits_scanned": 0}
    try:
        proc = subprocess.run(
            ["git", "log", "--name-only", "-n", "30", "--pretty=format:COMMIT:%ai"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        error_result["error"] = str(exc)
        results["git"] = error_result
        return

    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        error_result["error"] = stderr or "git log failed"
        results["git"] = error_result
        return

    file_counts = {}
    first_seen = {}
    commit_count = 0
    current_date = None

    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("COMMIT:"):
            commit_count += 1
            date_text = line[len("COMMIT:"):].strip()
            try:
                current_date = _dt.datetime.strptime(date_text, "%Y-%m-%d %H:%M:%S %z")
            except ValueError:
                current_date = None
            continue
        file_counts[line] = file_counts.get(line, 0) + 1
        if current_date is not None and line not in first_seen:
            first_seen[line] = current_date

    now = _dt.datetime.now(_dt.timezone.utc)
    churn = []
    for path, commits in file_counts.items():
        seen_at = first_seen.get(path)
        last_days_ago = (now - seen_at.astimezone(_dt.timezone.utc)).days if seen_at else 0
        if commits > 20:
            temp = "hot"
        elif commits >= 5:
            temp = "warm"
        else:
            temp = "cold"
        churn.append({
            "path": path,
            "commits": commits,
            "last_days_ago": last_days_ago,
            "temp": temp,
        })

    churn.sort(key=lambda item: item["commits"], reverse=True)
    results["git"] = {"churn": churn, "total_commits_scanned": commit_count}

def _scan_stage_arch(root: str, results: dict) -> None:
    """Stage 6: scan entry points, local imports, dead candidates, and pattern."""
    import ast as _ast

    skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}
    pkg_name = os.path.basename(os.path.abspath(root)) or ""

    def _should_skip(dirpath: str) -> bool:
        parts = set(dirpath.split(os.sep))
        return bool(parts & skip_names)

    entry_points = []
    import_graph = {}
    inbound = {}
    file_line_counts = {}
    public_api_count = 0

    if not os.path.isdir(root):
        results["arch"] = {
            "entry_points": entry_points,
            "import_graph": import_graph,
            "dead_candidates": [],
            "public_api_count": public_api_count,
            "pattern": "library",
        }
        return

    for dirpath, _, filenames in os.walk(root):
        if _should_skip(dirpath):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fn)
            rel_path = os.path.relpath(filepath, root)
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except OSError:
                continue

            file_line_counts[rel_path] = content.count("\n") + 1
            try:
                tree = _ast.parse(content, filename=filepath)
            except SyntaxError:
                continue

            is_test = fn.startswith("test_") or fn.endswith("_test.py")
            if not is_test:
                for node in _ast.walk(tree):
                    if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)) and not node.name.startswith("_"):
                        public_api_count += 1

            local_imports = []
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name == "main":
                    entry_points.append({
                        "name": "main",
                        "file": rel_path,
                        "lineno": node.lineno,
                    })
                elif isinstance(node, _ast.If):
                    test = node.test
                    if (
                        isinstance(test, _ast.Compare)
                        and isinstance(test.left, _ast.Name)
                        and test.left.id == "__name__"
                        and any(
                            isinstance(comp, _ast.Constant) and comp.value == "__main__"
                            for comp in test.comparators
                        )
                    ):
                        entry_points.append({
                            "name": "__main__",
                            "file": rel_path,
                            "lineno": node.lineno,
                        })
                elif isinstance(node, _ast.ImportFrom):
                    if node.level > 0:
                        local_imports.append(rel_path)
                        inbound[rel_path] = inbound.get(rel_path, 0) + 1
                    elif node.module and node.module.split(".")[0] == pkg_name:
                        imported = node.module.replace(".", os.sep) + ".py"
                        local_imports.append(imported)
                        inbound[imported] = inbound.get(imported, 0) + 1

            if local_imports:
                import_graph[rel_path] = local_imports

    source_files = {
        path for path in file_line_counts
        if not os.path.basename(path).startswith("test_")
    }
    total_lines = sum(file_line_counts.values()) or 1
    max_lines = max(file_line_counts.values(), default=0)
    if not entry_points and len(source_files) == 1 and next(iter(source_files), "") == "__init__.py":
        pattern = "library"
    elif max_lines / total_lines > 0.5:
        pattern = "monolith"
    elif not entry_points:
        pattern = "library"
    else:
        pattern = "modular"

    dead_candidates = sorted(
        path for path in source_files
        if path != "__init__.py" and inbound.get(path, 0) == 0 and "__init__" not in path
    )

    results["arch"] = {
        "entry_points": entry_points,
        "import_graph": import_graph,
        "dead_candidates": dead_candidates,
        "public_api_count": public_api_count,
        "pattern": pattern,
    }

def _scan_stage_stack(root: str, results: dict) -> None:
    """Stage 1: detect language, version, frameworks, CI, deps, and lock freshness."""
    import fnmatch as _fnmatch
    import json as _json

    skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}

    def _should_skip(dirpath: str) -> bool:
        parts = set(dirpath.split(os.sep))
        return bool(parts & skip_names)

    language = "unknown"
    if os.path.isdir(root):
        if os.path.exists(os.path.join(root, "pyproject.toml")) or os.path.exists(os.path.join(root, "setup.py")):
            language = "python"
        elif os.path.exists(os.path.join(root, "package.json")):
            language = "node"
        elif os.path.exists(os.path.join(root, "go.mod")):
            language = "go"
        elif os.path.exists(os.path.join(root, "Gemfile")):
            language = "ruby"
        else:
            for dirpath, _, filenames in os.walk(root):
                if _should_skip(dirpath):
                    continue
                if any(_fnmatch.fnmatch(fn, "*.py") for fn in filenames):
                    language = "python"
                    break
                if any(_fnmatch.fnmatch(fn, "*.ts") or _fnmatch.fnmatch(fn, "*.tsx") for fn in filenames):
                    language = "node"
                    break

    version = "unknown"
    version_files = [
        (".python-version", "line"),
        (".nvmrc", "line"),
        (".node-version", "line"),
        ("pyproject.toml", r'python_requires\s*=\s*["\']([^"\']+)'),
        ("go.mod", r"^go\s+(\S+)"),
    ]
    for filename, pattern in version_files:
        path = os.path.join(root, filename)
        if not os.path.exists(path):
            continue
        try:
            content = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if pattern == "line":
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if lines:
                version = lines[0]
                break
            continue
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            version = match.group(1)
            break

    frameworks = []
    seen_frameworks = set()
    framework_checks = [
        ("pytest", "pyproject.toml", "pytest"),
        ("pytest", "pytest.ini", None),
        ("pytest", "setup.cfg", "pytest"),
        ("django", "manage.py", None),
        ("flask", "requirements.txt", "flask"),
        ("fastapi", "requirements.txt", "fastapi"),
        ("next", "next.config.js", None),
        ("next", "next.config.ts", None),
        ("react", "package.json", "react"),
    ]
    for fw, filename, marker in framework_checks:
        if fw in seen_frameworks:
            continue
        path = os.path.join(root, filename)
        if not os.path.exists(path):
            continue
        if marker is None:
            frameworks.append(fw)
            seen_frameworks.add(fw)
            continue
        try:
            content = open(path, encoding="utf-8", errors="ignore").read().lower()
        except OSError:
            continue
        if marker.lower() in content:
            frameworks.append(fw)
            seen_frameworks.add(fw)

    package_manager = "unknown"
    for candidate in ("pyproject.toml", "setup.py", "package.json", "go.mod",
                      "Gemfile", "requirements.txt"):
        if os.path.exists(os.path.join(root, candidate)):
            package_manager = candidate
            break

    ci = (
        os.path.isdir(os.path.join(root, ".github", "workflows"))
        or os.path.exists(os.path.join(root, ".gitlab-ci.yml"))
        or os.path.isdir(os.path.join(root, ".circleci"))
    )
    ci_workflows = 0
    wf_dir = os.path.join(root, ".github", "workflows")
    if os.path.isdir(wf_dir):
        try:
            ci_workflows = sum(
                1 for name in os.listdir(wf_dir)
                if name.endswith((".yml", ".yaml"))
            )
        except OSError:
            ci_workflows = 0

    dep_count = {"prod": 0, "dev": 0}
    req_path = os.path.join(root, "requirements.txt")
    if os.path.exists(req_path):
        try:
            with open(req_path, encoding="utf-8", errors="ignore") as fh:
                dep_count["prod"] = sum(
                    1 for line in fh if line.strip() and not line.lstrip().startswith("#")
                )
        except OSError:
            pass
    req_dev = os.path.join(root, "requirements-dev.txt")
    if os.path.exists(req_dev):
        try:
            with open(req_dev, encoding="utf-8", errors="ignore") as fh:
                dep_count["dev"] = sum(
                    1 for line in fh if line.strip() and not line.lstrip().startswith("#")
                )
        except OSError:
            pass
    pkg_json = os.path.join(root, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, encoding="utf-8", errors="ignore") as fh:
                data = _json.loads(fh.read())
            dep_count["prod"] = len(data.get("dependencies", {}) or {})
            dep_count["dev"] = len(data.get("devDependencies", {}) or {})
        except (OSError, ValueError, TypeError):
            pass

    lockfile_fresh = False
    lock_pairs = [
        ("package.json", "package-lock.json"),
        ("package.json", "yarn.lock"),
        ("Gemfile", "Gemfile.lock"),
        ("go.mod", "go.sum"),
    ]
    for manifest, lockfile in lock_pairs:
        manifest_path = os.path.join(root, manifest)
        lock_path = os.path.join(root, lockfile)
        if os.path.exists(manifest_path) and os.path.exists(lock_path):
            try:
                lockfile_fresh = os.path.getmtime(lock_path) >= os.path.getmtime(manifest_path)
            except OSError:
                lockfile_fresh = False
            break
    if os.path.exists(os.path.join(root, "pyproject.toml")):
        lockfile_fresh = True

    results["stack"] = {
        "language": language,
        "version": version,
        "frameworks": frameworks,
        "package_manager": package_manager,
        "ci": ci,
        "ci_workflows": ci_workflows,
        "dep_count": dep_count,
        "lockfile_fresh": lockfile_fresh,
    }

STAGE_KEYS = ["stack", "source", "complexity", "tests", "git", "arch"]

def run_workspace_scan(roots: list = None, workspace_name: str = None,
                       dry_run: bool = False, deep: bool = True) -> dict:
    """Scan a workspace and return the contract payload used by init --wizard.

    roots: explicit list of repo paths. If omitted, discover git roots from
           common workspace locations plus the current directory.
    dry_run: accepted for contract parity; this implementation only returns
             the scan payload and does not write to disk.
    """
    import shutil as _shutil
    import time as _time

    if roots is None:
        search_dirs = [
            os.path.expanduser("~/dev"),
            os.path.expanduser("~/projects"),
            os.getcwd(),
        ]
        roots = _pkg("find_git_roots")(search_dirs, max_depth=2)

    normalized_roots = []
    seen_roots = set()
    for root in roots or []:
        if not root:
            continue
        abs_root = os.path.abspath(os.path.expanduser(root))
        if abs_root in seen_roots or not os.path.isdir(abs_root):
            continue
        seen_roots.add(abs_root)
        normalized_roots.append(abs_root)

    repos = []
    for repo_path in normalized_roots:
        readme_excerpt = ""
        readme_path = os.path.join(repo_path, "README.md")
        if os.path.exists(readme_path):
            try:
                with open(readme_path) as fh:
                    readme_excerpt = fh.read(200)
            except OSError:
                readme_excerpt = ""

        repos.append({
            "path": repo_path,
            "name": os.path.basename(repo_path),
            "stack_labels": _pkg("fingerprint_stack")(repo_path),
            "readme_excerpt": readme_excerpt,
            "context_sections": _pkg("parse_context_sections")(repo_path),
        })

    if len(repos) > 1:
        topology = "multi"
    elif repos and any(
        os.path.isdir(os.path.join(repos[0]["path"], marker))
        for marker in _MONOREPO_MARKERS
    ):
        topology = "monorepo"
    else:
        topology = "single"

    harnesses = []
    for name in ("claude", "agy", "codex", "grok", "gemini", "aider"):
        cli_path = _shutil.which(name)
        if not cli_path:
            continue
        version = "unknown"
        try:
            proc = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (proc.stdout or proc.stderr or "").strip().splitlines()
            if output:
                version = output[0]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        harnesses.append({
            "name": name,
            "cli": name,
            "version": version,
            "path": cli_path,
        })

    try:
        agents = _pkg("discover_agents")()
    except Exception:
        agents = []

    skills = _pkg("scan_skills")()
    home_harness = _pkg("detect_home_harness")(harnesses)

    if workspace_name is None:
        if normalized_roots:
            if topology == "single" and repos:
                workspace_name = repos[0]["name"]
            else:
                parent = os.path.basename(os.path.dirname(normalized_roots[0]))
                workspace_name = parent if parent and parent not in (os.sep, "~") else repos[0]["name"]
        else:
            workspace_name = os.path.basename(os.getcwd()) or "workspace"

    # ── BS-19 launch task trigger fields ─────────────────────────────────────
    primary_root = normalized_roots[0] if normalized_roots else os.getcwd()

    # test_ratio: test files / total source files (0.0 if no source files)
    def _count_files(root, patterns):
        import fnmatch as _fnmatch
        count = 0
        for dirpath, _, filenames in os.walk(root):
            if any(p in dirpath for p in (".git", "__pycache__", "node_modules", ".venv", "venv")):
                continue
            for fn in filenames:
                if any(_fnmatch.fnmatch(fn, p) for p in patterns):
                    count += 1
        return count

    src_count = _count_files(primary_root, ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.rb", "*.go"])
    test_count_files = _count_files(primary_root, ["test_*.py", "*_test.py", "*.test.ts",
                                                    "*.test.tsx", "*.test.js", "*.spec.ts", "*.spec.js"])
    test_ratio = test_count_files / src_count if src_count > 0 else 0.0

    # readme_word_count
    readme_path = os.path.join(primary_root, "README.md")
    readme_word_count = 0
    if os.path.exists(readme_path):
        try:
            readme_word_count = len(open(readme_path).read().split())
        except OSError:
            pass

    # has_ci
    has_ci = (
        os.path.isdir(os.path.join(primary_root, ".github", "workflows"))
        or os.path.exists(os.path.join(primary_root, ".gitlab-ci.yml"))
        or os.path.isdir(os.path.join(primary_root, ".circleci"))
    )

    # has_docs: docs/ dir with at least one .md file
    docs_dir = os.path.join(primary_root, "docs")
    has_docs = False
    if os.path.isdir(docs_dir):
        for fn in os.listdir(docs_dir):
            if fn.endswith(".md"):
                has_docs = True
                break

    # has_type_hints: derived from source-stage typed_pct after deep scan joins.
    has_type_hints = False

    # has_orm
    orm_markers = ("sqlalchemy", "from django.db", "import prisma", "activerecord", "ActiveRecord")
    has_orm = False
    for dep_file in ("requirements.txt", "requirements-dev.txt", "pyproject.toml",
                     "Gemfile", "package.json", "go.mod"):
        dep_path = os.path.join(primary_root, dep_file)
        if os.path.exists(dep_path):
            try:
                content = open(dep_path).read()
                if any(m in content for m in orm_markers):
                    has_orm = True
                    break
            except OSError:
                pass

    base = {
        "workspace_name": workspace_name,
        "topology": topology,
        "repos": repos,
        "harnesses": harnesses,
        "agents": agents,
        "skills": skills,
        "home_harness": home_harness,
        "scanned_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "test_ratio": test_ratio,
        "readme_word_count": readme_word_count,
        "has_ci": has_ci,
        "has_docs": has_docs,
        "has_type_hints": has_type_hints,
        "has_orm": has_orm,
        "stack": None,
        "source": None,
        "complexity": None,
        "tests": None,
        "git": None,
        "arch": None,
    }
    if not deep:
        return base

    stage_fns = [
        _pkg("_scan_stage_stack"),
        _pkg("_scan_stage_source"),
        _pkg("_scan_stage_complexity"),
        _pkg("_scan_stage_tests"),
        _pkg("_scan_stage_git"),
        _pkg("_scan_stage_arch"),
    ]
    threads = []
    for stage_fn in stage_fns:
        thread = threading.Thread(target=stage_fn, args=(primary_root, base), daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

    source_rows = [
        row for row in (base.get("source") or [])
        if isinstance(row, dict) and not row.get("parse_error") and row.get("path", "").endswith(".py")
    ]
    if source_rows:
        avg_typed = sum(row.get("typed_pct", 0) for row in source_rows) / len(source_rows)
        base["has_type_hints"] = avg_typed > 30.0

    return base

def _workspace_config_dir(workspace_name: str) -> str:
    """Return a writable workspace config directory, preferring ~/.synlynk."""
    preferred = os.path.expanduser(f"~/.synlynk/workspaces/{workspace_name}")
    try:
        os.makedirs(preferred, exist_ok=True)
        return preferred
    except PermissionError:
        fallback = os.path.abspath(os.path.join(".synlynk", "workspaces", workspace_name))
        os.makedirs(fallback, exist_ok=True)
        return fallback

def write_workspace_config(scan_result: dict, workspace_name: str) -> str:
    """Write workspace config to ~/.synlynk/workspaces/<name>/config.json.

    Returns the path written.
    """
    import json as _json
    ws_dir = _workspace_config_dir(workspace_name)
    config = {
        "workspace_name": workspace_name,
        "topology": scan_result.get("topology", "single"),
        "home_harness": scan_result.get("home_harness"),
        "repos": [
            {
                "path": r["path"],
                "name": r["name"],
                "stack_labels": r["stack_labels"],
            }
            for r in scan_result.get("repos", [])
        ],
        "agent_roles": {},  # populated by wizard Screen 5
        "created_at": scan_result.get("scanned_at", ""),
        "last_scanned_at": scan_result.get("scanned_at", ""),
    }
    config_path = os.path.join(ws_dir, "config.json")
    open(config_path, "w").write(_json.dumps(config, indent=2))
    return config_path

def generate_structured_context(scan_result: dict,
                                 out_path: str = None) -> str:
    """Write structured context.md from a ScanResult dict.

    This replaces generate_context() when a workspace scan has been run.
    Falls back to generate_context() if scan_result is None.
    """
    context_file = out_path or ".synlynk/context.md"
    os.makedirs(os.path.dirname(os.path.abspath(context_file)), exist_ok=True)

    lines = []
    ws_name = scan_result.get("workspace_name", "workspace")
    lines.append(f"# synlynk context — {ws_name}")
    lines.append(f"generated: {scan_result.get('scanned_at', '')}")
    lines.append("")
    lines.append("## workspace")
    lines.append(f"name: {ws_name}")
    home_h = scan_result.get("home_harness") or "none"
    lines.append(f"home harness: {home_h}")
    repo_list = scan_result.get("repos", [])
    lines.append(f"repos: {len(repo_list)}")
    lines.append("")

    if repo_list:
        lines.append("## repos")
        for repo in repo_list:
            lines.append(f"### {repo['name']}")
            lines.append(f"path: {repo['path']}")
            stack = ", ".join(repo.get("stack_labels", [])) or "unknown"
            lines.append(f"stack: {stack}")
            excerpt = (repo.get("readme_excerpt") or "").replace("\n", " ").strip()
            if excerpt:
                lines.append(f"readme: {excerpt[:200]}")
            for title, content in (repo.get("context_sections") or {}).items():
                lines.append(f"\n### {title} (from {repo['name']})")
                lines.append(content[:300])
            lines.append("")

    harnesses = scan_result.get("harnesses", [])
    agents = scan_result.get("agents", [])
    if harnesses or agents:
        lines.append("## agent fleet")
        for h in harnesses:
            lines.append(f"{h['name']}: {h['version']} — {h['path']}")
        lines.append("")

    skills = scan_result.get("skills", [])
    if skills:
        lines.append("## skills")
        for s in skills:
            lines.append(f"{s['name']}: {s['version']} — {s['path']}")
        lines.append("")

    content = "\n".join(lines)
    try:
        open(context_file, "w").write(content)
        print(f"  ✓ context.md updated ({len(content)} chars) → {context_file}")
    except OSError as e:
        print(f"  ⚠ Could not write context.md: {e}")

    return content

_PROJECT_DOC_NAMES = {"roadmap.md", "todo.md", "memory.md", "costs.md", "devlog.md"}

_AGENT_FILE_NAMES = {"CLAUDE.md", "GEMINI.md", "AGENTS.md", "AI_INSTRUCTIONS.md"}

_SCAN_SKIP_DIRS = {
    ".git", "node_modules", ".synlynk", "project-docs",
    "__pycache__", ".venv", "venv", "env", ".next", "dist", "build",
    "vendor", ".worktrees", "coverage", ".nyc_output", "target", "out", "tmp",
}

_SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".sh": "shell",
}

_SOURCE_ENTRY_POINTS = {
    "main.py", "app.py", "server.py", "index.js", "index.ts", "main.go",
    "lib.rs", "main.rs", "app.rb", "manage.py", "wsgi.py", "asgi.py", "__init__.py",
}

_SYMBOL_PATTERNS = {
    "python": [
        (re.compile(r"^async def (\w+)"), "async_function"),
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^([A-Z_]{2,})\s*="), "constant"),
    ],
    "javascript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "typescript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export interface (\w+)"), "interface"),
        (re.compile(r"^export type (\w+)"), "type"),
        (re.compile(r"^export enum (\w+)"), "enum"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "go": [
        (re.compile(r"^func (?:\(\w+ \*?\w+\) )?(\w+)"), "function"),
        (re.compile(r"^type (\w+) struct"), "struct"),
        (re.compile(r"^type (\w+) interface"), "interface"),
    ],
    "rust": [
        (re.compile(r"^pub fn (\w+)"), "function"),
        (re.compile(r"^pub struct (\w+)"), "struct"),
        (re.compile(r"^pub trait (\w+)"), "trait"),
        (re.compile(r"^pub enum (\w+)"), "enum"),
        (re.compile(r"^pub type (\w+)"), "type"),
    ],
    "ruby": [
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^module (\w+)"), "module"),
    ],
    "java": [
        (re.compile(r"(?:public|protected) (?:class|interface|enum) (\w+)"), "class"),
        (re.compile(r"(?:public|protected) \w+ (\w+)\s*\("), "function"),
    ],
    "kotlin": [
        (re.compile(r"^fun (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^object (\w+)"), "class"),
        (re.compile(r"^interface (\w+)"), "interface"),
    ],
    "shell": [
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^(\w+)\(\)"), "function"),
    ],
}

def _extract_symbols(file_path: str) -> list:
    """Returns [{"symbol": str, "symbol_type": str, "line": int}] from file_path.

    Reads at most 300 lines. Returns [] for unknown extensions or unreadable files.
    """
    ext = os.path.splitext(file_path)[1].lower()
    lang = _SOURCE_EXTENSIONS.get(ext)
    if not lang:
        return []
    patterns = _SYMBOL_PATTERNS.get(lang, [])
    if not patterns:
        return []
    results = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, 1):
                if lineno > 300:
                    break
                for pattern, sym_type in patterns:
                    m = pattern.match(line)
                    if m:
                        results.append({
                            "symbol": m.group(1),
                            "symbol_type": sym_type,
                            "line": lineno,
                        })
                        break
    except (OSError, IOError):
        pass
    return results

def _git_head_sha() -> Optional[str]:
    """Returns the full SHA of HEAD, or None if not in a git repo or no commits."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha if len(sha) == 40 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None

def _load_scan_meta() -> Optional[dict]:
    """Reads .synlynk/scan-meta.json. Returns None if absent or malformed."""
    path = os.path.join(".synlynk", "scan-meta.json")
    if not os.path.exists(path):
        return None
    try:
        return json.loads(open(path).read())
    except (ValueError, OSError):
        return None

def _save_scan_meta(head_sha: str, skeleton: list, deep: Optional[dict] = None) -> None:
    """Writes skeleton + metadata to .synlynk/scan-meta.json."""
    os.makedirs(".synlynk", exist_ok=True)
    existing = _pkg("_load_scan_meta")()
    meta = {
        "schema_version": 1,
        "head_sha": head_sha,
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_count": len(skeleton),
        "skeleton": skeleton,
    }
    if deep is not None:
        meta["deep"] = deep
    elif existing and existing.get("deep"):
        meta["deep"] = existing["deep"]
    with open(os.path.join(".synlynk", "scan-meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

def _score_source_files(root: str = ".") -> list:
    """Returns [(score, rel_path), ...] for all source files, sorted score descending.

    Scoring: +3 if filename is a known entry point, +1 per appearance in last-50
    git commits, -1 per directory level beyond 2.
    """
    # Collect git activity: count file appearances in last 50 commits
    git_counts: dict = {}
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "-50"],
            capture_output=True, text=True, cwd=root, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    git_counts[line] = git_counts.get(line, 0) + 1
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    scored = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SOURCE_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            # Depth = number of directory separators
            depth = rel_path.count(os.sep)
            # Entry point bonus: filename match OR cmd/main.go path
            entry_bonus = 3 if (fname in _SOURCE_ENTRY_POINTS or rel_path in ("cmd/main.go",)) else 0
            git_score = git_counts.get(rel_path, 0)
            depth_penalty = max(0, depth - 2)
            score = entry_bonus + git_score - depth_penalty
            scored.append((score, rel_path))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored

def _scan_source_skeleton(root: str = ".") -> list:
    """Top-15 prioritised files with up to 8 symbols each.

    Returns list of {"file": str, "language": str, "symbols": [str]} where
    symbols are display strings ("name()" for functions, "name" for others).
    """
    scored = _score_source_files(root)
    top = scored[:15]
    skeleton = []
    for _score, rel_path in top:
        ext = os.path.splitext(rel_path)[1].lower()
        lang = _SOURCE_EXTENSIONS.get(ext, "generic")
        abs_path = os.path.join(root, rel_path)
        raw_syms = _pkg("_extract_symbols")(abs_path)[:8]
        display_syms = []
        for s in raw_syms:
            name = s["symbol"]
            if s["symbol_type"] in ("function", "async_function"):
                display_syms.append(f"{name}()")
            else:
                display_syms.append(name)
        skeleton.append({"file": rel_path, "language": lang, "symbols": display_syms})
    return skeleton

def _query_repo_file_tree() -> dict:
    """Build a nested directory tree from source_symbols for the current HEAD."""
    conn = _pkg("_get_db")()
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(scanned_at) FROM source_symbols")
        row = cur.fetchone()
        if not row or not row[0]:
            return {"name": ".", "dirs": {}, "files": []}
        cur.execute(
            "SELECT file, COUNT(*) FROM source_symbols "
            "WHERE scanned_at = (SELECT MAX(scanned_at) FROM source_symbols) "
            "GROUP BY file"
        )
        file_counts = cur.fetchall()
    except sqlite3.OperationalError:
        return {"name": ".", "dirs": {}, "files": []}

    root = {"name": ".", "dirs": {}, "files": []}
    for file_path, symbol_count in file_counts:
        parts = file_path.split(os.sep) if os.sep in file_path else file_path.split("/")
        node = root
        for part in parts[:-1]:
            node = node["dirs"].setdefault(part, {"name": part, "dirs": {}, "files": []})
        node["files"].append({"name": parts[-1], "symbol_count": symbol_count})
    return root

def _scan_full_repo(root: str = ".") -> tuple:
    """Deep scan: extracts all symbols, writes DB + project-docs/source-map.md.

    Returns (skeleton, total_files, total_symbols).
    Clears rows for any head_sha != current HEAD before inserting.
    """
    head_sha = _pkg("_git_head_sha")() or "unknown"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    all_entries = []  # list of {"file": str, "language": str, "symbols": [raw_dict]}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SOURCE_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            lang = _SOURCE_EXTENSIONS[ext]
            raw_syms = _pkg("_extract_symbols")(abs_path)
            all_entries.append({"file": rel_path, "language": lang, "symbols": raw_syms})

    total_files = len(all_entries)
    total_syms = sum(len(e["symbols"]) for e in all_entries)

    # Write DB
    try:
        conn = _pkg("_get_db")()
        conn.execute("DELETE FROM source_symbols WHERE head_sha != ?", (head_sha,))
        rows = []
        for entry in all_entries:
            for sym in entry["symbols"]:
                rows.append((
                    head_sha, entry["file"], entry["language"],
                    sym["symbol"], sym["symbol_type"], sym.get("line"), now,
                ))
        conn.executemany(
            "INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, line, scanned_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception as e:
        print(f"  ⚠ source_symbols DB write failed: {e}")

    # Write project-docs/source-map.md
    source_map_path = os.path.join(_pkg("_docs_dir")(), "source-map.md")
    try:
        os.makedirs("project-docs", exist_ok=True)
        sha_short = head_sha[:7] if head_sha != "unknown" else "unknown"
        lines = [
            "# Source Map",
            f"_Generated: {now} · HEAD: {sha_short} · {total_files} files_",
            "",
        ]
        # Group by directory
        groups: dict = {}
        for entry in sorted(all_entries, key=lambda e: e["file"]):
            dirname = os.path.dirname(entry["file"])
            groups.setdefault(dirname, []).append(entry)

        for dirname, entries in sorted(groups.items()):
            lang_counts: dict = {}
            for e in entries:
                lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
            lang_str = ", ".join(
                f"{lg} · {cnt}" for lg, cnt in sorted(lang_counts.items())
            )
            label = dirname if dirname else "[root]"
            lines.append(f"## {label}/  [{lang_str}]")
            for entry in entries:
                sym_count = len(entry["symbols"])
                lines.append(f"`{entry['file']}` · {sym_count} symbols")
                display_parts = []
                for s in entry["symbols"]:
                    name = s["symbol"]
                    disp = f"{name}()" if s["symbol_type"] in ("function", "async_function") else name
                    disp += f" [{s['symbol_type']}:{s.get('line', '?')}]"
                    display_parts.append(disp)
                if display_parts:
                    lines.append("  " + ", ".join(display_parts))
                lines.append("")

        with open(source_map_path, "w") as fh:
            fh.write("\n".join(lines))
    except OSError as e:
        print(f"  ⚠ source-map.md write failed: {e}")

    # Build and persist skeleton
    skeleton = _pkg("_scan_source_skeleton")(root)
    deep_meta = {"total_files": total_files, "total_symbols": total_syms, "scanned_at": now}
    _pkg("_save_scan_meta")(head_sha, skeleton, deep=deep_meta)

    return skeleton, total_files, total_syms

def _check_scan_cache(root: str = ".") -> list:
    """Returns skeleton from cache if HEAD unchanged, else re-scans.

    Returns [] if not in a git repo (no commits). On re-scan, writes updated
    scan-meta.json but does NOT write source-map.md or the DB — that's --deep only.
    """
    current_sha = _pkg("_git_head_sha")()
    if current_sha is None:
        return []
    meta = _pkg("_load_scan_meta")()
    if meta and meta.get("head_sha") == current_sha:
        return meta.get("skeleton", [])
    skeleton = _pkg("_scan_source_skeleton")(root)
    _pkg("_save_scan_meta")(current_sha, skeleton)
    return skeleton

def _format_source_architecture(skeleton: list, head_sha: str, cache_hit: bool,
                                 total_files: int = 0) -> str:
    """Formats the ## Source Architecture block for context.md."""
    if not skeleton:
        return ""
    status = "cache hit" if cache_hit else "refreshed"
    sha_short = head_sha[:7] if head_sha and head_sha != "unknown" else "unknown"
    lines = [
        "## Source Architecture",
        f"_Scanned: {time.strftime('%Y-%m-%dT%H:%M')} · HEAD: {sha_short}"
        f" · {len(skeleton)} files · {status}_",
        "",
    ]
    # Group by directory
    groups: dict = {}
    for entry in skeleton:
        dirname = os.path.dirname(entry["file"])
        groups.setdefault(dirname, []).append(entry)

    for dirname in sorted(groups):
        entries = groups[dirname]
        lang_counts: dict = {}
        for e in entries:
            lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
        lang_str = ", ".join(
            f"{lg} · {cnt} {'file' if cnt == 1 else 'files'}"
            for lg, cnt in sorted(lang_counts.items())
        )
        label = dirname if dirname else "[root]"
        lines.append(f"### {label}/  [{lang_str}]")
        for entry in entries:
            syms = entry.get("symbols") or []
            if syms:
                lines.append(f"`{entry['file']}` — {', '.join(syms)}")
            else:
                lines.append(f"`{entry['file']}`")
        lines.append("")

    if total_files > len(skeleton):
        overflow = total_files - len(skeleton)
        noun = "file" if overflow == 1 else "files"
        lines.append(
            f"> {overflow} more {noun} in source-map.md"
            " — run `synlynk scan --deep` to refresh"
        )
    lines.append("---")
    lines.append("")
    return "\n".join(lines)

def _scan_repo_for_docs(root: str = ".") -> dict:
    """Scans repo tree for project docs and agent files outside expected locations.

    Returns {"docs": [absolute_paths], "agent_files": {name: absolute_path}}.
    """
    docs = []
    agent_files = {}
    abs_root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(abs_root):
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, abs_root)
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if fname.lower() in _PROJECT_DOC_NAMES:
                docs.append(fpath)
            if rel_dir == "." and fname in _AGENT_FILE_NAMES:
                agent_files[fname] = fpath
    return {"docs": docs, "agent_files": agent_files}

_STAGE_LABELS = ["STACK", "SOURCE", "COMPLEXITY", "TESTS", "GIT CHURN", "ARCHITECTURE"]

_STAGE_COLORS = [_GREEN, _CYAN, _YELLOW, _GREEN, _RED, _MAGENTA]
