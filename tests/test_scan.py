import synlynk
import synlynk.scan as scan


def test_shared_agent_file_is_registered_and_detected(tmp_path):
    assert "AGENTS.md" in synlynk._AGENT_FILE_NAMES
    assert "AGENTS.md" in scan._AGENT_FILE_NAMES

    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("# Shared instructions\n")

    result = scan._scan_repo_for_docs(str(tmp_path))

    assert result["agent_files"]["AGENTS.md"] == str(agents_file)
