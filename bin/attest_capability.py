#!/usr/bin/env python3
"""
Attest model versions and quality scores for backfilled PR stories.

Updates existing backfill rows in-place: sets model_version, quality,
signal_source='human', and note. Run once after backfill_capability.py.

Usage:
    python3 bin/attest_capability.py [--dry-run]
"""

import os
import sqlite3
import subprocess
import sys

# ---------------------------------------------------------------------------
# Borrow DB_PATH from synlynk.py — single source of truth for path resolution.
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synlynk  # noqa: E402
DB_PATH = synlynk.DB_PATH

# ---------------------------------------------------------------------------
# Attestation data
#
# model_version: best-known model for the session that produced the PR.
#   Jun 17-20 2026 (PRs 39+): claude-sonnet-4-6
#   Jun 9-14 2026  (PRs 28-39): claude-sonnet-4-5
#   May-Jun 3 2026 (PRs 1-26):  claude-opus-4-5  (early sessions)
#
# quality (0–10):
#   9-10: shipped clean, comprehensive tests, no rework
#   8:    shipped clean, solid scope
#   7.5:  minor friction (1 review cycle, or small scope)
#   7:    multiple review cycles
#   6:    trivial / mechanical (version bumps, minor fixes)
# ---------------------------------------------------------------------------

ATTESTATIONS: dict[str, dict] = {
    "story-pr49": {
        "model": "claude-sonnet-4-6",
        "quality": 9.0,
        "note": "316 tests (65 new), 9-lang scanner, subagent-driven-dev, shipped clean in one pass",
    },
    "story-pr47": {
        "model": "claude-sonnet-4-6",
        "quality": 7.0,
        "note": "VERSION sync fix — small but unblocked perpetual upgrade-prompt bug",
    },
    "story-pr46": {
        "model": "claude-sonnet-4-6",
        "quality": 8.0,
        "note": "5-state task status model, agent template updates, 7 new tests, clean",
    },
    "story-pr45": {
        "model": "claude-sonnet-4-6",
        "quality": 7.5,
        "note": "Instruction reach: 7 IDE targets, SHA manifest, drift sentinel; 1 review cycle",
    },
    "story-pr44": {
        "model": "claude-sonnet-4-6",
        "quality": 8.0,
        "note": "quality_auto normalization fix — caught a subtle weighting bug, targeted and clean",
    },
    "story-pr42": {
        "model": "claude-sonnet-4-5",
        "quality": 7.5,
        "note": "v0.6.0 capability engine: tier-2 probe, verifier pipeline, Tokq tags; 2 review cycles",
    },
    "story-pr41": {
        "model": "claude-sonnet-4-5",
        "quality": 8.5,
        "note": "v0.5.0 SQLite WAL ledger, model-aware routing, 3D taxonomy, story/score CLI — foundational",
    },
    "story-pr40": {
        "model": "claude-sonnet-4-5",
        "quality": 7.5,
        "note": "Quick start HTML guides — good production value, not core feature work",
    },
    "story-pr39": {
        "model": "claude-sonnet-4-5",
        "quality": 8.5,
        "note": "v0.4.0 Hybrid Workgroup Bootstrap — agent discovery, dispatch, jobs, init wizard; major feature",
    },
    "story-pr37": {
        "model": "claude-sonnet-4-5",
        "quality": 7.5,
        "note": "Spec correction: Tokq memory unit schema file-grain → state.db; targeted doc fix",
    },
    "story-pr36": {
        "model": "claude-sonnet-4-5",
        "quality": 7.5,
        "note": "Implementation plan doc for v0.4.0 — useful artefact, not code",
    },
    "story-pr35": {
        "model": "claude-sonnet-4-5",
        "quality": 8.0,
        "note": "Hybrid Workgroup design spec + brainstorm visuals + gap analysis; solid design artefact",
    },
    "story-pr30": {
        "model": "claude-sonnet-4-5",
        "quality": 9.0,
        "note": "17-test black-box E2E suite; broad coverage, no rework, sets regression baseline",
    },
    "story-pr29": {
        "model": "claude-sonnet-4-5",
        "quality": 8.0,
        "note": "v0.3.1 sentinel hardening: token scraping restored, burn rate, quota/loop/zombie detection",
    },
    "story-pr28": {
        "model": "claude-opus-4-5",
        "quality": 7.5,
        "note": "Design session docs: state-db, agent identity, dispatch specs — good foundation artefacts",
    },
    "story-pr26": {
        "model": "claude-opus-4-5",
        "quality": 8.0,
        "note": "v0.3.0 multi-agent foundation: AGENTS.md, parametric init, _build_templates refactor",
    },
    "story-pr24": {
        "model": "claude-opus-4-5",
        "quality": 6.0,
        "note": "Version bump to 0.2.2 — mechanical, no new functionality",
    },
    "story-pr23": {
        "model": "claude-opus-4-5",
        "quality": 7.5,
        "note": "GH CLI identity resolution fix, upgrade check correctness — targeted and clean",
    },
    "story-pr3": {
        "model": "claude-opus-4-5",
        "quality": 7.5,
        "note": "v0.2.1 correctness patch: exit code propagation, test suite reliability",
    },
    "story-pr1": {
        "model": "claude-opus-4-5",
        "quality": 8.5,
        "note": "v0.2.0 kernel: watch daemon, checkpoint, status, cost tracking, flatline sentinel — foundation",
    },
}

# ---------------------------------------------------------------------------

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    print("synlynk capability attestation")
    print(f"  DB: {DB_PATH}")
    if dry_run:
        print("  Mode: DRY RUN")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")

    updated = 0
    skipped = 0
    for story_id, data in ATTESTATIONS.items():
        row = conn.execute(
            "SELECT id, quality, signal_source FROM capability_ratings WHERE story_id=?",
            (story_id,)
        ).fetchone()

        if not row:
            print(f"  [skip] {story_id} — not in database")
            skipped += 1
            continue

        if row[2] != "backfill":
            print(f"  [skip] {story_id} — already attested (source: '{row[2]}', quality: {row[1]})")
            skipped += 1
            continue

        print(f"  {'[dry]' if dry_run else '[ok] '} {story_id:<22} "
              f"model={data['model']:<22} quality={data['quality']:>4}  {data['note'][:60]}")

        if not dry_run:
            conn.execute(
                """UPDATE capability_ratings
                   SET model_version=?, model_at_dispatch=?, model_at_completion=?,
                       quality=?, signal_source='human', note=?
                   WHERE id=?""",
                (data["model"], data["model"], data["model"],
                 data["quality"], data["note"], row[0])
            )
            updated += 1

    if not dry_run:
        conn.commit()
        print(f"\n  {updated} rows attested, {skipped} skipped.")
        print("\n  Check the ledger:")
        print("    synlynk score list --engg cli")
        print("    synlynk score list --engg test")
        print("    synlynk score list --engg docs")
    else:
        print(f"\n  (Dry run — {len(ATTESTATIONS) - skipped} rows would be updated)")

    conn.close()


if __name__ == "__main__":
    main()
