import os
import subprocess
import difflib

class RegenConflictError(Exception):
    pass

def check_regen_write_guard(filepath: str, new_content: str) -> None:
    """
    Diffs new_content against the current origin/main version (or existing file).
    Raises RegenConflictError if the write would remove or replace existing rows
    beyond a pure append.
    """
    old_content = None
    
    # Try origin/main first if inside a git repo
    try:
        git_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL).decode().strip()
        rel_path = os.path.relpath(filepath, git_root)
        old_content = subprocess.check_output(["git", "show", f"origin/main:{rel_path}"], stderr=subprocess.DEVNULL).decode('utf-8')
    except Exception:
        pass
        
    # Fallback to local file
    if old_content is None and os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                old_content = f.read()
        except Exception:
            pass

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
