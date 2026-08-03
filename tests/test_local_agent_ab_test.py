import unittest

from scripts.local_agent_ab_test import _build_temp_config


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
