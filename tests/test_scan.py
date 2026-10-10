import synlynk
import synlynk.scan as scan


def test_grok_agent_file_is_registered_and_detected(tmp_path):
    assert "GROK.md" in synlynk._AGENT_FILE_NAMES
    assert "GROK.md" in scan._AGENT_FILE_NAMES

    grok_file = tmp_path / "GROK.md"
    grok_file.write_text("# Grok instructions\n")

    result = scan._scan_repo_for_docs(str(tmp_path))

    assert result["agent_files"]["GROK.md"] == str(grok_file)
