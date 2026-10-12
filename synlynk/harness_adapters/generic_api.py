"""HarnessAdapter wrapper for the OpenRouter gateway harness (gh:#2076)."""

from typing import Optional

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class GenericAPIAdapter:
    """Protocol-shaped adapter for OpenAI-compatible gateway dispatch.

    The live legacy ``dispatch_agent`` path invokes the gateway through the
    ``openrouter`` harness baseline. This adapter keeps the same behavior
    available to the adapter registry and future pipeline callers.
    """

    def build_cmd(self, request: DispatchRequest) -> list:
        baseline = HARNESS_CAPABILITY_BASELINES["openrouter"]
        command = [baseline["cli"], *baseline["non_interactive_flags"]]
        if request.model:
            command.extend(["--model", request.model])
        command.extend([baseline["prompt_flag"], request.task])
        return command

    def parse_output(self, raw_text: str) -> DispatchEvent:
        from synlynk.lifecycle import compatibility_evidence, parse_output

        return DispatchEvent(
            raw_text=raw_text,
            failure=None,
            lifecycle_events=parse_output(raw_text),
            compatibility_evidence=compatibility_evidence(raw_text),
        )

    def translate_permissions(
        self, permissions: list, read_only: bool, skip_permissions: bool = False
    ) -> list:
        return []

    def classify_failure(
        self, exit_code: int, stderr: str, raw_text: str
    ) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        return "anthropic/claude-sonnet-5"
