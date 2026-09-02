"""Contracts shared by local and cloud swarm runners."""

from abc import ABC, abstractmethod
from typing import Callable


class SwarmRunnerDriver(ABC):
    """Provision, observe, harvest, and tear down one ephemeral runner."""

    @abstractmethod
    def provision(self, job_spec: dict) -> str:
        """Return an opaque runner id for an isolated execution environment."""

    @abstractmethod
    def stream_telemetry(self, runner_id: str, callback: Callable) -> None:
        """Send stdout/progress records to ``callback`` until the runner exits."""

    @abstractmethod
    def collect_results(self, runner_id: str) -> dict:
        """Return the runner receipt, including exit code and commit SHA."""

    @abstractmethod
    def destroy(self, runner_id: str) -> bool:
        """Unconditionally terminate the runner."""
