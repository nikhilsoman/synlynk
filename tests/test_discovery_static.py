import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.discovery import scan_workspace_static


def test_scan_workspace_static_fastapi_and_pydantic(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "med-ai"\ndependencies = ["fastapi>=0.100.0", "pydantic>=2.0"]\n')

    app_py = tmp_path / "app.py"
    app_py.write_text("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
""")

    result = scan_workspace_static(str(tmp_path))
    assert result["scan_time_ms"] < 10000
    assert "FastAPI" in result["physical"]["frameworks"]
    assert "Python" in result["physical"]["languages"]
    assert len(result["logical"]["routes"]) >= 1
    assert result["logical"]["routes"][0]["path"] == "/health"
