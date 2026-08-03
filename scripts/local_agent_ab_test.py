#!/usr/bin/env python3
"""A/B comparison harness for local-agent models.

Temporarily re-pins .agents/local.json to the model under test, runs one dispatch
through the real `synlynk dispatch local` CLI path, records wall-clock time, peak
child RSS, and git diff footprint, then always restores the original config. This
script does not decide a winner — it only produces data rows for a human/PM to read,
per docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import resource
import subprocess
import sys
import time

_CONFIG_PATH = os.path.join(".agents", "local.json")
_RESULTS_PATH = os.path.join(
    "project-docs", "decisions", "2026-08-03-local-agent-ab-test-results.jsonl"
)


def _build_temp_config(base_config: dict, model_id: str) -> dict:
    """Returns a deep copy of base_config with only model_id pinned, edit_format=diff."""
    config = copy.deepcopy(base_config)
    found = False
    for model in config["models"]:
        if model["id"] == model_id:
            model["pinned"] = True
            model["edit_format"] = "diff"
            found = True
        else:
            model["pinned"] = False
    if not found:
        raise ValueError(f"model_id {model_id!r} not present in roster")
    return config


def _load_config(path: str = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def _write_config(config: dict, path: str = _CONFIG_PATH) -> None:
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def _git_diff_stat() -> str:
    result = subprocess.run(
        ["git", "diff", "--stat"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def _build_result_row(model_id, label, prompt, wall_time_s, peak_rss_kb,
                       exit_code, diff_stat, stdout):
    return {
        "model_id": model_id,
        "label": label,
        "prompt": prompt,
        "wall_time_s": round(wall_time_s, 2),
        "peak_rss_kb": peak_rss_kb,
        "exit_code": exit_code,
        "git_diff_stat": diff_stat,
        "stdout_tail": stdout[-500:],
    }
