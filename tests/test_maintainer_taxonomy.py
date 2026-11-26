# tests/test_maintainer_taxonomy.py
import json

from synlynk.maintainer_taxonomy import cluster_keywords, remediation_topics, load_taxonomy

_BUILTIN_CLUSTER_KEYWORDS_FOR_TEST = {
    "backend": ["sqlite", "database", "server", "api", "endpoint", "query"],
    "frontend": ["css", "html", "ui", "vizor", "widget", "render"],
    "cli": ["argparse", "subcommand", "cli.py", "command"],
    "docs": ["readme", "docstring", "documentation", "spec"],
    "sentinel": ["alert", "circuit breaker", "sentinel", "flatline"],
    "testing": ["pytest", "fixture", "test_", "flaky"],
}


def test_cluster_keywords_reads_repo_config(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({
        "schema_version": 1,
        "cluster_keywords": {"backend": ["sqlite", "api"]},
        "remediation_topics": ["custom topic"],
    }))

    keywords = cluster_keywords(repo_root=str(tmp_path))
    assert keywords == {"backend": ["sqlite", "api"]}

    topics = remediation_topics(repo_root=str(tmp_path))
    assert topics == ("custom topic",)


def test_cluster_keywords_falls_back_to_builtin_defaults_when_missing(tmp_path):
    keywords = cluster_keywords(repo_root=str(tmp_path))
    assert "backend" in keywords
    assert "frontend" in keywords

    topics = remediation_topics(repo_root=str(tmp_path))
    assert "invariant 1" in topics


def test_load_taxonomy_falls_back_on_malformed_json(tmp_path):
    """DECIDE panel defect #5: malformed JSON must never raise -- fall back
    to built-in defaults and surface a validation error for the UI banner."""
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text("{not valid json")

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "malformed JSON" in result["validation_error"]
    assert "backend" in result["cluster_keywords"]


def test_load_taxonomy_falls_back_on_unsupported_schema_version(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({"schema_version": 99, "cluster_keywords": {"x": ["y"]}}))

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "schema_version" in result["validation_error"]
    assert "backend" in result["cluster_keywords"]
    assert result["cluster_keywords"]["backend"] == ["sqlite", "database", "server", "api", "endpoint", "query"]


def test_load_taxonomy_falls_back_on_non_dict_json(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps(["not", "a", "dict"]))

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False


def test_load_taxonomy_accepts_valid_schema_version_1(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({
        "schema_version": 1,
        "cluster_keywords": {"backend": ["sqlite"]},
    }))

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is True
    assert result["validation_error"] is None
    assert result["cluster_keywords"] == {"backend": ["sqlite"]}


def test_load_taxonomy_missing_file_is_not_a_validation_error(tmp_path):
    """Absence is the normal unconfigured case, not a malformed-config error."""
    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is True
    assert result["validation_error"] is None


def test_load_taxonomy_falls_back_on_non_list_cluster_keyword_value(tmp_path):
    """DECIDE panel re-review 2026-11-24 (Codex, Tasks 1-2): shape validation,
    not just schema_version, must gate every field -- a string where a list
    is expected must fall back, not raise or silently misbehave downstream."""
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({
        "schema_version": 1,
        "cluster_keywords": {"backend": "sqlite"},  # should be a list, not a str
    }))

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "cluster_keywords" in result["validation_error"]
    assert result["cluster_keywords"] == _BUILTIN_CLUSTER_KEYWORDS_FOR_TEST


def test_load_taxonomy_falls_back_on_missing_proximal_selection_key(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({
        "schema_version": 1,
        "proximal_selection": {"code_graph_weights": {"distance_1": 0.6}},  # missing other required keys
    }))

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "proximal_selection" in result["validation_error"]


def test_load_taxonomy_falls_back_on_negative_proximal_selection_weight(tmp_path):
    taxonomy_path = tmp_path / ".synlynk" / "maintainer_taxonomy.json"
    taxonomy_path.parent.mkdir(parents=True)
    taxonomy_path.write_text(json.dumps({
        "schema_version": 1,
        "proximal_selection": {
            "code_graph_weights": {"distance_1": 0.6, "distance_2": 0.3},
            "doc_graph_weights": {"shared_doc": 0.4, "shared_issue_or_pr": 0.3},
            "keyword_weight": -0.1,  # negative weight is invalid
            "join_threshold": 0.5,
        },
    }))

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "keyword_weight" in result["validation_error"]
