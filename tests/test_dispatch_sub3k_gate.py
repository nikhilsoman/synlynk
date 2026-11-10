import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.cli import build_parser
from synlynk.dispatch import (
    _format_prompt_for_agent,
    _CONTEXT_BUDGET_EXCEEDED_CODE,
)


def test_cli_parser_full_context_flag():
    parser = build_parser("dispatch")
    args = parser.parse_args(["dispatch", "agy", "--task", "test task", "--full-context"])
    assert getattr(args, "full_context", False) is True

    args_default = parser.parse_args(["dispatch", "agy", "--task", "test task"])
    assert getattr(args_default, "full_context", False) is False


def test_format_prompt_defaults_to_sub3k_pack():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("synlynk.pack.synthesize_sub3k_context_pack") as mock_sub3k, \
             patch("synlynk.pack.synthesize_context_pack") as mock_orig_pack:
            mock_sub3k.return_value = "## Sub3k Context Pack"

            prompt = _format_prompt_for_agent(
                agent="agy",
                context_text="",
                story_id="story-1234",
                task="test sub3k task",
                file_section="",
                verify_section="",
                cwd_hint=tmpdir,
                full_context=False,
            )

            assert mock_sub3k.called
            assert mock_orig_pack.call_count == 0
            assert "## Sub3k Context Pack" in prompt


def test_format_prompt_full_context_bypasses_sub3k():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("synlynk.pack.synthesize_sub3k_context_pack") as mock_sub3k, \
             patch("synlynk.pack.synthesize_context_pack") as mock_orig_pack:
            mock_orig_pack.return_value = "## Full Uncompacted Context Pack"

            prompt = _format_prompt_for_agent(
                agent="agy",
                context_text="",
                story_id="story-1234",
                task="test full context task",
                file_section="",
                verify_section="",
                cwd_hint=tmpdir,
                full_context=True,
            )

            assert mock_orig_pack.called
            assert mock_sub3k.call_count == 0
            assert "## Full Uncompacted Context Pack" in prompt


def test_format_prompt_triggers_budget_exceeded_sentinel_on_oversized_standard_dispatch():
    with tempfile.TemporaryDirectory() as tmpdir:
        sentinel_dir = Path(tmpdir) / ".synlynk"
        sentinel_dir.mkdir(parents=True, exist_ok=True)
        sentinel_file = sentinel_dir / "sentinel.md"

        huge_context = "x" * 15000  # ~3750 tokens > 3000
        with patch("synlynk.pack.synthesize_sub3k_context_pack", return_value=""):
            _format_prompt_for_agent(
                agent="agy",
                context_text=huge_context,
                story_id="story-1234",
                task="test oversized task",
                file_section="",
                verify_section="",
                cwd_hint=tmpdir,
                full_context=False,
            )

        assert sentinel_file.exists()
        sentinel_content = sentinel_file.read_text(encoding="utf-8")
        assert _CONTEXT_BUDGET_EXCEEDED_CODE in sentinel_content
