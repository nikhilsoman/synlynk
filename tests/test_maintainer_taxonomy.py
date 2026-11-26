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

from synlynk.maintainer_taxonomy import load_domain_pack, doc_type_extensions


def test_load_domain_pack_merges_cluster_keywords_over_repo_defaults(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "maintainer_taxonomy.json").write_text(json.dumps({
        "schema_version": 1,
        "cluster_keywords": {"backend": ["sqlite"]},
        "remediation_topics": ["topic a"],
    }))
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({
        "schema_version": 1,
        "pack_name": "test-pack",
        "cluster_keywords": {"backend": ["sqlite", "postgres"], "ops": ["pager"]},
        "remediation_topics": ["topic b"],
        "doc_type_extensions": {"compliance_doc": ["hipaa"]},
    }))

    pack = load_domain_pack(repo_root=str(tmp_path))
    assert pack["pack_name"] == "test-pack"

    keywords = cluster_keywords(repo_root=str(tmp_path))
    assert keywords["backend"] == ["sqlite", "postgres"]
    assert keywords["ops"] == ["pager"]

    topics = remediation_topics(repo_root=str(tmp_path))
    assert "topic b" in topics


def test_load_domain_pack_returns_none_when_absent(tmp_path):
    assert load_domain_pack(repo_root=str(tmp_path)) is None


def test_load_domain_pack_falls_back_on_unsupported_schema_version(tmp_path):
    """DECIDE panel defect #5 applies to the domain pack too."""
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({"schema_version": 99, "pack_name": "bad"}))

    pack = load_domain_pack(repo_root=str(tmp_path))
    assert pack is None

    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "domain_pack" in result["validation_error"]


def test_doc_type_extensions_reads_domain_pack(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({
        "schema_version": 1,
        "pack_name": "test-pack",
        "doc_type_extensions": {"shot_list": ["shotlist", "shot-list"]},
    }))
    assert doc_type_extensions(repo_root=str(tmp_path)) == {"shot_list": ["shotlist", "shot-list"]}


def test_load_domain_pack_falls_back_on_invalid_doc_type_extensions_shape(tmp_path):
    """DECIDE panel re-review 2026-11-24 (Codex, Tasks 1-2): the domain pack
    needs the same per-field shape validation as the taxonomy file, not just
    a schema_version check."""
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({
        "schema_version": 1,
        "pack_name": "test-pack",
        "doc_type_extensions": {"shot_list": "shotlist"},  # should be a list, not a str
    }))

    assert load_domain_pack(repo_root=str(tmp_path)) is None
    result = load_taxonomy(repo_root=str(tmp_path))
    assert result["schema_valid"] is False
    assert "doc_type_extensions" in result["validation_error"]


def test_load_domain_pack_falls_back_on_invalid_cluster_keywords_shape(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "domain_pack.json").write_text(json.dumps({
        "schema_version": 1,
        "pack_name": "test-pack",
        "cluster_keywords": {"ops": [1, 2]},  # list entries must be strings
    }))

    assert load_domain_pack(repo_root=str(tmp_path)) is None
