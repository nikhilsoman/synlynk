"""synlynk probe: harness capability probing, fence management, TC compliance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.sentinel import _clear_sentinel_alerts, _write_sentinel_alert

SOP_SECTION_HEADERS = [
    "## PR Review Discipline",
    "## Brainstorm-First Policy",
    "## Design → Plan → Build Sequence",
    "## Capability-Based Task Allocation",
    "## Cost Visibility",
    "## Repo Hygiene",
    "## Herdr Workspace Protocol",
]

_PR_REVIEW_SOP = """\
## PR Review Discipline
1. Assign a non-authoring agent to review the PR.
2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.
3. The reviewer alone must merge the PR.
4. If the reviewer is unavailable, escalate to Claude.

**GitHub identity note (#423):** If a role has a registered workspace agent (`synlynk agent init <role>`, e.g. `qa` or `architect`), dispatch its review via `synlynk dispatch claude --as-agent <role-agent-id>` — this posts a genuine approving review under that role's own distinct GitHub App identity, satisfying GitHub's non-author review requirement for real approvals. Route day-to-day reviews through `qa` and any feature/architecture-impacting review through `architect`. **Fallback (no registered agent for the role):** post a formal COMMENT review with an explicit approve checklist (as on PR #417) instead of an approving review, since dispatches without `--as-agent` share the single repo-owner GitHub identity and an approving review will fail with the self-approval error.
"""

_BRAINSTORM_SOP = """\
## Brainstorm-First Policy
1. Do not write code before an approved spec exists in `docs/superpowers/specs/`.
2. Run the brainstorm using Claude via `synlynk dispatch`.
3. Spec is approved only when committed to the branch and Nikhil signs off.
"""

_DESIGN_SEQUENCE_SOP = """\
## Design → Plan → Build Sequence
1. Design: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
2. Plan: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
3. Build: Code implementation
- Spec not committed = do not write plan.
- Plan not committed = do not dispatch tasks.
"""

_CAPABILITY_ALLOCATION_SOP = """\
## Capability-Based Task Allocation

**Note:** "Harness" below means the execution backend (Claude/Agy/Grok/Codex) that runs a task, not the Agent (role) doing the work
- See `docs/glossary-agent-vs-harness.md`

| Role | Harness | Tasks |
| :--- | :--- | :--- |
| Python/CLI/tests | Codex | Python, CLI, tests |
| HTML/CSS/content/docs | Agy | HTML, CSS, content, docs |
| canvas/JS/infra | Grok | canvas, JS, infra |
| PM/review/deploy/brainstorm | Claude | PM, deploy, brainstorm |
| PR review / GitHub write | Codex | PR review, issue/PR operations |
| GitHub write actions | **codex, Claude/Agy fallback** | `gh pr review`, `gh pr merge`, `gh pr create`, `gh issue comment` — Codex by default (PR #1271, verified live in job `job-836e13a4`); Claude and Agy remain fallbacks; the Grok harness's dispatch sandbox denies shell execution entirely in this environment, do not route here |
Do not start a task outside your role column without explicit Claude approval.

**GitHub write routing (#1271):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (verified live in job `job-836e13a4`)
- Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts)
- Codex receives `sandbox_workspace_write.network_access=true` only for explicit `--requires-gh-write` dispatches
- Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569)
"""

_COST_VISIBILITY_SOP = """\
## Cost Visibility
1. Log estimated_cost in the job context header before dispatch.
2. Check `synlynk status` for current burn rate.
3. Confirm all work is captured via telemetry and manual/PM work is logged via `synlynk cost log`.
4. Append actual cost to `project-docs/costs.md`.
"""

_REPO_HYGIENE_SOP = """\
## Repo Hygiene
1. Do not commit directly to main or master.
2. Use task-scoped branch naming: `feat/<description>`, `fix/<description>`, `chore/<description>`.
3. Co-Authored-By trailer is required: Claude (`Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`), Agy (`Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`), Codex (`Co-Authored-By: Codex <noreply@openai.com>`), Grok (`Co-Authored-By: Grok <noreply@x.ai>`).
4. Use worktree per feature with `git worktree add`.
5. Run `git branch --show-current` before committing to verify branch.
"""

_HERDR_WORKSPACE_SOP = """\
## Herdr Workspace Protocol
1. At a task/session boundary, finish housekeeping (project docs, memory, cost log) before running `/clear`.
2. File a ticket — with an appropriate label (e.g. `tech-debt` for a gap surfaced mid-task, out of current scope) — for anything left open beyond the current story/goal/session, rather than letting it go untracked.
3. Launch each new session in a new Herdr tab + new pane, within the same workspace (Herdr workspace = synlynk workspace).
- Never reuse another session's pane.
4. Name each pane and tab with the synlynk session_id / job-ID / agent name so panes are identifiable at a glance.
5. When working in person via Herdr, run interactive-shell sessions for each of the 4 core harnesses (Claude, Codex, Agy, Grok) as needed — synlynk aims to be harness-agnostic, giving each harness equal "home" (interactive) and "away" (headless dispatch) airtime while cycling through implementation work across target workspaces.
- (Local harness — Ornith+Aider+oMLX — is a future extension, not yet wired up.)
6. Any new harness interactive session also gets its own new tab within the same workspace.
7. Begin every Claude session with `/rc`.
- **Precondition for all Herdr commands:** check `test "${HERDR_ENV:-}" = 1` before issuing any `herdr` command; if unset, this agent is not running inside Herdr and must not attempt to control a Herdr session from outside it.
- Herdr is Apache-2.0 licensed (no NOTICE file) — free to reference/use without royalty or attribution beyond standard license retention.
- Full CLI reference: https://github.com/herdrdev/herdr/blob/v0.8.2/skills/herdr/SKILL.md
"""

SOP_BLOCKS = [
    _PR_REVIEW_SOP,
    _BRAINSTORM_SOP,
    _DESIGN_SEQUENCE_SOP,
    _CAPABILITY_ALLOCATION_SOP,
    _COST_VISIBILITY_SOP,
    _REPO_HYGIENE_SOP,
    _HERDR_WORKSPACE_SOP,
]

_VERSION_TOKEN_PATTERN = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b")


def _compute_capability_hash(headless_contract: dict, dispatch_flags) -> str:
    import hashlib as _hashlib
    import json as _json

    payload = _json.dumps({"contract": headless_contract, "flags": dispatch_flags}, sort_keys=True)
    return _hashlib.sha256(payload.encode()).hexdigest()[:16]


def _baseline_schema_issues(harness_name: str, baseline: dict) -> list:
    """Return human-readable schema issues for a baseline."""
    issues = []
    if not isinstance(baseline, dict):
        return [f"{harness_name}: baseline missing or not a dict"]

    required_sections = {
        "dispatch_flags": {
            "type": dict,
            "keys": {
                "valid_flags": list,
                "invalid_flags": list,
                "required_flags": list,
            },
        },
        "headless_contract": {
            "type": dict,
            "keys": {
                "requires_pty": bool,
                "stdout_flush_method": str,
                "env_vars_required": list,
                "non_interactive_flag": str,
            },
        },
        "network_deps": {
            "type": dict,
            "keys": {
                "required_endpoints": list,
                "optional_endpoints": list,
            },
        },
    }

    for section_name, spec in required_sections.items():
        section = baseline.get(section_name)
        if not isinstance(section, spec["type"]):
            issues.append(f"{harness_name}: {section_name} must be a dict")
            continue

        missing = [key for key in spec["keys"] if key not in section]
        if missing:
            issues.append(f"{harness_name}: {section_name} missing keys: {', '.join(missing)}")
            continue

        for key, expected_type in spec["keys"].items():
            value = section.get(key)
            if expected_type is bool:
                if not isinstance(value, bool):
                    issues.append(f"{harness_name}: {section_name}.{key} must be a bool")
            elif expected_type is str:
                if not isinstance(value, str) or not value.strip():
                    issues.append(f"{harness_name}: {section_name}.{key} must be a non-empty string")
            elif expected_type is list:
                if not isinstance(value, list):
                    issues.append(f"{harness_name}: {section_name}.{key} must be a list")
    return issues


def _run_tc0(harness_name: str, baseline: dict = None) -> dict:
    """TC-0: baseline schema completeness."""
    baseline = baseline if baseline is not None else HARNESS_CAPABILITY_BASELINES.get(harness_name, {})
    issues = _baseline_schema_issues(harness_name, baseline)
    return {"passed": not issues, "schema_issues": issues}


_re = re


def _scan_command_palette(harness_cli: str, harness_name: str, cli_version: str, db_conn) -> list:
    """Parse --help output and populate harness_command_palette."""
    try:
        result = subprocess.run([harness_cli, "--help"], capture_output=True, text=True, timeout=5)
        help_text = (result.stdout or "") + (result.stderr or "")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    found_commands = {}
    for line in help_text.splitlines():
        line = line.strip()
        if not line:
            continue

        flag_match = _re.match(r"^(--[\w-]+(?:=\S+)?)(?:\s+\S+)?\s{2,}(.*)", line)
        if flag_match:
            cmd = flag_match.group(1).split("=")[0]
            desc = flag_match.group(2).strip()
            found_commands[cmd] = {"type": "flag", "help": desc}
            continue

        sub_match = _re.match(r"^([\w][\w\s-]{1,30}?)\s{2,}(.*)", line)
        if sub_match:
            cmd = sub_match.group(1).strip()
            desc = sub_match.group(2).strip()
            if cmd and len(cmd.split()) <= 3 and not cmd.startswith("-"):
                found_commands[cmd] = {"type": "subcommand", "help": desc}

    prev_rows = db_conn.execute(
        "SELECT command, cli_version FROM harness_command_palette WHERE harness_name=? AND last_seen_version IS NULL",
        (harness_name,),
    ).fetchall()
    prev_commands = {row[0] for row in prev_rows}
    prev_versions = {row[0]: row[1] for row in prev_rows}
    removed = prev_commands - set(found_commands.keys())
    for cmd in removed:
        db_conn.execute(
            """
            UPDATE harness_command_palette
            SET last_seen_version=?
            WHERE harness_name=? AND command=? AND last_seen_version IS NULL
            """,
            (prev_versions.get(cmd, cli_version), harness_name, cmd),
        )

    for cmd, meta in found_commands.items():
        db_conn.execute(
            """
            INSERT OR IGNORE INTO harness_command_palette
                (harness_name, cli_version, command, command_type, help_text, first_seen_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (harness_name, cli_version, cmd, meta["type"], meta["help"], cli_version),
        )

    db_conn.commit()
    return list(found_commands.keys())


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _diff_and_queue_new_models(harness_name: str, discovered_model_ids: list, conn) -> None:
    """Diff a harness's discovered models against harness_models; queue a
    calibration sweep for any model_id not yet recorded (#786 Plan B)."""
    known = {
        row[0]
        for row in conn.execute(
            "SELECT model_id FROM harness_models WHERE harness_name=?", (harness_name,)
        ).fetchall()
    }
    now = _now_iso()
    for model_id in discovered_model_ids:
        if model_id in known:
            conn.execute(
                "UPDATE harness_models SET last_seen_at=? WHERE harness_name=? AND model_id=?",
                (now, harness_name, model_id),
            )
            continue
        conn.execute(
            "INSERT INTO harness_models "
            "(harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source) "
            "VALUES (?, ?, ?, ?, 'active', 'self_report')",
            (harness_name, model_id, now, now),
        )
        _queue_calibration_sweep(harness_name, model_id, conn)
    conn.commit()


def _queue_calibration_sweep(harness_name: str, model_id: str, conn) -> None:
    """Auto-trigger a cost-capped, verified calibration sweep for one newly
    discovered (harness, model) pair, reusing capability_sweep.py's machinery."""
    from synlynk.capability_sweep import cmd_capability_sweep_for_harness_model
    try:
        cmd_capability_sweep_for_harness_model(harness_name, model_id)
    except SystemExit:
        pass  # cost cap exceeded — model stays 'active' with zero calibration data,
              # picked up by the routing explore-bonus in Task 4 instead


def _scan_repo_requirements(repo_path: str) -> set[str]:
    """Return repo artifact requirements detected by presence only.

    This is a discovery primitive, not a policy decision. The caller decides
    whether a detected requirement should block, degrade, or be ignored.
    """
    requirements = set()
    root = os.fspath(repo_path)

    if not root:
        return requirements

    try:
        if any(
            os.path.exists(os.path.join(root, name))
            for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")
        ):
            requirements.add("docker")

        if any(
            os.path.exists(os.path.join(root, name))
            for name in (".mcp.json", "mcp.json")
        ):
            requirements.add("mcp")

        workflows_dir = os.path.join(root, ".github", "workflows")
        if os.path.isdir(workflows_dir):
            with os.scandir(workflows_dir) as entries:
                if any(True for _ in entries):
                    requirements.add("gh-actions")
    except OSError:
        pass

    return requirements


_FENCE_OPEN_PATTERN = _re.compile(
    r"<!-- synlynk:harness v\S+ verified:\S+ -->.*?<!-- /synlynk:harness -->",
    _re.DOTALL,
)
_FENCE_VERSION_AND_BODY_PATTERN = _re.compile(
    r"<!-- synlynk:harness v(\S+) verified:\S+ -->\n"
    r"# Harness Instructions \(synlynk-managed — do not edit\)\n\n"
    r"(.*?)\n<!-- /synlynk:harness -->",
    _re.DOTALL,
)


def _build_fence_content(harness_version: str, body: str) -> str:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"<!-- synlynk:harness v{harness_version} verified:{ts} -->\n"
        f"# Harness Instructions (synlynk-managed — do not edit)\n\n"
        f"{body}\n"
        f"<!-- /synlynk:harness -->"
    )


