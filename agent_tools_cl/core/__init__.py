import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import httpx

T = TypeVar("T")


class AllFailedError(Exception):
    """Every awaitable raised (or returned a value its source rejected)."""

    def __init__(self, errors: list[Exception]):
        self.errors = errors
        super().__init__("; ".join(f"{type(e).__name__}: {e}" for e in errors) or "no sources")


async def fetch(url: str, client: httpx.AsyncClient) -> httpx.Response:
    """Fetch a URL with the given client; raises on HTTP error statuses."""
    resp = await client.get(url)
    resp.raise_for_status()
    return resp


async def first_success(*aws: Awaitable[T]) -> T:
    """Return the first awaitable to complete *without raising*; cancel the rest.

    A fast failure does not win: the race keeps waiting for a source that
    returns a validated value. Validation lives in each source, which raises
    when its data is unusable. Raises AllFailedError if every one raises.
    """

    tasks = [asyncio.ensure_future(a) for a in aws]  # wait() rejects bare coroutines
    try:
        pending = set(tasks)
        errors: list[Exception] = []
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception() is None:
                    return task.result()
                errors.append(task.exception())  # ty: ignore[invalid-argument-type]
        raise AllFailedError(errors)

    finally:
        for task in tasks:
            task.cancel()
