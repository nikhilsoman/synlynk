"""Claude HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class ClaudeAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk._constants import _PERMISSION_TO_TOOL_MAP

        tools = []
        for perm in permissions or []:
            tools.extend(_PERMISSION_TO_TOOL_MAP.get(perm, []))
            if perm.startswith("write:") and perm not in _PERMISSION_TO_TOOL_MAP:
                tools.extend(("Edit", "Write", "MultiEdit"))
        tools = sorted(set(tools))
        if not tools:
            return []
        return ["--allowedTools", ",".join(tools)]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("claude")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output

        return DispatchEvent(raw_text=raw_text, failure=None,
                             lifecycle_events=parse_output(raw_text),
                             compatibility_evidence=compatibility_evidence(raw_text))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "claude")
