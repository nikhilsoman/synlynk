"""Muse harness adapter for the existing experimental dispatch path."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class MuseAdapter:
    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        return _dispatch_flags_for_agent("muse")

    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        from synlynk.dispatch import _permissions_to_flags

        return _permissions_to_flags(
            "muse", permissions, read_only=read_only, skip_permissions=skip_permissions
        )

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output

        return DispatchEvent(
            raw_text=raw_text,
            failure=None,
            lifecycle_events=parse_output(raw_text),
            compatibility_evidence=compatibility_evidence(raw_text),
        )

    def classify_failure(
        self, exit_code: int, stderr: str, raw_text: str
    ) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "muse")
