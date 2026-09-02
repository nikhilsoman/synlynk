"""Living charter drift detection and reviewable proposal generation."""

from __future__ import annotations

import json
from pathlib import Path

from synlynk.capability import capability_score


def _static_capabilities(path: str = ".synlynk/capability-roles.json") -> dict:
    """Load optional static charter probabilities, preserving old role maps."""
    try:
        with open(path) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    values = payload.get("static_capabilities", payload.get("capabilities", {}))
    return values if isinstance(values, dict) else {}


def detect_charter_divergence(conn=None, *, threshold: float = 0.25,
                              static_capabilities: dict | None = None) -> list[dict]:
    """Return empirical rows whose rate differs from the charter by > threshold."""
    from synlynk import _get_db
    db = conn or _get_db()
    owned = conn is None
    try:
        rows = db.execute("SELECT * FROM capability_ledger ORDER BY harness, task_domain, model_id").fetchall()
        names = [d[0] for d in db.execute("SELECT * FROM capability_ledger LIMIT 0").description]
        static = static_capabilities or _static_capabilities()
        findings = []
        for row in rows:
            item = dict(zip(names, row))
            empirical = item["alpha"] / (item["alpha"] + item["beta"])
            configured = static.get(item["harness"], {}).get(item["task_domain"], static.get(item["task_domain"], 0.5))
            if isinstance(configured, dict):
                configured = configured.get("success_rate", configured.get("probability", 0.5))
            configured = float(configured)
            divergence = empirical - configured
            if abs(divergence) > threshold:
                findings.append({**item, "empirical_success_rate": empirical,
                                 "static_success_rate": configured,
                                 "divergence": divergence})
        return findings
    finally:
        if owned:
            db.close()


def _proposal_text(finding: dict, roles_path: str, corpus_path: str) -> str:
    direction = "increase" if finding["divergence"] > 0 else "decrease"
    return f"""# Living charter proposal: {finding['harness']} / {finding['task_domain']}

This proposal is intentionally reviewable and does not modify a charter automatically.

- Model: `{finding['model_id']}`
- Harness: `{finding['harness']}`
- Domain: `{finding['task_domain']}`
- Empirical success rate: {finding['empirical_success_rate']:.1%}
- Static charter rate: {finding['static_success_rate']:.1%}
- Divergence: {finding['divergence']:+.1%}
- Observations: {finding['observations']}

Recommendation: **{direction}** the role's stated capability for this domain after
human review. Update `{roles_path}` and record the evidence in `{corpus_path}`.
"""


def cmd_charters_adapt(*, conn=None, threshold: float = 0.25, dry_run: bool = True,
                       proposals_dir: str = ".synlynk/charter-proposals",
                       roles_path: str = ".synlynk/roles.yaml",
                       corpus_path: str = "docs/charters/corpus-references.md") -> list[dict]:
    """Detect drift and emit one markdown proposal per divergent capability."""
    findings = detect_charter_divergence(conn, threshold=threshold)
    for finding in findings:
        finding["proposal"] = _proposal_text(finding, roles_path, corpus_path)
        if not dry_run:
            destination = Path(proposals_dir) / (
                f"{finding['harness']}-{finding['task_domain']}-{finding['model_id']}.md".replace("/", "-"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(finding["proposal"])
        print(f"{finding['harness']}/{finding['task_domain']}: "
              f"{finding['empirical_success_rate']:.1%} vs {finding['static_success_rate']:.1%} "
              f"({finding['divergence']:+.1%})")
    if not findings:
        print("No charter capability drift above the threshold.")
    return findings
