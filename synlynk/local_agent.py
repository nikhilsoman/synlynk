"""synlynk local agent: config loading and oMLX reachability helpers for the
'local' dispatch agent. 'local' is dispatched as a real CLI subprocess (`aider`,
pointed at oMLX as an OpenAI-compatible backend) via the existing dispatch_agent()
machinery — this module owns only the config/flag-building helpers that invocation
needs, and the `synlynk local doctor` health-check command. It does not talk to
Aider or oMLX's chat-completions endpoint directly; Aider does that."""

import json
import hashlib
import importlib.util
import os
import shutil
import subprocess as _subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Any, Callable, Iterable, Optional

from synlynk import _get_db
from synlynk.local_pilot import load_pilot_runtime


_RESUME_CONFIRMATION = "RESUME LOCAL PILOT"
_RESUME_SHARE = 0.20
_RESUME_CONCURRENCY = 1

_DEFAULT_CONFIG_PATH = os.path.join(".agents", "local.json")
_DEFAULT_LOCAL_CONFIG = {
    "name": "local",
    "endpoint": "http://127.0.0.1:8000",
    "models": [
        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
        {
            "id": "qwen-coder",
            "pinned": False,
            "edit_format": "whole",
            "dispatch_eligible": False,
            "qualification": "benchmark-only",
        },
    ],
    "hardware_tier": "16gb-default",
}


def _check_prism_ml_available() -> bool:
    """Returns True if the prism-ml package is importable (needed for Ternary-Bonsai)."""
    return importlib.util.find_spec("prism_ml") is not None


_TIER_THRESHOLDS = [
    (12 * 1024**3, "8gb-light"),
    (20 * 1024**3, "16gb-default"),
    (48 * 1024**3, "32gb-pro"),
    (float("inf"), "64gb-fleet"),
]


def _detect_hardware_tier() -> str:
    """Detect RAM and return the corresponding local hardware tier.

    Uses ``sysctl`` on macOS and ``/proc/meminfo`` on Linux. Detection
    failures conservatively fall back to the default tier.
    """
    try:
        if sys.platform == "darwin":
            raw = _subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], timeout=5
            )
            ram_bytes = int(raw.strip())
        else:
            with open("/proc/meminfo") as meminfo:
                for line in meminfo:
                    if line.startswith("MemTotal:"):
                        ram_bytes = int(line.split()[1]) * 1024
                        break
                else:
                    return "16gb-default"
    except Exception:
        return "16gb-default"

    for threshold, tier in _TIER_THRESHOLDS:
        if ram_bytes < threshold:
            return tier
    return "64gb-fleet"


def _is_dispatch_eligible(model: dict) -> bool:
    """Return whether a roster model may be selected by normal dispatch."""
    return model.get("dispatch_eligible", True)


def _select_model_for_tier(tier: str, config: dict) -> str:
    """Return the best available model id for a hardware tier."""
    candidates = [
        model
        for model in config["models"]
        if tier in model.get("tier", []) and _is_dispatch_eligible(model)
    ]
    eligible = [
        model for model in candidates
        if not (
            model.get("loader") == "prism-ml"
            and not _check_prism_ml_available()
        )
    ]
    if eligible:
        return eligible[0]["id"]

    fallback = next(
        (
            model
            for model in config["models"]
            if not model.get("loader") and _is_dispatch_eligible(model)
        ),
        None,
    )
    if fallback:
        return fallback["id"]
    raise ValueError("local roster has no dispatch-eligible models")


def _load_local_config(path: str = None) -> dict:
    """Reads and parses .agents/local.json. Raises FileNotFoundError if missing."""
    if path is None:
        path = _DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run `synlynk local doctor` for setup guidance."
        )
    with open(path) as f:
        return json.load(f)


