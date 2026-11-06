"""Command-line entry point.

Subcommands are added here as the project grows. Each one stays a thin
wrapper: argument parsing and the output for the reader live here, and the
work itself lives in the module that the command calls. Thus each step can be
tested without click.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import click
import numpy as np
from recto.ocrcheck import TesseractError, find_tesseract

from verso import __version__
from verso.groundtruth import draft
from verso.manifest import ManifestError, read_columns
from verso.tesseract import read_line

# Accept -h as well as --help, as recto does.
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

GROUND_TRUTH_DIR = Path("groundtruth")
"""Where verso lines writes, one folder for each recto output folder."""


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-V", "--version", prog_name="verso")
def main() -> None:
    """Read recto's column images into Latin text.

    Verso reads the column images and the manifest that recto run writes. It
    reads each line with Tesseract, and writes the text of the book in reading
    order, with markers that give the page, side and column of each part.
    """


@main.command("lines")
@click.argument(
    "out_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--column",
    "labels",
    metavar="LABEL",
    multiple=True,
    required=True,
    help="A column to sample, for example p0013-verso-c1. Give it once for each column.",
)
@click.option(
    "--count",
    type=click.IntRange(min=1),
    default=20,
    show_default=True,
    help="Lines to take from each column, at even spacing.",
)
@click.option(
    "--dest",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Folder for the pairs. Defaults to groundtruth\\<name of OUT_DIR>.",
)
@click.option(
    "--lang",
    default="lat",
    show_default=True,
    help="Tesseract language for the drafts.",
)
def lines_command(
    out_dir: Path,
    labels: tuple[str, ...],
    count: int,
    dest: Path | None,
    lang: str,
) -> None:
    """Write line images and OCR drafts to correct by hand.

    OUT_DIR is a folder that recto run wrote, for example ..\\recto\\out\\part1.
    Each line becomes a PNG and a .gt.txt file with Tesseract's draft. A pair
    that is already there is not changed, so corrected lines are safe.
    """
    try:
        found = read_columns(out_dir)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc

    by_label = {column.label: column for column in found.columns}
    missing = [label for label in labels if label not in by_label]
    if missing:
        raise click.ClickException(
            f"not a column image in {out_dir}: {', '.join(missing)}"
        )

    try:
        tesseract = find_tesseract()
    except TesseractError as exc:
        raise click.ClickException(str(exc)) from exc
    target = dest if dest is not None else GROUND_TRUTH_DIR / out_dir.resolve().name

    with tempfile.TemporaryDirectory(prefix="verso-") as work:

        def read(image: np.ndarray, dpi: int) -> str:
            """Read one line image with Tesseract.

            Args:
                image: The line image.
                dpi: Its resolution.

            Returns:
                The draft text.
            """
            return read_line(
                image, tesseract=tesseract, lang=lang, dpi=dpi, workdir=Path(work)
            )

        try:
            report = draft(
                [by_label[label] for label in labels],
                count=count,
                dest=target,
                read=read,
            )
        except RuntimeError as exc:
            # TesseractError is a RuntimeError, and so is a failed image write.
            raise click.ClickException(str(exc)) from exc

    click.echo(f"{report.written} new pairs, {report.kept} kept, in {target}")
    for column in report.short:
        click.echo(f"fewer lines than --count: {column}")
