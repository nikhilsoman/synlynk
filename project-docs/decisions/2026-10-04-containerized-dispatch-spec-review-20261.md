<!-- generated - source of truth is state.db -->
---
decision_id: dec-ff9a9005
topic: "containerized-dispatch-spec-review-20261004

Review the design spec below. Do not implement it. Judge whether the container contract actually isolates an untrusted harness, whether the spawn seam matches dispatch_agent's existing sh -c launch, whether the scope matches issue #1925's containerization half only, and whether the tests would catch a host fallback or a missing git mount. End the final paragraph with a clear position: approve, approve with required changes, or reject. Name the required changes if any.

# Design: Opt-in containerized dispatch for untrusted harnesses

- **Date:** 2026-10-04
- **Author:** Grok (infra)
- **Status:** Draft, awaiting review
- **Issue:** [#1925](https://github.com/nikhilsoman/synlynk/issues/1925) (containerization half only)
- **Source:** `docs/strategy/2026-10-02-decide-panel-roadmap.md` §1 row 6

## 1. Problem

The flag-default half of #1925 is already shipped. `HARNESS_CAPABILITY_BASELINES` leaves Claude's `required_flags` empty, and `--dangerously-skip-permissions` is an explicit per-dispatch opt-in.

Dispatch still starts every harness as a host subprocess. `dispatch_agent` builds an allowlisted environment and runs `sh -c <shell_cmd>` with `cwd` set to the job worktree (`synlynk/dispatch.py`, the `Popen(["sh", "-c", shell_cmd], ...)` call). The worktree isolates git state. It does not isolate the process, the network, or the rest of the filesystem.

`docker/Dockerfile.sovereign` is not this sandbox. It installs synlynk and aider-chat, points at a host oMLX endpoint, and its entrypoint either runs `synlynk dispatch local` or opens a shell. That image and `.github/workflows/sovereign-build.yml`'s publish of `ghcr.io/nikhilsoman/synlynk-sovereign` stay as they are.

## 2. Locked decisions

1. **Opt-in only.** First-party harnesses stay on the host unless this dispatch names an image. No entry in `HARNESS_CAPABILITY_BASELINES` gains a `container_image` in this change.
2. **Boundary.** The container gets the job worktree read-write, the git directory that worktree points at, and the existing env allowlist with the rewrites in §6. The root filesystem is read-only. There is no home mount, no SSH agent socket, and no Docker socket. Capabilities are dropped. The network stays on the default bridge, because a harness that cannot reach its model API cannot do the job.
3. **Generic runner image.** synlynk ships one small image. The harness CLI is whatever is already on `PATH` inside the image the operator names. Vendor CLIs are not packaged here. A Mac arm64 host binary cannot run inside a Linux container, so the host CLI is not bind-mounted.
4. **Git.** Mount the worktree plus the linked git dir and its `commondir`, at the same absolute host paths, so `git commit` works. Residual exposure is that repo's objects, refs, and `.git/config`.
5. **Shape.** A new `synlynk/container_exec.py` module rewrites the argv at the existing spawn site. `dispatch.py` does not grow a second execution policy. No shell script under `docker/` is the implementation.

## 3. Non-goals

- The HarnessAdapter plugin registry (roadmap row 5: OpenCode, Aider, Goose).
- Containerizing `synlynk exec`.
- Podman, an egress proxy, CPU or memory limits, and publishing the runner image to GHCR.
- Changing `Dockerfile.sovereign` or the sovereign image's tags.
- Implementing the 2026-09-04 sandbox research (`docs/superpowers/specs/2026-09-04-sandboxing-research.md`, #1392 / #1393): bubblewrap, Seatbelt, default-deny network, and domain-filtered egress. This spec is the opt-in Docker slice of #1925 only. It does not close #1392.
- Putting Claude, Codex, Agy, Grok, Muse, or local into a container by default.

## 4. Spawn seam

`synlynk/container_exec.py` exposes `wrap(cmd, env, cwd, image) -> (cmd, env, cwd)`.

`dispatch_agent` calls it immediately before the existing `Popen(["sh", "-c", shell_cmd], ...)`. Logs and the prompt already live inside the worktree (`.synlynk/logs`, `.synlynk/prompts`), and the shell string redirects there. Those paths stay valid because the worktree is mounted at its real host path.

With no image, `wrap` returns `cmd`, `env`, and `cwd` unchanged. The host `Popen` arguments (`stdout=DEVNULL`, `stderr=DEVNULL`, `start_new_session=True`) stay as they are.

With an image, `wrap` returns a `docker run` argv whose command is still `sh -c` plus the same shell string. `Popen` runs that argv. `argv[0]` is the absolute path from `which("docker")`. The docker client's own environment is the allowlisted `proc_env`, plus `DOCKER_HOST` copied from the parent when the parent has it set, so OrbStack or a remote daemon still works. `DOCKER_HOST` is never passed into the container with `-e`. The harness receives only the `-e` list from §6. Do not pass `-d`. A detached client exits immediately, and the startup check would treat a live job as finished. The recorded pid is the Docker client. `docker run` forwards a signal sent to that client into the container. `start_new_session=True` stays.

`synlynk exec` is not changed.

## 5. How an image is chosen

- New `synlynk dispatch` flag: `--container-image <ref>`.
- Optional baseline field `container_image` on a harness entry. The flag wins when both are set.
- Neither set: host path. An absent flag must not read a default image.
- Thread the resolved image into `dispatch_agent` as an explicit argument. When an image is set, the recursive startup failover in §7 is not called, so the image cannot be dropped on a second attempt.

The image ref is one token. Reject empty, whitespace, or a newline before building argv. Place it immediately after `--`, so a ref cannot be parsed as a `docker run` option.

## 6. `docker run` contract

`wrap` builds a list. It does not join the argv into a shell string.

```text
docker run --rm
  --network bridge
  --read-only
  --cap-drop ALL
  --security-opt no-new-privileges
  --user <host-uid>:<host-gid>
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777
  -w <worktree absolute path>
  -v <worktree>:<worktree>
  -v <per-worktree git dir>:<same path>   # only if outside the worktree
  -v <common git dir>:<same path>         # only if outside the worktree and distinct
  -e <rewritten allowlist>
  -- <image>
  sh -c <the shell string dispatch already built>
```

Forbidden in this argv: `--privileged`, `--network host`, `-v` of the home directory, `-v` of `docker.sock`, and any bind of `SSH_AUTH_SOCK`.

### Git mounts

Always mount the worktree read-write at its absolute path. `cwd` inside the container is that path, so existing Grok `--cwd`, Codex `-C`, and Muse `-C` flags still name a real directory.

If `<worktree>/.git` is a directory, it is already inside the mount. Add nothing.

If `<worktree>/.git` is a file, parse the `gitdir:` line, resolve it against the worktree, and require the target to exist. Mount it read-write at that same absolute path when it is outside the worktree. Then read `commondir` inside that git dir, resolve it against the git dir, and mount it the same way when it is outside the worktree and not the same path. That common dir is where the objects live. If the `gitdir:` line is missing or the resolved path does not exist, `wrap` raises and nothing is spawned.

### Environment

Start from the dict `_build_subprocess_env` already returned. Pass each remaining variable with `-e`.

Rewrites, applied only on the container path:

| Variable | Treatment | Why |
|---|---|---|
| `HOME`, `TMPDIR` | Set to `/tmp` | A host path would require mounting home or temp. `/tmp` is the tmpfs. |
| `PATH`, `SHELL` | Drop | The host `PATH` would hide the CLI installed in the image. |
| `SSH_AUTH_SOCK` | Drop | The socket is not mounted. Passing the variable without the socket is useless, and mounting the socket would hand the harness the operator's agent. |

Git author and committer name and email still pass. A `GH_TOKEN` / `GITHUB_TOKEN` injected by the existing `--requires-gh-write` path still passes. That opt-in already exists. The container does not gain host-keyring access. Other allowlisted variables pass through unchanged.

`--user` is the operator's numeric uid and gid, so files written in the worktree stay owned by that user. The image does not need a matching account.

## 7. Failures

No silent fall-back to a host subprocess.

- Image requested and `docker` is not on `PATH`: `dispatch_agent` raises before `Popen`. The harness command is not executed.
- Empty or whitespace image ref: raise before `Popen`.
- Git dir cannot be resolved: `wrap` raises before `Popen`.
- `docker run` fails to start (daemon down, image missing): the client exits non-zero and the inner `sh -c` never writes `<log>.exit`.

When an image is set, the client's stderr is the job log opened for append, not `DEVNULL`. The inner shell still redirects harness stdout and stderr to that same log. Client errors such as "image not found" are therefore visible. The host path keeps `stderr=DEVNULL`.

When an image is set, do not call the secondary-harness failover. A container failure must not retry on the host.

If the client has already exited non-zero and `<log>.exit` does not exist:

1. The client's stderr is already in the job log via the append handle.
2. Write that exit code to `<log>.exit`.
3. Persist the daemon job as `failed` with that `exit_code` and `completed_at` set, instead of the `status='running'` write this function uses for a live process.

If the client is still running, persist `running` exactly as today.

## 8. Runner image

New file: `docker/Dockerfile.runner`. Do not extend `Dockerfile.sovereign`.

The base is `debian:bookworm-slim`. It already provides `sh`. The image installs `git` and CA certificates, does not copy the synlynk source tree, and puts a `stub-harness` executable on `PATH`. The stub prints a fixed scrapeable line:

```text
Input tokens: 11
Output tokens: 7
```

It writes a marker file `stub-marker` in the current directory when that directory is writable, then exits with the integer in `STUB_EXIT`, or `0` when `STUB_EXIT` is unset.

This image is what tests and operators name. It is not a default. Real Claude, Codex, Agy, Grok, Muse, or third-party CLIs belong in an image the operator supplies via `--container-image`.

`.github/workflows/sovereign-build.yml` gains a second job that builds `docker/Dockerfile.runner` and runs `stub-harness` with the worktree mounted. It does not log in to GHCR and does not push. The existing sovereign build and push job is unchanged. Unit tests do not depend on this job.

## 9. Tests

Required tests use a fake `docker` placed first on `PATH`. The fake appends its argv to a file and then executes the command after the image token (`sh -c ...`). No Docker daemon is required.

1. **Host identity.** No image: `wrap` returns the original argv, env, and cwd.
2. **Mount contract.** With an image and a linked worktree, the argv contains `--rm`, `--read-only`, `--cap-drop`, `ALL`, `--security-opt`, `no-new-privileges`, `--network`, `bridge`, `--user` with the current uid and gid, `-v <worktree>:<worktree>`, `-v` for the per-worktree git dir, and `-v` for the common git dir. It does not contain the home directory, `docker.sock`, or `--network host`. The image is one token after `--`, followed by `sh -c` and the original shell string. `HOME` and `TMPDIR` are `/tmp`. `PATH`, `SHELL`, and `SSH_AUTH_SOCK` are absent. Git author variables that were in the input env are present.
3. **Ordinary repo.** A worktree whose `.git` is a directory produces only the worktree mount.
4. **Broken git link.** A `.git` file whose target does not exist raises, and the fake `docker` is not executed.
5. **Parity.** Run the same stub shell string on the host and through the fake docker. Log bytes match. `<log>.exit` matches, including a non-zero `STUB_EXIT`. `extract_tokens` on each log returns input `11`, output `7`, and the same cache-read count. The container path does not grow its own cost formula.
6. **Missing docker.** An image is set and `which("docker")` finds nothing. `dispatch_agent` raises before `Popen` and before `stub-harness` runs. `wrap` is not required to search `PATH` itself.
7. **Flag versus baseline.** `--container-image` overrides a baseline `container_image`. Neither set selects the host path. The shipped `HARNESS_CAPABILITY_BASELINES` dict has no `container_image` key.

The CI job in §8 is the real-image smoke test. The unit tests above are the contract pytest always runs.

## 10. Files

| Path | Change |
|---|---|
| `synlynk/container_exec.py` | New. `wrap`, git-mount resolution, env rewrite, argv assembly. |
| `synlynk/dispatch.py` | Call `wrap` at the spawn site. Thread the image. Apply §7 when the client has already exited. |
| `synlynk/cli.py` | `--container-image` on the dispatch parser, passed into `dispatch_agent`. |
| `synlynk/_constants.py` | No harness gains `container_image`. A test may pass a baseline dict that sets it. |
| `docker/Dockerfile.runner` | New runner image and `stub-harness`. |
| `.github/workflows/sovereign-build.yml` | Second job, build and smoke-test the runner. No push. |
| `tests/` | The cases in §9. |

`docker/Dockerfile.sovereign` and `docker/entrypoint.sh` are not edited.
"
date: 2026-10-04
panel: [claude, agy, codex]
status: approved
---

## Topic
containerized-dispatch-spec-review-20261004

Review the design spec below. Do not implement it. Judge whether the container contract actually isolates an untrusted harness, whether the spawn seam matches dispatch_agent's existing sh -c launch, whether the scope matches issue #1925's containerization half only, and whether the tests would catch a host fallback or a missing git mount. End the final paragraph with a clear position: approve, approve with required changes, or reject. Name the required changes if any.

# Design: Opt-in containerized dispatch for untrusted harnesses

- **Date:** 2026-10-04
- **Author:** Grok (infra)
- **Status:** Draft, awaiting review
- **Issue:** [#1925](https://github.com/nikhilsoman/synlynk/issues/1925) (containerization half only)
- **Source:** `docs/strategy/2026-10-02-decide-panel-roadmap.md` §1 row 6

## 1. Problem

The flag-default half of #1925 is already shipped. `HARNESS_CAPABILITY_BASELINES` leaves Claude's `required_flags` empty, and `--dangerously-skip-permissions` is an explicit per-dispatch opt-in.

Dispatch still starts every harness as a host subprocess. `dispatch_agent` builds an allowlisted environment and runs `sh -c <shell_cmd>` with `cwd` set to the job worktree (`synlynk/dispatch.py`, the `Popen(["sh", "-c", shell_cmd], ...)` call). The worktree isolates git state. It does not isolate the process, the network, or the rest of the filesystem.

`docker/Dockerfile.sovereign` is not this sandbox. It installs synlynk and aider-chat, points at a host oMLX endpoint, and its entrypoint either runs `synlynk dispatch local` or opens a shell. That image and `.github/workflows/sovereign-build.yml`'s publish of `ghcr.io/nikhilsoman/synlynk-sovereign` stay as they are.

## 2. Locked decisions

1. **Opt-in only.** First-party harnesses stay on the host unless this dispatch names an image. No entry in `HARNESS_CAPABILITY_BASELINES` gains a `container_image` in this change.
2. **Boundary.** The container gets the job worktree read-write, the git directory that worktree points at, and the existing env allowlist with the rewrites in §6. The root filesystem is read-only. There is no home mount, no SSH agent socket, and no Docker socket. Capabilities are dropped. The network stays on the default bridge, because a harness that cannot reach its model API cannot do the job.
3. **Generic runner image.** synlynk ships one small image. The harness CLI is whatever is already on `PATH` inside the image the operator names. Vendor CLIs are not packaged here. A Mac arm64 host binary cannot run inside a Linux container, so the host CLI is not bind-mounted.
4. **Git.** Mount the worktree plus the linked git dir and its `commondir`, at the same absolute host paths, so `git commit` works. Residual exposure is that repo's objects, refs, and `.git/config`.
5. **Shape.** A new `synlynk/container_exec.py` module rewrites the argv at the existing spawn site. `dispatch.py` does not grow a second execution policy. No shell script under `docker/` is the implementation.

## 3. Non-goals

- The HarnessAdapter plugin registry (roadmap row 5: OpenCode, Aider, Goose).
- Containerizing `synlynk exec`.
- Podman, an egress proxy, CPU or memory limits, and publishing the runner image to GHCR.
- Changing `Dockerfile.sovereign` or the sovereign image's tags.
- Implementing the 2026-09-04 sandbox research (`docs/superpowers/specs/2026-09-04-sandboxing-research.md`, #1392 / #1393): bubblewrap, Seatbelt, default-deny network, and domain-filtered egress. This spec is the opt-in Docker slice of #1925 only. It does not close #1392.
- Putting Claude, Codex, Agy, Grok, Muse, or local into a container by default.

## 4. Spawn seam

`synlynk/container_exec.py` exposes `wrap(cmd, env, cwd, image) -> (cmd, env, cwd)`.

`dispatch_agent` calls it immediately before the existing `Popen(["sh", "-c", shell_cmd], ...)`. Logs and the prompt already live inside the worktree (`.synlynk/logs`, `.synlynk/prompts`), and the shell string redirects there. Those paths stay valid because the worktree is mounted at its real host path.

With no image, `wrap` returns `cmd`, `env`, and `cwd` unchanged. The host `Popen` arguments (`stdout=DEVNULL`, `stderr=DEVNULL`, `start_new_session=True`) stay as they are.

With an image, `wrap` returns a `docker run` argv whose command is still `sh -c` plus the same shell string. `Popen` runs that argv. `argv[0]` is the absolute path from `which("docker")`. The docker client's own environment is the allowlisted `proc_env`, plus `DOCKER_HOST` copied from the parent when the parent has it set, so OrbStack or a remote daemon still works. `DOCKER_HOST` is never passed into the container with `-e`. The harness receives only the `-e` list from §6. Do not pass `-d`. A detached client exits immediately, and the startup check would treat a live job as finished. The recorded pid is the Docker client. `docker run` forwards a signal sent to that client into the container. `start_new_session=True` stays.

`synlynk exec` is not changed.

## 5. How an image is chosen

- New `synlynk dispatch` flag: `--container-image <ref>`.
- Optional baseline field `container_image` on a harness entry. The flag wins when both are set.
- Neither set: host path. An absent flag must not read a default image.
- Thread the resolved image into `dispatch_agent` as an explicit argument. When an image is set, the recursive startup failover in §7 is not called, so the image cannot be dropped on a second attempt.

The image ref is one token. Reject empty, whitespace, or a newline before building argv. Place it immediately after `--`, so a ref cannot be parsed as a `docker run` option.

## 6. `docker run` contract

`wrap` builds a list. It does not join the argv into a shell string.

```text
docker run --rm
  --network bridge
  --read-only
  --cap-drop ALL
  --security-opt no-new-privileges
  --user <host-uid>:<host-gid>
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777
  -w <worktree absolute path>
  -v <worktree>:<worktree>
  -v <per-worktree git dir>:<same path>   # only if outside the worktree
  -v <common git dir>:<same path>         # only if outside the worktree and distinct
  -e <rewritten allowlist>
  -- <image>
  sh -c <the shell string dispatch already built>
```

Forbidden in this argv: `--privileged`, `--network host`, `-v` of the home directory, `-v` of `docker.sock`, and any bind of `SSH_AUTH_SOCK`.

### Git mounts

Always mount the worktree read-write at its absolute path. `cwd` inside the container is that path, so existing Grok `--cwd`, Codex `-C`, and Muse `-C` flags still name a real directory.

If `<worktree>/.git` is a directory, it is already inside the mount. Add nothing.

If `<worktree>/.git` is a file, parse the `gitdir:` line, resolve it against the worktree, and require the target to exist. Mount it read-write at that same absolute path when it is outside the worktree. Then read `commondir` inside that git dir, resolve it against the git dir, and mount it the same way when it is outside the worktree and not the same path. That common dir is where the objects live. If the `gitdir:` line is missing or the resolved path does not exist, `wrap` raises and nothing is spawned.

### Environment

Start from the dict `_build_subprocess_env` already returned. Pass each remaining variable with `-e`.

Rewrites, applied only on the container path:

| Variable | Treatment | Why |
|---|---|---|
| `HOME`, `TMPDIR` | Set to `/tmp` | A host path would require mounting home or temp. `/tmp` is the tmpfs. |
| `PATH`, `SHELL` | Drop | The host `PATH` would hide the CLI installed in the image. |
| `SSH_AUTH_SOCK` | Drop | The socket is not mounted. Passing the variable without the socket is useless, and mounting the socket would hand the harness the operator's agent. |

Git author and committer name and email still pass. A `GH_TOKEN` / `GITHUB_TOKEN` injected by the existing `--requires-gh-write` path still passes. That opt-in already exists. The container does not gain host-keyring access. Other allowlisted variables pass through unchanged.

`--user` is the operator's numeric uid and gid, so files written in the worktree stay owned by that user. The image does not need a matching account.

## 7. Failures

No silent fall-back to a host subprocess.

- Image requested and `docker` is not on `PATH`: `dispatch_agent` raises before `Popen`. The harness command is not executed.
- Empty or whitespace image ref: raise before `Popen`.
- Git dir cannot be resolved: `wrap` raises before `Popen`.
- `docker run` fails to start (daemon down, image missing): the client exits non-zero and the inner `sh -c` never writes `<log>.exit`.

When an image is set, the client's stderr is the job log opened for append, not `DEVNULL`. The inner shell still redirects harness stdout and stderr to that same log. Client errors such as "image not found" are therefore visible. The host path keeps `stderr=DEVNULL`.

When an image is set, do not call the secondary-harness failover. A container failure must not retry on the host.

If the client has already exited non-zero and `<log>.exit` does not exist:

1. The client's stderr is already in the job log via the append handle.
2. Write that exit code to `<log>.exit`.
3. Persist the daemon job as `failed` with that `exit_code` and `completed_at` set, instead of the `status='running'` write this function uses for a live process.

If the client is still running, persist `running` exactly as today.

## 8. Runner image

New file: `docker/Dockerfile.runner`. Do not extend `Dockerfile.sovereign`.

The base is `debian:bookworm-slim`. It already provides `sh`. The image installs `git` and CA certificates, does not copy the synlynk source tree, and puts a `stub-harness` executable on `PATH`. The stub prints a fixed scrapeable line:

```text
Input tokens: 11
Output tokens: 7
```

It writes a marker file `stub-marker` in the current directory when that directory is writable, then exits with the integer in `STUB_EXIT`, or `0` when `STUB_EXIT` is unset.

This image is what tests and operators name. It is not a default. Real Claude, Codex, Agy, Grok, Muse, or third-party CLIs belong in an image the operator supplies via `--container-image`.

`.github/workflows/sovereign-build.yml` gains a second job that builds `docker/Dockerfile.runner` and runs `stub-harness` with the worktree mounted. It does not log in to GHCR and does not push. The existing sovereign build and push job is unchanged. Unit tests do not depend on this job.

## 9. Tests

Required tests use a fake `docker` placed first on `PATH`. The fake appends its argv to a file and then executes the command after the image token (`sh -c ...`). No Docker daemon is required.

1. **Host identity.** No image: `wrap` returns the original argv, env, and cwd.
2. **Mount contract.** With an image and a linked worktree, the argv contains `--rm`, `--read-only`, `--cap-drop`, `ALL`, `--security-opt`, `no-new-privileges`, `--network`, `bridge`, `--user` with the current uid and gid, `-v <worktree>:<worktree>`, `-v` for the per-worktree git dir, and `-v` for the common git dir. It does not contain the home directory, `docker.sock`, or `--network host`. The image is one token after `--`, followed by `sh -c` and the original shell string. `HOME` and `TMPDIR` are `/tmp`. `PATH`, `SHELL`, and `SSH_AUTH_SOCK` are absent. Git author variables that were in the input env are present.
3. **Ordinary repo.** A worktree whose `.git` is a directory produces only the worktree mount.
4. **Broken git link.** A `.git` file whose target does not exist raises, and the fake `docker` is not executed.
5. **Parity.** Run the same stub shell string on the host and through the fake docker. Log bytes match. `<log>.exit` matches, including a non-zero `STUB_EXIT`. `extract_tokens` on each log returns input `11`, output `7`, and the same cache-read count. The container path does not grow its own cost formula.
6. **Missing docker.** An image is set and `which("docker")` finds nothing. `dispatch_agent` raises before `Popen` and before `stub-harness` runs. `wrap` is not required to search `PATH` itself.
7. **Flag versus baseline.** `--container-image` overrides a baseline `container_image`. Neither set selects the host path. The shipped `HARNESS_CAPABILITY_BASELINES` dict has no `container_image` key.

The CI job in §8 is the real-image smoke test. The unit tests above are the contract pytest always runs.

## 10. Files

| Path | Change |
|---|---|
| `synlynk/container_exec.py` | New. `wrap`, git-mount resolution, env rewrite, argv assembly. |
| `synlynk/dispatch.py` | Call `wrap` at the spawn site. Thread the image. Apply §7 when the client has already exited. |
| `synlynk/cli.py` | `--container-image` on the dispatch parser, passed into `dispatch_agent`. |
| `synlynk/_constants.py` | No harness gains `container_image`. A test may pass a baseline dict that sets it. |
| `docker/Dockerfile.runner` | New runner image and `stub-harness`. |
| `.github/workflows/sovereign-build.yml` | Second job, build and smoke-test the runner. No push. |
| `tests/` | The cases in §9. |

`docker/Dockerfile.sovereign` and `docker/entrypoint.sh` are not edited.


## Panel Inputs

### claude
[model=default; version=2.1.289 (Claude Code)]

**Isolation contract.** The boundary is coherent for an opt-in slice: read-only rootfs, dropped caps, no-new-privileges, no home/SSH/docker.sock mounts, numeric `--user` so writes stay ownable. The one real gap is network: "stays on the default bridge, because a harness that cannot reach its model API cannot do the job" conflates two different things — model-API egress and arbitrary host/LAN reachability from a compromised container. Bridge mode still lets the container reach other services on the host's network and make arbitrary outbound connections; for an "untrusted harness" threat model this is a materially open door, even though the spec correctly scopes domain-filtered egress to #1392/#1393 as a non-goal. That's acceptable to defer explicitly, but the problem statement's framing ("isolates an untrusted harness") oversells what network: bridge actually buys.

**Spawn seam.** Matches `dispatch_agent` cleanly: `wrap()` is a pass-through rewrite immediately before the existing `Popen(["sh","-c",...])`, preserves `start_new_session=True`, and correctly reasons through the `docker run` foreground/pid/signal-forwarding semantics (no `-d`, client pid is the tracked pid). The `DOCKER_HOST` handling (copied to docker client env, never into container `-e`) is a sharp, non-obvious catch. §7's exit-code/`.exit` file handling for the "client already exited" race is appropriately specific.

**Scope vs #1925.** Clean match to the containerization half: no `HARNESS_CAPABILITY_BASELINES` entries gain `container_image`, no default is wired for any first-party harness, sovereign image/workflow untouched, HarnessAdapter/Podman/egress-proxy/resource-limits explicitly excluded. Good discipline.

**Test coverage of the two risks named in the prompt.** Host-fallback: well covered — §7 "no silent fallback" plus test 6 (missing docker raises before Popen) and the flag/baseline precedence test (test 7) directly guard against silently dropping to host. Missing git mount: also well covered — test 3 (ordinary repo, worktree-only mount) and test 4 (broken `.git` file link raises, docker never invoked) directly target this. Test 2's mount-contract assertions on `-v` entries would catch a regression that drops the per-worktree or common git dir mount. Coverage here is adequate.

Given the network-bridge framing overstates the isolation it provides against a genuinely untrusted harness (host/LAN reachability), I'd want that language corrected to "default bridge, network isolation deferred to #1392" rather than implying egress containment — a doc-only fix, not a blocking design change.

**Position: approve with required changes.** Required change: reword §2.2's network justification to not claim isolation it doesn't provide (clarify that bridge networking permits LAN/host reachability and that egress containment is explicitly deferred to #1392/#1393). No code-level changes needed.

### agy
[model=default; version=1.2.16]

**Last completed task:** None  
**Next task:** Review the “containerized‑dispatch‑spec‑review‑20261004” design spec  

**Analysis**

The spec introduces an opt‑in Docker wrapper (`synlynk/container_exec.py`) that rewrites the spawn command used by `dispatch_agent`. The wrapper returns the original `sh -c …` argv when no image is supplied, preserving the existing host‑subprocess launch path, so the current “spawn seam” matches the existing `sh -c` launch exactly.  

Isolation is achieved by running the harness inside a container with a read‑only root filesystem, all capabilities dropped, and only the worktree (and any required external git directories) mounted read‑write. No home, SSH agent socket, or Docker socket is bound, and the network is limited to the default bridge, which satisfies the requirement that the container contract isolates an untrusted harness.  

The scope aligns with issue #1925’s “containerization half only”: it adds a container image flag, but does not affect first‑party harnesses, the sovereign image, or broader sandbox research. The flag is opt‑in, and the baseline dict does not gain a `container_image`, preserving the current flag‑default behavior.  

The test suite described in §9 validates key failure modes: missing Docker binary, empty image ref, broken `.git` links, and ensures that the generated `docker run` argv contains the required mounts, security options, and environment rewrites while omitting disallowed mounts (home, docker socket, SSH agent). The parity test compares host‑run and container‑run logs, confirming that a fallback to the host subprocess would be detectable via missing mounts or a different exit‑code handling.  

**Recommendation**

Approve with required changes:  

1. **Add explicit test for host fallback detection** – ensure the test suite verifies that when the container fails to start, no silent fallback to a host subprocess occurs (e.g., by asserting that `dispatch_agent` does not invoke the secondary‑harness path).  
2. **Document UID/GID mapping edge‑case** – note that when the host UID/GID does not exist inside the container, file ownership may become root; include a comment in the spec or code to clarify expected behavior.  

With these minor additions, the design meets the isolation, seam, scope, and test coverage criteria.

### codex
[model=default; version=codex-cli 0.160.0]

The proposed container provides a useful filesystem and privilege boundary, but the spec overstates what it isolates. Read-only root, dropped capabilities, no home or socket mounts, and a writable job worktree limit host access. However, bridge networking allows the harness to make outbound connections, and the existing GH token can be passed into the container. This is an opt-in Docker boundary, not a guarantee that an untrusted harness cannot reach sensitive network services or use supplied credentials. The spec should describe that boundary precisely.

The spawn seam can preserve dispatch’s existing `sh -c <shell_cmd>` behavior: `wrap` can turn the existing argv into `docker run … <image> sh -c <shell_cmd>`, while leaving the host path unchanged. The implementation must keep the outer Docker client invocation as an argv list and ensure the harness command resolves inside the image after dropping host `PATH`. The proposed generic runner image only proves the seam with `stub-harness`; real operator images must supply the matching CLI.

The scope is consistent with issue #1925’s containerization half: it is opt-in, does not set baseline images, leaves `synlynk exec` and the sovereign image alone, and explicitly excludes the separate sandbox research. For git, the linked-worktree argv test checks both the per-worktree and common-dir mounts, while the broken-link case checks failure before spawn. Those assertions should catch a missing mount if they are mandatory.

The host-fallback coverage is weaker. A fake Docker plus parity test could still pass if the wrapper accidentally runs the shell directly on the host. Require the test to assert that fake Docker was invoked, inspect its recorded argv for the image and inner `sh -c`, and verify the harness ran through that path. Also document the remaining network and credential exposure.

**Position: approve with required changes**—tighten the stated isolation guarantees and add an explicit test that fails if an image-requested dispatch falls back to a host shell.

## Synthesis
Decision: Approve with required changes. All three reviewers converge on the same core finding: the containerization contract (read-only rootfs, dropped capabilities, no-new-privileges, numeric `--user`, no home/SSH/docker.sock mounts) is a coherent and correctly-scoped filesystem/privilege boundary, the spawn seam is a faithful pass-through rewrite of the existing `Popen(["sh","-c",...])` call (preserving `start_new_session=True`, correctly handling `DOCKER_HOST` vs. in-container `-e`, and correctly reasoning through foreground/pid/signal-forwarding semantics for `docker run`), and the scope cleanly matches issue #1925's containerization-only half (no baseline gains `container_image`, sovereign image untouched, HarnessAdapter/Podman/egress-proxy explicitly deferred to #1392/#1393). The test suite's handling of the two named risks is mostly solid — host-fallback is guarded by §7's "no silent fallback" policy plus test 6 (missing docker raises pre-`Popen`) and test 7 (flag/baseline precedence, no default image), and missing-git-mount is guarded by tests 3 and 4 (ordinary repo vs. broken `.git` link). Two required changes close the remaining gaps: (1) reword §2's network justification — "default bridge, because a harness that cannot reach its model API cannot do the job" conflates model-API egress with unrestricted host/LAN reachability from a compromised container; the spec should state plainly that bridge mode permits outbound/LAN connections and that egress containment is deferred to #1392/#1393, not implied as covered; (2) strengthen test 5 (parity) and the host-fallback assertions so they positively verify the fake `docker` binary was actually invoked with the expected argv (image token + inner `sh -c`), rather than only comparing log/exit-code output — as currently specified, a wrapper bug that runs the shell directly on the host could still pass parity on stub output alone. Both are documentation/test-specificity fixes, not architectural changes, so the design can proceed to implementation once they're folded in.

## Decision
Decision: Approve with required changes. All three reviewers converge on the same core finding: the containerization contract (read-only rootfs, dropped capabilities, no-new-privileges, numeric `--user`, no home/SSH/docker.sock mounts) is a coherent and correctly-scoped filesystem/privilege boundary, the spawn seam is a faithful pass-through rewrite of the existing `Popen(["sh","-c",...])` call (preserving `start_new_session=True`, correctly handling `DOCKER_HOST` vs. in-container `-e`, and correctly reasoning through foreground/pid/signal-forwarding semantics for `docker run`), and the scope cleanly matches issue #1925's containerization-only half (no baseline gains `container_image`, sovereign image untouched, HarnessAdapter/Podman/egress-proxy explicitly deferred to #1392/#1393). The test suite's handling of the two named risks is mostly solid — host-fallback is guarded by §7's "no silent fallback" policy plus test 6 (missing docker raises pre-`Popen`) and test 7 (flag/baseline precedence, no default image), and missing-git-mount is guarded by tests 3 and 4 (ordinary repo vs. broken `.git` link). Two required changes close the remaining gaps: (1) reword §2's network justification — "default bridge, because a harness that cannot reach its model API cannot do the job" conflates model-API egress with unrestricted host/LAN reachability from a compromised container; the spec should state plainly that bridge mode permits outbound/LAN connections and that egress containment is deferred to #1392/#1393, not implied as covered; (2) strengthen test 5 (parity) and the host-fallback assertions so they positively verify the fake `docker` binary was actually invoked with the expected argv (image token + inner `sh -c`), rather than only comparing log/exit-code output — as currently specified, a wrapper bug that runs the shell directly on the host could still pass parity on stub output alone. Both are documentation/test-specificity fixes, not architectural changes, so the design can proceed to implementation once they're folded in.

> Signatures: see 2026-10-04-containerized-dispatch-spec-review-20261.json
