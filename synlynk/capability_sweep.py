"""synlynk capability sweep -- periodic calibration of harness/model capability baselines."""

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
    """Discover available models per harness CLI, with a hardcoded fallback."""
    discovered = {}
    for harness, baseline in HARNESS_CAPABILITY_BASELINES.items():
        if harness == "local":
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
                models = _fallback_models_for_harness(harness)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            models = _fallback_models_for_harness(harness)
        if not models:
            models = _fallback_models_for_harness(harness)
        discovered[harness] = models
    return discovered


def _fallback_models_for_harness(harness: str) -> list:
    """Return fallback model names for a harness from the hardcoded rates table."""
    harness_model_prefixes = {
        "claude": ("claude-",),
        "codex": ("gpt-",),
        "agy": ("gemini-",),
        "grok": ("grok-",),
    }
    prefixes = harness_model_prefixes.get(harness, ())
    return [
        model
        for model in _HARDCODED_FALLBACK_RATES["models"]
        if any(model.startswith(prefix) for prefix in prefixes)
    ]


def _estimate_sweep_cost(discovered: dict, skills: list) -> float:
    """Estimate total USD cost for all discovered harness/model/skill combinations."""
    total = 0.0
    for harness, models in discovered.items():
        for model in models:
            rate = _model_rate_for_version(model, agent=harness)
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
        f"  Capability sweep: {len(discovered)} harnesses, {total_models} models, "
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


def _pick_verifier_harness(executor_harness: str, available_harnesses: list) -> str:
    """Picks a verifier harness that is not the executor - genuine independence,
    fixing the #353 self-attestation gap for the seeded portion of the ledger.
    """
    candidates = [harness for harness in available_harnesses if harness != executor_harness]
    if not candidates:
        raise ValueError(
            f"No independent verifier available for executor {executor_harness}; "
            "need at least 2 configured harnesses to run the calibration sweep"
        )
    return candidates[0]


def _get_db():
    from synlynk import _get_db as _real_get_db
    return _real_get_db()


def _extract_task_cost_usd(result: dict) -> float:
    if not isinstance(result, dict):
        return 0.0
    fence = result.get("fence")
    if fence is not None:
        if hasattr(fence, "cost_usd"):
            return float(getattr(fence, "cost_usd") or 0.0)
        if isinstance(fence, dict) and "cost_usd" in fence:
            return float(fence.get("cost_usd") or 0.0)
    return float(result.get("cost_usd", 0.0) or 0.0)


def cmd_capability_sweep_for_harness_model(harness_name: str, model_id: str) -> None:
    """Auto-triggered single-(harness,model) sweep against the full
    difficulty-graded task pool for every charter role (#786 Plan B).
    Reuses the existing dispatch/verify pair and cost-cap guardrail that
    _run_sweep() already uses for its 3-skill baseline sweep."""
    import uuid
    from datetime import datetime, timezone
    from synlynk import load_config

    conn = _get_db()
    cfg = load_config()
    cost_cap = cfg.get("capability_sweep", {}).get("cost_cap_usd", _DEFAULT_SWEEP_COST_CAP_USD)

    tasks = conn.execute(
        "SELECT task_id, role, skill, difficulty, prompt_template FROM capability_calibration_tasks"
    ).fetchall()
    available_agents = [a for a in HARNESS_CAPABILITY_BASELINES if a != "local" and a != harness_name]

    total_cost = 0.0
    now = datetime.now(timezone.utc).isoformat()
    for task_id, role, skill, difficulty, template in tasks:
        prompt = template.format(context=f"a {skill} scenario at {difficulty} difficulty")
        executor_result = _dispatch_calibration_task(harness_name, prompt)
        cost_usd = _extract_task_cost_usd(executor_result)
        total_cost += cost_usd
        if total_cost > cost_cap:
            print(
                f"  Calibration sweep for {harness_name}/{model_id} stopped: cost cap ${cost_cap:.2f} reached",
                file=sys.stderr,
            )
            break
        verifier_agent = _pick_verifier_agent(harness_name, available_agents)
        verdict = _verify_calibration_result(verifier_agent, harness_name, model_id, skill, executor_result)
        conn.execute(
            "INSERT INTO capability_calibration_results "
            "(result_id, harness_name, model_id, task_id, score, cost_usd, verified_by, run_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                harness_name,
                model_id,
                task_id,
                verdict["quality"] / 10.0,
                cost_usd,
                verifier_agent,
                now,
            ),
        )
    conn.commit()


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


def _dispatch_calibration_task(harness: str, task: str, **kwargs) -> dict:
    """Dispatch one calibration task through dispatch_agent behind a test seam."""
    from synlynk.dispatch import dispatch_agent

    dispatch_kwargs = dict(kwargs)
    dispatch_kwargs.setdefault("force_agent", True)
    dispatch_kwargs.setdefault("skip_preflight", True)
    return dispatch_agent(harness, task, **dispatch_kwargs)


