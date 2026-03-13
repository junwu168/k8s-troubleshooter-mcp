from src.server import mcp, settings


def test_fastmcp_uses_application_host_and_port():
    assert mcp.settings.host == settings.HOST
    assert mcp.settings.port == settings.PORT
