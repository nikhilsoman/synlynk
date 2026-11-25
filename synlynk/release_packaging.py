"""Goal-cohesive release packaging policy helpers."""

from dataclasses import dataclass
from typing import Iterable, Optional

from synlynk.policy import load_policy


DEFAULT_LIMITS = {
    "goal_story_ceiling": 30,
    "goal_token_ceiling": 1_500_000,
    "mixed_pool_cap": 5,
}

DEFAULT_STORY_TOKENS = 25_000


@dataclass
class PackagePlan:
    """A pure release partition plus the metadata needed to explain it."""

    parts: list[list[str]]
    context: list[str]
    escalation: Optional[str]
    split_reasons: list[str]
    total_stories: int
    total_tokens: int
    limits: dict
    part_stats: list[dict]


def load_limits(repo_path: str) -> dict[str, int]:
    """Load release-packaging ceilings, preserving defaults for sparse overrides."""
    configured = load_policy(repo_path).get("release_packaging", {})
    merged = {**DEFAULT_LIMITS, **configured}
    return {key: int(value) for key, value in merged.items()}


def _story_tokens(story: dict) -> int:
    return int(story.get("estimated_tokens") or DEFAULT_STORY_TOKENS)


def _exceeds_limits(stories: list[dict], limits: dict) -> bool:
    return len(stories) > int(limits["goal_story_ceiling"]) or sum(
        _story_tokens(story) for story in stories
    ) > int(limits["goal_token_ceiling"])


def _part_stats(parts: list[list[str]], stories_by_id: dict[str, dict]) -> list[dict]:
    return [
        {
            "stories": len(part),
            "tokens": sum(_story_tokens(stories_by_id[story_id]) for story_id in part),
        }
        for part in parts
    ]


