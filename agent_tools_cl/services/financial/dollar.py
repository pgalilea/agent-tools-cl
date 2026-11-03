import re
from datetime import date
from html import unescape
from urllib.parse import urljoin

import httpx

from ...core import fetch, first_success
from ...core.utils import normalize_clp, validator

MISINDICADORES_URL = "https://misindicadores.cl/"
FINDIC_DOLAR_URL = "https://findic.cl/api/dolar"
INDICADORES_URL = "https://si3.bcentral.cl/indicadoressiete/secure/IndicadoresDiarios.aspx"

_DOLAR_ROW = re.compile(
    r'class="name">\s*USD\s*<.*?class="value">\$?\s*([\d.,]+)\s*<.*?class="date">(\d{4}-\d{2}-\d{2})<',
    re.DOTALL,
)
_DOLAR_MIN, _DOLAR_MAX = 700.0, 1_200.0  # sanity bounds for CLP per USD

_validate_dollar = validator("dolar", _DOLAR_MIN, _DOLAR_MAX)


async def _get_dollar_misindicadores(client: httpx.AsyncClient) -> float:
    """Dollar parsed from misindicadores.cl's HTML table."""
    html = (await fetch(MISINDICADORES_URL, client)).text
    match = _DOLAR_ROW.search(html)
    if match is None:
        raise ValueError("USD row not found in misindicadores HTML")

    return _validate_dollar(normalize_clp(match.group(1)), date.fromisoformat(match.group(2)))


async def _get_dollar_findic(client: httpx.AsyncClient) -> float:
    """Dollar from findic.cl's JSON API (newest observation first)."""
    data = (await fetch(FINDIC_DOLAR_URL, client)).json()
    row = data["serie"][0]  # findic returns newest first

    return _validate_dollar(float(row["valor"]), date.fromisoformat(row["fecha"]))


async def _get_dollar_bcentral(client: httpx.AsyncClient) -> float:
    """Latest published dollar from BCCh: discover the series URL from the daily
    catalog, then read the newest non-empty cell of its yearly grid."""
    today = date.today()
    catalog = (await fetch(INDICADORES_URL, client)).text
    link = re.search(r'id="lblSerie(\d+_\d+)">[^<]*lar observado', catalog)
    if link is None:
        raise ValueError("BCCh 'Dólar observado' series not found in catalog")
    tag = re.search(rf'<a[^>]*id="hypLnk{link.group(1)}"[^>]*>', catalog)
    href = tag and re.search(r'href="([^"]+)"', tag.group(0))
    if href is None:
        raise ValueError("BCCh series link not found in catalog")
    serie_url = urljoin(INDICADORES_URL, unescape(href.group(1)))

    html = (await fetch(serie_url, client)).text

    year = re.search(r'<option selected="selected" value="(\d{4})"', html)
    if year is None or int(year.group(1)) != today.year:
        raise ValueError("the page is not showing the current year")

    grid = html[html.find('id="gr"') :]
    rows = re.findall(r"<td[^>]*>\s*(\d{1,2})\s*</td>(.*?)</tr>", grid, re.DOTALL)
    if not rows:
        raise ValueError("BCCh day rows not found in grid")

    newest: tuple[int, int, str] | None = None  # (month, day, raw), latest published
    for day, row in rows:
        cells = re.findall(r'class="obs">\s*([\d.,]*)\s*<', row)
        if len(cells) < 12:
            raise ValueError(f"BCCh grid layout changed: {len(cells)} month cells")
        for month, raw in enumerate(cells, 1):
            if raw and (newest is None or (month, int(day)) > (newest[0], newest[1])):
                newest = (month, int(day), raw)

    if newest is None:
        raise ValueError("nothing published this year")

    month, day, raw = newest
    as_of = date(today.year, month, day)

    return _validate_dollar(normalize_clp(raw), as_of)


async def get_dollar(client: httpx.AsyncClient | None = None) -> float:
    """Latest CLP/USD: first source whose value passes its own validation wins."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_dollar(client)

    return await first_success(
        _get_dollar_misindicadores(client),
        _get_dollar_findic(client),
        _get_dollar_bcentral(client),
    )
