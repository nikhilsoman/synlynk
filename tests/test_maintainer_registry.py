# tests/test_maintainer_registry.py
import json

import pytest

from synlynk.maintainer_registry import (
    FieldSpec,
    register_action,
    registered_actions,
    get_action_config,
    clear_registry,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_registry()
    yield
    clear_registry()


def test_register_action_stores_defaults_and_typed_filter_schema():
    register_action(
        role_slug="maintainer",
        name="sentinel_triage",
        default_config={"enabled": True, "mode": "dry_run"},
        filter_schema=[
            FieldSpec(name="exclude_codes", type="list[str]", default=[], label="Exclude alert codes"),
        ],
        run_fn=lambda **kwargs: {"ok": True},
    )
    actions = registered_actions()
    assert "maintainer:sentinel_triage" in actions
    action = actions["maintainer:sentinel_triage"]
    assert action.role_slug == "maintainer"
    assert action.name == "sentinel_triage"
    assert action.default_config == {"enabled": True, "mode": "dry_run"}
    assert action.filter_schema == [
        FieldSpec(name="exclude_codes", type="list[str]", default=[], label="Exclude alert codes"),
    ]


def test_register_action_rejects_unknown_field_type():
    with pytest.raises(ValueError, match="unknown FieldSpec type"):
        register_action(
            role_slug="maintainer",
            name="bad_action",
            default_config={},
            filter_schema=[FieldSpec(name="x", type="not_a_real_type", default=None, label="X")],
            run_fn=lambda **kwargs: {"ok": True},
        )


def test_registered_actions_filters_by_role_slug():
    register_action(
        role_slug="maintainer", name="mesh_sweep",
        default_config={"enabled": True, "mode": "dry_run"}, filter_schema=[],
        run_fn=lambda **kwargs: {"ok": True},
    )
    register_action(
        role_slug="tpm", name="release_sweep",
        default_config={"enabled": True, "mode": "dry_run"}, filter_schema=[],
        run_fn=lambda **kwargs: {"ok": True},
    )
    maintainer_only = registered_actions(role_slug="maintainer")
    assert set(maintainer_only) == {"maintainer:mesh_sweep"}
    everything = registered_actions()
    assert set(everything) == {"maintainer:mesh_sweep", "tpm:release_sweep"}


def test_get_action_config_returns_defaults_when_no_config_file(tmp_path):
    register_action(
        role_slug="maintainer", name="mesh_sweep",
        default_config={"enabled": True, "mode": "dry_run"},
        filter_schema=[],
        run_fn=lambda **kwargs: {"ok": True},
    )
    config = get_action_config("maintainer:mesh_sweep", repo_root=str(tmp_path))
    assert config == {"enabled": True, "mode": "dry_run"}


def test_get_action_config_applies_repo_overrides(tmp_path):
    register_action(
        role_slug="maintainer", name="backlog_burndown",
        default_config={"enabled": True, "mode": "dry_run"},
        filter_schema=[FieldSpec(name="exclude_labels", type="list[str]", default=[], label="Exclude labels")],
        run_fn=lambda **kwargs: {"ok": True},
    )
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({
        "maintainer_autonomy": {
            "backlog_burndown": {"mode": "promote", "exclude_labels": ["do-not-autosweep"]},
        }
    }))

    config = get_action_config("maintainer:backlog_burndown", repo_root=str(tmp_path))
    assert config == {
        "enabled": True,
        "mode": "promote",
        "exclude_labels": ["do-not-autosweep"],
    }


def test_get_action_config_rejects_unknown_override_keys(tmp_path):
    register_action(
        role_slug="maintainer", name="backlog_burndown",
        default_config={"enabled": True, "mode": "dry_run"}, filter_schema=[],
        run_fn=lambda **kwargs: {"ok": True},
    )
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({
        "maintainer_autonomy": {"backlog_burndown": {"not_a_real_key": 1}},
    }))
    with pytest.raises(ValueError, match="unknown config key"):
        get_action_config("maintainer:backlog_burndown", repo_root=str(tmp_path))


def test_get_action_config_raises_for_unregistered_action_id(tmp_path):
    with pytest.raises(KeyError):
        get_action_config("maintainer:nonexistent", repo_root=str(tmp_path))
