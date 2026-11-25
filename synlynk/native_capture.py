"""Native-session transcript capture: reader, de-dup, bucketing, ledger upsert."""
import json
from dataclasses import dataclass, field


class TranscriptFormatError(Exception):
    """The transcript's usage shape no longer matches what this reader understands."""


@dataclass
class Record:
    message_id: str
    model: str
    day: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


@dataclass
class Bucket:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    messages: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    records: list
    pr_links: list
    consumed: int


_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def parse_chunk(data: bytes, known_ids: set) -> ParseResult:
    end = data.rfind(b"\n") + 1  # only complete lines
    seen = set(known_ids)       # never mutate the caller's set
    records, pr_links = [], []
    for raw in data[:end].splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue  # a corrupt line is skipped, never counted
        kind = obj.get("type")
        if kind == "pr-link" and isinstance(obj.get("prNumber"), int):
            pr_links.append((obj["prNumber"], obj.get("timestamp")))
            continue
        if kind != "assistant":
            continue
        msg = obj.get("message") or {}
        model = msg.get("model")
        if not model or model == "<synthetic>":
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict) or not all(k in usage for k in _USAGE_KEYS):
            raise TranscriptFormatError(f"usage shape changed for message {msg.get('id')!r}")
        mid = msg.get("id")
        if not mid:
            raise TranscriptFormatError("assistant record without message.id")
        if mid in seen:
            continue
        seen.add(mid)
        ts = obj.get("timestamp") or ""
        records.append(Record(mid, model, ts[:10], usage["input_tokens"], usage["output_tokens"],
                              usage["cache_creation_input_tokens"], usage["cache_read_input_tokens"]))
    return ParseResult(records, pr_links, end)


def bucketize(records) -> dict:
    out: dict = {}
    for r in records:
        b = out.setdefault((r.model, r.day), Bucket())
        b.input_tokens += r.input_tokens
        b.output_tokens += r.output_tokens
        b.cache_creation_tokens += r.cache_creation_tokens
        b.cache_read_tokens += r.cache_read_tokens
        b.messages[r.message_id] = [r.input_tokens, r.output_tokens, r.cache_read_tokens, r.cache_creation_tokens]
    return out
