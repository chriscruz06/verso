"""Read one line image with Tesseract.

Tesseract runs as a separate program, as in recto ocr-check, and recto's
find_tesseract and TesseractError are used again here. Each line goes to it
as a PNG file in a temporary folder, through recto's write_png, which writes
safely to a Windows path with characters outside ASCII.

Page segmentation mode 7 tells Tesseract that the image is one line of text.
On the damaged lines of part 1 p13 verso column 1, mode 7 on each line gave
readable drafts where mode 4 on the whole column gave noise or nothing.

Mode 7 still checks if the image holds a line of text, and it can give an
empty result. Tesseract 5.5.3 on the laptop gave empty results for 5 of the 99
part 1 ground truth lines. Three of them are clean lines: p20 recto c2 l42,
p45 recto c1 l55 and p45 recto c1 l62. Tesseract 5.3.4 read all three. An
empty result loses a line from the text without a sign, so an empty read is
done again in mode 13, raw line, which does not make that check. Mode 13
read the three clean lines with 5.5.3. It gave noise for the two lines that
the other side of the leaf shows through, which is better than no text,
because the noise shows that a line is there. Mode 13 is not used for every
line: on 5.3.4 its CER over the 99 lines was 21.25 percent, against 18.76
percent for mode 7.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from recto.ocrcheck import TesseractError
from recto.pngio import write_png

LINE_PSM = 7
"""One line of text."""

RAW_LINE_PSM = 13
"""One raw line, for a line that LINE_PSM reads as empty."""


def _run(path: Path, *, tesseract: str, lang: str, psm: int, dpi: int) -> str:
    """Run Tesseract on one image file.

    Args:
        path: The PNG file.
        tesseract: The path of the tesseract program.
        lang: The Tesseract language.
        psm: The page segmentation mode.
        dpi: The resolution of the image.

    Returns:
        The text, without the line end. It can be empty.

    Raises:
        TesseractError: If Tesseract fails.
    """
    command = [tesseract, str(path), "stdout", "-l", lang]
    command += ["--psm", str(psm), "--dpi", str(dpi)]
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
        The text that Tesseract read, without the line end. It is empty only
        if both modes give no text.

    Raises:
        TesseractError: If Tesseract fails, for example because the language
            data is not installed.
    """
    path = workdir / "line.png"
    write_png(path, image)
    text = _run(path, tesseract=tesseract, lang=lang, psm=LINE_PSM, dpi=dpi)
    if text:
        return text
    return _run(path, tesseract=tesseract, lang=lang, psm=RAW_LINE_PSM, dpi=dpi)
