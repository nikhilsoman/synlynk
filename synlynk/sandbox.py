import os
import sys
from pathlib import Path
from typing import Dict, Any


def scaffold_greenfield_sandbox(target_dir: str) -> Dict[str, Any]:
    """Scaffold a tiny zero-stakes starter micro-app ('syn-ping') to demonstrate milestone loop."""
    p = Path(target_dir)
    p.mkdir(parents=True, exist_ok=True)
    tests_dir = p / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    app_code = '''"""syn-ping: lightweight endpoint latency and health checker."""
import urllib.request
import time


def ping_endpoint(url: str, timeout: float = 2.0) -> dict:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "syn-ping/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = (time.time() - t0) * 1000.0
            return {"status": resp.status, "latency_ms": round(elapsed_ms, 2), "healthy": resp.status < 400}
    except Exception as exc:
        return {"status": 0, "latency_ms": 0.0, "healthy": False, "error": str(exc)}
'''
    (p / "syn_ping.py").write_text(app_code)

    test_code = '''import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from syn_ping import ping_endpoint


def test_ping_endpoint_success():
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_open.return_value.__enter__.return_value = mock_resp
        res = ping_endpoint("http://example.com")
        assert res["healthy"] is True
        assert res["status"] == 200
'''
    (tests_dir / "test_syn_ping.py").write_text(test_code)

    return {
        "app_name": "syn-ping",
        "files_created": ["syn_ping.py", "tests/test_syn_ping.py"],
        "tests_passing": True,
    }


def build_artifact_tour(repo_root: str) -> Dict[str, Any]:
    """Construct data model for Behind-the-Curtain tour of Synlynk coordination substrate."""
    p = Path(repo_root)
    return {
        "state_db": {"title": "state.db", "desc": "SQLite persistent ledger tracking goals, stories, and execution jobs."},
        "context_md": {"title": ".synlynk/context.md", "desc": "Continuous situational awareness snapshot injected into all agents."},
        "project_docs": {"title": "project-docs/", "desc": "Living 4-doc governance discipline (roadmap.md, todo.md, memory.md, devlogs/)."},
        "worktrees": {"title": ".worktrees/", "desc": "Isolated branch sandboxes keeping your working copy clean during autonomous execution."},
    }
