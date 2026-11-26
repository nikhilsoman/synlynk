import json
import sqlite3
from pathlib import Path

from synlynk.migrations import m0042_release_packaging
from synlynk.migrations.runner import MIGRATIONS
from synlynk.policy import DEFAULT_WORKSPACE_POLICY
from synlynk.release_packaging import (
    DEFAULT_LIMITS,
    PackagePlan,
    load_limits,
    plan_goal_release,
)


EXPECTED_LIMITS = {
    "goal_story_ceiling": 30,
    "goal_token_ceiling": 1_500_000,
    "mixed_pool_cap": 5,
}


def _story(
    story_id: str,
    *,
    status: str = "ready",
    umbrella: bool = False,
    has_open_pr: bool = False,
    phase: str | None = "p1",
    estimated_tokens: int | None = None,
) -> dict:
    return {
        "story_id": story_id,
        "status": status,
        "umbrella": umbrella,
        "has_open_pr": has_open_pr,
        "phase": phase,
        "estimated_tokens": estimated_tokens,
    }


def _stories(count: int, *, phase: str | None = "p1", **overrides) -> list[dict]:
    return [
        _story(f"story-{index:02d}", phase=phase, **overrides)
        for index in range(1, count + 1)
    ]


def _plan(stories: list[dict], deps=(), **overrides) -> PackagePlan:
    return plan_goal_release(stories, deps, EXPECTED_LIMITS, **overrides)


def test_plan_keeps_thirteen_plain_stories_in_one_part():
    plan = _plan(_stories(13))

    assert plan.parts == [[f"story-{index:02d}" for index in range(1, 14)]]
    assert plan.total_stories == 13
    assert plan.total_tokens == 13 * 25_000
    assert plan.limits == EXPECTED_LIMITS
    assert plan.part_stats == [{"stories": 13, "tokens": 13 * 25_000}]


def test_plan_story_ceiling_is_inclusive():
    plan = _plan(_stories(30))

    assert len(plan.parts) == 1
    assert len(plan.parts[0]) == 30
    assert plan.escalation is None


def test_plan_lists_in_progress_and_umbrella_stories_as_context():
    packageable = _stories(12)
    context = [
        _story("underway-1", status="in_progress"),
        _story("underway-2", status="in_progress"),
        _story("underway-3", status="in_progress"),
        _story("umbrella-1", umbrella=True),
        _story("umbrella-2", umbrella=True),
        _story("umbrella-3", umbrella=True),
        _story("umbrella-4", umbrella=True),
    ]

    plan = _plan(packageable + context)

    assert plan.parts == [[story["story_id"] for story in packageable]]
    assert plan.context == [story["story_id"] for story in context]
    assert plan.total_stories == 12
    assert plan.total_tokens == 12 * 25_000


def test_plan_excludes_open_pr_story_from_both_ceilings():
    stories = _stories(30) + [
        _story("open-pr", has_open_pr=True, estimated_tokens=2_000_000)
    ]

    plan = _plan(stories)

    assert len(plan.parts) == 1
    assert len(plan.parts[0]) == 30
    assert plan.context == ["open-pr"]
    assert plan.total_stories == 30
    assert plan.total_tokens == 30 * 25_000


def test_plan_splits_only_between_whole_phases():
    stories = (
        _stories(15, phase="p1")
        + [
            _story(f"p2-{index:02d}", phase="p2")
            for index in range(1, 16)
        ]
        + [
            _story(f"p3-{index:02d}", phase="p3")
            for index in range(1, 11)
        ]
    )

    plan = _plan(stories)

    assert plan.parts == [
        [story["story_id"] for story in stories[:30]],
        [story["story_id"] for story in stories[30:]],
    ]
    assert plan.split_reasons == ["phase boundary p2 -> p3"]
    assert plan.part_stats == [
        {"stories": 30, "tokens": 750_000},
        {"stories": 10, "tokens": 250_000},
    ]


