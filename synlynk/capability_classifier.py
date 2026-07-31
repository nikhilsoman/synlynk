"""Classifies a probe/smoke-test failure as a synlynk regression or harness-side drift.

See docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md
section "4. Regression-vs-drift classifier"
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional


def _path_changed_since(repo_path: str, failing_path: str, since_sha: str) -> Optional[str]:
    """Returns the commit range as a string if the path changed since `since_sha`,
    else None.

    Returns None (not raises) if the sha is unknown to this repo - treated as
    "cannot determine", not as "no change".
    """

    result = subprocess.run(
        ["git", "log", f"{since_sha}..HEAD", "--oneline", "--", failing_path],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    return f"{since_sha[:7]}..HEAD ({len(lines)} commit(s) touching {failing_path})"


def classify_failure(
    conn,
    *,
    harness: str,
    failing_path: str,
    repo_path: str,
    last_green_sha: str,
    harness_fingerprint_changed: bool,
) -> dict:
    synlynk_change_evidence = _path_changed_since(repo_path, failing_path, last_green_sha)

    if synlynk_change_evidence:
        classification = "regression"
        evidence = synlynk_change_evidence
    elif harness_fingerprint_changed:
        classification = "drift"
        evidence = (
            f"harness '{harness}' CLI version/instruction fingerprint changed since last green run"
        )
    else:
        classification = "unclassified"
        evidence = "no synlynk commit on the failing path and no harness fingerprint change detected"

    conn.execute(
        "INSERT INTO capability_incidents (harness, failing_path, classification, evidence, detected_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            harness,
            failing_path,
            classification,
            evidence,
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ),
    )
    conn.commit()
    return {"classification": classification, "evidence": evidence}