def _upsert_harness_fence(file_path: str, harness_version: str, body: str) -> None:
    if not os.path.exists(file_path):
        print(f"  warning: {file_path} not found — fence skipped. Run synlynk init to create it.", file=sys.stderr)
        return

    with open(file_path, "r", encoding="utf-8") as f:
        current = f.read()

    existing_match = _FENCE_VERSION_AND_BODY_PATTERN.search(current)
    if existing_match and existing_match.group(1) == harness_version and existing_match.group(2) == body:
        return

    fence = _build_fence_content(harness_version, body)
    if _FENCE_OPEN_PATTERN.search(current):
        updated = _FENCE_OPEN_PATTERN.sub(fence, current, count=1)
    else:
        sep = "\n" if current.endswith("\n") else "\n\n"
        updated = current + sep + fence + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)


def _write_scan_fences(results: dict, root: str = ".") -> list:
    """Write Codebase Context fences into present directive files."""
    import datetime as _dt

    # CLAUDE.md is Claude Code's project instructions — probe must not write fences there.
    # Only write to agent directive files that read harness fences for headless dispatch.
    directive_files = ["GEMINI.md", "AGENTS.md", "GROK.md"]
    body_lines = []

    stack = results.get("stack") or {}
    source = results.get("source") or []
    complexity = results.get("complexity") or {}
    tests_data = results.get("tests") or {}
    git_data = results.get("git") or {}
    arch_data = results.get("arch") or {}

    lang = str(stack.get("language", "unknown")).capitalize()
    ver = str(stack.get("version", "")).strip()
    pattern = arch_data.get("pattern", "unknown")
    entry_points = arch_data.get("entry_points", []) or []
    total_files = len(source)
    total_fns = sum(int(f.get("functions", 0) or 0) for f in source)
    largest = source[0] if source else {}
    avg_typed = round(
        sum(float(f.get("typed_pct", 0) or 0) for f in source) / max(len(source), 1)
    ) if source else 0
    avg_doc = round(
        sum(float(f.get("docstring_pct", 0) or 0) for f in source) / max(len(source), 1)
    ) if source else 0

    body_lines.append("## Codebase Context")
    if stack:
        body_lines.append(
            f"- Architecture: {pattern} · {lang} {ver} · {len(entry_points)} entry point"
            f"{'s' if len(entry_points) != 1 else ''}"
        )
    if source:
        largest_note = ""
        if largest.get("lines", 0) > 1000:
            largest_note = f" · {largest['path']} {largest['lines']:,} lines"
        body_lines.append(
            f"- Source: {total_files} file{'s' if total_files != 1 else ''} · "
            f"{total_fns} functions{largest_note}"
        )
        body_lines.append(f"- Type coverage: {avg_typed}% · Docstring coverage: {avg_doc}%")

    hotspots = complexity.get("hotspots", []) or []
    if hotspots:
        body_lines.append("")
        body_lines.append("## Complexity Hotspots")
        for hotspot in hotspots[:3]:
            fn_label = f"{hotspot['fn']}()" if hotspot.get("fn") else os.path.basename(hotspot.get("path", "?"))
            body_lines.append(
                f"- {fn_label} — {int(hotspot.get('lines', 0) or 0)} lines "
                f"({hotspot.get('path', '?')}:{hotspot.get('lineno', '?')})"
            )

    gap_count = int(tests_data.get("gap_count", 0) or 0)
    if gap_count > 0:
        body_lines.append("")
        body_lines.append("## Test Gaps (structural, not runtime coverage)")
        gap_names = [gap.get("name", "?") for gap in (tests_data.get("gap_functions", []) or [])[:5]]
        suffix = f" [+{gap_count - 5} more]" if gap_count > 5 else ""
        body_lines.append(
            f"- {gap_count} untested public function{'s' if gap_count != 1 else ''}: "
            f"{', '.join(gap_names)}{suffix}"
        )

    churn = git_data.get("churn", []) or []
    has_git_error = "error" in git_data and not churn
    if churn and not has_git_error:
        body_lines.append("")
        body_lines.append("## Hot Files (last 30 commits)")
        for item in churn[:3]:
            icon = "🔥" if item.get("temp") == "hot" else ("⚡" if item.get("temp") == "warm" else "·")
            body_lines.append(f"- {icon} {item.get('path', '?')} — {int(item.get('commits', 0) or 0)} commits")

    todo_counts = complexity.get("todo_counts", {}) or {}
    total_markers = sum(int(v or 0) for v in todo_counts.values())
    if total_markers > 0:
        body_lines.append("")
        body_lines.append("## Tech Debt")
        parts = [f"{v} {k}" for k, v in todo_counts.items() if v]
        body_lines.append(f"- {' · '.join(parts)}")

    body = "\n".join(body_lines)
    scan_date = _dt.date.today().isoformat()

    updated = []
    for fname in directive_files:
        fpath = os.path.join(root, fname)
        if not os.path.exists(fpath):
            continue
        _upsert_harness_fence(fpath, f"scan-{scan_date}", body)
        updated.append(fpath)

    return updated


