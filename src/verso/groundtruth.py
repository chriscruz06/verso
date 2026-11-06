"""Write line images and OCR drafts for a hand transcription.

Accuracy can only be measured against lines that a person has checked. This
module cuts lines out of chosen columns and writes each one as a pair of files,
in the naming that Tesseract training uses:

    p0013-verso-c1-l039.png      the line image
    p0013-verso-c1-l039.gt.txt   the OCR draft, to correct by hand

The lines of a column are picked at even spacing, so that the top, the middle
and the foot of the column all appear in the sample.

A pair that already exists is never written again. Its text may be corrected,
and if the line finder changes later, a new image would not match the old
text. Thus a corrected line stays as it is, with the image it was read from.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from recto.pngio import read_png, write_png

from verso.lines import cut_line, find_lines
from verso.manifest import Column

LineReader = Callable[[np.ndarray, int], str]
"""Reads a line image at a given dpi and gives its text."""


@dataclass
class Report:
    """What one run wrote."""

    written: int = 0
    """New pairs."""

    kept: int = 0
    """Pairs that were there already and were not changed."""

    short: list[str] = field(default_factory=list)
    """Columns that had fewer lines than were asked for."""


def pick(total: int, count: int) -> list[int]:
    """Pick line positions at even spacing.

    Args:
        total: The number of lines in the column.
        count: The number of lines to pick.

    Returns:
        Zero-based positions, sorted and without repeats. All positions if
        count is not less than total.

    Raises:
        ValueError: If count is less than 1.
    """
    if count < 1:
        raise ValueError(f"count must be at least 1, not {count}")
    if count >= total:
        return list(range(total))
    # The middle of each of count equal parts, so no part is preferred.
    return [int((i + 0.5) * total / count) for i in range(count)]


def stem(label: str, number: int) -> str:
    """Give the file name stem of one line.

    Args:
        label: The label of the column, for example p0013-verso-c1.
        number: The one-based line number in the column.

    Returns:
        The stem, for example p0013-verso-c1-l039.
    """
    return f"{label}-l{number:03d}"


def draft(
    columns: list[Column],
    *,
    count: int,
    dest: Path,
    read: LineReader,
) -> Report:
    """Write line images and OCR drafts for some lines of each column.

    Args:
        columns: The columns to sample.
        count: The number of lines to take from each column.
        dest: The folder for the pairs. It is made if it does not exist.
        read: The function that reads a line image.

    Returns:
        What was written and what was kept.

    Raises:
        ValueError: If count is less than 1.
        RuntimeError: If an image cannot be read or written.
        recto.ocrcheck.TesseractError: If the reader fails on a line.
    """
    dest.mkdir(parents=True, exist_ok=True)
    report = Report()
    for column in columns:
        image = read_png(column.image)
        lines = find_lines(image, column.dpi)
        if len(lines) < count:
            report.short.append(f"{column.label} ({len(lines)} lines)")
        for position in pick(len(lines), count):
            line = lines[position]
            name = stem(column.label, line.number)
            png, text = dest / f"{name}.png", dest / f"{name}.gt.txt"
            if text.exists():
                report.kept += 1
                continue
            cut = cut_line(image, line, column.dpi)
            write_png(png, cut)
            # Written last, so that a stop between the two writes leaves no
            # text file, and the next run writes the pair again.
            text.write_text(read(cut, column.dpi) + "\n", encoding="utf-8")
            report.written += 1
    return report