def test_plan_rejects_phase_cut_when_later_story_depends_on_earlier_story():
    stories = _stories(20, phase="p1") + [
        _story(f"p3-{index:02d}", phase="p3") for index in range(1, 21)
    ]

    plan = _plan(stories, [("p3-01", "story-01")])

    assert plan.parts == []
    assert plan.escalation == "phase cut severs dependency"


def test_plan_rejects_phase_cut_when_earlier_story_depends_on_later_story():
    stories = _stories(20, phase="p1") + [
        _story(f"p3-{index:02d}", phase="p3") for index in range(1, 21)
    ]

    plan = _plan(stories, [("story-01", "p3-01")])

    assert plan.parts == []
    assert plan.escalation == "phase cut severs dependency"


def test_plan_escalates_when_over_ceiling_without_phase_data():
    stories = (
        _stories(14, phase="build")
        + [
            _story(f"none-{index:02d}", phase=None) for index in range(1, 14)
        ]
        + [
            _story(f"empty-{index:02d}", phase="") for index in range(1, 14)
        ]
    )

    plan = _plan(stories)

    assert plan.parts == []
    assert plan.escalation == "no phase data"


def test_plan_escalates_on_cyclic_dependency():
    stories = _stories(31)

    plan = _plan(
        stories,
        [("story-01", "story-02"), ("story-02", "story-01")],
    )

    assert plan.parts == []
    assert plan.escalation == "cyclic dependency"


def test_plan_requires_approval_to_split_oversized_phase():
    plan = _plan(_stories(35))

    assert plan.parts == []
    assert plan.escalation == "phase exceeds ceiling; operator confirmation required"


def test_plan_splits_approved_oversized_phase_in_story_id_order():
    plan = _plan(_stories(35), approved_splits={"p1"})

    assert plan.parts == [
        [f"story-{index:02d}" for index in range(1, 31)],
        [f"story-{index:02d}" for index in range(31, 36)],
    ]
    assert plan.split_reasons == ["operator-approved split within phase p1"]


def test_plan_keeps_dependency_component_together_in_approved_phase_split():
    plan = _plan(
        _stories(35),
        [("story-31", "story-30")],
        approved_splits={"p1"},
    )

    assert "story-30" in plan.parts[1]
    assert "story-31" in plan.parts[1]
    assert len(plan.parts[0]) == 29


def test_plan_records_boundary_after_approved_oversized_phase():
    stories = _stories(35, phase="p1") + [_story("p2-01", phase="p2")]

    plan = _plan(stories, approved_splits={"p1"})

    assert [len(part) for part in plan.parts] == [30, 5, 1]
    assert plan.split_reasons == [
        "operator-approved split within phase p1",
        "phase boundary p1 -> p2",
    ]


def test_plan_escalates_when_dependency_component_exceeds_ceiling():
    deps = [
        (f"story-{index + 1:02d}", f"story-{index:02d}")
        for index in range(1, 31)
    ]

    plan = _plan(_stories(35), deps, approved_splits={"p1"})

    assert plan.parts == []
    assert plan.escalation == "approved phase cannot be split without severing dependency"


def test_plan_packages_independent_phases_separately_without_dependency_check():
    stories = _stories(4, phase="p1") + [
        _story(f"p2-{index:02d}", phase="p2") for index in range(1, 5)
    ]

    plan = _plan(
        stories,
        [("p2-01", "story-01")],
        independent_phases=True,
    )

    assert plan.parts == [
        [f"story-{index:02d}" for index in range(1, 5)],
        [f"p2-{index:02d}" for index in range(1, 5)],
    ]
    assert plan.split_reasons == ["independent phases p1 -> p2"]
    assert plan.escalation is None


def test_plan_token_ceiling_splits_at_phase_boundary():
    stories = _stories(15, phase="p1", estimated_tokens=100_000) + [
        _story(f"p2-{index:02d}", phase="p2", estimated_tokens=100_000)
        for index in range(1, 6)
    ]

    plan = _plan(stories)

    assert [len(part) for part in plan.parts] == [15, 5]
    assert plan.part_stats == [
        {"stories": 15, "tokens": 1_500_000},
        {"stories": 5, "tokens": 500_000},
    ]


