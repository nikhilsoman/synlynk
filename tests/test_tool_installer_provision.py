import pytest
from unittest.mock import patch
from synlynk.tool_installer import RECOMMENDED_TOOLS, provision_ecosystem_tools

def test_recommended_tools_includes_superpowers_and_graphify():
    tools = [t['binary'] for t in RECOMMENDED_TOOLS.values()]
    assert 'graphify' in tools
    assert 'superpowers' in tools
    assert 'gh' in tools

@patch('synlynk.tool_installer.is_tool_available', return_value=False)
@patch('synlynk.tool_installer.install_tool', return_value=False)
def test_provision_ecosystem_tools_non_fatal(mock_install, mock_is_avail):
    # This should not raise an exception, just return a dict with False for the failed install
    result = provision_ecosystem_tools(tools=['non_existent_tool_mock'])
    assert result == {'non_existent_tool_mock': False}
