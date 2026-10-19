"""Unit tests for the Open SFIA 8/9 Taxonomy Classifier Module."""

import pytest
from synlynk.sfia import (
    SFIA_TAXONOMY,
    classify_task_sfia,
    get_sfia_name,
    get_sfia_domain,
    is_valid_sfia_code,
)


def test_sfia_taxonomy_contains_core_and_expanded_disciplines():
    expected_codes = [
        "PROG",
        "TEST",
        "REQM",
        "DBDS",
        "VISU",
        "ANIM",
        "GRAP",
        "MUDI",
        "SNDD",
        "ICDV",
        "BUSA",
        "MKTG",
        "COMM",
        "PROD",
        "UNAN",
    ]
    for code in expected_codes:
        assert code in SFIA_TAXONOMY, f"Missing expected SFIA code: {code}"
        assert "name" in SFIA_TAXONOMY[code]
        assert "domain" in SFIA_TAXONOMY[code]
        assert is_valid_sfia_code(code)


def test_get_sfia_helpers():
    assert get_sfia_name("PROG") == "Software Development"
    assert get_sfia_domain("PROG") == "Development & Implementation"
    assert get_sfia_name("ANIM") == "Animation Development"
    assert get_sfia_domain("ANIM") == "Creative & Content Operations"
    assert get_sfia_name("UNKNOWN_CODE") == "Unclassified / General Operations"
    assert not is_valid_sfia_code("INVALID")


def test_classify_programming_tasks():
    queries = [
        "Fix race condition in PostgreSQL thread pool worker queue",
        "Implement binary search tree refactor in backend parser",
        "def test_parse_arguments(): return parse()",
        "feat(dispatch): add retry loop to async subprocess worker",
    ]
    for q in queries:
        code, domain, conf = classify_task_sfia(q)
        assert code == "PROG", f"Failed to classify '{q}' as PROG (got {code})"
        assert domain == "Development & Implementation"
        assert conf >= 0.5


def test_classify_testing_tasks():
    queries = [
        "Write unit test suite with mock fixtures for payment gateway",
        "Add pytest regression tests for capability sweep edge case",
        "Verify test coverage across CLI dispatcher",
        "QA test matrix validation for python 3.10 and 3.12",
    ]
    for q in queries:
        code, domain, conf = classify_task_sfia(q)
        assert code == "TEST", f"Failed to classify '{q}' as TEST (got {code})"
        assert domain == "Development & Implementation"
        assert conf >= 0.5


def test_classify_requirements_and_architecture_tasks():
    queries = [
        "Define technical specification and system architecture for multi-agent swarm",
        "Document user stories, acceptance criteria, and requirement specs for v0.24",
        "Draft RFC design document for dynamic model catalog",
    ]
    for q in queries:
        code, domain, conf = classify_task_sfia(q)
        assert code == "REQM", f"Failed to classify '{q}' as REQM (got {code})"
        assert domain == "Strategy & Architecture"
        assert conf >= 0.5


def test_classify_database_design_tasks():
    queries = [
        "Design SQLite schema migration for ledger table with WAL foreign keys",
        "Optimize PostgreSQL index queries for high throughput transactions",
        "Add database column and update relational indices in state.db",
    ]
    for q in queries:
        code, domain, conf = classify_task_sfia(q)
        assert code == "DBDS", f"Failed to classify '{q}' as DBDS (got {code})"
        assert domain == "Development & Implementation"
        assert conf >= 0.5


def test_classify_graphics_and_visual_design_tasks():
    queries = [
        "Design SVG vector icon set and typography layout for splash screen",
        "Build glassmorphic CSS styling and dark mode UI theme for dashboard",
        "Create responsive layout template with CSS flexbox and modal dialogs",
    ]
    for q in queries:
        code, domain, conf = classify_task_sfia(q)
        assert code in ("GRAP", "VISU"), f"Failed to classify '{q}' as GRAP/VISU (got {code})"
        assert conf >= 0.5


def test_classify_creative_multimedia_audio_video_tasks():
    audio_task = "Compose ambient soundtrack and sound effect Foley cues for onboarding game"
    code, domain, conf = classify_task_sfia(audio_task)
    assert code == "SNDD", f"Failed to classify audio as SNDD (got {code})"
    assert domain == "Creative & Content Operations"
    assert conf >= 0.5

    video_task = "Edit video tutorial trailer and export multi-track multimedia presentation"
    code, domain, conf = classify_task_sfia(video_task)
    assert code == "MUDI", f"Failed to classify multimedia as MUDI (got {code})"
    assert domain == "Creative & Content Operations"
    assert conf >= 0.5

    anim_task = "Render 3D skeletal keyframe animation and particle tween motion in WebGL"
    code, domain, conf = classify_task_sfia(anim_task)
    assert code == "ANIM", f"Failed to classify animation as ANIM (got {code})"
    assert domain == "Creative & Content Operations"
    assert conf >= 0.5

    vr_task = "Implement WebXR stereoscopic VR scene with spatial tracking controllers"
    code, domain, conf = classify_task_sfia(vr_task)
    assert code == "ICDV", f"Failed to classify VR as ICDV (got {code})"
    assert domain == "Creative & Content Operations"
    assert conf >= 0.5


def test_classify_business_marketing_product_tasks():
    mktg_task = "Draft press release, social media launch announcement, and marketing pitch"
    code, domain, conf = classify_task_sfia(mktg_task)
    assert code in ("MKTG", "COMM"), f"Failed to classify marketing as MKTG/COMM (got {code})"
    assert domain == "Business Operations & Strategy"
    assert conf >= 0.5

    prod_task = "Define product roadmap milestones, sprint epics, and KPI release goals"
    code, domain, conf = classify_task_sfia(prod_task)
    assert code == "PROD", f"Failed to classify product as PROD (got {code})"
    assert domain == "Business Operations & Strategy"
    assert conf >= 0.5


def test_classify_fallback_for_empty_or_unmatched():
    code, domain, conf = classify_task_sfia("")
    assert code == "UNAN"
    assert domain == "General"
    assert conf == 0.0

    code, domain, conf = classify_task_sfia("asdf qwerty zxcv 12345")
    assert code == "UNAN"
    assert domain == "General"
    assert conf <= 0.3
