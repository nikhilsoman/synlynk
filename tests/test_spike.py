import pytest
from pathlib import Path
from synlynk.spike import run_spike_eval, generate_spike_receipt


def test_generate_spike_receipt_computes_deltas():
    baseline_stats = {"input_tokens": 38500, "turns": 9, "duration_s": 28.2, "recall": 0.80}
    candidate_stats = {"input_tokens": 1200, "turns": 1, "duration_s": 0.8, "recall": 1.00}

    receipt = generate_spike_receipt(
        candidate="graphify",
        scenario="codebase-exploration",
        baseline="grep-native",
        baseline_metrics=baseline_stats,
        candidate_metrics=candidate_stats,
    )
    assert "# Spike Evaluation Receipt: graphify" in receipt
    assert "-96.9%" in receipt  # token savings delta
    assert "+20.0%" in receipt  # recall delta


def test_run_spike_eval_creates_receipt_file(tmp_path):
    res = run_spike_eval(
        candidate="graphify",
        scenario="codebase-exploration",
        baseline="grep-native",
        repo_root=str(tmp_path),
    )
    assert res["candidate"] == "graphify"
    assert res["scenario"] == "codebase-exploration"
    assert "receipt" in res
    assert Path(res["receipt_path"]).is_file()


def test_cmd_spike_cli(tmp_path, capsys):
    import argparse
    from synlynk.spike import cmd_spike

    args = argparse.Namespace(
        spike_action="eval",
        candidate="graphify",
        scenario="codebase-exploration",
        baseline="grep-native",
        repo_root=str(tmp_path),
    )
    ret = cmd_spike(args)
    assert ret == 0
    captured = capsys.readouterr()
    assert "Spike Evaluation Complete" in captured.out
    assert "-96.9%" in captured.out

