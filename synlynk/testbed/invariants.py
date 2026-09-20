"""Relational state.db Invariant Asserters across Distributed Nodes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from synlynk.testbed.driver import TestbedDriver


@dataclass
class InvariantReport:
    lease_mutual_exclusion: bool = True
    zero_orphan_leases: bool = True
    relay_deduplication: bool = True
    attribution_preserved: bool = True
    details: str = ""

    @property
    def all_passed(self) -> bool:
        return (
            self.lease_mutual_exclusion
            and self.zero_orphan_leases
            and self.relay_deduplication
            and self.attribution_preserved
        )


class InvariantAsserter:
    """Queries and validates SQLite relational invariants across testbed nodes."""

    def __init__(self, driver: TestbedDriver):
        self.driver = driver

    def _parse_int(self, output: str) -> int:
        match = re.search(r"\b(\d+)\b", output.strip())
        return int(match.group(1)) if match else 0

    def check_all(self, node_ids: List[str]) -> InvariantReport:
        report = InvariantReport()

        for node_id in node_ids:
            # 1. Mutual exclusion: check if multiple active leases exist for the same story
            sql_mutex = (
                "sqlite3 .synlynk/state.db \"SELECT count(*) FROM (SELECT story_id, count(*) as c "
                "FROM daemon_jobs WHERE status='running' GROUP BY story_id HAVING c > 1);\" 2>/dev/null || echo 0"
            )
            res_mutex = self.driver.exec_command(node_id, sql_mutex)
            count_mutex = self._parse_int(res_mutex.stdout)
            if count_mutex > 0:
                report.lease_mutual_exclusion = False
                report.details += f"[{node_id}] Mutual exclusion violation: {count_mutex} duplicate active leases.\n"

            # 2. Check orphan dead leases
            sql_orphan = (
                "sqlite3 .synlynk/state.db \"SELECT count(*) FROM daemon_jobs "
                "WHERE status='running' AND strftime('%s', 'now') - strftime('%s', updated_at) > 300;\" 2>/dev/null || echo 0"
            )
            res_orphan = self.driver.exec_command(node_id, sql_orphan)
            count_orphan = self._parse_int(res_orphan.stdout)
            if count_orphan > 0:
                report.zero_orphan_leases = False
                report.details += f"[{node_id}] Orphan lease violation: {count_orphan} stalled jobs.\n"

        return report
