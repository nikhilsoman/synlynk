"""synlynk support_engineer: Support Engineer archetype - signal collection, investigation, draft fixes."""

import json
import os
import re
import subprocess
import sys
import time
from typing import Optional
from synlynk._constants import HARNESS_CAPABILITY_BASELINES


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def cmd_agent_run(name: str, dry_run: bool = False, install_cron: bool = False) -> None:
    """Run named agent: collect signals → dedup → investigate → file → fix."""
    import hashlib as _hashlib

    cfg = _pkg("_load_agent_config")(name)
    if install_cron:
        _install_cron_entry(name)
        return

    if "subscriptions" in cfg:
        from synlynk.workspace_agent import cmd_workspace_agent_run

        cmd_workspace_agent_run()
        return

    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    print(f"  [agent:{name}] {'DRY RUN — ' if dry_run else ''}collecting signals{' (CI mode)' if is_ci else ''}")

    collector_map = {
        "test_suite": _collect_test_suite,
        "sentinel_alerts": _collect_sentinel_alerts,
        "telemetry_anomaly": _collect_telemetry_anomaly,
        "capability_drop": _collect_capability_drop,
        "github_issues": _collect_github_issues,
        "platform_ops": _collect_platform_ops,
    }
    ci_skip = {"sentinel_alerts", "telemetry_anomaly"}

    all_findings: list = []
    for signal_cfg in cfg.get("signals", []):
        stype = signal_cfg.get("type")
        if is_ci and stype in ci_skip:
            continue
        collector = collector_map.get(stype)
        if collector is None:
            print(f"  [agent:{name}] unknown signal type: {stype}")
            continue
        try:
            found = collector(signal_cfg)
            all_findings.extend(found)
        except Exception as e:
            print(f"  [agent:{name}] collector {stype} error: {e}")

    new_findings = _dedup_findings(all_findings)
    print(f"  [agent:{name}] {len(all_findings)} signals, {len(new_findings)} new after dedup")

    if dry_run:
        for f in new_findings:
            print(f"  [{f['severity'].upper()}] {f['type']}: {f['summary']}")
        return

    severity_order = {"high": 0, "medium": 1, "low": 2}
    new_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 2))
    to_process = new_findings[:5]

    run_summary_lines = []
    conn = _pkg("_get_db")()

    for finding in to_process:
        print(f"  [agent:{name}] investigating: {finding['summary'][:80]}")
        investigation = _run_investigation(finding, cfg)
        gh_issue_url = _file_gh_issue(finding, investigation, dry_run=False)
        status = "filed"

        fix_pr_url = ""
        if investigation["fix_signal"]:
            fix_status, fix_pr_url = _attempt_fix(
                finding, investigation,
                fixer=cfg.get("fixer", "claude"), dry_run=False
            )
            if fix_status == "fix_attempted":
                status = "fix_attempted"
            elif fix_status == "fix_failed":
                status = "fix_failed"

        run_id = "run-" + _hashlib.md5(
            f"{finding['signal_hash']}{time.time()}".encode()
        ).hexdigest()[:8]
        pr_url_to_store = fix_pr_url if investigation["fix_signal"] else ""
        conn.execute(
            "INSERT INTO autopilot_runs "
            "(id, harness_name, signal_type, signal_hash, severity, summary, status, gh_issue_url, pr_url, story_id, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (run_id, name, finding["type"], finding["signal_hash"],
             finding["severity"], finding["summary"][:200],
             status, gh_issue_url, pr_url_to_store, investigation.get("story_id", ""))
        )
        conn.commit()
        run_summary_lines.append(
            f"  [{finding['severity'].upper()}] {finding['type']}: {finding['summary'][:60]} → {status}"
        )
        print(f"  [agent:{name}] {finding['type']} → {status}")

    conn.close()

    devlog_dir = os.path.join(_pkg("_docs_dir")(), "devlogs")
    if os.path.exists(devlog_dir):
        devlog_path = os.path.join(devlog_dir, f"{name}.md")
        n_high = sum(1 for f in to_process if f.get("severity") == "high")
        n_med = sum(1 for f in to_process if f.get("severity") == "medium")
        n_fix = sum(1 for l in run_summary_lines if "fix_attempted" in l)
        n_filed = sum(1 for l in run_summary_lines if " filed" in l)
        run_id_short = _hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        entry = (
            f"\n{time.strftime('%Y-%m-%dT%H:%M:%S')} · "
            f"{len(to_process)} findings ({n_high} high, {n_med} medium) · "
            f"{n_filed} filed · {n_fix} fix_attempted · run-{run_id_short}\n"
        )
        with open(devlog_path, "a") as f:
            f.write(entry)

    print(f"  [agent:{name}] done — {len(to_process)} findings processed")

