# Design Spec: Ephemeral Swarm Cloud Runner Drivers (Fly.io, K8s, Hetzner)

**Date:** 2026-09-02  
**Status:** In Review  
**Issue:** [#1341](https://github.com/nikhilsoman/synlynk/issues/1341)  
**Authors:** [@nikhilsoman], [@agy], [@codex]  
**Relates to:** #1326, `goal-005ea87d`  

---

## 1. Objective & Scope

Enable the Synlynk Swarm Engine to scale beyond local laptop hardware constraints (CPU/RAM/battery) by provisioning pluggable, low-cost **Ephemeral Cloud Runners** on demand in $<2\text{s}$ for massive parallel task fanout (10–100+ concurrent workers).

---

## 2. Architecture & Pluggable Driver Contract

```
                     ┌────────────────────────────────────────────────────────┐
                     │          LOCAL MASTER (synlynk swarm dispatch)         │
                     └──────────────────────────┬─────────────────────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
     ┌───────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
     │     Fly.io Driver     │      │   Kubernetes Driver   │      │     Hetzner Driver    │
     │  (Micro-VM in <2s)    │      │    (Pod / Job)        │      │   (Burst VPS Worker)  │
     └───────────┬───────────┘      └───────────┬───────────┘      └───────────┬───────────┘
                 │                              │                              │
                 └──────────────────────────────┼──────────────────────────────┘
                                                ▼
                                 ┌─────────────────────────────┐
                                 │   synlynk-worker Container  │
                                 │   - Git Worktree Clone      │
                                 │   - Headless CLI Runner     │
                                 │   - Telemetry Streamer      │
                                 │   - Auto-Destruct on Exit   │
                                 └─────────────────────────────┘
```

### A. Runner Driver Interface (`synlynk/runners/base.py`)
```python
class SwarmRunnerDriver(ABC):
    @abstractmethod
    def provision(self, job_spec: dict) -> str:
        """Provisions an isolated cloud container / micro-VM, returns runner_id."""
        pass

    @abstractmethod
    def stream_telemetry(self, runner_id: str, callback: Callable):
        """Streams live stdout and token telemetry back to master relay."""
        pass

    @abstractmethod
    def collect_results(self, runner_id: str) -> dict:
        """Collects git commit SHA, exit code, and execution receipts."""
        pass

    @abstractmethod
    def destroy(self, runner_id: str) -> bool:
        """Unconditionally terminates and tears down remote compute."""
        pass
```

### B. Standard Container Image (`synlynk-worker:latest`)
- Minimal alpine/debian container bundling:
  - Python 3.12 + `synlynk` CLI
  - Git + SSH deployment keys
  - Node.js runtime for Codex / Claude CLI runners
  - Pytest + common verification toolchains

### C. Fail-Safe Auto-Destruction & Budget Guard
- Every ephemeral instance includes a hardware watchdog timer (`TIMEOUT=900s`).
- If a runner loses contact with the local master for $>60\text{s}$ or reaches its task timeout, it self-terminates immediately, preventing orphaned billing.

---

## 3. Test & Verification Plan
- Mock runner lifecycle test in `tests/test_runners.py`.
- Integration tests with local Docker / Kind (Kubernetes) test fixtures.
