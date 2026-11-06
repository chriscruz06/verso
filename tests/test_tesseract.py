"""Check the retry of an empty line read, without running Tesseract.

subprocess.run is replaced by a stand in that answers by page segmentation
mode, so the tests run where Tesseract is not installed, as in CI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from recto.ocrcheck import TesseractError

from verso import tesseract as module
from verso.tesseract import LINE_PSM, RAW_LINE_PSM, read_line


def fake_tesseract(
    monkeypatch: pytest.MonkeyPatch,
    answers: dict[int, tuple[int, str]],
) -> list[int]:
    """Replace subprocess.run with a stand in for Tesseract.

    Args:
        monkeypatch: The pytest fixture.
        answers: The exit status and the output for each mode.

    Returns:
        A list that gets each mode that was run, in order.
    """
    modes: list[int] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess:
        """Answer one call as Tesseract would.

        Args:
            command: The command line.
            **_: The other arguments of subprocess.run.

        Returns:
            The result for the mode in the command.
        """
        psm = int(command[command.index("--psm") + 1])
        modes.append(psm)
        status, output = answers[psm]
        return subprocess.CompletedProcess(command, status, output, "failed")

    monkeypatch.setattr(module.subprocess, "run", run)
    return modes


def line() -> np.ndarray:
    """Give a small white line image.

    Returns:
        The image.
    """
    return np.full((40, 200), 255, np.uint8)


def test_a_read_line_is_not_read_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check that mode 7 text is used, and mode 13 is not run."""
    modes = fake_tesseract(monkeypatch, {LINE_PSM: (0, "vitam.\n\f")})
    text = read_line(line(), tesseract="t", lang="lat", dpi=300, workdir=tmp_path)
    assert text == "vitam."
    assert modes == [LINE_PSM]


def test_an_empty_read_is_done_again_as_a_raw_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check that an empty mode 7 result is read again in mode 13."""
    answers = {LINE_PSM: (0, "\n\f"), RAW_LINE_PSM: (0, "casionem: in secundo\n")}
    modes = fake_tesseract(monkeypatch, answers)
    text = read_line(line(), tesseract="t", lang="lat", dpi=300, workdir=tmp_path)
    assert text == "casionem: in secundo"
    assert modes == [LINE_PSM, RAW_LINE_PSM]


def test_empty_in_both_modes_gives_empty_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check that a line with no text in either mode gives an empty string."""
    fake_tesseract(monkeypatch, {LINE_PSM: (0, ""), RAW_LINE_PSM: (0, "")})
    text = read_line(line(), tesseract="t", lang="lat", dpi=300, workdir=tmp_path)
    assert text == ""


def test_a_failed_run_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check that a Tesseract failure raises TesseractError with its message."""
    fake_tesseract(monkeypatch, {LINE_PSM: (1, "")})
    with pytest.raises(TesseractError, match="failed"):
        read_line(line(), tesseract="t", lang="lat", dpi=300, workdir=tmp_path)