def _install_cron_entry(name: str) -> None:
    """Install local crontab entry for the named agent (idempotent)."""
    repo_path = os.path.abspath(".")
    synlynk_bin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "bin",
        "synlynk.py",
    )
    entry = (
        f"0 */6 * * * cd {repo_path} && "
        f"python3 {synlynk_bin} agent run {name} "
        f">> ~/.synlynk/autopilot.log 2>&1"
    )
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = result.stdout if result.returncode == 0 else ""
    if entry in current:
        print("  [cron] Entry already installed (idempotent)")
        return
    new_crontab = current.rstrip("\n") + "\n" + entry + "\n"
    result2 = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if result2.returncode != 0:
        print(f"  [cron] Failed to install crontab entry (exit {result2.returncode})")
        return
    print(f"  [cron] Installed: {entry}")

def cmd_agent_list() -> None:
    """List .agents/ config files and their last run status."""
    agents_dir = ".agents"
    if not os.path.exists(agents_dir):
        print("  No .agents/ directory found")
        return
    files = [f for f in os.listdir(agents_dir) if f.endswith(".json")]
    if not files:
        print("  No agent configs in .agents/")
        return
    conn = _pkg("_get_db")()
    for fname in sorted(files):
        harness_name = fname[:-5]
        row = conn.execute(
            "SELECT ts, status FROM autopilot_runs WHERE harness_name=? ORDER BY ts DESC LIMIT 1",
            (harness_name,)
        ).fetchone()
        last_run = f"{row[0]}  status={row[1]}" if row else "never run"
        print(f"  {harness_name:<25}  {last_run}")
    conn.close()

def _collect_test_suite(signal_cfg: dict) -> list:
    """Run pytest; return a high-severity finding if any test fails."""
    import hashlib as _hashlib
    cmd = signal_cfg.get("command", "pytest tests/ -q --tb=short").split()
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode == 0:
        return []
    output = result.stdout or ""
    signal_hash = _hashlib.md5(output[:500].encode()).hexdigest()[:16]
    return [{
        "type": "test_suite",
        "severity": "high",
        "summary": f"Test suite failure: {output.splitlines()[-1][:120] if output.splitlines() else 'unknown'}",
        "detail": output[:3000],
        "signal_hash": signal_hash,
    }]


def _collect_platform_ops(signal_cfg: dict) -> list:
    """Cross-repo platform ops rollup → findings for Support Engineer."""
    try:
        from synlynk.platform_ops import collect_platform_report
    except Exception as e:
        return [{
            "type": "platform_ops",
            "severity": "medium",
            "summary": f"platform_ops collector import failed: {e}",
            "detail": str(e),
            "signal_hash": "ops-import-fail",
        }]
    hours = int(signal_cfg.get("hours", 24))
    report = collect_platform_report(hours=hours)
    # Prefer structured findings; if ops RED with no findings, synthesize one
    findings = list(report.findings or [])
    if report.scoreboard.get("ops") == "RED" and not findings:
        findings.append({
            "type": "platform_ops",
            "severity": "high",
            "summary": report.scoreboard.get("summary", "platform ops RED"),
            "detail": json.dumps(report.scoreboard.get("ops_red_reasons", []))[:1500],
            "signal_hash": f"ops-scoreboard-red-{hours}h",
        })
    return findings


def _collect_sentinel_alerts(signal_cfg: dict) -> list:
    """Read sentinel.md, return a finding per ⚠ alert line."""
    import hashlib as _hashlib
    path = signal_cfg.get("path", ".synlynk/sentinel.md")
    if not os.path.exists(path):
        return []
    lines = [l for l in open(path).read().splitlines() if "⚠" in l]
    findings = []
    for line in lines:
        upper = line.upper()
        if "FLATLINE" in upper or "QUOTA_EXHAUSTED" in upper or "CRITICAL" in upper:
            severity = "high"
        else:
            severity = "medium"
        signal_hash = _hashlib.md5(line.encode()).hexdigest()[:16]
        findings.append({
            "type": "sentinel_alerts",
            "severity": severity,
            "summary": line.strip()[:200],
            "detail": line.strip(),
            "signal_hash": signal_hash,
        })
    return findings

