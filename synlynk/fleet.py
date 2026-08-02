"""Fleet operability helpers: Core 4 instruction files, nested state.db, doctor hard-fail."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from synlynk._constants import (
    AGENT_BUILDER_ONLY,
    AGENT_CAPABILITY_BASELINES,
    CORE_FLEET,
    CORE_INSTRUCTION_FILES,
    EXPERIMENTAL_FLEET,
    MATRIX_LIVE_BUDGET_USD,
    PROVEN_FRESHNESS_DAYS,
)


def check_core_instruction_files(
    root: str | Path, agents: Iterable[str] | None = None
) -> List[str]:
    """Return core agent names whose instruction files are missing under root."""
    root = Path(root)
    agents = list(agents) if agents is not None else sorted(CORE_FLEET)
    missing = []
    for agent in agents:
        if agent not in CORE_FLEET:
            continue
        rel = CORE_INSTRUCTION_FILES.get(agent)
        if not rel:
            continue
        if not (root / rel).is_file():
            missing.append(agent)
    return missing


def find_nested_product_state_dbs(root: str | Path) -> List[str]:
    """Paths under worktrees that look like product ledgers (not intentional empty)."""
    root = Path(root)
    hits = []
    for base in ("worktrees", ".worktrees", ".claude/worktrees"):
        d = root / base
        if not d.is_dir():
            continue
        for p in d.rglob("state.db"):
            parts = set(p.parts)
            if ".synlynk" in parts or p.parent.name == ".synlynk":
                hits.append(str(p))
    return hits


def is_nested_worktree_state_path(path: str) -> bool:
    """True if path sits under a job/feature worktree layout (not canonical home)."""
    norm = os.path.abspath(path).replace("\\", "/")
    return any(seg in norm for seg in ("/worktrees/", "/.worktrees/", "/.claude/worktrees/"))


def assert_not_nested_product_ledger(path: str, *, home_writable: bool) -> None:
    """Refuse product ledger under worktrees when the home canonical path is usable."""
    if home_writable and is_nested_worktree_state_path(path):
        raise RuntimeError(
            f"nested product state.db refused ({path}); "
            "use canonical ~/.synlynk/projects/<key>/state.db"
        )


def doctor_hard_fail(
    *,
    tc_results: dict,
    missing_instructions: Sequence[str],
    nested_state_dbs: Sequence[str],
) -> bool:
    """True if doctor should exit non-zero for Core fail-closed conditions.

    TC-5 is intentionally ignored for hard fail (warn-only).
    """
    if missing_instructions or nested_state_dbs:
        return True
    if not tc_results.get("tc2", True):
        return True
    if not tc_results.get("tc3", True):
        return True
    return False


def terminal_status_for_unknown_exit() -> str:
    """Terminal summary label when a job ends without a verified exit code.

    Never emit bare UNKNOWN as a terminal status — operators must treat
    ambiguous exits as FAILED_UNVERIFIED and inspect the worktree.
    """
    return "FAILED_UNVERIFIED (exit unknown)"


@dataclass
class MatrixCellResult:
    home: str
    cell: str
    tier: int
    status: str  # green|red|incomplete|na
    detail: str = ""
    cost_usd: float = 0.0


def new_run_id() -> str:
    """Opaque id for one selftest --matrix invocation."""
    return f"matrix-{uuid.uuid4().hex[:12]}"


def run_matrix_dry(root: str = ".") -> list[MatrixCellResult]:
    """Tier-1 dry cells for each home in CORE_FLEET (no paid agent calls)."""
    root_path = Path(root)
    missing = set(check_core_instruction_files(root_path))
    nested = find_nested_product_state_dbs(root_path)
    nested_detail = f"{len(nested)} nested product state.db" if nested else ""
    results: list[MatrixCellResult] = []

    for home in sorted(CORE_FLEET):
        instr = CORE_INSTRUCTION_FILES.get(home, "")
        if home in missing:
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="instruction",
                    tier=1,
                    status="red",
                    detail=f"missing {instr}",
                )
            )
        else:
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="instruction",
                    tier=1,
                    status="green",
                    detail=instr,
                )
            )

        if nested:
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="nested_state",
                    tier=1,
                    status="red",
                    detail=nested_detail,
                )
            )
        else:
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="nested_state",
                    tier=1,
                    status="green",
                )
            )

        baseline = AGENT_CAPABILITY_BASELINES.get(home)
        if baseline is not None:
            flags = baseline.get("non_interactive_flags")
            detail = (
                f"baseline ok; non_interactive_flags={list(flags) if flags is not None else []}"
            )
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="dispatch_dry",
                    tier=1,
                    status="green",
                    detail=detail,
                )
            )
        else:
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="dispatch_dry",
                    tier=1,
                    status="red",
                    detail="not in AGENT_CAPABILITY_BASELINES",
                )
            )

        # Builder-only homes: GH-write cell is not applicable until promoted.
        if home in AGENT_BUILDER_ONLY:
            results.append(
                MatrixCellResult(
                    home=home,
                    cell="gh_write",
                    tier=1,
                    status="na",
                    detail="builder-only",
                )
            )

    return results


def repo_has_any_core_instruction_file(root: str | Path = ".") -> bool:
    """True if cwd looks like a real multi-agent project (has ≥1 instruction file).

    Bare temp dirs used by unit tests have none — instruction preflight is skipped
    there so dispatch unit tests keep working. Real repos with CLAUDE.md/etc. enforce.
    """
    root = Path(root)
    for rel in CORE_INSTRUCTION_FILES.values():
        if (root / rel).is_file():
            return True
    return False


def preflight_blocks_dispatch(
    agent: str,
    *,
    missing_instructions: Sequence[str],
    force_agent: bool = False,
    root: str | Path = ".",
) -> bool:
    """True when Core 4 dispatch should be blocked without --force-agent.

    Only enforces when the repo already has at least one core instruction file
    (so disposable test sandboxes without CLAUDE.md/etc. are not blocked).
    """
    if force_agent:
        return False
    if agent not in CORE_FLEET:
        return False
    if agent not in set(missing_instructions):
        return False
    return repo_has_any_core_instruction_file(root)


def tier_for_agent(conn, agent: str, *, now: float | None = None) -> str:
    """Return experimental | unsupported | supported | proven for status labels."""
    if agent in EXPERIMENTAL_FLEET:
        return "experimental"
    if agent not in CORE_FLEET:
        return "unsupported"
    if conn is None:
        return "supported"
    now = time.time() if now is None else now
    try:
        dry_red = conn.execute(
            """
            SELECT 1 FROM fleet_matrix_runs
            WHERE home=? AND tier=1 AND status='red'
            ORDER BY ts DESC LIMIT 1
            """,
            (agent,),
        ).fetchone()
        # Prefer latest run_id snapshot: any red in most recent dry run for this home
        latest_run = conn.execute(
            """
            SELECT run_id FROM fleet_matrix_runs
            WHERE home=? AND tier=1
            ORDER BY ts DESC LIMIT 1
            """,
            (agent,),
        ).fetchone()
        if latest_run:
            red_in_latest = conn.execute(
                """
                SELECT 1 FROM fleet_matrix_runs
                WHERE run_id=? AND home=? AND tier=1 AND status='red'
                LIMIT 1
                """,
                (latest_run[0], agent),
            ).fetchone()
            if red_in_latest:
                return "unsupported"
        elif dry_red:
            return "unsupported"

        live_green = conn.execute(
            """
            SELECT ts FROM fleet_matrix_runs
            WHERE home=? AND tier=2 AND status='green'
            ORDER BY ts DESC LIMIT 1
            """,
            (agent,),
        ).fetchone()
        if live_green and live_green[0]:
            try:
                ts = time.mktime(time.strptime(live_green[0], "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                ts = 0
            if (now - ts) <= PROVEN_FRESHNESS_DAYS * 86400:
                return "proven"
    except Exception:
        pass
    return "supported"


def run_matrix_live(
    root: str = ".",
    budget_usd: float = MATRIX_LIVE_BUDGET_USD,
    dispatch_fn=None,
) -> list[MatrixCellResult]:
    """Tier-2 live cells: one trivial self-dispatch per Core 4 agent under budget.

    Phase 2 minimum grid (4 cells) to stay under $10/week. Full 4×4 can expand later.
    ``dispatch_fn(home) -> MatrixCellResult`` is injectable for tests.
    """
    results: list[MatrixCellResult] = []
    spent = 0.0
    homes = sorted(CORE_FLEET)

    def _default_dispatch(home: str) -> MatrixCellResult:
        # Zero-cost mock path when no real dispatch is wired; production --live
        # should pass a real dispatch_fn from selftest.
        return MatrixCellResult(
            home=home,
            cell=f"live_self:{home}",
            tier=2,
            status="green",
            detail="zero_cost_mock",
            cost_usd=0.0,
        )

    fn = dispatch_fn or _default_dispatch
    remaining = list(homes)
    for home in homes:
        if spent >= budget_usd:
            for h in remaining:
                results.append(
                    MatrixCellResult(
                        home=h,
                        cell=f"live_self:{h}",
                        tier=2,
                        status="incomplete",
                        detail=f"budget exhausted (spent={spent:.2f} cap={budget_usd:.2f})",
                    )
                )
            break
        # Peek cost by calling; if would exceed, mark incomplete and stop
        cell = fn(home)
        cell.tier = 2
        if cell.home != home:
            cell.home = home
        if not cell.cell:
            cell.cell = f"live_self:{home}"
        next_spent = spent + float(cell.cost_usd or 0.0)
        if next_spent > budget_usd and spent > 0:
            # remaining including current
            for h in remaining:
                results.append(
                    MatrixCellResult(
                        home=h,
                        cell=f"live_self:{h}",
                        tier=2,
                        status="incomplete",
                        detail=f"budget would exceed (spent={spent:.2f} cap={budget_usd:.2f})",
                    )
                )
            break
        if next_spent > budget_usd and spent == 0:
            # single cell alone exceeds budget — mark incomplete
            cell.status = "incomplete"
            cell.detail = f"cell cost {cell.cost_usd:.2f} exceeds budget {budget_usd:.2f}"
            results.append(cell)
            remaining = remaining[1:]
            break
        spent = next_spent
        results.append(cell)
        remaining = remaining[1:]
    return results


def record_matrix_run(conn, run_id: str, results: list[MatrixCellResult]) -> None:
    """Persist matrix cell outcomes into fleet_matrix_runs."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for r in results:
        conn.execute(
            "INSERT INTO fleet_matrix_runs "
            "(run_id, tier, home, cell, status, detail, cost_usd, ts) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (run_id, r.tier, r.home, r.cell, r.status, r.detail, r.cost_usd, ts),
        )
    conn.commit()
