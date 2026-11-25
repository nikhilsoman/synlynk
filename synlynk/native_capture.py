"""Native-session transcript capture: reader, de-dup, bucketing, ledger upsert."""
import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from synlynk import pricing

CHUNK_BYTES = 1 << 20
ANCHOR_BYTES = 4096
_GH_PR_RE = re.compile(r"\bgh\b[^|;&\n]*?\bpr\s+(review|merge|create|checks|view|comment|update-branch|diff|ready)\b[^|;&\n]*?\b(\d{2,6})\b")


class TranscriptFormatError(Exception):
    """The transcript's usage shape no longer matches what this reader understands."""


class TranscriptMissingError(Exception):
    """The transcript path does not exist (rotated, deleted, or never written)."""


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
    tool_pr_links: list = field(default_factory=list)


_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def parse_chunk(data: bytes, known_ids: set) -> ParseResult:
    end = data.rfind(b"\n") + 1  # only complete lines
    seen = set(known_ids)       # never mutate the caller's set
    records, pr_links, tool_pr_links = [], [], []
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

        # Scan tool use for GitHub PR commands
        ts = obj.get("timestamp") or ""
        content = msg.get("content") or []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use" and item.get("name") == "Bash":
                    inp = item.get("input") or {}
                    cmd = inp.get("command") or ""
                    if isinstance(cmd, str):
                        for m in _GH_PR_RE.finditer(cmd):
                            verb, num_str = m.group(1), m.group(2)
                            role = "reviewer" if verb in ("review", "merge") else ("implementer" if verb == "create" else "implementer")
                            tool_pr_links.append((int(num_str), ts, role))

        if mid in seen:
            continue
        seen.add(mid)
        records.append(Record(mid, model, ts[:10], usage["input_tokens"], usage["output_tokens"],
                              usage["cache_creation_input_tokens"], usage["cache_read_input_tokens"]))
    return ParseResult(records, pr_links, end, tool_pr_links)


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


def _session_row(conn, session_id):
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, title, status, opened_at) VALUES (?, ?, 'native', datetime('now'))",
        (session_id, "native-capture"),
    )


def _anchor(path: Path, offset: int) -> str:
    """sha1 of the first and last ANCHOR_BYTES before `offset`; detects a rewritten transcript."""
    if offset <= 0:
        return ""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(min(ANCHOR_BYTES, offset)))
        f.seek(max(0, offset - ANCHOR_BYTES))
        h.update(f.read(min(ANCHOR_BYTES, offset)))
    return h.hexdigest()


def _known_ids(conn, session_id) -> set:
    ids: set = set()
    for (blob,) in conn.execute(
        "SELECT turn_usage_json FROM cost_entries WHERE cost_source='transcript_derived' AND session_id=?",
        (session_id,),
    ):
        ids.update(json.loads(blob or "{}").get("messages", {}))
    return ids


def _row_cost(model, inp, out, cr, cc):
    cost = pricing.price_usd(model, inp, out, cr, cc)
    return cost, ("unpriced" if cost is None else "transcript_priced")


def _apply_bucket(conn, session_id, model, day, b):
    existing = conn.execute(
        "SELECT id, input_tokens, output_tokens, cache_read_tokens, turn_usage_json FROM cost_entries "
        "WHERE cost_source='transcript_derived' AND session_id=? AND model=? AND substr(session_date,1,10)=?",
        (session_id, model, day),
    ).fetchone()
    inp, out, cr, cc = b.input_tokens, b.output_tokens, b.cache_read_tokens, b.cache_creation_tokens
    msgs = dict(b.messages)
    if existing:
        _id, e_in, e_out, e_cr, e_json = existing
        prev = json.loads(e_json or "{}")
        inp += e_in or 0
        out += e_out or 0
        cr += e_cr or 0
        cc += prev.get("cache_creation_total", 0)
        msgs = {**prev.get("messages", {}), **msgs}
    cost, basis = _row_cost(model, inp, out, cr, cc)
    blob = json.dumps({"cache_creation_total": cc, "messages": msgs, "payment_mode_provisional": True})
    if existing:
        conn.execute(
            "UPDATE cost_entries SET input_tokens=?, output_tokens=?, cache_read_tokens=?, total_cost_usd=?, "
            "estimate_basis=?, turn_usage_json=? WHERE id=?",
            (inp, out, cr, cost, basis, blob, existing[0]),
        )
    else:
        conn.execute(
            "INSERT INTO cost_entries (session_date, agent, harness, model, input_tokens, output_tokens, cache_read_tokens, "
            "total_cost_usd, cost_source, estimate_basis, session_id, turn_usage_json, payment_mode) "
            "VALUES (?, 'claude', 'claude', ?, ?, ?, ?, ?, 'transcript_derived', ?, ?, ?, 'subscription')",
            (day, model, inp, out, cr, cost, basis, session_id, blob),
        )


