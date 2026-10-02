import difflib
import os
import subprocess

class RegenConflictError(Exception):
    pass

def check_regen_write_guard(
    filepath: str, new_content: str, *, source_path: str = None
) -> None:
    """
    Reject destructive regeneration against a committed origin/main baseline.

    Generated docs are also written inside isolated test projects and temporary
    working copies. Those paths have no committed upstream baseline, so they
    must not be compared with their local contents and treated as conflicts.
    """
    absolute_path = os.path.realpath(filepath)

    # A generated document backed by a database outside this repository is an
    # isolated working copy (the pattern used by the test harness). It cannot
    # represent a cross-process write against this repository's baseline.
    if source_path is not None:
        source_path = os.path.realpath(source_path)
        source_dir = source_path if os.path.isdir(source_path) else os.path.dirname(source_path)
        try:
            source_root = subprocess.check_output(
                ["git", "-C", source_dir, "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            target_root = subprocess.check_output(
                ["git", "-C", os.path.dirname(absolute_path), "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if os.path.realpath(source_root) != os.path.realpath(target_root):
                return
        except Exception:
            return

    # Resolve the repository from the target path, rather than from process cwd.
    # Callers commonly chdir into an isolated fixture before regenerating docs.
    try:
        git_root = subprocess.check_output(
            ["git", "-C", os.path.dirname(absolute_path), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return

    git_root = os.path.realpath(git_root)
    try:
        rel_path = os.path.relpath(absolute_path, git_root)
        if rel_path == os.pardir or rel_path.startswith(os.pardir + os.sep):
            return
    except ValueError:
        return

    # Only a tracked file with a readable remote baseline represents a real
    # cross-process write-through conflict. Never fall back to the local file:
    # that is precisely the isolated test-harness path this guard must allow.
    try:
        subprocess.check_output(
            ["git", "-C", git_root, "ls-files", "--error-unmatch", "--", rel_path],
            stderr=subprocess.DEVNULL,
        )
        old_content = subprocess.check_output(
            ["git", "-C", git_root, "show", f"origin/main:{rel_path}"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return

    if old_content is None:
        return

    diff = list(difflib.ndiff(old_content.splitlines(), new_content.splitlines()))
    removed = [l for l in diff if l.startswith('- ')]
    sig = [l for l in removed if l[2:].strip()]
    if sig:
        raise RegenConflictError(
            f"Regen bug write guard prevented destructive write to {filepath}.\n"
            f"Conflict: would remove or replace {len(sig)} existing lines.\n"
            f"Sample removed line: {sig[0][2:80]!r}\n"
            f"Please run `git fetch` and merge origin/main to ingest upstream state, "
            f"or manually resolve the data conflict."
        )
