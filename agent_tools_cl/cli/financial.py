import asyncio

import click

from ..core import AllFailedError
from ..services.financial import (
    get_copper,
    get_dollar,
    get_euro,
    get_imacec,
    get_ipc,
    get_tpm,
    get_uf,
    get_unemployment,
    get_utm,
)

financial = click.Group("financial", help="Financial indicators.")


@financial.command()
def uf():
    """Latest validated UF value in CLP (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_uf()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid UF source: {e}")


@financial.command()
def dollar():
    """Latest validated CLP/USD value (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_dollar()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid dollar source: {e}")


@financial.command()
def utm():
    """Latest validated UTM value in CLP (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_utm()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid UTM source: {e}")


@financial.command()
def copper():
    """Latest validated copper price in USD per lb (fastest of multiple sources)."""
    try:
        click.echo(f"{asyncio.run(get_copper()):.2f}")
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid copper source: {e}")


@financial.command()
def euro():
    """Latest validated CLP/EUR value (fastest of multiple sources)."""
    try:
        click.echo(asyncio.run(get_euro()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid euro source: {e}")


@financial.command()
def tpm():
    """Latest validated monetary policy rate (TPM) in percent."""
    try:
        click.echo(asyncio.run(get_tpm()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid TPM source: {e}")


@financial.command()
def ipc():
    """Latest validated IPC monthly variation in percent."""
    try:
        click.echo(asyncio.run(get_ipc()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid IPC source: {e}")


@financial.command()
def imacec():
    """Latest validated IMACEC variation in percent."""
    try:
        click.echo(asyncio.run(get_imacec()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid IMACEC source: {e}")


@financial.command()
def unemployment():
    """Latest validated unemployment rate in percent."""
    try:
        click.echo(asyncio.run(get_unemployment()))
    except AllFailedError as e:
        raise SystemExit(f"Error: no valid unemployment source: {e}")
