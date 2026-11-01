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

import subprocess


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


def _gather_snapshot(story_id: str) -> dict:
    return {
        "story_id": story_id,
        "head_sha": _git_head_sha(),
        "is_dirty": _git_is_dirty(),
    }

