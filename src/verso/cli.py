"""Command-line entry point.

Subcommands are added here as the project grows. Each one stays a thin
wrapper: argument parsing and the output for the reader live here, and the
work itself lives in the module that the command calls. Thus each step can be
tested without click.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import click
import numpy as np
from recto.ocrcheck import TesseractError, find_tesseract

from recto.pngio import read_png

from verso import __version__
from verso.cer import LineScore, Total, score_line, total
from verso.groundtruth import draft
from verso.manifest import Column, ManifestError, read_columns
from verso.reader import pending, read_part
from verso.tesseract import read_line
from verso.transcription import TranscriptionError, read_record

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


def _show(char: str) -> str:
    """Name one side of an error pair for the reader.

    Args:
        char: One character, or the empty string for a missing one.

    Returns:
        The character, or a word for a space or a missing character.
    """
    if char == "":
        return "(none)"
    if char == " ":
        return "(space)"
    return char


def _summary(label: str, part: Total) -> str:
    """Give one line of the summary.

    Args:
        label: What the lines are.
        part: Their sum.

    Returns:
        The line for the reader.
    """
    rate = "n/a" if part.rate is None else f"{100 * part.rate:.2f} %"
    return (
        f"{label}: {part.lines} lines, {part.length} characters, "
        f"{part.distance} errors, CER {rate}"
    )


@main.command("cer")
@click.argument(
    "gt_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--lang",
    default="lat",
    show_default=True,
    help="Tesseract language to measure.",
)
@click.option(
    "--dpi",
    type=click.IntRange(72, 1200),
    default=300,
    show_default=True,
    help="Resolution of the line images. Recto writes 300 dpi columns.",
)
@click.option(
    "--top",
    type=click.IntRange(min=0),
    default=15,
    show_default=True,
    help="How many of the most frequent errors to list.",
)
@click.option(
    "--report",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write one row for each line to this TSV file.",
)
def cer_command(
    gt_dir: Path,
    lang: str,
    dpi: int,
    top: int,
    report: Path | None,
) -> None:
    """Measure the character error rate of Tesseract on the ground truth.

    GT_DIR is a ground truth folder, for example groundtruth\\part1. Each line
    image is read with Tesseract and compared with its hand transcription. The
    rate is given for all lines, and for the lines not marked UNCERTAIN.
    """
    try:
        entries = read_record(gt_dir)
        tesseract = find_tesseract()
    except (TranscriptionError, TesseractError) as exc:
        raise click.ClickException(str(exc)) from exc

    scores: list[LineScore] = []
    with tempfile.TemporaryDirectory(prefix="verso-") as work:
        try:
            for entry in entries:
                text = read_line(
                    read_png(entry.image),
                    tesseract=tesseract,
                    lang=lang,
                    dpi=dpi,
                    workdir=Path(work),
                )
                scores.append(score_line(entry, text))
        except RuntimeError as exc:
            # TesseractError is a RuntimeError, and so is a failed image read.
            raise click.ClickException(str(exc)) from exc

    every = total(scores, lambda s: True)
    certain = total(scores, lambda s: s.entry.status != "UNCERTAIN")
    click.echo(_summary("all", every))
    click.echo(_summary("not UNCERTAIN", certain))

    if top:
        click.echo(f"most frequent errors, all lines (truth -> {lang}):")
        for (truth, read), count in every.errors.most_common(top):
            click.echo(f"  {count:5d}  {_show(truth)} -> {_show(read)}")

    if report is not None:
        rows = ["file\tstatus\terrors\tlength\ttruth\tread"]
        for s in scores:
            rows.append(
                f"{s.entry.image.name}\t{s.entry.status}\t{s.distance}\t"
                f"{s.length}\t{s.truth}\t{s.read}"
            )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("\n".join(rows) + "\n", encoding="utf-8")
        click.echo(f"line report: {report}")


@main.command("read")
@click.argument(
    "out_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--dest",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="The text file. Defaults to work\\<name of OUT_DIR>-<lang>.txt.",
)
@click.option(
    "--lang",
    default="lat",
    show_default=True,
    help="Tesseract language.",
)
@click.option(
    "--jobs",
    type=click.IntRange(min=1),
    default=None,
    help="Columns read at the same time. Defaults to the number of CPUs.",
)
def read_command(
    out_dir: Path,
    dest: Path | None,
    lang: str,
    jobs: int | None,
) -> None:
    """Read every column of a recto output folder into one text file.

    OUT_DIR is a folder that recto run wrote, for example ..\\recto\\out\\part1.
    The text keeps the printed lines, with a marker line before each column.
    A word broken by a hyphen at a line end is joined on the first line.
    The text of each finished column is kept in work, so a stopped run goes
    on where it stopped. Delete that folder to read every column again.
    """
    try:
        found = read_columns(out_dir)
        tesseract = find_tesseract()
    except (ManifestError, TesseractError) as exc:
        raise click.ClickException(str(exc)) from exc

    name = out_dir.resolve().name
    # The language is in the folder name, so a run with another model does
    # not take the text of this one from the cache.
    cache = Path("work") / name / f"lines-{lang}"
    target = dest if dest is not None else Path("work") / f"{name}-{lang}.txt"
    todo = pending(found, cache)
    finished = 0

    def read(image: np.ndarray, dpi: int, workdir: Path) -> str:
        """Read one line image with Tesseract.

        Args:
            image: The line image.
            dpi: Its resolution.
            workdir: A folder for the temporary PNG file.

        Returns:
            The text.
        """
        return read_line(image, tesseract=tesseract, lang=lang, dpi=dpi, workdir=workdir)

    def done(column: Column) -> None:
        """Report one finished column.

        Args:
            column: The column.
        """
        nonlocal finished
        finished += 1
        click.echo(f"  {column.label}  ({finished} of {len(todo)})")

    click.echo(f"{len(found.columns)} columns, {len(todo)} to read; cache {cache}")
    try:
        text, progress = read_part(
            found, cache=cache, read=read, jobs=jobs or os.cpu_count() or 1, done=done
        )
    except RuntimeError as exc:
        # TesseractError is a RuntimeError, and so is a failed image read.
        raise click.ClickException(str(exc)) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    click.echo(
        f"{progress.read} columns read, {progress.cached} from the cache, "
        f"{progress.lines} lines, in {target}"
    )
    joins = progress.joins
    click.echo(
        f"{joins.joined} words joined across a line end, "
        f"{joins.removed} lines left empty and removed, "
        f"{joins.kept} breaks not joined"
    )
    if found.errors:
        pages = ", ".join(str(p) for p in found.errors)
        click.echo(f"pages that recto could not do: {pages}")
    if progress.empty:
        click.echo(f"{len(progress.empty)} lines with no text, written as {{?}}:")
        for place in progress.empty:
            click.echo(f"  {place}")
