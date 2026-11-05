from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import validator

FINDIC_EURO_URL = "https://findic.cl/api/euro"
MINDICADOR_EURO_URL = "https://mindicador.cl/api/euro/{year}"

_EURO_MIN, _EURO_MAX = 800.0, 1500.0  # sanity bounds for CLP per EUR

_validate_euro = validator("euro", _EURO_MIN, _EURO_MAX)


async def _get_euro_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_EURO_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_euro(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_euro_mindicador(client: httpx.AsyncClient) -> float:
    data = (await fetch(MINDICADOR_EURO_URL.format(year=date.today().year), client)).json()
    row = data["serie"][0]  # mindicador returns newest first

    return _validate_euro(float(row["valor"]), date.fromisoformat(row["fecha"][:10]))


async def get_euro(client: httpx.AsyncClient | None = None) -> float:
    """Latest CLP/EUR: first source whose value passes its own validation wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_euro(client)

    return await first_success(
        _get_euro_findic(client),
        _get_euro_mindicador(client),
    )
