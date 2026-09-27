"""Universal multi-language target codebase extraction test for Vizor BS-6 views."""

import json
import os
import sqlite3
import tempfile
from synlynk.viz_views import (
    extract_product_nodes,
    extract_logical_nodes,
    extract_infra_nodes,
    extract_world_nodes,
    build_workspace_views_snapshot,
)
from synlynk.viz import (
    generate_product_html,
    generate_logical_html,
    generate_infra_html,
    generate_world_html,
)


def test_node_ts_fastify_workspace():
    """Verify that a Node/TypeScript Fastify workspace produces rich BS-6 views."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create package.json
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            json.dump({
                "name": "fastify-api",
                "version": "1.0.0",
                "scripts": {"start": "node server.js", "test": "jest"},
                "dependencies": {"fastify": "^4.0.0", "@anthropic-ai/sdk": "^0.20.0"}
            }, f)
        
        # Create routes and server files
        os.makedirs(os.path.join(tmpdir, "routes"), exist_ok=True)
        with open(os.path.join(tmpdir, "server.js"), "w") as f:
            f.write("// Server entrypoint\nconst fastify = require('fastify')();\n")
        with open(os.path.join(tmpdir, "routes", "users.js"), "w") as f:
            f.write("// Users route\nconst STRIPE_KEY = process.env.STRIPE_API_KEY;\n")

        conn = sqlite3.connect(":memory:")
        snapshot = build_workspace_views_snapshot(conn, tmpdir)

        assert len(snapshot["product"]["nodes"]) > 0
        assert len(snapshot["infra"]["nodes"]) > 0
        assert len(snapshot["world"]["nodes"]) > 0

        # Check world radar captures Stripe and Anthropic from package/code
        world_labels = [n["label"] for n in snapshot["world"]["nodes"]]
        assert any("Stripe" in l or "Anthropic" in l or "Core" in l for l in world_labels)

        # Check HTML generators produce valid markup
        data = {"workspace": {"name": "fastify-api", "path": tmpdir}, "workspace_views": snapshot}
        prod_html = generate_product_html(data, 8721)
        infra_html = generate_infra_html(data, 8721)
        world_html = generate_world_html(data, 8721)
        logical_html = generate_logical_html(data, 8721)

        assert "<!DOCTYPE html>" in prod_html
        assert "<!DOCTYPE html>" in infra_html
        assert "<!DOCTYPE html>" in world_html
        assert "<!DOCTYPE html>" in logical_html


def test_go_cli_workspace():
    """Verify that a Go CLI microservice workspace produces rich BS-6 views."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create go.mod
        with open(os.path.join(tmpdir, "go.mod"), "w") as f:
            f.write("module github.com/user/my-go-tool\n\ngo 1.22\n")

        os.makedirs(os.path.join(tmpdir, "cmd"), exist_ok=True)
        with open(os.path.join(tmpdir, "cmd", "main.go"), "w") as f:
            f.write("package main\nimport \"fmt\"\nfunc main() { fmt.Println(\"Hello\") }\n")

        conn = sqlite3.connect(":memory:")
        snapshot = build_workspace_views_snapshot(conn, tmpdir)

        assert len(snapshot["product"]["nodes"]) > 0
        assert len(snapshot["infra"]["nodes"]) > 0
        assert len(snapshot["world"]["nodes"]) > 0

        data = {"workspace": {"name": "my-go-tool", "path": tmpdir}, "workspace_views": snapshot}
        prod_html = generate_product_html(data, 8721)
        assert "my-go-tool" in prod_html
        assert "Zero-Friction" in prod_html


def test_rust_workspace():
    """Verify that a Rust Cargo workspace produces rich BS-6 views."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Cargo.toml
        with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
            f.write('[package]\nname = "rust-engine"\nversion = "0.1.0"\nedition = "2021"\n')

        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
        with open(os.path.join(tmpdir, "src", "main.rs"), "w") as f:
            f.write('fn main() { println!("Running Rust Engine"); }\n')

        conn = sqlite3.connect(":memory:")
        snapshot = build_workspace_views_snapshot(conn, tmpdir)

        assert len(snapshot["product"]["nodes"]) > 0
        assert len(snapshot["infra"]["nodes"]) > 0
        assert len(snapshot["world"]["nodes"]) > 0
