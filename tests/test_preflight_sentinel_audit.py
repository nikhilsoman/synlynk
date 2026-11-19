import re

_EXPECTED_SENTINELS = {
    "HARNESS_PREFLIGHT_FAIL",
    "LOCAL_CAPABILITY_UNAVAILABLE",
    "LOCAL_ORBSTACK_UNAVAILABLE",
    "INSTRUCTION_FILE_MISSING",
    "MCP_SERVER_MISSING",
    "CAPACITY_EXCEEDED_INPUT",
    "CAPACITY_EXCEEDED_OUTPUT",
    "GOVERNS_LINKAGE_MISSING",
    "HARNESS_MANIFEST_REVALIDATION_FAILED",  # added by Task 7
}


def test_every_preflight_sentinel_is_cataloged():
    with open("synlynk/dispatch.py") as f:
        text = f.read()
    start = text.index("def _dispatch_capability_preflight")
    end = text.index("\ndef dispatch_agent")  # covers both preflight functions
    body = text[start:end]
    found = set(re.findall(r'"sentinel":\s*"([A-Z_]+)"', body))
    uncataloged = found - _EXPECTED_SENTINELS
    assert not uncataloged, f"Uncataloged sentinel(s) found: {uncataloged} — add to _EXPECTED_SENTINELS if intentional, or fix the site"
