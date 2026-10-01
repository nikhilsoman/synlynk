import json

from synlynk.fleet_templates import apply_fleet_template, list_fleet_templates
from synlynk.version_policy import check_version_policy, plan_upgrade


def test_fleet_templates_available(tmp_path):
    templates = list_fleet_templates()
    assert "saas_web" in templates
    assert "fintech" in templates
    assert "healthcare" in templates

    result = apply_fleet_template(str(tmp_path), "saas_web")
    assert result["status"] == "applied"
    config = json.loads((tmp_path / ".synlynk" / "config.json").read_text())
    assert "roles" in config or "fleet_template" in config


def test_version_policy_check(tmp_path):
    config_dir = tmp_path / ".synlynk"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({
        "version_policy": {
            "min_version": "0.23.0",
            "target_version": "0.24.0",
            "enforcement": "warn_and_prompt",
        }
    }))

    ok, _ = check_version_policy(str(tmp_path), "0.23.0")
    assert ok is True
    ok, message = check_version_policy(str(tmp_path), "0.22.0")
    assert ok is False
    assert "0.23.0" in message


def test_plan_upgrade_dry_run(tmp_path):
    repo = tmp_path / "repo1"
    repo.mkdir()
    result = plan_upgrade([str(repo)], dry_run=True)
    assert result["dry_run"] is True
    assert len(result["targets"]) == 1
