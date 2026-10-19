"""Universal Pre-Flight Routing Engine.

Evaluates task descriptions, classifies them into SFIA 8/9 skill disciplines,
and consults the empirical capability matrix to recommend the optimal harness
and model variants for execution, failover, and budget optimization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from synlynk import _CYAN, _GREEN, _RED, _RESET, _YELLOW
from synlynk.sfia import classify_task_sfia, get_sfia_name

COMPLEXITY_KEYWORDS_HIGH = {
    "race condition", "deadlock", "concurrency", "distributed", "migration",
    "architecture", "refactor", "async", "lock", "consensus", "protocol",
    "circuit breaker", "memory leak", "scalability", "security vulnerability"
}

COMPLEXITY_KEYWORDS_LOW = {
    "typo", "readme", "comment", "docstring", "lint", "formatting",
    "rename", "bump version", "fix spelling", "clean up"
}


def estimate_task_complexity(prompt: str) -> str:
    """Classify prompt into low, medium, or complex execution tier."""
    lower = prompt.lower()
    for kw in COMPLEXITY_KEYWORDS_HIGH:
        if kw in lower:
            return "complex"

    for kw in COMPLEXITY_KEYWORDS_LOW:
        if kw in lower:
            return "low"

    if len(prompt) > 250:
        return "complex"
    if len(prompt) < 25:
        return "low"

    return "medium"


def _select_candidate(
    candidates: List[Dict[str, Any]],
    optimize_for: str = "balanced",
    exclude_harnesses: Optional[set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Rank candidates according to user optimization preference."""
    pool = [c for c in candidates if not exclude_harnesses or c.get("harness") not in exclude_harnesses]
    if not pool:
        return None

    if optimize_for == "quality":
        return sorted(pool, key=lambda c: (not c.get("unmeasured", False), c.get("quality_score", 0.0)), reverse=True)[0]
    elif optimize_for == "cost":
        return sorted(pool, key=lambda c: (not c.get("unmeasured", False), c.get("cost_per_verified_fix_usd", 999.0), -c.get("quality_score", 0.0)))[0]
    elif optimize_for == "quota":
        return sorted(pool, key=lambda c: (c.get("failover_risk") != "high", not c.get("unmeasured", False), c.get("quality_score", 0.0)), reverse=True)[0]
    else:  # balanced
        def balanced_score(c):
            q = c.get("quality_score", 0.0)
            cost = max(0.01, c.get("cost_per_verified_fix_usd", 0.50))
            unmeas = 0 if c.get("unmeasured", False) else 1
            risk_penalty = 0.8 if c.get("failover_risk") == "high" else 1.0
            return (unmeas, (q / cost) * risk_penalty)

        return sorted(pool, key=balanced_score, reverse=True)[0]


