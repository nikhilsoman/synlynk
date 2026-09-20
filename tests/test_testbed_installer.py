"""Tests for synlynk.testbed.installer."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from synlynk.testbed.driver import ExecResult
from synlynk.testbed.installer import (
    ResolvedTarget,
    TargetResolver,
    install_target_on_node,
    build_local_wheel,
)


def test_target_resolver_staging_unstable_and_commit():
    resolver = TargetResolver()

    staging = resolver.resolve("staging")
    assert staging.kind == "git_ref"
    assert staging.ref == "staging"

    unstable = resolver.resolve("unstable")
    assert unstable.kind == "git_ref"
    assert unstable.ref == "unstable"

    commit = resolver.resolve("commit:19fcd5ba")
    assert commit.kind == "git_commit"
    assert commit.ref == "19fcd5ba"

    local = resolver.resolve("local")
    assert local.kind == "local_build"


def test_install_target_git_ref_on_node():
    mock_driver = MagicMock()
    mock_driver.exec_command.return_value = ExecResult(returncode=0, stdout="Successfully installed synlynk\n", stderr="")

    res = install_target_on_node(
        driver=mock_driver,
        node_id="test-node-1",
        target_ref="unstable",
        repo_url="https://github.com/nikhilsoman/synlynk.git",
    )
    assert res is True
    assert mock_driver.exec_command.called


def test_install_target_local_wheel_on_node(tmp_path):
    mock_driver = MagicMock()
    mock_driver.exec_command.return_value = ExecResult(returncode=0, stdout="", stderr="")

    wheel_file = tmp_path / "synlynk-1.0.0-py3-none-any.whl"
    wheel_file.write_text("dummy wheel content")

    with patch("synlynk.testbed.installer.build_local_wheel", return_value=wheel_file):
        res = install_target_on_node(
            driver=mock_driver,
            node_id="test-node-1",
            target_ref="local",
            workspace_root=tmp_path,
        )
        assert res is True
        mock_driver.copy_file.assert_called()
