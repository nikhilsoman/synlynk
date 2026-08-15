"""Regression guard for the job-truth/gh-write consolidation spec (#701).

Asserts every known terminal-status-deciding code path for a
--requires-gh-write job calls gh_write_verified (or is in the explicit,
reviewed allowlist of documented exceptions). This is a static-source check,
not a runtime behavior check — its job is to fail loudly when a new
terminal-status code path is added without wiring the GTV check, the exact
failure mode #331/#579/#935/#659 each independently exhibited.
"""
import ast
import inspect
import textwrap

import synlynk.dispatch as dispatch_mod
import synlynk.jobs as jobs_mod

# Functions known to decide a job's terminal ("did this succeed") status.
# Any new function added to this pattern-space must be added here explicitly —
# that's the point: the addition should be a deliberate, reviewed decision.
_TERMINAL_STATUS_FUNCTIONS = [
    (dispatch_mod, "_check_job_stall"),
    (jobs_mod, "_reconcile_daemon_jobs"),
]

# Functions explicitly reviewed and confirmed NOT to need gh_write_verified
# (e.g. legacy _reconcile_jobs delegates to _check_job_stall rather than
# deciding terminal status itself). Document the reason inline.
_DOCUMENTED_EXCEPTIONS = {
    # _reconcile_jobs (synlynk/jobs.py) delegates the stall-kill decision to
    # _check_job_stall via _pkg("_check_job_stall")(...) — it does not decide
    # terminal status itself, so it is exempt rather than needing its own call.
}


def _source_calls_name(func, name: str) -> bool:
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def test_all_terminal_status_functions_consult_gh_write_verified():
    missing = []
    for module, func_name in _TERMINAL_STATUS_FUNCTIONS:
        if func_name in _DOCUMENTED_EXCEPTIONS:
            continue
        func = getattr(module, func_name)
        if not _source_calls_name(func, "gh_write_verified") and not _source_calls_name(
            func, "_apply_gh_write_verification"
        ):
            missing.append(f"{module.__name__}.{func_name}")
    assert not missing, (
        f"The following terminal-status-deciding functions do not consult "
        f"gh_write_verified for --requires-gh-write jobs: {missing}. "
        f"Either wire in the check, or add a documented, reviewed exception "
        f"to _DOCUMENTED_EXCEPTIONS in this test file with a reason."
    )


def test_guard_itself_fails_when_a_function_skips_the_check():
    """Proves the guard's detection actually works (not a tautology)."""

    def fake_terminal_status_decider(job):
        # Deliberately does NOT call gh_write_verified.
        if job.get("status") == "running":
            return "failed"
        return job.get("status")

    assert not _source_calls_name(fake_terminal_status_decider, "gh_write_verified")
