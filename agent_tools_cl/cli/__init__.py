import click

from .calendar import calendar
from .financial import financial

main = click.Group("agent-tools-cl", help="Agent tools for chilean people")
main.add_command(calendar)
main.add_command(financial)
