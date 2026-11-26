"""Shared Proposal schema (DECIDE panel re-review 2026-11-24, defect #4).

Every proposal-producing source -- TPM's story rows (from the `stories`
table) and Task 6's maintainer wake-cycle actions (from
`load_maintainer_proposals()`) -- must conform to this shape before
`synlynk/roadmap_studio.py`'s `normalize_proposal_for_studio` hands it to
`studio_data()`, which is what the browser's Proposal Studio JS actually
reads. This module is the one place that shape is defined and checked,
instead of leaving conformance as an implicit convention between
`normalize_proposal_for_studio`'s key-defaulting and whatever each
producer happens to emit -- the gap the DECIDE panel's re-review flagged:
a producer could pass a garbage `severity` or a non-list
`tier_provenance` and `normalize_proposal_for_studio`'s `str(...)`/
`list(...)` coercions would let it through silently malformed.
"""
from typing import Optional

REQUIRED_STRING_FIELDS = ("story_id", "title", "source", "severity")

# The only three values synlynk/viz/roadmap_studio.py's `draw()` and
# `cardHtml()` JS actually branch on (`story.severity === 'critical' ||
# story.severity === 'high'` routes a card into the "Needs attention now"
# lane; anything else renders as a normal card). A fourth value would
# silently never route into the lane, which is exactly the drift this
# validator exists to catch.
VALID_SEVERITIES = {"normal", "high", "critical"}


def validate_proposal(proposal: dict) -> Optional[str]:
    """Return None if `proposal` conforms to the shared Proposal schema,
    else a short, specific validation-error string. Mirrors the
    validate-or-fallback shape Tasks 1/2 use for taxonomy/domain-pack
    schemas: callers degrade on a non-None return rather than raising."""
    for field in REQUIRED_STRING_FIELDS:
        value = proposal.get(field)
        if not isinstance(value, str) or not value:
            return f"'{field}' must be a non-empty string, got {value!r}"

    if proposal["severity"] not in VALID_SEVERITIES:
        return f"'severity' must be one of {sorted(VALID_SEVERITIES)}, got {proposal['severity']!r}"

    github_issue = proposal.get("github_issue")
    if github_issue is not None and not isinstance(github_issue, int):
        return f"'github_issue' must be an int or None, got {github_issue!r}"

    tier_provenance = proposal.get("tier_provenance")
    if not isinstance(tier_provenance, list) or not all(isinstance(x, str) for x in tier_provenance):
        return f"'tier_provenance' must be a list of strings, got {tier_provenance!r}"

    return None
