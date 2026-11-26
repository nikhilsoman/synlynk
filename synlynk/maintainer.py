"""Autonomous maintainer issue burndown classifier and sentinel maintenance loop."""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Optional, Tuple

from synlynk.maintainer_taxonomy import cluster_keywords, remediation_topics
from synlynk.sentinel import _iter_sentinel_alerts, _normalize_sentinel_severity

SEVERITY_RANKS = {
    "CRITICAL": 4,
    "ERROR": 3,
    "WARN": 2,
    "INFO": 1,
}


def is_issue_remediated(
    issue_text: str,
    commit_messages: List[str],
    issue_number: Optional[int] = None,
) -> bool:
    """Return True if a commit message or closed decision remediates the same topic as the issue."""
    issue_lower = issue_text.lower()

    if issue_number is not None:
        num_patterns = [
            f"#{issue_number}",
            f"gh:#{issue_number}",
            f"fixes #{issue_number}",
            f"closes #{issue_number}",
            f"resolves #{issue_number}",
            f"gh-{issue_number}",
        ]
        for msg in commit_messages:
            msg_lower = msg.lower()
            if any(pat in msg_lower for pat in num_patterns):
                return True

    topics = remediation_topics()
    for msg in commit_messages:
        msg_lower = msg.lower()
        for topic in topics:
            if topic in issue_lower and topic in msg_lower:
                return True
        if "circuit breaker" in issue_lower and "live-19" in msg_lower:
            return True
        live_tags = re.findall(r"live-\d+", issue_lower)
        for tag in live_tags:
            if tag in msg_lower:
                return True
    return False


def triage_sentinel_alerts(path: Optional[str] = None, max_age_days: int = 7) -> list[dict]:
    """Parse, deduplicate, and rank recurring sentinel alerts by severity and frequency."""
    alerts = _iter_sentinel_alerts(path=path, active_only=True)
    if not alerts:
        return []

    now = datetime.now(timezone.utc)
    groups: dict[str, dict] = {}

    for alert in alerts:
        last_seen = alert.get("last_seen_dt") or alert.get("timestamp_dt")
        if last_seen is not None and (now - last_seen).total_seconds() > (max_age_days * 86400):
            continue

        sev = _normalize_sentinel_severity(alert.get("severity") or "INFO")
        code = (alert.get("code") or "GENERAL").strip().upper()
        fingerprint = f"{sev}:{code}"

        occurrences = int(alert.get("occurrences") or 1)
        first_seen_str = str(alert.get("first_seen") or alert.get("timestamp") or "unknown")
        last_seen_str = str(alert.get("last_seen") or alert.get("timestamp") or "unknown")
        message = str(alert.get("message") or alert.get("raw_line") or "").strip()

        if fingerprint not in groups:
            groups[fingerprint] = {
                "fingerprint": fingerprint,
                "severity": sev,
                "code": code,
                "total_occurrences": occurrences,
                "first_seen": first_seen_str,
                "last_seen": last_seen_str,
                "sample_messages": [message] if message else [],
                "alerts": [alert],
            }
        else:
            g = groups[fingerprint]
            g["total_occurrences"] += occurrences
            g["last_seen"] = last_seen_str
            if message and message not in g["sample_messages"]:
                g["sample_messages"].append(message)
            g["alerts"].append(alert)

    ranked = list(groups.values())
    ranked.sort(
        key=lambda g: (SEVERITY_RANKS.get(g["severity"], 0), g["total_occurrences"]),
        reverse=True,
    )
    return ranked


