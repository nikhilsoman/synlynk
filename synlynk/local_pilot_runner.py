"""Host-side lifecycle for one credential-minimal isolated Aider dispatch."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from synlynk.local_pilot import (
    PILOT_CLASSES,
    find_sensitive_worktree_paths,
    valid_scope_path,
)


class _SecretRedactor:
    """Stream bytes while withholding partial API-key matches between chunks."""

    def __init__(self, secret: bytes, output):
        self.secret = secret
        self.output = output
        self.pending = b""

    def write(self, chunk: bytes) -> None:
        if not self.secret:
            self.output.write(chunk)
            return
        data = (self.pending + chunk).replace(self.secret, b"[REDACTED]")
        limit = max(0, len(data) - len(self.secret) + 1)
        while limit:
            matched_prefix = next(
                (
                    size for size in range(min(len(self.secret) - 1, limit), 0, -1)
                    if data[limit - size:limit] == self.secret[:size]
                ),
                0,
            )
            if not matched_prefix:
                break
            limit -= matched_prefix
        self.output.write(data[:limit])
        self.pending = data[limit:]

    def flush(self) -> None:
        if self.pending:
            self.output.write(self.pending.replace(self.secret, b"[REDACTED]"))
            self.pending = b""
        self.output.flush()


def _run_captured(argv: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(argv, env=env, capture_output=True, check=False)


def _scoped_file_copy(source: str, destination: str, scope_paths: list[str]) -> None:
    """Copy only files explicitly admitted by the declared path scope."""
    source_root = os.path.realpath(source)
    selected = set()
    for pattern in scope_paths:
        if not valid_scope_path(pattern):
            raise RuntimeError("Local Pilot scope contains an unsafe path")
        for candidate in Path(source).glob(pattern):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(source).as_posix()
            if not valid_scope_path(relative):
                raise RuntimeError("Local Pilot scope selected a forbidden state path")
            selected.add(relative)
    if not selected:
        raise RuntimeError("Local Pilot scope did not match a file in the source worktree")

    for relative in sorted(selected):
        src_path = os.path.join(source, relative)
        if not os.path.lexists(src_path):
            continue
        real_source = os.path.realpath(src_path)
        if os.path.commonpath([source_root, real_source]) != source_root:
            raise RuntimeError("source worktree contains a symlink outside its root")
        relpath = PurePosixPath(relative)
        target = os.path.join(destination, *relpath.parts)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.isdir(real_source):
            raise RuntimeError("source worktree contains an unsupported directory symlink")
        shutil.copy2(real_source, target)

    subprocess.run(["git", "init", "--quiet", destination], check=True)
    subprocess.run(["git", "-C", destination, "config", "user.name", "Local Pilot"], check=True)
    subprocess.run(
        ["git", "-C", destination, "config", "user.email", "local-pilot@invalid"], check=True
    )
    subprocess.run(
        ["git", "-C", destination, "config", "core.hooksPath", "/dev/null"], check=True
    )
    subprocess.run(["git", "-C", destination, "add", "--all"], check=True)
    subprocess.run(
        ["git", "-C", destination, "commit", "--quiet", "--allow-empty", "-m", "pilot baseline"],
        check=True,
    )


def _expanded_scope(scratch: str, scope_paths: list[str], *, require_existing: bool) -> list[str]:
    expanded = set()
    for pattern in scope_paths:
        if not valid_scope_path(pattern):
            raise RuntimeError("Local Pilot scope contains an unsafe path")
        matches = [
            path for path in Path(scratch).glob(pattern)
            if path.is_file() and ".git" not in path.relative_to(scratch).parts
        ]
        if not matches and require_existing:
            raise RuntimeError("Local Pilot scope did not match a file in the scratch repository")
        for path in matches:
            expanded.add(path.relative_to(scratch).as_posix())
        if not matches and not any(char in pattern for char in "*?["):
            expanded.add(pattern)
    return sorted(expanded)


def _changed_paths(scratch: str) -> list[str]:
    subprocess.run(["git", "-C", scratch, "add", "--all"], check=True)
    result = subprocess.run(
        ["git", "-C", scratch, "diff", "--cached", "--name-only", "-z", "HEAD"],
        capture_output=True,
        check=True,
    )
    return [path.decode("utf-8", errors="surrogateescape") for path in result.stdout.split(b"\0") if path]


def _within_scope(path: str, patterns: list[str]) -> bool:
    if not valid_scope_path(path):
        return False
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _apply_validated_edits(scratch: str, source: str, paths: list[str]) -> None:
    diff = subprocess.run(
        ["git", "-C", scratch, "diff", "--cached", "--binary", "HEAD"],
        capture_output=True,
        check=True,
    ).stdout
    if not diff:
        raise RuntimeError("Local Pilot edit produced no patch")
    checked = subprocess.run(
        ["git", "-C", source, "apply", "--check", "--"],
        input=diff,
        capture_output=True,
        check=False,
    )
    if checked.returncode != 0:
        raise RuntimeError("Local Pilot patch did not apply cleanly to the disposable job worktree")
    applied = subprocess.run(
        ["git", "-C", source, "apply", "--"],
        input=diff,
        capture_output=True,
        check=False,
    )
    if applied.returncode != 0:
        raise RuntimeError("Local Pilot patch application failed")


def run_isolated_dispatch(
    *,
    repo_root: str,
    source_worktree: str,
    prompt_file: str,
    log_file: str,
    exit_file: str,
    job_id: str,
    pilot_class: str,
    scope_paths: list[str],
    aider_args: list[str],
    env: dict | None = None,
) -> int:
    env = dict(os.environ if env is None else env)
    api_key = env.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for isolated oMLX dispatch")
    if pilot_class not in PILOT_CLASSES or not scope_paths:
        raise RuntimeError("Local Pilot task class and bounded scope are required")
    compose_file = str(Path(repo_root) / "docker" / "local-pilot.compose.yaml")
    prefix = ["docker", "compose", "-f", compose_file, "--project-name", job_id]
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(exit_file).parent.mkdir(parents=True, exist_ok=True)
    pilot_receipt_file = log_file + ".pilot.json"
    receipt = {
        "schema_version": 1,
        "job_id": job_id,
        "pilot_class": pilot_class,
        "scope_paths": scope_paths,
        "changed_paths": [],
        "applied_paths": [],
        "outcome": "setup_failed",
        "exit_code": 1,
        "started_at": time.time(),
    }
    output_code = 1
    child: subprocess.Popen | None = None
    compose_started = False
    scratch_context = tempfile.TemporaryDirectory(
        prefix=".synlynk-local-pilot-", dir=os.path.dirname(source_worktree)
    )
    scratch = scratch_context.name
    log_handle = open(log_file, "wb")
    redactor = _SecretRedactor(api_key.encode("utf-8"), log_handle)

    def stop_child(signum, _frame):
        if child is not None and child.poll() is None:
            child.terminate()
        raise SystemExit(128 + signum)

    previous_handlers = {}
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        previous_handlers[signum] = signal.signal(signum, stop_child)

    try:
        if find_sensitive_worktree_paths(source_worktree):
            raise RuntimeError("source worktree contains credential-like paths")
        _scoped_file_copy(source_worktree, scratch, scope_paths)
        expanded_scope = _expanded_scope(scratch, scope_paths, require_existing=True)
        if not expanded_scope:
            raise RuntimeError("Local Pilot scope resolved to no files")
        env["PILOT_WORKTREE"] = scratch
        compose_started = True  # also clean up partial `up` failures
        relay = _run_captured(prefix + ["up", "--detach", "omlx-relay"], env)
        if relay.returncode != 0:
            redactor.write(relay.stdout + relay.stderr)
            output_code = relay.returncode
            return output_code
        build = _run_captured(prefix + ["build", "aider"], env)
        if build.returncode != 0:
            redactor.write(build.stdout + build.stderr)
            output_code = build.returncode
            return output_code

        scope_flags = []
        flag = "--read" if pilot_class in {
            "test_summary", "test_diagnosis", "codepath_summary", "change_summary"
        } else "--file"
        for path in expanded_scope:
            scope_flags.extend([flag, path])
        invocation_args = list(aider_args)
        # This suppresses optional model warnings; Aider may still attempt its
        # LiteLLM catalog lookup. The isolated container blocks that traffic.
        if "--no-show-model-warnings" not in invocation_args:
            invocation_args.append("--no-show-model-warnings")
        # Keep assistant output unwrapped so task receipts remain machine
        # verifiable, and avoid Aider's shell-command suggestion affordance in
        # this bounded pilot interface.
        for option in ("--no-pretty", "--no-suggest-shell-commands"):
            if option not in invocation_args:
                invocation_args.append(option)
        # Read the complete stdin stream as one Aider message. Without this,
        # Aider's interactive loop interprets each line of Synlynk's context
        # prompt as a separate message and may answer unrelated fragments.
        if "--message-file" not in invocation_args:
            invocation_args.extend(["--message-file", "/dev/stdin"])
        with open(prompt_file, "rb") as prompt_handle:
            child = subprocess.Popen(
                prefix + ["run", "--rm", "--no-deps", "--interactive", "--no-TTY", "aider"]
                + invocation_args + scope_flags,
                env=env,
                stdin=prompt_handle,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            assert child.stdout is not None
            while True:
                chunk = child.stdout.read1(8192)
                if not chunk:
                    break
                redactor.write(chunk)
            output_code = child.wait()

        paths = _changed_paths(scratch)
        receipt["changed_paths"] = paths
        if flag == "--read":
            if paths:
                receipt["outcome"] = "unexpected_write"
                output_code = output_code or 125
            else:
                receipt["outcome"] = "completed_read_only"
        elif not paths:
            receipt["outcome"] = "no_op_edit"
            output_code = output_code or 125
        elif not all(_within_scope(path, scope_paths) for path in paths):
            receipt["outcome"] = "out_of_scope_edit"
            output_code = output_code or 125
        elif output_code == 0:
            _apply_validated_edits(scratch, source_worktree, paths)
            receipt["outcome"] = "validated_scoped_edit_applied"
            receipt["applied_paths"] = paths
        else:
            receipt["outcome"] = "aider_failed_no_changes_applied"
    except Exception as exc:
        redactor.write(("Local Pilot runner failed closed: " + str(exc) + "\n").encode("utf-8"))
        receipt["outcome"] = "runner_failed_closed"
        output_code = output_code or 1
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if compose_started:
            down = _run_captured(prefix + ["down", "--remove-orphans"], env)
            if down.returncode != 0:
                redactor.write(down.stdout + down.stderr)
        redactor.flush()
        log_handle.close()
        receipt["exit_code"] = output_code
        receipt["ended_at"] = time.time()
        Path(pilot_receipt_file).write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        Path(exit_file).write_text(f"{output_code}\n", encoding="utf-8")
        scratch_context.cleanup()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return output_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-worktree", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--exit-file", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--pilot-class", required=True)
    parser.add_argument("--scope-path", action="append", default=[])
    parser.add_argument("aider_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    aider_args = args.aider_args
    if aider_args and aider_args[0] == "--":
        aider_args = aider_args[1:]
    return run_isolated_dispatch(
        repo_root=args.repo_root,
        source_worktree=args.source_worktree,
        prompt_file=args.prompt,
        log_file=args.log,
        exit_file=args.exit_file,
        job_id=args.job_id,
        pilot_class=args.pilot_class,
        scope_paths=args.scope_path,
        aider_args=aider_args,
    )


if __name__ == "__main__":
    sys.exit(main())
