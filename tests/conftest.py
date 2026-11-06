"""A synthetic column image for the tests of line finding and ground truth.

The real column images are too large to commit, and the line rules were
measured on them in recto. These tests check what verso adds: the cut around
each band, the sampling, and the files. So a column of dark blocks the size of
letters, set at the printed pitch, is enough.
"""

from __future__ import annotations

import numpy as np
import pytest

PITCH = 49
"""Px at 300 dpi. The printed line pitch of the book is 48 to 50 px."""

LINES = 12

TOP = 100
"""Px. The top of the first line of letters."""

LETTER = (24, 18)
"""Height and width of one block letter, in px. A full block has an area of
432 px, well over the 90 px that recto counts as a letter."""


def make_column(lines: int = LINES) -> np.ndarray:
    """Draw a white column with rows of black blocks the size of letters.

    Args:
        lines: The number of lines.

    Returns:
        The greyscale image, 300 dpi in scale.
    """
    height, width = TOP + lines * PITCH + 100, 900
    image = np.full((height, width), 255, np.uint8)
    tall, wide = LETTER
    for line in range(lines):
        top = TOP + line * PITCH
        for left in range(60, 840, wide + 6):
            image[top : top + tall, left : left + wide] = 0
    return image


@pytest.fixture
def column() -> np.ndarray:
    """Give the synthetic column.

    Returns:
        The image from make_column.
    """
    return make_column()
