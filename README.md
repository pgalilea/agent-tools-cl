# agent-tools-cl

Chilean indicators and public data: 
- **UF**
- **UTM**
- **dollar**
- **euro**
- **copper**
- **TPM**
- **IPC**
- **IMACEC**
- **unemployment**
- **holidays**
as both a **CLI** and an **MCP server**.

Every value is fetched from multiple sources in parallel and validated against sanity bounds and freshness; the first source whose value passes validation wins. If every source fails, the tool exits with an error instead of returning a stale or untrustworthy number.

## Running with uvx

**No installation needed** — run straight from GitHub:

```sh
uvx --from git+https://github.com/pgalilea/agent-tools-cl.git agent-tools-cl <command>
```
For example:
```sh
uvx --from git+https://github.com/pgalilea/agent-tools-cl.git agent-tools-cl financial uf
```

To avoid re-typing, **install it once** as a tool and use the plain command:

```sh
uv tool install git+https://github.com/pgalilea/agent-tools-cl.git
agent-tools-cl --help
```
<br>

Update the tool
```sh
uv tool upgrade agent-tools-cl
```

Uninstall the tool
```sh
uv tool uninstall agent-tools-cl
```

## CLI

All commands output a single bare number (easy to script / pipe) and exit non-zero if every source fails. Require Python ≥ 3.11.

### `financial uf`

Latest validated **UF** value in CLP.

```sh
agent-tools-cl financial uf
# 39663.97
```



### `financial utm`

Latest validated **UTM** value in CLP (monthly indicator).

```sh
agent-tools-cl financial utm
# 74542.0
```



### `financial dollar`

Latest validated **CLP/USD** rate.

```sh
agent-tools-cl financial dollar
# 941.52
```



### `financial copper`

Latest validated **copper price** in USD per pound, printed with 2 decimals.

```sh
agent-tools-cl financial copper
# 4.83
```



### `financial euro`

Latest validated **CLP/EUR** rate.

```sh
agent-tools-cl financial euro
# 1097.72
```



### `financial tpm`

Latest validated **monetary policy rate (TPM)** in percent.

```sh
agent-tools-cl financial tpm
# 4.5
```



### `financial ipc`

Latest validated **IPC monthly variation** in percent.

```sh
agent-tools-cl financial ipc
# 0.4
```



### `financial imacec`

Latest validated **IMACEC variation** in percent.

```sh
agent-tools-cl financial imacec
# 0.2
```



### `financial unemployment`

Latest validated **unemployment rate** in percent.

```sh
agent-tools-cl financial unemployment
# 9.8
```



### `calendar holidays`

Next Chilean public holiday, or every holiday in a year with `--year`.

```sh
agent-tools-cl calendar holidays
# 2026-12-08 Inmaculada Concepción (en 34 días)

agent-tools-cl calendar holidays --year 2027
# 2027-01-01 Año Nuevo
# ...
```



## MCP server

FastMCP HTTP server exposing the same tools with the same names and semantics:


| Tool           | Unit                              |
| -------------- | --------------------------------- |
| `uf`           | CLP                               |
| `utm`          | CLP                               |
| `dollar`       | CLP per USD                       |
| `euro`         | CLP per EUR                       |
| `copper`       | USD per pound                     |
| `tpm`          | percent                           |
| `ipc`          | percent (monthly)                 |
| `imacec`       | percent                           |
| `unemployment` | percent                           |
| `holidays`     | dates (optional `year`)           |

`holidays` takes an optional `year` and returns only the next holiday when omitted.




### Run

The MCP server needs the `mcp` extra (`pip install agent-tools-cl[mcp]`), which adds `fastmcp` on top of the base dependencies:

```sh
uvx --from "agent-tools-cl[mcp] @ git+https://github.com/pgalilea/agent-tools-cl.git" python -m agent_tools_cl.mcp.main
```

To install it once as a tool:

```sh
uv tool install "agent-tools-cl[mcp] @ git+https://github.com/pgalilea/agent-tools-cl.git"
python -m agent_tools_cl.mcp.main
```

HTTP transport on `http://127.0.0.1:8000/mcp`, liveness probe at `GET /health` (unauthenticated).

### Configuration (environment variables)


| Variable              | Default     | Purpose                                            |
| --------------------- | ----------- | -------------------------------------------------- |
| `MCP_HOST`            | `127.0.0.1` | Bind address                                       |
| `MCP_PORT`            | `8000`      | Bind port                                          |
| `MCP_ALLOWED_HOSTS`   | –           | Extra `Host` header allowlist (comma-separated)    |
| `MCP_ALLOWED_ORIGINS` | –           | Extra browser `Origin` allowlist (comma-separated) |




### Security

Without auth it binds to loopback only — it refuses a non-loopback bind. To expose it further, opt in to one of:

- `MCP_API_TOKEN` — static bearer token (header validation)
- `MCP_JWKS_URI` — JWT auth via your IdP, with `MCP_JWT_ISSUER`, `MCP_JWT_AUDIENCE`, `MCP_JWT_ALGORITHM`, `MCP_REQUIRED_SCOPES`, `MCP_AUTH_SERVER`, `MCP_PUBLIC_URL`

`MCP_API_TOKEN` wins over `MCP_JWKS_URI`. Put TLS in front (reverse proxy) and set HSTS there.

### Example client config

Point any MCP client at the server URL:

```json
{
  "mcpServers": {
    "agent-tools-cl": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

