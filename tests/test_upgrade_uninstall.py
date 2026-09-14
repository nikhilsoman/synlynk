import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.upgrade import execute_upgrade
from synlynk.uninstall import execute_uninstall


def test_execute_upgrade_refreshes_instructions_and_db(tmp_path):
    res = execute_upgrade(str(tmp_path))
    assert res["status"] == "upgraded"
    assert res["schema_version_current"] is True
    assert res["instructions_refreshed"] is True


def test_execute_uninstall_cleans_runtime(tmp_path):
    res = execute_uninstall(str(tmp_path))
    assert res["status"] == "uninstalled"
    assert res["services_unloaded"] is True
    assert res["shims_removed"] is True
