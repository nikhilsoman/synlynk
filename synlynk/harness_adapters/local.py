"""Local (aider/oMLX) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind, PermissionEnforcementError
from synlynk.harness_adapters.request import DispatchRequest


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

        flags = _dispatch_flags_for_agent(
            "local",
            skip_permissions=getattr(request, "skip_permissions", False),
            local_model=request.model,
        )
        return flags + self.translate_permissions(
            request.permissions,
            request.read_only,
            skip_permissions=getattr(request, "skip_permissions", False),
        )

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output

        return DispatchEvent(
            raw_text=raw_text,
            failure=self._classify(raw_text),
            lifecycle_events=parse_output(raw_text),
            compatibility_evidence=compatibility_evidence(raw_text),
        )

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if any(marker in lowered for marker in ("401", "unauthorized", "invalid api key", "authentication failed")):
            return FailureKind.AUTH_EXPIRED
        if "model" in lowered and any(marker in lowered for marker in ("not found", "unavailable", "does not exist")):
            return FailureKind.MODEL_UNAVAILABLE
        if any(marker in lowered for marker in ("inventory unavailable", "omlx is unavailable", "connection refused")):
            return FailureKind.INVENTORY_UNAVAILABLE
        if any(marker in lowered for marker in ("timed out", "timeout")):
            return FailureKind.TIMEOUT
        if any(marker in lowered for marker in ("malformed response", "invalid json", "json decode")):
            return FailureKind.MALFORMED_RESPONSE
        if any(marker in lowered for marker in ("no changes made", "no files were changed")):
            return FailureKind.NO_OP
        if "aider" in lowered and any(marker in lowered for marker in ("error", "failed", "traceback")):
            return FailureKind.AIDER_FAILURE
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "local")
