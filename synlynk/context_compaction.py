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

CONTEXT_COMPACTION_SETTINGS_SCHEMA = {
    "fields": {
        "auto_checkpoint_on_pack": {"type": "boolean", "required": False},
        "pack_token_budget": {"type": "integer", "required": False},
    },
}

import hashlib
from pathlib import Path
import re
import subprocess


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


def compute_dirty_hash() -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD"], capture_output=True, text=True, check=True,
    )
    return hashlib.sha256(result.stdout.encode()).hexdigest()[:12]


def _gather_snapshot(story_id: str) -> dict:
    return {
        "story_id": story_id,
        "head_sha": _git_head_sha(),
        "is_dirty": _git_is_dirty(),
    }


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


