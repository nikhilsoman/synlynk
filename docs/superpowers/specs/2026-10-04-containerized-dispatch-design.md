# Design: Opt-in containerized dispatch for untrusted harnesses

- **Date:** 2026-10-04
- **Author:** Grok (infra)
- **Status:** Approved for implementation. Panel `dec-ff9a9005` required changes are folded in.
- **Issue:** [#1925](https://github.com/nikhilsoman/synlynk/issues/1925) (containerization half only)
- **Source:** `docs/strategy/2026-10-02-decide-panel-roadmap.md` §1 row 6

## 1. Problem

The flag-default half of #1925 is already shipped. `HARNESS_CAPABILITY_BASELINES` leaves Claude's `required_flags` empty, and `--dangerously-skip-permissions` is an explicit per-dispatch opt-in.

Dispatch still starts every harness as a host subprocess. `dispatch_agent` builds an allowlisted environment and runs `sh -c <shell_cmd>` with `cwd` set to the job worktree (`synlynk/dispatch.py`, the `Popen(["sh", "-c", shell_cmd], ...)` call). The worktree isolates git state. It does not isolate the process, the network, or the rest of the filesystem.

`docker/Dockerfile.sovereign` is not this sandbox. It installs synlynk and aider-chat, points at a host oMLX endpoint, and its entrypoint either runs `synlynk dispatch local` or opens a shell. That image and `.github/workflows/sovereign-build.yml`'s publish of `ghcr.io/nikhilsoman/synlynk-sovereign` stay as they are.

## 2. Locked decisions

1. **Opt-in only.** First-party harnesses stay on the host unless this dispatch names an image. No entry in `HARNESS_CAPABILITY_BASELINES` gains a `container_image` in this change.
2. **Boundary.** The container gets the job worktree read-write, the git directory that worktree points at, and the existing env allowlist with the rewrites in §6. The root filesystem is read-only. There is no home mount, no SSH agent socket, and no Docker socket. Capabilities are dropped. The network is Docker's default bridge. Bridge mode is not a network sandbox: the container can open outbound connections and reach LAN addresses, which is what lets a harness call its model API. Domain-filtered egress and default-deny networking stay deferred to #1392 / #1393. A `GH_TOKEN` passed through `--requires-gh-write` is inside that container and can be used over that open network. That is the existing opt-in, not a new credential mount, and it is not host-keyring access.
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

`--network bridge` is the default bridge, not an egress policy. It allows outbound and LAN connections. It does not allow `--network host`. Egress containment is out of scope (§3).

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

Git author and committer name and email still pass. A `GH_TOKEN` / `GITHUB_TOKEN` injected by the existing `--requires-gh-write` path still passes, and because bridge networking is unrestricted the process inside the container can present that token to GitHub. The container does not gain host-keyring access. Other allowlisted variables pass through unchanged.

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
5. **Parity, through the fake docker.** Run the same stub shell string on the host and through the fake docker. The test fails unless the fake `docker` was executed and its recorded argv contains the image token and the inner `sh -c` plus the original shell string. Matching log bytes and exit codes alone are not a pass: a wrapper that runs `sh -c` on the host and never execs the fake `docker` must fail. When the fake was invoked, log bytes match, `<log>.exit` matches including a non-zero `STUB_EXIT`, and `extract_tokens` on each log returns input `11`, output `7`, and the same cache-read count. The container path does not grow its own cost formula.
6. **Missing docker.** An image is set and `which("docker")` finds nothing. `dispatch_agent` raises before `Popen` and before `stub-harness` runs. `wrap` is not required to search `PATH` itself. The secondary-harness failover is not called.
7. **Flag versus baseline.** `--container-image` overrides a baseline `container_image`. Neither set selects the host path. The shipped `HARNESS_CAPABILITY_BASELINES` dict has no `container_image` key.
8. **No host failover when the client dies.** The image is set and the fake `docker` exits non-zero without executing the inner shell, so `<log>.exit` was not written by `sh -c`. Dispatch writes that client exit code to `<log>.exit`, records the job failed, and does not call the secondary harness. The stub harness binary is not executed on the host.

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
