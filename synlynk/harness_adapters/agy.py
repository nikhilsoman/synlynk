"""Agy (Gemini) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class AgyAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        if not permissions:
            return []
        if set(permissions) <= {"read:*"}:
            return ["--mode", "plan"]
        return ["--sandbox"]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("agy")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output

        return DispatchEvent(raw_text=raw_text, failure=self._classify(raw_text),
                             lifecycle_events=parse_output(raw_text),
                             compatibility_evidence=compatibility_evidence(raw_text))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "resource_exhausted" in lowered or "429" in lowered or "credits balance" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        if "timeout waiting for response" in lowered:
            return FailureKind.AUTH_EXPIRED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "agy")
