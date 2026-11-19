import json
import os

import pytest

from synlynk.harness_manifest import HARNESS_BILLING_CONFIG_INVALID, discover_and_validate


def test_discover_and_validate_writes_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    manifest = discover_and_validate("claude")
    assert manifest["harness"] == "claude"
    assert manifest["manifest_schema_version"] == 1
    assert "cli_version_hash" in manifest
    path = os.path.join(".synlynk", "harnesses", "claude.json")
    assert os.path.exists(path)
    with open(path) as f:
        on_disk = json.load(f)
    assert on_disk == manifest


def test_per_token_billing_without_rate_fails_closed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    # muse is per_token billing (not subscription) per HARNESS_CAPABILITY_BASELINES/_payment_model_config_for_agent,
    # and no .synlynk/billing.json exists in this tmp_path — must fail closed.
    with pytest.raises(ValueError) as exc:
        discover_and_validate("muse")
    assert HARNESS_BILLING_CONFIG_INVALID in str(exc.value)


def test_per_token_billing_with_rate_succeeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/billing.json", "w") as f:
        json.dump({"muse": {"cost_per_1k_tokens": {"input": 0.00125, "output": 0.00425}}}, f)
    manifest = discover_and_validate("muse")
    assert manifest["harness"] == "muse"