def _pinned_model(config: dict) -> str:
    """Return the eligible pinned model, or the first eligible roster entry.

    Models marked ``dispatch_eligible: false`` stay visible for qualification
    but cannot become the normal local-dispatch default.
    """
    eligible = [model for model in config["models"] if _is_dispatch_eligible(model)]
    if not eligible:
        raise ValueError("local roster has no dispatch-eligible models")
    configured_id = config.get("pinned_model")
    if configured_id:
        configured = next((model for model in eligible if model["id"] == configured_id), None)
        if configured:
            return configured["id"]
    for model in eligible:
        if model.get("pinned"):
            return model["id"]
    return eligible[0]["id"]


def resolve_effective_local_model(
    config_path: Optional[str] = None,
    requested_model: Optional[str] = None,
    live_model_ids: Optional[Iterable[str]] = None,
    catalog: Optional[dict[str, Any]] = None,
    require_live_inventory: bool = False,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve one auditable local model without silently translating IDs.

    The executable model must be in the dispatch-approved local policy and,
    for production dispatch, in the live oMLX inventory. Global catalog data
    enriches receipts and drift diagnostics but cannot approve or substitute a
    model.
    A requested model is selectable only when the exact ID is approved by
    local policy and present in live inventory. This selects an already-served
    model; it never loads, substitutes, or mutates the pinned model.
    """
    try:
        config = _load_local_config(config_path)
    except FileNotFoundError:
        if config_path is not None:
            raise
        # Preserve the established no-config dispatch behavior while still
        # making the fallback policy explicit in the resolution record.
        config = _DEFAULT_LOCAL_CONFIG
    eligible_ids = {
        str(model["id"])
        for model in config["models"]
        if model.get("id") and _is_dispatch_eligible(model)
    }
    policy_ids = {str(model["id"]) for model in config["models"] if model.get("id")}
    if requested_model is not None:
        if requested_model not in eligible_ids:
            raise ValueError(
                f"local model {requested_model!r} is not dispatch-approved by local policy; "
                f"eligible IDs: {', '.join(sorted(eligible_ids)) or '(none)'}"
            )
        policy_model = requested_model
    else:
        policy_model = _pinned_model(config)
    model_entry = next(model for model in config["models"] if str(model.get("id")) == policy_model)
    if model_entry.get("loader") == "prism-ml" and not _check_prism_ml_available():
        raise ValueError(
            f"local model {policy_model!r} requires unavailable loader 'prism-ml'; "
            "refusing to substitute another model"
        )

    inventory_status = "unknown"
    if live_model_ids is None and require_live_inventory:
        endpoint = config.get("endpoint")
        if not endpoint:
            raise ValueError("local policy has no oMLX endpoint; cannot verify live model inventory")
        if api_key is None:
            try:
                from synlynk.local_credentials import LocalCredentialStore
                api_key = LocalCredentialStore().get()
            except Exception:
                api_key = None
        health_result = _health_check(endpoint, api_key=api_key)
        inventory_status = health_result.get("status", "unavailable")
        if not health_result.get("reachable"):
            detail = health_result.get("error", "inventory health check failed")
            if inventory_status == "unauthenticated":
                detail = "oMLX rejected authentication (HTTP 401); run `synlynk local credentials import`"
            elif inventory_status == "timeout":
                detail = "oMLX inventory request timed out"
            elif inventory_status == "malformed_inventory":
                detail = "oMLX returned malformed model inventory"
            raise ValueError(f"cannot resolve local model without healthy live oMLX inventory: {detail}")
        live_model_ids = health_result["available_models"]
    elif live_model_ids is not None:
        inventory_status = "healthy"

    live_ids = None if live_model_ids is None else {str(model_id) for model_id in live_model_ids}
    if live_ids is not None and policy_model not in live_ids:
        discovered = ", ".join(sorted(live_ids)) or "(none)"
        raise ValueError(
            f"local model {policy_model!r} is not currently served by oMLX; "
            f"discovered IDs: {discovered}. Start oMLX with the requested model; "
            "Synlynk will not load or substitute models."
        )
    if require_live_inventory and live_ids is None:
        raise ValueError("cannot resolve local model without live oMLX inventory")

    if catalog is None:
        from synlynk.models import load_model_catalog

        catalog = load_model_catalog()
    catalog_ids = {
        str(model.get("model_id"))
        for model in (catalog.get("models", []) if catalog else [])
        if isinstance(model, dict) and model.get("harness") == "local" and model.get("model_id")
    }
    health = "unknown" if live_ids is None else "available"
    catalog_model = next(
        (
            model
            for model in (catalog.get("models", []) if catalog else [])
            if isinstance(model, dict)
            and str(model.get("model_id", "")) == policy_model
            and model.get("harness") == "local"
        ),
        None,
    )

    return {
        "requested_model": requested_model or policy_model,
        "resolved_model": policy_model,
        "effective_model": policy_model,
        "edit_format": model_entry.get("edit_format", "whole"),
        "health": health,
        "inventory_status": inventory_status,
        "catalog_model": dict(catalog_model) if catalog_model else None,
        "sources": {
            "policy": policy_model,
            "catalog": policy_model if policy_model in catalog_ids else None,
            "live_inventory": policy_model if live_ids is not None and policy_model in live_ids else None,
        },
        "drift": {
            "live_but_unapproved": sorted((live_ids or set()) - eligible_ids),
            "policy_approved_but_not_live": (
                sorted(eligible_ids - live_ids) if live_ids is not None else []
            ),
            "catalog_only": sorted(catalog_ids - policy_ids),
            "policy_not_in_catalog": sorted(eligible_ids - catalog_ids),
        },
    }


def _health_check(endpoint: str, timeout: int = 5, api_key: str = None) -> dict:
    """GETs the authenticated OpenAI-compatible inventory without exposing credentials."""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{endpoint}/v1/models", method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = "unauthenticated" if exc.code == 401 else "endpoint_unavailable"
        return {"reachable": False, "status": status, "error": f"HTTP {exc.code} {exc.reason}"}
    except TimeoutError:
        return {"reachable": False, "status": "timeout", "error": "request timed out"}
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        timed_out = isinstance(reason, TimeoutError) or "timed out" in str(reason).lower()
        return {
            "reachable": False,
            "status": "timeout" if timed_out else "endpoint_unavailable",
            "error": "request timed out" if timed_out else str(reason),
        }
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        return {"reachable": False, "status": "malformed_inventory", "error": str(exc)}
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return {
            "reachable": False,
            "status": "malformed_inventory",
            "error": "expected an object containing a data array",
        }
    available = []
    for model in payload["data"]:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"].strip():
            return {
                "reachable": False,
                "status": "malformed_inventory",
                "error": "each inventory entry must contain a non-empty string id",
            }
        available.append(model["id"])
    return {"reachable": True, "status": "healthy", "available_models": available}


def _orbstack_health_check(timeout: int = 3) -> dict:
    """Return whether OrbStack is installed and running.

    This is intentionally separate from ``_health_check``: a reachable oMLX
    endpoint does not prove that the container runtime needed by a
    containerized local setup is available.
    """
    orbctl = shutil.which("orbctl")
    if orbctl is None:
        return {"reachable": False, "error": "orbctl is not installed or not on PATH"}
    try:
        result = _subprocess.run(
            [orbctl, "status"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, _subprocess.TimeoutExpired) as exc:
        return {"reachable": False, "error": str(exc)}
    status = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0 or "running" not in status.lower():
        detail = status or "status check failed"
        return {"reachable": False, "error": detail}
    return {"reachable": True}


_STARTER_TIER_GUARDRAIL_FLAGS = [
    "--no-auto-lint",
    "--no-auto-test",
    "--map-tokens", "0",
]


def _local_dispatch_model_flags(
    config_path: str = None, resolved_model: Optional[str] = None
) -> list:
    """Builds aider model flags from .agents/local.json.

    Always appends Starter-tier safety guardrails (no autonomous lint/test
    execution, no repo-map context) - see
    docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md.
    Full-tier flags (--architect, auto-lint/auto-test: true) are a future,
    separately-gated change and must not be added here.
    """
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError:
        return []
    resolution = resolve_effective_local_model(
        config_path=config_path, requested_model=resolved_model
    )
    endpoint = config["endpoint"]
    return [
        "--openai-api-base", f"{endpoint}/v1",
        "--model", f"openai/{resolution['effective_model']}",
        "--edit-format", resolution["edit_format"],
    ] + _STARTER_TIER_GUARDRAIL_FLAGS


def local_pilot_status() -> dict:
    """Return read-only operator state for the disabled-by-default pilot."""
    from synlynk.dispatch import _local_max_concurrent
    from synlynk.local_pilot import REBASELINE_SHARE, evaluate_rebaseline, load_pilot_runtime
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger, load_pilot_status

    conn = _get_db()
    try:
        ensure_local_pilot_ledger(conn)
        reconciled = _reconcile_activating_authorizations(conn)
        if reconciled:
            _write_disabled_local_pilot_config(
                os.getcwd(), "activation interrupted; fresh confirmation required"
            )
        cohorts = load_pilot_status(conn)
        max_concurrent = _local_max_concurrent()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM daemon_jobs WHERE status = 'running' AND agent = 'local'"
            ).fetchone()
            running = int(row[0]) if row else 0
        except Exception:
            running = None
    finally:
        conn.close()
    runtime = load_pilot_runtime(os.getcwd())
    decision = evaluate_rebaseline(cohorts)
    pause_reason = _local_pilot_pause_reason(os.getcwd())
    endpoint = _local_pilot_endpoint_status()
    reservation_state = (
        "unknown" if running is None else "at_capacity" if running >= max_concurrent else "available"
    )
    operational = {
        "endpoint": endpoint,
        "credentials": "configured" if os.environ.get("OPENAI_API_KEY") else "missing",
        "model_qualification": "qualified" if runtime["qualified"] else "unqualified",
        "runner": "available" if runtime["isolated"] else "unavailable",
        "reservation": {
            "state": reservation_state,
            "running": running,
            "max_concurrent": max_concurrent,
        },
    }
    return {
        "cohorts": cohorts,
        "progress": {
            "validation": {"accepted": cohorts["validation"]["accepted"], "required": 5},
            "expansion": {
                "consecutive_accepted": cohorts["expansion"]["consecutive_accepted"],
                "required": 10,
            },
        },
        "boundaries": {"share": REBASELINE_SHARE, "max_concurrent": max_concurrent},
        "state": {
            "enabled": runtime["enabled"],
            "paused": not runtime["enabled"],
            "reason": pause_reason,
        },
        "model": {
            "selected": runtime["qualified_models"][0] if runtime["qualified_models"] else None,
            "qualified": runtime["qualified"],
        },
        "operational": operational,
        "reconciled_authorizations": reconciled,
        "proposal_35_eligible": decision.proposal_35_eligible,
    }


def _local_pilot_pause_reason(repo_root: str) -> str:
    """Return the configured pause reason without falling back to generated state."""
    workspace_path = os.path.join(repo_root, ".synlynk", "workspace.json")
    try:
        with open(workspace_path, encoding="utf-8") as handle:
            settings = (json.load(handle).get("local_pilot") or {})
    except (OSError, json.JSONDecodeError, AttributeError):
        settings = {}
    if settings.get("enabled") is True:
        return "enabled"
    return str(settings.get("pause_reason") or "disabled by configuration")


def _local_pilot_endpoint_status() -> str:
    """Check the configured endpoint by status only; never return a credential or error body."""
    try:
        config = _load_local_config()
        endpoint = config.get("endpoint")
    except (FileNotFoundError, AttributeError):
        endpoint = None
    if not endpoint:
        return "missing"
    return str(
        _health_check(endpoint, timeout=3, api_key=os.environ.get("OPENAI_API_KEY")).get(
            "status", "endpoint_unavailable"
        )
    )


def _usable_compose_runner() -> bool:
    """Require a runnable Docker Compose implementation, not merely a compose file."""
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        result = _subprocess.run(
            [docker, "compose", "version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, _subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _load_workspace_local_pilot(repo_root: str) -> tuple[dict, dict]:
    path = os.path.join(repo_root, ".synlynk", "workspace.json")
    try:
        with open(path, encoding="utf-8") as handle:
            workspace = json.load(handle)
    except (OSError, json.JSONDecodeError):
        workspace = {}
    workspace = workspace if isinstance(workspace, dict) else {}
    settings = workspace.get("local_pilot")
    return workspace, dict(settings) if isinstance(settings, dict) else {}


def _resume_config_fingerprint(settings: dict) -> str:
    canonical = json.dumps(settings, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reconcile_activating_authorizations(conn) -> list[str]:
    """Fail staged records; a config file can never complete an approval ceremony."""
    from synlynk.local_pilot_ledger import fail_resume_authorization

    stranded = conn.execute(
        "SELECT authorization_id FROM local_pilot_resume_authorizations WHERE state = 'activating'"
    ).fetchall()
    reconciled = []
    for (authorization_id,) in stranded:
        fail_resume_authorization(conn, authorization_id, "activation interrupted; fresh confirmation required")
        reconciled.append(authorization_id)
    return reconciled


def preflight_local_pilot_resume(repo_root: str, conn) -> dict:
    """Return a durable, fail-closed receipt for a possible Local pilot resume."""
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger

    failures = []
    try:
        ensure_local_pilot_ledger(conn)
        reconciled = _reconcile_activating_authorizations(conn)
    except Exception:
        return {"result": "failed", "failures": ["ledger_unreadable"], "reconciled": []}
    workspace, settings = _load_workspace_local_pilot(repo_root)
    del workspace
    if settings.get("enabled") is not False:
        failures.append("config_not_disabled")
    if settings.get("share") != _RESUME_SHARE:
        failures.append("config_share")
    if settings.get("max_concurrent") != _RESUME_CONCURRENCY:
        failures.append("config_concurrency")
    try:
        local_config = _load_local_config(os.path.join(repo_root, ".agents", "local.json"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        local_config = {}
    if local_config.get("max_concurrent") != _RESUME_CONCURRENCY:
        failures.append("local_config_concurrency")
    runtime = load_pilot_runtime(repo_root)
    if not runtime.get("qualified"):
        failures.append("qualified_model")
    if not runtime.get("isolated") or not _usable_compose_runner():
        failures.append("isolated_runner")
    try:
        resolution = resolve_effective_local_model(
            config_path=os.path.join(repo_root, ".agents", "local.json"),
            require_live_inventory=True,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
    except Exception:
        resolution = None
        failures.append("endpoint_health")
    resolved_model = resolution.get("resolved_model") if resolution else None
    qualified_models = {str(model) for model in runtime.get("qualified_models", [])}
    if (
        not isinstance(resolved_model, str)
        or resolved_model not in qualified_models
        or not resolved_model.casefold().startswith("ornith")
    ):
        failures.append("resolved_model_unqualified")
    try:
        running = conn.execute(
            "SELECT COUNT(*) FROM daemon_jobs WHERE status = 'running' AND agent = 'local'"
        ).fetchone()[0]
    except Exception:
        running = None
        failures.append("reservation_unreadable")
    if running:
        failures.append("active_reservation")
    pending = conn.execute(
        "SELECT COUNT(*) FROM local_pilot_evidence "
        "WHERE safety_verdict = 'pending' OR quality_verdict = 'pending'"
    ).fetchone()[0]
    if pending:
        failures.append("reconciliation_debt")
    if conn.execute(
        "SELECT 1 FROM local_pilot_resume_authorizations WHERE state = 'active'"
    ).fetchone():
        failures.append("authorization_conflict")
    return {
        "result": "passed" if not failures else "failed",
        "failures": failures,
        "reconciled": reconciled,
        "runtime": runtime,
        "resolved_model": resolved_model,
        "config_fingerprint": _resume_config_fingerprint(settings),
        "requested_share": _RESUME_SHARE,
        "requested_max_concurrent": _RESUME_CONCURRENCY,
    }


def _identity_key_path() -> str:
    return os.path.expanduser("~/.synlynk/identity.key")


def _sign_resume_authorization(authorization: dict) -> str:
    key_path = _identity_key_path()
    if not os.path.isfile(key_path) or not os.path.isfile(key_path + ".pub"):
        raise ValueError("Local pilot resume requires an available host signing key")
    canonical = json.dumps(authorization, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as message:
        message.write(canonical)
        message_path = message.name
    signature_path = message_path + ".sig"
    try:
        result = _subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", key_path, "-n", "synlynk-local-pilot-resume", message_path],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0 or not os.path.isfile(signature_path):
            raise ValueError("Local pilot resume signing failed")
        with open(signature_path, encoding="utf-8") as signature_file:
            return signature_file.read()
    finally:
        for path in (message_path, signature_path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _write_resumed_local_pilot_config(repo_root: str) -> None:
    from synlynk import _write_json_atomic

    workspace, settings = _load_workspace_local_pilot(repo_root)
    settings.update({"enabled": True, "share": _RESUME_SHARE, "max_concurrent": _RESUME_CONCURRENCY})
    settings.pop("pause_reason", None)
    workspace["local_pilot"] = settings
    _write_json_atomic(os.path.join(repo_root, ".synlynk", "workspace.json"), workspace)


def resume_local_pilot(
    repo_root: str,
    conn,
    remediation_ref: str,
    verification_ref: str,
    confirm: Callable[[str], str],
    render: Callable[[dict], None] | None = None,
) -> dict:
    """Run the explicit human ceremony and activate only the fixed validation lane."""
    from synlynk.local_pilot_ledger import (
        activate_resume_authorization, create_resume_authorization, fail_resume_authorization,
        local_pilot_control_lock, resume_authorization_context,
    )

    remediation_ref = str(remediation_ref or "").strip()
    verification_ref = str(verification_ref or "").strip()
    if not remediation_ref or not verification_ref:
        raise ValueError("remediation and independent verification references are required")
    preflight = preflight_local_pilot_resume(repo_root, conn)
    if render is not None:
        render(preflight)
    if preflight["result"] != "passed":
        raise ValueError("Local pilot resume preflight failed: " + ", ".join(preflight["failures"]))
    if confirm("Type RESUME LOCAL PILOT to authorize the 20% / one-concurrent lane: ") != _RESUME_CONFIRMATION:
        raise ValueError("Local pilot resume confirmation was not accepted")
    context = resume_authorization_context(conn)
    receipt_json = json.dumps(preflight, sort_keys=True, separators=(",", ":"))
    authorization = {
        **context,
        "config_fingerprint": preflight["config_fingerprint"],
        "remediation_reference": remediation_ref,
        "verification_reference": verification_ref,
        "preflight_receipt": preflight,
        "preflight_receipt_digest": hashlib.sha256(receipt_json.encode("utf-8")).hexdigest(),
    }
    staged = create_resume_authorization(conn, {"signed_payload": {
        "authorization": authorization, "signature": _sign_resume_authorization(authorization),
    }})
    try:
        with local_pilot_control_lock(repo_root):
            _write_resumed_local_pilot_config(repo_root)
            # Recheck the state that can race the config write without treating enabled config as approval.
            try:
                running = conn.execute(
                    "SELECT COUNT(*) FROM daemon_jobs WHERE status = 'running' AND agent = 'local'"
                ).fetchone()[0]
            except Exception as error:
                raise ValueError("Local reservation state is unreadable during activation") from error
            pending = conn.execute(
                "SELECT COUNT(*) FROM local_pilot_evidence "
                "WHERE safety_verdict = 'pending' OR quality_verdict = 'pending'"
            ).fetchone()[0]
            post_watermark_failure = conn.execute(
                "SELECT COUNT(*) FROM local_pilot_evidence WHERE safety_verdict = 'failed' AND rowid > ?",
                (authorization["safety_watermark"],),
            ).fetchone()[0]
            if running or pending or post_watermark_failure:
                raise ValueError("Local pilot state changed during activation")
            active = activate_resume_authorization(conn, staged["authorization_id"])
        return {"preflight": preflight, "authorization": active, "enabled": True}
    except Exception as error:
        try:
            _write_disabled_local_pilot_config(repo_root, str(error))
        finally:
            fail_resume_authorization(conn, staged["authorization_id"], str(error))
        raise


def _write_disabled_local_pilot_config(repo_root: str, reason: str) -> None:
    from synlynk import _write_json_atomic

    workspace, settings = _load_workspace_local_pilot(repo_root)
    settings.update({"enabled": False, "pause_reason": reason})
    workspace["local_pilot"] = settings
    _write_json_atomic(os.path.join(repo_root, ".synlynk", "workspace.json"), workspace)


def render_local_pilot_resume_preflight(preflight: dict) -> str:
    """Render the operator-safe preflight receipt before an approval prompt."""
    return json.dumps(preflight, indent=2, sort_keys=True)


def render_local_pilot_status(status: dict) -> str:
    """Render the read-only pilot view without combining independent cohorts."""
    historical = status["cohorts"]["historical"]
    progress = status["progress"]
    boundaries = status["boundaries"]
    state = status["state"]
    model = status["model"]
    operational = status["operational"]
    mismatches = []
    for name in ("credentials", "endpoint", "model_qualification", "runner"):
        value = operational[name]
        if (name, value) not in {
            ("credentials", "configured"),
            ("endpoint", "healthy"),
            ("model_qualification", "qualified"),
            ("runner", "available"),
        }:
            mismatches.append(f"{name}={value}")
    reservation = operational["reservation"]
    if reservation["state"] != "available":
        mismatches.append(f"reservation={reservation['state']}")
    lines = [
        f"Pilot: {'enabled' if state['enabled'] else 'paused'} ({state['reason']})",
        f"Historical evidence: {historical['accepted']}/{historical['eligible']} (preserved separately)",
        f"Validation: {progress['validation']['accepted']}/{progress['validation']['required']} accepted",
        "Expansion: "
        f"{progress['expansion']['consecutive_accepted']}/{progress['expansion']['required']} consecutive accepted",
        f"Boundary: {boundaries['share']:.0%} cap; {boundaries['max_concurrent']} concurrent",
        f"Qualified Ornith model: {model['selected'] or 'none'}",
        f"35% proposal eligible: {'yes' if status['proposal_35_eligible'] else 'no'}",
        "Operational mismatches: " + ("; ".join(mismatches) if mismatches else "none"),
    ]
    return "\n".join(lines)


def start_local_pilot_review(job_id: str) -> dict:
    """Create one independently selected, factual-only Local pilot review brief."""
    from synlynk.local_pilot_ledger import start_local_pilot_review as _start

    conn = _get_db()
    try:
        return _start(conn, job_id)
    finally:
        conn.close()


def record_local_pilot_review(job_id: str, reviewer: str, verdict: str, rationale: str) -> dict:
    """Record one selected reviewer verdict without changing operational controls."""
    from synlynk.local_pilot_ledger import record_local_pilot_review as _record

    conn = _get_db()
    try:
        return _record(conn, job_id, reviewer, verdict, rationale)
    finally:
        conn.close()


def cmd_local_doctor(config_path: str = None, init: bool = False, api_key: str = None) -> int:
    """Print oMLX reachability, roster status, and hardware recommendation.

    With ``init=True``, write the detected ``hardware_tier`` and recommended
    ``pinned_model`` back to the local config.
    """
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError as exc:
        if config_path == _DEFAULT_CONFIG_PATH:
            config = _DEFAULT_LOCAL_CONFIG
        else:
            print(f"  ✗ {exc}")
            return 1
    endpoint = config["endpoint"]
    if api_key is None:
        try:
            from synlynk.local_credentials import LocalCredentialStore
            api_key = LocalCredentialStore().get()
        except Exception:
            api_key = None
    result = _health_check(endpoint, api_key=api_key)
    if not result["reachable"]:
        print(f"  ✗ oMLX unreachable at {endpoint}: {result['error']}")
        if "401" in result["error"]:
            print("    oMLX rejected the request (401 Unauthorized) — run `synlynk local credentials import`")
        else:
            print("    Start it with: omlx serve")
        return 1
    print(f"  ✓ oMLX reachable at {endpoint}")
    tier = _detect_hardware_tier()
    best_model = _select_model_for_tier(tier, config)
    print(f"  ✓ hardware tier: {tier}")
    print(f"  ✓ recommended model: {best_model}")
    if init:
        config["hardware_tier"] = tier
        config["pinned_model"] = best_model
        write_path = config_path or _DEFAULT_CONFIG_PATH
        with open(write_path, "w") as f:
            json.dump(config, f, indent=2)
        print(
            f"  ✓ wrote hardware_tier={tier!r} and "
            f"pinned_model={best_model!r} to {write_path}"
        )
    from synlynk.local_agent_seed import seed_local_capability_envelope
    seed_local_capability_envelope(_get_db())
    print("  ✓ starter capability envelope seeded (docs/testing, execute stage)")
    available = set(result["available_models"])
    resolution = resolve_effective_local_model(
        config_path=config_path if os.path.exists(config_path) else None,
        live_model_ids=available,
    )
    print(
        "  ✓ effective model: "
        f"{resolution['effective_model']} ({resolution['edit_format']}, {resolution['health']})"
    )
    for drift_kind, model_ids in resolution["drift"].items():
        if model_ids:
            print(f"  ⚠ model drift [{drift_kind}]: {', '.join(model_ids)}")
    missing = [model["id"] for model in config["models"] if model["id"] not in available]
    for model in config["models"]:
        model_id = model["id"]
        in_roster = model_id not in missing
        loader = model.get("loader")
        loader_ok = True
        loader_note = ""
        if loader == "prism-ml":
            loader_ok = _check_prism_ml_available()
            loader_note = " [prism-ml: ✓]" if loader_ok else " [prism-ml: ✗ — pip install prism-ml]"
        mark = "✓" if (in_roster and loader_ok) else ("⚠" if in_roster else "✗")
        print(f"  {mark} {model_id}{loader_note}")
    if missing:
        print(f"    Missing from oMLX roster: {', '.join(missing)}")
    aider_missing = shutil.which("aider") is None
    if aider_missing:
        print("  ✗ aider not found on PATH")
        print("    Install it with: pipx install aider-chat")
    else:
        print("  ✓ aider installed")
    if missing or aider_missing:
        return 1
    return 0


def cmd_local_credentials(action: str, *, replace: bool = False, environ=None,
                          interactive: bool = None, store=None) -> int:
    """Manage the host Keychain credential without displaying its value."""
    import sys
    from synlynk.local_credentials import LocalCredentialStore

    store = store or LocalCredentialStore()
    environ = os.environ if environ is None else environ
    interactive = (sys.stdin.isatty() and sys.stdout.isatty()) if interactive is None else interactive
    try:
        if action == "import":
            if not interactive:
                print("  ✗ credential import requires an interactive terminal")
                return 1
            store.import_from_environment(environ, replace=replace)
            print("  ✓ oMLX credential stored in macOS Keychain")
        elif action == "status":
            print("  ✓ oMLX credential configured" if store.is_configured()
                  else "  ✗ oMLX credential not configured")
        elif action == "delete":
            store.delete()
            print("  ✓ oMLX credential deleted from macOS Keychain")
        else:
            raise ValueError("unknown local credentials action")
        return 0
    except Exception as exc:
        message = str(exc)
        if "OPENAI_API_KEY" in message:
            print("  ✗ OPENAI_API_KEY is missing")
        else:
            print(f"  ✗ {message}")
        return 1
