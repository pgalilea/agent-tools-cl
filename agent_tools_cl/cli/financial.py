import asyncio

import click

from ..core import AllFailedError
from ..services.financial import get_dolar, get_uf

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
