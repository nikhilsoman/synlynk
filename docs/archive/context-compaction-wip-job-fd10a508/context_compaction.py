"""Harness Context Compaction Protocol. See
docs/superpowers/specs/2026-10-31-harness-context-compaction-protocol-design.md.

Two distinct artifacts sharing only _gather_snapshot():
  - checkpoint(): AST-grounded resumption-ledger write (reactive, manual or
    auto_checkpoint_on_pack-triggered)
  - pack()/inject(): proactive task-boundary context-pack injection

There is no 75%-threshold reactive monitor -- no cross-harness context-usage
signal exists anywhere in synlynk's own data, confirmed during brainstorming.

Ships unconditionally in v0.26.8/Dev Preview -- not registered against the
Configurability Framework, which is deferred to the "Expansion Capabilities"
goal. CONTEXT_COMPACTION_SETTINGS_SCHEMA is kept here so that framework can
register this feature retroactively once it exists.
"""

import ast
import hashlib
import re
import subprocess
from pathlib import Path

# Task 1: Module skeleton — settings schema constant
CONTEXT_COMPACTION_SETTINGS_SCHEMA = {
    "fields": {
        "auto_checkpoint_on_pack": {"type": "boolean", "required": False},
        "pack_token_budget": {"type": "integer", "required": False},
    },
}


# Task 2: _gather_snapshot() shared helper + AST-grounding (Self-Review fix)

def _git_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _git_is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def _git_changed_files() -> list:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def _extract_recent_function_signatures(file_path: str, limit: int = 5) -> list:
    """AST-grounds the snapshot's relevant-files content: parses a changed
    file and extracts its top-level function/class signatures rather than
    including raw file content, keeping the snapshot small and structural.
    """
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
    except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
        return []
    signatures = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            signatures.append(node.name)
        if len(signatures) >= limit:
            break
    return signatures


def _gather_snapshot(story_id: str) -> dict:
    changed_files = _git_changed_files()
    return {
        "story_id": story_id,
        "head_sha": _git_head_sha(),
        "is_dirty": _git_is_dirty(),
        "changed_file_signatures": {
            f: _extract_recent_function_signatures(f) for f in changed_files
        },
    }


# Task 3: compute_dirty_hash()

def compute_dirty_hash() -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD"], capture_output=True, text=True, check=True,
    )
    return hashlib.sha256(result.stdout.encode()).hexdigest()[:12]


# Task 4: Marker build/parse with identity key

_MARKER_PREFIX = "<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME"
_MARKER_PATTERN = re.compile(
    r"<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=(\S+) head_sha=(\S+?)(?: dirty_hash=(\S+))? -->"
)


def build_marker(story_id: str, head_sha: str, dirty_hash) -> str:
    if dirty_hash is None:
        return f"{_MARKER_PREFIX} story_id={story_id} head_sha={head_sha} -->"
    return f"{_MARKER_PREFIX} story_id={story_id} head_sha={head_sha} dirty_hash={dirty_hash} -->"


def parse_marker(line: str):
    match = _MARKER_PATTERN.match(line.strip())
    if match is None:
        return None
    story_id, head_sha, dirty_hash = match.groups()
    result = {"story_id": story_id, "head_sha": head_sha}
    if dirty_hash is not None:
        result["dirty_hash"] = dirty_hash
    return result


# Task 5: checkpoint() — idempotent devlog write

def _devlog_path(username: str) -> Path:
    return Path("project-docs/devlogs") / f"{username}.md"


def checkpoint(story_id: str, username: str) -> bool:
    """Writes an idempotent resumption-ledger entry keyed by
    (story_id, head_sha) or (story_id, head_sha, dirty_hash) when dirty.
    Returns True if a new entry was written, False if the key already
    existed (no-op).
    """
    snapshot = _gather_snapshot(story_id)
    dirty_hash = compute_dirty_hash() if snapshot["is_dirty"] else None
    marker = build_marker(story_id, snapshot["head_sha"], dirty_hash)

    devlog_path = _devlog_path(username)
    devlog_path.parent.mkdir(parents=True, exist_ok=True)
    existing = devlog_path.read_text() if devlog_path.exists() else ""

    for line in existing.splitlines():
        parsed = parse_marker(line)
        if parsed is not None and parsed == parse_marker(marker):
            return False  # identical key already checkpointed; no-op

    entry = f"\n{marker}\n- story: {story_id}\n- head_sha: {snapshot['head_sha']}\n"
    devlog_path.write_text(existing + entry)
    return True


# Task 6: Context-pack 5-part content model + pack()

def _read_story_summary(story_id: str) -> str:
    return f"Story {story_id}"


def _read_recent_decisions(story_id: str) -> list:
    return []


def _read_open_threads(story_id: str) -> list:
    return []


def _read_relevant_files(story_id: str) -> list:
    return []


def pack(story_id: str, task_description: str, username: str = None, auto_checkpoint: bool = False) -> dict:
    """Builds the 5-part context-pack content model for task-boundary
    injection. Proactive and independently triggered from checkpoint() --
    auto_checkpoint only controls whether this call also checkpoints as a
    side effect; there is no implicit automatic firing of either.
    """
    if auto_checkpoint:
        if username is None:
            raise ValueError("username is required when auto_checkpoint=True")
        checkpoint(story_id=story_id, username=username)

    return {
        "story_summary": _read_story_summary(story_id),
        "recent_decisions": _read_recent_decisions(story_id),
        "open_threads": _read_open_threads(story_id),
        "relevant_files": _read_relevant_files(story_id),
        "task_description": task_description,
    }
