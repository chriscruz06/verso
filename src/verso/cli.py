"""Command-line entry point.

Subcommands are added here as the project grows. Each one stays a thin
wrapper: argument parsing and the output for the reader live here, and the
work itself lives in the module that the command calls. Thus each step can be
tested without click.
"""

from __future__ import annotations

import click

from verso import __version__

# Accept -h as well as --help, as recto does.
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-V", "--version", prog_name="verso")
def main() -> None:
    """Read recto's column images into Latin text.

    Verso reads the column images and the manifest that recto run writes. It
    reads each line with Tesseract, and writes the text of the book in reading
    order, with markers that give the page, side and column of each part.
    """
