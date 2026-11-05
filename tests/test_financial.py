import asyncio
from datetime import date, timedelta

import httpx
import pytest

from agent_tools_cl.core import AllFailedError
from agent_tools_cl.services.financial import (
    get_dollar,
    get_euro,
    get_imacec,
    get_ipc,
    get_tpm,
    get_uf,
    get_unemployment,
)

TODAY = date.today().isoformat()
STALE = (date.today() - timedelta(days=30)).isoformat()

HTML = (
    '<div class="name">UF</div></td><td class="value">$ 41.242,32</td>'
    f'<td class="date">{TODAY}</td>'
)
STALE_HTML = HTML.replace(TODAY, STALE)
JSON = {"serie": [{"fecha": TODAY, "valor": 41242.32}]}
STALE_JSON = {"serie": [{"fecha": STALE, "valor": 41242.32}]}

DOLLAR_HTML = (
    f'<div class="name">USD</div></td><td class="value">$ 993,22</td><td class="date">{TODAY}</td>'
)
STALE_DOLLAR_HTML = DOLLAR_HTML.replace(TODAY, STALE)
DOLLAR_JSON = {"serie": [{"fecha": TODAY, "valor": 993.22}]}
STALE_DOLLAR_JSON = {"serie": [{"fecha": STALE, "valor": 993.22}]}


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
    row = (
        f"<tr><th style='text-align:center;'>{today.day}</th>"
        + "".join(f"<td style='text-align:right;'>{c}</td>" for c in cells)
        + "</tr>"
    )
    return f'<table id="table_export"><tbody>{row}</tbody></table>'


def _gr_html(value="993,22", year=None, day=None, month=None):
    """Minimal BCCh #gr grid: one day row, twelve month columns, one cell set."""
    today = date.today()
    cells = [""] * 12
    if value is not None:
        cells[(month if month is not None else today.month) - 1] = value
    row = (
        f'<tr><td align="center">{day if day is not None else today.day}</td>'
        + "".join(
            f'<td align="center"><span class="obs">{c}</span></td>' for c in cells
        )
        + "</tr>"
    )
    selected = year if year is not None else today.year
    select = f'<option selected="selected" value="{selected}">{selected}</option>'
    return f'{select}<table id="gr">{row}</table>'


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


def test_get_dollar_parses_html_source():
    assert (
        asyncio.run(get_dollar(client=_client(html=DOLLAR_HTML, payload={"serie": []}))) == 993.22
    )


def test_get_dollar_falls_back_to_findic():
    assert asyncio.run(get_dollar(client=_client(html_status=500, payload=DOLLAR_JSON))) == 993.22


def test_get_dollar_rejects_stale_values_from_every_source():
    client = _client(html=STALE_DOLLAR_HTML, payload=STALE_DOLLAR_JSON)
    with pytest.raises(AllFailedError):
        asyncio.run(get_dollar(client=client))


def test_get_dollar_rejects_uf_sized_values():
    # A UF-sized number must never pass as a dollar: bounds are per indicator.
    client = _client(html=DOLLAR_HTML.replace("993,22", "41.242,32"), payload=JSON)
    with pytest.raises(AllFailedError):
        asyncio.run(get_dollar(client=client))


def _catalog_html(href="Serie.aspx?gcode=PRE_TCO&amp;param=ignored"):
    """Minimal IndicadoresDiarios.aspx: the dollar series label plus its link."""
    return (
        '<label id="lblSerie1_3">Dólar observado</label>'
        f'<a id="hypLnk1_3" title="Ver serie" href="{href}">ver</a>'
    )


def _bcentral_client(grid, catalog=None):
    """Only BCCh answers: both aggregator sources are down."""

    def handler(request):
        if request.url.host != "si3.bcentral.cl":
            return httpx.Response(500)
        if "IndicadoresDiarios" in request.url.path:
            return httpx.Response(200, text=_catalog_html() if catalog is None else catalog)
        return httpx.Response(200, text=grid)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_get_dollar_accepts_bcentral_grid():
    assert asyncio.run(get_dollar(client=_bcentral_client(_gr_html()))) == 993.22


def test_get_dollar_bcentral_discovers_series_url_from_catalog():
    seen = []

    def handler(request):
        if request.url.host != "si3.bcentral.cl":
            return httpx.Response(500)
        seen.append(request.url.path)
        if "IndicadoresDiarios" in request.url.path:
            return httpx.Response(200, text=_catalog_html())
        return httpx.Response(200, text=_gr_html())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert asyncio.run(get_dollar(client=client)) == 993.22
    assert seen == [
        "/indicadoressiete/secure/IndicadoresDiarios.aspx",
        "/indicadoressiete/secure/Serie.aspx",
    ]


