import re
from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import normalize_clp, validator

MISINDICADORES_URL = "https://misindicadores.cl/"
FINDIC_DOLAR_URL = "https://findic.cl/api/dolar"


_DOLAR_ROW = re.compile(
    r'class="name">\s*USD\s*<.*?class="value">\$?\s*([\d.,]+)\s*<.*?class="date">(\d{4}-\d{2}-\d{2})<',
    re.DOTALL,
)
_DOLAR_MIN, _DOLAR_MAX = 700.0, 1_200.0  # sanity bounds for CLP per USD

_validate_dolar = validator("dolar", _DOLAR_MIN, _DOLAR_MAX)


async def _get_dolar_misindicadores(client: httpx.AsyncClient) -> float:
    html = (await fetch(MISINDICADORES_URL, client)).text
    match = _DOLAR_ROW.search(html)
    if match is None:
        raise ValueError("USD row not found in misindicadores HTML")

    return _validate_dolar(normalize_clp(match.group(1)), date.fromisoformat(match.group(2)))


async def _get_dolar_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_DOLAR_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_dolar(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def get_dolar(client: httpx.AsyncClient | None = None) -> float:
    """Latest CLP/USD: first source whose value passes its own validation wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_dolar(client)

    return await first_success(
        _get_dolar_misindicadores(client),
        _get_dolar_findic(client),
    )
