"""Find the lines of type in a column image, and cut each line out.

The lines come from recto's band_column, which applies the line rules that
were measured on this scan. Tesseract's own line finder was tried first, on
part 1 p13 verso column 1, and it failed on the bold, fused lines in the lower
half of that column: its line boxes overlapped, and some lines came out empty.
Recto's bands found every line of five part 1 columns, 65 to 68 lines each,
with a median spacing of 48.5 to 49.5 px, which is the printed line pitch.

A band holds only the body of the letters, about 24 px of a 49 px pitch. The
cut for a line goes to the middle of the gap above it and the middle of the
gap below it, so that the ascenders and the descenders are in the cut. The
first and the last line have no neighbour on one side, so the cut goes a fixed
distance past the band on that side.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from recto.stages.bands import band_column

REFERENCE_DPI = 300
"""The resolution of every length below."""

END_REACH = 16
"""How far past the band the cut goes, above the first line and below the
last line. About the height of an ascender or a descender."""

OVERLAP = 4
"""How far past the middle of a gap the cut goes. A long descender can cross
the middle of the gap, and a cut that clips it changes the letter."""

SIDE_REACH = 12
"""How far past the left and the right of the band the cut goes."""

BORDER = 10
"""White border put around each cut. Tesseract reads a line better when the
ink does not touch the edge of the image."""


@dataclass(frozen=True)
class Line:
    """The box of one line of type in a column image."""

    number: int
    """The one-based position of the line in the column, from the top."""

    top: int
    bottom: int
    """One past the last row."""

    left: int
    right: int
    """One past the last column."""


def _px(length: int, dpi: int) -> int:
    """Convert a length at REFERENCE_DPI to pixels at another resolution.

    Args:
        length: The length at REFERENCE_DPI.
        dpi: The resolution of the image.

    Returns:
        The length in pixels, at least 1.
    """
    return max(1, round(length * dpi / REFERENCE_DPI))


def find_lines(image: np.ndarray, dpi: int) -> list[Line]:
    """Find the box of each line of type in a column image.

    Args:
        image: The greyscale column image.
        dpi: The resolution of the image.

    Returns:
        The line boxes, from the top. The boxes of two lines next to each
        other overlap by twice OVERLAP rows.
    """
    bands = band_column(image, dpi)
    height, width = image.shape[:2]
    reach, overlap, side = _px(END_REACH, dpi), _px(OVERLAP, dpi), _px(SIDE_REACH, dpi)

    lines = []
    for index, band in enumerate(bands):
        if index > 0:
            top = (bands[index - 1].bottom + band.top) // 2 - overlap
        else:
            top = band.top - reach
        if index + 1 < len(bands):
            bottom = (band.bottom + bands[index + 1].top) // 2 + overlap
        else:
            bottom = band.bottom + reach
        lines.append(
            Line(
                number=index + 1,
                top=max(0, top),
                bottom=min(height, bottom),
                left=max(0, band.left - side),
                right=min(width, band.right + side),
            )
        )
    return lines


def cut_line(image: np.ndarray, line: Line, dpi: int) -> np.ndarray:
    """Cut one line out of a column image, with a white border.

    Args:
        image: The greyscale column image.
        line: The box of the line.
        dpi: The resolution of the image.

    Returns:
        The line image.
    """
    crop = image[line.top : line.bottom, line.left : line.right]
    border = _px(BORDER, dpi)
    return cv2.copyMakeBorder(
        crop, border, border, border, border, cv2.BORDER_CONSTANT, value=255
    )
