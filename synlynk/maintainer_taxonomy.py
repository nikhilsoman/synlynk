"""Per-workspace domain vocabulary for Maintainer's keyword clustering and
remediation-topic matching (spec: docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md §6).

Moves cluster_open_issues()'s keyword buckets and is_issue_remediated()'s
remediation-topic list out of Python so a synlynk-managed workspace outside
this repo's own software-engineering domain can populate its own vocabulary
without a code change.
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

_BUILTIN_CLUSTER_KEYWORDS: Dict[str, List[str]] = {
    "backend": ["sqlite", "database", "server", "api", "endpoint", "query"],
    "frontend": ["css", "html", "ui", "vizor", "widget", "render"],
    "cli": ["argparse", "subcommand", "cli.py", "command"],
    "docs": ["readme", "docstring", "documentation", "spec"],
    "sentinel": ["alert", "circuit breaker", "sentinel", "flatline"],
    "testing": ["pytest", "fixture", "test_", "flaky"],
}

_BUILTIN_REMEDIATION_TOPICS: Tuple[str, ...] = (
    "invariant 1",
    "circuit breaker",
    "daemon supervision",
)

_BUILTIN_PROXIMAL_SELECTION: Dict[str, Any] = {
    "code_graph_weights": {"distance_1": 0.6, "distance_2": 0.3},
    "doc_graph_weights": {"shared_doc": 0.4, "shared_issue_or_pr": 0.3},
    "keyword_weight": 0.2,
    "join_threshold": 0.5,
}

_SUPPORTED_TAXONOMY_SCHEMA_VERSIONS = {1}

_REQUIRED_PROXIMAL_SELECTION_KEYS = {"code_graph_weights", "doc_graph_weights", "keyword_weight", "join_threshold"}


def _validate_cluster_keywords_shape(value: Any) -> Optional[str]:
    """DECIDE panel re-review 2026-11-24 (Codex): schema_version alone doesn't
    catch a field holding the wrong shape. Every optional field gets its own
    shape check so a malformed single field falls back the same way a
    malformed whole file does, instead of raising deeper in cluster_keywords()
    or being silently misused as the wrong type."""
    if not isinstance(value, dict):
        return "cluster_keywords must be an object"
    for cluster, words in value.items():
        if not isinstance(cluster, str):
            return "cluster_keywords keys must be strings"
        if not isinstance(words, list) or not all(isinstance(w, str) and w for w in words):
            return f"cluster_keywords[{cluster!r}] must be a list of non-empty strings"
    return None


def _validate_remediation_topics_shape(value: Any) -> Optional[str]:
    if not isinstance(value, list) or not all(isinstance(t, str) and t for t in value):
        return "remediation_topics must be a list of non-empty strings"
    return None


def _validate_doc_type_extensions_shape(value: Any) -> Optional[str]:
    if not isinstance(value, dict):
        return "doc_type_extensions must be an object"
    for doc_type, substrings in value.items():
        if not isinstance(doc_type, str):
            return "doc_type_extensions keys must be strings"
        if not isinstance(substrings, list) or not all(isinstance(s, str) and s for s in substrings):
            return f"doc_type_extensions[{doc_type!r}] must be a list of non-empty strings"
    return None


def _validate_weight(value: Any, label: str) -> Optional[str]:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return f"{label} must be a non-negative number"
    return None


def _validate_proximal_selection_shape(value: Any) -> Optional[str]:
    if not isinstance(value, dict):
        return "proximal_selection must be an object"
    missing = _REQUIRED_PROXIMAL_SELECTION_KEYS - value.keys()
    if missing:
        return f"proximal_selection missing required key(s): {sorted(missing)}"
    for group_key in ("code_graph_weights", "doc_graph_weights"):
        group = value[group_key]
        if not isinstance(group, dict) or not group:
            return f"proximal_selection.{group_key} must be a non-empty object"
        for sub_key, weight in group.items():
            error = _validate_weight(weight, f"proximal_selection.{group_key}.{sub_key}")
            if error:
                return error
    for scalar_key in ("keyword_weight", "join_threshold"):
        error = _validate_weight(value[scalar_key], f"proximal_selection.{scalar_key}")
        if error:
            return error
    return None


def _taxonomy_path(repo_root: str) -> str:
    return os.path.join(repo_root, ".synlynk", "maintainer_taxonomy.json")


def _load_taxonomy_file_raw(repo_root: str) -> Tuple[dict, Optional[str]]:
    """Returns (data, validation_error). data is {} whenever validation_error
    is set, so every caller falls back to built-in defaults uniformly
    (DECIDE panel defect #5: never raise on malformed/unknown-version/missing
    config -- validate-or-fallback only)."""
    path = _taxonomy_path(repo_root)
    if not os.path.exists(path):
        return {}, None  # absence is the normal unconfigured case, not an error

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return {}, f"malformed JSON in {path}: {exc}"

    if not isinstance(data, dict):
        return {}, f"{path} must contain a JSON object, got {type(data).__name__}"

    schema_version = data.get("schema_version")
    if schema_version not in _SUPPORTED_TAXONOMY_SCHEMA_VERSIONS:
        return {}, f"unsupported schema_version {schema_version!r} in {path} (supported: {sorted(_SUPPORTED_TAXONOMY_SCHEMA_VERSIONS)})"

    # DECIDE panel re-review 2026-11-24 (Codex): validate each optional
    # field's shape, not just the top-level schema_version.
    if "cluster_keywords" in data:
        shape_error = _validate_cluster_keywords_shape(data["cluster_keywords"])
        if shape_error:
            return {}, f"{path}: {shape_error}"
    if "remediation_topics" in data:
        shape_error = _validate_remediation_topics_shape(data["remediation_topics"])
        if shape_error:
            return {}, f"{path}: {shape_error}"
    if "proximal_selection" in data:
        shape_error = _validate_proximal_selection_shape(data["proximal_selection"])
        if shape_error:
            return {}, f"{path}: {shape_error}"

    return data, None


def _load_taxonomy_file(repo_root: str) -> dict:
    data, _ = _load_taxonomy_file_raw(repo_root)
    return data


def load_taxonomy(repo_root: str = ".") -> Dict[str, Any]:
    """Full validated taxonomy config, merged with built-in defaults.

    Returns a dict with cluster_keywords, remediation_topics,
    proximal_selection, schema_valid, and validation_error -- the latter two
    so Vizor's Role Operations Panel (Task 13) can surface a "using built-in
    defaults -- config failed validation" banner (spec §6, DECIDE panel
    defect #5) without the loader itself ever raising.
    """
    data, error = _load_taxonomy_file_raw(repo_root)

    cluster = data.get("cluster_keywords")
    cluster = cluster if isinstance(cluster, dict) and cluster else dict(_BUILTIN_CLUSTER_KEYWORDS)

    topics = data.get("remediation_topics")
    topics = tuple(topics) if isinstance(topics, list) and topics else _BUILTIN_REMEDIATION_TOPICS

    proximal = data.get("proximal_selection")
    proximal = proximal if isinstance(proximal, dict) and proximal else dict(_BUILTIN_PROXIMAL_SELECTION)

    return {
        "cluster_keywords": cluster,
        "remediation_topics": topics,
        "proximal_selection": proximal,
        "schema_valid": error is None,
        "validation_error": error,
    }


def cluster_keywords(repo_root: str = ".") -> Dict[str, List[str]]:
    """Cluster name -> keyword list, from .synlynk/maintainer_taxonomy.json or built-in defaults."""
    return load_taxonomy(repo_root)["cluster_keywords"]


def remediation_topics(repo_root: str = ".") -> Tuple[str, ...]:
    """Remediation-topic keywords, from .synlynk/maintainer_taxonomy.json or built-in defaults."""
    return load_taxonomy(repo_root)["remediation_topics"]
