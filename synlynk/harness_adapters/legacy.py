"""Adapter that delegates to today's dispatch.py branching, unchanged.

Used for every harness not yet ported to a real adapter (see migration order
in docs/superpowers/specs/2026-10-03-harness-adapter-dispatch-decomposition-design.md).
Deleted once all harnesses have a real adapter (Task 12).
"""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class LegacyAdapter:
    def __init__(self, agent: str):
        self.agent = agent

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        return _dispatch_flags_for_agent(self.agent)

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output
        return DispatchEvent(raw_text=raw_text, failure=None,
                             lifecycle_events=parse_output(raw_text),
                             compatibility_evidence=compatibility_evidence(raw_text))

    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk.dispatch import _permissions_to_flags

        return _permissions_to_flags(self.agent, permissions, read_only=read_only)

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, self.agent)
