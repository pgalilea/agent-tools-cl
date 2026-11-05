import asyncio

import click

from ..core import AllFailedError
from ..core.utils import today_cl
from ..services.calendar import get_holidays, get_next_holiday

calendar = click.Group("calendar", help="Chilean dates.")


@calendar.command()
@click.option("--year", type=int, help="List every holiday in that year.")
def holidays(year: int | None):
    """Next Chilean public holiday, or the full list for --year."""

    try:
        if year is None:
            holiday = asyncio.run(get_next_holiday())
            days = (holiday.date - today_cl()).days
            when = "hoy" if days == 0 else f"en {days} día{'s' if days != 1 else ''}"
            click.echo(f"{holiday.date} {holiday.name} ({when})")
            return

        for holiday in asyncio.run(get_holidays(year)):
            click.echo(f"{holiday.date} {holiday.name}")

    except (AllFailedError, ValueError) as e:
        raise SystemExit(f"Error: no holiday data: {e}")
