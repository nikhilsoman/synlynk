"""HarnessAdapter Protocol and shared value types (gh:#1924)."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

from synlynk.harness_adapters.request import DispatchRequest


class FailureKind(Enum):
    AUTH_EXPIRED = "auth_expired"
    QUOTA_EXHAUSTED = "quota_exhausted"
    SANDBOX_DENIED = "sandbox_denied"


@dataclass
class DispatchEvent:
    raw_text: str
    failure: Optional[FailureKind]
    lifecycle_events: tuple = ()
    compatibility_evidence: Optional[dict] = None


class HarnessAdapter(Protocol):
    def build_cmd(self, request: DispatchRequest) -> list:
        ...

    def parse_output(self, raw_text: str) -> DispatchEvent:
        ...

    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        ...

    def classify_failure(
        self, exit_code: int, stderr: str, raw_text: str
    ) -> Optional[FailureKind]:
        ...

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        ...