def evaluate_preflight(
    prompt: str,
    pack: Dict[str, Any],
    preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate task prompt and return multi-vendor routing recommendations."""
    prefs = preferences or {}
    optimize_for = prefs.get("optimize_for", "balanced")
    available_harnesses = set(prefs.get("available_harnesses") or ["claude", "codex", "grok", "agy", "local"])

    # SFIA Classification
    sfia_code, domain, confidence = classify_task_sfia(prompt)
    if sfia_code == "UNAN":
        sfia_code = "PROG"
        confidence = 0.50

    sfia_name = get_sfia_name(sfia_code)
    complexity = estimate_task_complexity(prompt)

    matrix = pack.get("matrix", {})
    candidates = matrix.get(sfia_code) or matrix.get("PROG") or []

    # Filter to available harnesses if specified
    if available_harnesses:
        filtered = [c for c in candidates if c.get("harness") in available_harnesses]
        if filtered:
            candidates = filtered

    recommendations: Dict[str, Any] = {}

    if candidates:
        # 1. Primary Recommendation
        primary = _select_candidate(candidates, optimize_for=optimize_for)
        if primary:
            recommendations["primary"] = dict(primary)

        # 2. Failover Recommendation (different harness with low failover risk)
        primary_harness = primary.get("harness") if primary else None
        failover = _select_candidate(
            candidates,
            optimize_for="quota",
            exclude_harnesses={primary_harness} if primary_harness else None,
        )
        if failover:
            recommendations["failover"] = dict(failover)

        # 3. Budget Champion (lowest cost)
        budget = _select_candidate(candidates, optimize_for="cost")
        if budget:
            recommendations["budget"] = dict(budget)
    else:
        # Fallback default if matrix is empty
        recommendations["primary"] = {
            "harness": "codex",
            "model": "default",
            "quality_score": 8.0,
            "cost_per_verified_fix_usd": 0.25,
            "median_review_cycles": 1.0,
            "sample_size": 0,
            "unmeasured": True,
            "failover_risk": "low",
        }

    # Quota advisory lookup
    pack_advisories = pack.get("quota_advisories", {})
    active_advisories = {}
    for h in [recommendations.get(k, {}).get("harness") for k in ["primary", "failover", "budget"]]:
        if h and h in pack_advisories:
            active_advisories[h] = pack_advisories[h]

    return {
        "task_classification": {
            "sfia_code": sfia_code,
            "sfia_name": sfia_name,
            "complexity": complexity,
            "confidence": round(confidence, 2),
        },
        "recommendations": recommendations,
        "quota_advisory": active_advisories,
        "snapshot_metadata": pack.get("snapshot_metadata", {
            "snapshot_id": "ephemeral",
            "sha256": "unknown",
            "signature_verified": False,
        }),
        "cta": pack.get("cta", {
            "message": "Automate multi-agent routing, verification, and quota failovers in your codebase with Synlynk",
            "install_cmd": "brew install synlynk",
            "vscode_url": "https://marketplace.visualstudio.com/items?itemName=synlynk.synlynk-vscode",
        }),
    }


def cmd_preflight(
    prompt: str,
    optimize_for: str = "balanced",
    as_json: bool = False,
    pack_path: Optional[str] = None,
) -> None:
    """CLI runner for synlynk preflight."""
    from synlynk import _get_db
    from synlynk.capability_pack import export_capability_pack

    if pack_path and Path(pack_path).exists():
        pack = json.loads(Path(pack_path).read_text(encoding="utf-8"))
    else:
        conn = _get_db()
        pack = export_capability_pack(conn)

    result = evaluate_preflight(
        prompt=prompt,
        pack=pack,
        preferences={"optimize_for": optimize_for},
    )

    if as_json:
        print(json.dumps(result, indent=2))
        return

    cls = result["task_classification"]
    recs = result["recommendations"]

    print(f"\n{_CYAN}=== Synaptic AI Pre-Flight Oracle ==={_RESET}")
    print(f"Task: \"{prompt}\"")
    print(f"Discipline:  {_GREEN}{cls['sfia_code']}{_RESET} — {cls['sfia_name']} (Confidence: {cls['confidence'] * 100:.0f}%)")
    print(f"Complexity:  {_YELLOW}{cls['complexity'].upper()}{_RESET}")
    print(f"Optimizing:  {optimize_for}\n")

    print(f"{_CYAN}Recommendations:{_RESET}")
    if "primary" in recs:
        p = recs["primary"]
        unmeas = f" {_YELLOW}[Unmeasured]{_RESET}" if p.get("unmeasured") else ""
        print(f"  ★ {_GREEN}Primary Pick:{_RESET}     {p['harness']} ({p['model']}){unmeas}")
        print(f"    Quality: {p['quality_score']}/10.0 | Cost: ${p['cost_per_verified_fix_usd']:.2f}/fix | Cycles: {p['median_review_cycles']} (n={p['sample_size']})")

    if "failover" in recs:
        f = recs["failover"]
        print(f"  ⟳ {_YELLOW}Failover Pick:{_RESET}    {f['harness']} ({f['model']})")
        print(f"    Quality: {f['quality_score']}/10.0 | Cost: ${f['cost_per_verified_fix_usd']:.2f}/fix (Low rate-limit risk)")

    if "budget" in recs:
        b = recs["budget"]
        print(f"  $ {_GREEN}Budget Pick:{_RESET}      {b['harness']} ({b['model']})")
        print(f"    Quality: {b['quality_score']}/10.0 | Cost: ${b['cost_per_verified_fix_usd']:.2f}/fix")

    advisories = result.get("quota_advisory", {})
    if advisories:
        print(f"\n{_YELLOW}Quota Advisory:{_RESET}")
        for h, adv in advisories.items():
            print(f"  • {h}: {adv}")

    print(f"\n{_CYAN}Automate in your repo:{_RESET} {result['cta']['install_cmd']} | {result['cta']['vscode_url']}\n")
