import asyncio

import httpx
import pytest

from agent_tools_cl.core import AllFailedError, fetch, first_success

transport = httpx.MockTransport(
    lambda request: (
        httpx.Response(200, text="hello")
        if "good" in request.url.path
        else httpx.Response(404)
    )
)
client = httpx.AsyncClient(transport=transport)


def test_fetch_returns_response():
    resp = asyncio.run(fetch("https://example.com/good", client))
    assert resp.status_code == 200
    assert resp.text == "hello"


def test_fetch_raises_on_404():
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(fetch("https://example.com/bad", client))


async def _ok(value, delay=0.0):
    await asyncio.sleep(delay)
    return value


async def _boom(delay=0.0):
    await asyncio.sleep(delay)
    raise RuntimeError("invalid")


def test_first_success_skips_faster_failure():
    assert asyncio.run(first_success(_boom(), _ok(41242.32, 0.01))) == 41242.32


def test_first_success_raises_when_all_fail():
    with pytest.raises(AllFailedError):
        asyncio.run(first_success(_boom(), _boom()))


def test_first_success_cancels_losers():
    cancelled = []

    async def slow():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    async def main():
        result = await first_success(_ok(1), slow())
        await asyncio.sleep(0)  # let the cancellation be delivered
        return result

    assert asyncio.run(main()) == 1
    assert cancelled == [True]
