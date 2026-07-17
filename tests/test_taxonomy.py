from synlynk.cli import build_parser
from synlynk.taxonomy import (
    COMMAND_TAXONOMY,
    entries_for_tier,
    entries_up_to_tier,
    get_entry,
    iter_leaf_commands,
)


REQUIRED_KEYS = {
    "command",
    "governs_stage",
    "maturity_tier",
    "prominence",
    "orientation_gateway",
    "audience",
    "trigger_phrases",
    "hook_event",
}
VALID_STAGES = {"goal", "open", "visualize", "execute", "release", "notify", "sustain"}
VALID_TIERS = {0, 1, 2, 3, "latent"}
VALID_PROMINENCE = {"primary", "secondary", None}
VALID_AUDIENCE = {"human", "pilot", "hook"}


def test_every_entry_has_required_keys():
    for entry in COMMAND_TAXONOMY:
        assert REQUIRED_KEYS <= entry.keys(), f"{entry.get('command')} missing keys"


def test_every_entry_has_valid_field_values():
    for entry in COMMAND_TAXONOMY:
        assert entry["governs_stage"] in VALID_STAGES, entry["command"]
        assert entry["maturity_tier"] in VALID_TIERS, entry["command"]
        assert entry["prominence"] in VALID_PROMINENCE, entry["command"]
        assert entry["audience"] in VALID_AUDIENCE, entry["command"]
        assert isinstance(entry["trigger_phrases"], list), entry["command"]
        if entry["audience"] != "human":
            assert entry["trigger_phrases"] == [], entry["command"]


def test_no_duplicate_commands():
    commands = [entry["command"] for entry in COMMAND_TAXONOMY]
    assert len(commands) == len(set(commands))


def test_get_entry_returns_matching_command():
    entry = get_entry("dispatch")
    assert entry["command"] == "dispatch"
    assert entry["governs_stage"] == "execute"


def test_entries_for_tier_filters_exact_matches():
    tier_1_commands = [entry["command"] for entry in entries_for_tier(1)]
    assert "goal create" in tier_1_commands
    assert "dispatch" not in tier_1_commands


def test_entries_up_to_tier_includes_lower_tiers_only():
    commands = [entry["command"] for entry in entries_up_to_tier(1)]
    assert "init" in commands
    assert "dispatch" not in commands
    assert "status" in commands
    assert "relay start" not in commands


def test_taxonomy_matches_real_cli_surface():
    parser = build_parser()
    real_commands = set(iter_leaf_commands(parser))
    taxonomy_commands = {entry["command"] for entry in COMMAND_TAXONOMY}
    missing_from_taxonomy = real_commands - taxonomy_commands
    stale_in_taxonomy = taxonomy_commands - real_commands
    assert not missing_from_taxonomy, (
        f"cli.py commands with no taxonomy entry: {missing_from_taxonomy}"
    )
    assert not stale_in_taxonomy, (
        f"taxonomy entries for commands no longer in cli.py: {stale_in_taxonomy}"
    )
