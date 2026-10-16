# Isolated local-harness qualification

This is the isolation contract for the benchmark and pilot work in #2349. It
qualifies a local oMLX model with Aider without exposing a developer worktree
to the normal Docker bridge network.

## Network design

`aider` is connected only to the internal `qualification` Docker network. Its
only peer is `omlx-relay`; the relay alone also has a bridge attachment, and
is hard-coded to forward TCP port 8000 to `host.docker.internal:8000`.

This is necessary because oMLX is a native Apple-Silicon service rather than a
container image. It is equivalent to a dedicated oMLX container from Aider's
perspective: Aider has no route to the Internet, DNS resolution outside the
internal service is unavailable, and it cannot reach the host directly.

## Setup

Start the relay once after oMLX is serving on port 8000:

```sh
docker compose -f docker/local-qualification.compose.yaml up -d omlx-relay
```

Build and run Aider only against a disposable Git worktree. The caller must
export `OPENAI_API_KEY` and set `QUALIFICATION_WORKTREE` to that worktree:

```sh
export QUALIFICATION_WORKTREE="$(mktemp -d /private/tmp/synlynk-local-qualification.XXXXXX)"
git -C "$QUALIFICATION_WORKTREE" init
docker compose -f docker/local-qualification.compose.yaml run --rm aider \
  --model openai/Qwen2.5-Coder-14B-Instruct-4bit \
  --openai-api-base http://omlx:8000/v1 \
  --edit-format whole --no-stream --no-auto-commits --yes-always \
  --no-auto-lint --no-auto-test --map-tokens 0 \
  --no-check-update --no-analytics --no-show-model-warnings --no-gitignore
```

Do not mount a real project worktree, the user home directory, cloud
credentials, SSH agent, or GitHub token into this container. The model's
oMLX key is the only credential passed to Aider.

## Verified baseline

On 2026-10-16, Qwen2.5-Coder-14B-Instruct-4bit applied a requested single-file
Python edit through Aider 0.86.2 using the `whole` edit format. Direct model
access and the edit were both made through the internal relay. Gemma 4 passed
the service probe but did not complete the equivalent Aider edit, so it is not
eligible for coding dispatches yet.
