"""Regression test: a workspace registered with repo_path "/" must not trigger
a filesystem-root os.walk from build_workspace_views_snapshot() (gh:#5333)."""

import sqlite3

from synlynk.viz_views import (
    _is_unsafe_walk_root,
    build_workspace_views_snapshot,
)


def test_is_unsafe_walk_root_flags_filesystem_root():
    assert _is_unsafe_walk_root("/") is True


def test_is_unsafe_walk_root_allows_normal_directory(tmp_path):
    assert _is_unsafe_walk_root(str(tmp_path)) is False


def test_build_workspace_views_snapshot_skips_walk_for_root_path():
    """A misconfigured repo_path of "/" must not attempt a full-disk walk.

    extract_product_nodes() and extract_infra_nodes() always emit a small
    set of static/canonical nodes regardless of repo_path, so those views
    are not asserted empty here. Logical nodes are purely derived from
    os.walk(repo_path) and must be empty once the walk is skipped.
    """
    conn = sqlite3.connect(":memory:")
    snapshot = build_workspace_views_snapshot(conn, "/")

    assert snapshot["logical"]["nodes"] == []