def test_plan_null_token_estimates_leave_only_story_ceiling_binding():
    stories = _stories(30, estimated_tokens=None)

    plan = _plan(stories)

    assert len(plan.parts) == 1
    assert plan.total_tokens == 750_000


def test_plan_ignores_dependency_edge_to_story_outside_goal():
    stories = _stories(20, phase="p1") + [
        _story(f"p2-{index:02d}", phase="p2") for index in range(1, 21)
    ]

    plan = _plan(stories, [("story-01", "outside-goal")])

    assert [len(part) for part in plan.parts] == [20, 20]
    assert plan.escalation is None


def test_default_limits_are_available_in_code_and_policy():
    repo_root = Path(__file__).parents[1]
    repo_policy = json.loads((repo_root / ".synlynk" / "policy.json").read_text())

    assert DEFAULT_LIMITS == EXPECTED_LIMITS
    assert DEFAULT_WORKSPACE_POLICY["defaults"]["release_packaging"] == EXPECTED_LIMITS
    assert repo_policy["overrides"]["release_packaging"] == EXPECTED_LIMITS


def test_load_limits_merges_and_coerces_repo_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    policy_dir = tmp_path / "repo" / ".synlynk"
    policy_dir.mkdir(parents=True)
    (policy_dir / "policy.json").write_text(
        json.dumps(
            {
                "overrides": {
                    "release_packaging": {"goal_story_ceiling": "10"}
                }
            }
        )
    )

    limits = load_limits(str(tmp_path / "repo"))

    assert limits == {
        "goal_story_ceiling": 10,
        "goal_token_ceiling": 1_500_000,
        "mixed_pool_cap": 5,
    }


def test_migration_adds_release_packaging_schema_and_backfills_live_35():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE stories (story_id TEXT UNIQUE, gh_issue TEXT, status TEXT)"
    )
    conn.executemany(
        "INSERT INTO stories (story_id, gh_issue, status) VALUES (?, ?, 'ready')",
        [("parent", "5498"), ("ordinary", "5600")],
    )

    m0042_release_packaging.MIGRATION.up(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "umbrella" in columns
    assert conn.execute(
        "SELECT umbrella FROM stories WHERE story_id = 'parent'"
    ).fetchone() == (1,)
    assert conn.execute(
        "SELECT umbrella FROM stories WHERE story_id = 'ordinary'"
    ).fetchone() == (0,)

    conn.execute("INSERT INTO story_dependencies VALUES ('a', 'b')")
    conn.execute(
        "INSERT INTO release_split_approvals (goal_id, phase) VALUES ('g', 'p1')"
    )
    conn.execute(
        "INSERT INTO goal_packaging_flags (goal_id, independent_phases) "
        "VALUES ('g', 1)"
    )

    m0042_release_packaging.MIGRATION.up(conn)

    assert conn.execute("SELECT * FROM story_dependencies").fetchall() == [("a", "b")]
    assert conn.execute(
        "SELECT goal_id, phase, approved_by, approved_at "
        "FROM release_split_approvals"
    ).fetchone()[:3] == ("g", "p1", None)
    assert conn.execute("SELECT * FROM goal_packaging_flags").fetchall() == [("g", 1)]


def test_release_packaging_migration_is_registered_last():
    assert m0042_release_packaging.MIGRATION.version == 42
    assert MIGRATIONS[-1] is m0042_release_packaging.MIGRATION


def test_migration_supports_partial_databases_without_stories():
    conn = sqlite3.connect(":memory:")

    m0042_release_packaging.MIGRATION.up(conn)

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {
        "story_dependencies",
        "release_split_approvals",
        "goal_packaging_flags",
    } <= tables


def test_migration_supports_partial_stories_table_without_gh_issue():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE stories (story_id TEXT UNIQUE)")

    m0042_release_packaging.MIGRATION.up(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "umbrella" in columns
