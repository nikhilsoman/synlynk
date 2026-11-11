"""Tests for synlynk Document Sidecar Knowledge Graph (v0.32.1)."""

import json
import os
from pathlib import Path

import pytest
from synlynk.docgraph import (
    DocGraph,
    DocumentNode,
    build_docgraph,
    classify_doc_type,
    extract_document_node,
    parse_yaml_frontmatter,
)


def test_parse_yaml_frontmatter():
    text = """---
title: "Sample Spec"
parent_goal: "goal-1234"
target_release: "v0.32.1"
tags: [architecture, core]
---
# Sample Spec Title

Document content here.
"""
    fm, body = parse_yaml_frontmatter(text)
    assert fm.get("title") == "Sample Spec"
    assert fm.get("parent_goal") == "goal-1234"
    assert fm.get("target_release") == "v0.32.1"
    assert "Sample Spec Title" in body


def test_classify_doc_type():
    assert classify_doc_type("docs/superpowers/specs/2026-11-11-spec.md") == "spec"
    assert classify_doc_type("docs/superpowers/plans/2026-11-11-plan.md") == "plan"
    assert classify_doc_type("project-docs/decisions/2026-11-11-decision.md") == "decision"
    assert classify_doc_type("project-docs/roadmap.md") == "roadmap"
    assert classify_doc_type("project-docs/todo.md") == "todo"
    assert classify_doc_type("project-docs/costs.md") == "costs"
    assert classify_doc_type("README.md") == "readme"
    assert classify_doc_type("CHANGELOG.md") == "changelog"
    assert classify_doc_type("docs/guides/getting-started.md") == "guide"


def test_extract_document_node(tmp_path):
    doc_path = tmp_path / "docs" / "superpowers" / "specs" / "my-spec.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    content = """---
parent_goal: goal-core-1
target_release: v0.32.1
---
# Architecture Specification

## Overview
This spec links to [`docs/superpowers/plans/my-plan.md`](../plans/my-plan.md) and modifies `synlynk/scan.py` and `synlynk/db.py`.

See also PR #5204 and issue #5200.
Reference: [External link](https://github.com/nikhilsoman/synlynk).
"""
    doc_path.write_text(content, encoding="utf-8")

    node = extract_document_node(str(doc_path), repo_root=str(tmp_path))
    assert node.path == "docs/superpowers/specs/my-spec.md"
    assert node.title == "Architecture Specification"
    assert node.doc_type == "spec"
    assert node.frontmatter.get("parent_goal") == "goal-core-1"
    assert "synlynk/scan.py" in node.code_references
    assert "synlynk/db.py" in node.code_references
    assert 5204 in node.issues_and_prs
    assert 5200 in node.issues_and_prs
    assert len(node.links) >= 1


def test_build_docgraph_with_reverse_index(tmp_path):
    # Setup test workspace
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    plans_dir = tmp_path / "docs" / "superpowers" / "plans"
    src_dir = tmp_path / "synlynk"
    specs_dir.mkdir(parents=True, exist_ok=True)
    plans_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(parents=True, exist_ok=True)

    # Code file
    (src_dir / "core.py").write_text("def run(): pass\n", encoding="utf-8")

    # Spec file referencing core.py
    spec_file = specs_dir / "2026-11-11-core-design.md"
    spec_file.write_text(
        "# Core Design\nGoverns `synlynk/core.py`. Related to [Core Plan](../plans/2026-11-11-core-plan.md).",
        encoding="utf-8",
    )

    # Plan file referencing spec
    plan_file = plans_dir / "2026-11-11-core-plan.md"
    plan_file.write_text(
        "# Core Plan\nImplements [Core Design](../specs/2026-11-11-core-design.md). Modifies `synlynk/core.py`.",
        encoding="utf-8",
    )

    graph = build_docgraph(str(tmp_path))
    assert isinstance(graph, DocGraph)
    assert len(graph.nodes) >= 2

    # Reverse index: querying synlynk/core.py should return both spec and plan
    docs_for_core = graph.get_docs_for_code("synlynk/core.py")
    assert "docs/superpowers/specs/2026-11-11-core-design.md" in docs_for_core
    assert "docs/superpowers/plans/2026-11-11-core-plan.md" in docs_for_core


def test_docgraph_persistence_roundtrip(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "intro.md").write_text("# Intro\nWelcome.", encoding="utf-8")

    out_file = tmp_path / ".synlynk" / "docgraph.json"
    graph = build_docgraph(str(tmp_path), output_path=str(out_file))

    assert out_file.exists()
    loaded_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "nodes" in loaded_data
    assert "edges" in loaded_data
    assert "reverse_code_index" in loaded_data
    assert loaded_data["schema_version"] == "1.0"


def test_ensure_docgraph_creates_sidecar(tmp_path):
    from synlynk.scan import ensure_docgraph

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.md").write_text("# Documentation Index\nContents.", encoding="utf-8")

    assert ensure_docgraph(str(tmp_path)) is True
    docgraph_path = tmp_path / ".synlynk" / "docgraph.json"
    assert docgraph_path.exists()
    data = json.loads(docgraph_path.read_text(encoding="utf-8"))
    assert "docs/index.md" in data["nodes"]


def test_docgraph_skips_transient_dirs(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "valid.md").write_text("# Valid Doc", encoding="utf-8")

    # Transient dirs that must be ignored
    worktree_dir = tmp_path / "worktrees" / "nested"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    (worktree_dir / "skip.md").write_text("# Should Skip", encoding="utf-8")

    claude_dir = tmp_path / ".claude" / "transcripts"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "skip2.md").write_text("# Should Skip 2", encoding="utf-8")

    graph = build_docgraph(str(tmp_path))
    paths = list(graph.nodes.keys())
    assert "docs/valid.md" in paths
    assert not any("worktrees/" in p for p in paths)
    assert not any(".claude/" in p for p in paths)


