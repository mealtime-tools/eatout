"""Command-line entry point. Wiring only -- logic lives in `commands/`."""

from pathlib import Path

import click
from agentcli import JsonAwareGroup

from eatout import __version__, helptext
from eatout.commands.guide import guide
from eatout.commands.metadata import metadata
from eatout.commands.search import search
from eatout.commands.skill import skill

EPILOG = """\b
Run `eatout guide` for the full manual: the candidate record, the ranking, and
why a missing fat figure is never zero.

\b
Exit codes: 0 success, 1 usage error or unreadable data, 3 assertion failure,
4 warnings under --strict."""


@click.group(
    cls=JsonAwareGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=EPILOG,
)
@click.version_option(__version__)
@click.option(
    "--data",
    type=click.Path(dir_okay=False, path_type=Path),
    help=helptext.DATA,
)
@click.pass_context
def main(ctx: click.Context, data: Path | None) -> None:
    """Search cited vegetarian restaurant meals around Sydney CBD.

    The dataset is a reviewed, read-only snapshot: no command here fetches or
    writes anything. A macro appears only where an operator published it, and
    its absence means unknown, never zero.
    """
    ctx.obj = data


for command in (guide, skill, metadata, search):
    main.add_command(command)
