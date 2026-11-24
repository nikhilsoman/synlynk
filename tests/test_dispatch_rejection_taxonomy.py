import ast

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.dispatch_rejections import (
    HARNESS_DISPATCH_REJECTION_TAXONOMY,
    discover_dispatch_rejection_sentinels,
    validate_headless_contract_parity,
)


def test_every_dispatch_rejection_site_has_a_taxonomy_entry():
    source = open("synlynk/dispatch.py", encoding="utf-8").read()

    found = discover_dispatch_rejection_sentinels(source)

    assert found == set(HARNESS_DISPATCH_REJECTION_TAXONOMY)
    for sentinel, entry in HARNESS_DISPATCH_REJECTION_TAXONOMY.items():
        assert entry.category
        assert entry.remediation
        assert entry.modes == ("interactive", "headless")


def test_rejection_discovery_is_limited_to_preflight_functions():
    source = open("synlynk/dispatch.py", encoding="utf-8").read()
    tree = ast.parse(source)

    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_dispatch_capability_preflight", "_preflight_dispatch"}
    }
    assert names == {"_dispatch_capability_preflight", "_preflight_dispatch"}


def test_all_harnesses_have_interactive_and_headless_dispatch_contracts():
    errors = validate_headless_contract_parity(HARNESS_CAPABILITY_BASELINES)

    assert errors == []