def _build_fence_body_from_record(harness_name: str, db_conn=None) -> str:
    import json as _j

    baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name, {})
    contract = baseline.get("headless_contract", {})
    flags_spec = baseline.get("dispatch_flags", {})
    net_deps = baseline.get("network_deps", {})

    if db_conn:
        row = db_conn.execute(
            "SELECT active_contract, active_flags FROM harness_records WHERE harness_name=?",
            (harness_name,)
        ).fetchone()
        if row:
            contract = _j.loads(row[0]) or contract
            flags_spec = _j.loads(row[1]) or flags_spec

    mode = "pty" if contract.get("requires_pty") else "pipe"
    flush = contract.get("stdout_flush_method", "native")
    ni_flag = contract.get("non_interactive_flag", "")
    env_vars = contract.get("env_vars_required", [])
    if isinstance(flags_spec, dict):
        valid = " ".join(flags_spec.get("valid_flags", []))
        invalid = " ".join(flags_spec.get("invalid_flags", []))
    else:
        valid = " ".join(flags_spec) if isinstance(flags_spec, list) else ""
        invalid = ""
    endpoints = "\n".join(f"- Required: {e}" for e in net_deps.get("required_endpoints", []))
    env_line = f"- Stdout flush: unbuffered (set {' '.join(env_vars)})" if env_vars else f"- Stdout flush: {flush}"

    return f"""## Headless Execution Contract
- Execution mode: {mode}
- Non-interactive flag: {ni_flag}
{env_line}

## Active Dispatch Flags
- Valid: {valid}
- Invalid (do not use): {invalid}

## Network Dependencies
{endpoints or '- None required'}"""


