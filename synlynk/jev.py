"""Jev — sub-20ms AST Decision Engine (#1712).

Routes a dispatched task to a harness model tier (``fast``, ``pro``,
``reasoning``) using a pure-Python heuristic matrix over AST graph features.

Hard invariant: no network calls, no frontier-LLM tokens, and a decision
returned in well under 20ms so it can run inline on every dispatch.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

#: Prompt keywords that imply architectural reasoning regardless of file count.
ARCHITECTURAL_KEYWORDS = (
    "architect",
    "invariant",
    "protocol",
    "security",
    "ast",
)

#: Prompt keywords that imply multi-module work without architectural risk.
BROAD_SCOPE_KEYWORDS = (
    "refactor",
    "e2e",
    "integration",
    "migration",
)

#: Blast radius at or above which a task always escalates to the reasoning tier.
REASONING_BLAST_RADIUS = 25

#: Blast radius above which a task escalates to the pro tier.
PRO_BLAST_RADIUS = 3


@dataclass
class JevDecision:
    """The routing verdict for a single task."""

    recommended_tier: str  # fast, pro, reasoning
    blast_radius: int
    requires_architect_review: bool
    rationale: str


def evaluate_task_ast_features(
    files_touched: List[str],
    task_prompt: str,
    graph_data: Optional[Dict[str, Any]] = None,
) -> JevDecision:
    """Classify a task into a model tier from its files and graph degree.

    ``graph_data`` is the ``.synlynk/graphify-out/graph.json`` shape: a
    ``nodes`` list of ``{"id": <path>, "degree": <int>}`` entries. It is
    optional — without it the blast radius is simply the touched-file count.
    """
    prompt_lower = task_prompt.lower()
    blast_radius = len(files_touched)

    # Graph-aware blast radius: the most-connected touched node dominates.
    if graph_data and graph_data.get("nodes"):
        node_degrees = {
            n["id"]: n.get("degree", 1)
            for n in graph_data["nodes"]
            if isinstance(n, dict) and "id" in n
        }
        max_degree = max(
            (node_degrees.get(f, 1) for f in files_touched),
            default=1,
        )
        blast_radius = max(blast_radius, max_degree)

    # Heuristic decision matrix (sub-20ms in pure Python).
    if blast_radius >= REASONING_BLAST_RADIUS or any(
        k in prompt_lower for k in ARCHITECTURAL_KEYWORDS
    ):
        return JevDecision(
            recommended_tier="reasoning",
            blast_radius=blast_radius,
            requires_architect_review=True,
            rationale=f"High blast radius ({blast_radius}) or architectural keywords",
        )

    if blast_radius > PRO_BLAST_RADIUS or any(
        k in prompt_lower for k in BROAD_SCOPE_KEYWORDS
    ):
        return JevDecision(
            recommended_tier="pro",
            blast_radius=blast_radius,
            requires_architect_review=False,
            rationale=f"Moderate blast radius ({blast_radius}) across multiple modules",
        )

    return JevDecision(
        recommended_tier="fast",
        blast_radius=blast_radius,
        requires_architect_review=False,
        rationale=f"Low blast radius ({blast_radius}) isolated task",
    )
