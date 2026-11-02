import hmac
import os
from typing import TYPE_CHECKING

from fastmcp.server.auth import AccessToken, TokenVerifier

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider


class HeaderTokenVerifier(TokenVerifier):
    """Accept ``Authorization: Bearer <token>`` when it matches a static secret.

    FastMCP extracts the header, calls this verifier before routing, and turns
    ``None`` into a spec-compliant 401 with ``WWW-Authenticate``.
    """

    def __init__(self, expected: str) -> None:
        super().__init__()
        self._expected = expected

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._expected):
            return None
        return AccessToken(token=token, client_id="api-token", scopes=[])


def get_csv_env(name: str) -> list[str] | None:
    """Parse a comma-separated environment variable into stripped tokens.

    Empty or missing values become ``None`` so FastMCP can apply its defaults
    (for example the loopback Host allowlist).

    Args:
        name: Environment variable to read.

    Returns:
        Non-empty tokens, or ``None`` if the variable is unset or blank.
    """
    values = [v.strip() for v in os.getenv(name, "").split(",") if v.strip()]
    return values or None


def _static_token_auth() -> "AuthProvider | None":
    """Static bearer validation from ``MCP_API_TOKEN``, or ``None`` if unset."""

    api_token = os.getenv("MCP_API_TOKEN")
    return HeaderTokenVerifier(api_token) if api_token else None


def _remote_auth() -> "AuthProvider | None":
    """JWT validation from ``MCP_JWKS_URI``, or ``None`` if unset.

    With ``MCP_AUTH_SERVER`` the verifier is wrapped in ``RemoteAuthProvider`` so
    the server advertises RFC 9728 protected-resource metadata. Local imports
    keep the heavy JWT dependencies out of the default path.
    """

    jwks_uri = os.getenv("MCP_JWKS_URI")
    if not jwks_uri:
        return None

    from fastmcp.server.auth import JWTVerifier, RemoteAuthProvider
    from pydantic import AnyHttpUrl

    verifier = JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=os.getenv("MCP_JWT_ISSUER"),
        audience=os.getenv("MCP_JWT_AUDIENCE"),
        algorithm=os.getenv("MCP_JWT_ALGORITHM", "RS256"),
        required_scopes=get_csv_env("MCP_REQUIRED_SCOPES"),
        base_url=os.getenv("MCP_PUBLIC_URL"),
    )

    auth_server = os.getenv("MCP_AUTH_SERVER")
    if not auth_server:
        return verifier

    public_url = os.getenv("MCP_PUBLIC_URL")
    if not public_url:
        raise ValueError("MCP_PUBLIC_URL is required when MCP_AUTH_SERVER is set")

    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(auth_server)],
        base_url=public_url,
        resource_name="agent-tools-cl",
    )


def validate_token() -> "AuthProvider | None":
    """Static token wins over remote JWT; ``None`` means unauthenticated."""
    return _static_token_auth() or _remote_auth()
