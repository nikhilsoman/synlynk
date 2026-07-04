"""synlynk probe: agent capability probing, fence management, TC compliance."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.sentinel import _write_sentinel_alert


def _compute_capability_hash(headless_contract: dict, dispatch_flags) -> str:
    import hashlib as _hashlib
    import json as _json

    payload = _json.dumps({"contract": headless_contract, "flags": dispatch_flags}, sort_keys=True)
    return _hashlib.sha256(payload.encode()).hexdigest()[:16]


_re = re


def _scan_command_palette(agent_name: str, harness_name: str, cli_version: str, db_conn) -> list:
    """Parse --help output and populate harness_command_palette."""
    try:
        result = subprocess.run([agent_name, "--help"], capture_output=True, text=True, timeout=5)
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


_FENCE_OPEN_PATTERN = _re.compile(
    r"<!-- synlynk:harness v\S+ verified:\S+ -->.*?<!-- /synlynk:harness -->",
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

    fence = _build_fence_content(harness_version, body)
    with open(file_path, "r", encoding="utf-8") as f:
        current = f.read()

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

    directive_files = ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md"]
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


def _build_fence_body_from_record(agent_name: str, db_conn=None) -> str:
    import json as _j

    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    contract = baseline.get("headless_contract", {})
    flags_spec = baseline.get("dispatch_flags", {})
    net_deps = baseline.get("network_deps", {})

    if db_conn:
        row = db_conn.execute(
            "SELECT active_contract, active_flags FROM harness_records WHERE agent_name=?",
            (agent_name,)
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


def _probe_agent(agent_name: str, db_conn, fast_path_ok: bool = True) -> dict:
    import json as _json
    import socket as _sock
    import time as _time

    harness_map = {"claude": "claude-cli", "agy": "agy", "grok": "grok", "codex": "codex"}
    harness_name = harness_map.get(agent_name, agent_name)
    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})

    try:
        result = subprocess.run([agent_name, "--version"], capture_output=True, text=True, timeout=5)
        installed_version = result.stdout.strip().split()[-1] if result.stdout.strip() else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        installed_version = "unavailable"

    contract = baseline.get("headless_contract", {})
    flags = baseline.get("dispatch_flags", {})
    new_hash = _compute_capability_hash(contract, flags)

    if fast_path_ok:
        row = db_conn.execute(
            "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
            (agent_name,),
        ).fetchone()
        if row and row[0] == installed_version and row[1] == new_hash:
            return {"skipped": True, "version": installed_version, "status": "ok"}

    network_ok = True
    for endpoint in baseline.get("network_deps", {}).get("required_endpoints", []):
        host, _, port_s = endpoint.rpartition(":")
        try:
            s = _sock.create_connection((host, int(port_s or 443)), timeout=2)
            s.close()
        except OSError:
            network_ok = False

    compliance = "ok" if network_ok else "degraded"

    prev_row = db_conn.execute(
        "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
        (agent_name,),
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
            (agent_name, harness_name, installed_version, compliance_status, active_contract, active_flags, capability_hash, last_probe_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_name) DO UPDATE SET
            harness_name=excluded.harness_name,
            installed_version=excluded.installed_version,
            compliance_status=excluded.compliance_status,
            active_contract=excluded.active_contract,
            active_flags=excluded.active_flags,
            capability_hash=excluded.capability_hash,
            last_probe_at=excluded.last_probe_at
        """,
        (
            agent_name,
            harness_name,
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
            INSERT INTO harness_version_history (agent_name, cli_version, event_type, prev_hash, new_hash, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                agent_name,
                installed_version,
                event_type,
                prev_row[1] if prev_row else None,
                new_hash,
                now,
            ),
        )

    try:
        from synlynk.status import TIER1_CAPACITY, _compute_cycle_capability

        cap = TIER1_CAPACITY.get(agent_name, {})
        attach_point_in_time = 1 if compliance == "ok" else 0
        db_conn.execute(
            """
            INSERT INTO harness_status (
                agent_name, attach_point_in_time, installed_version,
                ctx_window_tokens, read_budget_tokens, write_budget_tokens,
                tool_budget_count, tc1_status, tc2_status, tc3_status, tc4_status,
                last_probe_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_name) DO UPDATE SET
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
                agent_name,
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
        _compute_cycle_capability(agent_name, db_conn)

        latest_version_cmds = {
            "claude": ["npm", "info", "@anthropic-ai/claude-code", "version"],
            "codex": ["npm", "info", "@openai/codex", "version"],
            "agy": None,
            "grok": None,
        }
        ver_cmd = latest_version_cmds.get(agent_name)
        if ver_cmd:
            try:
                latest_result = subprocess.run(ver_cmd, capture_output=True, text=True, timeout=3)
                latest_version = latest_result.stdout.strip() if latest_result.returncode == 0 else ""
                if latest_version:
                    db_conn.execute(
                        "UPDATE harness_status SET latest_version=? WHERE agent_name=?",
                        (latest_version, agent_name),
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
    instr_file = _INSTRUCTION_FILES.get(agent_name)
    if instr_file and os.path.exists(instr_file):
        body = _build_fence_body_from_record(agent_name, db_conn)
        _upsert_harness_fence(instr_file, installed_version, body)

    _scan_command_palette(agent_name, harness_name, installed_version, db_conn)

    db_conn.commit()
    return {"skipped": False, "version": installed_version, "status": compliance}


def _run_tc1(agent_name: str, timeout: int = 5) -> dict:
    """TC-1: Headless stdout contract."""
    import sys as _sys

    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
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
            [agent_name, non_interactive_flag],
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


def _run_tc2(agent_name: str, flags_spec: dict) -> dict:
    """TC-2: Flag compliance."""
    if isinstance(flags_spec, dict):
        invalid_flags = list(flags_spec.get("invalid_flags", []))
        valid_flags = list(flags_spec.get("valid_flags", []))
    else:
        invalid_flags, valid_flags = [], []

    failed = list(invalid_flags)
    try:
        result = subprocess.run([agent_name, "--help"], capture_output=True, text=True, timeout=5)
        help_text = (result.stdout or "") + (result.stderr or "")
        for flag in valid_flags:
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


def _run_tc4(agent_name: str, db_conn) -> dict:
    """TC-4: Verb map validation."""
    failed = []
    rows = db_conn.execute(
        """
        SELECT synlynk_verb, agent_command, supported
        FROM harness_verb_map
        WHERE agent_name=?
        """,
        (agent_name,),
    ).fetchall()
    for verb, cmd_template, supported in rows:
        if supported == "none" or not cmd_template:
            continue
        cmd = cmd_template.split()[0]
        try:
            subprocess.run([cmd, "--help"], capture_output=True, timeout=3)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(verb)
    return {"failed_verbs": failed, "passed": len(failed) == 0}


def cmd_probe(agent: str = None) -> None:
    agents = [agent] if agent else list(AGENT_CAPABILITY_BASELINES.keys())
    package = sys.modules.get("synlynk")
    get_db = getattr(package, "_get_db", None)
    if get_db is None:
        raise RuntimeError("synlynk package DB helper unavailable")
    db_conn = get_db()
    try:
        for agent_name in agents:
            result = _probe_agent(agent_name, db_conn)
            status = "skipped (up to date)" if result["skipped"] else result["status"]
            print(f"  probe [{agent_name}] {result['version']} → {status}")
    finally:
        db_conn.close()


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


def _probe_model_version(agent_name: str, cli: str) -> str:
    """Tier 2: probe the agent's active model from its statusline before dispatch."""
    probe_cmds = {
        "claude": [cli, "/status"],
        "agy":    [cli, "--version"],
        "codex":  [cli, "--version"],
        "grok":   [cli, "-v"],
    }
    cmd = probe_cmds.get(agent_name, [cli, "--version"])
    patterns = [
        r"(claude-[\d.a-z-]*(?:opus|sonnet|haiku)[\w.-]*)",
        r"(agy-[\w.-]+)",
        r"(gemini-[\w.-]+)",
        r"(gpt-[\d.]+-[\w.-]+)",
        r"(codex-[\w-]+)",
        r"(grok-[\w.-]+)",
    ]

    def _extract_version(text: str) -> str:
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).lower()
        return "unknown"

    try:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
        contract = baseline.get("headless_contract", {})
        env = os.environ.copy()
        for var in contract.get("env_vars_required", []):
            if "=" in var:
                k, v = var.split("=", 1)
                env[k] = v

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
            cwd=os.getcwd(),
        )
        text = "\n".join(
            part for part in (getattr(result, "stdout", ""), getattr(result, "stderr", ""))
            if part
        )
        version = _extract_version(text)
        if version != "unknown":
            return version
    except Exception:
        pass

    try:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
        contract = baseline.get("headless_contract", {})
        env = os.environ.copy()
        for var in contract.get("env_vars_required", []):
            if "=" in var:
                k, v = var.split("=", 1)
                env[k] = v
        package = sys.modules.get("synlynk")
        pty_fallback = getattr(package, "_spawn_with_pty_fallback", _spawn_with_pty_fallback_probe)
        _proc, out = pty_fallback(cmd, env, os.getcwd())
        text = out.decode("utf-8", errors="ignore") if out else ""
        version = _extract_version(text)
        if version != "unknown":
            return version
    except Exception:
        pass
    return "unknown"
