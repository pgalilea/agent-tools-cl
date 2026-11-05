from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import validator

FINDIC_UNEMPLOYMENT_URL = "https://findic.cl/api/tasa_desempleo"
MINDICADOR_UNEMPLOYMENT_URL = "https://mindicador.cl/api/tasa_desempleo/{year}"

_UNEMPLOYMENT_MIN, _UNEMPLOYMENT_MAX = 2.0, 15.0  # sanity bounds for percent
_UNEMPLOYMENT_MAX_AGE_DAYS = 100  # INE publishes late in the following month

_validate_unemployment = validator(
    "unemployment",
    _UNEMPLOYMENT_MIN,
    _UNEMPLOYMENT_MAX,
    max_age=_UNEMPLOYMENT_MAX_AGE_DAYS,
)


async def _get_unemployment_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_UNEMPLOYMENT_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_unemployment(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_unemployment_mindicador(client: httpx.AsyncClient) -> float:
    data = (await fetch(MINDICADOR_UNEMPLOYMENT_URL.format(year=date.today().year), client)).json()
    row = data["serie"][0]  # mindicador returns newest first

    return _validate_unemployment(float(row["valor"]), date.fromisoformat(row["fecha"][:10]))


async def get_unemployment(client: httpx.AsyncClient | None = None) -> float:
    """Latest unemployment rate, percent: first valid source wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_unemployment(client)

    return await first_success(
        _get_unemployment_findic(client),
        _get_unemployment_mindicador(client),
    )
