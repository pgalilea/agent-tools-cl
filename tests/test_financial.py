import asyncio
from datetime import date, timedelta

import httpx
import pytest

from agent_tools_cl.core import AllFailedError
from agent_tools_cl.services.financial import get_dolar, get_uf

TODAY = date.today().isoformat()
STALE = (date.today() - timedelta(days=30)).isoformat()

HTML = (
    '<div class="name">UF</div></td><td class="value">$ 41.242,32</td>'
    f'<td class="date">{TODAY}</td>'
)
STALE_HTML = HTML.replace(TODAY, STALE)
JSON = {"serie": [{"fecha": TODAY, "valor": 41242.32}]}
STALE_JSON = {"serie": [{"fecha": STALE, "valor": 41242.32}]}

DOLAR_HTML = (
    '<div class="name">USD</div></td><td class="value">$ 993,22</td>'
    f'<td class="date">{TODAY}</td>'
)
STALE_DOLAR_HTML = DOLAR_HTML.replace(TODAY, STALE)
DOLAR_JSON = {"serie": [{"fecha": TODAY, "valor": 993.22}]}
STALE_DOLAR_JSON = {"serie": [{"fecha": STALE, "valor": 993.22}]}


def _row(fecha, valor, estimate=False):
    return {
        "period_date": fecha,
        "value": valor,
        "unit": "CLP",
        "indicator_code": "UF",
        "is_estimate": estimate,
    }


# uf-hoy publishes ahead of time: `latest_published` is future-dated, `current` is today.
UFHOY = {
    "indicator_code": "UF",
    "current": _row(TODAY, 41242.32),
    "previous": _row((date.today() - timedelta(days=1)).isoformat(), 41237.01),
    "latest_published": _row((date.today() + timedelta(days=9)).isoformat(), 41295.46),
}
UFHOY_NO_CURRENT = {k: v for k, v in UFHOY.items() if k != "current"}
UFHOY_ESTIMATE = {**UFHOY, "current": _row(TODAY, 41242.32, estimate=True)}


def _sii_html(value="41.242,32"):
    """Minimal #table_export: one row for today, twelve month columns, today's cell set."""
    today = date.today()
    cells = ["&nbsp;"] * 12
    if value is not None:
        cells[today.month - 1] = value
    row = f"<tr><th style='text-align:center;'>{today.day}</th>" + "".join(
        f"<td style='text-align:right;'>{c}</td>" for c in cells
    ) + "</tr>"
    return f'<table id="table_export"><tbody>{row}</tbody></table>'


def _client(
    html=HTML,
    payload=JSON,
    ufhoy=UFHOY,
    sii=None,
    html_status=200,
    json_status=200,
    ufhoy_status=200,
):
    def handler(request):
        if request.url.host == "misindicadores.cl":
            return httpx.Response(html_status, text=html)
        if request.url.host == "www.uf-hoy.com":
            return httpx.Response(ufhoy_status, json=ufhoy)
        if request.url.host == "www.sii.cl":
            return httpx.Response(200, text=sii) if sii else httpx.Response(500)
        return httpx.Response(json_status, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_get_uf_parses_html_source():
    assert asyncio.run(get_uf(client=_client(payload={"serie": []}, ufhoy={}))) == 41242.32


def test_get_uf_falls_back_to_second_source():
    client = _client(html_status=500, ufhoy={})
    assert asyncio.run(get_uf(client=client)) == 41242.32


def test_get_uf_accepts_third_source():
    # Only uf-hoy answers; its latest_published row is future-dated, so current must win.
    client = _client(html_status=500, json_status=500, ufhoy=UFHOY)
    assert asyncio.run(get_uf(client=client)) == 41242.32


def test_ufhoy_rejects_missing_current_row():
    client = _client(html_status=500, json_status=500, ufhoy=UFHOY_NO_CURRENT)
    with pytest.raises(AllFailedError):
        asyncio.run(get_uf(client=client))


def test_get_uf_rejects_invalid_values_from_every_source():
    client = _client(html=STALE_HTML, payload=STALE_JSON, ufhoy=UFHOY_ESTIMATE)
    with pytest.raises(AllFailedError):
        asyncio.run(get_uf(client=client))


def test_get_uf_accepts_sii_source():
    seen = []

    def handler(request):
        if request.url.host == "www.sii.cl":
            seen.append(request.url.path)
            return httpx.Response(200, text=_sii_html())
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert asyncio.run(get_uf(client=client)) == 41242.32
    # The year is built from today's date, so the URL must point at the current file.
    assert seen == [f"/valores_y_fechas/uf/uf{date.today().year}.htm"]


def test_sii_rejects_unpublished_cell():
    client = _client(
        html=STALE_HTML,
        payload=STALE_JSON,
        ufhoy=UFHOY_ESTIMATE,
        sii=_sii_html(value=None),  # today's cell is &nbsp;
    )
    with pytest.raises(AllFailedError):
        asyncio.run(get_uf(client=client))


def test_get_dolar_parses_html_source():
    assert asyncio.run(get_dolar(client=_client(html=DOLAR_HTML, payload={"serie": []}))) == 993.22


def test_get_dolar_falls_back_to_findic():
    assert asyncio.run(get_dolar(client=_client(html_status=500, payload=DOLAR_JSON))) == 993.22


def test_get_dolar_rejects_stale_values_from_every_source():
    client = _client(html=STALE_DOLAR_HTML, payload=STALE_DOLAR_JSON)
    with pytest.raises(AllFailedError):
        asyncio.run(get_dolar(client=client))


def test_get_dolar_rejects_uf_sized_values():
    # A UF-sized number must never pass as a dollar: bounds are per indicator.
    client = _client(html=DOLAR_HTML.replace("993,22", "41.242,32"), payload=JSON)
    with pytest.raises(AllFailedError):
        asyncio.run(get_dolar(client=client))
