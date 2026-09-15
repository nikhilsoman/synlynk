import pytest
from synlynk.tool_installer import is_tool_available, install_tool, RECOMMENDED_TOOLS


def test_recommended_tools_registry():
    assert "graphify" in RECOMMENDED_TOOLS
    entry = RECOMMENDED_TOOLS["graphify"]
    assert entry["package"] == "graphifyy"
    assert entry["license"] == "Apache-2.0"
    assert "token reduction" in entry["description"].lower()


def test_is_tool_available_false_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert is_tool_available("graphify") is False


def test_is_tool_available_true_when_present(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/graphify")
    assert is_tool_available("graphify") is True


def test_install_tool_invokes_uv_or_pipx(monkeypatch):
    invoked = []

    def mock_run(cmd, capture_output, text, check):
        invoked.append(cmd)
        class Res:
            returncode = 0
            stdout = "Installed graphifyy"
        return Res()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/uv" if name == "uv" else None)
    monkeypatch.setattr("subprocess.run", mock_run)

    success = install_tool("graphify")
    assert success is True
    assert len(invoked) == 1
    assert invoked[0] == ["uv", "tool", "install", "graphifyy"]
