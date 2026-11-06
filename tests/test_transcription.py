"""Check the reading of the record and the check against its files."""

from __future__ import annotations

from pathlib import Path

import pytest

from verso.transcription import RECORD_NAME, TranscriptionError, read_record

HEAD = "file\ttext\tstatus\tnote"


def make_folder(directory: Path, rows: list[str], texts: dict[str, str]) -> None:
    """Write a record, an empty image for each text, and the .gt.txt files.

    Args:
        directory: The folder.
        rows: The rows of the record, without the head.
        texts: The text of each .gt.txt file, by file name stem.
    """
    (directory / RECORD_NAME).write_text(
        "\n".join([HEAD, *rows]) + "\n", encoding="utf-8"
    )
    for stem, text in texts.items():
        (directory / f"{stem}.png").write_bytes(b"")
        (directory / f"{stem}.gt.txt").write_text(text + "\n", encoding="utf-8")


def test_rows_in_use_are_read(tmp_path: Path) -> None:
    """Check status, note, a row without a note, and a DELETE row."""
    make_folder(
        tmp_path,
        [
            "a-l001.png\tcæli, & terræ\tOK\t",
            "a-l002.png\tcontemnens cum\tUNCERTAIN\tmay be eum",
            "a-l003.png\tvitam.\tOK",
            "a-l004.png\tvisione quando\tDELETE\tornament",
        ],
        {"a-l001": "cæli, & terræ", "a-l002": "contemnens cum", "a-l003": "vitam."},
    )
    entries = read_record(tmp_path)
    assert [e.name for e in entries] == ["a-l001", "a-l002", "a-l003"]
    assert entries[1].status == "UNCERTAIN" and entries[1].note == "may be eum"
    assert entries[2].note == ""


def test_text_that_drifted_is_an_error(tmp_path: Path) -> None:
    """Check that a .gt.txt file that differs from its row stops the read."""
    make_folder(tmp_path, ["a-l001.png\tesse\tOK\t"], {"a-l001": "effe"})
    with pytest.raises(TranscriptionError, match="does not match"):
        read_record(tmp_path)


def test_unknown_status_is_an_error(tmp_path: Path) -> None:
    """Check that a status the README does not define stops the read."""
    make_folder(tmp_path, ["a-l001.png\tesse\tMAYBE\t"], {"a-l001": "esse"})
    with pytest.raises(TranscriptionError, match="unknown status"):
        read_record(tmp_path)


def test_missing_text_file_is_an_error(tmp_path: Path) -> None:
    """Check that a row in use needs its .gt.txt file."""
    make_folder(tmp_path, ["a-l001.png\tesse\tOK\t"], {"a-l001": "esse"})
    (tmp_path / "a-l001.gt.txt").unlink()
    with pytest.raises(TranscriptionError, match="missing"):
        read_record(tmp_path)


def test_wrong_head_is_an_error(tmp_path: Path) -> None:
    """Check that a record with other columns stops the read."""
    (tmp_path / RECORD_NAME).write_text("file\ttext\n", encoding="utf-8")
    with pytest.raises(TranscriptionError, match="first line"):
        read_record(tmp_path)


def test_part1_record_matches_its_files() -> None:
    """Check the committed part 1 ground truth, so that a drift fails in CI."""
    folder = Path(__file__).parent.parent / "groundtruth" / "part1"
    entries = read_record(folder)
    assert len(entries) == 99
