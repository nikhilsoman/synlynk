"""Local (aider/oMLX) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind, PermissionEnforcementError
from synlynk.harness_adapters.request import DispatchRequest


# Hermes is an explicit local-only catalog tier.  It is intentionally not
# added to dispatch's global fast/pro/reasoning tiers: selecting Hermes is a
# local adapter concern and must not make remote harnesses accept a tier they
# cannot resolve.
HERMES_TIER = "hermes"


class LocalAdapter:
    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        if permissions:
            raise PermissionEnforcementError(
                f"local (aider) has no mechanism to enforce permissions {sorted(permissions)}; "
                "aider's declared CLI flags include no read-only/file-scope restriction. "
                "Refusing to dispatch rather than silently granting full read/write access."
            )
        return []

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        return _dispatch_flags_for_agent("local")

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=None)

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        if tier == HERMES_TIER:
            return resolve_tier_model(HERMES_TIER, "local")
        return resolve_tier_model(tier, "local")
