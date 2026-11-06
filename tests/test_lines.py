"""Check the cut around each line of a column."""

from __future__ import annotations

import numpy as np

from conftest import LETTER, LINES, PITCH, TOP
from verso.lines import BORDER, END_REACH, cut_line, find_lines


def test_every_line_is_found(column: np.ndarray) -> None:
    """Check one box for each line, numbered from 1, in order."""
    lines = find_lines(column, 300)
    assert [line.number for line in lines] == list(range(1, LINES + 1))
    assert all(a.top < b.top for a, b in zip(lines, lines[1:]))


def test_each_box_holds_its_whole_line(column: np.ndarray) -> None:
    """Check that no box clips the letters of its own line."""
    tall, _ = LETTER
    for index, line in enumerate(find_lines(column, 300)):
        letters_top = TOP + index * PITCH
        assert line.top <= letters_top
        assert line.bottom >= letters_top + tall


def test_no_box_reaches_the_next_line_body(column: np.ndarray) -> None:
    """Check that a box stops short of the letters of the line under it."""
    lines = find_lines(column, 300)
    for index, line in enumerate(lines[:-1]):
        assert line.bottom <= TOP + (index + 1) * PITCH


def test_end_lines_reach_past_the_band(column: np.ndarray) -> None:
    """Check the fixed reach above the first line and below the last."""
    tall, _ = LETTER
    lines = find_lines(column, 300)
    assert lines[0].top <= TOP - END_REACH // 2
    last_bottom = TOP + (LINES - 1) * PITCH + tall
    assert lines[-1].bottom >= last_bottom + END_REACH // 2


def test_cut_has_a_white_border(column: np.ndarray) -> None:
    """Check that the ink of a cut line does not touch the image edge."""
    line = find_lines(column, 300)[3]
    cut = cut_line(column, line, 300)
    assert cut.shape == (
        line.bottom - line.top + 2 * BORDER,
        line.right - line.left + 2 * BORDER,
    )
    edges = np.concatenate([cut[0], cut[-1], cut[:, 0], cut[:, -1]])
    assert (edges == 255).all()
    assert (cut == 0).any()
