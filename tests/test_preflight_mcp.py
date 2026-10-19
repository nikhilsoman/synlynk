"""Tests for @synlynk/preflight-mcp package."""

from pathlib import Path
import json

def test_preflight_mcp_package_manifest():
    pkg_path = Path("packages/preflight-mcp/package.json")
    assert pkg_path.exists(), "package.json missing"
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    assert data["name"] == "@synlynk/preflight-mcp"
    assert "bin" in data
    assert "synlynk-preflight" in data["bin"]
    assert (Path("packages/preflight-mcp") / data["main"]).exists()
    assert (Path("packages/preflight-mcp/README.md")).exists()


def test_preflight_mcp_cli_executable():
    cli_path = Path("packages/preflight-mcp/bin/cli.js")
    assert cli_path.exists()
    content = cli_path.read_text(encoding="utf-8")
    assert "#!/usr/bin/env node" in content
    assert "synlynk_preflight" in content or "evaluatePreflight" in content