def test_get_dollar_bcentral_uses_latest_cell_within_threshold():
    # e.g. Monday morning before publication: Friday's value is still recent.
    html = _gr_html(day=max(1, date.today().day - 1))
    assert asyncio.run(get_dollar(client=_bcentral_client(html))) == 993.22


def test_get_dollar_rejects_bcentral_when_nothing_published_this_year():
    client = _bcentral_client(_gr_html(value=None))
    with pytest.raises(AllFailedError):
        asyncio.run(get_dollar(client=client))


def test_get_dollar_rejects_stale_bcentral_value():
    stale = date.today() - timedelta(days=8)
    if stale.year != date.today().year:
        pytest.skip("no in-year date older than the threshold")
    html = _gr_html(day=stale.day, month=stale.month)
    with pytest.raises(AllFailedError):
        asyncio.run(get_dollar(client=_bcentral_client(html)))


def test_get_dollar_rejects_bcentral_when_page_shows_another_year():
    client = _bcentral_client(_gr_html(year=date.today().year - 1))
    with pytest.raises(AllFailedError):
        asyncio.run(get_dollar(client=client))


def test_get_dollar_rejects_bcentral_grid_without_day_rows():
    # A grid without day rows is a layout change, not "unavailable": be loud.
    html = _gr_html().split('<table id="gr">')[0] + '<table id="gr"><tr></tr></table>'
    client = _bcentral_client(html)
    with pytest.raises(AllFailedError):
        asyncio.run(get_dollar(client=client))


EURO_JSON = {"serie": [{"fecha": TODAY, "valor": 1097.72}]}
TPM_JSON = {"serie": [{"fecha": TODAY, "valor": 4.5}]}
IPC_JSON = {"serie": [{"fecha": TODAY, "valor": 0.4}]}
IMACEC_JSON = {"serie": [{"fecha": TODAY, "valor": 0.2}]}
UNEMPLOYMENT_JSON = {"serie": [{"fecha": TODAY, "valor": 9.8}]}

OLD = (date.today() - timedelta(days=90)).isoformat()
VERY_OLD = (date.today() - timedelta(days=120)).isoformat()


def test_get_euro_parses_json():
    assert asyncio.run(get_euro(client=_client(payload=EURO_JSON))) == 1097.72


def test_get_euro_rejects_non_euro_values():
    # A UF-sized number must never pass as a euro: bounds are per indicator.
    payload = {"serie": [{"fecha": TODAY, "valor": 41242.32}]}
    with pytest.raises(AllFailedError):
        asyncio.run(get_euro(client=_client(payload=payload)))


def test_get_tpm_parses_json():
    assert asyncio.run(get_tpm(client=_client(payload=TPM_JSON))) == 4.5


def test_get_tpm_rejects_out_of_range_values():
    payload = {"serie": [{"fecha": TODAY, "valor": 45.0}]}
    with pytest.raises(AllFailedError):
        asyncio.run(get_tpm(client=_client(payload=payload)))


def test_get_ipc_parses_json():
    assert asyncio.run(get_ipc(client=_client(payload=IPC_JSON))) == 0.4


def test_get_ipc_accepts_misindicadores_row():
    html = (
        '<div class="name">IPC</div></td><td class="value">0,40</td>'
        f'<td class="date">{TODAY}</td>'
    )
    client = _client(html=html, payload={"serie": []})
    assert asyncio.run(get_ipc(client=client)) == 0.4


def test_get_ipc_rejects_stale_values():
    # Monthly indicators are published weeks late, but 90 days is too old.
    payload = {"serie": [{"fecha": OLD, "valor": 0.4}]}
    with pytest.raises(AllFailedError):
        asyncio.run(get_ipc(client=_client(payload=payload)))


def test_get_imacec_parses_json():
    assert asyncio.run(get_imacec(client=_client(payload=IMACEC_JSON))) == 0.2


def test_get_imacec_rejects_stale_values():
    payload = {"serie": [{"fecha": VERY_OLD, "valor": 0.2}]}
    with pytest.raises(AllFailedError):
        asyncio.run(get_imacec(client=_client(payload=payload)))


def test_get_unemployment_parses_json():
    assert asyncio.run(
        get_unemployment(client=_client(payload=UNEMPLOYMENT_JSON))
    ) == 9.8


def test_get_unemployment_rejects_stale_values():
    payload = {"serie": [{"fecha": VERY_OLD, "valor": 9.8}]}
    with pytest.raises(AllFailedError):
        asyncio.run(get_unemployment(client=_client(payload=payload)))
