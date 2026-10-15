"""Integration tests for ``synlynk upgrade --all`` (wires version_policy)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import synlynk.cli as cli


def _write_workspace(repo: Path, *, min_version: str | None = None) -> Path:
    """Create a minimal registered-looking workspace repo + state.db."""
    repo.mkdir(parents=True, exist_ok=True)
    synlynk_dir = repo / ".synlynk"
    synlynk_dir.mkdir(parents=True, exist_ok=True)
    config = {"schema_version": 1}
    if min_version is not None:
        config["version_policy"] = {
            "min_version": min_version,
            "target_version": min_version,
            "enforcement": "warn_and_prompt",
        }
    (synlynk_dir / "config.json").write_text(json.dumps(config) + "\n", encoding="utf-8")
    return repo


def _write_state_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS _synlynk_marker (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()


def _seed_registry(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """Seed two workspaces into a private registry and point env at it."""
    home = tmp_path / "home"
    workspaces_root = home / ".synlynk" / "workspaces"
    registry_path = home / ".synlynk" / "registry.json"

    alpha = _write_workspace(tmp_path / "alpha", min_version="0.23.0")
    beta = _write_workspace(tmp_path / "beta", min_version="99.0.0")
    alpha_db = workspaces_root / "alpha" / "state.db"
    beta_db = workspaces_root / "beta" / "state.db"
    _write_state_db(alpha_db)
    _write_state_db(beta_db)

    registry = {
        "version": 1,
        "products": {
            "alpha": {
                "product_id": "test-alpha",
                "canonical_path": str(alpha_db),
                "repo_path": str(alpha),
            },
            "beta": {
                "product_id": "test-beta",
                "canonical_path": str(beta_db),
                "repo_path": str(beta),
            },
        },
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry) + "\n", encoding="utf-8")

    # Custom registry path also disables transient-test-path filtering in
    # vizor_daemon._registered_workspaces(), so tmp paths are accepted.
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry_path))
    return alpha, beta


def test_upgrade_all_dry_run_multi_workspace_via_cli(tmp_path, monkeypatch, capsys):
    """Real CLI entry point: upgrade --all prints a multi-workspace plan."""
    alpha, beta = _seed_registry(tmp_path, monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["upgrade", "--all"])
    assert excinfo.value.code in (0, None)

    output = capsys.readouterr().out
    assert "Upgrade plan for 2 registered workspace(s)" in output
    assert "alpha" in output
    assert "beta" in output
    assert str(alpha) in output
    assert str(beta) in output
    assert "DRY RUN — no upgrades applied" in output
    assert "below_min" in output  # beta requires 99.0.0
    assert "ok" in output  # alpha min 0.23.0 should pass current VERSION


def test_upgrade_all_explicit_dry_run_flag(tmp_path, monkeypatch, capsys):
    _seed_registry(tmp_path, monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["upgrade", "--all", "--dry-run"])
    assert excinfo.value.code in (0, None)

    output = capsys.readouterr().out
    assert "DRY RUN — no upgrades applied" in output
    assert "plan targets: 2" in output


def test_upgrade_parser_exposes_all_and_yes_flags():
    parser = cli.build_parser()
    args = parser.parse_args(["upgrade", "--all", "--yes"])
    assert args.command == "upgrade"
    assert args.all_workspaces is True
    assert args.yes is True
