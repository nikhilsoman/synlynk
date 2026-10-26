"""synlynk doctor: installation health checks and TC-1..TC-7 compliance suite."""

import json
import difflib
import os
import shutil
import subprocess
import tempfile
import sqlite3 as _sqlite3
import sys
import time
import urllib.error
import urllib.request
import stat
from pathlib import Path

from dataclasses import dataclass as _dataclass
from typing import List as _List

from synlynk._constants import HARNESS_CAPABILITY_BASELINES, CORE_FLEET, CORE_INSTRUCTION_FILES, VERSION
from synlynk._lazy import pkg as _pkg
from synlynk.db import cmd_remediation_log
from synlynk.dispatch import dispatch_agent
from synlynk.fleet import (
    check_core_instruction_files,
    doctor_hard_fail,
    find_nested_product_state_dbs,
    repo_has_any_core_instruction_file,
)
from synlynk.probe import (
    _compute_capability_hash,
    _run_tc0,
    _run_tc1,
    _run_tc2,
    _run_tc3,
    _run_tc4,
    _run_tc5,
    _run_tc6,
    _run_tc9,
)


_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_RESET = "\033[0m"


@_dataclass
class HealthCheck:
    name: str
    status: str
    message: str
    fix: str = ""


@_dataclass
class FixPlan:
    agent: str
    target_file: str
    current_content: str
    desired_content: str
    diff: str
    needs_write: bool
    message: str


def _hc_python_version() -> HealthCheck:
    import sys

    vi = sys.version_info
    ver_str = f"Python {vi[0]}.{vi[1]}.{vi[2]}"
    if vi[:2] >= (3, 9):
        return HealthCheck("python_version", "ok", ver_str)
    return HealthCheck(
        "python_version",
        "fail",
        f"{ver_str} is below minimum (3.9)",
        fix="Upgrade to Python 3.9 or later",
    )


def _find_all_synlynk_on_path() -> _List[str]:
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    candidates: _List[str] = []
    seen = set()
    for d in path_dirs:
        d = d.strip()
        if not d:
            continue
        candidate = os.path.join(d, "synlynk")
        try:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                norm = os.path.normpath(candidate)
                if norm not in seen:
                    seen.add(norm)
                    candidates.append(norm)
        except OSError:
            continue
    return candidates


