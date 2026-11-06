"""Read the record of a hand transcription, and check it against its files.

A ground truth folder holds transcription.tsv, the hand transcription as it
was made, with the columns file, text, status and note. It also holds one
.gt.txt file for each line in use, with the same text. The record keeps the
status and the note, which the .gt.txt files cannot hold. The .gt.txt files
are the form that Tesseract training reads.

Two copies of one text can drift apart. Thus every read checks that each
.gt.txt file holds exactly the text of its row, and stops if one does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

RECORD_NAME = "transcription.tsv"

COLUMNS = ("file", "text", "status", "note")

STATUSES = frozenset({"OK", "BRACKET", "UNCERTAIN", "DELETE"})
"""The statuses that the README defines."""


class TranscriptionError(RuntimeError):
    """The record is missing, malformed, or does not match its files."""


@dataclass(frozen=True)
class Entry:
    """One row of the record."""

    image: Path
    text: str
    status: str
    note: str

    @property
    def name(self) -> str:
        """The file name stem, for example p0013-verso-c1-l002."""
        return self.image.stem


def read_record(directory: Path) -> list[Entry]:
    """Read the record of a ground truth folder and check its files.

    Rows with the status DELETE are left out, because their files are gone.

    Args:
        directory: The ground truth folder, for example groundtruth\\part1.

    Returns:
        The rows in use, in the order of the record.

    Raises:
        TranscriptionError: If the record is missing, a row is malformed, a
            status is unknown, an image is missing, or a .gt.txt file does not
            hold exactly the text of its row.
    """
    path = directory / RECORD_NAME
    if not path.is_file():
        raise TranscriptionError(f"no {RECORD_NAME} in {directory}")

    # utf-8-sig accepts a file that an editor saved with a byte order mark.
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or tuple(lines[0].split("\t")) != COLUMNS:
        raise TranscriptionError(f"{path}: the first line must be {' '.join(COLUMNS)}")

    entries = []
    for number, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        fields = line.split("\t")
        # A row without a note can end after the status.
        if len(fields) == 3:
            fields.append("")
        if len(fields) != 4:
            raise TranscriptionError(f"{path}, line {number}: expected 4 columns")
        name, text, status, note = fields
        if status not in STATUSES:
            raise TranscriptionError(f"{path}, line {number}: unknown status {status!r}")
        if status == "DELETE":
            continue

        image = directory / name
        if not image.is_file():
            raise TranscriptionError(f"{path}, line {number}: {name} is missing")
        truth = image.with_suffix(".gt.txt")
        if not truth.is_file():
            raise TranscriptionError(f"{path}, line {number}: {truth.name} is missing")
        written = truth.read_text(encoding="utf-8-sig").rstrip("\r\n")
        if written != text:
            raise TranscriptionError(
                f"{truth.name} does not match line {number} of {RECORD_NAME}"
            )
        entries.append(Entry(image=image, text=text, status=status, note=note))
    return entries
