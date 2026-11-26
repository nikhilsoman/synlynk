def test_validate_proposal_accepts_a_conforming_proposal():
    from synlynk.proposal_schema import validate_proposal

    proposal = {
        "story_id": "s1", "title": "Fix the thing", "source": "tpm",
        "severity": "normal", "github_issue": None, "tier_provenance": [],
    }
    assert validate_proposal(proposal) is None


def test_validate_proposal_rejects_unknown_severity():
    from synlynk.proposal_schema import validate_proposal

    proposal = {
        "story_id": "s1", "title": "Fix the thing", "source": "tpm",
        "severity": "URGENT!!", "github_issue": None, "tier_provenance": [],
    }
    error = validate_proposal(proposal)
    assert error is not None
    assert "severity" in error


def test_validate_proposal_rejects_non_list_tier_provenance():
    from synlynk.proposal_schema import validate_proposal

    proposal = {
        "story_id": "s1", "title": "Fix the thing", "source": "tpm",
        "severity": "normal", "github_issue": None, "tier_provenance": "sentinel",
    }
    error = validate_proposal(proposal)
    assert error is not None
    assert "tier_provenance" in error


def test_validate_proposal_rejects_non_int_github_issue():
    from synlynk.proposal_schema import validate_proposal

    proposal = {
        "story_id": "s1", "title": "Fix the thing", "source": "tpm",
        "severity": "normal", "github_issue": "not-an-int", "tier_provenance": [],
    }
    error = validate_proposal(proposal)
    assert error is not None
    assert "github_issue" in error


def test_validate_proposal_rejects_blank_required_string_field():
    from synlynk.proposal_schema import validate_proposal

    proposal = {
        "story_id": "", "title": "Fix the thing", "source": "tpm",
        "severity": "normal", "github_issue": None, "tier_provenance": [],
    }
    error = validate_proposal(proposal)
    assert error is not None
    assert "story_id" in error
