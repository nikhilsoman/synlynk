from synlynk.dispatch_rejections import (
    HARNESS_DISPATCH_REJECTION_TAXONOMY,
    discover_dispatch_rejection_sentinels,
)


def test_every_preflight_sentinel_is_cataloged():
    with open("synlynk/dispatch.py") as f:
        text = f.read()
    start = text.index("def _dispatch_capability_preflight")
    end = text.index("\ndef dispatch_agent")  # covers both preflight functions
    body = text[start:end]
    found = discover_dispatch_rejection_sentinels(body)
    uncataloged = found - set(HARNESS_DISPATCH_REJECTION_TAXONOMY)
    assert not uncataloged, (
        f"Uncataloged sentinel(s) found: {uncataloged} — add them to "
        "HARNESS_DISPATCH_REJECTION_TAXONOMY if intentional, or fix the site"
    )
