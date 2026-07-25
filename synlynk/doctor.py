"""synlynk doctor: installation health checks and TC-1..TC-5 compliance suite."""

import json
import os
import sqlite3 as _sqlite3
import sys
import time
import urllib.error
import urllib.request

from dataclasses import dataclass as _dataclass
from typing import List as _List

from synlynk._constants import AGENT_CAPABILITY_BASELINES, VERSION
from synlynk.dispatch import dispatch_agent
from synlynk.probe import (
    _compute_capability_hash,
    _run_tc1,
    _run_tc2,
    _run_tc3,
    _run_tc4,
    _run_tc5,
)


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


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


def _hc_project_init() -> HealthCheck:
    if os.path.exists(".synlynk/config.json"):
        return HealthCheck("project_init", "ok", ".synlynk/config.json present")
    return HealthCheck(
        "project_init",
        "fail",
        "Project not initialized — .synlynk/config.json missing",
        fix="Run: synlynk init",
    )


def _hc_docs_dir() -> HealthCheck:
    try:
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

    roles = load_declared_roles()
    missing = []
    for role in roles:
        json_path = os.path.join(".synlynk", "github_apps", f"{role}.json")
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


HEALTH_CHECKS = [
    _hc_python_version,
    _hc_project_init,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_identity_roles,
    _hc_agent_profiles,
    _hc_instruction_files,
    _hc_model_rates,
    _hc_version_current,
]


def cmd_doctor(args=None, checks: _List = None) -> int:
    """Runs all registered health checks and prints a formatted report.

    Returns exit code: 0 if all checks ok/warn, 1 if any check fails.
    """
    if checks is not None:
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
        return 1 if failed else 0

    agent_filter = getattr(args, "agent", None) if args is not None else None
    db_conn = _pkg("_get_db")()
    baselines = AGENT_CAPABILITY_BASELINES
    agents = [agent_filter] if agent_filter else list(baselines.keys())
    any_failed = False
    try:
        for agent in agents:
            print(f"\n  doctor [{agent}]")
            baseline = baselines.get(agent, {})

            tc1 = _pkg("_run_tc1")(agent)
            tc2 = _pkg("_run_tc2")(agent, baseline.get("dispatch_flags", {}))
            endpoints = []
            for ep in baseline.get("network_deps", {}).get("required_endpoints", []):
                host, _, port_s = ep.rpartition(":")
                endpoints.append((host, int(port_s) if port_s.isdigit() else 443))
            tc3 = _pkg("_run_tc3")(endpoints)
            tc4 = _pkg("_run_tc4")(agent, db_conn)
            tc5_files = {
                "claude": "CLAUDE.md",
                "agy": "GEMINI.md",
                "codex": "AGENTS.md",
                "grok": "GROK.md",
            }
            tc5 = _pkg("_run_tc5")({a: tc5_files[a] for a in agents if a in tc5_files and os.path.exists(tc5_files[a])})

            all_passed = tc1["passed"] and tc2["passed"] and tc3["passed"] and tc4["passed"] and tc5["passed"]
            if not all_passed:
                any_failed = True
            status = "ok" if all_passed else "degraded"
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            capability_hash = _pkg("_compute_capability_hash")(
                baseline.get("headless_contract", {}),
                baseline.get("dispatch_flags", {}),
            )

            db_conn.execute(
                """
                INSERT INTO harness_records
                    (agent_name, harness_name, installed_version, compliance_status,
                     active_contract, active_flags, last_probe_at, capability_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
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
                    baseline.get("cli", agent),
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
                    INSERT INTO harness_version_history (agent_name, cli_version, event_type, recorded_at)
                    VALUES (?, ?, 'doctor_run', ?)
                    """,
                    (agent, "unknown", now),
                )
            except _sqlite3.IntegrityError:
                pass
            db_conn.commit()

            tc1_status = "✓" if tc1["passed"] else f"✗ requires_pty={tc1.get('requires_pty')}"
            tc2_status = "✓" if tc2["passed"] else f"✗ failed={tc2['failed_flags']}"
            tc3_status = "✓" if tc3["passed"] else f"✗ unreachable={tc3['unreachable']}"
            tc4_status = "✓" if tc4["passed"] else f"✗ failed={tc4['failed_verbs']}"
            print(f"    TC-1 stdout:  {tc1_status}")
            print(f"    TC-2 flags:   {tc2_status}")
            print(f"    TC-3 network: {tc3_status}")
            print(f"    TC-4 verbs:   {tc4_status}")
            if tc5["passed"]:
                print("    TC-5 sops:    ✓")
            else:
                for ag, missing in tc5["missing"].items():
                    print(f"    TC-5 sops:    ⚠ {ag}: missing {len(missing)} section(s): {', '.join(missing)}")

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
        for agent_name in cfg_roles:
            fname = _DIRECTIVE_MAP.get(agent_name, f"{agent_name}.md")
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