def format_triage_issue(group: dict) -> str:
    """Format structured GitHub issue body for a recurring sentinel fault group."""
    code = group.get("code", "GENERAL")
    sev = group.get("severity", "INFO")
    fingerprint = group.get("fingerprint", f"{sev}:{code}")
    occurrences = group.get("total_occurrences", 1)
    first_seen = group.get("first_seen", "unknown")
    last_seen = group.get("last_seen", "unknown")
    samples = "\n".join(f"- {msg}" for msg in group.get("sample_messages", [])[:5]) or "- No detailed messages."

    return f"""# [Maintainer Triage] {code}: recurring {sev.lower()} sentinel fault

## Intent
Automated triage by workspace Maintainer agent for recurring sentinel fault `{code}`.

## Context
- **Severity:** `{sev}`
- **Fingerprint:** `{fingerprint}`
- **Total Occurrences:** {occurrences}
- **First Seen:** `{first_seen}`
- **Last Seen:** `{last_seen}`

## Diagnostic Evidence
```
{samples}
```

## Reproduction Recipe
1. Verify sentinel alert state: `synlynk sentinel list`
2. Run focused reproduction test: `pytest -k "{code.lower()}"`
3. Check recent daemon logs: `tail -n 100 .synlynk/daemon.log`

## Acceptance Criteria
- [ ] Root cause identified and reproduction test committed.
- [ ] Minimal fix implemented without architectural scope creep.
- [ ] Sentinel alert cleared via `synlynk sentinel clear --code {code}`.
"""


def probe_reproduction(group: dict, workspace_root: Optional[str] = None) -> dict:
    """Execute reproduction probe in a scratch or local workspace."""
    code = str(group.get("code") or "").lower()
    root = workspace_root or os.getcwd()

    cmd = ["pytest", "-k", code]
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        reproduced = res.returncode != 0
        return {
            "reproduced": reproduced,
            "exit_code": res.returncode,
            "output": (res.stdout + res.stderr)[:2000],
        }
    except Exception as exc:
        return {
            "reproduced": False,
            "exit_code": 1,
            "output": f"Probe error: {exc}",
        }


