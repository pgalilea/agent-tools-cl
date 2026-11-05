import asyncio

import pytest
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from agent_tools_cl.core import AllFailedError
from agent_tools_cl.mcp import main as server
from agent_tools_cl.mcp import security


def test_tools_return_service_values(monkeypatch):
    values = {
        "get_uf": 40_000.0,
        "get_utm": 70_000.0,
        "get_dollar": 950.0,
        "get_copper": 4.25,
        "get_euro": 1_100.0,
        "get_tpm": 4.5,
        "get_ipc": 0.4,
        "get_imacec": 0.2,
        "get_unemployment": 9.8,
    }
    for name, value in values.items():

        async def stub(_value=value):
            return _value

        monkeypatch.setattr(server, name, stub)

    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "uf",
        "utm",
        "dollar",
        "copper",
        "euro",
        "tpm",
        "ipc",
        "imacec",
        "unemployment",
        "holidays",
    }

    result = asyncio.run(server.mcp.call_tool("copper", {}))
    assert result.structured_content == {"result": 4.25}


def test_failed_sources_become_tool_error(monkeypatch):
    async def fail():
        raise AllFailedError([ValueError("source down")])

    monkeypatch.setattr(server, "get_uf", fail)
    with pytest.raises(ToolError):
        asyncio.run(server.mcp.call_tool("uf", {}))


def test_api_token_header_validation(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "s3cret")

    verifier = security.validate_token()
    assert isinstance(verifier, security.HeaderTokenVerifier)

    assert asyncio.run(verifier.verify_token("wrong")) is None
    token = asyncio.run(verifier.verify_token("s3cret"))
    assert token is not None
    assert token.token == "s3cret"


def test_refuses_non_loopback_bind_without_auth(monkeypatch):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    assert server.mcp.auth is None
    with pytest.raises(SystemExit):
        server.main()


def test_health_route():
    response = TestClient(server.mcp.http_app()).get("/health")
    assert response.status_code == 200
    assert response.text == "ok"
