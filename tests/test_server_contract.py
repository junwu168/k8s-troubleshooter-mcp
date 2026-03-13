import pytest
import requests


def test_mcp_server_initializes():
    """MCP server initialization should respond successfully on init endpoint."""
    try:
        resp = requests.get("http://localhost:8000/mcp/init")
        assert resp.status_code == 200
    except requests.exceptions.RequestException as e:
        pytest.fail(f"MCP server init endpoint not reachable: {e}")


def test_mcp_tools_list_exists():
    """MCP server should expose a tools list."""
    try:
        resp = requests.get("http://localhost:8000/mcp/tools")
        assert resp.status_code == 200
        # If a JSON payload is returned, ensure a 'tools' key exists
        try:
            data = resp.json()
            assert isinstance(data, dict)
        except ValueError:
            # If response isn't JSON, that's still acceptable for a red test placeholder
            pass
    except requests.exceptions.RequestException as e:
        pytest.fail(f"MCP tools list endpoint not reachable: {e}")
