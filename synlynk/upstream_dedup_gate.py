"""Dedup/trust gate required (spec §3a.4) before any upstream GitHub
feature-request flow or remote Capability Registry ingestion ships.
References gh:#2139's lesson: a stale "closed via PR" claim in project
memory/roadmap text turned out to be wrong (issue was actually still open)
because nothing re-checked upstream state before treating it as resolved.

This module provides only the dedup check itself — the issue-filing and
remote-manifest-ingestion flows that will call it remain out of scope for
this plan (spec §7); they are a follow-on once this gate exists and is
wired in.
"""


def _search_issues(query: str) -> list:
    """Search this repo's GitHub issues for `query`. Real implementation
    delegates to the existing mcp__plugin_github_github__search_issues tool
    or `gh issue list --search`, whichever the caller's environment provides
    — left as an injection point so tests can stub it without a live GitHub
    call. Not implemented as a direct network call here, by design: this
    module must stay testable without GitHub credentials.
    """
    raise NotImplementedError(
        "wire this to a real search (gh issue list --search <query> --json number,title,state, "
        "or the github MCP server's search_issues tool) in the caller that has that access"
    )


def check_dedup(proposed_title_or_summary: str) -> dict:
    """Return {'has_candidate_duplicate': bool, 'candidates': [...]} for
    open issues that might already cover `proposed_title_or_summary`.

    Only open issues count as candidate duplicates — a closed issue is not
    evidence the work is done (gh:#2139's exact failure mode).
    """
    results = _search_issues(proposed_title_or_summary)
    open_candidates = [r for r in results if r.get("state") == "open"]
    return {
        "has_candidate_duplicate": bool(open_candidates),
        "candidates": open_candidates,
    }
