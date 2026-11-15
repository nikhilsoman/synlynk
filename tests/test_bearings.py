import pytest
from synlynk.bearings import generate_bearings_block, inject_bearings_block
from synlynk.constitution import CONSTITUTION_LAWS, DeliveryTier


def test_generate_bearings_block():
    """Verify generated bearings block includes all Tier 3 constitutional laws."""
    card = generate_bearings_block()
    assert card is not None
    assert "<!-- synlynk:bearings:start -->" in card
    assert "<!-- synlynk:bearings:end -->" in card

    # All Tier 3 (INJECTED) laws must be cited or summarized
    injected_laws = [l for l in CONSTITUTION_LAWS.values() if l.tier == DeliveryTier.INJECTED]
    for law in injected_laws:
        assert f"<!-- constitution: {law.id} -->" in card
        assert law.name in card

    # Highest stakes operational behaviors must be present
    assert "tpm wake" in card
    assert "tpm sweep" in card
    assert "--as-agent" in card
    assert "Evidence Over Assertions" in card


def test_inject_bearings_block():
    """Verify bearings card injection into instruction prompt or context."""
    base_text = "# Project Context\n\nSome guidelines here."
    injected = inject_bearings_block(base_text)
    assert "<!-- synlynk:bearings:start -->" in injected
    assert base_text.splitlines()[0] in injected

    # Re-injecting is idempotent (does not duplicate block)
    reinjected = inject_bearings_block(injected)
    assert reinjected.count("<!-- synlynk:bearings:start -->") == 1


def test_cmd_bearings_prints_to_stdout(capsys):
    from synlynk.bearings import cmd_bearings

    cmd_bearings()
    captured = capsys.readouterr().out
    assert "## Session Bearings & Constitutional Invariants" in captured
    assert "<!-- synlynk:bearings:start -->" in captured


def test_cmd_bearings_inject_file(tmp_path):
    from synlynk.bearings import cmd_bearings

    target = tmp_path / "CLAUDE.md"
    target.write_text("# Project Guidelines\n\nSome instructions.", encoding="utf-8")
    cmd_bearings(inject_file=str(target))

    content = target.read_text(encoding="utf-8")
    assert "## Session Bearings & Constitutional Invariants" in content
    assert "<!-- synlynk:bearings:start -->" in content