def _collect_telemetry_anomaly(signal_cfg: dict) -> list:
    """Compute failure rate over last 20 telemetry entries; return finding if above threshold."""
    import json as _json, hashlib as _hashlib
    path = ".synlynk/telemetry.json"
    if not os.path.exists(path):
        return []
    try:
        entries = _json.loads(open(path).read())
    except Exception:
        return []
    recent = entries[-20:]
    if len(recent) < 5:
        return []
    failures = sum(1 for e in recent if e.get("exit_code", 0) != 0)
    threshold = signal_cfg.get("failure_rate_threshold", 0.30)
    rate = failures / len(recent)
    if rate < threshold:
        return []
    severity = "high" if rate >= 0.60 else "medium"
    summary = f"High failure rate: {failures}/{len(recent)} sessions failed ({rate:.0%})"
    signal_hash = _hashlib.md5(summary.encode()).hexdigest()[:16]
    return [{
        "type": "telemetry_anomaly",
        "severity": severity,
        "summary": summary,
        "detail": summary,
        "signal_hash": signal_hash,
    }]

def _collect_capability_drop(signal_cfg: dict) -> list:
    """Compare each agent's avg quality: last 7 days vs. prior 7 days.
    Skip agents with fewer than 2 ratings in either window."""
    import hashlib as _hashlib
    drop_threshold = signal_cfg.get("drop_threshold", 1.5)
    conn = _pkg("_get_db")()
    agents = [r[0] for r in conn.execute(
        "SELECT DISTINCT agent FROM capability_ratings"
    ).fetchall()]
    findings = []
    for agent in agents:
        recent = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM capability_ratings "
            "WHERE agent=? AND ts > datetime('now', '-7 days')",
            (agent,)
        ).fetchone()
        prior = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM capability_ratings "
            "WHERE agent=? AND ts <= datetime('now', '-7 days') "
            "  AND ts > datetime('now', '-14 days')",
            (agent,)
        ).fetchone()
        if not recent or not prior:
            continue
        recent_avg, recent_n = recent
        prior_avg, prior_n = prior
        if recent_n < 2 or prior_n < 2:
            continue
        if recent_avg is None or prior_avg is None:
            continue
        drop = prior_avg - recent_avg
        if drop < drop_threshold:
            continue
        severity = "high" if drop >= 3.0 else "medium"
        summary = f"Capability drop for {agent}: {prior_avg:.1f} → {recent_avg:.1f} (Δ{drop:.1f}pts)"
        signal_hash = _hashlib.md5(f"{agent}{round(drop, 1)}".encode()).hexdigest()[:16]
        findings.append({
            "type": "capability_drop",
            "severity": severity,
            "summary": summary,
            "detail": summary,
            "signal_hash": signal_hash,
        })
    conn.close()
    return findings