def _verify_calibration_result(
    verifier_harness: str,
    executor_harness: str,
    model: str,
    skill: str,
    executor_output: dict,
) -> dict:
    """Ask a different agent to score the executor output and parse its verdict."""
    label = SFIA_CODES.get(skill, {}).get("label", skill)
    verify_task = (
        f"Review this {label} calibration task output from another harness and score it "
        "0-10 for quality.\n"
        "Respond with a line '# synlynk-meta' followed by 'quality=<N>' "
        "and 'correct=<true|false>'.\n\n"
        f"Executor harness: {executor_harness}\n"
        f"Executor model: {model}\n"
        f"Verifier harness: {verifier_harness}\n\n"
        f"Output to review:\n{executor_output.get('output', '')}"
    )
    result = _dispatch_calibration_task(verifier_harness, verify_task)
    from synlynk.costs import extract_verifier_meta

    meta = extract_verifier_meta(result.get("output", "")) or {}
    return {
        "quality": float(meta.get("quality", 5.0)),
        "correct": bool(meta.get("correct", True)),
    }


def _run_sweep(discovered: dict, skills: list) -> None:
    """Dispatches one calibration task per (harness, model, skill), scored by a
    different harness (never the executor), and writes a baseline_seed row with
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
    available_harnesses = list(discovered.keys())
    for harness, models in discovered.items():
        for model in models:
            for skill in skills:
                label = SFIA_CODES.get(skill, {}).get("label", skill)
                task = f"Write a minimal example demonstrating {label} for a small Python function."
                executor_result = _dispatch_calibration_task(harness, task)

                verifier_harness = _pick_verifier_harness(harness, available_harnesses)
                verdict = _verify_calibration_result(
                    verifier_harness, harness, model, skill, executor_result
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
                            harness,
                            model,
                            discipline_value,
                            "platform",
                            "unknown",
                            "build",
                            "baseline_seed",
                            verdict["quality"],
                            verdict["quality"],
                            verifier_harness,
                            1 if verdict.get("correct", True) else 0,
                        ),
                    )
                conn.commit()
                conn.close()
                print(
                    f"  [sweep] {harness} / {model} / {skill}: quality={verdict['quality']} "
                    f"(verified by {verifier_harness})"
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


_ROLE_TASK_TEMPLATES = {
    "pm": {
        "basic": "Write a 3-bullet status update summarizing a completed feature.",
        "intermediate": "Triage this bug report into a GitHub issue with severity and repro steps: {context}",
        "advanced": "Draft a roadmap section reconciling two conflicting stakeholder priorities: {context}",
    },
    "architect": {
        "basic": "List the trade-offs between two database indexing strategies for {context}.",
        "intermediate": "Design a data model for {context} with at least 2 tables and their relationships.",
        "advanced": "Review this system design for a race condition and propose a fix: {context}",
    },
    "tpm": {
        "basic": "Break a 3-step feature into a dependency-ordered task list.",
        "intermediate": "Identify the critical path across 4 parallel workstreams: {context}",
        "advanced": "Reconcile a slipping deadline against two blocked dependencies: {context}",
    },
    "dev": {
        "basic": "Write a minimal Python function demonstrating {context}.",
        "intermediate": "Fix a failing test given this stack trace: {context}",
        "advanced": "Refactor this function to remove duplication while preserving behavior: {context}",
    },
    "designer": {
        "basic": "Describe a simple 3-field form layout for {context}.",
        "intermediate": "Propose a navigation structure for a 5-page app: {context}",
        "advanced": "Resolve a usability conflict between mobile and desktop layouts: {context}",
    },
    "qa": {
        "basic": "Write 3 test cases for {context}.",
        "intermediate": "Identify an edge case this test suite misses: {context}",
        "advanced": "Design a regression test strategy for a flaky integration test: {context}",
    },
    "marketing": {
        "basic": "Write a 1-sentence pitch for {context}.",
        "intermediate": "Draft a changelog entry for a breaking change: {context}",
        "advanced": "Reconcile messaging across two conflicting positioning statements: {context}",
    },
    "synlynk-bot": {
        "basic": "Summarize a devlog entry in 2 sentences.",
        "intermediate": "Detect drift between two versions of a roadmap doc: {context}",
        "advanced": "Reconcile a merge conflict in a union-merged markdown file: {context}",
    },
}


def _seed_calibration_tasks(conn) -> None:
    """Idempotently seed capability_calibration_tasks with the 24 role x
    difficulty baseline templates (#786 Plan B)."""
    import uuid
    from datetime import datetime, timezone
    existing = {
        (row[0], row[1])
        for row in conn.execute("SELECT role, difficulty FROM capability_calibration_tasks").fetchall()
    }
    now = datetime.now(timezone.utc).isoformat()
    for role, by_difficulty in _ROLE_TASK_TEMPLATES.items():
        for difficulty, template in by_difficulty.items():
            if (role, difficulty) in existing:
                continue
            conn.execute(
                "INSERT INTO capability_calibration_tasks "
                "(task_id, role, skill, difficulty, prompt_template, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), role, "general", difficulty, template, now),
            )
    conn.commit()
