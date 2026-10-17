"""HarnessAdapter Protocol wrapper for the openrouter / generic API gateway harness (gh:#2076)."""

from typing import Optional

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.harness_adapters.base import DispatchEvent, FailureKind, PermissionEnforcementError
from synlynk.harness_adapters.request import DispatchRequest


class GenericAPIAdapter:
    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        if permissions and not skip_permissions:
            raise PermissionEnforcementError(
                f"openrouter has no mechanism to enforce permissions {sorted(permissions)}. "
                "Refusing to dispatch rather than silently granting unverified host permissions."
            )
        return []

    def build_cmd(self, request: DispatchRequest) -> list:
        baseline = HARNESS_CAPABILITY_BASELINES["openrouter"]
        cmd = [baseline["cli"]] + list(baseline["non_interactive_flags"])
        if getattr(request, "model", None):
            cmd += ["--model", request.model]
        if getattr(request, "task", None):
            cmd += ["--prompt", request.task]
        return cmd

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
        if exit_code == 0:
            return None
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if any(marker in lowered for marker in ("401", "unauthorized", "invalid api key", "authentication failed")):
            return FailureKind.AUTH_EXPIRED
        if any(marker in lowered for marker in ("quota exceeded", "rate limit", "429", "insufficient credits")):
            return FailureKind.QUOTA_EXHAUSTED
        if "model" in lowered and any(marker in lowered for marker in ("not found", "unavailable", "does not exist")):
            return FailureKind.MODEL_UNAVAILABLE
        if any(marker in lowered for marker in ("timed out", "timeout")):
            return FailureKind.TIMEOUT
        if any(marker in lowered for marker in ("malformed response", "invalid json", "json decode")):
            return FailureKind.MALFORMED_RESPONSE
        if any(marker in lowered for marker in ("no changes made", "no files were changed")):
            return FailureKind.NO_OP
        return None

    def resolve_model(self, tier: str, effort: Optional[str] = None) -> str:
        from synlynk.models import resolve_tier_model

        try:
            return resolve_tier_model(tier, "openrouter")
        except Exception:
            baseline = HARNESS_CAPABILITY_BASELINES.get("openrouter", {})
            return baseline.get("default_model", "anthropic/claude-sonnet-5")
