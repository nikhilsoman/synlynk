"""Muse harness adapter for the existing experimental dispatch path."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class MuseAdapter:
    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        skip_perms = getattr(request, "skip_permissions", False)
        flags = _dispatch_flags_for_agent("muse", skip_permissions=skip_perms)
        if "--approval-mode" in flags:
            idx = flags.index("--approval-mode")
            if idx + 1 == len(flags) or flags[idx + 1].startswith("--"):
                flags.insert(idx + 1, "never")
        elif "--approval-mode" not in flags and "--yolo" not in flags:
            flags += ["--approval-mode", "never"]
        flags += self.translate_permissions(
            request.permissions,
            request.read_only,
            skip_permissions=skip_perms,
        )
        return flags

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
            failure=self._classify(raw_text),
            lifecycle_events=parse_output(raw_text),
            compatibility_evidence=compatibility_evidence(raw_text),
        )

    def classify_failure(
        self, exit_code: int, stderr: str, raw_text: str
    ) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "not logged in" in lowered or "missing api key" in lowered or "login required" in lowered:
            return FailureKind.AUTH_EXPIRED
        if "quota exceeded" in lowered or "rate limit" in lowered or "429" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        if "sandbox" in lowered and "denied" in lowered:
            return FailureKind.SANDBOX_DENIED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "muse")