def _workspace_repos(repo_root: str) -> list[str]:
    """Read `.synlynk/workspace.json` repos. Accept path strings or `{path}` objects."""
    import json

    path = os.path.join(repo_root, ".synlynk", "workspace.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    repos = []
    for entry in data.get("repos") or []:
        if isinstance(entry, str) and entry.strip():
            repos.append(entry)
        elif isinstance(entry, dict) and entry.get("path"):
            repos.append(str(entry["path"]))
    return repos


def cmd_maintainer_sweep(repo_root: str = ".", refresh_graph: bool = False) -> int:
    """Dry-run by default. `--refresh-graph` rebuilds the graph, cache, and mesh."""
    import json

    repo_root = os.path.abspath(repo_root)
    repos = _workspace_repos(repo_root)
    mesh_path = os.path.join(repo_root, ".synlynk", "mesh.json")
    if not refresh_graph:
        print(f"would ensure graph for {repo_root}")
        print("would rewrite traversal cache")
        if len(repos) >= 2:
            print(f"would rebuild mesh from {len(repos)} repos at {mesh_path}")
        else:
            print("would skip mesh (workspace lists fewer than 2 repos)")
        return 0

    from synlynk.scan import ensure_graph_for_head

    if not ensure_graph_for_head(repo_root):
        print("graph refresh failed", file=__import__("sys").stderr)
        return 1

    from synlynk.graph_cache import write_traversal_cache

    write_traversal_cache(repo_root)
    if len(repos) < 2:
        return 0

    previous_edges = []
    if os.path.isfile(mesh_path):
        try:
            with open(mesh_path, encoding="utf-8") as handle:
                previous = json.load(handle)
            if isinstance(previous, dict):
                previous_edges = previous.get("edges") or []
        except (OSError, json.JSONDecodeError):
            previous_edges = []

    from synlynk.mesh import build_federated_mesh, contract_drift

    mesh = build_federated_mesh(repos, mesh_path)
    rows = contract_drift(previous_edges, mesh.get("edges") or [])
    if not rows:
        return 0
    for row in rows:
        print(f"contract drift: {row['source']} -> {row['target']}")
    try:
        from synlynk.sentinel import _write_sentinel_alert

        os.makedirs(os.path.join(repo_root, ".synlynk"), exist_ok=True)
        _write_sentinel_alert(
            "WARN",
            "MESH_CONTRACT_DRIFT",
            "; ".join(f"{row['source']} -> {row['target']}" for row in rows),
            sentinel_path=os.path.join(repo_root, ".synlynk", "sentinel.md"),
        )
    except Exception as exc:
        print(f"  ⚠ could not record MESH_CONTRACT_DRIFT: {exc}")
    return 0


def cluster_open_issues(issues: list[dict]) -> dict[str, list[dict]]:
    """Cluster open issues by keyword/label match against the repo's taxonomy."""
    keywords_by_cluster = cluster_keywords()
    clustered: dict[str, list[dict]] = {name: [] for name in keywords_by_cluster}
    clustered["other"] = []

    for issue in issues:
        title = str(issue.get("title") or "").lower()
        body = str(issue.get("body") or "").lower()
        labels = [str(l).lower() for l in (issue.get("labels") or [])]
        haystack = f"{title} {body} {' '.join(labels)}"

        matched = False
        for cluster_name, keywords in keywords_by_cluster.items():
            if cluster_name.lower() in haystack or any(kw.lower() in haystack for kw in keywords):
                clustered[cluster_name].append(issue)
                matched = True
                break
        if not matched:
            clustered["other"].append(issue)

    return {name: items for name, items in clustered.items() if items}


def run_backlog_burndown_sweep(
    repo_root: str = ".",
    conn=None,
    dry_run: bool = True,
    limit: int = 50,
) -> dict:
    """Execute backlog burndown sweep: identify remediated issues and cluster remaining work."""
    commit_messages = []
    try:
        res = subprocess.run(
            ["git", "log", "-n", "300", "--pretty=format:%B%x1f"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            commit_messages = [m.strip() for m in res.stdout.split("\x1f") if m.strip()]
    except Exception:
        pass

    from synlynk.backlog import fetch_open_github_issues

    open_issues = fetch_open_github_issues(limit=limit)
    remediated = []
    remaining = []

    for iss in open_issues:
        num = iss.get("number")
        title = iss.get("title", "")
        body = iss.get("body", "")
        text = f"{title} {body}"

        if is_issue_remediated(text, commit_messages, issue_number=num):
            remediated.append(iss)
            if not dry_run and num:
                try:
                    subprocess.run(
                        [
                            "python3", "bin/synlynk.py", "gh", "--role", "qa", "--",
                            "issue", "close", str(num),
                            "--comment", "Closed via autonomous Maintainer backlog burndown sweep: remediating commit detected in git log.",
                        ],
                        cwd=repo_root,
                        capture_output=True,
                        timeout=15,
                    )
                except Exception:
                    pass
        else:
            remaining.append(iss)

    clusters = cluster_open_issues(remaining)

    sprint_staged = None
    if remaining:
        largest_domain = max(clusters.keys(), key=lambda d: len(clusters[d])) if clusters else "general"
        count = len(clusters.get(largest_domain, []))
        if count >= 3:
            sprint_staged = {
                "domain": largest_domain,
                "count": count,
                "title": f"Backlog Burndown Sprint: {largest_domain} ({count} issues)",
                "issue_numbers": [i.get("number") for i in clusters.get(largest_domain, []) if i.get("number")],
            }

    return {
        "inspected": len(open_issues),
        "remediated_count": len(remediated),
        "remediated": [{"number": i.get("number"), "title": i.get("title")} for i in remediated],
        "remaining_count": len(remaining),
        "clusters": {k: len(v) for k, v in clusters.items()},
        "sprint_staged": sprint_staged,
        "dry_run": dry_run,
    }


def cmd_maintainer_burndown(repo_root: str = ".", dry_run: bool = False, limit: int = 50) -> int:
    """CLI verb for maintainer backlog burndown sweep."""
    res = run_backlog_burndown_sweep(repo_root=repo_root, dry_run=dry_run, limit=limit)
    mode_str = " (DRY-RUN)" if res["dry_run"] else ""
    print(f"\n  Maintainer Backlog Burndown Sweep{mode_str}:")
    print(f"  • Inspected: {res['inspected']} open issues")
    print(f"  • Remediated: {res['remediated_count']} issues")
    for r in res["remediated"][:5]:
        print(f"    - #{r.get('number')}: {r.get('title')}")
    print(f"  • Remaining: {res['remaining_count']} issues")
    print("  • Domain Clusters:")
    for dom, count in res["clusters"].items():
        print(f"    - {dom}: {count} issue(s)")
    if res.get("sprint_staged"):
        s = res["sprint_staged"]
        print(f"\n  ✓ Staged Burndown Sprint: {s['title']}")
    return 0


@dataclass(frozen=True)
class Evidence:
    tier: str  # "code_graph" | "doc_graph" | "keyword"
    weight: float
    detail: str


def _code_graph_distance(file_a: str, file_b: str, repo_root: str = ".") -> Optional[int]:
    """File-level graph distance (1 = a direct edge connects some node in
    file_a to some node in file_b; 2 = one hop apart via a shared neighbor
    file), or None if either file has no graph node.

    DECIDE panel re-review 2026-11-24 (Codex): reads .synlynk/graphify-out/graph.json
    directly and derives file-to-file adjacency from its node/edge lists on the fly.
    """
    import json
    import os

    if file_a == file_b:
        return 0
    graph_path = os.path.join(repo_root, ".synlynk", "graphify-out", "graph.json")
    if not os.path.exists(graph_path):
        return None
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    edges = [e for e in (graph.get("edges") or graph.get("links") or []) if isinstance(e, dict)]
    node_file = {str(n["id"]): n.get("file") for n in nodes}

    file_adjacency: dict = {}
    for edge in edges:
        source_file = node_file.get(str(edge.get("source") or ""))
        target_file = node_file.get(str(edge.get("target") or ""))
        if not source_file or not target_file or source_file == target_file:
            continue
        file_adjacency.setdefault(source_file, set()).add(target_file)
        file_adjacency.setdefault(target_file, set()).add(source_file)

    if file_a not in file_adjacency or file_b not in file_adjacency:
        return None
    if file_b in file_adjacency[file_a]:
        return 1
    if any(file_b in file_adjacency.get(mid, set()) for mid in file_adjacency[file_a]):
        return 2
    return None


def _load_docgraph(repo_root: str = "."):
    """Load the persisted .synlynk/docgraph.json, or None if absent/unreadable."""
    import json
    import os

    path = os.path.join(repo_root, ".synlynk", "docgraph.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    from synlynk.docgraph import DocGraph

    return DocGraph(**{k: v for k, v in data.items() if k in DocGraph.__dataclass_fields__})


def _proximal_selection_config(repo_root: str = ".") -> dict:
    """Weights/threshold from .synlynk/maintainer_taxonomy.json's
    proximal_selection block (spec §6), falling back to built-in defaults."""
    from synlynk.maintainer_taxonomy import load_taxonomy

    taxonomy = load_taxonomy(repo_root=repo_root)
    return taxonomy.get("proximal_selection") or {
        "code_graph_weights": {"distance_1": 0.6, "distance_2": 0.3},
        "doc_graph_weights": {"shared_doc": 0.4, "shared_issue_or_pr": 0.3},
        "keyword_weight": 0.2,
        "join_threshold": 0.5,
    }


def _collect_evidence(candidate: dict, proposal: dict, repo_root: str = ".") -> List[Evidence]:
    """Every Evidence record linking candidate to this one proposal, across
    all three tiers (spec §5.6). Each tier contributes independently --
    weights are summed by the caller, not first-match-wins."""
    config = _proximal_selection_config(repo_root)
    evidence: List[Evidence] = []
    candidate_files = candidate.get("touched_files") or []
    proposal_files = proposal.get("touched_files") or []

    code_weights = config["code_graph_weights"]
    for cf in candidate_files:
        for pf in proposal_files:
            distance = _code_graph_distance(cf, pf, repo_root)
            if distance == 1:
                evidence.append(Evidence("code_graph", code_weights["distance_1"], f"distance-1: {cf} <-> {pf}"))
            elif distance == 2:
                evidence.append(Evidence("code_graph", code_weights["distance_2"], f"distance-2: {cf} <-> {pf}"))

    docgraph = _load_docgraph(repo_root)
    if docgraph is not None:
        doc_weights = config["doc_graph_weights"]
        candidate_docs, candidate_refs = set(), set()
        for f in candidate_files:
            candidate_docs.update(docgraph.reverse_code_index.get(f, []))
            candidate_refs.update(docgraph.reverse_doc_index.get(f, []))
        proposal_docs, proposal_refs = set(), set()
        for f in proposal_files:
            proposal_docs.update(docgraph.reverse_code_index.get(f, []))
            proposal_refs.update(docgraph.reverse_doc_index.get(f, []))
        shared_docs = candidate_docs & proposal_docs
        if shared_docs:
            evidence.append(Evidence("doc_graph", doc_weights["shared_doc"], f"shared docs: {sorted(shared_docs)}"))
        shared_issues = (set(candidate.get("issues_and_prs") or []) | candidate_refs) & (
            set(proposal.get("issues_and_prs") or []) | proposal_refs
        )
        if shared_issues:
            evidence.append(Evidence("doc_graph", doc_weights["shared_issue_or_pr"], f"shared issues/PRs: {sorted(shared_issues)}"))

    if candidate.get("cluster") and candidate.get("cluster") == proposal.get("cluster"):
        evidence.append(Evidence("keyword", config["keyword_weight"], f"cluster match: {candidate['cluster']}"))

    return evidence


def select_proposal_target(
    candidate: dict, open_proposals: List[dict], repo_root: str = "."
) -> Tuple[Optional[str], List[str]]:
    """Weighted evidence-based proximal selection (spec §5.6). Returns
    (proposal_id_or_None, tier_provenance) -- tier_provenance lists which
    tiers contributed evidence to the winning proposal, recorded on the
    proposal for the "why this grouping" UI detail. Deterministic
    tie-break: highest score, then oldest created_at, then lexical
    proposal_id.
    """
    config = _proximal_selection_config(repo_root)
    threshold = config["join_threshold"]

    scored = []
    for proposal in open_proposals:
        proposal_evidence = _collect_evidence(candidate, proposal, repo_root)
        score = sum(e.weight for e in proposal_evidence)
        if score >= threshold:
            scored.append((score, proposal.get("created_at", ""), proposal["proposal_id"], proposal_evidence))

    if not scored:
        return None, []

    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    _, _, winning_id, winning_evidence = scored[0]
    tier_provenance = sorted({e.tier for e in winning_evidence})
    return winning_id, tier_provenance


def _qa_role_token_available(repo_root: str = ".") -> bool:
    """True only if a qa-role GitHub App token is actually provisioned.
    Never checks SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH or any host/personal
    credential -- per CLAUDE.md, "Personal GitHub token is strictly
    off-limits to every agent/harness," with no carve-out for Maintainer
    (spec §5.3a, DECIDE panel defect #2)."""
    import os

    app_dir = os.path.join(repo_root, ".synlynk", "github_apps", "qa")
    return os.path.isdir(app_dir) and bool(os.listdir(app_dir))


# Promotion-boundary guards (spec §5.3a, DECIDE panel re-review 2026-11-24
# defect #2). dry_run staging must make zero external calls; only "promote"
# mode may open a GitHub issue, and only within these guards. The cap and
# the rate limit are deliberately separate knobs: the cap bounds a single
# cycle's blast radius, the window bounds sustained promotion rate across
# many cycles (e.g. a scheduler that fires every few minutes).
_MAX_PROMOTIONS_PER_CYCLE = 5
_MAX_PROMOTIONS_PER_WINDOW = 10
_PROMOTION_WINDOW_SECONDS = 3600

# How long an "attempting" entry with no matching "completed" entry is
# treated as still in flight (DECIDE panel re-review 2026-11-24 round 2,
# condition 3). A crash-then-immediate-retry for the same signature must
# not file a duplicate issue just because the open-issue/audit-log dedupe
# checks can't see an in-progress write.
_PROMOTION_ATTEMPT_LOCK_SECONDS = 300


def _promotion_audit_log_path(repo_root: str) -> str:
    import os

    return os.path.join(repo_root, ".synlynk", "maintainer_promotion_audit.jsonl")


def _read_promotion_audit_log(repo_root: str = ".") -> list[dict]:
    """Append-only JSONL reader (DECIDE panel re-review 2026-11-24, defect
    #2): one JSON object per line, not a single JSON array. A line that
    fails to parse (e.g. a write that was cut off mid-flush) is skipped
    rather than invalidating the whole log."""
    import json

    path = _promotion_audit_log_path(repo_root)
    if not os.path.exists(path):
        return []
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return entries


def _append_promotion_audit_log(repo_root: str, entry: dict) -> None:
    """Append one JSON object as its own line. Never rewrites the file, so
    a crash immediately after this call still leaves every prior line
    intact (DECIDE panel re-review 2026-11-24, defect #2)."""
    import json

    path = _promotion_audit_log_path(repo_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _finding_signature(story: dict) -> str:
    """Stable identity for a finding, used to dedupe promotions across
    cycles and against already-open GitHub issues (DECIDE panel re-review
    2026-11-24, defect #2). story_id already encodes the fingerprint/domain
    that produced the finding, so it's sufficient on its own; title is only
    a fallback for a story with no story_id."""
    return str(story.get("story_id") or story.get("title") or "")


def _open_github_issue_signatures(repo_root: str = ".") -> set:
    """Signatures already filed as open GitHub issues, read from
    maintainer-finding-labeled issues' bodies (each carries a
    `<!-- finding-signature: SIG -->` marker, written by
    _ensure_github_issue_for_story). Best-effort: no qa token, a gh
    failure, or unparseable output all degrade to an empty set rather than
    raising -- dedupe then falls back to the audit log alone."""
    import json
    import re
    import subprocess

    if not _qa_role_token_available(repo_root):
        return set()
    try:
        result = subprocess.run(
            [
                "python3", "bin/synlynk.py", "gh", "--role", "qa", "--",
                "issue", "list", "--label", "maintainer-finding",
                "--state", "open", "--json", "body",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        issues = json.loads(result.stdout or "[]")
    except Exception:
        return set()
    signatures = set()
    for issue in issues:
        match = re.search(r"<!-- finding-signature: (.+?) -->", issue.get("body") or "")
        if match:
            signatures.add(match.group(1))
    return signatures


def _promotions_in_cycle(repo_root: str, cycle_id: str) -> int:
    """Count of external writes attempted this cycle (distinct signatures
    attempted)."""
    return len({
        e.get("signature")
        for e in _read_promotion_audit_log(repo_root)
        if e.get("cycle_id") == cycle_id and e.get("status") in ("attempting", "completed")
    })


def _promotions_in_window(repo_root: str, now: float) -> int:
    """Count distinct signatures attempted within the rolling window."""
    cutoff = now - _PROMOTION_WINDOW_SECONDS
    return len({
        e.get("signature")
        for e in _read_promotion_audit_log(repo_root)
        if e.get("status") in ("attempting", "completed") and e.get("ts", 0) >= cutoff
    })


def _has_in_flight_attempt(repo_root: str, signature: str, now: float) -> bool:
    """True if an "attempting" entry for this signature has no matching
    "completed" entry anywhere in the log, and is still within
    _PROMOTION_ATTEMPT_LOCK_SECONDS of now (DECIDE panel re-review
    2026-11-24 round 2, condition 3)."""
    entries = _read_promotion_audit_log(repo_root)
    completed_signatures = {
        e.get("signature") for e in entries if e.get("status") == "completed"
    }
    if signature in completed_signatures:
        return False
    return any(
        e.get("signature") == signature
        and e.get("status") == "attempting"
        and now - e.get("ts", 0) < _PROMOTION_ATTEMPT_LOCK_SECONDS
        for e in entries
    )


def _ensure_github_issue_for_story(story: dict, repo_root: str = ".", cycle_id: str = "") -> Optional[int]:
    """Open a GitHub issue for a story that has none yet, via the qa-role
    write path (spec §5.3). Returns the issue number on success, or None
    if the story was staged instead of promoted."""
    existing = story.get("github_issue")
    if existing:
        return int(existing)

    if not _qa_role_token_available(repo_root):
        return None

    import time
    now = time.time()

    signature = _finding_signature(story)
    audit_log = _read_promotion_audit_log(repo_root)
    if any(e.get("signature") == signature and e.get("status") == "completed" for e in audit_log):
        return None
    if _has_in_flight_attempt(repo_root, signature, now):
        return None
    if signature in _open_github_issue_signatures(repo_root):
        return None

    if _promotions_in_cycle(repo_root, cycle_id) >= _MAX_PROMOTIONS_PER_CYCLE:
        return None
    if _promotions_in_window(repo_root, now) >= _MAX_PROMOTIONS_PER_WINDOW:
        return None

    _append_promotion_audit_log(repo_root, {
        "cycle_id": cycle_id, "signature": signature, "status": "attempting", "ts": now,
    })

    import re
    import subprocess

    title = story.get("title") or f"Maintainer finding: {story.get('story_id', 'untitled')}"
    body = (story.get("body") or "Filed by Maintainer's autonomous wake cycle.") + (
        f"\n\n<!-- finding-signature: {signature} -->"
    )
    result = subprocess.run(
        [
            "python3", "bin/synlynk.py", "gh", "--role", "qa", "--",
            "issue", "create", "--title", title, "--body", body,
            "--label", "maintainer-finding",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None

    stdout = result.stdout or ""
    match = re.search(r"#(\d+)", stdout) or re.search(r"/issues/(\d+)", stdout)
    issue_number = int(match.group(1)) if match else None

    _append_promotion_audit_log(repo_root, {
        "cycle_id": cycle_id, "signature": signature, "status": "completed",
        "ts": time.time(), "issue_number": issue_number,
    })
    return issue_number


def _notify_slack_on_promotion(proposal: dict, repo_root: str = ".") -> None:
    from datetime import datetime, timezone

    from synlynk import uxcore
    from synlynk.notifiers.slack import _slack_webhook_url, post_to_webhook

    webhook_url = _slack_webhook_url(repo_root=repo_root)
    if not webhook_url:
        return

    event = uxcore.Event(
        actor_id="maintainer",
        action="maintainer_promote",
        params={"proposal_id": proposal.get("proposal_id"), "source": proposal.get("source")},
        timestamp=datetime.now(timezone.utc).isoformat(),
        result={"title": proposal.get("title"), "severity": proposal.get("severity")},
    )
    try:
        post_to_webhook(webhook_url, event)
    except Exception:
        pass


def _run_sentinel_triage_action(mode: str, repo_root: str = ".", cycle_id: str = "") -> dict:
    groups = triage_sentinel_alerts(max_age_days=7)
    proposals = []
    for group in groups:
        severity_label = "critical" if group["severity"] == "CRITICAL" else (
            "high" if group["severity"] == "ERROR" else "normal"
        )
        if severity_label in ("critical", "high"):
            story = {
                "story_id": group["fingerprint"],
                "title": format_triage_issue(group)[:80],
                "github_issue": None,
            }
            if mode == "promote":
                story["github_issue"] = _ensure_github_issue_for_story(story, repo_root=repo_root, cycle_id=cycle_id)
            proposal = {
                "proposal_id": f"maintainer-sentinel-{group['fingerprint']}",
                "source": "maintainer:sentinel_triage",
                "title": f"Sentinel: {group['code']}",
                "severity": severity_label,
                "cluster": "sentinel",
                "stories": [story],
            }
            proposals.append(proposal)
            notify_config = get_action_config("maintainer:sentinel_triage", repo_root=repo_root)
            if severity_label == "critical" or notify_config.get("notify_slack"):
                _notify_slack_on_promotion(proposal, repo_root=repo_root)
    return {"mode": mode, "groups": len(groups), "proposals": proposals}


def _run_backlog_burndown_action(mode: str, repo_root: str = ".", cycle_id: str = "") -> dict:
    result = run_backlog_burndown_sweep(repo_root=repo_root, dry_run=(mode != "promote"))
    sprint = result.get("sprint_staged")
    proposals = []
    if sprint:
        proposal = {
            "proposal_id": f"maintainer-backlog-{sprint['domain']}",
            "source": "maintainer:backlog_burndown",
            "title": sprint["title"],
            "severity": "normal",
            "cluster": sprint["domain"],
            "stories": [],
        }
        proposals.append(proposal)
        notify_config = get_action_config("maintainer:backlog_burndown", repo_root=repo_root)
        if notify_config.get("notify_slack"):
            _notify_slack_on_promotion(proposal, repo_root=repo_root)
    return {"mode": mode, "proposals": proposals, **result}


def _run_mesh_sweep_action(mode: str, repo_root: str = ".", cycle_id: str = "") -> dict:
    exit_code = cmd_maintainer_sweep(repo_root=repo_root, refresh_graph=(mode == "promote"))
    return {"mode": mode, "exit_code": exit_code, "proposals": []}


def _persist_maintainer_proposals(proposals: list[dict], repo_root: str = ".") -> None:
    """Write this cycle's pending proposals to a side-file so page renders
    can read them without re-running the wake cycle."""
    import json
    import time

    path = os.path.join(repo_root, ".synlynk", "maintainer_proposals.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"generated_at": time.time(), "proposals": proposals}, handle, indent=2)


def load_maintainer_proposals(repo_root: str = ".") -> list[dict]:
    """Read the last wake cycle's persisted proposals."""
    import json

    path = os.path.join(repo_root, ".synlynk", "maintainer_proposals.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return list(data.get("proposals") or [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


from synlynk.maintainer_registry import FieldSpec, register_action, get_action_config

register_action(
    role_slug="maintainer",
    name="sentinel_triage",
    default_config={"enabled": True, "mode": "dry_run", "notify_slack": False},
    filter_schema=[FieldSpec(name="exclude_codes", type="list[str]", default=[], label="Exclude alert codes")],
    run_fn=_run_sentinel_triage_action,
)
register_action(
    role_slug="maintainer",
    name="backlog_burndown",
    default_config={"enabled": True, "mode": "dry_run", "notify_slack": False},
    filter_schema=[FieldSpec(name="exclude_labels", type="list[str]", default=[], label="Exclude labels")],
    run_fn=_run_backlog_burndown_action,
)
register_action(
    role_slug="maintainer",
    name="mesh_sweep",
    default_config={"enabled": True, "mode": "dry_run", "notify_slack": False},
    filter_schema=[],
    run_fn=_run_mesh_sweep_action,
)


def run_maintainer_wake_cycle(repo_root: str = ".") -> dict:
    """Run Maintainer's autonomous wake-cycle SOP: sentinel triage, backlog
    burndown, mesh sweep -- mirroring run_tpm_wake_cycle()'s shape (spec §5.1).
    Each registered action runs in dry_run (stage, no side effects) or
    promote (real side effects) mode per its settings-registry config."""
    import time
    import uuid

    from synlynk.maintainer_registry import registered_actions

    cycle_id = f"cycle-{int(time.time())}-{uuid.uuid4().hex[:8]}"

    results: dict = {}
    for action_id, action in registered_actions(role_slug="maintainer").items():
        config = get_action_config(action_id, repo_root=repo_root)
        if not config.get("enabled", True):
            results[action.name] = {"skipped": True}
            continue
        mode = config.get("mode", "dry_run")
        outcome = action.run_fn(mode=mode, repo_root=repo_root, cycle_id=cycle_id)
        results[action.name] = outcome

    all_proposals = []
    for action_name, outcome in results.items():
        for proposal in (outcome.get("proposals") or []):
            all_proposals.append({**proposal, "action": action_name})
    _persist_maintainer_proposals(all_proposals, repo_root=repo_root)

    return results


