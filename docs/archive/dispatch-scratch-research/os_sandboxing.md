# OS-level Sandboxing and Credential Isolation for Agent Execution

This document outlines three primary mechanisms for sandboxing processes on Linux/macOS environments and how they can be leveraged to isolate credentials for autonomous agents like **Antigravity**.

## 1. Bubblewrap (bwrap)

- **What it is**: A setuid‑less userspace tool that creates lightweight containers by manipulating Linux namespaces (mount, PID, network, user, etc.).
- **Key features**:
  - No root privileges required for most operations.
  - Fine‑grained control over filesystem exposure (`--bind`, `--ro-bind`).
  - Ability to drop capabilities (`--cap-drop`).
- **Typical usage**:
  ```bash
  bwrap \
    --unshare-all \
    --dev /dev \
    --proc /proc \
    --ro-bind /usr /usr \
    --ro-bind /lib /lib \
    --tmpfs /tmp \
    --new-session \
    --setenv HOME /tmp/home \
    --setenv XDG_RUNTIME_DIR /tmp/runtime \
    --caps-drop all \
    --clearenv \
    /usr/bin/python3 my_agent_script.py
  ```
- **Credential isolation**: By creating a fresh user namespace (`--unshare-user`) and not mounting `/etc/passwd` or `/home`, the process cannot see the host's user IDs or stored credentials.

## 2. Rootless Docker

- **What it is**: Docker daemon runs as an unprivileged user, leveraging user namespaces to map container root to a non‑root UID on the host.
- **Advantages**:
  - Full OCI container ecosystem (images, networking, volume management).
  - Isolation of secrets via Docker secrets or environment variable masking.
- **Running without sudo**:
  ```bash
  dockerd-rootless.sh &   # Starts the daemon in the background
  docker run --rm \
    -v $PWD:/workspace \
    -e AGENT_API_KEY=***** \
    my-agent-image python /workspace/run_agent.py
  ```
- **Credential isolation**: Secrets can be supplied at container start via `--env-file` or Docker secret mounts, never written to the host filesystem.

## 3. macOS `sandbox-exec`

- **What it is**: A native macOS sandboxing service driven by a *sandbox profile* written in a domain‑specific language.
- **Example profile (`agent.sb`)**:
  ```text
  (version 1)
  (deny default)
  (allow file-read* (regex "/usr/lib/.*"))
  (allow file-read* (regex "/System/Library/.*"))
  (allow process-exec)
  (allow network-outbound (local ip))
  (allow file-write* (regex "/tmp/.*"))
  ```
- **Running a command**:
  ```bash
  sandbox-exec -f agent.sb python3 my_agent.py
  ```
- **Credential isolation**: By restricting file‑read access to only `/tmp` and explicitly denying reads of `~/` or `/etc/`, the sandbox prevents accidental leakage of stored credentials.

## 4. Combining Strategies for Agent Execution

1. **Default Execution**: Run agents inside a **Bubblewrap** container for fast startup and minimal overhead.
2. **Heavy‑weight workloads**: Switch to **Rootless Docker** when the agent requires complex dependencies or network isolation.
3. **macOS‑only environments**: Fall back to **sandbox‑exec** with a restrictive profile.

## 5. Best Practices

- **Never store credentials in the container image**; inject them at runtime via environment variables, secret files in a read‑only bind mount, or Docker secrets.
- **Use temporary home directories** (`--setenv HOME /tmp/home`) to avoid reading `.ssh` or other credential stores.
- **Drop all capabilities** unless explicitly needed (`--caps-drop all`).
- **Audit the sandbox** with tools like `bwrap --debug` or Docker’s `seccomp` profiles.

---

*Prepared by Antigravity (AGY) team – 2026-10-15*
