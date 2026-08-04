import json
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts.local_agent_ab_test import (
    _build_result_row,
    _build_temp_config,
    _load_config,
    _write_config,
    run_ab_case,
)


class TestBuildTempConfig(unittest.TestCase):
    def setUp(self):
        self.base_config = {
            "name": "local",
            "endpoint": "http://127.0.0.1:8000",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
                {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
            ],
            "hardware_tier": "16gb-default",
        }

    def test_pins_requested_model_and_sets_diff_format(self):
        result = _build_temp_config(self.base_config, "qwen-coder")
        pinned = [m for m in result["models"] if m["pinned"]]
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0]["id"], "qwen-coder")
        self.assertEqual(pinned[0]["edit_format"], "diff")

    def test_unpins_previously_pinned_model(self):
        result = _build_temp_config(self.base_config, "qwen-coder")
        ornith = next(m for m in result["models"] if m["id"] == "Ornith-1.0-9B-4bit")
        self.assertFalse(ornith["pinned"])

    def test_does_not_mutate_original_config(self):
        _build_temp_config(self.base_config, "qwen-coder")
        original_pinned = [m for m in self.base_config["models"] if m["pinned"]]
        self.assertEqual(original_pinned[0]["id"], "Ornith-1.0-9B-4bit")

    def test_raises_on_unknown_model_id(self):
        with self.assertRaises(ValueError):
            _build_temp_config(self.base_config, "does-not-exist")


if __name__ == "__main__":
    unittest.main()


class TestConfigReadWrite(unittest.TestCase):
    def test_write_then_load_roundtrips(self):
        config = {"name": "local", "models": [{"id": "x", "pinned": True}]}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            _write_config(config, path)
            loaded = _load_config(path)
            self.assertEqual(loaded, config)


class TestBuildResultRow(unittest.TestCase):
    def test_builds_expected_schema(self):
        row = _build_result_row(
            model_id="qwen-coder",
            label="quality-docstring",
            prompt="add a docstring to foo()",
            wall_time_s=12.345,
            peak_rss_kb=204800,
            exit_code=0,
            diff_stat=" 1 file changed, 3 insertions(+)",
            stdout="...long output..." + "x" * 1000,
        )
        self.assertEqual(row["model_id"], "qwen-coder")
        self.assertEqual(row["label"], "quality-docstring")
        self.assertEqual(row["wall_time_s"], 12.35)
        self.assertEqual(row["peak_rss_kb"], 204800)
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["git_diff_stat"], " 1 file changed, 3 insertions(+)")
        self.assertEqual(len(row["stdout_tail"]), 500)


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="ok"):
        self.returncode = returncode
        self.stdout = stdout


class TestRunAbCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.config_path = os.path.join(self.tmpdir.name, "local.json")
        self.original_config = {
            "name": "local",
            "endpoint": "http://127.0.0.1:8000",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
            ],
            "hardware_tier": "16gb-default",
        }
        with open(self.config_path, "w") as f:
            json.dump(self.original_config, f)

    def test_restores_original_config_after_success(self):
        fake_runner = lambda prompt: _FakeCompletedProcess()
        with patch("scripts.local_agent_ab_test._CONFIG_PATH", self.config_path):
            with patch("scripts.local_agent_ab_test._git_diff_stat", return_value=""):
                run_ab_case("qwen-coder", "quality-docstring", "add a docstring",
                            dispatch_runner=fake_runner)
        with open(self.config_path) as f:
            restored = json.load(f)
        self.assertEqual(restored, self.original_config)

    def test_restores_original_config_after_dispatch_raises(self):
        def failing_runner(prompt):
            raise RuntimeError("simulated dispatch failure")

        with patch("scripts.local_agent_ab_test._CONFIG_PATH", self.config_path):
            with self.assertRaises(RuntimeError):
                run_ab_case("qwen-coder", "quality-docstring", "add a docstring",
                            dispatch_runner=failing_runner)
        with open(self.config_path) as f:
            restored = json.load(f)
        self.assertEqual(restored, self.original_config)

    def test_returns_result_row_with_requested_model(self):
        fake_runner = lambda prompt: _FakeCompletedProcess(returncode=0, stdout="done")
        with patch("scripts.local_agent_ab_test._CONFIG_PATH", self.config_path):
            with patch("scripts.local_agent_ab_test._git_diff_stat", return_value="clean"):
                row = run_ab_case("qwen-coder", "quality-docstring", "add a docstring",
                                   dispatch_runner=fake_runner)
        self.assertEqual(row["model_id"], "qwen-coder")
        self.assertEqual(row["label"], "quality-docstring")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["git_diff_stat"], "clean")
