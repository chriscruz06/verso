"""Read one line image with Tesseract.

Tesseract runs as a separate program, as in recto ocr-check, and recto's
find_tesseract and TesseractError are used again here. Each line goes to it
as a PNG file in a temporary folder, through recto's write_png, which writes
safely to a Windows path with characters outside ASCII.

Page segmentation mode 7 tells Tesseract that the image is one line of text.
On the damaged lines of part 1 p13 verso column 1, mode 7 on each line gave
readable drafts where mode 4 on the whole column gave noise or nothing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from recto.ocrcheck import TesseractError
from recto.pngio import write_png

LINE_PSM = 7
"""One line of text."""


def read_line(
    image: np.ndarray,
    *,
    tesseract: str,
    lang: str,
    dpi: int,
    workdir: Path,
) -> str:
    """Read one line image with Tesseract.

    Args:
        image: The greyscale line image.
        tesseract: The path of the tesseract program.
        lang: The Tesseract language, for example "lat".
        dpi: The resolution of the image.
        workdir: A folder for the temporary PNG file.

    Returns:
        The text that Tesseract read, without the line end. It can be empty.

    Raises:
        TesseractError: If Tesseract fails, for example because the language
            data is not installed.
    """
    path = workdir / "line.png"
    write_png(path, image)
    command = [tesseract, str(path), "stdout", "-l", lang]
    command += ["--psm", str(LINE_PSM), "--dpi", str(dpi)]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or f"exit status {result.returncode}"
        raise TesseractError(message)
    # Tesseract ends its text with a line end, and some versions add a form
    # feed after it.
    return result.stdout.strip("\n\f ")
