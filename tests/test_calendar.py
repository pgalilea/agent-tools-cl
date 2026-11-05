import asyncio
from datetime import date, timedelta

import httpx
import pytest

from agent_tools_cl.core import AllFailedError
from agent_tools_cl.core.utils import today_cl
from agent_tools_cl.services.calendar import get_holidays, get_next_holiday


def _row(day: date, name: str, is_global: bool = True) -> dict:
    return {"date": day.isoformat(), "localName": name, "name": name, "global": is_global}


def _client(rows):
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rows))
    )


def test_get_holidays_parses_and_sorts():
    year = 2026
    rows = [_row(date(year, 5, 1), "Día del Trabajo"), _row(date(year, 1, 1), "Año Nuevo")]
    holidays = asyncio.run(get_holidays(year, client=_client(rows)))
    assert [h.name for h in holidays] == ["Año Nuevo", "Día del Trabajo"]
    assert holidays[0].date == date(year, 1, 1)


def test_get_holidays_rejects_wrong_year():
    rows = [_row(date(2025, 1, 1), "Año Nuevo")]
    with pytest.raises(AllFailedError):
        asyncio.run(get_holidays(2026, client=_client(rows)))


def test_get_holidays_skips_nager_region_specific_rows():
    year = 2026
    rows = [
        _row(date(year, 1, 1), "Año Nuevo"),
        _row(date(year, 6, 7), "Morro de Arica", is_global=False),
    ]
    holidays = asyncio.run(get_holidays(year, client=_client(rows)))
    assert [holiday.name for holiday in holidays] == ["Año Nuevo"]


def test_get_holidays_rejects_empty_payload():
    with pytest.raises(AllFailedError):
        asyncio.run(get_holidays(2026, client=_client([])))


def test_get_next_holiday_includes_today():
    today = today_cl()
    holidays = asyncio.run(get_next_holiday(client=_client([_row(today, "Feriado de hoy")])))
    assert holidays.date == today


def test_get_next_holiday_rolls_into_next_year():
    today = today_cl()
    past = today - timedelta(days=1) if today.day > 1 else None
    if past is None or past.year != today.year:
        pytest.skip("no past date left in the current year")

    def handler(request):
        if f"/{today.year}/" in request.url.path:
            return httpx.Response(200, json=[_row(past, "Feriado pasado")])
        return httpx.Response(
            200, json=[_row(today.replace(year=today.year + 1), "Feriado futuro")]
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    holiday = asyncio.run(get_next_holiday(client=client))
    assert holiday.date == today.replace(year=today.year + 1)


def _feriados_html(year: int, rows, title_year: int | None = None) -> str:
    body = "".join(
        f"<tr><td>{day}</td><td>{name}<br /><span>Irrenunciable</span></td>"
        "<td>Civil</td><td>Ley</td></tr>"
        for day, name in rows
    )
    return (
        f"<title>Feriados de Chile - Año {title_year or year}</title>"
        "<td class='subtabla'>Feriados de carácter general</td><table>"
        "<tr><td>Todos los Días Domingos</td><td>Día Domingo</td></tr>"
        f"{body}</table>"
        "<td class='subtabla'>Feriados espec&iacute;ficos</td><table>"
        "<tr><td>Lunes, 07 de Junio</td><td>Morro de Arica</td></tr></table>"
    )


def _feriados_client(year, rows, title_year=None, nager_status=200):
    html = _feriados_html(year, rows, title_year)

    def handler(request):
        if request.url.host == "date.nager.at":
            return httpx.Response(nager_status, json=[])
        return httpx.Response(200, text=html)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_get_holidays_falls_back_to_feriados_cl():
    year = 2027
    rows = [
        ("Viernes, 01 de Enero", "Año Nuevo"),
        ("Viernes, 26 de Marzo", "Viernes Santo"),
    ]
    client = _feriados_client(year, rows, nager_status=500)
    holidays = asyncio.run(get_holidays(year, client=client))
    # Sundays and region-specific holidays are not public holidays for everyone.
    assert [holiday.name for holiday in holidays] == ["Año Nuevo", "Viernes Santo"]
    assert holidays[0].date == date(year, 1, 1)


def test_feriados_cl_rejects_page_for_another_year():
    year = 2027
    rows = [("Viernes, 01 de Enero", "Año Nuevo")]
    client = _feriados_client(year, rows, title_year=2026, nager_status=500)
    with pytest.raises(AllFailedError):
        asyncio.run(get_holidays(year, client=client))
