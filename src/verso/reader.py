"""Read all the column images of a recto output folder into one text.

Each column is read line by line, and its text is kept in a cache folder, one
file for each column. The text of the part is then put together from those
files, in the reading order of the book. A full part is about 19000 lines, and
one line takes about 0.09 s, so a run can take half an hour on one thread. The
cache lets a stopped run go on from the last finished column, and the columns
are read in parallel.

The text keeps the printed lines: one line of text for each line of type. A
marker line before each column gives its label, for example

    === p0013-verso-c1 ===

The label is also the name of the column image, so each part of the text can
be found again in recto's output. A page that recto could not do gets a
marker of its own, so that the gap is seen. A line that Tesseract reads as
empty in both modes is written as EMPTY_LINE, so that no line is lost from
the count.

Each line gets the spacing normalisation of verso cer: one space between
words, and no space before , . : ; ? ! ) ] or after ( [. The transcription
rules do not record those spaces, so the text and the ground truth agree.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from recto.pngio import read_png

from verso.cer import normalise
from verso.hyphens import Joins, join_hyphens
from verso.lines import cut_line, find_lines
from verso.longs import LongS
from verso.manifest import SIDE_ORDER, Column, Columns

LineReader = Callable[[np.ndarray, int, Path], str]
"""Reads a line image at a given dpi, with a folder for temporary files."""

EMPTY_LINE = "{?}"
"""The text for a line with no OCR text. Braces do not occur in the book."""

MARKER = "=== {} ==="
"""The marker line before each column, or for a page with an error."""

GAP = "p{:04d} not read by recto"
"""The label of the marker for a page that recto could not do."""


def marker(label: str) -> str:
    """Give the marker line for a label.

    Args:
        label: A column label, or a page label for an error.

    Returns:
        The marker line.
    """
    return MARKER.format(label)


def is_marker(line: str) -> bool:
    """Tell if a line is a marker line.

    Args:
        line: A line of the text.

    Returns:
        True for a marker line.
    """
    return line.startswith("=== ") and line.endswith(" ===")


def is_gap(line: str) -> bool:
    """Tell if a line is the marker of a page that recto could not do.

    Args:
        line: A line of the text.

    Returns:
        True for such a marker.
    """
    return is_marker(line) and line.endswith(" not read by recto ===")


def read_column(column: Column, read: LineReader) -> list[str]:
    """Read every line of one column image.

    Args:
        column: The column.
        read: The function that reads a line image.

    Returns:
        One text for each line of type, from the top.

    Raises:
        RuntimeError: If the image cannot be read, or if the reader fails.
    """
    image = read_png(column.image)
    texts = []
    with tempfile.TemporaryDirectory(prefix="verso-") as work:
        for line in find_lines(image, column.dpi):
            cut = cut_line(image, line, column.dpi)
            text = normalise(read(cut, column.dpi, Path(work)))
            texts.append(text or EMPTY_LINE)
    return texts


def cache_file(cache: Path, column: Column) -> Path:
    """Give the cache file of one column.

    Args:
        cache: The cache folder.
        column: The column.

    Returns:
        The path of its text file.
    """
    return cache / f"{column.label}.txt"


def _store(path: Path, texts: list[str]) -> None:
    """Write the text of one column to the cache, all or nothing.

    Args:
        path: The cache file.
        texts: The lines.
    """
    # A stop during the write leaves only the temporary file, so a later run
    # does not take a part column for a finished one.
    part = path.with_suffix(".part")
    part.write_text("\n".join(texts) + "\n", encoding="utf-8")
    os.replace(part, path)


def pending(found: Columns, cache: Path) -> list[Column]:
    """Give the columns that have no text in the cache.

    Args:
        found: The columns of the part.
        cache: The cache folder.

    Returns:
        The columns to read, in reading order.
    """
    return [c for c in found.columns if not cache_file(cache, c).is_file()]


@dataclass
class Progress:
    """What one run of read_part did."""

    read: int = 0
    """Columns read in this run."""

    cached: int = 0
    """Columns taken from the cache."""

    lines: int = 0
    """Lines of type, before the joins."""

    empty: list[str] = field(default_factory=list)
    """The column labels and line numbers of lines with no OCR text."""

    joins: Joins = field(default_factory=Joins)
    """The words joined across line ends."""

    long_s: int = 0
    """The words changed from f to s."""


def read_part(
    found: Columns,
    *,
    cache: Path,
    read: LineReader,
    jobs: int,
    done: Callable[[Column], None] = lambda column: None,
    long_s: LongS | None = None,
) -> tuple[str, Progress]:
    """Read every column of a part, and put the text together.

    Args:
        found: The columns and the error pages, from read_columns.
        cache: The folder for the text of each column. It is made if it does
            not exist. A column with a file there is not read again.
        read: The function that reads a line image.
        jobs: The number of columns read at the same time.
        done: Called after each column is read, in the order they finish,
            on the thread that called read_part.
        long_s: The f to s change, or None to keep each f as read.

    Returns:
        The text of the part, and what the run did.

    Raises:
        ValueError: If jobs is less than 1.
        RuntimeError: If an image cannot be read, or if the reader fails.
    """
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, not {jobs}")
    cache.mkdir(parents=True, exist_ok=True)
    progress = Progress()
    todo = pending(found, cache)
    progress.cached = len(found.columns) - len(todo)

    def work(column: Column) -> Column:
        """Read one column into the cache.

        Args:
            column: The column.

        Returns:
            The same column, for the report.
        """
        _store(cache_file(cache, column), read_column(column, read))
        return column

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(work, column) for column in todo]
        # done is called here, on one thread, so it needs no lock. result()
        # raises the error of a failed column. The other columns that are
        # running finish and stay in the cache.
        for future in as_completed(futures):
            done(future.result())
            progress.read += 1

    return assemble(found, cache, progress, long_s), progress


def _order(found: Columns) -> Iterable[tuple[str, Column | None]]:
    """Give the columns and the error pages in reading order.

    Args:
        found: The columns and the error pages.

    Returns:
        Pairs of a label and its column, or a page label and None for an
        error page.
    """
    keyed: list[tuple[tuple[int, int, int], str, Column | None]] = [
        ((c.page, SIDE_ORDER[c.side], c.column), c.label, c) for c in found.columns
    ]
    # An error page has no sides, so its marker goes before the columns of
    # that page, which recto did not write.
    keyed += [((p, -1, 0), GAP.format(p), None) for p in found.errors]
    for _, label, column in sorted(keyed, key=lambda item: item[0]):
        yield label, column


def assemble(
    found: Columns,
    cache: Path,
    progress: Progress,
    long_s: LongS | None = None,
) -> str:
    """Put the text of a part together from the cache, and correct it.

    The cache keeps the lines as Tesseract read them. The hyphen joins and
    the f to s change are made only here, so a change to them does not need
    a new OCR run.

    Args:
        found: The columns and the error pages.
        cache: The cache folder. It must hold a file for each column.
        progress: Gets the line count, the empty lines, the joins and the
            f to s changes.
        long_s: The f to s change, or None to keep each f as read.

    Returns:
        The text of the part.

    Raises:
        FileNotFoundError: If a column has no cache file.
    """
    out: list[str] = []
    for label, column in _order(found):
        out.append(marker(label))
        if column is None:
            continue
        texts = cache_file(cache, column).read_text(encoding="utf-8").splitlines()
        for number, text in enumerate(texts, 1):
            if text == EMPTY_LINE:
                progress.empty.append(f"{column.label} line {number}")
        progress.lines += len(texts)
        out.extend(texts)
    out, progress.joins = join_hyphens(
        out,
        is_marker=is_marker,
        stops=lambda line: line == EMPTY_LINE or is_gap(line),
    )
    if long_s is not None:
        # After the joins, so that a word broken at a line end is whole.
        for index, line in enumerate(out):
            if not is_marker(line):
                out[index], changed = long_s.line(line)
                progress.long_s += changed
    return "\n".join(out) + "\n"
