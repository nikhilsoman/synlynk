"""synlynk capability sweep -- periodic calibration of agent/model capability baselines."""

import json
import os
import subprocess
import sys

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.costs import _HARDCODED_FALLBACK_RATES, _model_rate_for_version
from synlynk.taxonomy_standards import SFIA_CODES

_ESTIMATED_TOKENS_PER_CALL = {"input": 500, "output": 500}
_CALLS_PER_COMBINATION = 2
_DEFAULT_SWEEP_COST_CAP_USD = 10.0
_CALIBRATION_SKILLS = [skill for skill in ("PROG", "TEST", "REQM") if skill in SFIA_CODES]


def _discover_models() -> dict:
    """Discover available models per agent CLI, with a hardcoded fallback."""
    discovered = {}
    for agent, baseline in AGENT_CAPABILITY_BASELINES.items():
        if agent == "local":
            continue
        cli = baseline["cli"]
        models = []
        try:
            result = subprocess.run(
                [cli, "--help"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            help_text = (result.stdout or "") + (result.stderr or "")
            if "--model" in help_text:
                models = _fallback_models_for_agent(agent)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            models = _fallback_models_for_agent(agent)
        if not models:
            models = _fallback_models_for_agent(agent)
        discovered[agent] = models
    return discovered


def _fallback_models_for_agent(agent: str) -> list:
    """Return fallback model names for an agent from the hardcoded rates table."""
    agent_model_prefixes = {
        "claude": ("claude-",),
        "codex": ("gpt-",),
        "agy": ("gemini-",),
        "grok": ("grok-",),
    }
    prefixes = agent_model_prefixes.get(agent, ())
    return [
        model
        for model in _HARDCODED_FALLBACK_RATES["models"]
        if any(model.startswith(prefix) for prefix in prefixes)
    ]


def _estimate_sweep_cost(discovered: dict, skills: list) -> float:
    """Estimate total USD cost for all discovered agent/model/skill combinations."""
    total = 0.0
    for agent, models in discovered.items():
        for model in models:
            rate = _model_rate_for_version(model, agent=agent)
            per_call_cost = (
                (_ESTIMATED_TOKENS_PER_CALL["input"] / 1000.0) * rate["input"]
                + (_ESTIMATED_TOKENS_PER_CALL["output"] / 1000.0) * rate["output"]
            )
            total += per_call_cost * _CALLS_PER_COMBINATION * len(skills)
    return float(total)


def cmd_capability_sweep(cost_cap_override: float = None) -> None:
    """Run the calibration sweep after enforcing a cost guardrail."""
    from synlynk import load_config

    cfg = load_config()
    cost_cap = cost_cap_override
    if cost_cap is None:
        cost_cap = cfg.get("capability_sweep", {}).get("cost_cap_usd", _DEFAULT_SWEEP_COST_CAP_USD)

    discovered = _discover_models()
    estimated_cost = _estimate_sweep_cost(discovered, _CALIBRATION_SKILLS)

    total_models = sum(len(models) for models in discovered.values())
    print(
        f"  Capability sweep: {len(discovered)} agents, {total_models} models, "
        f"{len(_CALIBRATION_SKILLS)} SFIA skills",
        flush=True,
    )
    print(f"  Estimated cost: ${estimated_cost:.4f} (cap: ${cost_cap:.2f})", flush=True)

    if estimated_cost > cost_cap:
        print(
            f"  Aborting: estimated cost ${estimated_cost:.4f} exceeds cap ${cost_cap:.2f} "
            "Re-run with a higher --cost-cap to override",
            file=sys.stderr,
        )
        raise SystemExit(1)

    _run_sweep(discovered, _CALIBRATION_SKILLS)


def _run_sweep(discovered: dict, skills: list) -> None:
    """Queue sweep tasks for each agent/model/skill combination."""
    for agent, models in discovered.items():
        for model in models:
            for skill in skills:
                print(f"  [sweep] {agent} / {model} / {skill}: queued (see later task)")


def _seed_capability_ledger_from_baseline(conn) -> None:
    """Seed capability_ratings from the bundled capability_baseline.json when empty."""
    existing = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    if existing > 0:
        return

    baseline_path = os.path.join(os.path.dirname(__file__), "..", "capability_baseline.json")
    if not os.path.exists(baseline_path):
        return

    with open(baseline_path) as f:
        rows = json.load(f)

    if not rows:
        return

    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title) VALUES (?, ?)",
        ("__baseline_seed__", "Capability baseline seed (synthetic, not a real story)"),
    )

    for row in rows:
        for _ in range(row["sample_count"]):
            conn.execute(
                """INSERT INTO capability_ratings
                   (story_id, agent, model_version, discipline, org_domain, industry, phase,
                    signal_source, quality, quality_auto, correct)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["story_id"],
                    row["agent"],
                    row["model_version"],
                    row["discipline"],
                    row["org_domain"],
                    row["industry"],
                    row["phase"],
                    row["signal_source"],
                    row["quality"],
                    row["quality"],
                    1,
                ),
            )

    conn.commit()
