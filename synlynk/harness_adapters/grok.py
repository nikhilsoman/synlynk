"""Grok HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class GrokAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        permission_set = {perm for perm in (permissions or []) if perm}
        if not permission_set:
            return []
        return ["--always-approve", "--permission-mode", "bypassPermissions"]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("grok")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output
        return DispatchEvent(raw_text=raw_text, failure=self._classify(raw_text, exit_code=0),
                             lifecycle_events=parse_output(raw_text),
                             compatibility_evidence=compatibility_evidence(raw_text))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}", exit_code=exit_code)

    @staticmethod
    def _classify(text: str, exit_code: int) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "not signed in" in lowered or "login --device-code" in lowered:
            return FailureKind.AUTH_EXPIRED
        if "402" in lowered or "balance exhausted" in lowered or "payment required" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        if "permission denied" in lowered and "bash" in lowered:
            return FailureKind.SANDBOX_DENIED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "grok")
