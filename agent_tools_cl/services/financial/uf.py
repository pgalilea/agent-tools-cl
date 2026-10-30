import re
from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import normalize_clp, validator

MISINDICADORES_URL = "https://misindicadores.cl/"
FINDIC_UF_URL = "https://findic.cl/api/uf"
UFHOY_URL = "https://www.uf-hoy.com/wp-json/indicadores-economicos/v1/indicators/UF"
SII_UF_URL = "https://www.sii.cl/valores_y_fechas/uf/uf{year}.htm"  # year baked into the path

_UF_MIN, _UF_MAX = 40_000.0, 60_000.0  # sanity bounds for CLP per UF
_UF_ROW = re.compile(
    r'class="name">\s*UF\s*<.*?class="value">\$?\s*([\d.,]+)\s*<.*?class="date">(\d{4}-\d{2}-\d{2})<',
    re.DOTALL,
)


_validate_uf = validator("UF", _UF_MIN, _UF_MAX)


async def _get_uf_misindicadores(client: httpx.AsyncClient) -> float:
    html = (await fetch(MISINDICADORES_URL, client)).text
    match = _UF_ROW.search(html)
    if match is None:
        raise ValueError("UF row not found in misindicadores HTML")

    return _validate_uf(normalize_clp(match.group(1)), date.fromisoformat(match.group(2)))


async def _get_uf_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_UF_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_uf(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_uf_ufhoy(client: httpx.AsyncClient) -> float:
    """UF for *today* from uf-hoy's JSON API.

    Uses the ``current`` row: the site also exposes ``latest_published``, which is
    future-dated (the SII publishes UF days ahead), so it must never be used.
    """

    data = (await fetch(UFHOY_URL, client)).json()
    row = data["current"]
    if row["indicator_code"] != "UF" or row["unit"] != "CLP" or row["is_estimate"]:
        raise ValueError(f"untrusted uf-hoy row: {row['indicator_code']}/{row['unit']}")

    return _validate_uf(float(row["value"]), date.fromisoformat(row["period_date"]))


async def _get_uf_sii(client: httpx.AsyncClient) -> float:
    """Today's UF from the official SII page.

    The consolidated year table (#table_export) has one row per day and twelve
    columns in month order, so `cells[month - 1]` is today's UF. Unpublished
    cells are ``&nbsp;`` and must count as a failure, never as a value.
    """

    today = date.today()
    html = (await fetch(SII_UF_URL.format(year=today.year), client)).text
    table = html[html.find('id="table_export"') :]
    row = re.search(rf"<th[^>]*>\s*{today.day}\s*</th>(.*?)</tr>", table, re.DOTALL)
    cells = row and re.findall(r">([\d.,]+|&nbsp;)<", row.group(1))
    if not cells or cells[today.month - 1] == "&nbsp;":
        raise ValueError("SII has no UF value for today")

    return _validate_uf(
        normalize_clp(cells[today.month - 1]), today
    )  # date is today by construction


async def get_uf(client: httpx.AsyncClient | None = None) -> float:
    """Latest UF in CLP: first source whose value passes its own validation wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_uf(client)

    return await first_success(
        _get_uf_misindicadores(client),
        _get_uf_findic(client),
        _get_uf_ufhoy(client),
        _get_uf_sii(client),
    )
