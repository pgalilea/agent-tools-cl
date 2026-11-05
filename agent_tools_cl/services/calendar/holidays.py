import re
from dataclasses import dataclass
from datetime import date
from html import unescape

import httpx

from ...core import fetch, first_success
from ...core.constants import MONTHS
from ...core.utils import today_cl

NAGER_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/CL"
FERIADOS_URL = "https://www.feriados.cl/{page}"

_GENERAL_START = "Feriados de carácter general"
_GENERAL_END = "espec"  # page encodes "específicos" as `espec&iacute;ficos` some years
_TITLE = re.compile(r"<title>[^<]*Año\s+(\d{4})")
_ROW = re.compile(
    r"<tr[^>]*>\s*<td>\s*\w+\s*,\s*(\d{1,2})\s+de\s+(\w+)\s*</td>\s*<td>(.*?)</td>",
    re.DOTALL,
)


@dataclass(frozen=True)
class Holiday:
    date: date
    name: str


async def _get_holidays_nager(year: int, client: httpx.AsyncClient) -> list[Holiday]:
    """National holidays from Nager.Date's free JSON API.

    Rejects empty or mislabeled payloads instead of returning a wrong year.
    """
    data = (await fetch(NAGER_URL.format(year=year), client)).json()

    if not isinstance(data, list):
        raise TypeError(f"unexpected payload for {year}")

    holidays = [
        Holiday(date.fromisoformat(row["date"]), row["localName"])
        for row in data
        if row.get("global", True)  # skip region-specific holidays
    ]

    if not holidays:
        raise ValueError(f"no holidays returned for {year}")
    if any(holiday.date.year != year for holiday in holidays):
        raise ValueError(f"holidays do not belong to {year}")

    return sorted(holidays, key=lambda holiday: holiday.date)


async def _get_holidays_feriados_cl(year: int, client: httpx.AsyncClient) -> list[Holiday]:
    """National holidays scraped from feriados.cl.

    Only the "carácter general" table counts: it also lists every Sunday and,
    further down, region-specific holidays, none of which are public holidays
    for everyone.
    """
    page = "" if year == today_cl().year else f"{year}.php"
    html = (await fetch(FERIADOS_URL.format(page=page), client)).text

    title = _TITLE.search(html)
    if title is None or int(title.group(1)) != year:
        raise ValueError(f"feriados.cl is not showing {year}")

    start = html.find(_GENERAL_START)
    end = html.find(_GENERAL_END, start)
    if start == -1:
        raise ValueError("feriados.cl layout changed: no general table")
    section = html[start : end if end != -1 else len(html)]

    holidays = []
    for day, month, raw_name in _ROW.findall(section):
        name = re.sub(r"<[^>]+>", " ", raw_name.split("<br")[0])
        holidays.append(
            Holiday(date(year, MONTHS[month.lower()], int(day)), unescape(name).strip())
        )

    if not holidays:
        raise ValueError(f"no holidays parsed from feriados.cl for {year}")
    return sorted(holidays, key=lambda holiday: holiday.date)


async def get_holidays(year: int, client: httpx.AsyncClient | None = None) -> list[Holiday]:
    """Every Chilean public holiday in the given year."""

    if not 2000 <= year <= 2100:
        raise ValueError(f"year out of range: {year}")

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_holidays(year, client)

    return await first_success(
        _get_holidays_nager(year, client),
        _get_holidays_feriados_cl(year, client),
    )


async def get_next_holiday(client: httpx.AsyncClient | None = None) -> Holiday:
    """Next Chilean public holiday, today included."""

    if client is None:
        async with httpx.AsyncClient() as client:  # noqa
            return await get_next_holiday(client)

    today = today_cl()
    for year in (today.year, today.year + 1):
        upcoming = [h for h in await get_holidays(year, client) if h.date >= today]
        if upcoming:
            return upcoming[0]

    raise ValueError("no upcoming holiday found")
