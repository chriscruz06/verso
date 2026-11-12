"""Read the column images that recto run wrote, in the reading order of the book.

Recto writes one folder for each PDF, with one PNG for each text column and a
manifest.jsonl with one row for each column image and each skipped page. The
rows are in reading order, except after recto run --resume, which appends the
pages it did again. Thus this module sorts the rows again: by page, then the
verso before the recto, then by column.

Only rows with status "column" give an image. A blank row has no image, and an
error row marks a page that recto could not do. Error rows are counted and
reported, because their pages are missing from the text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = "manifest.jsonl"

SIDE_ORDER = {"verso": 0, "recto": 1}
"""The verso of a spread comes before its recto in the book."""


class ManifestError(RuntimeError):
    """The manifest is missing or cannot be read."""


@dataclass(frozen=True)
class Column:
    """One column image and where it came from in the book."""

    label: str
    """The image name without .png, for example p0013-verso-c1."""

    image: Path
    page: int
    """The one-based PDF page."""

    side: str
    """verso or recto."""

    column: int
    """The zero-based reading order of the column on its page."""

    dpi: int


@dataclass
class Columns:
    """The column images of one recto output folder, in reading order."""

    columns: list[Column] = field(default_factory=list)
    errors: list[int] = field(default_factory=list)
    """The pages that recto could not do."""


def read_columns(directory: Path) -> Columns:
    """Read the manifest of one recto output folder.

    Args:
        directory: The folder that recto run wrote, for example out\\part1.

    Returns:
        The column images in reading order, and the pages with an error row.

    Raises:
        ManifestError: If the manifest is missing, if a line is not valid
            JSON, or if a column row has no image file.
    """
    path = directory / MANIFEST_NAME
    if not path.is_file():
        raise ManifestError(f"no {MANIFEST_NAME} in {directory}; run recto run first")

    result = Columns()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            # Recto writes each page in one write, so a bad line is the last
            # line of a run that stopped. A resume removes it.
            raise ManifestError(
                f"{path}, line {number}, is not valid JSON; "
                "run recto run --resume to finish the run"
            ) from exc

        status = row.get("status")
        if status == "error":
            result.errors.append(row["page"])
            continue
        if status != "column":
            continue

        image = directory / row["image"]
        if not image.is_file():
            raise ManifestError(f"{path}, line {number}: {image.name} is missing")
        result.columns.append(
            Column(
                label=row["label"],
                image=image,
                page=row["page"],
                side=row["side"],
                column=row["column"],
                dpi=row["dpi"],
            )
        )

    result.columns.sort(key=lambda c: (c.page, SIDE_ORDER[c.side], c.column))
    result.errors.sort()
    return result


def until(found: Columns, last: str) -> Columns:
    """Keep the columns up to the end of one page side.

    A part can hold more than one work. In part 3, Super Iohannem ends on
    p0036-verso, and the indexes and In Apocalypsim come after it.

    Args:
        found: The columns and the error pages, from read_columns.
        last: The last page side to keep, for example p0036-verso.

    Returns:
        The columns up to and including those of that side, and the error
        pages up to and including its page.

    Raises:
        ManifestError: If last is not a page side, or if it has no columns.
    """
    match = re.fullmatch(r"p(\d+)-(verso|recto)", last)
    if match is None:
        raise ManifestError(f"{last} is not a page side, for example p0036-verso")
    end = (int(match.group(1)), SIDE_ORDER[match.group(2)])
    columns = [c for c in found.columns if (c.page, SIDE_ORDER[c.side]) <= end]
    # A side with no columns is blank or was not done, so the run would end
    # at another place than the one given.
    if not any((c.page, SIDE_ORDER[c.side]) == end for c in columns):
        raise ManifestError(f"{last} has no column image in the manifest")
    return Columns(columns=columns, errors=[p for p in found.errors if p <= end[0]])
