from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import validator

FINDIC_TPM_URL = "https://findic.cl/api/tpm"
MINDICADOR_TPM_URL = "https://mindicador.cl/api/tpm/{year}"

_TPM_MIN, _TPM_MAX = 0.0, 20.0  # sanity bounds for percent

_validate_tpm = validator("tpm", _TPM_MIN, _TPM_MAX)


async def _get_tpm_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_TPM_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_tpm(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_tpm_mindicador(client: httpx.AsyncClient) -> float:
    data = (await fetch(MINDICADOR_TPM_URL.format(year=date.today().year), client)).json()
    row = data["serie"][0]  # mindicador returns newest first

    return _validate_tpm(float(row["valor"]), date.fromisoformat(row["fecha"][:10]))


async def get_tpm(client: httpx.AsyncClient | None = None) -> float:
    """Latest monetary policy rate (TPM) in percent: first valid source wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_tpm(client)

    return await first_success(
        _get_tpm_findic(client),
        _get_tpm_mindicador(client),
    )
