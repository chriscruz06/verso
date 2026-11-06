"""Check the sampling of lines and the files of the ground truth."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from recto.pngio import write_png

from conftest import LINES, make_column
from verso.groundtruth import draft, pick, stem
from verso.manifest import Column


def test_pick_spreads_over_the_column() -> None:
    """Check even spacing that takes the top part and the foot part."""
    assert pick(68, 4) == [8, 25, 42, 59]
    chosen = pick(68, 20)
    assert len(set(chosen)) == 20
    assert chosen == sorted(chosen)
    assert chosen[0] < 68 / 20 and chosen[-1] >= 68 - 68 / 20


def test_pick_takes_all_of_a_short_column() -> None:
    """Check that asking for more lines than there are gives every line."""
    assert pick(5, 20) == [0, 1, 2, 3, 4]


def test_pick_needs_at_least_one() -> None:
    """Check that a count under 1 is refused."""
    with pytest.raises(ValueError):
        pick(10, 0)


def a_column(tmp_path: Path) -> Column:
    """Write the synthetic column as a column image.

    Args:
        tmp_path: The test folder.

    Returns:
        The column.
    """
    image = tmp_path / "out" / "p0013-verso-c1.png"
    write_png(image, make_column())
    return Column(
        label="p0013-verso-c1", image=image, page=13, side="verso", column=1, dpi=300
    )


def fake_reader(image: np.ndarray, dpi: int) -> str:
    """Stand in for Tesseract.

    Args:
        image: The line image.
        dpi: Its resolution.

    Returns:
        A draft that names the image size.
    """
    return f"draft {image.shape[0]}x{image.shape[1]} {dpi}"


def test_pairs_are_written(tmp_path: Path) -> None:
    """Check one PNG and one .gt.txt for each picked line."""
    dest = tmp_path / "gt"
    report = draft([a_column(tmp_path)], count=4, dest=dest, read=fake_reader)
    assert report.written == 4 and report.kept == 0
    names = [stem("p0013-verso-c1", i + 1) for i in pick(LINES, 4)]
    for name in names:
        assert (dest / f"{name}.png").is_file()
        text = (dest / f"{name}.gt.txt").read_text(encoding="utf-8")
        assert text.startswith("draft ") and text.endswith("\n")


def test_corrected_text_is_not_written_again(tmp_path: Path) -> None:
    """Check that a second run keeps a corrected text and its image."""
    column, dest = a_column(tmp_path), tmp_path / "gt"
    draft([column], count=4, dest=dest, read=fake_reader)
    name = stem("p0013-verso-c1", pick(LINES, 4)[0] + 1)
    (dest / f"{name}.gt.txt").write_text("correcta\n", encoding="utf-8")

    report = draft([column], count=4, dest=dest, read=fake_reader)
    assert report.written == 0 and report.kept == 4
    assert (dest / f"{name}.gt.txt").read_text(encoding="utf-8") == "correcta\n"


def test_short_column_is_reported(tmp_path: Path) -> None:
    """Check that a column with fewer lines than asked is named."""
    report = draft([a_column(tmp_path)], count=50, dest=tmp_path / "gt", read=fake_reader)
    assert report.written == LINES
    assert report.short == [f"p0013-verso-c1 ({LINES} lines)"]