def _collect_github_issues(signal_cfg: dict) -> list:
    """List open GitHub issues with matching labels via `gh issue list`."""
    import json as _json, hashlib as _hashlib
    labels = signal_cfg.get("labels", ["bug"])
    label_str = ",".join(labels)
    result = subprocess.run(
        ["gh", "issue", "list", "--label", label_str,
         "--json", "number,title,body,createdAt,labels", "--limit", "20"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [support] gh issue list failed: {result.stderr[:100]}")
        return []
    try:
        issues = _json.loads(result.stdout)
    except Exception:
        return []
    findings = []
    for issue in issues:
        issue_labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        if "support-engineer" in issue_labels:
            continue
        signal_hash = _hashlib.md5(str(issue.get("number", "")).encode()).hexdigest()[:16]
        findings.append({
            "type": "github_issues",
            "severity": "medium",
            "summary": f"#{issue['number']}: {issue.get('title', '')[:100]}",
            "detail": issue.get("body", "")[:500],
            "signal_hash": signal_hash,
        })
    return findings

def _dedup_findings(findings: list) -> list:
    """Filter findings whose signal_hash appeared in autopilot_runs within dedup window.
    github_issues uses 30-day window to avoid re-filing same issue every 8 days."""
    if not findings:
        return []
    conn = _pkg("_get_db")()
    new_findings = []
    for f in findings:
        days = 30 if f.get("type") == "github_issues" else 7
        row = conn.execute(
            "SELECT id FROM autopilot_runs WHERE signal_hash=? AND ts > datetime('now', ?)",
            (f["signal_hash"], f"-{days} days")
        ).fetchone()
        if row is None:
            new_findings.append(f)
    conn.close()
    return new_findings

def _run_investigation(finding: dict, agent_cfg: dict) -> dict:
    """Build prompt, dispatch investigator foreground (5-min timeout), parse output."""
    import hashlib as _hashlib, shlex as _shlex

    agent = agent_cfg.get("investigator", "claude")
    if agent not in HARNESS_CAPABILITY_BASELINES:
        agent = "claude"

    # Create story in DB
    story_id = "support-" + _hashlib.md5(finding["signal_hash"].encode()).hexdigest()[:8]
    conn = _pkg("_get_db")()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, engg_domain, phase) VALUES (?, ?, ?, ?)",
            (story_id, finding["summary"][:100], "test", "scale")
        )
        conn.commit()
    finally:
        conn.close()

    # Build prompt
    try:
        _pkg("generate_context")(scope="full")
    except Exception:
        pass
    context_text = ""
    if os.path.exists(".synlynk/context.md"):
        context_text = open(".synlynk/context.md").read()

    prompt = (
        f"## Signal: {finding['type']} (severity={finding['severity']})\n\n"
        f"{finding['detail']}\n\n"
        f"---\n\n{context_text}\n\n"
        "## Task\n"
        "Identify the root cause. If a code fix is possible, produce a unified diff with "
        "exact file paths. If not fixable, summarise your investigation findings. "
        "If providing a fix, include a line starting with `# FIX:` before the diff block."
    )

    # Write prompt file
    job_id = "support-" + _hashlib.md5(
        f"{finding['signal_hash']}{time.time()}".encode()
    ).hexdigest()[:8]
    os.makedirs(_pkg("LOGS_DIR"), exist_ok=True)
    os.makedirs(_pkg("PROMPTS_DIR"), exist_ok=True)
    log_file = os.path.join(_pkg("LOGS_DIR"), f"{job_id}.log")
    prompt_file = os.path.join(_pkg("PROMPTS_DIR"), f"{job_id}.md")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    # Build shell command (same pattern as dispatch_agent)
    baselines = HARNESS_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")
    if prompt_via_arg and prompt_flag:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
    else:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)

    if prompt_via_arg:
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        shell_cmd = (
            f"{cmd_str} < {_shlex.quote(prompt_file)} "
            f"> {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )

    _investigation_start = time.time()
    try:
        subprocess.run(["sh", "-c", shell_cmd], timeout=300)
    except subprocess.TimeoutExpired:
        pass

    log_text = ""
    if os.path.exists(log_file):
        log_text = open(log_file).read()

    duration_s = time.time() - _investigation_start
    token_counts = _pkg("extract_tokens")(log_text, agent=agent)
    in_tokens, out_tokens = token_counts
    basis = getattr(token_counts, "basis", "none")
    model_version = _pkg("extract_model_version")(log_text, agent=agent)
    _pkg("update_costs")(
        f"{agent} investigate {job_id}",
        in_tokens,
        out_tokens,
        duration_s,
        model_version=model_version,
        story_id=story_id,
        agent=agent,
        basis=basis,
        job_id=job_id,
    )

    import re as _re
    fix_signal = "# FIX:" in log_text or bool(
        _re.search(r"^--- a/", log_text, _re.MULTILINE)
    )

    return {
        "summary": log_text[:500] if log_text else "(no output)",
        "fix_signal": fix_signal,
        "log_text": log_text,
        "story_id": story_id,
        "log_file": log_file,
    }

def _file_gh_issue(finding: dict, investigation: dict, dry_run: bool) -> str:
    """File a GitHub issue via `gh issue create`. Returns issue URL or '' in dry-run."""
    if dry_run:
        return ""
    title = f"[support] {finding['type']}: {finding['summary'][:80]}"
    body = (
        f"## Signal\n\n**Type:** {finding['type']}  \n**Severity:** {finding.get('severity', '?')}\n\n"
        f"## Investigation\n\n{investigation['summary']}\n\n"
        f"**Story:** `{investigation.get('story_id', 'n/a')}`\n"
    )
    result = subprocess.run(
        ["gh", "issue", "create",
         "--title", title,
         "--body", body,
         "--label", "bug,support-engineer"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [support] gh issue create failed: {result.stderr[:200]}")
        return ""
    return result.stdout.strip()

def _recommend_handoff_agent(task_text: str, failed_agent: str, db_conn) -> str:
    """Pick the highest cycle-capability agent for the stalled task."""
    try:
        from synlynk.status import _classify_task_type
    except Exception:
        _classify_task_type = lambda prompt: "default"  # type: ignore

    task_type = _classify_task_type(task_text or "")
    task_to_cycle = {
        "implement": "execute",
        "review": "execute",
        "plan": "open",
        "debug": "sustain",
        "test": "execute",
        "docs": "notify",
        "default": "execute",
    }
    cycle = task_to_cycle.get(task_type, "execute")

    try:
        rows = db_conn.execute(
            "SELECT harness_name, support, verb_count, full_count, partial_count "
            "FROM cycle_capability WHERE cycle=?",
            (cycle,),
        ).fetchall()
    except Exception:
        rows = []

    ranked = []
    for harness_name, support, verb_count, full_count, partial_count in rows:
        if harness_name == failed_agent:
            continue
        support_score = {"full": 300, "partial": 150, "none": 0}.get(support, 0)
        score = (
            support_score
            + int(full_count or 0) * 10
            + int(partial_count or 0) * 5
            + int(verb_count or 0)
        )
        ranked.append((score, harness_name))

    if ranked:
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return ranked[0][1]

    for harness_name in HARNESS_CAPABILITY_BASELINES:
        if harness_name != failed_agent:
            return harness_name
    return failed_agent

def _stalled_job_ids_from_sentinel(sentinel_text: str) -> set:
    """Extract stalled job ids from HANDOFF_PENDING sentinel lines."""
    pending_ids = set()
    for line in (sentinel_text or "").splitlines():
        if "HANDOFF_PENDING" not in line:
            continue
        match = re.search(r"Job (job-[\w-]+)", line)
        if match:
            pending_ids.add(match.group(1))
    return pending_ids

def _extract_diff(text: str) -> Optional[str]:
    """Extract first unified diff block from text (fenced or raw)."""
    import re as _re
    # Prefer fenced ```diff block
    m = _re.search(r"```(?:diff)?\n(---[\s\S]+?)```", text)
    if m:
        return m.group(1)
    # Fall back to raw unified diff
    m = _re.search(r"(--- a/[\s\S]+?)(?=\n[^+\-@ \t]|\Z)", text)
    if m:
        return m.group(1)
    return None

def _attempt_fix(finding: dict, investigation: dict, fixer: str, dry_run: bool) -> tuple:
    """Branch, apply diff, run tests. Returns (status, pr_url) tuple.
    status: 'fix_attempted'|'fix_failed'|'no_diff'|'dry_run'"""
    import tempfile as _tempfile

    if dry_run:
        return "dry_run", ""

    diff = _extract_diff(investigation.get("log_text", ""))
    if diff is None:
        return "no_diff", ""

    branch = f"support/fix-{finding['signal_hash'][:8]}"
    base_branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    base_branch = base_branch_result.stdout.strip() or "main"

    # Create fix branch
    br = subprocess.run(["git", "checkout", "-b", branch], capture_output=True)
    if br.returncode != 0:
        subprocess.run(["git", "checkout", branch], capture_output=True)

    # Write diff to temp file and apply
    with _tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tf:
        tf.write(diff)
        patch_path = tf.name

    try:
        apply = subprocess.run(["git", "apply", patch_path], capture_output=True)
    finally:
        try:
            os.unlink(patch_path)
        except OSError:
            pass

    if apply.returncode != 0:
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        return "fix_failed", ""

    # Commit the patch
    subprocess.run(["git", "add", "-A"], capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"[support] fix: {finding['summary'][:60]}"],
        capture_output=True,
    )

    # Run tests
    test_result = subprocess.run(
        ["pytest", "tests/", "-q", "--tb=no"],
        capture_output=True, text=True,
    )

    if test_result.returncode == 0:
        pr_result = subprocess.run(
            ["gh", "pr", "create", "--draft",
             "--title", f"[support] fix: {finding['summary'][:60]}",
             "--body", (
                 f"Auto-generated fix.\n\n"
                 f"**Story:** `{investigation.get('story_id', 'n/a')}`\n\n"
                 f"**Investigation:**\n{investigation.get('summary', '')[:300]}"
             )],
            capture_output=True, text=True,
        )
        if pr_result.returncode != 0:
            print(f"  [support] gh pr create failed: {pr_result.stderr[:200]}")
        pr_url = pr_result.stdout.strip() if pr_result.returncode == 0 else ""
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        return "fix_attempted", pr_url
    else:
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        return "fix_failed", ""
