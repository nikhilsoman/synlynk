"""Repeatable state.db WAL soak: 20–50 concurrent synthetic job/state writers.

Simulates a fleet of daemon/CLI workers updating daemon_jobs, cost_entries, and
stories on an isolated temporary ledger. Production ~/.synlynk state.db is never
opened.

Refs gh:#2102.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from synlynk.wal_ledger import (
    WALConcurrencyError,
    ensure_wal_pragmas,
    write_transaction,
)

DEFAULT_WRITERS = 24
DEFAULT_READERS = 8
DEFAULT_OPS_PER_WRITER = 8
SEED_STORIES = 8

PASS_THRESHOLDS = {
    "max_lock_failure_rate": 0.01,
    "max_p99_latency_s": 5.0,
    "max_starved_writers": 0,
    "require_integrity_ok": True,
    "require_recovery_ok": True,
    "require_all_writes_committed": True,
}


@dataclass
class SoakConfig:
    db_path: str = ""
    writers: int = DEFAULT_WRITERS
    readers: int = DEFAULT_READERS
    ops_per_writer: int = DEFAULT_OPS_PER_WRITER
    executor: str = "thread"  # "thread" or "process"
    apply_wal: bool = True
    busy_timeout_ms: int = 30000
    connect_timeout_s: float = 30.0
    story_count: int = SEED_STORIES

    def __post_init__(self) -> None:
        if self.writers < 1:
            raise ValueError("writers must be >= 1")
        if self.ops_per_writer < 1:
            raise ValueError("ops_per_writer must be >= 1")
        if self.executor not in ("thread", "process"):
            raise ValueError("executor must be 'thread' or 'process'")


@dataclass
class SoakReport:
    db_path: str
    writers: int
    readers: int
    ops_per_writer: int
    executor: str
    apply_wal: bool
    duration_seconds: float
    expected_writes: int
    committed_writes: int
    lock_errors: int
    lock_failure_rate: float
    starved_writers: int
    integrity_ok: bool
    recovery_ok: bool
    journal_mode: str
    p50_latency_s: float
    p95_latency_s: float
    p99_latency_s: float
    max_latency_s: float
    read_ops: int
    failure_modes: List[str] = field(default_factory=list)
    passed: bool = False
    writer_successes: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def classify_failure_modes(
    *,
    lock_errors: int,
    integrity_ok: bool,
    starved_writers: int,
    committed_writes: int,
    expected_writes: int,
) -> List[str]:
    modes: List[str] = []
    if lock_errors > 0:
        modes.append("lock_contention")
    if not integrity_ok:
        modes.append("corruption")
    if starved_writers > 0:
        modes.append("write_starvation")
    if committed_writes < expected_writes and "lock_contention" not in modes:
        modes.append("lost_writes")
    return modes


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    weight = rank - lo
    return float(ordered[lo] * (1.0 - weight) + ordered[hi] * weight)


def _story_ids(count: int) -> List[str]:
    return [f"story-soak-{i}" for i in range(count)]


_LOCK_RETRY_ATTEMPTS = 6
_LOCK_RETRY_BASE_S = 0.02
_LOCK_RETRY_MAX_S = 0.25


def _is_lock_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def _apply_delete_journal_mode(
    conn: sqlite3.Connection,
    *,
    attempts: int = _LOCK_RETRY_ATTEMPTS,
    base_delay_s: float = _LOCK_RETRY_BASE_S,
) -> bool:
    """Put the ledger in DELETE journal mode.

    ``PRAGMA journal_mode=DELETE`` takes an exclusive lock. The negative-control
    soak issues it while sibling workers are still opening and writing, so
    ``sqlite3.OperationalError: database is locked`` is retried with a bounded
    backoff. When the lock never clears, return False and let the caller fall
    through into the write loop, which counts lock failures. Setup must not
    abort the run.
    """
    delay = base_delay_s
    for attempt in range(max(1, attempts)):
        try:
            current = conn.execute("PRAGMA journal_mode").fetchone()
            if current and str(current[0]).lower() == "delete":
                return True
            changed = conn.execute("PRAGMA journal_mode=DELETE").fetchone()
            if changed and str(changed[0]).lower() == "delete":
                return True
            # Another connection still holds the file, so SQLite kept the
            # previous mode instead of raising. Retry, then fall through.
        except sqlite3.OperationalError as exc:
            if not _is_lock_error(exc):
                raise
        if attempt >= attempts - 1:
            break
        if delay > 0:
            time.sleep(delay)
            delay = min(delay * 2, _LOCK_RETRY_MAX_S)
    return False


def _init_isolated_db(cfg: SoakConfig) -> None:
    parent = os.path.dirname(cfg.db_path) or "."
    os.makedirs(parent, exist_ok=True)
    import synlynk

    conn = synlynk._get_db(cfg.db_path)
    try:
        for story_id in _story_ids(cfg.story_count):
            conn.execute(
                "INSERT OR IGNORE INTO stories (story_id, title, engg_domain) VALUES (?, ?, ?)",
                (story_id, f"Soak {story_id}", "backend"),
            )
        if getattr(conn, "isolation_level", None) is not None:
            conn.commit()
    finally:
        conn.close()

    if not cfg.apply_wal:
        # Switch once before any worker connects. Later connections retry.
        raw = sqlite3.connect(cfg.db_path, timeout=max(float(cfg.connect_timeout_s), 5.0))
        try:
            _apply_delete_journal_mode(raw, attempts=8)
        finally:
            raw.close()


def _open_conn(cfg: SoakConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(
        cfg.db_path,
        timeout=cfg.connect_timeout_s,
        isolation_level=None,
        check_same_thread=False,
    )
    if cfg.apply_wal:
        ensure_wal_pragmas(conn)
    else:
        # Confirm DELETE before shrinking busy_timeout. A 1ms timeout is what
        # makes write contention observable; applying it first turns this
        # pragma into an uncaught "database is locked" and aborts the soak.
        _apply_delete_journal_mode(conn)
        conn.execute(f"PRAGMA busy_timeout={int(cfg.busy_timeout_ms)}")
    return conn


def _one_job_lifecycle(conn: sqlite3.Connection, cfg: SoakConfig, worker_id: int, op_index: int) -> None:
    job_id = f"soak-w{worker_id:03d}-op{op_index:04d}-{os.getpid()}"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    stories = _story_ids(cfg.story_count)
    story_id = stories[op_index % len(stories)]

    def _writes() -> None:
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, harness, task, story_id, status, "
            "priority, depends_on, enqueued_at, dispatch_context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                "grok",
                "grok",
                "synthetic soak job/state update",
                story_id,
                "queued",
                5,
                "[]",
                now,
                "headless",
            ),
        )
        conn.execute(
            "UPDATE daemon_jobs SET status='running', started_at=?, pid=? WHERE job_id=?",
            (now, os.getpid(), job_id),
        )
        # cost_entries writes must go through synlynk.db._insert_cost_row (ledger
        # contract). Use job_evidence for the extra per-job state row instead.
        conn.execute(
            "INSERT INTO job_evidence (evidence_id, job_id, kind, result, observed_at, "
            "source, payload_json, event_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"ev-{job_id}",
                job_id,
                "status",
                "ok",
                now,
                "state_db_soak",
                "{}",
                f"evt-{job_id}",
            ),
        )
        conn.execute(
            "UPDATE daemon_jobs SET status='done', exit_code=0, completed_at=? WHERE job_id=?",
            (now, job_id),
        )
        conn.execute(
            "UPDATE stories SET stage='in_progress' WHERE story_id=?",
            (story_id,),
        )

    if cfg.apply_wal:
        with write_transaction(conn):
            _writes()
    else:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _writes()
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise


def _run_writer(cfg: SoakConfig, worker_id: int) -> Dict[str, Any]:
    latencies: List[float] = []
    committed = 0
    lock_errors = 0
    errors: List[str] = []
    try:
        conn = _open_conn(cfg)
    except sqlite3.OperationalError as exc:
        if not _is_lock_error(exc):
            raise
        # Opening the control connection lost the lock race. Count it and
        # return so the soak report still reaches the lock-failure assertions.
        return {
            "worker_id": worker_id,
            "committed": 0,
            "lock_errors": 1,
            "latencies": [],
            "errors": [],
            "kind": "writer",
        }
    try:
        for op_index in range(cfg.ops_per_writer):
            started = time.perf_counter()
            try:
                _one_job_lifecycle(conn, cfg, worker_id, op_index)
                committed += 1
            except (sqlite3.OperationalError, sqlite3.DatabaseError, WALConcurrencyError) as exc:
                message = str(exc).lower()
                if "locked" in message or "busy" in message:
                    lock_errors += 1
                else:
                    errors.append(f"writer-{worker_id}: {exc}")
            except Exception as exc:
                errors.append(f"writer-{worker_id}: {exc}")
            latencies.append(time.perf_counter() - started)
    finally:
        conn.close()
    return {
        "worker_id": worker_id,
        "committed": committed,
        "lock_errors": lock_errors,
        "latencies": latencies,
        "errors": errors,
        "kind": "writer",
    }


def _run_reader(cfg: SoakConfig, stop_event: threading.Event, loops: int = 200) -> Dict[str, Any]:
    read_ops = 0
    errors: List[str] = []
    conn = _open_conn(cfg)
    try:
        for _ in range(loops):
            if stop_event.is_set():
                break
            try:
                conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()
                conn.execute(
                    "SELECT status, COUNT(*) FROM daemon_jobs GROUP BY status"
                ).fetchall()
                conn.execute("SELECT COUNT(*) FROM job_evidence").fetchone()
                conn.execute(
                    "SELECT story_id, stage FROM stories LIMIT 16"
                ).fetchall()
                read_ops += 4
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
                errors.append(f"reader: {exc}")
            time.sleep(0.005)
    finally:
        conn.close()
    return {
        "kind": "reader",
        "read_ops": read_ops,
        "errors": errors,
        "committed": 0,
        "lock_errors": 0,
        "latencies": [],
    }


def _writer_process_entry(payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = SoakConfig(**payload["cfg"])
    return _run_writer(cfg, payload["worker_id"])


def _integrity_and_recovery(cfg: SoakConfig) -> tuple[bool, bool, str]:
    journal_mode = "unknown"
    integrity_ok = False
    conn = sqlite3.connect(cfg.db_path, timeout=cfg.connect_timeout_s)
    try:
        if cfg.apply_wal:
            ensure_wal_pragmas(conn)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        integrity_ok = integrity == "ok"
        try:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
        except sqlite3.Error:
            if cfg.apply_wal:
                return integrity_ok, False, journal_mode
    except sqlite3.Error:
        return False, False, journal_mode
    finally:
        conn.close()

    reopen = sqlite3.connect(cfg.db_path, timeout=cfg.connect_timeout_s)
    try:
        if cfg.apply_wal:
            ensure_wal_pragmas(reopen)
        again = reopen.execute("PRAGMA integrity_check").fetchone()[0]
        reopen.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()
        return integrity_ok, again == "ok", journal_mode
    except sqlite3.Error:
        return integrity_ok, False, journal_mode
    finally:
        reopen.close()


def _evaluate(cfg: SoakConfig, writer_results: List[Dict[str, Any]], reader_results: List[Dict[str, Any]], duration: float) -> SoakReport:
    expected = cfg.writers * cfg.ops_per_writer
    committed = sum(int(r.get("committed") or 0) for r in writer_results)
    lock_errors = sum(int(r.get("lock_errors") or 0) for r in writer_results)
    successes = [int(r.get("committed") or 0) for r in writer_results]
    starved = sum(1 for n in successes if n == 0)
    latencies = [lat for r in writer_results for lat in r.get("latencies") or []]
    errors = [e for r in writer_results + reader_results for e in r.get("errors") or []]
    read_ops = sum(int(r.get("read_ops") or 0) for r in reader_results)
    attempts = max(expected, 1)
    lock_failure_rate = lock_errors / attempts
    integrity_ok, recovery_ok, journal_mode = _integrity_and_recovery(cfg)
    failure_modes = classify_failure_modes(
        lock_errors=lock_errors,
        integrity_ok=integrity_ok,
        starved_writers=starved,
        committed_writes=committed,
        expected_writes=expected,
    )
    passed = True
    if cfg.apply_wal:
        if PASS_THRESHOLDS["require_integrity_ok"] and not integrity_ok:
            passed = False
        if PASS_THRESHOLDS["require_recovery_ok"] and not recovery_ok:
            passed = False
        if PASS_THRESHOLDS["require_all_writes_committed"] and committed != expected:
            passed = False
        if lock_failure_rate > PASS_THRESHOLDS["max_lock_failure_rate"]:
            passed = False
        if starved > PASS_THRESHOLDS["max_starved_writers"]:
            passed = False
        if journal_mode != "wal":
            passed = False
            if "lock_contention" not in failure_modes:
                failure_modes.append("not_wal")
        if _percentile(latencies, 99) > PASS_THRESHOLDS["max_p99_latency_s"]:
            passed = False
            if "write_starvation" not in failure_modes:
                failure_modes.append("latency_budget")
    else:
        passed = not failure_modes and committed == expected and integrity_ok

    return SoakReport(
        db_path=cfg.db_path,
        writers=cfg.writers,
        readers=cfg.readers,
        ops_per_writer=cfg.ops_per_writer,
        executor=cfg.executor,
        apply_wal=cfg.apply_wal,
        duration_seconds=round(duration, 4),
        expected_writes=expected,
        committed_writes=committed,
        lock_errors=lock_errors,
        lock_failure_rate=round(lock_failure_rate, 6),
        starved_writers=starved,
        integrity_ok=integrity_ok,
        recovery_ok=recovery_ok,
        journal_mode=journal_mode,
        p50_latency_s=round(_percentile(latencies, 50), 6),
        p95_latency_s=round(_percentile(latencies, 95), 6),
        p99_latency_s=round(_percentile(latencies, 99), 6),
        max_latency_s=round(max(latencies) if latencies else 0.0, 6),
        read_ops=read_ops,
        failure_modes=failure_modes,
        passed=passed,
        writer_successes=successes,
        errors=errors,
    )


def _run_threaded(cfg: SoakConfig) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    stop = threading.Event()
    writer_results: List[Dict[str, Any]] = []
    reader_results: List[Dict[str, Any]] = []
    workers = cfg.writers + max(cfg.readers, 0)
    barrier = threading.Barrier(workers, timeout=30)

    def writer_fn(worker_id: int) -> Dict[str, Any]:
        barrier.wait()
        return _run_writer(cfg, worker_id)

    def reader_fn() -> Dict[str, Any]:
        barrier.wait()
        return _run_reader(cfg, stop)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        writer_futs = [pool.submit(writer_fn, i) for i in range(cfg.writers)]
        reader_futs = [pool.submit(reader_fn) for _ in range(cfg.readers)]
        wait(writer_futs)
        stop.set()
        wait(reader_futs)
        writer_results = [f.result() for f in writer_futs]
        reader_results = [f.result() for f in reader_futs]
    return writer_results, reader_results


def _run_processed(cfg: SoakConfig) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ctx = multiprocessing.get_context("spawn")
    cfg_dict = asdict(cfg)
    payloads = [{"cfg": cfg_dict, "worker_id": i} for i in range(cfg.writers)]
    # apply_async + get(timeout) so a crashed spawn worker cannot hang pytest.
    with ctx.Pool(processes=cfg.writers) as pool:
        pending = [pool.apply_async(_writer_process_entry, (payload,)) for payload in payloads]
        writer_results = [item.get(timeout=120) for item in pending]

    # Readers stay in-process: they only SELECT, and spawn-pool readers would
    # need a shared stop event. A short post-write read burst still exercises
    # WAL read concurrency against the populated ledger.
    stop = threading.Event()
    reader_results: List[Dict[str, Any]] = []
    if cfg.readers:
        with ThreadPoolExecutor(max_workers=cfg.readers) as pool:
            futs = [pool.submit(_run_reader, cfg, stop, 40) for _ in range(cfg.readers)]
            wait(futs)
            reader_results = [f.result() for f in futs]
    return writer_results, reader_results


def run_state_db_soak(cfg: Optional[SoakConfig] = None) -> SoakReport:
    """Run the isolated WAL soak and return a machine-readable report."""
    if cfg is None:
        cfg = SoakConfig()
    if not cfg.db_path:
        raise ValueError("SoakConfig.db_path is required (isolated temp database)")

    _init_isolated_db(cfg)
    started = time.perf_counter()
    if cfg.executor == "process":
        writer_results, reader_results = _run_processed(cfg)
    else:
        writer_results, reader_results = _run_threaded(cfg)
    duration = time.perf_counter() - started
    return _evaluate(cfg, writer_results, reader_results, duration)
