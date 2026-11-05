from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import validator

FINDIC_IMACEC_URL = "https://findic.cl/api/imacec"
MINDICADOR_IMACEC_URL = "https://mindicador.cl/api/imacec/{year}"

_IMACEC_MIN, _IMACEC_MAX = -15.0, 20.0  # sanity bounds for variation, percent
_IMACEC_MAX_AGE_DAYS = 100  # BCCh publishes late in the following month

_validate_imacec = validator("imacec", _IMACEC_MIN, _IMACEC_MAX, max_age=_IMACEC_MAX_AGE_DAYS)


async def _get_imacec_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_IMACEC_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_imacec(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_imacec_mindicador(client: httpx.AsyncClient) -> float:
    data = (await fetch(MINDICADOR_IMACEC_URL.format(year=date.today().year), client)).json()
    row = data["serie"][0]  # mindicador returns newest first

    return _validate_imacec(float(row["valor"]), date.fromisoformat(row["fecha"][:10]))


async def get_imacec(client: httpx.AsyncClient | None = None) -> float:
    """Latest IMACEC variation, percent: first valid source wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_imacec(client)

    return await first_success(
        _get_imacec_findic(client),
        _get_imacec_mindicador(client),
    )
