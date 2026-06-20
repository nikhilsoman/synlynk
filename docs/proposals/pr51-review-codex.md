# PR #51 Code Review — Codex

**Findings**
1. High - The Codex baseline is internally inconsistent and unsafe for write-capable dispatches in [`bin/synlynk.py`](/Users/nikhilsoman/dev/synlynk/.worktrees/fix+codex-headless-dispatch/bin/synlynk.py#L377). `-s read-only` is not a good default if the dispatched task is expected to edit files, because it prevents model-generated shell writes. More importantly, `--dangerously-bypass-approvals-and-sandbox` does not merely suppress prompts: I verified via `codex exec --help` that it means “execute commands without sandboxing,” with the CLI explicitly warning it is “EXTREMELY DANGEROUS” and intended only for environments that are already externally sandboxed. So the effective blast radius is full host/user access, not “safe unattended dispatch.” If the goal is file-writing dispatch, this should be `workspace-write` at minimum, and the bypass flag should be reserved for a separate externally-sandboxed path.
2. Medium - The new test in [`tests/test_synlynk.py`](/Users/nikhilsoman/dev/synlynk/.worktrees/fix+codex-headless-dispatch/tests/test_synlynk.py#L1519) only asserts substring presence in the constructed shell command. That proves the string was assembled, but not that the dispatch actually works in a non-TTY execution path. It will miss regressions in argv ordering, stdin wiring, shell quoting, or a command that still fails at runtime. A stronger test would assert the exact argv vector built for `sh -c`, and ideally add a minimal smoke test with a stub `codex` binary to confirm stdin-driven non-interactive execution succeeds.

**Verdict**
- Request changes.
- Quality score: `4/10`.

The fix likely unblocks headless Codex dispatch, but the sandbox choice is too risky for a default, and the test only covers string construction, not behavior.
tokens used
29,239
