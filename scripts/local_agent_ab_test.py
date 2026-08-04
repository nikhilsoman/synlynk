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


def _default_dispatch_runner(prompt: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", "-m", "synlynk", "dispatch", "local",
         "--task", prompt, "--force-agent"],
        capture_output=True, text=True, check=False,
    )


def run_ab_case(model_id: str, label: str, prompt: str, dispatch_runner=None) -> dict:
    """Re-pins model_id, runs one dispatch, restores config, returns a result row.

    Always restores .agents/local.json, even if the dispatch raises.
    """
    dispatch_runner = dispatch_runner or _default_dispatch_runner
    with open(_CONFIG_PATH) as f:
        original_text = f.read()
    original_config = json.loads(original_text)
    try:
        temp_config = _build_temp_config(original_config, model_id)
        _write_config(temp_config, _CONFIG_PATH)
        rss_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        start = time.monotonic()
        completed = dispatch_runner(prompt)
        wall_time_s = time.monotonic() - start
        rss_after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        peak_rss_kb = max(rss_after - rss_before, 0)
        diff_stat = _git_diff_stat()
        return _build_result_row(
            model_id, label, prompt, wall_time_s, peak_rss_kb,
            completed.returncode, diff_stat, completed.stdout,
        )
    finally:
        with open(_CONFIG_PATH, "w") as f:
            f.write(original_text)


def append_result(row: dict, results_path: str = _RESULTS_PATH) -> None:
    parent = os.path.dirname(results_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(results_path, "a") as f:
        f.write(json.dumps(row) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one A/B comparison dispatch for a local-agent model."
    )
    parser.add_argument("--model-id", required=True,
                         help="Roster id from .agents/local.json, e.g. qwen-coder")
    parser.add_argument("--label", required=True,
                         help="quality-<name>, safety-<name>, or cost-<name>")
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)
    row = run_ab_case(args.model_id, args.label, args.prompt)
    append_result(row)
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
