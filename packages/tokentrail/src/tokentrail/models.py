"""Data models and protocols for tokentrail."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Protocol, Any, Dict


@dataclass(frozen=True)
class TokenUsage:
    __slots__ = ("input_tokens", "output_tokens", "cache_write_tokens", "cache_read_tokens")

    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_write_tokens + self.cache_read_tokens


@dataclass(frozen=True)
class MessageTurn:
    __slots__ = ("message_id", "model", "timestamp", "usage")

    message_id: str
    model: str
    timestamp: Optional[str]
    usage: TokenUsage


@dataclass
class SessionLedger:
    session_id: str
    harness: str
    source_path: str
    turns: List[MessageTurn] = field(default_factory=list)

    @property
    def total_usage(self) -> TokenUsage:
        in_t = sum(t.usage.input_tokens for t in self.turns)
        out_t = sum(t.usage.output_tokens for t in self.turns)
        cw_t = sum(t.usage.cache_write_tokens for t in self.turns)
        cr_t = sum(t.usage.cache_read_tokens for t in self.turns)
        return TokenUsage(in_t, out_t, cw_t, cr_t)


class TranscriptAdapter(Protocol):
    """Protocol for transcript and event stream extractors."""

    def detect(self, source_path: str) -> bool:
        """Return True if this adapter can parse the given source."""
        ...

    def parse(self, source_path: str) -> SessionLedger:
        """Parse the source and return a deduplicated SessionLedger."""
        ...