def _hc_cli_entrypoint_health() -> HealthCheck:
    """Verifies that the active synlynk binary is executable, clean of import errors,
    owned by the current user, and not shadowed by shared/system paths.
    """
    active_bin = shutil.which("synlynk")
    if not active_bin:
        return HealthCheck(
            "cli_entrypoint_health",
            "fail",
            "synlynk CLI binary not found on PATH",
            fix="Install via pipx: pipx install synlynk or curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | sh",
        )

    if not os.access(active_bin, os.X_OK):
        return HealthCheck(
            "cli_entrypoint_health",
            "fail",
            f"synlynk binary at {active_bin} is not executable",
            fix=f"Run: chmod +x {active_bin}",
        )

    # 1. Test execution of synlynk --version
    try:
        proc = subprocess.run(
            [active_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (proc.stdout or proc.stderr).strip()
        if proc.returncode != 0:
            return HealthCheck(
                "cli_entrypoint_health",
                "fail",
                f"Active synlynk binary at {active_bin} failed execution (code {proc.returncode}): {output}",
                fix="Reinstall via pipx or install.sh to repair broken entrypoint",
            )
        if "ModuleNotFoundError" in output:
            return HealthCheck(
                "cli_entrypoint_health",
                "fail",
                f"Active synlynk binary at {active_bin} has missing module dependencies: {output}",
                fix="Reinstall via pipx or install.sh to repair broken entrypoint",
            )
    except Exception as exc:
        return HealthCheck(
            "cli_entrypoint_health",
            "fail",
            f"Failed to execute synlynk binary at {active_bin}: {exc}",
            fix="Reinstall via pipx or install.sh to repair broken entrypoint",
        )

    # 2. Check ownership
    current_uid = os.getuid() if hasattr(os, "getuid") else None
    try:
        st = os.stat(active_bin)
        bin_uid = st.st_uid
    except OSError:
        bin_uid = None

    if current_uid is not None and bin_uid is not None and bin_uid != current_uid:
        return HealthCheck(
            "cli_entrypoint_health",
            "warn",
            f"Active synlynk binary at {active_bin} is owned by foreign UID {bin_uid} (current UID {current_uid}), risking permission lockouts and profile collisions.",
            fix="Install synlynk in user-local space via 'pipx install synlynk' and clean up foreign binary",
        )

    # 3. Check for PATH shadowing: shared location shadowing user-local location
    home = os.path.expanduser("~")
    all_bins = _find_all_synlynk_on_path()
    if len(all_bins) > 1:
        first_is_user = os.path.abspath(all_bins[0]).startswith(os.path.abspath(home))
        user_binaries = [b for b in all_bins[1:] if os.path.abspath(b).startswith(os.path.abspath(home))]
        if not first_is_user and user_binaries:
            user_bin = user_binaries[0]
            return HealthCheck(
                "cli_entrypoint_health",
                "warn",
                f"Shared binary at {all_bins[0]} shadows user-isolated installation at {user_bin}. Prioritize user directory in PATH.",
                fix="Add 'export PATH=\"$HOME/.local/bin:$PATH\"' to ~/.zshrc or ~/.bashrc, or run 'synlynk doctor --fix cli'",
            )

    # 4. Check version parity
    if VERSION not in output:
        return HealthCheck(
            "cli_entrypoint_health",
            "warn",
            f"Active synlynk binary reports '{output}', differing from package version v{VERSION}.",
            fix="Run 'synlynk upgrade' or reinstall via pipx to sync versions",
        )

    return HealthCheck(
        "cli_entrypoint_health",
        "ok",
        f"Active CLI binary at {active_bin} (v{VERSION}) is healthy and user-isolated",
    )


def _hc_project_init() -> HealthCheck:
    if os.path.exists(".synlynk/workspace.json") or os.path.exists(".synlynk/config.json"):
        return HealthCheck("project_init", "ok", ".synlynk/workspace.json present")
    return HealthCheck(
        "project_init",
        "fail",
        "Project not initialized — .synlynk/workspace.json missing",
        fix="Run: synlynk init",
    )


def _hc_identity_slug() -> HealthCheck:
    workspace_path = os.path.join(".synlynk", "workspace.json")
    legacy_path = os.path.join(".synlynk", "config.json")
    path = workspace_path if os.path.exists(workspace_path) else legacy_path
    if not os.path.exists(path):
        return HealthCheck("identity_slug", "warn", "No .synlynk/workspace.json; product identity checks skipped")
    try:
        with open(path) as config_file:
            data = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return HealthCheck("identity_slug", "fail", f"Cannot read {path}")
    if not isinstance(data.get("identity_slug"), str) or not data["identity_slug"].strip():
        return HealthCheck("identity_slug", "warn", "identity_slug is required for workspace add-repo; dispatch will use the repository fallback",
                           fix="Set identity_slug in .synlynk/workspace.json")
    return HealthCheck("identity_slug", "ok", f"product identity configured: {data['identity_slug']}")


def _hc_config_schema() -> HealthCheck:
    """Validates .synlynk/workspace.json and .synlynk/billing.json against their schemas."""
    from synlynk.config_schema import validate, WORKSPACE_SCHEMA, BILLING_SCHEMA

    legacy_path = os.path.join(".synlynk", "config.json")
    workspace_path = os.path.join(".synlynk", "workspace.json")
    billing_path = os.path.join(".synlynk", "billing.json")

    if not os.path.exists(workspace_path) and not os.path.exists(legacy_path):
        return HealthCheck("config_schema", "warn", "No .synlynk/workspace.json; schema check skipped")

    errors: list = []
    for path, schema in (
        (workspace_path if os.path.exists(workspace_path) else legacy_path, WORKSPACE_SCHEMA),
        (billing_path if os.path.exists(billing_path) else legacy_path, BILLING_SCHEMA),
    ):
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            return HealthCheck("config_schema", "fail", f"Cannot parse {path}: {exc}")
        errors.extend(validate(data, schema))

    if not errors:
        return HealthCheck("config_schema", "ok", ".synlynk/workspace.json and .synlynk/billing.json match expected schema")
    return HealthCheck(
        "config_schema", "fail", "; ".join(errors),
        fix="Fix the listed field(s) in .synlynk/workspace.json or .synlynk/billing.json",
    )


def _hc_policy_schema() -> HealthCheck:
    """Validates .synlynk/policy.json against the known field schema."""
    from synlynk.config_schema import validate, POLICY_SCHEMA

    path = os.path.join(".synlynk", "policy.json")
    if not os.path.exists(path):
        return HealthCheck("policy_schema", "warn", "No .synlynk/policy.json; schema check skipped")
    try:
        with open(path) as policy_file:
            data = json.load(policy_file)
    except (OSError, json.JSONDecodeError) as exc:
        return HealthCheck("policy_schema", "fail", f"Cannot parse .synlynk/policy.json: {exc}")
    errors = validate(data, POLICY_SCHEMA)
    if not errors:
        return HealthCheck("policy_schema", "ok", ".synlynk/policy.json matches expected schema")
    return HealthCheck(
        "policy_schema", "fail", "; ".join(errors),
        fix="Fix the listed field(s) in .synlynk/policy.json",
    )


def _hc_model_registry() -> HealthCheck:
    """Ensure the canonical model catalog is available to doctor consumers."""
    try:
        from synlynk import _get_db
        from synlynk.db import list_models
        from synlynk.models import register_builtin_models
        conn = _get_db()
        register_builtin_models(conn)
        count = len(list_models(conn))
        conn.commit()
        return HealthCheck("model_registry", "ok", f"{count} model(s) registered")
    except Exception as exc:
        return HealthCheck("model_registry", "warn", f"registry unavailable: {exc}", fix="Run: synlynk models discover")


def _hc_codex_model_catalog() -> HealthCheck:
    """Detect drift between the Codex catalog and the authenticated CLI config."""
    try:
        from synlynk.models import load_model_catalog

        catalog = load_model_catalog(os.getcwd())
        catalog_ids = {
            model.get("model_id")
            for model in catalog.get("models", [])
            if isinstance(model, dict) and model.get("harness") == "codex" and model.get("model_id")
        }
        catalog_ids.update(
            tier.get("codex")
            for tier in catalog.get("tiers", {}).values()
            if isinstance(tier, dict) and tier.get("codex")
        )
        catalog_ids.discard(None)
        if not catalog_ids:
            return HealthCheck("codex_model_catalog", "warn", "No Codex model IDs found in the model catalog")

        codex_home = Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
        config_path = codex_home / "config.toml"
        configured_model = None
        try:
            from synlynk.probe import _read_toml_string_value
            configured_model = _read_toml_string_value(str(config_path), "model")
        except Exception:
            configured_model = None

        executable = shutil.which("codex")
        if not executable:
            return HealthCheck("codex_model_catalog", "warn", "Codex CLI is not installed; model authorization cannot be checked")
        try:
            login = subprocess.run(
                [executable, "login", "status"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return HealthCheck("codex_model_catalog", "warn", f"Codex login status unavailable: {exc}")

        login_output = (login.stdout + "\n" + login.stderr).lower()
        if login.returncode != 0 or "logged in" not in login_output:
            return HealthCheck(
                "codex_model_catalog",
                "warn",
                "Codex CLI is not authenticated; catalog authorization check skipped",
                fix="Run: codex login",
            )
        if not configured_model:
            return HealthCheck(
                "codex_model_catalog",
                "warn",
                f"Authenticated Codex has no model configured in {config_path}",
                fix=f"Set model = <authorized model ID> in {config_path}",
            )
        if configured_model not in catalog_ids:
            return HealthCheck(
                "codex_model_catalog",
                "warn",
                f"Codex config model {configured_model!r} is absent from catalog IDs: {', '.join(sorted(catalog_ids))}",
                fix="Update .synlynk/models.json and the builtin fallback catalog to the authorized Codex model",
            )
        return HealthCheck(
            "codex_model_catalog",
            "ok",
            f"Authenticated Codex model {configured_model} matches the catalog",
        )
    except Exception as exc:
        return HealthCheck("codex_model_catalog", "warn", f"Codex catalog check unavailable: {exc}")


def _hc_docs_dir() -> HealthCheck:
    try:
        if _pkg("_is_migrated")():
            docs = _pkg("_synlynk_project_docs_dir")()
        else:
            docs = _pkg("_docs_dir")()
    except Exception:
        return HealthCheck(
            "docs_dir",
            "warn",
            "Could not resolve docs directory (project may not be initialized)",
            fix="Run: synlynk init",
        )
    required = ["roadmap.md", "todo.md", "memory.md"]
    missing = [f for f in required if not os.path.exists(os.path.join(docs, f))]
    if not missing:
        return HealthCheck("docs_dir", "ok", f"project-docs complete ({docs})")
    return HealthCheck(
        "docs_dir",
        "warn",
        f"project-docs missing: {', '.join(missing)}",
        fix="Run: synlynk init",
    )


def _hc_todo_drift() -> HealthCheck:
    """Warns if todo.md has drifted between migration paths or from state.db regeneration."""
    try:
        is_migrated = _pkg("_is_migrated")() if callable(_pkg("_is_migrated")) else False
        legacy_path = os.path.join(_pkg("_docs_dir")(), "todo.md") if callable(_pkg("_docs_dir")) else "project-docs/todo.md"
        migrated_path = os.path.join(_pkg("_synlynk_project_docs_dir")(), "todo.md") if callable(_pkg("_synlynk_project_docs_dir")) else ".synlynk/project-docs/todo.md"
    except Exception:
        return HealthCheck("todo_drift", "ok", "todo.md path check skipped")

    # Check for split-path divergence in migrated repos
    if is_migrated and os.path.exists(legacy_path) and os.path.exists(migrated_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as f1, open(migrated_path, "r", encoding="utf-8") as f2:
                c1, c2 = f1.read().strip(), f2.read().strip()
            if c1 != c2:
                return HealthCheck(
                    "todo_drift",
                    "warn",
                    "todo.md exists in both project-docs/ and .synlynk/project-docs/ with divergent content",
                    fix="Reconcile tasks into state.db and run: synlynk checkpoint",
                )
        except Exception:
            pass

    # Check for hand-edit drift against state.db
    detect_fn = _pkg("_detect_hand_edit")
    if callable(detect_fn):
        try:
            warning = detect_fn("todo.md")
            if warning:
                return HealthCheck(
                    "todo_drift",
                    "warn",
                    "todo.md has drifted from state.db regeneration",
                    fix="Reconcile tasks via synlynk story create or run: synlynk checkpoint",
                )
        except Exception:
            pass

    return HealthCheck("todo_drift", "ok", "todo.md is synchronized")


def _merged_pr_numbers_from_origin_main() -> set[int] | None:
    """Return PR numbers recorded in local ``origin/main`` commit messages."""
    try:
        result = subprocess.run(
            ["git", "log", "origin/main", "--format=%B"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    import re
    return {int(number) for number in re.findall(r"(?<!\w)#(\d+)\b", result.stdout or "")}


def _roadmap_merge_drift_rows(conn, merged_prs: set[int]) -> list[tuple[int, int]]:
    """Return ``(phase_id, pr_number)`` for merged PRs with incomplete phases."""
    if not merged_prs:
        return []
    rows = conn.execute(
        "SELECT rp.id, rp.status, rp.phase_title, COALESCE(rp.notes, ''), "
        "COALESCE(s.title, '') FROM roadmap_phases rp "
        "LEFT JOIN stories s ON s.story_id=rp.story_id"
    ).fetchall()
    stale = []
    for phase_id, status, title, notes, story_title in rows:
        if status == "done":
            continue
        haystack = " ".join((title or "", notes or "", story_title or ""))
        for pr_number in merged_prs:
            if f"#{pr_number}" in haystack:
                stale.append((phase_id, pr_number))
    return stale


def _hc_roadmap_merge_parity() -> HealthCheck:
    """Warn when a merged PR still has an unfinished linked roadmap phase."""
    merged_prs = _merged_pr_numbers_from_origin_main()
    if merged_prs is None:
        return HealthCheck(
            "roadmap_merge_parity", "warn", "origin/main is unavailable; merge parity was not checked",
            fix="Fetch origin/main, then run: synlynk doctor --fix roadmap",
        )
    try:
        conn = _pkg("_get_db")()
        try:
            stale = _roadmap_merge_drift_rows(conn, merged_prs)
        finally:
            conn.close()
    except Exception as exc:
        return HealthCheck("roadmap_merge_parity", "warn", f"merge parity check unavailable: {exc}")
    if not stale:
        return HealthCheck("roadmap_merge_parity", "ok", "merged PRs and linked roadmap phases are synchronized")
    prs = ", ".join(f"#{pr}" for _, pr in stale)
    return HealthCheck(
        "roadmap_merge_parity", "warn", f"merged PRs have unfinished roadmap phases: {prs}",
        fix="Run: synlynk doctor --fix roadmap",
    )


def repair_roadmap_merge_parity() -> int:
    """Mark stale phase rows done when their referenced PR is merged on origin/main."""
    merged_prs = _merged_pr_numbers_from_origin_main()
    if merged_prs is None:
        print("  origin/main is unavailable; no roadmap phases were changed")
        return 0
    conn = _pkg("_get_db")()
    try:
        stale = _roadmap_merge_drift_rows(conn, merged_prs)
        for phase_id, _ in stale:
            conn.execute("UPDATE roadmap_phases SET status='done' WHERE id=?", (phase_id,))
        conn.commit()
    finally:
        conn.close()
    if stale:
        from synlynk.db import _generate_roadmap_md
        _generate_roadmap_md()
    print(f"  repaired {len(stale)} roadmap phase(s) from merged PR evidence")
    return len(stale)


def _hc_identity_key() -> HealthCheck:
    key_path = os.path.join(os.path.expanduser("~/.synlynk"), "identity.key")
    if os.path.exists(key_path):
        pub_path = key_path + ".pub"
        if os.path.exists(pub_path):
            return HealthCheck("identity_key", "ok", "Ed25519 identity key present")
        return HealthCheck(
            "identity_key",
            "warn",
            "identity.key exists but identity.key.pub is missing",
            fix="Run: synlynk identity init",
        )
    return HealthCheck(
        "identity_key",
        "warn",
        "No identity key — capability ratings will be unsigned",
        fix="Run: synlynk identity init",
    )


def _hc_identity_roles() -> HealthCheck:
    """Diffs .synlynk/roles.yaml's declared roles against provisioned GitHub Apps."""
    from synlynk.identity_roles import load_declared_roles

    from synlynk.readiness import check_durable_role_app_material
    from synlynk.product_store import migrate_repo_apps_if_needed, resolve_github_apps_dir
    migrate_repo_apps_if_needed(".")
    apps_dir = resolve_github_apps_dir(".")

    material = check_durable_role_app_material()
    if material["status"] == "FAIL":
        return HealthCheck(
            "identity_roles",
            "fail",
            material["message"],
            fix=material["remediation"],
        )

    roles = load_declared_roles()
    missing = []
    for role in roles:
        json_path = apps_dir / f"{role}.json"
        if not os.path.exists(json_path):
            missing.append(role)
            continue
        try:
            with open(json_path) as fh:
                config = json.load(fh)
        except (OSError, ValueError):
            missing.append(role)
            continue
        if not config.get("installation_id"):
            missing.append(role)
    if not missing:
        return HealthCheck("identity_roles", "ok", f"All declared roles provisioned ({', '.join(roles)})")
    return HealthCheck(
        "identity_roles",
        "warn",
        f"Missing GitHub App identity for role(s): {', '.join(missing)}",
        fix=f"Run: synlynk identity init --role {missing[0]}" + (
            f" (and {len(missing) - 1} more)" if len(missing) > 1 else ""
        ),
    )


def _hc_identity_file_perms() -> HealthCheck:
    """Verifies .synlynk/github_apps/*.{json,pem} are still 0o600 — private key
    material and installation IDs at rest must not be group/world-readable."""
    from synlynk.product_store import migrate_repo_apps_if_needed, resolve_github_apps_dir
    migrate_repo_apps_if_needed(".")
    apps_dir = str(resolve_github_apps_dir("."))
    if not os.path.isdir(apps_dir):
        return HealthCheck("identity_file_perms", "ok", "No .synlynk/github_apps/ directory yet")
    loose = []
    for fname in sorted(os.listdir(apps_dir)):
        if not (fname.endswith(".json") or fname.endswith(".pem")):
            continue
        path = os.path.join(apps_dir, fname)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode != 0o600:
            loose.append(f"{fname} ({oct(mode)})")
    if not loose:
        return HealthCheck("identity_file_perms", "ok", "All identity files are 0o600")
    return HealthCheck(
        "identity_file_perms",
        "warn",
        f"Loose permissions on: {', '.join(loose)}",
        fix="Run: chmod 600 .synlynk/github_apps/*.json .synlynk/github_apps/*.pem",
    )


def _hc_agent_profiles() -> HealthCheck:
    """Checks that each agent in config's agent_slots has a .agents/<name>.json profile."""
    try:
        cfg = _pkg("load_config")()
    except Exception:
        return HealthCheck(
            "agent_profiles",
            "warn",
            "Could not load config — skipping agent profile check",
            fix="Run: synlynk init",
        )
    slots = cfg.get("agent_slots", {})
    if not slots:
        return HealthCheck("agent_profiles", "warn", "No agent slots configured", fix="Run: synlynk init")
    missing = [name for name in slots if not os.path.exists(os.path.join(".agents", f"{name}.json"))]
    if not missing:
        return HealthCheck("agent_profiles", "ok", f"Agent profiles present: {', '.join(sorted(slots))}")
    return HealthCheck(
        "agent_profiles",
        "warn",
        f"Missing .agents/ profiles: {', '.join(missing)}",
        fix=f"Run: synlynk agent configure <name> — for: {', '.join(missing)}",
    )


def _hc_instruction_files() -> HealthCheck:
    """Checks that per-agent instruction files exist at the repo root."""
    expected = {"claude": "CLAUDE.md", "agy": "GEMINI.md", "codex": "AGENTS.md", "grok": "GROK.md"}
    missing = [fname for fname in expected.values() if not os.path.exists(fname)]
    if not missing:
        return HealthCheck("instruction_files", "ok", "Agent instruction files present")
    return HealthCheck(
        "instruction_files",
        "warn",
        f"Missing instruction files: {', '.join(missing)}",
        fix="Run: synlynk init",
    )


def _hc_version_current() -> HealthCheck:
    """Compares installed VERSION against latest GitHub release tag (best-effort, timeout 5s)."""
    url = "https://api.github.com/repos/nikhilsoman/synlynk/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"synlynk/{VERSION}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        latest_tag = data.get("tag_name", "").lstrip("v")
        if not latest_tag:
            return HealthCheck("version_current", "warn", "Could not parse latest release tag")
        if latest_tag == VERSION:
            return HealthCheck("version_current", "ok", f"synlynk {VERSION} is up to date")

        def _ver(s):
            try:
                return tuple(int(x) for x in s.split("."))
            except ValueError:
                return (0,)

        if _ver(latest_tag) > _ver(VERSION):
            return HealthCheck(
                "version_current",
                "warn",
                f"Update available: {VERSION} → {latest_tag}",
                fix="Run: synlynk upgrade",
            )
        return HealthCheck("version_current", "ok", f"synlynk {VERSION} (latest: {latest_tag})")
    except (urllib.error.URLError, OSError):
        return HealthCheck("version_current", "warn", "Version check skipped (offline or timeout)")
    except Exception:
        return HealthCheck("version_current", "warn", "Version check failed (unexpected error)")


def _agy_settings_path() -> str:
    return os.path.expanduser("~/.gemini/antigravity-cli/settings.json")


def _load_json_file(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        content = fh.read().strip()
    if not content:
        return {}
    return json.loads(content)


def _dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _build_agy_fix_plan() -> FixPlan:
    target_file = _agy_settings_path()
    current = _load_json_file(target_file)
    permissions = current.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}
    allow_rules = permissions.get("allow")
    if not isinstance(allow_rules, list):
        allow_rules = []

    required_rules = [
        "command(gh pr review)",
        "command(gh pr comment)",
        "command(gh pr merge)",
    ]
    desired_rules = list(allow_rules)
    for rule in required_rules:
        if rule not in desired_rules:
            desired_rules.append(rule)

    desired = dict(current)
    desired_permissions = dict(permissions)
    desired_permissions["allow"] = desired_rules
    desired["permissions"] = desired_permissions

    current_content = _dump_json(current)
    desired_content = _dump_json(desired)
    diff = "".join(
        difflib.unified_diff(
            current_content.splitlines(keepends=True),
            desired_content.splitlines(keepends=True),
            fromfile=target_file,
            tofile=target_file,
        )
    )
    needs_write = current_content != desired_content
    message = (
        "Agy settings.json is missing required GitHub write allow-rules."
        if needs_write
        else "Agy settings.json already contains required GitHub write allow-rules."
    )
    return FixPlan(
        agent="agy",
        target_file=target_file,
        current_content=current_content,
        desired_content=desired_content,
        diff=diff,
        needs_write=needs_write,
        message=message,
    )


def _confirm_fix(prompt: str, args=None) -> bool:
    if getattr(args, "yes", False):
        return True
    if not sys.stdin.isatty():
        return False
    response = input(f"{prompt} [y/N] ").strip().lower()
    return response in {"y", "yes"}


_TC7_REQUIRED_ALLOW_RULES = [
    "command(gh pr review)",
    "command(gh pr comment)",
    "command(gh pr merge)",
]


def _run_tc7(settings_path: str = None) -> dict:
    """TC-7: Agy (Gemini antigravity-cli) gh-write allow-rules preflight.

    Routing a --requires-gh-write task to Agy without these scoped allow-rules
    already present in its local settings produces a silent no-op or an
    interactive permission prompt Agy cannot answer headless (#426). This
    check must run BEFORE routing, not after -- the failure mode it prevents
    is discovering the gap only once the dispatched job has already burned
    its quota.
    """
    if settings_path is None:
        settings_path = os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
    if not os.path.exists(settings_path):
        return {
            "passed": False,
            "missing": list(_TC7_REQUIRED_ALLOW_RULES),
            "error": "settings file not found",
        }
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "missing": list(_TC7_REQUIRED_ALLOW_RULES),
            "error": str(exc),
        }
    present = set(settings.get("permissions", {}).get("allow", []))
    missing = [rule for rule in _TC7_REQUIRED_ALLOW_RULES if rule not in present]
    return {"passed": not missing, "missing": missing, "error": ""}


def _agy_mcp_config_path() -> str:
    return os.path.expanduser("~/.gemini/config/mcp_config.json")


def _run_tc8(mcp_config_path: str = None) -> dict:
    """TC-8: Agy (Gemini antigravity-cli) Stitch MCP configuration preflight.

    Checks that ~/.gemini/config/mcp_config.json contains an active, enabled
    Stitch MCP server configuration. Without this, Agy cannot call Stitch MCP
    tools in headless dispatch (#573).
    """
    if mcp_config_path is None:
        mcp_config_path = _agy_mcp_config_path()
    if not os.path.exists(mcp_config_path):
        return {
            "passed": False,
            "error": "mcp_config file not found",
        }
    try:
        with open(mcp_config_path) as f:
            content = f.read().strip()
            if not content:
                return {
                    "passed": False,
                    "error": "mcp_config file is empty",
                }
            cfg = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "error": str(exc),
        }
    if not isinstance(cfg, dict):
        return {
            "passed": False,
            "error": "mcp_config is invalid JSON (expected object)",
        }
    servers = cfg.get("mcpServers")
    if not isinstance(servers, dict) or "stitch" not in servers:
        return {
            "passed": False,
            "error": "stitch MCP server not configured in mcpServers",
        }
    stitch_cfg = servers.get("stitch")
    if not isinstance(stitch_cfg, dict):
        return {
            "passed": False,
            "error": "stitch MCP server configuration is invalid (expected object)",
        }
    if stitch_cfg.get("disabled", False):
        return {
            "passed": False,
            "error": "stitch MCP server is disabled in mcpServers",
        }
    cmd = stitch_cfg.get("command")
    if cmd != "npx":
        return {
            "passed": False,
            "error": f"stitch MCP server command is '{cmd}' (expected 'npx')",
        }
    args = stitch_cfg.get("args")
    if not isinstance(args, list) or not any("stitch-mcp" in str(a) for a in args):
        return {
            "passed": False,
            "error": "stitch MCP server args missing 'stitch-mcp'",
        }
    return {"passed": True, "error": ""}


def _build_agy_stitch_fix_plan() -> FixPlan:
    target_file = _agy_mcp_config_path()
    current = _load_json_file(target_file)
    servers = current.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    desired_servers = dict(servers)
    desired_servers["stitch"] = {
        "command": "npx",
        "args": ["-y", "stitch-mcp@1.0.0"],
        "disabled": False,
        "env": {
            "GOOGLE_CLOUD_PROJECT": "gen-lang-client-0187568210",
        },
    }
    desired = dict(current)
    desired["mcpServers"] = desired_servers
    current_content = _dump_json(current)
    desired_content = _dump_json(desired)
    diff = "".join(
        difflib.unified_diff(
            current_content.splitlines(keepends=True),
            desired_content.splitlines(keepends=True),
            fromfile=target_file,
            tofile=target_file,
        )
    )
    needs_write = current_content != desired_content
    message = (
        "Agy mcp_config.json is missing required Stitch MCP server configuration."
        if needs_write
        else "Agy mcp_config.json already contains required Stitch MCP server configuration."
    )
    return FixPlan(
        agent="agy",
        target_file=target_file,
        current_content=current_content,
        desired_content=desired_content,
        diff=diff,
        needs_write=needs_write,
        message=message,
    )


def _apply_fix_plan(plan: FixPlan, operator: str) -> None:
    os.makedirs(os.path.dirname(plan.target_file), exist_ok=True)
    with open(plan.target_file, "w") as fh:
        fh.write(plan.desired_content)
    cmd_remediation_log(
        agent=plan.agent,
        target_file=plan.target_file,
        exact_diff=plan.diff,
        operator=operator,
    )


def _fix_cli_path(args=None) -> int:
    home = Path(os.path.expanduser("~"))
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        rc_file = home / ".zshrc"
    else:
        rc_file = home / ".bashrc"

    if not rc_file.exists():
        fallback_rc = home / ".zshrc" if (home / ".zshrc").exists() else home / ".bashrc"
        rc_file = fallback_rc

    export_line = 'export PATH="$HOME/.local/bin:$PATH"'
    content = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""

    if export_line not in content:
        should_write = True
        if args is not None and not getattr(args, "yes", False):
            should_write = _confirm_fix(f"Add user-local PATH precedence to {rc_file}?", args=args)
        if should_write:
            with open(rc_file, "a", encoding="utf-8") as f:
                f.write(f"\n# Added by synlynk doctor --fix cli: ensure user-local binaries precede shared binaries\n{export_line}\n")
            print(f"  Wrote user-local PATH precedence to {rc_file}")
        else:
            print(f"  Aborted adding PATH precedence to {rc_file}")
            return 1
    else:
        print(f"  PATH configuration in {rc_file} already includes user-local bin precedence.")

    # Check for foreign/broken shared binaries
    for shared_path in ["/opt/homebrew/bin/synlynk", "/usr/local/bin/synlynk"]:
        p = Path(shared_path)
        if p.exists():
            try:
                p.unlink()
                print(f"  Removed obsolete shared binary {shared_path}")
            except OSError:
                print(f"  ⚠ Notice: To remove foreign-owned shared binary, run:")
                print(f"    sudo rm -f {shared_path}")

    return 0


def cmd_doctor_fix(agent: str, args=None) -> int:
    if agent == "cli":
        return _fix_cli_path(args=args)
    if agent != "agy":
        raise ValueError("synlynk doctor --fix currently supports agy, roadmap, or cli")

    plans = [_build_agy_fix_plan(), _build_agy_stitch_fix_plan()]
    active_plans = [p for p in plans if p.needs_write]

    if not active_plans:
        for plan in plans:
            print(f"No diff for {plan.target_file} (already compliant).")
            print(f"  {plan.message}")
        return 0

    exit_code = 0
    for plan in active_plans:
        print(plan.diff or f"No diff for {plan.target_file}.")
        should_write = _confirm_fix(f"Apply remediation to {plan.target_file}?", args=args)
        if not should_write:
            print("  Aborted. No files written.")
            exit_code = 1
            continue

        operator = "non-interactive --yes" if getattr(args, "yes", False) else "interactive confirm"
        _apply_fix_plan(plan, operator=operator)
        print(f"  Wrote {plan.target_file}")

    return exit_code


def _hc_model_rates() -> HealthCheck:
    from synlynk.costs import _load_model_rates
    rates = _load_model_rates()
    rates_updated_at = rates.get("rates_updated_at")
    if not rates_updated_at:
        return HealthCheck(
            "model_rates",
            "warn",
            "Model rates have never been updated (using hardcoded defaults)",
            fix="Run 'synlynk init' to seed '.synlynk/model_rates.json'",
        )
    try:
        t_parsed = time.mktime(time.strptime(rates_updated_at, "%Y-%m-%d"))
        age_days = (time.time() - t_parsed) / 86400
    except (ValueError, TypeError):
        return HealthCheck(
            "model_rates",
            "warn",
            f"Model rates have invalid timestamp: {rates_updated_at}",
            fix="Update 'rates_updated_at' to YYYY-MM-DD in '.synlynk/model_rates.json'",
        )
    if age_days > 90:
        return HealthCheck(
            "model_rates",
            "warn",
            f"Model rates are stale (updated {rates_updated_at}, {int(age_days)} days ago)",
            fix="Update the rates_updated_at timestamp or re-run 'synlynk init' to refresh '.synlynk/model_rates.json'",
        )
    return HealthCheck(
        "model_rates",
        "ok",
        f"Model rates are fresh (updated {rates_updated_at})",
    )


_PR_REVIEW_CYCLES_WINDOW_DAYS = 30
_PR_REVIEW_CYCLES_MIN_SAMPLES = 3
_PR_REVIEW_CYCLES_WARN_THRESHOLD = 1.5


def _hc_pr_review_cycles() -> HealthCheck:
    """Flags agents/roles with an elevated average pr_review_cycles over a recent window."""
    try:
        conn = _pkg("_get_db")()
        rows = conn.execute(
            "SELECT agent, AVG(pr_review_cycles), COUNT(*) FROM capability_ratings "
            "WHERE pr_review_cycles IS NOT NULL "
            f"AND ts > datetime('now', '-{_PR_REVIEW_CYCLES_WINDOW_DAYS} days') "
            "GROUP BY agent"
        ).fetchall()
    except Exception:
        return HealthCheck(
            "pr_review_cycles",
            "warn",
            "Could not read capability_ratings — skipping pr_review_cycles check",
        )

    elevated = [
        (agent, avg_cycles, count)
        for agent, avg_cycles, count in rows
        if count >= _PR_REVIEW_CYCLES_MIN_SAMPLES and avg_cycles is not None
        and avg_cycles > _PR_REVIEW_CYCLES_WARN_THRESHOLD
    ]

    if not elevated:
        return HealthCheck(
            "pr_review_cycles",
            "ok",
            f"No agent has elevated PR review cycles (no data, or all below "
            f"{_PR_REVIEW_CYCLES_WARN_THRESHOLD} avg over last {_PR_REVIEW_CYCLES_WINDOW_DAYS}d)",
        )

    elevated.sort(key=lambda t: t[1], reverse=True)
    summary = ", ".join(f"{agent} ({avg_cycles:.1f} avg, n={count})" for agent, avg_cycles, count in elevated)
    return HealthCheck(
        "pr_review_cycles",
        "warn",
        f"Elevated PR review cycles over last {_PR_REVIEW_CYCLES_WINDOW_DAYS}d: {summary}",
        fix="Review recent PRs from the flagged agent(s) for recurring rework patterns; "
            "consider adjusting task_allocation routing in .synlynk/policy.json if the pattern holds",
    )


def cleanup_selftest_workspaces(temp_root: str = None) -> int:
    """Remove orphaned synlynk selftest scratch workspaces under the temp dir."""
    root = temp_root or tempfile.gettempdir()
    stale_before = time.time() - 3600
    removed = 0
    try:
        entries = os.listdir(root)
    except OSError:
        return 0
    for name in entries:
        if not name.startswith("synlynk-selftest-"):
            continue
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        owner_path = os.path.join(path, ".owner.json")
        try:
            with open(owner_path) as owner_file:
                owner_data = json.load(owner_file)
                pid = owner_data.get("pid") if isinstance(owner_data, dict) else None
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                raise ValueError("owner PID must be a positive integer")
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            try:
                mtime = os.path.getmtime(path)
                # Unowned or invalid owner: only purge if older than 1h AND beyond 600s grace window
                if mtime > stale_before or mtime > (time.time() - 600):
                    continue
            except OSError:
                continue
        else:
            try:
                os.kill(pid, 0)
                continue  # process is alive: unconditionally preserve active selftest scratch
            except ProcessLookupError:
                pass  # PID confirmed dead
            except (PermissionError, OSError):
                continue  # non-zero / permission failure: fail closed to preserve workspace
        try:
            shutil.rmtree(path)
            removed += 1
        except OSError:
            pass
    return removed


def _check_dual_ledger_sync() -> dict:
    """Report legacy repo state without opening it as a second ledger."""
    try:
        from synlynk import get_state_db_path, _project_root
        active_path = get_state_db_path()
        root = _project_root()
        if not root:
            return {"passed": True, "detail": "not a project root"}
        fallback_path = os.path.abspath(os.path.join(root, ".synlynk", "state.db"))
        if not os.path.exists(fallback_path) or os.path.abspath(fallback_path) == os.path.abspath(active_path):
            return {"passed": True, "detail": "single ledger active"}
        return {
            "passed": False,
            "detail": f"legacy non-canonical ledger present: {fallback_path}; not opened or synchronized",
        }
    except Exception as exc:
        return {"passed": True, "detail": f"skipped ({exc})"}


def _hc_dual_ledger_sync() -> HealthCheck:
    sync_res = _check_dual_ledger_sync()
    if not sync_res["passed"]:
        return HealthCheck(
            "dual_ledger_sync",
            "warn",
            f"state.db drift detected: {sync_res['detail']}",
            fix="inventory or explicitly quarantine the legacy ledger; do not synchronize it",
        )
    return HealthCheck("dual_ledger_sync", "ok", sync_res["detail"])


def _hc_product_state_db_leftover() -> HealthCheck:
    """Warn about the legacy repo graph after product migration."""
    try:
        from synlynk.product_store import identity_slug_from_config, state_db_path
        from synlynk.state_registry import canonical_path
        slug = identity_slug_from_config(".")
        product_db = canonical_path(slug, state_db_path(slug))
        repo_db = os.path.abspath(os.path.join(os.getcwd(), ".synlynk", "state.db"))
        if product_db.exists() and os.path.isfile(repo_db) and os.path.abspath(repo_db) != os.path.abspath(product_db):
            return HealthCheck(
                "product_state_db_leftover", "warn",
                f"legacy repo state.db remains after product migration: {repo_db}",
                fix="Keep the product state.db authoritative; remove the repo copy after review",
            )
        return HealthCheck("product_state_db_leftover", "ok", "no legacy repo state.db remains")
    except Exception as exc:
        return HealthCheck("product_state_db_leftover", "warn", f"check unavailable: {exc}")


def _hc_product_policy_merge_types() -> HealthCheck:
    """Fail when product can_merge names a non-canonical QA type."""
    try:
        from synlynk.policy import load_policy
        from synlynk.product_store import identity_slug_from_config
        from synlynk.types_registry import load_types
        policy = load_policy(os.getcwd())
        types = load_types(identity_slug_from_config("."))
        invalid = [role for role in policy.get("merge_authority", {}).get("can_merge", [])
                   if role in types and not (types[role].get("canonical") and types[role].get("kind") == "qa")]
        if invalid:
            return HealthCheck("product_policy_merge_types", "fail", f"can_merge contains non-canonical QA type(s): {', '.join(invalid)}")
        return HealthCheck("product_policy_merge_types", "ok", "can_merge contains only canonical QA types")
    except Exception as exc:
        return HealthCheck("product_policy_merge_types", "warn", f"check unavailable: {exc}")


def _hc_product_specialist_apps() -> HealthCheck:
    try:
        from synlynk.product_store import configured_identity_slug, github_apps_dir
        from synlynk.types_registry import load_types
        slug = configured_identity_slug(".")
        if not slug:
            return HealthCheck("product_specialist_apps", "warn", "specialist App check skipped without identity_slug")
        missing = [type_id for type_id, info in load_types(slug).items()
                   if not info.get("canonical") and not (github_apps_dir(slug) / f"{type_id}.json").exists()]
        if missing:
            return HealthCheck("product_specialist_apps", "warn",
                               f"specialist/connector App JSON missing: {', '.join(sorted(missing))}")
        return HealthCheck("product_specialist_apps", "ok", "specialist App JSON present")
    except Exception as exc:
        return HealthCheck("product_specialist_apps", "warn", f"check unavailable: {exc}")


def _hc_fleet_parity() -> HealthCheck:
    """Check adoption parity across directives, config roster, and policy authority."""
    from synlynk.parity import check_fleet_parity
    res = check_fleet_parity(".")
    if res.get("status") == "PASS":
        return HealthCheck("fleet_parity", "ok", res.get("message", "Full parity active"))
    return HealthCheck(
        "fleet_parity",
        "warn",
        res.get("message", "Drift detected"),
        fix=res.get("remediation", "Run `synlynk heal --parity`"),
    )


def _hc_capability_reassessment() -> HealthCheck:
    """Warn when the living harness baseline needs its scheduled review."""
    try:
        from synlynk.capability_watch import capability_sweep_status

        status = capability_sweep_status(_pkg("_get_db")())
        if not status["overdue"]:
            return HealthCheck(
                "capability_reassessment",
                "ok",
                f"last sweep {status['last_sweep_at']} ({status['jobs_since_sweep']} jobs since)",
            )
        return HealthCheck(
            "capability_reassessment",
            "warn",
            f"capability sweep overdue ({status['jobs_since_sweep']} jobs since last sweep; "
            f"threshold {status['job_threshold']} or {status['max_age_days']} days)",
            fix="Run: synlynk capability sweep",
        )
    except Exception as exc:
        return HealthCheck("capability_reassessment", "warn", f"cadence check unavailable: {exc}")


def _hc_gh_host_auth_audit() -> HealthCheck:
    """Surface explicit host GitHub-auth calls recorded by the gh guard."""
    telemetry_file = os.path.join(".synlynk", "telemetry.json")
    try:
        with open(telemetry_file) as handle:
            events = json.load(handle)
        events = [event for event in events if event.get("type") == "gh_host_auth"]
    except (OSError, json.JSONDecodeError) as exc:
        return HealthCheck("gh_host_auth_audit", "warn", f"audit unavailable: {exc}")
    if not events:
        return HealthCheck("gh_host_auth_audit", "ok", "No host-auth GitHub calls recorded")
    latest = events[-1]
    return HealthCheck(
        "gh_host_auth_audit",
        "warn",
        f"{len(events)} host-auth GitHub call(s); latest {latest.get('recorded_at', 'unknown')} "
        f"by {latest.get('actor', 'unknown')} on {latest.get('repo', 'unknown')}: "
        f"{latest.get('gh_call', 'unknown')}",
        fix="Review .synlynk/telemetry.json and provision a role App token when possible",
    )


def _hc_spof_audit() -> HealthCheck:
    """Audit workspace for single points of failure across harness redundancy and roles."""
    try:
        workspace_path = os.path.join(".synlynk", "workspace.json")
        legacy_path = os.path.join(".synlynk", "config.json")
        config_path = workspace_path if os.path.exists(workspace_path) else legacy_path
        if not os.path.exists(config_path):
            return HealthCheck("spof_audit", "warn", "No .synlynk/workspace.json; SPOF audit skipped")

        with open(config_path) as f:
            data = json.load(f)

        agents = data.get("agents", {})
        if not agents or len(agents) < 2:
            return HealthCheck(
                "spof_audit",
                "warn",
                "Single harness configured; fleet lacks multi-agent redundancy",
                fix="Run: synlynk harness add <harness> to add fallback execution harnesses",
            )

        return HealthCheck(
            "spof_audit",
            "ok",
            f"Multi-agent redundancy verified ({len(agents)} active harnesses configured)",
        )
    except Exception as exc:
        return HealthCheck("spof_audit", "warn", f"SPOF audit unavailable: {exc}")


def _hc_memory_leak() -> HealthCheck:
    """Monitor process RSS memory footprint and heap headroom to guard against memory leaks."""
    try:
        import platform
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS returns bytes, Linux returns kilobytes
        rss_mb = (usage / (1024 * 1024)) if platform.system() == "Darwin" else (usage / 1024)

        if rss_mb > 1024:
            return HealthCheck(
                "memory_leak",
                "warn",
                f"Elevated process RSS memory usage: {rss_mb:.1f} MB (threshold 1024 MB)",
                fix="Restart long-running daemon workers",
            )
        return HealthCheck(
            "memory_leak",
            "ok",
            f"Process RSS memory baseline normal ({rss_mb:.1f} MB)",
        )
    except Exception as exc:
        return HealthCheck("memory_leak", "warn", f"Memory leak check unavailable: {exc}")


def _hc_daemon_service() -> HealthCheck:
    """Checks whether synlynk daemon is installed under OS process supervision (launchd/systemd)."""
    from synlynk.daemon import _daemon_service_path

    service_path = _daemon_service_path()
    if service_path is None:
        return HealthCheck("daemon_service", "ok", "Daemon supervision check not applicable for this environment")
    if os.path.exists(service_path):
        kind = "launchd" if sys.platform == "darwin" else "systemd"
        return HealthCheck("daemon_service", "ok", f"Daemon {kind} service installed: {service_path}")
    kind = "launchd" if sys.platform == "darwin" else "systemd"
    return HealthCheck(
        "daemon_service",
        "warn",
        f"Synlynk daemon is not registered as a background system service ({kind})",
        fix="Run 'synlynk daemon --install-service' to supervise daemon across crashes/reboots",
    )


def _hc_daemon_liveness() -> HealthCheck:
    """Detect a dead synlynk daemon process, including the gh:#2261 detached-child case."""
    from synlynk.daemon import (
        _daemon_service_installed,
        _daemon_state_path,
        _probe_pidfile_health,
    )

    pidfile = _daemon_state_path("daemon.pid")
    health = _probe_pidfile_health(pidfile)
    if health == "running":
        return HealthCheck("daemon_liveness", "ok", "Synlynk daemon process is running")
    if health == "zombie":
        return HealthCheck(
            "daemon_liveness",
            "fail",
            "Synlynk daemon pidfile exists but process is dead",
            fix="Run 'synlynk daemon stop && synlynk daemon start'",
        )
    if _daemon_service_installed():
        return HealthCheck(
            "daemon_liveness",
            "fail",
            "Daemon service is installed but the process is not running "
            "(detached child may have died without KeepAlive recovery)",
            fix="Run 'synlynk daemon start' (or 'synlynk daemon restart')",
        )
    return HealthCheck(
        "daemon_liveness",
        "warn",
        "Synlynk daemon is not running",
        fix="Run 'synlynk daemon start' or 'synlynk daemon --install-service'",
    )


HEALTH_CHECKS = [
    _hc_python_version,
    _hc_cli_entrypoint_health,
    _hc_project_init,
    _hc_identity_slug,
    _hc_config_schema,
    _hc_policy_schema,
    _hc_model_registry,
    _hc_codex_model_catalog,
    _hc_docs_dir,
    _hc_todo_drift,
    _hc_roadmap_merge_parity,
    _hc_identity_key,
    _hc_identity_roles,
    _hc_identity_file_perms,
    _hc_agent_profiles,
    _hc_instruction_files,
    _hc_model_rates,
    _hc_pr_review_cycles,
    _hc_version_current,
    _hc_dual_ledger_sync,
    _hc_product_state_db_leftover,
    _hc_product_policy_merge_types,
    _hc_product_specialist_apps,
    _hc_fleet_parity,
    _hc_capability_reassessment,
    _hc_gh_host_auth_audit,
    _hc_spof_audit,
    _hc_memory_leak,
    _hc_daemon_service,
    _hc_daemon_liveness,
]


def _print_health_check_report(checks: _List) -> bool:
    _STATUS_ICON = {"ok": f"{_GREEN}✓{_RESET}", "warn": f"{_YELLOW}⚠{_RESET}", "fail": f"\033[31m✗{_RESET}"}

    results = [fn() for fn in checks]
    failed = [r for r in results if r.status == "fail"]
    warned = [r for r in results if r.status == "warn"]

    print(f"\n{_BOLD}synlynk doctor{_RESET}\n")
    for r in results:
        icon = _STATUS_ICON.get(r.status, "?")
        print(f"  {icon}  {r.name}: {r.message}")
        if r.fix and r.status != "ok":
            print(f"     {_DIM}→ {r.fix}{_RESET}")

    print()
    if failed:
        print(f"  {len(failed)} check(s) failed — fix these before running synlynk.")
    elif warned:
        print(f"  {len(warned)} advisory warning(s). Everything should still work.")
    else:
        print(f"  {_GREEN}All checks passed.{_RESET}")
    print()
    return bool(failed)


def cmd_doctor(args=None, checks: _List = None) -> int:
    """Runs all registered health checks and prints a formatted report.

    Returns exit code: 0 if all checks ok/warn, 1 if any check fails.
    """
    if args is not None and getattr(args, "fix", None) == "roadmap":
        repair_roadmap_merge_parity()
        return 0
    if args is not None and getattr(args, "version", False) is True:
        from synlynk.release_authority import (
            format_version_authority_report,
            validate_release_authority,
        )

        version, findings = validate_release_authority(os.getcwd())
        print(format_version_authority_report(version, findings))
        return 1 if findings else 0
    if args is not None and getattr(args, "fix", None):
        return cmd_doctor_fix(getattr(args, "fix"), args=args)
    if args is not None and getattr(args, "readiness", False) is True:
        from synlynk.readiness import cmd_doctor_readiness
        return cmd_doctor_readiness(args=args)
    if args is not None and getattr(args, "provision", False) is True:
        from synlynk.tool_installer import provision_ecosystem_tools
        results = provision_ecosystem_tools()
        any_failed = False
        print("Provisioning ecosystem tools:")
        for tool, passed in results.items():
            status = "✓" if passed else "✗"
            if not passed:
                any_failed = True
            print(f"  {status} {tool}")
        return 1 if any_failed else 0
    if checks is not None:
        return 1 if _print_health_check_report(checks) else 0

    _print_health_check_report(HEALTH_CHECKS)

    agent_filter = getattr(args, "agent", None) if args is not None else None
    db_conn = _pkg("_get_db")()
    baselines = HARNESS_CAPABILITY_BASELINES
    agents = [agent_filter] if agent_filter else list(baselines.keys())
    any_failed = False
    # Once per doctor run: nested product state.db under worktrees is a hard fail.
    nested_state_dbs = find_nested_product_state_dbs(".")
    # Only enforce missing-instruction FAIL when the repo already looks like a
    # multi-agent project (has ≥1 instruction file). Bare test sandboxes skip.
    enforce_instructions = repo_has_any_core_instruction_file(".")
    missing_core_instructions = (
        check_core_instruction_files(".", agents=agents) if enforce_instructions else []
    )
    try:
        if nested_state_dbs:
            any_failed = True
            for path in nested_state_dbs:
                print(f"  ✗  nested product state.db: {path}")
        for agent in missing_core_instructions:
            fname = CORE_INSTRUCTION_FILES.get(agent, f"{agent}.md")
            print(f"  ✗  core instruction missing [{agent}]: {fname}")
        if missing_core_instructions:
            any_failed = True

        for agent in agents:
            print(f"\n  doctor [{agent}]")
            baseline = baselines.get(agent, {})

            tc0 = _pkg("_run_tc0")(agent, baseline)
            tc1 = _pkg("_run_tc1")(agent)
            tc2 = _pkg("_run_tc2")(agent, baseline.get("dispatch_flags", {}))
            endpoints = []
            for ep in baseline.get("network_deps", {}).get("required_endpoints", []):
                host, _, port_s = ep.rpartition(":")
                endpoints.append((host, int(port_s) if port_s.isdigit() else 443))
            tc3 = _pkg("_run_tc3")(endpoints)
            tc4 = _pkg("_run_tc4")(agent, db_conn)
            tc5_files = dict(CORE_INSTRUCTION_FILES)
            tc5_targets = {a: tc5_files[a] for a in agents if a in tc5_files and os.path.exists(tc5_files[a])}
            tc5_skips = []
            if "local" in agents:
                tc5_skips.append("local has no directive file configured; TC-5 intentionally skipped")
            tc5 = _pkg("_run_tc5")(tc5_targets)
            # Run for the four dispatch harnesses.  TC-6 parses gh output
            # because gh auth status can exit 0 for an invalid token.  The
            # check helper accepts an explicit child env for callers that
            # already have one; doctor itself runs headlessly in the dispatch
            # runner's environment.
            tc6 = (
                _pkg("_run_tc6")(agent)
                if agent in CORE_FLEET
                else {"passed": True, "skipped": "not a dispatch harness"}
            )
            tc7 = (
                _run_tc7()
                if agent == "agy"
                else {"passed": True, "skipped": "not Agy"}
            )
            live_probe = getattr(args, "live_probe", False) if args is not None else False
            tc9 = _run_tc9(agent, live=live_probe, db_conn=db_conn)

            # TC-5 is warn-only for exit code; still surfaces as ⚠ below.
            hard_tcs_passed = (
                tc0["passed"] and tc1["passed"] and tc2["passed"]
                and tc3["passed"] and tc4["passed"]
                and tc6["passed"] and tc7["passed"]
                # Grok's TC-9 result is the authoritative shell/gh-write
                # capability signal.  A denied shell must not look healthy
                # merely because the wrapper exited zero.
                and (agent != "grok" or tc9["passed"])
            )
            agent_missing = [agent] if agent in missing_core_instructions else []
            # Nested DBs already counted once above; avoid re-flagging per agent.
            hard = doctor_hard_fail(
                tc_results={
                    "tc2": tc2["passed"],
                    "tc3": tc3["passed"],
                    "tc5": tc5["passed"],
                },
                missing_instructions=agent_missing if agent in CORE_FLEET else [],
                nested_state_dbs=[],
            )
            if not hard_tcs_passed or hard:
                any_failed = True
            status = "ok" if hard_tcs_passed and not hard else "degraded"
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            capability_hash = _pkg("_compute_capability_hash")(
                baseline.get("headless_contract", {}),
                baseline.get("dispatch_flags", {}),
            )

            db_conn.execute(
                    """
                    INSERT INTO harness_records
                        (harness_name, installed_version, compliance_status,
                         active_contract, active_flags, last_probe_at, capability_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(harness_name) DO UPDATE SET
                    harness_name=excluded.harness_name,
                    installed_version=excluded.installed_version,
                    compliance_status=excluded.compliance_status,
                    active_contract=excluded.active_contract,
                    active_flags=excluded.active_flags,
                    last_probe_at=excluded.last_probe_at,
                    capability_hash=excluded.capability_hash
                """,
                    (
                        agent,
                        "unknown",
                    status,
                    json.dumps(baseline.get("headless_contract", {})),
                    json.dumps(baseline.get("dispatch_flags", {})),
                    now,
                    capability_hash,
                ),
            )
            try:
                db_conn.execute(
                    """
                    INSERT INTO harness_version_history (harness_name, cli_version, event_type, recorded_at)
                    VALUES (?, ?, 'doctor_run', ?)
                    """,
                    (agent, "unknown", now),
                )
            except _sqlite3.IntegrityError:
                pass
            db_conn.commit()

            tc0_status = "✓" if tc0["passed"] else f"✗ schema incomplete: {tc0['schema_issues']}"
            tc1_status = "✓" if tc1["passed"] else f"✗ requires_pty={tc1.get('requires_pty')}"
            tc2_status = "✓" if tc2["passed"] else f"✗ failed={tc2['failed_flags']}"
            tc3_status = "✓" if tc3["passed"] else f"✗ unreachable={tc3['unreachable']}"
            tc4_status = "✓" if tc4["passed"] else f"✗ failed={tc4['failed_verbs']}"
            tc6_status = "✓" if tc6["passed"] else f"✗ {tc6.get('error') or 'invalid or missing credentials'}"
            tc7_status = "✓" if tc7["passed"] else "✗"
            print(f"    TC-0 schema:  {tc0_status}")
            print(f"    TC-1 stdout:  {tc1_status}")
            print(f"    TC-2 flags:   {tc2_status}")
            print(f"    TC-3 network: {tc3_status}")
            print(f"    TC-4 verbs:   {tc4_status}")
            if agent in CORE_FLEET:
                print(f"    TC-6 gh-auth: {tc6_status}")
            if agent == "agy":
                print(f"    TC-7 agy-gh-write-preflight: {tc7_status}")
                if not tc7["passed"]:
                    for rule in tc7["missing"]:
                        print(f"      missing allow-rule: {rule}")
                tc8 = _run_tc8()
                tc8_status = "✓" if tc8["passed"] else "✗"
                print(f"    TC-8 agy-stitch-mcp-preflight: {tc8_status}")
                if not tc8["passed"]:
                    print(f"      {tc8['error']}")
            if tc9:
                if tc9["passed"]:
                    tc9_note = f" ({tc9.get('mechanism', 'supported')})" if tc9.get("mechanism") else ""
                    print(f"    TC-9 gh-write: ✓{tc9_note}")
                else:
                    print(f"    TC-9 gh-write: ✗ {tc9.get('error', 'unsupported')}")
            if tc5["passed"]:
                print("    TC-5 sops:    ✓")
            else:
                for ag, missing in tc5["missing"].items():
                    print(f"    TC-5 sops:    ⚠ {ag}: missing {len(missing)} section(s): {', '.join(missing)}")
            for skip in tc5_skips:
                print(f"    TC-5 sops:    ⚪ {skip}")

            if not tc1["passed"]:
                choice = _pkg("_doctor_fix_menu")(agent, "tc1", tc1)
                if choice == "escalate":
                    _pkg("_doctor_maybe_escalate")(agent, {"tc1": tc1})
            if not tc2["passed"]:
                choice = _pkg("_doctor_fix_menu")(agent, "tc2", tc2)
                if choice == "1":
                    _pkg("cmd_configure_agent")(
                        agent,
                        flags={flag.lstrip("-"): None for flag in tc2.get("failed_flags", [])},
                        envs={},
                        network_deps=[],
                    )
                elif choice == "escalate":
                    _pkg("_doctor_maybe_escalate")(agent, {"tc2": tc2})
            if not tc3["passed"]:
                choice = _pkg("_doctor_fix_menu")(agent, "tc3", tc3)
                if choice == "1":
                    unreachable = ", ".join(f"{host}:{port}" for host, port in tc3.get("unreachable", []))
                    print(f"    {_DIM}Unreachable endpoints: {unreachable}{_RESET}")
                elif choice == "escalate":
                    _pkg("_doctor_maybe_escalate")(agent, {"tc3": tc3})
            if not tc4["passed"]:
                choice = _pkg("_doctor_fix_menu")(agent, "tc4", tc4)
                if choice == "1":
                    _pkg("cmd_configure_agent")(
                        agent,
                        flags={verb.lstrip("-"): None for verb in tc4.get("failed_verbs", [])},
                        envs={},
                        network_deps=[],
                    )
                elif choice == "escalate":
                    _pkg("_doctor_maybe_escalate")(agent, {"tc4": tc4})
            if tc5["missing"].get(agent):
                choice = _pkg("_doctor_fix_menu")(agent, "tc5", tc5)
                if choice == "1":
                    try:
                        _pkg("_repair_sops_only")(harness_name=agent)
                    except TypeError:
                        _pkg("_repair_sops_only")(agent_name=agent)
                elif choice == "escalate":
                    _pkg("_doctor_maybe_escalate")(agent, {"tc5": tc5})

        _DIRECTIVE_MAP = {
            "claude": "CLAUDE.md",
            "agy": "GEMINI.md",
            "grok": "GROK.md",
            "codex": "AGENTS.md",
        }
        cfg_roles = _pkg("load_config")().get("roles", {})
        roles_issues = []
        for harness_name in cfg_roles:
            fname = _DIRECTIVE_MAP.get(harness_name, f"{harness_name}.md")
            if os.path.exists(fname) and not _pkg("_fence_exists")(fname):
                roles_issues.append(fname)
        if roles_issues:
            for fname in roles_issues:
                print(f"  {_YELLOW}⚠{_RESET}  roles: {fname} is missing role fence "
                      f"{_DIM}— run `synlynk roles --fix` to regenerate{_RESET}")
    finally:
        db_conn.close()
    return 1 if any_failed else 0


_DOCTOR_FIX_MENUS = {
    "tc1": lambda agent, tc: [
        f"Show PTY workaround for {agent} (requires_pty={tc.get('requires_pty')})",
    ],
    "tc2": lambda agent, tc: [
        f"Apply recommended flags to .agents/{agent}.json (fixes: {tc.get('failed_flags', [])})",
    ],
    "tc3": lambda agent, tc: [
        f"Show unreachable endpoints and configure proxy for {agent}",
        f"Skip {agent} in this session",
    ],
    "tc4": lambda agent, tc: [
        f"Run: synlynk configure agent {agent} (adds missing verbs: {tc.get('failed_verbs', [])})",
    ],
    "tc5": lambda agent, tc: [
        f"Run: synlynk sync --repair-sops (re-inject {len(tc.get('missing', {}).get(agent, []))} missing sections)",
    ],
}


def _doctor_fix_menu(agent: str, tc_name: str, tc_result: dict) -> str:
    """Render a numbered fix menu for a TC failure."""
    if not sys.stdin.isatty():
        return "skip"
    menu_fn = _DOCTOR_FIX_MENUS.get(tc_name)
    options = menu_fn(agent, tc_result) if menu_fn else []
    print(f"\n    {_YELLOW}Fix options for {tc_name.upper()} [{agent}]:{_RESET}")
    print("      0) I'm stuck — escalate to Claude")
    for i, opt in enumerate(options, 1):
        print(f"      {i}) {opt}")
    print("      s) Skip")
    try:
        choice = input("    Choose [0/1.../s]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "skip"
    if choice == "0":
        return "escalate"
    if choice == "s" or not choice:
        return "skip"
    return choice


def _doctor_maybe_escalate(agent: str, failures: dict) -> None:
    """Assemble failure context and dispatch to Claude for diagnosis."""
    lines = [f"# synlynk doctor failure — {agent}\n"]
    for tc_name, result in failures.items():
        lines.append(f"## {tc_name.upper()}\n```json\n{json.dumps(result, indent=2)}\n```\n")

    tel_path = os.path.join(".synlynk", "telemetry.json")
    if os.path.exists(tel_path):
        try:
            with open(tel_path) as f:
                events = json.load(f)[-5:]
            lines.append(f"## Last 5 telemetry events\n```json\n{json.dumps(events, indent=2)}\n```\n")
        except Exception:
            pass

    cfg_path = os.path.join(".agents", f"{agent}.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as f:
                lines.append(f"## Agent Config\n```json\n{json.dumps(json.load(f), indent=2)}\n```\n")
        except Exception:
            pass

    context = "\n".join(lines)
    task = (
        f"synlynk doctor found failures for agent '{agent}'. "
        "Please diagnose and suggest fixes.\n\n"
        f"{context}"
    )
    from synlynk.dispatch import dispatch_agent as _dispatch_agent
    print("\n    Escalating to Claude for diagnosis...\n")
    result = _dispatch_agent("claude", task=task)
    print(f"    Dispatched: {result.get('id', '?')} — check synlynk jobs for output")
