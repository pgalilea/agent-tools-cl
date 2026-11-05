import re
from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import normalize_clp, validator

MISINDICADORES_URL = "https://misindicadores.cl/"
FINDIC_IPC_URL = "https://findic.cl/api/ipc"

_IPC_MIN, _IPC_MAX = -5.0, 10.0  # sanity bounds for monthly variation, percent
_IPC_MAX_AGE_DAYS = 80  # INE publishes ~5-8 days into the following month

_IPC_ROW = re.compile(
    r'class="name">\s*IPC\s*<.*?class="value">\s*([\d.,]+)\s*<.*?class="date">(\d{4}-\d{2}-\d{2})<',
    re.DOTALL,
)

_validate_ipc = validator("ipc", _IPC_MIN, _IPC_MAX, max_age=_IPC_MAX_AGE_DAYS)


async def _get_ipc_misindicadores(client: httpx.AsyncClient) -> float:
    html = (await fetch(MISINDICADORES_URL, client)).text
    match = _IPC_ROW.search(html)
    if match is None:
        raise ValueError("IPC row not found in misindicadores HTML")

    return _validate_ipc(normalize_clp(match.group(1)), date.fromisoformat(match.group(2)))


async def _get_ipc_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_IPC_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_ipc(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def get_ipc(client: httpx.AsyncClient | None = None) -> float:
    """Latest IPC monthly variation, percent: first valid source wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_ipc(client)

    return await first_success(
        _get_ipc_misindicadores(client),
        _get_ipc_findic(client),
    )
