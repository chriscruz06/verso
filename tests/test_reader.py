"""Check the reading of a part, the cache, and the text that is put together."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from recto.pngio import write_png

from conftest import LINES, make_column
from verso.manifest import Column, Columns
from verso.reader import EMPTY_LINE, marker, pending, read_part


def a_column(directory: Path, page: int, side: str, number: int) -> Column:
    """Write the synthetic column as a column image.

    Args:
        directory: The output folder.
        page: One-based PDF page.
        side: verso or recto.
        number: Zero-based column.

    Returns:
        The column.
    """
    label = f"p{page:04d}-{side}-c{number}"
    image = directory / f"{label}.png"
    write_png(image, make_column())
    return Column(label=label, image=image, page=page, side=side, column=number, dpi=300)


class Counter:
    """A stand in for Tesseract that counts its calls."""

    def __init__(self, empty_every: int = 0) -> None:
        """Make the reader.

        Args:
            empty_every: Give empty text for every line whose call number is
                a multiple of this. 0 never gives empty text.
        """
        self.calls = 0
        self.empty_every = empty_every

    def __call__(self, image: np.ndarray, dpi: int, workdir: Path) -> str:
        """Read one line image.

        Args:
            image: The line image.
            dpi: Its resolution.
            workdir: The folder for temporary files.

        Returns:
            A text with spacing that the normalisation must fix.
        """
        assert workdir.is_dir()
        self.calls += 1
        if self.empty_every and self.calls % self.empty_every == 0:
            return ""
        return "ex ore :  nisi"


def test_part_is_put_together_in_reading_order(tmp_path: Path) -> None:
    """Check markers, reading order, an error page, and normalised lines."""
    out = tmp_path / "out"
    out.mkdir()
    columns = [
        a_column(out, 10, "verso", 0),
        a_column(out, 9, "recto", 1),
        a_column(out, 9, "verso", 0),
    ]
    found = Columns(
        columns=sorted(columns, key=lambda c: (c.page, c.side != "verso", c.column)),
        errors=[10],
    )
    text, progress = read_part(found, cache=tmp_path / "cache", read=Counter(), jobs=2)
    lines = text.splitlines()

    markers = [line for line in lines if line.startswith("===")]
    assert markers == [
        marker("p0009-verso-c0"),
        marker("p0009-recto-c1"),
        marker("p0010 not read by recto"),
        marker("p0010-verso-c0"),
    ]
    body = [line for line in lines if not line.startswith("===")]
    assert len(body) == 3 * LINES
    assert set(body) == {"ex ore: nisi"}
    assert progress.read == 3 and progress.cached == 0 and progress.lines == 3 * LINES


def test_finished_columns_are_not_read_again(tmp_path: Path) -> None:
    """Check that a second run takes every column from the cache."""
    out = tmp_path / "out"
    out.mkdir()
    found = Columns(columns=[a_column(out, 9, "verso", 0), a_column(out, 9, "recto", 0)])
    cache = tmp_path / "cache"
    first, _ = read_part(found, cache=cache, read=Counter(), jobs=1)
    assert pending(found, cache) == []

    reader = Counter()
    second, progress = read_part(found, cache=cache, read=reader, jobs=1)
    assert reader.calls == 0
    assert progress.read == 0 and progress.cached == 2
    assert second == first


def test_a_part_column_in_the_cache_is_read_again(tmp_path: Path) -> None:
    """Check that only a whole cache file counts as a finished column."""
    out = tmp_path / "out"
    out.mkdir()
    column = a_column(out, 9, "verso", 0)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / f"{column.label}.part").write_text("half\n", encoding="utf-8")
    assert pending(Columns(columns=[column]), cache) == [column]


def test_empty_lines_are_kept_and_reported(tmp_path: Path) -> None:
    """Check that a line with no text is written as EMPTY_LINE, not dropped."""
    out = tmp_path / "out"
    out.mkdir()
    found = Columns(columns=[a_column(out, 9, "verso", 0)])
    text, progress = read_part(
        found, cache=tmp_path / "cache", read=Counter(empty_every=4), jobs=1
    )
    body = text.splitlines()[1:]
    assert len(body) == LINES
    assert body.count(EMPTY_LINE) == LINES // 4
    assert progress.empty[0] == "p0009-verso-c0 line 4"


def test_a_failed_column_stops_the_run(tmp_path: Path) -> None:
    """Check that a reader error is raised and leaves no cache file for it."""
    out = tmp_path / "out"
    out.mkdir()
    found = Columns(columns=[a_column(out, 9, "verso", 0)])

    def broken(image: np.ndarray, dpi: int, workdir: Path) -> str:
        """Fail as Tesseract would without its language data.

        Args:
            image: The line image.
            dpi: Its resolution.
            workdir: The folder for temporary files.

        Returns:
            Nothing. It always raises.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("no lat")

    cache = tmp_path / "cache"
    with pytest.raises(RuntimeError, match="no lat"):
        read_part(found, cache=cache, read=broken, jobs=1)
    assert pending(found, cache) == found.columns


def test_jobs_must_be_at_least_one(tmp_path: Path) -> None:
    """Check that a run with no workers is refused."""
    with pytest.raises(ValueError):
        read_part(Columns(), cache=tmp_path, read=Counter(), jobs=0)
