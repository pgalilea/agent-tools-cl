import re
from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import normalize_clp

MISINDICADORES_URL = "https://misindicadores.cl/"
FINDIC_UTM_URL = "https://findic.cl/api/utm"
SII_UTM_URL = (
    "https://www.sii.cl/valores_y_fechas/utm/utm{year}.htm"  # year baked into the path
)

_UTM_MIN, _UTM_MAX = 60_000.0, 100_000.0  # sanity bounds for CLP per UTM
_UTM_ROW = re.compile(
    r'class="name">\s*UTM\s*<.*?class="value">\$?\s*([\d.,]+)\s*<.*?class="date">(\d{4}-\d{2}-\d{2})<',
    re.DOTALL,
)
_MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _validate_utm(value: float, as_of: date) -> float:
    """Reject implausible values and periods other than the current month.

    UTM is monthly and dated the 1st, so the shared 7-day ``validator`` would
    reject valid data for most of each month.
    """

    if not _UTM_MIN <= value <= _UTM_MAX:
        raise ValueError(f"UTM out of range: {value}")
    today = date.today()
    if (as_of.year, as_of.month) != (today.year, today.month):
        raise ValueError(f"stale UTM period: {as_of}")
    return value


async def _get_utm_misindicadores(client: httpx.AsyncClient) -> float:
    html = (await fetch(MISINDICADORES_URL, client)).text
    match = _UTM_ROW.search(html)
    if match is None:
        raise ValueError("UTM row not found in misindicadores HTML")

    return _validate_utm(
        normalize_clp(match.group(1)), date.fromisoformat(match.group(2))
    )


async def _get_utm_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_UTM_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_utm(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_utm_sii(client: httpx.AsyncClient) -> float:
    """This month's UTM from the official SII page.

    The year table has one row per month, keyed by Spanish month name; the UTM
    is the first cell after it. Unpublished cells are ``&nbsp;`` and must count
    as a failure, never as a value.
    """

    today = date.today()
    html = (await fetch(SII_UTM_URL.format(year=today.year), client)).text
    table = html[html.find("table_export") :]
    row = re.search(
        rf"<th[^>]*>\s*{_MESES[today.month - 1]}\s*</th>(.*?)</tr>",
        table,
        re.DOTALL | re.IGNORECASE,
    )
    cells = row and re.findall(r">([\d.,]+|&nbsp;)<", row.group(1))
    if not cells or cells[0] == "&nbsp;":
        raise ValueError("SII has no UTM value for the current month")

    return _validate_utm(
        normalize_clp(cells[0]), date(today.year, today.month, 1)
    )  # month is current by construction


async def get_utm(client: httpx.AsyncClient | None = None) -> float:
    """Latest UTM in CLP: first source whose value passes its own validation wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_utm(client)

    return await first_success(
        _get_utm_misindicadores(client),
        _get_utm_findic(client),
        _get_utm_sii(client),
    )
