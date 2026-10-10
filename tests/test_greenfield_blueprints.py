from synlynk.greenfield_blueprints import (
    BlueprintType,
    get_blueprint_catalog,
    synthesize_greenfield_goals,
)


def test_catalog_contains_dotfiles_and_personal_assistant():
    catalog = get_blueprint_catalog()

    assert "dotfiles" in catalog
    assert "personal_assistant" in catalog
    assert catalog["dotfiles"].blueprint_type is BlueprintType.DOTFILES
    assert len(catalog["personal_assistant"].available_charters) >= 6


def test_dotfiles_goal_synthesis():
    goals = synthesize_greenfield_goals("dotfiles")

    assert len(goals) >= 3
    assert goals[0]["priority"] == "P0"
    assert "symlink" in goals[0]["title"].lower() or "scaffold" in goals[0]["title"].lower()


def test_personal_assistant_synthesis_with_selected_charters():
    goals = synthesize_greenfield_goals(
        "personal_assistant",
        selected_charters=["bills", "reimbursements"],
    )

    assert len(goals) >= 3
    assert goals[0]["priority"] == "P0"
    assert "oauth" in goals[0]["title"].lower() or "credentials" in goals[0]["title"].lower()
    charter_goal = next(
        goal
        for goal in goals
        if "charter" in goal["category"] or "charter" in goal["title"].lower()
    )
    assert "bills" in charter_goal["rationale"].lower() or "bills" in str(
        charter_goal["acceptance_criteria"]
    ).lower()
