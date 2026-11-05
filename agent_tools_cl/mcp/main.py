"""MCP server exposing Chilean indicators and public data.

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
from typing import Any, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from agent_tools_cl.core import AllFailedError
from agent_tools_cl.mcp.security import get_csv_env, validate_token
from agent_tools_cl.services.calendar import get_holidays, get_next_holiday
from agent_tools_cl.services.financial import (
    get_copper,
    get_dollar,
    get_euro,
    get_imacec,
    get_ipc,
    get_tpm,
    get_uf,
    get_unemployment,
    get_utm,
)

T = TypeVar("T")


async def try_tool(getter: Callable[..., Awaitable[T]], *args: Any) -> T:
    try:
        # *args for tools with optional arguments
        return await getter(*args)
    except (AllFailedError, ValueError) as e:
        raise ToolError(f"no valid source: {e}") from e


mcp = FastMCP(
    name="agent-tools-cl",
    instructions=(
        "Chilean indicators and public data. uf and utm are in CLP; dollar and "
        "euro are CLP per unit; copper is USD per pound; tpm, ipc, imacec and "
        "unemployment are in percent; air is the latest MP2.5 reading for a "
        "comuna; holidays lists public holidays. Values are live-scraped and "
        "validated."
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


@mcp.tool
async def euro() -> float:
    """Latest validated euro value in CLP."""
    return await try_tool(get_euro)


@mcp.tool
async def tpm() -> float:
    """Latest validated monetary policy rate (TPM) in percent."""
    return await try_tool(get_tpm)


@mcp.tool
async def ipc() -> float:
    """Latest validated IPC monthly variation in percent."""
    return await try_tool(get_ipc)


@mcp.tool
async def imacec() -> float:
    """Latest validated IMACEC variation in percent."""
    return await try_tool(get_imacec)


@mcp.tool
async def unemployment() -> float:
    """Latest validated unemployment rate in percent."""
    return await try_tool(get_unemployment)


@mcp.tool
async def holidays(year: int | None = None) -> list[dict[str, str]]:
    """Chilean public holidays. Without a year: only the next one."""
    if year is None:
        holiday = await try_tool(get_next_holiday)
        return [{"date": holiday.date.isoformat(), "name": holiday.name}]
    return [
        {"date": holiday.date.isoformat(), "name": holiday.name}
        for holiday in await try_tool(get_holidays, year)
    ]


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
