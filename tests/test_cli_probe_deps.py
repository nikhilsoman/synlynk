import os
from pathlib import Path
import subprocess
import sys


def _fake_command(directory: Path, name: str, version: str, auth: bool = False) -> None:
    body = f"#!/bin/sh\nif [ \"$1\" = \"auth\" ]; then\n  echo {'authenticated' if auth else 'not authenticated'}\nelse\n  echo '{version}'\nfi\n"
    path = directory / name
    path.write_text(body)
    path.chmod(0o755)


def test_probe_deps_invokes_real_cli_entry_point(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, version in {
        "git": "git version 2.44.0",
        "python": "Python 3.12.0",
        "gh": "gh version 2.45.0",
        "pytest": "pytest 8.0.0",
        "graphify": "graphify 0.1.0",
    }.items():
        _fake_command(bin_dir, name, version)
    _fake_command(bin_dir, "codex", "codex 1.2.3", auth=True)

    env = os.environ.copy()
    env.update({
        "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        "SYNLYNK_CLI_ENTRYPOINT": "1",
        "OPENAI_API_KEY": "test-key",
    })
    result = subprocess.run(
        [sys.executable, "-m", "synlynk", "probe", "--deps", "--harness", "codex"],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "dependency/harness" in result.stdout
    assert "graphify" in result.stdout
    assert "codex" in result.stdout
    assert "verified" in result.stdout