def _merge_fence_body(existing_body: str, capability_body: str) -> str:
    """Merge capability sections into an existing harness fence body.

    SOP sections and other managed content may share this fence. Replace only
    sections owned by the capability probe and preserve everything else.
    """
    existing_body = (existing_body or "").strip()
    capability_body = (capability_body or "").strip()
    if not existing_body:
        return capability_body
    if not any(header in existing_body for header in SOP_SECTION_HEADERS):
        return capability_body

    merged = existing_body
    sections = re.split(r"(?m)(?=^## )", capability_body)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        header = section.splitlines()[0]
        section_pattern = re.compile(rf"(?ms)^{re.escape(header)}\n.*?(?=^## |\Z)")
        if section_pattern.search(merged):
            merged = section_pattern.sub(section + "\n", merged, count=1)
        else:
            merged = _repair_sop_body_parts(merged, section)
    return merged


def _probe_agent(harness_name: str, db_conn, fast_path_ok: bool = True, write_fence: bool = True) -> dict:
    import json as _json
    import socket as _sock
    import time as _time

    def _extract_installed_version(text: str) -> str:
        text = text.strip()
        if not text:
            return "unknown"

        match = _VERSION_TOKEN_PATTERN.search(text)
        if match:
            return match.group(0)

        return text.split()[-1]

    harness_map = {"claude": "claude-cli", "agy": "agy", "grok": "grok", "codex": "codex"}
    baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name, {})
    record_harness_name = harness_map.get(harness_name, harness_name)
    schema_result = _run_tc0(harness_name, baseline)
    schema_issues = schema_result["schema_issues"]

    try:
        result = subprocess.run([harness_name, "--version"], capture_output=True, text=True, timeout=5)
        installed_version = _extract_installed_version(result.stdout or "")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        installed_version = "unavailable"
    version_detected = installed_version not in {"unknown", "unavailable"}

    contract = baseline.get("headless_contract", {})
    flags = baseline.get("dispatch_flags", {})
    new_hash = _compute_capability_hash(contract, flags)

    if fast_path_ok and not schema_issues:
        row = db_conn.execute(
            "SELECT installed_version, capability_hash FROM harness_records WHERE harness_name=?",
            (record_harness_name,),
        ).fetchone()
        if row and row[0] == installed_version and row[1] == new_hash:
            return {
                "skipped": True,
                "version": installed_version,
                "version_detected": version_detected,
                "status": "ok",
                "schema_issues": schema_issues,
            }

    network_ok = True
    for endpoint in baseline.get("network_deps", {}).get("required_endpoints", []):
        host, _, port_s = endpoint.rpartition(":")
        try:
            s = _sock.create_connection((host, int(port_s or 443)), timeout=2)
            s.close()
        except OSError:
            network_ok = False

    compliance = "ok" if network_ok and not schema_issues else "degraded"

    prev_row = db_conn.execute(
        "SELECT installed_version, capability_hash FROM harness_records WHERE harness_name=?",
        (record_harness_name,),
    ).fetchone()

    now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    event_type = None
    if prev_row:
        if prev_row[0] != installed_version:
            event_type = "version_change"
        elif prev_row[1] != new_hash:
            event_type = "drift_detected"

    db_conn.execute(
        """
        INSERT INTO harness_records
            (harness_name, installed_version, compliance_status, active_contract, active_flags, capability_hash, last_probe_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(harness_name) DO UPDATE SET
            installed_version=excluded.installed_version,
            compliance_status=excluded.compliance_status,
            active_contract=excluded.active_contract,
            active_flags=excluded.active_flags,
            capability_hash=excluded.capability_hash,
            last_probe_at=excluded.last_probe_at
        """,
        (
            record_harness_name,
            installed_version,
            compliance,
            _json.dumps(contract),
            _json.dumps(flags),
            new_hash,
            now,
        ),
    )

    if event_type:
        db_conn.execute(
            """
            INSERT INTO harness_version_history (harness_name, cli_version, event_type, prev_hash, new_hash, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record_harness_name,
                installed_version,
                event_type,
                prev_row[1] if prev_row else None,
                new_hash,
                now,
            ),
        )

    try:
        from synlynk.status import TIER1_CAPACITY, _compute_cycle_capability

        cap = TIER1_CAPACITY.get(harness_name, {})
        attach_point_in_time = 1 if compliance == "ok" else 0
        db_conn.execute(
            """
            INSERT INTO harness_status (
                harness_name, attach_point_in_time, installed_version,
                ctx_window_tokens, read_budget_tokens, write_budget_tokens,
                tool_budget_count, tc1_status, tc2_status, tc3_status, tc4_status,
                last_probe_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(harness_name) DO UPDATE SET
                attach_point_in_time=excluded.attach_point_in_time,
                installed_version=excluded.installed_version,
                ctx_window_tokens=excluded.ctx_window_tokens,
                read_budget_tokens=excluded.read_budget_tokens,
                write_budget_tokens=excluded.write_budget_tokens,
                tool_budget_count=excluded.tool_budget_count,
                tc1_status=excluded.tc1_status,
                tc2_status=excluded.tc2_status,
                tc3_status=excluded.tc3_status,
                tc4_status=excluded.tc4_status,
                last_probe_at=excluded.last_probe_at
            """,
            (
                harness_name,
                attach_point_in_time,
                installed_version,
                cap.get("ctx_window_tokens"),
                cap.get("read_budget_tokens"),
                cap.get("write_budget_tokens"),
                cap.get("tool_budget_count"),
                "unknown",
                "unknown",
                "unknown",
                "unknown",
                now,
            ),
        )
        _compute_cycle_capability(harness_name, db_conn)

        latest_version_cmds = {
            "claude": ["npm", "info", "@anthropic-ai/claude-code", "version"],
            "codex": ["npm", "info", "@openai/codex", "version"],
            "agy": None,
            "grok": None,
        }
        ver_cmd = latest_version_cmds.get(harness_name)
        if ver_cmd:
            try:
                latest_result = subprocess.run(ver_cmd, capture_output=True, text=True, timeout=3)
                latest_version = latest_result.stdout.strip() if latest_result.returncode == 0 else ""
                if latest_version:
                    db_conn.execute(
                        "UPDATE harness_status SET latest_version=? WHERE harness_name=?",
                        (latest_version, harness_name),
                    )
            except Exception:
                pass
    except Exception:
        pass

    _INSTRUCTION_FILES = {
        "claude": "CLAUDE.md",
        "agy": "GEMINI.md",
        "grok": "GROK.md",
        "codex": "AGENTS.md",
    }
    instr_file = _INSTRUCTION_FILES.get(harness_name)
    if write_fence and instr_file and os.path.exists(instr_file):
        capability_body = _build_fence_body_from_record(harness_name, db_conn)
        body = _merge_fence_body(_read_harness_fence_body(instr_file), capability_body)
        _upsert_harness_fence(instr_file, installed_version, body)

    _scan_command_palette(harness_name, record_harness_name, installed_version, db_conn)

    discovered_version = _probe_model_version(harness_name, "")
    if discovered_version and discovered_version not in ("unknown", "session-scoped, no fixed default", "uses Claude Code's built-in default, no override"):
        _diff_and_queue_new_models(harness_name, [discovered_version], db_conn)

    db_conn.commit()
    return {
        "skipped": False,
        "version": installed_version,
        "version_detected": version_detected,
        "status": compliance,
        "schema_issues": schema_issues,
    }


def _run_tc1(harness_name: str, timeout: int = 5) -> dict:
    """TC-1: Headless stdout contract."""
    import sys as _sys

    baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name, {})
    contract = baseline.get("headless_contract", {})
    if not contract:
        return {"requires_pty": False, "passed": True, "stdout_method": "not_applicable"}

    non_interactive_flag = contract.get("non_interactive_flag", "--version")
    env = os.environ.copy()
    for var in contract.get("env_vars_required", []):
        if "=" in var:
            key, value = var.split("=", 1)
            env[key] = value

    try:
        proc = subprocess.Popen(
            [harness_name, non_interactive_flag],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        proc.communicate(timeout=timeout)
        return {"requires_pty": False, "passed": True, "stdout_method": "pipe"}
    except subprocess.TimeoutExpired:
        proc.kill()
        if _sys.platform == "win32":
            return {"requires_pty": True, "passed": False, "stdout_method": "pty"}
        return {"requires_pty": True, "passed": False, "stdout_method": "unavailable"}
    except FileNotFoundError:
        return {"requires_pty": False, "passed": False, "stdout_method": "not_found"}


def _run_tc2(harness_name: str, flags_spec: dict) -> dict:
    """TC-2: Flag compliance."""
    if isinstance(flags_spec, dict):
        invalid_flags = list(flags_spec.get("invalid_flags", []))
        valid_flags = list(flags_spec.get("valid_flags", []))
        required_flags = list(flags_spec.get("required_flags", []))
    else:
        invalid_flags, valid_flags, required_flags = [], [], []

    failed = []
    try:
        result = subprocess.run([harness_name, "--help"], capture_output=True, text=True, timeout=5)
        help_text = (result.stdout or "") + (result.stderr or "")
        expected_flags = list(dict.fromkeys(valid_flags + required_flags))
        for flag in expected_flags:
            flag_name = flag.lstrip("-")
            if flag_name and flag_name not in help_text and flag not in help_text:
                failed.append(flag)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"failed_flags": failed, "passed": len(failed) == 0}


def _run_tc3(endpoints: list) -> dict:
    """TC-3: Network reachability."""
    import socket as _sock

    reachable, unreachable = [], []
    for host, port in endpoints or []:
        try:
            conn = _sock.create_connection((host, port), timeout=2)
            conn.close()
            reachable.append((host, port))
        except OSError:
            unreachable.append((host, port))
    return {"reachable": reachable, "unreachable": unreachable, "passed": len(unreachable) == 0}


def _run_tc4(harness_name: str, db_conn) -> dict:
    """TC-4: Verb map validation."""
    failed = []
    try:
        rows = db_conn.execute(
            """
            SELECT synlynk_verb, harness_command, supported
            FROM harness_verb_map
            WHERE harness_name=?
            """,
            (harness_name,),
        ).fetchall()
    except Exception:
        # Keep TC-4 usable against a caller-supplied pre-rename connection.
        rows = db_conn.execute(
            """
            SELECT synlynk_verb, agent_command, supported
            FROM harness_verb_map
            WHERE agent_name=?
            """,
            (harness_name,),
        ).fetchall()
    for verb, cmd_template, supported in rows:
        if supported == "none" or not cmd_template:
            continue
        cmd = cmd_template.split()[0]
        if cmd.startswith("-"):
            # Some verb rows store a flag fragment (e.g. "--model {model}")
            # rather than a full invocation — there's no binary to probe here.
            continue
        try:
            subprocess.run([cmd, "--help"], capture_output=True, timeout=3)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(verb)
    return {"failed_verbs": failed, "passed": len(failed) == 0}


def _run_tc5(directive_files: dict) -> dict:
    """TC-5: SOP section presence validation."""
    missing = {}
    for agent, path in (directive_files or {}).items():
        try:
            content = open(path).read() if os.path.exists(path) else ""
        except OSError:
            content = ""
        absent = [header for header in SOP_SECTION_HEADERS if header not in content]
        if absent:
            missing[agent] = absent
    return {"passed": not missing, "missing": missing}


def _run_tc6(harness_name: str, env: Optional[dict] = None, timeout: int = 5) -> dict:
    """TC-6: GitHub CLI authentication in the dispatch environment.

    ``gh auth status`` has historically returned zero for some authentication
    failures, so both its exit status and human-readable output must be
    inspected.  Keep the output in the result only for diagnostics; ``gh``
    does not print the token itself.
    """
    auth_env = os.environ.copy() if env is None else dict(env)
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=auth_env,
        )
    except FileNotFoundError:
        return {"passed": False, "error": "gh CLI not found", "output": ""}
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "gh auth status timed out", "output": ""}

    output = ((result.stdout or "") + (result.stderr or "")).strip()
    lower = output.lower()
    invalid_markers = (
        "token in default is invalid",
        "token is invalid",
        "token is expired",
        "authentication token is required",
        "not logged in",
        "no oauth token",
        "failed to log in",
    )
    failures = [marker for marker in invalid_markers if marker in lower]
    if result.returncode != 0 and not failures:
        failures.append(f"exit {result.returncode}")
    return {
        "passed": not failures,
        "error": ", ".join(failures),
        "output": output,
        "returncode": result.returncode,
    }


def _read_harness_fence_body(file_path: str) -> str:
    """Return the current body inside the synlynk harness fence, if present."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return ""
    match = _FENCE_VERSION_AND_BODY_PATTERN.search(content)
    if not match:
        return ""
    return match.group(2)


def _repair_config_agents(cfg: dict) -> list:
    """Return the directive-backed agents that should be considered for SOP repair."""
    cfg_roles = cfg.get("roles") or {}
    workgroup_agents = list(cfg.get("workgroup_agents") or [])
    if workgroup_agents:
        return workgroup_agents
    return [agent for agent in cfg_roles.keys() if agent in {"claude", "agy", "codex", "grok"}]


def _repair_role_list(value) -> list:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _repair_agent_label(agent: str) -> str:
    return agent[:1].upper() + agent[1:] if agent else ""


def _repair_branch_convention(cfg: dict, agent: str) -> str:
    """Return the repo-specific branch pattern for an agent, if recorded."""
    for key in ("branch_conventions", "branch_convention", "branch_naming", "branch_pattern", "branch_prefix"):
        value = cfg.get(key)
        if not value:
            continue
        if isinstance(value, dict):
            agent_value = value.get(agent) or value.get(agent.lower()) or value.get(_repair_agent_label(agent))
            if agent_value:
                return str(agent_value).strip()
            for nested_key in ("pattern", "value", "summary", "description"):
                nested_value = value.get(nested_key)
                if nested_value:
                    return str(nested_value).strip()
            prefix = str(value.get("prefix") or "").strip()
            suffix = str(value.get("suffix") or "").strip()
            if prefix and suffix:
                return f"{prefix}{suffix}"
            if prefix:
                return prefix
            continue
        value_text = str(value).strip()
        if value_text:
            return value_text
    return ""


def _repair_escalation_target(cfg: dict) -> str:
    """Pick the configured PM/review owner, if any, for escalation text."""
    cfg_roles = cfg.get("roles") or {}
    candidates = _repair_config_agents(cfg)
    if not candidates:
        candidates = list(cfg_roles.keys())

    def _role_set(agent: str) -> set:
        return set(_repair_role_list(cfg_roles.get(agent)))

    for agent in candidates:
        roles = _role_set(agent)
        if {"pm", "review"} <= roles:
            return _repair_agent_label(agent)
    for agent in candidates:
        if "review" in _role_set(agent):
            return _repair_agent_label(agent)
    for agent in candidates:
        if "pm" in _role_set(agent):
            return _repair_agent_label(agent)
    return ""


def _repair_pr_review_sop(cfg: dict) -> str:
    escalation_target = _repair_escalation_target(cfg) or "the configured PM/reviewer"
    return (
        "## PR Review Discipline\n"
        "1. Assign a non-authoring agent to review the PR.\n"
        "2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.\n"
        "3. The reviewer alone must merge the PR.\n"
        f"4. If the reviewer is unavailable, escalate to {escalation_target}.\n\n"
        "**GitHub identity note (#423):** If a role has a registered workspace agent "
        "(`synlynk agent init <role>`, e.g. `qa` or `architect`), dispatch its review via "
        "`synlynk dispatch claude --as-agent <role-agent-id>` — this posts a genuine approving "
        "review under that role's own distinct GitHub App identity, satisfying GitHub's non-author "
        "review requirement for real approvals. Route day-to-day reviews through `qa` and any "
        "feature/architecture-impacting review through `architect`. **Fallback (no registered "
        "agent for the role):** post a formal COMMENT review with an explicit approve checklist "
        "(as on PR #417) instead of an approving review, since dispatches without `--as-agent` "
        "share the single repo-owner GitHub identity and an approving review will fail with the "
        "self-approval error.\n"
    )


def _repair_capability_allocation_sop(cfg: dict) -> str:
    cfg_roles = cfg.get("roles") or {}
    ordered_agents = _repair_config_agents(cfg)
    if not ordered_agents:
        ordered_agents = [agent for agent in cfg_roles.keys()]

    rows = []
    for agent in ordered_agents:
        role_list = _repair_role_list(cfg_roles.get(agent))
        if not role_list:
            continue
        role_label = " / ".join(role_list)
        rows.append(f"| {role_label} | {_repair_agent_label(agent)} | {', '.join(role_list)} |")

    if not rows:
        return (
            "## Capability-Based Task Allocation\n"
            "No repo-specific roles are recorded in `.synlynk/config.json`; keep work scoped to the "
            "harness you were assigned and follow the repo's own routing notes.\n"
            "GitHub write routing (#1271): Codex by default, Claude/Agy as fallbacks.\n"
        )

    escalation_target = _repair_escalation_target(cfg) or "the configured PM/reviewer"
    table = "\n".join([
        "## Capability-Based Task Allocation",
        "",
        "**Note:** \"Harness\" below means the execution backend (Claude/Agy/Grok/Codex) that runs a ",
        "task, not the Agent (role) doing the work\n- See `docs/glossary-agent-vs-harness.md`",
        "",
        "| Role | Harness | Tasks |",
        "| :--- | :--- | :--- |",
        *rows,
        f"Do not start a task outside your role column without explicit approval from {escalation_target}.",
        "",
        "**GitHub write routing (#1271):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (verified live in job `job-836e13a4`)\n- Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic \"OK, exit 0\" job status — do not trust job-status alone for Grok gh-write attempts)\n- Codex receives network access only for explicit `--requires-gh-write` dispatches\n- Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569)",
        "",
        "This table is generated from `.synlynk/config.json` so it tracks the repo's own routing "
        "rather than synlynk's default fleet assumptions.",
    ])
    return table + "\n"


def _repair_repo_hygiene_sop(cfg: dict, agent: str) -> str:
    branch_convention = _repair_branch_convention(cfg, agent)
    if branch_convention:
        branch_line = f"2. Use task-scoped branch naming recorded for this repo: `{branch_convention}`."
    else:
        branch_line = (
            "2. Use the repo's documented task-scoped branch pattern; if none is recorded, follow the "
            "project's existing feature/fix/chore naming convention."
        )
    return (
        "## Repo Hygiene\n"
        "1. Do not commit directly to main or master.\n"
        f"{branch_line}\n"
        "3. Co-Authored-By trailer is required: Claude (`Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`), "
        "Agy (`Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`), Codex (`Co-Authored-By: Codex <noreply@openai.com>`), "
        "Grok (`Co-Authored-By: Grok <noreply@x.ai>`).\n"
        "4. Use worktree per feature with `git worktree add`.\n"
        "5. Run `git branch --show-current` before committing to verify branch.\n"
    )


def _build_repair_sop_block(header: str, cfg: dict) -> str:
    if header == "## PR Review Discipline":
        return _repair_pr_review_sop(cfg)
    if header == "## Capability-Based Task Allocation":
        return _repair_capability_allocation_sop(cfg)
    if header == "## Repo Hygiene":
        return _repair_repo_hygiene_sop(cfg, "")
    idx = SOP_SECTION_HEADERS.index(header)
    return SOP_BLOCKS[idx]


def _extract_sop_section(body: str, header: str) -> str:
    pattern = re.compile(rf"(?ms)^{re.escape(header)}\n.*?(?=^## |\Z)")
    match = pattern.search(body or "")
    return match.group(0).rstrip("\n") if match else ""


def _repair_sop_body_parts(*parts: str) -> str:
    """Join SOP body fragments with exactly one blank line between sections."""
    cleaned = [part.strip("\n") for part in parts if part and part.strip("\n")]
    if not cleaned:
        return ""
    return "\n\n".join(cleaned) + "\n"


def _repair_sops_only(
    cfg: dict = None,
    harness_name: str = None,
    dry_run: bool = False,
    **legacy_kwargs,
) -> None:
    """Repair missing SOP sections without rewriting unrelated sync artifacts."""
    if harness_name is None:
        harness_name = legacy_kwargs.pop("agent_name", None)
    if legacy_kwargs:
        raise TypeError(f"unexpected keyword argument: {next(iter(legacy_kwargs))!r}")
    if cfg is None:
        from synlynk import load_config as _load_config

        cfg = _load_config()

    directive_files = {
        "claude": "CLAUDE.md",
        "agy": "GEMINI.md",
        "codex": "AGENTS.md",
        "grok": "GROK.md",
    }
    cfg_agents = _repair_config_agents(cfg)
    agent_names = [harness_name] if harness_name else cfg_agents
    for agent in agent_names:
        fpath = directive_files.get(agent)
        if not fpath or not os.path.exists(fpath):
            continue
        has_harness_fence = _fence_exists(fpath)
        existing_body = _read_harness_fence_body(fpath)
        try:
            full_content = open(fpath, encoding="utf-8").read()
        except OSError:
            full_content = ""
        # Check presence across the whole file, not just inside an existing fence —
        # pre-existing unfenced content (e.g. a raw "## PR Review Discipline" section
        # predating the fence mechanism) must not be duplicated (issue #718).
        fill_headers = [header for header in SOP_SECTION_HEADERS if header not in full_content]
        stale_headers = []

        if has_harness_fence and existing_body:
            stale_candidates = [
                "## PR Review Discipline",
                "## Capability-Based Task Allocation",
            ]
            for header in stale_candidates:
                canonical = _build_repair_sop_block(header, cfg).rstrip("\n")
                current = _extract_sop_section(existing_body, header)
                # Only replace a PR-review section when it contains the known
                # incompatible command shape; preserve repo-specific wording.
                pr_review_is_stale = (
                    header == "## PR Review Discipline"
                    and "synlynk pr check <pr#>" in current
                )
                if current and (
                    pr_review_is_stale
                    if header == "## PR Review Discipline"
                    else current != canonical
                ):
                    stale_headers.append(header)
                    if header in fill_headers:
                        fill_headers.remove(header)

        if dry_run:
            for missing_header in fill_headers:
                print(f"    → fill missing SOP '{missing_header}' in {fpath}")
            for stale_header in stale_headers:
                print(f"    → refresh stale SOP '{stale_header}' in {fpath}")
            continue

        if not fill_headers and not stale_headers:
            continue

        body = existing_body.rstrip("\n")
        for missing_header in fill_headers:
            block = _repair_repo_hygiene_sop(cfg, agent) if missing_header == "## Repo Hygiene" else _build_repair_sop_block(missing_header, cfg)
            body = _repair_sop_body_parts(body, block)
        for stale_header in stale_headers:
            block = _build_repair_sop_block(stale_header, cfg)
            section_pattern = rf"(?ms)^{re.escape(stale_header)}\n.*?(?=^## |\Z)"
            match = re.search(section_pattern, body)
            if match:
                body = _repair_sop_body_parts(body[:match.start()], block, body[match.end():])
            else:
                body = _repair_sop_body_parts(body, block)

        _upsert_harness_fence(fpath, harness_version="sop-repair", body=body)
        for missing_header in fill_headers:
            print(f"    ✓ fill missing SOP '{missing_header}' in {fpath}")
        for stale_header in stale_headers:
            print(f"    ✓ refresh stale SOP '{stale_header}' in {fpath}")


def cmd_probe(agent: str = None, write_fence: bool = True) -> list:
    agents = [agent] if agent else list(HARNESS_CAPABILITY_BASELINES.keys())
    package = sys.modules.get("synlynk")
    get_db = getattr(package, "_get_db", None)
    if get_db is None:
        raise RuntimeError("synlynk package DB helper unavailable")
    db_conn = get_db()
    results = []
    try:
        for harness_name in agents:
            result = _probe_agent(harness_name, db_conn, write_fence=write_fence)
            if result.get("version_detected"):
                _clear_sentinel_alerts(
                    code="HARNESS_VERSION_DRIFT",
                    agent=harness_name,
                )
            status = "skipped (up to date)" if result["skipped"] else result["status"]
            print(f"  probe [{harness_name}] {result['version']} → {status}")
            for issue in result.get("schema_issues", []):
                print(f"    schema incomplete: {issue}")
            results.append({"agent": harness_name, **result})
    finally:
        db_conn.close()
    return results


def _fence_exists(file_path: str) -> bool:
    """Returns True if file_path contains a synlynk harness fence."""
    try:
        with open(file_path) as f:
            return "<!-- synlynk:harness" in f.read()
    except IOError:
        return False


def _spawn_with_pty_fallback_probe(cmd, env, cwd):
    """Local PTY fallback used by _probe_model_version without importing dispatch."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, cwd=cwd)
    try:
        out, _ = proc.communicate(timeout=5)
        if out:
            return proc, out
    except subprocess.TimeoutExpired:
        proc.kill()
    if os.name != "nt":
        import pty
        import select

        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                cwd=cwd,
                close_fds=True,
            )
            os.close(slave_fd)
            out_chunks = []
            while True:
                r, _, _ = select.select([master_fd], [], [], 5)
                if not r:
                    proc.kill()
                    break
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    out_chunks.append(data)
                except OSError:
                    break
            proc.wait(timeout=5)
            return proc, b"".join(out_chunks)
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
    return None, b""


def _read_toml_string_value(path: str, key: str, section: Optional[str] = None) -> Optional[str]:
    """Read a string key from a simple TOML config (stdlib only; no tomllib dep).

    Supports top-level ``key = "value"`` or a single ``[section]`` table.
    Used for agent home configs (~/.codex/config.toml, ~/.grok/config.toml).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None

    # Prefer tomllib when available (3.11+) for nested/quoted edge cases.
    try:
        import tomllib  # type: ignore[attr-defined]

        data = tomllib.loads(text)
        if section:
            nested = data.get(section) if isinstance(data, dict) else None
            val = nested.get(key) if isinstance(nested, dict) else None
        else:
            val = data.get(key) if isinstance(data, dict) else None
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None
    except Exception:
        pass

    if section:
        sec_match = re.search(
            rf"^\[{re.escape(section)}\]\s*$", text, re.MULTILINE
        )
        if not sec_match:
            return None
        rest = text[sec_match.end() :]
        next_sec = re.search(r"^\[", rest, re.MULTILINE)
        if next_sec:
            rest = rest[: next_sec.start()]
        search_text = rest
    else:
        next_sec = re.search(r"^\[", text, re.MULTILINE)
        search_text = text[: next_sec.start()] if next_sec else text

    for quote in ('"', "'"):
        m = re.search(
            rf"^{re.escape(key)}\s*=\s*{quote}([^{quote}]+){quote}",
            search_text,
            re.MULTILINE,
        )
        if m:
            return m.group(1).strip()
    return None


def _probe_model_version(harness_name: str, cli: str) -> str:
    """Tier 2: resolve the harness's configured model from its own config files.

    CLI ``--version`` / ``/status`` probes only surface harness/CLI version (or
    require an interactive session), so this reads each harness's home config:

    - codex: ``~/.codex/config.toml`` top-level ``model``
    - grok:  ``~/.grok/config.toml`` ``[models] default``
    - claude: ``~/.claude/settings.json`` ``model`` (absent → built-in default)
    - agy: no persistent model config (session-scoped ``--model`` only)

    ``cli`` is retained for call-site compatibility; config-path probes do not
    invoke the binary.
    """
    del cli  # signature retained for dispatch_agent(agent, cli) callers

    if harness_name == "agy":
        return "session-scoped, no fixed default"

    if harness_name == "codex":
        model = _read_toml_string_value(
            os.path.expanduser("~/.codex/config.toml"), "model"
        )
        return model if model else "unknown"

    if harness_name == "grok":
        model = _read_toml_string_value(
            os.path.expanduser("~/.grok/config.toml"),
            "default",
            section="models",
        )
        return model if model else "unknown"

    if harness_name == "claude":
        settings_path = os.path.expanduser("~/.claude/settings.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            model = data.get("model") if isinstance(data, dict) else None
            if isinstance(model, str) and model.strip():
                return model.strip()
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            pass
        return "uses Claude Code's built-in default, no override"

    return "unknown"
