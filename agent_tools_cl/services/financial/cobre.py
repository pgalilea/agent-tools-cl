import re
from datetime import date

import httpx

from ...core import fetch, first_success
from ...core.utils import normalize_clp, validator

MISINDICADORES_URL = "https://misindicadores.cl/"
FINDIC_COBRE_URL = "https://findic.cl/api/libra_cobre"
SII_COBRE_URL = "https://www.sii.cl/valores_y_fechas/otros_valores/precio_libra_cobre.html"

_COBRE_MIN, _COBRE_MAX = 2.0, 12.0  # sanity bounds for USD per lb
_COBRE_ROW = re.compile(
    r'class="name">\s*Cobre \(lb\)\s*<.*?class="value">\s*USD\s*([\d.,]+)\s*<.*?class="date">(\d{4}-\d{2}-\d{2})<',
    re.DOTALL,
)
_SII_ROW = re.compile(
    r"<td>\s*(\d{4})\s*</td>\s*<td>\s*([\w\s-]+?)\s*</td>\s*<td>\s*([\d.,]+)\s*</td>"
)
_QUARTER_START = {"Enero": 1, "Abril": 4, "Julio": 7, "Octubre": 10}  # first month
# 200-day ceiling covers quarter publication delay; tighten if SII publishes sooner
_SII_MAX_AGE_DAYS = 200  # a published quarter is normally 0-4 months old

_validate_cobre = validator("cobre", _COBRE_MIN, _COBRE_MAX)


async def _get_cobre_misindicadores(client: httpx.AsyncClient) -> float:
    html = (await fetch(MISINDICADORES_URL, client)).text
    match = _COBRE_ROW.search(html)
    if match is None:
        raise ValueError("copper row not found in misindicadores HTML")

    return _validate_cobre(normalize_clp(match.group(1)), date.fromisoformat(match.group(2)))


async def _get_cobre_findic(client: httpx.AsyncClient) -> float:
    data = (await fetch(FINDIC_COBRE_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_cobre(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_cobre_sii(client: httpx.AsyncClient) -> float:
    """Latest published quarterly average from SII, in USD per lb.

    The page lists quarters with values in cents US$/lb, but selection does not
    rely on page order: the newest (year, quarter) wins. The current quarter's
    row exists but is empty until published, so empty cells are skipped, never
    counted as zero. A quarterly average has no per-value date, so freshness is
    checked against the quarter itself.
    """

    html = (await fetch(SII_COBRE_URL, client)).text
    parsed = []

    for year, quarter, cents in _SII_ROW.findall(html):
        first_month = quarter.split()[0] if quarter.split() else ""
        month = _QUARTER_START.get(first_month)
        if not year or not cents or month is None:  # empty or unrecognized cell
            continue
        parsed.append(((int(year), month), cents))

    if not parsed:
        raise ValueError("no published quarterly copper value in SII HTML")

    (year, month), cents = max(parsed)
    if (date.today() - date(year, month, 1)).days > _SII_MAX_AGE_DAYS:
        raise ValueError(f"stale SII copper quarter: {year}-{month:02d}")

    return _validate_cobre(normalize_clp(cents) / 100, date.today())


async def get_cobre(client: httpx.AsyncClient | None = None) -> float:
    """Latest copper price in USD per lb: first source whose value passes its own validation wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_cobre(client)

    return await first_success(
        _get_cobre_misindicadores(client),
        _get_cobre_findic(client),
        _get_cobre_sii(client),
    )
