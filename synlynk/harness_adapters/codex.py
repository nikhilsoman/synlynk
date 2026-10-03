"""Codex HarnessAdapter -- pilot harness for the strangler migration (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest

_CODEX_NETWORK_PERMISSION = "network:*"


class CodexAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk.dispatch import _codex_network_flags

        has_write = any((perm or "").startswith("write:") for perm in (permissions or []))
        flags = []
        if read_only and _CODEX_NETWORK_PERMISSION in (permissions or []) and not has_write:
            flags = ["-s", "workspace-write"]
        elif has_write:
            flags = ["-s", "workspace-write"]
        elif read_only or (not has_write and _CODEX_NETWORK_PERMISSION not in (permissions or [])):
            flags = ["-s", "read-only"]
        if _CODEX_NETWORK_PERMISSION in (permissions or []):
            flags += _codex_network_flags(read_only=read_only and not has_write)
        return flags

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("codex")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=self._classify(raw_text))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "--ask-for-approval" in lowered and ("unrecognized" in lowered or "unknown option" in lowered):
            return FailureKind.SANDBOX_DENIED
        if "not signed in" in lowered or "please log in" in lowered:
            return FailureKind.AUTH_EXPIRED
        if "402" in lowered or "quota exceeded" in lowered or "rate limit" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        import os
        from pathlib import Path
        from synlynk.models import resolve_tier_model
        from synlynk.probe import _read_toml_string_value

        try:
            codex_home = Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
            configured = _read_toml_string_value(str(codex_home / "config.toml"), "model")
            if configured:
                return configured
        except Exception:
            pass
        return resolve_tier_model(tier, "codex")