def _log_error(msg: str) -> None:
    path = Path(os.path.expanduser("~/.synlynk/native_capture_errors.log"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(msg.replace("\n", " ")[:500] + "\n")  # ids and counts only, never message text
    except OSError:
        pass


def capture(conn, session_id: str, transcript, *, final: bool = False, budget_s=None) -> dict:
    path = Path(transcript)
    if not path.exists():
        raise TranscriptMissingError(str(path))
    started = time.monotonic()
    size = path.stat().st_size
    cur = conn.execute(
        "SELECT byte_offset, anchor FROM native_capture_cursor WHERE session_id=?", (session_id,)
    ).fetchone()
    has_rows = conn.execute(
        "SELECT 1 FROM cost_entries WHERE cost_source='transcript_derived' AND session_id=? LIMIT 1", (session_id,)
    ).fetchone()
    rescan = (cur is None and bool(has_rows)) or (
        cur is not None and (size < cur[0] or _anchor(path, cur[0]) != cur[1])
    )
    if cur is not None and not rescan and size == cur[0]:
        if final:
            with conn:
                conn.execute("UPDATE native_capture_cursor SET final=1 WHERE session_id=?", (session_id,))
        return {"records": 0, "complete": True, "rescan": False}   # nothing new: no id load, no parse
    offset = 0 if (rescan or cur is None) else cur[0]
    with conn:
        _session_row(conn, session_id)
        if rescan:
            conn.execute("DELETE FROM cost_entries WHERE cost_source='transcript_derived' AND session_id=?", (session_id,))
            conn.execute("DELETE FROM native_capture_cursor WHERE session_id=?", (session_id,))
    known = _known_ids(conn, session_id)
    total = 0
    complete = False
    while True:
        n = CHUNK_BYTES
        while True:                               # grow the read until it holds a complete line
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read(n)
            res = parse_chunk(data, known)
            if res.consumed or len(data) < n:
                break
            n *= 2
        if not data or res.consumed == 0:
            complete = True                       # EOF, or only a partial trailing line remains
            break
        buckets = bucketize(res.records)
        new_offset = offset + res.consumed
        with conn:
            for (model, day), b in buckets.items():
                _apply_bucket(conn, session_id, model, day, b)
            for pr, ts in res.pr_links:
                conn.execute(
                    "INSERT OR IGNORE INTO session_pr_links (session_id, pr_number, role, first_seen_ts, source) "
                    "VALUES (?, ?, 'implementer', ?, 'pr-link')", (session_id, pr, ts))
            for pr, ts, role in res.tool_pr_links:
                conn.execute(
                    "INSERT OR IGNORE INTO session_pr_links (session_id, pr_number, role, first_seen_ts, source) "
                    "VALUES (?, ?, ?, ?, 'tool-use')", (session_id, pr, role, ts))
            conn.execute(
                "INSERT INTO native_capture_cursor (session_id, transcript_path, byte_offset, anchor, final, updated_at) "
                "VALUES (?, ?, ?, ?, 0, datetime('now')) ON CONFLICT(session_id) DO UPDATE SET "
                "transcript_path=excluded.transcript_path, byte_offset=excluded.byte_offset, "
                "anchor=excluded.anchor, updated_at=excluded.updated_at",
                (session_id, str(path), new_offset, _anchor(path, new_offset)))
        known.update(r.message_id for r in res.records)
        total += len(res.records)
        offset = new_offset
        if budget_s is not None and time.monotonic() - started > budget_s and offset < path.stat().st_size:
            break                                 # progress is saved; the sweep finishes the rest
    if complete and final:
        with conn:
            conn.execute("UPDATE native_capture_cursor SET final=1 WHERE session_id=?", (session_id,))
    return {"records": total, "complete": complete, "rescan": rescan}


def is_dispatch_slug(slug: str) -> bool:
    # Dispatch jobs run in <repo>/worktrees/job-<id>; Claude-managed interactive worktrees are
    # <repo>/.claude/worktrees/<name> (slug contains "claude-worktrees-") and are captured.
    return "worktrees-job-" in slug and "claude-worktrees-" not in slug


def _has_job_rows(conn, session_id) -> bool:
    return bool(conn.execute("SELECT 1 FROM cost_entries WHERE session_id=? AND job_id IS NOT NULL LIMIT 1", (session_id,)).fetchone())


def sweep(conn, projects_dir=None) -> dict:
    base = Path(projects_dir or os.path.expanduser("~/.claude/projects"))
    out = {"captured": 0, "skipped_dispatch": 0, "errors": 0}
    for proj in sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []:
        dispatch_dir = is_dispatch_slug(proj.name)
        for t in sorted(proj.glob("*.jsonl")):
            sid = t.stem
            if dispatch_dir or _has_job_rows(conn, sid):
                out["skipped_dispatch"] += 1
                continue
            cur = conn.execute("SELECT byte_offset, final FROM native_capture_cursor WHERE session_id=?", (sid,)).fetchone()
            if cur and cur[1] and t.stat().st_size == cur[0]:
                continue
            try:
                capture(conn, sid, t)
                out["captured"] += 1
            except (TranscriptFormatError, TranscriptMissingError, sqlite3.Error) as exc:
                out["errors"] += 1
                _log_error(f"sweep session={sid}: {type(exc).__name__}")
    return out


def reconcile(conn) -> list:
    return [r[0] for r in conn.execute(
        "SELECT session_id FROM cost_entries WHERE session_id IS NOT NULL "
        "GROUP BY session_id HAVING SUM(cost_source='transcript_derived')>0 AND SUM(job_id IS NOT NULL)>0 ORDER BY session_id")]


def link_session(conn, session_id, pr_number, *, role="implementer", source="manual"):
    with conn:
        conn.execute("INSERT OR IGNORE INTO session_pr_links (session_id, pr_number, role, first_seen_ts, source) "
                     "VALUES (?, ?, ?, datetime('now'), ?)", (session_id, pr_number, role, source))


def linked_session_identity(conn, pr_number, role):
    row = conn.execute(
        "SELECT ce.harness, ce.model FROM session_pr_links l JOIN cost_entries_effective ce "
        "ON ce.session_id = l.session_id AND ce.cost_source='transcript_derived' "
        "WHERE l.pr_number=? AND l.role=? ORDER BY ce.output_tokens DESC LIMIT 1", (pr_number, role)).fetchone()
    return tuple(row) if row else None