def _has_cycle(story_ids: set[str], edges: set[tuple[str, str]]) -> bool:
    dependencies: dict[str, list[str]] = {story_id: [] for story_id in story_ids}
    for story_id, depends_on_story_id in edges:
        dependencies[story_id].append(depends_on_story_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(story_id: str) -> bool:
        if story_id in visiting:
            return True
        if story_id in visited:
            return False
        visiting.add(story_id)
        if any(visit(dependency) for dependency in dependencies[story_id]):
            return True
        visiting.remove(story_id)
        visited.add(story_id)
        return False

    return any(visit(story_id) for story_id in sorted(story_ids))


def _dependency_components(
    stories: list[dict], edges: set[tuple[str, str]]
) -> list[list[dict]]:
    stories_by_id = {story["story_id"]: story for story in stories}
    neighbours: dict[str, set[str]] = {
        story_id: set() for story_id in stories_by_id
    }
    for story_id, depends_on_story_id in edges:
        if story_id in neighbours and depends_on_story_id in neighbours:
            neighbours[story_id].add(depends_on_story_id)
            neighbours[depends_on_story_id].add(story_id)

    remaining = set(stories_by_id)
    components: list[list[dict]] = []
    while remaining:
        first = min(remaining)
        pending = [first]
        component_ids: set[str] = set()
        while pending:
            story_id = pending.pop()
            if story_id in component_ids:
                continue
            component_ids.add(story_id)
            pending.extend(neighbours[story_id] - component_ids)
        remaining -= component_ids
        components.append(
            [stories_by_id[story_id] for story_id in sorted(component_ids)]
        )
    return components


def _split_approved_phase(
    stories: list[dict], edges: set[tuple[str, str]], limits: dict
) -> Optional[list[list[str]]]:
    components = _dependency_components(stories, edges)
    if any(_exceeds_limits(component, limits) for component in components):
        return None

    parts: list[list[str]] = []
    current: list[dict] = []
    for component in components:
        if current and _exceeds_limits(current + component, limits):
            parts.append([story["story_id"] for story in current])
            current = []
        current.extend(component)
    if current:
        parts.append([story["story_id"] for story in current])
    return parts


def _escalation_plan(
    reason: str,
    context: list[str],
    total_stories: int,
    total_tokens: int,
    limits: dict,
) -> PackagePlan:
    return PackagePlan(
        parts=[],
        context=context,
        escalation=reason,
        split_reasons=[],
        total_stories=total_stories,
        total_tokens=total_tokens,
        limits=limits,
        part_stats=[],
    )


def plan_goal_release(
    stories,
    deps: Iterable[tuple[str, str]],
    limits,
    approved_splits=frozenset(),
    independent_phases: bool = False,
) -> PackagePlan:
    """Plan goal stories without database access or silent truncation."""
    limits = dict(limits)
    context_stories = [
        story
        for story in stories
        if story.get("status") == "in_progress"
        or bool(story.get("umbrella"))
        or bool(story.get("has_open_pr"))
    ]
    packageable = [story for story in stories if story not in context_stories]
    context = [story["story_id"] for story in context_stories]
    total_stories = len(packageable)
    total_tokens = sum(_story_tokens(story) for story in packageable)
    stories_by_id = {story["story_id"]: story for story in packageable}
    all_story_ids = {story["story_id"] for story in stories}
    edges = {
        (story_id, depends_on_story_id)
        for story_id, depends_on_story_id in deps
        if story_id in all_story_ids and depends_on_story_id in all_story_ids
    }

    def build(parts: list[list[str]], split_reasons: list[str]) -> PackagePlan:
        return PackagePlan(
            parts=parts,
            context=context,
            escalation=None,
            split_reasons=split_reasons,
            total_stories=total_stories,
            total_tokens=total_tokens,
            limits=limits,
            part_stats=_part_stats(parts, stories_by_id),
        )

    if not packageable:
        return build([[]], [])

    missing_phase = any(story.get("phase") in (None, "", "build") for story in packageable)
    phases: dict[str, list[dict]] = {}
    if not missing_phase:
        for story in packageable:
            phases.setdefault(story["phase"], []).append(story)

    if independent_phases:
        if missing_phase:
            return _escalation_plan(
                "no phase data", context, total_stories, total_tokens, limits
            )
        independent_parts: list[list[str]] = []
        split_reasons: list[str] = []
        previous_phase: Optional[str] = None
        for phase in sorted(phases):
            phase_stories = phases[phase]
            if _exceeds_limits(phase_stories, limits):
                if phase not in approved_splits:
                    return _escalation_plan(
                        "phase exceeds ceiling; operator confirmation required",
                        context,
                        total_stories,
                        total_tokens,
                        limits,
                    )
                phase_parts = _split_approved_phase(phase_stories, edges, limits)
                if phase_parts is None:
                    return _escalation_plan(
                        "approved phase cannot be split without severing dependency",
                        context,
                        total_stories,
                        total_tokens,
                        limits,
                    )
            else:
                phase_parts = [[story["story_id"] for story in phase_stories]]

            if independent_parts:
                split_reasons.append(
                    f"independent phases {previous_phase} -> {phase}"
                )
            independent_parts.append(phase_parts[0])
            for phase_part in phase_parts[1:]:
                split_reasons.append(f"operator-approved split within phase {phase}")
                independent_parts.append(phase_part)
            previous_phase = phase
        return build(independent_parts, split_reasons)

    if not _exceeds_limits(packageable, limits):
        return build([[story["story_id"] for story in packageable]], [])

    if _has_cycle(all_story_ids, edges):
        return _escalation_plan(
            "cyclic dependency", context, total_stories, total_tokens, limits
        )
    if missing_phase:
        return _escalation_plan(
            "no phase data", context, total_stories, total_tokens, limits
        )

    parts: list[list[str]] = []
    split_reasons: list[str] = []
    current_stories: list[dict] = []
    current_last_phase: Optional[str] = None

    for phase in sorted(phases):
        phase_stories = phases[phase]
        if _exceeds_limits(phase_stories, limits):
            if phase not in approved_splits:
                return _escalation_plan(
                    "phase exceeds ceiling; operator confirmation required",
                    context,
                    total_stories,
                    total_tokens,
                    limits,
                )
            phase_parts = _split_approved_phase(phase_stories, edges, limits)
            if phase_parts is None:
                return _escalation_plan(
                    "approved phase cannot be split without severing dependency",
                    context,
                    total_stories,
                    total_tokens,
                    limits,
                )
            if current_stories:
                parts.append([story["story_id"] for story in current_stories])
                split_reasons.append(
                    f"phase boundary {current_last_phase} -> {phase}"
                )
                current_stories = []
            elif parts:
                split_reasons.append(
                    f"phase boundary {current_last_phase} -> {phase}"
                )
            parts.append(phase_parts[0])
            for phase_part in phase_parts[1:]:
                split_reasons.append(f"operator-approved split within phase {phase}")
                parts.append(phase_part)
            current_last_phase = phase
            continue

        if current_stories and _exceeds_limits(current_stories + phase_stories, limits):
            parts.append([story["story_id"] for story in current_stories])
            split_reasons.append(
                f"phase boundary {current_last_phase} -> {phase}"
            )
            current_stories = []
        elif not current_stories and parts:
            split_reasons.append(
                f"phase boundary {current_last_phase} -> {phase}"
            )
        current_stories.extend(phase_stories)
        current_last_phase = phase

    if current_stories:
        parts.append([story["story_id"] for story in current_stories])

    part_for_story = {
        story_id: part_index
        for part_index, part in enumerate(parts)
        for story_id in part
    }
    if any(
        story_id in part_for_story
        and depends_on_story_id in part_for_story
        and part_for_story[story_id] != part_for_story[depends_on_story_id]
        for story_id, depends_on_story_id in edges
    ):
        return _escalation_plan(
            "phase cut severs dependency",
            context,
            total_stories,
            total_tokens,
            limits,
        )

    return build(parts, split_reasons)
