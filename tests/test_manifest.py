"""Check that the manifest is read in the reading order of the book."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verso.manifest import MANIFEST_NAME, ManifestError, read_columns


def write_manifest(directory: Path, rows: list[dict]) -> None:
    """Write a manifest and an empty image file for each column row.

    Args:
        directory: The folder.
        rows: The rows, in file order.
    """
    lines = []
    for row in rows:
        if row.get("image"):
            (directory / row["image"]).write_bytes(b"")
        lines.append(json.dumps(row))
    (directory / MANIFEST_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def column_row(page: int, side: str, column: int) -> dict:
    """Make a column row as recto run writes it, without the stages.

    Args:
        page: One-based PDF page.
        side: verso or recto.
        column: Zero-based column.

    Returns:
        The row.
    """
    label = f"p{page:04d}-{side}-c{column}"
    return {
        "image": f"{label}.png",
        "label": label,
        "page": page,
        "side": side,
        "column": column,
        "status": "column",
        "dpi": 300,
    }


def test_rows_are_sorted_into_reading_order(tmp_path: Path) -> None:
    """Check page, then verso before recto, then column, as after a resume."""
    write_manifest(
        tmp_path,
        [
            column_row(10, "recto", 1),
            column_row(9, "recto", 0),
            column_row(10, "verso", 0),
            column_row(9, "verso", 1),
            column_row(9, "verso", 0),
            column_row(10, "recto", 0),
        ],
    )
    labels = [c.label for c in read_columns(tmp_path).columns]
    assert labels == [
        "p0009-verso-c0",
        "p0009-verso-c1",
        "p0009-recto-c0",
        "p0010-verso-c0",
        "p0010-recto-c0",
        "p0010-recto-c1",
    ]


def test_blank_rows_are_skipped_and_error_rows_reported(tmp_path: Path) -> None:
    """Check that a blank page gives no column and an error page is listed."""
    write_manifest(
        tmp_path,
        [
            {"image": None, "label": "p0002-verso", "page": 2, "status": "blank"},
            {"image": None, "label": "p0003", "page": 3, "status": "error"},
            column_row(4, "verso", 0),
        ],
    )
    found = read_columns(tmp_path)
    assert [c.label for c in found.columns] == ["p0004-verso-c0"]
    assert found.errors == [3]


def test_missing_manifest_is_an_error(tmp_path: Path) -> None:
    """Check that a folder without a manifest gives a clear error."""
    with pytest.raises(ManifestError, match="recto run"):
        read_columns(tmp_path)


def test_bad_line_is_an_error(tmp_path: Path) -> None:
    """Check that a cut last line, from a stopped run, gives a clear error."""
    write_manifest(tmp_path, [column_row(4, "verso", 0)])
    with (tmp_path / MANIFEST_NAME).open("a", encoding="utf-8") as file:
        file.write('{"image": "p0005')
    with pytest.raises(ManifestError, match="--resume"):
        read_columns(tmp_path)


def test_missing_image_is_an_error(tmp_path: Path) -> None:
    """Check that a row whose image file is gone gives a clear error."""
    write_manifest(tmp_path, [column_row(4, "verso", 0)])
    (tmp_path / "p0004-verso-c0.png").unlink()
    with pytest.raises(ManifestError, match="missing"):
        read_columns(tmp_path)
