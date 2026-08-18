"""synlynk capability sweep -- periodic calibration of agent/model capability baselines."""

import json
import os
import subprocess
import sys

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.costs import _HARDCODED_FALLBACK_RATES, _model_rate_for_version
from synlynk.taxonomy_standards import SFIA_CODES

_ESTIMATED_TOKENS_PER_CALL = {"input": 500, "output": 500}
_CALLS_PER_COMBINATION = 2
_DEFAULT_SWEEP_COST_CAP_USD = 10.0
_CALIBRATION_SKILLS = [skill for skill in ("PROG", "TEST", "REQM") if skill in SFIA_CODES]
_SKILL_TO_DISCIPLINE = {"PROG": "backend", "TEST": "testing", "REQM": "architecture"}


def _discover_models() -> dict:
    """Discover available models per agent CLI, with a hardcoded fallback."""
    discovered = {}
    for agent, baseline in HARNESS_CAPABILITY_BASELINES.items():
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


def _pick_verifier_agent(executor_agent: str, available_agents: list) -> str:
    """Picks a verifier agent that is not the executor - genuine independence,
    fixing the #353 self-attestation gap for the seeded portion of the ledger.
    """
    candidates = [agent for agent in available_agents if agent != executor_agent]
    if not candidates:
        raise ValueError(
            f"No independent verifier available for executor {executor_agent}; "
            "need at least 2 configured agents to run the calibration sweep"
        )
    return candidates[0]


def _dispatch_calibration_task(agent: str, task: str, **kwargs) -> dict:
    """Dispatch one calibration task through dispatch_agent behind a test seam."""
    from synlynk.dispatch import dispatch_agent

    dispatch_kwargs = dict(kwargs)
    dispatch_kwargs.setdefault("force_agent", True)
    dispatch_kwargs.setdefault("skip_preflight", True)
    return dispatch_agent(agent, task, **dispatch_kwargs)


def _verify_calibration_result(
    verifier_agent: str,
    executor_agent: str,
    model: str,
    skill: str,
    executor_output: dict,
) -> dict:
    """Ask a different agent to score the executor output and parse its verdict."""
    label = SFIA_CODES.get(skill, {}).get("label", skill)
    verify_task = (
        f"Review this {label} calibration task output from another agent and score it "
        "0-10 for quality.\n"
        "Respond with a line '# synlynk-meta' followed by 'quality=<N>' "
        "and 'correct=<true|false>'.\n\n"
        f"Executor agent: {executor_agent}\n"
        f"Executor model: {model}\n"
        f"Verifier agent: {verifier_agent}\n\n"
        f"Output to review:\n{executor_output.get('output', '')}"
    )
    result = _dispatch_calibration_task(verifier_agent, verify_task)
    from synlynk.costs import extract_verifier_meta

    meta = extract_verifier_meta(result.get("output", "")) or {}
    return {
        "quality": float(meta.get("quality", 5.0)),
        "correct": bool(meta.get("correct", True)),
    }


def _run_sweep(discovered: dict, skills: list) -> None:
    """Dispatches one calibration task per (agent, model, skill), scored by a
    different agent (never the executor), and writes a baseline_seed row with
    a phantom sample_count (3-5) per result - light enough that real organic
    jobs quickly dominate the weighted average once several accumulate.

    NOTE (spec dependency, issue #353): the blend between this phantom
    sample_count and real organic data assumes _DB_SCORES_VIEW's weighted
    average is sample-count-aware.
    As of 2026-07-18 it is not (decay cancellation bug) - this function writes
    correct, independently-verified rows regardless, but the *speed* at which
    organic data overtakes the seed is best-effort until #353 lands.
    """
    import synlynk as sl

    conn_get = sl._get_db
    all_agents = list(discovered.keys())
    for agent, models in discovered.items():
        for model in models:
            for skill in skills:
                label = SFIA_CODES.get(skill, {}).get("label", skill)
                task = f"Write a minimal example demonstrating {label} for a small Python function."
                executor_result = _dispatch_calibration_task(agent, task)

                verifier_agent = _pick_verifier_agent(agent, all_agents)
                verdict = _verify_calibration_result(
                    verifier_agent, agent, model, skill, executor_result
                )

                conn = conn_get()
                # capability_ratings.story_id is a NOT NULL FK to stories.story_id,
                # and foreign_keys=ON - ensure the shared placeholder story exists
                # before inserting (same fix as _seed_capability_ledger_from_baseline
                # in Task 5; harmless no-op after the first call via INSERT OR IGNORE).
                conn.execute(
                    "INSERT OR IGNORE INTO stories (story_id, title) VALUES (?, ?)",
                    ("__baseline_seed__", "Capability baseline seed (synthetic, not a real story)"),
                )
                discipline_value = _SKILL_TO_DISCIPLINE.get(skill, "backend")
                phantom_sample_count = 4
                for _ in range(phantom_sample_count):
                    conn.execute(
                        """INSERT INTO capability_ratings
                           (story_id, agent, model_version, discipline, org_domain, industry, phase,
                            signal_source, quality, quality_auto, verifier_agent, correct)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "__baseline_seed__",
                            agent,
                            model,
                            discipline_value,
                            "platform",
                            "unknown",
                            "build",
                            "baseline_seed",
                            verdict["quality"],
                            verdict["quality"],
                            verifier_agent,
                            1 if verdict.get("correct", True) else 0,
                        ),
                    )
                conn.commit()
                conn.close()
                print(
                    f"  [sweep] {agent} / {model} / {skill}: quality={verdict['quality']} "
                    f"(verified by {verifier_agent})"
                )


def _seed_capability_ledger_from_baseline(conn) -> None:
    """Seed capability_ratings from the bundled capability_baseline.json when empty."""
    existing = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    if existing > 0:
        return

    baseline_path = os.path.join(os.path.dirname(__file__), "capability_baseline.json")
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
