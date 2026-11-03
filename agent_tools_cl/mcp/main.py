"""MCP server exposing Chilean financial indicators (UF, UTM, dólar, copper).

Run: uv run python -m agent_tools_cl.mcp.main
(HTTP transport on http://127.0.0.1:8000/mcp)

Security is opt-in via environment variables:

    MCP_HOST                    bind address (default 127.0.0.1, loopback only)
    MCP_PORT                    bind port (default 8000)
    MCP_ALLOWED_HOSTS           comma-separated extra Host header allowlist
    MCP_ALLOWED_ORIGINS         comma-separated extra browser Origin allowlist
    MCP_API_TOKEN               static bearer token; enables header validation
    MCP_JWKS_URI                enables JWT auth; JWKS endpoint of your IdP
    MCP_JWT_ISSUER              expected ``iss``
    MCP_JWT_AUDIENCE            expected ``aud``
    MCP_JWT_ALGORITHM           signing algorithm (default RS256)
    MCP_REQUIRED_SCOPES         comma-separated scopes every token must carry
    MCP_AUTH_SERVER             authorization server URL; advertises RFC 9728 metadata
    MCP_PUBLIC_URL              public base URL of this server (required with auth server)

``MCP_API_TOKEN`` wins over ``MCP_JWKS_URI``. Without either the server starts
unauthenticated, which is only safe because it binds to loopback. Put TLS in
front (reverse proxy) and set HSTS there; this app cannot know the public scheme.
"""

import os
from collections.abc import Awaitable, Callable

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from agent_tools_cl.core import AllFailedError
from agent_tools_cl.mcp.security import get_csv_env, validate_token
from agent_tools_cl.services.financial import get_copper, get_dollar, get_uf, get_utm


async def try_tool(getter: Callable[[], Awaitable[float]]) -> float:
    try:
        return await getter()
    except AllFailedError as e:
        raise ToolError(f"no valid source: {e}") from e


mcp = FastMCP(
    name="agent-tools-cl",
    instructions=(
        "Chilean financial indicators. uf and utm are in CLP; dollar is CLP per "
        "USD; copper is USD per pound. Values are live-scraped and validated."
    ),
    auth=validate_token(),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    """Liveness probe; intentionally unauthenticated and opaque."""
    return PlainTextResponse("ok")


@mcp.tool
async def uf() -> float:
    """Latest validated UF value in CLP."""
    return await try_tool(get_uf)


@mcp.tool
async def utm() -> float:
    """Latest validated UTM value in CLP."""
    return await try_tool(get_utm)


@mcp.tool
async def dollar() -> float:
    """Latest validated US dollar value in CLP."""
    return await try_tool(get_dollar)


@mcp.tool
async def copper() -> float:
    """Latest validated copper price in USD per pound."""
    return await try_tool(get_copper)


def main() -> None:
    host = os.getenv("MCP_HOST", "127.0.0.1")

    # just in case
    if mcp.auth is None and host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(
            "refusing non-loopback bind without auth: set MCP_API_TOKEN or MCP_JWKS_URI"
        )

    mcp.run(
        transport="http",
        host=host,
        port=int(os.getenv("MCP_PORT", "8000")),
        allowed_hosts=get_csv_env("MCP_ALLOWED_HOSTS"),
        allowed_origins=get_csv_env("MCP_ALLOWED_ORIGINS"),
    )


if __name__ == "__main__":
    main()
