import asyncio

import click

from ..core import AllFailedError
from ..services.financial import get_cobre, get_dolar, get_uf, get_utm

financial = click.Group("financial", help="Financial indicators.")


@financial.command()
def uf():
    """Latest validated UF value in CLP (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_uf()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid UF source: {e}")


@financial.command()
def dolar():
    """Latest validated CLP/USD value (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_dolar()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid dolar source: {e}")


@financial.command()
def utm():
    """Latest validated UTM value in CLP (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_utm()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid UTM source: {e}")


@financial.command()
def cobre():
    """Latest validated copper price in USD per lb (fastest of multiple sources)."""
    try:
        click.echo(f"{asyncio.run(get_cobre()):.2f}")
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid cobre source: {e}")
