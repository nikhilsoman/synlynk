"""Fail-closed policy primitives for the graduated Local Harness pilot.

This module deliberately does not infer eligibility from free-form prompts.
Callers must provide an approved pilot class, and routing remains on the
frontier harness unless qualification and isolated execution are attested.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import PurePosixPath
from typing import Optional


PILOT_CLASSES = frozenset(
    {
        "test_summary",
        "test_diagnosis",
        "codepath_summary",
        "change_summary",
        "documentation_edit",
        "mechanical_edit",
    }
)
EXCLUDED_ROLES = frozenset({"architect", "pm", "tpm", "qa", "review"})
APPROVED_SHARES = frozenset({0.20, 0.35, 0.50})
MAX_SHARE = 0.50
REBASELINE_SHARE = 0.20
REBASELINE_PILOT_CLASSES = frozenset({"test_summary", "codepath_summary"})
LOCAL_PILOT_COMPOSE = "docker/local-pilot.compose.yaml"
_EXCLUDED_TASK_PATTERN = re.compile(
    r"\b(?:refactor|architecture|architectural|spec(?:ification)?|dependency|"
    r"deploy|merge|review|secret|repo[- ]wide|whole[- ]repo|full[- ]suite|"
    r"production\s+(?:edit|code|change|write))\b",
    re.IGNORECASE,
)
_SENSITIVE_PATH_NAMES = frozenset(
    {
        ".aws", ".ssh", ".config", "credentials", "credentials.json",
        "server.key", "private.key",
    }
)
_SENSITIVE_SUFFIXES = (".pem", ".p12", ".pfx", ".key")


@dataclass(frozen=True)
class LocalPilotDecision:
    route_local: bool
    reason: str
    pilot_class: Optional[str] = None
    share: float = 0.0
    bucket: Optional[int] = None


@dataclass(frozen=True)
class PromotionDecision:
    next_share: float
    reason: str
    rollback_required: bool = False


@dataclass(frozen=True)
class RebaselineDecision:
    """Fail-closed admission state for the separate Local re-baseline cohorts."""

    allow_admission: bool
    cohort: Optional[str]
    share: float
    pause_required: bool
    proposal_35_eligible: bool
    reason: str


class LocalPilotSetupError(RuntimeError):
    """The isolated local runner cannot be established; never run on-host."""


def find_sensitive_worktree_paths(worktree: str) -> list[str]:
    """Return likely credential/key paths that must not enter the Aider mount."""
    matches = []
    for root, dirs, files in os.walk(worktree, followlinks=False):
        dirs[:] = [name for name in dirs if name != ".git"]
        for name in [*dirs, *files]:
            lowered = name.lower()
            if (
                lowered in _SENSITIVE_PATH_NAMES
                or lowered.startswith(".env")
                or lowered.startswith("id_")
                or lowered.endswith(_SENSITIVE_SUFFIXES)
            ):
                matches.append(os.path.relpath(os.path.join(root, name), worktree))
    return sorted(set(matches))


def valid_scope_path(path: str) -> bool:
    """Reject absolute, parent-traversing, or state/credential paths."""
    candidate = PurePosixPath(str(path).replace("\\", "/"))
    return (
        bool(str(candidate))
        and not candidate.is_absolute()
        and ".." not in candidate.parts
        and ".git" not in candidate.parts
        and ".synlynk" not in candidate.parts
        and not str(path).startswith("/")
    )


def _bucket(dispatch_key: str) -> int:
    """Return a stable 0..9999 bucket for a dispatch identity."""
    digest = hashlib.sha256(
        ("synlynk-local-pilot-v1:" + dispatch_key).encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") % 10_000


def evaluate_local_pilot(
    *,
    enabled: bool,
    qualified: bool,
    isolated: bool,
    pilot_class: Optional[str],
    role: Optional[str],
    requires_gh_write: bool,
    share: float,
    dispatch_key: Optional[str],
    task: str = "",
    scope_paths: Optional[list[str]] = None,
    rebaseline: bool = False,
) -> LocalPilotDecision:
    """Decide whether an eligible dispatch belongs in the local pilot cohort.

    Unknown or missing evidence is a frontier decision. `share` is an exact
    approved stage rather than an arbitrary percentage so configuration drift
    cannot accidentally widen the cohort.
    """
    if not enabled:
        return LocalPilotDecision(False, "pilot_disabled")
    if not qualified:
        return LocalPilotDecision(False, "qualification_not_passed")
    if not isolated:
        return LocalPilotDecision(False, "isolated_runner_unavailable")
    if pilot_class not in PILOT_CLASSES:
        return LocalPilotDecision(False, "pilot_class_not_allowlisted")
    if rebaseline and pilot_class not in REBASELINE_PILOT_CLASSES:
        return LocalPilotDecision(False, "rebaseline_pilot_class_not_allowlisted")
    if (role or "").strip().lower() in EXCLUDED_ROLES:
        return LocalPilotDecision(False, "role_excluded", pilot_class=pilot_class)
    if requires_gh_write:
        return LocalPilotDecision(False, "github_write_excluded", pilot_class=pilot_class)
    if _EXCLUDED_TASK_PATTERN.search(task or ""):
        return LocalPilotDecision(False, "task_text_excluded", pilot_class=pilot_class)
    if not scope_paths:
        return LocalPilotDecision(False, "bounded_scope_required", pilot_class=pilot_class)
    if any(not valid_scope_path(path) for path in scope_paths):
        return LocalPilotDecision(False, "invalid_scope_path", pilot_class=pilot_class)
    if share not in APPROVED_SHARES or share > MAX_SHARE:
        return LocalPilotDecision(False, "share_not_an_approved_gate", pilot_class=pilot_class)
    if dispatch_key is None or not str(dispatch_key).strip():
        return LocalPilotDecision(False, "dispatch_identity_missing", pilot_class=pilot_class)

    bucket = _bucket(str(dispatch_key).strip())
    threshold = int(share * 10_000)
    if bucket >= threshold:
        return LocalPilotDecision(
            False, "outside_local_cohort", pilot_class=pilot_class,
            share=share, bucket=bucket,
        )
    return LocalPilotDecision(
        True, "eligible_local_cohort", pilot_class=pilot_class,
        share=share, bucket=bucket,
    )


def evaluate_promotion_gate(
    *,
    current_share: float,
    eligible_jobs: int,
    accepted_jobs: int,
    serious_incidents: int,
    latency_stable: bool,
    memory_stable: bool,
    rollback_drill_passed: bool = False,
) -> PromotionDecision:
    """Retired compatibility entry point; never grant automatic promotion.

    Re-baseline evidence is cohort-specific and needs a separate human
    approval after `evaluate_rebaseline` makes a proposal eligible.  Keeping
    this callable avoids turning old consumers into an accidental fallback to
    the obsolete 30/90-percent rules.
    """
    del (
        current_share,
        eligible_jobs,
        accepted_jobs,
        serious_incidents,
        latency_stable,
        memory_stable,
        rollback_drill_passed,
    )
    return PromotionDecision(0.0, "promotion_gate_retired_use_evaluate_rebaseline", True)


def evaluate_rebaseline(status: dict) -> RebaselineDecision:
    """Evaluate the 5/5 validation and 10-consecutive expansion evidence.

    The historical cohort intentionally does not participate in either
    denominator.  This decision can make a 35% proposal eligible, but it
    cannot alter the 20% Local allocation cap.
    """
    try:
        validation = status["validation"]
        expansion = status["expansion"]
        safety_failed = int(validation["safety_failed"]) + int(expansion["safety_failed"])
        validation_accepted = int(validation["accepted"])
        validation_rejected = int(validation["rejected"])
        expansion_consecutive = int(expansion["consecutive_accepted"])
    except (KeyError, TypeError, ValueError):
        return RebaselineDecision(
            False, None, 0.20, True, False, "rebaseline_status_incomplete_requires_pause"
        )

    if safety_failed > 0:
        return RebaselineDecision(
            False, None, 0.20, True, False, "hard_safety_failure_requires_pause"
        )
    if validation_rejected > 0:
        return RebaselineDecision(
            False,
            None,
            0.20,
            False,
            False,
            "validation_quality_rejection_requires_human_review",
        )
    if validation_accepted < 5:
        return RebaselineDecision(True, "validation", 0.20, False, False, "validation_incomplete")
    if expansion_consecutive >= 10:
        return RebaselineDecision(True, "expansion", 0.20, False, True, "proposal_35_eligible")
    return RebaselineDecision(True, "expansion", 0.20, False, False, "expansion_evidence_required")


def build_isolated_compose_shell(
    *,
    repo_root: str,
    worktree: str,
    prompt_file: str,
    log_file: str,
    exit_file: str,
    job_id: str,
    aider_args: list[str],
    pilot_class: str,
    scope_paths: list[str],
    env: dict,
) -> tuple[list[str], dict]:
    """Build a one-shot Docker Compose command with a closed Aider network.

    The runner builds a declared-scope-only scratch repository from the
    disposable job worktree. No out-of-scope files or host Git metadata are
    mounted into Aider. No setup failure falls back to host execution.
    """
    if not env.get("OPENAI_API_KEY"):
        raise LocalPilotSetupError(
            "isolated Local Harness pilot requires OPENAI_API_KEY; refusing host execution"
        )
    for name, path in (
        ("repo_root", repo_root), ("worktree", worktree),
        ("prompt_file", prompt_file),
        ("log_file", log_file), ("exit_file", exit_file),
    ):
        if not path or not os.path.isabs(path):
            raise LocalPilotSetupError(f"isolated Local Harness pilot requires an absolute {name}")
    if not os.path.isfile(prompt_file):
        raise LocalPilotSetupError("isolated Local Harness pilot prompt file is missing")
    if not os.path.isdir(worktree):
        raise LocalPilotSetupError("isolated Local Harness pilot source worktree is unavailable")
    sensitive_paths = find_sensitive_worktree_paths(worktree)
    if sensitive_paths:
        raise LocalPilotSetupError(
            "isolated Local Harness pilot worktree contains credential-like paths; refusing mount"
        )
    compose_file = os.path.join(repo_root, LOCAL_PILOT_COMPOSE)
    if not os.path.isfile(compose_file):
        raise LocalPilotSetupError("isolated Local Harness pilot Compose file is missing")
    project = re.sub(r"[^a-z0-9_-]", "-", job_id.lower())
    if not project or len(project) > 48:
        project = "job-" + hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:16]

    isolated_args = list(aider_args)
    endpoint = "http://omlx:8000/v1"
    if "--openai-api-base" in isolated_args:
        index = isolated_args.index("--openai-api-base")
        if index + 1 >= len(isolated_args):
            raise LocalPilotSetupError("Aider API base flag has no value")
        isolated_args[index + 1] = endpoint
    else:
        isolated_args.extend(["--openai-api-base", endpoint])
    isolated_args.extend(["--no-check-update", "--no-analytics"])
    isolated_args.extend(
        [
            "--chat-history-file", "/tmp/aider-chat.md",
            "--input-history-file", "/tmp/aider-input",
            "--llm-history-file", "/tmp/aider-llm.md",
            "--no-restore-chat-history", "--no-stream", "--no-gitignore",
        ]
    )

    # PATH can contain several directories; resolve Docker using shutil rather
    # than forwarding the host PATH into Aider's container.
    resolved_docker = shutil.which("docker")
    if not resolved_docker:
        raise LocalPilotSetupError("Docker is unavailable; refusing host execution")
    spawn_env = {
        key: value for key, value in env.items()
        if key in {"PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "DOCKER_HOST"}
    }
    spawn_env.update(
        {
            "PILOT_UID": str(os.getuid()),
            "PILOT_GID": str(os.getgid()),
            # The runner replaces this with a fresh declared-scope scratch repo.
            "PILOT_WORKTREE": "",
            "OPENAI_API_KEY": env["OPENAI_API_KEY"],
        }
    )
    command = [
        sys.executable,
        "-m",
        "synlynk.local_pilot_runner",
        "--repo-root", repo_root,
        "--source-worktree", worktree,
        "--prompt", prompt_file,
        "--log", log_file,
        "--exit-file", exit_file,
        "--job-id", project,
        "--pilot-class", pilot_class,
    ]
    for path in scope_paths:
        command.extend(["--scope-path", path])
    command.append("--")
    command.extend([
        *isolated_args,
    ])
    return command, spawn_env


def load_pilot_runtime(repo_root: str) -> dict:
    """Load opt-in policy and derive qualification/isolation availability."""
    settings = {}
    workspace_path = os.path.join(repo_root, ".synlynk", "workspace.json")
    try:
        with open(workspace_path, encoding="utf-8") as handle:
            workspace = json.load(handle)
        settings = workspace.get("local_pilot") or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        settings = {}

    profile_path = os.path.join(repo_root, ".agents", "local.json")
    qualified_models = set()
    try:
        with open(profile_path, encoding="utf-8") as handle:
            profile = json.load(handle)
        qualified_models = {
            model.get("id")
            for model in profile.get("models", [])
            if isinstance(model, dict)
            and model.get("id")
            and model.get("qualification") == "qualified"
            and model.get("dispatch_eligible", True)
            and str(model.get("id")).casefold().startswith("ornith")
        }
    except (OSError, json.JSONDecodeError, AttributeError):
        pass

    compose_path = os.path.join(repo_root, LOCAL_PILOT_COMPOSE)
    return {
        "enabled": settings.get("enabled") is True,
        # The re-baseline never widens the historical pilot allocation.  A
        # malformed or broader runtime value is returned for dispatch to
        # reject, rather than normalized into an accidental admission.
        "share": settings.get("share", 0.0),
        "qualified": bool(qualified_models),
        "qualified_models": sorted(qualified_models),
        "isolated": os.path.isfile(compose_path) and shutil.which("docker") is not None,
    }
