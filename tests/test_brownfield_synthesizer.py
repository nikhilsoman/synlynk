"""Tests for synlynk.goal_synthesizer: Brownfield evidence mapping and
ambient 1-shot fleet enrichment with offline fail-safe."""

from unittest.mock import patch

from synlynk.goal_synthesizer import (
    enrich_goals_ambient,
    synthesize_brownfield_goals,
)

LOW_RATIO_EVIDENCE = {
    "code_files": [f"src/mod_{i}.py" for i in range(20)],
    "test_files": ["tests/test_mod_0.py"],
    "manifests": ["pyproject.toml"],
    "open_issues": [{"number": 1, "title": "Fix bug"}],
    "languages": ["python"],
    "uncommitted_diffs": [],
}

HIGH_RATIO_EVIDENCE = {
    "code_files": [f"src/mod_{i}.py" for i in range(10)],
    "test_files": [f"tests/test_mod_{i}.py" for i in range(5)],
    "manifests": ["pyproject.toml", "package.json"],
    "open_issues": [],
    "languages": ["python", "javascript"],
    "uncommitted_diffs": ["src/mod_0.py"],
}


def _ids(goals):
    return [g["id"] for g in goals]


class TestSynthesizeBrownfieldGoals:
    def test_returns_between_3_and_5_goals(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        assert 3 <= len(goals) <= 5

    def test_always_includes_baseline_preflight_as_p0(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        baseline = next(g for g in goals if g["id"] == "goal-baseline-preflight")
        assert baseline["priority"] == "P0"
        assert baseline["title"] == "Baseline Health & Fleet Preflight Parity"

    def test_low_test_ratio_triggers_coverage_remediation(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        assert "goal-test-coverage-remediation" in _ids(goals)
        assert "goal-regression-hardening" not in _ids(goals)
        coverage_goal = next(
            g for g in goals if g["id"] == "goal-test-coverage-remediation"
        )
        assert coverage_goal["priority"] == "P0"

    def test_high_test_ratio_triggers_regression_hardening(self):
        goals = synthesize_brownfield_goals(HIGH_RATIO_EVIDENCE)
        assert "goal-regression-hardening" in _ids(goals)
        assert "goal-test-coverage-remediation" not in _ids(goals)
        regression_goal = next(
            g for g in goals if g["id"] == "goal-regression-hardening"
        )
        assert regression_goal["priority"] == "P1"

    def test_includes_dependency_modernization_goal(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        dep_goal = next(g for g in goals if g["id"] == "goal-dependency-modernization")
        assert dep_goal["priority"] == "P1"

    def test_includes_feature_acceleration_goal(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        feature_goal = next(g for g in goals if g["id"] == "goal-feature-acceleration")
        assert feature_goal["priority"] == "P1"

    def test_all_goals_target_milestone_v1(self):
        for evidence in (LOW_RATIO_EVIDENCE, HIGH_RATIO_EVIDENCE):
            goals = synthesize_brownfield_goals(evidence)
            assert all(g["target_milestone"] == "v1.0.0-rc1" for g in goals)

    def test_all_goals_conform_to_standard_schema(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        required_keys = {
            "id",
            "title",
            "category",
            "priority",
            "rationale",
            "acceptance_criteria",
            "target_milestone",
        }
        for goal in goals:
            assert required_keys.issubset(goal.keys())
            assert isinstance(goal["acceptance_criteria"], list)
            assert len(goal["acceptance_criteria"]) > 0

    def test_empty_evidence_still_produces_valid_goals(self):
        goals = synthesize_brownfield_goals({})
        assert 3 <= len(goals) <= 5
        # Zero code files -> ratio treated as 0.0 -> coverage remediation path.
        assert "goal-test-coverage-remediation" in _ids(goals)

    def test_none_evidence_does_not_raise(self):
        goals = synthesize_brownfield_goals(None)
        assert 3 <= len(goals) <= 5

    def test_goal_ids_are_unique(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        ids = _ids(goals)
        assert len(ids) == len(set(ids))


class TestEnrichGoalsAmbient:
    def test_offline_returns_original_goals_unchanged(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        with patch("synlynk.goal_synthesizer.shutil.which", return_value=None):
            result = enrich_goals_ambient(goals, LOW_RATIO_EVIDENCE)
        assert result == goals

    def test_offline_makes_zero_network_or_subprocess_calls(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)
        with patch("synlynk.goal_synthesizer.shutil.which", return_value=None):
            with patch("synlynk.goal_synthesizer.subprocess.run") as mock_run:
                enrich_goals_ambient(goals, LOW_RATIO_EVIDENCE)
        mock_run.assert_not_called()

    def test_timeout_fails_safe_to_original_goals(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)

        def _timeout_runner(harness, goals_arg, evidence, timeout):
            import subprocess as sp

            raise sp.TimeoutExpired(cmd=harness, timeout=timeout)

        with patch("synlynk.goal_synthesizer.shutil.which", return_value="/usr/bin/claude"):
            result = enrich_goals_ambient(
                goals, LOW_RATIO_EVIDENCE, timeout=0.01, harness_runner=_timeout_runner
            )
        assert result == goals

    def test_runner_exception_fails_safe_to_original_goals(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)

        def _broken_runner(harness, goals_arg, evidence, timeout):
            raise RuntimeError("harness exploded")

        with patch("synlynk.goal_synthesizer.shutil.which", return_value="/usr/bin/claude"):
            result = enrich_goals_ambient(
                goals, LOW_RATIO_EVIDENCE, harness_runner=_broken_runner
            )
        assert result == goals

    def test_runner_returning_none_fails_safe(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)

        def _noop_runner(harness, goals_arg, evidence, timeout):
            return None

        with patch("synlynk.goal_synthesizer.shutil.which", return_value="/usr/bin/claude"):
            result = enrich_goals_ambient(
                goals, LOW_RATIO_EVIDENCE, harness_runner=_noop_runner
            )
        assert result == goals

    def test_successful_enrichment_merges_refinements(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)

        def _refining_runner(harness, goals_arg, evidence, timeout):
            return {
                "goal-baseline-preflight": {
                    "title": "Baseline Health (src/mod_0.py verified)",
                }
            }

        with patch("synlynk.goal_synthesizer.shutil.which", return_value="/usr/bin/claude"):
            result = enrich_goals_ambient(
                goals, LOW_RATIO_EVIDENCE, harness_runner=_refining_runner
            )

        refined = next(g for g in result if g["id"] == "goal-baseline-preflight")
        assert refined["title"] == "Baseline Health (src/mod_0.py verified)"
        # Unrefined goals pass through unchanged.
        untouched_ids = {g["id"] for g in goals if g["id"] != "goal-baseline-preflight"}
        for goal_id in untouched_ids:
            original = next(g for g in goals if g["id"] == goal_id)
            unchanged = next(g for g in result if g["id"] == goal_id)
            assert original == unchanged

    def test_enrichment_never_raises_on_malformed_refinement(self):
        goals = synthesize_brownfield_goals(LOW_RATIO_EVIDENCE)

        def _malformed_runner(harness, goals_arg, evidence, timeout):
            return "not-a-dict"

        with patch("synlynk.goal_synthesizer.shutil.which", return_value="/usr/bin/claude"):
            result = enrich_goals_ambient(
                goals, LOW_RATIO_EVIDENCE, harness_runner=_malformed_runner
            )
        assert result == goals

    def test_default_timeout_is_3_seconds(self):
        import inspect

        sig = inspect.signature(enrich_goals_ambient)
        assert sig.parameters["timeout"].default == 3.0
