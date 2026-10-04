"""Confirms gh:#1925 part 1's consolidation: local.py and grok.py both raise
the SAME PermissionEnforcementError class (from base.py), not two separate
same-named classes.
"""


def test_local_and_grok_adapters_share_permission_enforcement_error_class():
    from synlynk.harness_adapters import base, grok, local

    assert local.PermissionEnforcementError is base.PermissionEnforcementError
    assert grok.PermissionEnforcementError is base.PermissionEnforcementError


def test_local_and_grok_permission_errors_are_interchangeable_in_except_blocks():
    from synlynk.harness_adapters.grok import GrokAdapter
    from synlynk.harness_adapters.local import PermissionEnforcementError as LocalError

    adapter = GrokAdapter()
    try:
        adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=False)
        assert False, "expected PermissionEnforcementError"
    except LocalError:
        pass  # catching via the OTHER module's imported name must work — same class object
