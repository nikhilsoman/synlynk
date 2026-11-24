"""harness-spec: Universal Agent CLI Discovery & Sandboxing Protocol."""

from harness_spec.models import HarnessContract, SandboxProfile
from harness_spec.probe import probe_binary, probe_all_known

__version__ = "0.1.0"
__all__ = ["HarnessContract", "SandboxProfile", "probe_binary", "probe_all_known"]
