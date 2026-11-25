"""Goal-cohesive release packaging policy helpers."""

from synlynk.policy import load_policy


DEFAULT_LIMITS = {
    "goal_story_ceiling": 30,
    "goal_token_ceiling": 1_500_000,
    "mixed_pool_cap": 5,
}


def load_limits(repo_path: str) -> dict[str, int]:
    """Load release-packaging ceilings, preserving defaults for sparse overrides."""
    configured = load_policy(repo_path).get("release_packaging", {})
    merged = {**DEFAULT_LIMITS, **configured}
    return {key: int(value) for key, value in merged.items()}
